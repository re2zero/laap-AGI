"""TaskSupervisor — 超长任务监督"""
import logging, time, json, threading
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger("task_supervisor")

class TaskStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskSource(Enum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"

class TaskSupervisor:
    def __init__(self, checkpoint_dir: str = "./checkpoints"):
        self._tasks: Dict[str, dict] = {}
        self._checkpoint_dir = checkpoint_dir
        logger.info(f"[TaskSupervisor] initialized (checkpoint_dir={checkpoint_dir})")

    def create_task(self, name: str, source: TaskSource = TaskSource.USER) -> str:
        tid = f"task_{int(time.time())}_{len(self._tasks)}"
        self._tasks[tid] = {"name": name, "source": source.value, "status": "pending",
                            "created": time.time(), "progress": 0.0, "checkpoints": []}
        return tid

    def update_status(self, tid: str, status: TaskStatus):
        if tid in self._tasks:
            self._tasks[tid]["status"] = status.value
            self._tasks[tid]["updated"] = time.time()

    def save_checkpoint(self, tid: str, data: dict) -> bool:
        if tid not in self._tasks: return False
        self._tasks[tid]["checkpoints"].append({"time": time.time(), "data": data})
        return True

    def load_all_checkpoints(self):
        pass

    def get_active_tasks(self) -> List[dict]:
        return [t for t in self._tasks.values() if t.get("status") in ("pending", "active")]
