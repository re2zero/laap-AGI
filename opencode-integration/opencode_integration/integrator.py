"""
OpenCodeIntegrator — OpenCode 专用 LAAP 认知集成器。

继承 HermesIntegrator,修复 3 个生命周期方法的调用错误
(HermesIntegrator 调用 cognitive_bridge.process/reflect 和 emotion_engine.update,
这些方法不存在,被 try/except 静默吞掉)。

正确调用:
- before_turn → cognitive_bridge.before_turn() (完整 PSI 管线)
- after_tool  → cognitive_bridge.after_tool()
- after_turn  → cognitive_bridge.after_turn()
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from laap_brain.integrator import (
    CognitiveState,
    HermesIntegrator,
    IntegrationConfig,
)

logger = logging.getLogger("laap.opencode.integrator")


@dataclass
class OpenCodeIntegrationConfig(IntegrationConfig):
    persona: str = "aris"
    personality: str = "neutral"
    traits: List[str] = field(default_factory=list)
    state_dir: str = ""
    inject_sys_path: bool = True

    def __post_init__(self):
        if not self.state_dir:
            self.state_dir = str(
                Path(__file__).resolve().parent.parent / "state" / self.persona
            )
        Path(self.state_dir).mkdir(parents=True, exist_ok=True)


@dataclass
class CognitiveModulators:
    """PSI 理论认知调节器: 调制认知处理的行为风格与情感涌现
    - activation:     觉醒/行动准备度(0-1),高=快速反应,低=深思熟虑
    - resolution:     感知分辨率(0-1),高=精确/深度,低=模糊/泛化
    - selection_threshold: 目标切换阈值(0-1),高=执着/稳定,低=易分心/多目标
    - sampling_rate:  定向/探索频率(0-1),高=频繁检查环境,低=专注当前
    """
    activation: float = 0.5
    resolution: float = 0.5
    selection_threshold: float = 0.5
    sampling_rate: float = 0.5

    def to_dict(self) -> dict:
        return {
            "activation": round(self.activation, 2),
            "resolution": round(self.resolution, 2),
            "selection_threshold": round(self.selection_threshold, 2),
            "sampling_rate": round(self.sampling_rate, 2),
        }

    def decay(self, rate: float = 0.02):
        """向 0.5 基线衰减"""
        for attr in ("activation", "resolution", "selection_threshold", "sampling_rate"):
            v = getattr(self, attr)
            if v > 0.5:
                setattr(self, attr, max(0.5, v - rate))
            elif v < 0.5:
                setattr(self, attr, min(0.5, v + rate))

    def perturb(self, activation: float = 0, resolution: float = 0,
                selection_threshold: float = 0, sampling_rate: float = 0):
        for attr, delta in [("activation", activation), ("resolution", resolution),
                            ("selection_threshold", selection_threshold),
                            ("sampling_rate", sampling_rate)]:
            v = getattr(self, attr) + delta
            setattr(self, attr, max(0.0, min(1.0, v)))


class OpenCodeIntegrator(HermesIntegrator):
    config: OpenCodeIntegrationConfig

    def __init__(self, config: Optional[OpenCodeIntegrationConfig] = None):
        actual_config = config or OpenCodeIntegrationConfig(persona="aris")
        self.persona = actual_config.persona
        super().__init__(actual_config)
        self._session_active = False
        self._current_state: Optional[CognitiveState] = None
        self._bridge_result: Optional[Dict[str, Any]] = None
        self._modulators = CognitiveModulators()
        self._pleasure = 0.0
        self._distress = 0.0
        self._interaction_count = 0
        self._success_streak = 0
        self._failure_streak = 0
        self._reinit_psi_core_for_persona()
        self._init_evolution_engines()

    def _reinit_psi_core_for_persona(self):
        if not self._psi_core_launcher:
            return
        try:
            self._psi_core_launcher.stop()
        except Exception:
            pass
        try:
            from laap_brain.psi_core_integration import PsiCoreLauncher

            persona_state_dir = Path(self.config.state_dir)
            self._psi_core_launcher = PsiCoreLauncher(state_dir=persona_state_dir)
            self._psi_core = self._psi_core_launcher
            if self._psi_core_launcher.available:
                self._psi_core_launcher.start()
                logger.info(
                    f"PSI Core started for persona '{self.persona}' "
                    f"at {persona_state_dir}"
                )
        except Exception as e:
            logger.debug(f"PSI Core reinit failed for {self.persona}: {e}")

    def _init_evolution_engines(self):
        self._rsi_engine = None
        self._learning_loop = None
        self._auto_healer = None
        try:
            from laap.agi.rsi_engine import RSIMetaEngine
            self._rsi_engine = RSIMetaEngine()
            logger.info(f"RSI engine loaded for {self.persona}")
        except Exception as e:
            logger.debug(f"RSI unavailable: {e}")
        try:
            from laap.agi.evolution_engine import LearningLoop
            self._learning_loop = LearningLoop()
            logger.info(f"LearningLoop loaded for {self.persona}")
        except Exception as e:
            logger.debug(f"LearningLoop unavailable: {e}")
        try:
            from laap.agi.self_healing import AutoHealer
            self._auto_healer = AutoHealer()
            logger.info(f"AutoHealer loaded for {self.persona}")
        except Exception as e:
            logger.debug(f"AutoHealer unavailable: {e}")

    def get_status(self) -> dict:
        status = super().get_status()
        status["evolution"] = {
            "rsi_engine": self._rsi_engine is not None,
            "learning_loop": self._learning_loop is not None,
            "auto_healer": self._auto_healer is not None,
        }
        return status

    def attach_session(self, session_id: str) -> Dict[str, Any]:
        self._session_active = True
        return {
            "persona": self.persona,
            "session_id": session_id,
            "engines": self.get_status().get("engines", {}),
            "evolution": self.get_status().get("evolution", {}),
            "state_dir": self.config.state_dir,
        }

    def _update_modulators_from_input(self, user_message: str):
        novelty = len(set(user_message.split())) / max(len(user_message.split()), 1)
        complexity = min(1.0, len(user_message) / 500)
        has_uncertainty = any(w in user_message.lower()
                              for w in ["不知道", "不确定", "maybe", "?", "不懂", "why", "how"])

        self._modulators.perturb(
            activation=0.05 * complexity,
            resolution=0.1 * novelty if novelty > 0.5 else -0.05,
            sampling_rate=0.1 if has_uncertainty else -0.05,
        )
        if complexity > 0.6:
            self._modulators.perturb(selection_threshold=0.05)
        if has_uncertainty:
            self._modulators.perturb(selection_threshold=-0.08)

    def _compute_emotion(self) -> str:
        m = self._modulators
        if m.activation > 0.7 and m.resolution > 0.6 and self._pleasure > 0.3:
            return "joy"
        if m.activation > 0.7 and m.resolution < 0.4 and self._distress > 0.3:
            return "anger"
        if m.activation < 0.4 and m.resolution > 0.6 and self._distress > 0.3:
            return "sadness"
        if m.activation > 0.6 and m.selection_threshold < 0.4 and self._distress > 0.2:
            return "anxiety"
        if m.activation > 0.4 and m.activation < 0.8 and self._pleasure > -0.1:
            return "curiosity"
        if m.activation < 0.4 and m.selection_threshold > 0.6:
            return "calm"
        if m.activation > 0.7 and m.sampling_rate > 0.6:
            return "alert"
        return "neutral"

    def _emotion_to_confidence_base(self, emotion: str) -> float:
        mapping = {"joy": 0.8, "curiosity": 0.65, "calm": 0.6, "neutral": 0.5,
                    "alert": 0.45, "anxiety": 0.35, "sadness": 0.25, "anger": 0.2}
        return mapping.get(emotion, 0.5)

    def before_turn(
        self, user_message: str, context: Optional[dict] = None
    ) -> CognitiveState:
        self._interaction_count += 1
        self._update_modulators_from_input(user_message)

        state = CognitiveState(cycle_count=self._get_cycle_count())

        if self._cognitive_bridge:
            try:
                result = self._cognitive_bridge.before_turn(user_message)
                if result:
                    state.focus = result.get("focus", state.focus)
                    state.attention = result.get("focus", state.attention)
                    needs = result.get("needs", {})
                    if needs:
                        state.needs = needs
                    self._bridge_result = result
            except Exception as e:
                logger.debug(f"CognitiveBridge before_turn error: {e}")

        if self._rules_engine:
            try:
                rule_result = self._rules_engine.process(user_message)
                if rule_result and rule_result.get("matched"):
                    state.focus = "rule_match"
                    state.confidence = rule_result.get("confidence", 0.5)
            except Exception as e:
                logger.debug(f"RulesEngine process error: {e}")

        state.emotion = self._compute_emotion()
        state.confidence = self._emotion_to_confidence_base(state.emotion)
        self._current_state = state
        return state

    def _run_evolution_after_turn(self, response: str):
        if self._learning_loop:
            try:
                self._learning_loop.record_task(
                    task_description=response[:100],
                    tools_used=[],
                    errors=[],
                    duration_s=0.0,
                    outcome="completed",
                )
            except Exception as e:
                logger.debug(f"LearningLoop record error: {e}")
        if self._rsi_engine:
            try:
                growth = self._rsi_engine.compute_growth_need()
                if growth > 0.6 and self._current_state:
                    self._current_state.needs["competence"] = min(
                        1.0, self._current_state.needs["competence"] + 0.05
                    )
            except Exception as e:
                logger.debug(f"RSI growth need error: {e}")

    def _update_pleasure_distress(self, success: bool):
        if success:
            self._success_streak += 1
            self._failure_streak = 0
            self._pleasure = min(1.0, self._pleasure + 0.15)
            self._distress = max(0.0, self._distress - 0.1)
            if self._success_streak >= 3:
                self._modulators.perturb(activation=0.05, selection_threshold=0.05)
        else:
            self._failure_streak += 1
            self._success_streak = 0
            self._distress = min(1.0, self._distress + 0.2)
            self._pleasure = max(0.0, self._pleasure - 0.15)
            if self._failure_streak >= 2:
                self._modulators.perturb(activation=-0.05, resolution=0.1)

    def after_tool(
        self, tool_name: str, tool_result: Any, context: Optional[dict] = None
    ):
        success = True
        if self._cognitive_bridge:
            try:
                if isinstance(tool_result, dict):
                    output = tool_result.get("output", "")
                    if isinstance(output, str) and ("error" in output.lower() or "fail" in output.lower()):
                        success = False
                self._cognitive_bridge.after_tool(
                    tool_name, tool_result, success=success
                )
            except Exception as e:
                logger.debug(f"CognitiveBridge after_tool error: {e}")
        self._update_pleasure_distress(success)

    def after_turn(self, response: str, context: Optional[dict] = None):
        if self._cognitive_bridge:
            try:
                self._cognitive_bridge.after_turn(response)
            except Exception as e:
                logger.debug(f"CognitiveBridge after_turn error: {e}")
        self._modulators.decay()
        self._pleasure = max(0.0, self._pleasure - 0.05)
        self._distress = max(0.0, self._distress - 0.05)
        self._run_evolution_after_turn(response)

    def before_tool(self, tool_name: str) -> str:
        state = self._current_state or CognitiveState()
        lines = [
            f"[LAAP Context — {self.persona}]",
            f"Personality: {self.config.personality}",
        ]
        if self.config.traits:
            lines.append(f"Traits: {', '.join(self.config.traits)}")
        lines.extend([
            f"Focus: {state.focus}",
            f"Emotion: {state.emotion} (emergent from modulators)",
            f"Confidence: {state.confidence:.2f}",
            f"Needs: {json.dumps(state.needs)}",
            f"Modulators: {json.dumps(self._modulators.to_dict())}",
        ])
        if self._bridge_result and self._bridge_result.get("cognitive_context"):
            lines.append(f"\n{self._bridge_result['cognitive_context']}")
        return "\n".join(lines)

    def _suggest_self_improvements(self) -> List[Dict[str, Any]]:
        suggestions = []
        pleasure_balance = self._pleasure - self._distress
        if pleasure_balance < -0.5:
            suggestions.append({
                "area": "emotion_regulation",
                "priority": "high",
                "suggestion": "情绪偏负向,建议添加 mood stabilizer 逻辑使 pleasure/distress 更快回归基线",
            })
        if self._modulators.selection_threshold < 0.3:
            suggestions.append({
                "area": "goal_stability",
                "priority": "medium",
                "suggestion": "目标切换阈值过低,易分心。当 failure_streak>2 时应提高 selection_threshold",
            })
        if self._modulators.resolution > 0.8 and self._distress > 0.5:
            suggestions.append({
                "area": "cognitive_load",
                "priority": "medium",
                "suggestion": "高分辨率+高痛苦,可能有过度分析倾向。建议在 distress 高时降低 resolution",
            })
        if self._rsi_engine:
            try:
                params = self._rsi_engine.get_parameter("competence_sensitivity")
                if params and hasattr(params, "current_value") and params.current_value < 0.3:
                    suggestions.append({
                        "area": "rsi_parameter",
                        "priority": "low",
                        "suggestion": f"competence_sensitivity={params.current_value:.2f} 偏低,建议增加以加速能力感知",
                    })
            except Exception:
                pass
        return suggestions

    def consolidate(self) -> Dict[str, Any]:
        result = {"state_saved": False, "memory_consolidated": False,
                   "rsi_cycle": False, "suggestions": []}
        if self._cognitive_bridge:
            try:
                if hasattr(self._cognitive_bridge, '_save_state'):
                    self._cognitive_bridge._save_state()
                    result["state_saved"] = True
            except Exception as e:
                logger.debug(f"consolidate save_state error: {e}")
        if self._rsi_engine:
            try:
                rsi_result = self._rsi_engine.full_improvement_cycle()
                result["rsi_cycle"] = True
                result["rsi_growth"] = rsi_result.get("growth_need", 0)
            except Exception as e:
                logger.debug(f"RSI cycle error: {e}")
        result["suggestions"] = self._suggest_self_improvements()
        return result

    def format_persona_preamble(self, agent_id: str) -> str:
        state = self._current_state or CognitiveState()
        header = f"[LAAP Persona: {agent_id} | Personality: {self.config.personality}"
        if self.config.traits:
            header += f" | Traits: {', '.join(self.config.traits)}"
        header += "]"

        parts = [header, state.to_preamble()]

        if self._bridge_result:
            ctx = self._bridge_result.get("cognitive_context", "")
            if ctx:
                parts.append(ctx)
            decision = self._bridge_result.get("decision")
            if decision and decision != "no_engine":
                parts.append(f"[CognitiveBus Route: {decision}]")

        return "\n".join(parts)

    def get_cognitive_state(self, input_text: str = "") -> Dict[str, Any]:
        if input_text:
            self._current_state = self.before_turn(input_text)
        state = self._current_state or CognitiveState()
        result = {
            "persona": self.persona,
            "state": {
                "focus": state.focus,
                "emotion": state.emotion,
                "confidence": state.confidence,
                "cognitive_load": state.cognitive_load,
                "attention": state.attention,
                "needs": state.needs,
            },
            "modulators": self._modulators.to_dict(),
            "pleasure": round(self._pleasure, 2),
            "distress": round(self._distress, 2),
            "preamble": self.format_persona_preamble(self.persona),
        }
        if self._bridge_result:
            result["decision"] = self._bridge_result.get("decision")
            result["cognitive_context"] = self._bridge_result.get(
                "cognitive_context"
            )
        return result

    def recall_memory(
        self, query: str, limit: int = 5
    ) -> Dict[str, Any]:
        memories = []
        try:
            from memory_bridge import recall_related
            fragments = recall_related(query, top_k=limit)
            if fragments:
                memories = [
                    {"content": f.content[:200], "relevance": getattr(f, "score", 0.5)}
                    for f in fragments
                ]
        except Exception as e:
            logger.debug(f"recall_related unavailable: {e}")

        if not memories and self._bridge_result:
            ctx = self._bridge_result.get("cognitive_context", "")
            if ctx:
                memories = [{"content": ctx[:200], "relevance": 0.5}]

        return {"memories": memories, "query": query}

    def reflect(
        self,
        output: str,
        success: bool = False,
        connection: bool = False,
    ) -> Dict[str, Any]:
        self.after_turn(output)
        return {
            "persona": self.persona,
            "reflected": True,
            "success": success,
            "connection": connection,
        }

    def inject_state(
        self,
        emotion: Optional[str] = None,
        confidence: Optional[float] = None,
        focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._current_state is None:
            self._current_state = CognitiveState()
        updated = []
        if emotion is not None:
            self._current_state.emotion = emotion
            updated.append("emotion")
        if confidence is not None:
            self._current_state.confidence = confidence
            updated.append("confidence")
        if focus is not None:
            self._current_state.focus = focus
            updated.append("focus")
        return {
            "status": "ok",
            "persona": self.persona,
            "updated": updated,
        }

    def bootstrap(
        self, user_name: str = "friend", preset: str = ""
    ) -> Dict[str, Any]:
        return {
            "persona": self.persona,
            "awakened": True,
            "user_name": user_name,
            "preset": preset or self.config.personality,
        }
