"""AutoLearner — 自动学习引擎"""
import logging, time, json, re
from collections import defaultdict
from typing import Dict, Any, List, Optional

logger = logging.getLogger("auto_learner")

class AutoLearner:
    def __init__(self):
        self._patterns: Dict[str, list] = defaultdict(list)
        self._frequency: Dict[str, int] = defaultdict(int)
        self._total_observations = 0
        logger.info("[AutoLearner] initialized")

    def observe(self, category: str, data: Any):
        self._patterns[category].append({"data": data, "time": time.time()})
        self._frequency[category] += 1
        self._total_observations += 1

    def suggest(self, context: str) -> List[str]:
        hints = []
        for cat, freq in sorted(self._frequency.items(), key=lambda x: -x[1]):
            if len(hints) < 3:
                hints.append(f"{cat} ({freq}次)")
        return hints

    def get_stats(self) -> dict:
        return {"total": self._total_observations, "categories": dict(self._frequency)}
