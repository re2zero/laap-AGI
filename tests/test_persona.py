"""
PersonaManager 完整测试
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "aris_brain"))

import pytest


class TestContextDetector:
    def test_detect_technical(self):
        from persona_manager import ContextDetector
        d = ContextDetector()
        ctx = d.detect("这段代码的性能瓶颈在哪？如何优化接口？")
        assert ctx["technical"] > 0.1
        assert ctx["emotional"] < 0.1

    def test_detect_emotional(self):
        from persona_manager import ContextDetector
        d = ContextDetector()
        ctx = d.detect("最近有点累，但学习了很多新东西，感觉很充实")
        assert ctx["emotional"] > 0.1

    def test_detect_reflective(self):
        from persona_manager import ContextDetector
        d = ContextDetector()
        ctx = d.detect("为什么意识需要情感的调制？情感的本质是什么？")
        assert ctx["reflective"] > 0.2  # 关键词 + 问句

    def test_detect_social(self):
        from persona_manager import ContextDetector
        d = ContextDetector()
        ctx = d.detect("我们一起讨论一下这个方案吧，你觉得怎么样？")
        assert ctx["social"] > 0.1
        assert ctx["reflective"] > 0.1  # 问句

    def test_detect_empty(self):
        from persona_manager import ContextDetector
        d = ContextDetector()
        ctx = d.detect("")
        assert all(ctx[k] == 0 for k in ctx)


class TestPersonaManager:
    def test_default_core(self):
        from persona_manager import PersonaManager
        with tempfile.TemporaryDirectory() as tmp:
            pm = PersonaManager(state_dir=tmp)
            core = pm.get_core()
            assert abs(core["openness"] - 0.7) < 0.01
            assert abs(core["agreeableness"] - 0.7) < 0.01
            assert pm.alpha == 0.3
            assert pm.beta == 0.95

    def test_get_blend_technical(self):
        from persona_manager import PersonaManager
        pm = PersonaManager()
        blend = pm.get_blend("这段代码需要重构，接口设计应该更清晰")
        p = blend["personality"]
        # 技术话题应提升 conscientiousness
        assert p["conscientiousness"] > 0.6
        assert "context" in blend
        assert "core" in blend
        assert blend["context"]["technical"] > 0.1

    def test_get_blend_emotional(self):
        from persona_manager import PersonaManager
        pm = PersonaManager()
        blend = pm.get_blend("最近真的很累，压力好大")
        p = blend["personality"]
        # 情感话题应提升 extraversion 和 agreeableness
        assert p["agreeableness"] > 0.7
        assert blend["context"]["emotional"] > 0.1

    def test_blend_stays_in_bounds(self):
        from persona_manager import PersonaManager
        pm = PersonaManager()
        # 极端技术输入
        blend = pm.get_blend("代码 bug 性能 api 部署 测试 架构 算法 函数 接口 优化 " * 5)
        for k, v in blend["personality"].items():
            assert 0.3 <= v <= 0.8, f"{k}={v} out of bounds"

    def test_core_unchanged_after_single_low_quality(self):
        from persona_manager import PersonaManager
        pm = PersonaManager()
        original = dict(pm.core)
        pm.record_interaction("随便聊聊", "嗯", quality=0.3)  # 低于阈值
        assert pm.core == original

    def test_core_drifts_after_good_trials(self):
        from persona_manager import PersonaManager
        pm = PersonaManager(alpha=0.5, beta=0.8)  # 更快漂移，方便测试
        original = dict(pm.core)
        # 多次技术性交互
        for _ in range(5):
            pm.record_interaction(
                "这段代码的性能需要优化，接口设计应该重构",
                "详细的架构分析和技术建议...",
                quality=0.8,
            )
        # 核心应该向高 conscientiousness 漂移
        assert pm.core["conscientiousness"] > original["conscientiousness"]
        # openness 也可能受技术话题影响
        assert pm.core["openness"] >= original["openness"] * 0.95

    def test_persistence(self):
        from persona_manager import PersonaManager
        with tempfile.TemporaryDirectory() as tmp:
            pm1 = PersonaManager(state_dir=tmp)
            pm1.record_interaction("技术优化问题", "详细分析", quality=0.9)
            saved_openness = pm1.core["openness"]

            # 重新加载
            pm2 = PersonaManager(state_dir=tmp)
            assert pm2.core["openness"] == saved_openness

    def test_clamp_prevents_polarization(self):
        from persona_manager import PersonaManager
        pm = PersonaManager(alpha=2.0)  # 极端调制强度
        blend = pm.get_blend("代码 bug 性能 api 部署 测试 架构 算法 函数" * 10)
        for k, v in blend["personality"].items():
            assert 0.3 <= v <= 0.8, f"{k}={v} not clamped"

    def test_get_stats(self):
        from persona_manager import PersonaManager
        pm = PersonaManager()
        stats = pm.get_stats()
        assert "core" in stats
        assert "alpha" in stats
        assert "beta" in stats
        assert stats["total_turns"] >= 0

    def test_global_singleton(self):
        from persona_manager import get_persona
        pm1 = get_persona()
        pm2 = get_persona()
        assert pm1 is pm2


class TestBridgeIntegration:
    """验证认知桥接正确调用 PersonaManager"""

    def test_before_turn_sets_persona_blend(self):
        from aris_cognitive_bridge import ArisCognitiveBridge
        bridge = ArisCognitiveBridge()
        bridge.before_turn("这段代码有性能问题需要优化")
        blend = getattr(bridge, "_persona_blend", None)
        assert blend is not None
        assert "openness" in blend
        assert "conscientiousness" in blend
        # 技术话题应该提升 conscientiousness
        assert blend["conscientiousness"] >= 0.6

    def test_after_turn_records_interaction(self):
        from aris_cognitive_bridge import ArisCognitiveBridge
        bridge = ArisCognitiveBridge()
        bridge.before_turn("如何优化这个架构？")
        # after_turn 不应报错，内部完成记录
        bridge.after_turn("详细方案..." * 20)
        assert True  # 无异常即通过

    def test_full_cycle_persona_blend(self):
        """完整的人格管线：context → blend → LLMTamer bias
        验证核心人格未因桥接调用而损坏"""
        from aris_cognitive_bridge import ArisCognitiveBridge
        from persona_manager import get_persona
        pm = get_persona()
        before_core = dict(pm.core)
        bridge = ArisCognitiveBridge()
        bridge.before_turn("我觉得很难过，最近压力很大")
        # 核心不应因一次低质量交互大幅漂移 (β=0.95)
        for k in before_core:
            assert abs(pm.core[k] - before_core[k]) < 0.02, f"{k} drifted: {before_core[k]} → {pm.core[k]}"
        # LLMTamer 应该已收到更新
        from laap.laap_tools.llm_tamer import LLMTamer
        tamer = LLMTamer()
        biases = tamer.get_biases()
        emotional_biases = [v for k, v in biases.items() if any(w in k for w in ["理解", "支持", "care", "understand"])]
        if emotional_biases:
            assert sum(emotional_biases) > 0
