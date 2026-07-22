"""Unit coverage for the exact-run Replay-scoring projection query use case."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import cast

import pytest

from lottolab.application.use_cases.query_replay_scoring_projection import (
    QueryReplayScoringProjection,
    ReplayScoringRunNotFoundError,
)
from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
)
from lottolab.evidence.replay_scoring_artifact import ReplayScoringArtifact

_SHA = "a" * 64
_OTHER_SHA = "b" * 64


def _prediction(
    ordinal: int,
    *,
    strategy_id: str,
    scoring_status: str,
    no_prize_result: str | None = None,
    prize_tier_id: str | None = None,
) -> ReplayScoredPredictionProjection:
    scored = scoring_status == "SCORED"
    return ReplayScoredPredictionProjection(
        run_payload_sha256=_SHA,
        ordinal=ordinal,
        source_snapshot_result_sha256=("3", "4", "5")[ordinal] * 64,
        scored_result_sha256=("6", "7", "8")[ordinal] * 64,
        target_draw_number="300",
        target_draw_date="2026-03-01",
        strategy_id=strategy_id,
        strategy_version="1.0.0" if scored else None,
        source_history_status="OK" if scored else "TARGET_NOT_FOUND",
        source_history_reason_code=None if scored else "TARGET_DRAW_NOT_FOUND",
        source_prediction_status="OK" if scored else None,
        source_prediction_reason_code=None,
        scoring_status=scoring_status,
        scoring_reason_code=None if scored else "SOURCE_HISTORY_CLOSED",
        predicted_main_numbers=(1, 2, 3, 4, 5, 6) if scored else None,
        target_outcome_sha256="9" * 64 if scored else None,
        main_number_hit_count=6 if prize_tier_id is not None else (0 if scored else None),
        special_number_hit=False if scored else None,
        prize_tier_id=prize_tier_id,
        prize_official_label="頭獎" if prize_tier_id is not None else None,
        no_prize_result=no_prize_result,
    )


_PREDICTIONS = (
    _prediction(
        0,
        strategy_id="closed",
        scoring_status="NOT_SCORED_HISTORY_CLOSED",
    ),
    _prediction(
        1,
        strategy_id="loser",
        scoring_status="SCORED",
        no_prize_result="NO_PRIZE",
    ),
    _prediction(
        2,
        strategy_id="winner",
        scoring_status="SCORED",
        prize_tier_id="FIRST",
    ),
)

_RUN = ReplayScoringRunProjection(
    scoring_artifact_schema_version="1.0.0",
    scoring_artifact_payload_sha256=_SHA,
    source_replay_artifact_payload_sha256=_OTHER_SHA,
    dataset_id="dataset",
    dataset_version="1",
    lottery_type="BIG_LOTTO",
    target_count=1,
    strategy_count=3,
    scored_record_count=3,
    overall_aggregate_sha256="c" * 64,
)


def _aggregate(
    ordinal: int, strategy_id: str, *, closed: int = 0, first: int = 0, no_prize: int = 0
) -> ReplayStrategyAggregateProjection:
    return ReplayStrategyAggregateProjection(
        run_payload_sha256=_SHA,
        ordinal=ordinal,
        strategy_id=strategy_id,
        strategy_version=None if closed else "1.0.0",
        source_snapshot_count=1,
        scored_count=first + no_prize,
        history_closed_count=closed,
        prediction_closed_count=0,
        target_outcome_not_found_count=0,
        target_identity_mismatch_count=0,
        first_prize_count=first,
        second_prize_count=0,
        third_prize_count=0,
        fourth_prize_count=0,
        fifth_prize_count=0,
        sixth_prize_count=0,
        seventh_prize_count=0,
        general_prize_count=0,
        no_prize_count=no_prize,
        aggregate_sha256=chr(ord("d") + ordinal) * 64,
    )


_STRATEGY_AGGREGATES = (
    _aggregate(0, "closed", closed=1),
    _aggregate(1, "loser", no_prize=1),
    _aggregate(2, "winner", first=1),
)

_OVERALL = ReplayOverallAggregateProjection(
    run_payload_sha256=_SHA,
    source_snapshot_count=3,
    scored_count=2,
    history_closed_count=1,
    prediction_closed_count=0,
    target_outcome_not_found_count=0,
    target_identity_mismatch_count=0,
    first_prize_count=1,
    second_prize_count=0,
    third_prize_count=0,
    fourth_prize_count=0,
    fifth_prize_count=0,
    sixth_prize_count=0,
    seventh_prize_count=0,
    general_prize_count=0,
    no_prize_count=1,
    aggregate_sha256="c" * 64,
)


class _Reader:
    def __init__(self, *, found: bool = True, fail: bool = False) -> None:
        self.found = found
        self.fail = fail
        self.calls: Counter[str] = Counter()

    def get_replay_scoring_artifact(self, scoring_artifact_payload_sha256: str):
        self.calls["get_artifact"] += 1
        if self.fail:
            raise RuntimeError("private storage path /tmp/secret.db")
        if not self.found:
            return None
        return cast(ReplayScoringArtifact, object())

    def get_run(self, scoring_artifact_payload_sha256: str):
        self.calls["get_run"] += 1
        return _RUN

    def list_scored_predictions(
        self,
        scoring_artifact_payload_sha256: str,
        *,
        target_draw_number: str | None = None,
        strategy_id: str | None = None,
    ):
        self.calls["list_predictions"] += 1
        return tuple(
            record
            for record in _PREDICTIONS
            if (target_draw_number is None or record.target_draw_number == target_draw_number)
            and (strategy_id is None or record.strategy_id == strategy_id)
        )

    def list_strategy_aggregates(self, scoring_artifact_payload_sha256: str):
        self.calls["list_strategy_aggregates"] += 1
        return _STRATEGY_AGGREGATES

    def get_overall_aggregate(self, scoring_artifact_payload_sha256: str):
        self.calls["get_overall_aggregate"] += 1
        return _OVERALL


class _Factory:
    def __init__(self, reader: _Reader) -> None:
        self.reader = reader
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


type _Operation = Callable[[QueryReplayScoringProjection], object]


def _get_run(query: QueryReplayScoringProjection) -> object:
    return query.get_run(_SHA)


def _get_artifact(query: QueryReplayScoringProjection) -> object:
    return query.get_artifact(_SHA)


def _list_predictions(query: QueryReplayScoringProjection) -> object:
    return query.list_predictions(_SHA)


def _list_strategy_aggregates(query: QueryReplayScoringProjection) -> object:
    return query.list_strategy_aggregates(_SHA)


def _get_overall_aggregate(query: QueryReplayScoringProjection) -> object:
    return query.get_overall_aggregate(_SHA)


@pytest.mark.parametrize("invalid_sha", ["short", "A" * 64, "g" * 64, "a" * 63])
def test_sha_validation_precedes_factory_call(invalid_sha: str) -> None:
    factory = _Factory(_Reader())
    query = QueryReplayScoringProjection(factory)

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        query.get_run(invalid_sha)

    assert factory.calls == 0


@pytest.mark.parametrize(
    ("filters", "message"),
    [
        ({"target_draw": " 300"}, "target_draw_number"),
        ({"strategy_id": ""}, "strategy_id"),
        ({"status": "UNKNOWN"}, "status"),
        ({"tier": "JACKPOT"}, "tier"),
    ],
)
def test_invalid_prediction_filters_precede_factory_call(
    filters: dict[str, str], message: str
) -> None:
    factory = _Factory(_Reader())
    query = QueryReplayScoringProjection(factory)

    with pytest.raises(ValueError, match=message):
        query.list_predictions(_SHA, **filters)

    assert factory.calls == 0


@pytest.mark.parametrize(
    ("operation", "reader_call"),
    [
        (_get_artifact, "get_artifact"),
        (_get_run, "get_run"),
        (_list_predictions, "list_predictions"),
        (_list_strategy_aggregates, "list_strategy_aggregates"),
        (_get_overall_aggregate, "get_overall_aggregate"),
    ],
)
def test_each_operation_creates_and_integrity_checks_exactly_one_reader(
    operation: _Operation, reader_call: str
) -> None:
    reader = _Reader()
    factory = _Factory(reader)

    operation(QueryReplayScoringProjection(factory))

    assert factory.calls == 1
    expected_calls = Counter({"get_artifact": 1, reader_call: 1})
    if reader_call == "get_artifact":
        expected_calls = Counter({"get_artifact": 1})
    assert reader.calls == expected_calls


def test_missing_exact_run_raises_without_fallback() -> None:
    reader = _Reader(found=False)
    factory = _Factory(reader)

    with pytest.raises(ReplayScoringRunNotFoundError):
        QueryReplayScoringProjection(factory).get_run(_OTHER_SHA)

    assert factory.calls == 1
    assert reader.calls == Counter({"get_artifact": 1})


def test_get_artifact_returns_the_exact_typed_reader_result() -> None:
    artifact = cast(ReplayScoringArtifact, object())
    reader = _Reader()
    reader.get_replay_scoring_artifact = lambda sha: artifact  # type: ignore[method-assign]
    factory = _Factory(reader)

    result = QueryReplayScoringProjection(factory).get_artifact(_SHA)

    assert result is artifact
    assert factory.calls == 1


def test_prediction_filters_preserve_stored_order_and_exact_semantics() -> None:
    query = QueryReplayScoringProjection(_Factory(_Reader()))

    all_records = query.list_predictions(_SHA)
    no_prize = query.list_predictions(_SHA, status="SCORED", tier="NO_PRIZE")
    closed = query.list_predictions(_SHA, status="NOT_SCORED_HISTORY_CLOSED")
    winner = query.list_predictions(_SHA, strategy_id="winner", tier="FIRST")

    assert [record.ordinal for record in all_records] == [0, 1, 2]
    assert [record.no_prize_result for record in no_prize] == ["NO_PRIZE"]
    assert [record.scoring_status for record in closed] == [
        "NOT_SCORED_HISTORY_CLOSED"
    ]
    assert [record.prize_tier_id for record in winner] == ["FIRST"]


def test_storage_failure_is_not_reclassified_as_not_found() -> None:
    query = QueryReplayScoringProjection(_Factory(_Reader(fail=True)))

    with pytest.raises(RuntimeError, match="private storage path"):
        query.get_run(_SHA)
