"""Pydantic contracts.

Two families:
- LLM extraction contract (PatchSummary / ExtractedChange) — the strict JSON
  the summarizer must produce. Validated in code; see pipeline/summarizer.py.
- API response models (PatchOut / ChangeOut) — what /api/patches returns.
"""

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
