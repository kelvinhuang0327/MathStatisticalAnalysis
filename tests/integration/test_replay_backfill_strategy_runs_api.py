from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Protocol, cast

import pytest
from fastapi.testclient import TestClient

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_CHECKSUM,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    SQLiteBackfillStore,
)
from lottolab.interfaces.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
API_PATH = "/api/v1/replay-backfill/strategy-runs"
TASK_ROOT_ENV = "NUMBER2_STRATEGY_RUNS_TASK_ROOT"


class _JsonResponse(Protocol):
    status_code: int

    def json(self) -> dict[str, Any]: ...


class _JsonTestClient(Protocol):
    def get(self, url: str, *, params: Any = None) -> _JsonResponse: ...


def _json_client(app: Any) -> _JsonTestClient:
    return cast(_JsonTestClient, TestClient(app))


def _insert_run(connection: sqlite3.Connection, run_id: str, created_at: str) -> None:
    connection.execute(
        "INSERT INTO replay_backfill_runs(run_id, manifest_json, expected_cells, created_at) "
        "VALUES (?, ?, ?, ?)",
        (
            run_id,
            json.dumps({"run_id": run_id, "lottery_type": LotteryType.BIG_LOTTO.value}),
            1,
            created_at,
        ),
    )


def _insert_inventory(connection: sqlite3.Connection, run_id: str, strategy_version: str) -> None:
    connection.execute(
        "INSERT INTO replay_backfill_strategy_inventory("
        "run_id, lottery_type, strategy_id, strategy_version, display_name, "
        "lifecycle_status, data_status, source_kind, executable, available_target_count, "
        "training_status, source_identity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            LotteryType.BIG_LOTTO.value,
            "strategy-alpha",
            strategy_version,
            "Synthetic strategy",
            "ACTIVE",
            "AVAILABLE",
            "TEST",
            1,
            2,
            "TRAINED",
            "synthetic-fixture-v1",
        ),
    )


def _insert_cell(
    connection: sqlite3.Connection,
    *,
    cell_identity: str,
    strategy_version: str,
    target_draw_id: str,
    target_draw_date: str,
    execution_version: str,
    dataset_identity: str,
    execution_status: str,
) -> None:
    connection.execute(
        "INSERT INTO replay_backfill_cells("
        "cell_identity, lottery_type, strategy_id, strategy_version, execution_version, "
        "dataset_identity, target_draw_id, target_draw_date, execution_status, "
        "result_identity, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            cell_identity,
            LotteryType.BIG_LOTTO.value,
            "strategy-alpha",
            strategy_version,
            execution_version,
            dataset_identity,
            target_draw_id,
            target_draw_date,
            execution_status,
            f"result-{cell_identity}",
            json.dumps({"cell_identity": cell_identity}),
        ),
    )


def _link_cell(connection: sqlite3.Connection, run_id: str, cell_identity: str) -> None:
    connection.execute(
        "INSERT INTO replay_backfill_run_cells(run_id, cell_identity) VALUES (?, ?)",
        (run_id, cell_identity),
    )


def _build_synthetic_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema(version, checksum) VALUES (?, ?)",
            (SCHEMA_VERSION, SCHEMA_CHECKSUM),
        )
        _insert_run(connection, "run-v1-old", "2026-01-01T00:00:00+00:00")
        _insert_run(connection, "run-v1-shared", "2026-01-02T00:00:00+00:00")
        _insert_run(connection, "run-v1-inventory-only", "2026-01-03T00:00:00+00:00")
        _insert_run(connection, "run-v2", "2026-01-04T00:00:00+00:00")
        _insert_run(connection, "run-latest-without-strategy", "2026-01-05T00:00:00+00:00")

        for run_id in ("run-v1-old", "run-v1-shared", "run-v1-inventory-only"):
            _insert_inventory(connection, run_id, "v1")
        _insert_inventory(connection, "run-v2", "v2")

        cells = (
            {
                "cell_identity": "cell-shared-v1",
                "strategy_version": "v1",
                "target_draw_id": "100001",
                "target_draw_date": "2025-12-01",
                "execution_version": "exec-v1",
                "dataset_identity": "dataset-a",
                "execution_status": "COMPLETE",
            },
            {
                "cell_identity": "cell-conflict-v1",
                "strategy_version": "v1",
                "target_draw_id": "100001",
                "target_draw_date": "2025-12-01",
                "execution_version": "exec-v2",
                "dataset_identity": "dataset-a",
                "execution_status": "FAILED",
            },
            {
                "cell_identity": "cell-second-target-v1",
                "strategy_version": "v1",
                "target_draw_id": "100002",
                "target_draw_date": "2025-12-08",
                "execution_version": "exec-v1",
                "dataset_identity": "dataset-a",
                "execution_status": "PARTIAL",
            },
            {
                "cell_identity": "cell-v2",
                "strategy_version": "v2",
                "target_draw_id": "200001",
                "target_draw_date": "2025-12-15",
                "execution_version": "exec-v3",
                "dataset_identity": "dataset-b",
                "execution_status": "COMPLETE",
            },
        )
        for cell in cells:
            _insert_cell(connection, **cell)

        _link_cell(connection, "run-v1-old", "cell-shared-v1")
        _link_cell(connection, "run-v1-old", "cell-conflict-v1")
        _link_cell(connection, "run-v1-old", "cell-second-target-v1")
        _link_cell(connection, "run-v1-shared", "cell-shared-v1")
        _link_cell(connection, "run-v2", "cell-v2")


@pytest.fixture(scope="session")
def synthetic_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    task_root_value = os.environ.get(TASK_ROOT_ENV)
    if task_root_value:
        artifact_dir = Path(task_root_value) / "candidate" / "test-artifacts"
    else:
        artifact_dir = tmp_path_factory.mktemp("replay-strategy-runs-api")
    path = artifact_dir / "strategy-runs.sqlite3"
    _build_synthetic_database(path)
    return path


@pytest.fixture(scope="session")
def readonly_store(synthetic_database: Path) -> SQLiteBackfillStore:
    return SQLiteBackfillStore(synthetic_database, read_only=True)


@pytest.fixture(scope="session")
def client(readonly_store: SQLiteBackfillStore) -> _JsonTestClient:
    return _json_client(create_app(replay_backfill_store=readonly_store))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _params(**overrides: Any) -> dict[str, Any]:
    return {
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "strategy_id": "strategy-alpha",
        **overrides,
    }


def test_strategy_runs_preserves_identity_inventory_and_execution_counts(
    client: _JsonTestClient,
) -> None:
    response = client.get(API_PATH, params=_params())

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "total_run_version_matches",
        "items",
        "has_more",
        "limit",
        "offset",
    }
    assert payload["total_run_version_matches"] == 4
    assert payload["has_more"] is False
    assert [item["run_id"] for item in payload["items"]] == [
        "run-v2",
        "run-v1-inventory-only",
        "run-v1-shared",
        "run-v1-old",
    ]
    assert "run-latest-without-strategy" not in {item["run_id"] for item in payload["items"]}

    by_run = {item["run_id"]: item for item in payload["items"]}
    assert by_run["run-v2"]["strategy_version"] == "v2"
    assert by_run["run-v1-old"]["strategy_version"] == "v1"
    assert by_run["run-v1-old"]["associated_cell_count"] == 3
    assert by_run["run-v1-old"]["unique_target_draw_count"] == 2
    assert by_run["run-v1-old"]["execution_identity_count"] == 2
    assert by_run["run-v1-old"]["execution_status_counts"] == {
        "COMPLETE": 1,
        "FAILED": 1,
        "PARTIAL": 1,
    }
    assert by_run["run-v1-old"]["earliest_target_draw_date"] == "2025-12-01"
    assert by_run["run-v1-old"]["latest_target_draw_date"] == "2025-12-08"

    inventory_only = by_run["run-v1-inventory-only"]
    assert inventory_only["inventory_present"] is True
    assert inventory_only["associated_cell_count"] == 0
    assert inventory_only["unique_target_draw_count"] == 0
    assert inventory_only["execution_identity_count"] == 0
    assert inventory_only["execution_status_counts"] == {}
    assert inventory_only["earliest_target_draw_date"] is None
    assert inventory_only["latest_target_draw_date"] is None

    shared_cell_run = by_run["run-v1-shared"]
    assert shared_cell_run["associated_cell_count"] == 1
    assert shared_cell_run["unique_target_draw_count"] == 1


def test_strategy_version_filter_empty_result_and_pagination(client: _JsonTestClient) -> None:
    version_response = client.get(API_PATH, params=_params(strategy_version="v1"))
    assert version_response.status_code == 200
    assert version_response.json()["total_run_version_matches"] == 3
    assert {item["strategy_version"] for item in version_response.json()["items"]} == {"v1"}

    v2_response = client.get(API_PATH, params=_params(strategy_version="v2"))
    assert v2_response.status_code == 200
    assert [item["run_id"] for item in v2_response.json()["items"]] == ["run-v2"]

    page_one = client.get(API_PATH, params=_params(limit=1))
    assert page_one.status_code == 200
    assert len(page_one.json()["items"]) == 1
    assert page_one.json()["total_run_version_matches"] == 4
    assert page_one.json()["has_more"] is True
    assert page_one.json()["items"][0]["run_id"] == "run-v2"

    page_after_end = client.get(API_PATH, params=_params(offset=4))
    assert page_after_end.status_code == 200
    assert page_after_end.json()["total_run_version_matches"] == 4
    assert page_after_end.json()["items"] == []
    assert page_after_end.json()["has_more"] is False

    empty = client.get(API_PATH, params=_params(strategy_id="does-not-exist"))
    assert empty.status_code == 200
    assert empty.json()["total_run_version_matches"] == 0
    assert empty.json()["items"] == []
    assert empty.json()["has_more"] is False


def test_strategy_id_is_bound_and_database_access_is_read_only(
    client: _JsonTestClient, synthetic_database: Path
) -> None:
    before = _sha256(synthetic_database)
    response = client.get(API_PATH, params=_params(strategy_id="strategy-alpha' OR 1=1 --"))
    after = _sha256(synthetic_database)

    assert response.status_code == 200
    assert response.json()["total_run_version_matches"] == 0
    assert response.json()["items"] == []
    assert after == before


def test_query_validation_errors_are_422(client: _JsonTestClient) -> None:
    invalid_queries: list[dict[str, Any]] = [
        {"strategy_id": "strategy-alpha"},
        {"lottery_type": LotteryType.BIG_LOTTO.value},
        _params(strategy_id=""),
        _params(strategy_id="   "),
        _params(strategy_id="s" * 201),
        _params(lottery_type="NOT_A_LOTTERY"),
        _params(limit=0),
        _params(limit=251),
        _params(offset=-1),
        _params(offset=9_007_199_254_740_992),
        _params(strategy_version=""),
        _params(strategy_version="   "),
    ]

    for query in invalid_queries:
        response = client.get(API_PATH, params=query)
        assert response.status_code == 422, query


def test_unconfigured_store_and_store_failures_are_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOTTOLAB_REPLAY_BACKFILL_DB", raising=False)
    unconfigured = _json_client(create_app(replay_backfill_store=None)).get(
        API_PATH, params=_params()
    )
    assert unconfigured.status_code == 503
    assert unconfigured.json() == {"error_code": "REPLAY_BACKFILL_NOT_CONFIGURED"}

    class BrokenStore:
        def discover_strategy_runs(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("synthetic query failure")

    broken_app = create_app(replay_backfill_store=cast(SQLiteBackfillStore, BrokenStore()))
    failed = _json_client(broken_app).get(API_PATH, params=_params())
    assert failed.status_code == 503
    assert failed.json() == {"error_code": "REPLAY_BACKFILL_UNAVAILABLE"}


def test_openapi_declares_one_get_with_strict_response_models(
    client: _JsonTestClient, readonly_store: SQLiteBackfillStore
) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    generated = response.json()
    static = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))
    assert generated == static

    path_item = generated["paths"][API_PATH]
    assert set(path_item) == {"get"}
    operation = path_item["get"]
    assert operation["operationId"] == "discoverReplayBackfillStrategyRuns"
    operation_ids = [
        item["operationId"]
        for value in generated["paths"].values()
        for method, item in value.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert set(parameters) == {
        "lottery_type",
        "strategy_id",
        "strategy_version",
        "limit",
        "offset",
    }
    assert parameters["lottery_type"]["required"] is True
    assert parameters["strategy_id"]["required"] is True
    assert parameters["strategy_id"]["schema"]["maxLength"] == 200
    assert parameters["strategy_version"]["required"] is False
    assert parameters["limit"]["schema"]["default"] == 50
    assert parameters["limit"]["schema"]["maximum"] == 250
    assert parameters["offset"]["schema"]["default"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 9_007_199_254_740_991

    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/ReplayBackfillStrategyRunsPageResponse")
    page_model = generated["components"]["schemas"]["ReplayBackfillStrategyRunsPageResponse"]
    item_model = generated["components"]["schemas"]["ReplayBackfillStrategyRunItemResponse"]
    assert page_model["additionalProperties"] is False
    assert item_model["additionalProperties"] is False
    assert set(page_model["properties"]) == {
        "total_run_version_matches",
        "items",
        "has_more",
        "limit",
        "offset",
    }
    assert set(item_model["properties"]) == {
        "run_id",
        "lottery_type",
        "strategy_id",
        "strategy_version",
        "run_created_at",
        "inventory_present",
        "associated_cell_count",
        "unique_target_draw_count",
        "execution_identity_count",
        "execution_status_counts",
        "earliest_target_draw_date",
        "latest_target_draw_date",
    }
    assert readonly_store.read_only is True
