"""Exactness and bounded scale checks for portfolio delta evaluation."""

from __future__ import annotations

import itertools
from typing import cast

import numpy as np
import pytest

from lottolab.research.b649_official_any_prize_delta import ExactPortfolioDeltaEvaluator
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

_SMALL_POOL_SIZE = 5
_SMALL_DRAW_SIZE = 3
_SMALL_OUTRIGHT_MATCHES = 2
_SMALL_TICKETS = tuple(itertools.combinations(range(1, _SMALL_POOL_SIZE + 1), 3))


def _canonical(
    portfolio: tuple[tuple[int, ...], ...] | list[tuple[int, ...]],
    *,
    pool_size: int,
    draw_size: int,
    outright_matches: int,
    draws: DrawMasks,
    chunk_size: int = 1 << 21,
) -> ExactPortfolioProbability:
    return evaluate_portfolio(
        portfolio,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=draws,
        chunk_size=chunk_size,
    )


def test_exhaustive_small_domain_add_remove_replace_match_canonical() -> None:
    draws = all_main_draw_masks(
        _SMALL_POOL_SIZE,
        _SMALL_DRAW_SIZE,
    )
    evaluator = ExactPortfolioDeltaEvaluator(
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=draws,
        chunk_size=7,
    )

    for base in itertools.combinations_with_replacement(_SMALL_TICKETS, 2):
        for ticket in _SMALL_TICKETS:
            assert evaluator.add(base, ticket) == _canonical(
                [*base, ticket],
                pool_size=_SMALL_POOL_SIZE,
                draw_size=_SMALL_DRAW_SIZE,
                outright_matches=_SMALL_OUTRIGHT_MATCHES,
                draws=evaluator.draws,
            )
        for old_ticket in base:
            expected_removed = list(base)
            expected_removed.remove(old_ticket)
            assert evaluator.remove(base, old_ticket) == _canonical(
                expected_removed,
                pool_size=_SMALL_POOL_SIZE,
                draw_size=_SMALL_DRAW_SIZE,
                outright_matches=_SMALL_OUTRIGHT_MATCHES,
                draws=evaluator.draws,
            )
            for new_ticket in _SMALL_TICKETS:
                expected_replaced = list(base)
                expected_replaced[expected_replaced.index(old_ticket)] = new_ticket
                assert evaluator.replace(base, old_ticket, new_ticket) == _canonical(
                    expected_replaced,
                    pool_size=_SMALL_POOL_SIZE,
                    draw_size=_SMALL_DRAW_SIZE,
                    outright_matches=_SMALL_OUTRIGHT_MATCHES,
                    draws=evaluator.draws,
                )


def test_rescue_union_counts_a_special_only_once() -> None:
    pool_size, draw_size, outright_matches = 6, 3, 3
    draws = all_main_draw_masks(pool_size, draw_size)
    portfolio = [(1, 2, 4), (1, 3, 4)]
    evaluator = ExactPortfolioDeltaEvaluator(
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=draws,
        chunk_size=7,
    )

    result = evaluator.evaluate(portfolio)
    expected = _canonical(
        portfolio,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=evaluator.draws,
        chunk_size=7,
    )

    assert result == expected
    draw = 0b000111
    first_rescue = 0b001011 & ~draw
    second_rescue = 0b001101 & ~draw
    assert first_rescue == second_rescue == 0b001000
    assert first_rescue.bit_count() + second_rescue.bit_count() == 2
    assert (first_rescue | second_rescue).bit_count() == 1


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 8, 9, 13])
def test_arbitrary_chunk_boundaries_match_canonical(chunk_size: int) -> None:
    draws = all_main_draw_masks(_SMALL_POOL_SIZE, _SMALL_DRAW_SIZE)
    base = [_SMALL_TICKETS[0], _SMALL_TICKETS[-1]]
    added = _SMALL_TICKETS[3]
    evaluator = ExactPortfolioDeltaEvaluator(
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=draws,
        chunk_size=chunk_size,
    )
    assert evaluator.add(base, added) == _canonical(
        [*base, added],
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=evaluator.draws,
        chunk_size=chunk_size,
    )
    assert evaluator.remove(base, base[0]) == _canonical(
        base[1:],
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=evaluator.draws,
        chunk_size=chunk_size,
    )
    assert evaluator.replace(base, base[0], added) == evaluate_portfolio(
        [added, base[1]],
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=evaluator.draws,
        chunk_size=chunk_size,
    )


def test_duplicate_and_no_op_edits_are_inert() -> None:
    draws = all_main_draw_masks(_SMALL_POOL_SIZE, _SMALL_DRAW_SIZE)
    ticket, other = _SMALL_TICKETS[0], _SMALL_TICKETS[1]
    base = [ticket, ticket]
    evaluator = ExactPortfolioDeltaEvaluator(
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=draws,
        chunk_size=3,
    )
    expected_single = evaluate_portfolio(
        [ticket],
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=evaluator.draws,
        chunk_size=3,
    )

    assert evaluator.add([ticket], ticket) == expected_single
    assert evaluator.remove(base, ticket) == expected_single
    assert evaluator.replace([ticket], ticket, ticket) == expected_single
    assert evaluator.add([ticket], other) == evaluate_portfolio(
        [ticket, other],
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=evaluator.draws,
        chunk_size=3,
    )


def test_cache_snapshot_is_immutable_and_invalid_edits_fail_closed() -> None:
    source_draws = all_main_draw_masks(_SMALL_POOL_SIZE, _SMALL_DRAW_SIZE)
    evaluator = ExactPortfolioDeltaEvaluator(
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=source_draws,
        chunk_size=5,
    )
    base = [_SMALL_TICKETS[0], _SMALL_TICKETS[-1]]
    cached_base = evaluator.evaluate(base)
    assert evaluator.cached_ticket_count == 2

    expected_draws = evaluator.draws.copy()
    source_draws[:] = 0
    assert not evaluator.draws.flags.writeable
    with pytest.raises(ValueError):
        evaluator.draws[0] = np.uint64(0)

    added = _SMALL_TICKETS[3]
    assert evaluator.add(base, added) == evaluate_portfolio(
        [*base, added],
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=expected_draws,
        chunk_size=5,
    )
    assert cached_base == evaluate_portfolio(
        base,
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=expected_draws,
        chunk_size=5,
    )

    second_evaluator = ExactPortfolioDeltaEvaluator(
        pool_size=_SMALL_POOL_SIZE,
        draw_size=_SMALL_DRAW_SIZE,
        outright_matches=_SMALL_OUTRIGHT_MATCHES,
        draws=expected_draws,
        chunk_size=5,
    )
    assert second_evaluator.cached_ticket_count == 0
    assert second_evaluator.evaluate(base) == cached_base
    assert second_evaluator.cached_ticket_count == 2

    with pytest.raises(ValueError, match="complete main-draw"):
        ExactPortfolioDeltaEvaluator(
            pool_size=_SMALL_POOL_SIZE,
            draw_size=_SMALL_DRAW_SIZE,
            outright_matches=_SMALL_OUTRIGHT_MATCHES,
            draws=np.zeros(1, dtype=np.uint64),
        )
    with pytest.raises(ValueError, match="uint64"):
        ExactPortfolioDeltaEvaluator(
            pool_size=_SMALL_POOL_SIZE,
            draw_size=_SMALL_DRAW_SIZE,
            outright_matches=_SMALL_OUTRIGHT_MATCHES,
            draws=cast(DrawMasks, np.zeros(10, dtype=np.int64)),
        )
    with pytest.raises(ValueError, match="not present"):
        evaluator.remove(base, _SMALL_TICKETS[1])
    with pytest.raises(ValueError, match="at least one"):
        evaluator.remove([_SMALL_TICKETS[0]], _SMALL_TICKETS[0])
    with pytest.raises(ValueError, match="not present"):
        evaluator.replace(base, _SMALL_TICKETS[1], _SMALL_TICKETS[2])


@pytest.mark.parametrize("ticket_count", [10, 20])
def test_bounded_real_scale_add_remove_replace_equal_canonical(ticket_count: int) -> None:
    draws = all_main_draw_masks(49, 6)
    base = [
        tuple(((start + step * 7) % 49) + 1 for step in range(6))
        for start in range(ticket_count)
    ]
    candidate = tuple(((ticket_count + 3 + step * 7) % 49) + 1 for step in range(6))
    evaluator = ExactPortfolioDeltaEvaluator(draws=draws)
    canonical_draws = evaluator.draws

    additions = [*base, candidate]
    removal = list(base[1:])
    replacement = [*base[:-1], candidate]

    assert evaluator.add(base, candidate) == evaluate_portfolio(
        additions, draws=canonical_draws
    )
    assert evaluator.remove(base, base[0]) == evaluate_portfolio(
        removal, draws=canonical_draws
    )
    assert evaluator.replace(base, base[-1], candidate) == evaluate_portfolio(
        replacement, draws=canonical_draws
    )
