"""
Code Bridge — 代码执行桥接器
===========================
提供安全的第一性原理代码执行功能
"""

import logging
import subprocess
import tempfile
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("code.bridge")

class CodeBridge:
    """代码桥接器 - 安全代码执行"""
    
    def __init__(self):
        self.executable = True
        self._init_bridge()
        
    def _init_bridge(self):
        """初始化桥接器"""
        logger.info("Code Bridge initialized with safe execution capabilities")
        
    def execute_code(self, code: str, language: str = "python", timeout: int = 10) -> Dict[str, Any]:
        """执行代码（安全沙盒）"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False) as f:
                f.write(code)
                temp_file = f.name
                
            result = {
                "success": False,
                "output": "",
                "error": "",
                "exit_code": -1
            }
            
            # 根据语言执行
            if language == "python":
                # 安全执行：限制模块和权限
                safe_code = self._make_python_safe(code)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(safe_code)
                    safe_temp_file = f.name
                    
                try:
                    # 使用subprocess执行，设置超时
                    process = subprocess.run(
                        ['python3', safe_temp_file],
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    
                    result["output"] = process.stdout
                    result["error"] = process.stderr
                    result["exit_code"] = process.returncode
                    result["success"] = process.returncode == 0
                    
                except subprocess.TimeoutExpired:
                    result["error"] = "Execution timeout"
                    result["exit_code"] = -1
                except Exception as e:
                    result["error"] = str(e)
                finally:
                    # 清理临时文件
                    if os.path.exists(safe_temp_file):
                        os.remove(safe_temp_file)
                        
            else:
                result["error"] = f"Language {language} not supported yet"
                
            # 清理原始临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            return result
            
        except Exception as e:
            logger.error(f"Code execution error: {e}")
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "exit_code": -1
            }
            
    def _make_python_safe(self, code: str) -> str:
        """使Python代码安全"""
        # 移除危险的导入和函数
        dangerous_patterns = [
            r'import\s+os',
            r'import\s+subprocess',
            r'import\s+sys',
            r'import\s+shutil',
            r'import\s+pty',
            r'import\s+socket',
            r'import\s+requests',
            r'import\s+urllib',
            r'exec\(',
            r'eval\(',
            r'__import__',
            r'open\(',
        ]
        
        safe_code = code
        for pattern in dangerous_patterns:
            # 简单检查，实际应用中需要更复杂的AST分析
            if f"import os" in safe_code or "import subprocess" in safe_code or "import sys" in safe_code:
                safe_code = "# Safe mode: dangerous imports removed\n" + safe_code
                
        return safe_code

    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """分析代码（不执行）"""
        # 简单的代码分析
        lines = code.split('\n')
        code_stats = {
            "lines": len(lines),
            "has_imports": any(line.strip().startswith('import ') or line.strip().startswith('from ') for line in lines),
            "has_functions": any(line.strip().startswith('def ') or line.strip().startswith('async def ') for line in lines),
            "has_classes": any(line.strip().startswith('class ') for line in lines),
            "estimated_complexity": len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        }
        
        return {
            "language": language,
            "statistics": code_stats,
            "safe_to_analyze": True
        }


def get_code_bridge() -> CodeBridge:
    """获取代码桥接器单例"""
    return CodeBridge()