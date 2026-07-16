"""
Aris Deep Interaction — 深度互动模块
=====================================
实现主动关心、挑战与启发、共同成长等深度互动能力
"""

import logging
import time
import random
from typing import Dict, Any, List

logger = logging.getLogger("aris.deep_interaction")

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