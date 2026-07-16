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


class OpenCodeIntegrator(HermesIntegrator):
    config: OpenCodeIntegrationConfig

    def __init__(self, config: Optional[OpenCodeIntegrationConfig] = None):
        actual_config = config or OpenCodeIntegrationConfig(persona="aris")
        self.persona = actual_config.persona
        super().__init__(actual_config)
        self._session_active = False
        self._current_state: Optional[CognitiveState] = None
        self._bridge_result: Optional[Dict[str, Any]] = None
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

    def before_turn(
        self, user_message: str, context: Optional[dict] = None
    ) -> CognitiveState:
        """
        修复:调用 cognitive_bridge.before_turn() 而非不存在的 process()。
        这会执行完整 PSI 管线(感知→注意→整合),包含记忆召回、情感检测、
        CognitiveBus 路由、AGI tick 等。
        """
        state = CognitiveState(cycle_count=self._get_cycle_count())

        if self._cognitive_bridge:
            try:
                result = self._cognitive_bridge.before_turn(user_message)
                if result:
                    state.focus = result.get("focus", state.focus)
                    state.emotion = result.get("emotion", state.emotion)
                    state.attention = result.get("focus", state.attention)
                    state.confidence = result.get(
                        "self_presence", state.confidence
                    )
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

    def after_tool(
        self, tool_name: str, tool_result: Any, context: Optional[dict] = None
    ):
        """
        修复:调用 cognitive_bridge.after_tool() 而非不存在的 emotion_engine.update()。
        CognitiveBridge.after_tool 会更新能力需求(needs_competence)和 SelfModel 经验。
        """
        if self._cognitive_bridge:
            try:
                success = True
                if isinstance(tool_result, dict):
                    output = tool_result.get("output", "")
                    if isinstance(output, str) and ("error" in output.lower() or "fail" in output.lower()):
                        success = False
                self._cognitive_bridge.after_tool(
                    tool_name, tool_result, success=success
                )
            except Exception as e:
                logger.debug(f"CognitiveBridge after_tool error: {e}")

    def after_turn(self, response: str, context: Optional[dict] = None):
        if self._cognitive_bridge:
            try:
                self._cognitive_bridge.after_turn(response)
            except Exception as e:
                logger.debug(f"CognitiveBridge after_turn error: {e}")
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
            f"Emotion: {state.emotion}",
            f"Confidence: {state.confidence:.2f}",
            f"Needs: {json.dumps(state.needs)}",
        ])
        if self._bridge_result and self._bridge_result.get("cognitive_context"):
            lines.append(f"\n{self._bridge_result['cognitive_context']}")
        return "\n".join(lines)

    def consolidate(self) -> Dict[str, Any]:
        result = {"state_saved": False, "memory_consolidated": False,
                   "rsi_cycle": False}
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
