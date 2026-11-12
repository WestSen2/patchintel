"""CLI entry point:  python -m app.pipeline.run [--seed-entities]

--seed-entities refreshes hero/item tables from the community API first
(run it at most daily — the assets change only when Valve ships patches).
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
    args = parser.parse_args()

    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        if args.seed_entities:
            heroes, items = seed_entities(db, settings)
            print(f"[seed] {heroes} heroes, {items} items")

        stats = run_pipeline(db, settings, get_summarizer(settings))
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
