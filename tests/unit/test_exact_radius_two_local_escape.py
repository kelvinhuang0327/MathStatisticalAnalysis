"""Independent focused checks for exact radius-two local escape."""

from __future__ import annotations

import itertools
import math
from dataclasses import replace
from fractions import Fraction

import pytest

from lottolab.research.exact_radius_two_local_escape import (
    ExactRadiusTwoIteration,
    PackedWinningSpace,
    evaluate_exact_radius_two_neighborhood,
    iterative_exact_radius_two_ascent,
    radius_two_endpoint_feasibility,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import Portfolio
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    enumerate_unique_legal_one_exchange_neighbors,
)


def _brute_force_q(
    pool_size: int,
    draw_size: int,
    portfolio: Portfolio,
) -> Fraction:
    covered = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_set = set(draw)
        if any(len(draw_set & set(ticket)) >= 3 for ticket in portfolio):
            covered += 1
    return Fraction(covered, math.comb(pool_size, draw_size))


def _literal_radius_two_endpoints(
    portfolio: Portfolio,
    pool_size: int,
) -> tuple[Portfolio, ...]:
    endpoints = {
        endpoint
        for intermediate in enumerate_unique_legal_one_exchange_neighbors(
            portfolio,
            pool_size,
        )
        for endpoint in enumerate_unique_legal_one_exchange_neighbors(
            intermediate,
            pool_size,
        )
        if endpoint != portfolio
    }
    return tuple(sorted(endpoints))


def _literal_best_endpoint(
    pool_size: int,
    draw_size: int,
    portfolio: Portfolio,
) -> tuple[Portfolio, Fraction, int]:
    endpoints = _literal_radius_two_endpoints(portfolio, pool_size)
    scored = tuple(
        (endpoint, _brute_force_q(pool_size, draw_size, endpoint)) for endpoint in endpoints
    )
    best_q = max(q_value for _, q_value in scored)
    best_portfolio = min(endpoint for endpoint, q_value in scored if q_value == best_q)
    return best_portfolio, best_q, len(endpoints)


def _literal_ascent(
    pool_size: int,
    draw_size: int,
    seed: Portfolio,
) -> tuple[Portfolio, Fraction, int, int]:
    current = seed
    move_count = 0
    endpoints_evaluated = 0
    while True:
        current_q = _brute_force_q(pool_size, draw_size, current)
        best, best_q, endpoint_count = _literal_best_endpoint(
            pool_size,
            draw_size,
            current,
        )
        endpoints_evaluated += endpoint_count
        if best_q <= current_q:
            return current, current_q, move_count, endpoints_evaluated
        current = best
        move_count += 1


def test_packed_objective_matches_independent_winning_space_scan() -> None:
    portfolio: Portfolio = (
        (1, 2, 3, 4),
        (1, 5, 6, 7),
        (2, 5, 7, 8),
    )
    space = PackedWinningSpace.build(8, 4)

    assert space.total_draws == math.comb(8, 4)
    assert space.exact_portfolio_q(portfolio) == _brute_force_q(8, 4, portfolio)


@pytest.mark.parametrize(
    "portfolio",
    [
        ((1, 2, 3, 4), (5, 6, 7, 8)),
        ((1, 2, 3, 4), (1, 2, 3, 5)),
        ((1, 2, 3, 4), (1, 2, 5, 6), (3, 4, 7, 8)),
    ],
)
def test_endpoint_count_scores_and_tie_break_match_literal_two_step_bfs(
    portfolio: Portfolio,
) -> None:
    space = PackedWinningSpace.build(8, 4)
    literal_best, literal_q, literal_count = _literal_best_endpoint(8, 4, portfolio)

    feasibility = radius_two_endpoint_feasibility(8, 4, portfolio)
    evaluated = evaluate_exact_radius_two_neighborhood(space, portfolio)

    assert feasibility.unique_endpoint_count == literal_count
    assert evaluated.unique_endpoint_count == literal_count
    assert evaluated.first_level_neighbor_count == len(
        enumerate_unique_legal_one_exchange_neighbors(portfolio, 8)
    )
    assert evaluated.input_q == _brute_force_q(8, 4, portfolio)
    assert evaluated.best_endpoint_portfolio == literal_best
    assert evaluated.best_endpoint_q == literal_q
    assert evaluated.delta == literal_q - evaluated.input_q
    assert evaluated.accepted_move is (literal_q > evaluated.input_q)


def test_iterative_ascent_matches_independent_literal_fixed_point() -> None:
    seed: Portfolio = (
        (1, 2, 3, 4),
        (1, 2, 3, 5),
        (1, 2, 3, 6),
    )
    expected_portfolio, expected_q, expected_moves, expected_evaluated = _literal_ascent(
        8,
        4,
        seed,
    )

    result = iterative_exact_radius_two_ascent(PackedWinningSpace.build(8, 4), seed)

    assert result.terminal_portfolio == expected_portfolio
    assert result.terminal_q == expected_q
    assert result.move_count == expected_moves
    assert result.unique_endpoints_evaluated == expected_evaluated
    assert len(result.iterations) == result.move_count + 1
    assert all(
        iteration.accepted_move and iteration.delta > 0 for iteration in result.iterations[:-1]
    )
    assert result.iterations[-1].accepted_move is False
    assert result.iterations[-1].delta <= 0


def test_iteration_checkpoint_prefix_resumes_to_identical_fixed_point() -> None:
    seed: Portfolio = (
        (1, 2, 3, 4),
        (1, 2, 3, 5),
        (1, 2, 3, 6),
    )
    space = PackedWinningSpace.build(8, 4)
    completed_iterations: list[ExactRadiusTwoIteration] = []
    uninterrupted = iterative_exact_radius_two_ascent(
        space,
        seed,
        iteration_completed=completed_iterations.append,
    )

    assert tuple(completed_iterations) == uninterrupted.iterations
    assert uninterrupted.move_count > 0
    resumed = iterative_exact_radius_two_ascent(
        space,
        seed,
        resume_iterations=uninterrupted.iterations[:1],
    )
    terminal_resume = iterative_exact_radius_two_ascent(
        space,
        seed,
        resume_iterations=uninterrupted.iterations,
        progress=lambda _message: pytest.fail("terminal resume rescored a neighborhood"),
    )

    assert resumed == uninterrupted
    assert terminal_resume == uninterrupted


def test_resume_rejects_changed_exact_checkpoint_value() -> None:
    seed: Portfolio = (
        (1, 2, 3, 4),
        (1, 2, 3, 5),
        (1, 2, 3, 6),
    )
    space = PackedWinningSpace.build(8, 4)
    result = iterative_exact_radius_two_ascent(space, seed)
    changed = replace(
        result.iterations[0],
        input_q=result.iterations[0].input_q + Fraction(1, space.total_draws),
    )

    with pytest.raises(ValueError, match="input exact-Q replay mismatch"):
        iterative_exact_radius_two_ascent(
            space,
            seed,
            resume_iterations=(changed,),
        )


def test_invalid_ticket_shape_is_rejected() -> None:
    space = PackedWinningSpace.build(8, 4)

    with pytest.raises(ValueError, match="duplicate numbers"):
        space.exact_portfolio_q(((1, 2, 3, 3),))
