"""
Rust PSI Bridge — Python 进化层与 Rust 性能层的桥接
=====================================================
使用 PyO3 桥接 Rust laap_psi_core 和 quantum_engine 库

架构:
  Python Evolution Layer (self-evolution modules)
      ↓
  RustPsiBridge (统一桥接)
      ↓
  ┌─────────────────────┬──────────────────────┐
  │ laap_psi_core (PyO3) │ quantum_engine (PyO3) │
  │ Multivector / Rotor  │ QuantumState / Gate   │
  │ Clifford Algebra     │ Quantum Cognition     │
  └─────────────────────┴──────────────────────┘

用法:
    from rust_psi_bridge import get_rust_psi_bridge
    bridge = get_rust_psi_bridge()
    mv = bridge.create_multivector_from([1.0, 2.0, 3.0])
    rotor = bridge.learn_rotor([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    result = rotor.apply([1.0, 0.0, 0.0])
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger("aris.rust_psi_bridge")


class RustPsiBridge:
    """Rust PSI 核心桥接器 — 统一访问两个 PyO3 模块"""

    def __init__(self):
        self._psi_core = None  # laap_psi_core module
        self._qre = None       # quantum_engine module
        self._available = False
        self._init_pyo3_bridges()

    def _init_pyo3_bridges(self):
        """初始化 PyO3 桥接"""
        try:
            import laap_psi_core
            self._psi_core = laap_psi_core
            logger.info("[RustPsiBridge] laap_psi_core (PyO3) 加载成功 ✓")
        except ImportError as e:
            logger.warning(f"[RustPsiBridge] laap_psi_core 加载失败: {e}")

        try:
            import quantum_engine
            self._qre = quantum_engine
            logger.info("[RustPsiBridge] quantum_engine (PyO3) 加载成功 ✓")
        except ImportError as e:
            logger.warning(f"[RustPsiBridge] quantum_engine 加载失败: {e}")

        self._available = self._psi_core is not None or self._qre is not None

    @property
    def available(self) -> bool:
        return self._available

    # ── Clifford Algebra (Multivector) Operations ──

    def create_multivector(self, dim: int = 3) -> Any:
        """创建空多向量"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        return self._psi_core.PyMultivector(dim)

    def create_multivector_from(self, vector: List[float]) -> Any:
        """从向量创建多向量（自动归一化）"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        return self._psi_core.PyMultivector.from_vector(vector)

    def inner_product(self, v1: List[float], v2: List[float]) -> float:
        """计算两个向量的内积"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        mv1 = self._psi_core.PyMultivector.from_vector(v1)
        mv2 = self._psi_core.PyMultivector.from_vector(v2)
        return mv1.inner_product(mv2)

    def outer_product(self, v1: List[float], v2: List[float]) -> Dict[str, Any]:
        """计算两个向量的外积 → 返回双向量"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        mv1 = self._psi_core.PyMultivector.from_vector(v1)
        mv2 = self._psi_core.PyMultivector.from_vector(v2)
        result = mv1.outer_product(mv2)
        return {
            "scalar": result.scalar,
            "vector": result.vector,
            "bivector": result.bivector,
            "trivector": result.trivector,
        }

    def geometric_product(self, v1: List[float], v2: List[float]) -> Dict[str, Any]:
        """计算两个向量的几何积"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        mv1 = self._psi_core.PyMultivector.from_vector(v1)
        mv2 = self._psi_core.PyMultivector.from_vector(v2)
        result = mv1.geometric_product(mv2)
        return {
            "scalar": result.scalar,
            "vector": result.vector,
            "bivector": result.bivector,
            "trivector": result.trivector,
        }

    # ── Rotor Operations ──

    def learn_rotor(self, source: List[float], target: List[float]) -> Any:
        """学习从 source 到 target 的旋转转子"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        return self._psi_core.PyRotor.learn(source, target)

    def create_rotor_from_bivector(self, bivector: List[float], dim: int = 3) -> Any:
        """从双向量创建转子"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        return self._psi_core.PyRotor.from_bivector(bivector, dim)

    def apply_rotor(self, rotor: Any, vector: List[float]) -> List[float]:
        """应用转子到向量"""
        if not self._psi_core:
            raise RuntimeError("laap_psi_core not available")
        return rotor.apply(vector)

    # ── Quantum Cognition Operations ──

    def create_quantum_state(self, num_qubits: int = 4) -> Any:
        """创建量子态"""
        if not self._qre:
            raise RuntimeError("quantum_engine not available")
        return self._qre.PyQuantumState(num_qubits)

    def create_cognition_model(self, num_qubits: int = 6) -> Any:
        """创建量子认知模型"""
        if not self._qre:
            raise RuntimeError("quantum_engine not available")
        return self._qre.PyQuantumCognitionModel(num_qubits)

    def simulate_interference(self, path1: List[float], path2: List[float]) -> List[float]:
        """量子干涉模拟 — 用于认知推理中的路径干涉"""
        if not self._qre:
            raise RuntimeError("quantum_engine not available")
        model = self._qre.PyQuantumCognitionModel(4)
        return model.simulate_interference(path1, path2)

    def simulate_order_effects(self, prob_a: float, prob_b: float, order: str = "A_then_B") -> float:
        """顺序效应模拟 — 用于认知偏见建模"""
        if not self._qre:
            raise RuntimeError("quantum_engine not available")
        model = self._qre.PyQuantumCognitionModel(4)
        return model.simulate_order_effects(prob_a, prob_b, order)

    # ── High-Level Cognitive Primitives ──

    def semantic_similarity(self, v1: List[float], v2: List[float]) -> float:
        """语义相似度 (使用内积 + 几何积特征)"""
        if not self._psi_core:
            # 降级到 numpy
            a = np.array(v1)
            b = np.array(v2)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
        inner = self.inner_product(v1, v2)
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        return inner / (n1 * n2 + 1e-10)

    def get_status(self) -> Dict[str, Any]:
        """获取桥接器状态"""
        return {
            "available": self._available,
            "laap_psi_core": self._psi_core is not None,
            "quantum_engine": self._qre is not None,
        }


# 单例实例
_rust_psi_bridge = None


def get_rust_psi_bridge() -> RustPsiBridge:
    """获取 Rust PSI 桥接器单例"""
    global _rust_psi_bridge
    if _rust_psi_bridge is None:
        _rust_psi_bridge = RustPsiBridge()
    return _rust_psi_bridge
