"""
LAAP AGI — Associative Node Net with IAC Dynamics (联想节点网络)

A spreading activation network inspired by Interactive Activation and
Competition (IAC) networks (McClelland & Rumelhart, PDP Handbook) and
ACT-R power-law memory decay (Anderson, 1983).

Architecture:
  - Grossberg-style IAC dynamics: activation in [min, max] with separate
    excitation and inhibition channels
  - ACT-R power-law link decay: weight(t) = initial * (1 + age)^(-d)
  - Domain-based competitive pools: nodes in same domain inhibit each other
  - Phase control: network settles in localized (Phase I) rather than
    globally-saturating (Phase III) regime
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
    GEN = "gen"           # General activation
    POR = "por"           # Forward causal
    RET = "ret"           # Backward causal
    SUR = "sur"           # Part-of / subsumption


@dataclass
class WeightedLink:
    target_id: str
    weight: float          # Base weight (decays over time)
    gate: GateType = GateType.GEN
    is_forward: bool = True
    last_used: float = 0.0  # Timestamp of last activation

    def effective_weight(self, decay_d: float = 0.5, now: Optional[float] = None) -> float:
        """ACT-R power-law decayed weight: w_eff = w * (1 + age)^(-d)."""
        age = (now or time.time()) - self.last_used
        if age < 1.0:
            return self.weight
        decay_factor = (1.0 + age) ** (-decay_d)
        return self.weight * decay_factor


@dataclass
class ConceptNode:
    id: str
    label: str
    activation: float = 0.0        # Current activation [min, max]
    baseline: float = 0.0          # Resting level (0.0)
    activation_min: float = -0.2   # Minimum activation (IAC lower bound)
    activation_max: float = 1.0    # Maximum activation (IAC upper bound)
    decay_rate: float = 0.1        # Decay toward baseline per step
    domain: str = "general"        # Competitive pool membership
    links: List[WeightedLink] = field(default_factory=list)
    created_at: float = 0.0
    last_activated: float = 0.0
    activation_history: List[float] = field(default_factory=list)

    def step_iac(self, excitation: float, inhibition: float,
                 alpha: float = 0.1, gamma: float = 0.1):
        """
        Grossberg IAC update:
          Δact = (max - act) * exc * alpha + (act - min) * inh * gamma
                 - decay * (act - rest)
        """
        exc_term = (self.activation_max - self.activation) * max(0, excitation) * alpha
        inh_term = (self.activation - self.activation_min) * min(0, inhibition) * gamma
        dec_term = self.decay_rate * (self.activation - self.baseline)
        self.activation += exc_term + inh_term - dec_term
        self.activation = max(self.activation_min, min(self.activation_max, self.activation))

    def record_state(self):
        self.activation_history.append(self.activation)
        if len(self.activation_history) > 100:
            self.activation_history = self.activation_history[-100:]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label,
            "activation": round(self.activation, 3),
            "baseline": self.baseline, "decay_rate": self.decay_rate,
            "domain": self.domain,
            "links": [{"target": l.target_id, "weight": round(l.weight, 3),
                       "gate": l.gate.value, "last_used": l.last_used}
                      for l in self.links],
        }


class AssociativeNet:
    """
    IAC-based spreading activation network.

    Usage:
        net = AssociativeNet()
        net.add_node("tech", "technology", domain="knowledge")
        net.add_link("tech", "solve", weight=0.4)
        net.seed("tech", amount=0.5)
        net.spread(steps=5)
        top = net.get_top_activated(k=3)
    """

    def __init__(self, global_decay: float = 0.08,
                 iac_alpha: float = 0.12, iac_gamma: float = 0.15,
                 associator_rate: float = 0.03, coherence_threshold: float = 0.15,
                 link_decay_d: float = 0.5,  # ACT-R power-law decay exponent
                 prune_threshold: float = 0.01):
        self._nodes: Dict[str, ConceptNode] = {}
        self._lock = threading.Lock()
        self._step_count = 0
        self._prune_counter = 0

        # IAC parameters
        self.global_decay = global_decay
        self.iac_alpha = iac_alpha          # Excitation scaling
        self.iac_gamma = iac_gamma           # Inhibition scaling

        # Learning & decay
        self.associator_rate = associator_rate
        self.link_decay_d = link_decay_d          # ACT-R d exponent
        self.coherence_threshold = coherence_threshold

        # Pruning
        self.prune_threshold = prune_threshold

    # ── Node Management ─────────────────────────────────

    def add_node(self, node_id: str, label: str = "",
                 baseline: float = 0.0, decay_rate: float = 0.1,
                 domain: str = "general") -> ConceptNode:
        with self._lock:
            if node_id in self._nodes:
                return self._nodes[node_id]
            node = ConceptNode(
                id=node_id, label=label or node_id,
                baseline=baseline, decay_rate=decay_rate,
                domain=domain, created_at=time.time(),
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
                existing[0].last_used = time.time()
            else:
                node.links.append(WeightedLink(
                    target_id=to_id, weight=weight, gate=gate,
                    last_used=time.time(),
                ))

    def get_links(self, node_id: str, gate: Optional[GateType] = None) -> List[WeightedLink]:
        node = self._nodes.get(node_id)
        if not node:
            return []
        if gate:
            return [l for l in node.links if l.gate == gate]
        return node.links

    # ── Activation ──────────────────────────────────────

    def seed(self, node_id: str, amount: float = 0.5):
        node = self.get_node(node_id)
        if node:
            node.activation = max(node.activation, min(node.activation_max, amount))
            node.last_activated = time.time()

    def seed_keywords(self, keywords: Dict[str, float]):
        for kw, amount in keywords.items():
            self.seed(kw, amount)

    def spread(self, steps: int = 4) -> Dict[str, float]:
        """Run IAC spreading activation for N steps."""
        with self._lock:
            now = time.time()
            for _ in range(steps):
                self._step_count += 1

                # Compute excitation (from linked nodes) and
                # inhibition (from same-domain nodes)
                exc_input: Dict[str, float] = {}
                inh_input: Dict[str, float] = {}

                for nid, node in self._nodes.items():
                    total_exc = 0.0
                    exc_count = 0
                    total_inh = 0.0
                    inh_count = 0

                    for src_id, src_node in self._nodes.items():
                        if src_id == nid or src_node.activation <= 0:
                            continue

                        # Excitatory: linked nodes with positive activation
                        for link in src_node.links:
                            if link.target_id == nid:
                                w_eff = link.effective_weight(self.link_decay_d, now)
                                if w_eff > 0:
                                    total_exc += src_node.activation * w_eff
                                    exc_count += 1
                                link.last_used = now

                        # Inhibitory: same-domain nodes (competitive pool)
                        if src_node.domain == node.domain and src_node.activation > 0:
                            total_inh += src_node.activation * 0.3  # domain inhibition
                            inh_count += 1

                    exc_input[nid] = total_exc / exc_count if exc_count > 0 else 0.0
                    inh_input[nid] = -(total_inh / inh_count) if inh_count > 1 else 0.0

                # IAC update for each node
                for nid, node in self._nodes.items():
                    exc = exc_input.get(nid, 0.0)
                    inh = inh_input.get(nid, 0.0)
                    node.step_iac(exc, inh, alpha=self.iac_alpha, gamma=self.iac_gamma)
                    node.record_state()

                # Stimulus-independent decay for all nodes
                for node in self._nodes.values():
                    if node.activation > node.baseline:
                        node.activation -= self.global_decay * (node.activation - node.baseline)

            # After spreading, apply ACT-R time decay to links
            self._decay_links()

            return {nid: n.activation for nid, n in self._nodes.items()}

    def _decay_links(self):
        """Apply ACT-R power-law decay to all links."""
        now = time.time()
        for node in self._nodes.values():
            for link in node.links:
                age = now - link.last_used
                if age > 10.0:  # Only decay links unused for 10s+
                    decay_factor = (1.0 + age) ** (-self.link_decay_d)
                    link.weight *= decay_factor
                    link.weight = max(0.0, link.weight)

    # ── Associator (Hebbian learning) ───────────────────

    def _associate(self):
        """Strengthen co-active node pairs."""
        active = [(nid, n) for nid, n in self._nodes.items()
                  if n.activation > self.coherence_threshold]
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                id_a, node_a = active[i]
                id_b, node_b = active[j]
                prod = node_a.activation * node_b.activation
                delta = prod * self.associator_rate
                self._modulate_link(id_a, id_b, delta)
                self._modulate_link(id_b, id_a, delta)

    def _modulate_link(self, from_id: str, to_id: str, delta: float):
        node = self._nodes.get(from_id)
        if not node:
            return
        for link in node.links:
            if link.target_id == to_id:
                link.weight = min(1.0, max(0.0, link.weight + delta))
                link.last_used = time.time()
                return
        node.links.append(WeightedLink(target_id=to_id, weight=delta,
                                        last_used=time.time()))

    # ── Knowledge Injection ─────────────────────────────

    def learn_pair(self, concept_a: str, concept_b: str, weight: float = 0.5):
        self.add_node(concept_a)
        self.add_node(concept_b)
        self.add_link(concept_a, concept_b, weight=weight)
        self.add_link(concept_b, concept_a, weight=weight)

    def learn_sequence(self, concepts: List[str], weight: float = 0.4):
        for i in range(len(concepts) - 1):
            a, b = concepts[i], concepts[i + 1]
            self.add_node(a)
            self.add_node(b)
            self.add_link(a, b, weight=weight, gate=GateType.POR)
            self.add_link(b, a, weight=weight * 0.3, gate=GateType.RET)

    # ── Pruning ─────────────────────────────────────────

    def prune(self, force: bool = False):
        """
        Remove weak links and stale nodes to maintain sparsity.
        Called automatically every ~100 spread steps.
        """
        self._prune_counter += 1
        if not force and self._prune_counter < 100:
            return
        self._prune_counter = 0

        with self._lock:
            now = time.time()

            # Prune links below threshold
            for node in self._nodes.values():
                node.links = [l for l in node.links if l.weight >= self.prune_threshold]

            # Prune nodes that have never been activated and are old
            stale_ids = []
            for nid, node in self._nodes.items():
                age = now - node.created_at
                if age > 3600 and node.activation <= node.baseline + 0.01:
                    if now - node.last_activated > 3600 and not node.links:
                        stale_ids.append(nid)

            for nid in stale_ids:
                # Remove links to this node
                for node in self._nodes.values():
                    node.links = [l for l in node.links if l.target_id != nid]
                del self._nodes[nid]

            if stale_ids:
                logger.debug(f"Pruned {len(stale_ids)} stale nodes")

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
        with self._lock:
            if not self._nodes:
                return 0.0
            above = sum(1 for n in self._nodes.values()
                        if n.activation > self.coherence_threshold)
            return above / len(self._nodes)

    # ── Persistence ─────────────────────────────────────

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
                "params": {
                    "global_decay": self.global_decay,
                    "iac_alpha": self.iac_alpha,
                    "iac_gamma": self.iac_gamma,
                    "associator_rate": self.associator_rate,
                    "coherence_threshold": self.coherence_threshold,
                    "link_decay_d": self.link_decay_d,
                },
                "step": self._step_count,
            }

    @classmethod
    def from_dict(cls, data: dict) -> "AssociativeNet":
        params = data.get("params", {})
        net = cls(
            global_decay=params.get("global_decay", 0.08),
            iac_alpha=params.get("iac_alpha", 0.12),
            iac_gamma=params.get("iac_gamma", 0.15),
            associator_rate=params.get("associator_rate", 0.03),
            coherence_threshold=params.get("coherence_threshold", 0.15),
            link_decay_d=params.get("link_decay_d", 0.5),
        )
        net._step_count = data.get("step", 0)
        raw = data.get("nodes", {})
        for nid, ndata in raw.items():
            node = ConceptNode(
                id=nid, label=ndata.get("label", nid),
                activation=ndata.get("activation", 0.0),
                baseline=ndata.get("baseline", 0.0),
                decay_rate=ndata.get("decay_rate", 0.1),
                domain=ndata.get("domain", "general"),
                links=[WeightedLink(
                    target_id=l["target"], weight=l["weight"],
                    gate=GateType(l.get("gate", "gen")),
                    last_used=l.get("last_used", 0.0),
                ) for l in ndata.get("links", [])],
                created_at=ndata.get("created_at", 0.0),
                last_activated=ndata.get("last_activated", 0.0),
            )
            net._nodes[nid] = node
        return net
