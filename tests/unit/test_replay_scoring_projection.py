"""Shape and invariant tests for the Replay-scoring projection domain types."""

from __future__ import annotations

from typing import Any

import pytest

from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringPersistenceOutcome,
    ReplayScoringPersistResult,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
)

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _run(**overrides: object) -> ReplayScoringRunProjection:
    values: dict[str, Any] = {
        "scoring_artifact_schema_version": "1.0.0",
        "scoring_artifact_payload_sha256": _SHA_A,
        "source_replay_artifact_payload_sha256": _SHA_B,
        "dataset_id": "dataset",
        "dataset_version": "1",
        "lottery_type": "BIG_LOTTO",
        "target_count": 2,
        "strategy_count": 2,
        "scored_record_count": 4,
        "overall_aggregate_sha256": _SHA_C,
    }
    values.update(overrides)
    return ReplayScoringRunProjection(**values)


def _prediction(**overrides: object) -> ReplayScoredPredictionProjection:
    values: dict[str, Any] = {
        "run_payload_sha256": _SHA_A,
        "ordinal": 0,
        "source_snapshot_result_sha256": _SHA_B,
        "scored_result_sha256": _SHA_C,
        "target_draw_number": "300",
        "target_draw_date": "2026-03-01",
        "strategy_id": "alpha",
        "strategy_version": "1.0.0",
        "source_history_status": "OK",
        "source_history_reason_code": None,
        "source_prediction_status": "OK",
        "source_prediction_reason_code": None,
        "scoring_status": "SCORED",
        "scoring_reason_code": None,
        "predicted_main_numbers": (1, 2, 3, 4, 5, 6),
        "target_outcome_sha256": _SHA_B,
        "main_number_hit_count": 6,
        "special_number_hit": False,
        "prize_tier_id": "FIRST",
        "prize_official_label": "頭獎",
        "no_prize_result": None,
    }
    values.update(overrides)
    return ReplayScoredPredictionProjection(**values)


def _aggregate_counts() -> dict[str, int]:
    return {
        "source_snapshot_count": 2,
        "scored_count": 1,
        "history_closed_count": 1,
        "prediction_closed_count": 0,
        "target_outcome_not_found_count": 0,
        "target_identity_mismatch_count": 0,
        "first_prize_count": 1,
        "second_prize_count": 0,
        "third_prize_count": 0,
        "fourth_prize_count": 0,
        "fifth_prize_count": 0,
        "sixth_prize_count": 0,
        "seventh_prize_count": 0,
        "general_prize_count": 0,
        "no_prize_count": 0,
    }


def _strategy_aggregate(**overrides: object) -> ReplayStrategyAggregateProjection:
    values: dict[str, Any] = {
        "run_payload_sha256": _SHA_A,
        "ordinal": 0,
        "strategy_id": "alpha",
        "strategy_version": "1.0.0",
        **_aggregate_counts(),
        "aggregate_sha256": _SHA_C,
    }
    values.update(overrides)
    return ReplayStrategyAggregateProjection(**values)


def _overall_aggregate(**overrides: object) -> ReplayOverallAggregateProjection:
    values: dict[str, Any] = {
        "run_payload_sha256": _SHA_A,
        **_aggregate_counts(),
        "aggregate_sha256": _SHA_C,
    }
    values.update(overrides)
    return ReplayOverallAggregateProjection(**values)


def test_run_projection_constructs_with_valid_fields() -> None:
    run = _run()
    assert run.scoring_artifact_payload_sha256 == _SHA_A
    assert run.target_count * run.strategy_count == run.scored_record_count


@pytest.mark.parametrize(
    "field,value",
    [
        ("scoring_artifact_payload_sha256", "not-a-sha"),
        ("source_replay_artifact_payload_sha256", "short"),
        ("overall_aggregate_sha256", ""),
        ("dataset_id", ""),
        ("lottery_type", ""),
    ],
)
def test_run_projection_rejects_invalid_sha_or_text(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _run(**{field: value})


def test_run_projection_rejects_target_strategy_count_mismatch() -> None:
    with pytest.raises(ValueError):
        _run(scored_record_count=5)


def test_run_projection_rejects_negative_counts() -> None:
    with pytest.raises(ValueError):
        _run(target_count=-1, scored_record_count=-2)


@pytest.mark.parametrize("field", ["target_count", "strategy_count", "scored_record_count"])
def test_run_projection_rejects_bool_count_fields(field: str) -> None:
    with pytest.raises(ValueError):
        _run(**{field: True})


def test_scored_prediction_projection_constructs_with_valid_fields() -> None:
    prediction = _prediction()
    assert prediction.ordinal == 0
    assert prediction.prize_tier_id == "FIRST"


def test_scored_prediction_projection_accepts_no_prize_variant() -> None:
    prediction = _prediction(
        prize_tier_id=None,
        prize_official_label=None,
        main_number_hit_count=0,
        special_number_hit=False,
        no_prize_result="NO_PRIZE",
    )
    assert prediction.no_prize_result == "NO_PRIZE"


def test_scored_prediction_projection_accepts_not_scored_variant() -> None:
    prediction = _prediction(
        source_prediction_status=None,
        source_prediction_reason_code=None,
        scoring_status="NOT_SCORED_HISTORY_CLOSED",
        scoring_reason_code="SOURCE_HISTORY_CLOSED",
        predicted_main_numbers=None,
        target_outcome_sha256=None,
        main_number_hit_count=None,
        special_number_hit=None,
        prize_tier_id=None,
        prize_official_label=None,
        no_prize_result=None,
    )
    assert prediction.scoring_status == "NOT_SCORED_HISTORY_CLOSED"


@pytest.mark.parametrize(
    "field,value", [("run_payload_sha256", "bad"), ("scored_result_sha256", "x")]
)
def test_scored_prediction_projection_rejects_invalid_sha(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _prediction(**{field: value})


@pytest.mark.parametrize("ordinal", [-1, -100])
def test_scored_prediction_projection_rejects_negative_ordinal(ordinal: int) -> None:
    with pytest.raises(ValueError):
        _prediction(ordinal=ordinal)


def test_scored_prediction_projection_rejects_bool_as_ordinal() -> None:
    with pytest.raises(ValueError):
        _prediction(ordinal=True)


def test_scored_prediction_projection_rejects_prize_tier_without_label() -> None:
    with pytest.raises(ValueError):
        _prediction(prize_official_label=None)


def test_scored_prediction_projection_rejects_both_prize_tier_and_no_prize() -> None:
    with pytest.raises(ValueError):
        _prediction(no_prize_result="NO_PRIZE")


def test_scored_prediction_projection_rejects_malformed_predicted_numbers() -> None:
    with pytest.raises(ValueError):
        _prediction(predicted_main_numbers=[1, 2, 3])  # type: ignore[arg-type]


def test_scored_prediction_projection_rejects_bool_hit_count() -> None:
    with pytest.raises(ValueError):
        _prediction(main_number_hit_count=True)


def test_strategy_aggregate_projection_constructs_with_valid_fields() -> None:
    aggregate = _strategy_aggregate()
    assert aggregate.strategy_id == "alpha"


def test_strategy_aggregate_projection_rejects_negative_ordinal() -> None:
    with pytest.raises(ValueError):
        _strategy_aggregate(ordinal=-1)


def test_strategy_aggregate_projection_rejects_partial_identity() -> None:
    with pytest.raises(ValueError):
        _strategy_aggregate(strategy_id="")


@pytest.mark.parametrize(
    "field", ["source_snapshot_count", "scored_count", "first_prize_count", "no_prize_count"]
)
def test_strategy_aggregate_projection_rejects_bool_count_fields(field: str) -> None:
    with pytest.raises(ValueError):
        _strategy_aggregate(**{field: True})


@pytest.mark.parametrize(
    "field", ["source_snapshot_count", "scored_count", "first_prize_count", "no_prize_count"]
)
def test_strategy_aggregate_projection_rejects_negative_count_fields(field: str) -> None:
    with pytest.raises(ValueError):
        _strategy_aggregate(**{field: -1})


def test_strategy_aggregate_projection_rejects_broken_conservation_equation() -> None:
    with pytest.raises(ValueError):
        _strategy_aggregate(source_snapshot_count=99)


def test_strategy_aggregate_projection_rejects_broken_prize_conservation() -> None:
    with pytest.raises(ValueError):
        _strategy_aggregate(scored_count=99)


def test_overall_aggregate_projection_constructs_with_valid_fields() -> None:
    overall = _overall_aggregate()
    assert overall.run_payload_sha256 == _SHA_A


def test_overall_aggregate_projection_rejects_broken_conservation_equation() -> None:
    with pytest.raises(ValueError):
        _overall_aggregate(source_snapshot_count=0)


_FORBIDDEN_FIELD_TOKENS = frozenset({"payout", "amount", "rate", "roi", "ranking", "rank"})


def _assert_no_monetary_or_rate_fields(field_names: set[str]) -> None:
    tokens = {token for name in field_names for token in name.lower().split("_")}
    assert not (tokens & _FORBIDDEN_FIELD_TOKENS)


def test_overall_aggregate_projection_has_no_monetary_or_rate_fields() -> None:
    _assert_no_monetary_or_rate_fields(set(ReplayOverallAggregateProjection.__dataclass_fields__))


def test_strategy_aggregate_projection_has_no_monetary_or_rate_fields() -> None:
    _assert_no_monetary_or_rate_fields(set(ReplayStrategyAggregateProjection.__dataclass_fields__))


def test_persist_result_constructs_with_valid_outcome() -> None:
    result = ReplayScoringPersistResult(ReplayScoringPersistenceOutcome.INSERTED, _SHA_A)
    assert result.outcome is ReplayScoringPersistenceOutcome.INSERTED


def test_persist_result_rejects_invalid_sha() -> None:
    with pytest.raises(ValueError):
        ReplayScoringPersistResult(ReplayScoringPersistenceOutcome.INSERTED, "bad")


def test_persist_result_rejects_non_enum_outcome() -> None:
    with pytest.raises(ValueError):
        ReplayScoringPersistResult("INSERTED", _SHA_A)  # type: ignore[arg-type]
