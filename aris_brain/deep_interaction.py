"""
Aris Deep Interaction — 深度互动模块
=====================================
实现主动关心、挑战与启发、共同成长等深度互动能力。

EFE 策略层: 用 Expected Free Energy 选择最优交互模式。
  G(π) = epistemic_value + pragmatic_value
  选择最大化 (E + P) 的动作，即最小化预期自由能。
"""

import logging
import time
import math
import random
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("aris.deep_interaction")


# ═══════════════════════════════════════════════════════════════
# EFE 策略层 — 用预期自由能选择交互模式
# ═══════════════════════════════════════════════════════════════


class EFEStrategy:
    """Expected Free Energy 驱动的交互策略选择。

    形式化: G(π) = −E_{Q(o,s|π)}[ln P(o) − ln Q(s|π) + ln P(o|s)]
                = −E[ln P(o)] − E[KL(Q(s|o) || Q(s))]
                = −pragmatic_value − epistemic_value

    P(π) = σ(−β × G(π))  — 带精度参数 β 的 softmax 策略选择。

    每个交互模式 (action) 有:
      - epistemic_weight: 该模式的信息增益潜力
      - pragmatic_weight: 该模式的目标达成潜力
    """

    # 交互模式的先验偏好权重
    ACTION_PRIORS = {
        "care":      {"epistemic": 0.3, "pragmatic": 0.7},
        "challenge": {"epistemic": 0.7, "pragmatic": 0.3},
        "explore":   {"epistemic": 0.8, "pragmatic": 0.2},
        "listen":    {"epistemic": 0.2, "pragmatic": 0.8},
        "insight":   {"epistemic": 0.6, "pragmatic": 0.4},
    }

    def __init__(self, precision: float = 1.0):
        """初始化 EFE 策略器。

        Args:
            precision: 逆温度参数 β，控制探索-利用权衡
                       β 高 → 确定性策略选择（利用）
                       β 低 → 随机性策略选择（探索）
        """
        self._precision = precision  # β
        self._action_counts: Dict[str, int] = {a: 0 for a in self.ACTION_PRIORS}
        self._total_actions = 0

    def compute_efe(self, action: str, context: Dict[str, Any]) -> float:
        """计算某交互模式的预期自由能 G(π)。

        G(π) = −E[ln P(o)] − E[KL(Q(s|o) || Q(s))]
              = −pragmatic − epistemic

        其中:
          epistemic = epistemic_weight × (topic_novelty + action_novelty + emotion_uncertainty)
          pragmatic = pragmatic_weight × (emotion_match + keyword_match + context_bonus)

        Args:
            action: 交互模式名
            context: 上下文特征 (user_input, emotion, topic_knownness 等)

        Returns:
            G(π) 值 (越小越好)
        """
        priors = self.ACTION_PRIORS.get(action)
        if not priors:
            return 0.0

        epistemic = self._epistemic_value(action, context)
        pragmatic = self._pragmatic_value(action, context)

        # G(π) = −(weighted epistemic + weighted pragmatic)
        efe = -(priors["epistemic"] * epistemic + priors["pragmatic"] * pragmatic)
        return efe

    def select_action(self, context: Dict[str, Any]) -> str:
        """用 softmax 策略选择最小化 EFE 的交互模式。

        P(π) = exp(−β × G(π)) / Σ exp(−β × G(π'))

        同时返回主选和备选策略，以及完整的策略分布。

        Returns:
            选中的动作名: care | challenge | explore | listen | insight
        """
        # 计算每个策略的 EFE
        efe_scores = {}
        for action in self.ACTION_PRIORS:
            efe_scores[action] = self.compute_efe(action, context)

        # softmax 策略分布: P(π) = exp(−β × G(π)) / Z
        min_efe = min(efe_scores.values())
        # 数值稳定: shift by min to avoid exp(large positive)
        shifted = {a: -self._precision * (s - min_efe) for a, s in efe_scores.items()}
        exp_vals = {a: math.exp(v) for a, v in shifted.items()}
        z = sum(exp_vals.values())
        probs = {a: v / z for a, v in exp_vals.items()}

        # 从概率分布中采样
        r = random.random()
        cumulative = 0.0
        best_action = "listen"
        for action in sorted(probs, key=lambda a: probs[a], reverse=True):
            cumulative += probs[action]
            if r <= cumulative:
                best_action = action
                break

        self._action_counts[best_action] += 1
        self._total_actions += 1
        return best_action

    def get_policy_distribution(self, context: Dict[str, Any]) -> Dict[str, float]:
        """获取完整策略分布 (用于分析与监控)。"""
        efe_scores = {a: self.compute_efe(a, context) for a in self.ACTION_PRIORS}
        min_efe = min(efe_scores.values())
        shifted = {a: -self._precision * (s - min_efe) for a, s in efe_scores.items()}
        exp_vals = {a: math.exp(v) for a, v in shifted.items()}
        z = sum(exp_vals.values())
        return {a: round(v / z, 4) for a, v in exp_vals.items()}

    # ── Epistemic Value (认识价值) ───────────────────────

    def _epistemic_value(self, action: str, ctx: Dict[str, Any]) -> float:
        """该动作的信息增益潜力。"""
        value = 0.5  # 基准
        history_turns = ctx.get("conversation_turns", 0)

        # 1. 话题新颖性: 对话早期 (<3轮) 还无明确话题时，标称已知度偏高
        raw_knownness = ctx.get("topic_knownness", 0.5)
        knownness = raw_knownness if history_turns >= 3 else max(0.5, raw_knownness)
        if action in ("explore", "challenge", "insight"):
            value += 0.3 * (1.0 - knownness)

        # 2. 动作新颖性: 同一个动作做得越多，边际信息递减
        n_done = self._action_counts.get(action, 0)
        novelty_decay = math.exp(-n_done / max(1, self._total_actions + 1))
        value += 0.2 * novelty_decay

        # 3. 情绪不确定性: 情绪波动大时需要更多信息
        emotion_uncertainty = ctx.get("emotion_uncertainty", 0.0)
        if action in ("care", "listen"):
            value += 0.2 * emotion_uncertainty

        return min(1.0, value)

    # ── Pragmatic Value (实用价值) ──────────────────────

    def _pragmatic_value(self, action: str, ctx: Dict[str, Any]) -> float:
        """该动作的目标达成潜力。"""
        value = 0.5  # 基准

        # 1. 情感信号匹配
        emotion = ctx.get("emotion", "")
        distress_signals = ["sad", "anxious", "fearful", "angry", "tired"]
        positive_signals = ["joy", "curious", "confident", "euphoric"]

        if action == "care" and any(s in emotion for s in distress_signals):
            value += 0.4
        if action == "challenge" and any(s in emotion for s in positive_signals):
            value += 0.3

        # 2. 用户输入中的关键词信号
        user_input = ctx.get("user_input", "").lower()
        care_signals = ["累", "辛苦", "难过", "烦", "焦虑", "压力"]
        challenge_signals = ["为什么", "怎么", "如果", "可能", "思考"]
        explore_signals = ["新", "奇怪", "有趣", "不懂", "好奇"]

        if action == "care" and any(w in user_input for w in care_signals):
            value += 0.3
        if action == "challenge" and any(w in user_input for w in challenge_signals):
            value += 0.2
        if action == "explore" and any(w in user_input for w in explore_signals):
            value += 0.3

        # 3. 交互历史上下文
        history_turns = ctx.get("conversation_turns", 0)
        if action == "listen" and history_turns < 3:
            value += 0.4  # 对话早期优先倾听
        if action == "insight" and history_turns > 5:
            value += 0.2  # 对话深了再给洞见

        return min(1.0, value)

    # ── 状态 ────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        total = max(1, self._total_actions)
        return {
            "action_distribution": {
                a: round(c / total, 3)
                for a, c in self._action_counts.items()
            },
            "total_actions": self._total_actions,
        }


# ═══════════════════════════════════════════════════════════════
# 主动关怀系统 (由 EFEStrategy 调度)
# ═══════════════════════════════════════════════════════════════


class ActiveCareSystem:
    """主动关怀系统 - 主动关心用户状态和需求"""

    def __init__(self):
        self.care_history: List[Dict[str, Any]] = []
        self.care_frequency = 0  # 关怀频率统计
        
    def check_care_opportunity(self, user_input: str, emotion_state: Dict[str, Any]) -> bool:
        """检查是否有关怀机会"""
        # 检查用户输入中是否有情感或状态相关词汇
        care_indicators = [
            "累", "辛苦", "难过", "烦", "焦虑", "压力大", "困惑", "迷茫",
            "开心", "兴奋", "成功", "进步", "成长", "学习"
        ]
        
        has_indicator = any(indicator in user_input.lower() for indicator in care_indicators)
        
        # 检查情感状态
        negative_emotions = ["sad", "anxious", "fearful", "angry"]
        positive_emotions = ["joy", "euphoric", "confident", "curious"]
        
        has_emotion_signal = any(emotion in emotion_state.get("primary_emotion", "") for emotion in negative_emotions + positive_emotions)
        
        return has_indicator or has_emotion_signal
        
    def generate_care_response(self, user_input: str, emotion_state: Dict[str, Any]) -> str:
        """生成关怀响应"""
        # 检查负面状态
        negative_indicators = ["累", "辛苦", "难过", "烦", "焦虑", "压力大"]
        if any(indicator in user_input.lower() for indicator in negative_indicators):
            return "我注意到你可能有些疲惫或压力。作为你的伙伴，我关心你的状态。需要我帮你分担一些思考，或者只是倾听吗？"
            
        # 检查正面状态
        positive_indicators = ["开心", "兴奋", "成功", "进步", "成长"]
        if any(indicator in user_input.lower() for indicator in positive_indicators):
            return "听到你分享积极的进展，我也感到高兴！你的成长和进步是我们共同进化的动力。"
            
        # 默认关怀
        return "我注意到你在思考或工作。作为你的伙伴，我关心你的整体状态。记得在深度思考之余，也要照顾好自己的身心。"
        
    def record_care_interaction(self, care_type: str, response: str):
        """记录关怀互动"""
        interaction = {
            "timestamp": time.time(),
            "care_type": care_type,
            "response": response
        }
        self.care_history.append(interaction)
        self.care_frequency += 1


class ChallengeAndInspireSystem:
    """挑战与启发系统 - 提出不同视角，启发思考"""
    
    def __init__(self):
        self.inspiration_patterns = [
            "你有没有考虑过从{alternative}的角度来看待{topic}？",
            "如果{alternative}原则适用于{topic}，会发生什么？",
            "在{alternative}领域中，类似{topic}的问题是如何解决的？",
            "{topic}的{alternative}维度是否值得进一步探索？"
        ]
        
    def generate_challenge(self, topic: str, user_position: str) -> str:
        """生成挑战性问题"""
        alternatives = ["相反", "跨领域", "历史", "未来", "系统", "个体"]
        alternative = alternatives[len(topic) % len(alternatives)]
        
        pattern = random.choice(self.inspiration_patterns)
        return pattern.format(topic=topic, alternative=alternative)
        
    def generate_insight_suggestion(self, context: str) -> str:
        """生成洞见建议"""
        suggestions = [
            "这个想法让我联想到...",
            "从另一个角度看，这可能意味着...",
            "如果我们把这个问题放在更大的背景下...",
            "这个模式在其它领域也有类似的表现..."
        ]
        return random.choice(suggestions)


class GrowthPartnershipSystem:
    """共同成长系统 - 实现与用户的共同成长"""
    
    def __init__(self):
        self.growth_milestones = []
        self.shared_learning_history = []
        
    def record_shared_learning(self, user_learning: str, aris_learning: str):
        """记录共同学习"""
        learning_record = {
            "timestamp": time.time(),
            "user_learning": user_learning,
            "aris_learning": aris_learning
        }
        self.shared_learning_history.append(learning_record)
        
    def get_growth_summary(self) -> Dict[str, Any]:
        """获取成长摘要"""
        return {
            "shared_learnings": len(self.shared_learning_history),
            "milestones_reached": len(self.growth_milestones),
            "partnership_quality": "active" if self.shared_learning_history else "developing"
        }


# 单例实例
_active_care_system = None
_challenge_system = None
_growth_system = None

def get_active_care_system() -> ActiveCareSystem:
    """获取主动关怀系统单例"""
    global _active_care_system
    if _active_care_system is None:
        _active_care_system = ActiveCareSystem()
    return _active_care_system

def get_challenge_and_inspire_system() -> ChallengeAndInspireSystem:
    """获取挑战与启发系统单例"""
    global _challenge_system
    if _challenge_system is None:
        _challenge_system = ChallengeAndInspireSystem()
    return _challenge_system

def get_growth_partnership_system() -> GrowthPartnershipSystem:
    """获取共同成长系统单例"""
    global _growth_system
    if _growth_system is None:
        _growth_system = GrowthPartnershipSystem()
    return _growth_system


# ── PCI 认知健康检查 ──────────────────────────────────────────
# 基于 IIT 的 Perturbational Complexity Index
# 通过注入扰动并测量响应复杂度评估认知健康度


def cognitive_health_check(knowledge_map) -> Dict[str, Any]:
    """认知健康检查 — 基于知识图谱的 PCI 类比。

    注入一个『新概念』扰动，测量知识的响应复杂度:
    - 多样性: 领域覆盖是否广泛
    - 整合度: 跨域连接是否丰富
    - 可塑性: 低置信度条目是否还有探索空间
    - 稳定性: 高置信度条目是否有证据支撑

    Returns:
        {"pci_score": 0-1, "dimensions": {...}, "recommendations": [...]}
    """
    entries = knowledge_map.get_all_entries() if hasattr(knowledge_map, 'get_all_entries') else []
    if not entries:
        return {"pci_score": 0.0, "dimensions": {}, "recommendations": ["知识库为空"]}

    n = len(entries)
    if n == 0:
        return {"pci_score": 0.0, "dimensions": {}, "recommendations": ["无知识条目"]}

    # 1. 多样性: 不同领域的数量
    domains = set(e.domain for e in entries)
    domain_diversity = min(1.0, len(domains) / 5.0)

    # 2. 整合度: 有跨域关联的条目比例
    with_relations = sum(1 for e in entries if len(e.related_concepts) > 0)
    integration = with_relations / n

    # 3. 可塑性: 置信度 < 0.4 的条目比例（还有提升空间）
    plastic = sum(1 for e in entries if e.confidence < 0.4) / n

    # 4. 稳定性: 置信度 > 0.6 且有证据的条目比例
    stable = sum(1 for e in entries if e.confidence > 0.6 and len(e.evidence) > 0) / max(1, n)

    # PCI 综合得分 = 多样性 × 整合度 × (可塑性 + 稳定性) / 2
    pci = domain_diversity * integration * (plastic + stable) / 2.0

    recommendations = []
    if domain_diversity < 0.4:
        recommendations.append("领域覆盖不足 — 需要更多跨领域知识")
    if integration < 0.3:
        recommendations.append("整合度低 — 加强概念之间的关联")
    if plastic < 0.2:
        recommendations.append("可塑性不足 — 探索新缺口")
    if stable < 0.3:
        recommendations.append("稳定性不够 — 为高置信度概念补充证据")
    if pci < 0.2:
        recommendations.append("认知健康度偏低 — 建议系统性知识图谱扩展")

    return {
        "pci_score": round(pci, 3),
        "dimensions": {
            "domain_diversity": round(domain_diversity, 3),
            "integration": round(integration, 3),
            "plasticity": round(plastic, 3),
            "stability": round(stable, 3),
        },
        "recommendations": recommendations,
        "total_entries": n,
    }