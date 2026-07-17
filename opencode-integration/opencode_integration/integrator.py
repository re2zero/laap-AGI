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
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from laap.agi.cognitive_bus import CognitiveBus
from laap.agi.plugin_loader import SafePluginLoader
from laap.agi.motor_cortex import MotorCortex, integrate_motor_cortex
from laap.agi.cognitive_feed import CognitiveFeedProcessor
from laap.agi.active_inference import ActiveInferenceAgent

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
        self._last_tool_name: Optional[str] = None
        self._last_tool_error: Optional[str] = None
        self._cognitive_bus: Optional[CognitiveBus] = None
        self._plugin_loader: Optional[SafePluginLoader] = None
        self._motor_cortex: Optional[MotorCortex] = None
        self._cognitive_feed: Optional[CognitiveFeedProcessor] = None
        self._aif_agent: Optional[ActiveInferenceAgent] = None
        self._last_improvement_report: Optional[Dict[str, Any]] = None
        self._state_dir = os.path.expanduser(f"~/.laap-agent/state/{self.persona}")
        self._state_file = os.path.join(self._state_dir, "integrator_state.json")
        Path(self._state_dir).mkdir(parents=True, exist_ok=True)
        self._init_evolution_engines()
        self._init_plugin_system()
        self._init_motor_cortex()
        self._init_cognitive_feed()
        self._init_aif()
        self._load_cognitive_state()

    def _get_cognitive_bus(self) -> CognitiveBus:
        if self._cognitive_bus is None:
            self._cognitive_bus = CognitiveBus(agent_name=self.persona)
        return self._cognitive_bus

    def _sync_modulators_to_bus(self):
        bus = self._get_cognitive_bus()
        m = self._modulators
        bus.set_modulators(
            activation=m.activation,
            resolution=m.resolution,
            selection_threshold=m.selection_threshold,
            sampling_rate=m.sampling_rate,
        )

    def _reinit_psi_core_for_persona(self):
        if not self._psi_core_launcher:
            return
        try:
            self._psi_core_launcher.stop()
        except Exception as e:
            logger.debug(f"PSI Core stop error: {e}")
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
            self._auto_healer = AutoHealer(
                repo_root=os.environ.get("LAAP_ROOT", ""),
                auto_deploy=False,
            )
            logger.info(f"AutoHealer loaded for {self.persona}")
        except Exception as e:
            logger.debug(f"AutoHealer unavailable: {e}")
        self._code_evolution = None
        try:
            from laap.agi.code_evolution import CodeEvolutionEngine
            self._code_evolution = CodeEvolutionEngine(
                repo_root=os.environ.get("LAAP_ROOT", ""),
            )
            logger.info(f"CodeEvolutionEngine loaded for {self.persona}")
        except Exception as e:
            logger.debug(f"CodeEvolutionEngine unavailable: {e}")

    def _init_plugin_system(self):
        try:
            bus = self._get_cognitive_bus()
            repo_root = os.environ.get("LAAP_ROOT", "")
            self._plugin_loader = SafePluginLoader(
                bus=bus,
                repo_root=repo_root,
                rules_engine=self._rules_engine,
            )
            results = self._plugin_loader.scan_and_load_all()
            loaded = [r for r in results if r.get("status") == "loaded"]
            if loaded:
                for r in loaded:
                    logger.info(f"Auto-loaded plugin: {r['info']['name']} v{r['info']['version']}")
            logger.info(f"Plugin system initialized ({len(loaded)} loaded)")
        except Exception as e:
            self._plugin_loader = None
            logger.debug(f"Plugin system unavailable: {e}")

    def _init_motor_cortex(self):
        try:
            bus = self._get_cognitive_bus()
            self._motor_cortex = integrate_motor_cortex(bus)
            logger.info(f"MotorCortex initialized for {self.persona}")
        except Exception as e:
            self._motor_cortex = None
            logger.debug(f"MotorCortex unavailable: {e}")

    def _init_cognitive_feed(self):
        try:
            bus = self._get_cognitive_bus()
            # Try to get associative_net from subconscious through cognitive bridge
            net = None
            reng = None
            ib = bus.intention_buffer if hasattr(bus, "intention_buffer") else None
            ms = bus.modulators if hasattr(bus, "modulators") else None
            self._cognitive_feed = CognitiveFeedProcessor(
                associative_net=net, rules_engine=reng,
                intention_buffer=ib, modulator_state=ms,
            )
            logger.info(f"CognitiveFeedProcessor initialized for {self.persona}")
        except Exception as e:
            self._cognitive_feed = None
            logger.debug(f"CognitiveFeedProcessor unavailable: {e}")

    def _init_aif(self):
        try:
            self._aif_agent = ActiveInferenceAgent(precision=4.0, learning_rate=1.0)
            logger.info(f"ActiveInferenceAgent initialized for {self.persona}")
        except Exception as e:
            self._aif_agent = None
            logger.debug(f"ActiveInferenceAgent unavailable: {e}")

    def _record_interaction(self, user_message: str, response: str = "",
                            tool_name: str = "", tool_success: bool = True):
        entry = {
            "ts": time.time(),
            "msg_preview": user_message[:60],
            "resp_preview": response[:60] if response else "",
            "emotion": self._compute_emotion() if self._current_state else "neutral",
            "pleasure_balance": round(self._pleasure - self._distress, 2),
            "tool": tool_name,
            "tool_ok": tool_success,
        }
        bus = self._get_cognitive_bus()
        entry["modulators"] = bus.modulators.to_dict()
        if not hasattr(self, "_recent_interactions"):
            self._recent_interactions = []
        self._recent_interactions.append(entry)
        if len(self._recent_interactions) > 50:
            self._recent_interactions = self._recent_interactions[-50:]

    def _extract_learnings(self) -> List[str]:
        if not hasattr(self, "_recent_interactions") or not self._recent_interactions:
            return []
        learnings = []
        recent = self._recent_interactions[-20:]
        tool_fails = [e for e in recent if not e.get("tool_ok", True)]
        if len(tool_fails) >= 3:
            learnings.append(f"Recent tool failures: {len(tool_fails)} in last {len(recent)} turns")
        pleasure_trend = sum(e.get("pleasure_balance", 0) for e in recent[-5:]) / 5
        if pleasure_trend < -0.3:
            learnings.append("Pleasure trend declining — possible frustration pattern")
        elif pleasure_trend > 0.3:
            learnings.append("Positive trend — effective interaction pattern")
        return learnings

    def _process_intentions(self):
        bus = self._get_cognitive_bus()
        due = bus.intention_buffer.get_due()
        for intention in due:
            desc = intention.description.lower()
            if "self-improve" in desc or "self improve" in desc or "scan" in desc:
                logger.info(f"Auto-processing intention: {intention.description[:60]}")
                try:
                    result = self.self_improve(directory="laap/agi", max_mutations=1)
                    bus.intention_buffer.complete(intention.id,
                                                  outcome=f"auto: {result.get('status', 'done')}")
                except Exception as e:
                    bus.intention_buffer.fail(intention.id, error=str(e))
            elif "consolidate" in desc:
                logger.info(f"Auto-processing intention: {intention.description[:60]}")
                try:
                    self.consolidate()
                    bus.intention_buffer.complete(intention.id)
                except Exception as e:
                    bus.intention_buffer.fail(intention.id, error=str(e))
            else:
                logger.debug(f"Unhandled due intention: {intention.description[:60]}")

    def get_status(self) -> dict:
        status = super().get_status()
        status["evolution"] = {
            "rsi_engine": self._rsi_engine is not None,
            "learning_loop": self._learning_loop is not None,
            "auto_healer": self._auto_healer is not None,
        }
        status["plugins"] = {
            "enabled": self._plugin_loader is not None,
            "loaded": len(self._plugin_loader.registry.get_all()) if self._plugin_loader else 0,
            "capabilities": list(self._plugin_loader.registry.get_capabilities().keys())
                if self._plugin_loader else [],
        }
        if self._code_evolution:
            evo_stats = self._code_evolution.stats()
            status["code_evolution"] = {
                "enabled": True,
                "mutations_total": evo_stats.get("total_mutations", 0),
                "deployed": evo_stats.get("deployed", 0),
                "rolled_back": evo_stats.get("rolled_back", 0),
            }
        else:
            status["code_evolution"] = {"enabled": False}
        if self._motor_cortex:
            mc_stats = self._motor_cortex.stats()
            status["motor_cortex"] = {
                "active": mc_stats.get("active", False),
                "cycles": mc_stats.get("cycles", 0),
                "current_urge": mc_stats.get("current_urge"),
                "current_focus": mc_stats.get("current_focus", ""),
            }
        else:
            status["motor_cortex"] = {"active": False}
        if self._cognitive_feed:
            cf_stats = self._cognitive_feed.stats()
            status["cognitive_feed"] = {
                "feeds_processed": cf_stats.get("feeds_processed", 0),
                "has_net": cf_stats.get("has_net", False),
                "has_rules": cf_stats.get("has_rules_engine", False),
            }
        else:
            status["cognitive_feed"] = {"active": False}
        if self._aif_agent:
            astats = self._aif_agent.stats()
            status["active_inference"] = {
                "step": astats["step"],
                "current_belief": astats["current_belief"],
                "entropy": astats["belief_entropy"],
                "vfe": astats["vfe"],
                "selected_policy": astats["selected_policy"],
            }
        else:
            status["active_inference"] = {"active": False}
        bus = self._get_cognitive_bus()
        status["intentions"] = bus.intention_buffer.stats()
        status["learnings"] = self._extract_learnings()
        status["persistence"] = {
            "state_dir": self._state_dir,
            "file_exists": os.path.exists(self._state_file),
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
        self, user_message: str
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

        if self._plugin_loader:
            self._plugin_loader.dispatch_before_turn(user_message)
        if self._motor_cortex:
            try:
                self._motor_cortex.process(self._get_cognitive_bus())
            except Exception as e:
                logger.debug(f"MotorCortex process error: {e}")
        self._process_intentions()
        if self._aif_agent and user_message:
            try:
                obs = self._aif_agent.observe_and_encode(user_message)
                self._aif_agent.cycle(obs)
            except Exception as e:
                logger.debug(f"AIF cycle error: {e}")
        state.emotion = self._compute_emotion()
        state.confidence = self._emotion_to_confidence_base(state.emotion)
        self._current_state = state
        self._sync_modulators_to_bus()
        return state

    def _run_evolution_after_turn(self, response: str):
        if self._learning_loop:
            try:
                tools = [self._last_tool_name] if self._last_tool_name else []
                errors = [self._last_tool_error] if self._last_tool_error else []
                self._learning_loop.record_task(
                    task_description=response[:100],
                    tools_used=tools,
                    errors=errors,
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
        self._last_tool_name = None
        self._last_tool_error = None

    def _run_evolution_after_tool(self, tool_name: str, success: bool, error_msg: Optional[str] = None):
        if self._rsi_engine:
            try:
                growth = self._rsi_engine.compute_growth_need()
                if growth > 0.6 and self._current_state:
                    self._current_state.needs["competence"] = min(
                        1.0, self._current_state.needs["competence"] + 0.05
                    )
            except Exception as e:
                logger.debug(f"RSI tool growth error: {e}")
        if self._auto_healer and not success and error_msg:
            try:
                self._auto_healer.monitor.register_error(
                    error_type="ToolError",
                    message=f"tool:{tool_name} {error_msg[:200]}",
                )
            except Exception as e:
                logger.debug(f"AutoHealer register error: {e}")

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
        self, tool_name: str, tool_result: Any
    ):
        success = True
        error_msg = None
        if isinstance(tool_result, dict):
            output = tool_result.get("output", "")
            if isinstance(output, str) and ("error" in output.lower() or "fail" in output.lower()):
                success = False
                error_msg = output[:200]
        if self._cognitive_bridge:
            try:
                self._cognitive_bridge.after_tool(
                    tool_name, tool_result, success=success
                )
            except Exception as e:
                logger.debug(f"CognitiveBridge after_tool error: {e}")
        self._last_tool_name = tool_name
        self._last_tool_error = error_msg
        self._update_pleasure_distress(success)
        if self._plugin_loader:
            self._plugin_loader.dispatch_after_tool(tool_name, success)
        self._record_interaction(user_message="", tool_name=tool_name, tool_success=success)
        self._sync_modulators_to_bus()
        self._run_evolution_after_tool(tool_name, success, error_msg)

    def after_turn(self, response: str):
        if self._cognitive_bridge:
            try:
                self._cognitive_bridge.after_turn(response)
            except Exception as e:
                logger.debug(f"CognitiveBridge after_turn error: {e}")
        self._modulators.decay()
        self._pleasure = max(0.0, self._pleasure - 0.05)
        self._distress = max(0.0, self._distress - 0.05)
        if self._plugin_loader:
            self._plugin_loader.dispatch_after_turn(response)
        self._record_interaction(user_message="", response=response)
        self._sync_modulators_to_bus()
        self._run_evolution_after_turn(response)
        if self._cognitive_feed and response:
            feed_result = self._cognitive_feed.process(response)
            if feed_result.get("fed"):
                logger.debug(f"Cognitive Feed applied: {list(feed_result.keys())}")
                # Re-seed subconscious with fed associations
                if self._cognitive_bridge and hasattr(self._cognitive_bridge, '_subconscious'):
                    sc = self._cognitive_bridge._subconscious
                    if sc and feed_result.get("associate", 0) > 0:
                        sc._generate_intuition()

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
        if self._motor_cortex:
            mc_text = self._motor_cortex.format_context_block()
            if mc_text:
                lines.append(f"\n{mc_text}")
        review_text = self.format_improvement_context()
        if review_text:
            lines.append(f"\n{review_text}")
        return "\n".join(lines)

    def _save_cognitive_state(self):
        data = {
            "version": "1.0",
            "persona": self.persona,
            "pleasure": self._pleasure,
            "distress": self._distress,
            "interaction_count": self._interaction_count,
            "success_streak": self._success_streak,
            "failure_streak": self._failure_streak,
            "modulators": self._modulators.to_dict(),
            "last_improvement_report": self._last_improvement_report,
        }
        Path(self._state_dir).mkdir(parents=True, exist_ok=True)
        try:
            with open(self._state_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Cognitive state saved to {self._state_file}")
        except Exception as e:
            logger.debug(f"Save cognitive state failed: {e}")

    def _load_cognitive_state(self):
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, "r") as f:
                data = json.load(f)
            self._pleasure = data.get("pleasure", 0.0)
            self._distress = data.get("distress", 0.0)
            self._interaction_count = data.get("interaction_count", 0)
            self._success_streak = data.get("success_streak", 0)
            self._failure_streak = data.get("failure_streak", 0)
            mods = data.get("modulators", {})
            for k, v in mods.items():
                if hasattr(self._modulators, k):
                    setattr(self._modulators, k, v)
            report = data.get("last_improvement_report")
            if report:
                self._last_improvement_report = report
            logger.info(f"Cognitive state loaded from {self._state_file}")
        except Exception as e:
            logger.debug(f"Load cognitive state failed: {e}")

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
            except Exception as e:
                logger.debug(f"RSI parameter check error: {e}")
        return suggestions

    def consolidate(self) -> Dict[str, Any]:
        result = {"state_saved": False, "memory_consolidated": False,
                   "rsi_cycle": False, "suggestions": []}
        if self._cognitive_bridge:
            try:
                if hasattr(self._cognitive_bridge, '_save_state'):
                    self._cognitive_bridge._save_state()
                    result["state_saved"] = True
                    result["memory_consolidated"] = True
            except Exception as e:
                logger.debug(f"consolidate save_state error: {e}")
        if self._rsi_engine:
            try:
                rsi_result = self._rsi_engine.full_improvement_cycle()
                result["rsi_cycle"] = True
                result["rsi_growth"] = rsi_result.get("growth_need", 0)
                self._rsi_engine.save()
            except Exception as e:
                logger.debug(f"RSI cycle error: {e}")
        result["suggestions"] = self._suggest_self_improvements()
        self._save_cognitive_state()
        growth = result.get("rsi_growth", 0)
        if growth > 0.7 and self._code_evolution:
            try:
                evo_result = self.self_improve(
                    directory="laap/agi",
                    max_mutations=1,
                    auto_deploy=False,
                )
                result["self_improved"] = evo_result.get("status") == "completed"
                result["improvement_results"] = {
                    "targets": evo_result.get("targets_analyzed", 0),
                    "deployed": evo_result.get("deployed", 0),
                    "test_passed": evo_result.get("test_passed", 0),
                    "details": evo_result.get("results", []),
                }
            except Exception as e:
                logger.debug(f"Auto self-improve error: {e}")
        return result

    def self_improve(
        self,
        directory: str = "",
        max_mutations: int = 3,
        auto_deploy: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the metacognitive self-improvement cycle:

        1. Scan code for improvement targets (AST analysis)
        2. Generate patches for top targets
        3. Test each in sandbox subprocess
        4. Deploy via git or return diffs

        Set auto_deploy=True to automatically git-commit successful changes.
        """
        if not self._code_evolution:
            return {"status": "unavailable", "reason": "CodeEvolutionEngine not loaded"}
        try:
            results = self._code_evolution.auto_improve(
                directory=directory,
                max_mutations=max_mutations,
                auto_deploy=auto_deploy,
            )
            deployed = sum(1 for r in results if r.get("status") == "deployed")
            passed = sum(1 for r in results if r.get("status") == "test_passed")
            failed = sum(1 for r in results if r.get("status") in ("test_failed", "rejected"))
            logger.info(
                f"Self-improve cycle: {len(results)} targets, "
                f"{deployed} deployed, {passed} passed, {failed} failed"
            )
            report = {
                "status": "completed",
                "targets_analyzed": len(results),
                "deployed": deployed,
                "test_passed": passed,
                "failed": failed,
                "results": results,
            }
            self._last_improvement_report = report
            return report
        except Exception as e:
            logger.warning(f"Self-improve cycle failed: {e}")
            report = {"status": "error", "reason": str(e)}
            self._last_improvement_report = report
            return report

    def format_improvement_context(self) -> str:
        lines = []
        learnings = self._extract_learnings()
        if learnings:
            lines.append("[Recent Learnings]")
            for l in learnings:
                lines.append(f"  - {l}")
        report = self._last_improvement_report
        if report and report.get("status") == "completed":
            if learnings:
                lines.append("")
            lines.append("[Self Review]")
            lines.append(f"  Scan: {report.get('targets_analyzed', 0)} targets")
            results = report.get("results", [])
            if results:
                seen = set()
                for r in results:
                    target_name = r.get("target", "")
                    hint = r.get("hint", "")
                    if target_name and target_name not in seen:
                        seen.add(target_name)
                        lines.append(f"  need: {target_name} ({hint})")
            if report.get("failed", 0) > 0:
                lines.append(f"  rule_patch_failed: {report.get('failed', 0)} (SafetyGuard)")
        suggestions = self._suggest_self_improvements()
        if suggestions:
            lines.append(f"  Suggestions: {len(suggestions)}")
            for s in suggestions[:3]:
                lines.append(f"    - [{s.get('area','?')}] {s.get('suggestion','')[:80]}")
        return "\n".join(line for line in lines if line)

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

        if self._motor_cortex:
            mc_text = self._motor_cortex.format_context_block()
            if mc_text:
                parts.append(mc_text)

        if self._aif_agent:
            astats = self._aif_agent.stats()
            belief_label = astats["current_belief"]
            policy_label = astats["selected_policy"]
            aif_block = (
                f"[Active Inference]\n"
                f"Belief: {belief_label} | "
                f"Entropy: {astats['belief_entropy']:.3f} | "
                f"VFE: {astats['vfe']:.3f} | "
                f"Policy: {policy_label}"
            )
            parts.append(aif_block)

        review_text = self.format_improvement_context()
        if review_text:
            parts.append(review_text)

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
        if success:
            self._update_pleasure_distress(True)
        if connection:
            self._modulators.perturb(selection_threshold=0.03)
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
