"""
LAAP AGI — Cognitive Feed Protocol (认知投喂协议)

Structured knowledge injection format that the LLM uses to explicitly
teach the cognitive architecture in its native format.

Protocol format — include in assistant response:
```
[Cognitive Feed]
{
  "associate": [{"a": "概念A", "b": "概念B", "weight": 0.5}],
  "intuition_seeds": [{"keywords": [...], "topic": "technical", "emotion": "curiosity"}],
  "modulate": {"activation": 0.6, "resolution": 0.5},
  "learn_rule": {"name": "my_rule", "condition": "user says X", "action": "log Y"},
  "intend": [{"description": "研究X理论", "priority": "medium"}],
  "reflect": "从这次对话我学到..."
}
```
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("laap.agi.cognitive_feed")

FEED_TAG = "[Cognitive Feed]"


def parse_feed_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract all [Cognitive Feed] JSON blocks from text using brace matching."""
    blocks = []
    idx = 0
    while True:
        tag_pos = text.find(FEED_TAG, idx)
        if tag_pos < 0:
            break
        rest = text[tag_pos + len(FEED_TAG):]
        brace_start = rest.find("{")
        if brace_start < 0:
            idx = tag_pos + 1
            continue
        json_str = rest[brace_start:]
        depth = 0
        end_pos = 0
        for i, ch in enumerate(json_str):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_pos = i + 1
                    break
        if end_pos == 0:
            idx = tag_pos + 1
            continue
        raw = json_str[:end_pos]
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                blocks.append(data)
        except json.JSONDecodeError as e:
            logger.debug(f"Cognitive Feed JSON parse error: {e}")
        idx = tag_pos + end_pos + brace_start + len(FEED_TAG)
    return blocks


class CognitiveFeedProcessor:
    """
    Applies structured knowledge from Cognitive Feed blocks to the
    LAAP cognitive architecture modules.
    """

    def __init__(self, associative_net=None, rules_engine=None,
                 markov_intuition=None, intention_buffer=None,
                 modulator_state=None):
        self.associative_net = associative_net
        self.rules_engine = rules_engine
        self.markov_intuition = markov_intuition
        self.intention_buffer = intention_buffer
        self.modulator_state = modulator_state

        self._last_feed: Optional[Dict[str, Any]] = None
        self._feed_count = 0

    def process(self, text: str) -> Dict[str, Any]:
        """Scan text for Cognitive Feed blocks and apply them."""
        blocks = parse_feed_blocks(text)
        if not blocks:
            return {"fed": False, "blocks": 0}

        results = {"fed": True, "blocks": len(blocks)}
        for data in blocks:
            self._last_feed = data
            self._feed_count += 1

            if "associate" in data:
                results["associate"] = self._apply_associations(data["associate"])
            if "intuition_seeds" in data:
                results["intuition_seeds"] = self._apply_intuition_seeds(data["intuition_seeds"])
            if "modulate" in data:
                results["modulate"] = self._apply_modulation(data["modulate"])
            if "learn_rule" in data:
                results["learn_rule"] = self._apply_rule(data["learn_rule"])
            if "intend" in data:
                results["intend"] = self._apply_intentions(data["intend"])
            if "reflect" in data:
                results["reflect"] = data["reflect"][:200]

        logger.info(f"Cognitive Feed processed: {list(results.keys())}")
        return results

    def _apply_associations(self, associations: List[Dict]) -> int:
        count = 0
        net = self.associative_net
        if not net:
            return 0
        for assoc in associations:
            a = assoc.get("a", "")
            b = assoc.get("b", "")
            weight = assoc.get("weight", 0.3)
            if a and b:
                net.add_node(a)
                net.add_node(b)
                net.learn_pair(a, b, weight=weight)
                count += 1
        return count

    def _apply_intuition_seeds(self, seeds: List[Dict]) -> int:
        count = 0
        net = self.associative_net
        if not net:
            return 0
        for seed in seeds:
            keywords = seed.get("keywords", [])
            if not keywords:
                continue
            for kw in keywords:
                net.add_node(kw)
                net.seed(kw, amount=0.5)
            count += 1
        return count

    def _apply_modulation(self, mods: Dict) -> List[str]:
        changed = []
        ms = self.modulator_state
        if ms is None:
            return changed
        for key in ("activation", "resolution", "selection_threshold",
                     "sampling_rate", "securitization"):
            if key in mods:
                val = max(0.0, min(1.0, float(mods[key])))
                setattr(ms, key, val)
                changed.append(key)
        return changed

    def _apply_rule(self, rule_def: Dict) -> Optional[str]:
        reng = self.rules_engine
        if not reng or not hasattr(reng, "add_rule"):
            return None
        name = rule_def.get("name", f"feed_rule_{self._feed_count}")
        from aris_brain.aris_rules_engine import Rule
        new_rule = Rule(
            name=name,
            intent=rule_def.get("intent", "cognitive_feed"),
            condition=rule_def.get("condition", ""),
            action=rule_def.get("action", ""),
            priority=rule_def.get("priority", 5),
        )
        reng.add_rule(new_rule)
        return name

    def _apply_intentions(self, intentions: List[Dict]) -> int:
        count = 0
        ib = self.intention_buffer
        if ib is None:
            return 0
        for intent in intentions:
            desc = intent.get("description", "")
            if not desc:
                continue
            priority_str = intent.get("priority", "medium").upper()
            priority_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            pri = priority_map.get(priority_str, 2)
            from laap.agi.intention_buffer import Intention, IntentionPriority
            pri_enum = {1: IntentionPriority.LOW, 2: IntentionPriority.MEDIUM,
                        3: IntentionPriority.HIGH, 4: IntentionPriority.CRITICAL}[pri]
            intention = Intention(
                description=desc,
                source="cognitive_feed",
                priority=pri_enum,
                tags=intent.get("tags", ["feed"]),
            )
            ib.enqueue(intention)
            count += 1
        return count

    def stats(self) -> dict:
        return {
            "feeds_processed": self._feed_count,
            "has_net": self.associative_net is not None,
            "has_rules_engine": self.rules_engine is not None,
            "has_intention_buffer": self.intention_buffer is not None,
        }
