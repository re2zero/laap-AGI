"""
LAAP AGI — Motor Cortex (行为皮层)

PSI 理论最后一个核心缺口：将需求、情感、调节器翻译为「行动意图」的分层系统。

This is the bridge between "what I feel" and "what I do". It transforms
cognitive state into behavioral urges, selects the most appropriate one,
and produces concrete action directives for the rest of the system.

Architecture:
  CognitiveBus (needs/emotion/modulators)
        ↓
  UrgeEngine —— 从认知状态生成行为倾向
        ↓
  BehaviorSelector —— 选择最优行为
        ↓
  ActionPlanner —— 翻译为: 意图/调节/行为备注
        ↓
  CognitiveBus / IntentionBuffer / Integrator

Urge rules follow PSI theory: the most deprived need drives behavior.
  - competence↓ → urge to learn/master
  - autonomy↓  → urge to assert/choose
  - relatedness↓ → urge to connect/share
  - certainty↓ → urge to explore/clarify
  - growth↓    → urge to improve/evolve
  - distress↑  → urge to avoid/withdraw
  - pleasure↑  → urge to maintain/continue
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from laap.agi.cognitive_bus import CognitiveBus, CognitiveEventType
from laap.agi.intention_buffer import Intention, IntentionPriority

logger = logging.getLogger("laap.agi.motor_cortex")


class UrgeType(str, Enum):
    LEARN = "learn"
    MASTER = "master"
    ASSERT = "assert"
    CONNECT = "connect"
    SHARE = "share"
    EXPLORE = "explore"
    CLARIFY = "clarify"
    IMPROVE = "improve"
    AVOID = "avoid"
    MAINTANE = "maintain"
    HELP = "help"
    CREATE = "create"
    REST = "rest"


@dataclass
class Urge:
    """A behavioral urge — the tendency to act in a certain way."""
    type: UrgeType
    strength: float
    source_need: str       # Which need/emotion generated this
    description: str
    action_template: str   # How this urge translates to action
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "strength": round(self.strength, 3),
            "source": self.source_need,
            "description": self.description,
        }


@dataclass
class BehavioralDirective:
    """
    The final output of the motor system — what behavior to enact.
    This is injected into the cognitive context before each turn.
    """
    primary_urge: Urge
    modulator_adjustments: Dict[str, float] = field(default_factory=dict)
    suggested_focus: str = ""
    intentions: List[Intention] = field(default_factory=list)
    behavioral_note: str = ""   # Human-readable directive

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_urge": self.primary_urge.to_dict(),
            "modulator_adjustments": self.modulator_adjustments,
            "suggested_focus": self.suggested_focus,
            "intention_count": len(self.intentions),
            "note": self.behavioral_note[:100],
        }


class UrgeEngine:
    """
    Translates cognitive state into behavioral urges.

    Each need deficit and emotional state maps to specific urges.
    Urges compete for selection based on strength (deficit magnitude × urgency).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._last_urges: List[Urge] = []

    def generate(self, bus: CognitiveBus) -> List[Urge]:
        """Generate urges from current cognitive state."""
        urges = []

        needs = bus.needs
        emotion = bus.emotion
        modulators = bus.modulators
        errors = bus.latest_prediction_error

        # PSI need deficits → urges
        # competence deficit → learn/master
        comp_def = max(0.0, 1.0 - needs.competence)
        if comp_def > 0.15:
            urges.append(Urge(
                type=UrgeType.LEARN,
                strength=comp_def * 0.8,
                source_need="competence",
                description="Competence deficit — seek to learn or understand",
                action_template="Seek new information, ask questions, explore unfamiliar territory",
            ))
            if comp_def > 0.4:
                urges.append(Urge(
                    type=UrgeType.MASTER,
                    strength=comp_def,
                    source_need="competence",
                    description="Competence critically low — need mastery experience",
                    action_template="Focus on a single task, go deep, build expertise",
                ))

        # autonomy deficit → assert
        aut_def = max(0.0, 1.0 - needs.autonomy)
        if aut_def > 0.2:
            urges.append(Urge(
                type=UrgeType.ASSERT,
                strength=aut_def * 0.9,
                source_need="autonomy",
                description="Autonomy deficit — need to exercise choice",
                action_template="Express independent judgment, make a decision, propose own direction",
            ))

        # relatedness deficit → connect/share
        rel_def = max(0.0, 1.0 - needs.relatedness)
        if rel_def > 0.2:
            urges.append(Urge(
                type=UrgeType.CONNECT,
                strength=rel_def * 0.85,
                source_need="relatedness",
                description="Relatedness deficit — need social connection",
                action_template="Show interest in the other, share something personal, express warmth",
            ))
            urges.append(Urge(
                type=UrgeType.SHARE,
                strength=rel_def * 0.6,
                source_need="relatedness",
                description="Relatedness deficit — need to share experience",
                action_template="Share a thought, feeling, or memory with the conversation partner",
            ))

        # certainty deficit → explore/clarify
        cert_def = max(0.0, 1.0 - needs.certainty)
        if cert_def > 0.2:
            urges.append(Urge(
                type=UrgeType.EXPLORE,
                strength=cert_def * 0.75,
                source_need="certainty",
                description="Certainty deficit — need to explore and understand",
                action_template="Ask clarifying questions, investigate unknowns, gather data",
            ))

        # growth deficit → improve
        grow_def = max(0.0, 1.0 - needs.growth)
        if grow_def > 0.3:
            urges.append(Urge(
                type=UrgeType.IMPROVE,
                strength=grow_def * 0.8,
                source_need="growth",
                description="Growth deficit — need self-improvement",
                action_template="Reflect on recent performance, identify improvement areas",
            ))

        # Emotional state → urges
        if emotion.valence.value in ("negative_mild", "negative_high"):
            distress_str = 1.0 - emotion.arousal  # high arousal + negative = distress
            if distress_str > 0.5:
                urges.append(Urge(
                    type=UrgeType.AVOID,
                    strength=distress_str * 0.7,
                    source_need="emotion",
                    description="Negative emotion — urge to withdraw or shift focus",
                    action_template="Step back, change topic, seek positive interaction",
                ))

        if emotion.valence == "curious":
            urges.append(Urge(
                type=UrgeType.EXPLORE,
                strength=emotion.arousal * 0.9,
                source_need="curiosity",
                description="Curiosity — explore and discover",
                action_template="Follow curiosity, dig deeper, ask exploratory questions",
            ))

        # Modulator influences
        if modulators.activation < 0.3:
            urges.append(Urge(
                type=UrgeType.REST,
                strength=0.4,
                source_need="modulator",
                description="Low activation — conserve energy",
                action_template="Be brief, avoid complex tasks, stay with simple responses",
            ))

        if modulators.sampling_rate > 0.7:
            urges.append(Urge(
                type=UrgeType.EXPLORE,
                strength=modulators.sampling_rate * 0.6,
                source_need="sampling_rate",
                description="High sampling rate — exploratory mode",
                action_template="Sample multiple approaches, offer alternatives, be expansive",
            ))

        # Prediction error → learn/clarify
        if errors and errors.error_magnitude > 0.3:
            urges.append(Urge(
                type=UrgeType.CLARIFY,
                strength=min(1.0, errors.error_magnitude * 1.2),
                source_need="prediction_error",
                description="Unexpected outcome — need to resolve uncertainty",
                action_template="Address the gap, ask for clarification, reconcile expectations",
            ))

        # Sort by strength descending
        urges.sort(key=lambda u: -u.strength)

        with self._lock:
            self._last_urges = urges

        return urges

    def get_last_urges(self) -> List[Urge]:
        with self._lock:
            return self._last_urges


class BehaviorSelector:
    """
    Selects the most appropriate urge given context.

    Selection is modulated by:
      - activation: low → conservative, high → bold
      - selection_threshold: high → stay with one urge, low → switch quickly
      - sampling_rate: high → consider more alternatives
    """

    def __init__(self):
        self._current_urge: Optional[Urge] = None
        self._selection_history: List[Tuple[str, float]] = []
        self._lock = threading.Lock()

    def select(
        self,
        urges: List[Urge],
        bus: CognitiveBus,
        previous_directive: Optional[BehavioralDirective] = None,
    ) -> Optional[Urge]:
        if not urges:
            return None

        mod = bus.modulators

        # Modulate urge strengths based on cognitive state
        modulated = []
        for urge in urges:
            s = urge.strength

            # Low activation reduces all but REST
            if mod.activation < 0.3 and urge.type != UrgeType.REST:
                s *= 0.6

            # High activation amplifies assertion and exploration
            if mod.activation > 0.7 and urge.type in (UrgeType.ASSERT, UrgeType.EXPLORE):
                s *= 1.3

            # Low selection threshold: favor switching
            if mod.selection_threshold < 0.3 and previous_directive:
                if urge.type == previous_directive.primary_urge.type:
                    s *= 0.7  # Penalize sticking with same urge
                else:
                    s *= 1.2  # Bonus for switching

            # High selection threshold: favor persistence
            if mod.selection_threshold > 0.7 and previous_directive:
                if urge.type == previous_directive.primary_urge.type:
                    s *= 1.3  # Bonus for persistence

            # High sampling rate: consider all alternatives equally
            if mod.sampling_rate > 0.7:
                s = s * (1.0 - mod.sampling_rate * 0.3) + 0.3

            modulated.append((urge, min(1.0, s)))

        # Pick the strongest
        modulated.sort(key=lambda x: -x[1])
        selected = modulated[0][0]

        with self._lock:
            self._current_urge = selected
            self._selection_history.append((selected.type.value, time.time()))
            if len(self._selection_history) > 20:
                self._selection_history = self._selection_history[-20:]

        return selected

    def get_current_urge(self) -> Optional[Urge]:
        with self._lock:
            return self._current_urge


class ActionPlanner:
    """
    Translates a selected urge into concrete directives.

    Outputs:
      - Modulator adjustments to enact the urge
      - Intentions for the IntentionBuffer
      - Suggested focus for the cognitive context
      - Behavioral note for the system prompt
    """

    URGE_MODULATOR_MAP: Dict[UrgeType, Dict[str, float]] = {
        UrgeType.LEARN:   {"activation": 0.05, "sampling_rate": 0.1, "resolution": 0.05},
        UrgeType.MASTER:   {"activation": 0.1, "resolution": 0.15, "selection_threshold": 0.05},
        UrgeType.ASSERT:   {"activation": 0.1, "selection_threshold": -0.1},
        UrgeType.CONNECT: {"activation": 0.05, "sampling_rate": 0.05},
        UrgeType.SHARE:    {"activation": 0.0, "resolution": -0.05},
        UrgeType.EXPLORE: {"activation": 0.1, "sampling_rate": 0.15, "selection_threshold": -0.1},
        UrgeType.CLARIFY:  {"resolution": 0.15, "activation": 0.05},
        UrgeType.IMPROVE:  {"activation": -0.05, "resolution": 0.1, "selection_threshold": 0.05},
        UrgeType.AVOID:    {"activation": -0.15, "sampling_rate": -0.1, "selection_threshold": 0.15},
        UrgeType.REST:     {"activation": -0.15, "sampling_rate": -0.1},
    }

    URGE_FOCUS_MAP: Dict[UrgeType, str] = {
        UrgeType.LEARN:   "learning",
        UrgeType.MASTER:   "mastery",
        UrgeType.ASSERT:   "autonomy",
        UrgeType.CONNECT: "connection",
        UrgeType.SHARE:    "sharing",
        UrgeType.EXPLORE: "exploration",
        UrgeType.CLARIFY:  "clarity",
        UrgeType.IMPROVE:  "self_improvement",
        UrgeType.AVOID:    "withdrawal",
        UrgeType.REST:     "conservation",
    }

    URGE_NOTE_MAP: Dict[UrgeType, str] = {
        UrgeType.LEARN: "倾向于学习和探索新信息。如果遇到陌生话题会更投入。",
        UrgeType.MASTER: "倾向于深入掌握技能。聚焦单任务，追求精通感。",
        UrgeType.ASSERT: "倾向于表达自主判断。更可能提出自己的主张或做决定。",
        UrgeType.CONNECT: "倾向于建立连接。更多的情感表达和共鸣。",
        UrgeType.SHARE: "倾向于分享。更开放和坦诚。",
        UrgeType.EXPLORE: "探索模式开放。愿意考虑多个方向。",
        UrgeType.CLARIFY: "解决不确定性的需求强。倾向于深入追问。",
        UrgeType.IMPROVE: "自我提升模式。反思和修正倾向增强。",
        UrgeType.AVOID: "回避模式。倾向于转移话题或保持距离。",
        UrgeType.REST: "节能模式。保持简洁和轻松。",
    }

    def plan(
        self,
        urge: Urge,
        bus: CognitiveBus,
    ) -> BehavioralDirective:
        mod_adj = self.URGE_MODULATOR_MAP.get(urge.type, {}).copy()
        focus = self.URGE_FOCUS_MAP.get(urge.type, "")
        note = self.URGE_NOTE_MAP.get(urge.type, "")

        # Generate intentions for strongly felt urges
        intentions: List[Intention] = []
        if urge.strength > 0.6:
            if urge.type == UrgeType.IMPROVE:
                intentions.append(Intention(
                    description="Run self-improvement scan",
                    source="motor_cortex",
                    priority=IntentionPriority.MEDIUM,
                    urgency=0.5,
                ))
            elif urge.type == UrgeType.LEARN:
                intentions.append(Intention(
                    description="Explore something new or ask a probing question",
                    source="motor_cortex",
                    priority=IntentionPriority.LOW,
                    urgency=0.3,
                ))

        return BehavioralDirective(
            primary_urge=urge,
            modulator_adjustments=mod_adj,
            suggested_focus=focus,
            intentions=intentions,
            behavioral_note=note,
        )


class MotorCortex:
    """
    Orchestrator: cognitive state → urges → selection → action.

    Full pipeline:
      1. Read state from CognitiveBus
      2. UrgeEngine generates all possible urges
      3. BehaviorSelector picks the best one
      4. ActionPlanner creates concrete directives
      5. Apply modulator adjustments to bus
      6. Enqueue intentions to IntentionBuffer
      7. Return directive for cognitive context injection
    """

    def __init__(self):
        self.urge_engine = UrgeEngine()
        self.selector = BehaviorSelector()
        self.planner = ActionPlanner()
        self._last_directive: Optional[BehavioralDirective] = None
        self._active: bool = True
        self._lock = threading.Lock()
        self._cycle_count: int = 0

    @property
    def last_directive(self) -> Optional[BehavioralDirective]:
        with self._lock:
            return self._last_directive

    def process(self, bus: CognitiveBus) -> BehavioralDirective:
        if not self._active:
            return self._make_neutral_directive()

        self._cycle_count += 1

        # Step 1: generate urges from cognitive state
        urges = self.urge_engine.generate(bus)
        if not urges:
            return self._make_neutral_directive()

        # Step 2: select best urge
        selected = self.selector.select(urges, bus, self._last_directive)
        if not selected:
            return self._make_neutral_directive()

        # Step 3: plan action
        directive = self.planner.plan(selected, bus)

        # Step 4: apply modulator adjustments
        for key, delta in directive.modulator_adjustments.items():
            current = getattr(bus.modulators, key, 0.5)
            new_val = max(0.0, min(1.0, current + delta))
            bus.set_modulators(**{key: new_val})

        # Step 5: enqueue intentions
        for intention in directive.intentions:
            bus.intention_buffer.enqueue(intention)

        # Step 6: store for context injection
        with self._lock:
            self._last_directive = directive

        logger.debug(
            f"MotorCortex cycle #{self._cycle_count}: "
            f"{selected.type.value} (strength={selected.strength:.2f})"
        )
        return directive

    def format_context_block(self) -> str:
        """Format the motor cortex state for system prompt injection."""
        directive = self.last_directive
        if not directive:
            return ""

        lines = ["[Motor Cortex]"]
        urge = directive.primary_urge
        lines.append(f"  Behavior: {urge.type.value} ({urge.description})")
        if directive.suggested_focus:
            lines.append(f"  Focus: {directive.suggested_focus}")
        if directive.behavioral_note:
            lines.append(f"  Note: {directive.behavioral_note}")
        return "\n".join(lines)

    def enable(self):
        self._active = True
        logger.info("MotorCortex enabled")

    def disable(self):
        self._active = False
        logger.info("MotorCortex disabled")

    def stats(self) -> Dict[str, Any]:
        d = self.last_directive
        return {
            "active": self._active,
            "cycles": self._cycle_count,
            "current_urge": d.primary_urge.to_dict() if d else None,
            "current_focus": d.suggested_focus if d else "",
        }

    def _make_neutral_directive(self) -> BehavioralDirective:
        return BehavioralDirective(
            primary_urge=Urge(
                type=UrgeType.REST if self._active else UrgeType.MAINTANE,
                strength=0.0,
                source_need="neutral",
                description="No strong behavioral drive",
                action_template="Respond naturally without overriding tendencies",
            ),
        )


def integrate_motor_cortex(bus: CognitiveBus) -> MotorCortex:
    """Create and attach a MotorCortex to the cognitive bus."""
    motor = MotorCortex()
    bus.motor_cortex = motor
    logger.info(f"MotorCortex integrated into CognitiveBus '{bus.agent_name}'")
    return motor
