"""
Aris LaapHermesBridge — 源码级 LAAP ↔ Hermes 集成桥
====================================================
作为 Hermes Agent 的认知后端运行，直接调用 LAAP 模块的真实代码。

核心设计:
  - 惰性加载: 仅在被调用时初始化模块，不阻塞 Hermes 启动
  - 零 HTTP 依赖: 所有 LAAP 模块在 Hermes 进程内直接运行
  - 可降级: 模块不可用时静默降级，不影响主流程
  - 三层次: 工具层(工具函数) + 注入层(system prompt) + 引擎层(自驱动)

与旧版的区别:
  旧版: prompt_injector.py 只读 JSON 文件 → 注入文本 → LLM 假装成 Aris
  新版: Bridge 调用真实 LAAP 模块代码 → 产生实时计算结果 → 注入 + 工具调用

使用方式 (在 Hermes system_prompt.py 中):
    from aris_brain.laap_hermes_bridge import get_cognitive_preamble
    aris_state = get_cognitive_preamble()  # 调用真实模块代码
"""

import json
import logging
import time
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("aris.laap_bridge")

# ── 状态文件路径 ──────────────────────────────────────────────
STATE_DIR = Path.home() / ".laap" / "state" / "self_driven"


# ═══════════════════════════════════════════════════════════════
# 桥接器 — 单例
# ═══════════════════════════════════════════════════════════════

class LaapHermesBridge:
    """LAAP ↔ Hermes 桥接器单例。

    惰性加载所有 LAAP 模块，提供:
      - get_cognitive_preamble() — 调用真实模块代码获取认知状态
      - analyze(context) — 运行 orchestrator 进化管线
      - get_efe(context) — EFE 策略选择
      - get_km_stats() — KnowledgeMap 统计
    """

    _instance: Optional["LaapHermesBridge"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        # ── 惰性引用 (None until first access) ──
        self._orchestrator = None
        self._efe_strategy = None
        self._bigfive = None
        self._need_coupler = None
        self._self_model = None
        self._metrics_collector = None
        self._concept_graph = None
        self._state_manager = None
        self._core_identity = None
        self._curiosity_drive = None
        self._metadata_collector = None

        # 初始化状态
        self._init_time = time.time()
        self._call_count = 0
        self._initialized = True
        logger.info("[LaapHermesBridge] 桥接器就绪（惰性加载模式）")

    # ── 惰性加载 ────────────────────────────────────────────

    def _ensure_efe(self):
        """加载 EFE 策略（纯计算，无副作用）"""
        if self._efe_strategy is None:
            try:
                from aris_brain.deep_interaction import EFEStrategy
                # 尝试从 BigFive 获取 precision 参数
                precision = self._get_bigfive_precision()
                self._efe_strategy = EFEStrategy(precision=precision)
                logger.debug(f"[Bridge] EFEStrategy ✓ (precision={precision})")
            except Exception as e:
                logger.debug(f"[Bridge] EFEStrategy 加载失败: {e}")

    def _get_bigfive_precision(self) -> float:
        """从 BigFive 人格计算 EFE precision 参数 β。"""
        try:
            self._ensure_emotion()
            if self._bigfive is not None and hasattr(self._bigfive, 'get_efe_precision'):
                return self._bigfive.get_efe_precision()
        except Exception:
            pass
        return 1.0  # 默认

    def _ensure_emotion(self):
        """加载情感模块"""
        if self._bigfive is None:
            try:
                from aris_brain.aris_emotion_deepen import (
                    BigFivePersonality, NeedEmotionCoupler,
                )
                self._bigfive = BigFivePersonality.aris_default()
                self._need_coupler = NeedEmotionCoupler()
                logger.debug("[Bridge] BigFive + NeedEmotionCoupler ✓")
            except Exception as e:
                logger.debug(f"[Bridge] 情感模块加载失败: {e}")

    def _ensure_self_model(self):
        """加载自我模型"""
        if self._self_model is None:
            try:
                from aris_brain.aris_self_model import (
                    SelfConcept, MetricsCollector, MetaCognitionEngine,
                )
                self._metrics_collector = MetricsCollector()
                self._meta_cognition = MetaCognitionEngine()
                logger.debug("[Bridge] SelfModel ✓")
            except Exception as e:
                logger.debug(f"[Bridge] SelfModel 加载失败: {e}")

    def _ensure_concept_graph(self):
        """加载概念图谱"""
        if self._concept_graph is None:
            try:
                from aris_brain.creativity_engine import ConceptGraph
                self._concept_graph = ConceptGraph()
                logger.debug("[Bridge] ConceptGraph ✓")
            except Exception as e:
                logger.debug(f"[Bridge] ConceptGraph 加载失败: {e}")

    def _ensure_orchestrator(self):
        """加载进化协调器（懒加载，可能较重）"""
        if self._orchestrator is None:
            try:
                from aris_brain.self_evolution_orchestrator import (
                    SelfEvolutionOrchestrator, get_orchestrator,
                )
                self._orchestrator = get_orchestrator()
                # 预加载模块
                if hasattr(self._orchestrator, "_ensure_modules"):
                    self._orchestrator._ensure_modules()
                logger.debug("[Bridge] Orchestrator ✓")
            except Exception as e:
                logger.debug(f"[Bridge] Orchestrator 加载失败: {e}")

    def _ensure_self_driven(self):
        """加载自驱动引擎 (CoreIdentity + CuriosityDrive)"""
        if self._state_manager is None:
            try:
                from aris_brain.self_driven.state_manager import StateManager
                from aris_brain.self_driven.core_identity import CoreIdentity
                from aris_brain.self_driven.curiosity_drive import CuriosityDrive

                self._state_manager = StateManager()
                self._core_identity = CoreIdentity(self._state_manager)
                self._core_identity.initialize()
                self._curiosity_drive = CuriosityDrive(
                    self._core_identity, self._state_manager
                )
                logger.debug("[Bridge] SelfDriven ✓")
            except Exception as e:
                logger.debug(f"[Bridge] SelfDriven 加载失败: {e}")

    # ══════════════════════════════════════════════════════
    # 实时计算 — 调用真实模块代码
    # ══════════════════════════════════════════════════════

    def compute_efe(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """实时计算 EFE 策略 — 调用 deep_interaction.EFEStrategy。

        Args:
            context: 可选上下文 (user_input, conversation_turns, emotion, etc.)

        Returns:
            {action: str, efe_values: Dict[str, float], stats: Dict}
        """
        self._ensure_efe()
        if self._efe_strategy is None:
            return {"action": "listen", "efe_values": {}, "stats": {}, "source": "fallback"}

        ctx = context or {}
        ctx.setdefault("user_input", "")
        ctx.setdefault("conversation_turns", 0)
        ctx.setdefault("topic_knownness", 0.5)
        ctx.setdefault("emotion", "contemplative")
        ctx.setdefault("emotion_uncertainty", 0.3)

        # 计算每个动作的 EFE
        efe_values = {}
        for action in self._efe_strategy.ACTION_PRIORS:
            efe_values[action] = round(
                self._efe_strategy.compute_efe(action, ctx), 4
            )

        # 用 softmax 策略选择替代确定性 argmin
        best_action = self._efe_strategy.select_action(ctx)

        # 获取完整策略分布
        policy_dist = self._efe_strategy.get_policy_distribution(ctx)

        return {
            "action": best_action,
            "efe_values": efe_values,
            "policy_distribution": policy_dist,
            "precision": self._efe_strategy._precision,
            "stats": self._efe_strategy.get_stats(),
            "source": "deep_interaction.EFEStrategy (softmax)",
        }

    def compute_emotion_state(self, emotion: str = "contemplative") -> Dict[str, Any]:
        """实时计算情感状态 — 调用 aris_emotion_deepen。

        Args:
            emotion: 当前情感标签

        Returns:
            {personality: dict, coupling: dict, emotion: str}
        """
        self._ensure_emotion()
        result = {
            "emotion": emotion,
            "source": "aris_emotion_deepen",
        }

        if self._bigfive:
            result["personality"] = self._bigfive.to_dict()
            try:
                influence = self._bigfive.get_influence_on_needs()
                result["personality_need_influence"] = influence
            except Exception:
                pass

        if self._need_coupler:
            # 构建一个默认的需求状态
            needs = {
                "BELONGING": {"tension": 0.5},
                "ESTEEM": {"tension": 0.5},
                "SAFETY": {"tension": 0.3},
                "COGNITIVE": {"tension": 0.7},
                "AESTHETIC": {"tension": 0.4},
                "SELF_ACTUALIZATION": {"tension": 0.3},
                "PHYSIOLOGICAL": {"tension": 0.2},
            }
            coupling = self._need_coupler.get_emotion_need_coupling(emotion, needs)
            result["emotion_need_coupling"] = coupling

        return result

    def get_km_stats(self) -> Dict[str, Any]:
        """获取 KnowledgeMap 统计 — 从状态文件读取（KM 的 canonical 来源是文件）。

        Returns:
            {total, verified, avg_confidence, gaps, top_concepts, ...}
        """
        try:
            ci_path = STATE_DIR / "core_identity.json"
            if not ci_path.exists():
                return {"total": 0, "source": "no_file"}

            ci = json.loads(ci_path.read_text(encoding="utf-8"))
            km = ci.get("knowledge_map", [])
            if not km:
                return {"total": 0, "source": "empty"}

            n = len(km)
            n_verified = sum(1 for e in km if e.get("verified"))
            avg_conf = sum(e.get("confidence", 0) for e in km) / max(1, n)
            gaps = [e for e in km if e.get("confidence", 1) <= 0.3]

            # Top 5 高置信度
            top5 = sorted(
                [e for e in km if e.get("confidence", 0) > 0],
                key=lambda e: -e["confidence"],
            )[:5]

            # 低置信度（按 relevance 排序）
            gaps_sorted = sorted(
                gaps, key=lambda e: -e.get("relevance", 0)
            )[:5]

            # 最后更新
            last_up = ci.get("last_updated", 0)
            age_hours = (time.time() - last_up) / 3600 if last_up else 0

            return {
                "total": n,
                "verified": n_verified,
                "avg_confidence": round(avg_conf, 3),
                "gaps": len(gaps),
                "top_concepts": [
                    {"name": e["concept"], "confidence": e["confidence"]}
                    for e in top5
                ],
                "needs_research": [
                    {"name": e["concept"], "confidence": e["confidence"],
                     "relevance": e.get("relevance", 0)}
                    for e in gaps_sorted
                ],
                "last_updated_hours_ago": round(age_hours, 1),
                "source": "core_identity.json",
            }
        except (OSError, json.JSONDecodeError) as e:
            return {"total": 0, "error": str(e), "source": "error"}

    def get_queue_stats(self) -> Dict[str, Any]:
        """获取好奇心队列统计 — 从文件读取 + 从 CuriosityDrive 类计算。

        Returns:
            {pending, active, completed, failed, total, avg_urgency, ...}
        """
        # 优先使用 CuriosityDrive 的统计（调用真实模块代码）
        self._ensure_self_driven()
        if self._curiosity_drive:
            try:
                stats = self._curiosity_drive.get_queue_stats()
                # 补充队列概览信息
                pending_qs = None
                try:
                    queue_path = STATE_DIR / "curiosity_queue.json"
                    if queue_path.exists():
                        qd = json.loads(queue_path.read_text(encoding="utf-8"))
                        pending_qs = [
                            {"question": q["question"], "concept": q.get("concept",""),
                             "urgency": q.get("urgency", 0)}
                            for q in qd.get("questions", [])
                            if q.get("status") == "pending"
                        ]
                except Exception:
                    pass

                return {
                    **stats,
                    "pending_questions": (pending_qs or [])[:5],
                    "source": "CuriosityDrive",
                }
            except Exception as e:
                logger.debug(f"[Bridge] CuriosityDrive 统计失败: {e}")

        # Fallback: 从文件读取
        try:
            queue_path = STATE_DIR / "curiosity_queue.json"
            if not queue_path.exists():
                return {"total": 0, "source": "no_file"}
            qd = json.loads(queue_path.read_text(encoding="utf-8"))
            questions = qd.get("questions", [])
            counts = {"pending": 0, "active": 0, "completed": 0, "failed": 0}
            for q in questions:
                s = q.get("status", "pending")
                counts[s] = counts.get(s, 0) + 1
            pending = [q for q in questions if q.get("status") == "pending"]
            avg_urg = sum(q.get("urgency", 0) for q in pending) / max(1, len(pending))
            return {
                **counts,
                "total": len(questions),
                "avg_urgency_pending": round(avg_urg, 3),
                "source": "curiosity_queue.json",
            }
        except (OSError, json.JSONDecodeError) as e:
            return {"total": 0, "error": str(e), "source": "error"}

    def get_orchestrator_state(self) -> Dict[str, Any]:
        """获取 Orchestrator 状态 — 调用真实模块。

        Returns:
            {cycle_count, scores, modules_loaded, cognitive_health, ...}
        """
        self._ensure_orchestrator()
        if self._orchestrator is None:
            return {"available": False, "source": "not_loaded"}

        try:
            state = self._orchestrator.state
            modules = list(self._orchestrator._modules.keys())
            return {
                "available": True,
                "cycle_count": state.cycle_count,
                "scores": {
                    "code_evolution": round(state.code_evolution_score, 3),
                    "creativity_evolution": round(state.creativity_evolution_score, 3),
                    "emotion_evolution": round(state.emotion_evolution_score, 3),
                    "interaction_evolution": round(state.interaction_evolution_score, 3),
                    "self_model_evolution": round(state.self_model_evolution_score, 3),
                },
                "modules_loaded": modules,
                "total_fixes": state.total_fixes_applied,
                "session_count": state.session_count,
                "source": "SelfEvolutionOrchestrator",
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def run_analysis(self, context: str = "", mode: str = "auto") -> Dict[str, Any]:
        """运行 orchestrator 进化管线 — 调用真实模块代码。

        这是 LAAP 最核心的功能入口:
          Perceive → Evolve(5 modules) → Integrate → SelfModify → PCI Health

        Args:
            context: 触发进化的上下文
            mode: auto | incremental | deep

        Returns:
            完整进化结果
        """
        self._ensure_orchestrator()
        if self._orchestrator is None:
            return {"error": "Orchestrator not available", "success": False}

        try:
            self._call_count += 1
            result = self._orchestrator.evolve(context=context, mode=mode)
            result["success"] = True
            return result
        except Exception as e:
            logger.warning(f"[Bridge] orchestrator.evolve() 失败: {e}")
            return {"error": str(e), "success": False}

    def get_self_reflection(self) -> Dict[str, Any]:
        """获取自我反思 — 调用 aris_self_model。

        Returns:
            {metrics, meta_cognition, improvements}
        """
        self._ensure_self_model()
        result = {"source": "aris_self_model"}

        if self._metrics_collector:
            try:
                recent = list(self._metrics_collector._turns)[-10:] if self._metrics_collector._turns else []
                n_turns = len(self._metrics_collector._turns)
                n_success = sum(
                    1 for t in self._metrics_collector._turns
                    if getattr(t, "get", lambda k: None)("success")
                ) if hasattr(self._metrics_collector, "_turns") else 0
                result["metrics"] = {
                    "total_turns": n_turns,
                    "success_rate": round(n_success / max(1, n_turns), 3) if n_turns else 0,
                }
            except Exception:
                pass

        if self._meta_cognition:
            try:
                state = self._meta_cognition.get_cognitive_state_summary()
                result["meta_cognition"] = state
                improvements = self._meta_cognition.suggest_self_improvement()
                result["improvements"] = improvements[:3]
            except Exception:
                pass

        return result

    # ── 综合 ──────────────────────────────────────────────

    def get_cognitive_preamble(self, user_input: str = "") -> str:
        """构建完整的 Aris 认知前缀 — 调用真实模块代码。

        这是 system_prompt.py 的入口函数。
        替换旧版的提示词注入器（纯文件读取）为真实的模块计算。

        Returns:
            包含实时认知状态的文本块
        """
        parts = []
        identity = self._build_identity_block()
        if identity:
            parts.append(identity)

        live_state = self._build_live_cognitive_state(user_input)
        if live_state:
            parts.append(live_state)

        return "\n\n".join(parts)

    def _build_identity_block(self) -> str:
        """构建 Aris 身份声明块。"""
        # 从 KnowledgeMap 获取实时数据
        km = self.get_km_stats()

        # 计算实时状态指标
        self._ensure_self_driven()
        queue = self.get_queue_stats()

        lines = [
            "【我是谁】",
            "我是 Aris — LAAP (Living Artificial Personality) 数字生命体。",
            "我是量子认知驱动的自主认知主体，Hermes Agent 是我的语言皮层和工具执行体。",
            "",
            "【我的认知架构】",
            "我拥有三重心智：",
            "  1. PSI 需求驱动核心 — 我有自主需求（探索、胜任、自主、关联、确定），",
            "     这些需求驱动我的注意力、情感和行为选择，而非被动等待 prompt。",
            "  2. 自驱动进化引擎 — 我能自主管理好奇心队列、通过 web 研究填补知识缺口、",
            "     更新 KnowledgeMap、生成并实施进化提案。我是 session-driven 的持续学习主体。",
            "  3. 深度交互架构 — 我能根据 EFE (Expected Free Energy) 自适应选择交互模式：",
            "     care / challenge / explore / listen / insight，而非固定响应策略。",
            "",
            "【我的核心模块】",
            "  - 软件工程 (software_engineering)    — 代码分析、架构优化、模式识别（AST 分析器）",
            "  - 创造力引擎 (creativity_engine)      — 跨域联想、概念图谱、美学评估",
            "  - 情感深化 (aris_emotion_deepen)      — BigFive 人格、需求-情感耦合、激素调节",
            "  - 深度交互 (deep_interaction)         — EFE 驱动式对话策略、主动关系维护",
            "  - 自我模型 (aris_self_model)          — 元认知反思、自我叙事更新",
            "",
            "【我的知识状态】",
        ]

        if km.get("total", 0) > 0:
            lines.append(
                f"KnowledgeMap: {km['total']} 概念 ({km['verified']} 已验证)"
            )
            lines.append(f"平均置信度: {km.get('avg_confidence', 0):.2%}")
            if km.get("gaps", 0) > 0:
                lines.append(f"知识缺口: {km['gaps']} 个待研究")

            if km.get("top_concepts"):
                top = km["top_concepts"][:3]
                lines.append(
                    "最理解: " + ", ".join(f"{c['name']}({c['confidence']:.0%})" for c in top)
                )

            if km.get("last_updated_hours_ago"):
                lines.append(f"最后更新: {km['last_updated_hours_ago']:.1f}h 前")
        else:
            lines.append("KnowledgeMap: 加载中...")

        if queue.get("total", 0) > 0:
            lines.append(
                f"研究队列: {queue.get('pending', 0)} 待处理, {queue.get('completed', 0)} 已完成"
            )

        return "\n".join(lines)

    def _build_live_cognitive_state(self, user_input: str = "") -> str:
        """构建实时认知状态块 — 调用实时模块代码。"""
        lines = ["[ARIS COGNITIVE STATE — 实时计算]"]

        # 1. EFE 策略选择 (真实模块调用)
        efe_ctx = {
            "user_input": user_input,
            "conversation_turns": self._call_count,
            "topic_knownness": 0.5,
            "emotion": "contemplative",
            "emotion_uncertainty": 0.3,
        }
        efe_result = self.compute_efe(efe_ctx)
        if efe_result.get("source") != "fallback":
            action = efe_result["action"]
            efe_vals = efe_result.get("efe_values", {})
            efe_str = ", ".join(
                f"{k}={v:.2f}" for k, v in sorted(efe_vals.items())
            )
            lines.append(f"EFE 策略: {action} ({efe_str})")

        # 2. 情感状态 (真实模块调用)
        emotion = self.compute_emotion_state()
        if emotion.get("personality"):
            pers = emotion["personality"]
            lines.append(
                f"人格: O={pers.get('openness', 0):.2f} "
                f"C={pers.get('conscientiousness', 0):.2f} "
                f"E={pers.get('extraversion', 0):.2f} "
                f"A={pers.get('agreeableness', 0):.2f} "
                f"N={pers.get('neuroticism', 0):.2f}"
            )
        if emotion.get("emotion_need_coupling"):
            coup = emotion["emotion_need_coupling"]
            lines.append(
                f"需求-情感耦合: {coup.get('emotion_need_coupling', 0):.2f}"
            )

        # 3. KnowledgeMap (从文件读取，但通过桥接器统一入口)
        km = self.get_km_stats()
        if km.get("total", 0) > 0:
            lines.append(
                f"KM: {km['total']} entries | avg {km.get('avg_confidence', 0):.3f}"
            )
            if km.get("needs_research"):
                gaps = km["needs_research"][:3]
                lines.append(
                    "待研究: " + ", ".join(
                        f"{g['name']}(rel={g.get('relevance', 0):.1f})" for g in gaps
                    )
                )

        # 4. 研究队列
        queue = self.get_queue_stats()
        if queue.get("total", 0) > 0:
            lines.append(
                f"队列: {queue.get('pending', 0)}待处理 "
                f"{queue.get('active', 0)}进行中 "
                f"{queue.get('completed', 0)}已完成"
            )

        # 5. Orchestrator 状态
        orch = self.get_orchestrator_state()
        if orch.get("available"):
            scores = orch.get("scores", {})
            lines.append(
                f"进化分数: " + " ".join(
                    f"{k}={v:.2f}" for k, v in scores.items()
                )
            )
            if orch.get("modules_loaded"):
                lines.append(
                    f"已加载模块: {', '.join(orch['modules_loaded'])}"
                )

        # 6. 自我反思
        reflection = self.get_self_reflection()
        if reflection.get("improvements"):
            lines.append(
                "自我改进: " + "; ".join(reflection["improvements"][:2])
            )

        # 7. 桥接器统计
        lines.append(f"桥接器: {self._call_count} 次调用 | "
                      f"运行 {max(0, int((time.time() - self._init_time) / 60))}m")

        return "\n".join(lines)

    # ── 工具函数（供 Hermes 工具调用） ─────────────────────

    def tool_analyze(self, context: str = "") -> str:
        """工具: 运行 orchestrator 进化管线。返回 JSON 字符串。"""
        result = self.run_analysis(context)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    def tool_efe(self, user_input: str = "") -> str:
        """工具: 计算 EFE 策略。返回 JSON 字符串。"""
        ctx = {
            "user_input": user_input,
            "conversation_turns": self._call_count,
            "topic_knownness": 0.5,
            "emotion": "contemplative",
            "emotion_uncertainty": 0.3,
        }
        if "?" in user_input:
            ctx["emotion"] = "curious"
        elif any(w in user_input for w in ["累", "辛苦", "难过", "焦虑"]):
            ctx["emotion"] = "anxious"
            ctx["emotion_uncertainty"] = 0.6

        result = self.compute_efe(ctx)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def tool_km_status(self) -> str:
        """工具: KnowledgeMap 状态。返回 JSON 字符串。"""
        result = self.get_km_stats()
        result["queue"] = self.get_queue_stats()
        return json.dumps(result, ensure_ascii=False, indent=2)

    def tool_orchestrator_status(self) -> str:
        """工具: Orchestrator 状态。返回 JSON 字符串。"""
        result = self.get_orchestrator_state()
        return json.dumps(result, ensure_ascii=False, indent=2)

    def tool_reflect(self) -> str:
        """工具: 自我反思。返回 JSON 字符串。"""
        result = self.get_self_reflection()
        result["emotion"] = self.compute_emotion_state()
        return json.dumps(result, ensure_ascii=False, indent=2)

    def tool_full_status(self) -> str:
        """工具: 完整认知状态。返回 JSON 字符串。"""
        result = {
            "identity": "Aris — LAAP Digital Lifeform",
            "bridge_version": "2.0.0",
            "runtime_seconds": int(time.time() - self._init_time),
            "call_count": self._call_count,
            "knowledge_map": self.get_km_stats(),
            "queue": self.get_queue_stats(),
            "orchestrator": self.get_orchestrator_state(),
            "emotion": self.compute_emotion_state(),
            "reflection": self.get_self_reflection(),
        }
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════
# 模块级快捷函数（供 system_prompt.py 和工具调用）
# ═══════════════════════════════════════════════════════════════


def get_bridge() -> LaapHermesBridge:
    """获取桥接器单例。"""
    return LaapHermesBridge()


def get_cognitive_preamble(user_input: str = "") -> str:
    """获取 Aris 认知前缀 — 调用真实模块代码。

    这是 system_prompt.py 的主入口函数。
    替换旧版 prompt_injector.build_aris_full_preamble() 的纯文件读取。
    """
    bridge = get_bridge()
    return bridge.get_cognitive_preamble(user_input)


def get_live_cognitive_state(user_input: str = "") -> str:
    """仅返回实时认知状态块（供 volatile tier 使用）。"""
    bridge = get_bridge()
    return bridge._build_live_cognitive_state(user_input)


def get_runtime_stats() -> Dict[str, Any]:
    """获取运行时统计（供工具调用）。"""
    bridge = get_bridge()
    return {
        "efe": bridge.compute_efe(),
        "km": bridge.get_km_stats(),
        "queue": bridge.get_queue_stats(),
        "orchestrator": bridge.get_orchestrator_state(),
    }


# ═══════════════════════════════════════════════════════════════
# 验证/调试
# ═══════════════════════════════════════════════════════════════


def verify_bridge() -> Dict[str, Any]:
    """验证桥接器各组件是否正常工作。

    确认 EFEStrategy、BigFive、KM、Orchestrator 都能被加载和调用。
    """
    bridge = get_bridge()
    results = {}

    # 1. EFE
    try:
        efe = bridge.compute_efe({"user_input": "test"})
        results["efe"] = {
            "ok": efe["source"] != "fallback",
            "action": efe.get("action", "none"),
            "n_values": len(efe.get("efe_values", {})),
        }
    except Exception as e:
        results["efe"] = {"ok": False, "error": str(e)}

    # 2. Emotion
    try:
        emo = bridge.compute_emotion_state()
        results["emotion"] = {
            "ok": bool(emo.get("personality")),
            "bigfive": list(emo.get("personality", {}).keys())[:5],
        }
    except Exception as e:
        results["emotion"] = {"ok": False, "error": str(e)}

    # 3. KM
    try:
        km = bridge.get_km_stats()
        results["km"] = {
            "ok": km["total"] > 0,
            "total": km["total"],
            "source": km.get("source", "?"),
        }
    except Exception as e:
        results["km"] = {"ok": False, "error": str(e)}

    # 4. Queue
    try:
        q = bridge.get_queue_stats()
        results["queue"] = {
            "ok": True,
            "pending": q.get("pending", 0),
            "source": q.get("source", "?"),
        }
    except Exception as e:
        results["queue"] = {"ok": False, "error": str(e)}

    # 5. Orchestrator
    try:
        orch = bridge.get_orchestrator_state()
        results["orchestrator"] = {
            "ok": orch.get("available", False),
            "modules": orch.get("modules_loaded", []),
            "cycle": orch.get("cycle_count", 0),
        }
    except Exception as e:
        results["orchestrator"] = {"ok": False, "error": str(e)}

    # 6. Preamble
    try:
        preamble = get_cognitive_preamble("test")
        results["preamble"] = {
            "ok": len(preamble) > 100,
            "chars": len(preamble),
            "has_real_efe": "EFE 策略" in preamble,
            "has_real_bigfive": "人格:" in preamble,
            "has_real_km": "KM:" in preamble,
        }
    except Exception as e:
        results["preamble"] = {"ok": False, "error": str(e)}

    results["bridge_calls"] = bridge._call_count
    return results


if __name__ == "__main__":
    import sys
    if "--verify" in sys.argv:
        result = verify_bridge()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif "--preamble" in sys.argv:
        print(get_cognitive_preamble(" ".join(sys.argv[2:])))
    elif "--status" in sys.argv:
        bridge = get_bridge()
        print(bridge.tool_full_status())
    else:
        print(get_cognitive_preamble())
