from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from datetime import date, timedelta
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
    canonical_json,
)
from lottolab.interfaces.api.app import create_app

PREDICTIONS_PATH = "/api/v1/replay-backfill/predictions"
TASK_ROOT_ENV = "NUMBER2_REPLAY_PREDICTION_VERSION_TASK_ROOT"
LOTTERY_TYPE = LotteryType.BIG_LOTTO.value
STRATEGY_ID = "S"


class _JsonResponse(Protocol):
    status_code: int

    def json(self) -> dict[str, Any]: ...


class _JsonTestClient(Protocol):
    def get(self, url: str, *, params: Any = None) -> _JsonResponse: ...


def _json_client(app: Any) -> _JsonTestClient:
    return cast(_JsonTestClient, TestClient(app))


def _legacy_cursor_token(value: dict[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(canonical_json(value).encode()).decode()
    return encoded.rstrip("=")


def _insert_run(
    connection: sqlite3.Connection,
    run_id: str,
    targets: list[tuple[str, str]],
) -> None:
    manifest = {
        "run_id": run_id,
        "lottery_type": LOTTERY_TYPE,
        "targets": [
            {"draw_number": draw_id, "draw_date": draw_date}
            for draw_id, draw_date in targets
        ],
    }
    connection.execute(
        "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) "
        "VALUES (?,?,?)",
        (run_id, json.dumps(manifest), max(1, len(targets))),
    )


def _insert_cell(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    cell_identity: str,
    strategy_version: str,
    target_draw_id: str,
    target_draw_date: str,
    execution_version: str,
) -> None:
    dataset_identity = f"dataset-{run_id}"
    history_fingerprint = "a" * 64
    cutoff_draw_id = str(int(target_draw_id) - 1)
    cutoff_draw_date = (date.fromisoformat(target_draw_date) - timedelta(days=7)).isoformat()
    source_identity = f"causal-history:{cell_identity}"
    payload = {
        "run_id": run_id,
        "lottery_type": LOTTERY_TYPE,
        "strategy_id": STRATEGY_ID,
        "strategy_version": strategy_version,
        "target_draw_id": target_draw_id,
        "target_draw_date": target_draw_date,
        "execution_status": "COMPLETE",
        "execution_version": execution_version,
        "dataset_identity": dataset_identity,
        "source_history_provenance_status": "VERIFIED",
        "history_fingerprint": history_fingerprint,
        "cutoff_draw_id": cutoff_draw_id,
        "cutoff_draw_date": cutoff_draw_date,
        "prediction_input": {
            "cutoff_draw_id": cutoff_draw_id,
            "cutoff_draw_date": cutoff_draw_date,
            "dataset_identity": dataset_identity,
            "history_fingerprint": history_fingerprint,
            "history_draw_count": 100,
            "source_identity": source_identity,
        },
        "predicted_tickets": [
            {
                "ticket_position": 1,
                "main_numbers": [1, 2, 3, 4, 5, 6],
                "special_number": 7,
                "lottery_type": LOTTERY_TYPE,
                "run_id": run_id,
                "target_draw_id": target_draw_id,
                "strategy_id": STRATEGY_ID,
                "strategy_version": strategy_version,
            }
        ],
        "hit_details": [
            {
                "ticket_position": 1,
                "zone1_hits": 4,
                "zone2_hit": False,
                "prize_tier": None,
                "lottery_type": LOTTERY_TYPE,
                "run_id": run_id,
                "target_draw_id": target_draw_id,
                "strategy_id": STRATEGY_ID,
                "strategy_version": strategy_version,
            }
        ],
    }
    connection.execute(
        "INSERT INTO replay_backfill_cells("
        "cell_identity,lottery_type,strategy_id,strategy_version,execution_version,"
        "dataset_identity,target_draw_id,target_draw_date,execution_status,result_identity,"
        "payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            cell_identity,
            LOTTERY_TYPE,
            STRATEGY_ID,
            strategy_version,
            execution_version,
            dataset_identity,
            target_draw_id,
            target_draw_date,
            "COMPLETE",
            f"result-{cell_identity}",
            json.dumps(payload),
        ),
    )
    connection.execute(
        "INSERT INTO replay_backfill_run_cells(run_id,cell_identity) VALUES (?,?)",
        (run_id, cell_identity),
    )
    connection.execute(
        "INSERT INTO replay_backfill_sources("
        "run_id,source_identity,source_kind,source_locator,source_hash,artifact_only) "
        "VALUES (?,?,?,?,?,0)",
        (
            run_id,
            source_identity,
            "CAUSAL_HISTORY",
            f"replay-input://{run_id}/{cell_identity}",
            history_fingerprint,
        ),
    )


def _build_synthetic_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema(version,checksum) VALUES (?,?)",
            (SCHEMA_VERSION, SCHEMA_CHECKSUM),
        )
        _insert_run(
            connection,
            "R1",
            [
                ("100001", "2025-12-01"),
                ("100002", "2025-12-08"),
                ("100003", "2025-12-15"),
                ("100004", "2025-12-22"),
            ],
        )
        _insert_run(connection, "R2", [("200001", "2026-01-05")])
        cells = (
            {
                "run_id": "R1",
                "cell_identity": "cell-100-ev1",
                "strategy_version": "v1",
                "target_draw_id": "100001",
                "target_draw_date": "2025-12-01",
                "execution_version": "EV1",
            },
            {
                "run_id": "R1",
                "cell_identity": "cell-100-ev2",
                "strategy_version": "v1",
                "target_draw_id": "100001",
                "target_draw_date": "2025-12-01",
                "execution_version": "EV2",
            },
            {
                "run_id": "R1",
                "cell_identity": "cell-101-v1",
                "strategy_version": "v1",
                "target_draw_id": "100002",
                "target_draw_date": "2025-12-08",
                "execution_version": "EV1",
            },
            {
                "run_id": "R1",
                "cell_identity": "cell-102-v2",
                "strategy_version": "v2",
                "target_draw_id": "100003",
                "target_draw_date": "2025-12-15",
                "execution_version": "EV1",
            },
            {
                "run_id": "R1",
                "cell_identity": "cell-103-v2",
                "strategy_version": "v2",
                "target_draw_id": "100004",
                "target_draw_date": "2025-12-22",
                "execution_version": "EV1",
            },
            {
                "run_id": "R2",
                "cell_identity": "cell-r2-v1",
                "strategy_version": "v1",
                "target_draw_id": "200001",
                "target_draw_date": "2026-01-05",
                "execution_version": "EV1",
            },
        )
        for cell in cells:
            _insert_cell(connection, **cell)


@pytest.fixture
def prediction_client(tmp_path: Path) -> tuple[_JsonTestClient, Path]:
    task_root = os.environ.get(TASK_ROOT_ENV)
    artifact_dir = (
        Path(task_root) / "candidate" / "test-artifacts"
        if task_root
        else tmp_path
    )
    database = artifact_dir / f"{tmp_path.name}.sqlite3"
    _build_synthetic_database(database)
    store = SQLiteBackfillStore(database, read_only=True)
    return _json_client(create_app(replay_backfill_store=store)), database


def _params(**overrides: Any) -> dict[str, Any]:
    return {
        "lottery_type": LOTTERY_TYPE,
        "run_id": "R1",
        "strategy_id": STRATEGY_ID,
        **overrides,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_predictions_filter_exact_strategy_version_and_preserve_all_versions(
    prediction_client: tuple[_JsonTestClient, Path],
) -> None:
    client, _ = prediction_client
    v1 = client.get(PREDICTIONS_PATH, params=_params(strategy_version="v1"))
    assert v1.status_code == 200
    assert v1.json()["run_id"] == "R1"
    assert v1.json()["total_count"] == 3
    assert {item["strategy_version"] for item in v1.json()["items"]} == {"v1"}

    v2 = client.get(PREDICTIONS_PATH, params=_params(strategy_version="v2"))
    assert v2.status_code == 200
    assert v2.json()["total_count"] == 2
    assert {item["strategy_version"] for item in v2.json()["items"]} == {"v2"}

    all_versions = client.get(PREDICTIONS_PATH, params=_params())
    assert all_versions.status_code == 200
    assert set(all_versions.json()) == {"run_id", "total_count", "items", "next_cursor"}
    assert all_versions.json()["total_count"] == 5
    assert [item["strategy_version"] for item in all_versions.json()["items"]] == [
        "v1",
        "v1",
        "v1",
        "v2",
        "v2",
    ]

    unknown_version = client.get(PREDICTIONS_PATH, params=_params(strategy_version="v3"))
    assert unknown_version.status_code == 200
    assert unknown_version.json()["total_count"] == 0
    assert unknown_version.json()["items"] == []

    missing_run = client.get(PREDICTIONS_PATH, params=_params(run_id="missing-run"))
    assert missing_run.status_code == 404
    assert missing_run.json() == {"error_code": "REPLAY_BACKFILL_RUN_NOT_FOUND"}

    wrong_lottery = client.get(
        PREDICTIONS_PATH,
        params=_params(lottery_type=LotteryType.DAILY_539.value, strategy_version="v1"),
    )
    assert wrong_lottery.status_code == 422


def test_version_pagination_keeps_cursor_identity_and_execution_cells(
    prediction_client: tuple[_JsonTestClient, Path],
) -> None:
    client, database = prediction_client
    database_hash_before = _sha256(database)
    params = _params(strategy_version="v1", limit=1)
    first = client.get(PREDICTIONS_PATH, params=params)
    assert first.status_code == 200
    assert first.json()["total_count"] == 3
    assert len(first.json()["items"]) == 1

    collected = list(first.json()["items"])
    cursor = first.json()["next_cursor"]
    while cursor is not None:
        page = client.get(PREDICTIONS_PATH, params={**params, "cursor": cursor})
        assert page.status_code == 200
        assert page.json()["total_count"] == 3
        assert all(item["strategy_version"] == "v1" for item in page.json()["items"])
        collected.extend(page.json()["items"])
        cursor = page.json()["next_cursor"]
    assert len(collected) == 3
    assert {item["strategy_version"] for item in collected} == {"v1"}
    same_draw = [item for item in collected if item["target_draw_number"] == "100001"]
    assert {item["execution_version"] for item in same_draw} == {"EV1", "EV2"}
    for item in same_draw:
        assert item["predicted_tickets"][0]["ticket_position"] == 1
        assert item["predicted_tickets"][0]["ticket_identity"]["ticket_position"] == 1
        assert item["source_history_provenance_status"] == "VERIFIED"
        assert item["prediction_cutoff"]["draw_number"] == "100000"
        assert item["prediction_cutoff"]["status"] == "VERIFIED"

    version_cursor = first.json()["next_cursor"]
    assert version_cursor is not None
    assert client.get(
        PREDICTIONS_PATH,
        params={**_params(strategy_version="v2", limit=1), "cursor": version_cursor},
    ).status_code == 422
    assert client.get(
        PREDICTIONS_PATH,
        params={
            **_params(strategy_id="other", strategy_version="v1", limit=1),
            "cursor": version_cursor,
        },
    ).status_code == 422
    assert client.get(
        PREDICTIONS_PATH,
        params={**_params(run_id="R2", strategy_version="v1", limit=1), "cursor": version_cursor},
    ).status_code == 422
    assert client.get(
        PREDICTIONS_PATH,
        params={**params, "period": "50", "cursor": version_cursor},
    ).status_code == 422
    assert _sha256(database) == database_hash_before


def test_unversioned_cursor_keeps_legacy_filter_identity(
    prediction_client: tuple[_JsonTestClient, Path],
) -> None:
    client, _ = prediction_client
    legacy_filters = {
        "lottery_type": LOTTERY_TYPE,
        "run_id": "R1",
        "strategy_id": STRATEGY_ID,
        "from_date": None,
        "to_date": None,
        "period": "ALL",
    }
    query_hash = hashlib.sha256(canonical_json(legacy_filters).encode()).hexdigest()
    legacy_cursor = _legacy_cursor_token(
        {
            "kind": "predictions",
            "query": query_hash,
            "run_id": "R1",
            "after": ["2025-12-01", 100001, STRATEGY_ID, "v1", "cell-100-ev1"],
        }
    )
    response = client.get(
        PREDICTIONS_PATH,
        params={**_params(limit=1), "cursor": legacy_cursor},
    )
    assert response.status_code == 200
    assert response.json()["total_count"] == 5
    assert response.json()["items"][0]["target_draw_number"] == "100001"
    assert response.json()["items"][0]["execution_version"] == "EV2"


def test_version_query_validation_and_sql_parameter_binding(
    prediction_client: tuple[_JsonTestClient, Path],
) -> None:
    client, database = prediction_client
    invalid_queries = [
        _params(strategy_version=""),
        _params(strategy_version="   "),
        {"lottery_type": LOTTERY_TYPE, "strategy_version": "v1"},
        {"run_id": "R1", "strategy_id": STRATEGY_ID, "strategy_version": "v1"},
        _params(strategy_version="v" * 201),
        _params(run_id=" R1", strategy_version="v1"),
        _params(run_id="R" * 201, strategy_version="v1"),
        _params(strategy_version="v1", limit=0),
        _params(strategy_version="v1", period="25"),
    ]
    for query in invalid_queries:
        response = client.get(PREDICTIONS_PATH, params=query)
        assert response.status_code == 422, query

    before = _sha256(database)
    injected = client.get(
        PREDICTIONS_PATH,
        params=_params(strategy_version="v1' OR 1=1 --"),
    )
    after = _sha256(database)
    assert injected.status_code == 200
    assert injected.json()["total_count"] == 0
    assert injected.json()["items"] == []
    assert after == before


def test_openapi_adds_optional_version_to_the_existing_predictions_operation(
    prediction_client: tuple[_JsonTestClient, Path],
) -> None:
    client, _ = prediction_client
    response = client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    path_item = document["paths"][PREDICTIONS_PATH]
    assert set(path_item) == {"get"}
    operation = path_item["get"]
    assert operation["operationId"] == "predictions_api_v1_replay_backfill_predictions_get"
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["strategy_version"]["required"] is False
    version_schema = parameters["strategy_version"]["schema"]
    if "anyOf" in version_schema:
        version_schema = next(
            schema for schema in version_schema["anyOf"] if schema.get("type") == "string"
        )
    assert version_schema["minLength"] == 1
    assert version_schema["maxLength"] == 200
