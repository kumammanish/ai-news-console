from __future__ import annotations

import logging

from app.config import Settings
from app.textutils import strip_html, truncate_sentences

logger = logging.getLogger(__name__)

_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_anthropic_client = None
_gemini_client = None


def _get_anthropic_client(api_key: str):
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
    return _anthropic_client


def _get_gemini_client(api_key: str):
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _gist_prompt(title: str, fallback: str) -> str:
    return (
        "Write a concise 1-2 sentence gist (no preamble, no "
        "quotes) of this article for a news dashboard card.\n\n"
        f"Title: {title}\n\nSummary: {fallback}"
    )


async def _make_gist_gemini(title: str, fallback: str, settings: Settings) -> str | None:
    if not settings.gemini_api_key:
        return None
    try:
        client = _get_gemini_client(settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=_gist_prompt(title, fallback),
        )
        text = (response.text or "").strip()
        return text or None
    except Exception:
        logger.warning("Gemini gist generation failed for %r, trying next provider", title, exc_info=True)
        return None


async def _make_gist_anthropic(title: str, fallback: str, settings: Settings) -> str | None:
    if not settings.anthropic_api_key:
        return None
    try:
        client = _get_anthropic_client(settings.anthropic_api_key)
        response = await client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": _gist_prompt(title, fallback)}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return text or None
    except Exception:
        logger.warning("Anthropic gist generation failed for %r, trying next provider", title, exc_info=True)
        return None


async def make_gist(title: str, raw_summary: str, settings: Settings) -> str:
    """Produce a 1-2 sentence gist for an item.

    Defaults to a cleaned/truncated version of the feed's own summary.
    If AI_GISTS_ENABLED, tries Gemini first (GEMINI_API_KEY), then Anthropic
    (ANTHROPIC_API_KEY) if Gemini is unavailable or errors, falling back to
    the cleaned summary if neither is configured or both fail.
    """
    cleaned = truncate_sentences(strip_html(raw_summary), max_sentences=2, max_chars=280)
    fallback = cleaned or title

    if not settings.ai_gists_enabled:
        return fallback

    gist = await _make_gist_gemini(title, fallback, settings)
    if gist:
        return gist

    gist = await _make_gist_anthropic(title, fallback, settings)
    if gist:
        return gist

    return fallback
