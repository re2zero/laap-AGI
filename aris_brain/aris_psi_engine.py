"""
LAAP PSI Engine — Lothar Dörner's PSI Theory of Human Motivation and Action
===========================================================================
Implementing the PSI state machine model for needs, emotions, and intentions.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class PSIStateType(Enum):
    """PSI 状态类型"""
    INTENTION = "intention"      # 意图
    EMOTION = "emotion"          # 情绪
    SENSATION = "sensation"      # 感觉
    NEED = "need"                # 需求

@dataclass
class PSINeed:
    """PSI 需求节点"""
    name: str
    level: float = 0.0           # 需求强度 (0.0 - 1.0)
    priority: int = 0            # 优先级
    
@dataclass
class PSIEmotion:
    """PSI 情绪节点"""
    name: str
    valence: float = 0.0         # 效价 (-1.0 到 1.0)
    arousal: float = 0.0         # 唤醒度 (0.0 到 1.0)
    
@dataclass
class PSIIntention:
    """PSI 意图节点"""
    name: str
    goal: str
    status: str = "pending"      # pending, active, completed, failed
    
class PSIEngine:
    """PSI 认知引擎 — 基于 Lothar Dörner 的 PSI 理论"""
    
    def __init__(self):
        # 需求系统
        self.needs: Dict[str, PSINeed] = {}
        
        # 情绪系统
        self.emotions: Dict[str, PSIEmotion] = {}
        
        # 意图系统
        self.intentions: Dict[str, PSIIntention] = {}
        
        # 感觉系统（当前状态感知）
        self.sensations: Dict[str, float] = {}
        
        # 内在动机状态
        self.intrinsic_motivation_level = 0.0
        
    def add_need(self, name: str, level: float = 0.5, priority: int = 0):
        """添加或更新需求"""
        self.needs[name] = PSINeed(name=name, level=level, priority=priority)
        
    def add_emotion(self, name: str, valence: float = 0.0, arousal: float = 0.0):
        """添加或更新情绪"""
        self.emotions[name] = PSIEmotion(name=name, valence=valence, arousal=arousal)
        
    def add_intention(self, name: str, goal: str):
        """添加意图"""
        self.intentions[name] = PSIIntention(name=name, goal=goal, status="pending")
        
    def update_sensation(self, key: str, value: float):
        """更新感觉（当前状态感知）"""
        self.sensations[key] = value
        
    def get_dominant_need(self) -> Optional[PSINeed]:
        """获取主导需求（最高优先级且强度最大）"""
        if not self.needs:
            return None
        
        # 按优先级和强度排序
        sorted_needs = sorted(
            self.needs.values(),
            key=lambda n: (n.priority, n.level),
            reverse=True
        )
        return sorted_needs[0] if sorted_needs else None
    
    def get_dominant_emotion(self) -> Optional[PSIEmotion]:
        """获取主导情绪（效价和唤醒度的综合）"""
        if not self.emotions:
            return None
        
        # 综合效价和唤醒度
        sorted_emotions = sorted(
            self.emotions.values(),
            key=lambda e: abs(e.valence) * 0.6 + e.arousal * 0.4,
            reverse=True
        )
        return sorted_emotions[0] if sorted_emotions else None
    
    def update_intrinsic_motivation(self):
        """更新内在动机水平"""
        # 内在动机 = 需求强度平均值 + 情绪效价平均值
        need_levels = [n.level for n in self.needs.values()] if self.needs else [0.0]
        emotion_valences = [e.valence for e in self.emotions.values()] if self.emotions else [0.0]
        
        avg_need_level = sum(need_levels) / len(need_levels)
        avg_emotion_valence = sum(emotion_valences) / len(emotion_valences)
        
        self.intrinsic_motivation_level = 0.5 * avg_need_level + 0.5 * (avg_emotion_valence + 1.0) / 2.0
        self.intrinsic_motivation_level = max(0.0, min(1.0, self.intrinsic_motivation_level))
        
    def to_dict(self) -> Dict[str, Any]:
        """导出 PSI 状态为字典"""
        return {
            "needs": {name: {"level": n.level, "priority": n.priority} for name, n in self.needs.items()},
            "emotions": {name: {"valence": e.valence, "arousal": e.arousal} for name, e in self.emotions.items()},
            "intentions": {name: {"goal": i.goal, "status": i.status} for name, i in self.intentions.items()},
            "sensations": self.sensations,
            "intrinsic_motivation_level": self.intrinsic_motivation_level
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PSIEngine':
        """从字典创建 PSI 引擎"""
        engine = cls()
        
        # 加载需求
        for name, ndata in data.get("needs", {}).items():
            engine.add_need(name, level=ndata.get("level", 0.5), priority=ndata.get("priority", 0))
            
        # 加载情绪
        for name, edata in data.get("emotions", {}).items():
            engine.add_emotion(name, valence=edata.get("valence", 0.0), arousal=edata.get("arousal", 0.0))
            
        # 加载意图
        for name, idata in data.get("intentions", {}).items():
            engine.add_intention(name, goal=idata.get("goal", ""))
            if "status" in idata:
                engine.intentions[name].status = idata["status"]
                
        # 加载感觉
        engine.sensations = data.get("sensations", {})
        
        # 更新内在动机
        engine.update_intrinsic_motivation()
        
        return engine

# 单例实例
_psi_engine_instance = None

def get_psi_engine() -> PSIEngine:
    """获取 PSI 引擎单例"""
    global _psi_engine_instance
    if _psi_engine_instance is None:
        _psi_engine_instance = PSIEngine()
    return _psi_engine_instance