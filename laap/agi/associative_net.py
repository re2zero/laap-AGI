"""
LAAP AGI — Associative Node Net (联想节点网络)

A simplified MicroPsi-inspired spreading activation network for
subconscious associative memory and intuition generation.

Based on principles from:
  - Bach, J. (2009). Principles of Synthetic Intelligence PSI
  - Bach & Vuine (2003). Designing Agents with MicroPsi Node Nets
  - Dörner, D. PSI theory: hierarchical spreading activation networks

Architecture:
  ConceptNode — fundamental unit with activation, gates, decay
  WeightedLink — directional connection between nodes
  NodeSpace — container with directional activators and associators
  AssociativeNet — orchestrator: seed → spread → settle → extract
"""

import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("laap.agi.associative_net")


class GateType(Enum):
    """Directional gate types for activation propagation (MicroPsi-inspired)."""
    GEN = "gen"           # General activation (spread to all connected)
    POR = "por"           # Forward causal (cause → effect)
    RET = "ret"           # Backward causal (effect → cause)
    SUR = "sur"           # Part-of / subsumption (whole → part)


@dataclass
class WeightedLink:
    target_id: str
    weight: float          # 0.0-1.0 link strength
    gate: GateType = GateType.GEN
    is_forward: bool = True


@dataclass
class ConceptNode:
    id: str
    label: str                # Human-readable name
    activation: float = 0.0   # Current activation [0, 1]
    baseline: float = 0.0     # Resting activation (decay target)
    activation_history: List[float] = field(default_factory=list)
    decay_rate: float = 0.1   # Per-step decay toward baseline
    links: List[WeightedLink] = field(default_factory=list)
    created_at: float = 0.0
    last_activated: float = 0.0

    def step_decay(self):
        """Decay activation toward baseline."""
        diff = self.activation - self.baseline
        if abs(diff) > 0.001:
            self.activation -= diff * self.decay_rate
        else:
            self.activation = self.baseline
        self.activation = max(0.0, min(1.0, self.activation))

    def record_state(self):
        self.activation_history.append(self.activation)
        if len(self.activation_history) > 100:
            self.activation_history = self.activation_history[-100:]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label,
            "activation": round(self.activation, 3),
            "baseline": self.baseline, "decay_rate": self.decay_rate,
            "links": [{"target": l.target_id, "weight": round(l.weight, 3),
                       "gate": l.gate.value} for l in self.links],
        }


class AssociativeNet:
    """
    Spreading activation node net for associative memory.

    Usage:
        net = AssociativeNet()
        net.add_node("tech", "technology")
        net.add_node("solve", "solving")
        net.add_link("tech", "solve", weight=0.6, gate=GateType.POR)
        net.seed("tech", amount=0.8)
        net.spread(steps=5)
        top = net.get_top_activated(k=3)
    """

    def __init__(self, decay_global: float = 0.05, spread_factor: float = 0.7,
                 associator_rate: float = 0.05, coherence_threshold: float = 0.15):
        self._nodes: Dict[str, ConceptNode] = {}
        self._lock = threading.Lock()
        self._step_count = 0

        # Global parameters
        self.decay_global = decay_global          # Per-step activation decay
        self.spread_factor = spread_factor        # How much activation propagates
        self.associator_rate = associator_rate    # Learning rate for link strengthening
        self.coherence_threshold = coherence_threshold

    # ── Node Management ─────────────────────────────────

    def add_node(self, node_id: str, label: str = "",
                 baseline: float = 0.0, decay_rate: float = 0.1) -> ConceptNode:
        with self._lock:
            if node_id in self._nodes:
                return self._nodes[node_id]
            node = ConceptNode(
                id=node_id, label=label or node_id,
                baseline=baseline, decay_rate=decay_rate,
                created_at=time.time(),
            )
            self._nodes[node_id] = node
            return node

    def get_node(self, node_id: str) -> Optional[ConceptNode]:
        with self._lock:
            return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._nodes

    def get_node_count(self) -> int:
        with self._lock:
            return len(self._nodes)

    # ── Link Management ─────────────────────────────────

    def add_link(self, from_id: str, to_id: str, weight: float = 0.5,
                 gate: GateType = GateType.GEN):
        with self._lock:
            node = self._nodes.get(from_id)
            if not node:
                logger.debug(f"add_link: source node '{from_id}' not found")
                return
            existing = [l for l in node.links if l.target_id == to_id and l.gate == gate]
            if existing:
                existing[0].weight = min(1.0, existing[0].weight + weight * 0.1)
            else:
                node.links.append(WeightedLink(target_id=to_id, weight=weight, gate=gate))

    def get_links(self, node_id: str, gate: Optional[GateType] = None) -> List[WeightedLink]:
        node = self._nodes.get(node_id)
        if not node:
            return []
        if gate:
            return [l for l in node.links if l.gate == gate]
        return node.links

    def link_strength(self, from_id: str, to_id: str) -> float:
        node = self._nodes.get(from_id)
        if not node:
            return 0.0
        for l in node.links:
            if l.target_id == to_id:
                return l.weight
        return 0.0

    # ── Activation ──────────────────────────────────────

    def seed(self, node_id: str, amount: float = 0.5):
        """Directly activate a node (like feeding a seed keyword to subconscious)."""
        node = self.get_node(node_id)
        if node:
            node.activation = min(1.0, node.activation + amount)
            node.last_activated = time.time()

    def seed_keywords(self, keywords: Dict[str, float]):
        """Activate multiple nodes at once, with different strengths."""
        for kw, amount in keywords.items():
            self.seed(kw, amount)

    def spread(self, steps: int = 3) -> Dict[str, float]:
        """
        Run spreading activation for N steps.
        Returns activation landscape after settling.
        """
        with self._lock:
            for _ in range(steps):
                self._step_count += 1
                activations: Dict[str, float] = {}

                # Compute incoming activation for each node
                for nid, node in self._nodes.items():
                    incoming = 0.0
                    source_count = 0
                    for src_id, src_node in self._nodes.items():
                        if src_id == nid:
                            continue
                        for link in src_node.links:
                            if link.target_id == nid:
                                incoming += src_node.activation * link.weight
                                source_count += 1
                    if source_count > 0:
                        incoming /= source_count
                    activations[nid] = incoming

                # Apply sigmoid-gated update + local decay
                for nid, node in self._nodes.items():
                    incoming = activations.get(nid, 0.0)
                    net_in = incoming * self.spread_factor + node.baseline * (1 - self.spread_factor)
                    new_act = self._sigmoid(net_in, gain=4.0, threshold=0.3)
                    node.activation = max(0.0, min(1.0, new_act))
                    node.step_decay()
                    node.record_state()

                # Associator: strengthen co-active link pairs
                if self.associator_rate > 0:
                    self._associate()

            return {nid: n.activation for nid, n in self._nodes.items()}

    def _sigmoid(self, x: float, gain: float = 4.0, threshold: float = 0.3) -> float:
        """Sigmoid activation function."""
        return 1.0 / (1.0 + math.exp(-gain * (x - threshold)))

    def _associate(self):
        """He bb rule: strengthen links between co-active nodes."""
        active = [(nid, n) for nid, n in self._nodes.items()
                  if n.activation > self.coherence_threshold]
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                id_a, node_a = active[i]
                id_b, node_b = active[j]
                prod = node_a.activation * node_b.activation
                delta = prod * self.associator_rate
                # Strengthen bidirectional links
                self._modulate_link(id_a, id_b, delta)
                self._modulate_link(id_b, id_a, delta)

    def _modulate_link(self, from_id: str, to_id: str, delta: float):
        """Strengthen or weaken a specific link."""
        node = self._nodes.get(from_id)
        if not node:
            return
        for link in node.links:
            if link.target_id == to_id:
                link.weight = min(1.0, max(0.0, link.weight + delta))
                return
        node.links.append(WeightedLink(target_id=to_id, weight=delta, gate=GateType.GEN))

    def decay_all(self, factor: float = 1.0):
        """Global decay of all node activations."""
        with self._lock:
            for node in self._nodes.values():
                node.activation = max(0.0, node.activation - self.decay_global * factor)

    # ── Queries ─────────────────────────────────────────

    def get_top_activated(self, k: int = 5, min_activation: float = 0.0) -> List[ConceptNode]:
        with self._lock:
            candidates = [n for n in self._nodes.values()
                          if n.activation >= min_activation]
            candidates.sort(key=lambda n: -n.activation)
            return candidates[:k]

    def get_activation_landscape(self) -> Dict[str, float]:
        with self._lock:
            return {nid: n.activation for nid, n in self._nodes.items()}

    def get_coherence(self) -> float:
        """
        Compute global coherence: ratio of nodes above threshold
        to total nodes. Higher = more settled / stable activation.
        """
        with self._lock:
            if not self._nodes:
                return 0.0
            above = sum(1 for n in self._nodes.values()
                        if n.activation > self.coherence_threshold)
            return above / len(self._nodes)

    # ── Vocabulary / Knowledge Injection ────────────────

    def learn_pair(self, concept_a: str, concept_b: str, weight: float = 0.5):
        """Learn a bidirectional association between two concepts."""
        self.add_node(concept_a)
        self.add_node(concept_b)
        self.add_link(concept_a, concept_b, weight=weight)
        self.add_link(concept_b, concept_a, weight=weight)

    def learn_sequence(self, concepts: List[str], weight: float = 0.4):
        """Learn sequential associations (POR/RET links)."""
        for i in range(len(concepts) - 1):
            a, b = concepts[i], concepts[i + 1]
            self.add_node(a)
            self.add_node(b)
            self.add_link(a, b, weight=weight, gate=GateType.POR)
            self.add_link(b, a, weight=weight * 0.3, gate=GateType.RET)

    # ── Persistence ─────────────────────────────────────

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
                "params": {
                    "decay_global": self.decay_global,
                    "spread_factor": self.spread_factor,
                    "associator_rate": self.associator_rate,
                    "coherence_threshold": self.coherence_threshold,
                },
                "step": self._step_count,
            }

    @classmethod
    def from_dict(cls, data: dict) -> "AssociativeNet":
        net = cls(
            decay_global=data.get("params", {}).get("decay_global", 0.05),
            spread_factor=data.get("params", {}).get("spread_factor", 0.7),
            associator_rate=data.get("params", {}).get("associator_rate", 0.05),
            coherence_threshold=data.get("params", {}).get("coherence_threshold", 0.15),
        )
        net._step_count = data.get("step", 0)
        raw = data.get("nodes", {})
        for nid, ndata in raw.items():
            node = ConceptNode(
                id=nid, label=ndata.get("label", nid),
                activation=ndata.get("activation", 0.0),
                baseline=ndata.get("baseline", 0.0),
                decay_rate=ndata.get("decay_rate", 0.1),
                links=[WeightedLink(
                    target_id=l["target"], weight=l["weight"],
                    gate=GateType(l.get("gate", "gen")),
                ) for l in ndata.get("links", [])],
                created_at=ndata.get("created_at", 0.0),
                last_activated=ndata.get("last_activated", 0.0),
            )
            net._nodes[nid] = node
        return net
