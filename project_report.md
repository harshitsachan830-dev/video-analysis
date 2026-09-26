# VideoGPT Pro - Project Status Report

## 1. Project Overview
VideoGPT Pro is an advanced AI-powered YouTube learning platform. It extracts transcripts and visual data from YouTube videos to provide chat, chapterized notes, MCQs, memory mnemonics, and cross-video knowledge graphs using Google's Gemini models and FAISS vector search.

## 2. Architecture
*   **Backend:** FastAPI (Python)
*   **Frontend:** React + Vite
*   **AI Engine:** Google Gemini (gemini-2.5-flash)
*   **Vector Database:** FAISS (Local)
*   **Storage:** Local JSON/Pickle (`/backend/video_store/`)

## 3. Features Implemented (Completed)

### Core Pipeline
*   **Video Indexing:** Extracts YouTube transcripts and builds a FAISS vector index for fast semantic search.
*   **RAG Chat:** Conversational AI that answers questions using the video's transcript as context, providing exact timestamp citations.
*   **Persistent Storage:** Videos are saved to disk so they don't need to be re-indexed on reload.

### Advanced AI Features
*   **Timestamp Queries:** Users can query specific timestamps or ranges (e.g., "38:00 to 45:36") to understand exactly what happened.
*   **Visual Extraction:** Uses `yt-dlp` and `cv2` to extract frames and Gemini Vision to extract slide text, whiteboard handwriting, and diagrams. Includes rate-limit retry logic.
*   **Study Materials Generation:** Automatically generates Chapter Notes, MCQs, Mnemonics, and Interview Questions.
*   **Fact Checking:** Ability to verify AI chat responses against the source transcript.

### Phase 3 & Startup-Grade Features
*   **Course / Playlist Mode:** Pass a YouTube Playlist URL and the backend automatically fetches and indexes all videos in the playlist.
*   **Knowledge Graph:** Analyzes multiple indexed videos to find overlapping concepts and visualizes them as a concept map.
*   **Analytics Dashboard:** Tracks study sessions, total time, MCQ accuracy, and generates a personalized learning profile highlighting weak topics.
*   **Robustness:** Implemented exponential backoff for Gemini API rate limits (429/503 errors).

## 4. Work In Progress (Unfinished)

### Spaced Repetition (SM-2 Algorithm)
*   **Status:** Backend engine created (`backend/spaced_repetition.py`), but not integrated.
*   **What's Done:** The core SM-2 scheduling algorithm and local JSON storage logic are implemented.
*   **What's Missing:**
    *   FastAPI routes in `main.py` (e.g., `/sr/schedule`, `/sr/due`, `/sr/review`).
    *   Frontend React tab (`Review`) to display due cards and allow the user to rate difficulty (Hard/Good/Easy).

## 5. Next Steps for Handover
To complete the Spaced Repetition feature:
1.  Import `spaced_repetition` into `main.py` and expose the REST endpoints.
2.  In `App.jsx`, add a new Tab for Spaced Repetition.
3.  Fetch due cards on load, and render a UI to review them and submit quality scores (0-3).
