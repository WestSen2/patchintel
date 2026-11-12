# M2 Addendum — Build-order mining UNBLOCKED (verified 2026-11-11)

Supersedes the open question in m2-design-review.md §6.

## Verified endpoints (live-checked against the API)

| Need | Endpoint | Key fields / params |
|---|---|---|
| Item win rates + avg purchase timing | `/v1/analytics/item-stats` | `wins`, `losses`, `matches`, `players`, **`avg_buy_time_s`**, `avg_sell_time_s`; filters: `hero_id`, `min_bought_at_s`, `max_bought_at_s`, **`item_order`**, `min_unix_timestamp`, `max_unix_timestamp`, rank brackets |
| Game-phase item flow | `/v1/analytics/item-flow-stats` | `phase_interval_s`, `phase_count` |
| Per-hero build win rates | `/v1/analytics/hero-build-stats/{hero_id}` | wins/losses/matches/players per build |
| Hero aggregates (verdict engine) | `/v1/analytics/hero-stats` | wins/losses/matches + kills/damage/net-worth totals, date filters |

Facts verified by direct calls:
- `item-stats` returned exactly 156 records = the standard shop item set.
- Patch-window snapshots map directly onto `min_unix_timestamp`/`max_unix_timestamp`.
- Win rate by purchase timing = call `item-stats` with `bought_at_s` buckets.
- Win rate by purchase ORDER = `item_order` param (the original user idea).

## Design consequences

1. **The sequence-only fallback is dead.** Full timing + order analysis is
   available at AGGREGATE level — no raw match storage needed, DB stays tiny.
2. **M2 gets simpler:** no match-metadata ingestion worker; the stats layer
   is a set of scheduled aggregate pulls + snapshot rows, as originally
   blueprinted.
3. **Build-Order Explorer (blueprint §2E) is a go:** timing histograms via
   bought_at buckets, decision trees via `item_order`, per-hero filtering.
4. Spike script outcome: hero-stats + build-stats confirmed by user run;
   item-stats timing confirmed by direct probe (match-metadata question
   is now moot).
