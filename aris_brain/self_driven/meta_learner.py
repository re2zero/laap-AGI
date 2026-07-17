"""MetaLearner — Layer 5: 元学习
================================
让进化本身也进化。

功能:
  1. 评估各探索策略的效率
  2. 调整 CuriosityDrive 参数
  3. 追踪进化效率指标
  4. 元学习循环

元学习只在积累足够数据后才有意义。
初期以记录和监控为主，调参为辅。
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from aris_brain.self_driven.core_identity import CoreIdentity
from aris_brain.self_driven.state_manager import StateManager

logger = logging.getLogger("aris.self_driven.meta")


class MetaLearner:
    """Layer 5 门面。

    职责:
    - 分析探索历史，评估策略效率
    - 调整 CuriosityDrive 参数
    - 维护进化效率指标
    - 定期运行元学习循环
    """

    def __init__(self, core: CoreIdentity, state_manager: StateManager):
        self._core = core
        self._state = state_manager
        self._strategy_stats: Dict[str, Dict[str, float]] = {}
        self._params_history: List[Dict[str, Any]] = []
        self._metrics: Dict[str, float] = {
            "overall_info_efficiency": 0.0,
            "overall_arch_efficiency": 0.0,
            "meta_learn_efficiency": 0.0,
        }
        self._load()
        logger.info("[MetaLearner] 初始化")

    # ── 策略评估 ──────────────────────────────────────────

    def evaluate_strategies(self) -> Dict[str, float]:
        """评估各探索策略的效率。

        策略分类:
        - arxiv_only: 只搜 arXiv
        - multi_source: 多源搜索
        - deep_read: 深入读一篇论文
        - wikipedia: 只查 Wikipedia

        Returns:
            strategy_name → efficiency_score
        """
        log = self._state.load_exploration_log()
        if len(log) < 3:
            return {"insufficient_data": 0.0}

        strategy_effectiveness: Dict[str, List[float]] = {}

        for entry in log:
            # 根据 sources_consulted 判断策略
            sources = [s.get("type", "") for s in
                       entry.get("sources_consulted", [])]
            if "arxiv" in sources and "semantic_scholar" in sources:
                strategy = "multi_source"
            elif "arxiv" in sources:
                strategy = "arxiv_only"
            elif "wikipedia" in sources:
                strategy = "wikipedia"
            elif "semantic_scholar" in sources:
                strategy = "semantic_scholar"
            else:
                strategy = "other"

            n_insights = len(entry.get("architecture_insights", []))
            n_updates = len(entry.get("knowledge_updates", {}))
            duration = entry.get("duration_ms", 10000)

            # 效率 = (insights + updates) / duration_seconds
            efficiency = (n_insights + n_updates) / max(1, duration / 1000)

            strategy_effectiveness.setdefault(strategy, []).append(efficiency)

        result = {}
        for strategy, effs in strategy_effectiveness.items():
            result[strategy] = round(
                sum(effs) / len(effs), 4
            ) if effs else 0.0

        # 更新持久化
        for strategy, avg_eff in result.items():
            if strategy not in self._strategy_stats:
                self._strategy_stats[strategy] = {
                    "trials": 0,
                    "avg_confidence_gain": 0.0,
                    "avg_cost_ms": 0.0,
                }
            stats = self._strategy_stats[strategy]
            stats["trials"] = stats.get("trials", 0) + 1
            # 滑动平均
            alpha = 0.3
            old_gain = stats.get("avg_confidence_gain", 0.0)
            stats["avg_confidence_gain"] = (
                old_gain * (1 - alpha) + avg_eff * alpha
            )

        self._save()
        return result

    # ── 参数调优 ──────────────────────────────────────────

    def tune_parameters(self) -> Dict[str, Any]:
        """调整 CuriosityDrive 参数。

        基于策略评估结果调整:
        - confidence_threshold: 该多好奇
        - exploration_depth: 该探索多深
        - cross_domain_weight: 跨域连接权重

        Returns:
            调整后的参数
        """
        strategy_eff = self.evaluate_strategies()
        params = self._get_current_params()
        suggestions: Dict[str, Any] = {}

        # 如果 multi_source 更有效率，降低 confidence_threshold（多探索）
        ms_eff = strategy_eff.get("multi_source", 0)
        ao_eff = strategy_eff.get("arxiv_only", 0)

        if ms_eff > ao_eff and ms_eff > 0.01:
            # 多源策略回报高 → 降低门槛，更多探索
            suggestions["confidence_threshold"] = round(
                max(0.1, params.get("confidence_threshold", 0.3) - 0.05), 2
            )
            suggestions["exploration_depth"] = min(
                3, params.get("exploration_depth", 2) + 1
            )

        elif ao_eff > ms_eff and ao_eff > 0.01:
            # arxiv-only 更有效率 → 提高门槛，精耕
            suggestions["confidence_threshold"] = round(
                min(0.5, params.get("confidence_threshold", 0.3) + 0.05), 2
            )

        # 跨域连接权重调整
        n_cross = sum(
            1 for e in self._state.load_exploration_log()
            if any(q.get("curiosity_level") == 2
                   for q in [e.get("question", {})])
        )
        total = len(self._state.load_exploration_log())

        if total > 5:
            cross_ratio = n_cross / total
            if cross_ratio < 0.2 and total > 10:
                # 跨域探索太少 → 增加权重
                suggestions["cross_domain_weight"] = round(
                    min(0.6, params.get("cross_domain_weight", 0.3) + 0.1), 2
                )

        # 记录参数调整
        if suggestions:
            self._params_history.append({
                "timestamp": time.time(),
                "old_params": dict(params),
                "new_params": suggestions,
                "strategy_effectiveness": strategy_eff,
            })

            self._save()
            logger.info(
                f"[MetaLearner] 参数调整: {suggestions}"
            )

        return suggestions

    def _get_current_params(self) -> Dict[str, Any]:
        """从 CuriosityDrive 获取当前参数。"""
        # 通过 StateManager 读取好奇心跳参数
        queue_data = self._state.load_queue()
        return queue_data.get("curiosity_params", {
            "confidence_threshold": 0.3,
            "relevance_threshold": 0.6,
            "exploration_depth": 2,
            "cross_domain_weight": 0.3,
            "risk_tolerance": 0.2,
        })

    # ── 元学习循环 ────────────────────────────────────────

    def meta_learn_cycle(self):
        """完整元学习循环。

        1. 评估各策略效率
        2. 调参
        3. 记录指标
        4. 写 lessons
        """
        logger.info("[MetaLearner] 开始元学习循环")

        # Step 1: 评估
        strategy_eff = self.evaluate_strategies()

        # Step 2: 调参
        param_changes = self.tune_parameters()

        # Step 3: 计算进化效率指标
        total_explorations = len(self._state.load_exploration_log())
        total_gain = sum(
            self._strategy_stats.get(s, {}).get("avg_confidence_gain", 0)
            for s in self._strategy_stats
        )
        n_strategies = max(1, len(self._strategy_stats))

        self._metrics["overall_info_efficiency"] = round(
            total_gain / n_strategies, 4
        )
        self._metrics["last_updated"] = time.time()

        # Step 4: 写 lessons
        if param_changes:
            changes_str = ", ".join(
                f"{k}={v}" for k, v in param_changes.items()
            )
            lesson = (
                f"元学习: 策略调参 ({changes_str})"
            )
            # 写入 NarrativeSelf
            self._core.narrative.add_milestone(
                f"元学习循环: {lesson}",
                impact="meta_learning",
            )

        logger.info(
            f"[MetaLearner] 循环完成: "
            f"策略数={len(strategy_eff)}, "
            f"参数调整={len(param_changes)}, "
            f"效率={self._metrics['overall_info_efficiency']}"
        )

        self._save()

    # ── 状态查询 ──────────────────────────────────────────

    def get_strategy_stats(self) -> Dict[str, Any]:
        return dict(self._strategy_stats)

    def get_metrics(self) -> Dict[str, float]:
        return dict(self._metrics)

    def get_status(self) -> Dict[str, Any]:
        return {
            "strategies": dict(self._strategy_stats),
            "metrics": dict(self._metrics),
            "params_history_count": len(self._params_history),
        }

    # ── 持久化 ────────────────────────────────────────────

    def _load(self):
        data = self._state.load_meta_state()
        self._strategy_stats = data.get("strategy_stats", {})
        self._params_history = data.get("params_history", [])
        self._metrics = data.get("efficiency_metrics", self._metrics)

    def _save(self):
        data = {
            "strategy_stats": {
                k: {
                    "trials": v.get("trials", 0),
                    "avg_confidence_gain": round(
                        v.get("avg_confidence_gain", 0.0), 4
                    ),
                    "avg_cost_ms": round(
                        v.get("avg_cost_ms", 0.0), 1
                    ),
                }
                for k, v in self._strategy_stats.items()
            },
            "params_history": self._params_history[-50:],  # 最多 50 条
            "efficiency_metrics": self._metrics,
        }
        self._state.save_meta_state(data)
