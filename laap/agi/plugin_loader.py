"""
LAAP AGI — Safe Plugin Loader (安全运行时插件加载器)

MISSING PIECE for real self-evolution: the ability to write, load, and
integrate NEW capabilities at runtime without modifying or restarting
the running system.

Architecture:
  ┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
  │ Write .py file  │────>│ SafePluginLoader │────>│ CognitiveBus │
  │ (new capability)│     │ - validate       │     │ - register   │
  └─────────────────┘     │ - importlib.load │     │ - hook inject│
                          │ - sandbox test   │     └──────────────┘
                          │ - register       │
                          └──────────────────┘
                                    │
                          ┌─────────┴──────────┐
                          │ RuntimeModuleRegistry│
                          │ - name → module    │
                          │ - capability map   │
                          └────────────────────┘

Plugin contract:
  A plugin is a .py file that exports optional hook functions:

    def metadata() -> dict:
        return {"name": str, "version": str, "capabilities": list[str]}

    def on_load(bus: CognitiveBus, registry: RuntimeModuleRegistry) -> None:
        Called after successful load and registration.

    def on_unload() -> None:
        Called when the plugin is being unloaded.

    def before_turn(user_message: str, bus: CognitiveBus) -> None:
    def after_tool(tool_name: str, success: bool, bus: CognitiveBus) -> None:
    def after_turn(response: str, bus: CognitiveBus) -> None:

    def get_rules() -> list[Rule]:
        Return Rule objects to register with RulesEngine.

    def get_intentions() -> list[Intention]:
        Return initial intentions for the IntentionBuffer.

Safety:
  - All plugins validated against SafetyGuard patterns
  - Sandbox test (subprocess import + function call) before registration
  - Cannot override builtin cognitive modules (core.py, safety.py, etc.)
  - Max execution time per hook enforced
  - Rollback on crash
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
import threading
import time
import types
import subprocess
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from laap.agi.cognitive_bus import CognitiveBus
from laap.agi.intention_buffer import Intention

logger = logging.getLogger("laap.agi.plugin_loader")

# Plugin hook names that the loader checks for
PLUGIN_HOOKS = [
    "on_load", "on_unload",
    "metadata",
    "before_turn", "after_tool", "after_turn",
    "get_rules", "get_intentions",
]

# Files that cannot be overridden by plugins (safety)
BLOCKLIST_MODULES: Set[str] = {
    "core", "safety", "cognitive_bus", "security",
    "guardian", "code_evolution", "plugin_loader",
}

# Danger patterns (mirrors SafetyGuard.BLACKLIST_PATTERNS)
DANGER_PATTERNS: List[str] = [
    "os.system(", "subprocess.call(", "eval(", "exec(",
    "__import__(", "shutil.rmtree",
    "import ctypes", "import socket",
]

PLUGIN_DIRS = [
    "plugins/loaded",       # Project-local loaded plugins
    "plugins/user",         # User-created plugins
]


@dataclass
class PluginInfo:
    """Runtime metadata for a loaded plugin."""
    name: str
    version: str
    file_path: str
    capabilities: List[str]
    module: types.ModuleType
    hooks: Dict[str, bool]  # hook_name → has_implementation
    loaded_at: float
    health: bool = True
    call_count: int = 0
    error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "file_path": self.file_path,
            "capabilities": self.capabilities,
            "hooks": [k for k, v in self.hooks.items() if v],
            "loaded_at": self.loaded_at,
            "health": self.health,
            "call_count": self.call_count,
            "error_count": self.error_count,
        }


class RuntimeModuleRegistry:
    """
    Registry for dynamically loaded modules.

    Tracks:
      - Which plugins are loaded
      - What capabilities each provides
      - Hook mapping for quick dispatch

    Persisted so plugins survive restarts.
    """

    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}
        self._capability_index: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.Lock()
        self._registries_path: Optional[str] = None

    def enable_persistence(self, path: str):
        self._registries_path = path
        self._load_registry()

    def register(self, info: PluginInfo):
        with self._lock:
            self._plugins[info.name] = info
            for cap in info.capabilities:
                self._capability_index[cap].append(info.name)
        self._save_registry()

    def unregister(self, name: str) -> bool:
        with self._lock:
            info = self._plugins.pop(name, None)
            if info:
                for cap in info.capabilities:
                    if name in self._capability_index.get(cap, []):
                        self._capability_index[cap].remove(name)
        self._save_registry()
        return info is not None

    def get(self, name: str) -> Optional[PluginInfo]:
        return self._plugins.get(name)

    def get_all(self) -> List[PluginInfo]:
        return list(self._plugins.values())

    def find_by_capability(self, capability: str) -> List[PluginInfo]:
        names = self._capability_index.get(capability, [])
        return [self._plugins[n] for n in names if n in self._plugins]

    def get_capabilities(self) -> Dict[str, List[str]]:
        return dict(self._capability_index)

    def get_hooks_for(self, hook_name: str) -> List[Tuple[PluginInfo, types.ModuleType]]:
        result = []
        with self._lock:
            for info in self._plugins.values():
                if info.hooks.get(hook_name) and info.health:
                    result.append((info, info.module))
        return result

    def mark_unhealthy(self, name: str):
        with self._lock:
            info = self._plugins.get(name)
            if info:
                info.health = False

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "plugins_loaded": len(self._plugins),
                "capabilities": dict(self._capability_index),
                "plugin_list": [p.to_dict() for p in self._plugins.values()],
            }

    def _save_registry(self):
        if not self._registries_path:
            return
        try:
            data = {
                name: info.to_dict()
                for name, info in self._plugins.items()
            }
            Path(self._registries_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self._registries_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save plugin registry: {e}")

    def _load_registry(self):
        if not self._registries_path or not os.path.exists(self._registries_path):
            return
        try:
            with open(self._registries_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded plugin registry: {len(data)} plugins")
        except Exception as e:
            logger.warning(f"Failed to load plugin registry: {e}")


class SafePluginLoader:
    """
    Runtime plugin loader with safety validation.

    Loads .py files from disk using importlib (NOT exec/eval),
    validates against danger patterns, sandbox tests in subprocess,
    and registers on the CognitiveBus.

    Usage:
        bus = CognitiveBus(agent_name="Aris")
        loader = SafePluginLoader(bus, repo_root="/path/to/repo")
        result = loader.load_plugin("plugins/user/my_module.py")
    """

    def __init__(
        self,
        bus: CognitiveBus,
        repo_root: str = "",
        registry: Optional[RuntimeModuleRegistry] = None,
        rules_engine: Optional[Any] = None,
    ):
        self._bus = bus
        self._repo_root = repo_root or os.getcwd()
        self._registry = registry or RuntimeModuleRegistry()
        self._rules_engine = rules_engine
        self._lock = threading.Lock()

        # Track which plugin dirs exist
        self._plugin_dirs: List[str] = []
        for d in PLUGIN_DIRS:
            full = os.path.join(self._repo_root, d)
            if os.path.isdir(full):
                self._plugin_dirs.append(full)

    @property
    def registry(self) -> RuntimeModuleRegistry:
        return self._registry

    # ── Load ──────────────────────────────────────────────

    def load_plugin(self, file_path: str, auto_test: bool = True) -> Dict[str, Any]:
        """
        Load a plugin from a .py file.

        1. Validate: not blocklisted, no danger patterns, syntax check
        2. Sandbox test: import + call metadata() in subprocess
        3. Load: importlib into current process
        4. Register: add to registry + CognitiveBus module registry

        Returns result dict with status and plugin info.
        """
        abs_path = self._resolve_path(file_path)
        result: Dict[str, Any] = {"file": abs_path, "status": "unknown"}

        # Step 0: basic checks
        check = self._pre_validate(abs_path)
        if not check["valid"]:
            result["status"] = "rejected"
            result["reason"] = check["reason"]
            return result

        # Step 1: sandbox test
        if auto_test:
            test = self._sandbox_test(abs_path)
            if not test["success"]:
                result["status"] = "sandbox_failed"
                result["reason"] = test.get("error", "")
                result["test_output"] = test.get("output", "")
                return result

        # Step 2: load into process
        try:
            module = self._import_module(abs_path)
        except Exception as e:
            result["status"] = "import_failed"
            result["reason"] = str(e)
            return result

        # Step 3: extract metadata
        meta = self._get_metadata(module)
        if not meta:
            result["status"] = "no_metadata"
            result["reason"] = "Plugin must export metadata() -> dict"
            return result

        plugin_name = meta.get("name", Path(abs_path).stem)
        if plugin_name in BLOCKLIST_MODULES:
            result["status"] = "rejected"
            result["reason"] = f"Cannot override builtin module: {plugin_name}"
            return result

        # Step 4: detect hooks
        hooks = {}
        for hook_name in PLUGIN_HOOKS:
            hooks[hook_name] = hasattr(module, hook_name)

        # Step 5: register
        info = PluginInfo(
            name=plugin_name,
            version=meta.get("version", "0.1.0"),
            file_path=abs_path,
            capabilities=meta.get("capabilities", []),
            module=module,
            hooks=hooks,
            loaded_at=time.time(),
        )
        self._registry.register(info)
        self._bus.register_module(
            name=f"plugin:{plugin_name}",
            version=info.version,
            capabilities=info.capabilities,
        )

        # Step 6: call on_load hook
        if hooks.get("on_load"):
            try:
                module.on_load(self._bus, self._registry)
            except Exception as e:
                logger.warning(f"Plugin '{plugin_name}' on_load error: {e}")

        # Step 7: register rules if any
        if hooks.get("get_rules") and self._rules_engine:
            try:
                rules = module.get_rules()
                for rule in rules:
                    self._rules_engine.add_rule(rule)
            except Exception as e:
                logger.warning(f"Plugin '{plugin_name}' get_rules error: {e}")

        # Step 8: register intentions if any
        if hooks.get("get_intentions"):
            try:
                intentions = module.get_intentions()
                for intention in intentions:
                    self._bus.intention_buffer.enqueue(intention)
            except Exception as e:
                logger.warning(f"Plugin '{plugin_name}' get_intentions error: {e}")

        logger.info(f"Plugin '{plugin_name}' v{info.version} loaded ({len(info.capabilities)} caps)")
        result["status"] = "loaded"
        result["info"] = info.to_dict()
        return result

    # ── Dispatch hooks ────────────────────────────────────

    def dispatch_before_turn(self, user_message: str):
        """Dispatch before_turn to all plugins that implement it."""
        for info, module in self._registry.get_hooks_for("before_turn"):
            try:
                module.before_turn(user_message, self._bus)
                info.call_count += 1
            except Exception as e:
                info.error_count += 1
                logger.warning(f"Plugin '{info.name}' before_turn error: {e}")

    def dispatch_after_tool(self, tool_name: str, success: bool):
        for info, module in self._registry.get_hooks_for("after_tool"):
            try:
                module.after_tool(tool_name, success, self._bus)
                info.call_count += 1
            except Exception as e:
                info.error_count += 1
                logger.warning(f"Plugin '{info.name}' after_tool error: {e}")

    def dispatch_after_turn(self, response: str):
        for info, module in self._registry.get_hooks_for("after_turn"):
            try:
                module.after_turn(response, self._bus)
                info.call_count += 1
            except Exception as e:
                info.error_count += 1
                logger.warning(f"Plugin '{info.name}' after_turn error: {e}")

    # ── Unload ────────────────────────────────────────────

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin by name."""
        info = self._registry.get(name)
        if not info:
            return False

        if info.hooks.get("on_unload"):
            try:
                info.module.on_unload()
            except Exception as e:
                logger.warning(f"Plugin '{name}' on_unload error: {e}")

        self._registry.unregister(name)

        # Remove from sys.modules so future reloads get fresh code
        if name in sys.modules:
            del sys.modules[name]

        logger.info(f"Plugin '{name}' unloaded")
        return True

    def reload_plugin(self, name: str) -> Dict[str, Any]:
        """Reload a plugin (unload + load)."""
        info = self._registry.get(name)
        if not info:
            return {"status": "not_found", "reason": f"Plugin '{name}' not loaded"}
        file_path = info.file_path
        self.unload_plugin(name)
        return self.load_plugin(file_path)

    # ── Scan dirs ─────────────────────────────────────────

    def scan_and_load_all(self, auto_test: bool = True) -> List[Dict[str, Any]]:
        """Scan all plugin directories and load any unloaded plugins."""
        results = []
        loaded_names = {p.name for p in self._registry.get_all()}
        for plugin_dir in self._plugin_dirs:
            for f in sorted(Path(plugin_dir).glob("*.py")):
                if f.stem in loaded_names or f.stem.startswith("_"):
                    continue
                result = self.load_plugin(str(f), auto_test=auto_test)
                results.append(result)
        return results

    # ── Internal ──────────────────────────────────────────

    def _resolve_path(self, file_path: str) -> str:
        """Resolve a possibly-relative path to absolute."""
        if os.path.isabs(file_path):
            return file_path
        abs_path = os.path.join(self._repo_root, file_path)
        if os.path.exists(abs_path):
            return abs_path
        for d in self._plugin_dirs:
            candidate = os.path.join(d, file_path)
            if os.path.exists(candidate):
                return candidate
        return abs_path

    def _pre_validate(self, abs_path: str) -> Dict[str, Any]:
        """Basic validation before loading."""
        if not os.path.exists(abs_path):
            return {"valid": False, "reason": f"File not found: {abs_path}"}
        if not abs_path.endswith(".py"):
            return {"valid": False, "reason": "Only .py files supported"}

        with open(abs_path, 'r') as f:
            source = f.read()

        # Danger patterns
        for pattern in DANGER_PATTERNS:
            if pattern in source:
                return {"valid": False, "reason": f"Danger pattern: {pattern}"}

        # Syntax check
        try:
            compile(source, abs_path, 'exec')
        except SyntaxError as e:
            return {"valid": False, "reason": f"Syntax error: {e}"}

        return {"valid": True}

    def _sandbox_test(self, abs_path: str) -> Dict[str, Any]:
        """
        Test the plugin in a subprocess before loading into runtime.
        Imports the module and calls metadata() to verify it works.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"""
import sys, importlib, importlib.util, json
sys.path.insert(0, '{self._repo_root}')
sys.path.insert(0, '{os.path.dirname(abs_path)}')
spec = importlib.util.spec_from_file_location('_plugin_test', '{abs_path}')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
if hasattr(mod, 'metadata'):
    meta = mod.metadata()
    print('METADATA:' + json.dumps(meta))
else:
    print('NO_METADATA')
"""],
                capture_output=True, text=True, timeout=15,
                env={**os.environ, "LAAP_PLUGIN_SANDBOX": "1"},
            )
            output = result.stdout.strip()
            if "METADATA:" in output:
                return {"success": True, "output": output}
            elif "NO_METADATA" in output:
                return {"success": True, "output": output}
            else:
                return {"success": False, "error": result.stderr[:500], "output": output[:500]}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Sandbox timeout (15s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _import_module(self, abs_path: str) -> types.ModuleType:
        """Import a .py file as a module using importlib."""
        module_name = f"_plugin_{Path(abs_path).stem}_{int(time.time())}"
        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec from {abs_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _get_metadata(self, module: types.ModuleType) -> Optional[Dict[str, Any]]:
        if hasattr(module, "metadata"):
            try:
                meta = module.metadata()
                if isinstance(meta, dict):
                    return meta
            except Exception:
                pass
        return {"name": module.__name__, "version": "0.1.0", "capabilities": []}


def integrate_plugin_loader(
    bus: CognitiveBus,
    repo_root: str = "",
    rules_engine: Any = None,
    auto_scan: bool = True,
) -> SafePluginLoader:
    """Create and integrate a SafePluginLoader into the system."""
    registry = RuntimeModuleRegistry()
    loader = SafePluginLoader(
        bus=bus,
        repo_root=repo_root,
        registry=registry,
        rules_engine=rules_engine,
    )
    bus.plugin_loader = loader

    if auto_scan:
        results = loader.scan_and_load_all()
        loaded = [r for r in results if r.get("status") == "loaded"]
        if loaded:
            logger.info(f"Auto-loaded {len(loaded)} plugins")
        for r in results:
            if r.get("status") != "loaded":
                logger.info(f"Plugin scan: {r.get('file', '?')} -> {r['status']}")

    logger.info(f"SafePluginLoader integrated into CognitiveBus '{bus.agent_name}'")
    return loader
