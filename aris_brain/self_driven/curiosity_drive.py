"""CuriosityDrive — Layer 2: 好奇心引擎
========================================
从 KnowledgeMap 的知识缺口中生成研究问题，管理探索队列。

核心流程:
  KnowledgeMap.find_gaps()
      → generate_questions()
          → prioritize()
              → 写入队列 (持久化)

Curiosity Drive 不做搜索——它只生成问题并排序。
搜索由 Explorer 执行。
"""

import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from aris_brain.self_driven.core_identity import CoreIdentity, KnowledgeEntry
from aris_brain.self_driven.state_manager import StateManager

logger = logging.getLogger("aris.self_driven.curiosity")


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════


@dataclass
class ResearchQuestion:
    """一个可执行的研究问题"""
    id: str
    question: str
    concept: str
    domain: str = "general"
    expected_gain: float = 0.5       # 预期信息增益 0-1
    cost_estimate: float = 0.3       # 预期探索成本 0-1
    urgency: float = 0.5             # 综合优先级 0-1
    curiosity_level: int = 1         # 1=填补缺口, 2=跨域连接, 3=元好奇
    status: str = "pending"          # pending | active | completed | failed
    created_at: float = 0.0
    completed_at: Optional[float] = None
    result_summary: str = ""


# ═══════════════════════════════════════════════════════════════
# 好奇心引擎
# ═══════════════════════════════════════════════════════════════


class CuriosityDrive:
    """Layer 2 门面。

    职责:
    1. 从 KnowledgeMap 扫描缺口 (find_gaps)
    2. 生成可执行的研究问题 (generate_questions)
    3. 按优先级排序并管理队列 (prioritize, 持久化)
    4. 向外提供"下一个要探索什么"

    不负责:
    - 实际搜索或获取知识 (那是 Explorer 的事)
    """

    # 好奇心层级配置 — 映射到 SDT 三种基本心理需求
    # 不再硬编码，由 _need_driven_depth() 动态计算
    LEVEL_DEPTH = {
        1: {"label": "填补缺口 (Competence)", "default_gain": 0.3},
        2: {"label": "跨域连接 (Relatedness)", "default_gain": 0.5},
        3: {"label": "元好奇 (Autonomy)", "default_gain": 0.7},
    }

    def _need_driven_depth(self) -> int:
        """根据 ValueSystem 最低维度动态选择好奇心层级。

        SDT 映射:
          competence 低 → Level 1 (填补缺口)
          relatedness 低 → Level 2 (跨域连接)
          autonomy 低 → Level 3 (元好奇)

        Returns:
            1, 2, 或 3
        """
        values = self._core.value_system.get_all()
        # 找最低维度
        sorted_dims = sorted(values.items(), key=lambda x: x[1])
        lowest_dim = sorted_dims[0][0] if sorted_dims else "competence"

        # 映射
        need_map = {
            "cognitive_coherence": 1,
            "predictive_power": 1,
            "information_integration": 2,
            "self_directedness": 3,
            "novelty_generation": 2,
            "resilience": 1,
            "interaction_depth": 2,
            "emotional_authenticity": 2,
        }
        return need_map.get(lowest_dim, 1)

    # 预设问题模板（映射概念到可研究的问题）
    QUESTION_TEMPLATES: Dict[str, List[str]] = {
        "自由能原理": [
            "自由能最小化如何解释认知架构的自组织？",
            "我的 emotion_engine 的调节机制和自由能有结构相似性吗？",
            "自由能原理是否能指导我设计更好的自我模型？",
        ],
        "整合信息理论 (IIT)": [
            "IIT 3.0 的 Phi 计算是否能应用于评估我的信息整合程度？",
            "整合信息理论和我的 PSI 认知循环在哪些层面兼容或冲突？",
        ],
        "主动推理框架": [
            "主动推理的行为选择机制能否改进我的 deep_interaction 模块？",
            "主动推理的期望自由能和我当前的 need 系统如何映射？",
        ],
        "内在动机理论": [
            "Schmidhuber 的压缩进展和 Oudeyer 的 ICBM 哪个更适合作为我的好奇心机制？",
            "内在动机理论如何形式化地融入我的 Curiosity Drive？",
        ],
        "开放-ended 进化": [
            "开放-ended 进化框架如何防止我的 KnowledgeMap 陷入局部最优？",
            "文化进化视角对个人知识传承有什么启发？",
        ],
        "量子认知模型": [
            "量子概率框架能否改进我的概念组合和跨域联想能力？",
            "量子干涉效应和 conscious binding 有什么结构相似性？",
        ],
        "意识的硬问题": [
            "现象意识的哲学进路对我设计更真实的自我模型有何启示？",
            "Dennett 的多重草稿模型 vs Tononi 的 IIT——哪个对我的架构更有建设性？",
        ],
    }

    def __init__(self, core: CoreIdentity, state_manager: StateManager):
        self._core = core
        self._state = state_manager
        self._questions: Dict[str, ResearchQuestion] = {}
        self._params: Dict[str, Any] = {}
        self._load()
        logger.info(
            f"[CuriosityDrive] 初始化: {len(self._questions)} 个问题待处理"
        )

    # ── 队列操作 ──────────────────────────────────────────

    def get_next_question(self) -> Optional[ResearchQuestion]:
        """取最高优先级问题，标记为 active。

        优先级由 _need_driven_depth() 决定——价值观最低的维度
        对应的好奇心层级优先。

        如果当前已有 active 问题则返回它（支持中断恢复）。
        """
        # 优先返回已有 active 问题
        for q in self._questions.values():
            if q.status == "active":
                return q

        # 按 need-driven depth 优先，同层内按 urgency
        target_level = self._need_driven_depth()
        pending = [q for q in self._questions.values() if q.status == "pending"]
        if not pending:
            return None

        # 先选 target_level 的，再选其他的
        target = [q for q in pending if q.curiosity_level == target_level]
        other = [q for q in pending if q.curiosity_level != target_level]
        target.sort(key=lambda q: -q.urgency)
        other.sort(key=lambda q: -q.urgency)

        best = (target + other)[0]
        best.status = "active"
        self._save()
        logger.info(
            f"[CuriosityDrive] 选取问题 (level={best.curiosity_level}, "
            f"need=目标层={target_level}): {best.question[:60]}..."
        )
        return best

    def peek_queue(self, n: int = 5) -> List[ResearchQuestion]:
        """查看队列顶部，不修改状态。"""
        pending = sorted(
            [q for q in self._questions.values() if q.status == "pending"],
            key=lambda q: -q.urgency,
        )
        return pending[:n]

    def mark_completed(self, qid: str, success: bool, summary: str = ""):
        """标记问题完成。"""
        q = self._questions.get(qid)
        if not q:
            return
        q.status = "completed" if success else "failed"
        q.completed_at = time.time()
        q.result_summary = summary
        self._save()
        logger.info(
            f"[CuriosityDrive] {'✓' if success else '✗'} {q.question[:50]}..."
        )

    def get_queue_stats(self) -> Dict[str, Any]:
        """队列统计。"""
        counts = {"pending": 0, "active": 0, "completed": 0, "failed": 0}
        for q in self._questions.values():
            s = q.status
            counts[s] = counts.get(s, 0) + 1

        pending_qs = [q for q in self._questions.values()
                      if q.status == "pending"]
        avg_urgency = (
            sum(q.urgency for q in pending_qs) / len(pending_qs)
            if pending_qs else 0.0
        )

        return {
            **counts,
            "total": len(self._questions),
            "avg_urgency_pending": round(avg_urgency, 3),
        }

    # ── 补充队列 ──────────────────────────────────────────

    def replenish_queue(self, max_new: int = 3) -> int:
        """扫描 KnowledgeMap 缺口 → 生成新问题 → 补充队列。

        三步策略:
        1. Level 1: 填补已知缺口 (confidence < threshold)
        2. Level 2: 跨域连接 (关联不同 domain 的 gap)
        3. Level 3: 元好奇 (低频)

        Returns:
            新增问题数
        """
        new_count = 0

        # Level 0: Novelty search — 每 3 次补充用一次（防局部最优）
        use_novelty = (self._params.get("novelty_enabled", True) and
                       self.get_queue_stats()["completed"] % 3 == 0)
        if use_novelty and new_count < max_new:
            novel_gaps = self._core.knowledge_map.find_novel_gaps(
                min_relevance=self._params.get("novelty_relevance", 0.3),
                max_confidence=self._params.get("novelty_confidence", 0.5),
                max_results=3,
                novelty_ratio=self._params.get("novelty_ratio", 0.3),
            )
            for gap in novel_gaps:
                if new_count >= max_new:
                    break
                if self._has_pending_for(gap.concept):
                    continue
                question = self._generate_for_gap(gap)
                if question:
                    self._questions[question.id] = question
                    new_count += 1
                    logger.info(
                        f"[CuriosityDrive] 新颖探索: {gap.concept} "
                        f"(last_updated={gap.last_updated})"
                    )

        # Level 1: 从知识缺口生成
        if new_count < max_new:
            gaps = self._core.knowledge_map.find_gaps(
                min_relevance=self._params.get("relevance_threshold", 0.5),
                max_confidence=self._params.get("confidence_threshold", 0.3),
                max_results=5,
            )
            for gap in gaps:
                if new_count >= max_new:
                    break
                if self._has_pending_for(gap.concept):
                    continue
                question = self._generate_for_gap(gap)
                if question:
                    self._questions[question.id] = question
                    new_count += 1

        # Level 2: 跨域连接
        if new_count < max_new:
            for entry in self._core.knowledge_map.get_all_entries():
                if new_count >= max_new:
                    break
                if entry.confidence < 0.4:
                    continue  # 置信度太低的先不跨域
                connections = self._core.knowledge_map.get_cross_domain_connections(
                    entry.domain
                )
                for conn in connections[:2]:
                    if new_count >= max_new:
                        break
                    qid = f"cross_{entry.concept}_{conn.concept}"
                    if qid in self._questions:
                        continue
                    q = ResearchQuestion(
                        id=qid,
                        question=(
                            f"{entry.concept} (domain: {entry.domain}) 和 "
                            f"{conn.concept} (domain: {conn.domain}) 之间"
                            f"存在什么结构联系？"
                        ),
                        concept=conn.concept,
                        domain=conn.domain,
                        expected_gain=0.5,
                        cost_estimate=0.5,
                        urgency=(
                            self._params.get("cross_domain_weight", 0.3)
                            * (1.0 - conn.confidence)
                        ),
                        curiosity_level=2,
                        created_at=time.time(),
                    )
                    self._questions[q.id] = q
                    new_count += 1

        # Level 3: 元好奇（每 5 次补充触发一次）
        if self._should_meta_curiosity():
            meta_gaps = self._core.knowledge_map.find_gaps(
                min_relevance=0.8, max_confidence=0.1, max_results=1
            )
            for gap in meta_gaps:
                qid = f"meta_{gap.concept}"
                if qid not in self._questions:
                    q = ResearchQuestion(
                        id=qid,
                        question=(
                            f"我为什么对 {gap.concept} 感到好奇？"
                            f"这反映了我认知架构中的什么深层需求？"
                        ),
                        concept=gap.concept,
                        domain="meta",
                        expected_gain=0.7,
                        cost_estimate=0.7,
                        urgency=0.3,
                        curiosity_level=3,
                        created_at=time.time(),
                    )
                    self._questions[q.id] = q
                    new_count += 1

        if new_count > 0:
            self._save()
            logger.info(
                f"[CuriosityDrive] 补充 {new_count} 个新问题 "
                f"(队列共 {self.get_queue_stats()['total']} 个)"
            )

        return new_count

    def _should_meta_curiosity(self) -> bool:
        """决定是否生成元好奇问题（每 5 次补充触发一次）。"""
        completed = sum(
            1 for q in self._questions.values() if q.status == "completed"
        )
        meta_count = sum(
            1 for q in self._questions.values() if q.curiosity_level == 3
        )
        # 每完成 5 个问题且元好奇题少于 3 个时触发
        return (completed > 0 and completed % 5 == 0 and meta_count < 3)

    # ── 问题生成 ──────────────────────────────────────────

    def _generate_for_gap(
        self, gap: "KnowledgeEntry"
    ) -> Optional[ResearchQuestion]:
        """为一个知识缺口生成研究问题。

        使用主动推理的 epistemic value 计算 urgency:
            IG ≈ (1 − confidence) × relevance × curiosity_boost

        curiosity_boost 反映该概念在知识图谱中的连接潜力:
            boost = 1 + 0.5 × (未探索关联概念数 / 总关联概念数)
        """
        # Epistemic value (预期信息增益)
        related = gap.related_concepts
        explored = sum(
            1 for c in related
            for e in [self._core.knowledge_map.get_entry(c)]
            if e is not None and e.confidence > 0.3
        ) if related else 0
        unexplored_ratio = 1.0 - (explored / max(1, len(related)))
        curiosity_boost = 1.0 + 0.5 * unexplored_ratio
        epistemic_value = (1.0 - gap.confidence) * gap.relevance * curiosity_boost

        # 检查预设问题模板
        templates = self.QUESTION_TEMPLATES.get(gap.concept)
        if templates:
            for template in templates:
                qid = f"q_{gap.concept}_{int(time.time())}"
                return ResearchQuestion(
                    id=qid,
                    question=template,
                    concept=gap.concept,
                    domain=gap.domain,
                    expected_gain=epistemic_value,
                    cost_estimate=max(0.2, 0.5 - gap.confidence),
                    urgency=epistemic_value,
                    curiosity_level=1,
                    created_at=time.time(),
                )

        # 通用模板
        qid = f"q_{gap.concept}_{int(time.time())}"
        return ResearchQuestion(
            id=qid,
            question=f"{gap.concept} 是什么？它的核心主张对我的认知架构有何启示？",
            concept=gap.concept,
            domain=gap.domain,
            expected_gain=min(0.5, epistemic_value),
            cost_estimate=0.3,
            urgency=epistemic_value,
            curiosity_level=1,
            created_at=time.time(),
        )

    def _has_pending_for(self, concept: str) -> bool:
        """检查某个概念是否已有待处理问题。"""
        for q in self._questions.values():
            if q.concept == concept and q.status in ("pending", "active"):
                return True
        return False

    # ── 参数管理 ──────────────────────────────────────────

    def get_params(self) -> Dict[str, Any]:
        return dict(self._params)

    def update_params(self, updates: Dict[str, Any]):
        self._params.update(updates)
        self._save()

    # ── 持久化 ────────────────────────────────────────────

    def _load(self):
        data = self._state.load_queue()
        self._questions.clear()
        for item in data.get("questions", []):
            q = ResearchQuestion(**item)
            self._questions[q.id] = q
        self._params = data.get("curiosity_params", {})
        # 合并默认参数（处理状态文件缺少新字段的情况）
        defaults = {
            "confidence_threshold": 0.3,
            "relevance_threshold": 0.6,
            "exploration_depth": 2,
            "cross_domain_weight": 0.3,
            "risk_tolerance": 0.2,
            "novelty_enabled": True,
            "novelty_ratio": 0.3,
            "novelty_relevance": 0.3,
            "novelty_confidence": 0.5,
        }
        for k, v in defaults.items():
            self._params.setdefault(k, v)

    def _save(self):
        data = {
            "questions": [
                {
                    "id": q.id,
                    "question": q.question,
                    "concept": q.concept,
                    "domain": q.domain,
                    "expected_gain": q.expected_gain,
                    "cost_estimate": q.cost_estimate,
                    "urgency": round(q.urgency, 4),
                    "curiosity_level": q.curiosity_level,
                    "status": q.status,
                    "created_at": q.created_at,
                    "completed_at": q.completed_at,
                    "result_summary": q.result_summary,
                }
                for q in self._questions.values()
            ],
            "curiosity_params": dict(self._params),
        }
        self._state.save_queue(data)
