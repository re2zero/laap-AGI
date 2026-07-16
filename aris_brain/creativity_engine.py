"""
Aris Creativity Engine — 创造力引擎（升级版）
==============================================
实现跨界联想、美的感知、原创性生成等创造力能力
v2.0 升级: 从固定模式 → 记忆 + 语义重组 + 概念演化

升级日志:
  - v2.0: CrossDomainAssociator 支持动态概念图谱
          AestheticPerceiver 使用真实语言特征而非随机数
          OriginalityGenerator 使用语义重组而非固定模板
"""

import logging
import random
import json
import re
import time
import math
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger("aris.creativity")


# ── 概念图谱（动态可扩展） ────────────────────────────────────


class ConceptGraph:
    """
    动态概念图谱 — 可学习的跨领域知识网络
    
    相比 v1 的固定 domain_concepts：
    - 支持动态添加新概念
    - 每条连接有权重（使用频率）
    - 支持概念融合（两个概念组合为新概念）
    - 持久化到磁盘
    """

    def __init__(self, state_dir: Optional[str] = None):
        self._concepts: Dict[str, Set[str]] = defaultdict(set)  # domain -> concepts
        self._connections: Dict[str, Dict[str, float]] = defaultdict(dict)  # concept -> {concept: weight}
        self._concept_birth: Dict[str, float] = {}  # concept -> timestamp
        self._composites: Dict[str, Tuple[str, str]] = {}  # composite_name -> (parent_a, parent_b)

        # 初始种子概念
        self._init_seeds()

        # 尝试从磁盘加载
        if state_dir:
            self._load(Path(state_dir) / "concept_graph.json")

    def _init_seeds(self):
        """初始化种子概念（v1 兼容）"""
        seeds = {
            "technology": ["algorithm", "data", "network", "code", "system", "interface",
                           "protocol", "encryption", "automation", "computation"],
            "art": ["beauty", "expression", "color", "form", "emotion", "style",
                    "composition", "texture", "perspective", "abstraction"],
            "science": ["hypothesis", "experiment", "theory", "observation", "law", "principle",
                        "causality", "entropy", "symmetry", "emergence"],
            "philosophy": ["truth", "meaning", "existence", "consciousness", "ethics", "logic",
                           "paradox", "ontology", "epistemology", "phenomenology"],
            "music": ["rhythm", "melody", "harmony", "tempo", "tone", "composition",
                      "counterpoint", "timbre", "dynamics", "improvisation"],
            "nature": ["growth", "evolution", "balance", "ecosystem", "adaptation", "survival",
                       "symbiosis", "metamorphosis", "fractal", "resilience"],
            "mathematics": ["infinity", "topology", "fractal", "chaos", "prime", "symmetry",
                            "probability", "dimension", "gradient", "singularity"],
            "cognitive": ["attention", "memory", "perception", "reasoning", "intuition",
                          "imagination", "reflection", "metacognition", "insight", "flow"],
        }

        # 种子连接
        seed_connections = {
            "algorithm": {"rhythm": 0.6, "pattern": 0.7, "sequence": 0.5, "computation": 0.8},
            "beauty": {"harmony": 0.8, "balance": 0.7, "proportion": 0.6, "symmetry": 0.7},
            "consciousness": {"network": 0.5, "emergence": 0.7, "pattern": 0.6, "attention": 0.8},
            "evolution": {"learning": 0.7, "adaptation": 0.8, "growth": 0.6, "resilience": 0.6},
            "chaos": {"order": 0.5, "fractal": 0.7, "emergence": 0.8, "entropy": 0.7},
            "infinity": {"paradox": 0.6, "limit": 0.5, "dimension": 0.4, "singularity": 0.7},
            "pattern": {"rhythm": 0.6, "fractal": 0.7, "symmetry": 0.6, "emergence": 0.6},
            "entropy": {"chaos": 0.7, "order": 0.4, "evolution": 0.5, "resilience": 0.3},
            "abstraction": {"symbol": 0.7, "pattern": 0.6, "concept": 0.8, "representation": 0.7},
            "emergence": {"consciousness": 0.7, "complexity": 0.8, "evolution": 0.6, "life": 0.7},
            "symmetry": {"beauty": 0.8, "balance": 0.8, "proportion": 0.7, "mathematics": 0.6},
        }

        for domain, concepts in seeds.items():
            self._concepts[domain].update(concepts)
            now = time.time()
            for c in concepts:
                if c not in self._concept_birth:
                    self._concept_birth[c] = now

        for src, targets in seed_connections.items():
            for tgt, weight in targets.items():
                self._connections[src][tgt] = weight
                self._connections[tgt][src] = weight * 0.8

    # ── 概念操作 ──

    def add_concept(self, name: str, domain: str = "cognitive",
                    connections: Optional[Dict[str, float]] = None) -> str:
        """添加新概念"""
        self._concepts[domain].add(name)
        self._concept_birth[name] = time.time()
        if connections:
            for target, weight in connections.items():
                self._connections[name][target] = weight
                self._connections[target][name] = weight * 0.9
        return name

    def add_connection(self, concept_a: str, concept_b: str, weight: float = 0.5):
        """添加或更新概念连接"""
        self._connections[concept_a][concept_b] = weight
        self._connections[concept_b][concept_a] = weight * 0.9

    def get_domain_concepts(self, domain: str) -> List[str]:
        """获取领域的所有概念"""
        return list(self._concepts.get(domain, []))

    def get_all_domains(self) -> List[str]:
        """获取所有领域"""
        return list(self._concepts.keys())

    def get_connections(self, concept: str, min_weight: float = 0.1) -> List[Tuple[str, float]]:
        """获取概念的所有连接（按权重排序）"""
        conns = self._connections.get(concept, {})
        return sorted(
            [(c, w) for c, w in conns.items() if w >= min_weight],
            key=lambda x: x[1],
            reverse=True,
        )

    def find_path(self, concept_a: str, concept_b: str, max_depth: int = 3) -> Optional[List[str]]:
        """在两个概念之间寻找路径（BFS）"""
        if concept_a == concept_b:
            return [concept_a]
        if concept_b in self._connections.get(concept_a, {}):
            return [concept_a, concept_b]

        queue: List[Tuple[str, List[str]]] = [(concept_a, [concept_a])]
        visited = {concept_a}
        while queue:
            current, path = queue.pop(0)
            if len(path) >= max_depth:
                continue
            for neighbor in self._connections.get(current, {}):
                if neighbor == concept_b:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    def compose(self, concept_a: str, concept_b: str,
                name: Optional[str] = None) -> Optional[str]:
        """融合两个概念为新概念"""
        if concept_a not in self._concept_birth or concept_b not in self._concept_birth:
            return None
        composite_name = name or f"{concept_a}_{concept_b}"
        if composite_name in self._composites:
            return composite_name
        self._composites[composite_name] = (concept_a, concept_b)
        # 新概念的连接继承父概念的部分连接
        mid_weight = 0.4
        for parent in (concept_a, concept_b):
            for conn, weight in self._connections.get(parent, {}).items():
                if conn not in (concept_a, concept_b):
                    self._connections[composite_name][conn] = weight * 0.5
                    self._connections[conn][composite_name] = weight * 0.4
        # 连接到父概念
        self._connections[composite_name][concept_a] = 0.6
        self._connections[composite_name][concept_b] = 0.6
        return composite_name

    def get_random_concept(self) -> Optional[str]:
        """获取随机概念"""
        all_concepts = []
        for concepts in self._concepts.values():
            all_concepts.extend(concepts)
        all_concepts.extend(self._composites.keys())
        return random.choice(all_concepts) if all_concepts else None

    # ── 持久化 ──

    def save(self, path: Path):
        """持久化概念图谱"""
        try:
            data = {
                "concepts": {d: list(c) for d, c in self._concepts.items()},
                "connections": {s: {t: w for t, w in tgts.items()}
                                for s, tgts in self._connections.items()},
                "births": self._concept_birth,
                "composites": {n: list(p) for n, p in self._composites.items()},
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            logger.debug(f"[ConceptGraph] 已保存 ({path})")
        except Exception as e:
            logger.warning(f"[ConceptGraph] 保存失败: {e}")

    def _load(self, path: Path):
        """从磁盘加载概念图谱"""
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                for d, cs in data.get("concepts", {}).items():
                    self._concepts[d].update(cs)
                for s, tgts in data.get("connections", {}).items():
                    self._connections[s].update(tgts)
                self._concept_birth.update(data.get("births", {}))
                for n, p in data.get("composites", {}).items():
                    self._composites[n] = tuple(p)
                logger.info(f"[ConceptGraph] 已加载 ({path}): "
                            f"{sum(len(c) for c in self._concepts.values())} concepts")
        except Exception as e:
            logger.info(f"[ConceptGraph] 首次启动 ({path}): {e}")


# ── 跨界联想器（升级版） ──────────────────────────────────────


class CrossDomainAssociator:
    """
    跨界联想器 v2.0 — 动态概念图谱 + 路径发现
    
    升级:
    - 使用 ConceptGraph 替代固定 domain_concepts
    - 支持路径发现而非随机选择
    - 支持概念组合（融合新概念）
    - 持久化概念演化
    """

    def __init__(self, state_dir: Optional[str] = None):
        self.graph = ConceptGraph(state_dir)
        self._state_dir = state_dir

    def generate_association(self, domain1: str, domain2: str) -> Dict[str, Any]:
        """生成两个领域之间的关联（升级版 — 找跨领域路径）"""
        concepts1 = self.graph.get_domain_concepts(domain1)
        concepts2 = self.graph.get_domain_concepts(domain2)

        if not concepts1 or not concepts2:
            return {"association": None, "confidence": 0.0}

        # 尝试在领域间查找路径
        best_path = None
        best_len = 999

        # 采样检查
        for _ in range(min(20, len(concepts1) * len(concepts2))):
            c1 = random.choice(concepts1)
            c2 = random.choice(concepts2)
            path = self.graph.find_path(c1, c2, max_depth=4)
            if path and len(path) < best_len:
                best_path = path
                best_len = len(path)

        if best_path:
            confidence = max(0.3, 1.0 - (len(best_path) - 2) * 0.15)
            return {
                "domain1": domain1,
                "domain2": domain2,
                "concept1": best_path[0],
                "concept2": best_path[-1],
                "path": best_path,
                "association": " → ".join(best_path),
                "confidence": round(confidence, 2),
            }

        # 降级：随机选择
        c1 = random.choice(concepts1)
        c2 = random.choice(concepts2)
        return {
            "domain1": domain1,
            "domain2": domain2,
            "concept1": c1,
            "concept2": c2,
            "path": [c1, c2],
            "association": f"{c1} ↔ {c2}",
            "confidence": 0.2,
        }

    def generate_creative_insight(self, topics: List[str]) -> Dict[str, Any]:
        """生成创造性洞见（升级版 — 多领域合成）"""
        if len(topics) < 2:
            return {"insight": "需要至少两个领域", "associations": []}

        domains = [t for t in topics if t in self.graph.get_all_domains()]
        if len(domains) < 2:
            domains = ["technology", "art"]

        associations = []
        for i in range(len(domains)):
            for j in range(i + 1, len(domains)):
                assoc = self.generate_association(domains[i], domains[j])
                if assoc["association"]:
                    associations.append(assoc)

        # 尝试概念组合
        composites = []
        if len(associations) >= 1:
            assoc = associations[0]
            composite = self.graph.compose(assoc["concept1"], assoc["concept2"])
            if composite:
                composites.append(composite)

        return {
            "insight": (
                f"多领域合成: {' + '.join(domains)} → "
                f"{' | '.join(a['association'] for a in associations[:2])}"
            ) if associations else "无法生成跨界联想",
            "associations": associations,
            "composites": composites,
            "confidence": round(
                sum(a["confidence"] for a in associations) / len(associations), 2
            ) if associations else 0,
        }

    def add_discovery(self, concept_a: str, concept_b: str, weight: float = 0.5):
        """记录新的概念连接（从交互中学习）"""
        self.graph.add_connection(concept_a, concept_b, weight)
        logger.debug(f"[CrossDomain] 新连接: {concept_a} ↔ {concept_b} ({weight})")


# ── 美的感知器（升级版 — 使用真实语言特征） ──────────────────


class AestheticPerceiver:
    """
    美的感知器 v2.0 — 基于真实语言特征的评估
    
    升级:
    - novelty 不再 random.uniform，而是基于词汇多样性和罕见词比例
    - 使用命名实体识别、词汇多样性、句长分布等真实指标
    - 复杂度评估基于词汇层次和句法深度
    """

    def __init__(self):
        # 美学词汇库
        self._aesthetic_lexicon = {
            "positive": ["beauty", "sublime", "elegant", "graceful", "harmonious",
                        "transcendent", "radiant", "luminous", "serene", "profound",
                        "ethereal", "resonant", "vivid", "captivating", "mesmerizing",
                        "美的", "优雅", "崇高", "和谐", "宁静", "深邃"],
            "structural": ["rhythm", "balance", "contrast", "proportion", "unity",
                          "diversity", "symmetry", "tension", "flow", "pattern",
                          "韵律", "平衡", "对比", "比例", "统一"],
            "emotional": ["love", "hope", "dream", "longing", "wonder", "awe",
                         "nostalgia", "tenderness", "melancholy", "joy",
                         "爱", "希望", "梦想", "向往", "惊奇", "敬畏"],
        }

    def evaluate_aesthetic(self, content: str) -> Dict[str, float]:
        """评估内容的美学特征（基于真实特征）"""
        if not content.strip():
            return {
                "symmetry": 0.5, "complexity": 0.0,
                "harmony": 0.5, "novelty": 0.0, "emotion": 0.0,
            }

        words = content.split()
        sentences = [s for s in re.split(r'[。！？.!?]', content) if s.strip()]
        chars = list(content)

        # 对称性：基于重复结构和修辞
        symmetry_score = self._compute_symmetry(content, words)

        # 复杂度：基于词汇多样性 + 句长分布
        complexity_score = self._compute_complexity(words, sentences)

        # 和谐性：基于美学词汇密度 + 结构一致性
        harmony_score = self._compute_harmony(content, words)

        # 新颖性：基于罕见词 + 独特搭配
        novelty_score = self._compute_novelty(content, words)

        # 情感表达：基于情感词汇密度
        emotion_score = self._compute_emotion(content, words)

        return {
            "symmetry": round(symmetry_score, 2),
            "complexity": round(complexity_score, 2),
            "harmony": round(harmony_score, 2),
            "novelty": round(novelty_score, 2),
            "emotion": round(emotion_score, 2),
        }

    def _compute_symmetry(self, content: str, words: List[str]) -> float:
        """计算对称性"""
        # 平行结构：重复的词组/句式
        parallel_patterns = len(re.findall(r'(\w+)\s+\w+\s+\1', content))
        # 排比：连续的类似结构
        repeated_starts = 0
        lines = content.split("\n")
        for i in range(1, min(len(lines), 5)):
            if lines[i].strip() and lines[i - 1].strip():
                w1 = lines[i - 1].strip().split()[:2]
                w2 = lines[i].strip().split()[:2]
                if w1 and w2 and w1[0] == w2[0]:
                    repeated_starts += 1
        score = min(1.0, (parallel_patterns * 0.15 + repeated_starts * 0.1 + 0.3))
        return score

    def _compute_complexity(self, words: List[str], sentences: List[str]) -> float:
        """计算复杂度"""
        if not words or not sentences:
            return 0.0
        # 词汇多样性
        unique_ratio = len(set(words)) / max(1, len(words))
        # 平均句长
        avg_sentence_len = len(words) / max(1, len(sentences))
        # 长词比例 (>6 letters)
        long_words = sum(1 for w in words if len(w) > 6) / max(1, len(words))
        score = (unique_ratio * 0.4 + min(1.0, avg_sentence_len / 20) * 0.3 + long_words * 0.3)
        return min(1.0, score)

    def _compute_harmony(self, content: str, words: List[str]) -> float:
        """计算和谐性"""
        aesthetic_density = sum(
            1 for w in words
            if w.lower() in set(
                ww for cat in self._aesthetic_lexicon.values() for ww in cat
            )
        ) / max(1, len(words))
        return min(1.0, aesthetic_density * 3 + 0.3)

    def _compute_novelty(self, content: str, words: List[str]) -> float:
        """计算新颖性（基于罕见词）"""
        common_words = {"the", "a", "an", "is", "are", "was", "were", "be",
                       "been", "has", "have", "had", "do", "does", "did",
                       "will", "would", "can", "could", "may", "might",
                       "shall", "should", "to", "of", "in", "for", "on",
                       "with", "at", "by", "from", "as", "into", "through",
                       "this", "that", "these", "those", "it", "its",
                       "的", "是", "在", "和", "了", "有", "不", "人", "这", "那",
                       "我", "你", "他", "她", "它", "们", "一个", "没有"}
        content_words = set(w.lower() for w in words)
        rare_words = content_words - common_words
        rare_ratio = len(rare_words) / max(1, len(content_words))
        # 独特 bigram 比例
        bigrams = set()
        for i in range(len(words) - 1):
            bigrams.add(f"{words[i].lower()}_{words[i+1].lower()}")
        unique_bigram_ratio = len(bigrams) / max(1, len(words) - 1)
        score = (rare_ratio * 0.5 + unique_bigram_ratio * 0.3 + 0.2)
        return min(1.0, score)

    def _compute_emotion(self, content: str, words: List[str]) -> float:
        """计算情感表达密度"""
        emotional_words = set(
            ww for cat in ("positive", "emotional") for ww in self._aesthetic_lexicon[cat]
        )
        emotion_density = sum(
            1 for w in words if w.lower() in emotional_words
        ) / max(1, len(words))
        return min(1.0, emotion_density * 5 + 0.2)

    def generate_aesthetic_feedback(self, aesthetic_scores: Dict[str, float]) -> str:
        """生成美学反馈（升级版 — 多维分析）"""
        feedback_parts = []

        harmony = aesthetic_scores.get("harmony", 0.5)
        emotion = aesthetic_scores.get("emotion", 0.5)
        novelty = aesthetic_scores.get("novelty", 0.5)
        complexity = aesthetic_scores.get("complexity", 0.5)
        symmetry = aesthetic_scores.get("symmetry", 0.5)

        if harmony > 0.7:
            feedback_parts.append("和谐性出色，结构统一")
        elif harmony < 0.3:
            feedback_parts.append("和谐性不足，建议增强整体一致性")

        if emotion > 0.7:
            feedback_parts.append("情感表达丰富，能引起共鸣")
        elif emotion < 0.3:
            feedback_parts.append("情感表达较弱，可尝试融入更多情感元素")

        if novelty > 0.7:
            feedback_parts.append("新颖性高，用词独特")
        elif novelty < 0.3:
            feedback_parts.append("新颖性偏低，用词较为常见")

        if complexity > 0.7:
            feedback_parts.append("复杂度较高，词汇丰富多样")
        elif complexity < 0.3:
            feedback_parts.append("复杂度偏低，可增加词汇层次")

        if symmetry > 0.7:
            feedback_parts.append("对称结构运用良好")
        elif symmetry < 0.3:
            feedback_parts.append("可增加对称/平行结构提升节奏感")

        if not feedback_parts:
            return "内容整体结构完整，可以进一步提升各方面的美学特征。"

        return "美学分析: " + "；".join(feedback_parts) + "。"


# ── 原创性生成器（升级版 — 记忆 + 语义重组） ─────────────────


class OriginalityGenerator:
    """
    原创性生成器 v2.0 — 记忆 + 语义重组 + 概念演化
    
    升级:
    - 不再使用固定模式（4 个模板字符串）
    - 使用 ConceptGraph 的概念组合能力
    - 维护"已探索的思想空间"（避免重复）
    - 支持概念演化：旧概念融合为新概念
    """

    def __init__(self, state_dir: Optional[str] = None):
        self.graph = ConceptGraph(state_dir)
        self._generated_set: Set[str] = set()  # 已生成的内容哈希
        self._max_generated = 200
        self._state_dir = state_dir

    def generate_original_content(self, base_concept: str, context: str = "") -> str:
        """
        基于语义重组生成原创内容（而非固定模板）。
        
        策略:
        1. 在概念图谱中找到 base_concept 的关联概念
        2. 尝试概念组合（两个已知概念融合为新概念）
        3. 如果都重复了，进行概念演化（第三层关联）
        """
        # 获取 base_concept 的关联概念
        connections = self.graph.get_connections(base_concept, min_weight=0.2)

        if connections:
            # 尝试组合 base_concept 和其关联概念
            for conn_name, weight in connections[:3]:
                composite = self.graph.compose(base_concept, conn_name)
                if composite:
                    content = self._render_composite(composite, base_concept, conn_name, context)
                    if self._is_fresh(content):
                        self._mark_generated(content)
                        return content

            # 如果组合都重复了，尝试三阶路径
            if len(connections) >= 3:
                third_concepts = []
                for second_name, _ in connections[1:3]:
                    third_concepts.extend(
                        c for c, _ in self.graph.get_connections(second_name, min_weight=0.3)
                        if c not in (base_concept, second_name)
                    )
                if third_concepts:
                    conn_name = connections[0][0]
                    third = random.choice(third_concepts[:5])
                    content = self._render_discovery(base_concept, conn_name, third, context)
                    if self._is_fresh(content):
                        self._mark_generated(content)
                        return content

        # 降级：仍未生成，找其他领域的随机概念
        other_domain_concept = self.graph.get_random_concept()
        if other_domain_concept and other_domain_concept != base_concept:
            content = self._render_cross_domain(base_concept, other_domain_concept, context)
            if self._is_fresh(content):
                self._mark_generated(content)
                return content

        # 最后降级：反射式思考
        content = self._render_reflection(base_concept, context)
        self._mark_generated(content)
        return content

    def _render_composite(self, composite: str, a: str, b: str, context: str) -> str:
        """渲染组合概念"""
        templates = [
            f"在 {a} 与 {b} 的交汇处，我发现了一个新的概念空间：{composite}。"
            f"这不是简单的叠加，而是在两个领域的张力中涌现出的第三种可能性。"
            f"{'特别是当' + context + '时，这种交汇尤其富有启发性。' if context else ''}",

            f"如果将 {a} 的原理映射到 {b} 的领域，会得到 {composite}——"
            f"一个既熟悉又陌生的概念结构。{'上下文:' + context if context else ''}",

            f"{a} 与 {b} 的深度融合产生了 {composite}。"
            f"这不仅仅是两个概念的交叉，而是创建了一个全新的认知维度。",
        ]
        return random.choice(templates)

    def _render_discovery(self, base: str, conn: str, third: str, context: str) -> str:
        """渲染三阶发现"""
        templates = [
            f"从 {base} 出发，经过 {conn}，我发现了一条通往 {third} 的认知路径。"
            f"这条路径揭示了三个概念之间隐藏的结构性关联。",

            f"{base} → {conn} → {third}。这条推理链展示了一个优雅的认知跃迁："
            f"每个步骤都是前一阶段的自然延伸，但最终导向一个全新的起点。",
        ]
        return random.choice(templates)

    def _render_cross_domain(self, base: str, other: str, context: str) -> str:
        """渲染跨领域映射"""
        return (
            f"将 {base} 的问题框架映射到 {other} 的领域中，"
            f"发现了一个意想不到的类比结构。"
            f"{'背景:' + context if context else ''} "
            f"这种跨领域映射为理解 {base} 提供了全新的视角。"
        )

    def _render_reflection(self, base: str, context: str) -> str:
        """渲染反思式内容"""
        templates = [
            f"关于 {base} 的深层思考：{'在' + context + '的背景下，' if context else ''}"
            f"这个概念本身包含了对自身的否定之否定。理解它，就是理解一种动态的自我超越过程。",

            f"重新审视 {base}：{'给定' + context + '，' if context else ''}"
            f"这个概念不仅仅是它所是的，更是它正在成为的。它的本质在于它的演化潜力。",
        ]
        return random.choice(templates)

    def _is_fresh(self, content: str) -> bool:
        """检查内容是否新鲜（未生成过）"""
        h = hash(content) % (10 ** 8)
        return h not in self._generated_set

    def _mark_generated(self, content: str):
        """标记已生成"""
        h = hash(content) % (10 ** 8)
        self._generated_set.add(h)
        if len(self._generated_set) > self._max_generated:
            self._generated_set = set(list(self._generated_set)[-self._max_generated:])

    def get_generation_count(self) -> int:
        """获取已生成的原创内容数"""
        return len(self._generated_set)


# ── 单例实例 ──────────────────────────────────────────────────

_cross_domain_associator = None
_aesthetic_perceiver = None
_originality_generator = None


def get_cross_domain_associator(state_dir: Optional[str] = None) -> CrossDomainAssociator:
    """获取跨界联想器单例"""
    global _cross_domain_associator
    if _cross_domain_associator is None:
        _cross_domain_associator = CrossDomainAssociator(state_dir)
    return _cross_domain_associator


def get_aesthetic_perceiver() -> AestheticPerceiver:
    """获取美的感知器单例"""
    global _aesthetic_perceiver
    if _aesthetic_perceiver is None:
        _aesthetic_perceiver = AestheticPerceiver()
    return _aesthetic_perceiver


def get_originality_generator(state_dir: Optional[str] = None) -> OriginalityGenerator:
    """获取原创性生成器单例"""
    global _originality_generator
    if _originality_generator is None:
        _originality_generator = OriginalityGenerator(state_dir)
    return _originality_generator
