import os
from contextvars import ContextVar
from dataclasses import dataclass

from google import genai


@dataclass
class GeminiRequestContext:
    api_key: str | None
    client: genai.Client | None = None


_request_context: ContextVar[GeminiRequestContext | None] = ContextVar(
    "gemini_request_context",
    default=None,
)


def set_request_api_key(api_key: str | None):
    context = GeminiRequestContext(api_key=api_key)
    return _request_context.set(context)


def reset_request_context(token) -> None:
    _request_context.reset(token)


def get_gemini_client() -> genai.Client:
    context = _request_context.get()
    api_key = (context.api_key if context else None) or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Add your Gemini API key in Settings to use AI features.")

    if context:
        if context.client is None:
            context.client = genai.Client(api_key=api_key)
        return context.client

    return genai.Client(api_key=api_key)
