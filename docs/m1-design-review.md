# M1 Design Review — Patch Pipeline

**Status:** ready for review
**Milestone goal:** Steam news watcher → structured DB records → LLM summaries → read-only patch history UI. Independently shippable and portfolio-worthy on its own.

---

## 1. Scope

**In scope for M1**
- Patch detection from official sources, stored raw + structured
- LLM extraction of per-change records (buff/nerf/rework/adjustment, entity, numbers)
- Postgres schema v1 (`patches`, `changes`, `heroes`, `items`)
- Read-only API: `GET /api/patches`, `GET /api/patches/{id}`
- Minimal server-rendered patch history UI
- pytest suite incl. hand-labeled golden patch set

**Explicitly NOT in M1** (guard against scope creep)
- No match stats, no verdicts (M2)
- No auth, no personal data (M3)
- No React SPA (see decision D2)
- No deployment beyond a single `docker compose up` (deploy in M4)

---

## 2. Verified external facts (checked 2026-11-11, not assumed)

| Fact | Evidence |
|---|---|
| Community API base `https://api.deadlock-api.com`, interactive docs at `/docs`, OpenAPI 3.1 available | Live docs page |
| Auth optional; `X-API-KEY` header preferred over query param (leaks less) | API docs |
| Rate limits: 200 req/min per IP, 400 req/min per key, analytics globally ~2000/min; many analytics responses cached 1h | API docs + guide |
| Load shedding: busy DB returns **503 + `Retry-After`**; slow queries return **504** then fail-fast for a few minutes | API docs |
| Entity resolution: numeric `hero_id`/`item_id` from `/v1/assets/heroes` and `/v1/assets/items` — never join on display names | API guide |
| `deadlock.io/api/v1/*.json` offers **patch-versioned** static hero/item JSON — useful for entity history across patches | deadlock.io index |
| Steam `GetNewsForApp` (appid 1422450) works for patch announcements | Steam Web API |
| Detailed balance numbers come from Yoshi's posts on forums.playdeadlock.com, not the Steam blurb | Community sources |
| **M5 relevant:** Overwolf GEP supports Deadlock live events (`match_start`, `match_end`, `kill`, `death`, `assist`, `match_clock`) — the same platform Tracker.gg's Valorant Tracker is built on. Also: an SSE live-match stream exists in the community API's `live-events` service | Overwolf docs, deadlock-api repo |

---

## 3. Pipeline design

```
┌──────────────┐   poll 6h   ┌─────────────────┐
│ Steam Web API │──────────▶│                 │
│ GetNewsForApp │            │                 │     ┌──────────────┐
└──────────────┘            │   orchestrator   │────▶│  PostgreSQL   │
┌──────────────┐   on hit   │   (APScheduler) │     │ patches      │
│ forums scraper│──────────▶│                 │     │ changes      │
│ (playdeadlock)│  raw text  └────────┬────────┘     │ heroes/items │
└──────────────┘                     │              └──────────────┘
                              ┌──────▼──────┐
                              │ LLM extractor│  strict JSON, Pydantic-validated
                              │ (provider-   │  retries w/ validation errors
                              │  agnostic)   │  fed back to the model
                              └─────────────┘
```

**Flow:**
1. **Detect** — poll `GetNewsForApp` every 6h; new news item with a patch-ish title/date → candidate patch row (`raw_text`, `source_url`, `status=detected`).
2. **Enrich** — follow the forum link, scrape the full notes with BeautifulSoup → `raw_text` replaced with full text (`status=fetched`).
3. **Extract** — LLM produces strict JSON (schema below) → validated → rows in `changes` (`status=extracted`). Validation failures retry once with the error message appended; second failure → `status=needs_review` (never silently wrong data).
4. **Resolve entities** — match `entity_name` against `heroes`/`items` tables seeded from `/v1/assets/*` and deadlock.io versioned JSON; store `entity_id` + keep the raw name for audit.
5. **Serve** — read-only endpoints + minimal UI.

**Idempotency:** everything keyed on `source_url` (unique). Re-running the whole pipeline against the same patch is a no-op. This matters for testing and for recovering from partial failures.

---

## 4. LLM extraction contract

```python
class ChangeType(str, Enum):
    BUFF = "buff"
    NERF = "nerf"
    REWORK = "rework"
    ADJUSTMENT = "adjustment"
    BUGFIX = "bugfix"

class ExtractedChange(BaseModel):
    entity_type: Literal["hero", "item", "system", "map", "unknown"]
    entity_name: str
    change_type: ChangeType
    description: str                     # one sentence, plain language
    numbers: list[NumberChange] = []     # {stat, old, new, unit} — only if explicit in text
    source_line: str                     # verbatim line from the notes (anti-hallucination anchor)

class PatchSummary(BaseModel):
    title: str
    summary: str                         # 3-5 sentences, casual-player readable
    changes: list[ExtractedChange]
```

**Anti-hallucination rules**
- `source_line` must be a verbatim substring of the raw notes — validated in code, rejected otherwise.
- `numbers` only when old/new values literally appear in the text. Never inferred.
- Entity name must resolve to a known hero/item or be marked `unknown` — never guessed.

**Provider abstraction:** `PatchSummarizer` protocol with `OpenAISummarizer`, `AnthropicSummarizer`, and `NullSummarizer` (regex/heuristic fallback so the pipeline runs with **no LLM key at all** — summary marked `llm_generated=false`). This answers the open API-key question: the design doesn't block on it.

**Golden test set:** 3–5 historical patches hand-labeled in `backend/tests/golden/`. Test asserts extraction recall ≥ 90% on change *lines* (not exact wording). This is the quality gate that keeps the LLM honest.

---

## 5. Decisions to review (please weigh in)

**D1 — M1 UI: server-rendered, not React.** FastAPI + Jinja2 + a bit of Tailwind via CDN for the M1 patch history page. Rationale: React SPA earns its keep in M2 (charts, filtering); in M1 it would double the work for a list view. Backend endpoints are JSON-first either way, so nothing is thrown away. *Alternative: scaffold React now if you want frontend reps early.*

**D2 — Forum scraping is required, not optional.** Steam blurbs lack per-change numbers; the forum post has them. Scraper is polite (1 req per enrichment, cached forever, `If-Modified-Since`). Risk: forum markup changes → scraper test against a saved fixture, `status=needs_review` on parse failure.

**D3 — SQLite allowed for local dev, Postgres in compose.** SQLAlchemy makes this free; keeps the "clone and run in 2 minutes" story strong for reviewers.

**D4 — M5 app platform: Overwolf is now the front-runner over Tauri.** New evidence: Overwolf's GEP already supports Deadlock live events (`match_start/end`, `kill/death/assist`, `match_clock`), and it's the same platform Valorant Tracker ships on. Tauri would rely on API polling only. Decision deferred to M5 as planned, but the blueprint's recommendation is updated.

**D5 — GameTracking-Deadlock diffs: stretch goal inside M1, cut first if time slips.** Undocumented-change detection is impressive but not core to "did the patch work."

---

## 6. Rate-limit & caching policy (applies from M1 onward)

- All upstream calls through one `UpstreamClient` with: per-host concurrency = 2, exponential backoff on 429/503 **honoring `Retry-After`**, and 504 fail-fast awareness (narrow or skip, don't retry the same query).
- Asset endpoints (`heroes`, `items`): refreshed at most daily, cached in DB.
- Never poll analytics endpoints faster than their 1h cache window.
- Every stored row keeps `source_url` + `captured_at` for reproducibility.

---

## 7. M1 file-by-file plan

```
backend/
  app/
    main.py                  # exists; add routers + templates
    config.py                # pydantic-settings (.env)
    db.py                    # engine/session, SQLite-or-Postgres
    models.py                # Patch, Change, Hero, Item (SQLAlchemy)
    schemas.py               # API + LLM Pydantic contracts
    upstream/
      steam_news.py          # GetNewsForApp poller
      forum_scraper.py       # playdeadlock.com full notes
      deadlock_assets.py     # hero/item seed from /v1/assets + deadlock.io
      client.py              # shared httpx client w/ backoff policy
    pipeline/
      orchestrator.py        # detect → enrich → extract → resolve
      summarizer.py          # PatchSummarizer protocol + providers
      entity_resolver.py     # name → hero_id/item_id matching
    api/
      patches.py             # GET /api/patches, /api/patches/{id}
    templates/patches.html   # minimal M1 UI (D1)
  tests/
    golden/                  # 3-5 hand-labeled historical patches
    test_extractor.py        # golden-set recall gate
    test_pipeline.py         # idempotency, needs_review paths
    test_api.py
scripts/
  spike_deadlock_api.py      # exists — run before M2 planning
```

## 8. M1 acceptance criteria

- [ ] `docker compose up && pytest` green on a fresh clone
- [ ] Running the pipeline twice creates zero duplicate rows
- [ ] Golden-set extraction recall ≥ 90%
- [ ] Every stored change has a verbatim `source_line`
- [ ] `/api/patches` returns structured history; UI renders it
- [ ] README M1 section: what it does, how to run, architecture diagram
- [ ] Commits show iterative work (feature branches → PRs to main)

## 9. Open questions

1. **LLM provider** — asked last turn: OpenAI key, Anthropic key, or design-first with `NullSummarizer` fallback? (Design supports all three; your call only affects summary polish.)
2. **D1** — Jinja2 for M1 UI OK, or scaffold React now?
3. **Forum scraping** — acceptable to you, or Steam-blurb-only for M1?
