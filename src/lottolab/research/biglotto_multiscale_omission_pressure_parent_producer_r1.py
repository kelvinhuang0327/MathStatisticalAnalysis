"""Concrete causal-history provider for the frozen Omission Pressure parent."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _authority,
)

type HistoryInput = Sequence[object] | Iterable[object]
type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]

FROZEN_PARENT_AUTHORITY_HEAD: Final[str] = (
    "7a032ef471fdb176b3149e3dfc34e815bf57522c"
)
FROZEN_PARENT_AUTHORITY_TREE: Final[str] = (
    "e4f4ef70212d6e6126e384e2b3db6a0f314ad014"
)
FROZEN_PARENT_SOURCE_SHA256: Final[str] = (
    "1da8b5384830f94a7846b3db56b106d1722d75cf386d0c4f75e4d1ce93a7dc4c"
)
MINIMUM_HISTORY: Final[int] = _authority.MINIMUM_HISTORY
SOURCE_WINDOWS: Final[tuple[int, int, int]] = _authority.SOURCE_WINDOWS


def produce_biglotto_multiscale_omission_pressure_parent_portfolio(
    history: HistoryInput,
    target_index: int,
    constructor_id: str,
    ticket_budget: int,
) -> TicketPortfolio:
    """Produce one native Omission Pressure portfolio from prior history."""

    candidate_id = _authority.candidate_id_for(constructor_id, ticket_budget)
    return _authority.produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate(
        candidate_id,
        history,
        target_index,
    )


produce_parent_portfolio = produce_biglotto_multiscale_omission_pressure_parent_portfolio


__all__ = [
    "FROZEN_PARENT_AUTHORITY_HEAD",
    "FROZEN_PARENT_AUTHORITY_TREE",
    "FROZEN_PARENT_SOURCE_SHA256",
    "MINIMUM_HISTORY",
    "SOURCE_WINDOWS",
    "produce_biglotto_multiscale_omission_pressure_parent_portfolio",
    "produce_parent_portfolio",
]
