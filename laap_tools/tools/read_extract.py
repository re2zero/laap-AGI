"""
Read Extract — 文档提取
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("laap_tools.tools.read_extract")

def extract_document_text(file_path: str) -> str:
    """提取文档文本"""
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return ""
        
    # 检查文件类型
    ext = os.path.splitext(file_path)[1].lower()
    
    # 支持文本文件
    if ext in ['.txt', '.md', '.json', '.csv', '.xml', '.html', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.rs', '.go']:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            return ""
            
    # 支持简单文档格式（模拟）
    elif ext in ['.pdf', '.doc', '.docx']:
        logger.info(f"Document extraction for {ext} is simulated")
        return f"[Simulated text extraction from {file_path}]\nThis is a simulated document extraction for {ext} files."
        
    else:
        logger.warning(f"Unsupported file type: {ext}")
        return ""

def is_extractable_document(file_path: str) -> bool:
    """检查是否可提取文档"""
    if not os.path.exists(file_path):
        return False
        
    ext = os.path.splitext(file_path)[1].lower()
    extractable_types = [
        '.txt', '.md', '.json', '.csv', '.xml', '.html', '.py', '.js', '.ts',
        '.java', '.c', '.cpp', '.h', '.rs', '.go', '.pdf', '.doc', '.docx'
    ]
    return ext in extractable_types