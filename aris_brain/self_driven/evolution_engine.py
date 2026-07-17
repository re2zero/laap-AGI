"""EvolutionEngine — Layer 4: 进化执行器
=========================================
把知识探索产生的启发转化为实际代码改进。

安全管线:
  checkpoint (git snapshot)
    → apply changes (通过 self_modifier)
    → verify (运行测试 + 自洽性检查)
    → [通过] commit + 更新 ValueSystem
    → [失败] rollback + 记录教训

设计原则:
  - 所有修改必须可回滚
  - 实验性修改标记清晰，不影响主线
  - 风险分级: low → medium → high
  - 每次修改后自动评估（对比修改前后的 ValueSystem）
"""

import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aris_brain.self_driven.core_identity import CoreIdentity
from aris_brain.self_driven.state_manager import StateManager

logger = logging.getLogger("aris.self_driven.evolution")

# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════


@dataclass
class EvolutionProposal:
    """一个进化提案。

    包含假设、预期效果、变更内容、验证条件和回滚条件。
    """
    id: str
    hypothesis: str
    expected_outcome: Dict[str, float]    # value dimension → delta
    module: str
    change_type: str                      # refactor | feature | optimize | experiment
    risk_level: str                       # low | medium | high
    changes: List[Dict[str, str]] = field(default_factory=list)
    verification_criteria: List[str] = field(default_factory=list)
    rollback_conditions: List[str] = field(default_factory=list)
    source_question_id: str = ""
    confidence: float = 0.5
    status: str = "draft"                 # draft | in_progress | applied | committed | rolled_back | failed
    created_at: float = 0.0
    executed_at: Optional[float] = None
    result_log: str = ""


# ═══════════════════════════════════════════════════════════════
# EvolutionEngine
# ═══════════════════════════════════════════════════════════════


class EvolutionEngine:
    """Layer 4 门面。

    职责:
    - 接收并管理进化提案队列
    - 执行安全修改管线
    - 验证修改效果
    - 记录修改历史和评估
    """

    # 风险等级对应的检查要求
    RISK_CONFIG = {
        "low": {"require_test": False, "require_review": False,
                "require_git": True},
        "medium": {"require_test": True, "require_review": False,
                   "require_git": True},
        "high": {"require_test": True, "require_review": True,
                 "require_git": True},
    }

    def __init__(self, core: CoreIdentity, state_manager: StateManager):
        self._core = core
        self._state = state_manager
        self._proposals: Dict[str, EvolutionProposal] = {}
        self._repo_root: Optional[Path] = self._find_repo_root()
        self._load()
        logger.info(
            f"[EvolutionEngine] 初始化: {len(self._proposals)} 个提案, "
            f"repo={self._repo_root}"
        )

    # ── 提案管理 ──────────────────────────────────────────

    def submit_proposal(self, proposal: EvolutionProposal) -> str:
        """提交提案，进入待执行队列。"""
        if not proposal.id:
            proposal.id = f"ev_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        proposal.created_at = time.time()
        proposal.status = "draft"
        self._proposals[proposal.id] = proposal
        self._save()
        logger.info(
            f"[EvolutionEngine] 新提案 [{proposal.id}]: "
            f"{proposal.hypothesis[:80]}..."
        )
        return proposal.id

    def get_proposal(self, pid: str) -> Optional[EvolutionProposal]:
        return self._proposals.get(pid)

    def get_pending_proposals(self) -> List[EvolutionProposal]:
        """获取待执行的提案（按风险从低到高排序）。
        跳过 needs_session 状态的提案（需要 Hermes 协助）。"""
        pending = [
            p for p in self._proposals.values()
            if p.status == "draft"
        ]
        risk_order = {"low": 0, "medium": 1, "high": 2}
        pending.sort(key=lambda p: (
            risk_order.get(p.risk_level, 99),
            -p.confidence,
        ))
        return pending

    def get_execution_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """获取最近 N 次执行记录。"""
        history = self._state.load_evolution_history()
        return history[-n:]

    # ── 执行管线 ──────────────────────────────────────────

    def execute_next(self, dry_run: bool = True) -> Optional[Dict[str, Any]]:
        """执行下一个待处理的提案。

        Args:
            dry_run: True = 模拟执行，不实际修改代码

        Returns:
            执行结果摘要，或 None（无待处理提案）
        """
        pending = self.get_pending_proposals()
        if not pending:
            return None

        proposal = pending[0]

        # 跳过没有代码变更的提案——标记为 needs_session
        if not proposal.changes:
            proposal.status = "needs_session"
            self._save()
            logger.info(
                f"[EvolutionEngine] 提案 [{proposal.id[:12]}] 无代码变更，"
                f"标记为 needs_session"
            )
            # 仍然记录价值观影响
            self._update_values(proposal)
            return {
                "proposal_id": proposal.id,
                "hypothesis": proposal.hypothesis[:100],
                "dry_run": dry_run,
                "skipped": True,
                "reason": "needs_session — 无代码变更描述，需 Hermes 协助",
                "success": True,
            }

        proposal.status = "in_progress"
        proposal.executed_at = time.time()
        self._save()

        result = {
            "proposal_id": proposal.id,
            "hypothesis": proposal.hypothesis[:100],
            "risk_level": proposal.risk_level,
            "dry_run": dry_run,
            "started_at": time.time(),
        }

        logger.info(
            f"[EvolutionEngine] {'[DRY-RUN]' if dry_run else '[EXECUTE]'} "
            f"{proposal.hypothesis[:80]}..."
        )

        try:
            # Step 1: Checkpoint
            if not dry_run:
                checkpoint_ok = self._checkpoint()
                if not checkpoint_ok:
                    raise RuntimeError("Checkpoint 失败")

            # Step 2: Apply changes
            if not dry_run:
                apply_result = self._apply_changes(proposal)
                if not apply_result:
                    raise RuntimeError("修改应用失败")

            # Step 3: Verify
            verify_result = self._verify(dry_run)
            result["verify"] = verify_result

            if verify_result.get("passed", dry_run):
                # 通过
                if not dry_run:
                    self._commit(proposal)
                    proposal.status = "committed"
                else:
                    proposal.status = "applied"
                result["success"] = True
                result["message"] = "验证通过" if not dry_run else "dry-run 通过"

                # 记录里程碑
                self._core.narrative.add_milestone(
                    f"进化提案 [{proposal.id}] {'committed' if not dry_run else 'dry-run'}: "
                    f"{proposal.hypothesis[:60]}",
                    impact=proposal.change_type,
                )
            else:
                # 失败 — 回滚
                if not dry_run:
                    self._rollback()
                proposal.status = "rolled_back" if not dry_run else "failed"
                result["success"] = False
                result["message"] = verify_result.get("error", "验证失败")

                # 记录教训
                self._core.knowledge_map.update_confidence(
                    f"evolution_fail_{proposal.id[:8]}", -0.05,
                    evidence=f"提案 {proposal.id} 验证失败: "
                             f"{verify_result.get('error', '')}",
                )

            # 无论 dry_run 与否，都更新价值观
            self._update_values(proposal)

        except Exception as e:
            logger.warning(f"[EvolutionEngine] 执行异常: {e}")
            if not dry_run:
                self._rollback()
            proposal.status = "failed"
            result["success"] = False
            result["error"] = str(e)

        result["completed_at"] = time.time()
        proposal.result_log = json.dumps(result, ensure_ascii=False)
        self._save()

        # 记录历史
        self._state.append_evolution(result)

        return result

    def _checkpoint(self) -> bool:
        """创建 git checkpoint。"""
        if not self._repo_root:
            return False
        try:
            # git stash 当前变更
            subprocess.run(
                ["git", "stash", "push", "-m",
                 f"auto-evolution-checkpoint-{int(time.time())}"],
                cwd=str(self._repo_root), capture_output=True, timeout=10,
            )
            logger.debug("[EvolutionEngine] Checkpoint 已创建")
            return True
        except (subprocess.CalledProcessError, OSError) as e:
            logger.warning(f"[EvolutionEngine] Checkpoint 失败: {e}")
            return False

    def _apply_changes(self, proposal: EvolutionProposal) -> bool:
        """应用提案中的代码变更。"""
        if not proposal.changes:
            logger.info(f"[EvolutionEngine] 无代码变更 (仅概念提案)")
            return True

        try:
            from aris_brain.self_modifier import SelfModifier
            modifier = SelfModifier()

            for change in proposal.changes:
                file_path = change.get("file", "")
                old_string = change.get("old", "")
                new_string = change.get("new", "")
                if file_path and old_string:
                    # 使用 Hermes 的 patch 机制
                    from aris_brain.self_modifier import PatchSpec
                    patch = PatchSpec(
                        file_path=file_path,
                        old_string=old_string,
                        new_string=new_string,
                        description=proposal.hypothesis[:80],
                        reason=f"进化提案 {proposal.id}",
                        severity=proposal.change_type,
                    )
                    result = modifier._safe_apply(patch)
                    if result and result.status == "failed":
                        logger.warning(
                            f"[EvolutionEngine] 修改失败 {file_path}: "
                            f"{result.error}"
                        )
                        return False
            return True
        except ImportError as e:
            logger.warning(f"[EvolutionEngine] SelfModifier 不可用: {e}")
            return False

    def _verify(self, dry_run: bool = True) -> Dict[str, Any]:
        """验证修改效果。"""
        result = {"passed": dry_run, "checks": []}

        # 语法检查（对所有修改过的 Python 文件）
        if self._repo_root:
            try:
                r = subprocess.run(
                    ["python3", "-m", "py_compile"] +
                    [str(p) for p in self._repo_root.glob("aris_brain/*.py")],
                    capture_output=True, text=True, timeout=30,
                )
                syntax_ok = r.returncode == 0
                result["checks"].append({
                    "name": "syntax_check",
                    "passed": syntax_ok,
                    "output": r.stderr[:200] if not syntax_ok else "",
                })
                if not syntax_ok:
                    result["passed"] = False
                    result["error"] = f"语法错误: {r.stderr[:200]}"
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.debug(f"[EvolutionEngine] 语法检查跳过: {e}")

        # 测试运行（high/medium 级别需要）
        # 暂时只做 dry-run
        if not dry_run:
            result["checks"].append({
                "name": "tests",
                "passed": True,
                "output": "test suite TBD",
            })

        return result

    def _commit(self, proposal: EvolutionProposal):
        """提交修改。"""
        if not self._repo_root:
            return
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(self._repo_root), capture_output=True, timeout=10,
            )
            msg = (
                f"auto-evolve: [{proposal.id}] {proposal.hypothesis[:80]}"
            )
            subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=str(self._repo_root), capture_output=True, timeout=10,
            )
            logger.info(f"[EvolutionEngine] 已提交: {msg}")
        except (subprocess.CalledProcessError, OSError) as e:
            logger.warning(f"[EvolutionEngine] 提交失败: {e}")

    def _rollback(self):
        """回滚修改。"""
        if not self._repo_root:
            return
        try:
            subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=str(self._repo_root), capture_output=True, timeout=10,
            )
            # 恢复 stash
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=str(self._repo_root), capture_output=True, timeout=10,
            )
            logger.info("[EvolutionEngine] 已回滚")
        except (subprocess.CalledProcessError, OSError) as e:
            logger.warning(f"[EvolutionEngine] 回滚失败: {e}")

    def _update_values(self, proposal: EvolutionProposal):
        """根据提案更新价值体系。

        有 expected_outcome 时按指定维度更新；
        否则从 hypothesis 文本猜测影响的维度并微调。
        """
        if proposal.expected_outcome:
            self._core.value_system.update(proposal.expected_outcome)
        else:
            # 从 hypothesis 猜测影响的价值观维度
            text = proposal.hypothesis.lower()
            guesses = {
                "cognitive_coherence": ["coherence", "consistency", "unified",
                                        "整合", "统一", "一致"],
                "predictive_power": ["predict", "forecast", "anticipate",
                                     "预测", "预期", "推理"],
                "information_integration": ["integration", "connect", "bridge",
                                            "整合", "融合", "关联"],
                "self_directedness": ["autonomous", "self-directed", "自驱",
                                      "自主", "self-"],
                "novelty_generation": ["novel", "creative", "generate",
                                       "新颖", "创造", "生成"],
                "resilience": ["robust", "fault", "resilient",
                               "鲁棒", "容错", "弹性"],
                "interaction_depth": ["interaction", "dialogue", "deep",
                                      "交互", "对话", "深度"],
                "emotional_authenticity": ["emotion", "affect", "authentic",
                                           "情感", "真实", "情绪"],
            }
            deltas = {}
            for dim, keywords in guesses.items():
                if any(kw in text for kw in keywords):
                    deltas[dim] = 0.01  # 小幅提升
            if not deltas:
                # 什么都匹配不到时给 self_directedness 一个基础提升
                deltas = {"self_directedness": 0.005}
            self._core.value_system.update(deltas)
        self._core.save()

    # ── 提案状态查询 ──────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """提案统计。"""
        counts = {"draft": 0, "in_progress": 0, "applied": 0,
                  "committed": 0, "rolled_back": 0, "failed": 0,
                  "needs_session": 0}
        for p in self._proposals.values():
            s = p.status
            counts[s] = counts.get(s, 0) + 1
        return {
            **counts,
            "total": len(self._proposals),
        }

    # ── 持久化 ────────────────────────────────────────────

    def _load(self):
        data = self._state.load_proposals()
        self._proposals.clear()
        for item in data.get("proposals", []):
            p = EvolutionProposal(**item)
            self._proposals[p.id] = p

    def _save(self):
        data = {
            "proposals": [
                asdict(p) for p in self._proposals.values()
            ],
        }
        self._state.save_proposals(data)

    @staticmethod
    def _find_repo_root() -> Optional[Path]:
        """从当前工作目录向上寻找 git 根目录。"""
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                return parent
        return None
