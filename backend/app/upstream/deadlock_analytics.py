"""Community Deadlock API analytics endpoints (M2).

Thin wrappers around /v1/analytics/* with the patch-window date filters
built in. All calls go through the shared backoff client (M1 policy).

Verified response shapes (2026-11-11):
- hero_stats: [{hero_id, wins, losses, matches, total_kills, ...}]
- item_stats: [{item_id, wins, losses, matches, players,
               avg_buy_time_s, avg_buy_time_relative, ...}]
- hero_build_stats: [{hero_id, hero_build_id, wins, losses, matches, players}]
"""

from __future__ import annotations

from datetime import datetime

from ..config import Settings
from .client import request_with_backoff


def _headers(settings: Settings) -> dict:
    return {"X-API-KEY": settings.deadlock_api_key} if settings.deadlock_api_key else {}


def _window_params(start: datetime | None, end: datetime | None) -> dict:
    params: dict = {}
    if start is not None:
        params["min_unix_timestamp"] = int(start.timestamp())
    if end is not None:
        params["max_unix_timestamp"] = int(end.timestamp())
    return params


def hero_stats(
    settings: Settings,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    """Per-hero wins/losses/matches (+ totals), optionally date-bounded."""
    resp = request_with_backoff(
        "GET",
        f"{settings.deadlock_api_base}/v1/analytics/hero-stats",
        params=_window_params(start, end),
        headers=_headers(settings),
    )
    return resp.json()


def item_stats(
    settings: Settings,
    start: datetime | None = None,
    end: datetime | None = None,
    *,
    hero_id: int | None = None,
    min_bought_at_s: int | None = None,
    max_bought_at_s: int | None = None,
    item_order: int | None = None,
) -> list[dict]:
    """Per-item win rates + average purchase timing.

    Filters map directly onto M2 features:
    - hero_id           -> per-hero item timing
    - bought_at bounds  -> win rate by purchase timing bucket
    - item_order        -> win rate by purchase order (1st, 2nd, ... buy)
    """
    params = _window_params(start, end)
    if hero_id is not None:
        params["hero_id"] = hero_id
    if min_bought_at_s is not None:
        params["min_bought_at_s"] = min_bought_at_s
    if max_bought_at_s is not None:
        params["max_bought_at_s"] = max_bought_at_s
    if item_order is not None:
        params["item_order"] = item_order
    resp = request_with_backoff(
        "GET",
        f"{settings.deadlock_api_base}/v1/analytics/item-stats",
        params=params,
        headers=_headers(settings),
    )
    return resp.json()


def hero_build_stats(settings: Settings, hero_id: int) -> list[dict]:
    """Per-build win/loss/matches for one hero."""
    resp = request_with_backoff(
        "GET",
        f"{settings.deadlock_api_base}/v1/analytics/hero-build-stats/{hero_id}",
        headers=_headers(settings),
    )
    return resp.json()


def item_purchase_curve(
    settings: Settings,
    item_id: int,
    *,
    slice_s: int = 120,
    max_time_s: int = 3000,
) -> list[dict]:
    """Win rate by exact purchase time — one item_stats call per time slice.

    The upstream API has no curve endpoint, but `min/max_bought_at_s` filters
    are arbitrary, so we sweep slices (default 2-min buckets over 0–50 min)
    and stitch a curve. ~25 upstream calls; cache results downstream.
    Returns [{bucket_start_s, wins, losses, matches, win_rate}] with
    zero-match slices included (win_rate None).
    """
    curve = []
    for start in range(0, max_time_s, slice_s):
        rows = item_stats(
            settings, min_bought_at_s=start, max_bought_at_s=start + slice_s
        )
        row = next((r for r in rows if r.get("item_id") == item_id), None)
        wins = row["wins"] if row else 0
        matches = row["matches"] if row else 0
        curve.append(
            {
                "bucket_start_s": start,
                "wins": wins,
                "losses": row["losses"] if row else 0,
                "matches": matches,
                "win_rate": round(wins / matches, 4) if matches else None,
            }
        )
    return curve
