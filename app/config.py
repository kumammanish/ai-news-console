from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "news.db"
SOURCES_PATH = BASE_DIR / "sources.yaml"

load_dotenv(BASE_DIR / ".env")


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    refresh_ttl_minutes: int = int(os.environ.get("REFRESH_TTL_MINUTES", "60"))
    github_token: str | None = os.environ.get("GITHUB_TOKEN") or None
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY") or None
    gemini_api_key: str | None = os.environ.get("GEMINI_API_KEY") or None
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    ai_gists_enabled: bool = _bool_env("AI_GISTS_ENABLED", False)
    trending_window_days: int = int(os.environ.get("TRENDING_WINDOW_DAYS", "7"))
    max_items_per_source: int = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "20"))


@dataclass(frozen=True)
class FeedSource:
    name: str
    category: str
    url: str
    enabled: bool = True
    use_case: bool = False  # every item from this feed is tagged as a "use case"


@dataclass(frozen=True)
class HackerNewsConfig:
    enabled: bool = True
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GithubTopicsConfig:
    enabled: bool = True
    topics: list[str] = field(default_factory=list)
    min_stars: int = 0


@dataclass(frozen=True)
class AksReleasesConfig:
    enabled: bool = True
    repo: str = "Azure/AKS"


@dataclass(frozen=True)
class UseCasesConfig:
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourcesConfig:
    feeds: list[FeedSource]
    hackernews: HackerNewsConfig
    github_topics: GithubTopicsConfig
    aks_releases: AksReleasesConfig
    use_cases: UseCasesConfig


def load_settings() -> Settings:
    return Settings()


def load_sources(path: Path = SOURCES_PATH) -> SourcesConfig:
    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}

    feeds = [FeedSource(**f) for f in raw.get("feeds", [])]
    hn_raw = raw.get("hackernews", {}) or {}
    gh_raw = raw.get("github_topics", {}) or {}
    aks_raw = raw.get("aks_releases", {}) or {}
    uc_raw = raw.get("use_cases", {}) or {}

    return SourcesConfig(
        feeds=feeds,
        hackernews=HackerNewsConfig(**hn_raw),
        github_topics=GithubTopicsConfig(**gh_raw),
        aks_releases=AksReleasesConfig(**aks_raw),
        use_cases=UseCasesConfig(**uc_raw),
    )
