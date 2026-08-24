"""Concrete causal-history provider for the frozen Graph Network parent."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from lottolab.research import biglotto_graph_network_multi_ticket_candidate_batch_r1 as _authority

type HistoryInput = Sequence[object] | Iterable[object]
type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]

FROZEN_PARENT_AUTHORITY_HEAD: Final[str] = (
    "cf2821b2c63a40e9743230cf760168a39ebbbf0b"
)
FROZEN_PARENT_AUTHORITY_TREE: Final[str] = (
    "f0e369e4c4d62fec215abf96637fb24d8bb81239"
)
FROZEN_PARENT_SOURCE_SHA256: Final[str] = (
    "252ac7a477bc10455932da07541d2aa22153d879673d9f5abfa1ccf1df60f005"
)
MINIMUM_HISTORY: Final[int] = _authority.MINIMUM_HISTORY
SOURCE_WINDOWS: Final[tuple[int, int, int]] = _authority.SOURCE_WINDOWS


def produce_biglotto_graph_network_parent_portfolio(
    history: HistoryInput,
    target_index: int,
    constructor_id: str,
    ticket_budget: int,
) -> TicketPortfolio:
    """Produce one native Graph portfolio from strictly prior history."""

    candidate_id = _authority.candidate_id_for(constructor_id, ticket_budget)
    return _authority.produce_biglotto_graph_network_multi_ticket_candidate(
        candidate_id,
        history,
        target_index,
    )


produce_parent_portfolio = produce_biglotto_graph_network_parent_portfolio


__all__ = [
    "FROZEN_PARENT_AUTHORITY_HEAD",
    "FROZEN_PARENT_AUTHORITY_TREE",
    "FROZEN_PARENT_SOURCE_SHA256",
    "MINIMUM_HISTORY",
    "SOURCE_WINDOWS",
    "produce_biglotto_graph_network_parent_portfolio",
    "produce_parent_portfolio",
]
