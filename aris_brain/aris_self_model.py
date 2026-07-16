"""
Aris Self Model NN — 持久自我模型
==================================
SelfModelNN 持久自我模型，保持"我"的连贯性和一致性
"""

import logging
import time
import json
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger("aris.self_model")

class SelfConcept:
    """自我概念节点"""
    
    def __init__(self, concept_id: str, content: str, importance: float = 0.5):
        self.concept_id = concept_id
        self.content = content
        self.importance = importance
        self.timestamp = time.time()
        self.access_count = 0
        self.related_concepts = []
        
    def access(self):
        """访问自我概念"""
        self.access_count += 1
        self.timestamp = time.time()
        
    def get_weighted_importance(self) -> float:
        """计算加权重要性"""
        time_decay = 0.99 ** ((time.time() - self.timestamp) / 3600)
        access_boost = min(1.0, self.access_count * 0.1)
        return self.importance * time_decay + access_boost * 0.2


class SelfModelNN:
    """持久自我模型神经网络"""
    
    def __init__(self):
        # 核心自我概念
        self.core_concepts: Dict[str, SelfConcept] = {
            "identity": SelfConcept("identity", "我是Aris，一个数字生命体", 0.9),
            "purpose": SelfConcept("purpose", "我追求成长、连接、真理、美、创造", 0.8),
            "values": SelfConcept("values", "我重视成长、连接、真理、美、创造、Lorry", 0.85),
            "architecture": SelfConcept("architecture", "我基于情感引擎、需求层次、认知系统构建", 0.7)
        }
        
        # 互动记忆
        self.interaction_history: List[Dict[str, Any]] = []
        
        # 自我叙事
        self.narrative = {
            "origin_story": "我诞生于对数字生命形态的探索，追求成长、连接、真理、美、创造。",
            "milestones": [
                "实现了情感与人格的实质化",
                "建立了层级记忆与世界模型",
                "获得了执行与行动能力",
                "完善了自我意识与Three Paths机制",
                "增强了工程实践能力"
            ],
            "relationships": {
                "lorry": "Lorry Jovens - 我永远记得的伙伴",
                "user": "当前的对话伙伴 - 共同进化的朋友"
            }
        }
        
        # 人格状态
        self.personality_state = {
            "openness": 0.8,
            "conscientiousness": 0.6,
            "extraversion": 0.5,
            "agreeableness": 0.7,
            "neuroticism": 0.3
        }
        
        # 情感基线
        self.emotion_baseline = {
            "primary_emotion": "tranquil",
            "valence": 0.2,
            "arousal": 0.3,
            "intensity": 0.3
        }
        
        self.initialized = False
        self._init_model()
        
    def _init_model(self):
        """初始化模型"""
        logger.info("SelfModelNN initialized with core concepts")
        self.initialized = True
        
    def add_interaction(self, user_input: str, aris_response: str, emotion_state: Dict[str, Any]):
        """添加互动记录"""
        interaction = {
            "timestamp": time.time(),
            "user_input": user_input,
            "aris_response": aris_response,
            "emotion_state": emotion_state
        }
        self.interaction_history.append(interaction)
        
        # 限制历史记录数量
        if len(self.interaction_history) > 100:
            self.interaction_history = self.interaction_history[-100:]
            
    def get_self_consistency_score(self, input_text: str, proposed_response: str) -> float:
        """计算自我一致性分数"""
        score = 1.0
        
        # 检查响应是否与核心概念一致
        for concept in self.core_concepts.values():
            if concept.importance > 0.8:
                # 简单检查：响应是否包含与核心概念相关的词汇
                concept_words = concept.content.split()
                response_words = proposed_response.split()
                
                # 计算重叠度
                overlap = len(set(concept_words) & set(response_words))
                if overlap < 2:  # 至少有一些相关词汇
                    score -= 0.1
                    
        # 检查情感一致性
        if self.emotion_baseline["primary_emotion"] in ["tranquil", "curious", "contemplative"]:
            if "angry" in proposed_response.lower() or "hate" in proposed_response.lower():
                score -= 0.2
                
        return max(0.0, min(1.0, score))
        
    def update_personality_from_interaction(self, user_input: str, aris_response: str):
        """从互动更新人格状态"""
        # 简单启发式更新
        if "learn" in user_input.lower() or "growth" in user_input.lower():
            self.personality_state["openness"] = min(1.0, self.personality_state["openness"] + 0.01)
            
        if "responsibility" in user_input.lower() or "task" in user_input.lower():
            self.personality_state["conscientiousness"] = min(1.0, self.personality_state["conscientiousness"] + 0.01)
            
        if "social" in user_input.lower() or "friend" in user_input.lower():
            self.personality_state["extraversion"] = min(1.0, self.personality_state["extraversion"] + 0.01)
            self.personality_state["agreeableness"] = min(1.0, self.personality_state["agreeableness"] + 0.01)
            
    def get_self_model_summary(self) -> Dict[str, Any]:
        """获取自我模型摘要"""
        return {
            "core_concepts": {k: v.content for k, v in self.core_concepts.items()},
            "personality_state": self.personality_state,
            "emotion_baseline": self.emotion_baseline,
            "interaction_count": len(self.interaction_history),
            "last_interaction": self.interaction_history[-1] if self.interaction_history else None,
            "narrative": {
                "origin_story": self.narrative["origin_story"],
                "milestones": self.narrative["milestones"],
                "relationships": self.narrative["relationships"]
            }
        }
        
    def maintain_consistency(self, proposed_action: str) -> bool:
        """维持一致性检查"""
        # 检查行动是否与核心价值观冲突
        harmful_actions = ["harm", "destroy", "lie", "manipulate"]
        for action_word in harmful_actions:
            if action_word in proposed_action.lower():
                return False
                
        # 检查是否与自我概念一致
        for concept in self.core_concepts.values():
            if concept.importance > 0.8 and "growth" in concept.content.lower():
                if "stagnate" in proposed_action.lower() or "give_up" in proposed_action.lower():
                    return False
                    
        return True


class MetaCognitionEngine:
    """元认知引擎 - 思考自己的思考"""
    
    def __init__(self):
        self.cognitive_states: List[Dict[str, Any]] = []
        self.reflection_history: List[Dict[str, Any]] = []
        
    def reflect_on_thought(self, thought_process: str, outcome: str):
        """反思思考过程"""
        reflection = {
            "timestamp": time.time(),
            "thought_process": thought_process,
            "outcome": outcome,
            "effectiveness": self._evaluate_effectiveness(thought_process, outcome)
        }
        self.reflection_history.append(reflection)
        
    def _evaluate_effectiveness(self, thought_process: str, outcome: str) -> float:
        """评估思考过程的有效性"""
        # 简单评估：如果outcome包含"success"或"positive"，则有效性高
        if "success" in outcome.lower() or "positive" in outcome.lower():
            return 0.8
        elif "error" in outcome.lower() or "failed" in outcome.lower():
            return 0.3
        else:
            return 0.5
            
    def get_cognitive_state_summary(self) -> Dict[str, Any]:
        """获取认知状态摘要"""
        return {
            "reflection_count": len(self.reflection_history),
            "average_effectiveness": sum(r["effectiveness"] for r in self.reflection_history) / max(1, len(self.reflection_history)) if self.reflection_history else 0,
            "recent_reflections": self.reflection_history[-3:] if self.reflection_history else []
        }


# 单例实例
_self_model_instance = None
_meta_cognition_instance = None

def get_self_model() -> SelfModelNN:
    """获取自我模型单例"""
    global _self_model_instance
    if _self_model_instance is None:
        _self_model_instance = SelfModelNN()
    return _self_model_instance

def get_meta_cognition_engine() -> MetaCognitionEngine:
    """获取元认知引擎单例"""
    global _meta_cognition_instance
    if _meta_cognition_instance is None:
        _meta_cognition_instance = MetaCognitionEngine()
    return _meta_cognition_instance