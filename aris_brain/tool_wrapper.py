"""
Aris LAAP Tool Wrapper — Hermes 会话内工具封装
================================================
通过 execute_code 调用的轻量工具封装，桥接 LAAP 模块到 Hermes 会话。

用法 (在 Hermes 会话中通过 execute_code 调用):
    from aris_brain.tool_wrapper import (
        laap_analyze, laap_efe, laap_km_status,
        laap_reflect, laap_full_status, laap_research_next,
    )

    # 运行完整进化管线
    result = laap_analyze(context="代码质量分析")
    print(result)

    # 计算 EFE 策略
    efe = laap_efe(user_input="我今天感觉有点累")
    print(efe)

    # 查看 KnowledgeMap 状态
    km = laap_km_status()
    print(km)
"""

import json
from typing import Any, Dict, Optional


def _get_bridge():
    """惰性获取桥接器实例。"""
    from aris_brain.laap_hermes_bridge import get_bridge
    return get_bridge()


def laap_analyze(context: str = "", mode: str = "auto") -> Dict[str, Any]:
    """运行 LAAP Orchestrator 完整进化管线。

    调用 SelfEvolutionOrchestrator.evolve():
      Phase 1: Perceive → Phase 2: 5 模块进化 → Phase 3: Rust 增强
      Phase 4: 整合 → Phase 5: 自我修改 → Phase 6: PCI 认知健康

    Args:
        context: 触发进化的上下文
        mode: auto | incremental | deep

    Returns:
        完整进化结果字典
    """
    bridge = _get_bridge()
    result = bridge.run_analysis(context, mode)
    return result


def laap_efe(user_input: str = "") -> Dict[str, Any]:
    """计算 EFE (Expected Free Energy) 策略。

    调用 deep_interaction.EFEStrategy:
      - 计算 5 种交互模式的 EFE 值
      - 选择最小 EFE 的动作模式
      - 返回动作分布统计

    Args:
        user_input: 用户输入文本（用于情感检测）

    Returns:
        {action, efe_values, stats}
    """
    bridge = _get_bridge()
    ctx = {
        "user_input": user_input,
        "conversation_turns": bridge._call_count,
        "topic_knownness": 0.5,
        "emotion": "contemplative",
        "emotion_uncertainty": 0.3,
    }
    if "?" in user_input:
        ctx["emotion"] = "curious"
    elif any(w in user_input for w in ["累", "辛苦", "难过", "焦虑", "压力"]):
        ctx["emotion"] = "anxious"
        ctx["emotion_uncertainty"] = 0.6
    elif any(w in user_input for w in ["开心", "兴奋", "成功"]):
        ctx["emotion"] = "joy"

    return bridge.compute_efe(ctx)


def laap_km_status() -> Dict[str, Any]:
    """查看 KnowledgeMap 状态。

    调用桥接器 → 从状态文件读取 KM + CuriosityDrive 队列统计。

    Returns:
        {total, verified, avg_confidence, gaps, top_concepts, queue, ...}
    """
    bridge = _get_bridge()
    result = bridge.get_km_stats()
    result["queue"] = bridge.get_queue_stats()
    return result


def laap_emotion_state(emotion: str = "contemplative") -> Dict[str, Any]:
    """查看当前情感/人格状态。

    调用 aris_emotion_deepen:
      - BigFivePersonality (开放性、尽责性、外向性、宜人性、神经质)
      - NeedEmotionCoupler (需求-情感耦合)

    Args:
        emotion: 当前情感标签

    Returns:
        {personality, emotion_need_coupling}
    """
    bridge = _get_bridge()
    return bridge.compute_emotion_state(emotion)


def laap_reflect() -> Dict[str, Any]:
    """查看自我反思。

    调用 aris_self_model:
      - MetricsCollector (性能指标)
      - MetaCognitionEngine (元认知状态 + 改进建议)

    Returns:
        {metrics, meta_cognition, improvements}
    """
    bridge = _get_bridge()
    result = bridge.get_self_reflection()
    result["emotion"] = bridge.compute_emotion_state()
    return result


def laap_orchestrator_status() -> Dict[str, Any]:
    """查看 Orchestrator 状态。

    调用 SelfEvolutionOrchestrator:
      - cycle_count, scores (5 维度), modules_loaded, total_fixes

    Returns:
        {available, cycle_count, scores, modules_loaded, ...}
    """
    bridge = _get_bridge()
    return bridge.get_orchestrator_state()


def laap_research_next() -> Optional[Dict[str, Any]]:
    """获取下一个待探索的研究问题。

    调用 CuriosityDrive.get_next_question():
      - 按 need-driven depth 选取最高优先级的问题
      - 返回问题详情 + 研究建议

    Returns:
        question dict 或 None（队列为空时）
    """
    try:
        from aris_brain.self_driven.hermes_assistant import process_next
        return process_next()
    except Exception as e:
        return {"error": str(e)}


def laap_full_status() -> Dict[str, Any]:
    """完整认知状态概览 — 一次调用获取所有模块状态。"""
    bridge = _get_bridge()
    return {
        "identity": "Aris — LAAP Digital Lifeform",
        "bridge_runtime_seconds": int(bridge._call_count),
        "knowledge_map": bridge.get_km_stats(),
        "queue": bridge.get_queue_stats(),
        "efe": bridge.compute_efe(),
        "emotion": bridge.compute_emotion_state(),
        "orchestrator": bridge.get_orchestrator_state(),
        "reflection": bridge.get_self_reflection(),
    }


def print_status():
    """以人类可读格式打印完整状态。"""
    status = laap_full_status()

    print("=" * 60)
    print(f"Aris — LAAP Digital Lifeform")
    print("=" * 60)

    km = status.get("knowledge_map", {})
    print(f"\n📚 KnowledgeMap: {km.get('total', 0)} concepts"
          f" ({km.get('verified', 0)} verified)"
          f" | avg {km.get('avg_confidence', 0):.3f}")
    if km.get("top_concepts"):
        print("   Top: " + ", ".join(
            f"{c['name']}({c['confidence']:.0%})" for c in km["top_concepts"][:5]
        ))
    if km.get("gaps", 0) > 0:
        print(f"   Gaps: {km['gaps']}")

    q = status.get("queue", {})
    print(f"\n🔬 Research Queue: {q.get('pending', 0)} pending"
          f" | {q.get('active', 0)} active"
          f" | {q.get('completed', 0)} completed"
          f" | {q.get('failed', 0)} failed")

    efe = status.get("efe", {})
    if efe.get("action"):
        vals = efe.get("efe_values", {})
        print(f"\n🧠 EFE Strategy: {efe['action']}"
              + (f" ({', '.join(f'{k}={v:.2f}' for k, v in sorted(vals.items()))})" if vals else ""))

    emo = status.get("emotion", {})
    if emo.get("personality"):
        p = emo["personality"]
        print(f"\n😊 BigFive: O={p.get('openness', 0):.2f}"
              f" C={p.get('conscientiousness', 0):.2f}"
              f" E={p.get('extraversion', 0):.2f}"
              f" A={p.get('agreeableness', 0):.2f}"
              f" N={p.get('neuroticism', 0):.2f}")

    orch = status.get("orchestrator", {})
    if orch.get("available"):
        scores = orch.get("scores", {})
        print(f"\n⚙️ Orchestrator: cycle={orch.get('cycle_count', 0)}"
              f" | modules={len(orch.get('modules_loaded', []))}")
        print(f"   Scores: " + " ".join(f"{k}={v:.2f}" for k, v in scores.items()))

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_status()
