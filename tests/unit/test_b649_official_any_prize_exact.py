"""Oracles for the exact BIG_LOTTO OFFICIAL_ANY_PRIZE portfolio evaluator."""

from __future__ import annotations

import itertools
import random
from fractions import Fraction
from math import comb

import numpy as np
import pytest

from lottolab.domain.lottery_rules import BigLottoPrizeTier, resolve_big_lotto_prize_tier
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    evaluate_single_ticket_closed_form,
    independent_random_official_any_prize,
)

SINGLE_TICKET_OFFICIAL_ANY_PRIZE = Fraction(7729, 249711)
SINGLE_TICKET_M3_PLUS = Fraction(4654, 249711)


@pytest.fixture(scope="module")
def big_lotto_draws() -> DrawMasks:
    return all_main_draw_masks(49, 6)


def test_big_lotto_draw_space_is_exactly_every_six_subset(big_lotto_draws: DrawMasks) -> None:
    assert big_lotto_draws.size == comb(49, 6)
    popcounts = np.bitwise_count(big_lotto_draws)
    assert int(popcounts.min()) == 6
    assert int(popcounts.max()) == 6
    assert int(big_lotto_draws.max()) < 1 << 49
    assert np.unique(big_lotto_draws).size == comb(49, 6)


def test_single_ticket_matches_the_committed_prize_table(big_lotto_draws: DrawMasks) -> None:
    # Outcome census for one fixed ticket by (main hits, special hit), priced through the
    # repository's sole prize-rule authority rather than this module's own rule text.
    winning_outcomes = 0
    for main_hits in range(7):
        draws = comb(6, main_hits) * comb(43, 6 - main_hits)
        specials_in_ticket = 6 - main_hits
        for special_hit, specials in ((True, specials_in_ticket), (False, 43 - specials_in_ticket)):
            if special_hit and specials == 0:
                continue
            tier = resolve_big_lotto_prize_tier(main_hits, special_hit)
            if isinstance(tier, BigLottoPrizeTier):
                winning_outcomes += draws * specials

    result = evaluate_portfolio([(1, 2, 3, 4, 5, 6)], draws=big_lotto_draws)

    assert Fraction(winning_outcomes, comb(49, 6) * 43) == SINGLE_TICKET_OFFICIAL_ANY_PRIZE
    assert result.official_any_prize_outcome_count == winning_outcomes
    assert result.official_any_prize == SINGLE_TICKET_OFFICIAL_ANY_PRIZE
    assert result.m3_plus == SINGLE_TICKET_M3_PLUS
    assert evaluate_single_ticket_closed_form() == SINGLE_TICKET_OFFICIAL_ANY_PRIZE


def _brute_force_winning_outcomes(
    portfolio: list[tuple[int, ...]], pool_size: int, draw_size: int, outright: int
) -> int:
    won = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        drawn = set(draw)
        for special in range(1, pool_size + 1):
            if special in drawn:
                continue
            for ticket in portfolio:
                hits = len(drawn.intersection(ticket))
                if hits >= outright or (hits == outright - 1 and special in ticket):
                    won += 1
                    break
    return won


def test_matches_brute_force_on_a_small_lottery() -> None:
    pool_size, draw_size, outright = 9, 3, 2
    draws = all_main_draw_masks(pool_size, draw_size)
    tickets = list(itertools.combinations(range(1, pool_size + 1), draw_size))
    rng = random.Random(20260919)
    cases = [rng.sample(tickets, rng.randint(1, 6)) for _ in range(60)]
    cases.append(tickets[:10])

    for portfolio in cases:
        result = evaluate_portfolio(
            portfolio,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright,
            draws=draws,
            chunk_size=7,
        )
        expected = _brute_force_winning_outcomes(portfolio, pool_size, draw_size, outright)
        assert result.official_any_prize_outcome_count == expected, portfolio


def test_relabeling_and_duplicate_tickets_leave_probability_unchanged(
    big_lotto_draws: DrawMasks,
) -> None:
    portfolio = [(1, 2, 3, 4, 5, 6), (4, 5, 6, 7, 8, 9), (10, 20, 30, 40, 41, 49)]
    permutation = list(range(1, 50))
    random.Random(7).shuffle(permutation)
    relabeled = [tuple(sorted(permutation[n - 1] for n in ticket)) for ticket in portfolio]

    base = evaluate_portfolio(portfolio, draws=big_lotto_draws)

    assert evaluate_portfolio(relabeled, draws=big_lotto_draws) == base
    assert evaluate_portfolio([*portfolio, portfolio[0]], draws=big_lotto_draws) == base


def test_independent_random_baseline_is_the_complement_power() -> None:
    assert independent_random_official_any_prize(1) == SINGLE_TICKET_OFFICIAL_ANY_PRIZE
    assert independent_random_official_any_prize(10) == 1 - (
        1 - SINGLE_TICKET_OFFICIAL_ANY_PRIZE
    ) ** 10


@pytest.mark.parametrize(
    "portfolio",
    [[], [(1, 2, 3, 4, 5)], [(1, 2, 3, 4, 5, 5)], [(0, 1, 2, 3, 4, 5)], [(1, 2, 3, 4, 5, 50)]],
)
def test_illegal_portfolios_are_rejected(portfolio: list[tuple[int, ...]]) -> None:
    with pytest.raises(ValueError):
        evaluate_portfolio(portfolio, draws=np.zeros(1, dtype=np.uint64))
