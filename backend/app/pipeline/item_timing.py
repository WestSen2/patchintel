"""Item purchase-timing snapshots (M2 build-order explorer).

For each patch window we bucket item purchases into game phases using the
item-stats `min_bought_at_s`/`max_bought_at_s` filters:

    early:  bought before 12:00
    mid:    12:00 - 24:00
    late:   after 24:00

One analytics call per bucket per window returns ALL items at once, so the
cost is 3 calls per window per patch. Win rates per bucket answer the
original product question: "does buying this item EARLY actually win more?"
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from ..config import Settings
from ..upstream import deadlock_analytics
from .snapshots import compute_windows

EARLY_MAX_S = 12 * 60
MID_MAX_S = 24 * 60

TIMING_BUCKETS: dict[str, tuple[int | None, int | None]] = {
    "early": (None, EARLY_MAX_S),
    "mid": (EARLY_MAX_S, MID_MAX_S),
    "late": (MID_MAX_S, None),
}


def _bucket_win_rate(row: dict | None) -> float | None:
    if not row or row.get("matches", 0) <= 0:
        return None
    return row["wins"] / row["matches"]


def snapshot_item_timing(db: Session, settings: Settings, patch: models.Patch) -> int:
    """Capture timing-bucket snapshots for one patch. Idempotent per window."""
    if patch.patch_date is None:
        return 0

    next_patch = (
        db.query(models.Patch)
        .filter(models.Patch.patch_date > patch.patch_date)
        .order_by(models.Patch.patch_date)
        .first()
    )
    pre, post = compute_windows(
        patch.patch_date, next_patch.patch_date if next_patch else None
    )

    stored = 0
    for label, window in (("pre", pre), ("post", post)):
        db.query(models.ItemTimingSnapshot).filter_by(
            patch_id=patch.id, window=label
        ).delete()

        bucket_rows: dict[str, dict[int, dict]] = {}
        for bucket, (lo, hi) in TIMING_BUCKETS.items():
            rows = deadlock_analytics.item_stats(
                settings,
                window.start,
                window.end,
                min_bought_at_s=lo,
                max_bought_at_s=hi,
            )
            bucket_rows[bucket] = {r["item_id"]: r for r in rows if "item_id" in r}

        item_ids = set().union(*(set(b) for b in bucket_rows.values()))
        for item_id in item_ids:
            early = bucket_rows["early"].get(item_id)
            mid = bucket_rows["mid"].get(item_id)
            late = bucket_rows["late"].get(item_id)
            total_matches = sum(
                (r or {}).get("matches", 0) for r in (early, mid, late)
            )

            # avg buy time comes from the base item snapshot (if captured)
            base = (
                db.query(models.StatSnapshot)
                .filter_by(
                    entity_type="item", entity_id=item_id, patch_id=patch.id, window=label
                )
                .first()
            )
            extra = base.extra if base else {}

            db.add(
                models.ItemTimingSnapshot(
                    item_id=item_id,
                    patch_id=patch.id,
                    window=label,
                    avg_buy_time_s=extra.get("avg_buy_time_s"),
                    avg_buy_time_relative=extra.get("avg_buy_time_relative"),
                    win_rate_early=_bucket_win_rate(early),
                    win_rate_mid=_bucket_win_rate(mid),
                    win_rate_late=_bucket_win_rate(late),
                    matches=total_matches,
                )
            )
            stored += 1

        db.commit()
    return stored
