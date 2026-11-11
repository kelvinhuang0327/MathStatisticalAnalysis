from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lottolab.infrastructure.b649_research_board_v2_reader import (
    B649_RESEARCH_BOARD_V2_ROOT_ENV,
)
from lottolab.interfaces.api.app import create_app

V2_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
    "NUMBER2_D_LMS_HUMAN_BOARD_V2_INTEGRATION_20261102_R1"
)
BASE_PATH = "/api/v1/b649-research-backtests"
RANK_QUERY = {
    "cohort": "D2_STANDARD_1317_TARGETS_103000101_115000069",
    "K": 5,
    "window": "FULL",
    "prize_metric": "OFFICIAL_ANY_PRIZE",
}
TIED_GROUP = {
    "target_draw_set_identity": (
        "COHORTSET:c8daf1b3c2a1b951aa3edec8731a2e69d44d8b9e6fd7110109ab91b6cdfecae1"
    ),
    "eligible_draws": 2148,
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(B649_RESEARCH_BOARD_V2_ROOT_ENV, str(V2_ROOT))
    return TestClient(create_app())


def test_summary_returns_verified_source_identity_and_counts(client: TestClient) -> None:
    response = client.get(f"{BASE_PATH}/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_task_id"] == "NUMBER2_D_LMS_HUMAN_BOARD_V2_INTEGRATION_20261102_R1"
    assert payload["source_authority_commit"] == "fe3aa81d3844ac11d4360447c243e90fe4a6613a"
    assert payload["observed_checkout_head"] == "b4e11ebd0981d549ce70055e70f8fbd0065cd2dd"
    assert payload["method_version_count"] == 305
    assert payload["inventory_count"] == 2968
    assert payload["ranking_count"] == 2818
    assert payload["unavailable_count"] == 60
    assert payload["not_applicable_count"] == 90
    assert payload["comparable_group_count"] == 224
    assert payload["comparison_group_count"] == 504
    assert payload["duplicate_output_groups"] == 48
    assert payload["windows"] == ["FULL", "RECENT_750", "RECENT_300", "RECENT_50"]
    assert payload["K_values"] == [2, 3, 5, 10, 15, 20]
    assert payload["prize_metrics"] == ["OFFICIAL_ANY_PRIZE"]
    assert payload["source_manifest_sha256"]
    assert "/Users/" not in response.text


def test_methods_pagination_statuses_manual_fields_and_safe_source_locators(
    client: TestClient,
) -> None:
    first = client.get(f"{BASE_PATH}/methods", params={"limit": 2, "offset": 0})
    second = client.get(f"{BASE_PATH}/methods", params={"limit": 2, "offset": 2})

    assert first.status_code == second.status_code == 200
    first_page = first.json()
    second_page = second.json()
    assert first_page["total"] == second_page["total"] == 2968
    assert len(first_page["items"]) == len(second_page["items"]) == 2
    first_ids = {item["method_id"] for item in first_page["items"]}
    second_ids = {item["method_id"] for item in second_page["items"]}
    assert first_ids.isdisjoint(second_ids)

    for item in first_page["items"]:
        assert item["method_version"]
        assert item["research_status"]
        assert item["source_identity"]
        assert item["source_lineage"]
        assert item["owner_long_rank"] == ""
        assert item["owner_middle_rank"] == ""
        assert item["owner_short_rank"] == ""
        assert item["owner_selected"] == ""
        assert item["owner_reason"] == ""
    assert "/Users/" not in first.text

    unavailable_response = client.get(
        f"{BASE_PATH}/methods",
        params={"method_id": "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d"},
    )
    unavailable = next(
        item
        for item in unavailable_response.json()["items"]
        if item["metrics_availability"] == "UNAVAILABLE"
    )
    assert unavailable["eligible_draws"] is None
    assert unavailable["successful_draws"] is None
    assert unavailable["wins"] is None
    assert unavailable["success_rate"] is None
    assert unavailable["metrics_unavailable_reason"] == "NO_SUCCESSFUL_EXECUTIONS_IN_WINDOW"

    not_applicable_response = client.get(
        f"{BASE_PATH}/methods",
        params={"method_id": "legacy_biglotto__advanced_bayesian_analyzer__8ad90229f37a"},
    )
    not_applicable = not_applicable_response.json()["items"][0]
    assert not_applicable["metrics_availability"] == "NOT_APPLICABLE"
    assert not_applicable["eligible_draws"] is None
    assert not_applicable["success_rate"] is None


def test_rankings_require_and_isolate_all_comparison_axes(client: TestClient) -> None:
    for window in ("FULL", "RECENT_750", "RECENT_300", "RECENT_50"):
        response = client.get(f"{BASE_PATH}/rankings", params={**RANK_QUERY, "window": window})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] > 0
        assert all(
            row["evaluation_cohort"] == RANK_QUERY["cohort"]
            and row["K"] == 5
            and row["window"] == window
            and row["prize_metric"] == RANK_QUERY["prize_metric"]
            for row in payload["items"]
        )

    alternate_k = client.get(f"{BASE_PATH}/rankings", params={**RANK_QUERY, "K": 2})
    legacy_cohort = (
        "LEGACY:FRESH_CURRENT_CATALOG_REPRODUCTION_V1:"
        "b62a7b71a0c445a1c3532a72aade92b63824bd483aa5d97e4bf6dd32f7f6752e"
    )
    alternate_cohort = client.get(
        f"{BASE_PATH}/rankings",
        params={**RANK_QUERY, "cohort": legacy_cohort},
    )
    assert alternate_k.status_code == alternate_cohort.status_code == 200
    assert all(row["K"] == 2 for row in alternate_k.json()["items"])
    assert all(
        row["evaluation_cohort"].startswith("LEGACY:") for row in alternate_cohort.json()["items"]
    )
    assert client.get(f"{BASE_PATH}/rankings", params={**RANK_QUERY, "K": 1}).status_code == 422
    assert (
        client.get(
            f"{BASE_PATH}/rankings", params={**RANK_QUERY, "cohort": "/etc/passwd"}
        ).status_code
        == 422
    )

    tied_response = client.get(
        f"{BASE_PATH}/rankings",
        params={**RANK_QUERY, "cohort": legacy_cohort, **TIED_GROUP, "limit": 100},
    )
    tied_payload = tied_response.json()
    assert tied_response.status_code == 200
    assert tied_payload["comparison_group_count"] == 1
    tied_rank_four = [row for row in tied_payload["items"] if row["comparison_rank"] == 4]
    assert len(tied_rank_four) == 2
    assert len({row["success_rate"] for row in tied_rank_four}) == 1

    tied_source = client.get(f"{BASE_PATH}/rankings", params={**RANK_QUERY, "limit": 100})
    tied_payload = tied_source.json()
    shared_output = next(
        row
        for row in tied_payload["items"]
        if row["comparison_status"] == "COMPARABLE;SHARED_OUTPUT_NOT_INDEPENDENT"
    )
    assert shared_output["method_id"]
    assert shared_output["method_version"]
    assert shared_output["shared_output_identity"]
    assert shared_output["source_identity"]
    assert shared_output["source_lineage"]

    replay_one = client.get(f"{BASE_PATH}/rankings", params={**RANK_QUERY, "limit": 10})
    replay_two = client.get(f"{BASE_PATH}/rankings", params={**RANK_QUERY, "limit": 10})
    assert replay_one.content == replay_two.content


def test_query_validation_rejects_incomplete_and_path_like_parameters(client: TestClient) -> None:
    assert client.get(f"{BASE_PATH}/rankings").status_code == 422
    assert (
        client.get(
            f"{BASE_PATH}/rankings",
            params={**RANK_QUERY, "window": "RECENT_999"},
        ).status_code
        == 422
    )
    unsafe = client.get(f"{BASE_PATH}/summary", params={"path": "/etc/passwd"})
    assert unsafe.status_code == 422
    assert unsafe.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert "/etc/passwd" not in unsafe.text
    assert client.get(f"{BASE_PATH}/methods", params={"limit": 101}).status_code == 422
    assert client.get(f"{BASE_PATH}/methods", params={"offset": 10_001}).status_code == 422
    assert (
        client.get(
            f"{BASE_PATH}/rankings",
            params={
                **RANK_QUERY,
                "target_draw_set_identity": TIED_GROUP["target_draw_set_identity"],
            },
        ).status_code
        == 422
    )


def test_missing_or_corrupt_source_returns_explicit_503(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(B649_RESEARCH_BOARD_V2_ROOT_ENV, raising=False)
    missing_client = TestClient(create_app())
    missing_requests = (
        ("summary", None),
        ("methods", None),
        ("rankings", RANK_QUERY),
    )
    for path, params in missing_requests:
        response = missing_client.get(f"{BASE_PATH}/{path}", params=params)
        assert response.status_code == 503
        assert response.json()["error_code"] == "B649_RESEARCH_BOARD_V2_NOT_CONFIGURED"
        assert "items" not in response.json()

    missing_source_root = tmp_path / "missing-source"
    missing_source_root.mkdir()
    monkeypatch.setenv(B649_RESEARCH_BOARD_V2_ROOT_ENV, str(missing_source_root))
    missing_source_client = TestClient(create_app())
    missing_source = missing_source_client.get(f"{BASE_PATH}/summary")
    assert missing_source.status_code == 503
    assert missing_source.json()["error_code"] == "B649_RESEARCH_BOARD_V2_UNAVAILABLE"

    corrupt_root = tmp_path / "corrupt-source"
    corrupt_root.mkdir()
    for filename in ("source_manifest.json", "result.json", "integration_summary.json"):
        shutil.copyfile(V2_ROOT / filename, corrupt_root / filename)
    with (corrupt_root / "integration_summary.json").open("ab") as stream:
        stream.write(b" ")
    monkeypatch.setenv(B649_RESEARCH_BOARD_V2_ROOT_ENV, str(corrupt_root))
    corrupt_client = TestClient(create_app())
    response = corrupt_client.get(f"{BASE_PATH}/summary")
    assert response.status_code == 503
    assert response.json()["error_code"] == "B649_RESEARCH_BOARD_V2_UNAVAILABLE"
    assert str(corrupt_root) not in response.text


def test_existing_b649_record_endpoints_still_serve_requests(client: TestClient) -> None:
    multi_ticket = client.get(
        "/api/v1/b649-multi-ticket-records",
        params={"prefix_count": 5, "window": "FULL", "criterion": "M3_PLUS"},
    )
    exact_native = client.get(
        "/api/v1/b649-exact-native-records",
        params={"ticket_count": 5, "window": "FULL"},
    )

    assert multi_ticket.status_code == 200
    assert exact_native.status_code == 200
    assert "items" in multi_ticket.json()
    assert "items" in exact_native.json()


def test_openapi_documents_new_routes_and_required_ranking_axes(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    paths = document["paths"]
    assert paths[f"{BASE_PATH}/summary"]["get"]["operationId"] == ("getB649ResearchBacktestSummary")
    assert paths[f"{BASE_PATH}/methods"]["get"]["operationId"] == (
        "listB649ResearchBacktestMethods"
    )
    ranking = paths[f"{BASE_PATH}/rankings"]["get"]
    assert ranking["operationId"] == "listB649ResearchBacktestRankings"
    parameters = {parameter["name"]: parameter for parameter in ranking["parameters"]}
    for required in ("cohort", "K", "window", "prize_metric"):
        assert parameters[required]["required"] is True
    assert parameters["window"]["schema"]["enum"] == [
        "FULL",
        "RECENT_750",
        "RECENT_300",
        "RECENT_50",
    ]
    assert ranking["responses"]["503"]["content"]["application/json"]["schema"]["$ref"]


def test_json_source_fields_are_structured_and_redacted(client: TestClient) -> None:
    response = client.get(f"{BASE_PATH}/methods", params={"limit": 100})

    assert response.status_code == 200
    payload = response.json()
    assert "/Users/" not in response.text
    assert "/.task-data/" not in response.text
    row = next(item for item in payload["items"] if item["source_inventory_json"])
    assert isinstance(row["source_inventory_json"], dict)
    assert isinstance(row["source_identity_chain"], list)
    assert row["artifact_locator"].startswith(("PROJECT/", "TASK_DATA/", "SOURCE/"))
    assert json.loads(json.dumps(row["source_inventory_json"])) == row["source_inventory_json"]
