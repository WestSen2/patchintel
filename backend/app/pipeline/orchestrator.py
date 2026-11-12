"""Pipeline orchestrator: detect -> enrich -> extract -> resolve.

Idempotent by design (design review §3):
- detect skips steam_gids already in the DB (unique constraint)
- enrich only touches status='detected'
- extract only touches status='fetched'
Re-running the whole pipeline is therefore always a safe no-op.

Quality gates:
- scrape failure -> status='needs_review' (never store garbage)
- extracted change with a source_line that is NOT verbatim in raw_text
  -> dropped and counted; >20% dropped -> status='needs_review'
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .. import models
from ..config import Settings
from ..upstream import deadlock_assets, forum_scraper, steam_news
from .entity_resolver import EntityResolver
from .summarizer import PatchSummarizer

MAX_DROPPED_RATIO = 0.2


@dataclass
class PipelineStats:
    detected_new: int = 0
    enriched: int = 0
    extracted: int = 0
    needs_review: int = 0
    dropped_changes: int = 0
    errors: list[str] = field(default_factory=list)


def seed_entities(db: Session, settings: Settings) -> tuple[int, int]:
    """Refresh hero/item tables from the community API (run at most daily)."""
    heroes = deadlock_assets.fetch_heroes(settings)
    items = deadlock_assets.fetch_items(settings)
    for h in heroes:
        db.merge(models.Hero(id=h["id"], name=h["name"]))
    for it in items:
        db.merge(
            models.Item(id=it["id"], name=it["name"], tier=it["tier"], cost=it["cost"])
        )
    db.commit()
    return len(heroes), len(items)


def detect_new_patches(db: Session, settings: Settings, stats: PipelineStats) -> None:
    known = {g for (g,) in db.query(models.Patch.steam_gid).all()}
    for item in steam_news.fetch_recent_news(settings):
        if not steam_news.is_patch_candidate(item) or item.gid in known:
            continue
        db.add(
            models.Patch(
                steam_gid=item.gid,
                title=item.title,
                patch_date=item.date,
                source_url=item.url,
                raw_text=item.contents or "",
                status="detected",
            )
        )
        stats.detected_new += 1
    db.commit()


def enrich_patches(db: Session, stats: PipelineStats) -> None:
    pending = db.query(models.Patch).filter_by(status="detected").all()
    for patch in pending:
        try:
            # Official announcements usually carry full BBCode notes in the
            # news payload itself — prefer that over scraping (faster + kinder).
            if len(patch.raw_text) >= forum_scraper.MIN_NOTES_LENGTH:
                patch.raw_text = steam_news.strip_bbcode(patch.raw_text)
            else:
                patch.raw_text = forum_scraper.fetch_patch_notes(patch.source_url)
            patch.status = "fetched"
            stats.enriched += 1
        except Exception as exc:  # ScrapeError or UpstreamError
            patch.status = "needs_review"
            stats.needs_review += 1
            stats.errors.append(f"enrich {patch.steam_gid}: {exc}")
    db.commit()


def extract_changes(
    db: Session, summarizer: PatchSummarizer, stats: PipelineStats
) -> None:
    resolver = EntityResolver(db)
    pending = db.query(models.Patch).filter_by(status="fetched").all()

    for patch in pending:
        try:
            result = summarizer.summarize(patch.title, patch.raw_text)
        except Exception as exc:
            patch.status = "needs_review"
            stats.needs_review += 1
            stats.errors.append(f"extract {patch.steam_gid}: {exc}")
            db.commit()
            continue

        # Anti-hallucination gate: source_line must be verbatim in raw_text
        valid, dropped = [], 0
        for ch in result.changes:
            if ch.source_line and ch.source_line in patch.raw_text:
                valid.append(ch)
            else:
                dropped += 1
        stats.dropped_changes += dropped

        if result.changes and dropped / len(result.changes) > MAX_DROPPED_RATIO:
            patch.status = "needs_review"
            stats.needs_review += 1
            stats.errors.append(
                f"extract {patch.steam_gid}: {dropped}/{len(result.changes)} "
                "changes failed source_line validation"
            )
            db.commit()
            continue

        patch.changes.clear()
        for ch in valid:
            patch.changes.append(
                models.Change(
                    entity_type=ch.entity_type,
                    entity_name=ch.entity_name,
                    entity_id=resolver.resolve(ch.entity_type, ch.entity_name),
                    change_type=ch.change_type.value,
                    description=ch.description,
                    numbers=[n.model_dump() for n in ch.numbers],
                    source_line=ch.source_line,
                )
            )
        patch.summary = result.summary
        patch.llm_generated = summarizer.llm_generated
        patch.status = "extracted"
        stats.extracted += 1
        db.commit()


def run_pipeline(
    db: Session, settings: Settings, summarizer: PatchSummarizer
) -> PipelineStats:
    stats = PipelineStats()
    detect_new_patches(db, settings, stats)
    enrich_patches(db, stats)
    extract_changes(db, summarizer, stats)
    return stats
