"""M3 tests: match import, sessionization, tilt analytics math."""

from datetime import datetime, timedelta
from unittest import mock

from app import models
from app.config import get_settings
from app.personal import analytics, sync

STEAM64 = "76561198012345678"
ACCT3 = sync.steam_id_3(STEAM64)
BASE = datetime(2026, 11, 1, 18, 0, 0)


def _user(db):
    user = models.User(steam_id=STEAM64, display_name="tester")
    db.add(user)
    db.commit()
    return user


def _meta_page(match_id, start, kills=5, deaths=2, assists=7, team="Team0",
               winning="Team0"):
    return [{
        "match_id": match_id,
        "start_time": int(start.timestamp()),
        "duration_s": 1800,
        "winning_team": winning,
        "players": [{
            "account_id": ACCT3, "hero_id": 1, "team": team,
            "kills": kills, "deaths": deaths, "assists": assists,
            "items": [{"item_id": 10, "game_time_s": 300}],
        }],
    }]


def test_steam_id_conversion():
    assert sync.steam_id_3(STEAM64) == int(STEAM64) - 76561197960265728


def test_import_matches_idempotent(db_session):
    user = _user(db_session)
    pages = [_meta_page(1001, BASE), _meta_page(1002, BASE + timedelta(hours=1))]
    assert sync.import_matches(db_session, user, pages) == 2
    assert sync.import_matches(db_session, user, pages) == 0
    matches = db_session.query(models.UserMatch).all()
    assert len(matches) == 2
    assert matches[0].result == "win"
    assert matches[0].items_json[0]["game_time_s"] == 300


def test_import_skips_when_user_not_in_payload(db_session):
    user = _user(db_session)
    page = _meta_page(1003, BASE)
    page[0]["players"] = []  # metadata without our player
    assert sync.import_matches(db_session, user, [page]) == 0


def _bulk_matches(db, user):
    """6 matches across 2 sessions (gap > 45 min), alternating results."""
    starts = [
        (BASE + timedelta(hours=0), "win"),
        (BASE + timedelta(hours=1), "loss"),
        (BASE + timedelta(hours=2), "loss"),
        # ---- 3-hour gap -> new session ----
        (BASE + timedelta(hours=5), "loss"),
        (BASE + timedelta(hours=6), "win"),
        (BASE + timedelta(hours=7), "win"),
    ]
    for i, (start, result) in enumerate(starts):
        db.add(models.UserMatch(
            user_id=user.id, match_id=2000 + i, played_at=start, duration_s=1800,
            hero_id=1 if i % 2 == 0 else 2, result=result,
            kills=10 - i, deaths=2 + i, assists=5,
        ))
    db.commit()


def test_rebuild_sessions_splits_on_gap(db_session):
    user = _user(db_session)
    _bulk_matches(db_session, user)
    assert sync.rebuild_sessions(db_session, user) == 2
    sessions = (
        db_session.query(models.PlaySession)
        .order_by(models.PlaySession.started_at).all()
    )
    assert [s.game_count for s in sessions] == [3, 3]
    assert [s.wins for s in sessions] == [1, 2]
    # every match assigned
    assert db_session.query(models.UserMatch).filter(
        models.UserMatch.session_id.is_(None)
    ).count() == 0
    # rebuild is idempotent
    assert sync.rebuild_sessions(db_session, user) == 2


def test_sync_user_end_to_end_mocked(db_session):
    user = _user(db_session)
    page = _meta_page(3001, BASE) + _meta_page(3002, BASE + timedelta(hours=1))
    with mock.patch(
        "app.personal.sync.fetch_metadata_page", side_effect=[page]
    ):
        result = sync.sync_user(db_session, get_settings(), user)
    assert result == {"imported": 2, "sessions": 1}
    assert user.last_sync_at is not None


def test_analytics_math(db_session):
    user = _user(db_session)
    _bulk_matches(db_session, user)
    sync.rebuild_sessions(db_session, user)
    matches = (
        db_session.query(models.UserMatch)
        .order_by(models.UserMatch.played_at).all()
    )
    out = analytics.compute_analytics(matches, "America/Los_Angeles")

    assert out["matches"] == 6
    assert out["win_rate"] == 0.5

    decay = {b["label"]: b for b in out["by_session_game_index"]}
    # game 1 of each session: W + L -> 0.5; game 2: L + W -> 0.5; game 3: L + W -> 0.5
    assert decay["game 1"]["matches"] == 2
    assert decay["game 1"]["win_rate"] == 0.5

    streaks = {b["label"]: b for b in out["after_loss_streak"]}
    # sequence: W L L | L W W
    # streaks before each game: 0(W), 0(L), 1(L), 2(L), 3(W), 0(W)
    assert streaks["after win/1st game"]["matches"] == 3  # W, L, W -> wins 2
    assert streaks["after 1 loss"]["matches"] == 1
    assert streaks["after 2 losses"]["matches"] == 1
    assert streaks["after 3+ losses"]["matches"] == 1

    assert len(out["by_hour"]) > 0
    assert len(out["by_weekday"]) > 0
    assert out["top_heroes"][0]["matches"] == 3
