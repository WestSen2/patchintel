"""Verdict math — the credibility engine (M2 design review §3).

Pure functions, fully unit-tested. Given pre/post window win+match counts
for one entity, decide whether a balance change did what it was meant to.

Rules:
- Wilson score 95% CI on both win rates; delta must exceed the combined
  half-width to mean anything.
- HARD FLOOR: < MIN_MATCHES in either window -> 'insufficient_data'
  (never guess from tiny samples).
- nerf expects win rate DOWN, buff expects UP.
  delta in expected direction beyond noise -> 'worked'; opposite -> 'backfired'.
- rework/adjustment have no expected direction:
  beyond noise -> 'shifted', within noise -> 'no_effect'.
- bugfix -> 'excluded' (not a balance change).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MIN_MATCHES = 500
Z = 1.96  # 95% confidence

EXPECTED_DIRECTION = {
    "nerf": "down",
    "buff": "up",
    "rework": "none",
    "adjustment": "none",
    "bugfix": "none",
}


@dataclass(frozen=True)
class VerdictOutcome:
    verdict: str  # worked|backfired|unclear|shifted|no_effect|excluded|insufficient_data
    expected_direction: str
    delta_win_rate: float | None
    ci_half_width: float | None
    reason: str


def wilson_half_width(wins: int, matches: int) -> float | None:
    """Half-width of the Wilson score interval for a win rate."""
    if matches <= 0:
        return None
    p = wins / matches
    denom = 1 + Z * Z / matches
    return Z * math.sqrt(p * (1 - p) / matches + Z * Z / (4 * matches * matches)) / denom


def combined_half_width(
    pre_wins: int, pre_matches: int, post_wins: int, post_matches: int
) -> float | None:
    """Approximate CI half-width for the DIFFERENCE of two win rates."""
    h1 = wilson_half_width(pre_wins, pre_matches)
    h2 = wilson_half_width(post_wins, post_matches)
    if h1 is None or h2 is None:
        return None
    return math.sqrt(h1 * h1 + h2 * h2)


def compute_verdict(
    change_type: str,
    pre_wins: int,
    pre_matches: int,
    post_wins: int,
    post_matches: int,
) -> VerdictOutcome:
    expected = EXPECTED_DIRECTION.get(change_type, "none")

    if change_type == "bugfix":
        return VerdictOutcome("excluded", expected, None, None, "bugfix, not a balance change")

    if pre_matches < MIN_MATCHES or post_matches < MIN_MATCHES:
        return VerdictOutcome(
            "insufficient_data",
            expected,
            None,
            None,
            f"need >= {MIN_MATCHES} matches per window "
            f"(pre={pre_matches}, post={post_matches})",
        )

    pre_wr = pre_wins / pre_matches
    post_wr = post_wins / post_matches
    delta = post_wr - pre_wr
    ci = combined_half_width(pre_wins, pre_matches, post_wins, post_matches)
    assert ci is not None  # guaranteed by the matches floor above

    beyond_noise = abs(delta) > ci

    if expected == "none":
        if beyond_noise:
            direction = "up" if delta > 0 else "down"
            return VerdictOutcome("shifted", expected, delta, ci, f"win rate moved {direction} beyond noise")
        return VerdictOutcome("no_effect", expected, delta, ci, "no measurable win-rate effect")

    if not beyond_noise:
        return VerdictOutcome("unclear", expected, delta, ci, "delta within noise / confidence interval")

    moved_expected = (expected == "down" and delta < 0) or (expected == "up" and delta > 0)
    if moved_expected:
        return VerdictOutcome("worked", expected, delta, ci, f"{change_type} moved win rate the expected way")
    return VerdictOutcome("backfired", expected, delta, ci, f"{change_type} moved win rate the WRONG way")
