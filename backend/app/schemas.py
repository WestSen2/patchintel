"""Pydantic contracts — LLM extraction contract + API response models."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- LLM contract

class ChangeType(str, Enum):
    BUFF = "buff"
    NERF = "nerf"
    REWORK = "rework"
    ADJUSTMENT = "adjustment"
    BUGFIX = "bugfix"


class NumberChange(BaseModel):
    """A numeric change ONLY when both values literally appear in the notes."""

    stat: str
    old: str
    new: str
    unit: str = ""


class ExtractedChange(BaseModel):
    entity_type: Literal["hero", "item", "system", "map", "unknown"]
    entity_name: str
    change_type: ChangeType
    description: str = Field(description="One sentence, plain language")
    numbers: list[NumberChange] = Field(default_factory=list)
    source_line: str = Field(
        description="Verbatim line copied from the raw patch notes"
    )


class PatchSummary(BaseModel):
    title: str
    summary: str = Field(description="3-5 sentences, casual-player readable")
    changes: list[ExtractedChange]


# ---------------------------------------------------------------- API responses

class ChangeOut(BaseModel):
    id: int
    entity_type: str
    entity_name: str
    entity_id: int | None
    change_type: str
    description: str
    numbers: list[dict]
    source_line: str

    model_config = {"from_attributes": True}


class PatchListOut(BaseModel):
    id: int
    title: str
    patch_date: datetime | None
    status: str
    summary: str
    change_count: int


class PatchDetailOut(BaseModel):
    id: int
    title: str
    patch_date: datetime | None
    source_url: str
    status: str
    summary: str
    llm_generated: bool
    changes: list[ChangeOut]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- M2: stats

class SnapshotOut(BaseModel):
    patch_id: int | None
    window: str
    window_start: datetime
    window_end: datetime
    truncated: bool
    win_rate: float
    pick_rate: float | None
    matches: int

    model_config = {"from_attributes": True}


class VerdictOut(BaseModel):
    id: int
    patch_id: int
    change_id: int | None
    entity_type: str
    entity_id: int
    expected_direction: str
    pre_win_rate: float | None
    post_win_rate: float | None
    delta_win_rate: float | None
    pre_pick_rate: float | None
    post_pick_rate: float | None
    pre_matches: int
    post_matches: int
    ci_half_width: float | None
    verdict: str
    reason: str

    model_config = {"from_attributes": True}


class PatchImpactOut(BaseModel):
    patch_id: int
    title: str
    patch_date: datetime | None
    verdicts: list[VerdictOut]


class HeroOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class HeroDetailOut(BaseModel):
    id: int
    name: str
    snapshots: list[SnapshotOut]
    changes: list[ChangeOut]


class ItemOut(BaseModel):
    id: int
    name: str
    tier: int | None
    cost: int | None

    model_config = {"from_attributes": True}


class TimingOut(BaseModel):
    patch_id: int | None
    window: str
    avg_buy_time_s: float | None
    avg_buy_time_relative: float | None
    win_rate_early: float | None
    win_rate_mid: float | None
    win_rate_late: float | None
    matches: int

    model_config = {"from_attributes": True}


class ItemDetailOut(BaseModel):
    id: int
    name: str
    tier: int | None
    cost: int | None
    snapshots: list[SnapshotOut]
    changes: list[ChangeOut]
    timing: list[TimingOut]
