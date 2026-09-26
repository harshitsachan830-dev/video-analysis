"""
spaced_repetition.py - VideoGPT Pro Spaced Repetition Engine (SM-2)
"""
import os, json
from datetime import date, datetime, timedelta

STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_store")
SR_FILE = os.path.join(STORAGE_DIR, "spaced_repetition.json")

def _load():
    os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(SR_FILE): return []
    try:
        with open(SR_FILE) as f: return json.load(f)
    except: return []

def _save(cards):
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(SR_FILE, "w") as f: json.dump(cards, f, indent=2)

def _today(): return date.today().isoformat()
def _now(): return datetime.utcnow().isoformat()

def _sm2_update(card, quality):
    ef = card.get("ease_factor", 2.5)
    rep = card.get("repetitions", 0)
    ivl = card.get("interval", 1)
    if quality == 1:
        rep, ivl = 0, 1
    elif quality == 2:
        rep, ivl = rep + 1, 3
    else:
        rep, ivl = rep + 1, 7 if rep < 2 else round(ivl * ef)
        ef = max(1.3, ef + 0.1)
    card.update({"ease_factor": round(ef,3), "repetitions": rep, "interval": ivl,
                 "due_date": (date.today()+timedelta(days=ivl)).isoformat(),
                 "last_reviewed": _now()})
    return card

def schedule_topic(topic, video_id, source="manual"):
    cards = _load()
    for c in cards:
        if c["topic"].lower()==topic.lower() and c["video_id"]==video_id: return c
    card = {"id": f"{video_id}_{len(cards)}_{_today()}", "topic": topic,
            "video_id": video_id, "source": source, "interval": 1,
            "ease_factor": 2.5, "repetitions": 0, "due_date": _today(),
            "created_at": _now(), "last_reviewed": None}
    cards.append(card); _save(cards); return card

def get_due_cards(video_id=None):
    cards = _load(); today = _today()
    due = [c for c in cards if c.get("due_date","9999") <= today]
    if video_id: due = [c for c in due if c["video_id"]==video_id]
    return sorted(due, key=lambda c: c.get("due_date",""))

def get_all_cards(video_id=None):
    cards = _load()
    if video_id: cards = [c for c in cards if c["video_id"]==video_id]
    return sorted(cards, key=lambda c: c.get("due_date",""))

def review_card(card_id, quality):
    cards = _load()
    for i,c in enumerate(cards):
        if c["id"]==card_id:
            cards[i] = _sm2_update(c, quality); _save(cards); return cards[i]
    raise ValueError(f"Card {card_id!r} not found.")

def delete_card(card_id):
    cards = _load(); before = len(cards)
    cards = [c for c in cards if c["id"]!=card_id]
    if len(cards)<before: _save(cards); return True
    return False

def get_stats():
    cards = _load(); today = _today()
    return {"total_cards": len(cards),
            "due_today":   len([c for c in cards if c.get("due_date","9999")<=today]),
            "learned":     len([c for c in cards if c.get("repetitions",0)>=3]),
            "new":         len([c for c in cards if c.get("repetitions",0)==0])}

def bulk_schedule_from_weak_topics(weak_topics, video_id):
    return [schedule_topic(t, video_id, source="weak_topic") for t in weak_topics]
