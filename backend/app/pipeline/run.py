"""CLI entry point:  python -m app.pipeline.run [flags]

--seed-entities  refresh hero/item tables from the community API first
--backfill       page through full Steam news history (ALL past patches)
--snapshots      M2: capture pre/post stat snapshots for extracted patches
--timing         M2: capture item purchase-timing bucket snapshots
--verdicts       M2: (re)compute verdicts from existing snapshots

Everything is idempotent; safe to re-run any combination.
"""

from __future__ import annotations

import argparse

from .. import models
from ..config import get_settings
from ..db import SessionLocal, init_db
from .entity_resolver import resolve_unknown_changes
from .item_timing import snapshot_item_timing
from .orchestrator import run_pipeline, seed_entities
from .snapshots import compute_verdicts, snapshot_patch
from .summarizer import get_summarizer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PatchIntel pipeline")
    parser.add_argument("--seed-entities", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--max-patches", type=int, default=None, metavar="N",
                        help="cap new patches ingested / processed (trial runs; "
                             "combine with --backfill and/or the stats flags)")
    parser.add_argument("--snapshots", action="store_true",
                        help="capture pre/post stat snapshots for extracted patches")
    parser.add_argument("--timing", action="store_true",
                        help="capture item purchase-timing bucket snapshots (3 calls/window/patch)")
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

        stats = run_pipeline(
            db, settings, get_summarizer(settings),
            backfill=args.backfill, max_patches=args.max_patches,
        )
        print(
            f"[done] new={stats.detected_new} enriched={stats.enriched} "
            f"extracted={stats.extracted} needs_review={stats.needs_review} "
            f"dropped_changes={stats.dropped_changes}"
        )
        for err in stats.errors:
            print(f"  [warn] {err}")

        if args.verdicts or args.snapshots:
            rescued = resolve_unknown_changes(db)
            if rescued:
                print(f"[resolve] rescued {rescued} changes with unknown entities")

        if args.snapshots or args.timing or args.verdicts:
            query = (
                db.query(models.Patch)
                .filter_by(status="extracted")
                .order_by(models.Patch.patch_date.desc())
            )
            if args.max_patches is not None:
                query = query.limit(args.max_patches)
            patches = query.all()
            for patch in patches:
                if args.snapshots:
                    rows = snapshot_patch(db, settings, patch)
                    print(f"[snapshot] {patch.title[:60]} -> {rows} rows")
                if args.timing:
                    rows = snapshot_item_timing(db, settings, patch)
                    print(f"[timing] {patch.title[:60]} -> {rows} rows")
                if args.verdicts:
                    n = compute_verdicts(db, patch)
                    print(f"[verdicts] {patch.title[:60]} -> {n} verdicts")
    finally:
        db.close()


if __name__ == "__main__":
    main()
