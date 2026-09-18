"""Frozen, outcome-free ``LOO_STABILITY_TIEBREAK_V1`` research candidate.

Branch 2 calls ``build_loo_stability_tiebreak(candidates)`` with the same
PRE_DRAW candidate pool and causal cutoff as the raw-majority baseline:
``build_portfolio(candidates, {}, bucket_sizes=(k,))`` for each feasible K.
The caller owns that causal cutoff; this module neither loads nor scores data.

Each LOO run ranks *all* remaining distinct tickets using the existing selector
with an empty quality mapping. Diagnostics supply canonical ticket support and
the observed distinct counts. A missing ticket gets that omission's count + 1,
including penalty 1 for an empty omission. No budget truncates the LOO ranks.

For S distinct streams, full-ranking survival is S for support >= 2 and S - 1
for support 1. It therefore cannot distinguish equal-support tickets in these
inputs, but remains the second frozen sort dimension. No tuning is implied.
Budget nesting is construction only, not evidence of stability or prediction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median
from typing import Final, Literal

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.research.b649_rank_stability import compute_stream_support_matrix

METHOD_ID: Final = "LOO_STABILITY_TIEBREAK_V1"
BUDGETS: Final[tuple[int, ...]] = (2, 3, 5, 10, 20)


@dataclass(frozen=True)
class LooTicketRank:
    ticket: Ticket
    distinct_stream_support: int
    loo_survival: int
    loo_median_rank: float
    loo_worst_rank: int
    penalized_rank_by_omission: tuple[tuple[str, int], ...]


def frozen_sort_key(row: LooTicketRank) -> tuple[int, int, float, int, Ticket]:
    """One lexicographic key; raw support always takes precedence."""
    return (
        -row.distinct_stream_support,
        -row.loo_survival,
        row.loo_median_rank,
        row.loo_worst_rank,
        row.ticket,
    )


@dataclass(frozen=True)
class LooOmissionRanking:
    omitted_stream_id: str
    ranking: tuple[Ticket, ...]

    @property
    def observed_distinct_ticket_count(self) -> int:
        return len(self.ranking)


@dataclass(frozen=True)
class CandidateBudgetResult:
    budget: int
    status: Literal["AVAILABLE", "UNAVAILABLE"]
    tickets: tuple[Ticket, ...] | None


@dataclass(frozen=True)
class LooStabilityTiebreakResult:
    method_id: Literal["LOO_STABILITY_TIEBREAK_V1"]
    ticket_rows: tuple[LooTicketRank, ...]
    omissions: tuple[LooOmissionRanking, ...]
    budgets: tuple[CandidateBudgetResult, ...]

    @property
    def ranking(self) -> tuple[Ticket, ...]:
        return tuple(row.ticket for row in self.ticket_rows)


def build_loo_stability_tiebreak(
    candidates: Sequence[StrategyCandidate],
) -> LooStabilityTiebreakResult:
    """Return one total ranking and fixed K2/K3/K5/K10/K20 prefixes.

    Reads only ``strategy_id`` and ``tickets``. Repeated IDs denote one stream,
    all of whose records are removed together. Repeated/reordered ticket order
    never multiplies support. Infeasible budgets return UNAVAILABLE with None,
    never a partial prefix. There are no quality, outcome, or tuning arguments.
    """
    support_rows = compute_stream_support_matrix(candidates).ticket_rows
    stream_ids = sorted({candidate.strategy_id for candidate in candidates})
    omissions: list[LooOmissionRanking] = []
    rank_maps: list[dict[Ticket, int]] = []
    for stream_id in stream_ids:
        reduced = [candidate for candidate in candidates if candidate.strategy_id != stream_id]
        distinct_count = len(compute_stream_support_matrix(reduced).ticket_rows)
        ranking = (
            tuple(build_portfolio(reduced, {}, bucket_sizes=(distinct_count,))[distinct_count])
            if distinct_count
            else ()
        )
        omissions.append(LooOmissionRanking(omitted_stream_id=stream_id, ranking=ranking))
        rank_maps.append({ticket: rank for rank, ticket in enumerate(ranking, start=1)})

    rows: list[LooTicketRank] = []
    for support in support_rows:
        ranks = tuple(rank_map.get(support.ticket, len(rank_map) + 1) for rank_map in rank_maps)
        rows.append(
            LooTicketRank(
                ticket=support.ticket,
                distinct_stream_support=support.stream_support_count,
                loo_survival=sum(support.ticket in rank_map for rank_map in rank_maps),
                loo_median_rank=float(median(ranks)),
                loo_worst_rank=max(ranks),
                penalized_rank_by_omission=tuple(zip(stream_ids, ranks, strict=True)),
            )
        )

    ordered_rows = tuple(sorted(rows, key=frozen_sort_key))
    ranking = tuple(row.ticket for row in ordered_rows)
    budgets = tuple(
        CandidateBudgetResult(
            budget=k,
            status="AVAILABLE" if len(ranking) >= k else "UNAVAILABLE",
            tickets=ranking[:k] if len(ranking) >= k else None,
        )
        for k in BUDGETS
    )
    return LooStabilityTiebreakResult(
        method_id=METHOD_ID,
        ticket_rows=ordered_rows,
        omissions=tuple(omissions),
        budgets=budgets,
    )
