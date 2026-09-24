"""Focused checks for the outside-native single-crossover augmentation study."""

from __future__ import annotations

import pytest

from lottolab.research.b649_outside_native_single_crossover_augmentation import (
    generate_single_crossover_children,
)


def test_crossover_known_answer_two_baseline_one_outside() -> None:
    baseline = [(1, 2, 3), (4, 5, 6)]
    outside = [(3, 7, 8)]
    children = generate_single_crossover_children(baseline, outside, pool_size=13, draw_size=3)
    expected = (
        (2, 3, 7),
        (2, 3, 8),
        (1, 3, 7),
        (1, 3, 8),
        (3, 5, 6),
        (5, 6, 7),
        (5, 6, 8),
        (3, 4, 6),
        (4, 6, 7),
        (4, 6, 8),
        (3, 4, 5),
        (4, 5, 7),
        (4, 5, 8),
    )
    assert children == expected


def test_no_outside_native_produces_no_children() -> None:
    baseline = [(1, 2, 3), (4, 5, 6)]
    assert generate_single_crossover_children(baseline, [], pool_size=13, draw_size=3) == ()


def test_disjoint_baseline_and_outside_produce_full_cartesian_swap_set() -> None:
    baseline = [(1, 2, 3)]
    outside = [(4, 5, 6)]
    children = generate_single_crossover_children(baseline, outside, pool_size=13, draw_size=3)
    assert len(children) == 3 * 3
    assert len(set(children)) == len(children)
    for child in children:
        assert len(child) == 3 == len(set(child))
        assert set(child) <= {1, 2, 3, 4, 5, 6}
        assert set(child) != {1, 2, 3}
        assert set(child) != {4, 5, 6}


def test_identical_baseline_and_outside_ticket_yields_no_children_for_that_pair() -> None:
    baseline = [(1, 2, 3), (4, 5, 6)]
    outside = [(1, 2, 3)]
    children = generate_single_crossover_children(baseline, outside, pool_size=13, draw_size=3)
    # (1,2,3) vs (1,2,3): s - o and o - s are both empty, so that pair contributes nothing;
    # (4,5,6) vs (1,2,3) is fully disjoint and still contributes its full 3*3 swap set.
    assert len(children) == 9
    assert all(set(child) <= {1, 2, 3, 4, 5, 6} for child in children)


def test_duplicate_children_across_pairs_are_deduplicated() -> None:
    # Both outside tickets share the swap-in number 4 with baseline's removable {1, 2},
    # so (2, 3, 4) and (1, 3, 4) are each produced twice, by different (s, o) pairs.
    baseline = [(1, 2, 3)]
    outside = [(3, 4, 5), (3, 4, 6)]
    raw_pair_totals = 4 + 4
    children = generate_single_crossover_children(baseline, outside, pool_size=13, draw_size=3)
    assert len(children) == len(set(children)) == 6 < raw_pair_totals
    assert (2, 3, 4) in children and children.count((2, 3, 4)) == 1
    assert (1, 3, 4) in children and children.count((1, 3, 4)) == 1
    assert set(children) == {
        (2, 3, 4),
        (2, 3, 5),
        (1, 3, 4),
        (1, 3, 5),
        (2, 3, 6),
        (1, 3, 6),
    }


def test_generation_is_deterministic() -> None:
    baseline = [(2, 4, 9), (1, 3, 5)]
    outside = [(6, 7, 8), (2, 5, 11)]
    first = generate_single_crossover_children(baseline, outside, pool_size=13, draw_size=3)
    second = generate_single_crossover_children(baseline, outside, pool_size=13, draw_size=3)
    assert first == second


def test_full_scale_six_number_children_stay_in_range() -> None:
    baseline = [
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
    ]
    outside = [(1, 13, 20, 30, 40, 49), (6, 14, 21, 31, 41, 48)]
    children = generate_single_crossover_children(baseline, outside)
    assert children
    for child in children:
        assert len(child) == 6 == len(set(child))
        assert all(1 <= number <= 49 for number in child)
        assert list(child) == sorted(child)


def test_illegal_ticket_rejected() -> None:
    with pytest.raises(ValueError, match="illegal ticket"):
        generate_single_crossover_children([(1, 2, 3)], [(1, 1, 2)], pool_size=13, draw_size=3)
    with pytest.raises(ValueError, match="illegal ticket"):
        generate_single_crossover_children([(1, 2)], [(1, 2, 3)], pool_size=13, draw_size=3)
