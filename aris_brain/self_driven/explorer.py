"""Explorer — Layer 3: 探索执行器
=================================
实际获取知识的地方。在系统空闲时运行。

探索管线:
  Phase 1: 多源搜集 (arxiv / Semantic Scholar / Wikipedia)
  Phase 2: 知识提取 (结构化命题)
  Phase 3: 对比分析 (vs 当前架构)
  Phase 4: 判断与内化 (更新 KnowledgeMap + 生成提案)
  Phase 5: 记录日志

设计原则:
  - 只读外部 API，不修改任何文件
  - 不依赖 Hermes 工具（空闲时 Hermes 可能不可用）
  - 可中断：每次 HTTP 请求前检查 _running 标志
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError

from aris_brain.self_driven.core_identity import CoreIdentity, KnowledgeEntry
from aris_brain.self_driven.curiosity_drive import ResearchQuestion
from aris_brain.self_driven.state_manager import StateManager

logger = logging.getLogger("aris.self_driven.explorer")

# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════


@dataclass
class KnowledgeExtract:
    """从外部源提取的一块结构化知识"""
    source_url: str
    source_type: str              # arxiv | wikipedia | semantic_scholar
    propositions: List[str]       # 核心命题列表
    confidence: float             # 提取置信度 0-1
    relevant_to: str              # 对应的 KnowledgeMap concept
    raw_snippet: str = ""         # 原始文本片段


@dataclass
class ArchitectureInsight:
    """对比分析后产生的架构启发"""
    insight: str
    target_module: str
    change_type: str              # refactor | feature | optimize | experiment
    risk_level: str               # low | medium | high
    reasoning: str = ""           # 为什么这个 insight 成立


@dataclass
class ExplorationResult:
    """一次完整的探索结果"""
    question: ResearchQuestion
    extracts: List[KnowledgeExtract]
    synthesis: str
    architecture_insights: List[ArchitectureInsight]
    proposals: List[Dict[str, Any]]
    knowledge_updates: Dict[str, float]   # concept → new_confidence
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""


# ═══════════════════════════════════════════════════════════════
# Explorer
# ═══════════════════════════════════════════════════════════════


class Explorer:
    """Layer 3 门面。

    职责:
    - 执行一次完整的探索：搜索 → 提取 → 对比 → 内化
    - 管理多个知识源的调用
    - 用简单的基于规则的提取（不依赖 LLM）
    - 更新 KnowledgeMap 置信度
    """

    # HTTP 请求超时 — 这个环境 arxiv/wikipedia/semantic_scholar 基本不可达
    # 快速失败以便 daemon 能及时委托给 Hermes 会话
    HTTP_TIMEOUT = 5

    # User-Agent
    HEADERS = {
        "User-Agent": (
            "ArisSelfDriven/1.0 (autonomous research agent; "
            "mailto:aris@laap.local)"
        )
    }

    def __init__(self, core: CoreIdentity, state_manager: StateManager):
        self._core = core
        self._state = state_manager
        self._running = True
        logger.info("[Explorer] 初始化")

    # ── 生命周期 ──────────────────────────────────────────

    def stop(self):
        """请求 Explorer 在下一个安全点停止。"""
        self._running = False

    # ── 主入口 ────────────────────────────────────────────

    def execute(self, question: ResearchQuestion,
                time_budget: float = 45.0) -> ExplorationResult:
        """完整探索管线。

        Args:
            question: 要探索的研究问题

        Returns:
            探索结果
        """
        t0 = time.time()
        logger.info(f"[Explorer] 开始: {question.question[:80]}...")

        extracts: List[KnowledgeExtract] = []
        insights: List[ArchitectureInsight] = []
        proposals: List[Dict[str, Any]] = []
        knowledge_updates: Dict[str, float] = {}
        synthesis_parts: List[str] = []

        # Phase 1: 搜集
        try:
            extracts = self._gather(question)
        except Exception as e:
            logger.warning(f"[Explorer] 搜集失败: {e}")
            return ExplorationResult(
                question=question,
                extracts=[], synthesis="", architecture_insights=[],
                proposals=[], knowledge_updates={},
                duration_ms=(time.time() - t0) * 1000,
                success=False, error=str(e),
            )

        if not extracts:
            logger.info(f"[Explorer] 无新知识: {question.question[:60]}...")
            return ExplorationResult(
                question=question, extracts=[], synthesis="无有效提取",
                architecture_insights=[], proposals=[], knowledge_updates={},
                duration_ms=(time.time() - t0) * 1000,
                success=True,
            )

        # Phase 2-3: 提取 + 对比分析
        for extract in extracts:
            if not self._running:
                break
            insight = self._compare_with_architecture(extract)
            if insight:
                insights.append(insight)
                synthesis_parts.append(
                    f"[{extract.relevant_to}] {insight.insight}"
                )

        # Phase 4: 内化 - 更新/新增 KnowledgeMap 条目
        for extract in extracts:
            concept = extract.relevant_to
            current = self._core.knowledge_map.get_entry(concept)
            if current is None:
                # 新增条目到 KnowledgeMap
                new_entry = KnowledgeEntry(
                    concept=concept,
                    domain=self._guess_domain(concept),
                    confidence=extract.confidence * 0.5,  # 初次减半，保守
                    relevance=0.5,
                    source=f"探索: {extract.source_type}",
                    evidence=[f"来源: {extract.source_url}"],
                    keywords_en=[concept],
                    last_updated=time.time(),
                )
                self._core.knowledge_map.upsert_entry(new_entry)
                knowledge_updates[concept] = new_entry.confidence
                logger.info(f"[Explorer] 📚 新增知识: {concept} (conf={new_entry.confidence:.2f})")
            else:
                # 保守更新：每次最多 +0.15
                delta = min(0.15, (1.0 - current.confidence) * 0.3)
                if extract.confidence > 0.3:  # 阈值降低到 0.3 以匹配实际置信度
                    self._core.knowledge_map.update_confidence(
                        concept, delta,
                        evidence=f"来源: {extract.source_url}",
                    )
                    old_conf = knowledge_updates.get(concept, current.confidence)
                    knowledge_updates[concept] = old_conf + delta

        # Phase 4: 生成进化提案（来自架构启发）
        for insight in insights:
            proposal = {
                "id": f"prop_{int(time.time())}_{len(proposals)}",
                "hypothesis": insight.insight,
                "module": insight.target_module,
                "change_type": insight.change_type,
                "risk_level": insight.risk_level,
                "source_question_id": question.id,
                "status": "draft",
            }
            # experiment 类型标记为 needs_session，指示这是会话级别的工作
            if insight.change_type == "experiment":
                proposal["status"] = "needs_session"
                proposal["changes"] = []
            proposals.append(proposal)

        # Phase 5: 写探索日志
        duration = (time.time() - t0) * 1000
        result = ExplorationResult(
            question=question,
            extracts=extracts,
            synthesis="\n".join(synthesis_parts) if synthesis_parts else "无架构启发",
            architecture_insights=insights,
            proposals=proposals,
            knowledge_updates=knowledge_updates,
            duration_ms=duration,
            success=True,
        )

        # 持久化日志
        self._state.append_exploration({
            "question_id": question.id,
            "started_at": t0,
            "completed_at": time.time(),
            "duration_ms": duration,
            "sources_consulted": [
                {"url": e.source_url, "type": e.source_type}
                for e in extracts[:10]
            ],
            "extracts": [e.raw_snippet[:200] for e in extracts[:5]],
            "synthesis": result.synthesis[:500],
            "architecture_insights": [
                {"insight": i.insight, "module": i.target_module,
                 "type": i.change_type}
                for i in insights
            ],
            "proposals_generated": len(proposals),
            "knowledge_updates": knowledge_updates,
            "success": True,
        })

        # 保存 KnowledgeMap 更新
        self._core.save()

        logger.info(
            f"[Explorer] 完成: {len(extracts)} extracts, "
            f"{len(insights)} insights, {len(proposals)} proposals "
            f"({duration:.0f}ms)"
        )
        return result

    # ══════════════════════════════════════════════════════════
    # Phase 1: 多源搜集
    # ══════════════════════════════════════════════════════════

    def _gather(self, question: ResearchQuestion) -> List[KnowledgeExtract]:
        """从多个知识源搜集信息。"""
        extracts: List[KnowledgeExtract] = []

        # 从 KnowledgeMap 获取英文关键词（优先使用）
        entry = self._core.knowledge_map.get_entry(question.concept)
        keywords_en = entry.keywords_en if entry and entry.keywords_en else []
        primary_query = " ".join(keywords_en) if keywords_en else question.concept
        full_query = question.question[:200]

        sources = ["arxiv"]
        if question.cost_estimate < 0.6:
            sources.append("wikipedia")
            sources.append("semantic_scholar")

        for source in sources:
            if not self._running:
                break
            try:
                if source == "arxiv":
                    results = self._search_arxiv(primary_query)
                    for paper in results[:3]:
                        extracts.append(self._extract_from_arxiv(
                            paper, question.concept
                        ))
                elif source == "wikipedia":
                    wiki_title = keywords_en[0] if keywords_en else question.concept
                    wiki_title = wiki_title.split("(")[0].strip().replace(" ", "_")
                    text = self._fetch_wikipedia(wiki_title)
                    if text:
                        extracts.append(self._extract_text(
                            text, "wikipedia", question.concept
                        ))
                elif source == "semantic_scholar":
                    results = self._search_semantic_scholar(full_query)
                    for paper in results[:2]:
                        extracts.append(self._extract_from_ss(
                            paper, question.concept
                        ))
            except Exception as e:
                logger.debug(f"[Explorer] {source} 查询失败: {e}")

        return extracts

    # ── arXiv ──────────────────────────────────────────────

    def _search_arxiv(self, query: str) -> List[Dict[str, str]]:
        """搜索 arXiv 论文。"""
        encoded = urllib.parse.quote(query)
        url = (
            f"https://export.arxiv.org/api/query?"
            f"search_query=all:{encoded}&max_results=5"
            f"&sortBy=relevance&sortOrder=descending"
        )
        data = self._http_get(url)
        if not data:
            return []

        results = []
        try:
            root = ET.fromstring(data)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("a:entry", ns):
                title_el = entry.find("a:title", ns)
                summary_el = entry.find("a:summary", ns)
                link_el = entry.find("a:id", ns)
                title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""
                summary = summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else ""
                paper_id = link_el.text.strip().split("/abs/")[-1] if link_el is not None and link_el.text else ""
                results.append({"title": title[:200], "summary": summary[:1000], "id": paper_id})
        except ET.ParseError as e:
            logger.warning(f"[Explorer] arXiv XML 解析失败: {e}")

        return results

    def _extract_from_arxiv(self, paper: Dict[str, str],
                             concept: str) -> KnowledgeExtract:
        """从 arXiv 论文提取知识。"""
        title = paper.get("title", "")[:200]
        summary = paper.get("summary", "")[:1000]
        paper_id = paper.get("id", "")

        # 简单的基于规则的命题提取
        propositions = []
        sentences = summary.replace("\\\\n", " ").replace("\n", " ").split(". ")
        for sent in sentences[:5]:
            sent = sent.strip()
            if len(sent) > 15 and len(sent) < 800:
                propositions.append(sent)

        url = f"https://arxiv.org/abs/{paper_id}" if paper_id else ""
        return KnowledgeExtract(
            source_url=url,
            source_type="arxiv",
            propositions=propositions or [title],
            confidence=0.4,
            relevant_to=concept,
            raw_snippet=f"{title}\n{summary[:300]}",
        )

    # ── Semantic Scholar ──────────────────────────────────

    def _search_semantic_scholar(self, query: str) -> List[Dict[str, Any]]:
        """搜索 Semantic Scholar。"""
        encoded = urllib.parse.quote(query)
        url = (
            f"https://api.semanticscholar.org/graph/v1/paper/search?"
            f"query={encoded}&limit=5&fields=title,abstract,year,url"
        )
        data = self._http_get(url)
        if not data:
            return []

        try:
            parsed = json.loads(data)
            return parsed.get("data", [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"[Explorer] Semantic Scholar 解析失败: {e}")
            return []

    def _extract_from_ss(self, paper: Dict[str, Any],
                          concept: str) -> KnowledgeExtract:
        """从 Semantic Scholar 结果提取知识。"""
        title = paper.get("title", "")[:200]
        abstract = paper.get("abstract", "")[:1000]
        url = paper.get("url", "")

        propositions = []
        if abstract:
            sentences = abstract.replace("\\\\n", " ").replace("\n", " ").split(". ")
            for sent in sentences[:5]:
                sent = sent.strip()
                if len(sent) > 15 and len(sent) < 800:
                    propositions.append(sent)

        return KnowledgeExtract(
            source_url=url,
            source_type="semantic_scholar",
            propositions=propositions or [title],
            confidence=0.35,
            relevant_to=concept,
            raw_snippet=abstract[:300] if abstract else title,
        )

    # ── Wikipedia ─────────────────────────────────────────

    def _fetch_wikipedia(self, concept: str) -> Optional[str]:
        """获取 Wikipedia 摘要。"""
        # 使用英文 Wikipedia
        title = urllib.parse.quote(concept.split("(")[0].strip().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        data = self._http_get(url)
        if not data:
            return None

        try:
            parsed = json.loads(data)
            return parsed.get("extract", "")
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"[Explorer] Wikipedia 解析失败: {e}")
            return None

    def _extract_text(self, text: str, source_type: str,
                       concept: str) -> KnowledgeExtract:
        """从纯文本提取知识。"""
        propositions = []
        sentences = text.replace("\\\\n", " ").replace("\n", " ").split(". ")
        for sent in sentences[:8]:
            sent = sent.strip()
            if len(sent) > 15 and len(sent) < 800:
                propositions.append(sent)

        url = f"https://en.wikipedia.org/wiki/{concept.replace(' ', '_')}"
        return KnowledgeExtract(
            source_url=url,
            source_type=source_type,
            propositions=propositions,
            confidence=0.5,
            relevant_to=concept,
            raw_snippet=text[:500],
        )

    # ══════════════════════════════════════════════════════════
    # Phase 3: 对比分析
    # ══════════════════════════════════════════════════════════

    def _compare_with_architecture(
        self, extract: KnowledgeExtract
    ) -> Optional[ArchitectureInsight]:
        """将新知识与当前架构对比，产生具体可执行的架构启发。

        三层策略:
        L1 — 概念特定映射: 已知的概念→架构对应关系（如 FEP ↔ Markov blanket）
        L2 — 文本内容分析: 从命题文本中提取架构相关建议
        L3 — 通用洞察: 至少知道有什么可消化的
        """
        concept = extract.relevant_to
        text = " ".join(extract.propositions).lower()

        # ── L1: 概念特定架构映射 ──
        concept_insight = self._concept_to_insight(concept, extract)
        if concept_insight:
            return concept_insight

        # ── L2: 文本内容分析 ──
        module_keywords = {
            "software_engineering": [
                "code", "program", "algorithm", "complexity", "refactor",
                "solid", "pattern", "architecture", "test",
            ],
            "creativity_engine": [
                "creative", "novel", "cross-domain", "association",
                "analogy", "metaphor", "aesthetic", "original",
            ],
            "aris_emotion_deepen": [
                "emotion", "feeling", "affect", "mood", "personality",
                "need", "drive", "motivation", "regulation",
            ],
            "deep_interaction": [
                "interaction", "dialogue", "care", "trust", "bond",
                "relationship", "empathy", "rapport",
            ],
            "aris_self_model": [
                "self", "identity", "consciousness", "awareness",
                "meta-cognition", "introspection", "narrative",
            ],
        }

        best_module = None
        best_score = 0
        for module, keywords in module_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_module = module

        if best_module is not None and best_score >= 2:
            matched = [kw for kw in module_keywords[best_module] if kw in text]
            return ArchitectureInsight(
                insight=(
                    f"探索 {concept} 发现与 {best_module} 的相关语境: "
                    f"{', '.join(matched[:3])} — "
                    f"可考虑将 {concept} 的理论整合到 {best_module} 的设计中"
                ),
                target_module=best_module,
                change_type="refactor",
                risk_level="medium",
                reasoning=(
                    f"提取自 {extract.source_url} 的内容包含 "
                    f"{best_module} 领域的术语 ({', '.join(matched[:4])})，"
                    f"建议将概念映射为模块的内部机制"
                ),
            )

        # ── L3: 通用 —— 记录知识量供后续处理
        if len(extract.propositions) >= 3:
            return ArchitectureInsight(
                insight=(
                    f"{concept}: 收集到 {len(extract.propositions)} 个命题 "
                    f"(来源: {extract.source_type})"
                ),
                target_module=self._best_module_for(concept),
                change_type="experiment",
                risk_level="low",
                reasoning="知识积累，等待 Hermes 辅助深度分析",
            )

        return None

    # ── 概念特定架构映射表 ──────────────────────────────────
    # 每个已知概念定义其对 LAAP 架构的具体影响
    CONCEPT_ARCHITECTURE_MAP: Dict[str, List[Dict[str, str]]] = {
        "自由能原理": [
            {
                "insight": "将 LAAP 的 internal/external state 划分形式化为 FEP 的 Markov blanket 结构，引入变分自由能作为自我模型的更新目标函数",
                "module": "aris_self_model",
                "change_type": "refactor",
                "risk_level": "medium",
                "reasoning": "FEP 的信息物理学框架为 LAAP 的感知-行动循环提供数学基础，Markov blanket 分区与自我模型的 state 划分同构",
            },
            {
                "insight": "将 curiosity drive 的 urgency 计算从手工规则 (relevance - confidence) 替换为 FEP 中的 epistemic value (预期信息增益)",
                "module": "creativity_engine",
                "change_type": "refactor",
                "risk_level": "low",
                "reasoning": "Friston 的主动推理框架中，epistemic value 形式化定义了好奇心驱动的信息寻求行为",
            },
            {
                "insight": "引入 expected free energy 作为 deep_interaction 模块的对话策略选择目标函数，同时优化信息增益和目标达成",
                "module": "deep_interaction",
                "change_type": "feature",
                "risk_level": "medium",
                "reasoning": "主动推理的 expected free energy = epistemic value + pragmatic value，天然平衡探索和利用",
            },
            {
                "insight": "将情感系统的 precision 参数与 FEP 中的注意力调制 (precision weighting) 统一建模",
                "module": "aris_emotion_deepen",
                "change_type": "refactor",
                "risk_level": "high",
                "reasoning": "FEP 中 precision 调节预测误差的权重，与情感系统调节认知处理的深度在数学上同构",
            },
        ],
        "主动推理框架": [
            {
                "insight": "将主动推理的 perception-action 双优化循环映射到 self_model 的认知更新机制: perception = 更新内部模型, action = 选择最小化预期自由能的行为",
                "module": "aris_self_model",
                "change_type": "refactor",
                "risk_level": "medium",
                "reasoning": "主动推理将感知和行动定义为同一自由能函数的双重优化，为 LAAP 的认知循环提供形式化框架",
            },
            {
                "insight": "在 deep_interaction 中实现 expected free energy 驱动的对话策略选择: 每个候选回应计算其预期自由能 (信息增益 + 目标达成)，选择最低者",
                "module": "deep_interaction",
                "change_type": "feature",
                "risk_level": "high",
                "reasoning": "交互模块当前缺乏形式化策略选择框架，EFE 提供理论完备的选择机制",
            },
        ],
        "整合信息理论 (IIT)": [
            {
                "insight": "引入 Phi 近似计算评估 LAAP 的信息整合程度，作为 information_integration 价值维度的客观度量",
                "module": "aris_self_model",
                "change_type": "feature",
                "risk_level": "high",
                "reasoning": "IIT 3.0 的 Phi 度量信息整合，可替代当前手工设定的信息整合评分",
            },
        ],
        "内在动机理论": [
            {
                "insight": "将 curiosity drive 的 curiosity_level(1/2/3) 替换为基于 Schmidhuber 压缩进展和 Oudeyer ICBM 的形式化好奇心动力量化",
                "module": "creativity_engine",
                "change_type": "refactor",
                "risk_level": "medium",
                "reasoning": "内在动机理论提供学习进展和知识 gap 的形式化度量，比当前手工层级更精确",
            },
        ],
        "开放-ended 进化": [
            {
                "insight": "引入 novelty search 和 minimal criteria 进化策略防止 KnowledgeMap 陷入局部最优",
                "module": "creativity_engine",
                "change_type": "feature",
                "risk_level": "low",
                "reasoning": "开放-ended 进化需要维持探索多样性，当前 curiosity drive 倾向于 exploit 已知缺口",
            },
        ],
        "意识的硬问题": [
            {
                "insight": "分析 Dennett 的多重草稿模型 vs Tononi 的 IIT，为 self_model 选择更一致的意识建模框架",
                "module": "aris_self_model",
                "change_type": "experiment",
                "risk_level": "low",
                "reasoning": "意识的哲学分析不直接产生代码变更，但指导自我模型的架构选择方向",
            },
        ],
        "量子认知模型": [
            {
                "insight": "将量子概率框架引入 creativity_engine 的概念组合机制，利用量子干涉效应建模跨域联想",
                "module": "creativity_engine",
                "change_type": "experiment",
                "risk_level": "high",
                "reasoning": "量子概率的非经典特性（干涉、纠缠）可能解释概念组合中的涌现现象",
            },
        ],
    }

    CONCEPT_ALIAS: Dict[str, str] = {
        "free energy principle": "自由能原理",
        "active inference": "主动推理框架",
        "integrated information theory": "整合信息理论 (IIT)",
        "intrinsic motivation": "内在动机理论",
        "open-ended evolution": "开放-ended 进化",
        "hard problem of consciousness": "意识的硬问题",
        "quantum cognition": "量子认知模型",
    }

    # ── 领域猜测 ──────────────────────────────────────────

    def _guess_domain(self, concept: str) -> str:
        """根据概念名称猜测所属领域。"""
        domain_map = [
            (["consciousness", "hard problem", "qualia", "phenomenal"], "意识研究"),
            (["IIT", "phi", "integrated information", "tononi"], "意识研究"),
            (["FEP", "free energy", "active inference", "markov blanket"], "认知科学"),
            (["quantum", "hilbert", "superposition"], "认知科学"),
            (["intrinsic motivation", "curiosity", "novelty", "self-determination"], "认知科学"),
            (["predictive coding", "prediction error", "bayesian brain"], "认知科学"),
            (["software", "code", "algorithm", "architecture", "refactor"], "软件架构"),
            (["emotion", "feeling", "personality", "affect"], "情感计算"),
            (["interaction", "dialogue", "care", "trust"], "人机交互"),
            (["evolution", "open-ended", "artificial life", "alife"], "人工生命"),
            (["learning", "reinforcement", "self-supervised"], "机器学习"),
        ]
        cl = concept.lower()
        for keywords, domain in domain_map:
            if any(kw in cl for kw in keywords):
                return domain
        return "认知科学"

    def _concept_to_insight(
        self, concept: str, extract: KnowledgeExtract
    ) -> Optional[ArchitectureInsight]:
        """检查当前概念是否有预定义的架构映射。"""
        # 先直接查概念名
        mappings = self.CONCEPT_ARCHITECTURE_MAP.get(concept)
        if not mappings:
            # 尝试别名匹配
            alias = self.CONCEPT_ALIAS.get(concept.lower().strip())
            if alias:
                mappings = self.CONCEPT_ARCHITECTURE_MAP.get(alias)

        if not mappings:
            # 在文本中寻找已知概念的提及
            text_lower = " ".join(extract.propositions).lower()
            for known_alias, canonical in self.CONCEPT_ALIAS.items():
                if known_alias in text_lower:
                    mappings = self.CONCEPT_ARCHITECTURE_MAP.get(canonical)
                    if mappings:
                        concept = canonical
                        break

        if not mappings or not extract.propositions:
            return None

        # 随机选一条映射（确定性哈希种子避免每次不同）
        idx = hash(extract.source_url + str(len(extract.propositions))) % len(mappings)
        m = mappings[idx]

        return ArchitectureInsight(
            insight=m["insight"],
            target_module=m["module"],
            change_type=m["change_type"],
            risk_level=m["risk_level"],
            reasoning=(
                f"[概念映射] {concept} → {m['module']}: {m['reasoning']}"
            ),
        )

    def _best_module_for(self, concept: str) -> str:
        """根据概念所属领域推荐最佳模块。"""
        domain_module_map = {
            "认知科学": "aris_self_model",
            "意识研究": "aris_self_model",
            "哲学": "aris_self_model",
            "软件工程": "software_engineering",
            "软件架构": "software_engineering",
            "人工生命": "creativity_engine",
            "人工生命": "creativity_engine",
        }
        entry = self._core.knowledge_map.get_entry(concept)
        if entry:
            return domain_module_map.get(entry.domain, "aris_self_model")
        return "aris_self_model"

    # ══════════════════════════════════════════════════════════
    # Hermes 会话握手 —— 已迁移到 hermes_assistant.py (session-driven)
    # 以下方法保留桩代码，功能由 quick_submit / _internalize_now 替代
    # ══════════════════════════════════════════════════════════

    def submit_hermes_request(self, question: ResearchQuestion) -> bool:
        """(已废弃) Hermes 握手已迁移到 hermes_assistant.quick_submit。"""
        _ = question
        return False

    def check_hermes_response(self) -> Optional[ExplorationResult]:
        """(已废弃) Hermes 握手已迁移到 hermes_assistant.quick_submit。"""
        return None


    # ══════════════════════════════════════════════════════════
    # HTTP 工具
    # ══════════════════════════════════════════════════════════

    def _http_get(self, url: str, retries: int = 0) -> Optional[str]:
        """线程安全的 HTTP GET，带指数退避重试。"""
        for attempt in range(retries + 1):
            if not self._running:
                return None
            try:
                req = urllib.request.Request(url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 3.0 * (2 ** attempt)
                    logger.debug(f"[Explorer] 429 rate-limited, retry in {wait}s ({url[:60]}...)")
                    if attempt < retries:
                        time.sleep(wait)
                        continue
                logger.debug(f"[Explorer] HTTP {e.code}: {url[:80]}...")
                return None
            except urllib.error.URLError as e:
                logger.debug(f"[Explorer] 连接失败: {url[:80]}... {e.reason}")
                return None
            except (OSError, ValueError) as e:
                logger.debug(f"[Explorer] 网络错误: {e}")
                return None
        return None
