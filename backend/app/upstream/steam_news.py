"""Steam Web API: patch announcement detection for Deadlock (appid 1422450).

Steam news is the TRIGGER ("a patch happened"). The full notes with real
numbers are scraped from the forums afterwards (forum_scraper.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from ..config import Settings
from .client import request_with_backoff

STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
DEADLOCK_APP_ID = 1422450

# Deadlock announcements consistently use "Update" in the title
# ("Deadlock - Gameplay Update - 04-30-2026", "Minor Update - 07-01-2026").
_PATCH_TITLE = re.compile(r"\b(update|patch)\b", re.IGNORECASE)


@dataclass(frozen=True)
class NewsItem:
    gid: str
    title: str
    url: str
    contents: str
    date: datetime


def fetch_recent_news(settings: Settings, count: int = 20) -> list[NewsItem]:
    """Fetch recent Deadlock news items. Requires settings.steam_api_key."""
    if not settings.steam_api_key:
        raise RuntimeError("STEAM_API_KEY is not set — put it in backend/.env")

    resp = request_with_backoff(
        "GET",
        STEAM_NEWS_URL,
        params={
            "appid": DEADLOCK_APP_ID,
            "key": settings.steam_api_key,
            "count": count,
            "format": "json",
        },
    )
    items = resp.json().get("appnews", {}).get("newsitems", [])
    return [
        NewsItem(
            gid=str(i["gid"]),
            title=i.get("title", ""),
            url=i.get("url", ""),
            contents=i.get("contents", ""),
            date=datetime.utcfromtimestamp(i.get("date", 0)),
        )
        for i in items
    ]


def is_patch_candidate(item: NewsItem) -> bool:
    """Heuristic filter: does this news item look like a gameplay patch?"""
    return bool(_PATCH_TITLE.search(item.title))
