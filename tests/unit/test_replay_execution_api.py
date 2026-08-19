"""API contract coverage for the Replay execution HTTP transport.

Uses a fake/stub executor throughout -- never a real DrawHistoryReader, SQLite
repository, or production dataset. ``ReplayHistoricalPredictions`` itself is
covered by ``tests/unit/test_replay_historical_predictions.py``; this file
only proves the HTTP adapter translates and serializes without altering
strategy/draw order or leaking internal state.
"""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (Starlette TestClient is partially untyped under the httpx v1 compatibility shim.)

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictionsInput,
    ReplayHistoricalPredictionsResult,
)
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.evidence.replay_artifact import build_replay_prediction_snapshot
from lottolab.interfaces.api.app import create_app

_PATH = "/api/v1/replay-execution"


class _RecordingExecutor:
    """Fake ReplayHistoricalPredictions-compatible executor for API-boundary tests."""

    def __init__(self, *, failure: str | None = None) -> None:
        self.received: list[ReplayHistoricalPredictionsInput] = []
        self._failure = failure

    def execute(
        self, request: ReplayHistoricalPredictionsInput
    ) -> ReplayHistoricalPredictionsResult:
        self.received.append(request)
        if self._failure is not None:
            raise RuntimeError(self._failure)
        return _echo_result(request)


def _closed_snapshot(
    request: ReplayHistoricalPredictionsInput, target_draw_number: str, strategy_id: str
) -> ReplayPredictionSnapshot:
    target = next(t for t in request.targets if t.draw_number == target_draw_number)
    return build_replay_prediction_snapshot(
        dataset_id=request.dataset_id,
        dataset_version=request.dataset_version,
        lottery_type=request.lottery_type,
        target=target,
        strategy_id=strategy_id,
        strategy_identity=None,
        history_status="TARGET_NOT_FOUND",
        history_reason_code="TARGET_DRAW_NOT_FOUND",
        causal_history=None,
        prediction_status=None,
        prediction_reason_code=None,
        predicted_main_numbers=None,
    )


def _echo_result(request: ReplayHistoricalPredictionsInput) -> ReplayHistoricalPredictionsResult:
    """Mirror the real use case's target-major/strategy-minor, no-reorder contract."""

    return ReplayHistoricalPredictionsResult(
        snapshots=tuple(
            _closed_snapshot(request, target.draw_number, strategy_id)
            for target in request.targets
            for strategy_id in request.strategy_ids
        )
    )


def _client_for(executor: _RecordingExecutor | None) -> TestClient:
    return TestClient(create_app(replay_executor=executor))


def _payload(
    *,
    targets: list[tuple[str, str]],
    strategy_ids: list[str],
    lottery_type: str = "BIG_LOTTO",
    dataset_id: str = "DS1",
    dataset_version: str = "1",
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "targets": [
            {"draw_number": draw_number, "draw_date": draw_date}
            for draw_number, draw_date in targets
        ],
        "strategy_ids": strategy_ids,
    }


def test_valid_request_reaches_the_injected_executor_and_returns_its_result() -> None:
    executor = _RecordingExecutor()
    client = _client_for(executor)

    response = client.post(
        _PATH,
        json=_payload(targets=[("10", "2020-01-05")], strategy_ids=["fixture_strategy_a"]),
    )

    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    assert len(body["snapshots"]) == 1
    snapshot = body["snapshots"][0]
    assert snapshot["target_draw_number"] == "10"
    assert snapshot["strategy_id"] == "fixture_strategy_a"
    assert snapshot["dataset_id"] == "DS1"
    assert snapshot["dataset_version"] == "1"
    assert snapshot["lottery_type"] == "BIG_LOTTO"
    assert len(executor.received) == 1


def test_request_values_are_translated_without_strategy_or_draw_reordering() -> None:
    executor = _RecordingExecutor()
    client = _client_for(executor)

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("20", "2020-01-06"), ("10", "2020-01-05")],
            strategy_ids=["fixture_strategy_b", "fixture_strategy_a"],
        ),
    )

    assert response.status_code == 200
    received = executor.received[0]
    assert [target.draw_number for target in received.targets] == ["20", "10"]
    assert list(received.strategy_ids) == ["fixture_strategy_b", "fixture_strategy_a"]
    body = cast(dict[str, Any], response.json())
    pairs = [
        (snapshot["target_draw_number"], snapshot["strategy_id"]) for snapshot in body["snapshots"]
    ]
    assert pairs == [
        ("20", "fixture_strategy_b"),
        ("20", "fixture_strategy_a"),
        ("10", "fixture_strategy_b"),
        ("10", "fixture_strategy_a"),
    ]


def test_successful_application_result_is_returned_deterministically() -> None:
    executor = _RecordingExecutor()
    client = _client_for(executor)
    payload = _payload(targets=[("10", "2020-01-05")], strategy_ids=["fixture_strategy_a"])

    first = client.post(_PATH, json=payload)
    second = client.post(_PATH, json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def _drop_strategy_ids(payload: dict[str, Any]) -> None:
    payload.pop("strategy_ids")


def _empty_targets(payload: dict[str, Any]) -> None:
    payload["targets"] = []


def _invalid_lottery_type(payload: dict[str, Any]) -> None:
    payload["lottery_type"] = "NOT_A_LOTTERY"


def _unknown_field(payload: dict[str, Any]) -> None:
    payload["unexpected_field"] = "nope"


@pytest.mark.parametrize(
    "mutate",
    [_drop_strategy_ids, _empty_targets, _invalid_lottery_type, _unknown_field],
    ids=["missing_field", "empty_targets", "invalid_enum", "unknown_field"],
)
def test_malformed_request_receives_the_existing_sanitized_validation_contract(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    executor = _RecordingExecutor()
    client = _client_for(executor)
    payload = _payload(targets=[("10", "2020-01-05")], strategy_ids=["fixture_strategy_a"])
    mutate(payload)

    response = client.post(_PATH, json=payload)

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert executor.received == []


def test_duplicate_targets_are_rejected_with_the_sanitized_validation_contract() -> None:
    executor = _RecordingExecutor()
    client = _client_for(executor)

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("10", "2020-01-05"), ("10", "2020-01-06")],
            strategy_ids=["fixture_strategy_a"],
        ),
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert executor.received == []


def test_duplicate_strategy_ids_are_rejected_with_the_sanitized_validation_contract() -> None:
    executor = _RecordingExecutor()
    client = _client_for(executor)

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("10", "2020-01-05")],
            strategy_ids=["fixture_strategy_a", "fixture_strategy_a"],
        ),
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert executor.received == []


def test_bounded_application_failure_closes_without_traceback_or_internal_state_leakage() -> None:
    private_detail = "sqlite:///private/replay/secret-history.db unreachable"
    executor = _RecordingExecutor(failure=private_detail)
    client = _client_for(executor)

    response = client.post(
        _PATH,
        json=_payload(targets=[("10", "2020-01-05")], strategy_ids=["fixture_strategy_a"]),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_EXECUTION_UNAVAILABLE",
        "message": "Replay execution is unavailable.",
    }
    assert private_detail not in response.text
    assert "Traceback" not in response.text


def test_default_app_returns_not_configured_503() -> None:
    client = TestClient(create_app())

    response = client.post(
        _PATH,
        json=_payload(targets=[("10", "2020-01-05")], strategy_ids=["fixture_strategy_a"]),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_EXECUTION_NOT_CONFIGURED",
        "message": "Replay execution is not configured.",
    }


def test_executor_is_not_called_during_app_construction_or_openapi_generation() -> None:
    executor = _RecordingExecutor()

    app = create_app(replay_executor=executor)
    app.openapi()

    assert executor.received == []
