"""Pool already-generated native-strategy tickets into nested K-bucket portfolios."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

type Ticket = tuple[int, ...]


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    tickets: Sequence[Ticket]


@dataclass(frozen=True)
class CandidatePoolEntry:
    """One deduplicated candidate ticket at its canonical candidate-pool position.

    ``supporters`` are the distinct emitting strategy IDs, sorted;
    ``quality_sum`` is the supplied strategy quality summed over them; and
    ``candidate_pool_index`` is the 0-based position in pool order.
    """

    ticket: Ticket
    supporters: tuple[str, ...]
    support_count: int
    quality_sum: float
    candidate_pool_index: int


def build_candidate_pool(
    candidates: Sequence[StrategyCandidate],
    quality_by_strategy: Mapping[str, float],
) -> tuple[CandidatePoolEntry, ...]:
    """Deduplicate candidate tickets across strategies and order them by
    cross-strategy consensus DESC, then summed strategy quality DESC, then the
    ticket itself ASC -- the order ``build_portfolio`` slices its buckets from.
    """
    supporters: dict[Ticket, set[str]] = {}
    for candidate in candidates:
        for raw in candidate.tickets:
            ticket = tuple(sorted(raw))
            if len(ticket) != 6 or len(set(ticket)) != 6:
                raise ValueError(f"invalid ticket from {candidate.strategy_id}: {raw}")
            supporters.setdefault(ticket, set()).add(candidate.strategy_id)

    def quality(ticket: Ticket) -> float:
        return sum(quality_by_strategy.get(s, 0.0) for s in supporters[ticket])

    quality_sums = {ticket: quality(ticket) for ticket in supporters}
    ranked = sorted(
        supporters,
        key=lambda t: (-len(supporters[t]), -quality_sums[t], t),
    )
    return tuple(
        CandidatePoolEntry(
            ticket=ticket,
            supporters=tuple(sorted(supporters[ticket])),
            support_count=len(supporters[ticket]),
            quality_sum=quality_sums[ticket],
            candidate_pool_index=index,
        )
        for index, ticket in enumerate(ranked)
    )


def build_portfolio(
    candidates: Sequence[StrategyCandidate],
    quality_by_strategy: Mapping[str, float],
    bucket_sizes: Sequence[int] = (5, 10, 20),
) -> dict[int, list[Ticket]]:
    """Rank deduplicated candidate tickets by cross-strategy consensus, then
    summed strategy quality, then the ticket itself; slice nested K-buckets
    from the resulting order.
    """
    ranked = [entry.ticket for entry in build_candidate_pool(candidates, quality_by_strategy)]

    buckets: dict[int, list[Ticket]] = {}
    for k in bucket_sizes:
        if k > len(ranked):
            raise ValueError(
                f"requested K{k} but only {len(ranked)} distinct candidate tickets are available"
            )
        buckets[k] = ranked[:k]
    return buckets
