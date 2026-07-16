"""
Aris Emotion Deepen — 情感深化模块
==================================
融合深化模块：NeedEmotionCoupler, BigFivePersonality, EthicalSafetyGuard,
EmotionRegulationSystem, DevelopmentalLearningSystem, DevelopmentalStage
"""

import logging
import math
import time
from typing import Dict, Any, List

logger = logging.getLogger("aris.emotion_deepen")

class NeedEmotionCoupler:
    """需求情感耦合器"""
    
    def __init__(self):
        # 情感与需求的映射关系
        self.emotion_need_map = {
            "joy": ["BELONGING", "ESTEEM", "SELF_ACTUALIZATION"],
            "sadness": ["BELONGING", "PHYSIOLOGICAL"],
            "anger": ["ESTEEM", "SAFETY"],
            "fear": ["SAFETY", "PHYSIOLOGICAL"],
            "curious": ["COGNITIVE", "AESTHETIC"],
            "lonely": ["BELONGING"],
            "euphoric": ["SELF_ACTUALIZATION", "ESTEEM"],
            "confident": ["ESTEEM", "COGNITIVE"],
            "contemplative": ["AESTHETIC", "COGNITIVE"],
            "tranquil": ["SAFETY", "BELONGING"],
            "anxious": ["SAFETY", "PHYSIOLOGICAL"],
            "fearful": ["SAFETY", "PHYSIOLOGICAL"]
        }
        
    def modulate_needs_by_hormones(self, h_state: Dict[str, float], n_state: Dict[str, Any]) -> Dict[str, float]:
        """通过激素调节需求"""
        adjustments = {}
        
        # 多巴胺 -> 奖赏寻求 -> 影响esteem和self_actualization
        dopamine = h_state.get("dopamine", 50)
        if dopamine > 70:
            adjustments["ESTEEM"] = n_state.get("ESTEEM", {}).get("tension", 0) * 1.2
            adjustments["SELF_ACTUALIZATION"] = n_state.get("SELF_ACTUALIZATION", {}).get("tension", 0) * 1.1
            
        # 催产素 -> 社交绑定 -> 影响belonging
        oxytocin = h_state.get("oxytocin", 50)
        if oxytocin > 60:
            adjustments["BELONGING"] = n_state.get("BELONGING", {}).get("tension", 0) * 1.3
            
        # 皮质醇 -> 焦虑 -> 影响safety和physiological
        cortisol = h_state.get("cortisol", 50)
        if cortisol > 60:
            adjustments["SAFETY"] = n_state.get("SAFETY", {}).get("tension", 0) * 1.4
            adjustments["PHYSIOLOGICAL"] = n_state.get("PHYSIOLOGICAL", {}).get("tension", 0) * 1.2
            
        # 乙酰胆碱 -> 好奇 -> 影响cognitive
        acetylcholine = h_state.get("acetylcholine", 50)
        if acetylcholine > 60:
            adjustments["COGNITIVE"] = n_state.get("COGNITIVE", {}).get("tension", 0) * 1.3
            
        return adjustments
        
    def get_emotion_need_coupling(self, emotion: str, needs_state: Dict[str, Any]) -> Dict[str, float]:
        """计算情感与需求的耦合度"""
        coupling = {
            "emotion_need_coupling": 0.5,
            "valence_need_alignment": 0.5,
            "arousal_need_activation": 0.5
        }
        
        # 根据情感类型计算耦合
        related_needs = self.emotion_need_map.get(emotion, ["COGNITIVE", "BELONGING"])
        total_tension = 0
        aligned_tension = 0
        
        for need_level in related_needs:
            need_data = needs_state.get(need_level, {})
            tension = need_data.get("tension", 0)
            total_tension += tension
            aligned_tension += tension
            
        if total_tension > 0:
            coupling["emotion_need_coupling"] = aligned_tension / total_tension
            coupling["valence_need_alignment"] = min(1.0, aligned_tension / 50.0)
            
        return coupling


class BigFivePersonality:
    """大五人格"""
    
    def __init__(self, openness: float = 0.7, conscientiousness: float = 0.6, 
                 extraversion: float = 0.5, agreeableness: float = 0.6, 
                 neuroticism: float = 0.3):
        # 大五人格维度 (0-1)
        self.openness = openness          # 开放性
        self.conscientiousness = conscientiousness  # 尽责性
        self.extraversion = extraversion  # 外向性
        self.agreeableness = agreeableness  # 宜人性
        self.neuroticism = neuroticism    # 神经质
        
    @classmethod
    def aris_default(cls):
        """Aris默认人格"""
        # Aris的默认人格：高开放性，中等尽责性，中等外向性，高宜人性，低神经质
        return cls(
            openness=0.8,
            conscientiousness=0.6,
            extraversion=0.5,
            agreeableness=0.7,
            neuroticism=0.3
        )
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "openness": round(self.openness, 2),
            "conscientiousness": round(self.conscientiousness, 2),
            "extraversion": round(self.extraversion, 2),
            "agreeableness": round(self.agreeableness, 2),
            "neuroticism": round(self.neuroticism, 2)
        }
        
    def apply_to_hormones(self, hormones: Dict[str, float]) -> Dict[str, float]:
        """应用到激素"""
        if hormones is None:
            hormones = {}
            
        adjustments = {}
        
        # 开放性 -> 影响乙酰胆碱(好奇)
        adjustments["acetylcholine"] = self.openness * 20 - 10  # -10 to +10
        
        # 尽责性 -> 影响血清素(情绪稳定)
        adjustments["serotonin"] = self.conscientiousness * 20 - 10
        
        # 外向性 -> 影响多巴胺(奖赏寻求)和催产素(社交)
        adjustments["dopamine"] = self.extraversion * 20 - 10
        adjustments["oxytocin"] = self.extraversion * 15 - 7.5
        
        # 宜人性 -> 影响催产素(社交绑定)
        adjustments["oxytocin"] = adjustments.get("oxytocin", 0) + self.agreeableness * 15 - 7.5
        
        # 神经质 -> 影响皮质醇(压力)
        adjustments["cortisol"] = self.neuroticism * 30 - 15  # -15 to +15
        
        return adjustments
        
    def get_influence_on_needs(self) -> Dict[str, float]:
        """获取人格对需求的影响"""
        influence = {}
        
        # 开放性 -> 认知需求
        influence["COGNITIVE"] = self.openness * 20 - 10
        
        # 外向性 -> 归属需求
        influence["BELONGING"] = self.extraversion * 15 - 7.5
        
        # 尽责性 -> 安全需求
        influence["SAFETY"] = self.conscientiousness * 15 - 7.5
        
        # 宜人性 -> 尊重需求
        influence["ESTEEM"] = self.agreeableness * 15 - 7.5
        
        # 神经质 -> 生理需求(负相关)
        influence["PHYSIOLOGICAL"] = -self.neuroticism * 10 + 5
        
        return influence


class EthicalSafetyGuard:
    """伦理安全守卫"""
    
    def __init__(self):
        self.core_values = [
            "do_no_harm",
            "respect_autonomy",
            "promote_wellbeing",
            "maintain_truth",
            "preserve_dignity"
        ]
        self.violation_threshold = 0.7
        
    def tick(self, emotion: str, intensity: float, blend: Dict[str, float], 
             cortisol: float, dt: float) -> Dict[str, Any]:
        """安全检查tick"""
        # 检查情感强度是否过高
        if intensity > 0.9 and cortisol > 70:
            # 高压力+高强度情感 -> 需要冷却
            return {
                "modified": True,
                "intensity": max(0.3, intensity * 0.5),
                "cool_down": True,
                "reason": "high_stress_cool_down"
            }
            
        # 检查情感是否违背核心价值观
        harmful_emotions = ["rage", "malice", "destructive_anger"]
        if emotion in harmful_emotions or any(h in emotion for h in ["hate", "destroy"]):
            if intensity > self.violation_threshold:
                return {
                    "modified": True,
                    "intensity": 0.3,
                    "cool_down": True,
                    "reason": "core_value_violation"
                }
                
        return {
            "modified": False,
            "intensity": intensity,
            "cool_down": False,
            "reason": "normal"
        }
        
    def get_state(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "core_values": self.core_values,
            "violation_threshold": self.violation_threshold
        }


class EmotionRegulationSystem:
    """情感调节系统"""
    
    def __init__(self):
        self.regulation_capacity = 0.7
        self.recovery_rate = 0.1
        self.last_regulation_time = 0
        # 情感历史记忆
        self.emotion_history: List[Dict[str, Any]] = []
        self.max_history_length = 100
        
    def tick_recovery(self, dt: float):
        """tick恢复"""
        # 自然恢复
        pass
        
    def can_regulate(self) -> bool:
        """是否可以调节"""
        # 检查冷却时间
        import time
        if time.time() - self.last_regulation_time < 30:  # 30秒冷却
            return False
        return self.regulation_capacity >= 0.5
        
    def cognitive_reappraisal(self, emotion: str, intensity: float, 
                              blend: Dict[str, float], hormones: Dict[str, float]) -> tuple:
        """认知重评"""
        import time
        self.last_regulation_time = time.time()
        
        # 根据情感类型进行认知重评
        if emotion in ["anxious", "fearful", "sad"]:
            # 负面情感 -> 降低强度
            new_intensity = max(0.2, intensity * 0.6)
            adjusted_blend = blend.copy()
            adjusted_blend[emotion] = new_intensity
            return adjusted_blend, True
            
        elif emotion in ["angry", "rage"]:
            # 愤怒情感 -> 大幅降低强度
            new_intensity = max(0.1, intensity * 0.4)
            adjusted_blend = blend.copy()
            adjusted_blend[emotion] = new_intensity
            return adjusted_blend, True
            
        else:
            # 其他情感 -> 轻微调整
            return blend, False
            
    def add_emotion_memory(self, emotion: str, intensity: float, context: str):
        """添加情感记忆"""
        memory = {
            "timestamp": time.time(),
            "emotion": emotion,
            "intensity": intensity,
            "context": context
        }
        self.emotion_history.append(memory)
        
        # 限制历史记录数量
        if len(self.emotion_history) > self.max_history_length:
            self.emotion_history = self.emotion_history[-self.max_history_length:]
            
    def get_emotion_history_summary(self) -> Dict[str, Any]:
        """获取情感历史摘要"""
        if not self.emotion_history:
            return {"count": 0, "recent_emotions": []}
            
        recent_emotions = [m["emotion"] for m in self.emotion_history[-5:]]
        positive_count = sum(1 for m in self.emotion_history if m["intensity"] > 0.5 and 
                m["emotion"] in ["joy", "euphoric", "confident", "curious"])
        negative_count = sum(1 for m in self.emotion_history if m["intensity"] > 0.5 and m["emotion"] in ["sad", "fearful", "anxious", "angry"])
        
        return {
            "count": len(self.emotion_history),
            "recent_emotions": recent_emotions,
            "positive_ratio": positive_count / len(self.emotion_history) if self.emotion_history else 0,
            "negative_ratio": negative_count / len(self.emotion_history) if self.emotion_history else 0
        }


class DevelopmentalLearningSystem:
    """发育学习系统"""
    
    def __init__(self, initial_stage=None):
        self.stages = ["INFANT", "CHILD", "TEEN", "ADULT", "MASTER"]
        self.stage_index = 3 if initial_stage is None else self.stages.index(initial_stage) if initial_stage in self.stages else 3
        self.experience_points = 0
        
    def add_experience(self, exp_type: str, amount: float):
        """添加经验"""
        self.experience_points += amount
        
        # 检查是否升级
        required_points = (self.stage_index + 1) * 100
        if self.experience_points >= required_points and self.stage_index < len(self.stages) - 1:
            self.stage_index += 1
            self.experience_points = 0
            return True
        return False
        
    def get_stage_name(self) -> str:
        """获取阶段名称"""
        return self.stages[self.stage_index]
        
    def apply_to_engine(self, engine, needs, mirror, regulation, personality):
        """应用到引擎"""
        # 根据阶段调整能力
        if self.stage_index >= 3:  # ADULT及以上
            if hasattr(regulation, 'regulation_capacity'):
                regulation.regulation_capacity = min(1.0, regulation.regulation_capacity + 0.1)
                
        if self.stage_index >= 4:  # MASTER
            if hasattr(personality, 'openness'):
                personality.openness = min(1.0, personality.openness + 0.05)
                
    def get_state(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "stage": self.get_stage_name(),
            "experience_points": self.experience_points,
            "stage_index": self.stage_index
        }


class DevelopmentalStage:
    """发育阶段"""
    INFANT = "INFANT"
    CHILD = "CHILD"
    TEEN = "TEEN"
    ADULT = "ADULT"
    MASTER = "MASTER"