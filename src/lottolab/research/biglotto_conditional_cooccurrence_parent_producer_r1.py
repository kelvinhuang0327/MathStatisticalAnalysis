"""Concrete causal-history provider for frozen Conditional Cooccurrence.

This module is intentionally only an execution adapter.  The ranking and
portfolio-construction semantics remain in the byte-identical frozen parent
authority module named below.  No database, date, outcome, or scoring input
is consulted.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as _authority,
)

type HistoryInput = Sequence[object] | Iterable[object]
type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]

FROZEN_PARENT_AUTHORITY_HEAD: Final[str] = (
    "89c9f2312d9cd8cf41c9573372dadf89a589366b"
)
FROZEN_PARENT_AUTHORITY_TREE: Final[str] = (
    "8502ed103da49d2e5cc539e8082d395ff8fdd851"
)
FROZEN_PARENT_SOURCE_SHA256: Final[str] = (
    "2f9afa24fa80737dc7b47d009dffdd6f343b9e187cd3eeb8349457b9fb5ca656"
)
MINIMUM_HISTORY: Final[int] = _authority.MINIMUM_HISTORY
SOURCE_WINDOWS: Final[tuple[int, int, int]] = _authority.SOURCE_WINDOWS


def produce_biglotto_conditional_cooccurrence_parent_portfolio(
    history: HistoryInput,
    target_index: int,
    constructor_id: str,
    ticket_budget: int,
) -> TicketPortfolio:
    """Produce one native parent portfolio from strictly prior history."""

    candidate_id = _authority.candidate_id_for(constructor_id, ticket_budget)
    return _authority.produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id,
        history,
        target_index,
    )


produce_parent_portfolio = produce_biglotto_conditional_cooccurrence_parent_portfolio


__all__ = [
    "FROZEN_PARENT_AUTHORITY_HEAD",
    "FROZEN_PARENT_AUTHORITY_TREE",
    "FROZEN_PARENT_SOURCE_SHA256",
    "MINIMUM_HISTORY",
    "SOURCE_WINDOWS",
    "produce_biglotto_conditional_cooccurrence_parent_portfolio",
    "produce_parent_portfolio",
]
