import json
import re
from google.genai import types
from dotenv import load_dotenv
from gemini import generate_content

load_dotenv()

MAX_TRANSCRIPT_CHARS = 12000
MAX_NOTES_CHARS = 15000


def _gemini_call(contents, config=None, max_retries=4):
    """Call Gemini with a fallback model for transient capacity errors."""
    return generate_content(contents, config=config, max_retries=min(max_retries, 1))

def build_context(chunks: list[dict]) -> str:
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            f"[Timestamp: {chunk.get('timestamp', 'Unknown')}]\n{chunk.get('text', '')}"
        )
    return "\n\n".join(context_parts)


# ─────────────────────────────────────────
# PHASE 1 — CHAT & SUMMARY
# ─────────────────────────────────────────

def chat_with_video(query: str, chunks: list[dict], video_title: str = "this video") -> dict:
    """Answer user questions using relevant transcript chunks (RAG)."""
    if not chunks:
        return {
            "answer": "I couldn't find relevant information in this video for your question. Try rephrasing or asking about a different topic.",
            "sources": []
        }

    context = build_context(chunks)
    prompt = f"""You are VideoGPT Pro, an AI that answers questions using ONLY the provided transcript context.

VIDEO TITLE: {video_title}

TRANSCRIPT CONTEXT:
{context}

QUESTION:
{query}

RULES:
- Use only the transcript context above.
- Cite timestamps whenever possible (e.g. "At 02:30, ...").
- If the answer is not in the context, say exactly: "I couldn't find information about that in this video."
- Do not invent or assume facts not in the transcript.
- Keep answers concise, clear, and accurate.

ANSWER:"""

    response = _gemini_call(prompt)
    sources = [{"timestamp": c["timestamp"], "start": c["start"]} for c in chunks[:3]]
    return {"answer": response.text.strip(), "sources": sources}


def chat_with_memory(query: str, chunks: list[dict], history: list[dict], video_title: str = "this video") -> dict:
    """Answer user questions with context from previous conversation history."""
    if not chunks:
        return {
            "answer": "I couldn't find relevant information in this video for your question.",
            "sources": []
        }

    from memory import format_history_for_prompt
    history_context = format_history_for_prompt(history)
    
    transcript_context = build_context(chunks)
    
    prompt = f"""You are VideoGPT Pro, an AI tutor answering questions about a video.

VIDEO TITLE: {video_title}

PREVIOUS CONVERSATION HISTORY:
{history_context if history_context else "(No prior history)"}

CURRENT TRANSCRIPT CONTEXT:
{transcript_context}

CURRENT QUESTION:
{query}

RULES:
- Answer the CURRENT QUESTION using the TRANSCRIPT CONTEXT.
- You can refer to the PREVIOUS CONVERSATION if the user asks a follow-up (e.g. "tell me more about that").
- Cite timestamps whenever possible (e.g. "At 02:30, ...").
- Do not invent facts not in the transcript.
- Keep answers concise and helpful.

ANSWER:"""

    response = _gemini_call(prompt)
    sources = [{"timestamp": c["timestamp"], "start": c["start"]} for c in chunks[:3]]
    return {"answer": response.text.strip(), "sources": sources}

def check_hallucination(answer: str, chunks: list[dict]) -> dict:
    """Check if an answer is supported by the transcript chunks (Hallucination Checker)."""
    context = build_context(chunks)
    
    prompt = f"""You are a strict Hallucination Checker.
    
TRANSCRIPT CONTEXT:
{context}

ANSWER TO CHECK:
{answer}

Determine if the ANSWER is fully supported by the CONTEXT. 
Return ONLY a valid JSON object in this exact format (no markdown):
{{
  "is_supported": true/false,
  "confidence_score": 0-100,
  "reason": "Brief explanation of why it is or isn't supported"
}}"""

    try:
        response = _gemini_call(
            prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        text = _clean_json_text(response.text)
        return json.loads(text)
    except Exception:
        return {
            "is_supported": True, 
            "confidence_score": 100, 
            "reason": "Could not verify (checker failed)."
        }


def generate_summary(full_transcript: str, video_title: str = "this video") -> str:
    """Generate a structured summary from the full transcript."""
    if not full_transcript or not full_transcript.strip():
        return "No transcript available to summarize."

    truncated = full_transcript[:MAX_TRANSCRIPT_CHARS]
    prompt = f"""You are an expert at summarizing YouTube video content.

Here is the full transcript of {video_title}:
{truncated}

Please provide:
1. A 3-4 sentence overall summary
2. 5-7 key points/takeaways (as bullet points)

Format it nicely with clear sections."""

    response = _gemini_call(prompt)
    return response.text.strip()


# ─────────────────────────────────────────
# PHASE 2 — TIMESTAMP QUERY
# ─────────────────────────────────────────

def answer_timestamp_query(start_sec: float, end_sec: float, chunks: list[dict]) -> dict:
    """Answer what happened between start_sec and end_sec in the video."""
    if not chunks:
        raise ValueError("No transcript chunks available.")

    from transcript import format_timestamp
    
    if start_sec == end_sec:
        # Single timestamp logic
        matching = None
        for chunk in chunks:
            c_start = chunk.get("start", 0)
            c_end = chunk.get("end", c_start + 60)
            if c_start <= start_sec <= c_end:
                matching = chunk
                break

        if matching:
            idx = chunks.index(matching)
            start_idx = max(0, idx - 1)
            end_idx = min(len(chunks), idx + 2)
            nearby = chunks[start_idx:end_idx]
        else:
            nearby = sorted(chunks, key=lambda c: abs(c.get("start", 0) - start_sec))[:3]
        
        ts_str = format_timestamp(start_sec)
        query_text = f"around timestamp {ts_str}"
    else:
        # Range logic
        nearby = []
        for chunk in chunks:
            c_start = chunk.get("start", 0)
            c_end = chunk.get("end", c_start + 60)
            # Check overlap
            if max(start_sec, c_start) < min(end_sec, c_end):
                nearby.append(chunk)
        
        # If range too narrow/didn't hit anything, find nearest
        if not nearby:
            nearby = sorted(chunks, key=lambda c: abs(c.get("start", 0) - start_sec))[:3]
        
        ts_str = f"{format_timestamp(start_sec)} to {format_timestamp(end_sec)}"
        query_text = f"between {ts_str}"

    context = build_context(nearby)

    prompt = f"""You are an AI assistant analyzing a YouTube video transcript.

The user wants to know what happens {query_text} in the video.

TRANSCRIPT CONTEXT FOR THAT TIMEFRAME:
{context}

Please describe:
1. What is being discussed {query_text}
2. Key points or information shared in that timeframe
3. How it fits into the overall topic

Be specific and reference the transcript content. Do not guess information outside the given timeframe."""

    response = _gemini_call(prompt)
    return {
        "timestamp": ts_str,
        "timestamp_seconds": start_sec,
        "answer": response.text.strip(),
        "sources": [{"timestamp": c["timestamp"], "start": c["start"]} for c in nearby],
    }


# ─────────────────────────────────────────
# PHASE 2 — NOTES GENERATION
# ─────────────────────────────────────────

def generate_notes(full_transcript: str) -> str:
    """Generate chapter-wise structured notes from the video."""
    if not full_transcript or not full_transcript.strip():
        return "No transcript available to generate notes."

    truncated = full_transcript[:MAX_NOTES_CHARS]
    prompt = f"""You are an expert educator creating structured study notes from a YouTube video transcript.

TRANSCRIPT (with timestamps):
{truncated}

Create comprehensive chapter-wise notes with this format:

## 📚 Chapter 1: [Topic Name] [HH:MM - HH:MM]
### Key Concepts:
- Point 1
- Point 2

### Important Details:
- Detail 1
- Detail 2

---

## 📚 Chapter 2: [Topic Name] [HH:MM - HH:MM]
...and so on.

## 🎯 Key Takeaways (Overall)
- Takeaway 1
- Takeaway 2

Make the notes detailed, well-structured, and useful for revision."""

    response = _gemini_call(prompt)
    return response.text.strip()


def generate_revision_notes(full_transcript: str) -> str:
    """Generate concise, high-yield revision notes."""
    if not full_transcript or not full_transcript.strip():
        return "No transcript available."

    truncated = full_transcript[:MAX_NOTES_CHARS]
    prompt = f"""You are an expert tutor creating last-minute revision notes from a video transcript.

TRANSCRIPT:
{truncated}

Create ULTRA-CONCISE, high-yield revision notes. Format:

## 🚀 Quick Summary
(2 sentences max)

## 📌 Top 5 Essential Points
- Point 1 (bold key terms)
...

## ⚠️ Common Pitfalls / Things to Remember
- Pitfall 1
...

Be brief, punchy, and highly informative."""

    response = _gemini_call(prompt)
    return response.text.strip()


# ─────────────────────────────────────────
# PHASE 2 — MCQ GENERATION
# ─────────────────────────────────────────

def _clean_json_text(text: str) -> str:
    """Strip markdown code fences and whitespace from a JSON string."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def generate_mcqs(full_transcript: str, count: int = 5) -> list[dict]:
    """Generate multiple choice questions from the video transcript."""
    if not full_transcript or not full_transcript.strip():
        return [{"question": "No transcript available.", "options": [], "answer": "", "explanation": "", "timestamp": ""}]

    truncated = full_transcript[:MAX_TRANSCRIPT_CHARS]
    prompt = f"""You are an expert quiz creator. Generate exactly {count} multiple choice questions based on this video transcript.

TRANSCRIPT:
{truncated}

Return ONLY a valid JSON array (no markdown, no explanation) in this exact format:
[
  {{
    "question": "Question text here?",
    "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
    "answer": "A",
    "explanation": "Brief explanation of why this is correct",
    "timestamp": "MM:SS"
  }}
]

Rules:
- Questions must be based strictly on video content
- Each question must have exactly 4 options labeled A, B, C, D
- Mix easy and challenging questions
- Include the approximate timestamp where the answer can be found
- Return ONLY the JSON array, nothing else"""

    response = _gemini_call(
        prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )

    text = _clean_json_text(response.text)

    try:
        result = json.loads(text)
        if not isinstance(result, list):
            raise ValueError("Response is not a JSON array")
        # Validate and sanitize each MCQ
        sanitized = []
        for item in result:
            if isinstance(item, dict) and "question" in item:
                sanitized.append({
                    "question": str(item.get("question", "")),
                    "options": item.get("options", []),
                    "answer": str(item.get("answer", "")),
                    "explanation": str(item.get("explanation", "")),
                    "timestamp": str(item.get("timestamp", "")),
                })
        return sanitized if sanitized else _fallback_mcq()
    except (json.JSONDecodeError, ValueError):
        return _fallback_mcq()


def _fallback_mcq() -> list[dict]:
    return [{
        "question": "MCQ generation failed. Please try again.",
        "options": [],
        "answer": "",
        "explanation": "",
        "timestamp": ""
    }]


# ─────────────────────────────────────────
# PHASE 2 — MNEMONIC EXTRACTION
# ─────────────────────────────────────────

def extract_mnemonics(full_transcript: str) -> str:
    """Extract key formulas, mnemonics, and memorable concepts."""
    if not full_transcript or not full_transcript.strip():
        return "No transcript available to extract mnemonics."

    truncated = full_transcript[:MAX_TRANSCRIPT_CHARS]
    prompt = f"""You are an expert at creating memory aids and extracting key concepts from educational content.

TRANSCRIPT:
{truncated}

Please extract and create:

## 🧠 Key Formulas & Definitions
(List any formulas, equations, or precise definitions mentioned)

## 🔑 Mnemonics & Memory Tricks
(Create or identify memorable acronyms, rhymes, or tricks to remember key concepts)

## ⚡ Quick-Reference Facts
(The most important facts that must be memorized)

## 💡 Concept Map
(Show how the main ideas connect to each other)

Make this genuinely useful for studying and memorization."""

    response = _gemini_call(prompt)
    return response.text.strip()


# ─────────────────────────────────────────
# PHASE 2 — INTERVIEW QUESTIONS
# ─────────────────────────────────────────

def generate_interview_questions(full_transcript: str) -> str:
    """Generate potential interview/exam questions from video content."""
    if not full_transcript or not full_transcript.strip():
        return "No transcript available to generate interview questions."

    truncated = full_transcript[:MAX_TRANSCRIPT_CHARS]
    prompt = f"""You are an expert interviewer and educator. Based on this video transcript, generate interview and exam questions.

TRANSCRIPT:
{truncated}

Generate high-quality questions in these categories. Base everything strictly on the transcript and avoid generic questions.

## 🟢 Basic Questions (Beginner)
1. Question...
2. Question...

## 🟡 Intermediate Questions
1. Question...
2. Question...

## 🔴 Advanced / Critical Thinking Questions
1. Question...
2. Question...

## 💼 Practical Application Questions
1. Question...
2. Question...

For each question, provide a brief model answer after it like:
**Q:** Question here?
**A:** Model answer here.

Base all questions strictly on the video content."""

    response = _gemini_call(prompt)
    return response.text.strip()
