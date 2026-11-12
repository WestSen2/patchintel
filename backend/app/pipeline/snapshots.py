"""Snapshot service (M2): patch windows -> aggregate pulls -> snapshots -> verdicts.

For every extracted patch we capture hero/item aggregates over the 7 days
BEFORE and days 1-8 AFTER the patch (skipping patch day itself), then run
the verdict math on every extracted change with a resolved entity.

Idempotent: snapshot/verdict rows for a patch are replaced, not duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import models
from ..config import Settings
from ..upstream import deadlock_analytics
from .verdicts import compute_verdict

PATCH_WINDOW_DAYS = 7
POST_WINDOW_SKIP_DAYS = 1  # patch day itself is chaotic; skip it


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime
    truncated: bool = False


def compute_windows(
    patch_date: datetime, next_patch_date: datetime | None
) -> tuple[Window, Window]:
    pre = Window(patch_date - timedelta(days=PATCH_WINDOW_DAYS), patch_date)
    post_end = patch_date + timedelta(days=POST_WINDOW_SKIP_DAYS + PATCH_WINDOW_DAYS)
    truncated = False
    if next_patch_date and next_patch_date < post_end:
        post_end = next_patch_date
        truncated = True
    post = Window(patch_date + timedelta(days=POST_WINDOW_SKIP_DAYS), post_end, truncated)
    return pre, post


def _replace_snapshots(
    db: Session,
    patch_id: int,
    label: str,
    window: Window,
    hero_rows: list[dict],
    item_rows: list[dict],
) -> int:
    db.query(models.StatSnapshot).filter_by(patch_id=patch_id, window=label).delete()

    stored = 0
    total_hero_matches = sum(r.get("matches", 0) for r in hero_rows) or 1
    for r in hero_rows:
        matches = r.get("matches", 0)
        if matches <= 0:
            continue
        wins = r.get("wins", 0)
        db.add(
            models.StatSnapshot(
                entity_type="hero",
                entity_id=r["hero_id"],
                patch_id=patch_id,
                window=label,
                window_start=window.start,
                window_end=window.end,
                truncated=window.truncated,
                win_rate=wins / matches,
                pick_rate=matches / total_hero_matches,
                matches=matches,
                extra={
                    "wins": wins,
                    "losses": r.get("losses", 0),
                    "kills": r.get("total_kills"),
                    "net_worth": r.get("total_net_worth"),
                },
            )
        )
        stored += 1

    for r in item_rows:
        matches = r.get("matches", 0)
        if matches <= 0:
            continue
        wins = r.get("wins", 0)
        db.add(
            models.StatSnapshot(
                entity_type="item",
                entity_id=r["item_id"],
                patch_id=patch_id,
                window=label,
                window_start=window.start,
                window_end=window.end,
                truncated=window.truncated,
                win_rate=wins / matches,
                pick_rate=None,
                matches=matches,
                extra={
                    "wins": wins,
                    "losses": r.get("losses", 0),
                    "avg_buy_time_s": r.get("avg_buy_time_s"),
                    "avg_buy_time_relative": r.get("avg_buy_time_relative"),
                },
            )
        )
        stored += 1

    db.commit()
    return stored


def snapshot_patch(db: Session, settings: Settings, patch: models.Patch) -> int:
    """Capture pre/post snapshots for one patch. Returns rows stored."""
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
        hero_rows = deadlock_analytics.hero_stats(settings, window.start, window.end)
        item_rows = deadlock_analytics.item_stats(settings, window.start, window.end)
        stored += _replace_snapshots(db, patch.id, label, window, hero_rows, item_rows)
    return stored


def _snapshot(db: Session, entity_type: str, entity_id: int, patch_id: int, window: str):
    return (
        db.query(models.StatSnapshot)
        .filter_by(
            entity_type=entity_type, entity_id=entity_id, patch_id=patch_id, window=window
        )
        .first()
    )


def compute_verdicts(db: Session, patch: models.Patch) -> int:
    """(Re)compute verdicts for every extracted change of one patch."""
    db.query(models.Verdict).filter_by(patch_id=patch.id).delete()

    computed = 0
    for change in patch.changes:
        if change.entity_id is None or change.entity_type not in ("hero", "item"):
            continue  # unresolved entities get no verdict (never guessed)

        pre = _snapshot(db, change.entity_type, change.entity_id, patch.id, "pre")
        post = _snapshot(db, change.entity_type, change.entity_id, patch.id, "post")

        if pre is None or post is None:
            db.add(
                models.Verdict(
                    patch_id=patch.id,
                    change_id=change.id,
                    entity_type=change.entity_type,
                    entity_id=change.entity_id,
                    expected_direction="none",
                    pre_matches=0,
                    post_matches=0,
                    verdict="insufficient_data",
                    reason="snapshot missing for this entity/window",
                )
            )
            computed += 1
            continue

        out = compute_verdict(
            change.change_type,
            pre.extra.get("wins", 0),
            pre.matches,
            post.extra.get("wins", 0),
            post.matches,
        )
        db.add(
            models.Verdict(
                patch_id=patch.id,
                change_id=change.id,
                entity_type=change.entity_type,
                entity_id=change.entity_id,
                expected_direction=out.expected_direction,
                pre_win_rate=pre.win_rate,
                post_win_rate=post.win_rate,
                delta_win_rate=out.delta_win_rate,
                pre_pick_rate=pre.pick_rate,
                post_pick_rate=post.pick_rate,
                pre_matches=pre.matches,
                post_matches=post.matches,
                ci_half_width=out.ci_half_width,
                verdict=out.verdict,
                reason=out.reason,
            )
        )
        computed += 1

    db.commit()
    return computed
