from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

from lottolab.research import (
    biglotto_cross_family_redundancy_pruned_ensemble_v1_candidate_batch_r1 as ensemble,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type History = tuple[Ticket, ...]
type CandidateProducer = Callable[[History, int], TicketPortfolio]

PORTFOLIO_NULL_OUTCOME_SPACE = 601_304_088


def _draw(seed: int) -> Ticket:
    numbers = sorted({((seed * 7 + offset * 9) % 49) + 1 for offset in range(6)})
    assert len(numbers) == 6
    return cast(Ticket, tuple(numbers))


def _history() -> History:
    return tuple(_draw(index) for index in range(ensemble.MINIMUM_HISTORY))


def _canonical(portfolio: TicketPortfolio) -> bytes:
    return json.dumps(portfolio, separators=(",", ":")).encode("utf-8")


def _assert_native_portfolio(portfolio: TicketPortfolio, budget: int) -> None:
    assert budget <= len(portfolio) <= budget * 3
    assert len(portfolio) == len(set(portfolio))
    assert all(
        isinstance(ticket, tuple)
        and len(ticket) == 6
        and ticket == tuple(sorted(ticket))
        and len(set(ticket)) == 6
        and all(type(number) is int and 1 <= number <= 49 for number in ticket)
        for ticket in portfolio
    )


def test_all_nine_frozen_candidates_execute_twice_canonically() -> None:
    history = _history()
    invocation_count = 0

    assert len(ensemble.CANDIDATE_AUTHORITIES) == 9
    assert tuple(ensemble.concrete_parent_producers()) == (
        "CONDITIONAL_COOCCURRENCE",
        "GRAPH_NETWORK",
        "MULTISCALE_OMISSION_PRESSURE",
    )
    assert PORTFOLIO_NULL_OUTCOME_SPACE == 601_304_088

    for metadata in ensemble.CANDIDATE_AUTHORITIES:
        producer = cast(CandidateProducer, getattr(ensemble, metadata.IMPLEMENTATION_SYMBOL))
        first = producer(history, ensemble.MINIMUM_HISTORY)
        invocation_count += 1
        second = producer(history, ensemble.MINIMUM_HISTORY)
        invocation_count += 1

        _assert_native_portfolio(first, metadata.TICKET_BUDGET)
        _assert_native_portfolio(second, metadata.TICKET_BUDGET)
        assert first == second
        assert _canonical(first) == _canonical(second)
        assert metadata.SEMANTICS["CONSTRUCTOR_ID"] == metadata.CONSTRUCTOR_ID
        assert metadata.SEMANTICS["REQUESTED_BUDGET"] == metadata.TICKET_BUDGET
        assert metadata.SEMANTICS["PARENT_MEMBERSHIP"] == (
            "CONDITIONAL_COOCCURRENCE",
            "GRAPH_NETWORK",
            "MULTISCALE_OMISSION_PRESSURE",
        )
        assert metadata.SEMANTICS["PRUNED_PARENT_FAMILIES"] == (
            "MULTISCALE_FREQUENCY",
        )

    assert invocation_count == 18
