"""Independent small-outcome oracle and move contracts for K20 exchange search."""

from __future__ import annotations

import itertools
from fractions import Fraction

import pytest

from lottolab.application.b649_sealed_geometry_portfolio import SEALED_GEOMETRY_PORTFOLIOS
from lottolab.research.b649_k20_exact_ticket_exchange import (
    ExchangeMove,
    apply_exchange,
    bounded_pilot_moves,
    canonical_portfolio,
    frequency_profile,
    scan_exchanges,
)

TOY_START = ((1, 2, 3), (1, 2, 4), (1, 2, 5))
PAIR_GAIN = ExchangeMove((1, 2), (1, 1), (6, 7))
TRIPLE_GAIN = ExchangeMove((0, 1, 2), (1, 1, 1), (6, 7, 8))
PAIR_TIE = ExchangeMove((1, 2), (4, 5), (6, 7))


def _brute_official_any_prize(portfolio: tuple[tuple[int, ...], ...]) -> Fraction:
    """Count every main/special outcome without using the collapsed evaluator."""

    wins = 0
    total = 0
    for draw in itertools.combinations(range(1, 10), 3):
        main = set(draw)
        for special in set(range(1, 10)) - main:
            total += 1
            if any(
                len(main.intersection(ticket)) >= 2
                or (len(main.intersection(ticket)) == 1 and special in ticket)
                for ticket in portfolio
            ):
                wins += 1
    return Fraction(wins, total)


def test_two_and_three_ticket_moves_are_scored_by_independent_outcome_census() -> None:
    pair = apply_exchange(TOY_START, PAIR_GAIN, pool_size=9, draw_size=3, ticket_count=3)
    triple = apply_exchange(TOY_START, TRIPLE_GAIN, pool_size=9, draw_size=3, ticket_count=3)
    assert pair != triple
    assert _brute_official_any_prize(TOY_START) == Fraction(83, 126)
    assert _brute_official_any_prize(pair) == Fraction(7, 9)
    assert _brute_official_any_prize(triple) == Fraction(7, 9)

    for moves in ((PAIR_GAIN, TRIPLE_GAIN), (TRIPLE_GAIN, PAIR_GAIN)):
        result = scan_exchanges(
            TOY_START,
            moves,
            max_proposals=2,
            outright_matches=2,
            pool_size=9,
            draw_size=3,
            ticket_count=3,
        )
        assert result.input_score.official_any_prize == _brute_official_any_prize(TOY_START)
        assert [row.score.official_any_prize for row in result.candidates] == [
            _brute_official_any_prize(row.portfolio) for row in result.candidates
        ]
        assert result.selected_portfolio == pair
        assert result.selected_move == PAIR_GAIN
        assert result.selected_score.official_any_prize == Fraction(7, 9)
        assert result.delta == Fraction(5, 42)
        assert result.strict_improvement


def test_equal_official_score_does_not_displace_incumbent() -> None:
    result = scan_exchanges(
        TOY_START,
        (PAIR_TIE,),
        max_proposals=1,
        outright_matches=2,
        pool_size=9,
        draw_size=3,
        ticket_count=3,
    )
    assert result.candidates[0].score.official_any_prize == result.input_score.official_any_prize
    assert result.selected_portfolio == canonical_portfolio(
        TOY_START, pool_size=9, draw_size=3, ticket_count=3
    )
    assert result.selected_move is None
    assert result.delta == 0
    assert not result.strict_improvement


def test_m3_gain_with_official_loss_is_rejected() -> None:
    start = ((1, 7, 9), (2, 3, 5), (3, 7, 9))
    move = ExchangeMove((0, 2), (7, 9), (3, 6))
    result = scan_exchanges(
        start,
        (move,),
        max_proposals=1,
        pool_size=9,
        draw_size=3,
        ticket_count=3,
        outright_matches=2,
    )
    candidate = result.candidates[0]
    assert _brute_official_any_prize(start) == Fraction(11, 14)
    assert _brute_official_any_prize(candidate.portfolio) == Fraction(7, 9)
    assert result.input_score.m3_plus == Fraction(11, 21)
    assert candidate.score.m3_plus == Fraction(15, 28)
    assert candidate.score.m3_plus > result.input_score.m3_plus
    assert candidate.score.official_any_prize < result.input_score.official_any_prize
    assert result.selected_portfolio == canonical_portfolio(
        start, pool_size=9, draw_size=3, ticket_count=3
    )
    assert not result.strict_improvement


@pytest.mark.parametrize(
    "move",
    [
        ExchangeMove((1, 1), (1, 1), (6, 7)),
        ExchangeMove((2, 1), (1, 1), (6, 7)),
        ExchangeMove((1, 2), (9, 1), (6, 7)),
        ExchangeMove((1, 2), (1, 1), (2, 7)),
        ExchangeMove((1, 2), (4, 5), (6, 6)),
    ],
)
def test_illegal_or_duplicate_exchange_is_rejected(move: ExchangeMove) -> None:
    with pytest.raises(ValueError):
        apply_exchange(TOY_START, move, pool_size=9, draw_size=3, ticket_count=3)


def test_budget_and_repeated_endpoint_fail_closed() -> None:
    with pytest.raises(ValueError, match="budget"):
        scan_exchanges(
            TOY_START,
            (PAIR_GAIN, TRIPLE_GAIN),
            max_proposals=1,
            pool_size=9,
            draw_size=3,
            ticket_count=3,
        )
    same_endpoint = ExchangeMove((1, 2), (1, 1), (6, 7), mode="SAME_ENDPOINT")
    with pytest.raises(ValueError, match="repeated endpoint"):
        scan_exchanges(
            TOY_START,
            (PAIR_GAIN, same_endpoint),
            max_proposals=2,
            outright_matches=2,
            pool_size=9,
            draw_size=3,
            ticket_count=3,
        )


@pytest.mark.parametrize("arity", [2, 3])
def test_pilot_proposes_both_on_face_and_off_face_endpoints(arity: int) -> None:
    start = canonical_portfolio(SEALED_GEOMETRY_PORTFOLIOS[20].tickets)
    first = bounded_pilot_moves(start, arity=arity)
    assert first == bounded_pilot_moves(start, arity=arity)
    assert [move.mode for move in first] == ["NUMBER_CYCLE", "EXTERNAL_SUBSTITUTION"]
    cycle, external = (apply_exchange(start, move) for move in first)
    assert frequency_profile(cycle) == frequency_profile(start)
    assert frequency_profile(external) != frequency_profile(start)
    assert len({start, cycle, external}) == 3
