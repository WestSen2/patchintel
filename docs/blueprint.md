# PatchIntel — Deadlock Patch Impact & Analytics Platform
## Full Project Blueprint

**Owner:** WestSen2
**Stack:** Python (backend) + React (frontend) + PostgreSQL
**One-liner:** "Every tracker shows Deadlock stats. Every archive shows patch notes. PatchIntel answers the question nobody else does: *did the patch actually work?*"

---

## 1. Originality Analysis — Why This Isn't "Another Tracker"

### What already exists (be able to name these in interviews)
| Existing tool | What it does | What it does NOT do |
|---|---|---|
| Statlocker.gg | Player profiles, hero/item win rates, item timing skim | No patch-to-stat causation, no personal session/tilt analytics |
| Deadlock Labs | Tier lists, item win rates, patch notes with buff/nerf tags | Static summaries; doesn't measure stat outcomes of each change |
| Tracker.gg | Profiles, match history, leaderboards | Generic cross-game platform, zero patch intelligence |
| deadlockpatchnotes.com / deadlock-update.com | Patch note archives | Pure archives — no data, no analysis |
| deadlock-api.com | Community data API | It's a data source, not a product |

### The three original pillars
1. **Patch → Outcome Engine (flagship).** Every balance change is automatically linked to the actual stat delta that followed. "Warden fire rate −20% → win rate 52.1% → 49.3%, pick rate −18%. Verdict: nerf worked." No existing site treats *the change* as a first-class entity with measured before/after evidence. This is the headline originality claim.
2. **Build-Order Mining.** Not "item X has 53% win rate" (exists everywhere) but *sequence and timing* analysis: win rate by first-T3-item timing, build-path decision trees per hero, "players who delay Lifesteal past minute 14 lose 9% more." Existing tools skim timing; none do deep path analysis.
3. **Personal Tilt & Session Analytics.** Steam login → your match history → performance decay across sessions, loss-streak impact, time-of-day effects, "you win 22% less on game 5+ of a session." Nobody has built this for Deadlock at all.

### Your interview/college story
> "I play Deadlock and used the existing trackers. I noticed they all show what the meta *is*, and archives show what Valve *changed*, but nobody measured whether each change *did what it was supposed to*. So I built a pipeline that parses every patch, snapshots match statistics around it, and publishes a verdict on every buff and nerf — plus personal analytics that tell me when I'm tilted and should stop queueing."

That is a data-engineering + statistics + product-thinking story in one sentence.

---

## 2. What the Finished Product Displays

### A. Latest Patch Impact Report (landing page)
- LLM-generated clean summary of the newest patch: every change tagged buff/nerf/rework/adjustment, with exact numbers extracted
- "Top movers" cards: heroes/items whose win rate shifted most since the patch
- Patch verdict list: each change with before/after stats and a green/yellow/red "worked / unclear / backfired" badge

### B. Patch History Timeline
- Full archive of every Deadlock patch, structured and searchable
- Filter by hero, item, or change type
- Each patch page: structured changes + the measured meta impact

### C. Hero Pages
- Complete change history across all patches ("Warden has been changed 14 times: 9 nerfs, 4 buffs, 1 rework")
- Win rate / pick rate chart with patch boundaries marked as vertical lines — you literally see the meta reacting to each patch
- Current top build orders with timing data

### D. Item Pages
- Change history, win rate and purchase-rate trends across patches
- Average purchase timing distribution; win rate by purchase-timing bucket

### E. Build-Order Explorer
- Pick a hero → decision tree of common build paths with win rates at each branch
- Timing histograms: "first T3 item completed at minute X → win rate Y"
- Compare two build paths head-to-head

### F. Personal Dashboard (after Steam login)
- Session analytics: performance per game within each play session, decay curve
- Tilt metrics: win rate after 1/2/3+ consecutive losses; KDA trend within sessions
- Time-of-day and day-of-week patterns
- Your build timings vs. global high-win-rate timings for your heroes
- Personalized patch impact: "You main Warden and Abrams — here's what this patch did to *your* pool"

### G. Methodology / About page
- Data sources, confidence intervals, sample sizes, refresh cadence — this page is what makes it look like engineering instead of a toy

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     React Frontend (Vite)                │
│  Landing / Patch timeline / Hero+Item pages / Dashboard  │
└──────────────────────┬──────────────────────────────────┘
                       │ REST (JSON)
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI Backend (Python)                    │
│  /api/patches  /api/heroes  /api/items  /api/builds      │
│  /api/me/* (auth'd)   OpenID callback                    │
├───────────┬────────────────────┬────────────────────────┤
│ Patch     │ Stats ingest       │ LLM summarizer         │
│ watcher   │ worker             │ (structured output)    │
│ (cron)    │ (cron)             │                        │
└───────────┴─────────┬──────────┴────────────────────────┘
                      │
        ┌─────────────▼──────────────┐
        │      PostgreSQL            │
        │  patches, changes, heroes, │
        │  items, stat_snapshots,    │
        │  users, user_matches       │
        └────────────────────────────┘
        External sources (read-only):
        • Steam Web API (news for app 1422450)
        • forums.playdeadlock.com (Yoshi's update posts)
        • SteamDB GameTracking-Deadlock GitHub diffs
        • Community Deadlock API (match/stat aggregates)
```

### Key design decisions
- **You do NOT store raw match data at scale.** You pull *aggregates* from the community API and snapshot them per patch window. This keeps your DB small (tens of MB, not GB) and hosting free.
- **Stat snapshots around patches:** when a new patch is detected, you immediately snapshot "pre" aggregates, wait ~7 days, snapshot "post" aggregates, then compute deltas. This scheduled-job design is the core of the originality claim.
- **LLM only for unstructured → structured.** Patch text in, strict JSON out (Pydantic-validated). Never let the LLM invent numbers; validate extracted changes against the raw text.

---

## 4. Tech Stack & Libraries

### Backend
| Need | Choice | Why |
|---|---|---|
| Framework | FastAPI | Modern, typed, auto-docs at /docs |
| HTTP client | httpx | Async pulls from external APIs |
| ORM / migrations | SQLAlchemy 2 + Alembic | Standard, interview-recognized |
| Validation | Pydantic v2 | Especially for LLM structured output |
| Scheduling | APScheduler (simple) or Celery+Redis (if you want the résumé keyword) | Patch watch + snapshot jobs |
| LLM | OpenAI or Anthropic SDK with structured/JSON mode | Patch summarization |
| Auth | authlib (Steam OpenID) | Users log in with Steam |
| Tests | pytest + httpx test client + factory fixtures | Required for the "not a toy" signal |

### Frontend
| Need | Choice |
|---|---|
| Framework | React + Vite + TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts (win-rate-over-patches, timing histograms, decay curves) |
| Data fetching | TanStack Query |

### Infra
| Piece | Recommended | Cost |
|---|---|---|
| Frontend hosting | Vercel | Free |
| Backend hosting | Render (free tier, cold starts) or Fly.io | Free–~$5/mo |
| Database | Neon or Supabase Postgres free tier (500 MB) | Free |
| LLM API | ~$0.01–0.05 per patch summary; Deadlock patches are infrequent | **< $5 total, realistically** |
| Steam API key | steamcommunity.com/dev/apikey | Free |
| Domain (optional) | patchintel.gg or similar | ~$10–12/yr, optional |
| **Realistic total cost** | | **$0–20 for the whole project** |

---

## 5. Database Schema (core tables)

```sql
patches        (id, patch_date, title, source_url, raw_text, summary_json, ingested_at)
changes        (id, patch_id, entity_type[hero|item|system], entity_name,
                change_type[buff|nerf|rework|adjustment], description, extracted_numbers_json)
heroes         (id, name)
items          (id, name, tier, cost)
stat_snapshots (id, entity_type, entity_id, patch_id, window[pre|post],
                win_rate, pick_rate, avg_purchase_timing, matches_sampled, captured_at)
build_paths    (id, hero_id, patch_id, path_json, matches_sampled, win_rate)
users          (id, steam_id, display_name, created_at)
user_matches   (id, user_id, match_id, played_at, hero_id, result, kda, items_json, session_id)
sessions       (id, user_id, started_at, ended_at, game_count)  -- derived: gap >45min = new session
```

---

## 6. Data Sources — What You Actually Pull From

1. **Steam Web API — GetNewsForApp (appid 1422450):** official patch announcements, free with an API key. Your primary patch trigger.
2. **forums.playdeadlock.com:** Yoshi's detailed update posts (the real numbers). Scrape with BeautifulSoup; polite rate limiting.
3. **SteamDB GameTracking-Deadlock (GitHub):** machine-readable diffs of game files — catches *undocumented* changes. Great "above and beyond" data source.
4. **Community Deadlock API (deadlock-api.com / assets.deadlock-api.com):** hero/item aggregates, match history, analytics endpoints. **Respect its rate limits; cache everything; credit it in your README.**
5. **Steam OpenID:** login + the user's own match history via the community API.

---

## 7. Milestones (each one is independently shippable)

| Milestone | Deliverable | Rough effort |
|---|---|---|
| **M1 — Patch pipeline** | Steam news watcher → DB → LLM structured summary → read-only UI with patch history | 2–3 weekends |
| **M2 — Stats layer** | Community API ingest, pre/post snapshots, delta computation, "patch verdict" badges, hero/item pages with patch-boundary charts | 3–4 weekends |
| **M3 — Personal layer** | Steam OpenID, match history sync, sessionization, tilt analytics, personal patch impact | 3–4 weekends |
| **M4 — Portfolio polish** | README (screenshots, architecture diagram, setup guide), tests, demo mode with seeded data, deploy | 1–2 weekends |
| **M5 — Companion desktop app** | Valorant Tracker-style app: live match detection, post-match insights, feeds personal analytics on the site | 3–5 weekends |

M1 alone is a portfolio-worthy repo. Never let it become a half-finished giant — finish M1 fully (tests, README, deploy) before touching M2.

---

## 8. Difficulties You Should Expect (honest list)

1. **Item purchase timing/order data may be the hardest data problem.** Aggregate item win rates are easy; *purchase timestamps* depend on how much match-detail data the community API exposes for your region/matches. **Validate this in week 1 with a spike script** — pull a few match details and check whether item timings exist. If granularity is limited, narrow build-order analysis to "first N items ordered" rather than minute-level timing. Don't build M2 around data you haven't confirmed.
2. **The community Deadlock API is unofficial.** It rate-limits, changes shape, and could restrict access. Mitigate: aggressive caching, a config-driven API client layer, and a demo mode with seeded data so your deployed site survives API outages (also great for reviewers).
3. **LLM extraction accuracy.** Patch notes are messy prose; the LLM will occasionally misclassify or drop changes. Mitigate: structured output with Pydantic validation, unit tests on a golden set of 3–5 historical patches you hand-label, and a "changes verified" flag.
4. **Small post-patch sample sizes.** A change might only have 2,000 matches in a 7-day window → noisy deltas. Mitigate: show sample sizes and confidence intervals everywhere; mark low-confidence verdicts as "unclear" instead of overclaiming. (Displaying uncertainty well is itself an impressive engineering signal.)
5. **Steam OpenID quirks.** It's old OpenID 2.0, not OAuth — expect a fiddly afternoon. Use authlib and copy a known-good Flask/FastAPI example rather than rolling your own.
6. **Scope creep.** "Personal satisfaction" projects die from endless features. The milestone table is the contract: M1 done means *done* — tests, README, deployed.
7. **Deadlock is in active development.** Valve can overhaul items/heroes wholesale (they have). Keep entity matching by name resilient (alias table), and treat giant reworks as "new entity version" rather than corrupting history.

---

## 9. README Outline (write this from day one, update per milestone)

1. Hero section: logo + one-liner + live demo link + screenshots/GIFs
2. "Why this exists" — the originality paragraph (section 1)
3. Feature tour with GIFs: patch verdicts, build-order explorer, personal dashboard
4. Architecture diagram
5. Data sources & methodology (with sample-size/confidence-interval notes)
6. Tech stack
7. Local setup: `git clone → docker compose up` (provide a seed script with demo data!)
8. Testing: how to run the suite
9. Roadmap / known limitations

---

## 10. Definition of "Strong" — checklist before calling it done

- [ ] Deployed, clickable, loads in < 3s
- [ ] Demo mode — a reviewer without a Steam account sees real-looking data
- [ ] ≥ 70% backend test coverage on the pipeline logic
- [ ] README passes the "recruiter in 60 seconds" test
- [ ] Commit history shows iterative development (branches, PRs to yourself, meaningful messages)
- [ ] Methodology page with honest uncertainty handling
- [ ] 2–3 pinned repos max on profile: this one + one more

---

## 11. Product Vision: Website + Companion Desktop App

**End goal is an app ecosystem, Valorant Tracker-style.** The website is the public face; the desktop app is the personal companion.

### Split of responsibilities
| Surface | Role |
|---|---|
| **Web app** (public) | Patch impact reports, patch timeline, hero/item pages, build-order explorer, personal dashboard via Steam sign-in. SEO-friendly, shareable, what recruiters/users browse. |
| **Desktop app** (companion) | Detects when you're in a Deadlock match (process detection + community API live-match polling), captures your matches automatically, shows post-match insights ("that loss was game 6 of your session — your win rate there is 31%"), nudges tilt warnings, syncs everything to your web dashboard. |

### Why the split works technically
- Both surfaces talk to the **same FastAPI backend** — the desktop app is just another client plus a local agent. No duplicated logic.
- Live-match detection does **not** need memory reading or anything bannable: Deadlock exposes live match data through the community API; the app just polls for your Steam ID's active match. Valorant Tracker works similarly through Riot's API.
- Tech choice for the app: **Tauri** (Rust shell + webview, tiny binary, reuse React components from the web frontend) is the strong recommendation over Electron. Decision deferred to M5; the FastAPI backend doesn't care either way.

### What the app adds that the site can't
- Zero-effort data capture (no manual Steam ID entry per match)
- Real-time moments: "you're on a 3-loss streak — data says stop" mid-session
- Offline-first local cache of your history, synced when online

### Milestone placement
App work starts at **M5**, after the personal-analytics API (M3) exists — the app needs `/api/me/*` endpoints to talk to. Building it earlier would mean building it twice.
