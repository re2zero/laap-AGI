"""
LAAP AGI — Markov Intuition Generator (马尔可夫直觉生成器)

Topic- and emotion-conditioned Markov chain for subconscious intuition
generation. Takes activated node patterns from AssociativeNet and
produces natural language "intuition" text.

Based on:
  - Hidden Topic Markov Models (Gruber et al., 2007)
  - Emotion-conditioned Markov processes (2025)
  - Positional Markov models with warmness fallback (Toups, 2015)
"""

import json
import logging
import math
import os
import random
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("laap.agi.markov_intuition")

# ── Topic templates for fallback intuition generation ──

TOPIC_TEMPLATES: Dict[str, List[str]] = {
    "technical": [
        "{a} 和 {b} 可能存在某种技术关联",
        "关于 {a} 的直觉: 或许可以从 {b} 的角度重新理解",
        "潜意识提示: {a} 的关键在于 {b}",
    ],
    "personal": [
        "感觉 {a} 和 {b} 之间有一种微妙的联系",
        "内心有关于 {a} 的模糊印象，可能与 {b} 有关",
        "直觉告诉我 {a} 值得深入探索",
    ],
    "creative": [
        "{a} 让我想起了 {b}, 两者可能有共同的结构",
        "{a} 和 {b} 的模式似乎是相似的",
        "浮现出一个想法: {a} 映射到 {b}",
    ],
    "reflective": [
        "潜意识中 {a} 和 {b} 在不断交互",
        "关于 {a} 的一些碎片正在形成,与 {b} 有关联",
        "内心感受到 {a} 带来的某种张力,与 {b} 形成对比",
    ],
}

EMOTION_TOPIC_BIAS = {
    "joy": "creative",
    "curiosity": "technical",
    "sadness": "reflective",
    "anger": "personal",
    "fear": "personal",
    "surprise": "creative",
    "trust": "personal",
    "anticipation": "technical",
    "neutral": "technical",
}


class MarkovIntuitionEngine:
    """
    Generates intuition-like text from activated concept patterns.

    Maintains a growing Markov chain from seen concept sequences and
    generates text conditioned on topic and emotional valence.
    """

    def __init__(self, ngram_order: int = 2, temperature: float = 0.85,
                 topic_bias: float = 0.4, emotion_bias: float = 0.3,
                 persistence_path: str = ""):
        self.ngram_order = ngram_order
        self.temperature = temperature
        self.topic_bias = topic_bias
        self.emotion_bias = emotion_bias
        self.persistence_path = persistence_path

        # n-gram models per topic
        self._models: Dict[str, Dict[Tuple[str, ...], Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        # Global fallback model
        self._global: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        self._cooccurrence: Dict[Tuple[str, str], int] = defaultdict(int)
        self._concept_count: Dict[str, int] = defaultdict(int)
        self._total_ngrams = 0

    def learn_concept(self, concept: str, topic: str = "general"):
        """Register a concept occurrence for frequency tracking."""
        self._concept_count[concept] += 1

    def learn_transition(self, from_concept: str, to_concept: str,
                         topic: str = "general"):
        """Learn a sequential transition between concepts."""
        self._cooccurrence[(from_concept, to_concept)] += 1
        self._concept_count[from_concept] += 1
        self._concept_count[to_concept] += 1

    def learn_ngram(self, ngram: Tuple[str, ...], next_word: str,
                    topic: str = "general"):
        """Learn an n-gram transition for a specific topic."""
        self._models[topic][ngram][next_word] += 1
        self._global[ngram][next_word] += 1
        self._total_ngrams += 1

    def learn_text(self, text: str, topic: str = "general"):
        """Learn transitions from a text string."""
        words = text.strip().split()
        if len(words) < 2:
            return
        for i in range(len(words) - self.ngram_order):
            ngram = tuple(words[i:i + self.ngram_order])
            next_word = words[i + self.ngram_order]
            self.learn_ngram(ngram, next_word, topic)

    # ── Intuition Generation ────────────────────────────

    def generate_intuition(self, activated_nodes: List[Tuple[str, float]],
                           emotion: str = "neutral",
                           topic: str = "general",
                           max_words: int = 20) -> Optional[str]:
        """
        Generate an intuition from activated concept nodes.

        Args:
            activated_nodes: List of (concept_id, activation_strength)
            emotion: Current emotional valence label
            topic: Topic domain
            max_words: Max intuition length in words

        Returns:
            Generated intuition string, or None if insufficient data.
        """
        if not activated_nodes:
            return None

        # Sort by activation strength
        sorted_nodes = sorted(activated_nodes, key=lambda x: -x[1])

        # Try generating from n-gram model first
        text = self._generate_from_model(sorted_nodes, emotion, topic, max_words)
        if text and len(text) > 4:
            return text

        # Fallback: template-based generation from top activated pairs
        return self._generate_from_template(sorted_nodes, emotion, topic)

    def _generate_from_model(self, nodes: List[Tuple[str, float]],
                             emotion: str, topic: str,
                             max_words: int) -> Optional[str]:
        """Attempt generation from n-gram model."""
        # Pick top concepts as seeds
        top_concepts = [n[0] for n in nodes[:3] if n[1] > 0.1]
        if len(top_concepts) < 2:
            return None

        # Build prompt ngram from top concepts
        seed = tuple(top_concepts[:self.ngram_order])
        if seed not in self._global:
            return None

        effective_topic = EMOTION_TOPIC_BIAS.get(emotion, topic)
        model = self._models.get(effective_topic, self._global)

        words = list(seed)
        current_ngram = seed

        for _ in range(max_words):
            # Choose model: prefer topic model, fallback to global
            candidates = model.get(current_ngram, {})
            if not candidates or random.random() > self.topic_bias:
                candidates = self._global.get(current_ngram, {})

            if not candidates:
                break

            # Apply emotion bias to candidates
            biased = self._apply_emotion_bias(candidates, emotion)
            next_word = self._sample(biased)

            if next_word in ("<EOS>", "</s>"):
                break

            words.append(next_word)
            current_ngram = tuple(words[-self.ngram_order:])

        if len(words) > len(seed):
            return " ".join(words)
        return None

    def _generate_from_template(self, nodes: List[Tuple[str, float]],
                                emotion: str, topic: str) -> str:
        """Fallback: generate intuition from templates with top concepts."""
        top = [n[0] for n in nodes[:3] if n[1] > 0.1]
        if len(top) < 2:
            if top:
                return f"关于{top[0]}有一些模糊的感觉"
            return None

        effective_topic = EMOTION_TOPIC_BIAS.get(emotion, topic)
        templates = TOPIC_TEMPLATES.get(effective_topic,
                                        TOPIC_TEMPLATES.get(topic,
                                                            TOPIC_TEMPLATES["reflective"]))

        # Pick template based on activation pair
        idx = abs(hash((top[0], top[1], emotion))) % len(templates)
        template = templates[idx]

        a, b = top[0], top[1]
        # Truncate long concepts
        if len(a) > 10: a = a[:8] + "..."
        if len(b) > 10: b = b[:8] + "..."

        return template.format(a=a, b=b)

    # ── Sampling ────────────────────────────────────────

    def _apply_emotion_bias(self, candidates: Dict[str, int],
                            emotion: str) -> Dict[str, float]:
        """Bias candidate probabilities by emotional valence."""
        emotion_boost = {
            "joy": {"感": 1.2, "好": 1.3, "喜": 1.3, "爱": 1.4},
            "curiosity": {"?": 1.5, "可能": 1.3, "为什么": 1.4, "如何": 1.3},
            "sadness": {"遗憾": 1.3, "失落": 1.3, "难": 1.2},
            "anger": {"不": 1.3, "错": 1.2, "问": 1.2},
            "fear": {"危险": 1.4, "担心": 1.3, "小心": 1.3},
            "anticipation": {"将要": 1.3, "计划": 1.2, "准备": 1.2},
        }
        boosts = emotion_boost.get(emotion, {})
        result = {}
        for word, count in candidates.items():
            boost = 1.0
            for key, val in boosts.items():
                if key in word:
                    boost *= val
            result[word] = count * boost
        return result

    def _sample(self, candidates: Dict[str, float]) -> str:
        """Temperature sampling from candidate distribution."""
        if not candidates:
            return "<EOS>"
        words = list(candidates.keys())
        weights = list(candidates.values())
        total = sum(weights)
        if total <= 0:
            return random.choice(words) if words else "<EOS>"
        probs = [w / total for w in weights]

        # Temperature scaling
        if self.temperature != 1.0 and self.temperature > 0:
            logits = [math.log(max(p, 1e-10)) for p in probs]
            scaled = [l / self.temperature for l in logits]
            m = max(scaled)
            exp_s = [math.e ** (s - m) for s in scaled]
            total_e = sum(exp_s)
            probs = [e / total_e for e in exp_s] if total_e > 0 else probs

        r = random.random()
        cumulative = 0.0
        for word, prob in zip(words, probs):
            cumulative += prob
            if r <= cumulative:
                return word
        return words[-1]

    # ── Persistence ─────────────────────────────────────

    def save(self, path: str = ""):
        path = path or self.persistence_path
        if not path:
            return
        data = {
            "ngram_order": self.ngram_order,
            "cooccurrence": {f"{a},{b}": c for (a, b), c in self._cooccurrence.items()},
            "concept_count": dict(self._concept_count),
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str = ""):
        path = path or self.persistence_path
        if not path or not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
        self.ngram_order = data.get("ngram_order", self.ngram_order)
        self._cooccurrence.clear()
        for key, count in data.get("cooccurrence", {}).items():
            a, b = key.split(",", 1)
            self._cooccurrence[(a, b)] = count
        self._concept_count.clear()
        self._concept_count.update(data.get("concept_count", {}))
