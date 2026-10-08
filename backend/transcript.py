import re
import os
import tempfile
import time
from urllib.parse import quote

import httpx
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from common URL formats."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL")


def is_playlist_url(url: str) -> bool:
    """Return True if the URL contains a playlist ID."""
    return bool(re.search(r'[?&]list=([A-Za-z0-9_-]+)', url))


def extract_playlist_video_ids(url: str, max_videos: int = 50) -> list[dict]:
    """
    Extract all video IDs and titles from a YouTube playlist URL.
    Returns list of {"video_id": str, "title": str, "url": str}
    Capped at max_videos to avoid runaway indexing.
    """
    ydl_opts = {
        "quiet":              True,
        "no_warnings":        True,
        "extract_flat":       True,   # Don't download, just list entries
        "playlistend":        max_videos,
        "ignoreerrors":       True,
    }
    videos = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("Could not fetch playlist info.")
            entries = info.get("entries", [])
            for entry in entries:
                if entry and entry.get("id"):
                    videos.append({
                        "video_id": entry["id"],
                        "title":    entry.get("title", entry["id"]),
                        "url":      f"https://www.youtube.com/watch?v={entry['id']}",
                    })
    except Exception as e:
        raise ValueError(f"Failed to fetch playlist: {str(e)}")
    return videos

# ─────────────────────────────────────────
# VTT / SRT PARSERS
# ─────────────────────────────────────────

def _vtt_ts_to_seconds(ts: str) -> float:
    """Convert VTT/SRT timestamp string to seconds."""
    ts = ts.strip().replace(',', '.')
    parts = ts.split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    except Exception:
        pass
    return 0.0


def _parse_vtt(content: str) -> list[dict]:
    """Parse WebVTT subtitle content into list of {text, start, duration}."""
    entries = []
    blocks = re.split(r'\n\n+', content.strip())
    seen_texts = set()

    for block in blocks:
        lines = block.strip().split('\n')
        ts_line_idx = None
        for i, line in enumerate(lines):
            if '-->' in line:
                ts_line_idx = i
                break
        if ts_line_idx is None:
            continue

        ts_match = re.match(r'([\d:.,]+)\s+-->\s+([\d:.,]+)', lines[ts_line_idx])
        if not ts_match:
            continue

        start_secs = _vtt_ts_to_seconds(ts_match.group(1))
        end_secs   = _vtt_ts_to_seconds(ts_match.group(2))

        text_lines = lines[ts_line_idx + 1:]
        text = ' '.join(l for l in text_lines if l.strip())
        # Remove VTT/HTML tags
        text = re.sub(r'<[^>]+>', '', text).strip()
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if not text or text in seen_texts:
            continue
        seen_texts.add(text)

        entries.append({
            'text': text,
            'start': start_secs,
            'duration': max(0.1, end_secs - start_secs),
        })

    return entries


# ─────────────────────────────────────────
# MAIN TRANSCRIPT FETCHER
# ─────────────────────────────────────────

def get_transcript(video_id: str) -> list[dict]:
    """
    Fetch a native transcript from Supadata when configured, otherwise use
    the existing YouTube transcript sources.
    """
    supadata_api_key = os.getenv("SUPADATA_API_KEY", "").strip()
    if supadata_api_key:
        return _get_transcript_supadata(video_id, supadata_api_key)

    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # ── Method 1: yt-dlp with Chrome cookies (handles IP blocks) ──
    for browser in ['chrome', 'safari', 'firefox']:
        try:
            result = _get_transcript_ytdlp(video_url, cookiesfrombrowser=browser)
            if result:
                return result
        except Exception:
            continue

    # ── Method 2: yt-dlp without cookies ──
    try:
        result = _get_transcript_ytdlp(video_url, cookiesfrombrowser=None)
        if result:
            return result
    except Exception:
        pass

    # ── Method 3: youtube-transcript-api (original) ──
    try:
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
    except Exception:
        pass

    try:
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)
        for t in transcript_list:
            fetched = t.fetch()
            return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
    except TranscriptsDisabled:
        raise Exception("Transcripts are disabled for this video.")
    except Exception as e:
        raise Exception(f"Could not fetch transcript: {str(e)}")


def _get_transcript_supadata(video_id: str, api_key: str) -> list[dict]:
    """Fetch an existing timestamped transcript through Supadata."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"x-api-key": api_key}
    deadline = time.monotonic() + 60

    with httpx.Client(timeout=20) as client:
        response = client.get(
            "https://api.supadata.ai/v1/transcript",
            params={"url": video_url, "mode": "native"},
            headers=headers,
        )

        if response.status_code == 206:
            raise ValueError("Supadata could not find an existing transcript for this video.")
        if response.status_code == 202:
            payload = response.json()
            job_id = payload.get("jobId") if isinstance(payload, dict) else None
            if not job_id:
                raise RuntimeError("Supadata started a transcript job but did not return a job ID.")

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Supadata transcript job did not finish within 60 seconds.")
                time.sleep(min(1, remaining))
                response = client.get(
                    f"https://api.supadata.ai/v1/transcript/{quote(str(job_id), safe='')}",
                    headers=headers,
                    timeout=min(15, remaining),
                )
                _raise_supadata_error(response)
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError("Supadata returned an invalid transcript job response.")
                status = payload.get("status")
                if status == "completed":
                    break
                if status == "failed":
                    raise RuntimeError(
                        f"Supadata transcript job failed: {payload.get('error', 'unknown error')}"
                    )
                if status not in {"queued", "active"}:
                    raise RuntimeError(f"Supadata returned an unknown transcript job status: {status!r}.")
        else:
            _raise_supadata_error(response)
            payload = response.json()

    if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
        raise RuntimeError("Supadata did not return timestamped transcript segments.")

    entries = []
    for segment in payload["content"]:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise RuntimeError("Supadata returned an invalid transcript segment.")
        try:
            start = float(segment["offset"]) / 1000
            duration = float(segment["duration"]) / 1000
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Supadata returned transcript segments without valid timestamps.") from exc
        text = segment["text"].strip()
        if text:
            entries.append({"text": text, "start": start, "duration": duration})
    return entries


def _raise_supadata_error(response: httpx.Response) -> None:
    if response.is_success:
        return

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    message = payload.get("message") if isinstance(payload, dict) else None
    detail = f": {message}" if message else ""
    raise RuntimeError(f"Supadata transcript API returned HTTP {response.status_code}{detail}")


def _get_transcript_ytdlp(video_url: str, cookiesfrombrowser=None) -> list[dict]:
    """Download subtitles via yt-dlp and parse them."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = os.path.join(tmpdir, '%(id)s')

        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'subtitlesformat': 'vtt',
            'outtmpl': out_template,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
        }

        if cookiesfrombrowser:
            ydl_opts['cookiesfrombrowser'] = (cookiesfrombrowser,)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_id = info.get('id', '')

        # Find the downloaded VTT file
        for fname in os.listdir(tmpdir):
            if fname.endswith('.vtt') and video_id in fname:
                fpath = os.path.join(tmpdir, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                entries = _parse_vtt(content)
                if entries:
                    return entries

    return []


# ─────────────────────────────────────────
# CHUNKING HELPERS
# ─────────────────────────────────────────

def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS."""
    seconds = int(seconds)
    hours   = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs    = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def chunk_transcript(transcript: list[dict], chunk_size_seconds: int = 60) -> list[dict]:
    """Group transcript entries into ~chunk_size_seconds chunks."""
    chunks = []
    current_text  = []
    current_start = None
    current_end   = None

    for entry in transcript:
        start    = entry['start']
        duration = entry.get('duration', 0)
        end      = start + duration
        text     = entry['text'].strip()

        if current_start is None:
            current_start = start

        current_text.append(text)
        current_end = end

        if (current_end - current_start) >= chunk_size_seconds:
            chunks.append({
                "text":      " ".join(current_text),
                "start":     current_start,
                "end":       current_end,
                "timestamp": format_timestamp(current_start),
            })
            current_text  = []
            current_start = None
            current_end   = None

    if current_text:
        chunks.append({
            "text":      " ".join(current_text),
            "start":     current_start or 0,
            "end":       current_end   or 0,
            "timestamp": format_timestamp(current_start or 0),
        })

    return chunks


def parse_timestamp_to_seconds(ts: str) -> float:
    """Convert 'MM:SS' or 'HH:MM:SS' to seconds."""
    parts = ts.strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    raise ValueError(f"Invalid timestamp format: '{ts}'. Use MM:SS or HH:MM:SS")

def parse_timestamp_range(ts: str) -> tuple[float, float]:
    """Parse a timestamp or range into (start_sec, end_sec).

    Supported formats:
        '4:30'               → single timestamp
        '4:30 - 5:00'        → hyphen-separated range
        '4:30 to 5:00'       → word-separated range
        '38:00 to 45:36'     → long timestamps
        '1:02:00 to 1:10:00' → HH:MM:SS ranges
    """
    ts = ts.strip()

    # Try splitting on ' to ' first (safest — no ambiguity with colons)
    if ' to ' in ts.lower():
        idx = ts.lower().index(' to ')
        left  = ts[:idx].strip()
        right = ts[idx + 4:].strip()
        return parse_timestamp_to_seconds(left), parse_timestamp_to_seconds(right)

    # Try splitting on ' - ' (space-hyphen-space, avoids splitting inside timestamps)
    if ' - ' in ts:
        parts = ts.split(' - ', 1)
        return parse_timestamp_to_seconds(parts[0].strip()), parse_timestamp_to_seconds(parts[1].strip())

    # Single timestamp
    return parse_timestamp_to_seconds(ts), parse_timestamp_to_seconds(ts)
