import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from transcript import (
    extract_video_id, get_transcript, chunk_transcript,
    parse_timestamp_to_seconds, parse_timestamp_range,
    is_playlist_url, extract_playlist_video_ids,
)
from embeddings import (
    build_index, search_chunks, is_video_indexed,
    get_full_transcript_text, get_video_chunks, get_video_stats,
    # Step 3 — Persistent Storage
    list_all_videos, delete_video,
)
from chat import (
    chat_with_video, generate_summary,
    # Phase 2
    answer_timestamp_query, generate_notes,
    generate_mcqs, extract_mnemonics, generate_interview_questions,
    # Phase 3
    chat_with_memory, check_hallucination, generate_revision_notes
)
from memory import add_message, get_history, clear_history
from ocr import extract_visual_understanding, get_visual_context, search_visual_chunks
from knowledge_graph import build_knowledge_graph
from analytics import (
    log_question, log_mcq_result, log_session_start, log_session_end, log_feature_used,
    get_analytics, get_learning_profile
)
from spaced_repetition import (
    schedule_topic, get_due_cards, get_all_cards, review_card, delete_card,
    get_stats, bulk_schedule_from_weak_topics
)
from gemini import reset_request_context, set_request_api_key

load_dotenv()


# ─────────────────────────────────────────
# STARTUP — preload all saved videos from disk
# ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app_instance):
    print("[VideoGPT] 📂 Saved videos will be loaded on demand.")
    yield


app = FastAPI(title="VideoGPT Pro API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def gemini_api_key_middleware(request: Request, call_next):
    api_key = request.headers.get("x-gemini-api-key", "").strip() or None
    token = set_request_api_key(api_key)
    try:
        return await call_next(request)
    finally:
        reset_request_context(token)


def require_gemini_api_key(
    x_gemini_api_key: str | None = Header(default=None),
) -> None:
    if not (x_gemini_api_key and x_gemini_api_key.strip()) and not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="Add your Gemini API key in Settings to use AI features.",
        )


# ─────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────

class LoadVideoRequest(BaseModel):
    url: str

class PlaylistRequest(BaseModel):
    url: str
    max_videos: int = 30   # default cap

class ChatRequest(BaseModel):
    video_id: str
    question: str

class SummaryRequest(BaseModel):
    video_id: str

class TimestampRequest(BaseModel):
    video_id: str
    timestamp: str          # e.g. "6:40" or "01:30:00"

class NotesRequest(BaseModel):
    video_id: str

class MCQRequest(BaseModel):
    video_id: str
    count: int = 5

class MnemonicsRequest(BaseModel):
    video_id: str

class InterviewRequest(BaseModel):
    video_id: str

# ─────────────────────────────────────────
# NEW ADVANCED REQUEST MODELS
# ─────────────────────────────────────────

class MemoryChatRequest(BaseModel):
    video_id: str
    question: str

class HallucinationRequest(BaseModel):
    video_id: str
    answer: str

class MultiSearchRequest(BaseModel):
    query: str

class VisualSearchRequest(BaseModel):
    video_id: str
    query: str

class SessionStartRequest(BaseModel):
    video_id: str

class FeatureLogRequest(BaseModel):
    video_id: str
    feature: str

class McqResultRequest(BaseModel):
    video_id: str
    question: str
    selected: str
    correct_answer: str
    is_correct: bool
    topic_hint: str = ""

class FlashcardCreateRequest(BaseModel):
    video_id: str
    topic: str
    source: str = "manual"

class FlashcardReviewRequest(BaseModel):
    card_id: str
    quality: int

class WeakTopicsRequest(BaseModel):
    video_id: str
    topics: list[str]


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def require_video(video_id: str):
    """Raise 404 if video is not loaded/indexed."""
    if not is_video_indexed(video_id):
        raise HTTPException(
            status_code=404,
            detail=f"Video '{video_id}' not loaded. Call /load-video first."
        )

def require_transcript(video_id: str) -> str:
    """Return full transcript text or raise 404."""
    text = get_full_transcript_text(video_id)
    if not text or not text.strip():
        raise HTTPException(status_code=404, detail="Transcript text not found for this video.")
    return text


# ─────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "VideoGPT Pro API v2.0 is running 🚀",
        "phase": "Phase 2",
        "features": [
            "chat",
            "summary",
            "timestamp-query",
            "generate-notes",
            "generate-mcqs",
            "extract-mnemonics",
            "generate-interview-questions",
            "timeline-memory",
            "visual-understanding",
            "knowledge-graph",
            "learning-analytics"
        ],
    }

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}


# ─────────────────────────────────────────
# PHASE 1 ROUTES
# ─────────────────────────────────────────


@app.get("/videos")
def list_videos():
    """List all videos saved to disk (persisted across restarts)."""
    videos = list_all_videos()
    return {
        "total": len(videos),
        "videos": videos,
    }


@app.delete("/delete-video/{video_id}")
def delete_video_endpoint(video_id: str):
    """Delete a video's index from memory and disk."""
    deleted = delete_video(video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")
    return {"message": f"Video '{video_id}' deleted successfully.", "video_id": video_id}

@app.post("/load-video")
def load_video(req: LoadVideoRequest):
    """Load a YouTube video, fetch transcript, and build FAISS index."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    try:
        video_id = extract_video_id(req.url.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL. Please provide a valid YouTube link.")

    # Return cached result if already indexed
    if is_video_indexed(video_id):
        stats = get_video_stats(video_id)
        return {
            "video_id": video_id,
            "chunk_count": stats["total_chunks"],
            "duration_seconds": stats["duration_seconds"],
            "message": "Video already loaded ✅ (cached)",
        }

    # Fetch transcript
    try:
        transcript = get_transcript(video_id)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not transcript:
        raise HTTPException(status_code=422, detail="Transcript is empty or unavailable for this video.")

    # Chunk and index
    chunks = chunk_transcript(transcript, chunk_size_seconds=60)
    if not chunks:
        raise HTTPException(status_code=422, detail="Could not create transcript chunks.")

    try:
        chunk_count = build_index(video_id, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build index: {str(e)}")

    stats = get_video_stats(video_id)
    return {
        "video_id": video_id,
        "chunk_count": chunk_count,
        "duration_seconds": stats["duration_seconds"],
        "message": f"Video loaded and indexed successfully ✅ ({chunk_count} chunks)",
    }


# ─────────────────────────────────────────
# PLAYLIST MODE
# ─────────────────────────────────────────

@app.post("/playlist-info")
def playlist_info(req: PlaylistRequest):
    """Fetch metadata (video list) from a YouTube playlist without indexing."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")
    try:
        videos = extract_playlist_video_ids(req.url.strip(), max_videos=req.max_videos)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "total": len(videos),
        "videos": videos,
    }


@app.post("/load-playlist")
def load_playlist(req: PlaylistRequest):
    """
    Index all videos in a YouTube playlist.
    Returns per-video results (success or error) and aggregate stats.
    """
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    # Fetch playlist video list
    try:
        videos = extract_playlist_video_ids(req.url.strip(), max_videos=req.max_videos)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not videos:
        raise HTTPException(status_code=404, detail="No videos found in this playlist.")

    results = []
    indexed_count = 0
    cached_count  = 0
    error_count   = 0

    for v in videos:
        vid = v["video_id"]
        title = v["title"]
        try:
            # Skip if already indexed
            if is_video_indexed(vid):
                stats = get_video_stats(vid)
                results.append({
                    "video_id": vid, "title": title,
                    "status": "cached", "chunk_count": stats["total_chunks"]
                })
                cached_count += 1
                continue

            transcript = get_transcript(vid)
            if not transcript:
                raise ValueError("Empty transcript")

            chunks = chunk_transcript(transcript, chunk_size_seconds=60)
            chunk_count = build_index(vid, chunks)
            results.append({
                "video_id": vid, "title": title,
                "status": "indexed", "chunk_count": chunk_count
            })
            indexed_count += 1

        except Exception as e:
            results.append({
                "video_id": vid, "title": title,
                "status": "error", "error": str(e)
            })
            error_count += 1

    return {
        "total_videos":   len(videos),
        "indexed":        indexed_count,
        "cached":         cached_count,
        "errors":         error_count,
        "results":        results,
    }


@app.post("/chat", dependencies=[Depends(require_gemini_api_key)])
def chat(req: ChatRequest):
    """Answer a question about the video using RAG."""
    require_video(req.video_id)

    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        relevant_chunks = search_chunks(req.video_id, req.question, top_k=5)
        result = chat_with_video(req.question, relevant_chunks)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summary", dependencies=[Depends(require_gemini_api_key)])
def summary(req: SummaryRequest):
    """Generate a full video summary."""
    require_video(req.video_id)
    try:
        full_text = require_transcript(req.video_id)
        return {"summary": generate_summary(full_text)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/video/{video_id}/status")
def video_status(video_id: str):
    """Check if a video is indexed and return its stats."""
    indexed = is_video_indexed(video_id)
    if indexed:
        return {"video_id": video_id, "indexed": True, **get_video_stats(video_id)}
    return {"video_id": video_id, "indexed": False}


# ─────────────────────────────────────────
# PHASE 2 ROUTES
# ─────────────────────────────────────────

@app.post("/timestamp-query", dependencies=[Depends(require_gemini_api_key)])
def timestamp_query(req: TimestampRequest):
    """Answer: 'What happened at 6:40?'"""
    require_video(req.video_id)

    if not req.timestamp or not req.timestamp.strip():
        raise HTTPException(status_code=400, detail="Timestamp cannot be empty.")

    try:
        start_sec, end_sec = parse_timestamp_range(req.timestamp.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        chunks = get_video_chunks(req.video_id)
        result = answer_timestamp_query(start_sec, end_sec, chunks)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-notes", dependencies=[Depends(require_gemini_api_key)])
def notes(req: NotesRequest):
    """Generate chapter-wise structured notes."""
    require_video(req.video_id)
    try:
        full_text = require_transcript(req.video_id)
        return {
            "video_id": req.video_id,
            "notes": generate_notes(full_text),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-mcqs", dependencies=[Depends(require_gemini_api_key)])
def mcqs(req: MCQRequest):
    """Generate multiple choice questions."""
    require_video(req.video_id)

    if req.count < 1:
        raise HTTPException(status_code=400, detail="count must be at least 1")
    if req.count > 20:
        raise HTTPException(status_code=400, detail="count cannot exceed 20")

    try:
        full_text = require_transcript(req.video_id)
        return {
            "video_id": req.video_id,
            "count": req.count,
            "mcqs": generate_mcqs(full_text, req.count),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract-mnemonics", dependencies=[Depends(require_gemini_api_key)])
def mnemonics(req: MnemonicsRequest):
    """Extract mnemonics, formulas, and key facts."""
    require_video(req.video_id)
    try:
        full_text = require_transcript(req.video_id)
        return {
            "video_id": req.video_id,
            "mnemonics": extract_mnemonics(full_text),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-interview-questions", dependencies=[Depends(require_gemini_api_key)])
def interview_questions(req: InterviewRequest):
    """Generate interview/exam questions."""
    require_video(req.video_id)
    try:
        full_text = require_transcript(req.video_id)
        return {
            "video_id": req.video_id,
            "questions": generate_interview_questions(full_text),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────
# PHASE 3 — ADVANCED FEATURES
# ─────────────────────────────────────────

@app.post("/extract-visuals", dependencies=[Depends(require_gemini_api_key)])
def extract_visuals(req: SummaryRequest):
    """Download video, extract frames, analyze with Gemini Vision."""
    require_video(req.video_id)
    try:
        log_feature_used(req.video_id, "visuals")
        return extract_visual_understanding(req.video_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/visual-context/{video_id}")
def visual_context(video_id: str):
    """Get stored visual chunks for a video."""
    require_video(video_id)
    return {"video_id": video_id, "visual_chunks": get_visual_context(video_id)}

@app.post("/chat-with-memory", dependencies=[Depends(require_gemini_api_key)])
def memory_chat(req: MemoryChatRequest):
    """Chat with the video, using timeline memory for context."""
    require_video(req.video_id)
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        log_question(req.video_id, req.question, "memory_chat")
        
        # 1. Get history
        history = get_history(req.video_id)
        
        # 2. Get relevant transcript chunks (also use visuals if available)
        relevant_chunks = search_chunks(req.video_id, req.question, top_k=5)
        visuals = search_visual_chunks(req.video_id, req.question)
        if visuals:
            # Add top visual chunk to context
            visuals[0]["text"] = f"[VISUAL FRAME ANALYSIS] {visuals[0]['analysis']}"
            relevant_chunks.append(visuals[0])
            
        # 3. Chat
        result = chat_with_memory(req.question, relevant_chunks, history)
        
        # 4. Save to history
        add_message(req.video_id, "user", req.question)
        add_message(req.video_id, "assistant", result["answer"])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chat-history/{video_id}")
def clear_chat_history(video_id: str):
    count = clear_history(video_id)
    return {"message": f"Cleared {count} messages for video {video_id}."}

@app.post("/check-hallucination", dependencies=[Depends(require_gemini_api_key)])
def hallucination_check(req: HallucinationRequest):
    """Verify if an AI answer is fully supported by the transcript sources."""
    require_video(req.video_id)
    try:
        # Re-fetch the chunks that were likely used
        relevant_chunks = search_chunks(req.video_id, req.answer, top_k=5)
        result = check_hallucination(req.answer, relevant_chunks)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/multi-search")
def multi_video_search(req: MultiSearchRequest):
    """Search across ALL indexed videos."""
    from embeddings import search_all_videos
    try:
        results = search_all_videos(req.query, top_k=8)
        return {"query": req.query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/knowledge-graph")
def get_knowledge_graph():
    """Build a concept map linking topics across multiple videos."""
    try:
        return build_knowledge_graph()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-revision-notes", dependencies=[Depends(require_gemini_api_key)])
def revision_notes(req: SummaryRequest):
    """Generate concise, last-minute revision notes."""
    require_video(req.video_id)
    try:
        log_feature_used(req.video_id, "revision_notes")
        full_text = require_transcript(req.video_id)
        return {"video_id": req.video_id, "revision_notes": generate_revision_notes(full_text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────
# PHASE 3 — ANALYTICS ENDPOINTS
# ─────────────────────────────────────────

@app.post("/analytics/session/start")
def start_session(req: SessionStartRequest):
    session_id = log_session_start(req.video_id)
    return {"session_id": session_id}

@app.post("/analytics/session/end")
def end_session(req: SessionStartRequest):
    log_session_end(req.video_id)
    return {"status": "ok"}

@app.post("/analytics/log-feature")
def log_feature(req: FeatureLogRequest):
    log_feature_used(req.video_id, req.feature)
    return {"status": "ok"}

@app.post("/analytics/log-mcq")
def log_mcq(req: McqResultRequest):
    log_mcq_result(
        req.video_id, req.question, req.selected, req.correct_answer, req.is_correct, req.topic_hint
    )
    return {"status": "ok"}

@app.get("/analytics/dashboard")
def analytics_dashboard():
    return get_analytics()

@app.get("/analytics/profile")
def learning_profile():
    return get_learning_profile()


# ─────────────────────────────────────────
# SPACED REPETITION / FLASHCARDS
# ─────────────────────────────────────────

@app.get("/flashcards")
def flashcards(video_id: str | None = None, due_only: bool = False):
    if video_id:
        require_video(video_id)
    cards = get_due_cards(video_id) if due_only else get_all_cards(video_id)
    return {
        "video_id": video_id,
        "due_only": due_only,
        "count": len(cards),
        "cards": cards,
        "stats": get_stats(),
    }

@app.get("/flashcards/stats")
def flashcard_stats():
    return get_stats()

@app.post("/flashcards")
def create_flashcard(req: FlashcardCreateRequest):
    require_video(req.video_id)
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")
    return {"card": schedule_topic(topic, req.video_id, req.source)}

@app.post("/flashcards/bulk")
def create_flashcards_from_topics(req: WeakTopicsRequest):
    require_video(req.video_id)
    topics = [topic.strip() for topic in req.topics if topic.strip()]
    if not topics:
        raise HTTPException(status_code=400, detail="At least one topic is required.")
    return {"cards": bulk_schedule_from_weak_topics(topics, req.video_id)}

@app.post("/flashcards/review")
def review_flashcard(req: FlashcardReviewRequest):
    if req.quality < 1 or req.quality > 3:
        raise HTTPException(status_code=400, detail="quality must be 1, 2, or 3.")
    try:
        return {"card": review_card(req.card_id, req.quality)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/flashcards/{card_id}")
def remove_flashcard(card_id: str):
    if not delete_card(card_id):
        raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found.")
    return {"status": "ok", "card_id": card_id}
