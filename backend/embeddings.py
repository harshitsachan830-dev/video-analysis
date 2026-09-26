import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)

# All data persisted here (relative to backend/ dir)
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "video_store")
os.makedirs(STORAGE_DIR, exist_ok=True)

# In-memory cache: video_id -> { index, chunks }
video_store: dict = {}

DEFAULT_TOP_K = 8
MIN_SIMILARITY_SCORE = 0.20


# ─────────────────────────────────────────
# DISK PATH HELPERS
# ─────────────────────────────────────────

def _video_dir(video_id: str) -> str:
    """Return the directory path for a specific video's data."""
    path = os.path.join(STORAGE_DIR, video_id)
    os.makedirs(path, exist_ok=True)
    return path

def _index_path(video_id: str) -> str:
    return os.path.join(_video_dir(video_id), "index.faiss")

def _chunks_path(video_id: str) -> str:
    return os.path.join(_video_dir(video_id), "chunks.json")

def _meta_path(video_id: str) -> str:
    return os.path.join(_video_dir(video_id), "meta.json")


# ─────────────────────────────────────────
# SAVE / LOAD FROM DISK
# ─────────────────────────────────────────

def _save_to_disk(video_id: str, index: faiss.Index, chunks: list[dict]) -> None:
    """Persist FAISS index + chunks to disk."""
    faiss.write_index(index, _index_path(video_id))

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
    Load a video's FAISS index + chunks from disk into memory.
    Returns True if successful, False if files don't exist.
    """
    idx_path    = _index_path(video_id)
    chunks_path = _chunks_path(video_id)

    if not os.path.exists(idx_path) or not os.path.exists(chunks_path):
        return False

    try:
        index = faiss.read_index(idx_path)
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        video_store[video_id] = {"index": index, "chunks": chunks}
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
    Build FAISS index from transcript chunks.
    Saves to disk AND keeps in memory.
    Returns the number of chunks indexed.
    """
    texts = [chunk.get("text", "") for chunk in chunks if chunk.get("text", "").strip()]

    if not texts:
        raise ValueError("No transcript text available to index.")

    embeddings = model.encode(texts, show_progress_bar=False, batch_size=64)
    embeddings = np.array(embeddings).astype('float32')

    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)   # Inner product = cosine after normalization
    index.add(embeddings)

    # Keep in memory
    video_store[video_id] = {
        "index":  index,
        "chunks": chunks,
    }

    # 💾 Persist to disk
    _save_to_disk(video_id, index, chunks)

    return len(chunks)


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

    store = video_store[video_id]
    index = store["index"]
    chunks = store["chunks"]

    effective_top_k = min(top_k, len(chunks))
    if effective_top_k == 0:
        return []

    query_embedding = model.encode([query.strip()], show_progress_bar=False)
    query_embedding = np.array(query_embedding).astype('float32')
    faiss.normalize_L2(query_embedding)

    scores, indices = index.search(query_embedding, effective_top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        score = float(score)
        if score < MIN_SIMILARITY_SCORE:
            continue
        results.append({
            **chunks[idx],
            "score": round(score, 4),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def search_all_videos(query: str, top_k: int = 5) -> list[dict]:
    """Search for relevant chunks across all indexed videos."""
    if not query or not query.strip():
        return []
        
    query_embedding = model.encode([query.strip()], show_progress_bar=False)
    query_embedding = np.array(query_embedding).astype('float32')
    faiss.normalize_L2(query_embedding)
    
    all_results = []
    
    # Load all videos to search them
    preload_all_videos()
    
    for vid, store in video_store.items():
        index = store["index"]
        chunks = store["chunks"]
        
        if len(chunks) == 0: continue
        
        eff_k = min(top_k, len(chunks))
        scores, indices = index.search(query_embedding, eff_k)
        
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(chunks): continue
            score = float(score)
            if score < MIN_SIMILARITY_SCORE: continue
            
            all_results.append({
                "video_id": vid,
                **chunks[idx],
                "score": round(score, 4),
            })
            
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:top_k]


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
