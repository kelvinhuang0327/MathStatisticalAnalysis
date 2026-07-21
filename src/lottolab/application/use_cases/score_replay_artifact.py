"""Post-hoc prize scoring for a validated canonical Replay artifact."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lottolab.application.ports import ReplayTargetOutcomeReader
from lottolab.domain import lottery_rules
from lottolab.domain.lottery_rules import BigLottoPrizeTier, NoPrizeResult
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.domain.replay_scoring import (
    SCORING_SCHEMA_VERSION,
    ReplayPrizeAggregation,
    ReplayScoredPrediction,
    ReplayScoringReason,
    ReplayScoringStatus,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadResult,
    ReplayTargetOutcomeReadStatus,
    validate_replay_target_draw_number,
)
from lottolab.evidence.replay_artifact import (
    ARTIFACT_SCHEMA_VERSION,
    ReplayArtifact,
    recompute_artifact_payload_sha256,
    recompute_snapshot_result_sha256,
)


@dataclass(frozen=True, slots=True)
class ScoreReplayArtifactResult:
    scored_predictions: tuple[ReplayScoredPrediction, ...]
    strategy_aggregates: tuple[ReplayPrizeAggregation, ...]
    overall_aggregate: ReplayPrizeAggregation


class ScoreReplayArtifact:
    """Score every source snapshot exactly once without mutating the source artifact."""

    def __init__(self, target_outcome_reader: ReplayTargetOutcomeReader) -> None:
        self._target_outcome_reader = target_outcome_reader

    def execute(self, artifact: ReplayArtifact) -> ScoreReplayArtifactResult:
        _validate_source_artifact(artifact)
        outcome_cache: dict[tuple[object, str], ReplayTargetOutcomeReadResult] = {}
        records = tuple(
            self._score_snapshot(artifact, snapshot, outcome_cache)
            for snapshot in artifact.snapshots
        )

        strategy_aggregates: list[ReplayPrizeAggregation] = []
        for strategy_id in artifact.strategy_ids:
            strategy_records = tuple(
                record for record in records if record.strategy_id == strategy_id
            )
            versions = {record.strategy_version for record in strategy_records}
            if len(versions) != 1:
                raise ValueError("source snapshots contain inconsistent strategy versions")
            strategy_aggregates.append(
                ReplayPrizeAggregation.from_records(
                    strategy_records,
                    strategy_id=strategy_id,
                    strategy_version=versions.pop(),
                )
            )
        return ScoreReplayArtifactResult(
            scored_predictions=records,
            strategy_aggregates=tuple(strategy_aggregates),
            overall_aggregate=ReplayPrizeAggregation.from_records(records),
        )

    def _score_snapshot(
        self,
        artifact: ReplayArtifact,
        snapshot: ReplayPredictionSnapshot,
        outcome_cache: dict[tuple[object, str], ReplayTargetOutcomeReadResult],
    ) -> ReplayScoredPrediction:
        base: dict[str, Any] = {
            "scoring_schema_version": SCORING_SCHEMA_VERSION,
            "source_replay_artifact_payload_sha256": artifact.payload_sha256,
            "source_replay_snapshot_result_sha256": snapshot.result_sha256,
            "dataset_id": snapshot.dataset_id,
            "dataset_version": snapshot.dataset_version,
            "lottery_type": snapshot.lottery_type,
            "target_draw_number": snapshot.target_draw_number,
            "target_draw_date": snapshot.target_draw_date,
            "strategy_id": snapshot.strategy_id,
            "strategy_version": snapshot.strategy_version,
            "source_history_status": snapshot.history_status,
            "source_history_reason_code": snapshot.history_reason_code,
            "source_prediction_status": snapshot.prediction_status,
            "source_prediction_reason_code": snapshot.prediction_reason_code,
            "predicted_main_numbers": snapshot.predicted_main_numbers,
            "target_outcome_sha256": None,
            "main_number_hit_count": None,
            "special_number_hit": None,
            "prize_tier_id": None,
            "prize_official_label": None,
            "no_prize_result": None,
        }
        if snapshot.history_status != "OK":
            return ReplayScoredPrediction.create(
                **base,
                scoring_status=ReplayScoringStatus.NOT_SCORED_HISTORY_CLOSED,
                scoring_reason_code=ReplayScoringReason.SOURCE_HISTORY_CLOSED,
            )
        if snapshot.prediction_status != "OK":
            return ReplayScoredPrediction.create(
                **base,
                scoring_status=ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED,
                scoring_reason_code=ReplayScoringReason.SOURCE_PREDICTION_CLOSED,
            )

        cache_key = (snapshot.lottery_type, snapshot.target_draw_number)
        read_result = outcome_cache.get(cache_key)
        if read_result is None:
            read_result = self._target_outcome_reader.load_target_outcome(
                snapshot.lottery_type,
                snapshot.target_draw_number,
            )
            outcome_cache[cache_key] = read_result
        if read_result.status is ReplayTargetOutcomeReadStatus.NOT_FOUND:
            return ReplayScoredPrediction.create(
                **base,
                scoring_status=ReplayScoringStatus.TARGET_OUTCOME_NOT_FOUND,
                scoring_reason_code=_scoring_read_reason(read_result.reason_code),
            )

        outcome = read_result.outcome
        assert outcome is not None
        base["target_outcome_sha256"] = outcome.outcome_sha256
        if (
            outcome.lottery_type is not snapshot.lottery_type
            or outcome.target_draw_number != snapshot.target_draw_number
            or outcome.target_draw_date != snapshot.target_draw_date
        ):
            return ReplayScoredPrediction.create(
                **base,
                scoring_status=ReplayScoringStatus.TARGET_IDENTITY_MISMATCH,
                scoring_reason_code=ReplayScoringReason.TARGET_IDENTITY_MISMATCH,
            )

        predicted = snapshot.predicted_main_numbers
        assert predicted is not None
        main_hits = len(set(predicted).intersection(outcome.winning_main_numbers))
        special_hit = outcome.winning_special_number in predicted
        resolution = lottery_rules.resolve_big_lotto_prize_tier(main_hits, special_hit)
        base["main_number_hit_count"] = main_hits
        base["special_number_hit"] = special_hit
        if isinstance(resolution, BigLottoPrizeTier):
            base["prize_tier_id"] = resolution.tier_id
            base["prize_official_label"] = resolution.official_label
        elif resolution is NoPrizeResult.NO_PRIZE:
            base["no_prize_result"] = NoPrizeResult.NO_PRIZE
        else:
            raise ValueError("Big Lotto prize resolver returned an unsupported result")
        return ReplayScoredPrediction.create(
            **base,
            scoring_status=ReplayScoringStatus.SCORED,
            scoring_reason_code=None,
        )


def _scoring_read_reason(
    reason: ReplayTargetOutcomeReadReason | None,
) -> ReplayScoringReason:
    if reason is ReplayTargetOutcomeReadReason.TARGET_OUTCOME_STORAGE_UNAVAILABLE:
        return ReplayScoringReason.TARGET_OUTCOME_STORAGE_UNAVAILABLE
    return ReplayScoringReason.TARGET_OUTCOME_NOT_FOUND


def _validate_source_artifact(artifact: ReplayArtifact) -> None:
    if artifact.artifact_schema_version != ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported source ReplayArtifact schema version")
    if recompute_artifact_payload_sha256(artifact) != artifact.payload_sha256:
        raise ValueError("source ReplayArtifact payload_sha256 mismatch")
    expected_pairs = tuple(
        (target, strategy_id)
        for target in artifact.targets
        for strategy_id in artifact.strategy_ids
    )
    if len(expected_pairs) != len(artifact.snapshots):
        raise ValueError("source ReplayArtifact snapshot cardinality mismatch")
    for snapshot, (target, strategy_id) in zip(
        artifact.snapshots,
        expected_pairs,
        strict=True,
    ):
        validate_replay_target_draw_number(target.draw_number)
        if recompute_snapshot_result_sha256(snapshot) != snapshot.result_sha256:
            raise ValueError("source ReplayPredictionSnapshot result_sha256 mismatch")
        if (
            snapshot.dataset_id != artifact.dataset_id
            or snapshot.dataset_version != artifact.dataset_version
            or snapshot.lottery_type is not artifact.lottery_type
            or snapshot.target_draw_number != target.draw_number
            or snapshot.target_draw_date != target.draw_date
            or snapshot.strategy_id != strategy_id
        ):
            raise ValueError("source ReplayArtifact snapshot identity/order mismatch")
        if snapshot.strategy_version is not None and (
            snapshot.adapter_strategy_id != snapshot.strategy_id
            or snapshot.adapter_strategy_version != snapshot.strategy_version
            or not snapshot.adapter_strategy_name
        ):
            raise ValueError("source ReplayPredictionSnapshot strategy identity mismatch")


__all__ = ["ScoreReplayArtifact", "ScoreReplayArtifactResult"]
