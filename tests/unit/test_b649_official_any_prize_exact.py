"""Oracles for the exact BIG_LOTTO OFFICIAL_ANY_PRIZE portfolio evaluator."""

from __future__ import annotations

import dataclasses
import itertools
import pickle
import random
from dataclasses import FrozenInstanceError
from fractions import Fraction
from math import comb

import numpy as np
import pytest

import lottolab.research.b649_official_any_prize_exact as exact_module
from lottolab.domain.lottery_rules import BigLottoPrizeTier, resolve_big_lotto_prize_tier
from lottolab.research.b649_official_any_prize_exact import (
    CompleteDrawSpace,
    DrawMasks,
    ExactPortfolioProbability,
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
    assert evaluate_portfolio(portfolio, draws=CompleteDrawSpace(big_lotto_draws)) == base


_TOY_POOL_SIZE, _TOY_DRAW_SIZE, _TOY_OUTRIGHT = 5, 2, 2
_TOY_PORTFOLIO: list[tuple[int, ...]] = [(1, 2)]


def _toy_draws_by_enumeration() -> DrawMasks:
    # Straight from itertools, sharing no code with the evaluator's own draw-space builder.
    # Order: 12 13 14 15 23 24 25 34 35 45, so index 9 is mask 24 = {4, 5}.
    return np.array(
        [
            sum(1 << (number - 1) for number in draw)
            for draw in itertools.combinations(range(1, _TOY_POOL_SIZE + 1), _TOY_DRAW_SIZE)
        ],
        dtype=np.uint64,
    )


def _toy_draws_with(index: int, mask: int) -> DrawMasks:
    draws = _toy_draws_by_enumeration()
    draws[index] = mask
    return draws


def _toy_evaluate(draws: object) -> ExactPortfolioProbability:
    return evaluate_portfolio(
        _TOY_PORTFOLIO,
        pool_size=_TOY_POOL_SIZE,
        draw_size=_TOY_DRAW_SIZE,
        outright_matches=_TOY_OUTRIGHT,
        draws=draws,  # pyright: ignore[reportArgumentType]
    )


def _toy_space(masks: object) -> CompleteDrawSpace:
    return CompleteDrawSpace(masks, _TOY_POOL_SIZE, _TOY_DRAW_SIZE)  # pyright: ignore[reportArgumentType]


def test_toy_complete_draw_space_matches_direct_enumeration() -> None:
    oracle = _brute_force_winning_outcomes(
        _TOY_PORTFOLIO, _TOY_POOL_SIZE, _TOY_DRAW_SIZE, _TOY_OUTRIGHT
    )
    enumerated = _toy_draws_by_enumeration()
    shuffled = enumerated[np.random.default_rng(20261016).permutation(enumerated.size)]
    assert oracle == 9
    assert not np.array_equal(shuffled, enumerated)

    for draws in (
        None,
        enumerated,
        shuffled,
        all_main_draw_masks(_TOY_POOL_SIZE, _TOY_DRAW_SIZE),
        _toy_space(enumerated),
        _toy_space(shuffled),
        CompleteDrawSpace.build(_TOY_POOL_SIZE, _TOY_DRAW_SIZE),
    ):
        result = _toy_evaluate(draws)
        assert result.main_draw_count == 10
        assert result.official_any_prize_outcome_count == oracle
        assert result.official_any_prize == Fraction(9, 30)


@pytest.mark.parametrize(
    ("draws", "reason"),
    [
        # Ten copies of mask 3 = {1, 2}: the length of C(5, 2), formerly scored as 30 / 30.
        pytest.param(np.full(10, 3, dtype=np.uint64), "repeat", id="one-draw-ten-times"),
        pytest.param(_toy_draws_with(9, 3), "repeat", id="one-duplicated-one-missing"),
        pytest.param(_toy_draws_with(9, 0b100001), "outside", id="number-6-in-pool-5"),
        pytest.param(_toy_draws_with(9, (1 << 63) | 1), "outside", id="number-64-in-pool-5"),
        pytest.param(_toy_draws_with(9, 0b111), "exactly 2", id="three-numbers"),
        pytest.param(_toy_draws_with(9, 0b1), "exactly 2", id="one-number"),
        pytest.param(_toy_draws_with(9, 0), "exactly 2", id="no-numbers"),
    ],
)
def test_right_length_draws_that_are_not_the_complete_space_are_rejected(
    draws: DrawMasks, reason: str
) -> None:
    with pytest.raises(ValueError, match=reason):
        _toy_evaluate(draws)
    with pytest.raises(ValueError, match=reason):
        _toy_space(draws)


@pytest.mark.parametrize(
    ("draws", "error"),
    [
        pytest.param(_toy_draws_by_enumeration().reshape(2, 5), ValueError, id="2-d"),
        pytest.param(np.array(3, dtype=np.uint64), ValueError, id="0-d"),
        pytest.param(_toy_draws_by_enumeration()[:-1], ValueError, id="one-draw-short"),
        pytest.param(all_main_draw_masks(6, 2), ValueError, id="pool-6-space"),
        pytest.param(_toy_draws_by_enumeration().astype(np.int64), TypeError, id="int64"),
        pytest.param(
            _toy_draws_by_enumeration().astype(np.dtype(np.uint64).newbyteorder()),
            TypeError,
            id="non-native-byte-order",
        ),
        pytest.param(_toy_draws_by_enumeration().tolist(), TypeError, id="python-list"),
    ],
)
def test_draws_outside_the_entry_contract_are_rejected(
    draws: object, error: type[Exception]
) -> None:
    with pytest.raises(error):
        _toy_evaluate(draws)
    with pytest.raises(error):
        _toy_space(draws)


def test_draw_space_for_other_lottery_parameters_is_rejected() -> None:
    toy = _toy_draws_by_enumeration()
    for draws in (toy, _toy_space(toy)):
        with pytest.raises(ValueError):
            evaluate_portfolio(
                _TOY_PORTFOLIO, pool_size=6, draw_size=2, outright_matches=2, draws=draws
            )


def test_verified_draws_do_not_vouch_for_later_edits() -> None:
    source = _toy_draws_by_enumeration()
    space = _toy_space(source)
    assert _toy_evaluate(source).official_any_prize_outcome_count == 9

    source[9] = source[0]  # same length: {1, 2} twice, {4, 5} gone

    with pytest.raises(ValueError, match="repeat"):
        _toy_evaluate(source)
    assert _toy_evaluate(space).official_any_prize_outcome_count == 9
    source[9] = 0b11000
    assert _toy_evaluate(source).official_any_prize_outcome_count == 9

    with pytest.raises(ValueError):
        space.masks[0] = 3
    with pytest.raises(ValueError):
        space.masks.flags.writeable = True
    with pytest.raises(FrozenInstanceError):
        space.masks = source  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(ValueError, match="repeat"):
        dataclasses.replace(space, masks=np.full(10, 3, dtype=np.uint64))
    restored = pickle.loads(pickle.dumps(space))
    assert not restored.masks.flags.writeable
    assert _toy_evaluate(restored).official_any_prize_outcome_count == 9


def test_reused_draw_space_is_fully_validated_once(monkeypatch: pytest.MonkeyPatch) -> None:
    validate = exact_module._verified_snapshot  # pyright: ignore[reportPrivateUsage]
    calls: list[int] = []

    def counting_validate(draws: object, pool_size: int, draw_size: int) -> DrawMasks:
        calls.append(pool_size)
        return validate(draws, pool_size, draw_size)

    monkeypatch.setattr(exact_module, "_verified_snapshot", counting_validate)
    space = _toy_space(_toy_draws_by_enumeration())
    raw = _toy_draws_by_enumeration()
    for _ in range(3):
        assert _toy_evaluate(space).official_any_prize_outcome_count == 9
        assert _toy_evaluate(raw).official_any_prize_outcome_count == 9
    assert len(calls) == 2  # constructing ``space`` and the first use of ``raw``

    raw[9] = raw[0]
    with pytest.raises(ValueError, match="repeat"):
        _toy_evaluate(raw)
    assert len(calls) == 3


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
