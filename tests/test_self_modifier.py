"""
闭环自我修改管线测试
"""
import sys, os, tempfile, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "aris_brain"))

import pytest


class TestSelfModifier:
    """SelfModifier 闭环自我修改引擎测试"""

    def test_self_modifier_importable(self):
        from aris_brain.self_modifier import get_self_modifier, SelfModifier, PatchSpec, ModificationResult
        assert SelfModifier is not None
        assert PatchSpec is not None

    def test_scan_all_discovers_issues(self):
        from aris_brain.self_modifier import get_self_modifier
        mod = get_self_modifier()
        issues = mod.scan_all()
        assert len(issues) > 0
        # 至少应该有一些不同类型的 issue
        types = set(i["type"] for i in issues)
        assert len(types) >= 3  # missing_type_hints, long_line, etc.

    def test_dry_run_no_side_effects(self):
        from aris_brain.self_modifier import get_self_modifier
        mod = get_self_modifier()
        results = mod.fix_all(dry_run=True)
        for r in results:
            assert r.status == "pending", f"dry-run should not modify: {r.spec.description}"
            assert not r.commit_hash, "dry-run should not commit"

    def test_safety_check_blocks_dangerous_paths(self):
        """安全检查应阻止修改配置文件 and 危险操作"""
        from aris_brain.self_modifier import SelfModifier, PatchSpec

        mod = SelfModifier(repo_root=str(REPO_ROOT))
        with tempfile.TemporaryDirectory() as tmp:
            # 修改配置文件
            bad_patch = PatchSpec(
                file_path="pyproject.toml",
                old_string="", new_string="",
                description="test",
            )
            ok, msg = mod._safety_check(bad_patch)
            assert not ok, f"should block config file: {msg}"

            # 修改 .env
            bad_patch2 = PatchSpec(
                file_path=".env",
                old_string="", new_string="",
                description="test",
            )
            ok2, _ = mod._safety_check(bad_patch2)
            assert not ok2

            # 修改 aris_brain/*.py 应该通过
            good_patch = PatchSpec(
                file_path="aris_brain/self_modifier.py",
                old_string="", new_string="# test",
                description="test",
            )
            ok3, msg3 = mod._safety_check(good_patch)
            assert ok3, f"should allow aris_brain/*.py: {msg3}"

    def test_fix_file_dry_run(self):
        from aris_brain.self_modifier import get_self_modifier
        mod = get_self_modifier()
        target = "aris_brain/self_modifier.py"
        results = mod.fix_file(target, dry_run=True)
        for r in results:
            assert r.status == "pending"

    def test_history_persists(self):
        from aris_brain.self_modifier import get_self_modifier
        mod = get_self_modifier()
        mod.fix_all(dry_run=True)
        history = mod.get_history()
        assert len(history) > 0
        summary = mod.get_summary()
        assert summary["total_scans"] > 0
        assert "pending" in str(summary)
        assert "committed" in str(summary)


class TestClosedLoopIntegration:
    """Orchestrator + SelfModifier 闭环集成测试"""

    def test_orchestrator_loads_self_modifier(self):
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            orch._ensure_modules()
            assert orch._self_modifier is not None, "SelfModifier should load"

    def test_evolve_cycle_includes_self_modify(self):
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            result = orch.evolve("自我改进", mode="auto")
            # Phase 5 应出现在结果中（可能没有修改，但应该有阶段输出）
            if "self_modifications" in result:
                sm = result["self_modifications"]
                assert "scan_count" in sm
                assert "dry_run_fixes" in sm

    def test_self_assess_includes_self_modifier(self):
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            assess = orch.self_assess()
            assert "self_modifier_available" in assess

    def test_suggest_improvements_not_broken(self):
        from aris_brain.self_evolution_orchestrator import get_orchestrator
        with tempfile.TemporaryDirectory() as tmp:
            orch = get_orchestrator(tmp)
            suggestions = orch.suggest_improvements()
            assert isinstance(suggestions, list)
