# Build: Local AI & Azure News Console

Build a **locally-hosted web dashboard** I open every morning to scan the latest AI news, Azure Cloud updates, and trending AI GitHub repos — each with a title, a short gist, and a clickable source link.

## Stack
- **Backend:** Python + FastAPI. Serves the API and static frontend on `http://localhost:8000`.
- **Frontend:** Single-page app (vanilla JS + Tailwind via CDN, or React if simpler for you). No build step required to run.
- **Storage:** SQLite (`news.db`) for caching fetched items, dedup, and read/unread state.
- **Runner:** Target **macOS**. One command starts everything via a `run.sh` (`chmod +x`) that creates a `python3 -m venv`, installs `requirements.txt`, starts the server, and runs `open http://localhost:8000`. Use `python3`/`pip3` throughout. Include a `README.md`.

## Data sources (fetch via RSS/Atom + public APIs, no paid keys)
**AI news / tech blogs**
- Anthropic news, OpenAI blog, Google AI/DeepMind blog, Hugging Face blog
- Ars Technica AI, VentureBeat AI, TechCrunch AI, The Verge AI
- Hacker News front page filtered to AI/LLM keywords

**Azure Cloud news / new features**
- Azure Updates feed (`https://azure.microsoft.com/en-us/updates/feed/`)
- Azure blog, Azure DevOps blog, Microsoft Tech Community (Azure), AKS release notes (GitHub releases)

**Trending GitHub repos**
- GitHub Search API sorted by stars, windowed to the last 7 days, for topics: `ai`, `llm`, `agents`, `mcp`, `claude`, `rag`, `azure`. No auth required, but support an optional `GITHUB_TOKEN` env var to raise rate limits.

Make sources a config list (`sources.yaml`) so I can add/remove feeds without touching code.

## Gist generation
- For each item, produce a 1–2 sentence gist. Default: extract/clean the feed summary.
- Optional AI-enhanced gists: if `ANTHROPIC_API_KEY` is set, summarize via the Anthropic API (`claude-haiku-4-5`); otherwise fall back to the feed summary. Make this a toggle in config.

## Backend behavior
- On refresh: fetch all sources concurrently (async), normalize to `{title, gist, url, source, category, published_at, image?}`, dedup by URL/title, store in SQLite.
- Cache results; only re-fetch sources older than a configurable TTL (default 60 min).
- Endpoints: `GET /api/news`, `GET /api/azure`, `GET /api/repos`, `POST /api/refresh`, `POST /api/item/{id}/read`.
- Graceful per-source failure — one dead feed must not break the page. Log failures.

## Frontend / UX
- Three sections: **AI News**, **Azure Updates**, **Trending AI Repos** — as tabs or columns.
- Each card: title (links out in new tab), gist, source badge, relative time (e.g. "3h ago"), and for repos: star count, language, ⭐-this-week delta.
- Top bar: prominent manual **Refresh** button (triggers `POST /api/refresh`, shows a spinner while fetching, then reloads cards), last-updated timestamp, search/filter box, category filter chips.
- Read/unread visual state; "new since last visit" highlight.
- Clean, modern, readable layout — card grid, dark mode default, responsive.
- Sorted newest-first; show source and timestamp clearly.

## macOS desktop launcher (one-click)
- Generate a double-clickable **`.app` bundle** (AppleScript/osascript wrapper, or a `.command` file if simpler) placed on the Desktop named **"AI News"**.
- On click: check if the server is already running on `localhost:8000` (health check); start it in the background if not, wait until it's ready, then `open http://localhost:8000`. Never launch a duplicate server.
- Give it a custom app icon (`.icns`) — generate a simple one and bundle it. Include a script/step that installs the launcher to the Desktop.
- Document in the README how to re-run the installer if the path changes.


- `REFRESH_TTL_MINUTES`, `GITHUB_TOKEN` (optional), `ANTHROPIC_API_KEY` (optional), `AI_GISTS_ENABLED`, `TRENDING_WINDOW_DAYS`, `MAX_ITEMS_PER_SOURCE`.

## Deliverables
- Full working project, runnable on macOS in one command (`./run.sh`).
- `requirements.txt`, `README.md` (macOS setup + run + how to add sources), `sources.yaml`, seed run that populates the DB on first start.
- Sensible error handling and logging throughout.

Build it end to end, then tell me the exact command to run and the URL to open.
