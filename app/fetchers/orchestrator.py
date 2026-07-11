from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app import db
from app.config import Settings, SourcesConfig, load_settings, load_sources
from app.fetchers.aks_releases import fetch_aks_releases
from app.fetchers.github_trending import fetch_github_trending
from app.fetchers.hackernews import fetch_hackernews
from app.fetchers.rss import fetch_feed
from app.summarize import make_gist

logger = logging.getLogger(__name__)

_GIST_CONCURRENCY = 8


def _matches_use_case_keywords(title: str, summary: str, keywords: list[str]) -> bool:
    text = f"{title} {summary}".lower()
    return any(kw.lower() in text for kw in keywords)


async def _within_ttl(source_name: str, ttl_minutes: int) -> bool:
    state = await db.get_source_state(source_name)
    if not state or not state.get("last_fetched_at"):
        return False
    last = datetime.fromisoformat(state["last_fetched_at"])
    return datetime.now(timezone.utc) - last < timedelta(minutes=ttl_minutes)


async def _run_source(
    name: str, coro
) -> tuple[str, list[dict[str, Any]], str | None]:
    try:
        items = await coro
        return name, items, None
    except Exception as exc:  # noqa: BLE001 - one dead source must not kill the refresh
        logger.warning("Source %r failed: %s", name, exc)
        return name, [], str(exc)


async def run_refresh(force: bool = False) -> dict[str, Any]:
    settings: Settings = load_settings()
    sources: SourcesConfig = load_sources()
    started_at = db.now_iso()

    jobs: list[asyncio.Task] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for feed in sources.feeds:
            if not feed.enabled:
                continue
            if not force and await _within_ttl(feed.name, settings.refresh_ttl_minutes):
                continue
            jobs.append(
                asyncio.create_task(
                    _run_source(feed.name, fetch_feed(client, feed, settings.max_items_per_source))
                )
            )

        if sources.hackernews.enabled and (
            force or not await _within_ttl("Hacker News", settings.refresh_ttl_minutes)
        ):
            jobs.append(
                asyncio.create_task(
                    _run_source(
                        "Hacker News",
                        fetch_hackernews(client, sources.hackernews, settings.max_items_per_source),
                    )
                )
            )

        if sources.github_topics.enabled and (
            force or not await _within_ttl("GitHub Trending", settings.refresh_ttl_minutes)
        ):
            jobs.append(
                asyncio.create_task(
                    _run_source(
                        "GitHub Trending",
                        fetch_github_trending(
                            client,
                            sources.github_topics,
                            settings.github_token,
                            settings.trending_window_days,
                            settings.max_items_per_source,
                        ),
                    )
                )
            )

        aks_name = f"{sources.aks_releases.repo} Releases"
        if sources.aks_releases.enabled and (
            force or not await _within_ttl(aks_name, settings.refresh_ttl_minutes)
        ):
            jobs.append(
                asyncio.create_task(
                    _run_source(
                        aks_name,
                        fetch_aks_releases(
                            client, sources.aks_releases, settings.github_token, settings.max_items_per_source
                        ),
                    )
                )
            )

        results = await asyncio.gather(*jobs) if jobs else []

    existing_gists = await db.get_existing_gists()

    all_items: list[dict[str, Any]] = []
    for _name, items, _error in results:
        for item in items:
            raw_summary = item.get("summary", "")
            item["is_use_case"] = item.pop("use_case", False) or _matches_use_case_keywords(
                item["title"], raw_summary, sources.use_cases.keywords
            )
            all_items.append(item)

    gist_semaphore = asyncio.Semaphore(_GIST_CONCURRENCY)

    async def _resolve_gist(item: dict[str, Any]) -> None:
        cached_gist = existing_gists.get(item["url"])
        if cached_gist is not None:
            item["gist"] = cached_gist
            return
        async with gist_semaphore:
            item["gist"] = await make_gist(item["title"], item.pop("summary", ""), settings)

    await asyncio.gather(*(_resolve_gist(item) for item in all_items))

    for item in all_items:
        await db.upsert_item(item)

    total_items = 0
    source_states = []
    for name, items, error in results:
        status = "ok" if error is None else "error"
        await db.set_source_state(name, status, error, len(items))
        source_states.append(
            {"name": name, "last_status": status, "last_error": error, "item_count": len(items)}
        )
        total_items += len(items)

    finished_at = db.now_iso()
    logger.info(
        "Refresh complete: %d source(s) run, %d item(s) upserted", len(results), total_items
    )
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "sources": source_states,
        "total_items": total_items,
    }
