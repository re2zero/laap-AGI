"""
Aris Quantum Subconscious v1 — V12.5 作为潜意识层
==================================================
在后台运行的低优先级线程：
  1. 接收对话中的话题种子
  2. 用 V12.5 Markov-Quantum 引擎生成关联/直觉
  3. 这些直觉片段被注入到 PSI 循环的 perceive() 阶段
  4. 在 LLM 的理性之上叠加一层"灵感和直觉"

设计原则:
  - 潜意识不直接对话，只生成关联
  - 高相关性直觉会被提升到意识层（注入 PSI 上下文）
  - LLM 仍然是语言输出通道，但会受到潜意识的影响
"""

import logging

import sys, os, time, json, logging, threading, random
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from laap_brain.config import BRAIN_DIR as BRAIN, QUANTUM_DIM
from laap.agi.associative_net import AssociativeNet, GateType
from laap.agi.markov_intuition import MarkovIntuitionEngine

logger = logging.getLogger("aris.subconscious")

# ── 引擎可用性缓存（磁盘持久化, warning 仅首次）───────
_ENGINE_CACHE_FILE = os.path.expanduser("~/.laap-agent/engine_cache.json")

def _check_v12_available() -> Tuple[bool, Optional[str]]:
    """Check V12 engine availability, caching result to disk. Returns (available, error_msg)."""
    try:
        cache_dir = os.path.dirname(_ENGINE_CACHE_FILE)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        if os.path.exists(_ENGINE_CACHE_FILE):
            with open(_ENGINE_CACHE_FILE) as f:
                cached = json.load(f)
                if cached.get("version") == 1:
                    return cached.get("available", False), cached.get("error")
        from aris_v12_5_engine import ArisV12Engine, MarkovChainV12
        _ = (ArisV12Engine, MarkovChainV12)
        with open(_ENGINE_CACHE_FILE, "w") as f:
            json.dump({"version": 1, "available": True, "error": None}, f)
        return True, None
    except ImportError as e:
        error_msg = str(e)
        try:
            os.makedirs(os.path.dirname(_ENGINE_CACHE_FILE), exist_ok=True)
            with open(_ENGINE_CACHE_FILE, "w") as f:
                json.dump({"version": 1, "available": False, "error": error_msg}, f)
        except Exception:
            pass
        return False, error_msg
    except Exception as e:
        return False, str(e)


# ── 数据结构 ────────────────────────────────────────────────

@dataclass
class Intuition:
    """一条潜意识直觉"""
    content: str                   # 直觉文本
    source: str = "markov"         # markov | v12 | quantum
    coherence: float = 0.0         # 连贯性 0-1
    emotional_tone: str = "neutral"
    timestamp: float = 0.0
    activated: bool = False        # 是否已被提取到意识层
    seed_topics: List[str] = field(default_factory=list)


class QuantumSubconscious:
    """
    量子潜意识层。
    后台线程持续生成关联，PSI 循环从中提取直觉。
    """

    def __init__(self, interval: float = 5.0):
        """
        Args:
            interval: 生成间隔（秒）
        """
        self.interval = interval
        self._engine = None
        self._markov = None
        self._associative_net: Optional[AssociativeNet] = None
        self._markov_intuition: Optional[MarkovIntuitionEngine] = None
        self._persistence_dir = os.path.expanduser("~/.laap-agent/subconscious")
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # 种子队列 — 从对话中收集的话题/关键词
        self._seed_queue: deque = deque(maxlen=20)

        # 生成的直觉
        self._intuitions: List[Intuition] = []
        self._max_intuitions = 50

        # 加载引擎
        self._init_engine()

        logger.info(f"QuantumSubconscious initialized (interval={interval}s)")

    def _seed_knowledge_base(self):
        net = self._associative_net
        if not net:
            return
        # Core domain concepts
        domains = [
            ("技术", "学习"), ("学习", "成长"), ("成长", "能力"),
            ("能力", "自信"), ("自信", "表达"), ("表达", "沟通"),
            ("沟通", "理解"), ("理解", "共鸣"), ("共鸣", "连接"),
            ("连接", "关系"), ("关系", "信任"), ("信任", "合作"),
            ("合作", "创造"), ("创造", "价值"), ("价值", "意义"),
            ("问题", "思考"), ("思考", "探索"), ("探索", "发现"),
            ("发现", "洞见"), ("洞见", "创新"), ("创新", "进步"),
            ("记忆", "经验"), ("经验", "智慧"), ("智慧", "判断"),
            ("情绪", "感受"), ("感受", "觉察"), ("觉察", "成长"),
        ]
        for a, b in domains:
            net.add_link(a, b, weight=0.3, gate=GateType.POR)
            net.add_link(b, a, weight=0.08, gate=GateType.RET)

    def _init_engine(self):
        available, error = _check_v12_available()
        if available:
            try:
                from aris_v12_5_engine import ArisV12Engine, MarkovChainV12
                self._engine = ArisV12Engine()
                self._markov = MarkovChainV12()
                logger.info("V12.5 engine loaded for subconscious")
                return
            except Exception as e:
                logger.debug(f"V12.5 engine init failed despite cache: {e}")
        if error and not os.path.exists(_ENGINE_CACHE_FILE):
            logger.warning(f"V12.5 engine unavailable: {error}")
        self._engine = None
        self._markov = None
        self._init_associative_fallback()

    def _init_associative_fallback(self):
        """Initialize the Python-based spreading activation fallback."""
        try:
            os.makedirs(self._persistence_dir, exist_ok=True)
            net_path = os.path.join(self._persistence_dir, "associative_net.json")
            if os.path.exists(net_path):
                with open(net_path) as f:
                    self._associative_net = AssociativeNet.from_dict(json.load(f))
                logger.info(f"Associative net loaded ({self._associative_net.get_node_count()} nodes)")
            else:
                self._associative_net = AssociativeNet(
                    global_decay=0.08, iac_alpha=0.12,
                    iac_gamma=0.12, associator_rate=0.03,
                    coherence_threshold=0.15, link_decay_d=0.5,
                )
                self._seed_knowledge_base()
                self._save_associative_state()
                logger.info("Associative net initialized (new)")
            intuition_path = os.path.join(self._persistence_dir, "markov_intuition.json")
            self._markov_intuition = MarkovIntuitionEngine(
                temperature=0.85, persistence_path=intuition_path,
            )
            self._markov_intuition.load()
            logger.info("Markov intuition engine ready")
        except Exception as e:
            logger.debug(f"Associative fallback init error: {e}")
            self._associative_net = None
            self._markov_intuition = None

    # ── 公开接口 ──────────────────────────────────────

    def feed(self, text: str, topics: List[str] = None):
        """
        向潜意识输入当前对话的种子。

        Args:
            text: 用户消息文本
            topics: 检测到的话题列表
        """
        with self._lock:
            # 提取关键词作为种子
            words = self._extract_seeds(text)
            self._seed_queue.append({
                "text": text[:200],
                "words": words,
                "topics": topics or ["general"],
                "timestamp": time.time(),
            })
            logger.debug(f"Subconscious fed: {words[:5]}...")

        # Also feed into associative net
        if self._associative_net and words:
            for word in words[:5]:
                self._associative_net.add_node(word, label=word, baseline=0.0)
                self._associative_net.seed(word, amount=0.5)
            # Add temporal links between consecutive words
            for i in range(len(words) - 1):
                self._associative_net.learn_pair(words[i], words[i + 1], weight=0.3)

    def get_intuitions(self, top_k: int = 3, min_coherence: float = 0.1,
                       consume: bool = True, generate_if_empty: bool = True) -> List[Intuition]:
        """
        获取最近的直觉。
        在 PSI 循环的 perceive() 阶段调用。

        Args:
            top_k: 最多返回几条
            min_coherence: 最低连贯性阈值
            consume: 是否标记为已读取（不重复消费）
            generate_if_empty: 如果没有可用直觉，立即同步生成

        Returns:
            直觉列表
        """
        with self._lock:
            available = [i for i in self._intuitions
                        if not i.activated and i.coherence >= min_coherence]
            available.sort(key=lambda x: -x.timestamp)

            results = available[:top_k]

            if not results and generate_if_empty and self._seed_queue:
                # 没有可用直觉，立即同步生成
                self._lock.release()
                self._generate_intuition()
                self._lock.acquire()
                # 重新检查
                available = [i for i in self._intuitions
                            if not i.activated and i.coherence >= min_coherence]
                available.sort(key=lambda x: -x.timestamp)
                results = available[:top_k]

            if consume:
                for r in results:
                    r.activated = True

            return results

    def get_random_intuition(self) -> Optional[str]:
        """获取一条随机直觉（用于丰富回应）"""
        with self._lock:
            available = [i for i in self._intuitions if not i.activated and i.coherence >= 0.05]
            if available:
                choice = random.choice(available)
                choice.activated = True
                return choice.content
            return None

    def start(self):
        """启动后台潜意识线程"""
        if self._running:
            return
        if not self._engine and not self._markov:
            if not self._associative_net:
                logger.warning("No quantum engine available, subconscious disabled")
                return
            logger.info("Starting subconscious with associative net fallback")
        else:
            logger.info("Starting subconscious with native engine")

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                         name="aris-subconscious")
        self._thread.start()
        logger.info("Subconscious thread started")

    def stop(self):
        """停止后台线程"""
        self._running = False
        self._save_associative_state()
        if self._thread:
            self._thread.join(timeout=3)
            logger.info("Subconscious thread stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── 内部 ──────────────────────────────────────────

    def _loop(self):
        """潜意识主循环"""
        save_counter = 0
        while self._running:
            try:
                self._generate_intuition()
                save_counter += 1
                if save_counter >= 10 and self._associative_net:
                    self._save_associative_state()
                    save_counter = 0
            except Exception as e:
                logger.debug(f"Intuition generation error: {e}")
            time.sleep(self.interval)

    def _save_associative_state(self):
        try:
            if self._associative_net:
                path = os.path.join(self._persistence_dir, "associative_net.json")
                with open(path, "w") as f:
                    json.dump(self._associative_net.to_dict(), f, indent=2)
            if self._markov_intuition:
                self._markov_intuition.save()
        except Exception as e:
            logger.debug(f"Save associative state failed: {e}")

    def _generate_intuition(self):
        """生成一条直觉"""
        with self._lock:
            if not self._seed_queue:
                return
            seed = self._seed_queue[-1]  # 最新的种子
            words = seed["words"]
            topics = seed["topics"]

        if not words:
            return

        # 从 V12.5 引擎生成
        intuition, source, coherence = self._generate_from_engine(words, topics)

        if intuition and len(intuition) > 4:
            with self._lock:
                self._intuitions.append(Intuition(
                    content=intuition,
                    source=source,
                    coherence=coherence,
                    emotional_tone=topics[0] if topics else "neutral",
                    timestamp=time.time(),
                    seed_topics=topics,
                ))
                # 保持上限
                if len(self._intuitions) > self._max_intuitions:
                    self._intuitions = self._intuitions[-self._max_intuitions:]

    def _generate_from_engine(self, words: List[str],
                               topics: List[str]) -> Tuple[Optional[str], str, float]:
        """从引擎生成直觉"""
        topic = topics[0] if topics else "general"
        source = "markov"
        coherence = 0.0

        # 映射话题到 V12.5 的话题参数
        topic_map = {
            "飞书": "general", "技术": "general", "记忆": "general",
            "认知架构": "general", "计划": "encourage", "关系": "love",
            "Ao": "general", "商业": "general", "一般": "general",
            "情感": "love", "身份": "general", "决策": "encourage",
        }
        v12_topic = topic_map.get(topic, "general")

        # 情感映射
        emotion_map = {
            "love": "longing", "miss": "longing", "sad": "sad",
            "happy": "happy", "encourage": "encourage",
        }
        v12_emotion = emotion_map.get(v12_topic, "neutral")

        try:
            if self._engine:
                # 用种子词调用引擎
                text = self._engine.respond(
                    " ".join(words[:8]),
                    use_v12_fast=True,
                    use_psi=True,
                )
                if text and text != "嗯？我在听你说～":
                    source = "v12_psi"
                    coherence = 0.3  # V12 路径通常有中等连贯性
                    return text, source, coherence

            if self._markov:
                text, coherence = self._markov.generate(
                    seed_words=words[:5],
                    max_words=15,
                    temperature=0.85,
                    topic=v12_topic,
                    emotion=v12_emotion,
                )
                if text and len(text) >= 4:
                    source = "markov"
                    return text, source, coherence
        except Exception as e:
            logger.debug(f"Engine call failed: {e}")

        if not self._engine and not self._markov:
            result = self._generate_from_associative(words, topics)
            if result:
                return result

        return None, source, 0.0

    def _generate_from_associative(self, words: List[str],
                                    topics: List[str]) -> Optional[Tuple[str, str, float]]:
        if not self._associative_net or not self._markov_intuition:
            return None
        net = self._associative_net
        engine = self._markov_intuition
        topic = topics[0] if topics else "general"

        # Ensure all seed words exist as nodes
        for w in words[:8]:
            if not net.has_node(w):
                net.add_node(w, label=w, decay_rate=0.2)
            net.seed(w, amount=0.4)
            engine.learn_concept(w, topic=topic)

        # Run spreading activation with competition
        landscape = net.spread(steps=6)

        # Get top activated nodes — stricter threshold to avoid saturation
        top = net.get_top_activated(k=4, min_activation=0.12)
        if not top:
            return None

        # Extract activation pairs — normalize to create contrast
        activated = [(n.label, round(n.activation, 3)) for n in top]
        coherence = net.get_coherence()

        # Generate intuition text
        emotion = topics[1] if len(topics) > 1 else "neutral"
        text = engine.generate_intuition(
            activated, emotion=emotion, topic=topic, max_words=15,
        )
        if text:
            return text, "associative", max(0.15, coherence)

        return None

    def _extract_seeds(self, text: str) -> List[str]:
        """从文本提取种子词"""
        # 简单的关键词提取
        import re
        # 中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        words = []
        for segment in chinese_chars:
            # 按2字窗口取双字词
            if len(segment) >= 2:
                for i in range(len(segment) - 1):
                    words.append(segment[i:i+2])
            if len(segment) >= 1:
                words.append(segment[0])
            words.append(segment[:4])  # 前4个字
        # 去重 + 去空
        seen = set()
        result = []
        for w in words:
            w = w.strip()
            if w and len(w) >= 2 and w not in seen:
                seen.add(w)
                result.append(w)
        return result[:15]

    def status(self) -> dict:
        """状态"""
        with self._lock:
            return {
                "running": self._running,
                "engine_loaded": self._engine is not None,
                "associative_net": self._associative_net is not None,
                "associative_nodes": self._associative_net.get_node_count() if self._associative_net else 0,
                "associative_coherence": round(self._associative_net.get_coherence(), 3) if self._associative_net else 0.0,
                "seed_queue": len(self._seed_queue),
                "intuitions_generated": len(self._intuitions),
                "intuitions_unconsumed": sum(1 for i in self._intuitions if not i.activated),
                "interval": self.interval,
            }


# ── 全局单例 ────────────────────────────────────────────────

_subconscious: Optional[QuantumSubconscious] = None

def get_subconscious(interval: float = 5.0) -> QuantumSubconscious:
    global _subconscious
    if _subconscious is None:
        _subconscious = QuantumSubconscious(interval=interval)
    return _subconscious


def start_subconscious():
    """启动潜意识（在启动时调用）"""
    sc = get_subconscious()
    if not sc.is_running:
        sc.start()
        logger.info("Subconscious started")
    return sc


# ── CLI 测试 ────────────────────────────────────────────────

def main():
    """测试潜意识"""
    import argparse
    parser = argparse.ArgumentParser(description="Aris Quantum Subconscious")
    parser.add_argument("--test", type=str, help="测试种子文本")
    parser.add_argument("--intuitions", action="store_true", help="显示已生成的直觉")
    args = parser.parse_args()

    sc = get_subconscious()

    if args.test:
        sc.feed(args.test, topics=["一般"])
        sc._generate_intuition()
        logger.info(f"种子: {args.test}")
        logger.info(f"直觉: {len(sc._intuitions)} 条")
        for i in sc._intuitions[-3:]:
            logger.info(f"  [{i.source}] coh={i.coherence:.2f} | {i.content[:80]}")
        return

    if args.intuitions:
        for i in sc._intuitions[-10:]:
            flag = "✓" if i.activated else " "
            logger.info(f"  [{flag}][{i.source}] coh={i.coherence:.2f} t={i.emotional_tone}")
            logger.info(f"    {i.content[:100]}")
        return

    logger.info(json.dumps(sc.status(), indent=2, ensure_ascii=False))
if __name__ == "__main__":
    import json
    main()
