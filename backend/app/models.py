"""SQLAlchemy models — schema v1 (M1: patches + changes + entity tables).

Design notes:
- Patch.source_url is unique -> pipeline re-runs are idempotent no-ops.
- Change.source_line stores the VERBATIM patch-note line the change was
  extracted from. This is the anti-hallucination anchor (see
  docs/m1-design-review.md section 4).
- Hero/Item use the game's numeric IDs as PKs; never join on display names.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


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
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    changes: Mapped[list["Change"]] = relationship(
        back_populates="patch", cascade="all, delete-orphan", order_by="Change.id"
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
