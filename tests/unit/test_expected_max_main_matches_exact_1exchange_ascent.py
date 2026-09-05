"""Tests for ``ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1``."""

from __future__ import annotations

import itertools
import random
from fractions import Fraction

from lottolab.research.expected_max_main_matches import expected_max_main_matches
from lottolab.research.expected_max_main_matches_exact_1exchange_ascent import (
    Portfolio,
    coverage_at_least_one_exact,
    evaluate_expected_max_one_exchange_neighborhood,
    expected_max_main_matches_exact,
    iterative_exact_1exchange_expected_max_ascent,
    portfolio_sha256,
)
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    enumerate_legal_one_exchange_neighbors,
)


def _brute_force_expected_max(pool_size: int, draw_size: int, portfolio: Portfolio) -> Fraction:
    """Ground truth by direct definition, independent of the tail-sum
    identity and of every evaluator this module reuses."""

    ticket_sets = [set(ticket) for ticket in portfolio]
    total = 0
    count = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_set = set(draw)
        total += max((len(draw_set & ticket) for ticket in ticket_sets), default=0)
        count += 1
    return Fraction(total, count)


def _brute_force_best_neighbor(
    pool_size: int, draw_size: int, portfolio: Portfolio
) -> tuple[Portfolio, Fraction]:
    """Independent best-neighbor oracle: enumerate the canonical topology's
    own neighbor set directly, score every one by the brute-force
    definition (not this module's evaluator), and pick max with
    lexicographic tie-break -- exercising none of the code under test."""

    neighbors = enumerate_legal_one_exchange_neighbors(portfolio, pool_size)
    scored = [(_brute_force_expected_max(pool_size, draw_size, n), n) for n in neighbors]
    best_score, best_portfolio = min(scored, key=lambda item: (-item[0], item[1]))
    return best_portfolio, best_score


# ---------------------------------------------------------------------------
# Expected-max core regression (parity with the frozen authority)
# ---------------------------------------------------------------------------


def test_expected_max_core_matches_frozen_authority() -> None:
    rng = random.Random(20260905)
    for _ in range(40):
        pool_size = rng.randint(5, 12)
        draw_size = rng.randint(1, min(5, pool_size))
        ticket_count = rng.randint(1, 4)
        seen: set[tuple[int, ...]] = set()
        tickets: list[tuple[int, ...]] = []
        attempts = 0
        while len(tickets) < ticket_count and attempts < 30:
            attempts += 1
            candidate = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
            if candidate in seen:
                continue
            seen.add(candidate)
            tickets.append(candidate)
        portfolio = tuple(sorted(tickets))
        authority = expected_max_main_matches(pool_size, draw_size, portfolio)
        under_test = expected_max_main_matches_exact(pool_size, draw_size, portfolio)
        assert under_test == authority, (pool_size, draw_size, portfolio)


def test_coverage_at_least_one_matches_fast_evaluator_at_m1() -> None:
    from lottolab.research.exact_coverage_fast_evaluator import fast_exact_portfolio_coverage

    rng = random.Random(7)
    for _ in range(20):
        pool_size = rng.randint(5, 14)
        draw_size = rng.randint(1, min(6, pool_size))
        portfolio = tuple(
            sorted(tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size))) for _ in range(2))
        )
        closed_form = coverage_at_least_one_exact(pool_size, draw_size, portfolio)
        via_evaluator = fast_exact_portfolio_coverage(pool_size, draw_size, 1, portfolio)
        assert closed_form == via_evaluator


# ---------------------------------------------------------------------------
# One-exchange topology regression (reused canonical enumerator, not reimplemented)
# ---------------------------------------------------------------------------


def test_neighborhood_matches_canonical_topology_enumeration() -> None:
    pool_size, draw_size = 7, 3
    portfolio = ((1, 2, 3), (4, 5, 6))
    result = evaluate_expected_max_one_exchange_neighborhood(pool_size, draw_size, portfolio)

    canonical_neighbors = set(enumerate_legal_one_exchange_neighbors(portfolio, pool_size))
    scored_neighbors = {neighbor.portfolio for neighbor in result.neighbors}
    assert scored_neighbors == canonical_neighbors
    assert result.unique_legal_neighbor_count == len(canonical_neighbors)


def test_duplicate_ticket_neighbor_rejection() -> None:
    pool_size, draw_size = 7, 3
    portfolio = ((1, 2, 3), (1, 2, 4))
    result = evaluate_expected_max_one_exchange_neighborhood(pool_size, draw_size, portfolio)

    for neighbor in result.neighbors:
        assert len(neighbor.portfolio) == 2
        assert len(set(neighbor.portfolio)) == 2
        assert portfolio != neighbor.portfolio
    canonical_neighbors = set(enumerate_legal_one_exchange_neighbors(portfolio, pool_size))
    assert {n.portfolio for n in result.neighbors} == canonical_neighbors


# ---------------------------------------------------------------------------
# Independent brute-force best-neighbor oracle
# ---------------------------------------------------------------------------


def test_neighborhood_scores_match_brute_force_definition() -> None:
    pool_size, draw_size = 7, 3
    portfolio = ((1, 2, 3), (4, 5, 6))
    result = evaluate_expected_max_one_exchange_neighborhood(pool_size, draw_size, portfolio)

    assert result.input_expected_max == _brute_force_expected_max(pool_size, draw_size, portfolio)
    for neighbor in result.neighbors:
        assert neighbor.expected_max == _brute_force_expected_max(
            pool_size, draw_size, neighbor.portfolio
        )


def test_best_neighbor_matches_independent_brute_force_oracle() -> None:
    for portfolio in (
        ((1, 2, 3), (4, 5, 6)),
        ((1, 2, 3), (1, 2, 4), (5, 6, 7)),
    ):
        pool_size, draw_size = 7, 3
        result = evaluate_expected_max_one_exchange_neighborhood(pool_size, draw_size, portfolio)
        expected_best_portfolio, expected_best_score = _brute_force_best_neighbor(
            pool_size, draw_size, portfolio
        )
        assert result.best_neighbor_portfolio == expected_best_portfolio
        assert result.best_neighbor_expected_max == expected_best_score


# ---------------------------------------------------------------------------
# Lexicographic tie-break
# ---------------------------------------------------------------------------


def test_lexicographic_tie_break_among_equal_scoring_neighbors() -> None:
    pool_size, draw_size = 6, 3
    portfolio = ((1, 2, 3),)
    result = evaluate_expected_max_one_exchange_neighborhood(pool_size, draw_size, portfolio)

    maximum = max(n.expected_max for n in result.neighbors)
    tied = [n.portfolio for n in result.neighbors if n.expected_max == maximum]
    assert len(tied) > 1, "fixture must actually exercise a tie"
    assert result.best_neighbor_portfolio == min(tied)


# ---------------------------------------------------------------------------
# Strict-improvement acceptance / equal-value plateau rejection
# ---------------------------------------------------------------------------


def test_strict_acceptance_requires_greater_not_equal() -> None:
    pool_size, draw_size = 6, 3
    portfolio = ((1, 2, 3),)
    result = evaluate_expected_max_one_exchange_neighborhood(pool_size, draw_size, portfolio)
    # The single-ticket pool=6/draw=3 rung is already known (from the tie-break
    # test above) to have its best neighbor exactly equal to the incumbent's
    # score plateau; confirm the ascent driver refuses an equal-value move.
    ascent = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, portfolio)
    assert not ascent.iterations[0].accepted_move or ascent.iterations[0].delta > 0
    if not ascent.iterations[0].accepted_move:
        assert ascent.iterations[0].delta <= 0
        assert ascent.iterations[0].best_neighbor_expected_max <= result.input_expected_max


# ---------------------------------------------------------------------------
# Improving trajectory (>=1 accepted move)
# ---------------------------------------------------------------------------


def test_ascent_finds_at_least_one_improving_move() -> None:
    pool_size, draw_size = 10, 3
    seed = ((1, 2, 3), (1, 2, 4))
    ascent = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed)

    assert ascent.move_count >= 1
    assert ascent.terminal_expected_max > ascent.seed_expected_max
    for iteration in ascent.iterations[:-1]:
        assert iteration.accepted_move
        assert iteration.delta > 0
    assert not ascent.iterations[-1].accepted_move


def test_ascent_trajectory_is_strictly_increasing_and_chained() -> None:
    pool_size, draw_size = 10, 3
    seed = ((1, 2, 3), (1, 2, 4))
    ascent = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed)

    for previous, following in itertools.pairwise(ascent.iterations):
        assert previous.accepted_move
        assert previous.best_neighbor_portfolio == following.input_portfolio
        assert previous.best_neighbor_expected_max == following.input_expected_max
        assert following.input_expected_max > previous.input_expected_max


# ---------------------------------------------------------------------------
# No-improvement local-optimum fixture
# ---------------------------------------------------------------------------


def test_already_local_optimum_seed_stops_immediately() -> None:
    pool_size, draw_size = 6, 3
    # C(6,3) = 20 possible tickets; a single ticket already achieves the
    # maximum possible expected-max score for a 1-ticket portfolio at this
    # scale (every legal neighbor is itself another 3-of-6 ticket, so by
    # symmetry -- verified against the brute-force oracle above -- the
    # neighborhood plateaus rather than strictly improves).
    seed = ((1, 2, 3),)
    ascent = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed)

    assert ascent.move_count == 0
    assert len(ascent.iterations) == 1
    assert not ascent.iterations[0].accepted_move
    assert ascent.terminal_portfolio == seed
    assert ascent.terminal_expected_max == ascent.seed_expected_max


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_ascent_is_deterministic_across_repeated_calls() -> None:
    pool_size, draw_size = 10, 3
    seed = ((1, 2, 3), (1, 2, 4))
    first = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed)
    second = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed)
    assert first == second


def test_ascent_is_independent_of_seed_ticket_order() -> None:
    pool_size, draw_size = 10, 3
    seed_a = ((1, 2, 3), (1, 2, 4))
    seed_b = ((1, 2, 4), (1, 2, 3))
    a = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed_a)
    b = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed_b)
    assert a == b


# ---------------------------------------------------------------------------
# Mutation discrimination (documented manual check, see module docstring note
# in the handoff report -- these assertions are the ones that must fail if
# STRICT_BEST_IMPROVEMENT were weakened to `>=`, or if the lexicographic
# tie-break secondary key were dropped).
# ---------------------------------------------------------------------------


def test_mutation_discrimination_strict_greater_and_tie_break() -> None:
    pool_size, draw_size = 6, 3
    portfolio = ((1, 2, 3),)
    ascent = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, portfolio)
    # A `>=` acceptance mutant would accept the terminal iteration's
    # equal-valued best neighbor and never halt at move_count == 0.
    assert ascent.move_count == 0
    assert ascent.iterations[0].delta <= 0

    pool_size2, draw_size2 = 10, 3
    seed = ((1, 2, 3), (1, 2, 4))
    result = evaluate_expected_max_one_exchange_neighborhood(pool_size2, draw_size2, seed)
    maximum = max(n.expected_max for n in result.neighbors)
    tied = sorted(n.portfolio for n in result.neighbors if n.expected_max == maximum)
    # A dropped/broken tie-break would not guarantee the lexicographically
    # smallest of the tied portfolios is selected.
    assert result.best_neighbor_portfolio == tied[0]


# ---------------------------------------------------------------------------
# Method-E focused regression (wiring smoke test at toy scale)
# ---------------------------------------------------------------------------


def test_method_e_seed_wires_into_the_ascent() -> None:
    pool_size, draw_size, ticket_count = 9, 3, 2
    seed = greedy_minmax_then_sum_overlap_portfolio(pool_size, draw_size, ticket_count)
    ascent = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed)

    assert ascent.seed_portfolio == tuple(sorted(seed))
    assert 0 < ascent.seed_expected_max <= draw_size
    assert ascent.terminal_expected_max >= ascent.seed_expected_max
    assert not ascent.iterations[-1].accepted_move
    assert (
        ascent.terminal_unique_neighbor_count == ascent.iterations[-1].unique_legal_neighbor_count
    )


# ---------------------------------------------------------------------------
# Fraction-authority / portfolio hashing sanity
# ---------------------------------------------------------------------------


def test_portfolio_sha256_is_stable_and_order_independent() -> None:
    a = ((1, 2, 3), (4, 5, 6))
    b = ((4, 5, 6), (1, 2, 3))
    assert portfolio_sha256(a) == portfolio_sha256(tuple(sorted(a)))
    assert portfolio_sha256(tuple(sorted(a))) == portfolio_sha256(tuple(sorted(b)))


def test_no_floating_point_used_anywhere_in_the_result() -> None:
    pool_size, draw_size = 10, 3
    seed = ((1, 2, 3), (1, 2, 4))
    ascent = iterative_exact_1exchange_expected_max_ascent(pool_size, draw_size, seed)
    for iteration in ascent.iterations:
        assert isinstance(iteration.input_expected_max, Fraction)
        assert isinstance(iteration.best_neighbor_expected_max, Fraction)
        assert isinstance(iteration.delta, Fraction)
