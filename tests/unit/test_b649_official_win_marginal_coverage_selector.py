"""Focused tests for the frozen B649 official-win marginal selector."""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.research.b649_official_win_marginal_coverage_selector import (
    FROZEN_K10_SPEC,
    generate_selection_draw_sample,
    select_official_win_marginal_coverage,
)


def test_frozen_selection_sample_is_reproducible_and_legal() -> None:
    first = generate_selection_draw_sample(sample_count=128, seed=91)
    second = generate_selection_draw_sample(sample_count=128, seed=91)

    assert np.array_equal(first, second)
    assert first.size == 128
    assert np.all(np.bitwise_count(first) == 6)
    assert np.all(first < 1 << 49)


def test_frozen_spec_declares_primary_k_and_sample_contract() -> None:
    assert FROZEN_K10_SPEC.selector_id == "B649_OFFICIAL_WIN_MARGINAL_COVERAGE_V1"
    assert FROZEN_K10_SPEC.primary_k == 10
    assert FROZEN_K10_SPEC.selection_draw_count == 65_536
    assert FROZEN_K10_SPEC.tie_break == "EARLIEST_CANDIDATE_POOL_POSITION"


def test_selector_uses_official_prize_marginal_and_preserves_pool_order() -> None:
    pool_size, draw_size, outright_matches = 9, 3, 2
    candidate_pool = (
        (1, 2, 3),
        (1, 2, 4),
        (4, 5, 6),
        (7, 8, 9),
    )
    original_pool = tuple(tuple(ticket) for ticket in candidate_pool)
    draws = all_main_draw_masks(pool_size, draw_size)

    selected = select_official_win_marginal_coverage(
        candidate_pool,
        2,
        selection_draws=draws,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )

    assert selected.selected_indices[0] == 0
    assert len(selected.portfolio) == 2
    assert len(set(selected.portfolio)) == 2
    assert tuple(tuple(ticket) for ticket in candidate_pool) == original_pool

    exact_gains: list[tuple[int, int]] = []
    current = evaluate_portfolio(
        [candidate_pool[0]],
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=draws,
    ).official_any_prize_outcome_count
    for index, ticket in enumerate(candidate_pool[1:], start=1):
        expanded = evaluate_portfolio(
            [candidate_pool[0], ticket],
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            draws=draws,
        ).official_any_prize_outcome_count
        exact_gains.append((expanded - current, index))
    best_gain = max(gain for gain, _ in exact_gains)
    expected_index = min(index for gain, index in exact_gains if gain == best_gain)

    assert selected.selected_indices[1] == expected_index
    assert (
        selected.sample_official_any_prize_probability
        == evaluate_portfolio(
            selected.portfolio,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            draws=draws,
        ).official_any_prize
    )
    assert sum(selected.marginal_sample_outcome_counts) == (
        selected.sample_official_any_prize_probability * draws.size * (pool_size - draw_size)
    )


def test_selector_rejects_duplicate_candidates_and_invalid_k() -> None:
    draws = all_main_draw_masks(9, 3)
    with pytest.raises(ValueError, match="duplicate candidate"):
        select_official_win_marginal_coverage(
            ((1, 2, 3), (3, 2, 1)), 1, selection_draws=draws, pool_size=9, draw_size=3
        )
    with pytest.raises(ValueError, match="k must"):
        select_official_win_marginal_coverage(
            ((1, 2, 3),), 2, selection_draws=draws, pool_size=9, draw_size=3
        )


def test_selector_rejects_empty_or_illegal_selection_evidence() -> None:
    candidate_pool = ((1, 2, 3),)
    with pytest.raises(ValueError, match="non-empty"):
        select_official_win_marginal_coverage(
            candidate_pool,
            1,
            selection_draws=np.asarray([], dtype=np.uint64),
            pool_size=9,
            draw_size=3,
        )
    with pytest.raises(ValueError, match="illegal main draw"):
        select_official_win_marginal_coverage(
            candidate_pool,
            1,
            selection_draws=np.asarray([1], dtype=np.uint64),
            pool_size=9,
            draw_size=3,
        )


def test_single_sample_probability_integrates_special_ball_exactly() -> None:
    pool_size, draw_size, outright_matches = 9, 3, 2
    candidate_pool = ((1, 2, 3), (4, 5, 6), (1, 7, 8))
    draws = all_main_draw_masks(pool_size, draw_size)

    selected = select_official_win_marginal_coverage(
        candidate_pool,
        2,
        selection_draws=draws,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )
    exact = evaluate_portfolio(
        selected.portfolio,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=draws,
    )

    assert selected.sample_official_any_prize_probability == Fraction(
        exact.official_any_prize_outcome_count,
        exact.main_draw_count * exact.special_count,
    )
