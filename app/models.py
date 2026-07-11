from __future__ import annotations

from pydantic import BaseModel


class Item(BaseModel):
    id: int
    url: str
    title: str
    gist: str | None = None
    source: str | None = None
    category: str
    published_at: str | None = None
    image: str | None = None
    stars: int | None = None
    language: str | None = None
    star_delta: int | None = None
    read: bool
    first_seen_at: str
    last_seen_at: str


class SourceState(BaseModel):
    name: str
    last_fetched_at: str | None = None
    last_status: str | None = None
    last_error: str | None = None
    item_count: int = 0


class RefreshResult(BaseModel):
    started_at: str
    finished_at: str
    sources: list[SourceState]
    total_items: int
