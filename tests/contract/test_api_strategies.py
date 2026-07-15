"""API contract tests — the payload shape the frontend TypeScript types rely on."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from fastapi.testclient import TestClient

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.interfaces.api.app import create_app
from lottolab.strategies.catalog import StrategyCatalog


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
    response = client.get("/api/strategies")
    assert response.status_code == 200
    assert response.json() == [
        {
            "strategy_id": "fixture_observation_strategy",
            "strategy_name": "Fixture Observation Strategy",
            "version": "v0.1",
            "lottery_types": ["BIG_LOTTO"],
            "lifecycle_status": "OBSERVATION",
            "executable": False,
        }
    ]
