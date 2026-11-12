# PatchIntel

> Every tracker shows Deadlock stats. Every archive shows patch notes.
> **PatchIntel answers the question nobody else does: did the patch actually work?**

PatchIntel is a Deadlock (Valve) analytics platform that automatically links every balance change in every patch to the measured stat outcome that followed it — win-rate deltas, pick-rate shifts, and build-order changes — and publishes a per-change verdict: **nerf worked / unclear / backfired**.

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

### `.env` keys

| Key | Required? | Where to get it |
|---|---|---|
| `STEAM_API_KEY` | Yes, for patch detection | steamcommunity.com/dev/apikey (free) |
| `OPENAI_API_KEY` | Optional | platform.openai.com — without it the pipeline uses a heuristic fallback |
| `DEADLOCK_API_KEY` | Optional | raises community API rate limits |
| `DATABASE_URL` | Optional | defaults to local SQLite; use `postgresql+psycopg://patchintel:patchintel@localhost:5432/patchintel` with `docker compose up -d` |

`.env` is gitignored. Never commit keys.

### Run it

```bash
# 1. Ingest patches (detect -> scrape full notes -> LLM extraction -> DB)
python -m app.pipeline.run --seed-entities

# 2. Serve the app
uvicorn app.main:app --reload
#    UI:  http://localhost:8000/
#    API: http://localhost:8000/api/patches  (docs at /docs)
```

### Test it

```bash
pytest                 # 9 passed, 1 skipped
# The skipped test is the golden-set LLM extraction gate; it runs only
# when a real OPENAI_API_KEY is present:
OPENAI_API_KEY=... pytest tests/test_golden_extraction.py -v
```

## Roadmap

- [x] **M1 — Patch pipeline:** Steam news watcher -> forum scraper -> LLM structured extraction -> Postgres -> read-only UI *(code complete, tests green)*
- [ ] **M2 — Stats layer:** community Deadlock API ingest, pre/post patch snapshots, verdict badges, hero/item pages
- [ ] **M3 — Personal layer:** Steam OpenID, match sync, sessionization, tilt analytics
- [ ] **M4 — Portfolio polish:** demo mode with seeded data, deploy, README screenshots
- [ ] **M5 — Companion desktop app:** live match detection feeding personal analytics

Docs: [full blueprint](docs/blueprint.md) · [M1 design review](docs/m1-design-review.md)

## Data credit

Match statistics are aggregated from the community Deadlock API and official Valve sources. PatchIntel caches aggressively and respects upstream rate limits. Community project, not affiliated with Valve.
