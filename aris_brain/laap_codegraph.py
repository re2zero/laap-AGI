"""
LAAP CodeGraph - 代码知识图谱(真实版)
======================================
功能:
- 扫描项目 Python 文件,提取类,函数,导入关系
- 构建可查询的知识图谱
- 支持"这个函数被谁调用了","这个类继承自谁"等查询
- 用于进化模块的代码上下文感知
"""
import ast
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger("laap_codegraph")


class CodeEntity:
    """代码实体:文件,类,函数"""
    def __init__(self, name: str, etype: str, meta: dict = None):
        self.name = name
        self.type = etype       # file | class | function | import
        self.meta = meta or {}
        self.relations: List[Tuple[str, str, str]] = []  # (target, rel_type, detail)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "meta": self.meta,
            "relations": [(t, r, d[:50]) for t, r, d in self.relations],
        }


class LAAPCodeGraph:
    """代码知识图谱 - 从项目源码中构建"""

    def __init__(self):
        self._entities: Dict[str, CodeEntity] = {}
        self._built = False
        self._scan_stats: dict = {}
        logger.info("[CodeGraph] initialized")

    def _scan_pyfile(self, root_path: Path, rel_path: str) -> tuple:
        """扫描单个 Python 文件,返回发现的实体数"""
        pyfile = root_path / rel_path
        code = pyfile.read_text(encoding="utf-8", errors="replace")
        file_entity = CodeEntity(rel_path, "file", {"size": len(code), "lines": code.count("\n") + 1})
        self._entities[rel_path] = file_entity
        found_classes, found_funcs, found_imports, errors = 0, 0, 0, 0
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 1, 0, 0, 0, 1
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cname = f"{rel_path}::{node.name}"
                bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                self._entities[cname] = CodeEntity(cname, "class", {"bases": bases, "methods": methods, "file": rel_path, "line": node.lineno})
                file_entity.relations.append((cname, "contains", f"class {node.name}"))
                for b in bases:
                    self._entities[cname].relations.append((f"::{b}", "inherits", f"base {b}"))
                found_classes += 1
            elif isinstance(node, ast.FunctionDef):
                if not any(isinstance(p, ast.ClassDef) for p in ast.walk(tree) if p is not node and isinstance(getattr(p, 'body', None), list) and node in p.body):
                    fname = f"{rel_path}::{node.name}"
                    self._entities[fname] = CodeEntity(fname, "function", {"file": rel_path, "line": node.lineno, "args": len(node.args.args), "decorators": [d.id for d in node.decorator_list if isinstance(d, ast.Name)]})
                    file_entity.relations.append((fname, "contains", f"function {node.name}"))
                    found_funcs += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                items = node.names if isinstance(node, ast.Import) else [alias for alias in node.names]
                for alias in items:
                    imp_name = alias.asname or alias.name
                    module = node.module or "" if isinstance(node, ast.ImportFrom) else ""
                    full = f"{module}.{imp_name}" if module else imp_name
                    key = f"import::{full}"
                    self._entities[key] = CodeEntity(key, "import", {"source": full, "file": rel_path})
                    file_entity.relations.append((key, "imports", full))
                    found_imports += 1
        return 1, found_classes, found_funcs, found_imports, errors

    def build(self, root: str) -> dict:
        """扫描项目目录,构建知识图谱(分发到 _scan_pyfile)"""
        root_path = Path(root)
        files, classes, funcs, imports, errs = 0, 0, 0, 0, 0
        
        for pyfile in sorted(root_path.rglob("*.py")):
            if any(p in str(pyfile) for p in ("__pycache__", ".venv", ".git", "target", "_archive")):
                continue
            rel = str(pyfile.relative_to(root_path))
            f, c, fn, i, e = self._scan_pyfile(root_path, rel)
            files += f; classes += c; funcs += fn; imports += i; errs += e

        self._built = True
        self._scan_stats = {"files": files, "classes": classes, "functions": funcs, "imports": imports, "errors": errs, "entities": len(self._entities)}
        logger.info(f"[CodeGraph] built: {files} files, {classes} classes, {funcs} functions, {imports} imports")
        return self._scan_stats
    def query(self, name: str) -> Optional[dict]:
        """查询实体"""
        entity = self._entities.get(name)
        return entity.to_dict() if entity else None

    def search(self, keyword: str, limit: int = 10) -> List[dict]:
        """搜索实体"""
        results = []
        for name, entity in self._entities.items():
            if keyword.lower() in name.lower():
                results.append(entity.to_dict())
                if len(results) >= limit:
                    break
        return results

    def get_related(self, name: str, rel_type: str = "") -> List[dict]:
        """获取与某实体相关的所有实体"""
        entity = self._entities.get(name)
        if not entity:
            return []
        related = []
        for target, rtype, detail in entity.relations:
            if not rel_type or rtype == rel_type:
                target_entity = self._entities.get(target)
                if target_entity:
                    related.append({"name": target, "type": target_entity.type, "relation": rtype, "detail": detail})
        return related

    def get_stats(self) -> dict:
        return dict(self._scan_stats) if self._built else {"built": False, "entities": len(self._entities)}

    def __len__(self) -> int:
        return len(self._entities)


# 全局实例(惰性构建)
_cg: Optional[LAAPCodeGraph] = None


def get_codegraph(build: bool = True) -> LAAPCodeGraph:
    """获取 CodeGraph 单例(首次调用时自动构建)"""
    global _cg
    if _cg is None:
        _cg = LAAPCodeGraph()
        if build:
            # 自动检测项目根目录
            candidates = [Path.cwd(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]
            for c in candidates:
                if (c / "pyproject.toml").exists() or (c / "setup.py").exists():
                    _cg.build(str(c))
                    break
    return _cg
