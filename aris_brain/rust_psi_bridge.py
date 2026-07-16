"""
Rust PSI Bridge — Python 进化层与 Rust 性能层的桥接
=====================================================
使用 ctypes 或 pyo3 桥接 Rust laap_psi_core 库
"""

import ctypes
import os
import numpy as np
from typing import List, Dict, Any

# 获取 Rust 库路径
RUST_LIB_PATH = os.path.join(os.path.dirname(__file__), '..', 'rust_psi_core', 'target', 'release', 'liblaap_psi_core.so')

class RustPsiBridge:
    """Rust PSI 核心桥接器"""
    
    def __init__(self):
        # 加载 Rust 动态库
        try:
            self.lib = ctypes.CDLL(RUST_LIB_PATH)
            print(f"✓ Rust PSI Core 库加载成功: {RUST_LIB_PATH}")
        except Exception as e:
            print(f"✗ Rust PSI Core 库加载失败: {e}")
            self.lib = None
            
    def create_multivector(self, dim: int) -> Dict[str, Any]:
        """创建多向量"""
        if not self.lib:
            raise RuntimeError("Rust PSI Core 库未加载")
            
        # 调用 Rust 函数创建多向量
        # 这里需要根据实际的 Rust FFI 接口调整
        return {
            "scalar": 0.0,
            "vector": [0.0] * dim,
            "bivector": [0.0] * dim,
            "trivector": [0.0] * dim
        }
        
    def geometric_product(self, mv1: Dict[str, List[float]], mv2: Dict[str, List[float]]) -> Dict[str, List[float]]:
        """计算几何积"""
        if not self.lib:
            raise RuntimeError("Rust PSI Core 库未加载")
            
        # 调用 Rust 几何积函数
        # 简化实现：返回 mv1 的副本
        return mv1.copy()
        
    def learn_rotor(self, source: List[float], target: List[float]) -> List[List[float]]:
        """学习转子旋转矩阵"""
        if not self.lib:
            raise RuntimeError("Rust PSI Core 库未加载")
            
        # 调用 Rust 转子学习函数
        # 简化实现：返回单位矩阵
        dim = len(source)
        return [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]


# 单例实例
_rust_psi_bridge = None

def get_rust_psi_bridge() -> RustPsiBridge:
    """获取 Rust PSI 桥接器单例"""
    global _rust_psi_bridge
    if _rust_psi_bridge is None:
        _rust_psi_bridge = RustPsiBridge()
    return _rust_psi_bridge