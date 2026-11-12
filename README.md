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
| Frontend | React + Vite + TypeScript, Tailwind CSS, Recharts, TanStack Query |
| Desktop app | TBD (Tauri or Electron) — post-M3 |
| Database | PostgreSQL (Neon/Supabase free tier in prod, Docker locally) |
| LLM | Structured-output patch summarization (OpenAI/Anthropic), Pydantic-validated |
| Data sources | Steam Web API, forums.playdeadlock.com, SteamDB GameTracking-Deadlock diffs, community Deadlock API |

## Monorepo layout

```
backend/     FastAPI API + ingest workers + pipeline logic
docs/        Blueprint, architecture notes, methodology
frontend/    (M1 later) React web app
desktop/     (post-M3) companion app
```

## Local dev (backend)

```bash
docker compose up -d            # Postgres
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in keys
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

## Roadmap

- [ ] **M1 — Patch pipeline:** Steam news watcher -> structured DB records -> LLM summaries -> read-only patch history UI
- [ ] **M2 — Stats layer:** community Deadlock API ingest, pre/post patch snapshots, verdict badges, hero/item pages
- [ ] **M3 — Personal layer:** Steam OpenID, match sync, sessionization, tilt analytics
- [ ] **M4 — Portfolio polish:** tests, demo mode with seeded data, deploy, README screenshots
- [ ] **M5 — Companion desktop app:** live match detection feeding personal analytics

Full blueprint: [docs/blueprint.md](docs/blueprint.md)

## Data credit

Match statistics are aggregated from the community Deadlock API and official Valve sources. PatchIntel caches aggressively and respects upstream rate limits.
