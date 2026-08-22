from __future__ import annotations

import pytest

from lottolab.research.regime_changepoint_cusum import (
    cusum_path,
    max_abs_cusum,
    trimmed_split_points,
)


def test_cusum_path_hand_computed() -> None:
    # values - mean = [1, -1, 2, -2] -> cumulative = [1, 0, 2, 0]
    path = cusum_path([3.0, 1.0, 4.0, 0.0], null_mean=2.0)
    assert path == (1.0, 0.0, 2.0, 0.0)


def test_cusum_path_rejects_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        cusum_path([], null_mean=0.0)


def test_trimmed_split_points_known_boundaries() -> None:
    # n=2138, 15% trim -> ceil(320.7)=321 on each side.
    points = trimmed_split_points(2138, 15, 100)
    assert points[0] == 321
    assert points[-1] == 2138 - 321
    assert len(points) == points[-1] - points[0] + 1


def test_trimmed_split_points_rejects_invalid_fraction() -> None:
    with pytest.raises(ValueError, match="trim fraction"):
        trimmed_split_points(100, 100, 100)
    with pytest.raises(ValueError, match="trim fraction"):
        trimmed_split_points(100, -1, 100)


def test_trimmed_split_points_rejects_fraction_leaving_nothing() -> None:
    # n=2, 60% trim -> low=ceil(1.2)=2, high=min(2, 2-2)=0, low>high.
    with pytest.raises(ValueError, match="no eligible split points"):
        trimmed_split_points(2, 60, 100)


def test_max_abs_cusum_zero_when_sequence_equals_null_mean_everywhere() -> None:
    result = max_abs_cusum(
        [5.0] * 200, null_mean=5.0, trim_fraction_numerator=10, trim_fraction_denominator=100
    )
    assert result.statistic == 0.0


def test_max_abs_cusum_detects_a_classic_tent_shaped_break() -> None:
    # Textbook CUSUM case: deviation -1 for the first half, +1 for the
    # second half, null_mean=0. The path is a "tent" that peaks exactly at
    # the true break (t=1000) and returns to 0 by the end -- this is the
    # standard worked example demonstrating CUSUM localizes the break, not
    # just detects "something changed somewhere."
    n_half = 1000
    values = [-1.0] * n_half + [1.0] * n_half
    result = max_abs_cusum(
        values, null_mean=0.0, trim_fraction_numerator=10, trim_fraction_denominator=100
    )
    assert result.statistic == pytest.approx(float(n_half))
    assert result.argmax_split_point == n_half


def test_max_abs_cusum_is_much_larger_with_a_break_than_without() -> None:
    n_half = 500
    with_break = max_abs_cusum(
        [-1.0] * n_half + [1.0] * n_half,
        null_mean=0.0,
        trim_fraction_numerator=15,
        trim_fraction_denominator=100,
    )
    without_break = max_abs_cusum(
        [0.0] * (2 * n_half),
        null_mean=0.0,
        trim_fraction_numerator=15,
        trim_fraction_denominator=100,
    )
    assert with_break.statistic > without_break.statistic
    assert without_break.statistic == 0.0


def test_max_abs_cusum_respects_the_trim_boundary() -> None:
    # An extreme break placed right at the very start (t=1) must not be
    # picked if it falls outside the trimmed candidate range.
    n = 200
    values = [1000.0] + [0.0] * (n - 1)  # huge deviation only at t=1
    result = max_abs_cusum(
        values, null_mean=0.0, trim_fraction_numerator=15, trim_fraction_denominator=100
    )
    low = trimmed_split_points(n, 15, 100)[0]
    assert result.argmax_split_point >= low
    assert result.statistic == pytest.approx(1000.0)  # the deviation persists in the cumsum
