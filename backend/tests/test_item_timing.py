"""Item timing tests: bucket snapshots from mocked analytics calls."""

from datetime import datetime
from unittest import mock

from app import models
from app.config import get_settings
from app.pipeline.item_timing import TIMING_BUCKETS, snapshot_item_timing

PATCH_DATE = datetime(2026, 1, 10)

EARLY = [{"item_id": 10, "wins": 700, "losses": 300, "matches": 1000}]
MID = [{"item_id": 10, "wins": 500, "losses": 500, "matches": 1000}]
LATE = [{"item_id": 10, "wins": 300, "losses": 700, "matches": 1000}]


def _seed(db):
    patch = models.Patch(
        steam_gid="t1",
        title="Deadlock - Gameplay Update - 01-10-2026",
        patch_date=PATCH_DATE,
        source_url="https://example.com/t1",
        raw_text="x",
        status="extracted",
    )
    db.add(patch)
    db.commit()
    return patch


def test_item_timing_buckets(db_session):
    patch = _seed(db_session)
    # 2 windows x 3 buckets = 6 analytics calls
    with mock.patch(
        "app.pipeline.item_timing.deadlock_analytics.item_stats",
        side_effect=[EARLY, MID, LATE, EARLY, MID, LATE],
    ) as call:
        stored = snapshot_item_timing(db_session, get_settings(), patch)

    assert call.call_count == 2 * len(TIMING_BUCKETS)
    assert stored == 2  # one item, two windows

    snap = db_session.query(models.ItemTimingSnapshot).filter_by(
        item_id=10, window="pre"
    ).one()
    assert snap.win_rate_early == 0.7
    assert snap.win_rate_mid == 0.5
    assert snap.win_rate_late == 0.3
    assert snap.matches == 3000


def test_item_timing_idempotent(db_session):
    patch = _seed(db_session)
    with mock.patch(
        "app.pipeline.item_timing.deadlock_analytics.item_stats",
        side_effect=[EARLY, MID, LATE] * 4,
    ):
        snapshot_item_timing(db_session, get_settings(), patch)
        snapshot_item_timing(db_session, get_settings(), patch)
    assert db_session.query(models.ItemTimingSnapshot).count() == 2


def test_bucket_win_rate_handles_zero_matches(db_session):
    patch = _seed(db_session)
    empty = [{"item_id": 10, "wins": 0, "losses": 0, "matches": 0}]
    with mock.patch(
        "app.pipeline.item_timing.deadlock_analytics.item_stats",
        side_effect=[EARLY, empty, LATE, EARLY, empty, LATE],
    ):
        snapshot_item_timing(db_session, get_settings(), patch)
    snap = db_session.query(models.ItemTimingSnapshot).filter_by(
        item_id=10, window="pre"
    ).one()
    assert snap.win_rate_mid is None  # zero matches -> no fake 0% win rate
