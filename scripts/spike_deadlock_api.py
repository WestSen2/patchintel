#!/usr/bin/env python3
"""Spike: validate the community Deadlock API before building M2 around it.

Answers three questions:
  1. Do hero aggregate stats work, and what fields/filters exist?
  2. Does match metadata expose ITEM PURCHASE TIMING/ORDER? (blueprint risk #1)
  3. What do hero build stats offer (build paths, win rates)?

Usage:
    python scripts/spike_deadlock_api.py                 # unauthenticated (lower limits)
    DEADLOCK_API_KEY=... python scripts/spike_deadlock_api.py

Respect the service: this script makes ~5 requests total.
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


def main() -> int:
    findings: list[str] = []

    with client() as c:
        # --- Q0: heroes (also gives us hero_ids for later calls) ----------
        r = c.get("/v1/assets/heroes")
        r.raise_for_status()
        heroes = r.json()
        print(f"[ok] /v1/assets/heroes -> {len(heroes)} heroes")
        hero_id = heroes[0]["id"] if heroes else None
        hero_name = heroes[0].get("name") if heroes else None

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

        # --- Q2: match metadata -> item timing? (THE critical question) ---
        # Need a recent match_id: pull one from hero build stats or leaderboard
        match_id = None
        r = c.get(f"/v1/analytics/hero-build-stats/{hero_id}") if hero_id else None
        if r is not None and r.status_code == 200:
            builds = r.json()
            show(f"Q3: /v1/analytics/hero-build-stats/{hero_id} ({hero_name})", builds)
            findings.append("hero-build-stats: OK — inspect output for build-path fields")
        elif r is not None:
            findings.append(f"hero-build-stats FAILED: {r.status_code} {r.text[:200]}")

        if match_id is None:
            r = c.get("/v1/leaderboard/NA")
            if r.status_code == 200:
                lb = r.json()
                entries = lb if isinstance(lb, list) else lb.get("entries", [])
                for e in entries[:5]:
                    if isinstance(e, dict) and e.get("last_match_id"):
                        match_id = e["last_match_id"]
                        break

        if match_id:
            r = c.get(f"/v1/matches/{match_id}/metadata")
            if r.status_code == 200:
                meta = r.json()
                show(f"Q2: /v1/matches/{match_id}/metadata", meta, limit=3000)
                text = json.dumps(meta).lower()
                has_timing = any(k in text for k in ("purchase_time", "buy_time", "time_s", "game_time"))
                findings.append(
                    f"match metadata item-timing signals present: {has_timing} "
                    "(manual inspection required — look for per-item timestamps/order)"
                )
            else:
                findings.append(f"match metadata FAILED: {r.status_code} {r.text[:200]}")
        else:
            findings.append("could not obtain a match_id — rerun later or pass one manually")

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
