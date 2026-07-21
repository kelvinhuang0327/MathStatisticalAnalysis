"""Pure post-hoc ranking of 1-5-ticket Replay strategy portfolios.

Consumes one already-validated :class:`ReplayScoringArtifact` and produces a
:class:`PortfolioRankingResult` under the frozen
``BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1`` policy. Generates no numbers,
executes no strategy, selects no combination per draw, and reads no external
state -- every candidate's counters come only from the artifact's already
validated scored records and per-strategy aggregates.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from lottolab.domain.replay_portfolio_ranking import (
    MAX_EXHAUSTIVE_PORTFOLIO_CANDIDATES,
    MAX_TICKET_COUNT,
    MIN_TICKET_COUNT,
    PortfolioGroupStatus,
    PortfolioRankingGroup,
    PortfolioRankingResult,
    PortfolioSearchSpaceExceededError,
    build_ranked_portfolio_candidate,
    portfolio_sort_key,
)
from lottolab.evidence.replay_scoring_artifact import ReplayScoringArtifact

_SUMMED_FIELDS = (
    "scored_count",
    "history_closed_count",
    "prediction_closed_count",
    "target_outcome_not_found_count",
    "target_identity_mismatch_count",
    "first_prize_count",
    "second_prize_count",
    "third_prize_count",
    "fourth_prize_count",
    "fifth_prize_count",
    "sixth_prize_count",
    "seventh_prize_count",
    "general_prize_count",
    "no_prize_count",
)


class RankReplayStrategyPortfolios:
    """Exhaustively rank every 1..5-strategy portfolio; fails closed on search-space overflow."""

    def execute(self, artifact: ReplayScoringArtifact, *, top_k: int) -> PortfolioRankingResult:
        strategy_count = len(artifact.strategy_identities)
        target_count = len(artifact.target_identities)

        total_search_space = sum(
            math.comb(strategy_count, n) for n in range(MIN_TICKET_COUNT, MAX_TICKET_COUNT + 1)
        )
        if total_search_space > MAX_EXHAUSTIVE_PORTFOLIO_CANDIDATES:
            raise PortfolioSearchSpaceExceededError(
                f"complete N={MIN_TICKET_COUNT}..{MAX_TICKET_COUNT} search space "
                f"({total_search_space}) exceeds the exhaustive-search cap "
                f"({MAX_EXHAUSTIVE_PORTFOLIO_CANDIDATES})"
            )

        groups = tuple(
            self._rank_group(
                artifact,
                ticket_count=ticket_count,
                top_k=top_k,
                target_count=target_count,
                strategy_count=strategy_count,
            )
            for ticket_count in range(MIN_TICKET_COUNT, MAX_TICKET_COUNT + 1)
        )
        return PortfolioRankingResult(
            strategy_count=strategy_count,
            target_count=target_count,
            top_k=top_k,
            groups=groups,
        )

    def _rank_group(
        self,
        artifact: ReplayScoringArtifact,
        *,
        ticket_count: int,
        top_k: int,
        target_count: int,
        strategy_count: int,
    ) -> PortfolioRankingGroup:
        if strategy_count < ticket_count:
            return PortfolioRankingGroup(
                ticket_count=ticket_count,
                status=PortfolioGroupStatus.INSUFFICIENT_STRATEGIES,
                total_candidate_count=0,
                candidates=(),
            )

        total_candidate_count = math.comb(strategy_count, ticket_count)
        raw_candidates = [
            self._raw_candidate(artifact, positions)
            for positions in itertools.combinations(range(strategy_count), ticket_count)
        ]
        raw_candidates.sort(key=lambda raw: raw[0])

        candidates = tuple(
            build_ranked_portfolio_candidate(
                rank=rank,
                ticket_count=ticket_count,
                target_count=target_count,
                total_ticket_count=target_count * ticket_count,
                **raw[1],
            )
            for rank, raw in enumerate(raw_candidates[:top_k], start=1)
        )
        return PortfolioRankingGroup(
            ticket_count=ticket_count,
            status=PortfolioGroupStatus.RANKED,
            total_candidate_count=total_candidate_count,
            candidates=candidates,
        )

    def _raw_candidate(
        self,
        artifact: ReplayScoringArtifact,
        positions: tuple[int, ...],
    ) -> tuple[tuple[int, ...], dict[str, Any]]:
        aggregates = [artifact.strategy_aggregates[position] for position in positions]
        identities = [artifact.strategy_identities[position] for position in positions]
        totals = {
            name: sum(getattr(aggregate, name) for aggregate in aggregates)
            for name in _SUMMED_FIELDS
        }
        winning_ticket_count = sum(
            totals[name]
            for name in (
                "first_prize_count",
                "second_prize_count",
                "third_prize_count",
                "fourth_prize_count",
                "fifth_prize_count",
                "sixth_prize_count",
                "seventh_prize_count",
                "general_prize_count",
            )
        )
        sort_key = portfolio_sort_key(
            first_prize_count=totals["first_prize_count"],
            second_prize_count=totals["second_prize_count"],
            third_prize_count=totals["third_prize_count"],
            fourth_prize_count=totals["fourth_prize_count"],
            fifth_prize_count=totals["fifth_prize_count"],
            sixth_prize_count=totals["sixth_prize_count"],
            seventh_prize_count=totals["seventh_prize_count"],
            general_prize_count=totals["general_prize_count"],
            scored_count=totals["scored_count"],
            target_identity_mismatch_count=totals["target_identity_mismatch_count"],
            target_outcome_not_found_count=totals["target_outcome_not_found_count"],
            history_closed_count=totals["history_closed_count"],
            prediction_closed_count=totals["prediction_closed_count"],
            strategy_positions=positions,
        )
        payload: dict[str, Any] = {
            "strategy_positions": positions,
            "strategy_ids": tuple(identity.strategy_id for identity in identities),
            "strategy_versions": tuple(identity.strategy_version for identity in identities),
            "winning_ticket_count": winning_ticket_count,
            **totals,
        }
        return sort_key, payload


__all__ = ["RankReplayStrategyPortfolios"]
