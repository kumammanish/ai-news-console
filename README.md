# AI News Console

A locally-hosted dashboard for scanning the latest AI news, Microsoft/Azure
(AI + infrastructure) updates, trending AI GitHub repos, and real-world use
cases every morning — one page, four tabs, no accounts, no paid API keys
required. Weighted toward Microsoft enterprise products (Azure AI, Azure
infrastructure, Microsoft 365/Copilot, Power Platform, Security, GitHub/dev
tooling) since that's the intended reader's day job.

## Quick start (macOS)

```bash
./run.sh
```

This creates a `.venv`, installs dependencies, starts the server, and opens
`http://localhost:8000` in your browser once it's ready. On the very first
run it also does a one-time "seed fetch" of every enabled source before
serving the page, so the dashboard isn't empty on first load (this can take
up to ~60 seconds depending on how many feeds respond quickly).

**URL:** http://localhost:8000

Stop the server with `Ctrl+C` in the terminal it's running in.

## One-click Desktop launcher

```bash
./macos/install_launcher.sh
```

Creates **`AI News.app`** on your Desktop with a generated icon. Double-click
it any morning: it health-checks `localhost:8000`, starts the server in the
background only if it isn't already running (never spawns a duplicate), waits
until it's ready, then opens your browser. Re-run this script any time the
repo is moved — the app bundle bakes in an absolute path to `run.sh` at
install time.

## Configuration

Copy `.env.example` to `.env` and fill in what you want:

| Variable | Default | Purpose |
|---|---|---|
| `REFRESH_TTL_MINUTES` | `60` | Per-source cache TTL — a source won't be re-fetched sooner than this unless you force-refresh. |
| `GITHUB_TOKEN` | *(none)* | Optional. Raises GitHub API rate limits from 60/hr to 5000/hr. No scopes needed (public data only). |
| `GEMINI_API_KEY` | *(none)* | Optional. Primary AI-gist provider — a Google AI Studio API key (not the consumer Gemini Pro/Advanced subscription, which doesn't grant programmatic access on its own). |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model used for gists. |
| `ANTHROPIC_API_KEY` | *(none)* | Optional. Fallback AI-gist provider (`claude-haiku-4-5-20251001`) — used only if Gemini is unset or its call fails. |
| `AI_GISTS_ENABLED` | `false` | Toggle for AI gists. Falls back to a cleaned-up feed summary whenever this is off, both keys are missing, or both API calls fail. |
| `TRENDING_WINDOW_DAYS` | `7` | How far back "trending" GitHub search looks. |
| `MAX_ITEMS_PER_SOURCE` | `20` | Cap on items kept per individual source. |

## Adding or removing sources

Edit `sources.yaml` — no code changes needed. Each RSS/Atom feed is a `name` /
`category` (`ai_news` or `microsoft`) / `url` / `enabled` entry. Set
`use_case: true` on a feed to tag every item from it into the Use Cases tab
in addition to its normal tab. GitHub trending topics, the Hacker News
keyword list, the AKS releases repo, and the Use Cases keyword list (scanned
across every feed's title+summary, any category) are also configured there.

The **Microsoft** tab currently pulls from ~13 feeds: Azure Updates, Azure
Blog, Azure AI Blog, Azure Infrastructure Blog, Azure DevOps Blog, Tech
Community (Azure), Microsoft 365/Copilot, Power Platform, Microsoft Security,
GitHub Blog, .NET Blog, and Visual Studio Blog. Two additional customer-story
feeds exist in `sources.yaml` but are currently `enabled: false` (see below).

**Known caveats, already handled gracefully (one dead source never breaks the
page — check `data/app.log` if a tab looks thin):**
- Anthropic publishes no official RSS feed, so `sources.yaml` points at a
  community-maintained mirror of anthropic.com/news. Swap it out if it goes
  stale.
- Azure AI Blog, Azure Infrastructure Blog, and Tech Community (Azure) were
  all verified live and re-pointed at working URLs on 2026-07-11 (Azure Blog
  moved from `/topics/<slug>/feed/` to `/category/<slug>/feed/`; Tech
  Community moved from `/gxcuf89792/rss/...` to `/t5/s/gxcuf89792/rss/...`
  during a platform migration). Azure Infrastructure Blog is now a combined
  feed across five related Azure Blog categories, since there's no longer a
  single "infrastructure" category.
- **Azure Customer Stories** and **Microsoft Customer Stories** are disabled
  (`enabled: false`) — both source sites were confirmed to have no working
  RSS feed anymore as of 2026-07-11 (Microsoft's customer-stories site was
  rebuilt as a JS-driven search page with no feed). Re-enable only if you
  find a real replacement feed.
- The GitHub repo "star delta (this week)" is computed as `current stars −
  stars when we first saw the repo in our own database`, since GitHub's API
  has no historical star-count endpoint. It reads "new" until a repo has been
  seen across at least two refreshes.

## API

- `GET /api/news`, `GET /api/microsoft`, `GET /api/repos`, `GET /api/use-cases` — items for each tab, newest first.
- `POST /api/refresh?force=true|false` — re-fetch enabled sources (force bypasses the TTL); returns per-source status.
- `POST /api/item/{id}/read` — mark an item read.

## Project layout

```
app/            FastAPI backend, fetchers, gist generation, SQLite layer
static/         Vanilla-JS frontend (no build step)
macos/          Desktop launcher + icon generator
sources.yaml    Editable source list
data/           news.db + app.log (gitignored, created at runtime)
```

## Troubleshooting

- **A tab is empty or thin:** check `data/app.log` — failures are logged
  per-source and never take down the rest of the page.
- **Port 8000 already in use by something else:** stop that process, or edit
  `PORT` in `run.sh`.
- **Re-running `run.sh` after pulling changes:** it always re-installs
  `requirements.txt` into the existing `.venv`, so new dependencies are
  picked up automatically.
