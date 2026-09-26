"""
analytics.py — VideoGPT Pro Learning Analytics Engine
Tracks questions, MCQ results, study sessions, and builds a personalized learning profile.
"""

import os
import json
import datetime
from collections import defaultdict

# ─────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────

ANALYTICS_DIR = os.path.join(os.path.dirname(__file__), "analytics_store")
os.makedirs(ANALYTICS_DIR, exist_ok=True)

QUESTIONS_LOG_PATH  = os.path.join(ANALYTICS_DIR, "questions_log.json")
MCQ_LOG_PATH        = os.path.join(ANALYTICS_DIR, "mcq_log.json")
SESSIONS_LOG_PATH   = os.path.join(ANALYTICS_DIR, "sessions_log.json")


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _load_json(path: str, default) -> any:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────
# QUESTION LOGGING
# ─────────────────────────────────────────

def log_question(video_id: str, question: str, tab: str = "chat") -> None:
    """Log a question asked by the user."""
    log = _load_json(QUESTIONS_LOG_PATH, [])
    log.append({
        "video_id":  video_id,
        "question":  question,
        "tab":       tab,
        "timestamp": _now(),
    })
    # Keep last 500 entries
    if len(log) > 500:
        log = log[-500:]
    _save_json(QUESTIONS_LOG_PATH, log)


# ─────────────────────────────────────────
# MCQ PERFORMANCE LOGGING
# ─────────────────────────────────────────

def log_mcq_result(
    video_id: str,
    question: str,
    selected: str,
    correct_answer: str,
    is_correct: bool,
    topic_hint: str = "",
) -> None:
    """Log a single MCQ attempt."""
    log = _load_json(MCQ_LOG_PATH, [])
    log.append({
        "video_id":      video_id,
        "question":      question,
        "selected":      selected,
        "correct_answer": correct_answer,
        "is_correct":    is_correct,
        "topic_hint":    topic_hint,
        "timestamp":     _now(),
    })
    if len(log) > 1000:
        log = log[-1000:]
    _save_json(MCQ_LOG_PATH, log)


# ─────────────────────────────────────────
# SESSION LOGGING
# ─────────────────────────────────────────

def log_session_start(video_id: str) -> str:
    """Start a study session and return session_id."""
    sessions = _load_json(SESSIONS_LOG_PATH, [])
    session_id = f"session_{len(sessions) + 1}"
    sessions.append({
        "session_id": session_id,
        "video_id":   video_id,
        "start":      _now(),
        "end":        None,
        "features_used": [],
    })
    _save_json(SESSIONS_LOG_PATH, sessions)
    return session_id


def log_feature_used(video_id: str, feature: str) -> None:
    """Record which feature was used in the most recent session for this video."""
    sessions = _load_json(SESSIONS_LOG_PATH, [])
    # Find last session for this video
    for s in reversed(sessions):
        if s["video_id"] == video_id and s["end"] is None:
            if feature not in s["features_used"]:
                s["features_used"].append(feature)
            break
    _save_json(SESSIONS_LOG_PATH, sessions)


def log_session_end(video_id: str) -> None:
    """Close the most recent open session for a video."""
    sessions = _load_json(SESSIONS_LOG_PATH, [])
    for s in reversed(sessions):
        if s["video_id"] == video_id and s["end"] is None:
            s["end"] = _now()
            break
    _save_json(SESSIONS_LOG_PATH, sessions)


# ─────────────────────────────────────────
# ANALYTICS DASHBOARD
# ─────────────────────────────────────────

def get_analytics() -> dict:
    """Return full analytics data for the dashboard."""
    questions = _load_json(QUESTIONS_LOG_PATH, [])
    mcq_log   = _load_json(MCQ_LOG_PATH, [])
    sessions  = _load_json(SESSIONS_LOG_PATH, [])

    # ── Question stats ──
    total_questions = len(questions)
    questions_by_tab = defaultdict(int)
    questions_by_video = defaultdict(int)
    for q in questions:
        questions_by_tab[q.get("tab", "chat")] += 1
        questions_by_video[q.get("video_id", "unknown")] += 1

    # ── MCQ stats ──
    total_mcqs   = len(mcq_log)
    correct_mcqs = sum(1 for m in mcq_log if m.get("is_correct"))
    accuracy     = round((correct_mcqs / total_mcqs * 100), 1) if total_mcqs else 0

    # Weak topics = videos/topics with most wrong answers
    wrong_by_video = defaultdict(int)
    for m in mcq_log:
        if not m.get("is_correct"):
            wrong_by_video[m.get("video_id", "unknown")] += 1

    weak_videos = sorted(wrong_by_video.items(), key=lambda x: x[1], reverse=True)[:5]

    # ── Session stats ──
    total_sessions    = len(sessions)
    completed_sessions = [s for s in sessions if s.get("end")]
    total_study_mins  = 0
    for s in completed_sessions:
        try:
            start = datetime.datetime.fromisoformat(s["start"].replace("Z", "+00:00"))
            end   = datetime.datetime.fromisoformat(s["end"].replace("Z", "+00:00"))
            total_study_mins += (end - start).total_seconds() / 60
        except Exception:
            pass

    # Videos studied
    videos_studied = list({s["video_id"] for s in sessions})

    # Feature usage
    feature_counts = defaultdict(int)
    for s in sessions:
        for f in s.get("features_used", []):
            feature_counts[f] += 1

    # Recent activity (last 10 questions)
    recent_questions = questions[-10:][::-1]

    return {
        "questions": {
            "total": total_questions,
            "by_tab": dict(questions_by_tab),
            "by_video": dict(questions_by_video),
            "recent": recent_questions,
        },
        "mcq": {
            "total_attempts":  total_mcqs,
            "correct":         correct_mcqs,
            "wrong":           total_mcqs - correct_mcqs,
            "accuracy_percent": accuracy,
            "weak_videos":     [{"video_id": v, "wrong_count": c} for v, c in weak_videos],
        },
        "sessions": {
            "total":              total_sessions,
            "completed":          len(completed_sessions),
            "total_study_minutes": round(total_study_mins, 1),
            "videos_studied":     videos_studied,
        },
        "feature_usage": dict(feature_counts),
    }


# ─────────────────────────────────────────
# LEARNING PROFILE
# ─────────────────────────────────────────

def get_learning_profile() -> dict:
    """Return a personalized learning profile based on usage patterns."""
    mcq_log   = _load_json(MCQ_LOG_PATH, [])
    questions = _load_json(QUESTIONS_LOG_PATH, [])
    sessions  = _load_json(SESSIONS_LOG_PATH, [])

    # Per-video breakdown
    video_profiles: dict = defaultdict(lambda: {
        "questions_asked": 0,
        "mcq_attempts":    0,
        "mcq_correct":     0,
        "features_used":   set(),
    })

    for q in questions:
        vid = q.get("video_id", "")
        video_profiles[vid]["questions_asked"] += 1

    for m in mcq_log:
        vid = m.get("video_id", "")
        video_profiles[vid]["mcq_attempts"] += 1
        if m.get("is_correct"):
            video_profiles[vid]["mcq_correct"] += 1

    for s in sessions:
        vid = s.get("video_id", "")
        for f in s.get("features_used", []):
            video_profiles[vid]["features_used"].add(f)

    # Build profile list
    profiles = []
    for vid, data in video_profiles.items():
        attempts = data["mcq_attempts"]
        correct  = data["mcq_correct"]
        accuracy = round((correct / attempts * 100), 1) if attempts else None
        strength = "Strong" if accuracy and accuracy >= 70 else ("Needs Work" if accuracy is not None else "Not Tested")
        profiles.append({
            "video_id":       vid,
            "questions_asked": data["questions_asked"],
            "mcq_accuracy":   accuracy,
            "strength":       strength,
            "features_used":  list(data["features_used"]),
        })

    # Sort by most activity
    profiles.sort(key=lambda x: x["questions_asked"] + (x["mcq_accuracy"] or 0), reverse=True)

    # Overall stats
    total_attempts = len(mcq_log)
    total_correct  = sum(1 for m in mcq_log if m.get("is_correct"))
    overall_accuracy = round((total_correct / total_attempts * 100), 1) if total_attempts else 0

    # Preferred learning style based on feature usage
    feature_counts = defaultdict(int)
    for s in sessions:
        for f in s.get("features_used", []):
            feature_counts[f] += 1

    preferred_features = sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    return {
        "overall_accuracy":    overall_accuracy,
        "total_mcq_attempts":  total_attempts,
        "videos_profiled":     len(profiles),
        "video_profiles":      profiles,
        "preferred_features":  [{"feature": f, "uses": c} for f, c in preferred_features],
        "recommendation": _get_recommendation(overall_accuracy, profiles),
    }


def _get_recommendation(accuracy: float, profiles: list) -> str:
    """Generate a personalized study recommendation."""
    if not profiles:
        return "Start by loading a video and exploring all features to build your learning profile!"

    weak = [p for p in profiles if p["strength"] == "Needs Work"]
    if weak:
        vids = ", ".join(p["video_id"] for p in weak[:2])
        return f"Focus on revisiting: {vids}. Try the MCQ quiz and Mnemonics tabs for these videos."

    if accuracy >= 80:
        return "Excellent work! You're performing strongly. Try the Interview Prep tab to challenge yourself further."

    if accuracy >= 60:
        return "Good progress! Keep practicing MCQs and use the Revision Notes feature to reinforce weak areas."

    return "Keep going! Use Chapter Notes and Mnemonics to strengthen your understanding before taking quizzes."
