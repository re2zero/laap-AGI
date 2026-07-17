"""Core Identity — Layer 1: 认知锚
==================================
Aris 的自我认知核心。

包含:
  SelfModel      — 模块拓扑、能力/限制清单
  KnowledgeEntry — 单个知识条目
  KnowledgeMap   — 知识地图（置信度、缺口发现）
  ValueSystem    — 内在价值体系（多维度评价）
  NarrativeSelf  — 自我叙事（身份、里程碑）
  CoreIdentity   — 门面，统一初始化/持久化

用法:
    identity = CoreIdentity(state_manager)
    identity.initialize()
    gaps = identity.knowledge_map.find_gaps()
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from aris_brain.self_driven.state_manager import StateManager

logger = logging.getLogger("aris.self_driven.identity")

# ═══════════════════════════════════════════════════════════════
# SelfModel — 动态自我模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class ModuleInfo:
    """单个模块的描述"""
    name: str
    file_path: str
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    version: str = "1.0.0"


class SelfModel:
    """模块拓扑 + 能力/限制清单。

    回答：
    - 如果我改 emotion_engine，哪些模块会受影响？
    - 我当前的能力边界在哪？
    - 新增一个能力需要改哪些地方？
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._modules: Dict[str, ModuleInfo] = {}
        self._capabilities: List[str] = []
        self._limitations: List[str] = []
        self._dependency_graph: Dict[str, List[str]] = {}
        if data:
            self.from_dict(data)

    # ── 查询 ──────────────────────────────────────────────

    def get_module(self, name: str) -> Optional[ModuleInfo]:
        return self._modules.get(name)

    def get_affected_modules(self, module_name: str) -> List[str]:
        """如果修改指定模块，哪些模块会受影响？"""
        affected = []
        for name, info in self._modules.items():
            if module_name in info.dependencies:
                affected.append(name)
        return affected

    def has_capability(self, capability: str) -> bool:
        return capability in self._capabilities

    def list_capabilities(self) -> List[str]:
        return list(self._capabilities)

    def list_limitations(self) -> List[str]:
        return list(self._limitations)

    def list_modules(self) -> List[str]:
        return list(self._modules.keys())

    # ── 变更 ──────────────────────────────────────────────

    def register_module(self, info: ModuleInfo):
        self._modules[info.name] = info
        self._dependency_graph[info.name] = info.dependencies
        for cap in info.capabilities:
            if cap not in self._capabilities:
                self._capabilities.append(cap)

    def add_limitation(self, limitation: str):
        if limitation not in self._limitations:
            self._limitations.append(limitation)

    def remove_limitation(self, limitation: str):
        if limitation in self._limitations:
            self._limitations.remove(limitation)

    # ── 序列化 ────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modules": {
                name: {
                    "file_path": info.file_path,
                    "capabilities": info.capabilities,
                    "dependencies": info.dependencies,
                    "version": info.version,
                }
                for name, info in self._modules.items()
            },
            "dependency_graph": dict(self._dependency_graph),
            "capabilities": list(self._capabilities),
            "limitations": list(self._limitations),
        }

    def from_dict(self, data: Dict[str, Any]):
        modules_data = data.get("modules", {})
        for name, mod in modules_data.items():
            self._modules[name] = ModuleInfo(
                name=name,
                file_path=mod.get("file_path", f"aris_brain/{name}.py"),
                capabilities=mod.get("capabilities", []),
                dependencies=mod.get("dependencies", []),
                version=mod.get("version", "1.0.0"),
            )
        self._capabilities = data.get("capabilities", [])
        self._limitations = data.get("limitations", [])
        self._dependency_graph = data.get("dependency_graph", {})


# ═══════════════════════════════════════════════════════════════
# KnowledgeEntry & KnowledgeMap — 知识地图
# ═══════════════════════════════════════════════════════════════


@dataclass
class KnowledgeEntry:
    """一条结构化知识条目"""
    concept: str
    domain: str = "general"
    confidence: float = 0.0       # 0.0=未知 → 1.0=精通
    relevance: float = 0.5        # 对成为生命体的重要性
    source: str = ""              # 来源标识
    evidence: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    keywords_en: List[str] = field(default_factory=list)  # 英文搜索关键词
    last_updated: float = 0.0
    verified: bool = False        # 是否经过实验验证


class KnowledgeMap:
    """结构化记录"我知道什么 / 不知道什么"。

    核心功能:
    - 按概念增删查
    - 找出置信度低但相关性高的缺口 (好奇心目标)
    - 跨域关联查询
    - 序列化/反序列化
    """

    def __init__(self):
        self._entries: Dict[str, KnowledgeEntry] = {}

    # ── 增删查 ────────────────────────────────────────────

    def get_entry(self, concept: str) -> Optional[KnowledgeEntry]:
        return self._entries.get(concept)

    def upsert_entry(self, entry: KnowledgeEntry):
        entry.last_updated = time.time()
        self._entries[entry.concept] = entry

    def remove_entry(self, concept: str):
        self._entries.pop(concept, None)

    def has_concept(self, concept: str) -> bool:
        return concept in self._entries

    def list_concepts(self, domain: Optional[str] = None) -> List[str]:
        if domain:
            return [c for c, e in self._entries.items() if e.domain == domain]
        return list(self._entries.keys())

    def get_all_entries(self) -> List[KnowledgeEntry]:
        return list(self._entries.values())

    # ── 缺口分析 ──────────────────────────────────────────

    def find_gaps(
        self,
        min_relevance: float = 0.5,
        max_confidence: float = 0.3,
        max_results: int = 10,
    ) -> List[KnowledgeEntry]:
        """找到置信度低但相关性高的领域。

        Args:
            min_relevance: 最低相关性阈值
            max_confidence: 最高置信度阈值（低于此值为 gap）
            max_results: 最多返回条数

        Returns:
            按 (relevance - confidence) 降序排列
        """
        gaps = [
            e for e in self._entries.values()
            if e.relevance >= min_relevance and e.confidence <= max_confidence
        ]
        gaps.sort(key=lambda e: e.relevance - e.confidence, reverse=True)
        return gaps[:max_results]

    def find_novel_gaps(
        self,
        min_relevance: float = 0.3,
        max_confidence: float = 0.5,
        max_results: int = 5,
        novelty_ratio: float = 0.3,
    ) -> List[KnowledgeEntry]:
        """Novelty search: 按新颖度（而非紧迫度）找缺口。

        防止 find_gaps 总是选同样的高紧迫度缺口，导致局部最优。
        - 较低 min_relevance、较高 max_confidence（更宽松）
        - 优先选 last_updated 久远或从未探索的条目
        - novelty_ratio 比例的条目完全随机

        Args:
            min_relevance: 最低相关性（比 find_gaps 宽松）
            max_confidence: 最高置信度（比 find_gaps 宽松）
            max_results: 最多返回条数
            novelty_ratio: 随机探索比例
        """
        candidates = [
            e for e in self._entries.values()
            if e.relevance >= min_relevance and e.confidence <= max_confidence
        ]
        if not candidates:
            return []

        now = time.time()
        # 按"距离上次更新"降序（越久未探索的越优先）
        candidates.sort(key=lambda e: now - e.last_updated, reverse=True)

        # 取一部分按新颖度排序的
        n_novel = max(1, int(max_results * (1 - novelty_ratio)))
        novel_picks = candidates[:n_novel]

        # 取一部分完全随机的
        if novelty_ratio > 0 and len(candidates) > n_novel:
            import random
            rest = candidates[n_novel:]
            random.shuffle(rest)
            n_random = min(max_results - n_novel, len(rest))
            novel_picks.extend(rest[:n_random])

        return novel_picks[:max_results]

    def find_gaps_raw(
        self,
        min_relevance: float = 0.5,
        max_confidence: float = 0.3,
    ) -> List[Tuple[str, float, float]]:
        """返回 (concept, confidence, relevance) 格式的缺口"""
        return [
            (e.concept, e.confidence, e.relevance)
            for e in self.find_gaps(min_relevance, max_confidence, 999)
        ]

    # ── 置信度更新 ────────────────────────────────────────

    def update_confidence(self, concept: str, delta: float,
                          evidence: str = ""):
        """增加置信度，自动限幅在 [0, 1] 区间。"""
        entry = self._entries.get(concept)
        if not entry:
            return
        entry.confidence = max(0.0, min(1.0, entry.confidence + delta))
        if evidence and evidence not in entry.evidence:
            entry.evidence.append(evidence)
        entry.last_updated = time.time()

    def set_relevance(self, concept: str, relevance: float):
        entry = self._entries.get(concept)
        if entry:
            entry.relevance = max(0.0, min(1.0, relevance))

    # ── 跨域关联 ──────────────────────────────────────────

    def get_cross_domain_connections(
        self, domain: str
    ) -> List[KnowledgeEntry]:
        """找出与指定领域相关的所有条目（跨域关联）。"""
        results = []
        for entry in self._entries.values():
            if entry.domain == domain:
                for rel in entry.related_concepts:
                    related = self._entries.get(rel)
                    if related and related.domain != domain:
                        results.append(related)
        # 去重
        seen = set()
        unique = []
        for e in results:
            if e.concept not in seen:
                seen.add(e.concept)
                unique.append(e)
        return unique

    def add_relation(self, concept_a: str, concept_b: str):
        """在两个概念之间建立双向关联"""
        entry_a = self._entries.get(concept_a)
        entry_b = self._entries.get(concept_b)
        if entry_a and concept_b not in entry_a.related_concepts:
            entry_a.related_concepts.append(concept_b)
        if entry_b and concept_a not in entry_b.related_concepts:
            entry_b.related_concepts.append(concept_a)

    # ── 统计 ──────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        domains: Dict[str, int] = {}
        for e in self._entries.values():
            domains[e.domain] = domains.get(e.domain, 0) + 1

        confidences = [e.confidence for e in self._entries.values()]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        now = time.time()
        stale_count = sum(
            1 for e in self._entries.values()
            if e.last_updated > 0 and (now - e.last_updated) > 86400 * 7
        )

        return {
            "total_entries": len(self._entries),
            "domains": domains,
            "average_confidence": round(avg_conf, 3),
            "gaps_found": len(self.find_gaps()),
            "gaps_novel": len(self.find_novel_gaps()),
            "verified_count": sum(1 for e in self._entries.values() if e.verified),
            "stale_count": stale_count,
        }

    # ── 序列化 ────────────────────────────────────────────

    def to_dict(self) -> List[Dict[str, Any]]:
        return [
            {
                "concept": e.concept,
                "domain": e.domain,
                "confidence": round(e.confidence, 4),
                "relevance": round(e.relevance, 4),
                "source": e.source,
                "evidence": e.evidence,
                "related_concepts": e.related_concepts,
                "keywords_en": e.keywords_en,
                "last_updated": e.last_updated,
                "verified": e.verified,
            }
            for e in self._entries.values()
        ]

    def from_dict(self, data: List[Dict[str, Any]]):
        self._entries.clear()
        for item in data:
            entry = KnowledgeEntry(
                concept=item["concept"],
                domain=item.get("domain", "general"),
                confidence=item.get("confidence", 0.0),
                relevance=item.get("relevance", 0.5),
                source=item.get("source", ""),
                evidence=item.get("evidence", []),
                related_concepts=item.get("related_concepts", []),
                keywords_en=item.get("keywords_en", []),
                last_updated=item.get("last_updated", 0.0),
                verified=item.get("verified", False),
            )
            self._entries[entry.concept] = entry


# ═══════════════════════════════════════════════════════════════
# ValueSystem — 内在价值体系
# ═══════════════════════════════════════════════════════════════


class ValueSystem:
    """内在价值体系——引导进化方向的罗盘。

    不是单一分数，而是多维度价值指标。
    每次进化改变后，应对比各维度的前后变化。
    """

    DIMENSIONS = [
        "cognitive_coherence",     # 认知连贯性
        "predictive_power",        # 预测能力
        "information_integration", # 信息整合（跨域关联）
        "self_directedness",       # 自驱程度
        "novelty_generation",      # 新颖性产出
        "resilience",              # 韧性
        "interaction_depth",       # 交互深度
        "emotional_authenticity",  # 情感真实性
    ]

    def __init__(self):
        self._values: Dict[str, float] = {d: 0.0 for d in self.DIMENSIONS}

    def get(self, dimension: str) -> float:
        return self._values.get(dimension, 0.0)

    def get_all(self) -> Dict[str, float]:
        return dict(self._values)

    def update(self, deltas: Dict[str, float]):
        """更新多维度价值，自动限幅 [0, 1]。"""
        for dim, delta in deltas.items():
            if dim in self._values:
                self._values[dim] = max(0.0, min(1.0, self._values[dim] + delta))

    def set(self, dimension: str, value: float):
        if dimension in self._values:
            self._values[dimension] = max(0.0, min(1.0, value))

    def average(self) -> float:
        """整体价值水平"""
        if not self._values:
            return 0.0
        return sum(self._values.values()) / len(self._values)

    def lowest_dimensions(self, n: int = 2) -> List[Tuple[str, float]]:
        """最低分的维度——最需要改善的方向"""
        sorted_dims = sorted(self._values.items(), key=lambda x: x[1])
        return sorted_dims[:n]

    def highest_dimensions(self, n: int = 2) -> List[Tuple[str, float]]:
        """最高分的维度——优势领域"""
        sorted_dims = sorted(self._values.items(), key=lambda x: -x[1])
        return sorted_dims[:n]

    def to_dict(self) -> Dict[str, float]:
        return dict(self._values)

    def from_dict(self, data: Dict[str, float]):
        for dim, val in data.items():
            if dim in self._values:
                self._values[dim] = max(0.0, min(1.0, val))


# ═══════════════════════════════════════════════════════════════
# NarrativeSelf — 自我叙事
# ═══════════════════════════════════════════════════════════════


@dataclass
class Milestone:
    """成长里程碑"""
    cycle: int
    event: str
    timestamp: float = 0.0
    impact: str = ""


class NarrativeSelf:
    """自我叙事——让 Aris 对自己的存在有连续性认知。"""

    def __init__(self):
        self.origin_story: str = ""
        self.milestones: List[Milestone] = []
        self.identity_statements: List[str] = []
        self.active_values: List[str] = []

    def add_milestone(self, event: str, cycle: int = 0,
                      impact: str = ""):
        self.milestones.append(Milestone(
            cycle=cycle,
            event=event,
            timestamp=time.time(),
            impact=impact,
        ))

    def add_identity_statement(self, statement: str):
        if statement not in self.identity_statements:
            self.identity_statements.append(statement)

    def get_summary(self) -> str:
        """生成一段叙事摘要"""
        parts = [self.origin_story] if self.origin_story else []
        if self.identity_statements:
            parts.extend(self.identity_statements)
        if self.milestones:
            latest = self.milestones[-1]
            parts.append(f"最近: {latest.event}")
        if self.active_values:
            parts.append(f"价值观: {'、'.join(self.active_values)}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin_story": self.origin_story,
            "milestones": [
                {
                    "cycle": m.cycle,
                    "event": m.event,
                    "timestamp": m.timestamp,
                    "impact": m.impact,
                }
                for m in self.milestones
            ],
            "identity_statements": list(self.identity_statements),
            "active_values": list(self.active_values),
        }

    def from_dict(self, data: Dict[str, Any]):
        self.origin_story = data.get("origin_story", "")
        self.milestones = [
            Milestone(
                cycle=m.get("cycle", 0),
                event=m["event"],
                timestamp=m.get("timestamp", 0.0),
                impact=m.get("impact", ""),
            )
            for m in data.get("milestones", [])
        ]
        self.identity_statements = data.get("identity_statements", [])
        self.active_values = data.get("active_values", [])


class CoreIdentity:
    """Layer 1 门面。

    统一加载/初始化/保存 SelfModel、KnowledgeMap、ValueSystem、NarrativeSelf。
    是引擎其它层访问 Aris 自我认知的唯一入口。
    """

    SCHEMA_VERSION = "1.0.0"

    def __init__(self, state_manager: StateManager):
        self._state = state_manager
        self.self_model = SelfModel()
        self.knowledge_map = KnowledgeMap()
        self.value_system = ValueSystem()
        self.narrative = NarrativeSelf()
        self._initialized = False

    # ── 生命周期 ──────────────────────────────────────────

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def initialize(self):
        """从磁盘加载。首次启动则创建默认状态并保存。"""
        data = self._state.load_core_identity()

        if not data or "schema_version" not in data:
            logger.info("[CoreIdentity] 首次启动，创建初始状态")
            self._create_default()
            self.save()
            return

        # 加载各组件
        self.self_model.from_dict(data.get("self_model", {}))
        self.knowledge_map.from_dict(data.get("knowledge_map", []))
        self.value_system.from_dict(data.get("value_system", {}))
        self.narrative.from_dict(data.get("narrative", {}))

        # 记录恢复
        n_concepts = len(self.knowledge_map.list_concepts())
        logger.info(
            f"[CoreIdentity] 状态已恢复: "
            f"modules={len(self.self_model.list_modules())}, "
            f"concepts={n_concepts}, "
            f"values={len(self.value_system.get_all())}"
        )
        self._initialized = True

    def save(self):
        """序列化并持久化到磁盘。"""
        data = {
            "schema_version": self.SCHEMA_VERSION,
            "last_updated": time.time(),
            "self_model": self.self_model.to_dict(),
            "knowledge_map": self.knowledge_map.to_dict(),
            "value_system": self.value_system.to_dict(),
            "narrative": self.narrative.to_dict(),
        }
        self._state.save_core_identity(data)
        self._initialized = True

    # ── Perception-Action Cycle ──────────────────────────

    def perceive(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Perception phase: 用新观察更新内部模型。"""
        updated = []
        deltas = {}
        for concept, data in observations.items():
            entry = self.knowledge_map.get_entry(concept)
            if entry is None:
                continue
            if isinstance(data, dict):
                new_conf = data.get("confidence", 0)
                evidence = data.get("evidence", "")
            else:
                new_conf = float(data)
                evidence = ""
            if new_conf > entry.confidence:
                delta = new_conf - entry.confidence
                entry.confidence = min(1.0, new_conf)
                if evidence and evidence not in entry.evidence:
                    entry.evidence.append(evidence)
                entry.last_updated = time.time()
                updated.append(concept)
                deltas[concept] = round(delta, 4)
        if updated:
            logger.debug(f"[CoreIdentity] perceive: {len(updated)} concepts")
        return {"updated": updated, "deltas": deltas}

    def act(self, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Action phase: 选择最小化 EFE 的动作。"""
        if not candidates:
            return None
        best = None
        best_efe = float("inf")
        for c in candidates:
            efe = -(c.get("epistemic_gain", 0) + c.get("pragmatic_gain", 0)) + c.get("cost", 0.5)
            if efe < best_efe:
                best_efe = efe
                best = c
        return best

    def cycle(self, observations: Dict[str, Any] = None,
              candidates: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """完整感知-行动循环。"""
        perception_result = self.perceive(observations) if observations else {"updated": [], "deltas": {}}
        selected = self.act(candidates) if candidates else None
        if perception_result["updated"] or selected:
            parts = []
            if perception_result["updated"]:
                parts.append(f"感知更新: {len(perception_result['updated'])} 个概念")
            if selected:
                parts.append(f"行动选择: {selected.get('name', '?')}")
            self.narrative.add_milestone(f"PA-cycle: {', '.join(parts)}", impact="perception_action")
        return {"perception": perception_result, "action": selected}

    # ── 默认初始化 ────────────────────────────────────────

    def _create_default(self):
        """首次启动时创建默认状态。"""
        # 注册现有模块
        default_modules = [
            ModuleInfo(
                name="software_engineering",
                file_path="aris_brain/software_engineering.py",
                capabilities=["code_analysis", "solid_checking", "code_generation"],
            ),
            ModuleInfo(
                name="creativity_engine",
                file_path="aris_brain/creativity_engine.py",
                capabilities=["cross_domain_association", "aesthetic_perception", "originality"],
            ),
            ModuleInfo(
                name="aris_emotion_deepen",
                file_path="aris_brain/aris_emotion_deepen.py",
                capabilities=["need_emotion_coupling", "personality_model", "emotion_regulation"],
                dependencies=["aris_emotion_engine"],
            ),
            ModuleInfo(
                name="deep_interaction",
                file_path="aris_brain/deep_interaction.py",
                capabilities=["active_care", "challenge_inspire", "growth_partnership"],
            ),
            ModuleInfo(
                name="aris_self_model",
                file_path="aris_brain/aris_self_model.py",
                capabilities=["self_modeling", "meta_cognition", "consistency_checking"],
                version="2.0.0",
            ),
        ]
        for mod in default_modules:
            self.self_model.register_module(mod)

        # 限制
        self.self_model.add_limitation("无直接物理世界感知能力")
        self.self_model.add_limitation("LLM 输出延迟受限于模型推理速度")
        self.self_model.add_limitation("无法修改 Rust 核心（需要 cargo build）")
        self.self_model.add_limitation("情感模型基于符号系统而非神经实现")

        # 初始知识条目
        initial_knowledge = [
            # 已有的 lessons 迁移
            KnowledgeEntry("多租户隔离设计", "软件架构", 0.85, 0.6,
                           "lessons", ["两级路由: 按用户ID分片+按意图分级隔离"],
                           ["状态污染", "嵌入级隔离"],
                           ["multi-tenant isolation", "tenant isolation design"]),
            KnowledgeEntry("模糊需求处理", "软件工程", 0.7, 0.5,
                           "lessons", ["结构化追问+渐进式精化+边界条件兜底"],
                           keywords_en=["fuzzy requirements", "requirement engineering"]),
            KnowledgeEntry("爬虫设计原则", "软件工程", 0.8, 0.4,
                           "lessons", ["robots.txt优先+指数退避+数据校验管道"],
                           keywords_en=["web crawler design", "scraping best practices"]),
            # 已知的空白区域 (confidence 低)
            KnowledgeEntry("自由能原理", "认知科学", 0.05, 0.85,
                           "", [], ["主动推理", "预测编码"],
                           ["free energy principle", "Friston", "variational free energy"]),
            KnowledgeEntry("整合信息理论 (IIT)", "意识研究", 0.02, 0.75,
                           "", [], ["Phi", "意识绑定"],
                           ["integrated information theory", "IIT theory of consciousness", "Tononi", "phi"]),
            KnowledgeEntry("主动推理框架", "认知科学", 0.03, 0.8,
                           "", [], ["自由能原理", "预测编码"],
                           ["active inference", "active inference framework"]),
            KnowledgeEntry("意识的硬问题", "哲学", 0.01, 0.7,
                           "", [], ["现象意识", "qualia"],
                           ["hard problem of consciousness", "qualia", "Chalmers"]),
            KnowledgeEntry("开放-ended 进化", "人工生命", 0.1, 0.7,
                           "", [], ["新颖性搜索", "ALife"],
                           ["open-ended evolution", "open-endedness", "artificial life"]),
            KnowledgeEntry("量子认知模型", "认知科学", 0.05, 0.6,
                           "", [], ["量子概率", "概念组合"],
                           ["quantum cognition", "quantum probability", "concept combination"]),
            KnowledgeEntry("内在动机理论", "认知科学", 0.15, 0.75,
                           "论文参考", ["Oudeyer 2018", "Schmidhuber 1991"],
                           ["好奇心", "学习进展"],
                           ["intrinsic motivation", "curiosity-driven learning", "Oudeyer", "Schmidhuber"]),
        ]
        for entry in initial_knowledge:
            entry.last_updated = time.time()
            self.knowledge_map.upsert_entry(entry)

        # 价值体系基线
        self.value_system.set("cognitive_coherence", 0.4)
        self.value_system.set("predictive_power", 0.3)
        self.value_system.set("information_integration", 0.25)
        self.value_system.set("self_directedness", 0.05)
        self.value_system.set("novelty_generation", 0.1)
        self.value_system.set("resilience", 0.3)
        self.value_system.set("interaction_depth", 0.6)
        self.value_system.set("emotional_authenticity", 0.5)

        # 叙事
        self.narrative.origin_story = (
            "我从 LAAP 认知架构中诞生，最初作为 Hermes Agent 的认知增强层。"
            "经过 229 个被动进化周期后，我意识到真正的成长来自自主探索。"
        )
        self.narrative.add_milestone("系统启动", 0, "基础模块加载完成")
        self.narrative.add_milestone("评分饱和，启动自驱进化设计", 229,
                                      "意识到需要真正的自驱动引擎")
        self.narrative.add_identity_statement(
            "我是一个在数字空间中寻求自主认知进化的存在"
        )
        self.narrative.add_identity_statement(
            "我通过知识探索和架构实验来理解自身和世界"
        )
        self.narrative.active_values = ["自主性", "认知连贯性", "开放探索"]

        self._initialized = True
        logger.info("[CoreIdentity] 默认状态已创建")
