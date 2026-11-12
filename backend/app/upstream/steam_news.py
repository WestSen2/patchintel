"""Steam Web API: patch announcement detection for Deadlock (appid 1422450).

Steam news is the TRIGGER ("a patch happened"). For official announcements
the API payload usually already contains the full notes (BBCode) — use that
first; only fall back to scraping when contents are too short.

Only items from the official feed (feedname == "steam_community_announcements")
count as patch candidates: the same API also returns third-party coverage
(PCGamesN, PC Gamer, ...), which is news ABOUT patches, not patch notes.

Pagination: GetNewsForApp supports `enddate` (unix seconds) — items strictly
before that timestamp. backfill_patches() pages backwards to ingest the
full patch history.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import Settings
from .client import request_with_backoff

STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
DEADLOCK_APP_ID = 1422450
OFFICIAL_FEED = "steam_community_announcements"

# Deadlock announcements consistently use "Update" in the title
# ("Deadlock - Gameplay Update - 04-30-2026", "Minor Update - 07-01-2026").
_PATCH_TITLE = re.compile(r"\b(update|patch)\b", re.IGNORECASE)
_BBCODE_TAG = re.compile(r"\[/?[^\]\n]{1,40}\]")


@dataclass(frozen=True)
class NewsItem:
    gid: str
    title: str
    url: str
    contents: str
    date: datetime
    feedname: str = ""


def strip_bbcode(text: str) -> str:
    """Remove BBCode markup ([b], [list], [*], [url=...]) from Steam news bodies."""
    text = _BBCODE_TAG.sub("", text)
    lines = (ln.strip() for ln in text.splitlines())
    return "\n".join(ln for ln in lines if ln)


def fetch_recent_news(
    settings: Settings, count: int = 20, enddate: int | None = None
) -> list[NewsItem]:
    """Fetch Deadlock news items (newest first). Requires settings.steam_api_key.

    enddate: unix seconds — only return items published before this moment.
    """
    if not settings.steam_api_key:
        raise RuntimeError("STEAM_API_KEY is not set — put it in backend/.env")

    params = {
        "appid": DEADLOCK_APP_ID,
        "key": settings.steam_api_key,
        "count": count,
        "format": "json",
    }
    if enddate is not None:
        params["enddate"] = enddate

    resp = request_with_backoff("GET", STEAM_NEWS_URL, params=params)
    items = resp.json().get("appnews", {}).get("newsitems", [])
    return [
        NewsItem(
            gid=str(i["gid"]),
            title=i.get("title", ""),
            url=i.get("url", ""),
            contents=i.get("contents", ""),
            date=datetime.fromtimestamp(i.get("date", 0), tz=timezone.utc).replace(
                tzinfo=None
            ),
            feedname=i.get("feedname", ""),
        )
        for i in items
    ]


def is_patch_candidate(item: NewsItem) -> bool:
    """Official-feed announcements that look like gameplay patches only."""
    return item.feedname == OFFICIAL_FEED and bool(_PATCH_TITLE.search(item.title))
