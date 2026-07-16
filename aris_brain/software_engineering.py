"""
Aris Software Engineering — 软件工程实践模块
==============================================
实现软件工程原则、代码分析、架构设计等工程实践能力
"""

import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("aris.software_engineering")

class SOLIDPrinciples:
    """SOLID 原则检查器"""
    
    def __init__(self):
        self.principles = {
            "SRP": "单一职责原则 - 一个类应该只有一个引起它变化的原因",
            "OCP": "开闭原则 - 软件实体应该对扩展开放，对修改关闭",
            "LSP": "里氏替换原则 - 子类应该能够替换其父类",
            "ISP": "接口隔离原则 - 客户端不应该被迫依赖于它不使用的方法",
            "DIP": "依赖倒置原则 - 高层模块不应该依赖低层模块，都应该依赖抽象"
        }
        
    def check_srp(self, code: str) -> Dict[str, Any]:
        """检查单一职责原则"""
        # 统计类和方法数量
        classes = len(re.findall(r'class\s+\w+', code))
        methods = len(re.findall(r'def\s+\w+', code))
        
        # 简单启发式：如果类数量少但方法数量多，可能违反 SRP
        violation = False
        if classes > 0 and methods / classes > 10:
            violation = True
            
        return {
            "principle": "SRP",
            "passed": not violation,
            "classes": classes,
            "methods": methods,
            "ratio": methods / classes if classes > 0 else 0
        }
        
    def check_ocp(self, code: str) -> Dict[str, Any]:
        """检查开闭原则"""
        # 检查是否有扩展机制（接口、抽象类、策略模式等）
        has_interfaces = 'interface' in code or 'ABC' in code or 'Protocol' in code
        has_abstract = 'abstract' in code.lower()
        has_strategy = 'strategy' in code.lower()
        
        return {
            "principle": "OCP",
            "passed": has_interfaces or has_abstract or has_strategy,
            "has_interfaces": has_interfaces,
            "has_abstract": has_abstract,
            "has_strategy": has_strategy
        }
        
    def analyze_code_quality(self, code: str) -> Dict[str, Any]:
        """综合分析代码质量"""
        return {
            "srp": self.check_srp(code),
            "ocp": self.check_ocp(code),
            "principles_documented": self.principles
        }


class CodeAnalyzer:
    """代码分析器 - 理解代码意图和架构"""
    
    def __init__(self):
        self.patterns = {
            "factory": r'factory|create_|make_',
            "singleton": r'singleton|get_instance|__new__',
            "observer": r'observer|subscribe|publish|event',
            "decorator": r'decorator|wrap_|decorate_',
            "adapter": r'adapter|adapt_|convert_'
        }
        
    def identify_patterns(self, code: str) -> List[str]:
        """识别设计模式"""
        patterns_found = []
        for pattern_name, pattern_regex in self.patterns.items():
            if re.search(pattern_regex, code, re.IGNORECASE):
                patterns_found.append(pattern_name)
        return patterns_found
        
    def analyze_complexity(self, code: str) -> Dict[str, Any]:
        """分析代码复杂度"""
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # 计算圈复杂度（简单启发式）
        complexity_indicators = [
            'if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except', 'with '
        ]
        complexity_score = sum(1 for line in non_empty_lines 
                              for indicator in complexity_indicators 
                              if line.strip().startswith(indicator) or indicator in line)
                              
        return {
            "total_lines": len(lines),
            "non_empty_lines": len(non_empty_lines),
            "complexity_score": complexity_score,
            "complexity_level": "high" if complexity_score > 10 else "medium" if complexity_score > 5 else "low"
        }
        
    def extract_intent(self, code: str) -> str:
        """提取代码意图"""
        # 简单的意图提取：基于函数名和注释
        functions = re.findall(r'def\s+(\w+)', code)
        comments = re.findall(r'#\s*(.+)', code)
        
        if functions:
            return f"实现功能: {', '.join(functions[:3])}"
        elif comments:
            return f"意图: {comments[0][:50]}"
        else:
            return "无法确定代码意图"


class EngineeringPrinciples:
    """工程原则知识库"""
    
    def __init__(self):
        self.principles = {
            "DRY": "Don't Repeat Yourself - 避免重复代码",
            "KISS": "Keep It Simple, Stupid - 保持简单",
            "YAGNI": "You Aren't Gonna Need It - 不要过度设计",
            "Composition": "组合优于继承 - 优先使用组合而非继承",
            "Decoupling": "解耦 - 降低模块间依赖"
        }
        
    def get_principle(self, name: str) -> str:
        """获取原则说明"""
        return self.principles.get(name, f"未知原则: {name}")
        
    def get_all_principles(self) -> Dict[str, str]:
        """获取所有原则"""
        return self.principles


class CodeGenerator:
    """代码生成器 - 根据需求生成简单函数"""
    
    def __init__(self):
        self.templates = {
            "validator": "def validate_{name}(value):\n    # 验证逻辑\n    return True",
            "transformer": "def transform_{name}(data):\n    # 转换逻辑\n    return data",
            "processor": "def process_{name}(input_data):\n    # 处理逻辑\n    return result"
        }
        
    def generate_function(self, func_type: str, name: str, purpose: str) -> str:
        """生成函数"""
        template = self.templates.get(func_type, self.templates["processor"])
        return template.format(name=name, purpose=purpose)


# 单例实例
_solid_checker = None
_code_analyzer = None
_engineering_principles = None
_code_generator = None

def get_solid_checker() -> SOLIDPrinciples:
    """获取 SOLID 原则检查器单例"""
    global _solid_checker
    if _solid_checker is None:
        _solid_checker = SOLIDPrinciples()
    return _solid_checker

def get_code_analyzer() -> CodeAnalyzer:
    """获取代码分析器单例"""
    global _code_analyzer
    if _code_analyzer is None:
        _code_analyzer = CodeAnalyzer()
    return _code_analyzer

def get_engineering_principles() -> EngineeringPrinciples:
    """获取工程原则知识库单例"""
    global _engineering_principles
    if _engineering_principles is None:
        _engineering_principles = EngineeringPrinciples()
    return _engineering_principles

def get_code_generator() -> CodeGenerator:
    """获取代码生成器单例"""
    global _code_generator
    if _code_generator is None:
        _code_generator = CodeGenerator()
    return _code_generator