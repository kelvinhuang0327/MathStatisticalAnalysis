"""Integration checks for the frozen-input B649 canonical authority."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
import tools.materialize_b649_canonical_forecast as materializer

from lottolab.domain.b649_canonical_consensus import (
    CanonicalConsensusContext,
    StreamConsensusInput,
    build_canonical_consensus,
)
from lottolab.evidence.canonical_json import canonical_file_bytes
from lottolab.infrastructure.b649_canonical_forecast_writer import StagedCanonicalForecast

FIXTURE_NUMBERS = (4, 12, 24, 25, 26, 29)
FIXTURE_PREDICTION_CREATED_AT = "2026-09-10T13:00:00+00:00"
HISTORICAL_087_TICKETS = {
    "b649_new_horizon_minimax_disagreement_r1": (
        (15, 16, 23, 26, 29, 35),
        (4, 7, 12, 22, 29, 34),
    ),
    "biglotto_deviation_2bet": ((4, 12, 16, 25, 26, 29),),
    "biglotto_social_wisdom_anti_popularity": ((42, 43, 44, 45, 47, 49),),
    "legacy_biglotto__graph_predictor__cd70713a5709": ((16, 23, 24, 26, 29, 47),),
    "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8": ((12, 24, 25, 26, 29, 35),),
    "legacy_biglotto__pure_cold_predict__9e89f2b41add": ((7, 22, 31, 38, 39, 42),),
    "legacy_biglotto__test_asm__d39a233a4c75": (
        (1, 4, 6, 9, 10, 25),
        (1, 4, 34, 36, 45, 46),
        (6, 8, 9, 10, 11, 18),
    ),
    "legacy_biglotto__test_ces__78d17c530ab8": (
        (8, 9, 11, 26, 29, 43),
        (1, 9, 18, 19, 26, 39),
        (4, 9, 18, 24, 28, 29),
    ),
    "legacy_biglotto__test_ecp__c9d5ac6decdd": (
        (8, 10, 11, 18, 19, 43),
        (10, 25, 34, 36, 43, 45),
        (1, 4, 6, 36, 45, 46),
    ),
    "legacy_biglotto__test_mwsc__ba37643d6a3b": (
        (10, 12, 25, 26, 36, 38),
        (10, 24, 36, 45, 46, 47),
        (24, 32, 34, 39, 40, 47),
    ),
    "legacy_biglotto__test_tme__f3bb5106dfe3": (
        (2, 8, 11, 18, 19, 43),
        (1, 2, 3, 4, 6, 9),
        (9, 26, 28, 29, 39, 44),
    ),
}
HISTORICAL_087_RANKING = (
    29,
    26,
    4,
    24,
    25,
    12,
    47,
    16,
    9,
    43,
    45,
    10,
    39,
    42,
    1,
    18,
    36,
    7,
    22,
    23,
    34,
    35,
    6,
    8,
    11,
    38,
    44,
    19,
    31,
    46,
    49,
    2,
    28,
    15,
    3,
    32,
    40,
    5,
    13,
    14,
    17,
    20,
    21,
    27,
    30,
    33,
    37,
    41,
    48,
)
HISTORICAL_087_SUPPORT_UNITS = (
    30,
    29,
    19,
    18,
    18,
    17,
    16,
    15,
    14,
    14,
    14,
    12,
    12,
    12,
    10,
    10,
    10,
    9,
    9,
    9,
    9,
    9,
    8,
    8,
    8,
    8,
    8,
    6,
    6,
    6,
    6,
    4,
    4,
    3,
    2,
    2,
    2,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
)
HISTORICAL_087_MANIFEST_SHA256 = "ce725dfdb2e162f1c68f9cb2dc75bc2fc073a0ba55ea6fa29a4fbc5cc647ded8"
FIXTURE_STREAM_INPUT_MANIFEST_SHA256 = (
    "b92fa0bdfac9032d10de8fb409466652ba4765578bbd07be038b7d0442d5e221"
)
IDENTITY = materializer.ImplementationIdentity(
    commit="a" * 40,
    tree="b" * 40,
    source_hashes=tuple(
        materializer.ImplementationSource(path, "c" * 64)
        for path in materializer.IMPLEMENTATION_SOURCE_PATHS
    ),
)
HISTORICAL_IDENTITY = materializer.ImplementationIdentity(
    commit="d" * 40,
    tree="e" * 40,
    source_hashes=tuple(
        materializer.ImplementationSource(path, "f" * 64)
        for path in materializer.IMPLEMENTATION_SOURCE_PATHS
    ),
)
CREATED_AT = datetime(2026, 9, 10, 14, 0, 0, tzinfo=UTC)
PRE_PUBLISH_AT = datetime(2026, 9, 10, 14, 0, 1, tzinfo=UTC)


def _copy_inputs(
    destination: Path,
    *,
    tickets_by_strategy: dict[str, tuple[tuple[int, ...], ...]] | None = None,
) -> None:
    ticket_sets = {} if tickets_by_strategy is None else tickets_by_strategy
    for spec in materializer.FROZEN_STREAM_SPECS:
        target = destination / spec.source_relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tickets = ticket_sets.get(spec.strategy_id)
        if tickets is None:
            tickets = tuple(FIXTURE_NUMBERS for _ in range(spec.native_ticket_count))
        assert len(tickets) == spec.native_ticket_count
        payload = {
            "schema_version": "b649-operational-prediction-v1",
            "task_id": "B649_OPERATIONAL_PREDICTION_LOOP_R1",
            "lottery_type": "BIG_LOTTO",
            "draw_number": "115000087",
            "draw_date": "2026-09-11",
            "scheduled_at": "2026-09-11T20:30:00+08:00",
            "prediction_temporal_class": "PRE_DRAW",
            "availability": "AVAILABLE",
            "history_draw_count": 2168,
            "history_sha256": "c2ba95be375c739c096baaae6ac03b666bc93ef81c9a721ec9381ed7b4c2cec4",
            "history_caveat": "YES",
            "history_cutoff": {"draw_number": "115000086", "draw_date": "2026-09-08"},
            "strategy_id": spec.strategy_id,
            "strategy_version": spec.strategy_version,
            "native_ticket_count": spec.native_ticket_count,
            "prediction_run_id": Path(spec.source_relative_path).stem,
            "prediction_created_at": FIXTURE_PREDICTION_CREATED_AT,
            "tickets": [
                {
                    "ticket_position": position,
                    "predicted_numbers": list(numbers),
                }
                for position, numbers in enumerate(tickets, start=1)
            ],
        }
        target.write_bytes(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        )


def _clock(*values: datetime):
    iterator = iter(values)

    def next_value() -> datetime:
        return next(iterator)

    return next_value


def test_materializes_exact_11_stream_authority_and_is_idempotent(tmp_path: Path) -> None:
    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root)
    destination = tmp_path / "authority" / "final_forecast_payload.json"

    result = materializer.materialize_canonical_forecast(
        operation_root=operation_root,
        destination=destination,
        implementation_identity=IDENTITY,
        specs=materializer.FROZEN_STREAM_SPECS,
        expected_manifest_sha256=None,
        clock=_clock(CREATED_AT, PRE_PUBLISH_AT),
    )

    assert result.status == "CREATED"
    assert result.payload["target_result_used"] is False
    assert result.payload["stream_count"] == 11
    ranking_value = result.payload["final_decision_ranking"]
    assert isinstance(ranking_value, list)
    ranking = cast(list[dict[str, object]], ranking_value)
    assert len(ranking) == 49
    assert [entry["number"] for entry in ranking[:10]] == [4, 12, 24, 25, 26, 29, 1, 2, 3, 5]
    assert [entry["support_units"] for entry in ranking[:6]] == [66] * 6
    assert all(entry["support_units"] == 0 for entry in ranking[6:])
    assert result.payload["final_recommended_output"] == [
        {"ticket_position": 1, "predicted_numbers": [4, 12, 24, 25, 26, 29]}
    ]
    assert (
        result.payload["stream_input_manifest_sha256"]
        == FIXTURE_STREAM_INPUT_MANIFEST_SHA256
    )
    assert result.payload["aggregation_method_id"] == (
        "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
    )
    assert result.payload["aggregation_method_version"] == "1.0.0"
    raw = destination.read_bytes()
    assert raw == canonical_file_bytes(result.payload)
    assert not list(destination.parent.glob("*.tmp"))

    def clock_must_not_be_called() -> datetime:
        raise AssertionError("idempotent authority retry sampled the clock")

    retry = materializer.materialize_canonical_forecast(
        operation_root=operation_root,
        destination=destination,
        implementation_identity=IDENTITY,
        specs=materializer.FROZEN_STREAM_SPECS,
        expected_manifest_sha256=None,
        clock=clock_must_not_be_called,
    )
    assert retry.status == "ALREADY_PRESENT"
    assert destination.read_bytes() == raw


def test_created_at_boundary_fails_closed_without_authority_file(tmp_path: Path) -> None:
    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root)
    destination = tmp_path / "authority" / "final_forecast_payload.json"
    closed = datetime.fromisoformat("2026-09-10T05:50:28+00:00")

    with pytest.raises(
        materializer.PreOutcomeWindowClosedError,
        match="BLOCKED_PRE_OUTCOME_WINDOW_CLOSED",
    ):
        materializer.materialize_canonical_forecast(
            operation_root=operation_root,
            destination=destination,
            implementation_identity=IDENTITY,
            specs=materializer.FROZEN_STREAM_SPECS,
            expected_manifest_sha256=None,
            clock=_clock(closed),
        )

    assert not destination.exists()
    assert not list(destination.parent.glob("*.tmp"))


def test_prediction_created_at_must_precede_created_at(tmp_path: Path) -> None:
    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root)
    first = materializer.FROZEN_STREAM_SPECS[0]
    source = operation_root / first.source_relative_path
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["prediction_created_at"] = "2026-09-10T15:00:00+00:00"
    source.write_bytes(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    )
    destination = tmp_path / "authority" / "final_forecast_payload.json"

    with pytest.raises(
        materializer.PreOutcomeWindowClosedError,
        match="prediction_created_at",
    ):
        materializer.materialize_canonical_forecast(
            operation_root=operation_root,
            destination=destination,
            implementation_identity=IDENTITY,
            specs=materializer.FROZEN_STREAM_SPECS,
            expected_manifest_sha256=None,
            clock=_clock(CREATED_AT, PRE_PUBLISH_AT),
        )
    assert not destination.exists()


def test_pre_publish_boundary_is_checked_immediately_before_publish(tmp_path: Path) -> None:
    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root)
    destination = tmp_path / "authority" / "final_forecast_payload.json"
    scheduled = datetime.fromisoformat(materializer.TARGET_SCHEDULED_AT)

    with pytest.raises(
        materializer.PreOutcomeWindowClosedError,
        match="pre_publish_now",
    ):
        materializer.materialize_canonical_forecast(
            operation_root=operation_root,
            destination=destination,
            implementation_identity=IDENTITY,
            specs=materializer.FROZEN_STREAM_SPECS,
            expected_manifest_sha256=None,
            clock=_clock(CREATED_AT, scheduled),
        )
    assert not destination.exists()
    assert not list(destination.parent.glob("*.tmp"))


def test_existing_malformed_authority_blocks_without_sampling_clock(tmp_path: Path) -> None:
    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root)
    destination = tmp_path / "authority" / "final_forecast_payload.json"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"not-json\n")

    def clock_must_not_be_called() -> datetime:
        raise AssertionError("conflict path sampled the publication clock")

    with pytest.raises(
        materializer.ForecastAuthorityConflictError,
        match="BLOCK_FORECAST_AUTHORITY_REMEDIATION_REQUIRED",
    ):
        materializer.materialize_canonical_forecast(
            operation_root=operation_root,
            destination=destination,
            implementation_identity=IDENTITY,
            specs=materializer.FROZEN_STREAM_SPECS,
            expected_manifest_sha256=None,
            clock=clock_must_not_be_called,
        )
    assert destination.read_bytes() == b"not-json\n"


def test_outcome_key_in_any_frozen_input_is_rejected(tmp_path: Path) -> None:
    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root)
    first = materializer.FROZEN_STREAM_SPECS[0]
    source = operation_root / first.source_relative_path
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["result"] = {"score": 6}
    source.write_bytes(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    )

    with pytest.raises(materializer.FrozenInputError, match="forbidden outcome/scoring key"):
        materializer.materialize_canonical_forecast(
            operation_root=operation_root,
            destination=tmp_path / "authority" / "final_forecast_payload.json",
            implementation_identity=IDENTITY,
            specs=materializer.FROZEN_STREAM_SPECS,
            expected_manifest_sha256=None,
            clock=_clock(CREATED_AT, PRE_PUBLISH_AT),
        )


def test_atomic_publish_race_preserves_competing_authority_and_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root)
    destination = tmp_path / "authority" / "final_forecast_payload.json"
    original_publish = materializer.publish_staged

    def competing_publish(staged: StagedCanonicalForecast):
        staged.destination.write_bytes(b"{\"competing\":true}\n")
        return original_publish(staged)

    monkeypatch.setattr(materializer, "publish_staged", competing_publish)
    with pytest.raises(
        materializer.ForecastAuthorityConflictError,
        match="BLOCK_FORECAST_AUTHORITY_REMEDIATION_REQUIRED",
    ):
        materializer.materialize_canonical_forecast(
            operation_root=operation_root,
            destination=destination,
            implementation_identity=IDENTITY,
            specs=materializer.FROZEN_STREAM_SPECS,
            expected_manifest_sha256=None,
            clock=_clock(CREATED_AT, PRE_PUBLISH_AT),
        )
    assert destination.read_bytes() == b"{\"competing\":true}\n"


def test_historical_087_authority_and_domain_parity_are_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an older immutable authority is accepted without rematerialization."""

    operation_root = tmp_path / "operation"
    _copy_inputs(operation_root, tickets_by_strategy=HISTORICAL_087_TICKETS)
    artifact = tmp_path / "authority" / "final_forecast_payload.json"
    historical = materializer.materialize_canonical_forecast(
        operation_root=operation_root,
        destination=artifact,
        implementation_identity=HISTORICAL_IDENTITY,
        specs=materializer.FROZEN_STREAM_SPECS,
        expected_manifest_sha256=HISTORICAL_087_MANIFEST_SHA256,
        clock=_clock(CREATED_AT, PRE_PUBLISH_AT),
    )
    assert historical.status == "CREATED"
    assert historical.payload["implementation_commit"] == HISTORICAL_IDENTITY.commit
    before = artifact.read_bytes()
    before_stat = artifact.stat()
    payload = json.loads(before.decode("utf-8"))
    bundle = materializer.load_frozen_stream_inputs(
        operation_root,
        expected_manifest_sha256=HISTORICAL_087_MANIFEST_SHA256,
    )
    decision = build_canonical_consensus(bundle.streams)
    ranking_payload = cast(list[dict[str, object]], payload["final_decision_ranking"])
    expected_ranking = tuple(cast(int, entry["number"]) for entry in ranking_payload)

    assert len(bundle.streams) == 11
    assert len(decision.deterministic_ranking) == 49
    assert decision.stream_input_manifest_sha256 == payload["stream_input_manifest_sha256"]
    assert expected_ranking == HISTORICAL_087_RANKING
    assert decision.deterministic_ranking == expected_ranking
    assert tuple(
        decision.support_units[number - 1] for number in expected_ranking
    ) == HISTORICAL_087_SUPPORT_UNITS
    assert sum(decision.support_units) == 396
    assert decision.final_ticket == (4, 12, 24, 25, 26, 29)
    assert payload["final_recommended_output"] == [
        {"ticket_position": 1, "predicted_numbers": [4, 12, 24, 25, 26, 29]}
    ]

    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("historical authority retry attempted a write")

    monkeypatch.setattr(materializer, "ensure_output_parent", fail_write)
    monkeypatch.setattr(materializer, "stage_payload", fail_write)
    monkeypatch.setattr(materializer, "publish_staged", fail_write)
    monkeypatch.setattr(materializer, "discard_staged", fail_write)

    def clock_must_not_be_called() -> datetime:
        raise AssertionError("historical authority retry sampled the clock")

    retry = materializer.materialize_canonical_forecast(
        operation_root=operation_root,
        destination=artifact,
        implementation_identity=IDENTITY,
        specs=materializer.FROZEN_STREAM_SPECS,
        expected_manifest_sha256=HISTORICAL_087_MANIFEST_SHA256,
        clock=clock_must_not_be_called,
    )
    assert retry.status == "ALREADY_PRESENT"
    assert retry.payload["implementation_commit"] == HISTORICAL_IDENTITY.commit
    assert retry.payload["created_at"] == payload["created_at"]
    assert retry.payload["created_at"] == historical.payload["created_at"]
    assert before == artifact.read_bytes()
    after_stat = artifact.stat()
    assert before_stat.st_ino == after_stat.st_ino
    assert before_stat.st_size == after_stat.st_size
    assert before_stat.st_mtime_ns == after_stat.st_mtime_ns
def test_dynamic_materializer_binds_later_target_and_causal_history(tmp_path: Path) -> None:
    created_at = datetime(2099, 1, 2, 10, 0, 0, tzinfo=UTC)
    scheduled_at = datetime(2099, 1, 2, 12, 30, 0, tzinfo=UTC)
    streams = tuple(
        StreamConsensusInput(
            strategy_id=f"synthetic_stream_{index:02d}",
            strategy_version="v1.0",
            native_ticket_count=1,
            prediction_run_id=f"run-{index:02d}",
            source_relative_path=f"predictions/209900001/stream-{index:02d}.json",
            source_sha256=f"{index + 1:064x}",
            prediction_created_at=created_at,
            tickets=(FIXTURE_NUMBERS,),
        )
        for index in range(11)
    )
    context = CanonicalConsensusContext(
        lottery_type="BIG_LOTTO",
        target_draw_number="209900001",
        target_draw_date="2099-01-02",
        scheduled_at=scheduled_at,
        causal_cutoff_draw_number="209899999",
        causal_cutoff_date="2099-01-01",
        history_draw_count=42,
        history_sha256="d" * 64,
        streams=streams,
    )

    result = materializer.materialize_dynamic_canonical_forecast(
        context=context,
        operation_root=tmp_path / "operation",
        clock=_clock(created_at + timedelta(minutes=1), created_at + timedelta(minutes=2)),
    )

    expected_destination = materializer.canonical_forecast_path(
        tmp_path / "operation", "209900001"
    )
    assert result.status == "CREATED"
    assert result.destination == expected_destination
    assert result.payload["target_result_used"] is False
    assert result.payload["target_draw"] == {
        "draw_number": "209900001",
        "draw_date": "2099-01-02",
    }
    assert result.payload["scheduled_at"] == "2099-01-02T12:30:00+00:00"
    assert result.payload["max_data_cutoff"] == {
        "draw_number": "209899999",
        "draw_date": "2099-01-01",
    }
    assert result.payload["history_draw_count"] == 42
    assert result.payload["history_sha256"] == "d" * 64
    assert result.payload["aggregation_method_id"] == (
        "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
    )
    assert result.payload["aggregation_method_version"] == "1.0.0"
    assert expected_destination.read_bytes() == canonical_file_bytes(result.payload)
