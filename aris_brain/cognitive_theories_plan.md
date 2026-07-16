# LAAP 经典认知理论研究与实现计划

## 阶段 1：经典认知理论实现

### 1. PSI 理论（人类动机与行动） - Lothar Dörner
**原始文献**: Dörner, D. (2003). *The PSI theory of human motivation and action*.

**核心概念**:
- 心理状态分为：意图（intentions）、情绪（emotions）、感觉（sensations）
- 从外部指令到内在驱动的转化
- 需求、情绪与类脑决策的动力学模型

**实现目标**:
- 实现 PSI 状态机模型（需求、情绪、意图的状态转换）
- 实现内在动机系统（从外部指令到内在驱动的转化）

### 2. 全局工作空间理论（GWT） - Baars & Dehaene
**原始文献**: 
- Baars, B. J. (1988). *A Cognitive Theory of Consciousness*.
- Dehaene, S., & Naccache, L. (2001). "Towards a cognitive neuroscience of consciousness: basic evidence and a workspace framework".

**核心概念**:
- 信息只有进入"全局工作空间"才能被意识访问
- 全局广播机制（Global Broadcast）
- 注意力机制与信息整合

**实现目标**:
- 实现信息整合与全局广播机制
- 实现注意力流和意识流模块

### 3. 因果理论（Causality） - Judea Pearl
**原始文献**: Pearl, J. (2009). *Causality: Models, Reasoning, and Inference* (2nd edition).

**核心概念**:
- 因果图（Causal Graphs）
- do-calculus（干预计算）
- 因果层级：关联（Association）、干预（Intervention）、反事实（Counterfactuals）

**实现目标**:
- 实现因果推理引擎
- 实现因果图和 do-calculus 计算框架

### 4. 结构映射理论（Structure Mapping） - Dedre Gentner
**原始文献**: Gentner, D. (1983). "Structure-mapping: A theoretical framework for analogy".

**核心概念**:
- 类比基于关系结构的映射，而非表面特征的匹配
- 源域（source）到目标域（target）的关系映射

**实现目标**:
- 实现类比引擎
- 实现概念映射和关系图匹配算法

---

## 阶段 2：几何代数与语义空间（后续研究）

### 几何代数在自然语言语义中的应用
**原始文献**: Pustejovsky, J. "Toward a Functional Geometric Algebra for Natural Language Semantics".

**核心概念**:
- 多向量（Multivector）表示概念
- 几何积（Geometric Product）表示概念组合和关系
- 转子（Rotor）表示语义空间中的旋转和类比映射

**实现目标**:
- 实现真正的 Clifford 代数核心库
- 实现语义空间的几何代数表示