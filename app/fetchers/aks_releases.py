from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import AksReleasesConfig

logger = logging.getLogger(__name__)


async def fetch_aks_releases(
    client: httpx.AsyncClient,
    config: AksReleasesConfig,
    github_token: str | None,
    max_items: int,
) -> list[dict[str, Any]]:
    if not config.enabled:
        return []

    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    resp = await client.get(
        f"https://api.github.com/repos/{config.repo}/releases",
        params={"per_page": max_items},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    items: list[dict[str, Any]] = []
    for release in data:
        name = release.get("name") or release.get("tag_name")
        if not name:
            continue
        items.append(
            {
                "title": f"{config.repo}: {name}",
                "url": release.get("html_url"),
                "source": f"{config.repo} Releases",
                "category": "azure",
                "published_at": release.get("published_at"),
                "image": None,
                "summary": release.get("body") or "",
            }
        )
    return items
