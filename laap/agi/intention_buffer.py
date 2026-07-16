"""
LAAP AGI — Intention Buffer (意图缓冲)

PSI-style intention/prospective memory. Stores deferred intentions that
cannot be executed immediately — waiting for the right conditions, resources,
or priority alignment. The intention buffer serves as the bridge between
"what I want to do" (goal setting) and "what I do now" (action selection).

Architecture:
  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐
  │ Goal Engine      │───>│ Intention Buffer │───>│ Action       │
  │ (wants something)│    │ (ranked queue)   │    │ Selection    │
  └──────────────────┘    └──────────────────┘    └──────────────┘
                                │
                          persisted across
                          sessions (optional)

Design:
  - Intentions enter with a priority, urgency curve, and optional trigger
  - Urgency decays over time — a postponed intention gets more pressing
  - The buffer can be peeked for the most urgent/pending intention
  - Completed/cancelled intentions move to history for self-reflection
"""
from __future__ import annotations

import time
import uuid
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("laap.agi.intention_buffer")


class IntentionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"


class IntentionPriority(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Intention:
    """
    An intention — a delayed or pending goal.

    Each intention carries the context of why it was created,
    under what conditions it should fire, and how urgent it has become.
    """
    description: str
    source: str
    priority: IntentionPriority = IntentionPriority.MEDIUM
    urgency: float = 0.3
    decay_rate: float = 0.01
    context: Dict[str, Any] = field(default_factory=dict)
    trigger_condition: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: IntentionStatus = IntentionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    max_retries: int = 0
    retry_count: int = 0
    tags: List[str] = field(default_factory=list)

    def tick_urgency(self) -> float:
        """Decay urgency upward — deferred intentions get more pressing."""
        elapsed = time.time() - self.created_at
        self.urgency = min(1.0, self.urgency + elapsed * self.decay_rate)
        return self.urgency

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description[:80],
            "source": self.source,
            "priority": self.priority.value,
            "urgency": round(self.urgency, 3),
            "status": self.status.value,
            "created_at": self.created_at,
            "tags": self.tags,
        }


@dataclass
class IntentionHistoryEntry:
    """Record of a completed/cancelled intention for self-reflection."""
    intention_id: str
    description: str
    source: str
    status: IntentionStatus
    started_at: float
    ended_at: float
    outcome: str = ""
    duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.intention_id,
            "description": self.description[:60],
            "source": self.source,
            "status": self.status.value,
            "duration": round(self.duration, 1),
            "outcome": self.outcome[:100],
        }


class IntentionBuffer:
    """
    PSI-style intention buffer with urgency-based ranking.

    Intentions are stored in a list and ranked by urgency × priority.
    The buffer handles: enqueue, dequeue (pop highest ranked), peek,
    cancel, complete, and urgency ticking.

    Capacity-limited. Oldest completed intentions eventually evicted.
    """

    def __init__(self, capacity: int = 20, history_capacity: int = 50):
        self._intentions: List[Intention] = []
        self._history: List[IntentionHistoryEntry] = []
        self._capacity = capacity
        self._history_capacity = history_capacity
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    # ── Core API ──────────────────────────────────────────

    def enqueue(self, intention: Intention) -> bool:
        """
        Add an intention to the buffer.

        If at capacity, the lowest-ranked pending intention is removed.
        Returns True if the intention was added, False if rejected.
        """
        if intention.status == IntentionStatus.PENDING:
            intention.tick_urgency()
        with self._lock:
            if len(self._intentions) >= self._capacity:
                self._evict_one()
            self._intentions.append(intention)
        logger.info(f"Intention '{intention.description[:40]}' enqueued "
                     f"(priority={intention.priority.name})")
        return True

    def dequeue(self, source: str = "") -> Optional[Intention]:
        """
        Pop the highest-ranked intention (by urgency × priority).
        Optionally filter by source module.

        Returns None if no pending intentions match.
        """
        candidates = [i for i in self._intentions
                      if i.status == IntentionStatus.PENDING
                      and (not source or i.source == source)]
        if not candidates:
            return None
        ranked = sorted(candidates, key=self._rank, reverse=True)
        chosen = ranked[0]
        chosen.status = IntentionStatus.ACTIVE
        chosen.updated_at = time.time()
        logger.info(f"Intention '{chosen.description[:40]}' dequeued "
                     f"(rank={self._rank(chosen):.2f})")
        return chosen

    def peek(self, limit: int = 5) -> List[Intention]:
        """
        Peek at the highest-ranked intentions without removing them.
        Ticks urgency on all pending intentions first.
        """
        self._tick_all()
        pending = [i for i in self._intentions
                   if i.status == IntentionStatus.PENDING]
        ranked = sorted(pending, key=self._rank, reverse=True)
        return ranked[:limit]

    def complete(self, id: str, outcome: str = "") -> bool:
        """Mark an intention as completed and record to history."""
        for i in self._intentions:
            if i.id == id:
                i.status = IntentionStatus.COMPLETED
                i.updated_at = time.time()
                self._archive(i, outcome=outcome)
                self._intentions.remove(i)
                logger.info(f"Intention '{i.description[:40]}' completed")
                return True
        return False

    def cancel(self, id: str, reason: str = "") -> bool:
        """Cancel a pending or active intention."""
        for i in self._intentions:
            if i.id == id:
                i.status = IntentionStatus.CANCELLED
                i.updated_at = time.time()
                self._archive(i, outcome=reason or "cancelled")
                self._intentions.remove(i)
                logger.info(f"Intention '{i.description[:40]}' cancelled: {reason[:40]}")
                return True
        return False

    def fail(self, id: str, error: str = "") -> bool:
        """
        Mark an intention as failed. Retries if retry_count < max_retries,
        otherwise archives as failed.
        """
        for i in self._intentions:
            if i.id == id:
                i.retry_count += 1
                if i.retry_count < i.max_retries:
                    i.status = IntentionStatus.PENDING
                    i.updated_at = time.time()
                    logger.info(f"Intention '{i.description[:40]}' retry "
                                 f"{i.retry_count}/{i.max_retries}")
                    return True
                i.status = IntentionStatus.FAILED
                i.updated_at = time.time()
                self._archive(i, outcome=f"failed: {error[:80]}")
                self._intentions.remove(i)
                return True
        return False

    def defer(self, id: str, duration: float = 60.0) -> bool:
        """Postpone an intention for a given duration (seconds)."""
        for i in self._intentions:
            if i.id == id and i.status in (IntentionStatus.PENDING,
                                           IntentionStatus.ACTIVE):
                i.status = IntentionStatus.DEFERRED
                i.expires_at = time.time() + duration
                i.updated_at = time.time()
                logger.info(f"Intention '{i.description[:40]}' deferred for {duration}s")
                return True
        return False

    # ── Query ─────────────────────────────────────────────

    def get_pending(self, source: str = "") -> List[Intention]:
        """Get all pending intentions, optionally filtered by source."""
        return [i for i in self._intentions
                if i.status == IntentionStatus.PENDING
                and (not source or i.source == source)]

    def get_due(self) -> List[Intention]:
        """
        Get intentions that should be acted on now:
        - Deferred intentions whose expiration has passed
        - High-urgency pending intentions
        """
        due: List[Intention] = []
        now = time.time()
        for i in self._intentions:
            if i.status == IntentionStatus.DEFERRED and i.expires_at and now >= i.expires_at:
                i.status = IntentionStatus.PENDING
                i.updated_at = now
                due.append(i)
            elif i.status == IntentionStatus.PENDING:
                i.tick_urgency()
                if i.urgency >= 0.85:
                    due.append(i)
        return due

    def get_by_id(self, id: str) -> Optional[Intention]:
        for i in self._intentions:
            if i.id == id:
                return i
        return None

    def stats(self) -> Dict[str, Any]:
        pending = sum(1 for i in self._intentions if i.status == IntentionStatus.PENDING)
        active = sum(1 for i in self._intentions if i.status == IntentionStatus.ACTIVE)
        deferred = sum(1 for i in self._intentions if i.status == IntentionStatus.DEFERRED)
        return {
            "total": len(self._intentions),
            "pending": pending,
            "active": active,
            "deferred": deferred,
            "history_size": len(self._history),
            "capacity": self._capacity,
            "utilization": round(len(self._intentions) / max(self._capacity, 1), 2),
        }

    def get_history(self, limit: int = 10) -> List[IntentionHistoryEntry]:
        return sorted(self._history, key=lambda h: -h.ended_at)[:limit]

    def clear_completed(self) -> int:
        """Remove completed/cancelled intentions from active buffer."""
        before = len(self._intentions)
        self._intentions = [i for i in self._intentions
                            if i.status not in (IntentionStatus.COMPLETED,
                                                IntentionStatus.CANCELLED,
                                                IntentionStatus.FAILED)]
        return before - len(self._intentions)

    # ── Internal ──────────────────────────────────────────

    def _rank(self, i: Intention) -> float:
        """Rank an intention by a composite score (urgency × priority)."""
        i.tick_urgency()
        return i.urgency * i.priority.value

    def _tick_all(self):
        """Tick urgency on all pending intentions."""
        now = time.time()
        for i in self._intentions:
            if i.status == IntentionStatus.PENDING:
                i.tick_urgency()
                if i.is_expired():
                    i.status = IntentionStatus.FAILED
                    self._archive(i, outcome="expired")
            elif i.status == IntentionStatus.DEFERRED:
                if i.expires_at and now >= i.expires_at:
                    i.status = IntentionStatus.PENDING
                    i.updated_at = now

    def _evict_one(self):
        """Remove the lowest-ranked pending intention."""
        pending = [i for i in self._intentions
                   if i.status == IntentionStatus.PENDING]
        if not pending:
            return
        lowest = min(pending, key=self._rank)
        self._intentions.remove(lowest)
        self._archive(lowest, outcome="evicted")
        logger.info(f"Intention '{lowest.description[:40]}' evicted (buffer full)")

    def _archive(self, intention: Intention, outcome: str = ""):
        """Move an intention to history."""
        entry = IntentionHistoryEntry(
            intention_id=intention.id,
            description=intention.description,
            source=intention.source,
            status=intention.status,
            started_at=intention.created_at,
            ended_at=time.time(),
            outcome=outcome,
            duration=time.time() - intention.created_at,
        )
        self._history.append(entry)
        if len(self._history) > self._history_capacity:
            self._history = self._history[-self._history_capacity:]
