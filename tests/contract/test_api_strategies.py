"""API contract tests — the payload shape the frontend TypeScript types rely on."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

import json
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.interfaces.api.app import create_app
from lottolab.strategies.catalog import StrategyCatalog

ROOT = Path(__file__).resolve().parents[2]


def fixture_catalog() -> StrategyCatalog:
    return StrategyCatalog(
        [
            StrategyDescriptor(
                strategy_id="fixture_observation_strategy",
                strategy_name="Fixture Observation Strategy",
                version="v0.1",
                lottery_types=(LotteryType.BIG_LOTTO,),
                lifecycle_status=LifecycleStatus.OBSERVATION,
                executable=False,
            )
        ]
    )


def test_health() -> None:
    client = TestClient(create_app(fixture_catalog()))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "api_version": "v1"}


def test_strategies_contract_shape() -> None:
    client = TestClient(create_app(fixture_catalog()))
    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    assert response.json() == [
        {
            "strategy_id": "fixture_observation_strategy",
            "display_name": "Fixture Observation Strategy",
            "version": "v0.1",
            "supported_lottery_types": ["BIG_LOTTO"],
            "minimum_history": 1,
            "lifecycle_status": "OBSERVATION",
            "executable": False,
        }
    ]


def test_default_strategy_endpoint_is_db_free(monkeypatch: MonkeyPatch) -> None:
    import sqlite3

    def fail_on_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"unexpected sqlite connect: {args!r} {kwargs!r}")

    monkeypatch.setattr(sqlite3, "connect", fail_on_connect)
    client = TestClient(create_app())
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "api_version": "v1"}
    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    manifest = cast(
        dict[str, object],
        json.loads(
            (ROOT / "tests/fixtures/legacy/p600b/manifest.json").read_text(encoding="utf-8")
        ),
    )
    scope = cast(dict[str, object], manifest["scope"])
    target_ids = cast(list[str], scope["strategy_ids"])
    records = cast(list[dict[str, object]], response.json())
    records_by_id = {str(record["strategy_id"]): record for record in records}
    assert set(target_ids) <= records_by_id.keys()
    assert [
        record["strategy_id"] for record in records if record["strategy_id"] in target_ids
    ] == target_ids
    assert all(
        records_by_id[strategy_id]["lifecycle_status"] == "OBSERVATION"
        for strategy_id in target_ids
    )
    assert all(records_by_id[strategy_id]["executable"] is False for strategy_id in target_ids)


def test_openapi_exposes_exact_local_runtime_operation_set() -> None:
    response = TestClient(create_app()).get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    operations = {
        (method, path)
        for path, path_item in document["paths"].items()
        for method in path_item
        if method in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    }
    assert operations == {
        ("get", "/api/health"),
        ("get", "/api/v1/strategies"),
        ("post", "/api/v1/draw-imports/preview"),
        ("post", "/api/v1/draw-imports/commit"),
        ("get", "/api/v1/draws"),
        ("get", "/api/v1/draws/{lottery_type}/{draw_number}"),
        ("get", "/api/v1/ingestion-runs"),
        ("get", "/api/v1/ingestion-runs/{run_id}"),
    }


def test_committed_openapi_contract_is_current() -> None:
    committed = cast(
        dict[str, object],
        json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8")),
    )
    assert committed == create_app().openapi()
