# M3 Design Review — Personal Layer (Steam login + tilt/session analytics)

Status: **DRAFT for review** — not yet implemented
Date: 2026-11-12
Depends on: M2 (stats layer) — code complete, data backfill in progress

---

## 1. Scope (from blueprint §2F / §7)

After Steam login, PatchIntel shows a **personal dashboard**:

- Session analytics: performance per game within each play session, decay curve
- Tilt metrics: win rate after 1/2/3+ consecutive losses; KDA trend within sessions
- Time-of-day and day-of-week patterns
- Personalized patch impact: "you main Warden and Abrams — here's what this patch did to *your* pool"

Explicitly **out of scope** for M3: build-timing comparison vs global stats (needs
per-match item timing for arbitrary users — expensive; deferred to M5/desktop app),
live match detection (M5), any social/friend features.

## 2. Data availability — verified this milestone

| Need | Source | Status |
|---|---|---|
| User identity | Steam OpenID 2.0 → SteamID64 | Known-good pattern via `authlib` (blueprint risk #5) |
| User match history | `GET /v1/matches/metadata?account_ids=<id>&only_filtered_players=true&include_player_kda=true&include_player_items=true&order_by=start_time&limit=N` | **Verified in OpenAPI spec** — returns per-player KDA, items, hero, result, start time, duration |
| User hero pool | `GET /v1/players/hero-stats?account_ids=<id>` | Verified in OpenAPI spec |
| Player profile card | `GET /v1/players/steam?account_ids=<id>` | Verified in OpenAPI spec |

No per-match fetch needed for the dashboard: one bulk metadata call per sync,
paginated by `max_match_id` / `min_unix_timestamp` until we hit matches we
already have. At ~50 matches/call and typical play volume, a sync is 1–3 calls —
well inside rate limits.

## 3. New schema

```sql
users        (id, steam_id UNIQUE, display_name, avatar_url, created_at, last_sync_at)
user_matches (id, user_id FK, match_id UNIQUE-per-user, played_at, duration_s,
              hero_id, result, kills, deaths, assists, net_worth, items_json,
              session_id FK NULL)
sessions     (id, user_id FK, started_at, ended_at, game_count, wins,
              avg_kda)  -- derived, gap > 45 min = new session
```

- `user_matches.match_id` unique per user (a match can hold 2 PatchIntel users).
- Rebuilding sessions: matches are assigned `session_id` lazily after each sync
  (walk matches in time order, split on > 45 min gaps). Cheap at personal scale.
- Migration: this is the milestone where `init_db()` create_all stops being
  enough (existing users' DBs need ALTERs). **M3 adds Alembic** with one initial
  migration capturing M1+M2 schema, then the M3 tables as migration 2.

## 4. Auth design

- `GET /api/auth/steam/login` → redirect to steamcommunity.com OpenID
- `GET /api/auth/steam/callback` → verify assertion with authlib, upsert `users`
  row, set a signed session cookie (`itsdangerous`, `SECRET_KEY` in `.env`),
  redirect to `/dashboard`
- `POST /api/auth/logout`; `GET /api/me` → current user or 401
- Session cookie: HttpOnly, SameSite=Lax, 30-day expiry. No JWT needed — this is
  a first-party app, server-side validation is simpler and safer.
- All `/api/me/*` endpoints require the session; no other endpoints change
  (public stats stay public).
- React side: `useQuery(['me'])` gates the Dashboard nav link; 401 → "Sign in
  through Steam" button. No client-side token handling at all.

## 5. Endpoints

```
GET  /api/me                      → profile + last_sync_at
POST /api/me/sync                 → pull new matches from community API, rebuild sessions
GET  /api/me/matches?limit=&offset= → match history (session_id included)
GET  /api/me/sessions             → sessions with per-game results
GET  /api/me/analytics            → computed tilt/session stats (below)
GET  /api/me/patch-impact         → patches that touched the user's top-5 heroes,
                                    joined with M2 verdicts
```

`/api/me/analytics` returns one JSON blob:

```json
{
  "overall": { "matches": 0, "win_rate": 0, "avg_kda": 0 },
  "by_session_game_index": [{ "game_index": 1, "win_rate": 0, "kda": 0, "matches": 0 }],
  "after_loss_streak": [{ "streak": 1, "win_rate": 0, "matches": 0 }],
  "by_hour": [{ "hour": 20, "win_rate": 0, "matches": 0 }],
  "by_weekday": [{ "weekday": 5, "win_rate": 0, "matches": 0 }],
  "top_heroes": [{ "hero_id": 1, "matches": 0, "win_rate": 0 }]
}
```

Sample-size honesty, same as M2: any bucket < 20 matches is still returned but
the UI greys it out with a "low sample" tag. Tilt claims are where people
overclaim — we display, we don't lecture.

## 6. Tilt analytics — precise definitions

- **Session decay curve**: group matches by `game_index` within session
  (1st, 2nd, … 8th+); win rate + KDA per index. The "stop after game 5" chart.
- **Loss-streak response**: for each match, count consecutive losses immediately
  before it (streak 0/1/2/3+); win rate per streak value. This is the tilt metric.
- **Time patterns**: bucket by local hour and weekday of `played_at`.
  Timezone: store user's chosen TZ on `users` (default from browser on first
  login, editable) — server-side UTC storage, bucket at query time.

## 7. Frontend

- `/dashboard` (new page, auth-gated): four cards — decay line chart,
  loss-streak bar chart, hour-of-day heat strip, top heroes table — plus
  "patches affecting your pool" list reusing `VerdictBadge`.
- Nav gains: Dashboard link (when logged in) + Steam sign-in button (when not).
- Match history table is a stretch goal for M3; dashboard first.

## 8. Testing plan

- Steam OpenID callback: mock authlib's verification (fixture with a canned
  claimed_id); assert user upsert + cookie set.
- Sync: mock community API metadata responses (two pages) → assert idempotent
  import, correct session splitting across a > 45 min gap, duplicate-match
  handling when 2 users share a match.
- Analytics math: pure-function tests on a hand-built match list (known decay
  curve, known streaks) — same pattern as `test_verdicts.py`.
- Auth gates: every `/api/me/*` returns 401 without cookie.
- Target: suite goes from 38 → ~55 tests.

## 9. Risks

1. **Steam OpenID is fiddly** (blueprint risk #5). Mitigation: authlib's
   `openid` client, copy a known-good FastAPI example verbatim, timebox.
2. **Community API coverage of old matches.** Metadata only exists for matches
   the API has ingested; a returning user may see partial history. Mitigation:
   show `last_sync_at` + match count honestly; first sync pulls as far back as
   the API allows.
3. **Rate limits on sync.** Bulk endpoint + per-user `min_match_id` pagination
   keeps it to 1–3 calls; debounce the sync button server-side (1 sync / 2 min
   per user).
4. **Privacy.** Only the logged-in user sees their data; no public profile pages
   in M3. State that in the README.

## 10. Acceptance checklist

- [ ] Alembic set up; fresh + existing DBs migrate cleanly
- [ ] Steam login round-trip works locally (real Steam account)
- [ ] Sync imports the reviewer's real match history idempotently
- [ ] Dashboard shows all four analytics cards with low-sample tagging
- [ ] "Patches affecting your pool" list joins M2 verdicts correctly
- [ ] All new tests green; README updated with M3 section + screenshots
