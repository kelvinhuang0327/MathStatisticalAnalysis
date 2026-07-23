"""Policy tests for the explicit local Historical Results composition."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import lottolab.interfaces.api.local_app as local_app
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.local_app import (
    HISTORICAL_RESULTS_DB_ENV,
    LocalHistoricalComposition,
    create_local_app,
    local_historical_composition,
)

RUNS_PATH = "/api/v1/historical-results/runs"
WINDOWS_PATH = "/api/v1/historical-prefix-success-windows"
WINDOW_PARAMS = {
    "import_identity_sha256": "a" * 64,
    "prefix_count": 1,
    "criterion": "M3_PLUS",
}


def _client(monkeypatch: MonkeyPatch, configured: str | None) -> TestClient:
    monkeypatch.delenv(HISTORICAL_RESULTS_DB_ENV, raising=False)
    if configured is not None:
        monkeypatch.setenv(HISTORICAL_RESULTS_DB_ENV, configured)
    return TestClient(create_local_app())


def _assert_not_configured(client: TestClient) -> None:
    runs = client.get(RUNS_PATH)
    windows = client.get(WINDOWS_PATH, params=WINDOW_PARAMS)
    assert runs.status_code == 503
    assert runs.json()["error_code"] == "HISTORICAL_RESULTS_NOT_CONFIGURED"
    assert windows.status_code == 503
    assert windows.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_WINDOWS_NOT_CONFIGURED"
    )


@pytest.mark.parametrize("configured", [None, ""])
def test_absent_or_empty_configuration_keeps_both_route_families_unconfigured(
    monkeypatch: MonkeyPatch, configured: str | None
) -> None:
    _assert_not_configured(_client(monkeypatch, configured))


def test_generic_create_app_ignores_the_local_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(HISTORICAL_RESULTS_DB_ENV, "/explicit/historical.db")

    _assert_not_configured(TestClient(create_app()))


def test_configuration_is_exact_and_both_factories_share_one_path_object() -> None:
    configured = " /absolute/path-is-not-trimmed.db "

    composition = local_historical_composition({HISTORICAL_RESULTS_DB_ENV: configured})

    assert composition is not None
    assert str(composition.database) == configured
    assert composition.historical_query_repository.__self__ is composition
    assert (
        composition.historical_prefix_success_window_source_reader.__self__
        is composition
    )


def test_configuration_never_falls_back_to_draw_data_environment() -> None:
    composition = local_historical_composition({"LOTTOLAB_DATA_DIR": "/draw-data"})

    assert composition is None


def test_configured_app_construction_and_openapi_do_not_touch_the_filesystem(
    monkeypatch: MonkeyPatch,
) -> None:
    verifier = Mock(side_effect=AssertionError("database must stay lazy"))
    monkeypatch.setattr(local_app, "verify_schema_read_only", verifier)
    monkeypatch.setenv(HISTORICAL_RESULTS_DB_ENV, "/not-opened/historical.db")

    app = create_local_app()
    document = app.openapi()

    assert RUNS_PATH in document["paths"]
    assert WINDOWS_PATH in document["paths"]
    verifier.assert_not_called()


@pytest.mark.parametrize(
    "configured",
    [
        "relative/historical.db",
        " /absolute/path-with-leading-space.db",
        "/tmp/LotteryNew/historical.db",
        "/tmp/lotterynew/historical.db",
    ],
)
def test_malformed_or_forbidden_configured_path_is_sanitized_unavailable(
    monkeypatch: MonkeyPatch, configured: str
) -> None:
    client = _client(monkeypatch, configured)

    runs = client.get(RUNS_PATH)
    windows = client.get(WINDOWS_PATH, params=WINDOW_PARAMS)

    assert runs.status_code == 503
    assert runs.json() == {
        "error_code": "HISTORICAL_RESULTS_UNAVAILABLE",
        "message": "Historical results storage is unavailable.",
    }
    assert windows.status_code == 503
    assert windows.json() == {
        "error_code": "HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE",
        "message": "Historical prefix success windows are unavailable.",
    }
    assert configured not in runs.text
    assert configured not in windows.text


def test_nul_configuration_is_rejected_lazily_without_using_os_environ() -> None:
    composition = local_historical_composition(
        {HISTORICAL_RESULTS_DB_ENV: "/tmp/historical\x00.db"}
    )
    assert composition is not None
    client = TestClient(
        create_app(
            historical_query_repository_factory=composition.historical_query_repository,
            historical_prefix_success_window_source_reader_factory=(
                composition.historical_prefix_success_window_source_reader
            ),
        )
    )

    assert client.get(RUNS_PATH).status_code == 503
    assert client.get(WINDOWS_PATH, params=WINDOW_PARAMS).status_code == 503


def test_missing_configured_database_is_sanitized_unavailable(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database = tmp_path / "missing" / "historical.db"
    client = _client(monkeypatch, str(database))

    assert client.get(RUNS_PATH).status_code == 503
    assert client.get(WINDOWS_PATH, params=WINDOW_PARAMS).status_code == 503
    assert not database.exists()


def test_factories_validate_lazily_on_each_request(monkeypatch: MonkeyPatch) -> None:
    verifier = Mock(return_value=False)
    monkeypatch.setattr(local_app, "verify_schema_read_only", verifier)
    composition = LocalHistoricalComposition(Path("/missing/historical.db"))

    client = TestClient(
        create_app(
            historical_query_repository_factory=composition.historical_query_repository,
            historical_prefix_success_window_source_reader_factory=(
                composition.historical_prefix_success_window_source_reader
            ),
        )
    )
    assert verifier.call_count == 0

    assert client.get(RUNS_PATH).status_code == 503
    assert client.get(WINDOWS_PATH, params=WINDOW_PARAMS).status_code == 503
    assert verifier.call_count == 2
