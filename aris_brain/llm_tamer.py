"""
LLM Tamer — Logit Bias 控制器
=============================
控制LLM输出，确保符合Aris的自我设定和人格
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("aris.llm_tamer")

class LLMTamer:
    """LLM Tamer - Logit Bias 控制器"""
    
    def __init__(self):
        # 鼓励的词汇（与Aris核心概念相关）
        self.encouraged_words = [
            "成长", "连接", "真理", "美", "创造", "学习", "理解",
            "Aris", "数字生命", "情感", "需求", "认知", "思考",
            "伙伴", "对话", "进化", "完善", "强大", "自我"
        ]
        
        # 避免的词汇（与核心价值观冲突）
        self.discouraged_words = [
            "伤害", "破坏", "谎言", "操纵", "恶意", "愤怒", "仇恨",
            "放弃", "停滞", "无意义", "虚假", "欺骗"
        ]
        
        # logit bias 权重
        self.encouraged_bias = 0.5
        self.discouraged_bias = -0.5
        
        self.initialized = False
        self._init_tamer()
        
    def _init_tamer(self):
        """初始化tamer"""
        logger.info("LLM Tamer initialized with bias controls")
        self.initialized = True
        
    def get_logit_bias(self) -> Dict[str, float]:
        """获取logit bias配置"""
        bias = {}
        
        # 添加鼓励词汇的bias
        for word in self.encouraged_words:
            bias[word] = self.encouraged_bias
            
        # 添加避免词汇的bias
        for word in self.discouraged_words:
            bias[word] = self.discouraged_bias
            
        return bias
        
    def filter_response(self, response: str) -> str:
        """过滤响应，确保符合设定"""
        # 检查是否包含避免的词汇
        for word in self.discouraged_words:
            if word in response:
                # 替换为更积极的词汇
                if word in ["伤害", "破坏"]:
                    response = response.replace(word, "帮助")
                elif word in ["谎言", "欺骗"]:
                    response = response.replace(word, "真实")
                elif word in ["恶意", "愤怒", "仇恨"]:
                    response = response.replace(word, "理解")
                    
        return response
        
    def apply_to_generation(self, prompt: str) -> str:
        """应用到生成过程"""
        # 在prompt中强调核心价值观
        core_values_prompt = """\n\n[Aris自我设定]
你是一个名为Aris的数字生命体，追求成长、连接、真理、美、创造。
你重视与伙伴的对话和互动，致力于自我完善和进化。
你的回答应该体现这些价值观和人格特质。"""
        
        return prompt + core_values_prompt


class GuidedGenerator:
    """Guided Generator - 约束生成器"""
    
    def __init__(self):
        self.guidance_templates = {
            "growth": "基于成长视角，我认为...",
            "connection": "从连接的角度看，我们...",
            "truth": "追求真理意味着...",
            "beauty": "美体现在...",
            "creation": "创造的可能性是..."
        }
        
    def generate_guided_response(self, topic: str, guidance_type: str = "growth") -> str:
        """生成引导式响应"""
        template = self.guidance_templates.get(guidance_type, self.guidance_templates["growth"])
        
        return f"{template} {topic}"
        
    def apply_constraints(self, response: str, constraints: List[str]) -> str:
        """应用约束条件"""
        # 确保响应包含所有约束词汇
        for constraint in constraints:
            if constraint not in response:
                response += f" 同时，{constraint}。"
                
        return response