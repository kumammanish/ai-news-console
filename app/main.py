from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.fetchers.orchestrator import run_refresh
from app.logging_conf import setup_logging
from app.models import Item, RefreshResult

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

SEED_FETCH_TIMEOUT_SECONDS = 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await db.init_db()

    if not await db.has_any_items():
        logger.info("Empty database detected — running seed fetch before serving")
        try:
            await asyncio.wait_for(run_refresh(force=True), timeout=SEED_FETCH_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(
                "Seed fetch exceeded %ss — serving with whatever was fetched so far; "
                "click Refresh once the page loads",
                SEED_FETCH_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("Seed fetch failed — serving an empty dashboard")

    yield
    await db.close_db()


app = FastAPI(title="AI News Console", lifespan=lifespan)


def _row_to_item(row: dict) -> Item:
    star_delta = None
    if row.get("stars") is not None and row.get("star_first_seen") is not None:
        star_delta = row["stars"] - row["star_first_seen"]
    return Item(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        gist=row.get("gist"),
        source=row.get("source"),
        category=row["category"],
        published_at=row.get("published_at"),
        image=row.get("image"),
        stars=row.get("stars"),
        language=row.get("language"),
        star_delta=star_delta,
        read=bool(row["read"]),
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
    )


async def _category_items(category: str) -> list[Item]:
    rows = await db.list_items(category)
    return [_row_to_item(r) for r in rows]


@app.get("/api/news", response_model=list[Item])
async def get_news():
    return await _category_items("ai_news")


@app.get("/api/microsoft", response_model=list[Item])
async def get_microsoft():
    return await _category_items("microsoft")


@app.get("/api/repos", response_model=list[Item])
async def get_repos():
    return await _category_items("repos")


@app.get("/api/use-cases", response_model=list[Item])
async def get_use_cases():
    rows = await db.list_use_cases()
    return [_row_to_item(r) for r in rows]


@app.post("/api/refresh", response_model=RefreshResult)
async def post_refresh(force: bool = False):
    result = await run_refresh(force=force)
    return RefreshResult(**result)


@app.post("/api/item/{item_id}/read")
async def post_item_read(item_id: int):
    ok = await db.mark_read(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
