from __future__ import annotations

import math
import random

import pytest

from lottolab.research import b649_eh10_permutation_entropy as eh10


def test_tie_key_is_deterministic_and_draw_id_sensitive() -> None:
    a = eh10.tie_key(100)
    b = eh10.tie_key(100)
    c = eh10.tie_key(101)
    assert a == b
    assert a != c
    assert len(a) == 32  # SHA-256 digest bytes


def test_tie_key_rejects_negative_draw_id() -> None:
    with pytest.raises(ValueError):
        eh10.tie_key(-1)


def test_ordinal_pattern_breaks_exact_ties_by_tie_key_not_position() -> None:
    keys_a = eh10.precompute_tie_keys((100, 5))
    keys_b = eh10.precompute_tie_keys((5, 100))
    pattern_a = eh10.ordinal_pattern((7, 7), keys_a, 0, 2)
    pattern_b = eh10.ordinal_pattern((7, 7), keys_b, 0, 2)
    # Same values, swapped draw IDs -> the tie resolution must follow the
    # hash key (which moved with the draw ID), not stay pinned to position.
    assert pattern_a != pattern_b


def test_ordinal_pattern_is_strict_ascending_rank_for_distinct_values() -> None:
    keys = eh10.precompute_tie_keys((1, 2, 3))
    # values are already ascending -> pattern is the identity order
    assert eh10.ordinal_pattern((10, 20, 30), keys, 0, 3) == (0, 1, 2)
    # values descending -> pattern is fully reversed
    assert eh10.ordinal_pattern((30, 20, 10), keys, 0, 3) == (2, 1, 0)


def test_all_ordinal_patterns_count_matches_factorial() -> None:
    assert len(eh10.all_ordinal_patterns(3)) == 6
    assert len(eh10.all_ordinal_patterns(4)) == 24
    assert len(eh10.all_ordinal_patterns(5)) == 120


@pytest.mark.parametrize("order", [3, 4, 5])
def test_strictly_monotonic_series_has_zero_entropy_everywhere(order: int) -> None:
    # Every unit-delay word in a strictly increasing (or decreasing) series
    # realizes the exact same one ordinal pattern -> single-pattern
    # occupancy -> entropy exactly 0 -> T_PE = 1 - 0 = 1, the strongest
    # possible low-entropy-deficit reading. This is the cleanest
    # hand-checkable ground truth for this statistic.
    n = 300
    values_up = tuple(range(1, n + 1))
    values_down = tuple(range(n, 0, -1))
    draw_ids = tuple(range(1, n + 1))

    for values in (values_up, values_down):
        result = eh10.rolling_permutation_entropy(values, draw_ids, order=order, window=124)
        assert result.min_hnorm == pytest.approx(0.0, abs=1e-12)
        assert result.statistic == pytest.approx(1.0, abs=1e-12)
        assert result.diagnostics_at_min.occupancy_fraction == pytest.approx(
            1 / math.factorial(order)
        )
        assert result.diagnostics_at_min.missing_pattern_count == math.factorial(order) - 1


def test_earliest_window_wins_on_an_exact_minimum_tie() -> None:
    # Build two windows that are guaranteed to produce identical Hnorm (both
    # strictly monotonic, hence both exactly 0) and confirm the earlier one
    # is reported, per the locked earliest-tie rule.
    n = 400
    values = tuple(range(1, n + 1))  # monotonic everywhere -> every window ties at Hnorm=0
    draw_ids = tuple(range(1, n + 1))
    result = eh10.rolling_permutation_entropy(values, draw_ids, order=3, window=124)
    assert result.min_window_start == 1  # the very first eligible window


def test_eligible_window_count_matches_n_minus_window_plus_one() -> None:
    n = 400
    values = tuple(range(1, n + 1))
    draw_ids = tuple(range(1, n + 1))
    result = eh10.rolling_permutation_entropy(values, draw_ids, order=3, window=124)
    assert result.eligible_window_count == n - 124 + 1


def test_order_5_window_124_has_exactly_120_words_per_window() -> None:
    # 124 - 5 + 1 = 120 = 5!, the locked geometry rationale from the
    # proposal (section 9): the smallest window with at least one word
    # slot per possible order-5 pattern.
    n = 400
    rng = random.Random(21)
    values = tuple(rng.randint(21, 279) for _ in range(n))
    draw_ids = tuple(range(1, n + 1))
    result = eh10.rolling_permutation_entropy(values, draw_ids, order=5, window=124)
    words_per_window = 124 - 5 + 1
    assert words_per_window == 120 == math.factorial(5)
    assert result.diagnostics_at_min.missing_pattern_count <= 120  # sane upper bound


def test_geometry_insufficient_when_series_shorter_than_window() -> None:
    values = tuple(range(1, 50))
    draw_ids = tuple(range(1, 50))
    with pytest.raises(eh10.GeometryInsufficientError):
        eh10.rolling_permutation_entropy(values, draw_ids, order=3, window=124)


def test_rejects_unsupported_order() -> None:
    values = tuple(range(1, 200))
    draw_ids = tuple(range(1, 200))
    with pytest.raises(ValueError):
        eh10.rolling_permutation_entropy(values, draw_ids, order=6, window=124)


def test_mismatched_values_and_draw_ids_length_is_rejected() -> None:
    with pytest.raises(ValueError):
        eh10.rolling_permutation_entropy((1, 2, 3), (1, 2), order=3, window=2)
