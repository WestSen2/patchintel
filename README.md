# PatchIntel

> Every tracker shows Deadlock stats. Every archive shows patch notes.
> **PatchIntel answers the question nobody else does: did the patch actually work?**

PatchIntel is a Deadlock (Valve) analytics platform that automatically links every balance change in every patch to the measured stat outcome that followed it — win-rate deltas, pick-rate shifts, and build-order changes — and publishes a per-change verdict: **nerf worked / unclear / backfired**.

![Patch history](docs/screenshots/patches.png)

![Per-change verdicts with measured win-rate deltas](docs/screenshots/patch-impact.png)

![Item purchase-timing analytics](docs/screenshots/item-timing.png)

## Product shape

- **Web app** — patch impact reports, patch history timeline, hero/item pages with patch-boundary charts, build-order explorer, personal dashboard (Steam sign-in)
- **Companion desktop app** — Valorant Tracker-style: detects your live matches, feeds your personal session/tilt analytics, and delivers post-match insights. The app complements the site; the site is the public face.

## The three original pillars

1. **Patch -> Outcome Engine** — stat snapshots before/after every patch, per-change verdicts. No existing Deadlock tool treats *the change* as a first-class entity with measured evidence.
2. **Build-Order Mining** — win rate by purchase *timing and sequence*, build-path decision trees per hero. Existing tools show item win rates; nobody does deep path analysis.
3. **Personal Tilt & Session Analytics** — performance decay across sessions, loss-streak impact, time-of-day patterns. Completely unclaimed territory for Deadlock.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, APScheduler, authlib (Steam OpenID) |
| Frontend | Jinja2 + Tailwind (M1); React + Vite + TypeScript + Recharts (M2+) |
| Desktop app | Overwolf or Tauri — decided at M5 |
| Database | PostgreSQL (docker compose locally); SQLite allowed for quick dev |
| LLM | OpenAI structured-output patch extraction, Pydantic-validated; heuristic fallback when no key |
| Data sources | Steam Web API, forums.playdeadlock.com, SteamDB GameTracking-Deadlock diffs, community Deadlock API |

## Architecture

```mermaid
flowchart LR
    subgraph Upstream
        steam[Steam News API]
        forums[forums.playdeadlock.com]
        dlapi[Community Deadlock API]
        openid[Steam OpenID]
    end

    subgraph Backend["FastAPI backend (Python 3.12)"]
        pipeline[Patch pipeline\ndetect → enrich → LLM extract]
        stats[Stats ingest\nsnapshots · timing · verdicts]
        personal[Personal layer\nsync · sessionize · tilt]
        api[REST API]
    end

    subgraph Storage
        db[(PostgreSQL / SQLite)]
    end

    subgraph Frontend
        react[React SPA\npatches · heroes · items · dashboard]
    end

    steam --> pipeline
    forums --> pipeline
    dlapi --> stats
    dlapi --> personal
    openid --> personal
    pipeline --> db
    stats --> db
    personal --> db
    db --> api
    api --> react
```

## Monorepo layout

```
backend/     FastAPI API + ingest pipeline + server-rendered M1 UI
docs/        Blueprint, M1 design review, methodology
scripts/     One-off validation scripts (spike_deadlock_api.py)
frontend/    (M2) React web app
desktop/     (M5) companion app
```

## Local dev

```bash
git clone https://github.com/WestSen2/patchintel.git
cd patchintel/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys (see below)
```

### Database migrations (M3+)

The schema is managed by Alembic. Fresh clones can skip this — the app still
auto-creates tables on startup for dev. Existing databases from M1/M2 should
be stamped so future migrations apply cleanly:

```bash
cd backend
python -c "from app.db import init_db; init_db()"   # create any missing tables
alembic stamp head                                   # record current schema version
```

### `.env` keys

| Key | Required? | Where to get it |
|---|---|---|
| `STEAM_API_KEY` | Yes, for patch detection | steamcommunity.com/dev/apikey (free) |
| `OPENAI_API_KEY` | Optional | platform.openai.com — without it the pipeline uses a heuristic fallback |
| `DEADLOCK_API_KEY` | Optional | raises community API rate limits |
| `APP_SECRET_KEY` | Yes for login | any random string — signs the session cookie (`openssl rand -hex 32`) |
| `APP_BASE_URL` | Optional | defaults to `http://localhost:8000`; set to your public URL in production |
| `DATABASE_URL` | Optional | defaults to local SQLite; use `postgresql+psycopg://patchintel:patchintel@localhost:5432/patchintel` with `docker compose up -d` |

`.env` is gitignored. Never commit keys.

### Run it

```bash
# 1. Ingest patches (detect -> scrape full notes -> LLM extraction -> DB)
python -m app.pipeline.run --seed-entities

# 2. (M2) Backfill historical patches, then compute stat snapshots,
#    purchase-timing buckets, and verdicts. First do a quick trial run on a
#    few patches to sanity-check everything:
python -m app.pipeline.run --backfill --max-patches 3 --snapshots --timing --verdicts

#    Then the full run — takes a while (~10 upstream API calls per patch,
#    rate-limit friendly; safe to Ctrl-C and re-run, it resumes):
python -m app.pipeline.run --backfill --snapshots --timing --verdicts

# 3. Serve the API + fallback Jinja UI
uvicorn app.main:app --reload
#    UI:  http://localhost:8000/
#    API: http://localhost:8000/api/patches  (docs at /docs)
```

### Frontend (React, M2)

```bash
brew install node          # once, if you don't have Node
cd frontend
npm install
npm run dev                # http://localhost:5173 (proxies /api -> :8000)
```

The React app is the primary UI: patches list, patch impact (verdict badges,
stat blocks), hero pages with pre/post win-rate charts, and item pages with
purchase-timing breakdowns (avg buy time + early/mid/late win rates).

### Demo mode (no API keys needed)

```bash
python ../scripts/seed_demo.py   # fabricates 3 labeled demo patches + verdicts
DEMO_MODE=true uvicorn app.main:app
```

The site becomes fully browsable with fabricated, clearly labeled sample data —
for reviewers, screenshots, and deploys that must survive upstream outages.

### Test it

```bash
pytest                 # 54 passed, 1 skipped
# The skipped test is the golden-set LLM extraction gate; it runs only
# when a real OPENAI_API_KEY is present:
OPENAI_API_KEY=... pytest tests/test_golden_extraction.py -v
```

## Methodology

**Verdicts ("did the patch actually work?")** — For every extracted change, we
compare the affected entity's win rate in a pre window (7 days before the patch)
against a post window (days 1–8 after; day 0 excluded as a settling period).
Windows truncated by a follow-up hotfix are flagged. We use Wilson score 95%
confidence intervals, and any window under 500 matches is reported as
`insufficient_data` rather than drawing a conclusion. Verdicts:

- `worked` / `backfired` — win rate moved in the intended / opposite direction
  beyond the CI
- `shifted` — pick rate changed significantly while win rate held
- `unclear` / `no_effect` — movement inside the noise, or no measurable movement
- `excluded` — entity not comparable across the patch (e.g. new hero)

**Purchase timing** — Item win rates are split by when the item was bought
in-match: early (< 12:00), mid (12:00–24:00), late (> 24:00), plus the average
purchase time per patch window. This answers "is rushing this item still worth
it after the nerf?" — the stat nobody else publishes per patch.

**Every change carries its source line.** Extracted changes are only stored
when the exact sentence they came from is kept alongside them, so any verdict
can be traced back to the verbatim patch note.

## Roadmap

- [x] **M1 — Patch pipeline:** Steam news watcher -> forum scraper -> LLM structured extraction -> Postgres -> read-only UI *(code complete, tests green)*
- [x] **M2 — Stats layer:** community Deadlock API ingest, pre/post patch snapshots, item purchase-timing buckets, verdict badges, React hero/item pages *(code complete, tests green — data backfill in progress)*
- [ ] **M3 — Personal layer:** Steam OpenID, match sync, sessionization, tilt analytics *(code complete, tests green — awaiting live login test)*
- [ ] **M4 — Portfolio polish:** demo mode with seeded data *(done)*, deploy, README screenshots
- [ ] **M5 — Companion desktop app:** live match detection feeding personal analytics

Docs: [full blueprint](docs/blueprint.md) · [M1 design review](docs/m1-design-review.md) · [M2 design review](docs/m2-design-review.md) · [M2 item-timing addendum](docs/m2-addendum-item-timing.md) · [M3 design review](docs/m3-design-review.md) · [M4 design review](docs/m4-design-review.md)

## Data credit

Match statistics are aggregated from the community Deadlock API and official Valve sources. PatchIntel caches aggressively and respects upstream rate limits. Community project, not affiliated with Valve.
