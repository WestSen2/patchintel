"""CLI entry point:  python -m app.pipeline.run [flags]

--seed-entities  refresh hero/item tables from the community API first
--backfill       page through full Steam news history (ALL past patches)
--snapshots      M2: capture pre/post stat snapshots for extracted patches
--verdicts       M2: (re)compute verdicts from existing snapshots

Everything is idempotent; safe to re-run any combination.
"""

from __future__ import annotations

import argparse

from .. import models
from ..config import get_settings
from ..db import SessionLocal, init_db
from .orchestrator import run_pipeline, seed_entities
from .snapshots import compute_verdicts, snapshot_patch
from .summarizer import get_summarizer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PatchIntel pipeline")
    parser.add_argument("--seed-entities", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--snapshots", action="store_true",
                        help="capture pre/post stat snapshots for extracted patches")
    parser.add_argument("--verdicts", action="store_true",
                        help="compute verdicts from existing snapshots")
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

        if args.snapshots or args.verdicts:
            patches = db.query(models.Patch).filter_by(status="extracted").all()
            for patch in patches:
                if args.snapshots:
                    rows = snapshot_patch(db, settings, patch)
                    print(f"[snapshot] {patch.title[:60]} -> {rows} rows")
                if args.verdicts:
                    n = compute_verdicts(db, patch)
                    print(f"[verdicts] {patch.title[:60]} -> {n} verdicts")
    finally:
        db.close()


if __name__ == "__main__":
    main()
