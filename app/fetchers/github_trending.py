from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import GithubTopicsConfig

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://api.github.com/search/repositories"


def _headers(github_token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


async def fetch_github_trending(
    client: httpx.AsyncClient,
    config: GithubTopicsConfig,
    github_token: str | None,
    window_days: int,
    max_items: int,
) -> list[dict[str, Any]]:
    if not config.enabled:
        return []

    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%d")
    headers = _headers(github_token)

    # Dedup across topics (a repo can match several) while preserving highest star count seen.
    by_full_name: dict[str, dict[str, Any]] = {}
    for topic in config.topics:
        query = f"topic:{topic} pushed:>={since} stars:>={config.min_stars}"
        resp = await client.get(
            _SEARCH_URL,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": max_items},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        for repo in data.get("items", []):
            full_name = repo["full_name"]
            by_full_name[full_name] = {
                "title": full_name,
                "url": repo["html_url"],
                "source": "GitHub Trending",
                "category": "repos",
                "published_at": repo.get("pushed_at"),
                "image": (repo.get("owner") or {}).get("avatar_url"),
                "summary": repo.get("description") or "",
                "stars": repo.get("stargazers_count"),
                "language": repo.get("language"),
            }

    return list(by_full_name.values())
