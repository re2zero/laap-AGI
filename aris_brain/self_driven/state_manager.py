"""StateManager — 自驱动引擎状态持久化
======================================
线程安全的 JSON 文件读写，每个组件独立文件避免锁竞争。
所有组件通过此管理器访问持久化状态。

用法:
    mgr = StateManager()
    data = mgr.load_core_identity()
    data["cycle_count"] += 1
    mgr.save_core_identity(data)
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aris.self_driven.state")


class StateManager:
    """统一管理所有 self_driven 组件的持久化。线程安全。"""

    STATE_DIR = Path.home() / ".laap" / "state" / "self_driven"

    def __init__(self, state_dir: Optional[str] = None):
        self._lock = threading.Lock()
        self._dir = Path(state_dir) if state_dir else self.STATE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = {}
        self._dirty = False
        logger.info(f"[StateManager] 目录: {self._dir}")

    # ── Core Identity ──────────────────────────────────────────

    def load_core_identity(self) -> Dict[str, Any]:
        return self._read("core_identity.json")

    def save_core_identity(self, data: Dict[str, Any]):
        self._write("core_identity.json", data)

    # ── Curiosity Queue ────────────────────────────────────────

    def load_queue(self) -> Dict[str, Any]:
        return self._read("curiosity_queue.json")

    def save_queue(self, data: Dict[str, Any]):
        self._write("curiosity_queue.json", data)

    # ── Exploration Log ────────────────────────────────────────

    def load_exploration_log(self) -> List[Dict[str, Any]]:
        return self._read("exploration_log.json")

    def append_exploration(self, result: Dict[str, Any]):
        log = self.load_exploration_log()
        log.append(result)
        # 最多保留 200 条
        if len(log) > 200:
            log[:] = log[-200:]
        self._write("exploration_log.json", log)

    # ── Evolution Proposals ────────────────────────────────────

    def load_proposals(self) -> Dict[str, Any]:
        return self._read("evolution_proposals.json")

    def save_proposals(self, data: Dict[str, Any]):
        self._write("evolution_proposals.json", data)

    # ── Evolution History ──────────────────────────────────────

    def load_evolution_history(self) -> List[Dict[str, Any]]:
        return self._read("evolution_history.json")

    def append_evolution(self, result: Dict[str, Any]):
        hist = self.load_evolution_history()
        hist.append(result)
        if len(hist) > 100:
            hist[:] = hist[-100:]
        self._write("evolution_history.json", hist)

    # ── Meta Learner ───────────────────────────────────────────

    def load_meta_state(self) -> Dict[str, Any]:
        return self._read("meta_learner_state.json")

    def save_meta_state(self, data: Dict[str, Any]):
        self._write("meta_learner_state.json", data)

    # ── 通用读写 ───────────────────────────────────────────────

    def _path(self, filename: str) -> Path:
        return self._dir / filename

    def _read(self, filename: str) -> Any:
        """线程安全地读取 JSON 文件。不存在则返回类型默认值。"""
        path = self._path(filename)
        with self._lock:
            try:
                if path.exists():
                    text = path.read_text(encoding="utf-8")
                    if text.strip():
                        data = json.loads(text)
                        self._cache[filename] = data
                        return data
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[StateManager] 读取失败 {filename}: {e}")
            return self._default_for(filename)

    def _write(self, filename: str, data: Any):
        """线程安全地写入 JSON 文件。原子写入。"""
        path = self._path(filename)
        tmp = path.with_suffix(".tmp")
        with self._lock:
            try:
                tmp.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                tmp.replace(path)
                self._cache[filename] = data
                logger.debug(f"[StateManager] 已保存 {filename}")
            except OSError as e:
                logger.warning(f"[StateManager] 写入失败 {filename}: {e}")

    def _default_for(self, filename: str) -> Any:
        """返回每个文件的类型默认值"""
        defaults = {
            "core_identity.json": {},
            "curiosity_queue.json": {"questions": [], "curiosity_params": {}},
            "exploration_log.json": [],
            "evolution_proposals.json": {"proposals": [], "next_id": 1},
            "evolution_history.json": [],
            "meta_learner_state.json": {
                "strategy_stats": {},
                "params_history": [],
                "efficiency_metrics": {},
            },
        }
        return defaults.get(filename, {})
