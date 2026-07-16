"""
Async Delegation — 异步背景委托 + 批量 fan-out
"""

import logging
import threading
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger("laap_tools.tools.async_delegation")

class AsyncDelegationTask:
    """异步委托任务"""
    
    def __init__(self, task_id: str, task: str, status: str = "pending"):
        self.task_id = task_id
        self.task = task
        self.status = status
        self.created_at = time.time()
        self.completed_at = None
        self.result = None
        
    def complete(self, result: Any):
        """完成任务"""
        self.status = "completed"
        self.completed_at = time.time()
        self.result = result
        
    def fail(self, error: str):
        """任务失败"""
        self.status = "failed"
        self.completed_at = time.time()
        self.result = {"error": error}


# 任务存储
_tasks: Dict[str, AsyncDelegationTask] = {}

def dispatch_async_delegation(task: str) -> str:
    """分派异步委托"""
    task_id = f"task_{int(time.time())}_{hash(task) % 10000}"
    task_obj = AsyncDelegationTask(task_id, task, "pending")
    _tasks[task_id] = task_obj
    
    # 启动后台线程
    def worker():
        try:
            # 模拟任务执行
            time.sleep(1)  # 模拟处理时间
            result = f"Completed: {task}"
            task_obj.complete(result)
        except Exception as e:
            task_obj.fail(str(e))
            
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    
    logger.info(f"Dispatched async delegation: {task_id}")
    return task_id

def dispatch_async_delegation_batch(tasks: List[str]) -> List[str]:
    """分派异步委托批处理"""
    task_ids = []
    for task in tasks:
        task_id = dispatch_async_delegation(task)
        task_ids.append(task_id)
    return task_ids

def list_async_delegations() -> List[Dict[str, Any]]:
    """列出异步委托"""
    result = []
    for task_id, task_obj in _tasks.items():
        result.append({
            "task_id": task_id,
            "task": task_obj.task,
            "status": task_obj.status,
            "created_at": task_obj.created_at,
            "completed_at": task_obj.completed_at,
            "result": task_obj.result
        })
    return result

def get_delegation_status(task_id: str) -> Optional[Dict[str, Any]]:
    """获取委托状态"""
    task_obj = _tasks.get(task_id)
    if not task_obj:
        return None
        
    return {
        "task_id": task_obj.task_id,
        "task": task_obj.task,
        "status": task_obj.status,
        "created_at": task_obj.created_at,
        "completed_at": task_obj.completed_at,
        "result": task_obj.result
    }