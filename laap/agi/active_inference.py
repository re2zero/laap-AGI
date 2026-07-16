"""
LAAP AGI — Active Inference Agent (主动推理代理)

Minimal Active Inference module implementing a POMDP generative model
with variational state inference, expected free energy policy selection,
and Dirichlet parameter learning.

Runs alongside the existing LAAP architecture for Phase 1 validation.

Based on:
  - Friston et al. (2016). Active inference and learning.
  - Heins et al. (2022). pymdp: A Python library for active inference.
  - Da Costa et al. (2020). Active inference on discrete state-spaces.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("laap.agi.active_inference")

# ── Constants ─────────────────────────────────────────────

# State space: cognitive contexts
NUM_STATES = 16
STATE_LABELS = [
    "explore_knowledge",     # 探索新知识
    "exploit_known",         # 利用已知知识
    "social_bond",           # 社交连接
    "problem_solving",       # 问题解决
    "creative_association",  # 创造性联想
    "self_reflection",       # 自省
    "uncertainty_resolution",# 不确定性消除
    "goal_planning",         # 目标规划
    "emotional_regulation",  # 情绪调节
    "skill_practice",        # 技能练习
    "memory_consolidation",  # 记忆巩固
    "attention_focus",       # 专注
    "context_switching",     # 上下文切换
    "learning_observation",  # 观察学习
    "idle_rest",             # 休息
    "error_recovery",        # 错误恢复
]

# Observation space: categories from user input
NUM_OBS = 8
OBS_LABELS = [
    "technical_query",       # 技术问题
    "personal_sharing",      # 个人分享
    "social_interaction",    # 社交互动
    "reflective_question",   # 反思性问题
    "directive_command",     # 指令
    "uncertainty_expression",# 不确定表达
    "positive_feedback",     # 正面反馈
    "negative_feedback",     # 负面反馈
]

# Action space: LAAP's action repertoire
NUM_ACTIONS = 6
ACTION_LABELS = [
    "respond_direct",        # 直接回应
    "explore_deep",          # 深入探索
    "use_tool",              # 使用工具
    "reflect_consolidate",   # 反思与巩固
    "social_engage",         # 社交参与
    "self_improve",          # 自我改进
]


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax."""
    x_max = np.max(x, axis=axis, keepdims=True)
    e_x = np.exp(x - x_max)
    return e_x / np.sum(e_x, axis=axis, keepdims=True)


def one_hot(idx: int, size: int) -> np.ndarray:
    arr = np.zeros(size)
    arr[idx] = 1.0
    return arr


@dataclass
class GenerativeModel:
    """POMDP generative model parameters."""
    A: np.ndarray          # P(o|s): [num_obs, num_states] — observation likelihood
    B: np.ndarray          # P(s'|s,a): [num_states, num_states, num_actions] — transition
    C: np.ndarray          # ln P(o): [num_obs] — prior preferences
    D: np.ndarray          # P(s_0): [num_states] — initial state prior
    E: np.ndarray          # P(π): [num_actions] — policy prior (habits)

    num_states: int = NUM_STATES
    num_obs: int = NUM_OBS
    num_actions: int = NUM_ACTIONS

    # Dirichlet concentration parameters for learning
    alpha_A: Optional[np.ndarray] = None   # [num_obs, num_states]
    alpha_B: Optional[np.ndarray] = None   # [num_states, num_states, num_actions]

    @classmethod
    def default(cls) -> "GenerativeModel":
        """Create default generative model with uniform priors."""
        A = np.random.dirichlet(np.ones(NUM_OBS) * 0.5, NUM_STATES).T  # [obs, state]
        B = np.random.dirichlet(np.ones(NUM_STATES) * 0.5, NUM_STATES * NUM_ACTIONS)
        B = B.T.reshape(NUM_STATES, NUM_STATES, NUM_ACTIONS)  # [s', s, a]
        C = np.zeros(NUM_OBS)  # uniform preferences
        D = np.ones(NUM_STATES) / NUM_STATES  # uniform initial state
        E = np.ones(NUM_ACTIONS) / NUM_ACTIONS  # uniform policy prior
        alpha_A = np.ones((NUM_OBS, NUM_STATES)) * 10.0
        alpha_B = np.ones((NUM_STATES, NUM_STATES, NUM_ACTIONS)) * 10.0
        return cls(A=A, B=B, C=C, D=D, E=E, alpha_A=alpha_A, alpha_B=alpha_B)


@dataclass
class BeliefState:
    """Current posterior beliefs."""
    qs: np.ndarray                    # Q(s): [num_states] — current state belief
    qs_prev: np.ndarray               # Q(s_{t-1}): previous state belief
    q_pi: np.ndarray                  # Q(π): [num_actions] — policy posterior
    vfe: float = 0.0                  # Variational free energy (current)
    efe: np.ndarray = field(default_factory=lambda: np.zeros(NUM_ACTIONS))  # G(π)

    def entropy(self) -> float:
        """Entropy of current state belief (uncertainty)."""
        p = np.maximum(self.qs, 1e-10)
        return -np.sum(p * np.log(p))


class ActiveInferenceAgent:
    """
    Minimal Active Inference agent for LAAP.

    Operates a POMDP generative model and performs:
      - State inference (perception): variational free energy minimization
      - Policy inference (action): expected free energy minimization
      - Parameter learning: Dirichlet concentration update
    """

    def __init__(self, model: Optional[GenerativeModel] = None,
                 precision: float = 4.0, learning_rate: float = 1.0):
        self.model = model or GenerativeModel.default()
        self.gamma = precision           # Action precision (γ)
        self.eta = learning_rate         # Learning rate

        self.belief = BeliefState(
            qs=self.model.D.copy(),
            qs_prev=self.model.D.copy(),
            q_pi=np.ones(NUM_ACTIONS) / NUM_ACTIONS,
        )
        self._step = 0
        self._history: List[dict] = []

    # ── Perception: State Inference ────────────────────

    def infer_states(self, obs: int, num_iter: int = 16) -> np.ndarray:
        """
        Variational state estimation via gradient descent on VFE.

        Q(s) ← argmin_Q F[Q]

        Implements the variational message passing update:
          ŝ_τ = σ( ln A·o_τ + ln B·ŝ_{τ-1} + ln B·ŝ_{τ+1} )
        """
        if obs < 0 or obs >= self.model.num_obs:
            raise ValueError(f"Observation {obs} out of range [0, {self.model.num_obs})")

        o = one_hot(obs, self.model.num_obs)
        self.belief.qs_prev = self.belief.qs.copy()

        # Initial belief: combine prior and likelihood
        likelihood = o @ np.log(self.model.A + 1e-10)  # [states]
        prior = np.log(self.model.D + 1e-10)
        qs = softmax(likelihood + prior)

        # Iterative variational update
        for _ in range(num_iter):
            # Expected state transition from previous belief
            prev_contribution = self.belief.qs_prev @ np.log(self.model.B.mean(axis=-1) + 1e-10)
            qs = softmax(likelihood + prev_contribution)

        self.belief.qs = qs
        self.belief.vfe = self._compute_vfe(obs)

        return qs

    def _compute_vfe(self, obs: int) -> float:
        """Compute variational free energy F[Q]."""
        o = one_hot(obs, self.model.num_obs)
        qs = self.belief.qs
        # F = E_Q[ln Q(s) - ln P(o,s)]
        ln_q = np.log(qs + 1e-10)
        ln_po_s = o @ np.log(self.model.A @ qs + 1e-10)
        ln_prior = np.log(self.model.D @ qs + 1e-10)
        # Complexity + inaccuracy
        complexity = qs @ (ln_q - ln_prior)
        inaccuracy = -ln_po_s
        return float(complexity + inaccuracy)

    # ── Action: Policy Selection ───────────────────────

    def infer_policy(self, depth: int = 1) -> np.ndarray:
        """
        Policy selection via expected free energy minimization.

        G(π) = -E_Q[ln P(o|π)] - E_Q[KL[Q(s|o) || Q(s)]]
             = pragmatic_value + epistemic_value

        Returns posterior over actions Q(π).
        """
        G = np.zeros(self.model.num_actions)

        for a in range(self.model.num_actions):
            B_a = self.model.B[:, :, a]  # P(s' | s, a)

            # Expected next state
            expected_next = self.belief.qs @ B_a.T  # [states]

            # Pragmatic value: -E[ln P(o|π)] — prefers preferred outcomes
            expected_obs = expected_next @ self.model.A.T  # [obs]
            pragmatic = expected_obs @ self.model.C

            # Epistemic value: E[KL[Q(s|o) || Q(s)]] — prefers informative outcomes
            epistemic = 0.0
            for o_idx in range(self.model.num_obs):
                log_post = (np.log(self.model.A[o_idx, :] + 1e-10)
                            + np.log(expected_next + 1e-10))
                posterior = softmax(log_post)
                epistemic += expected_obs[o_idx] * _kl(posterior, expected_next)

            G[a] = -pragmatic + -epistemic

        # Action prior from habits
        prior = np.log(self.model.E + 1e-10)

        # Precision-weighted policy posterior
        self.belief.q_pi = softmax(-self.gamma * G + prior)
        self.belief.efe = G
        return self.belief.q_pi

    def select_action(self) -> int:
        """Sample action from policy posterior."""
        return int(np.random.choice(self.model.num_actions, p=self.belief.q_pi))

    # ── Learning ───────────────────────────────────────

    def learn(self, obs: int, action: int):
        """
        Dirichlet parameter update.

        α_A += η · Q(s) ⊗ o
        α_B += η · Q(s_prev) ⊗ Q(s) ⊗ a
        """
        if self.model.alpha_A is not None:
            outer = np.outer(self.belief.qs, one_hot(obs, self.model.num_obs)).T
            self.model.alpha_A += self.eta * outer
            # Update A from Dirichlet expectations
            self.model.A = self.model.alpha_A / self.model.alpha_A.sum(axis=0, keepdims=True)

        if self.model.alpha_B is not None and action >= 0:
            # Update B for the taken action
            outer = np.outer(self.belief.qs_prev, self.belief.qs)
            self.model.alpha_B[:, :, action] += self.eta * outer
            # Update B from Dirichlet expectations
            B_a = self.model.alpha_B[:, :, action]
            self.model.B[:, :, action] = B_a / B_a.sum(axis=0, keepdims=True)

        self._step += 1

    # ── Cycle ──────────────────────────────────────────

    def cycle(self, obs: int) -> Tuple[int, float, float, float]:
        """
        Full active inference cycle: perceive → plan → act → learn.

        Returns:
            (action_idx, vfe, efe_selected, uncertainty)
        """
        self.infer_states(obs)
        self.infer_policy()
        action = self.select_action()
        self.learn(obs, action)

        self._history.append({
            "step": self._step,
            "obs": obs,
            "action": action,
            "vfe": self.belief.vfe,
            "efe": self.belief.efe.copy(),
            "qs": self.belief.qs.copy(),
            "uncertainty": self.belief.entropy(),
            "timestamp": time.time(),
        })

        return action, self.belief.vfe, self.belief.efe[action], self.belief.entropy()

    # ── Interface for LLM Teaching ─────────────────────

    def set_preference(self, obs_idx: int, value: float):
        """Set prior preference C[obs_idx] = value (higher = more preferred)."""
        self.model.C[obs_idx] = value

    def set_transition_prior(self, from_state: int, to_state: int,
                              action: int, weight: float):
        """Manually set a transition prior (B matrix entry)."""
        self.model.B[to_state, from_state, action] = weight
        # Normalize column
        self.model.B[:, from_state, action] /= self.model.B[:, from_state, action].sum()

    def observe_and_encode(self, text: str) -> int:
        """Encode user text to an observation index.

        This is a simple rule-based encoder. Will be improved with
        actual text understanding in Phase 2.
        """
        text_lower = text.lower()

        # Check for social interaction (greetings — highest priority)
        if any(w in text_lower for w in ["hi", "hello", "你好", "在吗", "hey"]):
            return 2  # social_interaction

        # Check for positive feedback — must come BEFORE negative to avoid "不错" conflict
        if any(w in text_lower for w in ["好", "对", "正确", "不错", "可以", "yes", "good", "谢谢"]):
            return 6  # positive_feedback

        # Check for negative feedback
        if any(w in text_lower for w in ["错", "问题", "error", "bug", "不对", "批评"]):
            return 7  # negative_feedback

        # Check for directive commands
        if any(w in text_lower for w in ["提交", "commit", "push", "执行", "implement",
                                          "写", "创建", "修改", "删除", "执行", "fix"]):
            return 4  # directive_command

        # Check for uncertainty
        if "?" in text or any(w in text_lower for w in ["不知道", "不确定", "可能", "也许",
                                          "maybe", "perhaps", "uncertain"]):
            return 5  # uncertainty_expression

        # Check for technical content
        if any(w in text_lower for w in ["代码", "函数", "算法", "架构", "系统",
                                          "python", "api", "模块", "框架", "性能"]):
            return 0  # technical_query

        # Check for personal sharing — "我" is common but should be recognized after priority checks
        if any(w in text_lower for w in ["我的", "觉得", "认为", "感觉", "想"]):
            return 1  # personal_sharing

        return 3  # reflective_question (default)

    # ── Status ─────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "step": self._step,
            "current_belief": STATE_LABELS[int(np.argmax(self.belief.qs))],
            "belief_entropy": round(self.belief.entropy(), 3),
            "vfe": round(self.belief.vfe, 3),
            "selected_policy": ACTION_LABELS[int(np.argmax(self.belief.q_pi))],
            "efe": {ACTION_LABELS[i]: round(float(self.belief.efe[i]), 3)
                    for i in range(self.model.num_actions)},
            "history_length": len(self._history),
        }

    def compare_with_iac(self, iac_activation: np.ndarray,
                         iac_entropy: float = 0.0) -> dict:
        """Compare AIF belief with IAC activation landscape."""
        ai_winner = int(np.argmax(self.belief.qs))
        return {
            "aif_belief": STATE_LABELS[ai_winner],
            "aif_confidence": float(self.belief.qs[ai_winner]),
            "aif_uncertainty": round(self.belief.entropy(), 3),
            "iac_activation": iac_activation.tolist() if isinstance(iac_activation, np.ndarray) else [],
            "iac_entropy": round(iac_entropy, 3),
        }


def _kl(p: np.ndarray, q: np.ndarray) -> float:
    """KL divergence D_KL[p || q]."""
    p = np.maximum(p, 1e-10)
    q = np.maximum(q, 1e-10)
    return float(np.sum(p * (np.log(p) - np.log(q))))
