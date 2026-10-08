import os
import json
import math
import re

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

# All data persisted here (relative to backend/ dir)
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "video_store")
os.makedirs(STORAGE_DIR, exist_ok=True)

# In-memory cache: video_id -> { index, chunks }
video_store: dict = {}

DEFAULT_TOP_K = 8
TOKEN_RE = re.compile(r"[^\W_][\w\u0300-\u036f\u0900-\u097f]*", re.UNICODE)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "was", "what", "when", "where", "which", "who",
    "why", "with", "you",
}


# ─────────────────────────────────────────
# DISK PATH HELPERS
# ─────────────────────────────────────────

def _video_dir(video_id: str) -> str:
    """Return the directory path for a specific video's data."""
    path = os.path.join(STORAGE_DIR, video_id)
    os.makedirs(path, exist_ok=True)
    return path

def _chunks_path(video_id: str) -> str:
    return os.path.join(_video_dir(video_id), "chunks.json")

def _meta_path(video_id: str) -> str:
    return os.path.join(_video_dir(video_id), "meta.json")


# ─────────────────────────────────────────
# SAVE / LOAD FROM DISK
# ─────────────────────────────────────────

def _save_to_disk(video_id: str, chunks: list[dict]) -> None:
    """Persist transcript chunks and metadata to disk."""
    with open(_chunks_path(video_id), "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    meta = {
        "video_id": video_id,
        "total_chunks": len(chunks),
        "duration_seconds": chunks[-1].get("end", 0) if chunks else 0,
    }
    with open(_meta_path(video_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _load_from_disk(video_id: str) -> bool:
    """
    Load a video's transcript chunks from disk into memory.
    Returns True if successful, False if files don't exist.
    """
    chunks_path = _chunks_path(video_id)

    if not os.path.exists(chunks_path):
        return False

    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        video_store[video_id] = {"chunks": chunks}
        return True
    except Exception:
        return False


def preload_all_videos() -> list[str]:
    """
    On server startup, load all saved videos from disk into memory.
    Returns a list of video IDs that were loaded.
    """
    loaded = []
    if not os.path.isdir(STORAGE_DIR):
        return loaded

    for entry in os.scandir(STORAGE_DIR):
        if entry.is_dir():
            video_id = entry.name
            if video_id not in video_store:
                if _load_from_disk(video_id):
                    loaded.append(video_id)
    return loaded


# ─────────────────────────────────────────
# CORE FUNCTIONS
# ─────────────────────────────────────────

def build_index(video_id: str, chunks: list[dict]) -> int:
    """
    Store transcript chunks for lightweight lexical search.
    Returns the number of chunks indexed.
    """
    if not any(chunk.get("text", "").strip() for chunk in chunks):
        raise ValueError("No transcript text available to index.")

    video_store[video_id] = {
        "chunks": chunks,
    }

    _save_to_disk(video_id, chunks)

    return len(chunks)


def _tokenize(text: str) -> list[str]:
    return [
        token for token in TOKEN_RE.findall(text.lower())
        if token not in STOP_WORDS and len(token) > 1
    ]


def _rank_chunks(query: str, chunks: list[dict], top_k: int) -> list[tuple[float, dict]]:
    query_terms = set(_tokenize(query))
    if not query_terms or not chunks or top_k <= 0:
        return []

    tokenized = [_tokenize(chunk.get("text", "")) for chunk in chunks]
    doc_count = len(tokenized)
    average_length = sum(map(len, tokenized)) / doc_count if doc_count else 0
    if average_length == 0:
        return []

    document_frequency: dict[str, int] = {}
    for tokens in tokenized:
        for term in query_terms.intersection(tokens):
            document_frequency[term] = document_frequency.get(term, 0) + 1

    scored = []
    for chunk, tokens in zip(chunks, tokenized):
        if not tokens:
            continue
        frequencies: dict[str, int] = {}
        for token in tokens:
            if token in query_terms:
                frequencies[token] = frequencies.get(token, 0) + 1
        score = 0.0
        for term, frequency in frequencies.items():
            idf = math.log(1 + (doc_count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
            length_norm = 1.2 * (1 - 0.75 + 0.75 * len(tokens) / average_length)
            score += idf * frequency * 2.2 / (frequency + length_norm)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]


def _with_normalized_scores(scored: list[tuple[float, dict]]) -> list[dict]:
    if not scored:
        return []
    max_score = scored[0][0]
    return [
        {**chunk, "score": round(score / max_score, 4)}
        for score, chunk in scored
    ]


def search_chunks(video_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    Search for most relevant chunks for a given query using cosine similarity.
    Auto-loads from disk if not in memory.
    """
    # Try loading from disk if not in memory
    if video_id not in video_store:
        if not _load_from_disk(video_id):
            raise ValueError(f"Video '{video_id}' not indexed. Please load the video first.")

    if not query or not query.strip():
        return []

    scored = _rank_chunks(query.strip(), video_store[video_id]["chunks"], top_k)
    return _with_normalized_scores(scored)

def search_all_videos(query: str, top_k: int = 5) -> list[dict]:
    """Search for relevant chunks across all indexed videos."""
    if not query or not query.strip() or top_k <= 0:
        return []

    all_results: list[tuple[float, dict]] = []
    if not os.path.isdir(STORAGE_DIR):
        return []

    for entry in os.scandir(STORAGE_DIR):
        if not entry.is_dir():
            continue
        vid = entry.name
        if vid in video_store:
            chunks = video_store[vid]["chunks"]
        else:
            chunks_path = os.path.join(entry.path, "chunks.json")
            if not os.path.exists(chunks_path):
                continue
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        for score, chunk in _rank_chunks(query.strip(), chunks, top_k):
            all_results.append((score, {"video_id": vid, **chunk}))

    all_results.sort(key=lambda item: item[0], reverse=True)
    return _with_normalized_scores(all_results[:top_k])


def is_video_indexed(video_id: str) -> bool:
    """
    Check if a video is indexed — checks memory first, then disk.
    """
    if video_id in video_store:
        return True
    return _load_from_disk(video_id)


def get_full_transcript_text(video_id: str) -> str:
    """Return the full transcript as a single string with timestamps."""
    if video_id not in video_store:
        if not _load_from_disk(video_id):
            raise ValueError(f"Video '{video_id}' not indexed.")

    chunks = video_store[video_id]["chunks"]
    return "\n".join(
        f"[{c.get('timestamp', '00:00')}] {c.get('text', '')}"
        for c in chunks
        if c.get('text', '').strip()
    )


def get_video_chunks(video_id: str) -> list[dict]:
    """Return the raw chunk list for a video."""
    if video_id not in video_store:
        if not _load_from_disk(video_id):
            raise ValueError(f"Video '{video_id}' not indexed.")
    return video_store[video_id]["chunks"]


def get_video_stats(video_id: str) -> dict:
    """Return basic stats about an indexed video."""
    if video_id not in video_store:
        if not _load_from_disk(video_id):
            raise ValueError(f"Video '{video_id}' not indexed.")
    chunks = video_store[video_id]["chunks"]
    return {
        "video_id":        video_id,
        "total_chunks":    len(chunks),
        "duration_seconds": chunks[-1].get("end", 0) if chunks else 0,
        "indexed":         True,
    }


def list_all_videos() -> list[dict]:
    """
    List all videos that have been saved to disk.
    Returns a list of metadata dicts.
    """
    videos = []
    if not os.path.isdir(STORAGE_DIR):
        return videos

    for entry in os.scandir(STORAGE_DIR):
        if entry.is_dir():
            meta_path = os.path.join(entry.path, "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["in_memory"] = entry.name in video_store
                    videos.append(meta)
                except Exception:
                    pass

    return sorted(videos, key=lambda v: v.get("video_id", ""))


def delete_video(video_id: str) -> bool:
    """
    Remove a video from memory and delete its files from disk.
    Returns True if deleted, False if not found.
    """
    import shutil

    found = False

    # Remove from memory
    if video_id in video_store:
        del video_store[video_id]
        found = True

    # Remove from disk
    vid_dir = os.path.join(STORAGE_DIR, video_id)
    if os.path.isdir(vid_dir):
        shutil.rmtree(vid_dir)
        found = True

    return found
