"""Golden-set LLM extraction gate (design review §4).

Hand-labeled from the REAL 2024-08-29 Deadlock patch notes. This test only
runs when OPENAI_API_KEY is configured — it measures LLM extraction quality,
so it is meaningless (and would fail) against the NullSummarizer.

Run explicitly with:
    OPENAI_API_KEY=... pytest tests/test_golden_extraction.py -v

Gate: >= 90% of expected change lines must appear verbatim among the
extracted changes' source_lines.
"""

import json
import os
from pathlib import Path

import pytest

from app.config import get_settings
from app.pipeline.summarizer import OpenAISummarizer

GOLDEN_DIR = Path(__file__).parent / "golden"
RECALL_GATE = 0.9

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="golden extraction gate requires a real OPENAI_API_KEY",
)


def _golden_files():
    return sorted(GOLDEN_DIR.glob("*.json"))


@pytest.mark.parametrize("golden_path", _golden_files(), ids=lambda p: p.stem)
def test_golden_extraction_recall(golden_path):
    golden = json.loads(golden_path.read_text())
    summarizer = OpenAISummarizer(get_settings())

    result = summarizer.summarize(golden["title"], golden["raw_text"])
    extracted_lines = [c.source_line for c in result.changes]

    hits = sum(
        1
        for expected in golden["expected_source_lines"]
        if any(expected in line for line in extracted_lines)
    )
    recall = hits / len(golden["expected_source_lines"])
    assert recall >= RECALL_GATE, (
        f"extraction recall {recall:.0%} below gate: missed "
        f"{[e for e in golden['expected_source_lines'] if not any(e in l for l in extracted_lines)]}"
    )
