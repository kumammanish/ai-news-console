from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import HackerNewsConfig

logger = logging.getLogger(__name__)

_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=100"


async def fetch_hackernews(
    client: httpx.AsyncClient, config: HackerNewsConfig, max_items: int
) -> list[dict[str, Any]]:
    if not config.enabled:
        return []

    resp = await client.get(_ALGOLIA_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    keywords = [k.lower() for k in config.keywords]
    items: list[dict[str, Any]] = []
    for hit in data.get("hits", []):
        title = hit.get("title") or hit.get("story_title") or ""
        if not title:
            continue
        if keywords and not any(kw in title.lower() for kw in keywords):
            continue

        url = (
            hit.get("url")
            or hit.get("story_url")
            or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        )
        points = hit.get("points")
        items.append(
            {
                "title": title,
                "url": url,
                "source": "Hacker News",
                "category": "ai_news",
                "published_at": hit.get("created_at"),
                "image": None,
                "summary": f"{points} points on Hacker News." if points is not None else "",
            }
        )
        if len(items) >= max_items:
            break
    return items
