"""Use-case coverage for deterministic post-hoc Replay prize scoring."""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pytest

from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain import lottery_rules
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BigLottoPrizeTierId, NoPrizeResult
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot, ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayScoringReason,
    ReplayScoringStatus,
    ReplayTargetOutcome,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadResult,
)
from lottolab.evidence.replay_artifact import (
    ReplayArtifact,
    build_replay_artifact,
    build_replay_prediction_snapshot,
    serialize_replay_artifact,
)


class FakeOutcomeReader:
    def __init__(self, outcomes: dict[str, ReplayTargetOutcome]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    def load_target_outcome(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
    ) -> ReplayTargetOutcomeReadResult:
        assert lottery_type is LotteryType.BIG_LOTTO
        self.calls.append(target_draw_number)
        outcome = self.outcomes.get(target_draw_number)
        if outcome is None:
            return ReplayTargetOutcomeReadResult.not_found(
                ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
            )
        return ReplayTargetOutcomeReadResult.found(outcome)


def _target(index: int) -> ReplayTarget:
    return ReplayTarget(str(100 + index), date(2026, 1, 1) + timedelta(days=index))


def _outcome(target: ReplayTarget, *, draw_number: str | None = None) -> ReplayTargetOutcome:
    return ReplayTargetOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number=draw_number or target.draw_number,
        target_draw_date=target.draw_date,
        winning_main_numbers=(1, 2, 3, 4, 5, 6),
        winning_special_number=7,
    )


def _snapshot(
    target: ReplayTarget,
    strategy_id: str,
    *,
    predicted: tuple[int, ...] | None = (1, 2, 3, 4, 5, 6),
    history_status: str = "OK",
    history_reason: str | None = None,
    prediction_status: str | None = "OK",
    prediction_reason: str | None = None,
    strategy_known: bool = True,
) -> ReplayPredictionSnapshot:
    return build_replay_prediction_snapshot(
        dataset_id="dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        target=target,
        strategy_id=strategy_id,
        strategy_identity=(strategy_id, f"{strategy_id} name", "1.0.0") if strategy_known else None,
        history_status=history_status,
        history_reason_code=history_reason,
        causal_history=() if history_status == "OK" else None,
        prediction_status=prediction_status,
        prediction_reason_code=prediction_reason,
        predicted_main_numbers=predicted,
    )


def _artifact(
    targets: tuple[ReplayTarget, ...],
    strategy_ids: tuple[str, ...],
    snapshots: tuple[ReplayPredictionSnapshot, ...],
) -> ReplayArtifact:
    return build_replay_artifact(
        dataset_id="dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=strategy_ids,
        targets=targets,
        snapshots=snapshots,
    )


def _always_no_prize(_main_hits: int, _special_hit: bool) -> NoPrizeResult:
    return NoPrizeResult.NO_PRIZE


_SIGNATURES = (
    ((1, 2, 3, 4, 5, 6), BigLottoPrizeTierId.FIRST),
    ((1, 2, 3, 4, 5, 7), BigLottoPrizeTierId.SECOND),
    ((1, 2, 3, 4, 5, 8), BigLottoPrizeTierId.THIRD),
    ((1, 2, 3, 4, 7, 8), BigLottoPrizeTierId.FOURTH),
    ((1, 2, 3, 4, 8, 9), BigLottoPrizeTierId.FIFTH),
    ((1, 2, 3, 7, 8, 9), BigLottoPrizeTierId.SIXTH),
    ((1, 2, 7, 8, 9, 10), BigLottoPrizeTierId.SEVENTH),
    ((1, 2, 3, 8, 9, 10), BigLottoPrizeTierId.GENERAL),
)


def test_all_eight_tiers_and_no_prize_use_the_merged_resolver_and_exact_aggregates() -> None:
    targets = tuple(_target(index) for index in range(9))
    predictions = (
        *(signature for signature, _tier in _SIGNATURES),
        (1, 8, 9, 10, 11, 12),
    )
    source = _artifact(
        targets,
        ("strategy",),
        tuple(
            _snapshot(target, "strategy", predicted=predicted)
            for target, predicted in zip(targets, predictions, strict=True)
        ),
    )
    reader = FakeOutcomeReader({target.draw_number: _outcome(target) for target in targets})

    result = ScoreReplayArtifact(reader).execute(source)

    assert len(result.scored_predictions) == len(source.snapshots) == 9
    assert tuple(record.target_draw_number for record in result.scored_predictions) == tuple(
        target.draw_number for target in targets
    )
    assert tuple(record.prize_tier_id for record in result.scored_predictions[:8]) == tuple(
        tier for _signature, tier in _SIGNATURES
    )
    assert result.scored_predictions[-1].no_prize_result is NoPrizeResult.NO_PRIZE
    assert reader.calls == [target.draw_number for target in targets]
    aggregate = result.overall_aggregate
    assert aggregate.source_snapshot_count == aggregate.scored_count == 9
    assert aggregate.no_prize_count == 1
    assert (
        aggregate.first_prize_count,
        aggregate.second_prize_count,
        aggregate.third_prize_count,
        aggregate.fourth_prize_count,
        aggregate.fifth_prize_count,
        aggregate.sixth_prize_count,
        aggregate.seventh_prize_count,
        aggregate.general_prize_count,
    ) == (1, 1, 1, 1, 1, 1, 1, 1)
    assert result.strategy_aggregates[0].source_snapshot_count == 9


def test_target_major_strategy_minor_order_is_preserved_and_each_target_loads_once() -> None:
    targets = (_target(1), _target(2))
    strategies = ("alpha", "beta")
    snapshots = tuple(
        _snapshot(target, strategy)
        for target in targets
        for strategy in strategies
    )
    source = _artifact(targets, strategies, snapshots)
    reader = FakeOutcomeReader({target.draw_number: _outcome(target) for target in targets})

    result = ScoreReplayArtifact(reader).execute(source)

    assert tuple(
        (record.target_draw_number, record.strategy_id)
        for record in result.scored_predictions
    ) == tuple((target.draw_number, strategy) for target in targets for strategy in strategies)
    assert reader.calls == [target.draw_number for target in targets]
    assert [aggregate.strategy_id for aggregate in result.strategy_aggregates] == list(strategies)
    assert result.overall_aggregate.source_snapshot_count == 4


def test_closed_missing_and_mismatched_snapshots_each_emit_one_typed_record() -> None:
    targets = tuple(_target(index) for index in range(4))
    snapshots = (
        _snapshot(
            targets[0],
            "strategy",
            predicted=None,
            history_status="TARGET_NOT_FOUND",
            history_reason="TARGET_DRAW_NOT_FOUND",
            prediction_status=None,
        ),
        _snapshot(
            targets[1],
            "strategy",
            predicted=None,
            prediction_status="STRATEGY_NOT_FOUND",
            prediction_reason="UNKNOWN_STRATEGY",
        ),
        _snapshot(targets[2], "strategy"),
        _snapshot(targets[3], "strategy"),
    )
    source = _artifact(targets, ("strategy",), snapshots)
    mismatched = _outcome(targets[3], draw_number="999")
    reader = FakeOutcomeReader({targets[3].draw_number: mismatched})

    result = ScoreReplayArtifact(reader).execute(source)

    assert tuple(record.scoring_status for record in result.scored_predictions) == (
        ReplayScoringStatus.NOT_SCORED_HISTORY_CLOSED,
        ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED,
        ReplayScoringStatus.TARGET_OUTCOME_NOT_FOUND,
        ReplayScoringStatus.TARGET_IDENTITY_MISMATCH,
    )
    assert (
        result.scored_predictions[0].scoring_reason_code
        is ReplayScoringReason.SOURCE_HISTORY_CLOSED
    )
    assert result.scored_predictions[2].main_number_hit_count is None
    assert result.scored_predictions[3].target_outcome_sha256 == mismatched.outcome_sha256
    assert reader.calls == [targets[2].draw_number, targets[3].draw_number]
    aggregate = result.overall_aggregate
    assert aggregate.source_snapshot_count == 4
    assert aggregate.scored_count == 0
    assert aggregate.history_closed_count == 1
    assert aggregate.prediction_closed_count == 1
    assert aggregate.target_outcome_not_found_count == 1
    assert aggregate.target_identity_mismatch_count == 1


def test_source_replay_artifact_bytes_and_hash_remain_identical() -> None:
    target = _target(1)
    source = _artifact((target,), ("strategy",), (_snapshot(target, "strategy"),))
    before_bytes = serialize_replay_artifact(source)
    before_hash = source.payload_sha256

    ScoreReplayArtifact(FakeOutcomeReader({target.draw_number: _outcome(target)})).execute(source)

    assert serialize_replay_artifact(source) == before_bytes
    assert source.payload_sha256 == before_hash


def test_live_resolver_behavior_is_observed_without_a_copied_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _target(1)
    source = _artifact((target,), ("strategy",), (_snapshot(target, "strategy"),))
    monkeypatch.setattr(
        lottery_rules,
        "resolve_big_lotto_prize_tier",
        _always_no_prize,
    )

    result = ScoreReplayArtifact(
        FakeOutcomeReader({target.draw_number: _outcome(target)})
    ).execute(source)

    assert result.scored_predictions[0].no_prize_result is NoPrizeResult.NO_PRIZE


def test_invalid_source_artifact_hash_fails_before_any_target_read() -> None:
    target = _target(1)
    source = _artifact((target,), ("strategy",), (_snapshot(target, "strategy"),))
    tampered = dataclasses.replace(source, payload_sha256="d" * 64)
    reader = FakeOutcomeReader({target.draw_number: _outcome(target)})

    with pytest.raises(ValueError, match="payload_sha256 mismatch"):
        ScoreReplayArtifact(reader).execute(tampered)
    assert reader.calls == []


def test_mismatched_source_strategy_identity_fails_closed_before_target_read() -> None:
    target = _target(1)
    snapshot = build_replay_prediction_snapshot(
        dataset_id="dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        target=target,
        strategy_id="strategy",
        strategy_identity=("different", "Different", "1.0.0"),
        history_status="OK",
        history_reason_code=None,
        causal_history=(),
        prediction_status="OK",
        prediction_reason_code=None,
        predicted_main_numbers=(1, 2, 3, 4, 5, 6),
    )
    source = _artifact((target,), ("strategy",), (snapshot,))
    reader = FakeOutcomeReader({target.draw_number: _outcome(target)})

    with pytest.raises(ValueError, match="strategy identity mismatch"):
        ScoreReplayArtifact(reader).execute(source)
    assert reader.calls == []


def test_non_normalized_source_target_fails_closed_before_target_read() -> None:
    target = ReplayTarget("\uff13\uff10\uff10", date(2026, 1, 1))
    source = _artifact((target,), ("strategy",), (_snapshot(target, "strategy"),))
    reader = FakeOutcomeReader({})

    with pytest.raises(ValueError, match="ASCII decimal digits"):
        ScoreReplayArtifact(reader).execute(source)
    assert reader.calls == []
