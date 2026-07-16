"""
Aris PersonaManager — 动态混合人格
====================================
双时间尺度人格系统：

数学形式:
  P(t)    = P_core + α × C(t)          ← 每轮对话的情境调制
  P_core  = β × P_core + (1-β) × P*    ← 会话间核心漂移
  P*      = 成功交互的 P(t) 平均
  clamp(P, 0.3, 0.8)                   ← 防极化

5 个输出维度 (直接喂给 LLMTamer):
  openness, conscientiousness, extraversion, agreeableness, neuroticism

5 个情境特征 (从用户输入提取):
  technical, emotional, reflective, urgency, social

用法:
  pm = PersonaManager()
  blend = pm.get_blend("用户输入")
  print(blend["personality"])           # 当前混合人格
  pm.record_interaction(input, response, quality=0.8)
"""
import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("aris.persona")

# ── 默认核心人格 (冷启动基准) ──────────────────────────────

DEFAULT_CORE = {
    "openness": 0.7,
    "conscientiousness": 0.6,
    "extraversion": 0.5,
    "agreeableness": 0.7,
    "neuroticism": 0.3,
}

# ── 情境特征 → 人格维度映射 ──────────────────────────────

CONTEXT_TO_TRAIT = {
    # 每种情境特征调制的目标人格维度列表 (dim, intensity)
    "technical":   [("openness", 0.2), ("conscientiousness", 0.3)],
    "emotional":   [("extraversion", 0.2), ("agreeableness", 0.3),
                    ("neuroticism", -0.15)],
    "reflective":  [("openness", 0.25), ("neuroticism", 0.15)],
    "urgency":     [("conscientiousness", 0.2), ("neuroticism", 0.2),
                    ("extraversion", -0.15)],
    "social":      [("extraversion", 0.3), ("agreeableness", 0.2)],
}

# ── 词汇特征库 ──────────────────────────────────────────────

LEXICON = {
    "technical": [
        "代码", "算法", "架构", "函数", "接口", "性能", "优化", "bug",
        "debug", "api", "实现", "部署", "测试", "重构", "数据",
        "code", "algorithm", "function", "api", "implement", "deploy",
        "refactor", "architecture", "performance", "optimize",
    ],
    "emotional": [
        "累", "难过", "开心", "烦", "焦虑", "压力", "感动", "温暖",
        "害怕", "孤独", "爱", "恨", "希望", "失望",
        "tired", "sad", "happy", "anxious", "love", "hope", "scared",
        "lonely", "grateful", "warm", "touched",
    ],
    "reflective": [
        "为什么", "如果", "也许", "可能", "想想", "思考", "意义",
        "本质", "原因", "目的", "理解",
        "why", "if", "perhaps", "maybe", "think", "meaning",
        "purpose", "本质", "understand", "reflect",
    ],
    "urgency": [
        "快点", "马上", "急", "尽快", "抓紧", "立刻", "来不及",
        "重要", "必须",
        "urgent", "quickly", "immediately", "asap", "critical",
        "important", "must", "now",
    ],
    "social": [
        "我们", "一起", "你", "大家", "朋友", "分享", "帮助",
        "信任", "关系", "合作",
        "we", "together", "you", "friend", "share", "help",
        "trust", "relationship", "collaborate", "team",
    ],
}


class ContextDetector:
    """从用户输入中提取 5 维情境特征 C(t)"""

    @staticmethod
    def detect(text: str) -> Dict[str, float]:
        """返回 5 个情境维度的强度 [0, 1]"""
        text_lower = text.lower()
        words = text_lower.split()
        n_words = max(len(words), 1)
        features = {}

        for dim, keywords in LEXICON.items():
            # 关键词密度 + 加权重复
            matches = sum(1 for kw in keywords if kw in text_lower)
            # 多次提到同一类词增加强度
            intensity = min(1.0, matches * 0.2 + matches * 0.05)
            features[dim] = round(intensity, 3)

        # 句子特征: 问句
        n_questions = text.count("?") + text.count("？")
        if n_questions > 0:
            features["reflective"] = min(1.0, features["reflective"] + n_questions * 0.15)

        return features


class PersonaManager:
    """
    动态混合人格管理器
    
    核心公式:
      P(t) = P_core + α × C(t)          ← 情境调制
      P_core 缓慢漂移                    ← 跨会话学习
      clamp(P, 0.3, 0.8)                ← 防极化
    """

    def __init__(self,
                 alpha: float = 0.3,    # 调制强度
                 beta: float = 0.95,    # 核心惯性
                 state_dir: Optional[str] = None):

        # 超参数
        self.alpha = alpha
        self.beta = beta
        self._lower = 0.3
        self._upper = 0.8

        # 核心人格 (慢变量)
        self.core: Dict[str, float] = dict(DEFAULT_CORE)

        # 情境检测器
        self._detector = ContextDetector()

        # 交互历史 (只记录高质量交互)
        self._good_trials: List[Dict[str, float]] = []
        self._total_good = 0
        self._total_turns = 0

        # 持久化
        if state_dir:
            self._path = Path(state_dir) / "persona.json"
        else:
            try:
                from laap_brain.config import STATE_DIR
                self._path = STATE_DIR / "persona.json"
            except ImportError:
                self._path = Path.home() / ".laap" / "state" / "persona.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

        logger.info(f"[Persona] 初始化 α={alpha} β={beta} core={self._fmt_core()}")

    # ── 公共接口 ──────────────────────────────────────────

    def get_blend(self, user_input: str) -> Dict[str, Any]:
        """
        根据用户输入计算当前混合人格 P(t)。
        
        Args:
            user_input: 当前轮用户输入
        
        Returns:
            dict with keys:
              - personality: 5 维混合人格
              - context: 检测到的 5 维情境特征
              - core: 当前核心人格
              - blend_info: 混合强度记录
        """
        # 1. 提取情境特征 C(t)
        context = self._detector.detect(user_input)

        # 2. 计算混合人格 P(t) = P_core + α × C(t)
        blend = dict(self.core)
        modulation_log = {}
        for ctx_dim, intensity in context.items():
            if ctx_dim in CONTEXT_TO_TRAIT and intensity > 0:
                for trait, direction in CONTEXT_TO_TRAIT[ctx_dim]:
                    delta = self.alpha * intensity * direction
                    old = blend[trait]
                    blend[trait] = self._clamp(old + delta)
                    modulation_log[f"{trait}({ctx_dim})"] = {
                        "delta": round(delta, 4),
                        "from": round(old, 3),
                        "to": round(blend[trait], 3),
                    }

        # 3. 返回
        return {
            "personality": blend,
            "context": context,
            "core": dict(self.core),
            "blend_info": {
                "alpha_used": self.alpha,
                "modulations": modulation_log,
                "n_modulations": len(modulation_log),
            },
        }

    def record_interaction(self, user_input: str, response: str,
                           quality: float = 0.5):
        """
        记录一次交互，更新核心人格 (P_core)。
        
        只在 quality > 0.6 时采纳 (防止噪音漂移)。
        """
        self._total_turns += 1

        if quality < 0.6:
            return  # 低质量交互不参与核心进化

        # 记录当前混合人格作为合格试验
        ctx = self._detector.detect(user_input)
        # 用低调制强度时的 P(t) 近似 P*
        trial = dict(self.core)
        for ctx_dim, intensity in ctx.items():
            if ctx_dim in CONTEXT_TO_TRAIT and intensity > 0.2:
                for trait, direction in CONTEXT_TO_TRAIT[ctx_dim]:
                    delta = self.alpha * intensity * direction
                    trial[trait] = self._clamp(trial[trait] + delta)

        self._good_trials.append(trial)
        self._total_good += 1
        if len(self._good_trials) > 20:
            self._good_trials = self._good_trials[-20:]

        # 更新核心人格
        if self._good_trials:
            # P* = 最近成功试验的平均
            avg_trial = {
                k: sum(t[k] for t in self._good_trials) / len(self._good_trials)
                for k in self.core
            }
            # P_core = β × P_core + (1-β) × P*
            for k in self.core:
                self.core[k] = self._clamp(
                    self.beta * self.core[k] + (1 - self.beta) * avg_trial[k]
                )

        logger.debug(f"[Persona] 核心更新: {self._fmt_core()} (good={self._total_good})")
        self._save()

    def get_core(self) -> Dict[str, float]:
        return dict(self.core)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "core": self.core,
            "alpha": self.alpha,
            "beta": self.beta,
            "total_turns": self._total_turns,
            "good_trials": self._total_good,
        }

    # ── 内部 ──────────────────────────────────────────────

    def _clamp(self, v: float) -> float:
        return max(self._lower, min(self._upper, v))

    def _fmt_core(self) -> str:
        return f"O={self.core['openness']:.2f} C={self.core['conscientiousness']:.2f} " \
               f"E={self.core['extraversion']:.2f} A={self.core['agreeableness']:.2f} " \
               f"N={self.core['neuroticism']:.2f}"

    def _save(self):
        try:
            data = {
                "core": self.core,
                "alpha": self.alpha,
                "beta": self.beta,
                "total_turns": self._total_turns,
                "good_trials": self._total_good,
                "updated": time.time(),
            }
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[Persona] 保存失败: {e}")

    def _load(self):
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if "core" in data:
                    self.core.update(data["core"])
                self._total_turns = data.get("total_turns", 0)
                self._total_good = data.get("good_trials", 0)
                logger.info(f"[Persona] 恢复: {self._fmt_core()}")
        except Exception as e:
            logger.info(f"[Persona] 首次启动: {e}")


# ── 全局单例 ──────────────────────────────────────────────

_persona: Optional[PersonaManager] = None


def get_persona(alpha: float = 0.3, beta: float = 0.95,
                state_dir: Optional[str] = None) -> PersonaManager:
    global _persona
    if _persona is None:
        _persona = PersonaManager(alpha=alpha, beta=beta, state_dir=state_dir)
    return _persona
