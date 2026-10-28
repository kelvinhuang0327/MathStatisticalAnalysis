from __future__ import annotations

import math

import pytest

from lottolab.research.b649_triad_shrinkage_candidate_r1 import (
    MAX_ABSOLUTE_STANDARDIZED_RESIDUAL,
    MINIMUM_TRIAD_SUPPORT,
    SHRINKAGE_STRENGTHS,
    compute_triad_residual_state,
    produce_b649_triad_shrinkage_candidate_r1,
    shrink_standardized_residual,
    strictly_prior_history,
)


def _history(count: int) -> tuple[tuple[int, ...], ...]:
    draws = []
    for index in range(count):
        numbers = tuple(sorted(((index * 13 + offset * 7) % 49) + 1 for offset in range(6)))
        draws.append(numbers)
    return tuple(draws)


def test_prior_prefix_excludes_target_and_future_draws() -> None:
    draws = list(_history(340))
    expected = produce_b649_triad_shrinkage_candidate_r1(draws, 300, 3, 5)
    draws[300:] = [(44, 45, 46, 47, 48, 49)] * 40

    actual = produce_b649_triad_shrinkage_candidate_r1(draws, 300, 3, 5)

    assert actual == expected
    assert strictly_prior_history(draws, 300) == _history(300)


def test_triad_residuals_and_support_arrays_have_fixed_bounded_shape() -> None:
    state = compute_triad_residual_state(_history(320), 300)

    assert state.history_draw_count == 300
    assert len(state.support_counts) == 18_424
    assert len(state.standardized_residuals) == 18_424
    assert int(state.support_counts.max()) <= state.history_draw_count
    assert max(abs(float(value)) for value in state.standardized_residuals) <= (
        MAX_ABSOLUTE_STANDARDIZED_RESIDUAL
    )
    assert not state.support_counts.flags.writeable
    assert not state.standardized_residuals.flags.writeable


@pytest.mark.parametrize("ticket_count", (2, 3, 5))
def test_candidate_emits_legal_unique_portfolios_for_k2_k3_k5(
    ticket_count: int,
) -> None:
    history = _history(330)

    first = produce_b649_triad_shrinkage_candidate_r1(history, 320, ticket_count, 10)
    second = produce_b649_triad_shrinkage_candidate_r1(history, 320, ticket_count, 10)

    assert first == second
    assert len(first) == ticket_count
    assert len(set(first)) == ticket_count
    for ticket in first:
        assert len(ticket) == 6
        assert ticket == tuple(sorted(ticket))
        assert len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)


def test_minimum_support_and_strength_grid_bound_sparse_triad_weight() -> None:
    for strength in SHRINKAGE_STRENGTHS:
        assert shrink_standardized_residual(1_000_000.0, MINIMUM_TRIAD_SUPPORT - 1, strength) == 0
        weight = shrink_standardized_residual(1_000_000.0, MINIMUM_TRIAD_SUPPORT, strength)
        assert math.isfinite(weight)
        assert 0 < weight <= MAX_ABSOLUTE_STANDARDIZED_RESIDUAL

    assert shrink_standardized_residual(-1_000_000.0, 1_000_000, 2) == (
        -MAX_ABSOLUTE_STANDARDIZED_RESIDUAL
        * 1_000_000
        / (1_000_000 + 2)
    )


def test_candidate_rejects_non_grid_shrinkage_and_insufficient_history() -> None:
    history = _history(320)

    with pytest.raises(ValueError, match="shrinkage_strength"):
        produce_b649_triad_shrinkage_candidate_r1(history, 310, 2, 3)
    with pytest.raises(ValueError, match="strictly prior"):
        produce_b649_triad_shrinkage_candidate_r1(history, 299, 2, 5)
