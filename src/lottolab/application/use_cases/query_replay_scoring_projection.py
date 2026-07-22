"""Query one exact persisted Replay-scoring projection without re-deriving it."""

from __future__ import annotations

import re

from lottolab.application.ports import (
    ReplayScoringProjectionReader,
    ReplayScoringProjectionReaderFactory,
)
from lottolab.domain.lottery_rules import BigLottoPrizeTierId, NoPrizeResult
from lottolab.domain.replay_scoring import (
    ReplayScoringStatus,
    validate_replay_target_draw_number,
)
from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
)
from lottolab.evidence.replay_scoring_artifact import ReplayScoringArtifact

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_MAX_STRATEGY_ID_LENGTH = 100
_VALID_STATUSES = frozenset(status.value for status in ReplayScoringStatus)
_VALID_TIERS = frozenset(
    {tier.value for tier in BigLottoPrizeTierId} | {NoPrizeResult.NO_PRIZE.value}
)


class ReplayScoringRunNotFoundError(LookupError):
    """No persisted run matches the exact scoring-artifact SHA-256."""


class ReplayScoringQueryUnavailableError(RuntimeError):
    """A persisted run failed its required projection consistency checks."""


class QueryReplayScoringProjection:
    """Read stored projections through one lazily-created reader per operation."""

    def __init__(self, reader_factory: ReplayScoringProjectionReaderFactory) -> None:
        self._reader_factory = reader_factory

    def get_run(self, scoring_artifact_payload_sha256: str) -> ReplayScoringRunProjection:
        reader = self._verified_reader(scoring_artifact_payload_sha256)
        run = reader.get_run(scoring_artifact_payload_sha256)
        if run is None:
            raise ReplayScoringQueryUnavailableError(
                "verified Replay-scoring artifact is missing its run projection"
            )
        return run

    def get_artifact(self, scoring_artifact_payload_sha256: str) -> ReplayScoringArtifact:
        """Load one exact, integrity-checked persisted scoring artifact."""

        _validate_sha256(scoring_artifact_payload_sha256)
        reader = self._reader_factory()
        artifact = reader.get_replay_scoring_artifact(scoring_artifact_payload_sha256)
        if artifact is None:
            raise ReplayScoringRunNotFoundError(scoring_artifact_payload_sha256)
        return artifact

    def list_predictions(
        self,
        scoring_artifact_payload_sha256: str,
        *,
        target_draw: str | None = None,
        strategy_id: str | None = None,
        status: str | None = None,
        tier: str | None = None,
    ) -> tuple[ReplayScoredPredictionProjection, ...]:
        _validate_sha256(scoring_artifact_payload_sha256)
        _validate_prediction_filters(
            target_draw=target_draw,
            strategy_id=strategy_id,
            status=status,
            tier=tier,
        )
        reader = self._verified_reader_after_validation(scoring_artifact_payload_sha256)
        records = reader.list_scored_predictions(
            scoring_artifact_payload_sha256,
            target_draw_number=target_draw,
            strategy_id=strategy_id,
        )
        if status is not None:
            records = tuple(record for record in records if record.scoring_status == status)
        if tier is not None:
            if tier == NoPrizeResult.NO_PRIZE.value:
                records = tuple(
                    record for record in records if record.no_prize_result == tier
                )
            else:
                records = tuple(record for record in records if record.prize_tier_id == tier)
        return records

    def list_strategy_aggregates(
        self, scoring_artifact_payload_sha256: str
    ) -> tuple[ReplayStrategyAggregateProjection, ...]:
        reader = self._verified_reader(scoring_artifact_payload_sha256)
        return reader.list_strategy_aggregates(scoring_artifact_payload_sha256)

    def get_overall_aggregate(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayOverallAggregateProjection:
        reader = self._verified_reader(scoring_artifact_payload_sha256)
        aggregate = reader.get_overall_aggregate(scoring_artifact_payload_sha256)
        if aggregate is None:
            raise ReplayScoringQueryUnavailableError(
                "verified Replay-scoring artifact is missing its overall aggregate projection"
            )
        return aggregate

    def _verified_reader(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringProjectionReader:
        _validate_sha256(scoring_artifact_payload_sha256)
        return self._verified_reader_after_validation(scoring_artifact_payload_sha256)

    def _verified_reader_after_validation(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringProjectionReader:
        reader = self._reader_factory()
        artifact = reader.get_replay_scoring_artifact(scoring_artifact_payload_sha256)
        if artifact is None:
            raise ReplayScoringRunNotFoundError(scoring_artifact_payload_sha256)
        return reader


def _validate_sha256(value: object) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError("scoring_artifact_payload_sha256 must be a lowercase SHA-256 digest")


def _validate_prediction_filters(
    *,
    target_draw: str | None,
    strategy_id: str | None,
    status: str | None,
    tier: str | None,
) -> None:
    if target_draw is not None:
        validate_replay_target_draw_number(target_draw)
    if strategy_id is not None and (
        type(strategy_id) is not str
        or not strategy_id
        or len(strategy_id) > _MAX_STRATEGY_ID_LENGTH
    ):
        raise ValueError("strategy_id must contain 1-100 characters")
    if status is not None and status not in _VALID_STATUSES:
        raise ValueError("status is not a supported Replay-scoring status")
    if tier is not None and tier not in _VALID_TIERS:
        raise ValueError("tier is not a supported BIG_LOTTO prize tier")


__all__ = [
    "QueryReplayScoringProjection",
    "ReplayScoringQueryUnavailableError",
    "ReplayScoringRunNotFoundError",
]
