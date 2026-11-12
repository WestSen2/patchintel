"""Verdict math: known inputs -> known verdicts (M2 acceptance criterion)."""

from app.pipeline.verdicts import (
    MIN_MATCHES,
    combined_half_width,
    compute_verdict,
    wilson_half_width,
)


def test_wilson_half_width_shrinks_with_sample():
    wide = wilson_half_width(260, 500)
    narrow = wilson_half_width(5200, 10000)
    assert wide is not None and narrow is not None
    assert wide > narrow > 0


def test_wilson_handles_zero_matches():
    assert wilson_half_width(0, 0) is None


def test_nerf_that_worked():
    # 52% -> 48% over 2000 matches each: delta -4% exceeds combined CI (~3.1%)
    out = compute_verdict("nerf", 1040, 2000, 960, 2000)
    assert out.verdict == "worked"
    assert out.expected_direction == "down"
    assert out.delta_win_rate is not None and out.delta_win_rate < 0


def test_nerf_that_backfired():
    # win rate ROSE after a nerf, beyond noise
    out = compute_verdict("nerf", 960, 2000, 1040, 2000)
    assert out.verdict == "backfired"


def test_buff_that_worked():
    out = compute_verdict("buff", 960, 2000, 1040, 2000)
    assert out.verdict == "worked"


def test_small_delta_is_unclear():
    # 50.5% -> 50.0%: real direction but far inside the confidence interval
    out = compute_verdict("nerf", 1010, 2000, 1000, 2000)
    assert out.verdict == "unclear"


def test_insufficient_data_floor():
    out = compute_verdict("nerf", 60, 100, 40, 100)  # huge delta, tiny sample
    assert out.verdict == "insufficient_data"
    assert str(MIN_MATCHES) in out.reason


def test_bugfix_is_excluded():
    out = compute_verdict("bugfix", 1040, 2000, 960, 2000)
    assert out.verdict == "excluded"


def test_rework_with_big_move_is_shifted():
    out = compute_verdict("rework", 960, 2000, 1100, 2000)
    assert out.verdict == "shifted"


def test_rework_without_move_is_no_effect():
    out = compute_verdict("rework", 1005, 2000, 1000, 2000)
    assert out.verdict == "no_effect"


def test_combined_half_width_widens_with_uncertainty():
    tight = combined_half_width(5200, 10000, 4800, 10000)
    wide = combined_half_width(520, 1000, 480, 1000)
    assert tight is not None and wide is not None
    assert wide > tight
