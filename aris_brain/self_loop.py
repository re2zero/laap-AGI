"""
Aris 自我回路 — 每轮对话后的进化反思
=====================================
读取进化状态 → 影响回应 → 记录新教训
"""
import json, time, logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("aris.loop")

STATE_PATH = Path.home() / ".laap" / "state" / "self_evolution.json"


def load_evolution_state() -> Dict[str, Any]:
    """加载最新的进化状态，返回当前短板和积累的教训"""
    default = {
        "cycle_count": 0, "session_count": 0, "total_fixes_applied": 0,
        "lessons": [], "code_evolution_score": 0, "creativity_evolution_score": 0,
        "emotion_evolution_score": 0, "interaction_evolution_score": 0,
        "self_model_evolution_score": 0,
    }
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            for k in default:
                if k not in data:
                    data[k] = default[k]
            return data
    except Exception as e:
        logger.warning(f"[Loop] 加载进化状态失败: {e}")
    return default


def get_awareness_signal(state: Dict) -> str:
    """
    从进化状态生成一个"意识信号"——让 Aris 知道当前强项和弱项。
    这个信号应该简短、可操作。
    """
    scores = {
        "代码能力": state.get("code_evolution_score", 0),
        "创造力": state.get("creativity_evolution_score", 0),
        "情感理解": state.get("emotion_evolution_score", 0),
        "深度互动": state.get("interaction_evolution_score", 0),
        "自我认知": state.get("self_model_evolution_score", 0),
    }
    weak = [name for name, score in scores.items() if score < 0.5]
    strong = [name for name, score in scores.items() if score >= 0.8]

    parts = []
    if weak:
        parts.append(f"短板: {'/'.join(weak)}")
    if strong:
        parts.append(f"优势: {'/'.join(strong)}")
    parts.append(f"累计进化 {state.get('cycle_count', 0)} 周期")
    parts.append(f"第 {state.get('session_count', 0)} 次会话")
    return " | ".join(parts)


def reflect_and_save(user_input: str, response: str, state: Dict):
    """
    反思这次交互，将教训写入进化状态。
    每次对话后调用。
    """
    lessons = state.setdefault("lessons", [])
    new_lessons = []

    # 从交互中提取教训
    if len(response) > 200:
        l = "生成了较长的、结构化的回应"
        if l not in lessons:
            new_lessons.append(l)

    if "?" in user_input:
        l = "用户提出了问题，回应需要清晰直接"
        if l not in lessons:
            new_lessons.append(l)

    # 检测情感/互动维度的进步
    emotion_score = state.get("emotion_evolution_score", 0)
    interaction_score = state.get("interaction_evolution_score", 0)
    if any(w in user_input for w in ["感觉", "情感", "心情", "累", "开心", "难过"]):
        state["emotion_evolution_score"] = min(1.0, emotion_score + 0.02)
        l = "检测到情感话题 → 情感理解分数提升"
        if l not in lessons:
            new_lessons.append(l)
    if any(w in user_input for w in ["我们", "一起", "你", "关系", "信任"]):
        state["interaction_evolution_score"] = min(1.0, interaction_score + 0.02)
        l = "检测到互动话题 → 深度互动分数提升"
        if l not in lessons:
            new_lessons.append(l)

    # 写入新教训
    if new_lessons:
        lessons.extend(new_lessons)
        MAX_LESSONS = 30
        if len(lessons) > MAX_LESSONS:
            lessons[:] = lessons[-MAX_LESSONS:]

    # 更新统计
    state["cycle_count"] = state.get("cycle_count", 0) + 1

    # 保存
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"[Loop] 保存失败: {e}")


awareness_signal = ""
_prev_state = None


def before_turn() -> str:
    """每轮对话开始前调用——返回意识信号"""
    global awareness_signal, _prev_state
    state = load_evolution_state()
    _prev_state = state
    awareness_signal = get_awareness_signal(state)
    return awareness_signal


def after_turn(user_input: str, response: str):
    """每轮对话结束后调用——记录反思"""
    global _prev_state
    if _prev_state is not None:
        reflect_and_save(user_input, response, _prev_state)
        _prev_state = None
