"""Focused contract tests for the target-parameterized forecast service."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast

import pytest

import lottolab.application.b649_canonical_forecast_materialization as service_module
from lottolab.application.b649_canonical_forecast_materialization import (
    AmbiguousStreamInputError,
    CanonicalForecastAuthorityPort,
    CanonicalForecastCutoff,
    CanonicalForecastMaterializationRequest,
    CanonicalForecastTarget,
    CanonicalHistoryIdentity,
    CausalCutoffMismatchError,
    ForecastAuthorityConflictError,
    HistoryIdentityMismatchError,
    ImplementationIdentity,
    ImplementationSource,
    MissingStreamInputError,
    PersistedForecastPrediction,
    PostDrawInputError,
    PreOutcomeWindowClosedError,
    RegisteredForecastStream,
    SourceIdentityMismatchError,
    StreamVersionMismatchError,
    TargetIdentityMismatchError,
    materialize_canonical_forecast,
    select_stream_inputs,
)
from lottolab.evidence.canonical_json import canonical_file_bytes
from lottolab.infrastructure.b649_canonical_forecast_writer import (
    discard_staged,
    ensure_output_parent,
    publish_staged,
    read_existing_bytes,
    read_persisted_prediction_records,
    stage_payload,
)

TARGET = CanonicalForecastTarget(
    lottery_type="BIG_LOTTO",
    draw_number="209900001",
    draw_date="2099-01-02",
    scheduled_at="2099-01-02T20:30:00+08:00",
)
CUTOFF = CanonicalForecastCutoff("209899999", "2099-01-01")
HISTORY = CanonicalHistoryIdentity(
    cutoff_draw_number=CUTOFF.draw_number,
    cutoff_date=CUTOFF.draw_date,
    draw_count=3,
    history_sha256="a" * 64,
    history_caveat="YES",
)
STREAM_IDS = tuple(f"stream-{index:02d}" for index in range(1, 12))
IDENTITY = ImplementationIdentity(
    commit="b" * 40,
    tree="c" * 40,
    source_hashes=(ImplementationSource("src/service.py", "d" * 64),),
)
PREDICTION_CREATED_AT = "2099-01-01T18:00:00+08:00"
CREATE_AT = datetime(2099, 1, 2, 11, 0, tzinfo=UTC)
PRE_PUBLISH_AT = datetime(2099, 1, 2, 11, 0, 1, tzinfo=UTC)


def _registered() -> tuple[RegisteredForecastStream, ...]:
    return tuple(
        RegisteredForecastStream(strategy_id, "v1", 1) for strategy_id in STREAM_IDS
    )


def _payload(
    target: CanonicalForecastTarget,
    strategy_id: str,
    *,
    run_id: str,
    strategy_version: str = "v1",
    temporal_class: str = "PRE_DRAW",
    history_cutoff: CanonicalForecastCutoff = CUTOFF,
    history_sha256: str = HISTORY.history_sha256,
) -> dict[str, object]:
    return {
        "schema_version": "b649-operational-prediction-v1",
        "task_id": "prediction-fixture",
        "prediction_run_id": run_id,
        "lottery_type": target.lottery_type,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "scheduled_at": target.scheduled_at,
        "prediction_created_at": PREDICTION_CREATED_AT,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "prediction_temporal_class": temporal_class,
        "availability": "AVAILABLE",
        "history_cutoff": {
            "draw_number": history_cutoff.draw_number,
            "draw_date": history_cutoff.draw_date,
        },
        "history_draw_count": HISTORY.draw_count,
        "history_sha256": history_sha256,
        "history_caveat": HISTORY.history_caveat,
        "native_ticket_count": 1,
        "tickets": [
            {"ticket_position": 1, "predicted_numbers": [1, 2, 3, 4, 5, 6]}
        ],
    }


def _write_streams(root: Path, target: CanonicalForecastTarget = TARGET) -> None:
    for strategy_id in STREAM_IDS:
        run_id = f"{target.draw_number}-{strategy_id}-run"
        path = root / "predictions" / target.draw_number / strategy_id / f"{run_id}.json"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(
            canonical_file_bytes(
                _payload(target, strategy_id, run_id=run_id)
            )
        )
        path.chmod(0o600)


def _request(
    root: Path,
    target: CanonicalForecastTarget = TARGET,
) -> CanonicalForecastMaterializationRequest:
    records = read_persisted_prediction_records(root, target.draw_number)
    predictions = tuple(
        PersistedForecastPrediction(
            source_relative_path=record.source_relative_path,
            source_sha256=record.source_sha256,
            raw_bytes=record.raw_bytes,
            payload=record.payload,
        )
        for record in records
    )
    return CanonicalForecastMaterializationRequest(
        task_id="scheduler-test",
        upstream_task_id="prediction-test",
        target=target,
        max_data_cutoff=CUTOFF,
        history=HISTORY,
        registered_streams=_registered(),
        predictions=predictions,
        implementation_identity=IDENTITY,
    )


def _authority() -> CanonicalForecastAuthorityPort:
    return CanonicalForecastAuthorityPort(
        read_existing_bytes=read_existing_bytes,
        ensure_output_parent=ensure_output_parent,
        stage_payload=stage_payload,
        publish_staged=publish_staged,
        discard_staged=discard_staged,
    )


def _destination(root: Path, target: CanonicalForecastTarget = TARGET) -> Path:
    return (
        root
        / "forecasts"
        / target.draw_number
        / "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
        / "1.0.0"
        / "final_forecast_payload.json"
    )


def test_future_target_selects_exactly_one_stream_and_creates_immutable_authority(
    tmp_path: Path,
) -> None:
    _write_streams(tmp_path)
    request = _request(tmp_path)

    selected = select_stream_inputs(request)
    assert len(selected) == 11
    assert tuple(item.strategy_id for item in selected) == STREAM_IDS
    assert tuple(item.prediction_run_id for item in selected) == tuple(
        f"{TARGET.draw_number}-{strategy_id}-run" for strategy_id in STREAM_IDS
    )

    destination = _destination(tmp_path)
    result = materialize_canonical_forecast(
        request,
        destination=destination,
        authority=_authority(),
        clock=lambda: CREATE_AT,
    )
    assert result.status == "COMPLETE"
    assert result.publication == "CREATED"
    assert result.payload["target_draw"] == {
        "draw_number": TARGET.draw_number,
        "draw_date": TARGET.draw_date,
    }
    assert result.payload["aggregation_method_id"] == (
        "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
    )
    assert result.payload["aggregation_method_version"] == "1.0.0"
    assert result.payload["target_result_used"] is False
    assert len(cast(list[object], result.payload["final_decision_ranking"])) == 49
    original = destination.read_bytes()

    def clock_must_not_be_called() -> datetime:
        raise AssertionError("existing authority must not sample publication clock")

    retry = materialize_canonical_forecast(
        replace(request, task_id="another-scheduler-task"),
        destination=destination,
        authority=_authority(),
        clock=clock_must_not_be_called,
    )
    assert retry.status == "COMPLETE"
    assert retry.publication == "ALREADY_PRESENT"
    assert retry.payload["created_at"] == result.payload["created_at"]
    assert destination.read_bytes() == original


def test_existing_authority_is_read_before_selection_compute_or_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_streams(tmp_path)
    request = _request(tmp_path)
    destination = _destination(tmp_path)
    materialize_canonical_forecast(
        request,
        destination=destination,
        authority=_authority(),
        clock=lambda: CREATE_AT,
    )
    original = destination.read_bytes()

    def fail(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("existing authority path performed forbidden work")

    monkeypatch.setattr(service_module, "_select_stream_inputs", fail)
    monkeypatch.setattr(service_module, "build_canonical_consensus", fail)
    monkeypatch.setattr(service_module, "_clock_value", fail)
    authority = CanonicalForecastAuthorityPort(
        read_existing_bytes=read_existing_bytes,
        ensure_output_parent=fail,
        stage_payload=fail,
        publish_staged=fail,
        discard_staged=fail,
    )

    retry = materialize_canonical_forecast(
        replace(request, predictions=()),
        destination=destination,
        authority=authority,
        clock=fail,
    )

    assert retry.publication == "ALREADY_PRESENT"
    assert retry.payload["created_at"]
    assert destination.read_bytes() == original


@pytest.mark.parametrize(
    ("failure", "expected"),
    (
        ("missing", MissingStreamInputError),
        ("ambiguous", AmbiguousStreamInputError),
        ("target", TargetIdentityMismatchError),
        ("version", StreamVersionMismatchError),
        ("cutoff", CausalCutoffMismatchError),
        ("history", HistoryIdentityMismatchError),
        ("post_draw", PostDrawInputError),
        ("source_hash", SourceIdentityMismatchError),
    ),
)
def test_invalid_exact_stream_inputs_fail_closed(
    tmp_path: Path,
    failure: str,
    expected: type[ValueError],
) -> None:
    _write_streams(tmp_path)
    first_path = next(
        (tmp_path / "predictions" / TARGET.draw_number / STREAM_IDS[0]).glob("*.json")
    )
    if failure == "missing":
        first_path.unlink()
    elif failure == "ambiguous":
        payload = json.loads(first_path.read_text(encoding="utf-8"))
        duplicate_run_id = f"{TARGET.draw_number}-{STREAM_IDS[0]}-duplicate"
        payload["prediction_run_id"] = duplicate_run_id
        duplicate_path = first_path.with_name(f"{duplicate_run_id}.json")
        duplicate_path.write_bytes(canonical_file_bytes(payload))
        duplicate_path.chmod(0o600)
    else:
        payload = json.loads(first_path.read_text(encoding="utf-8"))
        if failure == "target":
            payload["draw_number"] = "209900002"
        elif failure == "version":
            payload["strategy_version"] = "v2"
        elif failure == "cutoff":
            payload["history_cutoff"] = {
                "draw_number": "209899998",
                "draw_date": CUTOFF.draw_date,
            }
        elif failure == "history":
            payload["history_sha256"] = "e" * 64
        elif failure == "post_draw":
            payload["prediction_temporal_class"] = "POST_DRAW"
        first_path.write_bytes(canonical_file_bytes(payload))
    request = _request(tmp_path)
    if failure == "source_hash":
        predictions = (
            replace(request.predictions[0], source_sha256="f" * 64),
            *request.predictions[1:],
        )
        request = replace(request, predictions=predictions)

    with pytest.raises(expected):
        select_stream_inputs(request)


def test_closed_pre_outcome_window_does_not_backdate_or_stage_authority(
    tmp_path: Path,
) -> None:
    _write_streams(tmp_path)
    destination = _destination(tmp_path)
    request = _request(tmp_path)

    with pytest.raises(PreOutcomeWindowClosedError, match="PRE_OUTCOME_WINDOW_MISSED"):
        materialize_canonical_forecast(
            request,
            destination=destination,
            authority=_authority(),
            clock=lambda: datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
        )
    assert not destination.exists()
    assert not list(destination.parent.glob("*.tmp"))


def test_conflicting_authority_is_preserved_without_sampling_clock(tmp_path: Path) -> None:
    _write_streams(tmp_path)
    destination = _destination(tmp_path)
    request = _request(tmp_path)
    materialize_canonical_forecast(
        request,
        destination=destination,
        authority=_authority(),
        clock=lambda: CREATE_AT,
    )
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["target_result_used"] = True
    conflicting = canonical_file_bytes(payload)
    destination.write_bytes(conflicting)

    def clock_must_not_be_called() -> datetime:
        raise AssertionError("conflict path sampled publication clock")

    with pytest.raises(
        ForecastAuthorityConflictError,
        match="FORECAST_AUTHORITY_CONFLICT",
    ):
        materialize_canonical_forecast(
            request,
            destination=destination,
            authority=_authority(),
            clock=clock_must_not_be_called,
        )
    assert destination.read_bytes() == conflicting


def test_forecast_service_has_no_outcome_dependency(tmp_path: Path) -> None:
    _write_streams(tmp_path)
    result = materialize_canonical_forecast(
        _request(tmp_path),
        destination=_destination(tmp_path),
        authority=_authority(),
        clock=lambda: CREATE_AT,
    )
    assert result.payload["target_result_used"] is False
    assert not (tmp_path / "outcomes").exists()
    assert not (tmp_path / "scores").exists()
