# M2 Design Review — Stats Layer & Patch Verdicts (FINAL)

**Status:** final — all open questions resolved, ready to implement
**Depends on:** M1 (shipped, tests green, backfill shipped)
**Milestone goal:** turn parsed patches into *measured outcomes* — the feature that makes PatchIntel original.

---

## 0. What changed since the first draft

| Was open | Now verified (2026-11-11, live API probes) |
|---|---|
| Item purchase timing/order availability (risk #1) | **AVAILABLE at aggregate level.** `/v1/analytics/item-stats` returns `avg_buy_time_s` + filters `min_bought_at_s`, `max_bought_at_s`, **`item_order`**, `hero_id`, date bounds. Sequence-only fallback is dead. See docs/m2-addendum-item-timing.md |
| Hero stats shape | `/v1/analytics/hero-stats`: wins/losses/matches + kills/damage/net-worth totals, date-filterable (user spike run) |
| Entity lists | 44 playable heroes (`disabled==false`), 156 standard items (`type==upgrade, shopable, cost!=9999`) — seeded correctly |
| Window size | 7 days default, `PATCH_WINDOW_DAYS` env config |
| DEADLOCK_API_KEY | Not needed at M2 request volume (~6 requests/patch) |

---

## 1. Scope

**In scope**
- Aggregate stat snapshots around every patch (heroes + items)
- Per-change **verdict computation** with honest uncertainty
- Item timing/order analytics endpoints (build-order foundation)
- API: `/api/heroes`, `/api/heroes/{id}`, `/api/items`, `/api/items/{id}`, `/api/patches/{id}/impact`
- UI: patch detail gains an "Impact" section; hero pages with win-rate-over-time charts and patch boundary markers
- React SPA introduced (decision D1), replacing M1 Jinja2 for stat surfaces
- Alembic migrations start here (schema v2)

**Out of scope**
- Personal analytics / auth (M3)
- Live anything (M5)
- Deployment (M4)

---

## 2. Core concept: patch windows

```
         patch_date
             │
  ───────────┼───────────
   pre: [d-7, d)   post: [d+1, d+8)
```

- **pre** = the 7 days before the patch; **post** = days 1–8 after (skipping patch day itself)
- Both map directly onto `min_unix_timestamp`/`max_unix_timestamp` filters — one analytics call per window per entity class (~6 requests/patch total)
- A hotfix inside a post window truncates it; `truncated=true` recorded, verdict confidence lowered

**Snapshot scheduling (APScheduler):**
1. Patch extracted → compute `pre` snapshot immediately (historical data already exists)
2. Schedule `post` snapshot at `patch_date + 8d` (for past patches: immediately)
3. Post snapshot complete → compute verdicts for that patch's changes
4. Nightly job re-captures the "current" window for trend charts

---

## 3. Verdict math (unchanged from draft — the credibility engine)

For each change with a resolved `entity_id`:

```
delta_wr = post_win_rate - pre_win_rate
```

- Wilson score 95% CI on both win rates; sample sizes displayed everywhere
- **Verdict rules:** worked = delta in expected direction beyond combined CI half-width; backfired = opposite beyond noise; **everything else = unclear**
- Hard floor: ≥500 matches per window or verdict = unclear (no exceptions)
- rework/adjustment → "shifted"/"no measurable effect"; bugfix → excluded
- Pick-rate delta reported alongside (nerfs can crater playrate without moving win rate)

---

## 4. Schema v2 (first Alembic migration)

```sql
stat_snapshots (
  id, entity_type[hero|item], entity_id, patch_id FK,
  window[pre|post|current], window_start, window_end, truncated bool,
  win_rate, pick_rate, matches int, extra_json, captured_at
)
verdicts (
  id, patch_id FK, entity_id, change_id FK nullable,
  expected_direction[down|up|none],
  pre_win_rate, post_win_rate, delta_win_rate,
  pre_pick_rate, post_pick_rate,
  pre_matches, post_matches, ci_half_width,
  verdict[worked|backfired|unclear|shifted|no_effect|excluded],
  computed_at
)
item_timing_snapshots (
  id, item_id FK, patch_id FK, window,
  avg_buy_time_s, avg_buy_time_relative,
  win_rate_early, win_rate_mid, win_rate_late,   -- bought_at bucket splits
  matches int, captured_at
)
```

Verdicts stored, not computed on read — doubles as an audit trail.

---

## 5. API & UI

**API**
- `GET /api/heroes` / `GET /api/heroes/{id}` — roster + win-rate time series with patch markers
- `GET /api/items` / `GET /api/items/{id}` — incl. avg buy time + timing-bucket win rates
- `GET /api/patches/{id}/impact` — verdicts + top movers

**UI decision D1 — React SPA arrives in M2.** Vite + TS + Tailwind + Recharts + TanStack Query in `frontend/`, consuming `/api/*`. Jinja2 pages stay as zero-JS fallback until SPA parity. Visual direction: NOT generic dark-AI-template — design pass with the owner's input at implementation time (Deadlock's art-deco palette is the leading candidate).

---

## 6. Build-Order Explorer — CONFIRMED, full design

All features verified against live endpoints:

| Feature | Implementation |
|---|---|
| Win rate by purchase timing | `item-stats` with `min_bought_at_s`/`max_bought_at_s` buckets (early/mid/late splits stored in `item_timing_snapshots`) |
| Win rate by purchase order | `item_order` param |
| Per-hero timing | `hero_id` filter |
| Game-phase flow | `/v1/analytics/item-flow-stats` |
| Build win rates | `/v1/analytics/hero-build-stats/{hero_id}` |

Aggregation happens upstream; we store small snapshot rows only.

---

## 7. Failure modes & mitigations

1. **Hotfix chains** → `truncated` flag + lowered confidence.
2. **Analytics schema drift** → `UpstreamClient` backoff policy (M1) + job log; snapshot failures retry next cycle.
3. **Entity renamed between patches** → numeric IDs everywhere; deadlock.io versioned JSON for name archaeology.
4. **Sample drought** → 500-match floor; "unclear" by design.
5. **Old patches predating API coverage** → snapshot comes back sparse → verdict "insufficient_data", displayed honestly (expected for 2024-era patches).
6. **Upstream 1h analytics cache** → capture timestamps stored; one re-capture pass 24h later.

---

## 8. M2 acceptance criteria

- [ ] Alembic migration applies cleanly on SQLite and Postgres
- [ ] Every extracted patch has pre/post snapshots or a logged reason
- [ ] Every verdict shows sample sizes + CI; none violate the 500-match floor
- [ ] Patch page Impact section with worked/backfired/unclear badges
- [ ] Hero page chart marks patch boundaries
- [ ] Item pages show avg buy time + timing-bucket win rates
- [ ] React SPA at parity with M1 pages
- [ ] Tests: verdict math (known inputs → known verdicts), truncation, snapshot idempotency
- [ ] README methodology section updated

## 9. Implementation order

1. Alembic setup + schema v2 migration
2. Analytics client (item-stats/hero-stats wrappers with window helpers)
3. Snapshot jobs + verdict computation + unit tests
4. API endpoints
5. React scaffold + hero/patch-impact pages
6. Item timing explorer
