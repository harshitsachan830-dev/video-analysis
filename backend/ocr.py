"""
ocr.py — VideoGPT Pro Visual Understanding Engine
Downloads YouTube videos, extracts key frames, and analyzes them with Gemini Vision
to understand slides, diagrams, code, and whiteboard content.
"""

import os
import json
import time
import base64
import tempfile
import datetime

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False

from google.genai import types
from dotenv import load_dotenv
from gemini import generate_content

load_dotenv()

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

STORAGE_DIR      = os.path.join(os.path.dirname(__file__), "video_store")
FRAME_INTERVAL_S = 30       # Extract one frame every 30 seconds
MAX_FRAMES       = 40       # Cap at 40 frames per video to control API costs
JPEG_QUALITY     = 75       # JPEG compression quality for frame export


# ─────────────────────────────────────────
# STORAGE HELPERS
# ─────────────────────────────────────────

def _visual_chunks_path(video_id: str) -> str:
    video_dir = os.path.join(STORAGE_DIR, video_id)
    os.makedirs(video_dir, exist_ok=True)
    return os.path.join(video_dir, "visual_chunks.json")


def _has_visual_analysis(video_id: str) -> bool:
    path = _visual_chunks_path(video_id)
    return os.path.exists(path) and os.path.getsize(path) > 10


def _load_visual_chunks(video_id: str) -> list[dict]:
    path = _visual_chunks_path(video_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_visual_chunks(video_id: str, chunks: list[dict]) -> None:
    with open(_visual_chunks_path(video_id), "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────
# VIDEO DOWNLOAD
# ─────────────────────────────────────────

def _download_video(video_id: str, output_dir: str) -> str | None:
    """
    Download the YouTube video (lowest quality for speed) to output_dir.
    Returns the path to the downloaded file, or None on failure.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        # Download worst quality video to minimize file size / download time
        "format":      "worstvideo[ext=mp4]/worst[ext=mp4]/worst",
        "outtmpl":     out_template,
        "quiet":       True,
        "no_warnings": True,
    }

    # Try with browser cookies first (avoids bot detection)
    for browser in ["chrome", "safari", None]:
        try:
            opts = dict(ydl_opts)
            if browser:
                opts["cookiesfrombrowser"] = (browser,)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                vid_id = info.get("id", video_id)
                # Find the downloaded file
                for fname in os.listdir(output_dir):
                    if vid_id in fname and not fname.endswith(".part"):
                        return os.path.join(output_dir, fname)
        except Exception:
            continue

    return None


# ─────────────────────────────────────────
# FRAME EXTRACTION
# ─────────────────────────────────────────

def _extract_frames(video_path: str, interval_s: int = FRAME_INTERVAL_S, max_frames: int = MAX_FRAMES) -> list[dict]:
    """
    Extract frames from a video file at regular intervals.
    Returns list of {"timestamp_s": float, "timestamp": str, "frame_bytes": bytes}
    """
    cap    = cv2.VideoCapture(video_path)
    fps    = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = []

    frame_interval = int(fps * interval_s)
    frame_count    = 0

    while len(frames) < max_frames:
        success, frame = cap.read()
        if not success:
            break

        if frame_count % frame_interval == 0:
            ts_s    = frame_count / fps
            ts_str  = _format_ts(ts_s)

            # Resize to 720p max width to save memory / API bandwidth
            h, w    = frame.shape[:2]
            if w > 1280:
                scale  = 1280 / w
                frame  = cv2.resize(frame, (1280, int(h * scale)))

            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                frames.append({
                    "timestamp_s": ts_s,
                    "timestamp":   ts_str,
                    "frame_bytes": buf.tobytes(),
                })

        frame_count += 1

    cap.release()
    return frames


def _format_ts(seconds: float) -> str:
    s  = int(seconds)
    h  = s // 3600
    m  = (s % 3600) // 60
    sc = s % 60
    return f"{h:02d}:{m:02d}:{sc:02d}" if h else f"{m:02d}:{sc:02d}"


# ─────────────────────────────────────────
# GEMINI VISION ANALYSIS
# ─────────────────────────────────────────

_VISION_PROMPT = """Analyze this video frame and extract ALL visible information that would be useful for a student studying this content.

Look for and extract:
1. **Slide Text** — any text visible on presentation slides (title, bullet points, body text)
2. **Diagrams / Charts** — describe what diagrams, flowcharts, or charts show
3. **Code** — transcribe any code snippets, formulas, or pseudocode exactly
4. **Whiteboard / Handwriting** — transcribe any handwritten content
5. **Key Visual Info** — anything on screen that adds meaning beyond the spoken audio

If the frame is just a talking-head shot with no informational content (e.g. presenter speaking with blank background), respond with exactly: NO_CONTENT

Otherwise, provide a structured extraction. Be concise but complete."""


def _analyze_frame_with_gemini(frame_bytes: bytes, timestamp: str, max_retries: int = 3) -> str | None:
    """Send a single frame to Gemini Vision and return the analysis text."""
    try:
        response = generate_content(
            contents=[
                types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                f"Video timestamp: {timestamp}\n\n{_VISION_PROMPT}",
            ],
            max_retries=min(max_retries, 1),
        )
    except Exception as error:
        print(f"[Vision] Frame analysis error at {timestamp}: {error}")
        raise RuntimeError(f"Frame analysis failed at {timestamp}: {error}") from error

    text = response.text.strip() if response.text else ""
    if text == "NO_CONTENT" or not text:
        return None
    return text


# ─────────────────────────────────────────
# MAIN PUBLIC API
# ─────────────────────────────────────────

def extract_visual_understanding(video_id: str, force: bool = False) -> dict:
    """
    Full pipeline: download video → extract frames → analyze with Gemini Vision.
    Caches results to disk — skips if already done unless force=True.

    Returns:
        {
            "video_id": str,
            "visual_chunks": list[dict],   # frames with visual content
            "total_frames_analyzed": int,
            "frames_with_content": int,
            "status": "completed" | "cached" | "failed",
        }
    """
    if not force and _has_visual_analysis(video_id):
        chunks = _load_visual_chunks(video_id)
        return {
            "video_id":               video_id,
            "visual_chunks":          chunks,
            "total_frames_analyzed":  len(chunks),
            "frames_with_content":    len([c for c in chunks if c.get("analysis")]),
            "status":                 "cached",
        }

    # Check dependencies
    if not CV2_AVAILABLE:
        return {
            "video_id": video_id, "visual_chunks": [], "total_frames_analyzed": 0,
            "frames_with_content": 0, "status": "failed",
            "error": "OpenCV (cv2) is not installed. Run: pip install opencv-python-headless"
        }
    if not YT_DLP_AVAILABLE:
        return {
            "video_id": video_id, "visual_chunks": [], "total_frames_analyzed": 0,
            "frames_with_content": 0, "status": "failed",
            "error": "yt-dlp is not installed. Run: pip install yt-dlp"
        }

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"[Vision] Downloading video {video_id}...")
        video_path = _download_video(video_id, tmpdir)

        if not video_path or not os.path.exists(video_path):
            return {
                "video_id": video_id,
                "visual_chunks": [],
                "total_frames_analyzed": 0,
                "frames_with_content": 0,
                "status": "failed",
                "error": "Could not download video. It may be private, geo-restricted, or require login.",
            }

        print(f"[Vision] Extracting frames from {video_path}...")
        frames = _extract_frames(video_path)
        print(f"[Vision] Extracted {len(frames)} frames. Analyzing with Gemini Vision...")

        visual_chunks = []
        for i, frame_data in enumerate(frames):
            ts    = frame_data["timestamp"]
            ts_s  = frame_data["timestamp_s"]
            print(f"[Vision]   Frame {i+1}/{len(frames)} @ {ts}")

            analysis = _analyze_frame_with_gemini(frame_data["frame_bytes"], ts)
            if analysis:
                visual_chunks.append({
                    "timestamp":   ts,
                    "timestamp_s": ts_s,
                    "analysis":    analysis,
                    "type":        "visual",
                })

        _save_visual_chunks(video_id, visual_chunks)
        print(f"[Vision] Done. {len(visual_chunks)}/{len(frames)} frames had content.")

    return {
        "video_id":               video_id,
        "visual_chunks":          visual_chunks,
        "total_frames_analyzed":  len(frames),
        "frames_with_content":    len(visual_chunks),
        "status":                 "completed",
    }


def get_visual_context(video_id: str) -> list[dict]:
    """Return stored visual analysis chunks for a video."""
    return _load_visual_chunks(video_id)


def has_visual_analysis(video_id: str) -> bool:
    """Check if visual analysis has been run for this video."""
    return _has_visual_analysis(video_id)


def search_visual_chunks(video_id: str, query: str) -> list[dict]:
    """
    Simple keyword search over visual chunks (no vector search needed for visuals —
    text is extracted and keyword matching is sufficient).
    """
    chunks   = _load_visual_chunks(video_id)
    query_lc = query.lower()
    results  = []
    for chunk in chunks:
        if query_lc in chunk.get("analysis", "").lower():
            results.append(chunk)
    return results
