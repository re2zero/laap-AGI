"""
Aris HAM Memory — 层级注意力记忆
================================
Hierarchical Attentive Memory 层级记忆
"""

import logging
import time
from typing import Dict, Any, List
from collections import deque

logger = logging.getLogger("aris.ham_memory")

class MemoryNode:
    """记忆节点"""
    
    def __init__(self, content: str, memory_type: str, importance: float = 0.5):
        self.content = content
        self.memory_type = memory_type  # 'short', 'medium', 'long', 'episodic', 'semantic'
        self.importance = importance
        self.timestamp = time.time()
        self.access_count = 0
        self.related_nodes = []
        
    def access(self):
        """访问记忆节点"""
        self.access_count += 1
        self.timestamp = time.time()
        
    def get_weighted_importance(self) -> float:
        """计算加权重要性"""
        # 重要性随时间衰减，但访问次数会增加权重
        time_decay = 0.99 ** ((time.time() - self.timestamp) / 3600)  # 每小时衰减1%
        access_boost = min(1.0, self.access_count * 0.1)
        return self.importance * time_decay + access_boost * 0.2


class HAMMemorySystem:
    """HAM层级记忆系统"""
    
    def __init__(self):
        self.short_term_memories: deque = deque(maxlen=50)
        self.medium_term_memories: List[MemoryNode] = []
        self.long_term_memories: List[MemoryNode] = []
        self.episodic_memories: List[MemoryNode] = []
        self.semantic_memories: List[MemoryNode] = []
        
        # 注意力权重
        self.short_term_weight = 0.6
        self.medium_term_weight = 0.3
        self.long_term_weight = 0.1
        
    def add_memory(self, content: str, memory_type: str = "episodic", importance: float = 0.5):
        """添加记忆"""
        node = MemoryNode(content, memory_type, importance)
        
        if memory_type == "short":
            self.short_term_memories.append({"node": node, "timestamp": time.time()})
        elif memory_type == "medium":
            self.medium_term_memories.append(node)
            self._promote_to_long_term(node)
        elif memory_type == "long":
            self.long_term_memories.append(node)
        elif memory_type == "episodic":
            self.episodic_memories.append(node)
            self._promote_to_long_term(node)
        elif memory_type == "semantic":
            self.semantic_memories.append(node)
            self._promote_to_long_term(node)
            
        logger.info(f"Added {memory_type} memory: {content[:50]}...")
        
    def _promote_to_long_term(self, node: MemoryNode):
        """促进记忆到长期记忆"""
        # 如果记忆在中期或情景记忆中很重要，也添加到长期记忆
        if node.importance > 0.7 and node not in self.long_term_memories:
            # 检查是否已存在相似记忆
            existing_similar = self._find_similar_memory(node.content)
            if not existing_similar:
                self.long_term_memories.append(node)
                
    def _find_similar_memory(self, content: str) -> bool:
        """查找相似记忆"""
        # 简单实现：检查内容是否已存在
        for memory_list in [self.long_term_memories, self.episodic_memories, self.semantic_memories]:
            for node in memory_list:
                if node.content == content or content in node.content or node.content in content:
                    return True
        return False
        
    def retrieve_memories(self, context: str, limit: int = 10) -> List[Dict[str, Any]]:
        """检索记忆"""
        retrieved = []
        
        # 1. 短期记忆（最高优先级）
        for mem in list(self.short_term_memories)[-limit:]:
            node = mem["node"]
            node.access()
            retrieved.append({
                "content": node.content,
                "type": "short",
                "importance": node.get_weighted_importance(),
                "timestamp": mem["timestamp"]
            })
            
        # 2. 中期记忆
        medium_memories = sorted(self.medium_term_memories, 
                                key=lambda x: x.get_weighted_importance(), 
                                reverse=True)[:limit//2]
        for node in medium_memories:
            node.access()
            retrieved.append({
                "content": node.content,
                "type": "medium",
                "importance": node.get_weighted_importance(),
                "timestamp": node.timestamp
            })
            
        # 3. 长期记忆
        long_memories = sorted(self.long_term_memories + self.episodic_memories + self.semantic_memories,
                              key=lambda x: x.get_weighted_importance(),
                              reverse=True)[:limit//2]
        for node in long_memories:
            node.access()
            retrieved.append({
                "content": node.content,
                "type": node.memory_type,
                "importance": node.get_weighted_importance(),
                "timestamp": node.timestamp
            })
            
        # 按重要性排序并限制数量
        retrieved.sort(key=lambda x: x["importance"], reverse=True)
        return retrieved[:limit]
        
    def update_attention_weights(self, short_weight: float, medium_weight: float, long_weight: float):
        """更新注意力权重"""
        self.short_term_weight = short_weight
        self.medium_term_weight = medium_weight
        self.long_term_weight = long_weight
        
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        return {
            "short_term_count": len(self.short_term_memories),
            "medium_term_count": len(self.medium_term_memories),
            "long_term_count": len(self.long_term_memories),
            "episodic_count": len(self.episodic_memories),
            "semantic_count": len(self.semantic_memories),
            "attention_weights": {
                "short_term": self.short_term_weight,
                "medium_term": self.medium_term_weight,
                "long_term": self.long_term_weight
            }
        }


class HAMAugmenter:
    """HAM记忆增强器"""
    
    def __init__(self):
        self.memory_system = HAMMemorySystem()
        self.initialized = False
        self._init_augmenter()
        
    def _init_augmenter(self):
        """初始化增强器"""
        logger.info("HAM Memory Augmenter initialized")
        self.initialized = True
        
    def augment_memory(self, memories: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
        """增强记忆"""
        # 将传入的记忆添加到HAM系统
        for mem in memories:
            content = mem.get("content", "")
            mem_type = mem.get("type", "episodic")
            importance = mem.get("importance", 0.5)
            self.memory_system.add_memory(content, mem_type, importance)
            
        # 检索相关记忆
        retrieved = self.memory_system.retrieve_memories(context, limit=10)
        return retrieved

    def get_memory_system(self) -> HAMMemorySystem:
        """获取记忆系统"""
        return self.memory_system


def get_ham_augmenter() -> HAMAugmenter:
    """获取HAM增强器单例"""
    return HAMAugmenter()