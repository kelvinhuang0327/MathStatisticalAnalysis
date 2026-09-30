"""Focused checks for exact fixed-K candidate-pool recombination."""

from __future__ import annotations

import itertools
from collections.abc import Sequence

import numpy as np
import pytest

from lottolab.research.b649_fixed_k_exact_recombination import (
    _marginal_outcome_gains,  # pyright: ignore[reportPrivateUsage]
    select_fixed_k_exact_recombination,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

type Ticket = tuple[int, ...]


def _brute_force_outcome_count(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int,
    draw_size: int,
    outright_matches: int,
) -> int:
    winning_outcomes = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        drawn = set(draw)
        for special in range(1, pool_size + 1):
            if special in drawn:
                continue
            if any(
                len(drawn.intersection(ticket)) >= outright_matches
                or (
                    len(drawn.intersection(ticket)) == outright_matches - 1
                    and special in ticket
                )
                for ticket in portfolio
            ):
                winning_outcomes += 1
    return winning_outcomes


def _brute_force_m3_plus_draw_count(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int,
    draw_size: int,
    outright_matches: int,
) -> int:
    return sum(
        any(
            len(set(draw).intersection(ticket)) >= outright_matches
            for ticket in portfolio
        )
        for draw in itertools.combinations(range(1, pool_size + 1), draw_size)
    )


def _brute_force_greedy(
    candidate_pool: Sequence[Sequence[int]],
    k: int,
    *,
    pool_size: int,
    draw_size: int,
    outright_matches: int,
) -> tuple[tuple[Ticket, ...], tuple[int, ...]]:
    remaining = sorted({tuple(sorted(ticket)) for ticket in candidate_pool})
    selected: list[Ticket] = []
    marginal_gains: list[int] = []
    current_outcomes = 0

    for _ in range(k):
        options = [
            (
                _brute_force_outcome_count(
                    [*selected, candidate],
                    pool_size=pool_size,
                    draw_size=draw_size,
                    outright_matches=outright_matches,
                )
                - current_outcomes,
                candidate,
            )
            for candidate in remaining
        ]
        gain, chosen = min(options, key=lambda item: (-item[0], item[1]))
        selected.append(chosen)
        marginal_gains.append(gain)
        current_outcomes += gain
        remaining.remove(chosen)

    return tuple(selected), tuple(marginal_gains)


@pytest.mark.parametrize(
    "candidate",
    [
        (1, 2),
        (1, 1, 2),
        (0, 2, 3),
        (1, 2, 8),
        (True, 2, 3),
    ],
)
def test_rejects_illegal_candidate_tickets(candidate: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="illegal candidate ticket"):
        select_fixed_k_exact_recombination(
            [candidate],
            1,
            pool_size=7,
            draw_size=3,
            outright_matches=2,
        )


def test_deduplicates_canonical_tickets_and_returns_exact_k() -> None:
    result = select_fixed_k_exact_recombination(
        [(3, 2, 1), (1, 2, 3), (6, 5, 4)],
        2,
        pool_size=7,
        draw_size=3,
        outright_matches=2,
        chunk_size=5,
    )

    assert len(result) == 2
    assert len(set(result)) == 2
    assert all(ticket == tuple(sorted(ticket)) for ticket in result)

    with pytest.raises(ValueError, match="distinct legal candidates"):
        select_fixed_k_exact_recombination(
            [(1, 2, 3), (3, 2, 1)],
            2,
            pool_size=7,
            draw_size=3,
            outright_matches=2,
        )


def test_candidate_order_does_not_change_selection() -> None:
    candidate_pool = [
        (1, 2, 3),
        (1, 2, 4),
        (1, 4, 5),
        (2, 5, 7),
        (3, 6, 8),
        (4, 6, 8),
    ]
    forward = select_fixed_k_exact_recombination(
        candidate_pool,
        4,
        pool_size=8,
        draw_size=3,
        outright_matches=2,
        chunk_size=7,
    )
    reversed_order = select_fixed_k_exact_recombination(
        list(reversed(candidate_pool)),
        4,
        pool_size=8,
        draw_size=3,
        outright_matches=2,
        chunk_size=7,
    )

    assert len(forward) == 4
    assert len(set(forward)) == 4
    assert forward == reversed_order


def test_ties_choose_the_lexicographically_smallest_ticket() -> None:
    candidate_pool = [(2, 4, 6), (1, 3, 5), (1, 2, 3)]

    result = select_fixed_k_exact_recombination(
        candidate_pool,
        1,
        pool_size=6,
        draw_size=3,
        outright_matches=3,
        chunk_size=4,
    )

    assert result == ((1, 2, 3),)


def test_matches_brute_force_greedy_steps_on_a_small_domain() -> None:
    pool_size, draw_size, outright_matches = 8, 3, 2
    candidate_pool = [
        (1, 2, 3),
        (1, 2, 4),
        (1, 4, 5),
        (2, 5, 7),
        (3, 6, 8),
        (4, 6, 8),
    ]
    expected, expected_gains = _brute_force_greedy(
        candidate_pool,
        4,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )
    draws = all_main_draw_masks(pool_size, draw_size)

    actual = select_fixed_k_exact_recombination(
        candidate_pool,
        4,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=draws,
        chunk_size=7,
    )

    assert actual == expected
    selected: list[Ticket] = []
    previous_outcomes = 0
    for ticket, expected_gain in zip(actual, expected_gains, strict=True):
        selected.append(ticket)
        result = evaluate_portfolio(
            selected,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            draws=draws,
            chunk_size=7,
        )
        brute_count = _brute_force_outcome_count(
            selected,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
        )
        assert result.official_any_prize_outcome_count == brute_count
        assert brute_count - previous_outcomes == expected_gain
        previous_outcomes = brute_count


def test_special_ball_rescue_changes_the_exact_marginal_ranking() -> None:
    first = (1, 2, 3)
    lower_rescue_gain = (1, 2, 4)
    higher_rescue_gain = (1, 4, 5)
    candidate_pool = [first, lower_rescue_gain, higher_rescue_gain]

    result = select_fixed_k_exact_recombination(
        candidate_pool,
        2,
        pool_size=6,
        draw_size=3,
        outright_matches=3,
        chunk_size=4,
    )

    base_outcomes = _brute_force_outcome_count(
        [first],
        pool_size=6,
        draw_size=3,
        outright_matches=3,
    )
    lower_gain = _brute_force_outcome_count(
        [first, lower_rescue_gain],
        pool_size=6,
        draw_size=3,
        outright_matches=3,
    ) - base_outcomes
    higher_gain = _brute_force_outcome_count(
        [first, higher_rescue_gain],
        pool_size=6,
        draw_size=3,
        outright_matches=3,
    ) - base_outcomes
    main_only_lower_gain = _brute_force_m3_plus_draw_count(
        [first, lower_rescue_gain],
        pool_size=6,
        draw_size=3,
        outright_matches=3,
    ) - _brute_force_m3_plus_draw_count(
        [first],
        pool_size=6,
        draw_size=3,
        outright_matches=3,
    )
    main_only_higher_gain = _brute_force_m3_plus_draw_count(
        [first, higher_rescue_gain],
        pool_size=6,
        draw_size=3,
        outright_matches=3,
    ) - _brute_force_m3_plus_draw_count(
        [first],
        pool_size=6,
        draw_size=3,
        outright_matches=3,
    )
    actual_gains = _marginal_outcome_gains(
        all_main_draw_masks(6, 3),
        [
            np.uint64(ticket_mask(lower_rescue_gain)),
            np.uint64(ticket_mask(higher_rescue_gain)),
        ],
        [np.uint64(ticket_mask(first))],
        special_count=3,
        outright_matches=3,
        chunk_size=4,
    )

    assert (lower_gain, higher_gain) == (8, 12)
    assert main_only_lower_gain == main_only_higher_gain
    assert tuple(actual_gains) == (lower_gain, higher_gain)
    assert result == (first, higher_rescue_gain)


def test_zero_marginal_candidates_still_fill_fixed_k() -> None:
    candidate_pool = [(1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4)]
    expected, marginal_gains = _brute_force_greedy(
        candidate_pool,
        3,
        pool_size=4,
        draw_size=3,
        outright_matches=1,
    )

    result = select_fixed_k_exact_recombination(
        candidate_pool,
        3,
        pool_size=4,
        draw_size=3,
        outright_matches=1,
        chunk_size=2,
    )

    assert result == expected == ((1, 2, 3), (1, 2, 4), (1, 3, 4))
    assert marginal_gains == (4, 0, 0)
