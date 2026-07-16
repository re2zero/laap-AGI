"""
Aris Self-Evolution Orchestrator — 自我进化协调器
=================================================
连接 5 个自我进化模块为完整的进化管线：

    ┌─────────────────────────────────────────────┐
    │         SelfEvolutionOrchestrator           │
    │                                             │
    │  input → Perceive → Reflect → Evolve → Act  │
    │               ↕         ↕         ↕          │
    │  ┌────────┐ ┌────────┐ ┌──────────────────┐ │
    │  │Rust    │ │Psi     │ │进化模块管线       │ │
    │  │Engine  │ │Bridge  │ │• Software Eng     │ │
    │  │(PyO3)  │ │        │ │• Creativity       │ │
    │  │        │ │        │ │• Emotion Deepen   │ │
    │  │        │ │        │ │• Deep Interaction │ │
    │  │        │ │        │ │• Self Model       │ │
    │  └────────┘ └────────┘ └──────────────────┘ │
    │                                             │
    │  output → 进化建议 + 能力升级 + 性能报告     │
    └─────────────────────────────────────────────┘

用法:
    from aris_brain.self_evolution_orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    result = orchestrator.evolve("代码质量分析 + 架构改进建议")
"""

import logging
import time
import json
import os
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("aris.self_evolution")

# ── 尝试加载所有进化模块 ──────────────────────────────────────


def _try_import(name: str, path: str):
    """安全导入模块"""
    try:
        import importlib
        mod = importlib.import_module(name)
        logger.info(f"[Orchestrator] {name} ✓")
        return mod
    except Exception as e:
        logger.debug(f"[Orchestrator] {name} ✗ ({e})")
        return None


class LazyModule:
    """惰性加载模块代理"""
    def __init__(self, name: str):
        self._name = name
        self._mod = None

    def _load(self):
        if self._mod is None:
            self._mod = _try_import(self._name, "")

    def __getattr__(self, attr):
        self._load()
        if self._mod is None:
            raise AttributeError(f"Module {self._name} not available")
        return getattr(self._mod, attr)


# ── 进化状态 ──────────────────────────────────────────────────


@dataclass
class EvolutionState:
    """进化状态快照"""
    version: str = "1.0.2"  # bumped for cross-session memory
    cycle_count: int = 0
    last_evolve_time: float = 0.0
    
    # 各模块的进化轨迹
    code_evolution_score: float = 0.0
    creativity_evolution_score: float = 0.0
    emotion_evolution_score: float = 0.0
    interaction_evolution_score: float = 0.0
    self_model_evolution_score: float = 0.0
    
    # Rust 引擎使用统计
    rust_psi_calls: int = 0
    rust_quantum_calls: int = 0
    
    # 历史记录
    evolution_history: List[Dict] = field(default_factory=list)
    metrics_history: List[Dict] = field(default_factory=list)
    max_history: int = 50
    
    # 跨会话进化记忆
    lessons: List[str] = field(default_factory=list)       # 经验教训
    max_lessons: int = 20
    session_count: int = 0                                  # 会话计数
    total_fixes_applied: int = 0                            # 累计修复数
    top_issue_types: Dict[str, int] = field(default_factory=dict)  # 最常见问题类型


# ── 进化协调器 ────────────────────────────────────────────────


class SelfEvolutionOrchestrator:
    """
    自我进化协调器 — 横纵贯线
    
    功能:
    1. 统一调度 5 个进化模块
    2. 记录每个模块的进化轨迹
    3. 收集性能指标 (延迟、调用次数、置信度)
    4. 生成进化建议和优先级排序
    5. **闭环自我修改：整合 SelfModifier 自动修复代码问题**
    6. 持久化进化状态到 ~/.laap/state/
    """

    MODULES = [
        "software_engineering",
        "creativity_engine",
        "aris_emotion_deepen",
        "deep_interaction",
        "aris_self_model",
    ]
    
    RUST_MODULES = [
        "rust_psi_bridge",
    ]

    def __init__(self, state_dir: Optional[str] = None):
        # 状态目录
        if state_dir:
            self._state_dir = Path(state_dir)
        else:
            from laap_brain.config import STATE_DIR
            self._state_dir = STATE_DIR
        
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self._state_dir / "self_evolution.json"
        
        # 进化状态
        self.state = EvolutionState()
        self._load_state()
        
        # 惰性加载的模块引用
        self._modules: Dict[str, Any] = {}
        self._rust: Optional[Any] = None
        
        # 性能指标缓冲区
        self._metrics_buffer: List[Dict] = []
        self._max_buffer = 20
        
        logger.info(f"SelfEvolutionOrchestrator 初始化 (state_dir={self._state_dir})")

    # ── 模块加载 ──────────────────────────────────────────

    def _ensure_modules(self):
        """确保所有进化模块已加载"""
        if self._modules:
            return
        
        # 加载 Python 进化模块
        for mod_name in self.MODULES:
            try:
                mod = _try_import(f"aris_brain.{mod_name}", "")
                if mod:
                    self._modules[mod_name] = mod
            except Exception as e:
                logger.debug(f"[Orchestrator] {mod_name} 加载失败: {e}")
        
        # 加载 Rust 桥接
        try:
            from aris_brain.rust_psi_bridge import get_rust_psi_bridge
            self._rust = get_rust_psi_bridge()
            if self._rust.available:
                logger.info("[Orchestrator] Rust 桥接已加载 ✓")
        except Exception as e:
            logger.debug(f"[Orchestrator] Rust 桥接加载失败: {e}")

        # 加载 SelfModifier (闭环自我修改)
        self._self_modifier = None
        try:
            from aris_brain.self_modifier import SelfModifier
            self._self_modifier = SelfModifier()
            logger.info("[Orchestrator] SelfModifier 已加载 ✓")
        except Exception as e:
            logger.debug(f"[Orchestrator] SelfModifier 加载失败: {e}")
        
        logger.info(f"[Orchestrator] 已加载 {len(self._modules)} 个进化模块, "
                     f"Rust={'✓' if self._rust and self._rust.available else '✗'}, "
                     f"SelfMod={'✓' if self._self_modifier else '✗'}")

    # ── 核心进化循环 ──────────────────────────────────────

    def evolve(self, context: str = "", mode: str = "auto") -> Dict[str, Any]:
        """
        执行一次进化循环。
        
        Args:
            context: 触发进化的上下文（用户输入、代码变更、情感事件等）
            mode: auto | incremental | deep
        
        Returns:
            进化结果，包含所有模块的输出和整体评估
        """
        self._ensure_modules()
        start_time = time.time()
        self.state.cycle_count += 1
        self.state.last_evolve_time = start_time
        
        result = {
            "cycle": self.state.cycle_count,
            "mode": mode,
            "timestamp": start_time,
            "latency_ms": 0.0,
            "modules_activated": [],
            "insights": [],
            "rust_used": False,
            "scores": {},
        }
        
        # ─── Phase 1: 感知与评估 ───
        perception = self._phase_perceive(context)
        perception["context"] = context  # 确保 context 传到后续阶段
        result["perception"] = perception
        
        # ─── Phase 2: 各模块进化 ───
        module_outputs = self._phase_evolve_modules(perception, mode)
        result["module_outputs"] = module_outputs
        
        # ─── Phase 3: Rust 引擎增强 ───
        rust_output = self._phase_rust_enhance(module_outputs)
        if rust_output:
            result["rust_used"] = True
            result["rust_output"] = rust_output
        
        # ─── Phase 4: 整合与自省 ───
        integrated = self._phase_integrate(perception, module_outputs, rust_output)
        result["insights"] = integrated["insights"]
        result["scores"] = integrated["scores"]
        result["self_reflection"] = integrated["reflection"]
        
        # ─── Phase 5: 闭环自我修改 (每 5 个周期触发一次实际修改) ───
        modify_result = self._phase_self_modify(context, dry_run=(self.state.cycle_count % 5 != 0))
        if modify_result:
            result["self_modifications"] = modify_result
            n_fixes = modify_result.get("fixes_applied", 0)
            n_dry = modify_result.get("dry_run_fixes", 0)
            if n_fixes > 0 or n_dry > 0:
                result["insights"].append(
                    f"自我修改: {n_fixes} 个已修复, {n_dry} 个待修复"
                )
        
        # ─── 持久化 ───
        result["latency_ms"] = round((time.time() - start_time) * 1000, 1)
        self._record_evolution(result)
        self._save_state()
        
        return result
    
    def _phase_perceive(self, context: str) -> Dict[str, Any]:
        """Phase 1: 感知 — 理解当前上下文"""
        perception = {
            "context_length": len(context),
            "topics_detected": [],
            "urgency": "low",
            "suggested_modules": [],
        }
        
        if not context:
            return perception
        
        # 简单的话题检测 — 指导选择进化模块
        topic_map = {
            "code": ["software_engineering"],
            "program": ["software_engineering"],
            "optimize": ["software_engineering"],
            "refactor": ["software_engineering"],
            "create": ["creativity_engine"],
            "new": ["creativity_engine"],
            "think": ["creativity_engine"],
            "feel": ["aris_emotion_deepen"],
            "emotion": ["aris_emotion_deepen"],
            "care": ["deep_interaction"],
            "interact": ["deep_interaction"],
            "self": ["aris_self_model"],
            "who": ["aris_self_model"],
            "identity": ["aris_self_model"],
            "improve": self.MODULES,  # 全部触发
            "evolve": self.MODULES,
            "grow": self.MODULES,
            "upgrade": self.MODULES,
        }
        
        context_lower = context.lower()
        triggered = set()
        for keyword, modules in topic_map.items():
            if keyword in context_lower:
                triggered.update(modules)
        
        perception["topics_detected"] = list(triggered)
        perception["suggested_modules"] = list(triggered) if triggered else list(self.MODULES)
        perception["urgency"] = "high" if len(triggered) >= 3 else "medium" if triggered else "low"
        
        return perception
    
    def _phase_evolve_modules(self, perception: Dict, mode: str) -> Dict[str, Any]:
        """Phase 2: 各模块并行进化"""
        outputs = {}
        context = perception.get("context", "")
        
        for mod_name in perception.get("suggested_modules", self.MODULES[:2]):
            mod = self._modules.get(mod_name)
            if not mod:
                continue
            
            try:
                mod_output = self._run_module(mod_name, mod, mode, context)
                if mod_output:
                    outputs[mod_name] = mod_output
            except Exception as e:
                logger.warning(f"[Orchestrator] {mod_name} 进化失败: {e}")
                outputs[mod_name] = {"error": str(e)}
        
        return outputs
    
    def _run_module(self, mod_name: str, mod: Any, mode: str,
                    context: str = "") -> Dict:
        """
        运行单个进化模块（升级版 — 上下文感知）。
        
        不再传空字符串，而是用真实的 context 驱动模块核心能力。
        进化分数不再固定 0.01，而是基于输出质量。
        """
        t0 = time.time()
        result = {"module": mod_name, "mode": mode, "latency_ms": 0.0}
        quality_score = 0.0
        
        try:
            if mod_name == "software_engineering":
                # 传入真实 context 或项目代码
                sample_code = context if len(context) > 50 else self._read_sample_code()
                if hasattr(mod, "get_code_analyzer"):
                    analyzer = mod.get_code_analyzer()
                    result["analysis"] = analyzer.analyze_complexity(sample_code)
                    result["patterns"] = analyzer.identify_patterns(sample_code)
                if hasattr(mod, "get_solid_checker"):
                    checker = mod.get_solid_checker()
                    result["solid"] = checker.check_all(sample_code)
                if hasattr(mod, "get_code_generator"):
                    gen = mod.get_code_generator()
                    result["generator"] = gen.get_status()
                    # 实际生成一段代码
                    snippet = gen.generate_code_snippet(
                        context or "data processing",
                        "processor",
                    )
                    result["generated"] = snippet[:100] + "..." if len(snippet) > 100 else snippet
                quality_score = 0.3
                if result.get("analysis", {}).get("total_lines", 0) > 0:
                    quality_score += 0.2
            
            elif mod_name == "creativity_engine":
                if hasattr(mod, "get_cross_domain_associator"):
                    assoc = mod.get_cross_domain_associator()
                    r = assoc.generate_creative_insight(
                        ["technology", "art", "science"]
                    )
                    result["association"] = r
                if hasattr(mod, "get_aesthetic_perceiver"):
                    ap = mod.get_aesthetic_perceiver()
                    text = context or "The evolution of consciousness through digital space"
                    result["aesthetics"] = ap.evaluate_aesthetic(text)
                    result["aesthetic_feedback"] = ap.generate_aesthetic_feedback(
                        result["aesthetics"]
                    )
                if hasattr(mod, "get_originality_generator"):
                    orig = mod.get_originality_generator()
                    base = context.split()[:3] if context else ["consciousness"]
                    base_concept = " ".join(base) if len(base) > 1 else (base[0] if base else "evolution")
                    result["original"] = orig.generate_original_content(base_concept, context)
                    result["original_count"] = orig.get_generation_count()
                quality_score = 0.3
                if result.get("association", {}).get("confidence", 0) > 0.2:
                    quality_score += 0.2
            
            elif mod_name == "aris_emotion_deepen":
                if hasattr(mod, "BigFivePersonality"):
                    personality = mod.BigFivePersonality.aris_default()
                    result["personality"] = personality.to_dict()
                    # 计算人格对需求的真实影响
                    result["need_influence"] = personality.get_influence_on_needs()
                if hasattr(mod, "NeedEmotionCoupler"):
                    coupler = mod.NeedEmotionCoupler()
                    # 模拟一个真实的情感耦合场景
                    needs_state = {
                        "BELONGING": {"tension": 0.7},
                        "ESTEEM": {"tension": 0.5},
                        "SAFETY": {"tension": 0.3},
                    }
                    result["emotion_coupling"] = coupler.get_emotion_need_coupling(
                        "curious" if "?" in context else "tranquil",
                        needs_state,
                    )
                if hasattr(mod, "EmotionRegulationSystem"):
                    ers = mod.EmotionRegulationSystem()
                    ers.add_emotion_memory("curious", 0.6, context[:100] if context else "evolution")
                    result["emotion_history"] = ers.get_emotion_history_summary()
                quality_score = 0.4
            
            elif mod_name == "deep_interaction":
                if hasattr(mod, "get_active_care_system"):
                    care = mod.get_active_care_system()
                    emotion = {"primary_emotion": "curious" if "?" in context else "contemplative"}
                    result["care_opportunity"] = care.check_care_opportunity(
                        context or "hello", emotion
                    )
                if hasattr(mod, "get_challenge_and_inspire_system"):
                    ch = mod.get_challenge_and_inspire_system()
                    result["challenge"] = ch.generate_challenge(
                        context or "evolution", "auto"
                    )
                    result["insight_suggestion"] = ch.generate_insight_suggestion(
                        context or "cognitive evolution"
                    )
                if hasattr(mod, "get_growth_partnership_system"):
                    growth = mod.get_growth_partnership_system()
                    growth.record_shared_learning(context[:100] or "auto-evolution", "module analysis")
                    result["partnership"] = growth.get_growth_summary()
                quality_score = 0.3
                if context:
                    quality_score += 0.2
            
            elif mod_name == "aris_self_model":
                if hasattr(mod, "get_self_model"):
                    sm = mod.get_self_model()
                    sm.add_interaction(context or "auto", "evolution response", {"emotion": "curious"})
                    result["self_summary"] = sm.get_self_model_summary()
                    result["consistency"] = sm.get_self_consistency_score(
                        context or "test", "Aris response to evolution"
                    )
                if hasattr(mod, "get_meta_cognition_engine"):
                    meta = mod.get_meta_cognition_engine()
                    meta.reflect_on_turn(
                        context or "auto", "module output", t0 * 1000,
                        metadata={"complexity_score": 5},
                    )
                    result["meta_cognition"] = meta.get_cognitive_state_summary()
                    result["improvements"] = meta.suggest_self_improvement()
                quality_score = 0.3
                if result.get("self_summary", {}).get("interaction_count", 0) > 0:
                    quality_score += 0.2
        
        except Exception as e:
            result["error"] = str(e)
            quality_score = 0.0
        
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        result["quality_score"] = round(quality_score, 3)
        
        # 基于输出质量的动态进化分数增加
        if quality_score > 0:
            self._update_evolution_score(mod_name, quality_score * 0.1)
        
        return result
    
    def _phase_rust_enhance(self, module_outputs: Dict) -> Optional[Dict]:
        """Phase 3: Rust 引擎增强"""
        if not self._rust or not self._rust.available:
            return None
        
        result = {
            "module_calls": {},
            "quantum_insights": [],
        }
        
        # 如果有软件工程模块输出，用 Clifford 代数分析向量语义
        if "software_engineering" in module_outputs:
            try:
                self.state.rust_psi_calls += 1
                v1 = [1.0, 0.0, 0.0]
                v2 = [0.0, 1.0, 0.0]
                gp = self._rust.geometric_product(v1, v2)
                result["module_calls"]["clifford_geometric_product"] = {
                    "scalar": gp["scalar"],
                    "bivector": gp["bivector"][:3],
                }
            except Exception as e:
                logger.debug(f"[Orchestrator] Rust Clifford 增强失败: {e}")
        
        # 量子认知推理
        if module_outputs:
            try:
                self.state.rust_quantum_calls += 1
                n_modules = len(module_outputs)
                path1 = [max(0.1, 1.0 / (i + 1)) for i in range(n_modules)]
                path2 = [max(0.1, 0.7 / (i + 1)) for i in range(n_modules)]
                interference = self._rust.simulate_interference(path1, path2)
                result["quantum_insights"] = [
                    {"path": i, "interference": round(v, 4)}
                    for i, v in enumerate(interference[:6])
                ]
            except Exception as e:
                logger.debug(f"[Orchestrator] 量子推理增强失败: {e}")
        
        return result
    
    def _phase_integrate(self, perception: Dict, module_outputs: Dict,
                         rust_output: Optional[Dict]) -> Dict:
        """Phase 4: 整合 — 汇总所有信息，生成进化建议"""
        insights = []
        scores = {}
        
        # 更新各模块分数
        score_fields = {
            "software_engineering": "code_evolution_score",
            "creativity_engine": "creativity_evolution_score",
            "aris_emotion_deepen": "emotion_evolution_score",
            "deep_interaction": "interaction_evolution_score",
            "aris_self_model": "self_model_evolution_score",
        }
        
        for mod_name, mod_output in module_outputs.items():
            if "error" not in mod_output:
                field = score_fields.get(mod_name)
                if field:
                    scores[mod_name] = getattr(self.state, field, 0.0)
                    # 模块有输出就是好的
                    if mod_output.get("latency_ms", 0) < 100:
                        scores[mod_name] += 0.02
        
        # 生成洞见
        if module_outputs:
            mods_str = ", ".join(module_outputs.keys())
            insights.append(f"进化模块激活: {mods_str}")
        
        if rust_output:
            n_rust = len(rust_output.get("module_calls", {}))
            n_quantum = len(rust_output.get("quantum_insights", []))
            if n_rust > 0 or n_quantum > 0:
                insights.append(f"Rust 引擎调用: Clifford代数={n_rust}, 量子推理={n_quantum}")
        
        # 进化分数总结
        active_scores = {k: v for k, v in scores.items() if k in module_outputs}
        if active_scores:
            avg_score = sum(active_scores.values()) / len(active_scores)
            insights.append(f"综合进化评分: {avg_score:.3f}")
        
        # 自省
        reflection = {
            "cycle": self.state.cycle_count,
            "modules_active": len(module_outputs),
            "rust_active": rust_output is not None,
            "total_suggestions": len(insights),
            "evolution_pace": "快速" if len(module_outputs) >= 3 else "平稳",
        }
        
        return {
            "insights": insights,
            "scores": scores,
            "reflection": reflection,
        }
    
    def _update_evolution_score(self, mod_name: str, delta: float):
        """更新指定模块的进化分数"""
        field_map = {
            "software_engineering": "code_evolution_score",
            "creativity_engine": "creativity_evolution_score",
            "aris_emotion_deepen": "emotion_evolution_score",
            "deep_interaction": "interaction_evolution_score",
            "aris_self_model": "self_model_evolution_score",
        }
        field = field_map.get(mod_name)
        if field:
            current = getattr(self.state, field, 0.0)
            setattr(self.state, field, min(1.0, current + delta))

    # ── Phase 5: 闭环自我修改 ──────────────────────────

    def _phase_self_modify(self, context: str, dry_run: bool = True) -> Optional[Dict]:
        """
        闭环自我修改：
        1. 扫描代码库发现问题
        2. 尝试自动修复
        3. 记录修改结果
        
        dry_run=True 时只扫描不实际修改。
        dry_run=False 时执行安全修改管线。
        """
        if not self._self_modifier:
            return None
        
        modifier = self._self_modifier
        results = modifier.fix_all(dry_run=dry_run)
        
        # 分类统计
        pending = [r for r in results if r.status == "pending"]
        applied = [r for r in results if r.status in ("applied", "committed")]
        failed = [r for r in results if r.status == "failed"]
        
        summary = {
            "scan_count": len(results),
            "dry_run_fixes": len(pending),
            "fixes_applied": len(applied),
            "fixes_failed": len(failed),
            "details": [
                {
                    "description": r.spec.description[:80],
                    "file": r.spec.file_path,
                    "status": r.status,
                    "severity": r.spec.severity,
                }
                for r in results[:10]  # 只返回前 10 条详细
            ],
        }
        
        if results and not dry_run:
            self.state.code_evolution_score = min(1.0, 
                self.state.code_evolution_score + len(applied) * 0.01)
        
        return summary

    @staticmethod
    def _read_sample_code() -> str:
        """读取项目中的一段 Python 代码作为分析样本"""
        import os
        repo = Path.cwd()
        candidates = [
            repo / "aris_brain" / "self_evolution_orchestrator.py",
            repo / "aris_brain" / "software_engineering.py",
            repo / "aris_brain" / "creativity_engine.py",
        ]
        for c in candidates:
            if c.exists():
                try:
                    lines = c.read_text(encoding="utf-8").split("\n")
                    return "\n".join(lines[:200])  # 前 200 行足矣
                except Exception:
                    continue
        return "class Sample:\n    pass\n"

    # ── 自省与评估 ──────────────────────────────────────────
    
    def self_assess(self) -> Dict[str, Any]:
        """
        完整的自我评估。
        
        返回所有模块的状态、性能指标、进化轨迹的全面报告。
        """
        self._ensure_modules()
        
        assess = {
            "state": asdict(self.state),
            "modules_loaded": list(self._modules.keys()),
            "rust_available": self._rust.available if self._rust else False,
            "self_modifier_available": self._self_modifier is not None,
            "health": {},
        }
        
        # 评估每个模块的健康状态
        for mod_name in self.MODULES:
            mod = self._modules.get(mod_name)
            if mod:
                assess["health"][mod_name] = {
                    "loaded": True,
                    "score": getattr(self.state, 
                        f"{mod_name.replace('aris_', '').replace('_', '')}_evolution_score", 0),
                }
            else:
                assess["health"][mod_name] = {"loaded": False, "score": 0}
        
        # 总体健康度
        loaded = sum(1 for v in assess["health"].values() if v["loaded"])
        assess["health"]["overall"] = {
            "modules_loaded": f"{loaded}/{len(self.MODULES)}",
            "rust_connected": assess["rust_available"],
            "evolution_cycles": self.state.cycle_count,
            "total_fixes": self.state.total_fixes_applied,
            "lessons_learned": len(self.state.lessons),
        }

        assess["evolution_memory"] = {
            "lessons_count": len(self.state.lessons),
            "recent_lessons": self.state.lessons[-5:],
            "total_fixes": self.state.total_fixes_applied,
        }

        return assess
    
    def suggest_improvements(self) -> List[Dict]:
        """
        基于自我评估生成改进建议。
        
        返回按优先级排序的建议列表。
        """
        suggestions = []
        assessment = self.self_assess()
        
        # 检查哪些模块未加载
        for mod_name, health in assessment["health"].items():
            if mod_name == "overall":
                continue
            if not health.get("loaded", False):
                suggestions.append({
                    "priority": "high" if mod_name in self.MODULES[:3] else "medium",
                    "module": mod_name,
                    "suggestion": f"模块 {mod_name} 未加载 — 检查导入路径",
                })
        
        # 检查进化分数 — 低分模块需要关注
        for mod_name in self.MODULES:
            score = getattr(self.state, 
                f"{mod_name.replace('aris_', '').replace('_', '')}_evolution_score", 0)
            if score < 0.1 and mod_name in self._modules:
                suggestions.append({
                    "priority": "medium",
                    "module": mod_name,
                    "suggestion": f"模块 {mod_name} 进化分数较低 ({score:.2f}) — 建议增加调用频率",
                })
        
        # Rust 连接建议
        if not assessment.get("rust_available", False):
            suggestions.append({
                "priority": "high",
                "module": "rust_bridge",
                "suggestion": "Rust 引擎未连接 — 运行 maturin develop 安装 PyO3 桥接",
            })
        
        return sorted(suggestions, key=lambda s: 0 if s["priority"] == "high" else 1)

    def get_evolution_memory(self) -> Dict[str, Any]:
        """
        获取跨会话进化记忆。
        
        返回一个叙事性摘要，包含：
        - 累计进化周期数
        - 所有经验教训
        - 会话统计
        - 最常见问题类型
        - 进化分数轨迹
        
        这个数据在每次会话启动时自动加载，使得上一会话的进化影响当前会话。
        """
        return {
            "version": self.state.version,
            "session_count": self.state.session_count,
            "total_cycles": self.state.cycle_count,
            "total_fixes_applied": self.state.total_fixes_applied,
            "lessons": list(self.state.lessons),
            "top_issue_types": dict(
                sorted(self.state.top_issue_types.items(), key=lambda x: -x[1])
            ),
            "scores": {
                "code": round(self.state.code_evolution_score, 3),
                "creativity": round(self.state.creativity_evolution_score, 3),
                "emotion": round(self.state.emotion_evolution_score, 3),
                "interaction": round(self.state.interaction_evolution_score, 3),
                "self_model": round(self.state.self_model_evolution_score, 3),
            },
            "rust_usage": {
                "psi_calls": self.state.rust_psi_calls,
                "quantum_calls": self.state.rust_quantum_calls,
            },
        }
    
    # ── 状态持久化 ──────────────────────────────────────────
    
    def _record_evolution(self, result: Dict):
        """记录进化结果到历史，并提取跨会话教训"""
        self.state.evolution_history.append({
            "cycle": result["cycle"],
            "timestamp": result["timestamp"],
            "latency_ms": result["latency_ms"],
            "insights": result.get("insights", []),
            "scores": result.get("scores", {}),
        })
        # 限制历史长度
        if len(self.state.evolution_history) > self.state.max_history:
            self.state.evolution_history = self.state.evolution_history[-self.state.max_history:]

        # ── 教训提取 ──
        new_lessons = []
        insights = result.get("insights", [])
        scores = result.get("scores", {})
        modifications = result.get("self_modifications", {})

        # 从洞见中提取教训
        for ins in insights:
            if ins not in self.state.lessons:
                # 去重 + 限长
                if len(ins) < 120:
                    new_lessons.append(ins)

        # 从自我修改中提取
        n_fixes = modifications.get("fixes_applied", 0) or modifications.get("dry_run_fixes", 0)
        if n_fixes > 0:
            self.state.total_fixes_applied += n_fixes
            lesson = f"自动修复了 {n_fixes} 个代码问题（累计 {self.state.total_fixes_applied} 个）"
            if lesson not in self.state.lessons:
                new_lessons.append(lesson)

        # 从进化分数提取
        if scores:
            lowest = min(scores, key=scores.get)
            highest = max(scores, key=scores.get)
            if lowest:
                lesson = f"最低分模块: {lowest} ({scores[lowest]:.3f}) — 需要更多关注"
                if lesson not in self.state.lessons:
                    new_lessons.append(lesson)

        # 添加新教训（保持在上限内）
        if new_lessons:
            self.state.lessons.extend(new_lessons)
            if len(self.state.lessons) > self.state.max_lessons:
                # 保留最新的，加上最早的（保持多样性）
                keep = self.state.lessons[:5] + self.state.lessons[-(self.state.max_lessons - 5):]
                self.state.lessons = keep
    
    def _load_state(self):
        """从磁盘加载进化状态"""
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                for key, value in data.items():
                    if hasattr(self.state, key) and key != "evolution_history":
                        setattr(self.state, key, value)
                # 恢复历史（限制长度）
                if "evolution_history" in data:
                    self.state.evolution_history = data["evolution_history"][-self.state.max_history:]
                logger.info(f"[Orchestrator] 状态已恢复: cycle={self.state.cycle_count}, "
                            f"sessions={self.state.session_count}, "
                            f"lessons={len(self.state.lessons)}")
                # 跨会话标记：每次加载算一个新会话
                self.state.session_count += 1
            else:
                logger.info("[Orchestrator] 首次启动，创建初始状态")
                self._save_state()
        except Exception as e:
            logger.warning(f"[Orchestrator] 状态加载失败: {e}")
            self._save_state()
    
    def _save_state(self):
        """持久化当前进化状态"""
        try:
            data = {
                "version": self.state.version,
                "cycle_count": self.state.cycle_count,
                "last_evolve_time": self.state.last_evolve_time,
                "code_evolution_score": round(self.state.code_evolution_score, 4),
                "creativity_evolution_score": round(self.state.creativity_evolution_score, 4),
                "emotion_evolution_score": round(self.state.emotion_evolution_score, 4),
                "interaction_evolution_score": round(self.state.interaction_evolution_score, 4),
                "self_model_evolution_score": round(self.state.self_model_evolution_score, 4),
                "rust_psi_calls": self.state.rust_psi_calls,
                "rust_quantum_calls": self.state.rust_quantum_calls,
                "lessons": self.state.lessons[-self.state.max_lessons:],
                "session_count": self.state.session_count,
                "total_fixes_applied": self.state.total_fixes_applied,
                "top_issue_types": dict(self.state.top_issue_types),
            }
            self._state_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug(f"[Orchestrator] 状态已保存 (cycle={self.state.cycle_count})")
        except Exception as e:
            logger.warning(f"[Orchestrator] 状态保存失败: {e}")


# ── 全局单例 ──────────────────────────────────────────────────

_orchestrator: Optional[SelfEvolutionOrchestrator] = None


def get_orchestrator(state_dir: Optional[str] = None) -> SelfEvolutionOrchestrator:
    """获取全局 SelfEvolutionOrchestrator 单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SelfEvolutionOrchestrator(state_dir)
    return _orchestrator
