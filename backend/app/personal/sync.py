"""Match sync + sessionization for the personal layer (M3).

Data source: GET /v1/matches/metadata (community Deadlock API) filtered by
account_ids with only_filtered_players=true. One bulk call per page; we page
backwards by max_match_id until we hit matches already in the DB. Verified
response shape (2026-11-12):

  match:  {match_id, start_time (unix int or ISO str), duration_s,
           winning_team: "Team0"|"Team1", players: [...]}
  player: {account_id (SteamID3), hero_id, team, kills, deaths, assists,
           items: [{game_time_s, item_id, ...}]}

Steam OpenID gives us a SteamID64; the API returns SteamID3 account ids.
Conversion: steam_id_3 = steam_id_64 - 76561197960265728.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..config import Settings
from ..upstream.client import request_with_backoff

STEAM_ID_64_BASE = 76561197960265728
SESSION_GAP = timedelta(minutes=45)
SYNC_PAGE_LIMIT = 100
SYNC_MAX_PAGES = 10  # 1000 matches max per sync — plenty for a session's worth


def steam_id_3(steam_id_64: str) -> int:
    return int(steam_id_64) - STEAM_ID_64_BASE


def fetch_metadata_page(
    settings: Settings, account_id_3: int, max_match_id: int | None
) -> list[dict]:
    params = {
        "account_ids": str(account_id_3),
        "only_filtered_players": "true",
        "include_player_kda": "true",
        "include_player_items": "true",
        "order_by": "match_id",
        "order_direction": "desc",
        "limit": SYNC_PAGE_LIMIT,
    }
    if max_match_id is not None:
        params["max_match_id"] = max_match_id - 1
    headers = {}
    if settings.deadlock_api_key:
        headers["X-API-KEY"] = settings.deadlock_api_key
    resp = request_with_backoff(
        "GET",
        f"{settings.deadlock_api_base}/v1/matches/metadata",
        params=params,
        headers=headers,
    )
    return resp.json()


def _parse_start_time(value) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
    # "2026-11-11 08:13:51" (UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(
        tzinfo=None
    )


def import_matches(db: Session, user: models.User, pages: list[list[dict]]) -> int:
    """Insert UserMatch rows from fetched pages. Idempotent — existing
    (user_id, match_id) rows are skipped. Returns number imported."""
    acct = steam_id_3(user.steam_id)
    known = {
        mid
        for (mid,) in db.query(models.UserMatch.match_id)
        .filter_by(user_id=user.id)
        .all()
    }
    imported = 0
    for page in pages:
        for match in page:
            match_id = match.get("match_id")
            if match_id is None or match_id in known:
                continue
            players = match.get("players") or []
            player = next(
                (p for p in players if p.get("account_id") == acct),
                players[0] if len(players) == 1 else None,
            )
            if player is None:
                continue  # user not found in this payload — skip defensively
            won = player.get("team") and player.get("team") == match.get(
                "winning_team"
            )
            db.add(
                models.UserMatch(
                    user_id=user.id,
                    match_id=match_id,
                    played_at=_parse_start_time(match.get("start_time")),
                    duration_s=match.get("duration_s") or 0,
                    hero_id=player.get("hero_id"),
                    result="win" if won else "loss",
                    kills=player.get("kills") or 0,
                    deaths=player.get("deaths") or 0,
                    assists=player.get("assists") or 0,
                    items_json=[
                        {
                            "item_id": it.get("item_id"),
                            "game_time_s": it.get("game_time_s"),
                        }
                        for it in (player.get("items") or [])
                    ],
                )
            )
            known.add(match_id)
            imported += 1
    db.commit()
    return imported


def rebuild_sessions(db: Session, user: models.User) -> int:
    """Regenerate PlaySession rows from the user's matches.

    Rule: a gap > 45 min between a match's END and the next match's START
    starts a new session. Matches are assigned session_id; session
    aggregates (game_count, wins) are denormalized onto the row.
    """
    db.query(models.PlaySession).filter_by(user_id=user.id).delete()
    matches = (
        db.query(models.UserMatch)
        .filter_by(user_id=user.id)
        .order_by(models.UserMatch.played_at)
        .all()
    )
    session = None
    for m in matches:
        m_end = m.played_at + timedelta(seconds=m.duration_s)
        if session is None or m.played_at - session.ended_at > SESSION_GAP:
            session = models.PlaySession(
                user_id=user.id, started_at=m.played_at, ended_at=m_end,
                game_count=0, wins=0,
            )
            db.add(session)
            db.flush()  # session.id for the FK
        session.ended_at = max(session.ended_at, m_end)
        session.game_count += 1
        session.wins += 1 if m.result == "win" else 0
        m.session_id = session.id
    db.commit()
    return db.query(models.PlaySession).filter_by(user_id=user.id).count()


def sync_user(db: Session, settings: Settings, user: models.User) -> dict:
    """Full sync: pull new matches from the community API, rebuild sessions."""
    acct = steam_id_3(user.steam_id)
    known = {
        mid
        for (mid,) in db.query(models.UserMatch.match_id)
        .filter_by(user_id=user.id)
        .all()
    }
    pages: list[list[dict]] = []
    max_match_id = None
    for _ in range(SYNC_MAX_PAGES):
        page = fetch_metadata_page(settings, acct, max_match_id)
        if not page:
            break
        pages.append(page)
        max_match_id = min(m["match_id"] for m in page)
        if any(m["match_id"] in known for m in page) or len(page) < SYNC_PAGE_LIMIT:
            break  # reached history we already have (or exhausted it)
    imported = import_matches(db, user, pages)
    sessions = rebuild_sessions(db, user)
    user.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"imported": imported, "sessions": sessions}
