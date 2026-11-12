"""LLM patch summarization behind a provider-agnostic protocol.

Three implementations:
- OpenAISummarizer: strict JSON output -> PatchSummary, one retry with the
  validation error fed back to the model (design review section 4).
- NullSummarizer:  heuristic line splitter so the whole pipeline runs with NO
  LLM key. Output is flagged llm_generated=False.
- get_summarizer(): picks based on settings.

The summarizer never decides what is "true": every ExtractedChange carries a
verbatim source_line which the orchestrator re-validates against raw_text.
"""

from __future__ import annotations

import re
from typing import Protocol

from ..config import Settings
from ..schemas import (
    ChangeType,
    ExtractedChange,
    PatchSummary,
)

_SYSTEM_PROMPT = """You are a patch-notes parser for the game Deadlock.
Return STRICT JSON matching this schema:
{
  "title": string,
  "summary": string,            // 3-5 sentences, casual-player readable
  "changes": [
    {
      "entity_type": "hero"|"item"|"system"|"map"|"unknown",
      "entity_name": string,    // exact name as written in the notes
      "change_type": "buff"|"nerf"|"rework"|"adjustment"|"bugfix",
      "description": string,    // one sentence, plain language
      "numbers": [{"stat": string, "old": string, "new": string, "unit": string}],
      "source_line": string     // VERBATIM line copied from the notes
    }
  ]
}
Rules:
- source_line must be copied EXACTLY from the notes. Never paraphrase it.
- numbers only when old AND new values literally appear in the text.
- If an entity name is unclear, use entity_type "unknown". Never guess.
- buff/nerf = clearly stronger/weaker; adjustment = unclear direction;
  rework = ability or item fundamentally redesigned; bugfix = fix only.
"""


class PatchSummarizer(Protocol):
    llm_generated: bool

    def summarize(self, title: str, raw_text: str) -> PatchSummary: ...


class OpenAISummarizer:
    llm_generated = True

    def __init__(self, settings: Settings):
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def summarize(self, title: str, raw_text: str) -> PatchSummary:
        user = f"PATCH TITLE: {title}\n\nPATCH NOTES:\n{raw_text[:24000]}"
        result = self._complete(user)
        try:
            return PatchSummary.model_validate_json(result)
        except Exception as first_error:
            # One retry, feeding the validation error back (design review §4)
            retry_user = (
                f"{user}\n\nYour previous output failed validation: {first_error}. "
                "Return corrected strict JSON only."
            )
            return PatchSummary.model_validate_json(self._complete(retry_user))

    def _complete(self, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return resp.choices[0].message.content or "{}"


class NullSummarizer:
    """No LLM key: split notes into lines, keep change-looking ones.

    Quality is intentionally low — this exists so the pipeline, DB, API and
    UI are all exercisable before an OpenAI key is configured.
    """

    llm_generated = False

    _CHANGE_HINT = re.compile(
        r"(increased|reduced|decreased|buff|nerf|fixed|rework|now|from .* to )",
        re.IGNORECASE,
    )

    def summarize(self, title: str, raw_text: str) -> PatchSummary:
        lines = [ln.strip("-•* ") for ln in raw_text.splitlines()]
        changes = []
        for ln in lines:
            if 20 < len(ln) < 400 and self._CHANGE_HINT.search(ln):
                changes.append(
                    ExtractedChange(
                        entity_type="unknown",
                        entity_name="unknown",
                        change_type=ChangeType.ADJUSTMENT,
                        description=ln,
                        numbers=[],
                        source_line=ln,
                    )
                )
        return PatchSummary(
            title=title,
            summary=(
                "Heuristic summary (no LLM configured). "
                f"{len(changes)} potential change lines detected."
            ),
            changes=changes[:200],
        )


def get_summarizer(settings: Settings) -> PatchSummarizer:
    if settings.openai_api_key:
        return OpenAISummarizer(settings)
    return NullSummarizer()
