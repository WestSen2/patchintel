# M2 Design Review — Stats Layer & Patch Verdicts

**Status:** ready for review
**Depends on:** M1 (done, tests green); `scripts/spike_deadlock_api.py` results for §6
**Milestone goal:** turn parsed patches into *measured outcomes* — the feature that makes PatchIntel original.

---

## 1. Scope

**In scope**
- Aggregate stat snapshots around every patch (heroes + items)
- Per-change **verdict computation** with honest uncertainty
- API: `/api/heroes`, `/api/heroes/{id}`, `/api/items/{id}`, `/api/patches/{id}/impact`
- UI: patch detail gains an "Impact" section; hero pages with win-rate-over-time charts and patch boundary markers
- React SPA introduced (as scheduled), replacing the M1 Jinja2 pages for the stat surfaces
- Alembic migrations start here (schema v2)

**Out of scope**
- Personal analytics / auth (M3)
- Live anything (M5)
- Deployment (M4)

---

## 2. Core concept: patch windows

Every extracted patch gets two measurement windows:

```
         patch_date
             │
  ───────────┼───────────
   pre: [d-7, d)   post: [d+1, d+8)
```

- **pre snapshot** — aggregates over the 7 days before the patch (the meta the patch was reacting to)
- **post snapshot** — aggregates over days 1–8 after (skipping patch day itself, when matches mix old/new clients and player behavior is chaotic)
- **7-day windows** balance sample size vs. meta drift; configurable per patch (a hotfix 3 days later truncates the window — record the truncation, don't pretend it's clean)

The community API's analytics endpoints (e.g. `/v1/analytics/hero-stats`) accept date-range filters and return win/pick rates with match counts — one request per window per entity class, not per entity. **Budget: ~4–6 requests per patch.** Trivially inside the 200 req/min IP limit; the 1-hour analytics cache is irrelevant at this cadence.

**Snapshot trigger (APScheduler):**
1. Patch inserted → immediately schedule `pre` snapshot job (data already exists historically, so this runs right away)
2. Schedule `post` snapshot job for `patch_date + 8 days`
3. On post-snapshot → compute verdicts for all changes in that patch

---

## 3. Verdict math (the credibility engine)

For each change with a resolved `entity_id`:

```
delta_wr = post_win_rate - pre_win_rate
```

**Uncertainty, always:** Wilson score 95% CI on both win rates from their match counts. Display sample sizes everywhere (methodology page requirement from the blueprint).

**Verdict rules** (expected direction comes from `change_type`):

| change_type | expected | verdict = worked | verdict = backfired |
|---|---|---|---|
| nerf | win rate ↓ | delta < 0 beyond noise | delta > 0 beyond noise |
| buff | win rate ↑ | delta > 0 beyond noise | delta < 0 beyond noise |
| rework / adjustment | none set | classified as "shifted" / "no measurable effect" |
| bugfix | n/a | excluded from verdicts |

"Beyond noise" = |delta| exceeds the combined CI half-width **and** both windows have ≥ 500 matches. Everything else = **unclear**, displayed honestly. Low-sample verdicts are forbidden — this rule is what separates PatchIntel from Reddit tier-list science.

Also tracked per entity: **pick-rate delta** (a nerf can "work" on win rate while players simply abandon the hero — that's a different story and worth showing).

---

## 4. Schema v2 (first Alembic migration)

```sql
stat_snapshots (
  id, entity_type[hero|item], entity_id, patch_id FK,
  window[pre|post], window_start, window_end, truncated bool,
  win_rate, pick_rate, matches int, captured_at
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
```

Verdicts are **stored, not computed on read** — they're cheap to precompute and the stored row doubles as an audit trail (methodology page links the exact inputs).

---

## 5. API & UI

**API**
- `GET /api/heroes` — roster with current-patch win/pick rates
- `GET /api/heroes/{id}` — win-rate time series + change history (patch markers)
- `GET /api/items/{id}` — same for items
- `GET /api/patches/{id}/impact` — verdicts + top movers for the patch

**UI decision D1 — React arrives in M2 as previously scheduled.** Win-rate charts with patch-boundary markers, filters, and the impact view are interactive enough that server-rendered Jinja2 would be throwaway work. Vite + TS + Tailwind + Recharts + TanStack Query, in `frontend/`, consuming `/api/*`. The M1 Jinja2 pages stay as the zero-JS fallback until the SPA reaches parity.

---

## 6. Build-order mining — GATED on the spike

Design review risk #1 from the blueprint lands here. Two outcomes:

- **Spike shows item purchase timing/order in match metadata** → full design: build-path decision trees per hero, first-T3 timing histograms, `build_paths` table as blueprinted.
- **Spike shows only final inventories** → narrow to *item sequence* analysis (first-N-items win rates) via `/v1/analytics/hero-build-stats/{hero_id}`, and drop timing claims from the UI copy. Honest scope cut, still original.

**Action required:** run `python scripts/spike_deadlock_api.py` and paste the output. M2 implementation of this section starts only after that answer exists.

---

## 7. Failure modes & mitigations

1. **Hotfix chains** (patch 3 days after patch) → windows truncate; recorded via `truncated` flag; verdicts on truncated windows marked lower-confidence.
2. **Analytics endpoint schema drift** → the same `UpstreamClient` policy from M1 applies; snapshot jobs retry with backoff and alert via `needs_review`-style job log table.
3. **Entity renamed between patches** → resolution already stores numeric IDs; deadlock.io versioned JSON gives old→new name mapping if needed.
4. **Sample drought on unpopular heroes/items** → 500-match floor means some verdicts are "unclear" by design. Fine.
5. **Stat snapshot taken while upstream cache is stale** → capture timestamps stored; re-capture job runs 24h later and updates if values moved beyond rounding.

---

## 8. M2 acceptance criteria

- [ ] Alembic migration applies cleanly on both SQLite and Postgres
- [ ] For every extracted patch: pre/post snapshots exist or a logged reason they couldn't
- [ ] Every verdict displays sample sizes + CI; none violate the 500-match floor
- [ ] Patch page shows Impact section with worked/backfired/unclear badges
- [ ] Hero page chart visually marks patch boundaries
- [ ] React SPA at parity with M1 pages; old pages still work
- [ ] Tests: verdict-math unit tests (known inputs → known verdicts), window-truncation tests, snapshot idempotency
- [ ] Methodology section in README updated

## 9. Open questions

1. **Spike results** — item timing/order: present or not? (blocking §6 only)
2. **DEADLOCK_API_KEY** — do you want the higher rate limits (400/min vs 200/min)? Not required at M2's request volume; skip unless you hit 429s.
3. **Window size** — 7 days is the default; if you play enough to judge, say whether post-patch metas in Deadlock settle faster (→ 5 days) or slower (→ 10). Config value either way.
