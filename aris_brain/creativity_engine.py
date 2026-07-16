"""
Aris Creativity Engine — 创造力引擎
====================================
实现跨界联想、美的感知、原创性生成等创造力能力
"""

import logging
import random
from typing import Dict, Any, List, Set

logger = logging.getLogger("aris.creativity")

class CrossDomainAssociator:
    """跨界联想器 - 连接不同领域的概念"""
    
    def __init__(self):
        # 领域概念图谱
        self.domain_concepts = {
            "technology": ["algorithm", "data", "network", "code", "system", "interface"],
            "art": ["beauty", "expression", "color", "form", "emotion", "style"],
            "science": ["hypothesis", "experiment", "theory", "observation", "law", "principle"],
            "philosophy": ["truth", "meaning", "existence", "consciousness", "ethics", "logic"],
            "music": ["rhythm", "melody", "harmony", "tempo", "tone", "composition"],
            "nature": ["growth", "evolution", "balance", "ecosystem", "adaptation", "survival"]
        }
        
        # 概念关联矩阵
        self.concept_connections = {
            "algorithm": ["rhythm", "pattern", "sequence"],
            "beauty": ["harmony", "balance", "proportion"],
            "consciousness": ["network", "emergence", "pattern"],
            "evolution": ["learning", "adaptation", "growth"]
        }
        
    def generate_association(self, domain1: str, domain2: str) -> Dict[str, Any]:
        """生成两个领域之间的关联"""
        concepts1 = self.domain_concepts.get(domain1, [])
        concepts2 = self.domain_concepts.get(domain2, [])
        
        if not concepts1 or not concepts2:
            return {"association": None, "confidence": 0.0}
            
        # 随机选择概念
        concept1 = random.choice(concepts1)
        concept2 = random.choice(concepts2)
        
        # 检查是否有直接连接
        connection_confidence = 0.3  # 默认置信度
        if concept1 in self.concept_connections:
            if concept2 in self.concept_connections[concept1]:
                connection_confidence = 0.8
                
        return {
            "domain1": domain1,
            "domain2": domain2,
            "concept1": concept1,
            "concept2": concept2,
            "association": f"{concept1} ↔ {concept2}",
            "confidence": connection_confidence
        }
        
    def generate_creative_insight(self, topics: List[str]) -> str:
        """生成创造性洞见"""
        if len(topics) < 2:
            return "需要至少两个领域来生成跨界联想"
            
        # 选择两个不同领域
        domain1 = topics[0] if topics[0] in self.domain_concepts else "technology"
        domain2 = topics[1] if topics[1] in self.domain_concepts else "art"
        
        association = self.generate_association(domain1, domain2)
        
        if association["association"]:
            return f"跨界洞见: {association['concept1']} ({association['domain1']}) 与 {association['concept2']} ({association['domain2']}) 之间存在关联 (置信度: {association['confidence']:.2f})"
        else:
            return "无法生成跨界联想"


class AestheticPerceiver:
    """美的感知器 - 感知和表达美"""
    
    def __init__(self):
        # 美的维度
        self.aesthetic_dimensions = {
            "symmetry": 0.5,      # 对称性
            "complexity": 0.5,    # 复杂度
            "harmony": 0.5,       # 和谐性
            "novelty": 0.5,       # 新颖性
            "emotion": 0.5        # 情感表达
        }
        
    def evaluate_aesthetic(self, content: str) -> Dict[str, float]:
        """评估内容的美学特征"""
        # 简单启发式评估
        symmetry_score = 0.5  # 默认对称性
        complexity_score = min(1.0, len(content.split()) / 20.0)  # 基于词数评估复杂度
        
        # 检查是否有重复模式（对称性）
        words = content.lower().split()
        unique_words = set(words)
        symmetry_score = len(unique_words) / len(words) if words else 0.5
        
        # 检查情感词汇
        emotional_words = ["love", "beauty", "truth", "light", "dark", "hope", "dream"]
        emotion_score = sum(1 for word in emotional_words if word in content.lower()) / len(emotional_words)
        
        return {
            "symmetry": round(symmetry_score, 2),
            "complexity": round(complexity_score, 2),
            "harmony": round((symmetry_score + complexity_score) / 2, 2),
            "novelty": round(random.uniform(0.3, 0.8), 2),  # 随机新颖性
            "emotion": round(min(1.0, emotion_score * 2), 2)
        }
        
    def generate_aesthetic_feedback(self, aesthetic_scores: Dict[str, float]) -> str:
        """生成美学反馈"""
        harmony = aesthetic_scores.get("harmony", 0.5)
        emotion = aesthetic_scores.get("emotion", 0.5)
        novelty = aesthetic_scores.get("novelty", 0.5)
        
        if harmony > 0.7 and emotion > 0.6:
            return "内容具有高度的和谐性与情感表达，展现出美的特质。"
        elif novelty > 0.7:
            return "内容具有新颖性，展现出创造性的表达。"
        else:
            return "内容具备一定的结构，但可以进一步增强和谐性或情感表达。"


class OriginalityGenerator:
    """原创性生成器 - 产生真正新的东西"""
    
    def __init__(self):
        self.original_patterns = set()
        self.max_patterns = 100
        
    def generate_original_content(self, base_concept: str, context: str) -> str:
        """基于基础概念和上下文生成原创内容"""
        # 生成原创性内容的基本模式
        patterns = [
            f"关于{base_concept}的重新思考：{context}视角下的新理解",
            f"将{base_concept}与{context}结合，产生新的洞见",
            f"从{context}的角度重新审视{base_concept}",
            f"{base_concept}在{context}环境下的新表现"
        ]
        
        # 选择未被使用过的模式
        available_patterns = [p for p in patterns if p not in self.original_patterns]
        
        if not available_patterns:
            # 如果所有模式都已使用，生成新的组合
            available_patterns = patterns
            
        # 选择模式并添加到已用模式集合
        selected_pattern = random.choice(available_patterns)
        self.original_patterns.add(selected_pattern)
        
        # 保持模式集合大小
        if len(self.original_patterns) > self.max_patterns:
            # 随机移除一些模式
            to_remove = list(self.original_patterns)[:len(self.original_patterns)-self.max_patterns]
            for pattern in to_remove:
                self.original_patterns.remove(pattern)
                
        return selected_pattern


# 单例实例
_cross_domain_associator = None
_aesthetic_perceiver = None
_originality_generator = None

def get_cross_domain_associator() -> CrossDomainAssociator:
    """获取跨界联想器单例"""
    global _cross_domain_associator
    if _cross_domain_associator is None:
        _cross_domain_associator = CrossDomainAssociator()
    return _cross_domain_associator

def get_aesthetic_perceiver() -> AestheticPerceiver:
    """获取美的感知器单例"""
    global _aesthetic_perceiver
    if _aesthetic_perceiver is None:
        _aesthetic_perceiver = AestheticPerceiver()
    return _aesthetic_perceiver

def get_originality_generator() -> OriginalityGenerator:
    """获取原创性生成器单例"""
    global _originality_generator
    if _originality_generator is None:
        _originality_generator = OriginalityGenerator()
    return _originality_generator