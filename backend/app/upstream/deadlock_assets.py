"""Seed hero/item entity tables from the community Deadlock API.

Numeric game IDs are the join keys everywhere downstream; display names are
only for humans (design review: never join on names). Refreshed at most
daily per the upstream caching policy.

Filtering (verified against the live API, 2026-11-11):
- Heroes: the endpoint returns 65 entries including 21 in-development /
  unreleased ones. Only `disabled == false` heroes are playable -> 44.
- Items: the endpoint returns 782 entries mixing abilities (437) and weapons
  (95) with actual shop items. Real buyable items are
  `type == "upgrade" AND shopable == true` -> 173, of which the 17 costing
  9999 souls are Street Brawl legendaries. Excluded for now (product
  decision): -> 156 standard items.
"""

from __future__ import annotations

from ..config import Settings
from .client import request_with_backoff

BRAWL_LEGENDARY_COST = 9999


def _headers(settings: Settings) -> dict:
    # Header, not query param — keys in URLs leak into logs.
    return {"X-API-KEY": settings.deadlock_api_key} if settings.deadlock_api_key else {}


def fetch_heroes(settings: Settings) -> list[dict]:
    """Playable heroes only -> [{"id": int, "name": str}, ...] (44 today)."""
    resp = request_with_backoff(
        "GET", f"{settings.deadlock_api_base}/v1/assets/heroes", headers=_headers(settings)
    )
    return [
        {"id": h["id"], "name": h.get("name", "")}
        for h in resp.json()
        if "id" in h and not h.get("disabled", False)
    ]


def fetch_items(settings: Settings, include_brawl_legendaries: bool = False) -> list[dict]:
    """Standard shop items only -> [{"id", "name", "tier", "cost"}, ...] (156 today).

    Pass include_brawl_legendaries=True to also keep the 17 Street Brawl
    legendary items (cost 9999). Excluded by default per product decision.
    """
    resp = request_with_backoff(
        "GET", f"{settings.deadlock_api_base}/v1/assets/items", headers=_headers(settings)
    )
    items = []
    for it in resp.json():
        if "id" not in it:
            continue
        if it.get("type") != "upgrade" or not it.get("shopable", False):
            continue
        cost = it.get("cost")
        if not include_brawl_legendaries and cost == BRAWL_LEGENDARY_COST:
            continue
        items.append(
            {
                "id": it["id"],
                "name": it.get("name", ""),
                "tier": it.get("item_tier"),
                "cost": cost,
            }
        )
    return items
