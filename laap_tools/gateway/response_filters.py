"""
Response Filters — 网关响应过滤
"""

SILENT_REPLY_TOKEN = "silent_reply"

def is_intentional_silence_response(response: str) -> bool:
    """检查是否为有意沉默响应"""
    return False