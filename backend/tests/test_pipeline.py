"""Pipeline orchestrator tests: idempotency, scrape-failure path, official
contents shortcut, feed filtering, and the verbatim source_line gate."""

from datetime import datetime
from unittest import mock

from app import models
from app.config import get_settings
from app.pipeline import orchestrator
from app.pipeline.summarizer import NullSummarizer
from app.schemas import ChangeType, ExtractedChange, PatchSummary
from app.upstream import steam_news
from app.upstream.forum_scraper import ScrapeError
from app.upstream.steam_news import NewsItem

NOTES = (
    "Heroes\n"
    "Warden: Base movement speed reduced from 6.5 to 6\n"
    "Yamato: Power Slash collision radius reduced by 8%\n"
)


def _item(gid: str = "1", contents: str = "", feedname: str = "steam_community_announcements") -> NewsItem:
    return NewsItem(
        gid=gid,
        title="Deadlock - Gameplay Update - 01-01-2026",
        url=f"https://forums.playdeadlock.com/threads/{gid}",
        contents=contents,
        date=datetime(2026, 1, 1),
        feedname=feedname,
    )


def _run(db, summarizer=None, items=None):
    settings = get_settings()
    with mock.patch(
        "app.pipeline.orchestrator.steam_news.fetch_recent_news",
        return_value=items if items is not None else [_item()],
    ), mock.patch(
        "app.pipeline.orchestrator.forum_scraper.fetch_patch_notes",
        return_value=NOTES,
    ):
        return orchestrator.run_pipeline(db, settings, summarizer or NullSummarizer())


def test_pipeline_end_to_end_and_idempotent(db_session):
    first = _run(db_session)
    assert first.detected_new == 1
    assert first.enriched == 1
    assert first.extracted == 1
    assert first.needs_review == 0

    patch = db_session.query(models.Patch).one()
    assert patch.status == "extracted"
    assert patch.changes, "NullSummarizer should extract change-looking lines"
    for ch in patch.changes:
        assert ch.source_line in patch.raw_text  # verbatim gate held

    second = _run(db_session)  # re-run: everything already processed
    assert second.detected_new == 0
    assert second.enriched == 0
    assert second.extracted == 0
    assert db_session.query(models.Patch).count() == 1


def test_official_contents_skip_scraping(db_session):
    """Long official BBCode contents are used directly — no forum request."""
    bbcode = "[b]Heroes[/b]\n[list]\n[*]Warden: Base movement speed reduced from 6.5 to 6\n" + "padding " * 100
    with mock.patch(
        "app.pipeline.orchestrator.forum_scraper.fetch_patch_notes"
    ) as scrape:
        stats = _run(db_session, items=[_item(contents=bbcode)])
    assert not scrape.called, "full official contents should not trigger scraping"
    assert stats.extracted == 1
    patch = db_session.query(models.Patch).one()
    assert "[b]" not in patch.raw_text  # BBCode was stripped
    assert "Warden: Base movement speed reduced" in patch.raw_text


def test_non_official_feeds_are_not_patch_candidates(db_session):
    external = _item(gid="ext1", feedname="PCGamesN")
    stats = _run(db_session, items=[external])
    assert stats.detected_new == 0
    assert db_session.query(models.Patch).count() == 0


def test_is_patch_candidate_requires_official_feed():
    official = _item()
    assert steam_news.is_patch_candidate(official)
    assert not steam_news.is_patch_candidate(_item(feedname="PC Gamer"))
    assert not steam_news.is_patch_candidate(
        NewsItem(gid="x", title="Deadlock cosplay contest", url="", contents="", date=datetime(2026, 1, 1))
    )


def test_scrape_failure_goes_to_needs_review(db_session):
    settings = get_settings()
    with mock.patch(
        "app.pipeline.orchestrator.steam_news.fetch_recent_news",
        return_value=[_item("2")],
    ), mock.patch(
        "app.pipeline.orchestrator.forum_scraper.fetch_patch_notes",
        side_effect=ScrapeError("markup changed"),
    ):
        stats = orchestrator.run_pipeline(db_session, settings, NullSummarizer())

    assert stats.needs_review == 1
    patch = db_session.query(models.Patch).one()
    assert patch.status == "needs_review"
    assert patch.changes == []


def test_hallucinated_source_lines_are_rejected(db_session):
    """A summarizer that invents source_lines must trip the quality gate."""

    class HallucinatingSummarizer:
        llm_generated = True

        def summarize(self, title, raw_text):
            return PatchSummary(
                title=title,
                summary="fake",
                changes=[
                    ExtractedChange(
                        entity_type="hero",
                        entity_name="Warden",
                        change_type=ChangeType.NERF,
                        description="invented change",
                        source_line="THIS LINE IS NOT IN THE NOTES",
                    )
                ],
            )

    stats = _run(db_session, summarizer=HallucinatingSummarizer())
    assert stats.extracted == 0
    assert stats.needs_review == 1
    patch = db_session.query(models.Patch).one()
    assert patch.status == "needs_review"
    assert patch.changes == []
