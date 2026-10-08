import os
import time
from contextvars import ContextVar
from dataclasses import dataclass

from google import genai

GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"


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


def generate_content(contents, config=None, max_retries: int = 1):
    client = get_gemini_client()
    last_error = None

    for model in (GEMINI_MODEL, GEMINI_FALLBACK_MODEL):
        for attempt in range(max_retries + 1):
            kwargs = {"model": model, "contents": contents}
            if config:
                kwargs["config"] = config
            try:
                return client.models.generate_content(**kwargs)
            except Exception as error:
                last_error = error
                message = str(error)
                is_transient = any(
                    marker in message
                    for marker in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
                )
                if not is_transient:
                    raise
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                break

    raise RuntimeError(
        "Gemini is temporarily unavailable on the primary and fallback models. "
        "Please wait a moment and try again."
    ) from last_error
