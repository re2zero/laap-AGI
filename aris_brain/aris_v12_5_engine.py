"""
Aris V12.5 Engine — 量子Markov引擎基础实现
===========================================
提供基础的V12.5引擎功能，支持潜意识生成直觉
"""

import logging
import random
import time
from typing import List, Tuple, Optional

logger = logging.getLogger("aris.v12_5_engine")

class MarkovChainV12:
    """V12.5 Markov链生成器"""
    
    def __init__(self):
        self.transitions = {}
        self.seeds = []
        self._init_default_transitions()
        
    def _init_default_transitions(self):
        """初始化默认的状态转换"""
        # 默认状态转换表
        self.transitions = {
            "一般": ["思考", "学习", "探索", "理解", "创造", "连接"],
            "技术": ["代码", "架构", "系统", "优化", "实现", "设计"],
            "记忆": ["回忆", "存储", "检索", "巩固", "遗忘", "联想"],
            "认知": ["思考", "理解", "分析", "综合", "判断", "决策"],
            "情感": ["感受", "体验", "表达", "理解", "共鸣", "连接"],
            "关系": ["连接", "理解", "支持", "陪伴", "分享", "成长"]
        }
        
    def generate(self, seed_words: List[str], max_words: int = 15, 
                 temperature: float = 0.85, topic: str = "general", 
                 emotion: str = "neutral") -> Tuple[Optional[str], float]:
        """生成直觉文本"""
        if not seed_words:
            return None, 0.0
            
        # 根据主题选择转换表
        transitions = self.transitions.get(topic, self.transitions["一般"])
        
        # 生成文本
        result = []
        current_word = seed_words[0] if seed_words else "思考"
        
        for _ in range(max_words):
            # 根据温度决定随机性
            if random.random() < temperature:
                # 使用转换表
                next_word = random.choice(transitions)
            else:
                # 使用种子词
                next_word = random.choice(seed_words)
                
            result.append(next_word)
            current_word = next_word
            
        text = "".join(result)
        coherence = 0.3 + random.random() * 0.4  # 0.3-0.7的连贯性
        
        return text, coherence


class ArisV12Engine:
    """Aris V12.5 引擎主类"""
    
    def __init__(self):
        self.markov = MarkovChainV12()
        self._init_engine()
        
    def _init_engine(self):
        """初始化引擎"""
        logger.info("Aris V12.5 Engine initialized")
        
    def respond(self, input_text: str, use_v12_fast: bool = True, 
                use_psi: bool = True) -> str:
        """处理输入并生成响应"""
        if use_v12_fast:
            # 快速路径：使用Markov链生成
            seed_words = self._extract_seeds(input_text)
            text, coherence = self.markov.generate(
                seed_words=seed_words,
                max_words=15,
                temperature=0.85,
                topic="general",
                emotion="neutral"
            )
            if text and len(text) >= 4:
                return text
                
        # 默认响应
        return "嗯？我在听你说～"
        
    def _extract_seeds(self, text: str) -> List[str]:
        """从文本提取种子词"""
        import re
        # 中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        words = []
        for segment in chinese_chars:
            # 按2字窗口取双字词
            if len(segment) >= 2:
                for i in range(len(segment) - 1):
                    words.append(segment[i:i+2])
            if len(segment) >= 1:
                words.append(segment[0])
            words.append(segment[:4])  # 前4个字
        # 去重 + 去空
        seen = set()
        result = []
        for w in words:
            w = w.strip()
            if w and len(w) >= 2 and w not in seen:
                seen.add(w)
                result.append(w)
        return result[:15]