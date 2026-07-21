"""Canonical serialization and tamper checks for ReplayScoringArtifact."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, cast

import pytest

from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcome,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadResult,
)
from lottolab.evidence.canonical_json import canonical_bytes, self_key_removed_sha256
from lottolab.evidence.replay_artifact import (
    build_replay_artifact,
    build_replay_prediction_snapshot,
)
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    ReplayScoringArtifactShapeError,
    ReplayScoringArtifactTamperError,
    build_replay_scoring_artifact,
    deserialize_replay_scoring_artifact,
    recompute_scoring_artifact_payload_sha256,
    serialize_replay_scoring_artifact,
)


class _Reader:
    def __init__(self, outcome: ReplayTargetOutcome) -> None:
        self.outcome = outcome

    def load_target_outcome(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
    ) -> ReplayTargetOutcomeReadResult:
        assert lottery_type is LotteryType.BIG_LOTTO
        if target_draw_number == self.outcome.target_draw_number:
            return ReplayTargetOutcomeReadResult.found(self.outcome)
        return ReplayTargetOutcomeReadResult.not_found(
            ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
        )


def _build_artifact() -> ReplayScoringArtifact:
    targets = tuple(
        ReplayTarget(str(200 + index), date(2026, 2, 1) + timedelta(days=index))
        for index in range(3)
    )
    snapshots = (
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[0],
            strategy_id="strategy",
            strategy_identity=("strategy", "Strategy", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=(1, 2, 3, 4, 5, 6),
        ),
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[1],
            strategy_id="strategy",
            strategy_identity=("strategy", "Strategy", "1.0.0"),
            history_status="TARGET_NOT_FOUND",
            history_reason_code="TARGET_DRAW_NOT_FOUND",
            causal_history=None,
            prediction_status=None,
            prediction_reason_code=None,
            predicted_main_numbers=None,
        ),
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[2],
            strategy_id="strategy",
            strategy_identity=("strategy", "Strategy", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=(1, 8, 9, 10, 11, 12),
        ),
    )
    source = build_replay_artifact(
        dataset_id="dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=("strategy",),
        targets=targets,
        snapshots=snapshots,
    )
    outcome = ReplayTargetOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number=targets[0].draw_number,
        target_draw_date=targets[0].draw_date,
        winning_main_numbers=(1, 2, 3, 4, 5, 6),
        winning_special_number=7,
    )
    result = ScoreReplayArtifact(_Reader(outcome)).execute(source)
    return build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=result.scored_predictions,
        strategy_aggregates=result.strategy_aggregates,
        overall_aggregate=result.overall_aggregate,
    )


def _parsed(data: bytes) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(data))


def _rehash(payload: dict[str, Any]) -> bytes:
    payload["payload_sha256"] = self_key_removed_sha256(payload, "payload_sha256")
    return canonical_bytes(payload)


def test_payload_hash_and_serialization_are_stable_and_round_trip_exactly() -> None:
    artifact = _build_artifact()
    first = serialize_replay_scoring_artifact(artifact)
    second = serialize_replay_scoring_artifact(artifact)
    restored = deserialize_replay_scoring_artifact(first)

    assert first == second
    assert restored == artifact
    assert recompute_scoring_artifact_payload_sha256(restored) == restored.payload_sha256
    assert len(restored.payload_sha256) == 64
    assert [record.scoring_status.value for record in restored.scored_predictions] == [
        "SCORED",
        "NOT_SCORED_HISTORY_CLOSED",
        "TARGET_OUTCOME_NOT_FOUND",
    ]


def test_identical_inputs_produce_the_same_payload_hash() -> None:
    first = _build_artifact()
    second = _build_artifact()

    assert first == second
    assert serialize_replay_scoring_artifact(first) == serialize_replay_scoring_artifact(second)


def test_top_level_tampering_is_detected() -> None:
    payload = _parsed(serialize_replay_scoring_artifact(_build_artifact()))
    payload["dataset_id"] = "tampered"

    with pytest.raises(ReplayScoringArtifactTamperError):
        deserialize_replay_scoring_artifact(canonical_bytes(payload))


def test_nested_scored_record_tampering_is_detected_even_with_rehashed_top_level() -> None:
    payload = _parsed(serialize_replay_scoring_artifact(_build_artifact()))
    scored = cast("list[dict[str, Any]]", payload["scored_predictions"])
    scored[0]["prize_official_label"] = "tampered"

    with pytest.raises(ReplayScoringArtifactTamperError):
        deserialize_replay_scoring_artifact(_rehash(payload))


def test_aggregate_tampering_is_detected_even_with_rehashed_top_level() -> None:
    payload = _parsed(serialize_replay_scoring_artifact(_build_artifact()))
    overall = cast("dict[str, Any]", payload["overall_aggregate"])
    overall["first_prize_count"] = 0
    overall["no_prize_count"] = 1

    with pytest.raises(ReplayScoringArtifactTamperError):
        deserialize_replay_scoring_artifact(_rehash(payload))


def test_scored_record_count_mismatch_is_rejected() -> None:
    payload = _parsed(serialize_replay_scoring_artifact(_build_artifact()))
    payload["scored_record_count"] = 4

    with pytest.raises(ReplayScoringArtifactShapeError):
        deserialize_replay_scoring_artifact(_rehash(payload))


@pytest.mark.parametrize("identity_key", ("target_identities", "strategy_identities"))
def test_duplicate_target_or_strategy_identity_is_rejected(identity_key: str) -> None:
    payload = _parsed(serialize_replay_scoring_artifact(_build_artifact()))
    identities = cast("list[dict[str, Any]]", payload[identity_key])
    identities.append(dict(identities[0]))

    with pytest.raises(ReplayScoringArtifactShapeError):
        deserialize_replay_scoring_artifact(_rehash(payload))


def test_artifact_contains_no_time_path_or_environment_identity() -> None:
    data = serialize_replay_scoring_artifact(_build_artifact())

    for forbidden in (b"timestamp", b"produced_at", b"absolute_path", b"environment", b"uuid"):
        assert forbidden not in data
