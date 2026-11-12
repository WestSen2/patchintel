# M4 Design Review — Portfolio Polish (demo mode, deploy, presentation)

Status: **DRAFT for review** — not yet implemented
Date: 2026-11-12
Depends on: M2 (accepted by user, "works flawless"), M3 (code complete, live
login test pending)

---

## 1. Why M4 exists

The target audience for this repo is a recruiter, hiring manager, or admissions
reviewer who will give it **under 5 minutes**. M1–M3 built the substance; M4
makes the substance visible without requiring the reviewer to run anything.

## 2. Scope

1. **Demo mode / seed script** — one command (`scripts/seed_demo.py`) fills a
   fresh DB with realistic fabricated data: 3 patches with extracted changes,
   pre/post snapshots, verdicts, item timing buckets. The site is fully
   browsable with zero API keys. Doubles as outage resilience (blueprint
   risk #2) and as the data source for screenshots.
2. **README glow-up** — hero screenshot, architecture diagram (Mermaid),
   feature tour, methodology link, setup in 5 commands.
3. **Deployment** — backend on Render/Fly (free tier, Postgres or SQLite
   volume), frontend on Vercel. Env vars documented. Demo mode ON in prod so
   the deployed site works even before the first real ingest.
4. **Screenshots/GIFs** — captured from the demo-seeded site, committed to
   `docs/screenshots/`, referenced from the README hero section.

Out of scope: custom domain, CI deploy pipelines (nice-to-have, not needed),
any new analytics features.

## 3. Demo data design

- Fabricate 3 fictional-but-plausible patches ("Gameplay Update — demo") with
  8–12 changes each across 6 heroes and 4 items, drawn from the real seeded
  hero/item tables when present (fall back to hardcoded IDs).
- Snapshots: realistic win rates 45–55%, matches 2k–50k per window, deltas
  sized to exercise every verdict type (worked, backfired, unclear, shifted,
  insufficient_data).
- Clearly labeled: `summary` starts with "[DEMO DATA]" and the UI footer shows
  a demo banner when `DEMO_MODE=true`. Fabricated stats must never be
  mistaken for real measurements — that would undermine the project's whole
  credibility claim.
- `python scripts/seed_demo.py` is idempotent (skips if demo rows exist).

## 4. Deploy plan

| Piece | Host | Notes |
|---|---|---|
| Backend | Render free web service | `uvicorn app.main:app`, health check `/health` |
| DB | SQLite on a Render disk | simplest; Postgres upgrade path stays in compose |
| Frontend | Vercel | `frontend/`, `VITE_API_BASE` env → backend URL |
| Pipeline | Render cron job | `python -m app.pipeline.run` every 6h |

Frontend change required: `api.ts` currently hardcodes same-origin `/api` —
add `import.meta.env.VITE_API_BASE` prefix. CORS middleware on FastAPI
allowing the Vercel origin.

## 5. README structure (blueprint §9)

1. Hero: one-liner + live demo link + screenshot
2. Why this exists (originality paragraph)
3. Feature tour with screenshots
4. Architecture diagram
5. Methodology (already written)
6. Stack, setup, testing
7. Roadmap / limitations

## 6. Acceptance checklist

- [ ] `seed_demo.py` fills a fresh DB; site browsable with no keys
- [ ] Demo banner visible; demo data clearly labeled
- [ ] Frontend builds with configurable API base; CORS configured
- [ ] Deployed URL in README, loads for a stranger
- [ ] Screenshots in README render on the GitHub repo page
- [ ] Full test suite still green
