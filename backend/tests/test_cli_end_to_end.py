"""End-to-end CLI test: run.py with ALL upstream I/O mocked.

Simulates the user's real local run — --backfill --snapshots --timing
--verdicts — and asserts the database ends up with patches, snapshots,
timing buckets, and verdicts. This is the closest validation of the M2
acceptance flow possible without API keys.
"""

import sys
from datetime import datetime
from unittest import mock

from app import models
from app.pipeline import run as cli

BASE_DATE = datetime(2026, 1, 10)

RAW_NOTES = (
    "Deadlock Gameplay Update\n\n"
    + "General fixes and improvements across the board. " * 16
    + "\nHeroes:\nInfernus: Base damage reduced from 30 to 27\n"
)

NEWS_ITEM = {
    "gid": "e2e-1",
    "title": "Deadlock - Gameplay Update - 01-10-2026",
    "url": "https://forums.playdeadlock.com/threads/e2e-1",
    "contents": RAW_NOTES,
    "date": BASE_DATE,
    "feedlabel": "Product Update",
    "feedname": "steam_community_announcements",
}

LLM_RESULT = {
    "summary": "Infernus nerfed.",
    "changes": [
        {
            "entity_type": "hero",
            "entity_name": "Infernus",
            "change_type": "nerf",
            "description": "Base damage reduced from 30 to 27.",
            "numbers": [{"stat": "Base damage", "old": "30", "new": "27", "unit": ""}],
            "source_line": "Infernus: Base damage reduced from 30 to 27",
        }
    ],
}

HERO_ROWS = [{"hero_id": 1, "wins": 1040, "losses": 960, "matches": 2000}]
ITEM_ROWS = [{"item_id": 10, "wins": 1000, "losses": 1000, "matches": 2000,
              "avg_buy_time_s": 720.0, "avg_buy_time_relative": 33.3}]


def test_cli_full_m2_flow(db_session, monkeypatch):
    """python -m app.pipeline.run --backfill --snapshots --timing --verdicts"""
    monkeypatch.setattr(sys, "argv", ["run.py", "--backfill", "--snapshots",
                                      "--timing", "--verdicts"])

    # Entity resolver needs the hero seeded (normally done by --seed-entities)
    db_session.add(models.Hero(id=1, name="Infernus"))
    db_session.commit()

    summarizer = mock.Mock()
    summarizer.llm_generated = True
    summarizer.summarize.return_value = mock.Mock(
        summary=LLM_RESULT["summary"],
        changes=[
            mock.Mock(
                entity_type=c["entity_type"],
                entity_name=c["entity_name"],
                change_type=mock.Mock(value=c["change_type"]),
                description=c["description"],
                numbers=[mock.Mock(model_dump=lambda n=n: n) for n in c["numbers"]],
                source_line=c["source_line"],
            )
            for c in LLM_RESULT["changes"]
        ],
    )

    news_item = mock.Mock(
        gid=NEWS_ITEM["gid"], title=NEWS_ITEM["title"], url=NEWS_ITEM["url"],
        contents=NEWS_ITEM["contents"], date=NEWS_ITEM["date"],
        feedlabel=NEWS_ITEM["feedlabel"], feedname=NEWS_ITEM["feedname"],
    )

    with mock.patch(
        "app.pipeline.orchestrator.steam_news.fetch_recent_news",
        side_effect=[[news_item], []],  # one page, then history exhausted
    ), mock.patch(
        "app.pipeline.orchestrator.steam_news.strip_bbcode", side_effect=lambda t: t
    ), mock.patch(
        "app.pipeline.orchestrator.steam_news.is_patch_candidate", return_value=True
    ), mock.patch(
        "app.pipeline.orchestrator.forum_scraper.fetch_patch_notes",
        side_effect=AssertionError("scraper should not be needed for full contents"),
    ), mock.patch(
        "app.pipeline.run.get_summarizer", return_value=summarizer
    ), mock.patch(
        "app.pipeline.snapshots.deadlock_analytics.hero_stats",
        side_effect=[HERO_ROWS, HERO_ROWS],
    ), mock.patch(
        "app.pipeline.snapshots.deadlock_analytics.item_stats",
        side_effect=[ITEM_ROWS, ITEM_ROWS],
    ), mock.patch(
        "app.pipeline.item_timing.deadlock_analytics.item_stats",
        return_value=ITEM_ROWS,
    ), mock.patch(
        "app.pipeline.run.SessionLocal", return_value=db_session
    ), mock.patch("app.pipeline.run.init_db"):
        cli.main()

    patch = db_session.query(models.Patch).one()
    assert patch.status == "extracted"
    assert patch.summary == "Infernus nerfed."
    assert len(patch.changes) == 1

    snapshots = db_session.query(models.StatSnapshot).all()
    assert {s.window for s in snapshots} == {"pre", "post"}

    timing = db_session.query(models.ItemTimingSnapshot).all()
    assert timing, "timing buckets should be captured"

    verdicts = db_session.query(models.Verdict).all()
    assert len(verdicts) == 1
    assert verdicts[0].verdict in {
        "worked", "backfired", "unclear", "shifted", "no_effect",
        "insufficient_data", "excluded",
    }
