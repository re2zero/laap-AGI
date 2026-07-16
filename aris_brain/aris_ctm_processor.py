"""
Aris CTM Processor — 意识图灵机世界模型处理器
==============================================
Conscious Turing Machine 世界模型处理器
"""

import logging
import time
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger("aris.ctm_processor")

class WorldState:
    """世界状态"""
    
    def __init__(self):
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.relationships: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.events: List[Dict[str, Any]] = []
        self.beliefs: Dict[str, float] = defaultdict(lambda: 0.5)
        
    def add_entity(self, entity_id: str, properties: Dict[str, Any]):
        """添加实体"""
        self.entities[entity_id] = properties
        
    def add_relationship(self, entity1: str, entity2: str, relationship: str):
        """添加关系"""
        self.relationships[entity1].append({"target": entity2, "relationship": relationship})
        self.relationships[entity2].append({"target": entity1, "relationship": relationship})
        
    def add_event(self, event_type: str, entities: List[str], description: str):
        """添加事件"""
        event = {
            "type": event_type,
            "entities": entities,
            "description": description,
            "timestamp": time.time()
        }
        self.events.append(event)
        
    def update_belief(self, belief_key: str, evidence: float):
        """更新信念"""
        # 贝叶斯更新
        current_belief = self.beliefs[belief_key]
        # 简单贝叶斯更新
        self.beliefs[belief_key] = (current_belief * 0.7) + (evidence * 0.3)


class CTMProcessor:
    """CTM处理器 - 意识图灵机世界模型"""
    
    def __init__(self):
        self.world_state = WorldState()
        self.initialized = False
        self._init_processor()
        
    def _init_processor(self):
        """初始化处理器"""
        logger.info("CTM Processor initialized")
        self.initialized = True
        
    def process_input(self, input_text: str) -> Dict[str, Any]:
        """处理输入文本，构建世界模型"""
        # 简单实体和关系提取
        entities = self._extract_entities(input_text)
        relationships = self._extract_relationships(input_text)
        
        # 更新世界状态
        for entity in entities:
            self.world_state.add_entity(entity, {"type": "concept", "confidence": 0.8})
            
        for rel in relationships:
            self.world_state.add_relationship(rel["entity1"], rel["entity2"], rel["relationship"])
            
        # 记录事件
        if entities and relationships:
            # 使用第一个关系作为事件示例
            rel = relationships[0]
            self.world_state.add_event(
                "cognitive_event",
                [rel["entity1"], rel["entity2"]],
                f"Relationship: {rel['entity1']} -{rel['relationship']}-> {rel['entity2']}"
            )
            
        return {
            "status": "processed",
            "entities_count": len(self.world_state.entities),
            "relationships_count": len(self.world_state.relationships),
            "events_count": len(self.world_state.events)
        }
        
    def simulate_scenario(self, scenario: str) -> Dict[str, Any]:
        """模拟场景"""
        # 基于当前世界状态模拟场景结果
        prediction = {
            "scenario": scenario,
            "likely_outcomes": [],
            "confidence": 0.6
        }
        
        # 简单模拟逻辑
        if "conflict" in scenario.lower():
            prediction["likely_outcomes"].append("tension_increase")
            prediction["confidence"] = 0.7
        elif "cooperation" in scenario.lower():
            prediction["likely_outcomes"].append("relationship_strengthen")
            prediction["confidence"] = 0.8
            
        return prediction
        
    def _extract_entities(self, text: str) -> List[str]:
        """提取实体"""
        # 简单实现：提取中文字词
        import re
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        entities = []
        for segment in chinese_chars:
            if len(segment) >= 2:
                entities.append(segment)
        return list(set(entities))[:20]  # 限制数量
        
    def _extract_relationships(self, text: str) -> List[Dict[str, str]]:
        """提取关系"""
        # 简单实现：检测常见关系模式
        relationships = []
        text_lower = text.lower()
        
        # 检测关系模式
        patterns = [
            ("是", "is"),
            ("成为", "becomes"),
            ("影响", "influences"),
            ("导致", "causes"),
            ("帮助", "helps"),
            ("反对", "opposes")
        ]
        
        for entity1 in self._extract_entities(text):
            for entity2 in self._extract_entities(text):
                if entity1 != entity2:
                    for pattern_text, pattern_rel in patterns:
                        if pattern_text in text:
                            relationships.append({
                                "entity1": entity1,
                                "entity2": entity2,
                                "relationship": pattern_rel
                            })
                            
        return relationships[:10]  # 限制数量
        
    def get_world_model_summary(self) -> Dict[str, Any]:
        """获取世界模型摘要"""
        return {
            "entities": list(self.world_state.entities.keys()),
            "relationships": {k: [r["target"] for r in v] for k, v in self.world_state.relationships.items()},
            "recent_events": self.world_state.events[-5:] if self.world_state.events else [],
            "top_beliefs": sorted(self.world_state.beliefs.items(), key=lambda x: x[1], reverse=True)[:5]
        }


def get_ctm_processor() -> CTMProcessor:
    """获取CTM处理器单例"""
    return CTMProcessor()