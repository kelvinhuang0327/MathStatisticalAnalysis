from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, cast

import httpx
import pytest
from fastapi.testclient import TestClient

from lottolab.infrastructure.b649_research_record_archive_reader import (
    B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV,
)
from lottolab.interfaces.api.app import create_app


class JsonTestClient(Protocol):
    def __enter__(self) -> JsonTestClient: ...

    def __exit__(self, *args: object) -> None: ...

    def get(self, url: str, **kwargs: object) -> httpx.Response: ...

ARCHIVE_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
    "NUMBER2_C_BACKTEST_RECOVERY_BUNDLE_20261102_R1"
)
BASE_PATH = "/api/v1/b649-research-backtests"
EXPECTED_COUNTS = {
    "NUMBER2_D_NATIVE_SUBSET_W50_K235_20261101_R1": 15_804,
    "NUMBER2_D_DECISION_OBJECTIVE_W50_1317_20261101_R1": 15_804,
    "NUMBER2_D_GROUP_DRO_CAUSAL_W50_20261101_R1": 19_755,
    "NUMBER2_D_SPECIAL_LAG_BUCKET_W50_K235_20261102_R1": 15_804,
    "NUMBER2_D_DRAW_ORDER_POSITION_SIGNAL_V1_20261102_R1": 15_804,
}


@pytest.fixture(scope="module")
def client() -> Iterator[JsonTestClient]:
    previous = os.environ.get(B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV)
    os.environ[B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV] = str(ARCHIVE_ROOT)
    try:
        with cast(JsonTestClient, TestClient(create_app())) as test_client:
            yield test_client
    finally:
        if previous is None:
            os.environ.pop(B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV, None)
        else:
            os.environ[B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV] = previous


def test_record_sources_returns_only_the_five_verified_formal_sources(
    client: JsonTestClient,
) -> None:
    response = client.get(f"{BASE_PATH}/record-sources")

    assert response.status_code == 200
    payload = response.json()
    assert [item["source_task_id"] for item in payload["items"]] == list(EXPECTED_COUNTS)
    assert {item["source_task_id"]: item["record_count"] for item in payload["items"]} == (
        EXPECTED_COUNTS
    )
    for item in payload["items"]:
        assert set(item) == {
            "source_task_id",
            "record_count",
            "research_class",
            "artifact_sha256",
            "availability_status",
        }
        assert item["research_class"] == "FORMAL_HISTORICAL_BACKTEST"
        assert item["availability_status"] == "AVAILABLE"
        assert len(item["artifact_sha256"]) == 64
    assert sum(item["record_count"] for item in payload["items"]) == 82_971
    assert "/Users/" not in response.text
    assert "monthly" not in response.text.lower()


def test_records_preserve_source_fields_filter_and_return_deterministic_json(
    client: JsonTestClient,
) -> None:
    native = "NUMBER2_D_NATIVE_SUBSET_W50_K235_20261101_R1"
    params = {
        "source_task_id": native,
        "target_draw": "103000101",
        "arm": "WEIGHTED_DIVERSE",
        "K": 2,
        "limit": 1,
        "offset": 0,
    }
    first = client.get(f"{BASE_PATH}/records", params=params)
    repeated = client.get(f"{BASE_PATH}/records", params=params)

    assert first.status_code == repeated.status_code == 200
    assert first.content == repeated.content
    payload = first.json()
    assert payload["total"] == 1
    assert payload["items"] == [
        {
            "source_task_id": native,
            "source_record_identity": f"{native}:record:000001",
            "target_draw": "103000101",
            "arm_or_method_identity": "WEIGHTED_DIVERSE@NATIVE_WEIGHTED_SUBSET_W50_V1",
            "K": 2,
            "predicted_tickets": [[9, 23, 28, 32, 36, 48], [14, 20, 21, 27, 32, 45]],
            "actual_main_numbers": [11, 18, 30, 34, 37, 47],
            "actual_special_number": 17,
            "official_prize_result": {
                "ticket_prize_tiers": ["NO_PRIZE", "NO_PRIZE"],
                "ticket_special_hits": [False, False],
            },
            "any_official_prize": False,
            "execution_status": "SUCCESS",
            "original_source_sha256": payload["items"][0]["original_source_sha256"],
            "null_reasons": {},
        }
    ]
    assert "/Users/" not in first.text
    assert "/.task-data/" not in first.text

    decision = client.get(
        f"{BASE_PATH}/records",
        params={
            "source_task_id": "NUMBER2_D_DECISION_OBJECTIVE_W50_1317_20261101_R1",
            "target_draw": "103000101",
            "arm": "OFFICIAL_REWARD_SELECTOR",
            "K": 2,
            "limit": 1,
        },
    ).json()["items"][0]
    assert decision["official_prize_result"] == {
        "ticket_results": [
            {"main_hits": 1, "special_hit": False, "tier": "NO_PRIZE"},
            {"main_hits": 0, "special_hit": False, "tier": "NO_PRIZE"},
        ]
    }
    assert decision["execution_status"] is None
    assert "execution_status" in decision["null_reasons"]

    special = client.get(
        f"{BASE_PATH}/records",
        params={
            "source_task_id": "NUMBER2_D_SPECIAL_LAG_BUCKET_W50_K235_20261102_R1",
            "target_draw": "103000101",
            "arm": "SPECIAL_LAG_BUCKET_W50",
            "K": 2,
            "limit": 1,
        },
    ).json()["items"][0]
    assert special["any_official_prize"] is None
    assert "any_official_prize" in special["null_reasons"]


def test_filters_pagination_and_errors_are_explicit(client: JsonTestClient) -> None:
    source_task_id = "NUMBER2_D_DRAW_ORDER_POSITION_SIGNAL_V1_20261102_R1"
    filtered = client.get(
        f"{BASE_PATH}/records",
        params={
            "source_task_id": source_task_id,
            "target_draw": "103000101",
            "arm": "ORDER_POSITION_W50",
            "K": 3,
            "limit": 1,
            "offset": 0,
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["K"] == 3

    next_page = client.get(
        f"{BASE_PATH}/records",
        params={"source_task_id": source_task_id, "limit": 2, "offset": 2},
    )
    assert next_page.status_code == 200
    assert [item["source_record_identity"] for item in next_page.json()["items"]] == [
        f"{source_task_id}:record:000003",
        f"{source_task_id}:record:000004",
    ]

    unknown = client.get(f"{BASE_PATH}/records", params={"source_task_id": "unknown-source"})
    assert unknown.status_code == 404
    assert unknown.json()["error_code"] == "B649_RESEARCH_BACKTEST_SOURCE_NOT_FOUND"

    invalid_queries = (
        {"source_task_id": source_task_id, "K": 4},
        {"source_task_id": source_task_id, "limit": 0},
        {"source_task_id": source_task_id, "limit": 101},
        {"source_task_id": source_task_id, "offset": -1},
        {"source_task_id": "../private/file"},
        {"source_task_id": source_task_id, "arm": "../../private/file"},
        {"source_task_id": source_task_id, "member": "../../private/file"},
    )
    for params in invalid_queries:
        response = client.get(f"{BASE_PATH}/records", params=params)
        assert response.status_code == 422
        assert "/Users/" not in response.text
        assert "private/file" not in response.text

    missing_source = client.get(f"{BASE_PATH}/records")
    assert missing_source.status_code == 422


def test_full_http_pagination_has_no_missing_or_duplicate_source_rows(
    client: JsonTestClient,
) -> None:
    for source_task_id, expected_count in EXPECTED_COUNTS.items():
        observed_identities: list[str] = []
        offset = 0
        while True:
            response = client.get(
                f"{BASE_PATH}/records",
                params={"source_task_id": source_task_id, "limit": 100, "offset": offset},
            )
            assert response.status_code == 200
            page = response.json()
            assert page["total"] == expected_count
            observed_identities.extend(item["source_record_identity"] for item in page["items"])
            offset += len(page["items"])
            if len(page["items"]) < 100:
                break

        expected_identities = [
            f"{source_task_id}:record:{line_number:06d}"
            for line_number in range(1, expected_count + 1)
        ]
        assert observed_identities == expected_identities


def test_missing_or_checksum_invalid_archive_returns_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    invalid_root = tmp_path / "bad-archive"
    invalid_root.mkdir()
    (invalid_root / "archive_manifest.json").write_text("{}", encoding="utf-8")
    (invalid_root / "backtest_bundle.zip").write_bytes(b"not-a-zip")
    (invalid_root / "result.json").write_text("{}", encoding="utf-8")
    (invalid_root / "sha256sums.txt").write_text("", encoding="utf-8")
    monkeypatch.setenv(B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV, str(invalid_root))

    response = cast(JsonTestClient, TestClient(create_app())).get(
        f"{BASE_PATH}/record-sources"
    )

    assert response.status_code == 503
    assert response.json()["error_code"] == "B649_RESEARCH_BACKTEST_ARCHIVE_UNAVAILABLE"
    assert "/Users/" not in response.text
    assert str(invalid_root) not in response.text


def test_openapi_documents_both_read_only_routes_and_fixed_query_contract(
    client: JsonTestClient,
) -> None:
    document = client.get("/openapi.json").json()
    paths = document["paths"]
    assert paths[f"{BASE_PATH}/record-sources"]["get"]["operationId"] == (
        "listB649ResearchBacktestRecordSources"
    )
    records = paths[f"{BASE_PATH}/records"]["get"]
    assert records["operationId"] == "listB649ResearchBacktestRecords"
    parameters = {item["name"]: item for item in records["parameters"]}
    assert parameters["source_task_id"]["required"] is True
    for optional in ("target_draw", "arm", "K", "limit", "offset"):
        assert parameters[optional]["required"] is False
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 100
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert {"200", "404", "422", "503"}.issubset(records["responses"])
