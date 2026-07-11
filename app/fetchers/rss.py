from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.config import FeedSource
from app.textutils import strip_html

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "ai-news-console/1.0 (local dashboard; +http://localhost:8000)"}


def _parse_date(entry: dict[str, Any]) -> str | None:
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if not struct:
        return None
    ts = calendar.timegm(struct)
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _extract_image(entry: dict[str, Any]) -> str | None:
    media_thumb = entry.get("media_thumbnail")
    if media_thumb and isinstance(media_thumb, list):
        url = media_thumb[0].get("url")
        if url:
            return url
    media_content = entry.get("media_content")
    if media_content and isinstance(media_content, list):
        url = media_content[0].get("url")
        if url:
            return url
    for link in entry.get("links", []) or []:
        if str(link.get("type", "")).startswith("image/"):
            return link.get("href")
    return None


async def fetch_feed(
    client: httpx.AsyncClient, feed: FeedSource, max_items: int
) -> list[dict[str, Any]]:
    resp = await client.get(feed.url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    parsed = await asyncio.to_thread(feedparser.parse, resp.content)

    items: list[dict[str, Any]] = []
    for entry in parsed.entries[:max_items]:
        title = (entry.get("title") or "").strip()
        link = entry.get("link")
        if not title or not link:
            continue
        summary_raw = entry.get("summary") or entry.get("description") or ""
        items.append(
            {
                "title": title,
                "url": link,
                "source": feed.name,
                "category": feed.category,
                "published_at": _parse_date(entry),
                "image": _extract_image(entry),
                "summary": strip_html(summary_raw),
                "use_case": feed.use_case,
            }
        )
    return items
