"""Focused contract tests for the scheduler-owned B649 current forecast API."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import lottolab.interfaces.api.b649_canonical_forecast as api_module
from lottolab.application.b649_sealed_geometry_portfolio import SEALED_GEOMETRY_PORTFOLIOS
from lottolab.evidence.canonical_json import canonical_file_bytes
from lottolab.infrastructure.b649_operational_portfolio_materializer import (
    PersistedPortfolioCandidate,
    materialize_portfolios,
)
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.b649_canonical_forecast import (
    FORECAST_METHOD_ID,
    FORECAST_METHOD_VERSION,
    FORECAST_SCHEMA_VERSION,
    HEALTH_PATH_ENV,
    PORTFOLIO_METHOD_ID,
    PORTFOLIO_METHOD_VERSION,
    PORTFOLIO_SCHEMA_VERSION,
)

PATH = "/api/b649/canonical-forecast/current"
TARGET = {
    "lottery_type": "BIG_LOTTO",
    "draw_number": "115000089",
    "draw_date": "2026-09-18",
    "scheduled_at": "2026-09-18T12:30:00Z",
}
ARTIFACT_SCHEDULED_AT = "2026-09-18T20:30:00+08:00"


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _forecast(draw_number: str = TARGET["draw_number"]) -> dict[str, object]:
    return {
        "schema_version": FORECAST_SCHEMA_VERSION,
        "lottery_type": "BIG_LOTTO",
        "aggregation_method_id": FORECAST_METHOD_ID,
        "aggregation_method_version": FORECAST_METHOD_VERSION,
        "target_draw": {"draw_number": draw_number, "draw_date": TARGET["draw_date"]},
        "scheduled_at": ARTIFACT_SCHEDULED_AT,
        "stream_count": 11,
        "stream_inputs": [{} for _ in range(11)],
        "final_recommended_output": [
            {"ticket_position": 1, "predicted_numbers": [1, 2, 3, 4, 5, 6]}
        ],
    }


def _ticket_rows(count: int) -> list[dict[str, object]]:
    return [
        {"ticket_position": position, "predicted_numbers": list(ticket)}
        for position, ticket in enumerate(SEALED_GEOMETRY_PORTFOLIOS[count].tickets, start=1)
    ]


def _portfolio() -> dict[str, object]:
    return {
        "schema_version": PORTFOLIO_SCHEMA_VERSION,
        "lottery_type": "BIG_LOTTO",
        "portfolio_method_id": PORTFOLIO_METHOD_ID,
        "portfolio_method_version": PORTFOLIO_METHOD_VERSION,
        "target_draw": {
            "draw_number": TARGET["draw_number"],
            "draw_date": TARGET["draw_date"],
        },
        "scheduled_at": ARTIFACT_SCHEDULED_AT,
        "portfolio_status": "COMPLETE",
        "k5_status": "COMPLETE",
        "k10_status": "COMPLETE",
        "k20_status": "COMPLETE",
        "k5": _ticket_rows(5),
        "k10": _ticket_rows(10),
        "k20": _ticket_rows(20),
    }


def _health(
    forecast_path: Path,
    forecast_sha256: str,
    portfolio_path: Path,
    *,
    forecast_health: dict[str, object] | None = None,
    portfolio_health: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "b649-goalc-local-scheduler-health-v1",
        "current_status": "PREDRAW_READY",
        "current_target": TARGET,
        "forecast_materialization": {
            "status": "COMPLETE",
            "target_draw": TARGET["draw_number"],
            "method_id": FORECAST_METHOD_ID,
            "method_version": FORECAST_METHOD_VERSION,
            "artifact_path": str(forecast_path),
            "artifact_sha256": forecast_sha256,
            **({} if forecast_health is None else forecast_health),
        },
        "portfolio_materialization": {
            "status": "COMPLETE",
            "target_draw": {
                "draw_number": TARGET["draw_number"],
                "draw_date": TARGET["draw_date"],
            },
            "method_id": PORTFOLIO_METHOD_ID,
            "method_version": PORTFOLIO_METHOD_VERSION,
            "portfolio_authority_locator": str(portfolio_path),
            **({} if portfolio_health is None else portfolio_health),
        },
    }


def _write_bundle(
    root: Path,
    *,
    forecast: dict[str, object] | None = None,
    portfolio: dict[str, object] | None = None,
    forecast_health: dict[str, object] | None = None,
    portfolio_health: dict[str, object] | None = None,
) -> tuple[Path, Path, Path]:
    forecast_path = root / "forecast.json"
    portfolio_path = root / "portfolio.json"
    health_path = root / "health.json"
    forecast_bytes = _json_bytes(_forecast() if forecast is None else forecast)
    portfolio_bytes = _json_bytes(_portfolio() if portfolio is None else portfolio)
    forecast_path.write_bytes(forecast_bytes)
    portfolio_path.write_bytes(portfolio_bytes)
    health_path.write_bytes(
        _json_bytes(
            _health(
                forecast_path,
                hashlib.sha256(forecast_bytes).hexdigest(),
                portfolio_path,
                forecast_health=forecast_health,
                portfolio_health=portfolio_health,
            )
        )
    )
    return health_path, forecast_path, portfolio_path


def _client(monkeypatch: MonkeyPatch, health_path: Path) -> httpx.Client:
    monkeypatch.setenv(HEALTH_PATH_ENV, str(health_path))
    return cast(httpx.Client, TestClient(create_app()))


def test_success_projects_scheduler_artifacts_and_ignores_caller_paths(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    health_path, forecast_path, portfolio_path = _write_bundle(tmp_path)
    response = _client(monkeypatch, health_path).get(
        PATH,
        params={"health_path": str(tmp_path / "caller-selected.json")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "AVAILABLE"
    assert payload["authority"] == "SCHEDULER_ARTIFACT"
    assert payload["current_target"] == {
        "draw_number": TARGET["draw_number"],
        "draw_date": TARGET["draw_date"],
        "scheduled_at": TARGET["scheduled_at"],
    }
    assert payload["consensus_numbers"] == [1, 2, 3, 4, 5, 6]
    assert payload["source_stream_count"] == 11
    assert len(payload["k5_tickets"]) == 5
    assert len(payload["k10_tickets"]) == 10
    assert len(payload["k20_tickets"]) == 20
    assert payload["forecast_actual_sha256"] == hashlib.sha256(
        forecast_path.read_bytes()
    ).hexdigest()
    assert payload["portfolio_actual_sha256"] == hashlib.sha256(
        portfolio_path.read_bytes()
    ).hexdigest()
    assert str(health_path) not in response.text
    assert str(forecast_path) not in response.text
    assert str(portfolio_path) not in response.text


def test_missing_server_health_configuration_is_sanitized_503(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv(HEALTH_PATH_ENV, raising=False)

    response = cast(httpx.Client, TestClient(create_app())).get(PATH)

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "B649_CANONICAL_FORECAST_UNAVAILABLE",
        "message": "The scheduler-owned B649 canonical forecast is unavailable.",
    }


def test_corrupt_health_is_sanitized_without_leaking_private_content(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    health_path = tmp_path / "health.json"
    private_detail = "/private/health/secret"
    health_path.write_text(private_detail, encoding="utf-8")

    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 503
    assert private_detail not in response.text


def test_forecast_digest_mismatch_fails_closed(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    health_path, _, _ = _write_bundle(tmp_path, forecast_health={"artifact_sha256": "0" * 64})

    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 503


def test_forecast_target_mismatch_fails_closed(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    health_path, _, _ = _write_bundle(
        tmp_path,
        forecast=_forecast(draw_number="115000090"),
    )

    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 503


def test_incomplete_portfolio_bucket_fails_closed(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    portfolio = _portfolio()
    portfolio["k10_status"] = "WAITING_FOR_PREDICTIONS"
    health_path, _, _ = _write_bundle(tmp_path, portfolio=portfolio)

    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 503


@pytest.mark.parametrize(
    "forecast_health",
    [
        {"method_id": None},
        {"method_id": "wrong-method"},
    ],
)
def test_missing_or_conflicting_method_provenance_fails_closed(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    forecast_health: dict[str, object],
) -> None:
    health_path, _, _ = _write_bundle(tmp_path, forecast_health=forecast_health)

    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 503


def test_health_rollover_race_fails_closed(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    health_path, _, _ = _write_bundle(tmp_path)
    original_reader = api_module._read_regular_bytes
    calls = 0

    def read_with_rollover(path: Path) -> bytes:
        nonlocal calls
        calls += 1
        raw = original_reader(path)
        if calls == 2:
            health = json.loads(health_path.read_text(encoding="utf-8"))
            cast(dict[str, object], health)["finished_at"] = "rollover"
            health_path.write_bytes(_json_bytes(health))
        return raw

    monkeypatch.setattr(api_module, "_read_regular_bytes", read_with_rollover)
    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 503


def test_production_app_composition_exposes_only_the_get_route() -> None:
    document = create_app().openapi()

    assert PATH in document["paths"]
    assert set(document["paths"][PATH]) == {"get"}
    assert document["paths"][PATH]["get"]["operationId"] == (
        "getB649CanonicalForecastCurrent"
    )


@pytest.mark.parametrize(
    "k10_numbers",
    [
        # The retired selector's nested layout: legal tickets, not the sealed geometry.
        [list(range(position, position + 6)) for position in range(1, 11)],
        # One number off in one ticket.
        [[1, 2, 3, 4, 5, 6], *[list(t) for t in SEALED_GEOMETRY_PORTFOLIOS[10].tickets[1:]]],
    ],
)
def test_non_sealed_portfolio_tickets_fail_closed(
    tmp_path: Path, monkeypatch: MonkeyPatch, k10_numbers: list[list[int]]
) -> None:
    portfolio = _portfolio()
    portfolio["k10"] = [
        {"ticket_position": position, "predicted_numbers": numbers}
        for position, numbers in enumerate(k10_numbers, start=1)
    ]
    health_path, _, _ = _write_bundle(tmp_path, portfolio=portfolio)

    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 503


def _scheduler_candidates() -> tuple[PersistedPortfolioCandidate, ...]:
    candidates: list[PersistedPortfolioCandidate] = []
    for index in range(11):
        strategy_id = f"stream-{index:02d}"
        payload: dict[str, object] = {
            "schema_version": "b649-operational-prediction-v1",
            "task_id": "B649_OPERATIONAL_PREDICTION_LOOP_R1",
            "prediction_run_id": f"run-{index}",
            "lottery_type": "BIG_LOTTO",
            "draw_number": TARGET["draw_number"],
            "draw_date": TARGET["draw_date"],
            "scheduled_at": ARTIFACT_SCHEDULED_AT,
            "prediction_created_at": f"2026-09-18T10:{index:02d}:00+08:00",
            "strategy_id": strategy_id,
            "strategy_version": "v1",
            "history_cutoff": {"draw_number": "115000088", "draw_date": "2026-09-15"},
            "history_draw_count": 100,
            "history_sha256": "a" * 64,
            "history_caveat": "YES",
            "prediction_temporal_class": "PRE_DRAW",
            "native_ticket_count": 1,
            "tickets": [{"ticket_position": 1, "predicted_numbers": [1, 2, 3, 4, 5, 6]}],
        }
        candidates.append(
            PersistedPortfolioCandidate(
                strategy_id=strategy_id,
                source_relative_path=f"predictions/{strategy_id}.json",
                raw_bytes=canonical_file_bytes(payload),
                payload=payload,
            )
        )
    return tuple(candidates)


def test_real_materializer_health_is_servable_end_to_end(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The scheduler writes ``health_dict()`` verbatim as portfolio health; the
    route must accept exactly that shape, not only hand-written fixtures.
    """

    candidates = _scheduler_candidates()
    result = materialize_portfolios(
        candidates=candidates,
        expected_strategy_ids=tuple(candidate.strategy_id for candidate in candidates),
        target_draw_number=TARGET["draw_number"],
        target_draw_date=TARGET["draw_date"],
        scheduled_at=ARTIFACT_SCHEDULED_AT,
        destination=tmp_path / "portfolio" / "final_portfolio_payload.json",
        pre_outcome_seal_check=lambda: True,
    )
    health_path, _, _ = _write_bundle(tmp_path)
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health["portfolio_materialization"] = result.health_dict()
    health_path.write_bytes(_json_bytes(health))

    response = _client(monkeypatch, health_path).get(PATH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio_method_id"] == "B649_SEALED_GEOMETRY_PORTFOLIO"
    for size in (5, 10, 20):
        served = [tuple(row["predicted_numbers"]) for row in payload[f"k{size}_tickets"]]
        assert served == list(SEALED_GEOMETRY_PORTFOLIOS[size].tickets)
