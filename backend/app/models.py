"""SQLAlchemy models — schema v2 (M1 tables + M2 snapshots/verdicts).

Design notes:
- Patch.source_url is unique -> pipeline re-runs are idempotent no-ops.
- Change.source_line stores the VERBATIM patch-note line the change was
  extracted from. This is the anti-hallucination anchor.
- Hero/Item use the game's numeric IDs as PKs; never join on display names.
- Verdicts are STORED (not computed on read) — the row doubles as an audit
  trail: the methodology page can show the exact inputs behind every badge.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ M1 tables

class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[int] = mapped_column(primary_key=True)
    steam_gid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    patch_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    # detected -> fetched -> extracted | needs_review
    status: Mapped[str] = mapped_column(String(32), default="detected", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    llm_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    changes: Mapped[list["Change"]] = relationship(
        back_populates="patch", cascade="all, delete-orphan", order_by="Change.id"
    )
    verdicts: Mapped[list["Verdict"]] = relationship(
        back_populates="patch", cascade="all, delete-orphan", order_by="Verdict.id"
    )


class Change(Base):
    __tablename__ = "changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    patch_id: Mapped[int] = mapped_column(ForeignKey("patches.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(16))  # hero|item|system|map|unknown
    entity_name: Mapped[str] = mapped_column(String(200))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_type: Mapped[str] = mapped_column(String(16))  # buff|nerf|rework|adjustment|bugfix
    description: Mapped[str] = mapped_column(Text)
    numbers: Mapped[list] = mapped_column(JSON, default=list)
    source_line: Mapped[str] = mapped_column(Text)

    patch: Mapped[Patch] = relationship(back_populates="changes")


class Hero(Base):
    __tablename__ = "heroes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # game hero_id
    name: Mapped[str] = mapped_column(String(200), index=True)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # game item_id
    name: Mapped[str] = mapped_column(String(200), index=True)
    tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ------------------------------------------------------------------ M2 tables

class StatSnapshot(Base):
    """Aggregate stats for one entity over one patch window (or 'current')."""

    __tablename__ = "stat_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(8), index=True)  # hero|item
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    patch_id: Mapped[int | None] = mapped_column(
        ForeignKey("patches.id"), nullable=True, index=True
    )
    window: Mapped[str] = mapped_column(String(8))  # pre|post|current
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    win_rate: Mapped[float] = mapped_column(Float)
    pick_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    matches: Mapped[int] = mapped_column(Integer)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # kills/damage/networth etc.
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Verdict(Base):
    """The headline artifact: did one entity's change do what it was meant to?"""

    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    patch_id: Mapped[int] = mapped_column(ForeignKey("patches.id"), index=True)
    change_id: Mapped[int | None] = mapped_column(
        ForeignKey("changes.id"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(8))
    entity_id: Mapped[int] = mapped_column(Integer)
    expected_direction: Mapped[str] = mapped_column(String(8))  # down|up|none
    pre_win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_pick_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_pick_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_matches: Mapped[int] = mapped_column(Integer, default=0)
    post_matches: Mapped[int] = mapped_column(Integer, default=0)
    ci_half_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    # worked|backfired|unclear|shifted|no_effect|excluded|insufficient_data
    verdict: Mapped[str] = mapped_column(String(20), index=True)
    reason: Mapped[str] = mapped_column(String(300), default="")
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patch: Mapped[Patch] = relationship(back_populates="verdicts")


class ItemTimingSnapshot(Base):
    """Item purchase-timing analytics per patch window (build-order explorer)."""

    __tablename__ = "item_timing_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    patch_id: Mapped[int | None] = mapped_column(
        ForeignKey("patches.id"), nullable=True, index=True
    )
    window: Mapped[str] = mapped_column(String(8))  # pre|post|current
    avg_buy_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_buy_time_relative: Mapped[float | None] = mapped_column(Float, nullable=True)
    # win rates when bought in each third of the game (bought_at buckets)
    win_rate_early: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate_mid: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate_late: Mapped[float | None] = mapped_column(Float, nullable=True)
    matches: Mapped[int] = mapped_column(Integer, default=0)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# ------------------------------------------------------------------ M3 tables

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    steam_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    avatar_url: Mapped[str] = mapped_column(String(1000), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    matches: Mapped[list["UserMatch"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="UserMatch.played_at"
    )
    sessions: Mapped[list["PlaySession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="PlaySession.started_at"
    )


class PlaySession(Base):
    """A run of consecutive games; a gap > 45 min starts a new session."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime)
    game_count: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="sessions")
    matches: Mapped[list["UserMatch"]] = relationship(
        back_populates="session", order_by="UserMatch.played_at"
    )


class UserMatch(Base):
    __tablename__ = "user_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    match_id: Mapped[int] = mapped_column(Integer, index=True)
    played_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_s: Mapped[int] = mapped_column(Integer, default=0)
    hero_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(8), default="")  # win|loss
    kills: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    net_worth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_json: Mapped[list] = mapped_column(JSON, default=list)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id"), nullable=True, index=True
    )

    user: Mapped["User"] = relationship(back_populates="matches")
    session: Mapped["PlaySession | None"] = relationship(back_populates="matches")

    # one row per user per match — sync re-runs are no-ops
    __table_args__ = (UniqueConstraint("user_id", "match_id"),)
