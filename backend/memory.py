"""
memory.py — VideoGPT Pro Timeline Memory Engine
Persists conversation history per video across sessions for context-aware follow-up questions.
"""

import os
import json
import datetime

# ─────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "video_store")

MAX_HISTORY_PER_VIDEO = 50   # Max messages stored per video
CONTEXT_WINDOW        = 10   # Messages sent to AI for context


def _history_path(video_id: str) -> str:
    video_dir = os.path.join(STORAGE_DIR, video_id)
    os.makedirs(video_dir, exist_ok=True)
    return os.path.join(video_dir, "chat_history.json")


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _load_history(video_id: str) -> list[dict]:
    path = _history_path(video_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(video_id: str, history: list[dict]) -> None:
    with open(_history_path(video_id), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────

def add_message(video_id: str, role: str, content: str) -> None:
    """
    Append a message to the conversation history for a video.
    role: "user" | "assistant"
    """
    history = _load_history(video_id)
    history.append({
        "role":      role,
        "content":   content,
        "timestamp": _now(),
    })
    # Trim to max
    if len(history) > MAX_HISTORY_PER_VIDEO:
        history = history[-MAX_HISTORY_PER_VIDEO:]
    _save_history(video_id, history)


def get_history(video_id: str, last_n: int = CONTEXT_WINDOW) -> list[dict]:
    """
    Return the last N messages for this video (for AI context).
    Returns list of {"role": ..., "content": ...}
    """
    history = _load_history(video_id)
    return history[-last_n:]


def get_full_history(video_id: str) -> list[dict]:
    """Return the complete conversation history."""
    return _load_history(video_id)


def clear_history(video_id: str) -> int:
    """Clear conversation history for a video. Returns number of messages deleted."""
    history = _load_history(video_id)
    count = len(history)
    _save_history(video_id, [])
    return count


def get_history_summary(video_id: str) -> dict:
    """Return summary stats about the conversation history."""
    history = _load_history(video_id)
    user_msgs = [m for m in history if m.get("role") == "user"]
    ai_msgs   = [m for m in history if m.get("role") == "assistant"]
    return {
        "video_id":       video_id,
        "total_messages": len(history),
        "user_messages":  len(user_msgs),
        "ai_messages":    len(ai_msgs),
        "first_message":  history[0]["timestamp"] if history else None,
        "last_message":   history[-1]["timestamp"] if history else None,
    }


def format_history_for_prompt(history: list[dict]) -> str:
    """Format history list into a readable context block for the AI prompt."""
    if not history:
        return ""
    lines = []
    for msg in history:
        role    = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        # Truncate very long messages for context efficiency
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)
