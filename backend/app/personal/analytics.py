"""Tilt & session analytics (M3) — pure functions over UserMatch rows.

Definitions (design review §6):
- Session decay: win rate / KDA by game index WITHIN a session (1st, 2nd, ...).
- Loss-streak response: win rate of matches played right after N consecutive
  losses (streak counted within the user's full match history, chronological).
- Time patterns: win rate by hour-of-day and weekday, in the user's timezone.

Sample-size honesty: buckets are returned regardless of size; the UI greys
out anything under LOW_SAMPLE matches. We never hide noisy data silently.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from .. import models

LOW_SAMPLE = 20


def _kda(m: models.UserMatch) -> float:
    return (m.kills + m.assists) / max(m.deaths, 1)


def _bucket(matches: list[models.UserMatch], label: str) -> dict:
    n = len(matches)
    return {
        "label": label,
        "win_rate": round(sum(1 for m in matches if m.result == "win") / n, 4)
        if n
        else None,
        "avg_kda": round(sum(_kda(m) for m in matches) / n, 3) if n else None,
        "matches": n,
    }


def session_decay(matches: list[models.UserMatch]) -> list[dict]:
    """Win rate / KDA by game index within session (1-based, 8+ collapsed)."""
    by_index: dict[int, list[models.UserMatch]] = defaultdict(list)
    for m in matches:
        if m.session is None:
            continue
        idx = (
            sum(1 for x in m.session.matches if x.played_at < m.played_at) + 1
        )
        by_index[min(idx, 8)].append(m)
    return [
        _bucket(by_index[i], f"game {i}" if i < 8 else "game 8+")
        for i in sorted(by_index)
    ]


def loss_streak_response(matches: list[models.UserMatch]) -> list[dict]:
    """Win rate after 0 / 1 / 2 / 3+ consecutive losses (chronological)."""
    by_streak: dict[int, list[models.UserMatch]] = defaultdict(list)
    streak = 0
    for m in sorted(matches, key=lambda x: x.played_at):
        by_streak[min(streak, 3)].append(m)
        streak = streak + 1 if m.result == "loss" else 0
    labels = {0: "after win/1st game", 1: "after 1 loss", 2: "after 2 losses", 3: "after 3+ losses"}
    return [_bucket(by_streak[s], labels[s]) for s in sorted(by_streak)]


def _local_time(m: models.UserMatch, tz: ZoneInfo) -> datetime:
    from datetime import timezone

    return m.played_at.replace(tzinfo=timezone.utc).astimezone(tz)


def time_patterns(
    matches: list[models.UserMatch], tz_name: str
) -> tuple[list[dict], list[dict]]:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    by_hour: dict[int, list[models.UserMatch]] = defaultdict(list)
    by_day: dict[int, list[models.UserMatch]] = defaultdict(list)
    for m in matches:
        local = _local_time(m, tz)
        by_hour[local.hour].append(m)
        by_day[local.weekday()].append(m)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return (
        [_bucket(by_hour[h], f"{h:02d}:00") for h in sorted(by_hour)],
        [_bucket(by_day[d], days[d]) for d in sorted(by_day)],
    )


def top_heroes(matches: list[models.UserMatch], limit: int = 5) -> list[dict]:
    by_hero: dict[int, list[models.UserMatch]] = defaultdict(list)
    for m in matches:
        if m.hero_id is not None:
            by_hero[m.hero_id].append(m)
    ranked = sorted(by_hero.items(), key=lambda kv: -len(kv[1]))[:limit]
    return [
        {
            "hero_id": hero_id,
            "matches": len(ms),
            "win_rate": round(sum(1 for m in ms if m.result == "win") / len(ms), 4),
            "avg_kda": round(sum(_kda(m) for m in ms) / len(ms), 3),
        }
        for hero_id, ms in ranked
    ]


def compute_analytics(matches: list[models.UserMatch], tz_name: str) -> dict:
    by_hour, by_day = time_patterns(matches, tz_name)
    n = len(matches)
    return {
        "matches": n,
        "win_rate": round(sum(1 for m in matches if m.result == "win") / n, 4)
        if n
        else None,
        "avg_kda": round(sum(_kda(m) for m in matches) / n, 3) if n else None,
        "by_session_game_index": session_decay(matches),
        "after_loss_streak": loss_streak_response(matches),
        "by_hour": by_hour,
        "by_weekday": by_day,
        "top_heroes": top_heroes(matches),
    }
