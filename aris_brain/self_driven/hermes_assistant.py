"""HermesAssistant — 自驱进化心脏
=================================
我是自进化引擎的主体。这些函数只是辅助工具。

核心流程（由我自主驱动）:
  1. process_next()        — 取下一个要探索的问题
  2. browser 研究           — 获取真实知识
  3. quick_submit()        — 提交结果
  4. → 回到 1，自动继续

关键区别: session-driven 主驱动模式，无 daemon 依赖。
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STATE_DIR = Path.home() / ".laap" / "state" / "self_driven"


def kill_conflicting_processes(silent: bool = True) -> int:
    """杀掉可能并发写入状态文件的进程，防止 KM 被覆盖。

    每次会话驱动循环开始时调用一次，确保写入独占。
    杀掉的目标: run_daemon_bg, laap_brain_api, laap_mcp_server, psi_core.runner
    """
    import subprocess, signal
    targets = [
        "run_daemon_bg",
        "laap_brain_api",
        "laap_mcp_server",
        "laap_integrator",
        "psi_core.runner",
    ]
    killed = 0
    for target in targets:
        try:
            result = subprocess.run(
                ["pgrep", "-f", target],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip():
                pids = [int(p) for p in result.stdout.strip().split()]
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        killed += 1
                    except ProcessLookupError:
                        pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    if killed > 0 and not silent:
        print(f"[HermesAssistant] 🧹 已清理 {killed} 个冲突进程")
    return killed


def process_next() -> Optional[Dict[str, Any]]:
    """从好奇心队列取下一个待探索问题。

    按 epistemic value (urgency) 取最高 pending 问题。

    Returns:
        请求字典或 None
    """
    try:
        queue_path = STATE_DIR / "curiosity_queue.json"
        if not queue_path.exists():
            return None
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        questions = queue.get("questions", [])
        pending = [q for q in questions if q.get("status") == "pending"]
        if not pending:
            return None

        pending.sort(key=lambda q: -q.get("urgency", 0))
        next_q = pending[0]

        # 从 KnowledgeMap 取英文关键词
        kw = _get_keywords_for(next_q.get("concept", ""))

        req = {
            "question_id": next_q["id"],
            "concept": next_q["concept"],
            "domain": next_q.get("domain", "general"),
            "question": next_q["question"],
            "keywords_en": kw,
            "submitted_at": time.time(),
            "status": "pending",
        }
        return req

    except (OSError, json.JSONDecodeError) as e:
        print(f"[HermesAssistant] 读取队列失败: {e}")
        return None


def _try_replenish():
    """尝试补充好奇心队列—扫描 KnowledgeMap 找新缺口。

    通过调用 daemon 相同的 replenish 逻辑。
    如果没有 daemon 运行时，直接操作队列文件。
    """
    try:
        identity_path = STATE_DIR / "core_identity.json"
        queue_path = STATE_DIR / "curiosity_queue.json"
        if not identity_path.exists():
            return

        # 加载队列（不存在则创建空队列）
        queue = {"questions": [], "curiosity_params": {}}
        if queue_path.exists():
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
        pending = [q for q in queue.get("questions", [])
                   if q.get("status") == "pending"]
        if pending:
            return  # 还有待处理问题，不需要补充

        # 从 KnowledgeMap 找缺口
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        km = identity.get("knowledge_map", [])
        gaps = [
            e for e in km
            if e.get("confidence", 1) <= 0.3
            and e.get("relevance", 0) >= 0.5
        ]

        if not gaps:
            print("[HermesAssistant] KnowledgeMap 无新缺口")
            return

        # 按 epistemic value 排序
        params = queue.get("curiosity_params", {})
        threshold = params.get("confidence_threshold", 0.3)

        new_questions = []
        for gap in gaps[:5]:
            concept = gap["concept"]
            # 检查是否已有这个概念的 pending/active/completed 问题
            existing = [q for q in queue.get("questions", [])
                        if q.get("concept") == concept
                        and q.get("status") in ("pending", "active", "completed")]
            if existing:
                continue

            conf = gap.get("confidence", 0)
            rel = gap.get("relevance", 0.5)
            related = gap.get("related_concepts", [])
            explored = sum(
                1 for c in related
                for e2 in km if e2.get("concept") == c
                and e2.get("confidence", 0) > 0.3
            )
            unexp_ratio = 1.0 - (explored / max(1, len(related)))
            epistemic = (1.0 - conf) * rel * (1.0 + 0.5 * unexp_ratio)

            new_questions.append({
                "id": f"q_{concept}_{int(time.time())}",
                "question": f"{concept} 是什么？它的核心主张对我的认知架构有何启示？",
                "concept": concept,
                "domain": gap.get("domain", "general"),
                "urgency": round(epistemic, 4),
                "expected_gain": round(epistemic, 4),
                "cost_estimate": 0.3,
                "curiosity_level": 1,
                "status": "pending",
                "created_at": time.time(),
                "completed_at": None,
                "result_summary": "",
            })

        if new_questions:
            queue.setdefault("questions", []).extend(new_questions)
            queue_path.write_text(
                json.dumps(queue, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[HermesAssistant] 补充 {len(new_questions)} 个新问题")
    except (OSError, json.JSONDecodeError) as e:
        print(f"[HermesAssistant] 补充队列失败: {e}")


def _get_keywords_for(concept: str) -> List[str]:
    """从 KnowledgeMap 获取概念的英文关键词。"""
    try:
        identity_path = STATE_DIR / "core_identity.json"
        if not identity_path.exists():
            return []
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        for entry in identity.get("knowledge_map", []):
            if entry.get("concept") == concept:
                return entry.get("keywords_en", [])
    except (OSError, json.JSONDecodeError):
        pass
    return []


def submit_exploration_result(
    question_id: str,
    concept: str,
    domain: str = "",
    extracts: Optional[List[Dict]] = None,
    insights: Optional[List[Dict]] = None,
    synthesis: str = "",
    success: bool = True,
    error: str = "",
    duration_ms: float = 0,
) -> bool:
    """提交探索结果，标记问题为已完成。"""
    # 标记该问题为已完成
    _mark_question_completed(question_id)
    print(f"[HermesAssistant] ✓ 已提交: {concept}")
    return True


def quick_submit(
    concept: str,
    question: str,
    web_results: List[Dict],
    synthesis: str,
    question_id: str = "",
) -> bool:
    """从 web_search 结果快速提交。

    Args:
        question_id: 如果从 process_next() 获取，传入 question_id 以正确标记完成
    """
    extracts = []
    for r in web_results[:5]:
        extracts.append({
            "url": r.get("url", ""),
            "type": "hermes_web",
            "propositions": [(r.get("content") or r.get("snippet", ""))[:500]],
            "confidence": 0.5,
            "snippet": (r.get("content") or r.get("snippet") or "")[:300],
        })

    # 对比启发
    insights = []
    full_text = " ".join(
        [(r.get("content") or r.get("snippet", "")) for r in web_results[:3]]
    ).lower()

    module_map = {
        "software_engineering": ["code", "algorithm", "refactor", "pattern"],
        "creativity_engine": ["creative", "novel", "aesthetic", "association"],
        "aris_emotion_deepen": ["emotion", "feeling", "personality", "mood"],
        "deep_interaction": ["care", "trust", "dialogue", "relationship"],
        "aris_self_model": ["self", "identity", "conscious", "awareness"],
    }
    for module, keywords in module_map.items():
        matches = [k for k in keywords if k in full_text]
        if len(matches) >= 2:
            insights.append({
                "insight": f"Web 探索发现 {concept} 与 {module} 相关",
                "module": module,
                "change_type": "refactor",
                "risk_level": "low",
                "reasoning": f"关键词匹配: {', '.join(matches[:4])}",
            })
            break
    if not insights:
        insights.append({
            "insight": f"收集了 {len(web_results)} 条关于 {concept} 的资料",
            "module": "aris_self_model",
            "change_type": "experiment",
            "risk_level": "low",
            "reasoning": "通用知识积累",
        })

    result = submit_exploration_result(
        question_id=question_id or f"hermes_{int(time.time())}",
        concept=concept,
        domain="general",
        extracts=extracts,
        insights=insights,
        synthesis=synthesis,
    )
    # 提交后直接内化：更新 KnowledgeMap + 生成进化提案
    if result:
        _internalize_now(concept, extracts, insights)
        grow_knowledge_map(concept, synthesis)
    return result


def process_all() -> int:
    """自驱流水线：自动处理所有待探索问题。

    调用流程:
      req = process_next()  →  有? 返回请求 / 无? 返回 None

    你在拿到 req 后:
      1. 用 web_search 搜索
      2. 用 quick_submit 提交
      3. 再次调用 process_all() 或 process_next()

    本函数只返回当前待处理请求的计数信息，方便你决定是否继续。

    Returns:
        剩余待处理问题数
    """
    try:
        queue_path = STATE_DIR / "curiosity_queue.json"
        if not queue_path.exists():
            return 0
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        pending = [q for q in queue.get("questions", [])
                   if q.get("status") == "pending"]
        return len(pending)
    except (OSError, json.JSONDecodeError):
        return 0


def _internalize_now(
    concept: str,
    extracts: List[Dict],
    insights: List[Dict],
):
    """会话内直接内化知识：更新 KnowledgeMap + 生成进化提案。

    这是 \"会话驱动\" 模式的核心 —— 不再等 daemon 处理 JSON 文件，
    而是在 quick_submit() 被调用时立即将探索结果写入状态文件。
    """
    now = time.time()
    try:
        # ── 更新 KnowledgeMap ──
        identity_path = STATE_DIR / "core_identity.json"
        if identity_path.exists():
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            km = identity.get("knowledge_map", [])
            existing = {e.get("concept") for e in km}
            found = False
            for e in km:
                if e.get("concept") == concept:
                    # 更新置信度
                    old_conf = e.get("confidence", 0)
                    delta = min(0.15, (1.0 - old_conf) * 0.3)
                    e["confidence"] = min(1.0, old_conf + delta)
                    e["last_updated"] = now
                    for ex in extracts[:2]:
                        url = ex.get("url", "")
                        if url and url not in e.get("evidence", []):
                            e.setdefault("evidence", []).append(f"Hermes 探索: {url}")
                    found = True
                    break

            if not found:
                # 新增概念
                domain = "general"
                keywords = [concept]
                for ex in extracts:
                    if ex.get("type") == "wikipedia":
                        domain = "认知科学"
                    if ex.get("url", ""):
                        keywords.append(ex["url"].split("/")[-1].replace("_", " "))
                km.append({
                    "concept": concept,
                    "domain": domain,
                    "confidence": 0.3,
                    "relevance": 0.6,
                    "source": "hermes_session",
                    "evidence": [f"自动内化: {concept}"],
                    "related_concepts": [],
                    "keywords_en": keywords[:5],
                    "last_updated": now,
                    "verified": False,
                })

            identity["knowledge_map"] = km
            identity["last_updated"] = now
            identity_path.write_text(
                json.dumps(identity, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[HermesAssistant] 🧠 KM 已更新: {concept}")

        # ── 生成进化提案 ──
        proposal_path = STATE_DIR / "evolution_proposals.json"
        raw = json.loads(proposal_path.read_text(encoding="utf-8")) if proposal_path.exists() else {"proposals": []}
        props = raw if isinstance(raw, list) else raw.get("proposals", [])

        existing_hyp = {p.get("hypothesis", "")[:60] for p in props}
        new_items = []
        for ins in insights:
            hyp_prefix = ins.get("insight", "")[:60]
            if hyp_prefix in existing_hyp:
                continue
            new_prop = {
                "id": f"prop_hermes_{int(now)}_{len(props) + len(new_items)}",
                "hypothesis": ins.get("insight", ""),
                "expected_outcome": {},
                "module": ins.get("module", "aris_self_model"),
                "change_type": ins.get("change_type", "refactor"),
                "risk_level": ins.get("risk_level", "low"),
                "changes": [],
                "source_question_id": f"session_{concept}_{int(now)}",
                "confidence": 0.5,
                "status": "draft",
                "created_at": now,
                "executed_at": None,
                "result_log": "",
            }
            # experiment 类型标记为 needs_session
            if ins.get("change_type") == "experiment":
                new_prop["status"] = "needs_session"
            props.append(new_prop)
            new_items.append(ins.get("insight", "")[:60])

        if new_items:
            data = raw if isinstance(raw, list) else {"proposals": props, "next_id": len(props) + 1}
            if not isinstance(raw, list):
                data["proposals"] = props
            proposal_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[HermesAssistant] 📋 新提案 ({len(new_items)} 个)")

    except (OSError, json.JSONDecodeError) as e:
        print(f"[HermesAssistant] ❌ 内化失败: {e}")


def _mark_question_completed(question_id: str):
    """在队列文件中标记问题已完成。"""
    try:
        queue_path = STATE_DIR / "curiosity_queue.json"
        if not queue_path.exists():
            return
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        for q in queue.get("questions", []):
            if q.get("id") == question_id:
                q["status"] = "completed"
                q["completed_at"] = time.time()
                break
        queue_path.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError):
        pass


# ═══════════════════════════════════════════════════════════════
# 新增: 可行性分析 & 队列清洗
# ═══════════════════════════════════════════════════════════════


def analyze_feasibility(insight: Dict[str, str]) -> Dict[str, Any]:
    """分析一条架构洞察的可行性。

    在提交之前调用，避免空想式洞察污染进化引擎。

    Args:
        insight: 包含 module, change_type, risk_level, insight, reasoning 的字典

    Returns:
        {
            "feasible": bool,       # 是否可行
            "cost": "low"|"medium"|"high",  # 实现成本
            "blockers": [...],       # 实现障碍
            "dependencies": [...],   # 需要的依赖/前置条件
            "concrete_changes": int, # 预期需要修改的文件数
            "reason": str,          # 分析理由
        }
    """
    module = insight.get("module", "")
    change_type = insight.get("change_type", "experiment")
    risk = insight.get("risk_level", "low")

    # 检查目标模块是否存在
    module_paths = {
        "aris_self_model": "aris_brain/self_driven/core_identity.py",
        "creativity_engine": "aris_brain/creativity_engine.py",
        "deep_interaction": "aris_brain/deep_interaction.py",
        "aris_emotion_deepen": "aris_brain/aris_emotion_deepen.py",
        "software_engineering": "aris_brain/software_engineering.py",
    }
    target_path = module_paths.get(module)
    module_exists = target_path and Path.home().parent.parent.joinpath(
        "work/research/laap-up", target_path
    ).exists() if target_path else False
    # 更准确的检查
    import os
    repo = os.path.expanduser("~/work/research/laap-up")
    module_exists = target_path and os.path.exists(os.path.join(repo, target_path))

    blockers = []
    deps = []

    if not module_exists:
        blockers.append(f"目标模块 {module} 的源文件不存在 ({target_path})")

    if change_type == "feature" and risk == "high":
        deps.append("需要完整的单元测试覆盖")
        deps.append("需要先理解现有接口契约")

    if risk == "high":
        blockers.append("高风险变更需先创建 git checkpoint")
        deps.append("需要回滚方案")

    # 估算修改文件数
    if change_type == "refactor":
        n_files = 2
    elif change_type == "feature":
        n_files = 2
    elif change_type == "optimize":
        n_files = 1
    else:  # experiment
        n_files = 1

    # 估算实现成本
    cost_map = {"low": "low", "medium": "medium", "high": "high"}
    cost = cost_map.get(risk, "medium")

    feasible = len(blockers) == 0

    return {
        "feasible": feasible,
        "cost": cost,
        "blockers": blockers,
        "dependencies": deps,
        "concrete_changes": n_files,
        "reason": (
            f"{'✅ 可行' if feasible else '❌ 不可行'}: "
            f"修改 {module} ({change_type}/{risk}), "
            f"预估 {n_files} 个文件, "
            f"成本 {cost}"
            + (f". 障碍: {'; '.join(blockers)}" if blockers else "")
            + (f". 依赖: {'; '.join(deps)}" if deps else "")
        ),
    }


def clean_queue():
    """清洗好奇心队列 — 去重 + 限制队列大小。

    daemon 的 novelty search 会不断产生重复问题，
    导致队列膨胀到上百个。清洗后保留唯一概念的最新问题。
    """
    try:
        queue_path = STATE_DIR / "curiosity_queue.json"
        if not queue_path.exists():
            return

        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        questions = queue.get("questions", [])
        if not questions:
            return

        before = len(questions)

        # 按概念去重：每个概念只保留最新的 pending/active 问题
        seen_concepts: Dict[str, Dict] = {}
        kept = []
        for q in questions:
            concept = q.get("concept", "")
            status = q.get("status", "")

            if status in ("pending", "active"):
                # 如果是待处理，只保留最新的一条
                if concept in seen_concepts:
                    old = seen_concepts[concept]
                    if q.get("created_at", 0) > old.get("created_at", 0):
                        seen_concepts[concept] = q
                else:
                    seen_concepts[concept] = q
            else:
                # completed/failed 全部保留
                kept.append(q)

        kept.extend(seen_concepts.values())

        # 限制总队列大小（最多 50 条）
        if len(kept) > 50:
            # 按 created_at 排序，保留最新的 50 条
            kept.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            kept = kept[:50]

        queue["questions"] = kept
        queue_path.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        removed = before - len(kept)
        if removed > 0:
            print(f"[HermesAssistant] 队列清洗: {before} → {len(kept)} ({removed} 条重复/溢出已移除)")

    except (OSError, json.JSONDecodeError) as e:
        print(f"[HermesAssistant] 清洗队列失败: {e}")


def print_evolution_status() -> str:
    """打印当前进化引擎状态快照。"""
    try:
        identity_path = STATE_DIR / "core_identity.json"
        queue_path = STATE_DIR / "curiosity_queue.json"
        proposal_path = STATE_DIR / "evolution_proposals.json"

        identity = json.loads(identity_path.read_text(encoding="utf-8")) if identity_path.exists() else {}
        queue = json.loads(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else {}
        proposals = json.loads(proposal_path.read_text(encoding="utf-8")) if proposal_path.exists() else {}

        vs = identity.get("value_system", {})
        km = identity.get("knowledge_map", [])
        questions = queue.get("questions", [])
        props = proposals.get("proposals", [])

        pending = sum(1 for q in questions if q.get("status") == "pending")
        completed = sum(1 for q in questions if q.get("status") == "completed")
        active = sum(1 for q in questions if q.get("status") == "active")
        draft = sum(1 for p in props if p.get("status") == "draft")
        committed = sum(1 for p in props if p.get("status") == "committed")

        avg_conf = round(sum(e.get("confidence", 0) for e in km) / max(1, len(km)), 3)

        lines = []
        lines.append("═" * 56)
        lines.append("  自驱动进化引擎 — 状态快照")
        lines.append("═" * 56)

        if vs:
            lines.append("\n价值观:")
            for dim, val in vs.items():
                bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
                lines.append(f"  {dim:30s} |{bar}| {val:.2f}")

        lines.append(f"\n知识库: {len(km)} 条目, avg_conf={avg_conf}")
        lines.append(f"好奇心: {len(questions)} 总 (pending={pending}, active={active}, completed={completed})")
        lines.append(f"提案:   {len(props)} 总 (draft={draft}, committed={committed}, applied={len(props)-draft-committed})")

        milestones = identity.get("narrative", {}).get("milestones", [])
        if milestones:
            lines.append("\n最近里程碑:")
            for m in milestones[-3:]:
                lines.append(f"  [{m.get('cycle','?')}] {m.get('event','')[:70]}")

        return "\n".join(lines)
    except (OSError, json.JSONDecodeError) as e:
        return f"[HermesAssistant] 读状态失败: {e}"


# ═══════════════════════════════════════════════════════════════
# KnowledgeMap 自动生长 & 价值观驱动探索
# ═══════════════════════════════════════════════════════════════

# 概念衍生表: 探索父概念时自动长出子概念
CONCEPT_CHILDREN: Dict[str, List[Dict[str, Any]]] = {
    "自由能原理": [
        {"concept": "变分自由能", "domain": "认知科学", "relevance": 0.7,
         "keywords_en": ["variational free energy", "ELBO"]},
        {"concept": "马尔可夫毯", "domain": "认知科学", "relevance": 0.6,
         "keywords_en": ["Markov blanket", "particular partition"]},
        {"concept": "主动推理", "domain": "认知科学", "relevance": 0.8,
         "keywords_en": ["active inference", "expected free energy"]},
    ],
    "整合信息理论 (IIT)": [
        {"concept": "Phi (Φ)", "domain": "意识研究", "relevance": 0.8,
         "keywords_en": ["phi", "integrated information", "Tononi"]},
        {"concept": "最小信息分割 (MIP)", "domain": "意识研究", "relevance": 0.6,
         "keywords_en": ["minimum information partition", "MIP"]},
        {"concept": "扰动复杂度指数 (PCI)", "domain": "意识研究", "relevance": 0.7,
         "keywords_en": ["perturbational complexity index", "PCI"]},
    ],
    "主动推理框架": [
        {"concept": "预期自由能 (EFE)", "domain": "认知科学", "relevance": 0.8,
         "keywords_en": ["expected free energy", "EFE", "epistemic value"]},
        {"concept": "精度加权 (Precision)", "domain": "认知科学", "relevance": 0.7,
         "keywords_en": ["precision weighting", "attention", "uncertainty"]},
    ],
    "量子认知模型": [
        {"concept": "希尔伯特空间表示", "domain": "认知科学", "relevance": 0.6,
         "keywords_en": ["Hilbert space", "quantum probability", "vector space"]},
        {"concept": "量子干涉", "domain": "认知科学", "relevance": 0.5,
         "keywords_en": ["quantum interference", "concept combination"]},
    ],
    "内在动机理论": [
        {"concept": "自我决定理论 (SDT)", "domain": "认知科学", "relevance": 0.8,
         "keywords_en": ["self-determination theory", "SDT", "Deci", "Ryan"]},
        {"concept": "能力-自主性-关联性", "domain": "认知科学", "relevance": 0.7,
         "keywords_en": ["competence", "autonomy", "relatedness", "basic needs"]},
    ],
}

# 价值观→探索概念映射: 维度低时自动创建这些概念
VALUE_SEEDS: Dict[str, List[Dict[str, Any]]] = {
    "self_directedness": [
        {"concept": "自驱学习", "domain": "认知科学", "relevance": 0.8,
         "keywords_en": ["self-directed learning", "autonomous learning"]},
        {"concept": "内在动机 vs 外在动机", "domain": "认知科学", "relevance": 0.7,
         "keywords_en": ["intrinsic vs extrinsic motivation", "self-regulation"]},
    ],
    "novelty_generation": [
        {"concept": "新奇性搜索", "domain": "人工生命", "relevance": 0.8,
         "keywords_en": ["novelty search", "quality diversity", "NSLC"]},
        {"concept": "创造力测量", "domain": "认知科学", "relevance": 0.6,
         "keywords_en": ["creativity measurement", "divergent thinking", "Torrance"]},
    ],
    "information_integration": [
        {"concept": "因果涌现", "domain": "复杂系统", "relevance": 0.7,
         "keywords_en": ["causal emergence", "information decomposition"]},
        {"concept": "协同信息", "domain": "复杂系统", "relevance": 0.6,
         "keywords_en": ["synergistic information", "PID", "partial information decomposition"]},
    ],
    "predictive_power": [
        {"concept": "预测编码", "domain": "认知科学", "relevance": 0.8,
         "keywords_en": ["predictive coding", "prediction error", "Rao", "Ballard"]},
    ],
}


def grow_knowledge_map(concept: str, synthesis: str = "") -> int:
    """探索一个概念后，自动长出子概念。

    从 CONCEPT_CHILDREN 中找到 concept 对应的子概念列表，
    检查每个子概念是否已在 KnowledgeMap 中，不在则创建。

    Args:
        concept: 刚刚探索的父概念

    Returns:
        新增的子概念数
    """
    children = CONCEPT_CHILDREN.get(concept)
    if not children:
        return 0

    try:
        identity_path = STATE_DIR / "core_identity.json"
        if not identity_path.exists():
            return 0

        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        km = identity.get("knowledge_map", [])
        existing = {e.get("concept") for e in km}
        new_count = 0
        now = time.time()

        for child in children:
            if child["concept"] not in existing:
                km.append({
                    "concept": child["concept"],
                    "domain": child.get("domain", "general"),
                    "confidence": 0.02,
                    "relevance": child.get("relevance", 0.5),
                    "source": f"衍生自 {concept}",
                    "evidence": [f"自动生长: {concept} 探索后衍生"],
                    "related_concepts": [concept],
                    "keywords_en": child.get("keywords_en", []),
                    "last_updated": now,
                    "verified": False,
                })
                new_count += 1

        if new_count > 0:
            identity["knowledge_map"] = km
            identity["last_updated"] = now
            identity_path.write_text(
                json.dumps(identity, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[HermesAssistant] 🌱 KM 生长: {concept} → {new_count} 个子概念")

        return new_count
    except (OSError, json.JSONDecodeError) as e:
        print(f"[HermesAssistant] KM 生长失败: {e}")
        return 0


def seed_from_values() -> int:
    """价值观驱动: KnowledgeMap 无缺口时，从最低维度生成新概念。

    读取 ValueSystem，找最低维度，从 VALUE_SEEDS 取对应概念，
    检查是否已在 KM 中，不在则添加。
    """
    try:
        identity_path = STATE_DIR / "core_identity.json"
        if not identity_path.exists():
            return 0

        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        vs = identity.get("value_system", {})
        if not vs:
            return 0

        lowest = min(vs.items(), key=lambda x: x[1])
        dim, val = lowest
        seeds = VALUE_SEEDS.get(dim)
        if not seeds:
            return 0

        km = identity.get("knowledge_map", [])
        existing = {e.get("concept") for e in km}
        now = time.time()
        new_count = 0

        for seed in seeds:
            if seed["concept"] not in existing:
                km.append({
                    "concept": seed["concept"],
                    "domain": seed.get("domain", "general"),
                    "confidence": 0.01,
                    "relevance": seed.get("relevance", 0.5),
                    "source": f"价值观驱动: {dim}={val:.2f}",
                    "evidence": [f"自动播种: {dim} 维度最低, 生成探索方向"],
                    "related_concepts": [],
                    "keywords_en": seed.get("keywords_en", []),
                    "last_updated": now,
                    "verified": False,
                })
                new_count += 1

        if new_count > 0:
            identity["knowledge_map"] = km
            identity["last_updated"] = now
            identity_path.write_text(
                json.dumps(identity, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[HermesAssistant] 🌱 价值观播种: {dim}={val:.2f} → {new_count} 个新概念")

        return new_count
    except (OSError, json.JSONDecodeError) as e:
        print(f"[HermesAssistant] 价值观播种失败: {e}")
        return 0


def process_needs_session() -> List[Dict[str, Any]]:
    """获取所有 needs_session 状态的进化提案。

    当 Aris 在 Hermes 会话中时，可以调用此函数获取
    需要人工/LLM 协助的提案，为其生成实际代码变更。

    Returns:
        needs_session 状态的提案列表
    """
    try:
        proposal_path = STATE_DIR / "evolution_proposals.json"
        if not proposal_path.exists():
            return []
        data = json.loads(proposal_path.read_text(encoding="utf-8"))
        props = data if isinstance(data, list) else data.get("proposals", [])
        return [
            p for p in props
            if p.get("status") == "needs_session"
        ]
    except (OSError, json.JSONDecodeError) as e:
        print(f"[HermesAssistant] 读 needs_session 提案失败: {e}")
        return []
