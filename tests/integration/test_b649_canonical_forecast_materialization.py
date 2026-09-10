"""Integration checks for the frozen-input B649 canonical authority."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
import tools.materialize_b649_canonical_forecast as materializer

from lottolab.evidence.canonical_json import canonical_file_bytes

UPSTREAM_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "B649_OPERATIONAL_PREDICTION_LOOP_R1"
)
IDENTITY = materializer.ImplementationIdentity(
    commit="a" * 40,
    tree="b" * 40,
    source_hashes=tuple(
        materializer.ImplementationSource(path, "c" * 64)
        for path in materializer.IMPLEMENTATION_SOURCE_PATHS
    ),
)
CREATED_AT = datetime(2026, 9, 10, 14, 0, 0, tzinfo=UTC)
PRE_PUBLISH_AT = datetime(2026, 9, 10, 14, 0, 1, tzinfo=UTC)


def _copy_inputs(destination: Path) -> None:
    for spec in materializer.FROZEN_STREAM_SPECS:
        source = UPSTREAM_ROOT / spec.source_relative_path
        target = destination / spec.source_relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


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
        clock=_clock(CREATED_AT, PRE_PUBLISH_AT),
    )

    assert result.status == "CREATED"
    assert result.payload["target_result_used"] is False
    assert result.payload["stream_count"] == 11
    assert result.payload["final_recommended_output"] == [
        {"ticket_position": 1, "predicted_numbers": [4, 12, 24, 25, 26, 29]}
    ]
    raw = destination.read_bytes()
    assert raw == canonical_file_bytes(result.payload)
    assert not list(destination.parent.glob("*.tmp"))

    def clock_must_not_be_called() -> datetime:
        raise AssertionError("idempotent authority retry sampled the clock")

    retry = materializer.materialize_canonical_forecast(
        operation_root=operation_root,
        destination=destination,
        implementation_identity=IDENTITY,
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

    def competing_publish(staged: materializer.StagedCanonicalForecast):
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
            clock=_clock(CREATED_AT, PRE_PUBLISH_AT),
        )
    assert destination.read_bytes() == b"{\"competing\":true}\n"
