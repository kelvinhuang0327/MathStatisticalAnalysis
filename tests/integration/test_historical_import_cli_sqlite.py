"""SQLite and HTTP readback acceptance for the Historical Results import CLI."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from tests.fixtures.historical.builder import (
    REAL_STRATEGY_IDS,
    build_baseline_envelope,
    envelope_bytes,
)
from typer.testing import CliRunner

from lottolab.application.historical_queries import HistoricalReplayQuery, HistoricalRunQuery
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
)
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.cli.main import app

runner = CliRunner()
API_PREFIX = "/api/v1/historical-results"


def _task_path(tmp_path: Path, env_name: str, filename: str) -> Path:
    configured_root = os.environ.get(env_name)
    root = Path(configured_root) if configured_root else tmp_path
    case_root = Path(tempfile.mkdtemp(prefix=f"{tmp_path.name}-", dir=root))
    return case_root / filename


def _invoke(input_path: Path, database: Path) -> tuple[int, dict[str, Any], str]:
    result = runner.invoke(
        app,
        [
            "import-historical-results",
            "--input",
            str(input_path),
            "--database",
            str(database),
        ],
    )
    return result.exit_code, json.loads(result.stdout), result.stderr


def _client(database: Path) -> TestClient:
    return TestClient(
        create_app(
            historical_query_repository_factory=lambda: SQLiteHistoricalResultQueryRepository(
                database
            )
        )
    )


def test_valid_import_round_trips_through_query_repository_and_http_api(
    tmp_path: Path,
) -> None:
    envelope = build_baseline_envelope()
    input_path = _task_path(
        tmp_path,
        "LOTTOLAB_HISTORICAL_IMPORT_TEST_INPUT_ROOT",
        "valid-target-envelope.json",
    )
    input_path.write_bytes(envelope_bytes(envelope))
    database = _task_path(
        tmp_path,
        "LOTTOLAB_HISTORICAL_IMPORT_TEST_DATABASE_ROOT",
        "historical-results.db",
    )

    exit_code, first_output, stderr = _invoke(input_path, database)

    assert exit_code == 0
    assert stderr == ""
    assert first_output["status"] == "COMPLETED"
    assert first_output["reason_code"] is None
    assert first_output["is_idempotent_replay"] is False
    assert first_output["import_identity_sha256"] == envelope["import_identity_sha256"]
    assert first_output["manifest_sha256"] == envelope["manifest_sha256"]
    run_id = first_output["run_id"]

    repository = SQLiteHistoricalResultQueryRepository(database)
    runs = repository.list_runs(HistoricalRunQuery())
    assert runs.total_count == 1
    (run,) = runs.items
    assert run.run_id == run_id
    assert run.import_identity_sha256 == envelope["import_identity_sha256"]
    assert run.manifest_sha256 == envelope["manifest_sha256"]
    assert run.source_commit_oid == envelope["source"]["source_commit_oid"]
    assert run.source_artifact_sha256 == envelope["source"]["source_artifact_sha256"]
    assert run.dataset_identity == envelope["dataset"]["dataset_identity"]
    assert run.dataset_sha256 == envelope["dataset"]["dataset_sha256"]

    strategies = repository.list_strategies(run_id, ticket_count=20)
    assert strategies is not None
    actual_strategy_identities = [
        (
            item.strategy_id,
            item.effective_strategy_id,
            item.strategy_version,
            item.replicate,
            item.identity_kind,
            item.governance_status,
            item.alias_of_strategy_id,
            item.equivalence_group,
            item.nested_prefix_supported,
        )
        for item in strategies.items
    ]
    expected_strategy_identities = sorted(
        (
            item["strategy_id"],
            item["effective_strategy_id"],
            item["strategy_version"],
            item["replicate"],
            item["identity_kind"],
            item["governance_status"],
            item.get("alias_of_strategy_id"),
            item.get("equivalence_group"),
            item["nested_prefix_supported"],
        )
        for item in envelope["strategy_descriptors"]
    )
    assert actual_strategy_identities == expected_strategy_identities

    replay = repository.list_replay_portfolios(
        run_id,
        HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20),
    )
    assert replay is not None
    assert replay.total_count == 1
    (portfolio,) = replay.items
    source_portfolio = next(
        item for item in envelope["portfolios"] if item["strategy_id"] == REAL_STRATEGY_IDS[0]
    )
    assert portfolio.portfolio_sha256 == source_portfolio["portfolio_sha256"]
    assert portfolio.prefix10_sha256 == source_portfolio["prefix10_sha256"]
    assert portfolio.prefix15_sha256 == source_portfolio["prefix15_sha256"]
    assert [ticket.portfolio_position for ticket in portfolio.tickets] == list(range(1, 21))
    assert [ticket.ticket_sha256 for ticket in portfolio.tickets] == [
        ticket["ticket_sha256"] for ticket in source_portfolio["tickets"]
    ]

    client = _client(database)
    runs_response = client.get(f"{API_PREFIX}/runs")
    strategies_response = client.get(
        f"{API_PREFIX}/runs/{run_id}/strategies",
        params={"ticket_count": 20},
    )
    replay_response = client.get(
        f"{API_PREFIX}/runs/{run_id}/replay",
        params={"strategy_id": REAL_STRATEGY_IDS[0], "ticket_count": 20},
    )
    portfolio_response = client.get(
        f"{API_PREFIX}/portfolios/{portfolio.portfolio_id}",
        params={"ticket_count": 20},
    )
    assert runs_response.status_code == 200
    assert strategies_response.status_code == 200
    assert replay_response.status_code == 200
    assert portfolio_response.status_code == 200
    assert runs_response.json()["items"][0]["import_identity_sha256"] == (
        envelope["import_identity_sha256"]
    )
    assert replay_response.json()["items"][0]["prefix10_sha256"] == (
        source_portfolio["prefix10_sha256"]
    )
    assert replay_response.json()["items"][0]["prefix15_sha256"] == (
        source_portfolio["prefix15_sha256"]
    )
    assert [
        ticket["ticket_sha256"] for ticket in portfolio_response.json()["tickets"]
    ] == [ticket["ticket_sha256"] for ticket in source_portfolio["tickets"]]

    exit_code, replay_output, stderr = _invoke(input_path, database)

    assert exit_code == 0
    assert stderr == ""
    assert replay_output["status"] == "COMPLETED"
    assert replay_output["run_id"] == run_id
    assert replay_output["is_idempotent_replay"] is True
    after_replay = SQLiteHistoricalResultQueryRepository(database)
    assert after_replay.list_runs(HistoricalRunQuery()).total_count == 1
    replay_page = after_replay.list_replay_portfolios(
        run_id,
        HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20),
    )
    assert replay_page is not None
    assert replay_page.total_count == 1

    containment_root = database.parent.resolve(strict=True)
    database_outputs = [
        path for path in database.parent.rglob("*") if path.is_file() or path.is_symlink()
    ]
    assert database_outputs
    for output in database_outputs:
        output.resolve(strict=False).relative_to(containment_root)
        assert output.name == database.name or output.name in {
            f"{database.name}-wal",
            f"{database.name}-shm",
        }


def test_hash_invalid_envelope_leaves_existing_database_unchanged(
    tmp_path: Path,
) -> None:
    envelope = build_baseline_envelope()
    input_path = _task_path(
        tmp_path,
        "LOTTOLAB_HISTORICAL_IMPORT_TEST_INPUT_ROOT",
        "valid-target-envelope.json",
    )
    input_path.write_bytes(envelope_bytes(envelope))
    database = _task_path(
        tmp_path,
        "LOTTOLAB_HISTORICAL_IMPORT_TEST_DATABASE_ROOT",
        "historical-results.db",
    )
    exit_code, output, stderr = _invoke(input_path, database)
    assert exit_code == 0
    assert stderr == ""
    run_id = output["run_id"]

    repository = SQLiteHistoricalResultQueryRepository(database)
    before_runs = repository.list_runs(HistoricalRunQuery())
    before_strategies = repository.list_strategies(run_id, ticket_count=20)
    before_replay = repository.list_replay_portfolios(
        run_id,
        HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20),
    )

    invalid = dict(envelope)
    invalid["manifest_sha256"] = "0" * 64
    invalid_input = input_path.with_name("hash-invalid-target-envelope.json")
    invalid_input.write_bytes(envelope_bytes(invalid))

    exit_code, invalid_output, stderr = _invoke(invalid_input, database)

    assert exit_code == 1
    assert stderr == ""
    assert invalid_output == {
        "reason_code": "IMPORT_MANIFEST_HASH_MISMATCH",
        "status": "IMPORT_MANIFEST_HASH_MISMATCH",
    }
    after = SQLiteHistoricalResultQueryRepository(database)
    assert after.list_runs(HistoricalRunQuery()) == before_runs
    assert after.list_strategies(run_id, ticket_count=20) == before_strategies
    assert (
        after.list_replay_portfolios(
            run_id,
            HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20),
        )
        == before_replay
    )
