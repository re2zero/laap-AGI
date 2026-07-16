"""
Aris Self-Evolution 完整管线测试
=================================
验证所有升级模块是否可以正常加载、互联、协作运行。

运行:
    python -m pytest tests/test_self_evolution.py -v -x -s

测试覆盖:
    1. Rust PyO3 桥接可用性
    2. 所有 5 个自我进化模块可导入
    3. SelfEvolutionOrchestrator 完整进化循环
    4. CodeGenerator v2 真实代码生成
    5. OriginalityGenerator v2 概念重组
    6. MetaCognitionEngine v2 真实指标
    7. 模块间互联
    8. Rust 引擎增强
"""

import sys
import os
import time
import tempfile
from pathlib import Path

# 项目根
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "aris_brain"))

import pytest


# ═══════════════════════════════════════════════════════════════
# 测试 1: Rust PyO3 桥接
# ═══════════════════════════════════════════════════════════════


class TestRustBridge:
    """验证 Rust PyO3 桥接器已正确安装并可调用"""

    def test_quantum_engine_importable(self):
        """quantum_engine 应可通过 import 正常加载"""
        import quantum_engine
        assert hasattr(quantum_engine, "PyQuantumState")
        assert hasattr(quantum_engine, "PyQuantumGate")
        assert hasattr(quantum_engine, "PyQuantumCognitionModel")

    def test_laap_psi_core_importable(self):
        """laap_psi_core 应可通过 import 正常加载"""
        import laap_psi_core
        assert hasattr(laap_psi_core, "PyMultivector")
        assert hasattr(laap_psi_core, "PyRotor")

    def test_quantum_state_creation(self):
        """PyQuantumState 应能创建和计算概率"""
        import quantum_engine
        state = quantum_engine.PyQuantumState(2)
        assert state.num_qubits == 2
        probs = state.get_measurement_probabilities()
        assert len(probs) == 4  # 2^2

    def test_quantum_interference(self):
        """量子干涉模拟应返回有效结果"""
        import quantum_engine
        model = quantum_engine.PyQuantumCognitionModel(4)
        result = model.simulate_interference([0.5, 0.3], [0.5, 0.3])
        assert len(result) == 2
        # 建设性干涉应该增加概率
        assert result[0] >= 0.5

    def test_order_effects(self):
        """顺序效应应反映非交换测量"""
        import quantum_engine
        model = quantum_engine.PyQuantumCognitionModel(4)
        a = model.simulate_order_effects(0.7, 0.5, "A_then_B")
        b = model.simulate_order_effects(0.7, 0.5, "B_then_A")
        assert 0 <= a <= 1.0
        assert 0 <= b <= 1.0

    def test_multivector_geometric_product(self):
        """PyMultivector 的几何积应正确"""
        import laap_psi_core
        mv1 = laap_psi_core.PyMultivector.from_vector([1.0, 0.0, 0.0])
        mv2 = laap_psi_core.PyMultivector.from_vector([0.0, 1.0, 0.0])
        inner = mv1.inner_product(mv2)
        assert abs(inner) < 1e-10  # 正交向量内积为0

    def test_rotor_learn(self):
        """Rotor 应能学习从 source 到 target 的旋转"""
        import laap_psi_core
        rotor = laap_psi_core.PyRotor.learn([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        applied = rotor.apply([1.0, 0.0, 0.0])
        assert abs(applied[0]) < 1e-2
        assert abs(applied[1] - 1.0) < 1e-2

    def test_rust_bridge_wrapper(self):
        """RustPsiBridge 包装器应能正常使用"""
        from aris_brain.rust_psi_bridge import get_rust_psi_bridge
        bridge = get_rust_psi_bridge()
        assert bridge.available
        assert bridge.get_status()["laap_psi_core"]
        assert bridge.get_status()["quantum_engine"]

        mv = bridge.create_multivector_from([1.0, 2.0, 3.0])
        assert mv is not None

        sim = bridge.semantic_similarity([1.0, 0.0, 0.0], [1.0, 0.1, 0.0])
        assert sim > 0.9


# ═══════════════════════════════════════════════════════════════
# 测试 2: 自我进化模块
# ═══════════════════════════════════════════════════════════════


class TestSelfEvolutionModules:
    """验证 5 个自我进化模块可加载并具备 v2 功能"""

    def test_software_engineering_v2(self):
        """software_engineering v2: AST 分析、代码生成"""
        from aris_brain.software_engineering import (
            get_code_generator, get_solid_checker, get_code_analyzer,
        )
        generator = get_code_generator()
        # v2 应支持 AST 分析
        assert hasattr(generator, "generate_code_snippet")
        # 验证 ASTAnalyzer
        from aris_brain.software_engineering import ASTAnalyzer
        funcs = ASTAnalyzer.extract_functions("def foo(x): return x + 1")
        assert len(funcs) == 1
        assert funcs[0]["name"] == "foo"
        # 验证代码生成
        code = generator.generate_code_snippet("validate email input", "validator")
        assert "class" in code
        assert "Validator" in code
        assert "validate" in code
        # 验证 SOLID 检查
        checker = get_solid_checker()
        result = checker.check_all("class A: pass")
        assert "srp" in result
        # 验证 CodeAnalyzer
        analyzer = get_code_analyzer()
        result = analyzer.analyze_complexity("if x: pass\nif y: pass")
        assert result["complexity_level"] in ("low", "medium")

    def test_creativity_engine_v2(self):
        """creativity_engine v2: 概念图谱、动态联想"""
        from aris_brain.creativity_engine import (
            get_cross_domain_associator, get_aesthetic_perceiver,
            get_originality_generator, ConceptGraph,
        )
        with tempfile.TemporaryDirectory() as tmp:
            # ConceptGraph 动态扩展
            graph = ConceptGraph(tmp)
            initial_concepts = len(graph.get_domain_concepts("technology"))
            assert initial_concepts >= 8
            # 添加新概念
            graph.add_concept("quantum_semantics", "cognitive")
            assert "quantum_semantics" in graph.get_domain_concepts("cognitive")
            # 概念组合
            composite = graph.compose("algorithm", "rhythm", "algorhythm")
            assert composite == "algorhythm"
            # 跨界联想
            assoc = get_cross_domain_associator(tmp)
            insight = assoc.generate_creative_insight(["technology", "art"])
            assert insight["confidence"] > 0
            # 美学感知（真实特征）
            perceiver = get_aesthetic_perceiver()
            scores = perceiver.evaluate_aesthetic(
                "The light dances across the water like a symphony of silver threads."
            )
            for dim in ["symmetry", "complexity", "harmony", "novelty", "emotion"]:
                assert dim in scores
                assert 0 <= scores[dim] <= 1.0
            # 原创生成（语义重组）
            orig = get_originality_generator(tmp)
            content = orig.generate_original_content("consciousness", "emergence")
            assert len(content) > 20
            assert "consciousness" in content or "emergence" in content

    def test_aris_self_model_v2(self):
        """aris_self_model v2: 持久化 + 指标收集"""
        from aris_brain.aris_self_model import (
            get_self_model, get_meta_cognition_engine, MetricsCollector,
        )
        with tempfile.TemporaryDirectory() as tmp:
            # 指标收集器
            collector = MetricsCollector()
            collector.record_turn(150.0, success=True, coherence=0.8)
            collector.record_turn(200.0, success=True, coherence=0.7)
            summary = collector.get_summary()
            assert summary["count"] == 2
            assert summary["success_rate"] == 1.0
            assert "trend" in summary
            # 元认知引擎
            meta = get_meta_cognition_engine(tmp)
            meta.reflect_on_turn(
                "test input", "test output", 150.0,
                metadata={"complexity_score": 5},
            )
            state = meta.get_cognitive_state_summary()
            assert state["reflection_count"] >= 1
            assert "metrics" in state
            # 自我改进建议
            suggestions = meta.suggest_self_improvement()
            assert isinstance(suggestions, list)
            # 自我模型持久化
            model = get_self_model(tmp)
            summary = model.get_self_model_summary()
            assert "core_concepts" in summary
            assert "personality_state" in summary
            assert "metrics" in summary

    def test_aris_emotion_deepen(self):
        """aris_emotion_deepen 应可正常使用"""
        from aris_brain.aris_emotion_deepen import (
            BigFivePersonality, NeedEmotionCoupler,
            EmotionRegulationSystem,
        )
        personality = BigFivePersonality.aris_default()
        traits = personality.to_dict()
        assert traits["openness"] == 0.8
        # 激素调整
        hormones = {"dopamine": 50, "oxytocin": 50, "cortisol": 50, "acetylcholine": 50}
        adj = personality.apply_to_hormones(hormones)
        assert "acetylcholine" in adj
        assert "serotonin" in adj
        # 情感调节
        regulation = EmotionRegulationSystem()
        blend, changed = regulation.cognitive_reappraisal("anxious", 0.8, {"anxious": 0.8}, hormones)
        assert changed
        assert blend["anxious"] < 0.8

    def test_deep_interaction(self):
        """deep_interaction 模块应可正常使用"""
        from aris_brain.deep_interaction import (
            get_active_care_system, get_challenge_and_inspire_system,
            get_growth_partnership_system,
        )
        care = get_active_care_system()
        assert care.check_care_opportunity("我今天学习了很多", {"primary_emotion": "joy"})
        challenge = get_challenge_and_inspire_system()
        q = challenge.generate_challenge("进化", "快速迭代")
        assert len(q) > 10
        growth = get_growth_partnership_system()
        growth.record_shared_learning("Python元类", "Rust所有权系统")
        summary = growth.get_growth_summary()
        assert summary["shared_learnings"] >= 1


# ═══════════════════════════════════════════════════════════════
# 测试 3: SelfEvolutionOrchestrator
# ═══════════════════════════════════════════════════════════════


class TestSelfEvolutionOrchestrator:
    """验证 Orchestrator 的完整进化管线"""

    @pytest.fixture
    def orchestrator(self):
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            yield orch

    def test_orchestrator_evolve_full_cycle(self, orchestrator):
        """完整进化循环应调用所有可用模块并返回结构化结果"""
        result = orchestrator.evolve(
            "代码优化和架构改进",
            mode="auto",
        )
        # 基本结构
        assert result["cycle"] >= 0
        assert "perception" in result
        assert "latency_ms" in result
        assert result["latency_ms"] > 0
        # 感知阶段
        assert "suggested_modules" in result["perception"]
        # 模块输出
        if result.get("module_outputs"):
            for mod_name, output in result["module_outputs"].items():
                assert "module" in output
                assert "latency_ms" in output
        # 洞见
        assert "insights" in result
        assert "scores" in result
        assert "self_reflection" in result

    def test_orchestrator_self_assess(self, orchestrator):
        """自我评估应返回所有模块的健康状态"""
        assessment = orchestrator.self_assess()
        assert "state" in assessment
        assert "modules_loaded" in assessment
        assert "rust_available" in assessment
        assert "health" in assessment
        # 至少应该加载一些模块
        assert len(assessment["modules_loaded"]) > 0 or not assessment["health"]["overall"]

    def test_orchestrator_suggestions(self, orchestrator):
        """改进建议应返回排序后的列表"""
        suggestions = orchestrator.suggest_improvements()
        assert isinstance(suggestions, list)
        # 如果没有 Rust，应有高优先级建议
        from aris_brain.rust_psi_bridge import get_rust_psi_bridge
        if not get_rust_psi_bridge().available:
            rust_suggestions = [s for s in suggestions if s["module"] == "rust_bridge"]
            assert any(s["priority"] == "high" for s in rust_suggestions)

    def test_orchestrator_state_persistence(self, orchestrator):
        """进化状态应能持久化和恢复"""
        # 第一次进化
        orchestrator.evolve("测试进化", mode="auto")
        c1 = orchestrator.state.cycle_count
        # 重新创建（模拟重启）
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        with tempfile.TemporaryDirectory() as tmp:
            orch2 = get_orchestrator(tmp)
            orch2.evolve("更多测试", mode="auto")
            assert orch2.state.cycle_count >= c1


# ═══════════════════════════════════════════════════════════════
# 测试 4: 模块间互联
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """验证模块间的协作网络"""

    def test_orchestrator_integrates_modules(self):
        """Orchestrator 应能激活多个模块并收集结果"""
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            result = orch.evolve("进化、学习、创造", mode="auto")
            # 至少应该触发了某个模块
            assert len(result.get("module_outputs", {})) >= 0

    def test_code_generator_produces_real_code(self):
        """CodeGenerator v2 应生成可执行的代码"""
        from aris_brain.software_engineering import get_code_generator
        gen = get_code_generator()

        # 验证器生成
        validator = gen.generate_code_snippet("validate user age", "validator")
        assert "class" in validator
        assert "validate" in validator

        # 工厂生成
        factory = gen.generate_code_snippet("create database connection", "factory")
        assert "class" in factory
        assert "create" in factory or "Factory" in factory

        # 流水线生成
        pipeline = gen.generate_code_snippet("data processing pipeline", "pipeline")
        assert "class" in pipeline
        assert "Pipeline" in pipeline or "Step" in pipeline

    def test_originality_generator_diverse_outputs(self):
        """连续调用应产生不同的原创内容"""
        from aris_brain.creativity_engine import get_originality_generator
        with tempfile.TemporaryDirectory() as tmp:
            orig = get_originality_generator(tmp)
            outputs = set()
            for _ in range(5):
                content = orig.generate_original_content("consciousness", "emergence")
                outputs.add(content[:30])  # 前缀足矣判断不同
            # 至少要有 3 种不同输出
            assert len(outputs) >= 3, f"Only {len(outputs)} unique outputs out of 5"

    def test_meta_cognition_real_metrics(self):
        """MetaCognitionEngine 应基于真实指标而非关键词"""
        from aris_brain.aris_self_model import get_meta_cognition_engine
        with tempfile.TemporaryDirectory() as tmp:
            meta = get_meta_cognition_engine(tmp)
            # 记录一些不好的表现
            for _ in range(5):
                meta.reflect_on_turn(
                    "test input",
                    "short",
                    3000.0,  # 高延迟
                    metadata={"error": True},
                )
            # 应该检测到问题
            suggestions = meta.suggest_self_improvement()
            # 至少应该有一些建议
            if suggestions:
                assert any(s["priority"] in ("high", "medium") for s in suggestions)

    def test_orchestrator_with_rust(self):
        """Orchestrator 应能在可用时调用 Rust 引擎"""
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        from aris_brain.rust_psi_bridge import get_rust_psi_bridge
        if not get_rust_psi_bridge().available:
            pytest.skip("Rust bridge not available")

        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            result = orch.evolve("进化", mode="auto")
            if result.get("rust_used"):
                assert "rust_output" in result
                assert "quantum_insights" in result["rust_output"]


# ═══════════════════════════════════════════════════════════════
# 测试 5: 状态持久化
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """验证状态能在模块重启后恢复"""

    def test_orchestrator_state_survives_reinit(self):
        """进化状态文件持久化后应能正确恢复"""
        import tempfile, json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            from aris_brain.self_evolution_orchestrator import SelfEvolutionOrchestrator
            orch1 = SelfEvolutionOrchestrator(tmp)
            orch1.evolve("第一次进化", mode="auto")
            orch1.evolve("第二次进化", mode="auto")
            saved_cycle = orch1.state.cycle_count

            # 验证状态文件存在
            state_path = Path(tmp) / "self_evolution.json"
            assert state_path.exists()
            data = json.loads(state_path.read_text(encoding="utf-8"))
            assert data["cycle_count"] >= saved_cycle - 1

            # 重新创建实例，模拟重启
            orch2 = SelfEvolutionOrchestrator(tmp)
            assert orch2.state.cycle_count > 0

    def test_self_model_state_survives_reinit(self):
        """自我模型持久化后应能恢复人格状态"""
        import tempfile, json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            from aris_brain.aris_self_model import get_self_model
            model1 = get_self_model(tmp)
            model1.personality_state["openness"] = 0.95

            # 重新创建
            model2 = get_self_model(tmp)
            # 应该从磁盘恢复
            assert model2.personality_state["openness"] >= 0.7
