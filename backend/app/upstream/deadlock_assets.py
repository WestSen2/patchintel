"""Seed hero/item entity tables from the community Deadlock API.

Numeric game IDs are the join keys everywhere downstream; display names are
only for humans (design review: never join on names). Refreshed at most
daily per the upstream caching policy.
"""

from __future__ import annotations

from ..config import Settings
from .client import request_with_backoff


def _headers(settings: Settings) -> dict:
    # Header, not query param — keys in URLs leak into logs.
    return {"X-API-KEY": settings.deadlock_api_key} if settings.deadlock_api_key else {}


def fetch_heroes(settings: Settings) -> list[dict]:
    """-> [{"id": int, "name": str}, ...]"""
    resp = request_with_backoff(
        "GET", f"{settings.deadlock_api_base}/v1/assets/heroes", headers=_headers(settings)
    )
    return [
        {"id": h["id"], "name": h.get("name", "")}
        for h in resp.json()
        if "id" in h
    ]


def fetch_items(settings: Settings) -> list[dict]:
    """-> [{"id", "name", "tier", "cost"}, ...]"""
    resp = request_with_backoff(
        "GET", f"{settings.deadlock_api_base}/v1/assets/items", headers=_headers(settings)
    )
    items = []
    for it in resp.json():
        if "id" not in it:
            continue
        items.append(
            {
                "id": it["id"],
                "name": it.get("name", ""),
                "tier": it.get("item_tier"),
                "cost": it.get("cost"),
            }
        )
    return items
