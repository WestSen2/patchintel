"""CLI entry point:  python -m app.pipeline.run [--seed-entities] [--backfill]

--seed-entities refreshes hero/item tables from the community API first
(run it at most daily — the assets change only when Valve ships patches).

--backfill pages backwards through the entire Steam news history so the
archive contains EVERY Deadlock patch, not just the recent window. Safe to
re-run: already-known patches are skipped.
"""

from __future__ import annotations

import argparse

from ..config import get_settings
from ..db import SessionLocal, init_db
from .orchestrator import run_pipeline, seed_entities
from .summarizer import get_summarizer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PatchIntel M1 pipeline")
    parser.add_argument(
        "--seed-entities",
        action="store_true",
        help="refresh hero/item tables from the community Deadlock API first",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="page through full Steam news history to ingest ALL past patches",
    )
    args = parser.parse_args()

    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        if args.seed_entities:
            heroes, items = seed_entities(db, settings)
            print(f"[seed] {heroes} heroes, {items} items")

        stats = run_pipeline(db, settings, get_summarizer(settings), backfill=args.backfill)
        print(
            f"[done] new={stats.detected_new} enriched={stats.enriched} "
            f"extracted={stats.extracted} needs_review={stats.needs_review} "
            f"dropped_changes={stats.dropped_changes}"
        )
        for err in stats.errors:
            print(f"  [warn] {err}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
