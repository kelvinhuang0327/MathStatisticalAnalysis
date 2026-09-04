from __future__ import annotations

import itertools
import math
import random
from fractions import Fraction

from lottolab.research.bounded_coverage_optimizer import exact_portfolio_coverage
from lottolab.research.exact_coverage_baseline import qualifying_ticket_count
from lottolab.research.exact_coverage_fast_evaluator import fast_exact_portfolio_coverage
from lottolab.research.expected_max_main_matches import expected_max_main_matches


def _brute_force_expected_max(
    pool_size: int, draw_size: int, portfolio: tuple[tuple[int, ...], ...]
) -> Fraction:
    """Ground truth E[max_t |t ∩ D|] by direct definition: enumerate every
    possible draw, take the max per-ticket intersection size, average
    exactly. Independent of the tail-sum identity under test."""

    ticket_sets = [set(ticket) for ticket in portfolio]
    total = 0
    count = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_set = set(draw)
        best = max((len(draw_set & ticket) for ticket in ticket_sets), default=0)
        total += best
        count += 1
    return Fraction(total, count)


def _random_portfolio(
    rng: random.Random, pool_size: int, draw_size: int, ticket_count: int
) -> tuple[tuple[int, ...], ...]:
    portfolio: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    attempts = 0
    while len(portfolio) < ticket_count and attempts < 30:
        attempts += 1
        candidate = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
        if candidate in seen:
            continue
        seen.add(candidate)
        portfolio.append(candidate)
    return tuple(portfolio)


def test_matches_brute_force_definition_for_hand_picked_case() -> None:
    portfolio = ((1, 2, 3), (4, 5, 6))
    assert expected_max_main_matches(10, 3, portfolio) == _brute_force_expected_max(
        10, 3, portfolio
    )


def test_empty_portfolio_is_zero() -> None:
    assert expected_max_main_matches(49, 6, ()) == Fraction(0)


def test_zero_draw_size_is_zero() -> None:
    assert expected_max_main_matches(49, 0, ((1, 2, 3, 4, 5, 6),)) == Fraction(0)


def test_randomized_small_scale_against_brute_force_definition() -> None:
    rng = random.Random(20260904)
    checked = 0
    for _ in range(60):
        pool_size = rng.randint(4, 11)
        draw_size = rng.randint(1, min(4, pool_size))
        portfolio = _random_portfolio(rng, pool_size, draw_size, rng.randint(0, 4))
        expected = _brute_force_expected_max(pool_size, draw_size, portfolio)
        actual = expected_max_main_matches(pool_size, draw_size, portfolio)
        assert actual == expected, (pool_size, draw_size, portfolio)
        checked += 1
    assert checked == 60


def test_single_ticket_matches_independent_closed_form_tail_sum() -> None:
    # For one ticket, P(match >= m) = qualifying_ticket_count(m) / C(pool, draw)
    # -- a closed-form combinatorial count (exact_coverage_baseline.py),
    # computed independently of the enumeration-based evaluators.
    pool_size, draw_size = 20, 6
    ticket = (1, 2, 3, 4, 5, 6)
    total_tickets = math.comb(pool_size, draw_size)
    expected = Fraction(
        sum(qualifying_ticket_count(pool_size, draw_size, m) for m in range(1, draw_size + 1)),
        total_tickets,
    )
    assert expected_max_main_matches(pool_size, draw_size, (ticket,)) == expected


def test_default_evaluator_matches_brute_force_enumerator() -> None:
    portfolio = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))
    fast_result = expected_max_main_matches(
        20, 6, portfolio, evaluator=fast_exact_portfolio_coverage
    )
    exact_result = expected_max_main_matches(20, 6, portfolio, evaluator=exact_portfolio_coverage)
    assert fast_result == exact_result


def test_bounded_between_zero_and_draw_size() -> None:
    rng = random.Random(9)
    for _ in range(20):
        pool_size = rng.randint(6, 15)
        draw_size = rng.randint(1, min(6, pool_size))
        portfolio = _random_portfolio(rng, pool_size, draw_size, rng.randint(0, 5))
        value = expected_max_main_matches(pool_size, draw_size, portfolio)
        assert 0 <= value <= draw_size


def test_monotonic_non_decreasing_when_adding_a_ticket() -> None:
    pool_size, draw_size = 12, 4
    one_ticket = ((1, 2, 3, 4),)
    two_tickets = ((1, 2, 3, 4), (5, 6, 7, 8))
    before = expected_max_main_matches(pool_size, draw_size, one_ticket)
    after = expected_max_main_matches(pool_size, draw_size, two_tickets)
    assert after >= before


def test_ticket_order_within_portfolio_is_irrelevant() -> None:
    pool_size, draw_size = 15, 5
    a = ((1, 2, 3, 4, 5), (6, 7, 8, 9, 10))
    b = ((6, 7, 8, 9, 10), (1, 2, 3, 4, 5))
    assert expected_max_main_matches(pool_size, draw_size, a) == expected_max_main_matches(
        pool_size, draw_size, b
    )
