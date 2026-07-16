"""
Aris Context Compressor — 上下文压缩器
=======================================
压缩认知上下文和工具输出
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("aris.context_compressor")

def compress_cognitive_context(context: str, max_length: int = 500) -> str:
    """压缩认知上下文"""
    if not context or len(context) <= max_length:
        return context
        
    # 基础压缩实现：截断并添加提示
    return context[:max_length-20] + "...\n[上下文已压缩]"

def compress_tool_output(output: str, max_length: int = 300) -> str:
    """压缩工具输出"""
    if not output or len(output) <= max_length:
        return output
        
    # 基础压缩实现：截断并添加提示
    return output[:max_length-20] + "...\n[工具输出已压缩]"