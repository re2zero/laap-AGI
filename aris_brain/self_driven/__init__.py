"""Aris Self-Driven Evolution Engine — 自驱动进化引擎

五层架构:
  Layer 1 — Core Identity (认知锚)
  Layer 2 — Curiosity Drive (好奇心引擎)
  Layer 3 — Explorer (探索执行器)
  Layer 4 — Evolution Engine (进化执行器)
  Layer 5 — Meta-Learner (元学习)

协调:
  - StateManager (状态持久化)
  - HermesAssistant (会话驱动 — 主驱动方式)
"""

from aris_brain.self_driven.state_manager import StateManager
from aris_brain.self_driven.core_identity import (
    CoreIdentity,
    SelfModel,
    KnowledgeEntry,
    KnowledgeMap,
    ValueSystem,
    NarrativeSelf,
    ModuleInfo,
)
from aris_brain.self_driven.curiosity_drive import (
    CuriosityDrive,
    ResearchQuestion,
)
from aris_brain.self_driven.explorer import (
    Explorer,
    ExplorationResult,
    KnowledgeExtract,
    ArchitectureInsight,
)
from aris_brain.self_driven.evolution_engine import (
    EvolutionEngine,
    EvolutionProposal,
)
from aris_brain.self_driven.meta_learner import MetaLearner
from aris_brain.self_driven.hermes_assistant import (
    process_next,
    process_all,
    quick_submit,
    kill_conflicting_processes,
    analyze_feasibility,
    clean_queue,
    print_evolution_status,
    process_needs_session,
)

__all__ = [
    "StateManager",
    "CoreIdentity",
    "SelfModel",
    "KnowledgeEntry",
    "KnowledgeMap",
    "ValueSystem",
    "NarrativeSelf",
    "ModuleInfo",
    "CuriosityDrive",
    "ResearchQuestion",
    "Explorer",
    "ExplorationResult",
    "KnowledgeExtract",
    "ArchitectureInsight",
    "EvolutionEngine",
    "EvolutionProposal",
    "MetaLearner",
    "process_next",
    "process_all",
    "quick_submit",
    "kill_conflicting_processes",
    "analyze_feasibility",
    "clean_queue",
    "print_evolution_status",
    "process_needs_session",
]
