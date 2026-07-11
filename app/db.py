from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.config import DATA_DIR, DB_PATH

logger = logging.getLogger(__name__)

_conn: aiosqlite.Connection | None = None
_lock = asyncio.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    gist TEXT,
    source TEXT,
    category TEXT NOT NULL,
    published_at TEXT,
    image TEXT,
    stars INTEGER,
    language TEXT,
    star_first_seen INTEGER,
    read INTEGER NOT NULL DEFAULT 0,
    is_use_case INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_published_at ON items(published_at);

CREATE TABLE IF NOT EXISTS sources_state (
    name TEXT PRIMARY KEY,
    last_fetched_at TEXT,
    last_status TEXT,
    last_error TEXT,
    item_count INTEGER DEFAULT 0
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> aiosqlite.Connection:
    global _conn
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _conn = await aiosqlite.connect(DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.executescript(SCHEMA)
    await _conn.commit()
    return _conn


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def _get_conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _conn


async def has_any_items() -> bool:
    conn = _get_conn()
    async with conn.execute("SELECT 1 FROM items LIMIT 1") as cur:
        row = await cur.fetchone()
        return row is not None


async def get_existing_gists() -> dict[str, str]:
    """Map of url -> gist for every item that already has one.

    Used to skip re-summarizing items the AI gist generator has already
    processed in a prior refresh — feeds re-serve the same recent items on
    every fetch, so without this every refresh would burn API tokens
    re-summarizing articles whose content hasn't changed.
    """
    conn = _get_conn()
    async with conn.execute("SELECT url, gist FROM items WHERE gist IS NOT NULL") as cur:
        rows = await cur.fetchall()
        return {r["url"]: r["gist"] for r in rows}


async def upsert_item(item: dict[str, Any]) -> None:
    """Insert a normalized item, or update it in place on URL conflict.

    `read`, `first_seen_at`, and `star_first_seen` are preserved across
    updates so re-fetching a source doesn't clear read state or reset the
    baseline used for the repo star-delta calculation.
    """
    conn = _get_conn()
    ts = now_iso()
    async with _lock:
        await conn.execute(
            """
            INSERT INTO items (
                url, title, gist, source, category, published_at, image,
                stars, language, star_first_seen, read, is_use_case, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                gist=excluded.gist,
                source=excluded.source,
                published_at=excluded.published_at,
                image=excluded.image,
                stars=excluded.stars,
                language=excluded.language,
                is_use_case=excluded.is_use_case,
                last_seen_at=excluded.last_seen_at
            """,
            (
                item["url"],
                item["title"],
                item.get("gist"),
                item.get("source"),
                item["category"],
                item.get("published_at"),
                item.get("image"),
                item.get("stars"),
                item.get("language"),
                item.get("stars"),  # star_first_seen, only used on INSERT
                int(bool(item.get("is_use_case", False))),
                ts,
                ts,
            ),
        )
        await conn.commit()


async def list_items(category: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    async with conn.execute(
        """
        SELECT id, url, title, gist, source, category, published_at, image,
               stars, language, star_first_seen, read, is_use_case, first_seen_at, last_seen_at
        FROM items
        WHERE category = ?
        ORDER BY COALESCE(published_at, first_seen_at) DESC
        """,
        (category,),
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def list_use_cases() -> list[dict[str, Any]]:
    """Items flagged as use cases, merged across categories (a dedicated
    case-study feed or a keyword match in any feed can set the flag)."""
    conn = _get_conn()
    async with conn.execute(
        """
        SELECT id, url, title, gist, source, category, published_at, image,
               stars, language, star_first_seen, read, is_use_case, first_seen_at, last_seen_at
        FROM items
        WHERE is_use_case = 1
        ORDER BY COALESCE(published_at, first_seen_at) DESC
        """
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def mark_read(item_id: int) -> bool:
    conn = _get_conn()
    async with _lock:
        cur = await conn.execute("UPDATE items SET read = 1 WHERE id = ?", (item_id,))
        await conn.commit()
        return cur.rowcount > 0


async def get_source_state(name: str) -> dict[str, Any] | None:
    conn = _get_conn()
    async with conn.execute(
        "SELECT * FROM sources_state WHERE name = ?", (name,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_source_state(
    name: str, status: str, error: str | None = None, item_count: int = 0
) -> None:
    conn = _get_conn()
    async with _lock:
        await conn.execute(
            """
            INSERT INTO sources_state (name, last_fetched_at, last_status, last_error, item_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                last_fetched_at=excluded.last_fetched_at,
                last_status=excluded.last_status,
                last_error=excluded.last_error,
                item_count=excluded.item_count
            """,
            (name, now_iso(), status, error, item_count),
        )
        await conn.commit()


async def all_source_states() -> list[dict[str, Any]]:
    conn = _get_conn()
    async with conn.execute("SELECT * FROM sources_state") as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
