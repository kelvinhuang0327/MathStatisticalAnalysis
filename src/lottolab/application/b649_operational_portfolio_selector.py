"""Pool already-generated native-strategy tickets into nested K-bucket portfolios."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

type Ticket = tuple[int, ...]


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    tickets: Sequence[Ticket]


def build_portfolio(
    candidates: Sequence[StrategyCandidate],
    quality_by_strategy: Mapping[str, float],
    bucket_sizes: Sequence[int] = (5, 10, 20),
) -> dict[int, list[Ticket]]:
    """Rank deduplicated candidate tickets by cross-strategy consensus, then
    summed strategy quality, then the ticket itself; slice nested K-buckets
    from the resulting order.
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

    ranked = sorted(
        supporters,
        key=lambda t: (-len(supporters[t]), -quality(t), t),
    )

    buckets: dict[int, list[Ticket]] = {}
    for k in bucket_sizes:
        if k > len(ranked):
            raise ValueError(
                f"requested K{k} but only {len(ranked)} distinct candidate tickets are available"
            )
        buckets[k] = ranked[:k]
    return buckets
