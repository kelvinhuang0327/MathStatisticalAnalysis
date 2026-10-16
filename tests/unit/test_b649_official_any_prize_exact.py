"""Oracles for the exact BIG_LOTTO OFFICIAL_ANY_PRIZE portfolio evaluator."""

from __future__ import annotations

import itertools
import random
from fractions import Fraction
from math import comb
from typing import NoReturn, cast

import numpy as np
import pytest

from lottolab.domain.lottery_rules import BigLottoPrizeTier, resolve_big_lotto_prize_tier
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    evaluate_single_ticket_closed_form,
    independent_random_official_any_prize,
    validate_main_draw_masks,
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


def test_toy_complete_draw_space_has_nine_winning_outcomes() -> None:
    expected = _brute_force_winning_outcomes([(1, 2)], 5, 2, 2)
    assert expected == 9
    result = evaluate_portfolio(
        [(1, 2)],
        pool_size=5,
        draw_size=2,
        outright_matches=2,
        draws=all_main_draw_masks(5, 2),
    )
    assert result.main_draw_count * result.special_count == 30
    assert result.official_any_prize_outcome_count == expected
    assert result.official_any_prize == Fraction(9, 30)


def test_repeated_main_draws_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        evaluate_portfolio(
            [(1, 2)],
            pool_size=5,
            draw_size=2,
            outright_matches=2,
            draws=np.full(10, 3, dtype=np.uint64),
        )


@pytest.mark.parametrize("order", ["original", "shuffled", "strided", "reversed"])
def test_external_complete_spaces_match_independent_oracle(order: str) -> None:
    draws = np.array(
        [sum(1 << (n - 1) for n in d) for d in itertools.combinations(range(1, 6), 2)],
        dtype=np.uint64,
    )
    if order == "shuffled":
        np.random.default_rng(17).shuffle(draws)
    elif order == "strided":
        draws = np.repeat(draws, 2)[::2]
    elif order == "reversed":
        draws = draws[::-1]
    for portfolio in [[(1, 2)], [(1, 2), (1, 2)], [(1, 2), (3, 5)]]:
        expected = _brute_force_winning_outcomes(portfolio, 5, 2, 2)
        expected_main = sum(
            any(len(set(d).intersection(t)) >= 2 for t in portfolio)
            for d in itertools.combinations(range(1, 6), 2)
        )
        for space in (draws, validate_main_draw_masks(draws, 5, 2)):
            result = evaluate_portfolio(
                portfolio,
                pool_size=5,
                draw_size=2,
                outright_matches=2,
                draws=space,
                chunk_size=3,
            )
            assert result.main_draw_count == 10
            assert result.special_count == 3
            assert result.m3_plus_draw_count == expected_main
            assert result.official_any_prize_outcome_count == expected
            assert result.official_any_prize == Fraction(expected, 30)


@pytest.mark.parametrize(
    ("replacement", "message"),
    [(5, "unique"), (33, "outside"), (1, "exactly draw_size"), (7, "exactly draw_size")],
)
def test_invalid_masks_with_correct_row_count_are_rejected(replacement: int, message: str) -> None:
    draws = np.array(all_main_draw_masks(5, 2))
    draws[0] = replacement  # Original first two entries are 3 and 5.
    assert draws.size == 10
    with pytest.raises(ValueError, match=message):
        evaluate_portfolio(
            [(1, 2)],
            pool_size=5,
            draw_size=2,
            outright_matches=2,
            draws=draws,
        )
    with pytest.raises(ValueError, match=message):
        validate_main_draw_masks(draws, 5, 2)


@pytest.mark.parametrize(
    "draws",
    [
        np.full((2, 5), 3, dtype=np.uint64),
        np.array(3, dtype=np.uint64),
        np.full(10, 3, dtype=np.int64),
        np.full(10, 3, dtype=np.uint32),
        np.full(10, 3, dtype=np.float64),
        np.full(10, 3, dtype=object),
        np.full(10, True, dtype=np.bool_),
        [3] * 10,
    ],
)
def test_invalid_draw_dimensions_and_dtypes_are_rejected(draws: object) -> None:
    with pytest.raises(ValueError, match=r"one-dimensional|uint64"):
        evaluate_portfolio(
            [(1, 2)],
            pool_size=5,
            draw_size=2,
            outright_matches=2,
            draws=cast(DrawMasks, draws),
        )


@pytest.mark.parametrize("size", [0, 9, 11])
def test_incomplete_draw_space_cardinality_is_rejected(size: int) -> None:
    with pytest.raises(ValueError, match="complete"):
        evaluate_portfolio(
            [(1, 2)],
            pool_size=5,
            draw_size=2,
            outright_matches=2,
            draws=np.full(size, 3, dtype=np.uint64),
        )


def test_verified_snapshot_is_isolated_from_mutable_input() -> None:
    source = np.array(all_main_draw_masks(5, 2))
    alias = source.view()
    source.setflags(write=False)
    snapshot = validate_main_draw_masks(source, 5, 2)
    kwargs = dict(pool_size=5, draw_size=2, outright_matches=2)
    baseline = evaluate_portfolio([(1, 2)], draws=snapshot, **kwargs)
    assert evaluate_portfolio([(1, 2)], draws=source, **kwargs) == baseline
    alias[0] = alias[1]
    assert baseline.official_any_prize_outcome_count == 9
    assert evaluate_portfolio([(1, 2)], draws=snapshot, **kwargs) == baseline
    with pytest.raises(ValueError, match="unique"):
        evaluate_portfolio([(1, 2)], draws=source, **kwargs)
    with pytest.raises(ValueError, match="unique"):
        validate_main_draw_masks(source, 5, 2)
    for space in (snapshot, all_main_draw_masks(5, 2)):
        with pytest.raises(ValueError):
            space[0] = space[1]
        with pytest.raises(ValueError):
            space.setflags(write=True)
        with pytest.raises(ValueError):
            np.asarray(space).setflags(write=True)


def test_mutable_derived_array_cannot_inherit_trust() -> None:
    snapshot = validate_main_draw_masks(np.array(all_main_draw_masks(5, 2)), 5, 2)
    derived = snapshot.copy()
    derived[0] = derived[1]
    with pytest.raises(ValueError, match="unique"):
        evaluate_portfolio(
            [(1, 2)],
            pool_size=5,
            draw_size=2,
            outright_matches=2,
            draws=derived,
        )


@pytest.mark.parametrize("trusted", [True, False])
def test_draw_space_must_match_current_parameters(trusted: bool) -> None:
    draws = all_main_draw_masks(5, 2)
    if not trusted:
        draws = np.array(draws)
    # C(5, 2) == C(5, 3): length alone cannot bind draw_size.
    with pytest.raises(ValueError, match=r"parameters|exactly draw_size"):
        evaluate_portfolio(
            [(1, 2, 3)],
            pool_size=5,
            draw_size=3,
            outright_matches=2,
            draws=draws,
        )
    # A pool mismatch with equal cardinality: C(6, 1) == C(4, 2).
    with pytest.raises(ValueError, match="parameters"):
        validate_main_draw_masks(all_main_draw_masks(6, 1), 4, 2)


def test_trusted_reuse_skips_full_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    generated = all_main_draw_masks(5, 2)
    verified = validate_main_draw_masks(np.array(generated), 5, 2)

    def unexpected(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("trusted reuse performed full validation")

    monkeypatch.setattr(np, "unique", unexpected)
    monkeypatch.setattr(np, "any", unexpected)
    for space in (generated, verified):
        assert validate_main_draw_masks(space, 5, 2) is space
        for _ in range(2):
            result = evaluate_portfolio(
                [(1, 2)],
                pool_size=5,
                draw_size=2,
                outright_matches=2,
                draws=space,
            )
            assert result.official_any_prize_outcome_count == 9


@pytest.mark.parametrize(
    ("attribute", "value", "message"),
    [("shape", (2, 5), "one-dimensional"), ("dtype", np.dtype(np.int64), "uint64")],
)
def test_trusted_array_metadata_changes_do_not_bypass_contract(
    attribute: str, value: object, message: str
) -> None:
    draws = all_main_draw_masks(5, 2)
    setattr(draws, attribute, value)
    with pytest.raises(ValueError, match=message):
        evaluate_portfolio(
            [(1, 2)],
            pool_size=5,
            draw_size=2,
            outright_matches=2,
            draws=draws,
        )


def test_uint64_high_bit_is_a_legal_pool_number() -> None:
    draws = np.array(all_main_draw_masks(64, 1))
    result = evaluate_portfolio(
        [(64,)],
        pool_size=64,
        draw_size=1,
        outright_matches=1,
        draws=draws,
    )
    expected = _brute_force_winning_outcomes([(64,)], 64, 1, 1)
    assert result.official_any_prize_outcome_count == expected == 126


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
    assert (
        independent_random_official_any_prize(10)
        == 1 - (1 - SINGLE_TICKET_OFFICIAL_ANY_PRIZE) ** 10
    )


@pytest.mark.parametrize(
    "portfolio",
    [[], [(1, 2, 3, 4, 5)], [(1, 2, 3, 4, 5, 5)], [(0, 1, 2, 3, 4, 5)], [(1, 2, 3, 4, 5, 50)]],
)
def test_illegal_portfolios_are_rejected(portfolio: list[tuple[int, ...]]) -> None:
    with pytest.raises(ValueError):
        evaluate_portfolio(portfolio, draws=np.zeros(1, dtype=np.uint64))
