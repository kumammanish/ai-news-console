from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    no_tags = _TAG_RE.sub(" ", text)
    unescaped = html.unescape(no_tags)
    return _WS_RE.sub(" ", unescaped).strip()


def truncate_sentences(text: str, max_sentences: int = 2, max_chars: int = 280) -> str:
    if not text:
        return ""
    sentences = _SENTENCE_RE.split(text)
    result = " ".join(sentences[:max_sentences]).strip()
    if len(result) > max_chars:
        result = result[: max_chars - 1].rstrip() + "…"
    return result
