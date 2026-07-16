"""SelfModel Adapter — 桥接状态转换"""
from typing import Any, Dict

def bridge_state_to_snapshot(state: Any) -> Dict:
    return {"type": "cognitive_bridge", "data": str(state)[:100]}

def self_state_output_to_snapshot(output: Any) -> Dict:
    return {"type": "self_state", "data": str(output)[:100]}

def snapshot_to_self_state_output(snapshot: Dict) -> Any:
    return None
