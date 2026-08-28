"""Compose one native-ticket-count bucket's Next-Draw Recommendation view.

Reads the real catalog (candidate universe + exclusion classification) and
one already-computed :class:`NextDrawRecommendationEvidenceArtifact`
(backtested window metrics); performs no execution, no backtesting, and no
re-derivation of evidence. Ranking itself is delegated entirely to
``lottolab.domain.next_draw_recommendation.rank_candidate_order`` -- this
module only assembles inputs and classifies exclusions.
"""

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import (
    RANKING_WINDOW_KINDS,
    RecommendationBucketView,
    RecommendationCandidate,
    RecommendationExclusion,
    RecommendationExclusionReason,
    RecommendationWindowMetric,
    bucket_availability,
    cross_window_rank_sum,
    rank_candidate_order,
)
from lottolab.evidence.next_draw_recommendation_evidence import (
    NextDrawRecommendationEvidenceArtifact,
    StrategyBacktestStatus,
)
from lottolab.strategies.catalog import StrategyCatalog


class BuildNextDrawRecommendationBucket:
    """Assemble one :class:`RecommendationBucketView` for one ticket-count bucket."""

    def __init__(
        self,
        *,
        catalog: StrategyCatalog,
        evidence: NextDrawRecommendationEvidenceArtifact,
    ) -> None:
        self._catalog = catalog
        self._evidence_by_strategy_id = {
            record.strategy_id: record for record in evidence.records
        }

    def execute(
        self, *, lottery_type: LotteryType, native_ticket_count: int
    ) -> RecommendationBucketView:
        candidates = [
            descriptor
            for descriptor in self._catalog
            if lottery_type in descriptor.lottery_types
            and descriptor.executable
            and descriptor.native_ticket_count == native_ticket_count
        ]

        eligible_ids: list[str] = []
        exclusions: list[RecommendationExclusion] = []
        metrics_by_strategy: dict[str, dict[str, RecommendationWindowMetric]] = {}
        names_by_strategy: dict[str, str] = {}

        for descriptor in candidates:
            record = self._evidence_by_strategy_id.get(descriptor.strategy_id)
            names_by_strategy[descriptor.strategy_id] = descriptor.strategy_name
            if record is None:
                exclusions.append(
                    RecommendationExclusion(
                        strategy_id=descriptor.strategy_id,
                        reason=RecommendationExclusionReason.EVIDENCE_UNAVAILABLE,
                        detail="no backtest evidence record for this strategy_id",
                    )
                )
                continue
            if record.status is not StrategyBacktestStatus.EVALUATED:
                exclusions.append(
                    RecommendationExclusion(
                        strategy_id=descriptor.strategy_id,
                        reason=RecommendationExclusionReason.EXECUTION_UNREACHABLE,
                        detail=f"backtest status={record.status.value}",
                    )
                )
                continue
            windows_by_kind = {window.window_kind: window for window in record.windows}
            window_metrics: dict[str, RecommendationWindowMetric] = {}
            for window_kind in RANKING_WINDOW_KINDS:
                window = windows_by_kind.get(window_kind)
                if window is None:
                    continue
                window_metrics[window_kind] = RecommendationWindowMetric(
                    window_kind=window_kind,
                    eligible_draw_count=window.eligible_draw_count,
                    window_complete=(window.window_status == "COMPLETE"),
                    observed_rate=window.observed_value,
                    random_baseline_rate=window.random_reference,
                    delta_vs_random=window.delta_vs_random,
                )
            if not window_metrics:
                exclusions.append(
                    RecommendationExclusion(
                        strategy_id=descriptor.strategy_id,
                        reason=RecommendationExclusionReason.INSUFFICIENT_WINDOW_HISTORY,
                        detail="no window reached COMPLETE or evaluable status",
                    )
                )
                continue
            metrics_by_strategy[descriptor.strategy_id] = window_metrics
            eligible_ids.append(descriptor.strategy_id)

        ordered_ids = rank_candidate_order(eligible_ids, metrics_by_strategy)
        ranked = tuple(
            RecommendationCandidate(
                rank=rank,
                strategy_id=strategy_id,
                strategy_name=names_by_strategy[strategy_id],
                native_ticket_count=native_ticket_count,
                windows=tuple(
                    metrics_by_strategy[strategy_id][window_kind]
                    for window_kind in RANKING_WINDOW_KINDS
                    if window_kind in metrics_by_strategy[strategy_id]
                ),
                cross_window_rank_sum=cross_window_rank_sum(
                    strategy_id, metrics_by_strategy, ordered_ids
                ),
            )
            for rank, strategy_id in enumerate(ordered_ids, start=1)
        )

        total = len(candidates)
        return RecommendationBucketView(
            native_ticket_count=native_ticket_count,
            availability=bucket_availability(total),
            total_candidate_count=total,
            ranked=ranked,
            excluded=tuple(exclusions),
        )


__all__ = ["BuildNextDrawRecommendationBucket"]
