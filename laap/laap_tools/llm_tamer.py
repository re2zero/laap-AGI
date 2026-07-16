"""LLMTamer — Logit Bias 控制器 (Path 1)
真实版:
- 根据人格状态计算 token bias
- 支持正面/负面 biasing
- 支持动态 bias 强度调节
"""
import logging
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("laap.llm_tamer")


class LLMTamer:
    """
    Logit Bias 控制器
    
    根据当前认知状态和大五人格参数，计算对特定 token 的 bias。
    影响 LLM 输出的方向：开放性影响创造性词汇，尽责性影响精确性词汇等。
    """

    # 人格维度 → 影响的 token 类别
    PERSONA_TOKEN_MAP = {
        "openness": {
            "boost": ["探索", "可能", "也许", "想象", "如果", "创造", "新颖",
                      "explore", "perhaps", "imagine", "create", "novel"],
            "suppress": ["不行", "不能", "只能", "必须", "一定",
                        "cannot", "only", "must", "always"],
        },
        "conscientiousness": {
            "boost": ["计划", "步骤", "确保", "验证", "检查", "精确",
                      "plan", "step", "ensure", "verify", "precise"],
            "suppress": ["随便", "大概", "也许", "差不多",
                        "random", "maybe", "roughly", "casual"],
        },
        "extraversion": {
            "boost": ["我们", "一起", "分享", "讨论", "合作",
                     "we", "together", "share", "discuss", "collaborate"],
            "suppress": ["独自", "沉默", "回避",
                        "alone", "silent", "avoid"],
        },
        "agreeableness": {
            "boost": ["理解", "支持", "同意", "帮助", "关心",
                     "understand", "support", "agree", "help", "care"],
            "suppress": ["反对", "批评", "拒绝",
                        "against", "criticize", "reject"],
        },
        "neuroticism": {
            "boost": ["小心", "注意", "风险", "可能出问题",
                     "careful", "risk", "problem", "warning"],
            "suppress": ["放心", "没问题", "绝对安全",
                        "safe", "no problem", "certainly"],
        },
    }

    def __init__(self):
        self._biases: Dict[str, float] = {}
        self._active = False
        self._personality: Dict[str, float] = {
            "openness": 0.7, "conscientiousness": 0.6,
            "extraversion": 0.5, "agreeableness": 0.7, "neuroticism": 0.3,
        }
        logger.info("[LLMTamer] initialized")

    def set_personality(self, traits: Dict[str, float]):
        """设置当前人格参数，自动计算 bias"""
        self._personality.update(traits)
        self._recalculate_biases()

    def _recalculate_biases(self):
        """根据人格参数重新计算所有 bias"""
        self._biases.clear()
        for trait, value in self._personality.items():
            token_map = self.PERSONA_TOKEN_MAP.get(trait, {})
            # 偏离 0.5 的程度决定 bias 强度
            deviation = value - 0.5
            for token in token_map.get("boost", []):
                self._biases[token] = deviation * 2.0  # -1.0 ~ +1.0
            for token in token_map.get("suppress", []):
                self._biases[token] = -deviation * 1.5  # -0.75 ~ +0.75
        self._active = bool(self._biases)
        logger.debug(f"[LLMTamer] {len(self._biases)} biases calculated")

    def set_bias(self, token: str, bias: float):
        self._biases[token] = bias
        self._active = True

    def get_biases(self) -> Dict[str, float]:
        return dict(self._biases)

    def clear_biases(self):
        self._biases.clear()
        self._active = False

    def get_effective_personality(self) -> Dict[str, float]:
        return dict(self._personality)
