"""GuidedGenerator — 约束生成器 (Path 2)"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("laap.guided_generator")

class GuidedGenerator:
    def __init__(self):
        self._constraints: list = []
        logger.info("[GuidedGenerator] initialized (Path 2: constrained generation)")

    def add_constraint(self, constraint: str):
        self._constraints.append(constraint)

    def generate(self, prompt: str, **kwargs) -> str:
        return f"[guided] {prompt}"
