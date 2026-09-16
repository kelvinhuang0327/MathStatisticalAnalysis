"""HTTP contracts for the canonical structural Matrix runtime authority."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lottolab.application.strategy_matrix_structural import StrategyMatrixStructuralDataset
from lottolab.infrastructure.strategy_matrix_structural_reader import (
    PackagedStrategyMatrixStructuralReader,
    StrategyMatrixStructuralProjectionError,
)
from lottolab.interfaces.api.app import create_app

PATH = "/api/v1/strategy-matrix/structural"


class _FailingReader:
    def read(self) -> StrategyMatrixStructuralDataset:
        raise StrategyMatrixStructuralProjectionError(
            "boom at /Users/someone/repo/secret/path.json with a Traceback"
        )


def client() -> TestClient:
    return TestClient(create_app())


def test_no_filters_returns_the_full_210_cell_grid() -> None:
    response = client().get(PATH)
    assert response.status_code == 200
    body = response.json()
    assert len(body["cells"]) == 210
    assert body["schema_id"] == "lottolab.strategy_matrix.structural"
    assert body["schema_version"] == "1.0.0"
    assert body["scope"] == "NATIVE_UNIFORM_WINNING_SPACE"
    assert body["supported_ticket_counts"] == [2, 3, 5, 10, 20]
    assert body["claim_boundary"] == {
        "historical_outcomes_used": False,
        "historical_success_rate_claimed": False,
        "ranking_score_claimed": False,
        "global_optimum_claimed": False,
        "cross_lottery_normalization": "NOT_PERFORMED",
    }


@pytest.mark.parametrize(
    ("params", "expected_count"),
    [
        ({"lottery": "BIG_LOTTO"}, 70),
        ({"lottery": "DAILY_539"}, 70),
        ({"lottery": "POWER_LOTTO_ZONE1"}, 70),
        ({"method_id": "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1"}, 15),
        ({"ticket_count": 2}, 42),
        ({"ticket_count": 20}, 42),
    ],
)
def test_each_single_filter_narrows_the_grid(
    params: dict[str, object], expected_count: int
) -> None:
    response = client().get(PATH, params=params)
    assert response.status_code == 200
    cells = response.json()["cells"]
    assert len(cells) == expected_count


def test_filter_intersection_returns_the_exact_k20_cell() -> None:
    response = client().get(
        PATH,
        params={
            "lottery": "BIG_LOTTO",
            "method_id": "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1",
            "ticket_count": 20,
        },
    )
    assert response.status_code == 200
    cells = response.json()["cells"]
    assert len(cells) == 1
    cell = cells[0]
    assert cell["measurement_status"] == "MEASURED"
    assert cell["value"] == {"numerator": "8249099", "denominator": "3495954"}
    assert cell["local_optimum_status"] == "COMPLETE_RADIUS_1_LOCAL_OPTIMUM"


def test_filtering_never_changes_the_projection_digest() -> None:
    full = client().get(PATH).json()
    filtered = client().get(PATH, params={"lottery": "DAILY_539"}).json()
    assert full["projection_sha256"] == filtered["projection_sha256"]
    assert full["authority"] == filtered["authority"]


def test_a_valid_method_on_an_unsupported_game_k_returns_typed_not_applicable() -> None:
    response = client().get(
        PATH,
        params={
            "lottery": "BIG_LOTTO",
            "method_id": "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
            "ticket_count": 2,
        },
    )
    assert response.status_code == 200
    cells = response.json()["cells"]
    assert len(cells) == 1
    assert cells[0]["measurement_status"] == "NOT_APPLICABLE"
    assert cells[0]["value"] is None
    assert cells[0]["unavailable_reason"]


@pytest.mark.parametrize(
    "params",
    [
        {"lottery": "NOT_A_REAL_LOTTERY"},
        {"method_id": "NOT_A_REAL_METHOD"},
        {"ticket_count": 7},
        {"lottery": ""},
        {"bogus_field": "1"},
    ],
)
def test_invalid_or_extra_query_values_are_rejected_with_422(params: dict[str, object]) -> None:
    response = client().get(PATH, params=params)
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_FAILED"


def test_authority_failure_returns_503_without_leaking_internal_detail() -> None:
    app = create_app(strategy_matrix_structural_reader_factory=_FailingReader)
    response = TestClient(app).get(PATH)
    assert response.status_code == 503
    body = response.json()
    assert body == {
        "error_code": "STRUCTURAL_MATRIX_AUTHORITY_UNAVAILABLE",
        "message": "Canonical structural Matrix authority is unavailable.",
    }
    assert "/Users/" not in response.text
    assert "Traceback" not in response.text


def test_operation_set_adds_exactly_one_approved_route() -> None:
    schema = create_app().openapi()
    operation = schema["paths"][PATH]
    assert set(operation.keys()) == {"get"}
    assert operation["get"]["operationId"] == "queryStrategyMatrixStructural"


def test_default_production_reader_serves_the_real_packaged_artifact() -> None:
    response = client().get(PATH)
    expected = PackagedStrategyMatrixStructuralReader().read()
    assert response.json()["projection_sha256"] == expected.projection_sha256
