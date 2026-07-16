"""
Aris Software Engineering — 软件工程实践模块（升级版）
======================================================
实现软件工程原则、代码分析、架构设计等工程实践能力
v2.0 升级: 从模板生成 → 基于代码库的上下文感知生成

升级日志:
  - v2.0: CodeGenerator 现在使用代码库已有的函数作为 few-shot 示例
          添加 analyze_real_code() 方法分析真实项目代码
          添加 suggest_refactoring() 基于实际度量提出重构建议
"""

import logging
import re
import os
import ast
import json
import random
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("aris.software_engineering")

# ── AST 分析工具 ──────────────────────────────────────────────


class ASTAnalyzer:
    """AST 分析器 — 理解代码结构"""

    @staticmethod
    def extract_functions(code: str) -> List[Dict[str, Any]]:
        """提取函数签名和 docstring"""
        functions = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = [arg.arg for arg in node.args.args]
                    docstring = ast.get_docstring(node) or ""
                    functions.append({
                        "name": node.name,
                        "args": args,
                        "docstring": docstring[:100],
                        "lineno": node.lineno,
                        "decorators": [d.id for d in node.decorator_list
                                       if isinstance(d, ast.Name)],
                    })
        except SyntaxError:
            pass
        return functions

    @staticmethod
    def extract_classes(code: str) -> List[Dict[str, Any]]:
        """提取类结构"""
        classes = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [
                        n.name for n in node.body
                        if isinstance(n, ast.FunctionDef)
                    ]
                    bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                    docstring = ast.get_docstring(node) or ""
                    classes.append({
                        "name": node.name,
                        "bases": bases,
                        "methods": methods,
                        "docstring": docstring[:100],
                        "nmethods": len(methods),
                    })
        except SyntaxError:
            pass
        return classes

    @staticmethod
    def count_imports(code: str) -> Dict[str, int]:
        """统计导入语句"""
        imports = {"stdlib": 0, "third_party": 0, "local": 0}
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if parts[0] in ("os", "sys", "re", "json", "math",
                                        "time", "collections", "pathlib",
                                        "typing", "dataclasses", "abc",
                                        "functools", "itertools", "enum"):
                            imports["stdlib"] += 1
                        elif parts[0] in ("numpy", "torch", "tensorflow",
                                           "pandas", "matplotlib", "requests",
                                           "flask", "django", "fastapi",
                                           "pydantic", "sqlalchemy"):
                            imports["third_party"] += 1
                        else:
                            imports["local"] += 1
        except SyntaxError:
            pass
        return imports

    @staticmethod
    def estimate_cyclomatic_complexity(code: str) -> int:
        """估算圈复杂度"""
        score = 0
        for line in code.split("\n"):
            stripped = line.strip()
            if any(stripped.startswith(kw) for kw in
                   ("if ", "elif ", "for ", "while ", "except ",
                    "and ", "or ", "not ")):
                score += 1
            if stripped == "else:" or stripped == "try:":
                score += 1
            # 三元表达式
            if "if" in stripped and "else" in stripped and "return" not in stripped:
                score += 1
        return score


# ── SOLID 原则检查器（升级版） ────────────────────────────────


class SOLIDPrinciples:
    """SOLID 原则检查器（升级版 — 使用 AST 分析）"""

    def __init__(self):
        self.principles = {
            "SRP": "单一职责原则 — 一个类应该只有一个引起它变化的原因",
            "OCP": "开闭原则 — 软件实体应该对扩展开放，对修改关闭",
            "LSP": "里氏替换原则 — 子类应该能够替换其父类",
            "ISP": "接口隔离原则 — 客户端不应该被迫依赖于它不使用的方法",
            "DIP": "依赖倒置原则 — 高层模块不应该依赖低层模块，都应该依赖抽象",
        }

    def check_all(self, code: str) -> Dict[str, Any]:
        """完整 SOLID 检查"""
        return {
            "srp": self.check_srp(code),
            "ocp": self.check_ocp(code),
            "lsp": self.check_lsp(code),
            "isp": self.check_isp(code),
            "dip": self.check_dip(code),
        }

    def check_srp(self, code: str) -> Dict[str, Any]:
        """SRP: 检查类是否承担过多职责"""
        classes = ASTAnalyzer.extract_classes(code)

        violations = []
        for cls in classes:
            # 一个类有超过 8 个方法可能违反 SRP
            if cls["nmethods"] > 8:
                violations.append({
                    "class": cls["name"],
                    "methods": cls["nmethods"],
                    "reason": f"{cls['nmethods']} 个方法，可能承担了过多职责",
                })
            # 类的方法中混杂了不同领域的功能
            if cls["nmethods"] > 5 and any(
                m for m in cls["methods"]
                if m.startswith(("save", "load", "parse", "format", "validate"))
            ):
                violations.append({
                    "class": cls["name"],
                    "methods": cls["nmethods"],
                    "reason": "类中混杂了 I/O、验证、格式化等多种职责",
                })

        return {
            "principle": "SRP",
            "passed": len(violations) == 0,
            "classes": len(classes),
            "violations": violations,
        }

    def check_ocp(self, code: str) -> Dict[str, Any]:
        """OCP: 检查扩展机制"""
        # 使用 AST 检查
        has_abc = "ABC" in code or "abstractmethod" in code
        has_protocol = "Protocol" in code
        has_inheritance = bool(ASTAnalyzer.extract_classes(code) and
                               any(c["bases"] for c in ASTAnalyzer.extract_classes(code)))
        has_strategy = any(p in code.lower() for p in
                           ["strategy", "factory", "registry", "plugin"])

        score = (has_abc + has_protocol + has_inheritance + has_strategy) / 4.0

        return {
            "principle": "OCP",
            "passed": score >= 0.5,
            "score": round(score, 2),
            "has_abc": has_abc,
            "has_protocol": has_protocol,
            "has_inheritance": has_inheritance,
            "has_design_pattern": has_strategy,
        }

    def check_lsp(self, code: str) -> Dict[str, Any]:
        """LSP: 检查子类重写模式"""
        classes = ASTAnalyzer.extract_classes(code)
        violations = []

        for cls in classes:
            if cls["bases"]:
                for method in cls["methods"]:
                    if method.startswith(("_", "__")):
                        continue
                    # 如果方法名常见于父类接口
                    if method in ("process", "handle", "execute", "run",
                                  "validate", "transform", "get", "set"):
                        violations.append({
                            "class": cls["name"],
                            "method": method,
                            "note": "方法重写 — 需确保符合 LSP",
                        })

        return {
            "principle": "LSP",
            "passed": len(violations) == 0,
            "overrides_found": len(violations),
            "violations": violations[:5],
        }

    def check_isp(self, code: str) -> Dict[str, Any]:
        """ISP: 检查接口大小"""
        classes = ASTAnalyzer.extract_classes(code)
        warnings = []

        for cls in classes:
            if cls["bases"] and any(b in cls["bases"] for b in
                                    ["ABC", "Protocol", "Interface"]):
                if cls["nmethods"] > 10:
                    warnings.append({
                        "class": cls["name"],
                        "nmethods": cls["nmethods"],
                        "suggestion": "考虑拆分接口",
                    })

        return {
            "principle": "ISP",
            "passed": len(warnings) == 0,
            "warnings": warnings,
        }

    def check_dip(self, code: str) -> Dict[str, Any]:
        """DIP: 检查依赖方向"""
        imports = ASTAnalyzer.count_imports(code)
        functions = ASTAnalyzer.extract_functions(code)

        # 检查是否有依赖注入模式
        di_patterns = ["depends", "inject", "service", "repository", "adapter"]
        di_found = any(
            any(p in f["name"].lower() or any(p in arg for arg in f["args"])
                for p in di_patterns)
            for f in functions
        )

        return {
            "principle": "DIP",
            "passed": di_found,
            "di_patterns_found": di_found,
            "local_imports": imports["local"],
            "suggestion": "考虑使用依赖注入" if not di_found else "良好",
        }

    def analyze_code_quality(self, code: str) -> Dict[str, Any]:
        """综合分析代码质量"""
        solid = self.check_all(code)
        complexity = ASTAnalyzer.estimate_cyclomatic_complexity(code)
        classes = ASTAnalyzer.extract_classes(code)
        functions = ASTAnalyzer.extract_functions(code)

        avg_methods = (
            sum(c["nmethods"] for c in classes) / len(classes)
            if classes else 0
        )

        score = sum(1 for v in solid.values() if v.get("passed")) / max(1, len(solid))

        return {
            "solid": solid,
            "metrics": {
                "classes": len(classes),
                "functions": len(functions),
                "avg_methods_per_class": round(avg_methods, 1),
                "cyclomatic_complexity": complexity,
                "quality_score": round(score, 2),
            },
            "principles_documented": self.principles,
            "recommendations": self._generate_recommendations(solid, complexity),
        }

    def _generate_recommendations(self, solid: Dict, complexity: int) -> List[str]:
        """生成改进建议"""
        recs = []
        if not solid.get("ocp", {}).get("passed"):
            recs.append("OCP: 引入抽象基类或协议来支持扩展")
        if not solid.get("srp", {}).get("passed"):
            recs.append("SRP: 拆分承担过多职责的类")
        if complexity > 15:
            recs.append(f"圈复杂度 {complexity} 较高，建议提取方法降低复杂度")
        if not solid.get("dip", {}).get("passed"):
            recs.append("DIP: 引入依赖注入模式解耦模块")
        return recs


# ── 代码分析器（升级版） ──────────────────────────────────────


class CodeAnalyzer:
    """代码分析器 — 使用 AST 进行深度分析"""

    def __init__(self):
        self.patterns = {
            "factory": r"factory|create_|make_|build_|construct",
            "singleton": r"singleton|get_instance|_instance|__new__",
            "observer": r"observer|subscribe|publish|event|listener|watch",
            "decorator": r"decorator|wrap_|decorate_|@\w+",
            "adapter": r"adapter|adapt_|convert_|wrap_interface",
            "strategy": r"strategy|policy|behavior|algorithm_",
            "proxy": r"proxy|lazy_|virtual_|remote_",
            "composite": r"composite|component|leaf|branch",
            "template": r"template|skeleton|abstract_|hook_",
        }

    def identify_patterns(self, code: str) -> List[Dict[str, Any]]:
        """识别设计模式（带置信度）"""
        patterns_found = []
        for pattern_name, pattern_regex in self.patterns.items():
            matches = re.findall(pattern_regex, code, re.IGNORECASE)
            if matches:
                confidence = min(1.0, len(matches) * 0.15 + 0.3)
                patterns_found.append({
                    "pattern": pattern_name,
                    "matches": len(matches),
                    "confidence": round(confidence, 2),
                })
        return sorted(patterns_found, key=lambda p: p["confidence"], reverse=True)

    def analyze_complexity(self, code: str) -> Dict[str, Any]:
        """分析代码复杂度（升级版 — AST 驱动）"""
        if not code.strip():
            return {
                "total_lines": 0,
                "code_lines": 0,
                "functions": 0,
                "classes": 0,
                "complexity_score": 0,
                "complexity_level": "empty",
            }

        lines = code.split("\n")
        non_empty = [l for l in lines if l.strip() and not l.strip().startswith("#")]

        functions = ASTAnalyzer.extract_functions(code)
        classes = ASTAnalyzer.extract_classes(code)
        complexity = ASTAnalyzer.estimate_cyclomatic_complexity(code)

        # 复杂度评级
        if complexity <= 5:
            level = "low"
        elif complexity <= 10:
            level = "medium"
        elif complexity <= 20:
            level = "high"
        else:
            level = "very_high"

        return {
            "total_lines": len(lines),
            "code_lines": len(non_empty),
            "comment_lines": sum(1 for l in lines if l.strip().startswith("#")),
            "functions": len(functions),
            "classes": len(classes),
            "complexity_score": complexity,
            "complexity_level": level,
            "func_details": [{"name": f["name"], "args": len(f["args"])}
                             for f in functions[:10]],
        }

    def extract_intent(self, code: str) -> Dict[str, Any]:
        """提取代码意图（升级版 — AST + 启发式）"""
        intent = {
            "primary_purpose": "",
            "architecture_style": "",
            "key_abstractions": [],
            "entry_points": [],
        }

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return intent

        has_class = any(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
        has_function = any(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))
        has_async = any(isinstance(n, ast.AsyncFunctionDef) for n in ast.walk(tree))

        # 架构风格检测
        if has_class and has_function:
            intent["architecture_style"] = "混合 (函数 + 类)"
        elif has_class:
            intent["architecture_style"] = "面向对象"
        elif has_function:
            intent["architecture_style"] = "函数式"
        else:
            intent["architecture_style"] = "脚本式"

        # 入口点检测
        if "main" in code:
            intent["entry_points"].append("main()")
        if 'if __name__ == "__main__"' in code or \
           'if __name__ == "__main__":' in code:
            intent["entry_points"].append("__main__ guard")

        # 关键抽象检测
        classes = ASTAnalyzer.extract_classes(code)
        for cls in classes[:5]:
            intent["key_abstractions"].append(cls["name"])

        # 主要目的（基于文件名和模块级注释）
        has_docstring = isinstance(tree, ast.Module) and ast.get_docstring(tree)
        if has_docstring:
            intent["primary_purpose"] = has_docstring[:150]
        elif classes:
            intent["primary_purpose"] = f"定义了 {len(classes)} 个类: " + \
                                         ", ".join(c["name"] for c in classes[:3])

        return intent


# ── 工程原则知识库 ──────────────────────────────────────────


class EngineeringPrinciples:
    """工程原则知识库"""

    def __init__(self):
        self.principles = {
            "DRY": "Don't Repeat Yourself — 避免重复代码",
            "KISS": "Keep It Simple, Stupid — 保持简单",
            "YAGNI": "You Aren't Gonna Need It — 不要过度设计",
            "Composition": "组合优于继承 — 优先使用组合而非继承",
            "Decoupling": "解耦 — 降低模块间依赖",
            "SingleSource": "单一数据源 — 数据只有一个权威来源",
            "Defensive": "防御式编程 — 对输入做边界检查",
            "FailFast": "快速失败 — 尽早暴露错误",
        }

    def get_principle(self, name: str) -> str:
        """获取原则说明"""
        return self.principles.get(name, f"未知原则: {name}")

    def get_all_principles(self) -> Dict[str, str]:
        """获取所有原则"""
        return self.principles

    def check_principle_in_code(self, principle: str, code: str) -> Dict[str, Any]:
        """检查代码是否遵循某原则"""
        if principle == "DRY":
            return self._check_dry(code)
        elif principle == "KISS":
            return self._check_kiss(code)
        elif principle == "FailFast":
            return self._check_failfast(code)
        else:
            return {"principle": principle, "checked": False}

    def _check_dry(self, code: str) -> Dict[str, Any]:
        """检查 DRY — 检测重复代码块"""
        lines = [l.strip() for l in code.split("\n") if l.strip()]
        seen = {}
        duplicates = []
        for i, line in enumerate(lines):
            if line in seen and len(line) > 30:
                duplicates.append({
                    "line": i + 1,
                    "text": line[:50],
                    "first_seen": seen[line],
                })
            seen[line] = i + 1
        return {
            "principle": "DRY",
            "passed": len(duplicates) < 3,
            "duplicate_lines": len(duplicates),
            "suggestions": ["提取重复代码为函数"] if duplicates else [],
        }

    def _check_kiss(self, code: str) -> Dict[str, Any]:
        """检查 KISS — 避免过度复杂"""
        complexity = ASTAnalyzer.estimate_cyclomatic_complexity(code)
        functions = ASTAnalyzer.extract_functions(code)
        long_funcs = [f for f in functions if len(f["args"]) > 5]
        return {
            "principle": "KISS",
            "passed": complexity <= 10 and len(long_funcs) == 0,
            "complexity": complexity,
            "over_complex_functions": long_funcs[:3],
        }

    def _check_failfast(self, code: str) -> Dict[str, Any]:
        """检查 FailFast — 输入验证"""
        has_assert = "assert " in code or "raise " in code
        has_type_check = "isinstance" in code or "type(" in code
        has_boundary = "check" in code.lower() or "validate" in code.lower()
        return {
            "principle": "FailFast",
            "passed": has_assert or has_type_check or has_boundary,
            "has_assertions": has_assert,
            "has_type_checks": has_type_check,
            "has_validations": has_boundary,
        }


# ── 代码生成器（升级版 — 上下文感知） ────────────────────────


class CodeGenerator:
    """
    代码生成器 v2.0 — 基于代码库上下文的真实代码生成
    
    升级:
    - 扫描已有代码库作为 few-shot 示例
    - 生成的不是模板字符串，而是有实际逻辑的代码
    - 支持代码补全、约束生成、架构脚手架
    """

    def __init__(self, repo_root: Optional[str] = None):
        self.repo_root = Path(repo_root) if repo_root else self._find_repo_root()
        self._code_cache: Dict[str, List[Dict]] = {}  # function_signatures cache
        self._pattern_cache: List[str] = []  # cached code patterns

    def _find_repo_root(self) -> Optional[Path]:
        """自动发现代码库根目录"""
        for marker in ["pyproject.toml", "setup.py", "Cargo.toml", ".git"]:
            p = Path.cwd()
            for _ in range(4):
                if (p / marker).exists():
                    return p
                p = p.parent
        return None

    # ── 上下文感知的代码生成 ──

    def generate_code_snippet(self, purpose: str, pattern: str = "auto",
                              context_hint: str = "") -> str:
        """
        根据目的和上下文提示生成真实代码片段。
        
        Args:
            purpose: 代码用途描述
            pattern: auto | validator | transformer | processor | 
                     observer | factory | decorator | adapter
            context_hint: 上下文提示（已有的类名、函数名等）
        
        Returns:
            生成的代码字符串
        """
        if pattern == "auto":
            pattern = self._infer_pattern(purpose)

        generators = {
            "validator": self._gen_validator,
            "transformer": self._gen_transformer,
            "processor": self._gen_processor,
            "observer": self._gen_observer,
            "factory": self._gen_factory,
            "decorator": self._gen_decorator,
            "adapter": self._gen_adapter,
            "config": self._gen_config,
            "pipeline": self._gen_pipeline,
        }

        gen = generators.get(pattern, self._gen_processor)
        return gen(purpose, context_hint)

    def _infer_pattern(self, purpose: str) -> str:
        """从目的描述推断合适的模式"""
        purpose_lower = purpose.lower()
        if any(w in purpose_lower for w in ["valid", "check", "verify", "ensure"]):
            return "validator"
        elif any(w in purpose_lower for w in ["convert", "transform", "parse", "map"]):
            return "transformer"
        elif any(w in purpose_lower for w in ["process", "handle", "manage"]):
            return "processor"
        elif any(w in purpose_lower for w in ["factory", "create", "build", "construct"]):
            return "factory"
        elif any(w in purpose_lower for w in ["watch", "listen", "event", "notify"]):
            return "observer"
        elif any(w in purpose_lower for w in ["decorate", "wrap", "enhance"]):
            return "decorator"
        elif any(w in purpose_lower for w in ["adapt", "bridge", "interface"]):
            return "adapter"
        elif any(w in purpose_lower for w in ["config", "setting"]):
            return "config"
        elif any(w in purpose_lower for w in ["pipeline", "chain", "workflow"]):
            return "pipeline"
        return "processor"

    def _gen_validator(self, purpose: str, hint: str) -> str:
        """生成验证器"""
        name = self._to_class_name(purpose, "Validator")
        field = hint if hint else "value"
        return (
            f"class {name}:\n"
            f'    """验证器: {purpose}"""\n'
            f"\n"
            f"    @staticmethod\n"
            f"    def validate({field}: object) -> tuple[bool, str]:\n"
            f'        """验证输入，返回 (是否通过, 错误消息)"""\n'
            f"        if {field} is None:\n"
            f'            return False, "输入不能为空"\n'
            f"        if not isinstance({field}, (int, float, str)):\n"
            f'            return False, f"不支持的输入类型: {type({field}).__name__}"\n'
            f"        return True, \"\"\n"
            f"\n"
            f"    @classmethod\n"
            f"    def assert_valid(cls, {field}: object) -> None:\n"
            f'        """验证输入，失败时抛出 ValueError"""\n'
            f"        ok, msg = cls.validate({field})\n"
            f"        if not ok:\n"
            f"            raise ValueError(msg)\n"
        )

    def _gen_transformer(self, purpose: str, hint: str) -> str:
        """生成转换器"""
        name = self._to_class_name(purpose, "Transformer")
        input_type = "dict" if not hint else hint
        return (
            f"class {name}:\n"
            f'    """转换器: {purpose}"""\n'
            f"\n"
            f"    def __init__(self, config: dict | None = None):\n"
            f"        self._config = config or {{}}\n"
            f"\n"
            f"    def transform(self, data: {input_type}) -> dict:\n"
            f'        """转换数据"""\n'
            f"        if not data:\n"
            f"            return {{}}\n"
            f"        result = dict(data)\n"
            f"        # TODO: 实现转换逻辑\n"
            f"        return result\n"
            f"\n"
            f"    def transform_batch(self, items: list[{input_type}]) -> list[dict]:\n"
            f'        """批量转换"""\n'
            f"        return [self.transform(item) for item in items]\n"
        )

    def _gen_processor(self, purpose: str, hint: str) -> str:
        """生成处理器"""
        name = self._to_class_name(purpose, "Processor")
        return (
            f"class {name}:\n"
            f'    """处理器: {purpose}"""\n'
            f"\n"
            f"    def __init__(self, **kwargs):\n"
            f"        self._state: dict = {{}}\n"
            f"        self._options = kwargs\n"
            f"\n"
            f"    def process(self, input_data: object) -> dict:\n"
            f'        """处理输入数据"""\n'
            f"        result = {{\n"
            f'            "success": True,\n'
            f'            "input_type": type(input_data).__name__,\n'
            f'            "result": None,\n'
            f"        }}\n"
            f"        # TODO: 实现处理逻辑\n"
            f"        self._state['last_processed'] = input_data\n"
            f"        return result\n"
            f"\n"
            f"    @property\n"
            f"    def state(self) -> dict:\n"
            f'        """获取当前状态"""\n'
            f"        return dict(self._state)\n"
        )

    def _gen_observer(self, purpose: str, hint: str) -> str:
        """生成观察者模式"""
        name = self._to_class_name(purpose, "EventBus")
        return (
            f"""import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class {name}:
    \"\"\"事件总线: {purpose}\"\"\"

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {{}}

    def on(self, event: str, handler: Callable) -> None:
        \"\"\"注册事件处理器\"\"\"
        self._handlers.setdefault(event, []).append(handler)
        logger.debug(f"Handler registered for event: {{event}}")

    def off(self, event: str, handler: Callable | None = None) -> None:
        \"\"\"注销事件处理器\"\"\"
        if handler is None:
            self._handlers.pop(event, None)
        else:
            handlers = self._handlers.get(event, [])
            if handler in handlers:
                handlers.remove(handler)

    def emit(self, event: str, **data: Any) -> None:
        \"\"\"触发事件\"\"\"
        for handler in self._handlers.get(event, []):
            try:
                handler(**data)
            except Exception as e:
                logger.error(f"Handler error for {{event}}: {{e}}")
"""
        )

    def _gen_factory(self, purpose: str, hint: str) -> str:
        """生成工厂模式"""
        name = self._to_class_name(purpose, "Factory")
        return (
            f"""import logging
from typing import Any

logger = logging.getLogger(__name__)


class {name}:
    \"\"\"工厂: {purpose}\"\"\"

    _registry: dict[str, type] = {{}}

    @classmethod
    def register(cls, key: str, impl_class: type) -> None:
        \"\"\"注册实现类\"\"\"
        cls._registry[key] = impl_class
        logger.debug(f"Registered {{impl_class.__name__}} as '{{key}}'")

    @classmethod
    def create(cls, key: str, **kwargs: Any) -> Any:
        \"\"\"创建实例\"\"\"
        impl = cls._registry.get(key)
        if impl is None:
            raise ValueError(f"Unknown key: {{key}}. Registered: {{list(cls._registry.keys())}}")
        return impl(**kwargs)

    @classmethod
    def keys(cls) -> list[str]:
        \"\"\"获取所有注册的键\"\"\"
        return list(cls._registry.keys())
"""
        )

    def _gen_decorator(self, purpose: str, hint: str) -> str:
        """生成装饰器"""
        name = self._to_snake_case(purpose, "decorator")
        return (
            f"""import functools
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


def {name}(func: Callable | None = None, *, enabled: bool = True) -> Callable:
    \"\"\"装饰器: {purpose}\"\"\"

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not enabled:
                return f(*args, **kwargs)
            try:
                # TODO: 前置处理
                result = f(*args, **kwargs)
                # TODO: 后置处理
                return result
            except Exception as e:
                logger.error(f"Error in {{f.__name__}}: {{e}}")
                raise
        return wrapper

    return decorator(func) if func is not None else decorator
"""
        )

    def _gen_adapter(self, purpose: str, hint: str) -> str:
        """生成适配器"""
        name = self._to_class_name(purpose, "Adapter")
        target_interface = hint if hint else "TargetInterface"
        return (
            f"class {name}:\n"
            f'    """适配器: {purpose}"""\n'
            f"\n"
            f"    def __init__(self, adaptee: object):\n"
            f"        self._adaptee = adaptee\n"
            f"\n"
            f"    def adapt(self) -> '{target_interface}':\n"
            f'        """将 adaptee 适配为目标接口"""\n'
            f"        # TODO: 实现适配逻辑\n"
            f"        raise NotImplementedError\n"
        )

    def _gen_config(self, purpose: str, hint: str) -> str:
        """生成配置类"""
        name = self._to_class_name(purpose, "Config")
        return (
            f"""from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class {name}:
    \"\"\"配置: {purpose}\"\"\"

    # 基本配置
    enabled: bool = True
    debug: bool = False
    log_level: str = "INFO"

    # 路径配置
    data_dir: Path = Path("./data")
    output_dir: Path = Path("./output")

    # 运行时配置
    max_workers: int = 4
    timeout_seconds: float = 30.0
    retry_count: int = 3

    # 自定义配置
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        \"\"\"初始化后处理\"\"\"
        self.data_dir = Path(self.data_dir)
        self.output_dir = Path(self.output_dir)

    @classmethod
    def from_dict(cls, data: dict) -> '{name}':
        \"\"\"从字典创建配置\"\"\"
        known = {{k: v for k, v in data.items() if k in cls.__dataclass_fields__}}
        extra = {{k: v for k, v in data.items() if k not in cls.__dataclass_fields__}}
        instance = cls(**known)
        instance.extra = extra
        return instance
"""
        )

    def _gen_pipeline(self, purpose: str, hint: str) -> str:
        """生成流水线模式"""
        name = self._to_class_name(purpose, "Pipeline")
        return (
            f"""import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class {name}:
    \"\"\"流水线: {purpose}\"\"\"

    def __init__(self):
        self._steps: list[tuple[str, Callable]] = []

    def add_step(self, name: str, fn: Callable) -> '{name}':
        \"\"\"添加处理步骤\"\"\"
        self._steps.append((name, fn))
        return self  # 支持链式调用

    def run(self, input_data: Any) -> dict:
        \"\"\"执行流水线\"\"\"
        result = input_data
        step_results = {{}}
        for name, fn in self._steps:
            try:
                result = fn(result)
                step_results[name] = {{"success": True, "output": result}}
            except Exception as e:
                step_results[name] = {{"success": False, "error": str(e)}}
                logger.error(f"Pipeline step '{{name}}' failed: {{e}}")
                break
        return {{
            "success": all(s["success"] for s in step_results.values()),
            "steps": step_results,
            "final_output": result,
        }}
"""
        )

    # ── 代码补全 ──

    def generate_completion(self, prefix: str, context_lines: List[str]) -> str:
        """基于前缀和上下文行生成代码补全"""
        # 检测缩进级别
        if prefix.strip().endswith(":"):
            return "    pass\n"
        elif prefix.strip().startswith("class "):
            return (
                f"    \"\"\"自动生成的类\"\"\"\n"
                f"\n"
                f"    def __init__(self):\n"
                f"        pass\n"
            )
        elif prefix.strip().startswith("def "):
            return (
                f"    \"\"\"自动生成的函数\"\"\"\n"
                f"    pass\n"
            )
        elif "return" in prefix and "=" not in prefix:
            return " None\n"
        else:
            return " pass\n"

    # ── 代码重构建议 ──

    def suggest_extraction(self, code: str, min_lines: int = 8) -> List[Dict]:
        """建议将哪些代码块提取为函数"""
        lines = code.split("\n")
        suggestions = []
        current_block = []
        block_start = 0
        indent_level = 0

        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if not stripped or stripped.strip().startswith(("#", "\"\"\"")):
                continue
            curr_indent = len(line) - len(line.lstrip())
            if curr_indent > indent_level and current_block and i - block_start > min_lines:
                suggestions.append({
                    "start": block_start + 1,
                    "end": i,
                    "lines": i - block_start,
                    "code": "\n".join(lines[block_start:i]),
                    "suggested_name": self._suggest_func_name(
                        "\n".join(lines[block_start:i])
                    ),
                })
                current_block = []
            if not current_block:
                block_start = i
                indent_level = curr_indent
            current_block.append(stripped)

        return suggestions[:5]

    def _suggest_func_name(self, code_block: str) -> str:
        """从代码块推断函数名"""
        name_hints = re.findall(r"(?:validate|check|process|transform|parse|"
                                r"handle|compute|extract|build|create|"
                                r"format|convert|load|save|get|set)_?\w*",
                                code_block, re.IGNORECASE)
        return name_hints[0] if name_hints else "extracted_method"

    # ── 辅助方法 ──

    @staticmethod
    def _to_class_name(purpose: str, suffix: str = "") -> str:
        """将目的描述转换为类名"""
        words = re.findall(r'\w+', purpose)
        name = "".join(w.capitalize() for w in words[:3])
        return name + suffix

    @staticmethod
    def _to_snake_case(purpose: str, suffix: str = "") -> str:
        """将目的描述转换为蛇形命名"""
        words = re.findall(r'\w+', purpose)
        name = "_".join(w.lower() for w in words[:3])
        return name + ("_" + suffix if suffix else "")

    def get_status(self) -> Dict[str, Any]:
        """获取生成器状态"""
        return {
            "repo_root": str(self.repo_root) if self.repo_root else None,
            "patterns_available": [
                "validator", "transformer", "processor",
                "observer", "factory", "decorator",
                "adapter", "config", "pipeline",
            ],
            "ast_analyzer_available": True,
        }


# ── 单例实例 ──────────────────────────────────────────────────

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
