"""Use-case tests for ``PersistReplayScoringArtifact`` against a fake writer port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from lottolab.application.use_cases.persist_replay_scoring_artifact import (
    PersistReplayScoringArtifact,
)
from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcome,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadResult,
)
from lottolab.domain.replay_scoring_projection import (
    ReplayScoringPersistenceOutcome,
    ReplayScoringPersistResult,
)
from lottolab.evidence.replay_artifact import (
    build_replay_artifact,
    build_replay_prediction_snapshot,
)
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    ReplayScoringArtifactTamperError,
    build_replay_scoring_artifact,
    serialize_replay_scoring_artifact,
)


class _Reader:
    def __init__(self, outcome: ReplayTargetOutcome) -> None:
        self.outcome = outcome

    def load_target_outcome(
        self, lottery_type: LotteryType, target_draw_number: str
    ) -> ReplayTargetOutcomeReadResult:
        if target_draw_number == self.outcome.target_draw_number:
            return ReplayTargetOutcomeReadResult.found(self.outcome)
        return ReplayTargetOutcomeReadResult.not_found(
            ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
        )


def _build_artifact() -> ReplayScoringArtifact:
    targets = (ReplayTarget("300", date(2026, 3, 1)),)
    snapshots = (
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[0],
            strategy_id="alpha",
            strategy_identity=("alpha", "Alpha", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=(1, 2, 3, 4, 5, 6),
        ),
    )
    source = build_replay_artifact(
        dataset_id="dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=("alpha",),
        targets=targets,
        snapshots=snapshots,
    )
    outcome = ReplayTargetOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number="300",
        target_draw_date=date(2026, 3, 1),
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


@dataclass
class _FakeWriter:
    outcome: ReplayScoringPersistenceOutcome = ReplayScoringPersistenceOutcome.INSERTED
    calls: list[tuple[ReplayScoringArtifact, bytes]] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def persist_replay_scoring_artifact(
        self, artifact: ReplayScoringArtifact, canonical_bytes: bytes
    ) -> ReplayScoringPersistResult:
        assert self.calls is not None
        self.calls.append((artifact, canonical_bytes))
        return ReplayScoringPersistResult(self.outcome, artifact.payload_sha256)


def test_execute_passes_the_complete_artifact_and_deterministic_canonical_bytes_to_writer() -> None:
    artifact = _build_artifact()
    writer = _FakeWriter()
    use_case = PersistReplayScoringArtifact(writer)

    use_case.execute(artifact)

    assert writer.calls is not None
    assert len(writer.calls) == 1
    passed_artifact, passed_bytes = writer.calls[0]
    assert passed_artifact is artifact
    assert passed_bytes == serialize_replay_scoring_artifact(artifact)
    assert passed_bytes == serialize_replay_scoring_artifact(artifact)  # deterministic, re-derived


def test_execute_propagates_inserted_outcome() -> None:
    artifact = _build_artifact()
    writer = _FakeWriter(outcome=ReplayScoringPersistenceOutcome.INSERTED)
    use_case = PersistReplayScoringArtifact(writer)

    result = use_case.execute(artifact)

    assert result.outcome is ReplayScoringPersistenceOutcome.INSERTED
    assert result.scoring_artifact_payload_sha256 == artifact.payload_sha256


def test_execute_propagates_already_present_outcome() -> None:
    artifact = _build_artifact()
    writer = _FakeWriter(outcome=ReplayScoringPersistenceOutcome.ALREADY_PRESENT)
    use_case = PersistReplayScoringArtifact(writer)

    result = use_case.execute(artifact)

    assert result.outcome is ReplayScoringPersistenceOutcome.ALREADY_PRESENT


def test_execute_propagates_conflict_outcome_without_raising() -> None:
    artifact = _build_artifact()
    writer = _FakeWriter(outcome=ReplayScoringPersistenceOutcome.CONFLICT)
    use_case = PersistReplayScoringArtifact(writer)

    result = use_case.execute(artifact)

    assert result.outcome is ReplayScoringPersistenceOutcome.CONFLICT


def test_execute_rejects_a_tampered_payload_hash_before_calling_the_writer() -> None:
    artifact = _build_artifact()
    object.__setattr__(artifact, "payload_sha256", "0" * 64)
    writer = _FakeWriter()
    use_case = PersistReplayScoringArtifact(writer)

    with pytest.raises(ReplayScoringArtifactTamperError):
        use_case.execute(artifact)
    assert writer.calls == []


def test_execute_rejects_a_tampered_nested_scored_result_hash_before_calling_the_writer() -> None:
    artifact = _build_artifact()
    tampered_record = object.__new__(type(artifact.scored_predictions[0]))
    for field_name in artifact.scored_predictions[0].__dataclass_fields__:
        object.__setattr__(
            tampered_record, field_name, getattr(artifact.scored_predictions[0], field_name)
        )
    object.__setattr__(tampered_record, "main_number_hit_count", 0)
    tampered_predictions = (tampered_record, *artifact.scored_predictions[1:])
    object.__setattr__(artifact, "scored_predictions", tampered_predictions)
    writer = _FakeWriter()
    use_case = PersistReplayScoringArtifact(writer)

    with pytest.raises(ReplayScoringArtifactTamperError):
        use_case.execute(artifact)
    assert writer.calls == []


def test_execute_rejects_a_tampered_nested_aggregation_hash_before_calling_the_writer() -> None:
    artifact = _build_artifact()
    tampered_overall = object.__new__(type(artifact.overall_aggregate))
    for field_name in artifact.overall_aggregate.__dataclass_fields__:
        object.__setattr__(
            tampered_overall, field_name, getattr(artifact.overall_aggregate, field_name)
        )
    object.__setattr__(tampered_overall, "no_prize_count", 99)
    object.__setattr__(artifact, "overall_aggregate", tampered_overall)
    writer = _FakeWriter()
    use_case = PersistReplayScoringArtifact(writer)

    with pytest.raises(ReplayScoringArtifactTamperError):
        use_case.execute(artifact)
    assert writer.calls == []


def test_execute_never_mutates_the_source_artifact() -> None:
    artifact = _build_artifact()
    before = serialize_replay_scoring_artifact(artifact)
    writer = _FakeWriter()
    use_case = PersistReplayScoringArtifact(writer)

    use_case.execute(artifact)

    after = serialize_replay_scoring_artifact(artifact)
    assert before == after


def test_execute_never_recomputes_scoring_and_returns_the_original_identity() -> None:
    artifact = _build_artifact()
    writer = _FakeWriter()
    use_case = PersistReplayScoringArtifact(writer)

    result = use_case.execute(artifact)

    assert result.scoring_artifact_payload_sha256 == artifact.payload_sha256
    assert artifact.scored_predictions[0].prize_tier_id is not None
