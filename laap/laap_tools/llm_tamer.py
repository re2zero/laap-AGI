"""LLMTamer — Logit Bias 控制器 (Path 1)"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("laap.llm_tamer")

class LLMTamer:
    def __init__(self):
        self._biases: Dict[str, float] = {}
        self._active = False
        logger.info("[LLMTamer] initialized (Path 1: logit bias control)")

    def set_bias(self, token: str, bias: float):
        self._biases[token] = bias
        self._active = True

    def clear_biases(self):
        self._biases.clear()
        self._active = False

    def get_biases(self) -> Dict[str, float]:
        return dict(self._biases)
