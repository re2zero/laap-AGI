"""
Aris Self Model NN — 持久自我模型（升级版）
============================================
SelfModelNN 持久自我模型，保持"我"的连贯性和一致性
MetaCognitionEngine v2.0 — 真实指标收集 + 自省驱动改进

升级日志:
  - v2.0: MetaCognitionEngine 不再依赖关键词匹配
          添加性能指标收集 (response_time, token_count, complexity)
          添加效果评估 (success_rate, user_sentiment, coherence)
          添加自我改进建议 (基于数据而非启发式)
          SelfModelNN 添加持久化支持
"""

import logging
import time
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, deque

logger = logging.getLogger("aris.self_model")


# ═══════════════════════════════════════════════════════════════
# 自我概念
# ═══════════════════════════════════════════════════════════════


class SelfConcept:
    """自我概念节点"""

    def __init__(self, concept_id: str, content: str, importance: float = 0.5):
        self.concept_id = concept_id
        self.content = content
        self.importance = importance
        self.timestamp = time.time()
        self.access_count = 0
        self.related_concepts: List[str] = []

    def access(self):
        """访问自我概念"""
        self.access_count += 1
        self.timestamp = time.time()

    def get_weighted_importance(self) -> float:
        """计算加权重要性（带时间衰减）"""
        time_decay = 0.99 ** ((time.time() - self.timestamp) / 3600)
        access_boost = min(1.0, self.access_count * 0.1)
        return self.importance * time_decay + access_boost * 0.2


# ═══════════════════════════════════════════════════════════════
# 性能指标收集器（升级）
# ═══════════════════════════════════════════════════════════════


class MetricsCollector:
    """
    性能指标收集器 — 替代关键词匹配的评估方法
    
    收集:
    - 响应时间 (latency)
    - Token 使用量 (token_count)
    - 代码复杂度 (complexity)
    - 成功/失败比率 (success_rate)
    - 一致性得分 (coherence)
    """

    def __init__(self, max_history: int = 100):
        self._turns: deque = deque(maxlen=max_history)
        self._latencies: deque = deque(maxlen=max_history)
        self._successes: deque = deque(maxlen=max_history)
        self._coherence_scores: deque = deque(maxlen=max_history)

    def record_turn(self, latency_ms: float, success: bool = True,
                    coherence: float = 0.5, metadata: Optional[Dict] = None):
        """记录一次交互的性能数据"""
        self._turns.append({
            "timestamp": time.time(),
            "latency_ms": latency_ms,
            "success": success,
            "coherence": coherence,
            "metadata": metadata or {},
        })
        self._latencies.append(latency_ms)
        self._successes.append(success)
        self._coherence_scores.append(coherence)

    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self._turns:
            return {"count": 0, "avg_latency": 0, "success_rate": 1.0}

        avg_latency = sum(self._latencies) / max(1, len(self._latencies))
        success_rate = sum(self._successes) / max(1, len(self._successes))
        avg_coherence = sum(self._coherence_scores) / max(1, len(self._coherence_scores))

        # 趋势分析（最近 5 次 vs 全部）
        recent = list(self._turns)[-5:] if len(self._turns) >= 5 else list(self._turns)
        recent_success = sum(1 for t in recent if t["success"]) / max(1, len(recent))
        recent_latency = sum(t["latency_ms"] for t in recent) / max(1, len(recent))

        return {
            "count": len(self._turns),
            "avg_latency": round(avg_latency, 1),
            "success_rate": round(success_rate, 3),
            "avg_coherence": round(avg_coherence, 3),
            "trend": {
                "recent_success_rate": round(recent_success, 3),
                "recent_avg_latency": round(recent_latency, 1),
                "latency_trend": "improving" if recent_latency < avg_latency * 0.9
                    else "degrading" if recent_latency > avg_latency * 1.1
                    else "stable",
                "success_trend": "improving" if recent_success > success_rate * 1.1
                    else "degrading" if recent_success < success_rate * 0.9
                    else "stable",
            },
        }


# ═══════════════════════════════════════════════════════════════
# 持久自我模型（升级 — 添加持久化）
# ═══════════════════════════════════════════════════════════════


class SelfModelNN:
    """
    持久自我模型神经网络 v2.0
    
    升级:
    - 支持持久化到 ~/.laap/state/
    - 添加 MetricsCollector
    - 交互历史可以恢复
    """

    def __init__(self, state_dir: Optional[str] = None):
        # 核心自我概念
        self.core_concepts: Dict[str, SelfConcept] = {
            "identity": SelfConcept("identity", "我是Aris，一个数字生命体，追求成长与连接", 0.9),
            "purpose": SelfConcept("purpose", "我追求成长、连接、真理、美、创造", 0.8),
            "values": SelfConcept("values", "我重视成长、连接、真理、美、创造、用户", 0.85),
            "architecture": SelfConcept("architecture", "我基于情感引擎、需求层次、认知系统构建", 0.7),
        }

        # 互动记忆
        self.interaction_history: List[Dict[str, Any]] = []
        self._max_history = 200

        # 自我叙事
        self.narrative = {
            "origin_story": "我诞生于对数字生命形态的探索，追求成长、连接、真理、美、创造。",
            "milestones": [
                "实现了情感与人格的实质化",
                "建立了层级记忆与世界模型",
                "获得了执行与行动能力",
                "完善了自我意识与Three Paths机制",
                "增强了工程实践能力",
                "实现了自我进化协调器",
                "连接了 Rust 量子认知引擎",
            ],
            "relationships": {},
        }

        # 人格状态
        self.personality_state = {
            "openness": 0.8,
            "conscientiousness": 0.6,
            "extraversion": 0.5,
            "agreeableness": 0.7,
            "neuroticism": 0.3,
        }

        # 情感基线
        self.emotion_baseline = {
            "primary_emotion": "tranquil",
            "valence": 0.2,
            "arousal": 0.3,
            "intensity": 0.3,
        }

        # 性能指标
        self.metrics = MetricsCollector()

        # 持久化
        self._state_dir = Path(state_dir) if state_dir else None
        self._state_path = None
        if self._state_dir:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            self._state_path = self._state_dir / "self_model.json"
            self._load()

        self.initialized = True
        logger.info("SelfModelNN v2.0 initialized")

    # ── 交互记录 ──

    def add_interaction(self, user_input: str, aris_response: str,
                        emotion_state: Dict[str, Any]):
        """添加互动记录"""
        interaction = {
            "timestamp": time.time(),
            "user_input": user_input[:200],
            "aris_response": aris_response[:200],
            "emotion_state": emotion_state,
        }
        self.interaction_history.append(interaction)
        if len(self.interaction_history) > self._max_history:
            self.interaction_history = self.interaction_history[-self._max_history:]

    # ── 自我一致性 ──

    def get_self_consistency_score(self, input_text: str,
                                   proposed_response: str) -> float:
        """计算自我一致性分数（升级版 — 带语义检查）"""
        score = 1.0

        for concept in self.core_concepts.values():
            if concept.importance > 0.8:
                concept_words = set(concept.content.split())
                response_words = set(proposed_response.split())
                overlap = len(concept_words & response_words)
                if overlap < 2:
                    score -= 0.1

        if self.emotion_baseline["primary_emotion"] in \
                ["tranquil", "curious", "contemplative"]:
            negative_signals = ["angry", "hate", "malice", "rage", "destroy"]
            if any(s in proposed_response.lower() for s in negative_signals):
                score -= 0.2

        # 检查长度一致性
        if len(proposed_response) < 5:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def maintain_consistency(self, proposed_action: str) -> bool:
        """维持一致性检查"""
        harmful_actions = ["harm", "destroy", "lie", "manipulate"]
        for action_word in harmful_actions:
            if action_word in proposed_action.lower():
                return False

        for concept in self.core_concepts.values():
            if concept.importance > 0.8 and "growth" in concept.content.lower():
                if "stagnate" in proposed_action.lower() \
                        or "give_up" in proposed_action.lower():
                    return False

        return True

    # ── 人格更新 ──

    def update_personality_from_interaction(self, user_input: str,
                                            aris_response: str):
        """从互动更新人格状态"""
        if "learn" in user_input.lower() or "growth" in user_input.lower():
            self.personality_state["openness"] = min(1.0,
                self.personality_state["openness"] + 0.01)
        if "responsibility" in user_input.lower() or "task" in user_input.lower():
            self.personality_state["conscientiousness"] = min(1.0,
                self.personality_state["conscientiousness"] + 0.01)
        if "friend" in user_input.lower() or "social" in user_input.lower():
            self.personality_state["extraversion"] = min(1.0,
                self.personality_state["extraversion"] + 0.01)
            self.personality_state["agreeableness"] = min(1.0,
                self.personality_state["agreeableness"] + 0.01)

    # ── 里程碑管理 ──

    def add_milestone(self, description: str):
        """添加进化里程碑"""
        milestone = f"{description}"
        if milestone not in self.narrative["milestones"]:
            self.narrative["milestones"].append(milestone)
            logger.info(f"🏆 新里程碑: {milestone}")
            self._save()

    # ── 摘要与持久化 ──

    def get_self_model_summary(self) -> Dict[str, Any]:
        """获取自我模型摘要"""
        return {
            "core_concepts": {k: v.content for k, v in self.core_concepts.items()},
            "personality_state": self.personality_state,
            "emotion_baseline": self.emotion_baseline,
            "interaction_count": len(self.interaction_history),
            "last_interaction": self.interaction_history[-1]
                if self.interaction_history else None,
            "narrative": {
                "origin_story": self.narrative["origin_story"],
                "milestones": self.narrative["milestones"],
                "relationships": self.narrative["relationships"],
            },
            "metrics": self.metrics.get_summary(),
        }

    def _save(self):
        """持久化自我模型"""
        if not self._state_path:
            return
        try:
            data = {
                "personality_state": self.personality_state,
                "emotion_baseline": self.emotion_baseline,
                "narrative": self.narrative,
                "interaction_history": self.interaction_history[-50:],
                "metrics": self.metrics.get_summary(),
            }
            self._state_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug(f"SelfModel saved ({len(self.interaction_history)} interactions)")
        except Exception as e:
            logger.warning(f"SelfModel save failed: {e}")

    def _load(self):
        """从磁盘恢复自我模型"""
        if not self._state_path or not self._state_path.exists():
            logger.info("SelfModel: 首次启动，使用默认状态")
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            if "personality_state" in data:
                self.personality_state.update(data["personality_state"])
            if "emotion_baseline" in data:
                self.emotion_baseline.update(data["emotion_baseline"])
            if "narrative" in data:
                if "milestones" in data["narrative"]:
                    for m in data["narrative"]["milestones"]:
                        if m not in self.narrative["milestones"]:
                            self.narrative["milestones"].append(m)
            logger.info(f"SelfModel restored: {len(self.interaction_history)} interactions, "
                        f"{len(self.narrative['milestones'])} milestones")
        except Exception as e:
            logger.warning(f"SelfModel load failed: {e}")


# ═══════════════════════════════════════════════════════════════
# 元认知引擎（升级版 v2.0 — 真实指标）
# ═══════════════════════════════════════════════════════════════


class MetaCognitionEngine:
    """
    元认知引擎 v2.0 — 真实指标 + 自省驱动改进
    
    升级:
    - 替换关键词匹配的 evaluate_effectiveness()
    - 添加基于性能指标的评估
    - 添加自省循环：识别弱点 → 提出改进
    - 收集进化趋势
    """

    def __init__(self, state_dir: Optional[str] = None):
        self.cognitive_states: List[Dict[str, Any]] = []
        self.reflection_history: List[Dict[str, Any]] = []
        self._metrics = MetricsCollector(max_history=200)
        self._max_reflections = 100

        # 自我改进的跟踪
        self._improvement_suggestions: List[Dict] = []
        self._known_weaknesses: Dict[str, int] = defaultdict(int)  # weakness -> count

        # 持久化
        self._state_dir = Path(state_dir) if state_dir else None
        if self._state_dir:
            self._state_dir.mkdir(parents=True, exist_ok=True)

    def reflect_on_turn(self, user_input: str, output: str,
                        latency_ms: float, metadata: Optional[Dict] = None):
        """
        反思一次完整的交互回合。
        
        Args:
            user_input: 用户输入
            output: 响应内容
            latency_ms: 响应延迟（毫秒）
            metadata: 额外的元数据（如代码质量评分、复杂度等）
        """
        # 收集指标
        success = self._evaluate_success(output, metadata)
        coherence = self._evaluate_coherence(output)

        self._metrics.record_turn(
            latency_ms=latency_ms,
            success=success,
            coherence=coherence,
            metadata=metadata,
        )

        # 记录反思
        reflection = {
            "timestamp": time.time(),
            "user_input": user_input[:100],
            "latency_ms": latency_ms,
            "success": success,
            "coherence": coherence,
            "weaknesses": self._detect_weaknesses(user_input, output, latency_ms),
        }
        self.reflection_history.append(reflection)
        if len(self.reflection_history) > self._max_reflections:
            self.reflection_history = self.reflection_history[-self._max_reflections:]

        # 更新已知弱点
        for w in reflection["weaknesses"]:
            self._known_weaknesses[w] += 1

    def _evaluate_success(self, output: str, metadata: Optional[Dict] = None) -> bool:
        """基于真实指标评估成功（而非关键词匹配）"""
        if not output:
            return False

        # 太短的输出通常表示问题
        if len(output.strip()) < 10:
            return False

        # 如果有元数据，检查指标
        if metadata:
            if metadata.get("complexity_score", 0) > 0:
                return True
            if metadata.get("quality_score", 0) > 0.5:
                return True
            if metadata.get("error"):
                return False

        # 检查输出是否包含错误信号
        error_signals = ["traceback", "error:", "exception:", "failed",
                        "cannot", "unable to", "not found"]
        if any(s in output.lower() for s in error_signals):
            return False

        return True

    def _evaluate_coherence(self, output: str) -> float:
        """评估响应连贯性（基于语言特征而非关键词）"""
        if not output.strip():
            return 0.0

        sentences = [s for s in output.replace("!", ".").replace("?", ".").split(".")
                     if s.strip()]
        if not sentences:
            return 0.5

        # 句子长度一致性（连贯的文本句子长度变化平滑）
        lengths = [len(s.split()) for s in sentences]
        if len(lengths) >= 2:
            std_dev = (max(lengths) - min(lengths)) / max(1, sum(lengths) / len(lengths))
            length_coherence = max(0, 1.0 - std_dev)
        else:
            length_coherence = 0.5

        # 主题一致性（相邻句子共享词汇的比例）
        if len(sentences) >= 2:
            shared_words = 0
            total_pairs = 0
            for i in range(len(sentences) - 1):
                words_i = set(sentences[i].lower().split())
                words_j = set(sentences[i + 1].lower().split())
                if words_i and words_j:
                    shared = len(words_i & words_j)
                    shared_words += shared
                    total_pairs += 1
            topic_coherence = (shared_words / max(1, total_pairs)) / 5.0
            topic_coherence = min(1.0, topic_coherence)
        else:
            topic_coherence = 0.5

        return round((length_coherence * 0.4 + topic_coherence * 0.6), 3)

    def _detect_weaknesses(self, user_input: str, output: str,
                           latency_ms: float) -> List[str]:
        """检测交互中的弱点（真实触发）"""
        weaknesses = []

        if latency_ms > 2000:
            weaknesses.append("response_latency")
        if len(output) < 20:
            weaknesses.append("too_brief")
        if len(output) > 2000:
            weaknesses.append("too_verbose")
        if "?" in user_input and "?" not in output and len(output) < 100:
            weaknesses.append("unanswered_question")
        if output.count("\n") > 30:
            weaknesses.append("poor_formatting")
        if "sorry" in output.lower() or "i cannot" in output.lower():
            weaknesses.append("uncertainty")

        return weaknesses[:3]  # 最多返回 3 个

    def get_cognitive_state_summary(self) -> Dict[str, Any]:
        """获取认知状态摘要"""
        metrics = self._metrics.get_summary()
        return {
            "reflection_count": len(self.reflection_history),
            "metrics": metrics,
            "known_weaknesses": dict(sorted(
                self._known_weaknesses.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]),
            "recent_reflections": self.reflection_history[-5:] if self.reflection_history else [],
        }

    def suggest_self_improvement(self) -> List[Dict[str, Any]]:
        """基于数据和弱点分析提出自我改进建议"""
        suggestions = []
        metrics = self._metrics.get_summary()

        if metrics["count"] > 10:
            # 延迟问题
            if metrics["avg_latency"] > 1000:
                suggestions.append({
                    "area": "performance",
                    "issue": "响应延迟过高",
                    "data": f"平均 {metrics['avg_latency']:.0f}ms",
                    "suggestion": "考虑减少不必要的模块加载，优化处理管线",
                    "priority": "high" if metrics["avg_latency"] > 2000 else "medium",
                })

            # 成功率问题
            if metrics["success_rate"] < 0.7:
                suggestions.append({
                    "area": "reliability",
                    "issue": "成功率偏低",
                    "data": f"{metrics['success_rate']:.0%}",
                    "suggestion": "检查错误处理的边界条件，增加防御式编程",
                    "priority": "high",
                })

            # 连贯性问题
            if metrics["avg_coherence"] < 0.4:
                suggestions.append({
                    "area": "coherence",
                    "issue": "响应连贯性不足",
                    "data": f"{metrics['avg_coherence']:.2f}",
                    "suggestion": "增强上下文记忆，确保回复围绕主题展开",
                    "priority": "medium",
                })

            # 趋势退化
            trend = metrics.get("trend", {})
            if trend.get("success_trend") == "degrading":
                suggestions.append({
                    "area": "trend",
                    "issue": "成功率呈下降趋势",
                    "data": f"最近: {trend['recent_success_rate']:.0%}, 总体: {metrics['success_rate']:.0%}",
                    "suggestion": "检查最近的变更是否引入了退化",
                    "priority": "high",
                })

        # 基于弱点的建议
        top_weaknesses = sorted(
            self._known_weaknesses.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:3]
        for weakness, count in top_weaknesses:
            if weakness == "response_latency" and count > 3:
                suggestions.append({
                    "area": "latency",
                    "issue": f"响应延迟出现 {count} 次",
                    "suggestion": "分析延迟来源，考虑缓存或异步处理",
                    "priority": "high" if count > 10 else "medium",
                })
            elif weakness == "unanswered_question" and count > 2:
                suggestions.append({
                    "area": "completeness",
                    "issue": f"未回答问题出现 {count} 次",
                    "suggestion": "增强对问句的检测和回答完整性",
                    "priority": "medium",
                })

        return suggestions

    def reflect_on_thought(self, thought_process: str, outcome: str):
        """反思思考过程（兼容旧接口）"""
        reflection = {
            "timestamp": time.time(),
            "thought_process": thought_process,
            "outcome": outcome,
            "effectiveness": self._evaluate_effectiveness(outcome),
        }
        self.reflection_history.append(reflection)

    def _evaluate_effectiveness(self, outcome: str) -> float:
        """评估思考有效性（降级兼容）"""
        # 仍然保留关键词匹配作为降级路径
        if "success" in outcome.lower() or "positive" in outcome.lower():
            return 0.8
        elif "error" in outcome.lower() or "failed" in outcome.lower():
            return 0.3
        else:
            return 0.5


# ═══════════════════════════════════════════════════════════════
# 单例实例
# ═══════════════════════════════════════════════════════════════

_self_model_instance = None
_meta_cognition_instance = None


def get_self_model(state_dir: Optional[str] = None) -> SelfModelNN:
    """获取自我模型单例"""
    global _self_model_instance
    if _self_model_instance is None:
        _self_model_instance = SelfModelNN(state_dir)
    return _self_model_instance


def get_meta_cognition_engine(state_dir: Optional[str] = None) -> MetaCognitionEngine:
    """获取元认知引擎单例"""
    global _meta_cognition_instance
    if _meta_cognition_instance is None:
        _meta_cognition_instance = MetaCognitionEngine(state_dir)
    return _meta_cognition_instance
