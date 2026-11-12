"""Snapshot service tests: windows, storage, verdicts — analytics mocked."""

from datetime import datetime
from unittest import mock

from app import models
from app.config import get_settings
from app.pipeline.snapshots import (
    compute_verdicts,
    compute_windows,
    snapshot_patch,
)

PATCH_DATE = datetime(2026, 1, 10)

HERO_PRE = [{"hero_id": 1, "wins": 1040, "losses": 960, "matches": 2000, "total_kills": 5}]
HERO_POST = [{"hero_id": 1, "wins": 960, "losses": 1040, "matches": 2000}]
ITEM_ROWS = [{"item_id": 10, "wins": 1000, "losses": 1000, "matches": 2000,
              "avg_buy_time_s": 720.0, "avg_buy_time_relative": 33.3}]


def _seed_patch(db, entity_id=1, change_type="nerf"):
    patch = models.Patch(
        steam_gid="snap-1",
        title="Deadlock - Gameplay Update - 01-10-2026",
        patch_date=PATCH_DATE,
        source_url="https://example.com/p1",
        raw_text="x",
        status="extracted",
    )
    patch.changes.append(
        models.Change(
            entity_type="hero",
            entity_name="Infernus",
            entity_id=entity_id,
            change_type=change_type,
            description="d",
            numbers=[],
            source_line="x",
        )
    )
    db.add(patch)
    db.commit()
    return patch


def _run_snapshots(db, patch):
    settings = get_settings()
    with mock.patch(
        "app.pipeline.snapshots.deadlock_analytics.hero_stats",
        side_effect=[HERO_PRE, HERO_POST],
    ), mock.patch(
        "app.pipeline.snapshots.deadlock_analytics.item_stats",
        side_effect=[ITEM_ROWS, ITEM_ROWS],
    ):
        return snapshot_patch(db, settings, patch)


def test_compute_windows_normal_and_truncated():
    pre, post = compute_windows(PATCH_DATE, None)
    assert (PATCH_DATE - pre.start).days == 7
    assert (post.start - PATCH_DATE).days == 1  # patch day skipped
    assert not post.truncated

    hotfix = PATCH_DATE.replace(day=14)
    _, post2 = compute_windows(PATCH_DATE, hotfix)
    assert post2.truncated
    assert post2.end == hotfix


def test_snapshot_stores_pre_and_post(db_session):
    patch = _seed_patch(db_session)
    stored = _run_snapshots(db_session, patch)
    assert stored == 4  # 1 hero + 1 item, x2 windows

    snaps = db_session.query(models.StatSnapshot).filter_by(
        entity_type="hero", entity_id=1
    ).all()
    assert {s.window for s in snaps} == {"pre", "post"}
    pre = next(s for s in snaps if s.window == "pre")
    assert pre.win_rate == 1040 / 2000
    assert pre.extra["wins"] == 1040

    item_snap = db_session.query(models.StatSnapshot).filter_by(
        entity_type="item", entity_id=10, window="pre"
    ).one()
    assert item_snap.extra["avg_buy_time_s"] == 720.0


def test_snapshot_idempotent(db_session):
    patch = _seed_patch(db_session)
    _run_snapshots(db_session, patch)
    _run_snapshots(db_session, patch)  # second run replaces, not duplicates
    assert db_session.query(models.StatSnapshot).count() == 4


def test_verdicts_computed_from_snapshots(db_session):
    patch = _seed_patch(db_session)  # nerf, 52% -> 48% = worked
    _run_snapshots(db_session, patch)
    n = compute_verdicts(db_session, patch)
    assert n == 1
    v = db_session.query(models.Verdict).one()
    assert v.verdict == "worked"
    assert v.pre_matches == 2000
    assert v.delta_win_rate is not None and v.delta_win_rate < 0


def test_verdict_missing_snapshot_is_insufficient_data(db_session):
    patch = _seed_patch(db_session, entity_id=999)  # no stats for hero 999
    _run_snapshots(db_session, patch)
    compute_verdicts(db_session, patch)
    v = db_session.query(models.Verdict).one()
    assert v.verdict == "insufficient_data"


def test_unresolved_entity_gets_no_verdict(db_session):
    patch = _seed_patch(db_session, entity_id=None)
    _run_snapshots(db_session, patch)
    n = compute_verdicts(db_session, patch)
    assert n == 0
    assert db_session.query(models.Verdict).count() == 0


def test_snapshot_skips_patch_without_date(db_session):
    patch = _seed_patch(db_session)
    patch.patch_date = None
    db_session.commit()
    assert snapshot_patch(db_session, get_settings(), patch) == 0
