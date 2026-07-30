"""Policy tests for the explicit local Replay-scoring composition."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import lottolab.interfaces.api.local_app as local_app
from lottolab.application.use_cases.query_replay_scoring_projection import (
    ReplayScoringQueryUnavailableError,
)
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.local_app import (
    REPLAY_SCORING_DB_ENV,
    LocalReplayScoringComposition,
    create_local_app,
    local_replay_scoring_composition,
)

RANKINGS_PATH = "/api/v1/replay-rankings/optimal"
RANKINGS_PARAMS = {"scoring_artifact_sha256": "a" * 64}
RUN_PATH = f"/api/v1/replay-scoring/{'a' * 64}"


def _client(monkeypatch: MonkeyPatch, configured: str | None) -> TestClient:
    monkeypatch.delenv(REPLAY_SCORING_DB_ENV, raising=False)
    if configured is not None:
        monkeypatch.setenv(REPLAY_SCORING_DB_ENV, configured)
    return TestClient(create_local_app())


def _assert_not_configured(client: TestClient) -> None:
    rankings = client.get(RANKINGS_PATH, params=RANKINGS_PARAMS)
    run = client.get(RUN_PATH)
    assert rankings.status_code == 503
    assert rankings.json()["error_code"] == "REPLAY_RANKING_NOT_CONFIGURED"
    assert run.status_code == 503
    assert run.json()["error_code"] == "REPLAY_SCORING_QUERY_NOT_CONFIGURED"


@pytest.mark.parametrize("configured", [None, ""])
def test_absent_or_empty_configuration_keeps_both_routes_unconfigured(
    monkeypatch: MonkeyPatch, configured: str | None
) -> None:
    _assert_not_configured(_client(monkeypatch, configured))


def test_generic_create_app_ignores_the_local_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(REPLAY_SCORING_DB_ENV, "/explicit/replay-scoring.db")

    _assert_not_configured(TestClient(create_app()))


def test_configuration_is_exact() -> None:
    configured = " /absolute/path-is-not-trimmed.db "

    composition = local_replay_scoring_composition({REPLAY_SCORING_DB_ENV: configured})

    assert composition is not None
    assert str(composition.database) == configured
    assert composition.replay_scoring_projection_reader.__self__ is composition


def test_configuration_never_falls_back_to_historical_results_environment() -> None:
    composition = local_replay_scoring_composition(
        {"LOTTOLAB_HISTORICAL_RESULTS_DB": "/historical.db"}
    )

    assert composition is None


def test_configured_app_construction_and_openapi_do_not_touch_the_filesystem(
    monkeypatch: MonkeyPatch,
) -> None:
    verifier = Mock(side_effect=AssertionError("database must stay lazy"))
    monkeypatch.setattr(local_app, "verify_replay_scoring_schema_read_only", verifier)
    monkeypatch.setenv(REPLAY_SCORING_DB_ENV, "/not-opened/replay-scoring.db")

    app = create_local_app()
    document = app.openapi()

    assert RANKINGS_PATH in document["paths"]
    verifier.assert_not_called()


def test_missing_configured_database_is_sanitized_unavailable(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database = tmp_path / "missing" / "replay-scoring.db"
    client = _client(monkeypatch, str(database))

    response = client.get(RANKINGS_PATH, params=RANKINGS_PARAMS)

    assert response.status_code == 503
    assert response.json()["error_code"] == "REPLAY_RANKING_UNAVAILABLE"
    assert not database.exists()
    assert str(database) not in response.text


def test_factory_raises_the_shared_unavailable_error_directly() -> None:
    composition = LocalReplayScoringComposition(Path("/missing/replay-scoring.db"))

    with pytest.raises(ReplayScoringQueryUnavailableError):
        composition.replay_scoring_projection_reader()


def test_factory_validates_lazily_on_each_request(monkeypatch: MonkeyPatch) -> None:
    verifier = Mock(return_value=False)
    monkeypatch.setattr(local_app, "verify_replay_scoring_schema_read_only", verifier)
    composition = LocalReplayScoringComposition(Path("/missing/replay-scoring.db"))

    client = TestClient(
        create_app(
            replay_scoring_projection_reader_factory=composition.replay_scoring_projection_reader
        )
    )
    assert verifier.call_count == 0

    assert client.get(RANKINGS_PATH, params=RANKINGS_PARAMS).status_code == 503
    assert verifier.call_count == 1
