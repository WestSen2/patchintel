#!/usr/bin/env python3
"""Spike: validate the community Deadlock API before building M2 around it.

Answers three questions:
  1. Do hero aggregate stats work, and what fields/filters exist?
  2. Does match metadata expose ITEM PURCHASE TIMING/ORDER? (blueprint risk #1)
  3. What do hero build stats offer (build paths, win rates)?

Usage:
    python scripts/spike_deadlock_api.py                 # unauthenticated
    DEADLOCK_API_KEY=... python scripts/spike_deadlock_api.py
    python scripts/spike_deadlock_api.py 135954275       # explicit match_id

Respect the service: this script makes ~4 requests total.
Docs: https://api.deadlock-api.com/docs
"""

from __future__ import annotations

import json
import os
import sys

import httpx

BASE = "https://api.deadlock-api.com"
TIMEOUT = 30.0


def client() -> httpx.Client:
    headers = {}
    key = os.environ.get("DEADLOCK_API_KEY")
    if key:
        headers["X-API-KEY"] = key  # header, not query param (leaks less)
    return httpx.Client(base_url=BASE, headers=headers, timeout=TIMEOUT)


def show(title: str, data, limit: int = 1200) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    text = json.dumps(data, indent=2, default=str)
    print(text[:limit] + ("\n... [truncated]" if len(text) > limit else ""))


def get_match_id(c: httpx.Client) -> int | None:
    """Grab a live match_id from the active-matches feed (always available)."""
    r = c.get("/v1/matches/active")
    if r.status_code != 200:
        return None
    matches = r.json()
    return matches[0]["match_id"] if matches else None


def main() -> int:
    findings: list[str] = []

    with client() as c:
        # --- Q0: heroes (also gives us hero_ids for later calls) ----------
        r = c.get("/v1/assets/heroes")
        r.raise_for_status()
        heroes = r.json()
        playable = [h for h in heroes if not h.get("disabled")]
        print(f"[ok] /v1/assets/heroes -> {len(heroes)} total, {len(playable)} playable")
        hero_id = playable[0]["id"] if playable else None
        hero_name = playable[0].get("name") if playable else None

        # --- Q1: hero aggregate stats -------------------------------------
        r = c.get("/v1/analytics/hero-stats")
        if r.status_code == 200:
            stats = r.json()
            sample = stats[0] if isinstance(stats, list) and stats else stats
            show("Q1: /v1/analytics/hero-stats (first record)", sample)
            fields = sorted(sample.keys()) if isinstance(sample, dict) else []
            findings.append(f"hero-stats fields: {fields}")
        else:
            findings.append(f"hero-stats FAILED: {r.status_code} {r.text[:200]}")

        # --- Q3: hero build stats ------------------------------------------
        if hero_id:
            r = c.get(f"/v1/analytics/hero-build-stats/{hero_id}")
            if r.status_code == 200:
                show(f"Q3: /v1/analytics/hero-build-stats/{hero_id} ({hero_name})", r.json())
                findings.append("hero-build-stats: OK — build-level win/loss/matches available")
            else:
                findings.append(f"hero-build-stats FAILED: {r.status_code} {r.text[:200]}")

        # --- Q2: match metadata -> item timing? (THE critical question) ---
        match_id = int(sys.argv[1]) if len(sys.argv) > 1 else get_match_id(c)
        if match_id:
            print(f"[ok] probing match metadata for match_id={match_id}")
            r = c.get(f"/v1/matches/{match_id}/metadata")
            if r.status_code == 200:
                meta = r.json()
                show(f"Q2: /v1/matches/{match_id}/metadata", meta, limit=4000)
                text = json.dumps(meta).lower()
                signals = [k for k in ("purchase_time", "buy_time", "time_s", "game_time", "items") if k in text]
                findings.append(
                    f"match metadata timing/item signals found: {signals or 'NONE'} "
                    "— inspect output above; per-item timestamps = full build-order design, "
                    "final inventory only = item-sequence fallback"
                )
            else:
                findings.append(f"match metadata FAILED: {r.status_code} {r.text[:200]}")
        else:
            findings.append("could not obtain a match_id — pass one: spike_deadlock_api.py <match_id>")

    print(f"\n{'=' * 70}\nFINDINGS\n{'=' * 70}")
    for f in findings:
        print(f"- {f}")
    print(
        "\nNext: paste this output into the M2 planning discussion.\n"
        "If item timing/order is NOT in match metadata, narrow build-order\n"
        "analysis to item SEQUENCE (first N items) per blueprint risk #1."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
