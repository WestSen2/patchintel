"""Scrape full patch notes from forums.playdeadlock.com.

Steam blurbs rarely contain the per-change numbers; Yoshi's forum posts do.
This runs at most once per detected patch and the result is cached in the DB
forever, so load on the forum is negligible.

The forum is XenForo: post bodies live in .bbWrapper containers. Selectors
are ordered most-specific-first with a whole-page fallback; if the markup
changes, we raise ScrapeError and the patch goes to needs_review rather
than storing garbage (design review D2).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from .client import request_with_backoff

MIN_NOTES_LENGTH = 500  # chars; shorter means we probably grabbed chrome, not notes

_CANDIDATE_SELECTORS = [
    ".bbWrapper",      # XenForo post body (primary)
    "article",
    ".post-content",
    "main",
]


class ScrapeError(Exception):
    """Forum markup changed or the page didn't contain usable notes."""


def fetch_patch_notes(url: str) -> str:
    resp = request_with_backoff("GET", url)
    soup = BeautifulSoup(resp.text, "html.parser")

    for selector in _CANDIDATE_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        text = node.get_text("\n", strip=True)
        if len(text) >= MIN_NOTES_LENGTH:
            return text

    # Last resort: whole page, but demand it looks like real notes
    text = soup.get_text("\n", strip=True)
    if len(text) < MIN_NOTES_LENGTH:
        raise ScrapeError(
            f"Page too short ({len(text)} chars) to be patch notes: {url}"
        )
    return text
