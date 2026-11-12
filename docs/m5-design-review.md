# M5 Design Review — Companion Desktop App

Status: **DRAFT for review** — not yet implemented
Date: 2026-11-12
Depends on: M3 (`/api/me/*` endpoints the app talks to)

---

## 1. Goal

A Valorant Tracker-style desktop companion: detects your Deadlock matches,
delivers post-match insights ("that was your 4th loss in a row — your data says
stop"), and feeds the website's personal analytics. The site is the public
face; the app is the personal instrument panel.

## 2. Platform decision: Overwolf vs Tauri

| | Overwolf | Tauri + custom detection |
|---|---|---|
| Live game events | **GEP officially supports Deadlock** (match start/end, kills, deaths) | None — we'd poll the community API |
| Distribution | Overwolf store (discoverability) | Self-distributed |
| Trust/perf reputation | Some players dislike overlays | Clean, tiny binary |
| Dev effort | Their SDK/UX conventions | We own everything; detection is the hard part |
| Language | JS/TS overlay windows | Rust + webview |

**Recommendation: Tauri + polling-first architecture.**

- The core value (post-match insight + syncing into PatchIntel analytics) does
  NOT need in-game overlay events. Polling the community API every 60s for a
  new finished match is simpler, cross-platform, and avoids Overwolf's UX
  overhead.
- Detecting "match just ended" = `match_id` newer than last seen for the
  signed-in SteamID — the same metadata endpoint M3 already uses.
- Overwolf remains the upgrade path if we later want *live* (in-match) events.

## 3. MVP feature set

1. **Steam sign-in passthrough** — app opens the site's Steam login in a
   webview; backend issues a long-lived device token for the app
   (`/api/me/token` → bearer token, since cookie flows are awkward in apps).
2. **Match watcher** — poll every 60s while Deadlock is running (process
   detection: `deadlock.exe`/app manifest) or every 5 min otherwise; on new
   match → local notification with quick stats (result, KDA, session context:
   "game 6 of this session — your win rate after game 5 is 31%").
3. **Post-match insight card** — small always-on-top-able window showing the
   just-finished match against your personal analytics.
4. **Sync feed** — imported matches are already server-side; the app only
   triggers `/api/me/sync`. No duplicate data pipeline.

Explicitly out: in-game overlay, live draft advice, anything touching game
memory or files (VAC-safe by construction — we only call public APIs).

## 4. Architecture

```
Tauri app (Rust core + React webview reusing site components)
  ├── settings: PatchIntel URL + device token
  ├── watcher loop: GET /api/me/sync (server does the heavy lifting)
  │                 → GET /api/me/matches?limit=1 (detect new)
  │                 → GET /api/me/analytics (context for insight)
  └── UI: insight card + session summary
```

New backend work is minimal: device-token endpoint + CORS already done in M4.
All analytics math stays server-side (single source of truth).

## 5. Risks

1. **Scope creep** — this is the milestone where side projects die. MVP is
   poll + notify + one insight card. Nothing else ships in M5.
2. **Tauri learning curve** (Rust) — keep Rust layer paper-thin; all logic in
   TS against the existing REST API.
3. **API rate limits from polling** — 60s polls during gameplay only;
   exponential backoff on 429s; respect Retry-After (client already does).

## 6. Acceptance checklist

- [ ] Device-token auth end-to-end (app ↔ backend)
- [ ] New-match detection produces a local notification within 90s of match end
- [ ] Insight card shows match result + session context from real analytics
- [ ] Zero game-process interaction beyond presence detection (VAC-safe)
