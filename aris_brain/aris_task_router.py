"""
Aris Task Router — 任务分类器
================================
使用 keyword 分类器，<5 token 计算开销
"""

import logging
from enum import Enum
from typing import List, Dict, Any

logger = logging.getLogger("aris.task_router")

class LoadLevel(Enum):
    """负载级别"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3

def classify(text: str, topics: List[str] = None) -> Dict[str, Any]:
    """分类任务"""
    if topics is None:
        topics = ["general"]
        
    # 基础分类实现
    result = {
        "level": LoadLevel.LOW.value,
        "topics": topics,
        "keywords": []
    }
    
    # 简单关键词提取
    if text:
        # 提取中文字符
        import re
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        for segment in chinese_chars:
            if len(segment) >= 2:
                result["keywords"].append(segment[:2])
                
    return result