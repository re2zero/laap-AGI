"""
Aris SelfModifier - 闭环自我修改引擎
======================================
让 Aris 不仅能诊断自身问题,还能安全地修改自己的代码.

安全链:
  checkpoint -> apply -> verify -> commit | rollback
     ↑          ↑         ↑         ↑
  git stash   补丁写入  跑测试    通过/回滚

用法:
    from aris_brain.self_modifier import SelfModifier
    modifier = SelfModifier()
    modifier.fix_all()  # 自动发现并修复问题
"""

import ast
import hashlib
import json
import logging
import os
import re
import subprocess
import time
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("aris.self_modifier")

# ── 安全检查 ──────────────────────────────────────────────────

SAFETY_BLOCKED_PATTERNS = [
    # 禁止删除文件
    r"os\.remove\(|os\.unlink\(|\.unlink\(|shutil\.rmtree",
    # 禁止执行任意代码
    r"eval\(|exec\(|compile\(|__import__\(|subprocess\.(Popen|call|run)",
    # 禁止修改关键配置
    r"(?i)api_key|password|secret|token|credential",
    # 禁止修改 .env / 密钥/安全文件
    r"\.env|credentials\.json|config\.yaml.*secret",
]

ALLOWED_MODIFICATION_SCOPES = [
    # 只允许修改 aris_brain/*.py 下的文件
    "aris_brain/*.py",
    "aris_brain/psi_semiotics/*.py",
    # 不允许修改 Rust 代码(需要 cargo build)
    # 不允许修改 pyproject.toml,配置文件
]


@dataclass
class PatchSpec:
    """一次代码修改的完整规约"""
    file_path: str               # 相对仓库根目录的路径
    old_string: str              # 被替换的代码段
    new_string: str              # 替换后的代码段
    description: str             # 修改的语义描述
    reason: str = ""             # 为什么要改
    author: str = "Aris SelfModifier"
    severity: str = "refactor"   # refactor | bugfix | perf | docs | feature


@dataclass
class ModificationResult:
    """一次修改的完整记录"""
    spec: PatchSpec
    status: str                   # pending | applied | verified | committed | rolled_back | failed
    checkpoint_hash: str = ""
    verify_log: str = ""
    commit_hash: str = ""
    error: str = ""
    timestamp: float = 0.0


# ── AST 分析器 ────────────────────────────────────────────────


class CodeAnalyzer:
    """代码分析器 - 深度扫描可改进点"""

    @staticmethod
    def _check_unused_imports(tree: ast.AST, code: str, file_path: Path, issues: list):
        """检测未使用的导入"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    if code.count(name) <= 1 and name != name.upper():
                        common = {"os", "sys", "re", "json", "time", "math", "logging", "pathlib", "typing"}
                        if name.split(".")[0] not in common:
                            issues.append({"type": "unused_import", "file": str(file_path), "line": node.lineno, "name": name, "severity": "low", "fixable": True, "suggestion": f"删除未使用的导入: {name}"})

    @staticmethod
    def _check_bare_except(tree: ast.AST, file_path: Path, issues: list):
        """检测空的 except 块"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and node.body[0].value.value == "pass"):
                    issues.append({"type": "bare_except", "file": str(file_path), "line": node.lineno, "severity": "medium", "fixable": True, "suggestion": "给 except 块添加日志或处理逻辑"})

    @staticmethod
    def _check_missing_hints(tree: ast.AST, file_path: Path, issues: list):
        """检测缺少类型注解的函数"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                has_ret = node.returns is not None
                no_type = [a.arg for a in node.args.args if a.arg != "self" and a.annotation is None]
                if no_type or (not has_ret and len(node.body) > 1):
                    missing = []
                    if no_type: missing.append("参数")
                    if not has_ret: missing.append("返回值")
                    issues.append({"type": "missing_type_hints", "file": str(file_path), "line": node.lineno, "name": node.name, "severity": "low", "fixable": True, "suggestion": f"为 {node.name}() 添加{','.join(missing)}类型注解"})

    @staticmethod
    def _check_long_lines(code: str, file_path: Path, lines: list, issues: list):
        """检测过长行"""
        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            if len(stripped) > 120 and not stripped.strip().startswith(("#", '"""')):
                issues.append({"type": "long_line", "file": str(file_path), "line": i, "length": len(stripped), "severity": "low", "fixable": True, "suggestion": f"第 {i} 行 {len(stripped)} 字符,建议换行"})

    @staticmethod
    def _check_todo(tree: ast.AST, code: str, file_path: Path, lines: list, issues: list):
        """检测 TODO/FIXME 标记"""
        for i, line in enumerate(lines, 1):
            if "TODO" in line or "FIXME" in line:
                issues.append({"type": "todo_marker", "file": str(file_path), "line": i, "severity": "info", "fixable": False, "suggestion": line.strip()})

    @staticmethod
    def _check_complexity(tree: ast.AST, file_path: Path, issues: list):
        """检测高圈复杂度函数"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = sum(1 for c in ast.walk(node) if isinstance(c, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.BoolOp)))
                if complexity > 15:
                    issues.append({"type": "high_complexity", "file": str(file_path), "line": node.lineno, "name": node.name, "complexity": complexity, "severity": "medium", "fixable": False, "suggestion": f"函数 {node.name}() 圈复杂度 {complexity} > 15,建议拆分"})

    @staticmethod
    def find_simple_issues(file_path: Path) -> List[Dict[str, Any]]:
        """在单个文件中寻找可自动修复的问题(分发到专用检查器)"""
        try:
            code = file_path.read_text(encoding="utf-8")
        except Exception:
            return []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [{"type": "syntax_error", "file": str(file_path), "severity": "high", "fixable": False}]
        
        lines = code.split("\n")
        issues: List[Dict[str, Any]] = []
        
        CodeAnalyzer._check_unused_imports(tree, code, file_path, issues)
        CodeAnalyzer._check_bare_except(tree, file_path, issues)
        CodeAnalyzer._check_missing_hints(tree, file_path, issues)
        CodeAnalyzer._check_long_lines(code, file_path, lines, issues)
        CodeAnalyzer._check_todo(tree, code, file_path, lines, issues)
        CodeAnalyzer._check_complexity(tree, file_path, issues)
        
        return issues
    @staticmethod
    def find_dry_violations(file_path: Path, min_block_lines: int = 6) -> List[Dict]:
        """寻找重复代码块(DRY 违反)"""
        issues = []
        try:
            code = file_path.read_text(encoding="utf-8")
        except Exception:
            return issues

        lines = [l.rstrip() for l in code.split("\n")]
        # 寻找连续重复的代码行组
        seen_blocks: Dict[str, List[int]] = {}
        i = 0
        while i < len(lines) - min_block_lines + 1:
            block = "\n".join(lines[i:i + min_block_lines])
            # 跳过注释块和空行块
            if not block.strip() or all(l.strip().startswith("#") for l in block.split("\n") if l.strip()):
                i += 1
                continue
            block_hash = hashlib.md5(block.encode()).hexdigest()
            seen_blocks.setdefault(block_hash, []).append(i + 1)  # 1-indexed
            i += 1

        for block_hash, positions in seen_blocks.items():
            if len(positions) >= 2:
                issues.append({
                    "type": "dry_violation",
                    "file": str(file_path),
                    "lines": positions,
                    "severity": "medium",
                    "fixable": True,
                    "suggestion": f"第 {positions[0]} 行与第 {positions[1]} 行附近存在重复代码",
                })
                # 只报告第一组重复
                break

        return issues


# ── 安全修改器 ────────────────────────────────────────────────


class SelfModifier:
    """
    闭环自我修改引擎
    
    安全保证:
    1. 修改前创建 git checkpoint
    2. 修改后自动跑测试
    3. 测试失败自动 rollback
    4. 禁止修改安全敏感文件
    5. 修改记录持久化到 ~/.laap/state/
    """

    SAFE_PATTERNS = {
        "bare_except": "_add_logging_to_except",
        "missing_type_hints": "_add_type_hints",
        "long_line": "_wrap_long_line",
        "dry_violation": "_extract_duplicated_code",
        "unused_import": "_remove_unused_import",
    }

    def __init__(self, repo_root: Optional[str] = None, state_dir: Optional[str] = None):
        self.repo_root = Path(repo_root) if repo_root else self._find_repo_root()
        
        if state_dir:
            self._state_dir = Path(state_dir)
        else:
            try:
                from laap_brain.config import STATE_DIR
                self._state_dir = STATE_DIR
            except ImportError:
                self._state_dir = Path.home() / ".laap" / "state"
        
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._state_dir / "self_modifications.json"
        
        # 历史记录
        self._history: List[ModificationResult] = []
        self._load_history()
        
        logger.info(f"SelfModifier 初始化 (repo={self.repo_root}, state={self._state_dir})")

    # ── 公共接口 ──────────────────────────────────────────

    def scan_all(self) -> List[Dict[str, Any]]:
        """扫描所有可修改的 Python 文件,返回所有可修复问题"""
        all_issues = []
        for pyfile in sorted(self.repo_root.glob("aris_brain/*.py")):
            if pyfile.name.startswith("_"):
                continue
            issues = CodeAnalyzer.find_simple_issues(pyfile)
            issues.extend(CodeAnalyzer.find_dry_violations(pyfile))
            for issue in issues:
                issue["file"] = str(pyfile.relative_to(self.repo_root))
            all_issues.extend(issues)
        return all_issues

    def fix_all(self, dry_run: bool = True) -> List[ModificationResult]:
        """
        自动扫描并修复所有可修复的问题.
        
        Args:
            dry_run: True = 只诊断不修改,False = 实际修改
        
        Returns:
            每次修改的完整记录
        """
        results = []
        issues = self.scan_all()

        if not issues:
            logger.info("[SelfModifier] 扫描完成:未发现可修复问题")
            return results

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
        issues.sort(key=lambda i: severity_order.get(i["severity"], 99))

        logger.info(f"[SelfModifier] 发现 {len(issues)} 个问题 ({sum(1 for i in issues if i.get('fixable'))} 个可修复)")

        for issue in issues:
            if not issue.get("fixable", False):
                continue

            fixer_method = self.SAFE_PATTERNS.get(issue["type"])
            if fixer_method is None:
                continue

            try:
                fixer = getattr(self, fixer_method)
                patch = fixer(issue)
                if patch is None:
                    continue

                if dry_run:
                    result = ModificationResult(
                        spec=patch,
                        status="pending",
                        timestamp=time.time(),
                    )
                    logger.info(f"  [dry-run] 将修复: {patch.description} ({patch.file_path}:{issue.get('line', '?')})")
                else:
                    result = self._safe_apply(patch)

                results.append(result)
                self._history.append(result)
            except Exception as e:
                logger.warning(f"  [SelfModifier] 修复失败 {issue.get('type')}: {e}")

        self._save_history()
        return results

    def fix_file(self, file_path: str, dry_run: bool = True) -> List[ModificationResult]:
        """仅扫描并修复指定文件"""
        full_path = self.repo_root / file_path
        if not full_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return []

        issues = CodeAnalyzer.find_simple_issues(full_path)
        results = []
        for issue in issues:
            if not issue.get("fixable"):
                continue
            fixer_method = self.SAFE_PATTERNS.get(issue["type"])
            if not fixer_method:
                continue
            try:
                patch = getattr(self, fixer_method)(issue)
                if patch is None:
                    continue
                if dry_run:
                    results.append(ModificationResult(spec=patch, status="pending", timestamp=time.time()))
                    logger.info(f"  [dry-run] {patch.description}")
                else:
                    result = self._safe_apply(patch)
                    results.append(result)
                    self._history.append(result)
            except Exception as e:
                logger.warning(f"  {issue['type']} 修复失败: {e}")

        if not dry_run:
            self._save_history()
        return results

    # ── 修复器(每种问题类型对应一个方法) ─────────────────

    def _add_logging_to_except(self, issue: Dict) -> Optional[PatchSpec]:
        """给空的 except 块添加日志"""
        file_path = self.repo_root / issue["file"]
        code = file_path.read_text(encoding="utf-8")
        lines = code.split("\n")
        line_idx = issue["line"] - 1  # 0-indexed

        if line_idx >= len(lines):
            return None

        # 查找 except 行
        line = lines[line_idx]
        if "except" not in line:
            return None

        # 提取异常变量名
        var_match = re.search(r"except\s+(?:\w+\s+as\s+)?(\w+)\s*:", line)
        exc_var = var_match.group(1) if var_match else "e"

        # 在 except 块的第一行插入日志
        # 查找块的第一条语句
        insert_pos = line_idx + 1
        while insert_pos < len(lines) and not lines[insert_pos].strip():
            insert_pos += 1

        indent = " " * (len(line) - len(line.lstrip()) + 4)
        logging_line = f'{indent}logger.warning(f"处理异常: {{{exc_var}}}")\n'

        old = lines[insert_pos] if insert_pos < len(lines) else ""
        if not old.strip() or old.strip() == "pass":
            old_line = lines[insert_pos]
            new_content = f"{logging_line}{old_line}"
        else:
            new_content = f"{logging_line}{old}"

        # 确保 logging 已导入
        has_logging_import = any(l.strip().startswith("import logging") or
                                  "from logging" in l for l in lines)
        import_fix = ""
        if not has_logging_import:
            # 在文件顶部添加导入
            import_fix = 'import logging\n\n'
            new_content = import_fix + "\n".join(lines)
            old_content = "\n".join(lines)
        else:
            old_content = lines[line_idx]
            new_content = f"{line}\n{logging_line}" if old.strip() == "pass" else \
                          old.replace(old, f"{line}\n{logging_line}{old}")

        # 简化:直接替换整个 except 块
        # 找到从 except: 到下一个不在 except 缩进的行的范围
        start = line_idx
        end = start + 1
        base_indent = len(line) - len(line.lstrip())
        while end < len(lines):
            stripped = lines[end].strip()
            if not stripped:
                end += 1
                continue
            curr_indent = len(lines[end]) - len(lines[end].lstrip())
            if curr_indent <= base_indent and stripped not in ("", "pass"):
                break
            end += 1

        except_block = "\n".join(lines[start:end])
        new_block = f"{line}\n{logging_line}"
        # 如果没有 pass,加上 pass
        if "pass" not in except_block:
            new_block += f"{indent}pass\n"

        return PatchSpec(
            file_path=str(issue["file"]),
            old_string=except_block,
            new_string=new_block.rstrip("\n"),
            description=f"给 {issue['file']}:{issue['line']} 的 except 块添加日志",
            reason=issue.get("suggestion", ""),
            severity="refactor",
        )

    def _wrap_long_line(self, issue: Dict) -> Optional[PatchSpec]:
        """将过长的行换行(仅在安全的位置)"""
        file_path = self.repo_root / issue["file"]
        code = file_path.read_text(encoding="utf-8")
        lines = code.split("\n")
        idx = issue["line"] - 1
        if idx >= len(lines):
            return None

        line = lines[idx]
        stripped = line.rstrip()

        # 只在字符串连接处或二元运算符处换行
        # 如果行里有 " + " 或 " or " 或 " and ",在第一个之后换行
        for op in [" + ", " or ", " and ", " | ", " || ", " && "]:
            pos = stripped.find(op)
            if pos > 0 and pos < len(stripped) - 3:
                indent = " " * (len(line) - len(line.lstrip()) + 8)
                new_line = (stripped[:pos + len(op)] + "\n" +
                           indent + stripped[pos + len(op):].lstrip())
                return PatchSpec(
                    file_path=str(issue["file"]),
                    old_string=line.rstrip(),
                    new_string=new_line.rstrip(),
                    description=f"换行第 {issue['line']} 行({issue['length']} 字符)",
                    reason=issue.get("suggestion", ""),
                    severity="refactor",
                )

        return None

    # ── 修复器: 删除未使用的导入 ─────────────────────────

    def _remove_unused_import(self, issue: Dict) -> Optional[PatchSpec]:
        """删除未使用的导入语句"""
        file_path = self.repo_root / issue["file"]
        code = file_path.read_text(encoding="utf-8")
        lines = code.split("\n")
        line_idx = issue["line"] - 1
        if line_idx >= len(lines):
            return None

        line = lines[line_idx]
        name = issue.get("name", "")
        if not name:
            return None

        # 检查 name 在代码中的出现次数
        # 减去 import 语句本身的一次
        occurrences = code.count(name)
        if occurrences > 1:
            return None  # 实际上还在用

        # 处理不同导入格式
        old_line = line.rstrip()

        # 单行 import X
        if line.strip().startswith("import ") and "," not in line:
            new_lines = [l for i, l in enumerate(lines) if i != line_idx]
            new_code = "\n".join(new_lines)
            return PatchSpec(
                file_path=str(issue["file"]),
                old_string=code,
                new_string=new_code,
                description=f"删除未使用的导入: {name} ({issue['file']}:{issue['line']})",
                reason=issue.get("suggestion", ""),
                severity="refactor",
            )

        # from X import Y
        if line.strip().startswith("from "):
            # 检查是否同一行有多个导入
            import_match = re.match(r"(from\s+\S+\s+import\s+)(.*)", line.strip())
            if import_match:
                prefix = import_match.group(1)
                imports_str = import_match.group(2)
                # 检查是否有括号跨行
                if "(" in line:
                    return None  # 跨行导入暂不处理
                imported_items = [x.strip().strip(",") for x in imports_str.split(",")]
                imported_items = [x for x in imported_items if x and x != "\\"]
                if len(imported_items) > 1:
                    # 多个导入,只移除这一个
                    remaining = [x for x in imported_items if x != name]
                    if remaining:
                        new_line = prefix + ", ".join(remaining)
                        return PatchSpec(
                            file_path=str(issue["file"]),
                            old_string=old_line,
                            new_string=new_line,
                            description=f"从导入中移除未用的 {name}",
                            reason=issue.get("suggestion", ""),
                            severity="refactor",
                        )
                # 唯一导入,整行删除
                new_lines = [l for i, l in enumerate(lines) if i != line_idx]
                new_code = "\n".join(new_lines)
                return PatchSpec(
                    file_path=str(issue["file"]),
                    old_string=code,
                    new_string=new_code,
                    description=f"删除未使用的导入: {name}",
                    reason=issue.get("suggestion", ""),
                    severity="refactor",
                )

        return None

    # ── 修复器: 添加类型注解(基本版本) ──────────────────

    @staticmethod
    def _infer_type_from_default(default_node: ast.AST) -> str:
        """从 AST 默认值节点推断类型"""
        if isinstance(default_node, ast.Constant):
            v = default_node.value
            if isinstance(v, str): return "str"
            elif isinstance(v, bool): return "bool"
            elif isinstance(v, int): return "int"
            elif isinstance(v, float): return "float"
            elif v is None: return "None"
        elif isinstance(default_node, ast.List): return "list"
        elif isinstance(default_node, ast.Dict): return "dict"
        return "Any"

    @staticmethod
    def _infer_return_type(func_node: ast.FunctionDef) -> str:
        """从函数体的 return 语句推断返回值类型"""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value is not None:
                if isinstance(node.value, ast.Constant):
                    v = node.value.value
                    if isinstance(v, str): return "str"
                    elif isinstance(v, bool): return "bool"
                    elif isinstance(v, int): return "int"
                    elif isinstance(v, float): return "float"
                    elif v is None: return "None"
                elif isinstance(node.value, ast.List): return "list"
                elif isinstance(node.value, ast.Dict): return "dict"
                elif isinstance(node.value, ast.Name): return node.value.id
                break
        return "None"

    def _add_type_hints(self, issue: Dict) -> Optional[PatchSpec]:
        """为函数添加基本类型注解(从默认值推断)"""
        file_path = self.repo_root / issue["file"]
        code = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        func_name = issue.get("name", "")
        target_func = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func_name), None)
        if not target_func:
            return None

        new_params = []
        for arg in target_func.args.args:
            if arg.arg == "self":
                new_params.append("self")
                continue
            if arg.annotation:
                new_params.append(arg.arg)
                continue
            inferred = "Any"
            for i, a in enumerate(target_func.args.args):
                if a is arg and i >= len(target_func.args.args) - len(target_func.args.defaults):
                    idx = i - (len(target_func.args.args) - len(target_func.args.defaults))
                    if idx < len(target_func.args.defaults):
                        inferred = self._infer_type_from_default(target_func.args.defaults[idx])
            new_params.append(f"{arg.arg}: {inferred}")

        if new_params == [a.arg for a in target_func.args.args]:
            return None

        return_type = self._infer_return_type(target_func)
        old_def_line = code.split("\n")[target_func.lineno - 1]
        new_def_line = f"def {func_name}({', '.join(new_params)}) -> {return_type}:"
        if old_def_line.strip().endswith(":"):
            return PatchSpec(
                file_path=str(issue["file"]),
                old_string=old_def_line.rstrip(),
                new_string=new_def_line,
                description=f"为 {func_name}() 添加类型注解 -> {return_type}",
                reason=issue.get("suggestion", ""),
                severity="refactor",
            )
        return None
    # ── 修复器: 提取重复代码(安全版本) ──────────────────

    def _extract_duplicated_code(self, issue: Dict) -> Optional[PatchSpec]:
        """为重复代码块生成提取建议(只报告,不实际提取)"""
        # 重复代码提取是最复杂的操作--需要创建新函数,替换两个位置
        # 当前版本只记录到历史,标记为可修复但不自动执行
        # 未来版本可以基于 AST 精确提取
        logger.info(f"[SelfModifier] DRY 违反检测到但暂不自动提取: {issue.get('suggestion', '')}")
        return None

    def _safe_apply(self, patch: PatchSpec) -> ModificationResult:
        """
        安全的修改管线:
        1. git stash checkpoint
        2. 应用修改
        3. 跑测试
        4. 测试通过 -> commit, 失败 -> rollback
        """
        result = ModificationResult(spec=patch, timestamp=time.time())

        # ── 安全检查 ──
        check_ok, check_msg = self._safety_check(patch)
        if not check_ok:
            result.status = "failed"
            result.error = check_msg
            logger.warning(f"[SelfModifier] 安全检查未通过: {check_msg}")
            return result

        # ── 步骤 1: checkpoint ──
        checkpoint = self._checkpoint(patch.description)
        result.checkpoint_hash = checkpoint
        if not checkpoint:
            result.status = "failed"
            result.error = "无法创建 git checkpoint"
            return result

        # ── 步骤 2: 应用修改 ──
        try:
            file_path = self.repo_root / patch.file_path
            code = file_path.read_text(encoding="utf-8")
            if patch.old_string not in code:
                result.status = "failed"
                result.error = "old_string 在文件中未找到"
                logger.warning(f"[SelfModifier] 补丁不匹配: {patch.file_path}")
                logger.debug(f"  期望:\n{patch.old_string[:200]}")
                return result

            new_code = code.replace(patch.old_string, patch.new_string, 1)
            file_path.write_text(new_code, encoding="utf-8")
            logger.info(f"[SelfModifier] ✓ 已修改 {patch.file_path}")
        except Exception as e:
            self._rollback(checkpoint)
            result.status = "rolled_back"
            result.error = f"写入失败: {e}"
            return result

        # ── 步骤 3: 验证 ──
        verify_ok, verify_log = self._verify()
        result.verify_log = verify_log
        if not verify_ok:
            self._rollback(checkpoint)
            result.status = "rolled_back"
            result.error = "测试未通过"
            logger.warning(f"[SelfModifier] 验证失败,已回滚: {patch.description}")
            return result

        # ── 步骤 4: 提交 ──
        commit_hash = self._commit(patch)
        result.commit_hash = commit_hash
        result.status = "committed"
        logger.info(f"[SelfModifier] 🎉 已提交: {patch.description} ({commit_hash[:8]})")

        self._save_history()
        return result

    # ── 安全机制 ──────────────────────────────────────────

    def _safety_check(self, patch: PatchSpec) -> Tuple[bool, str]:
        """安全检查:禁止修改敏感文件或执行危险操作"""
        file_path = patch.file_path.replace("\\", "/")

        # 不修改 .git 下的文件
        if ".git" in file_path.split("/"):
            return False, "禁止修改 .git 目录下的文件"

        # 不修改配置文件
        config_files = {"pyproject.toml", "Cargo.toml", ".env", ".gitignore",
                        "Makefile", "Dockerfile", "docker-compose.yml",
                        "setup.py", "setup.cfg"}
        if Path(file_path).name in config_files:
            return False, f"禁止修改配置文件: {file_path}"

        # 只修改 aris_brain 下的文件
        if not file_path.startswith("aris_brain/"):
            return False, f"超出修改范围: {file_path}"

        # 检查 new_string 是否包含危险模式
        for pattern in SAFETY_BLOCKED_PATTERNS:
            if re.search(pattern, patch.new_string):
                return False, f"检测到危险操作: {pattern}"

        return True, "ok"

    def _checkpoint(self, description: str) -> str:
        """创建 git stash checkpoint"""
        try:
            result = subprocess.run(
                ["git", "stash", "create"],
                capture_output=True, text=True, cwd=self.repo_root, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                hash_val = result.stdout.strip()
                # 用 stash push 保存工作区
                subprocess.run(
                    ["git", "stash", "push", "-m", f"SelfModifier: {description[:60]}"],
                    capture_output=True, cwd=self.repo_root, timeout=10,
                )
                return hash_val
            return ""
        except Exception as e:
            logger.warning(f"[SelfModifier] checkpoint 失败: {e}")
            return ""

    def _rollback(self, checkpoint_hash: str):
        """从 checkpoint 恢复"""
        try:
            subprocess.run(
                ["git", "stash", "pop"],
                capture_output=True, cwd=self.repo_root, timeout=10,
            )
            logger.info(f"[SelfModifier] ✓ 回滚到 checkpoint {checkpoint_hash[:8]}")
        except Exception as e:
            logger.warning(f"[SelfModifier] 回滚失败: {e}")

    def _verify(self) -> Tuple[bool, str]:
        """运行测试验证修改的正确性"""
        log_lines = []
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-x", "--tb=line"],
                capture_output=True, text=True,
                cwd=self.repo_root, timeout=60,
            )
            log_lines.append(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            if result.returncode == 0:
                log_lines.append("pytest: 通过")
                return True, "\n".join(log_lines)
            else:
                log_lines.append(f"pytest: 失败 (exit={result.returncode})")
                return False, "\n".join(log_lines)
        except subprocess.TimeoutExpired:
            log_lines.append("pytest: 超时")
            return False, "\n".join(log_lines)
        except Exception as e:
            log_lines.append(f"pytest 错误: {e}")
            return False, "\n".join(log_lines)

    def _commit(self, patch: PatchSpec) -> str:
        """提交修改"""
        try:
            # stage
            subprocess.run(
                ["git", "add", patch.file_path],
                capture_output=True, cwd=self.repo_root, timeout=10,
            )
            # commit
            result = subprocess.run(
                ["git", "commit", "-m", f"self-modify: {patch.description[:72]}\n\n{patch.reason or patch.description}"],
                capture_output=True, text=True, cwd=self.repo_root, timeout=10,
            )
            if result.returncode == 0:
                # 提取 hash
                match = re.search(r"\[.*?\]\s*([a-f0-9]{7,})", result.stdout)
                if match:
                    return match.group(1)
            return ""
        except Exception as e:
            logger.warning(f"[SelfModifier] commit 失败: {e}")
            return ""

    # ── 状态查询 ──────────────────────────────────────────

    def get_history(self) -> List[Dict]:
        """获取修改历史"""
        return [
            {
                "status": m.status,
                "description": m.spec.description,
                "file": m.spec.file_path,
                "severity": m.spec.severity,
                "timestamp": m.timestamp,
                "commit": m.commit_hash[:8] if m.commit_hash else "",
                "error": m.error,
            }
            for m in self._history
        ]

    def get_summary(self) -> Dict[str, Any]:
        """获取总结报告"""
        history = self.get_history()
        return {
            "total_scans": len(history),
            "applied": sum(1 for h in history if h["status"] == "applied"),
            "committed": sum(1 for h in history if h["status"] == "committed"),
            "rolled_back": sum(1 for h in history if h["status"] == "rolled_back"),
            "failed": sum(1 for h in history if h["status"] == "failed"),
            "pending": sum(1 for h in history if h["status"] == "pending"),
            "recent": history[-5:] if history else [],
        }

    # ── 内部 ──

    def _find_repo_root(self) -> Path:
        for marker in ["pyproject.toml", ".git"]:
            p = Path.cwd()
            for _ in range(4):
                if (p / marker).exists():
                    return p
                p = p.parent
        return Path.cwd()

    def _load_history(self):
        try:
            if self._log_path.exists():
                data = json.loads(self._log_path.read_text(encoding="utf-8"))
                for item in data:
                    spec = PatchSpec(**item["spec"])
                    mr = ModificationResult(
                        spec=spec,
                        status=item.get("status", "pending"),
                        checkpoint_hash=item.get("checkpoint_hash", ""),
                        verify_log=item.get("verify_log", ""),
                        commit_hash=item.get("commit_hash", ""),
                        error=item.get("error", ""),
                        timestamp=item.get("timestamp", 0.0),
                    )
                    self._history.append(mr)
        except Exception:
            pass

    def _save_history(self):
        try:
            data = [{
                "spec": {
                    "file_path": m.spec.file_path,
                    "old_string": m.spec.old_string[:100],
                    "new_string": m.spec.new_string[:100],
                    "description": m.spec.description,
                    "reason": m.spec.reason,
                    "severity": m.spec.severity,
                },
                "status": m.status,
                "checkpoint_hash": m.checkpoint_hash,
                "verify_log": m.verify_log[-200:],
                "commit_hash": m.commit_hash,
                "error": m.error,
                "timestamp": m.timestamp,
            } for m in self._history[-50:]]
            self._log_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[SelfModifier] 历史保存失败: {e}")


# ── 全局单例 ──────────────────────────────────────────────────

_modifier: Optional[SelfModifier] = None


def get_self_modifier(repo_root: Optional[str] = None) -> SelfModifier:
    global _modifier
    if _modifier is None:
        _modifier = SelfModifier(repo_root)
    return _modifier
