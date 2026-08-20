"""Exact recurrence parity and failure closure for the evolution gap matrix."""

from __future__ import annotations

from itertools import combinations, product

import pytest

from lottolab.domain.evolution_gap_matrix import (
    BIG_LOTTO_NUMBER_COUNT,
    BIG_LOTTO_PICK_COUNT,
    DONOR_METHOD,
    DONOR_SOURCE,
    DONOR_SOURCE_SHA256,
    UNSEEN_GAP,
    EvolutionGapMatrix,
    EvolutionGapMatrixError,
    compute_evolution_gap_matrix,
)


def _donor_reference(draws: tuple[tuple[int, ...], ...]) -> EvolutionGapMatrix:
    binary = [[0] * BIG_LOTTO_NUMBER_COUNT for _ in draws]
    for draw_index, draw in enumerate(draws):
        for number in draw:
            binary[draw_index][number - 1] = 1

    gaps = [[UNSEEN_GAP] * BIG_LOTTO_NUMBER_COUNT for _ in draws]
    last_seen = [UNSEEN_GAP] * BIG_LOTTO_NUMBER_COUNT
    for draw_index in range(len(draws)):
        for number_index in range(BIG_LOTTO_NUMBER_COUNT):
            if last_seen[number_index] >= 0:
                gaps[draw_index][number_index] = draw_index - last_seen[number_index]
            if binary[draw_index][number_index]:
                last_seen[number_index] = draw_index
    return tuple(tuple(row) for row in gaps)


def test_donor_identity_method_and_fixed_dimensions_are_frozen() -> None:
    assert DONOR_SOURCE == "tools/evolving_strategy_engine/data_loader.py"
    assert DONOR_SOURCE_SHA256 == (
        "0f3f8c75acf87b510be1787cc9cb2b99c029ffa51af38f2b47fed4a5275074ac"
    )
    assert DONOR_METHOD == "compute_gaps"
    assert (BIG_LOTTO_NUMBER_COUNT, BIG_LOTTO_PICK_COUNT, UNSEEN_GAP) == (49, 6, -1)


def test_golden_preserves_pre_observation_sentinel_and_update_order() -> None:
    history = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (2, 7, 12, 13, 14, 15),
    )

    matrix = compute_evolution_gap_matrix(history)

    assert matrix == (
        (UNSEEN_GAP,) * 49,
        (1, 1, 1, 1, 1, 1) + (UNSEEN_GAP,) * 43,
        (1, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1) + (UNSEEN_GAP,) * 38,
    )
    assert matrix == _donor_reference(history)


def test_generated_histories_match_donor_recurrence_exhaustively() -> None:
    tickets = tuple(combinations(range(1, 8), BIG_LOTTO_PICK_COUNT))

    for history_length in range(5):
        for history in product(tickets, repeat=history_length):
            assert compute_evolution_gap_matrix(history) == _donor_reference(history)


def test_each_cell_is_distance_from_most_recent_earlier_occurrence() -> None:
    history = (
        (6, 5, 4, 3, 2, 1),
        (7, 8, 9, 10, 11, 12),
        (1, 8, 13, 14, 15, 16),
        (1, 2, 8, 16, 17, 18),
    )

    matrix = compute_evolution_gap_matrix(history)

    assert all(len(row) == BIG_LOTTO_NUMBER_COUNT for row in matrix)
    for draw_index, row in enumerate(matrix):
        for number in range(1, BIG_LOTTO_NUMBER_COUNT + 1):
            earlier = tuple(index for index in range(draw_index) if number in history[index])
            expected = draw_index - earlier[-1] if earlier else UNSEEN_GAP
            assert row[number - 1] == expected


def test_empty_history_returns_empty_immutable_matrix() -> None:
    result = compute_evolution_gap_matrix(())

    assert result == ()
    assert isinstance(result, tuple)


def test_input_order_is_irrelevant_and_caller_state_is_not_mutated() -> None:
    draws = [
        [6, 5, 4, 3, 2, 1],
        [12, 11, 10, 9, 8, 7],
    ]
    before = [draw.copy() for draw in draws]

    result = compute_evolution_gap_matrix(draws)

    assert result == _donor_reference(tuple(tuple(draw) for draw in draws))
    assert draws == before
    assert isinstance(result, tuple)
    assert all(isinstance(row, tuple) for row in result)


def test_fixed_history_is_deterministic() -> None:
    history = (
        (1, 2, 3, 4, 5, 6),
        (6, 7, 8, 9, 10, 11),
        (1, 12, 13, 14, 15, 16),
    )

    first = compute_evolution_gap_matrix(history)

    assert all(compute_evolution_gap_matrix(history) == first for _ in range(20))


@pytest.mark.parametrize(
    "draws",
    (
        "not-draws",
        object(),
        ("not-a-draw",),
        ((1, 2, 3, 4, 5),),
        ((1, 1, 2, 3, 4, 5),),
        ((True, 2, 3, 4, 5, 6),),
        ((1.0, 2, 3, 4, 5, 6),),
        ((0, 1, 2, 3, 4, 5),),
        ((1, 2, 3, 4, 5, 50),),
    ),
)
def test_invalid_histories_fail_closed(draws: object) -> None:
    with pytest.raises(EvolutionGapMatrixError):
        compute_evolution_gap_matrix(draws)  # type: ignore[arg-type]
