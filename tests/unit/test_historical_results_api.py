"""API contract tests for the read-only /api/v1/historical-results/* endpoints (BLHQ R2)."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.historical.builder import (
    REAL_STRATEGY_IDS,
    build_baseline_envelope,
    envelope_bytes,
)

from lottolab.domain.historical_results import HistoricalRunImport, HistoricalRunStatus
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
    SQLiteHistoricalResultRepository,
)
from lottolab.interfaces.api.app import create_app
from lottolab.normalization.historical_import import verify_and_normalize_historical_import

PREFIX = "/api/v1/historical-results"


def _normalized_import(envelope: dict[str, Any]) -> HistoricalRunImport:
    result = verify_and_normalize_historical_import(envelope_bytes(envelope))
    assert result.normalized_import is not None
    return result.normalized_import


def _seed_database(database: Path) -> str:
    write_repository = SQLiteHistoricalResultRepository(database)
    result = write_repository.commit_import(_normalized_import(build_baseline_envelope()))
    assert result.status is HistoricalRunStatus.COMPLETED
    return result.run_id


def _client_for(database: Path) -> TestClient:
    def factory() -> SQLiteHistoricalResultQueryRepository:
        return SQLiteHistoricalResultQueryRepository(database)

    return TestClient(create_app(historical_query_repository_factory=factory))


# --- all four routes, configured real SQLite repository ---------------------


def test_list_runs_returns_the_seeded_completed_run(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_id = _seed_database(database)
    client = _client_for(database)

    response = client.get(f"{PREFIX}/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert [item["run_id"] for item in body["items"]] == [run_id]


def test_list_run_strategies_returns_summaries_for_each_ticket_count(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_id = _seed_database(database)
    client = _client_for(database)

    for ticket_count in (10, 15, 20):
        response = client.get(
            f"{PREFIX}/runs/{run_id}/strategies", params={"ticket_count": ticket_count}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == run_id
        assert body["ticket_count"] == ticket_count
        assert len(body["items"]) == 5


def test_list_run_replay_portfolios_returns_ordered_prefix_tickets(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_id = _seed_database(database)
    client = _client_for(database)

    response = client.get(
        f"{PREFIX}/runs/{run_id}/replay",
        params={"strategy_id": REAL_STRATEGY_IDS[0], "ticket_count": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["strategy_id"] == REAL_STRATEGY_IDS[0]
    assert body["total_count"] == 1
    (portfolio,) = body["items"]
    assert [t["portfolio_position"] for t in portfolio["tickets"]] == list(range(1, 11))


def test_get_portfolio_returns_full_committed_detail(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_id = _seed_database(database)
    client = _client_for(database)

    replay = client.get(
        f"{PREFIX}/runs/{run_id}/replay",
        params={"strategy_id": REAL_STRATEGY_IDS[0], "ticket_count": 20},
    ).json()
    portfolio_id = replay["items"][0]["portfolio_id"]

    response = client.get(f"{PREFIX}/portfolios/{portfolio_id}", params={"ticket_count": 15})

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["requested_ticket_count"] == 15
    assert len(body["tickets"]) == 15


# --- default unconfigured app -> 503 NOT_CONFIGURED --------------------------


@pytest.mark.parametrize(
    ("method_path", "params"),
    [
        ("/runs", {}),
        ("/runs/any-run/strategies", {"ticket_count": 10}),
        ("/runs/any-run/replay", {"strategy_id": "any", "ticket_count": 10}),
        ("/portfolios/any-portfolio", {"ticket_count": 10}),
    ],
)
def test_default_unconfigured_app_returns_not_configured(
    method_path: str, params: dict[str, object]
) -> None:
    client = TestClient(create_app())

    response = client.get(f"{PREFIX}{method_path}", params=params)

    assert response.status_code == 503
    body = response.json()
    assert body["error_code"] == "HISTORICAL_RESULTS_NOT_CONFIGURED"


# --- absent configured DB: empty page / not-found, no path created ----------


def test_absent_configured_database_returns_empty_runs_page(tmp_path: Path) -> None:
    database = tmp_path / "does-not-exist" / "historical.db"
    client = _client_for(database)

    response = client.get(f"{PREFIX}/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total_count"] == 0
    assert not database.exists()


def test_absent_configured_database_returns_not_found_for_run_and_portfolio_routes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "does-not-exist" / "historical.db"
    client = _client_for(database)

    strategies_response = client.get(
        f"{PREFIX}/runs/any-run/strategies", params={"ticket_count": 10}
    )
    replay_response = client.get(
        f"{PREFIX}/runs/any-run/replay", params={"strategy_id": "any", "ticket_count": 10}
    )
    portfolio_response = client.get(
        f"{PREFIX}/portfolios/any-portfolio", params={"ticket_count": 10}
    )

    assert strategies_response.status_code == 404
    assert strategies_response.json()["error_code"] == "HISTORICAL_RUN_NOT_FOUND"
    assert replay_response.status_code == 404
    assert replay_response.json()["error_code"] == "HISTORICAL_RUN_NOT_FOUND"
    assert portfolio_response.status_code == 404
    assert portfolio_response.json()["error_code"] == "HISTORICAL_PORTFOLIO_NOT_FOUND"
    assert not database.exists()


# --- sanitized 404 / 422 / 503, no raw exception or path leakage ------------


def test_unknown_run_id_on_configured_database_is_not_found(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    _seed_database(database)
    client = _client_for(database)

    response = client.get(f"{PREFIX}/runs/does-not-exist/strategies", params={"ticket_count": 10})

    assert response.status_code == 404
    assert response.json()["error_code"] == "HISTORICAL_RUN_NOT_FOUND"


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/runs", {"limit": 0}),
        ("/runs", {"limit": 201}),
        ("/runs", {"offset": -1}),
        ("/runs/some-run/strategies", {"ticket_count": 12}),
        ("/runs/some-run/replay", {"strategy_id": "x", "ticket_count": 11}),
        ("/portfolios/some-portfolio", {"ticket_count": 0}),
    ],
)
def test_invalid_query_parameters_return_sanitized_422(
    path: str, params: dict[str, object]
) -> None:
    client = TestClient(create_app())

    response = client.get(f"{PREFIX}{path}", params=params)

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_FAILED"


def test_corrupt_database_returns_sanitized_503_without_leaking_path_or_exception(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    database.write_bytes(b"not a valid sqlite database, just garbage bytes")
    client = _client_for(database)

    response = client.get(f"{PREFIX}/runs")

    assert response.status_code == 503
    body = response.json()
    assert body["error_code"] == "HISTORICAL_RESULTS_UNAVAILABLE"
    raw_text = response.text
    assert str(database) not in raw_text
    assert "Traceback" not in raw_text
    assert "sqlite3" not in raw_text.lower()


# --- OpenAPI response schemas + no DB access at app-construction time -------


def test_openapi_document_declares_all_four_operations() -> None:
    document = create_app().openapi()

    paths = document["paths"]
    assert set(paths[f"{PREFIX}/runs"]) == {"get"}
    assert set(paths[f"{PREFIX}/runs/{{run_id}}/strategies"]) == {"get"}
    assert set(paths[f"{PREFIX}/runs/{{run_id}}/replay"]) == {"get"}
    assert set(paths[f"{PREFIX}/portfolios/{{portfolio_id}}"]) == {"get"}


def test_app_construction_and_openapi_generation_perform_no_db_access(tmp_path: Path) -> None:
    called = False

    def explosive_factory() -> SQLiteHistoricalResultQueryRepository:
        nonlocal called
        called = True
        raise AssertionError("must not be constructed during app/OpenAPI generation")

    app = create_app(historical_query_repository_factory=explosive_factory)
    app.openapi()
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    assert called is False
    assert not (tmp_path / "historical.db").exists()
