"""
Message Timestamps — 消息时间戳渲染
"""

def format_message_timestamp(ts: float) -> str:
    """格式化消息时间戳"""
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def strip_leading_message_timestamps(text: str) -> str:
    """移除领先的消息时间戳"""
    return text