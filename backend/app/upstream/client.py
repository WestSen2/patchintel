"""Shared upstream HTTP policy.

Every external call in PatchIntel goes through request_with_backoff so the
rate-limit/caching rules from docs/m1-design-review.md section 6 live in
exactly one place:
- redirects are FOLLOWED (Steam news URLs 302 to steamcommunity.com etc.)
- 429 / 503 / 504 -> retry honoring Retry-After (capped), exponential backoff
- transport errors -> retry with backoff
- everything else -> raise_for_status
"""

from __future__ import annotations

import time

import httpx

USER_AGENT = "PatchIntel/0.1 (github.com/WestSen2/patchintel)"
MAX_WAIT_SECONDS = 60.0


class UpstreamError(Exception):
    """Upstream call failed after all retry attempts."""


def request_with_backoff(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    max_attempts: int = 4,
    timeout: float = 30.0,
) -> httpx.Response:
    merged_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    delay = 1.0
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.request(
                    method, url, params=params, headers=merged_headers
                )
        except httpx.TransportError as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(delay)
            delay *= 2
            continue

        if resp.status_code in (429, 503, 504):
            retry_after = resp.headers.get("Retry-After")
            wait = min(float(retry_after), MAX_WAIT_SECONDS) if retry_after else delay
            if attempt == max_attempts:
                raise UpstreamError(
                    f"{url} returned {resp.status_code} after {max_attempts} attempts"
                )
            time.sleep(wait)
            delay *= 2
            continue

        resp.raise_for_status()
        return resp

    raise UpstreamError(f"{url} failed: {last_error}")
