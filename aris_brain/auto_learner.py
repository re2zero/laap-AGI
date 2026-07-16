"""AutoLearner — 自动学习引擎（真实版）
功能:
- 从交互历史中学习模式
- 基于频率和时效的推荐
- 持久化学习结果到 ~/.laap/state/
"""
import logging
import time
import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional

logger = logging.getLogger("auto_learner")


class AutoLearner:
    """自动学习引擎 — 从交互中提取模式并生成建议"""

    def __init__(self, state_dir: Optional[str] = None):
        self._observations: Dict[str, list] = defaultdict(list)
        self._frequencies: Counter = Counter()
        self._max_per_category = 50
        self._total = 0

        # 持久化
        if state_dir:
            self._path = Path(state_dir) / "auto_learner.json"
        else:
            try:
                from laap_brain.config import STATE_DIR
                self._path = STATE_DIR / "auto_learner.json"
            except ImportError:
                self._path = Path.home() / ".laap" / "state" / "auto_learner.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info(f"[AutoLearner] initialized ({self._total} past observations)")

    def observe(self, category: str, data: Any):
        """记录一条观察"""
        entry = {"data": data, "time": time.time()}
        self._observations[category].append(entry)
        self._frequencies[category] += 1
        self._total += 1
        # 限制每个类别的存储量
        if len(self._observations[category]) > self._max_per_category:
            self._observations[category] = self._observations[category][-self._max_per_category:]
        # 每 5 条持久化一次
        if self._total % 5 == 0:
            self._save()

    def get_frequency(self, category: str) -> int:
        return self._frequencies.get(category, 0)

    def get_recent(self, category: str, n: int = 5) -> list:
        return self._observations.get(category, [])[-n:]

    def suggest(self, context: str = "") -> List[str]:
        """基于学习到的模式生成建议"""
        suggestions = []
        # 最常见的类别
        for cat, freq in self._frequencies.most_common(3):
            suggestions.append(f"{cat} (观察到 {freq} 次)")
        # 最近活跃的类别
        now = time.time()
        recent_cats = []
        for cat, entries in self._observations.items():
            recent = [e for e in entries if now - e["time"] < 3600]
            if recent:
                recent_cats.append((cat, len(recent)))
        recent_cats.sort(key=lambda x: -x[1])
        for cat, count in recent_cats[:2]:
            suggestions.append(f"{cat} 近期活跃 ({count} 次/小时)")
        return suggestions

    def get_stats(self) -> dict:
        return {
            "total": self._total,
            "categories": dict(self._frequencies.most_common(10)),
            "category_count": len(self._frequencies),
        }

    def _save(self):
        try:
            data = {
                "frequencies": dict(self._frequencies),
                "total": self._total,
                "observations": {
                    cat: entries[-20:] for cat, entries in self._observations.items()
                },
            }
            self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.debug(f"[AutoLearner] save failed: {e}")

    def _load(self):
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._frequencies.update(data.get("frequencies", {}))
                self._total = data.get("total", 0)
                for cat, entries in data.get("observations", {}).items():
                    self._observations[cat] = entries
        except Exception:
            pass
