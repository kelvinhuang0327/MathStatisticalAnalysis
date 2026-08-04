"""Acceptance coverage for the P638 Historical Results V2 vertical."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lottolab.application.p638_historical import P638ForwardingResult
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
)
from lottolab.infrastructure.persistence.historical_schema import verify_schema_read_only
from lottolab.infrastructure.persistence.p638_historical_forwarder import (
    P638HistoricalForwarder,
)
from lottolab.infrastructure.persistence.p638_historical_repositories import (
    SQLiteP638HistoricalQueryRepository,
)
from lottolab.interfaces.api.app import create_app

WORKSPACE = Path(__file__).parents[5]
SOURCE_REPLAY_DB = (
    WORKSPACE
    / ".runs/MathStatisticalAnalysis/P638_WAVE1_REPLAY_R4_LEDGER_SOURCE_AUTHORITY"
    / "p638_wave1_replay_r4.sqlite3"
)
SOURCE_DRAW_DB = (
    WORKSPACE
    / ".runs/MathStatisticalAnalysis/P638_OLD_DB_DRAW_MIGRATION_R1"
    / "powerlotto_draws.sqlite3"
)


@pytest.fixture(scope="module")
def forwarded_p638_database(tmp_path_factory: pytest.TempPathFactory) -> tuple[
    Path, P638ForwardingResult, P638ForwardingResult
]:
    if not SOURCE_REPLAY_DB.exists() or not SOURCE_DRAW_DB.exists():
        pytest.skip("authoritative P638 source databases are not present")
    replay_before = _sha256(SOURCE_REPLAY_DB)
    draws_before = _sha256(SOURCE_DRAW_DB)
    output = tmp_path_factory.mktemp("p638-historical") / "historical_results_v2.sqlite3"
    forwarder = P638HistoricalForwarder(
        source_replay_db=SOURCE_REPLAY_DB,
        source_draw_db=SOURCE_DRAW_DB,
        output_db=output,
    )
    first = forwarder.forward()
    second = forwarder.forward()
    assert _sha256(SOURCE_REPLAY_DB) == replay_before
    assert _sha256(SOURCE_DRAW_DB) == draws_before
    return output, first, second


def test_forwarding_is_complete_idempotent_and_source_immutable(
    forwarded_p638_database: tuple[
        Path, P638ForwardingResult, P638ForwardingResult
    ],
) -> None:
    database, first, second = forwarded_p638_database
    assert verify_schema_read_only(database) is True
    assert first.strategy_count == 10
    assert first.draw_count == 1933
    assert first.source_target_count == 15464
    assert first.source_complete_target_count == 15224
    assert first.source_excluded_target_count == 240
    assert first.source_failed_target_count == 0
    assert first.source_ticket_count == 39963
    assert first.forwarded_target_count == 15464
    assert first.forwarded_complete_target_count == 15224
    assert first.forwarded_excluded_target_count == 240
    assert first.forwarded_failed_target_count == 0
    assert first.forwarded_ticket_count == 39963
    assert first.excluded_strategy_count == 2
    assert second.run_id == first.run_id
    assert second.import_identity_sha256 == first.import_identity_sha256
    assert second.is_idempotent_replay is True


def test_repository_exposes_registry_replay_metrics_and_ranges(
    forwarded_p638_database: tuple[
        Path, P638ForwardingResult, P638ForwardingResult
    ],
) -> None:
    database = forwarded_p638_database[0]
    repository = SQLiteP638HistoricalQueryRepository(database)
    runs = repository.list_runs(limit=10, offset=0)
    assert runs.total_count == 1
    run = runs.items[0]
    assert run.strategy_count == 10
    assert run.draw_count == 1933
    assert run.first_draw_number == "97000001"
    assert run.last_draw_number == "115000061"

    strategies = repository.list_strategies(run.run_id, limit=200, offset=0)
    assert strategies is not None
    assert len(strategies.items) == 10
    assert sum(item.replay_status == "R4_RESULT_REUSABLE" for item in strategies.items) == 8
    assert sum(item.replay_status != "R4_RESULT_REUSABLE" for item in strategies.items) == 2
    assert sum(item.ticket_count for item in strategies.items) == 39963
    excluded_strategy = next(
        item for item in strategies.items if item.strategy_id == "power_fourier_rhythm_2bet"
    )
    assert excluded_strategy.replay_status == "EXCLUDED_UNRESOLVED_CONTRACT"
    assert "bounded P47/P56/P128 adapter wave" in (excluded_strategy.exclusion_reason or "")
    assert excluded_strategy.ticket_count == 0

    replay = repository.list_replay(run.run_id, query=_replay_query())
    assert replay is not None
    assert replay.total_count == 15464
    assert replay.items[0].target_draw_date == "2008-01-24"
    complete = repository.list_replay(
        run.run_id,
        query=_replay_query(status="COMPLETE"),
    )
    assert complete is not None
    assert complete.items[0].status == "COMPLETE"
    assert len(complete.items[0].tickets) in {2, 3, 4}
    excluded = repository.list_replay(
        run.run_id,
        query=_replay_query(status="EXCLUDED_INSUFFICIENT_HISTORY"),
    )
    assert excluded is not None
    assert excluded.total_count == 240
    assert excluded.items[0].tickets == ()

    metrics = repository.get_metrics(run.run_id)
    assert metrics is not None
    assert metrics.target_count == 15464
    assert metrics.complete_target_count == 15224
    assert metrics.excluded_target_count == 240
    assert metrics.ticket_count == 39963
    assert metrics.first_draw_number == "97000001"
    assert metrics.last_draw_number == "115000061"


def test_p638_api_is_lottery_scoped_and_factory_is_lazy(
    forwarded_p638_database: tuple[
        Path, P638ForwardingResult, P638ForwardingResult
    ],
) -> None:
    database = forwarded_p638_database[0]
    repository = SQLiteP638HistoricalQueryRepository(database)
    generic_repository = SQLiteHistoricalResultQueryRepository(database)
    calls = 0

    def factory() -> SQLiteP638HistoricalQueryRepository:
        nonlocal calls
        calls += 1
        return repository

    app = create_app(
        historical_query_repository_factory=lambda: generic_repository,
        p638_historical_query_repository_factory=factory,
    )
    assert calls == 0
    assert "/api/v1/p638-historical/runs" in app.openapi()["paths"]
    assert calls == 0
    client: Any = TestClient(app)

    runs_response = client.get("/api/v1/p638-historical/runs?limit=10&offset=0")
    assert runs_response.status_code == 200
    run = runs_response.json()["items"][0]
    assert run["strategy_count"] == 10
    run_id = run["run_id"]
    assert calls == 1

    strategies_response = client.get(
        f"/api/v1/p638-historical/runs/{run_id}/strategies?limit=200&offset=0"
    )
    assert strategies_response.status_code == 200
    assert len(strategies_response.json()["items"]) == 10

    replay_response = client.get(
        f"/api/v1/p638-historical/runs/{run_id}/replay?strategy_id=zonal_entropy_2bet&status=COMPLETE&limit=5&offset=0"
    )
    assert replay_response.status_code == 200
    assert replay_response.json()["total_count"] == 1903
    assert all(
        item["strategy_id"] == "zonal_entropy_2bet"
        for item in replay_response.json()["items"]
    )

    metrics_response = client.get(f"/api/v1/p638-historical/runs/{run_id}/metrics")
    assert metrics_response.status_code == 200
    assert metrics_response.json()["ticket_count"] == 39963

    target_id = replay_response.json()["items"][0]["target_id"]
    detail_response = client.get(
        f"/api/v1/p638-historical/runs/{run_id}/targets/{target_id}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["target_id"] == target_id

    generic_runs = client.get(
        "/api/v1/historical-results/runs?lottery_type=POWER_LOTTO&limit=10&offset=0"
    )
    assert generic_runs.status_code == 200
    assert generic_runs.json()["items"][0]["strategy_count"] == 10
    assert generic_runs.json()["items"][0]["portfolio_count"] == 15464


def test_p638_api_reports_unconfigured_without_opening_a_database() -> None:
    client: Any = TestClient(create_app())
    response = client.get("/api/v1/p638-historical/runs")
    assert response.status_code == 503
    assert response.json()["error_code"] == "P638_HISTORICAL_NOT_CONFIGURED"


def _replay_query(*, status: str | None = None):
    from lottolab.application.p638_historical import P638ReplayQuery

    return P638ReplayQuery(limit=3, offset=0, status=status)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
