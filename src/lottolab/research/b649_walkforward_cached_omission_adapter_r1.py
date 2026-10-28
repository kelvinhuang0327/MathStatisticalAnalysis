"""Research adapter for the cached low-overlap K5 omission candidate.

The adapter replaces only the repeated 50/300/750 window-statistic reads.
Ranking fusion, ordered source-ticket construction, and the native K5
constructor remain the implementations owned by the original research code.
"""

from __future__ import annotations

from dataclasses import dataclass

from lottolab.research import b649_walkforward_incremental_cache_r1 as _cache
from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _multiscale,
)

LOW_OVERLAP_K5_CANDIDATE_ID = (
    _multiscale.CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[
        ("B649_CANDIDATE_SET_LOW_OVERLAP_V1", 5)
    ]
)


@dataclass(slots=True)
class B649WalkForwardCachedOmissionAdapter:
    """Reuse one J cache across strictly-prior low-overlap K5 cutoffs."""

    cache: _cache.B649WalkForwardIncrementalCache

    def __post_init__(self) -> None:
        if type(self.cache) is not _cache.B649WalkForwardIncrementalCache:
            raise TypeError(
                "cache must be a B649WalkForwardIncrementalCache instance"
            )

    def produce_low_overlap_k5(
        self,
        history: _cache.B649WalkForwardHistory,
        target_index: int,
    ) -> _multiscale.TicketPortfolio:
        """Produce the original native K5 portfolio using cached source ranks.

        The snapshot contains chronological history and may contain the target
        draw. J's exclusive cutoff and prefix digest ensure that draw is neither
        read into nor keyed by the statistics used for this target.
        """

        if type(history) is not _cache.B649WalkForwardHistory:
            raise TypeError(
                "history must be an immutable B649WalkForwardHistory snapshot"
            )

        source_tickets = _cache.produce_source_ticket_universe_cached(
            history,
            target_index,
            self.cache,
        )
        metadata = _multiscale.CANDIDATE_AUTHORITY[LOW_OVERLAP_K5_CANDIDATE_ID]
        constructor = _constructors.CONSTRUCTORS[metadata.CONSTRUCTOR_ID]
        return constructor(source_tickets, metadata.TICKET_COUNT)


__all__ = [
    "LOW_OVERLAP_K5_CANDIDATE_ID",
    "B649WalkForwardCachedOmissionAdapter",
]
