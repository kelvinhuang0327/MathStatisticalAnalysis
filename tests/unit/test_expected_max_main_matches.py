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


def test_draw_size_one() -> None:
    pool_size, draw_size = 9, 1
    portfolio = ((1,), (5,))
    assert expected_max_main_matches(pool_size, draw_size, portfolio) == _brute_force_expected_max(
        pool_size, draw_size, portfolio
    )


def test_pool_size_equals_draw_size() -> None:
    # Only one legal draw exists (the whole pool), so every ticket matches
    # it with certainty: E[max] must equal draw_size exactly.
    pool_size = draw_size = 5
    portfolio = ((1, 2, 3, 4, 5),)
    assert expected_max_main_matches(pool_size, draw_size, portfolio) == Fraction(draw_size)
    assert expected_max_main_matches(pool_size, draw_size, portfolio) == _brute_force_expected_max(
        pool_size, draw_size, portfolio
    )


def test_per_threshold_coverage_is_non_increasing_in_minimum_matches() -> None:
    # Each term of the tail sum is P(M >= m); requiring more matches can
    # only shrink (never grow) the qualifying draw set as m increases.
    pool_size, draw_size = 15, 5
    portfolio = ((1, 2, 3, 4, 5), (6, 7, 8, 9, 10))
    coverages = [
        fast_exact_portfolio_coverage(pool_size, draw_size, m, portfolio)
        for m in range(1, draw_size + 1)
    ]
    assert all(earlier >= later for earlier, later in itertools.pairwise(coverages))


def test_out_of_range_ticket_number_does_not_raise_but_is_out_of_contract() -> None:
    # Neither reused coverage evaluator validates ticket contents (see
    # `bounded_coverage_optimizer.exact_portfolio_coverage` and
    # `exact_coverage_fast_evaluator.fast_exact_portfolio_coverage`), so
    # `expected_max_main_matches` adds none either -- it never raises for a
    # malformed ticket. But this is *not* the same as being correct for one:
    # the frozen contract's domain is "P = exactly-k canonical portfolio",
    # i.e. every number already lies in `1..pool_size`, and a number outside
    # that range is genuinely out of contract for the default evaluator --
    # `fast_exact_portfolio_coverage` treats the ticket as its own candidate
    # pool member when building qualifying draws, so it disagrees with both
    # the literal `|t ∩ D|` definition and with `exact_portfolio_coverage`
    # (which stays correct here since its bitmask approach only ever tests
    # bits a real draw could set). This is a pre-existing characteristic of
    # the reused evaluator, not something this composition layer introduces
    # or is scoped to fix -- callers must only ever pass validated tickets.
    pool_size, draw_size = 10, 3
    portfolio = ((1, 2, 999),)
    default_result = expected_max_main_matches(pool_size, draw_size, portfolio)
    literal_definition = _brute_force_expected_max(pool_size, draw_size, portfolio)
    correct_evaluator_result = expected_max_main_matches(
        pool_size, draw_size, portfolio, evaluator=exact_portfolio_coverage
    )
    assert correct_evaluator_result == literal_definition
    assert default_result != literal_definition


def test_wrong_size_ticket_matches_literal_set_intersection_definition() -> None:
    # A ticket with fewer distinct numbers than draw_size is not rejected
    # either; it is scored the same as the literal definition would score
    # it (it can never contribute more matches than it has numbers).
    pool_size, draw_size = 10, 4
    portfolio = ((1, 2),)
    assert expected_max_main_matches(pool_size, draw_size, portfolio) == _brute_force_expected_max(
        pool_size, draw_size, portfolio
    )


def test_duplicate_ticket_in_portfolio_is_redundant() -> None:
    pool_size, draw_size = 12, 4
    single = ((1, 2, 3, 4),)
    duplicated = ((1, 2, 3, 4), (1, 2, 3, 4))
    assert expected_max_main_matches(pool_size, draw_size, duplicated) == expected_max_main_matches(
        pool_size, draw_size, single
    )
    assert expected_max_main_matches(pool_size, draw_size, duplicated) == _brute_force_expected_max(
        pool_size, draw_size, duplicated
    )
