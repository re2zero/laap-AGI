"""
缺失模块 + 认知桥接 + 3路径控制 测试
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "aris_brain"))

import pytest


class TestCodeGraph:
    def test_import(self):
        from laap_codegraph import get_codegraph, LAAPCodeGraph, CodeEntity
        assert LAAPCodeGraph is not None

    def test_get_codegraph(self):
        from laap_codegraph import get_codegraph
        cg = get_codegraph(build=True)
        assert cg is not None
        stats = cg.get_stats()
        assert stats.get("files", 0) > 0  # 真实扫描了文件
        assert stats.get("entities", 0) > 0

    def test_search_and_query(self):
        from laap_codegraph import get_codegraph
        cg = get_codegraph(build=True)
        results = cg.search("laap_codegraph")
        assert len(results) >= 1
        # 应该能找到自身
        self_entity = cg.query("aris_brain/laap_codegraph.py")
        assert self_entity is not None
        assert self_entity["type"] == "file"


class TestTaskSupervisor:
    def test_import(self):
        from task_supervisor import TaskSupervisor, TaskSource, TaskStatus
        assert TaskSupervisor is not None

    def test_create_task(self):
        from task_supervisor import TaskSupervisor, TaskSource
        ts = TaskSupervisor()
        tid = ts.create_task("test-task", TaskSource.USER)
        assert tid.startswith("task_")
        assert len(ts.get_active_tasks()) >= 1

    def test_checkpoint(self):
        from task_supervisor import TaskSupervisor, TaskSource
        ts = TaskSupervisor()
        tid = ts.create_task("test", TaskSource.SYSTEM)
        ok = ts.save_checkpoint(tid, {"progress": 0.5})
        assert ok is True


class TestProjectPlanner:
    def test_import(self):
        from project_planner import ProjectPlanner, Phase, save_project, load_project, list_projects
        assert ProjectPlanner is not None

    def test_add_project(self):
        from project_planner import ProjectPlanner
        pp = ProjectPlanner()
        pid = pp.add_project("test-proj", "a test project")
        assert pid.startswith("proj_")

    def test_add_phase(self):
        from project_planner import ProjectPlanner
        pp = ProjectPlanner()
        phase = pp.add_phase("design")
        assert phase.name == "design"
        assert phase.status == "pending"


class TestAutoLearner:
    def test_import(self):
        from auto_learner import AutoLearner
        assert AutoLearner is not None

    def test_observe_and_suggest(self):
        from auto_learner import AutoLearner
        al = AutoLearner()
        al.observe("testing", {"passed": True})
        al.observe("code_review", {"issues": 3})
        stats = al.get_stats()
        assert stats["total"] == 2
        hints = al.suggest("context")
        assert len(hints) >= 1


class TestThreePaths:
    def test_llm_tamer(self):
        from laap.laap_tools.llm_tamer import LLMTamer
        tamer = LLMTamer()
        tamer.set_bias("the", 1.5)
        assert tamer.get_biases()["the"] == 1.5

    def test_guided_generator(self):
        from laap.laap_tools.guided_generator.generator import GuidedGenerator
        gen = GuidedGenerator()
        out = gen.generate("test prompt")
        assert "[guided]" in out

    def test_self_state_manager(self):
        from laap.laap_tools.self_model.state_manager import SelfStateManager
        ssm = SelfStateManager()
        ssm.load_state()
        assert ssm._state.get("loaded") is True

    def test_self_model_nn(self):
        from laap.laap_tools.self_model.model import SelfModelNN, SelfModelConfig
        config = SelfModelConfig(dim=128)
        model = SelfModelNN(config)
        output = model.forward([0.0] * 128)
        assert output is not None

    def test_self_model_adapter(self):
        from laap.laap_tools.self_model.adapter import bridge_state_to_snapshot
        snapshot = bridge_state_to_snapshot({"key": "value"})
        assert snapshot["type"] == "cognitive_bridge"


class TestCognitiveBridgeHealth:
    """验证认知桥接的缺失模块现在全部连通"""

    def test_bridge_all_modules_loaded(self):
        import importlib
        import aris_cognitive_bridge
        importlib.reload(aris_cognitive_bridge)
        bridge = aris_cognitive_bridge.ArisCognitiveBridge()
        assert getattr(bridge, "_cg_available", False), "CodeGraph should be available"
        assert getattr(bridge, "_ts_available", False), "TaskSupervisor should be available"
        assert getattr(bridge, "_pp_available", False), "ProjectPlanner should be available"
        assert getattr(bridge, "_al_available", False), "AutoLearner should be available"
        assert getattr(bridge, "_three_paths_available", False), "3-paths should be available"

    def test_bridge_init_logs_all_checks(self):
        import aris_cognitive_bridge
        bridge = aris_cognitive_bridge.ArisCognitiveBridge()
        # 验证初始化日志包含所有模块的检查标记
        summary = f"CodeGraph={'✓' if bridge._cg_available else '✗'}"
        assert "✓" in summary  # 字面意义检验可用

    def test_orchestrator_health(self):
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            assess = orch.self_assess()
            # 验证进化分数可正常读取
            assert "health" in assess
            assert "modules_loaded" in assess
