"""Contract tests for the checksum-pinned B649 read-only API."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.application.biglotto_multi_ticket_records import (
    B649HistoryWindow,
    B649MultiTicketRecord,
    B649MultiTicketRecordDataset,
    B649OfficialPrizeCounts,
    B649SuccessCriterion,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.b649_multi_ticket_records import (
    create_b649_multi_ticket_records_router,
)

PATH = "/api/v1/b649-multi-ticket-records"
SUMMARY_PATH = f"{PATH}/summary"
DISCLAIMER = (
    "歷史成功率、排名與隨機基準差異僅供描述性研究，"  # noqa: RUF001
    "不構成未來預測、推薦、上線決策或中獎保證。"
)


class _Reader:
    def __init__(self, dataset: B649MultiTicketRecordDataset) -> None:
        self._dataset = dataset

    def read(self) -> B649MultiTicketRecordDataset:
        return self._dataset


def _record(
    *,
    strategy_id: str,
    legacy_method_id: str,
    source_path: str,
    method_family: str,
    status: ReproductionStatus,
) -> B649MultiTicketRecord:
    backtested = status is ReproductionStatus.BACKTESTED
    return B649MultiTicketRecord(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        legacy_method_id=legacy_method_id,
        source_path=source_path,
        method_family=method_family,
        reproduction_status=status,
        duplicate_alias_target=None,
        prefix_count=5,
        window=B649HistoryWindow.FULL,
        criterion=B649SuccessCriterion.M3_PLUS,
        rank=3 if backtested else None,
        official_rank=2 if backtested else None,
        official_any_prize_count=4 if backtested else None,
        official_any_prize_rate="0.400000000000000000" if backtested else None,
        official_random_baseline_probability=(
            "0.300000000000000000" if backtested else None
        ),
        official_random_baseline_delta=(
            "0.100000000000000000" if backtested else None
        ),
        unranked_reason=None if backtested else "FORMALLY_CLOSED",
        success_count=4 if backtested else None,
        effective_backtest_draw_count=10 if backtested else None,
        successful_execution_count=10 if backtested else None,
        historical_success_rate="0.400000000000000000" if backtested else None,
        random_baseline_success_rate=(
            "0.250000000000000000" if backtested else None
        ),
        random_baseline_rate_difference=(
            "0.150000000000000000" if backtested else None
        ),
        coverage="1.000000000000000000" if backtested else None,
        window_available_draws=10 if backtested else None,
        window_requested_draws=10 if backtested else None,
        window_complete=True if backtested else None,
        official_prize_counts=(
            B649OfficialPrizeCounts(
                first=0,
                second=0,
                third=0,
                fourth=1,
                fifth=1,
                sixth=1,
                seventh=1,
                general=2,
            )
            if backtested
            else None
        ),
        no_prize_count=44 if backtested else None,
        report_sha256="a" * 64 if backtested else None,
        report_file_sha256="b" * 64 if backtested else None,
        catalog_sha256="c" * 64,
        authority_mode="HISTORICAL_SEALED_EVIDENCE_V1" if backtested else None,
        metrics_unavailable_reason=None,
    )


def _dataset() -> B649MultiTicketRecordDataset:
    return B649MultiTicketRecordDataset(
        records=(
            _record(
                strategy_id="strategy_z",
                legacy_method_id="Legacy Z",
                source_path="legacy/z.py",
                method_family="family-z",
                status=ReproductionStatus.BACKTESTED,
            ),
            _record(
                strategy_id="strategy_a",
                legacy_method_id="Legacy A",
                source_path="legacy/a.py",
                method_family="family-a",
                status=ReproductionStatus.CLOSED_UNEXECUTABLE,
            ),
        ),
        catalog_sha256="c" * 64,
        projection_sha256="d" * 64,
        source_report_count=1,
        metrics_available_strategy_count=1,
        metrics_unavailable_strategy_count=0,
    )


def _client() -> TestClient:
    catalog = load_full_strategy_catalog()
    app = FastAPI()
    dataset = _dataset()
    app.include_router(
        create_b649_multi_ticket_records_router(
            catalog,
            lambda: _Reader(dataset),
        )
    )
    return TestClient(app)


def test_summary_exposes_exact_progress_and_closed_query_sets() -> None:
    response = _client().get(SUMMARY_PATH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["progress"] == {
        "total_strategy_count": 221,
        "reproduced_count": 135,
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "uncompleted_count": 0,
    }
    assert payload["prefix_counts"] == [5, 10, 15, 20]
    assert payload["windows"] == ["FULL", "RECENT_750", "RECENT_300", "RECENT_50"]
    assert payload["success_criteria"] == [
        "M3_PLUS",
        "M4_PLUS",
        "M5_PLUS",
        "M6",
        "M2_PLUS_SPECIAL",
        "M3_PLUS_SPECIAL",
        "M4_PLUS_SPECIAL",
        "M5_PLUS_SPECIAL",
    ]
    assert payload["reproduction_statuses"] == [
        "BACKTESTED",
        "CLOSED_UNEXECUTABLE",
        "DUPLICATE_ALIAS",
    ]
    assert payload["records_available"] is True
    assert payload["metrics_available_strategy_count"] == 1
    assert payload["metrics_unavailable_strategy_count"] == 0
    assert payload["primary_ranking_criterion"] == "OFFICIAL_ANY_PRIZE"
    assert payload["research_disclaimer"] == DISCLAIMER


def test_query_requires_all_three_explicit_research_selections() -> None:
    client = _client()
    assert client.get(PATH).status_code == 422
    assert client.get(PATH, params={"prefix_count": 5}).status_code == 422
    assert (
        client.get(
            PATH,
            params={"prefix_count": 5, "window": "FULL"},
        ).status_code
        == 422
    )


def test_query_filters_then_orders_by_strategy_id_not_rank() -> None:
    response = _client().get(
        PATH,
        params={
            "prefix_count": 5,
            "window": "FULL",
            "criterion": "M3_PLUS",
            "q": "legacy",
            "limit": 100,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [row["strategy_id"] for row in payload["items"]] == [
        "strategy_a",
        "strategy_z",
    ]
    assert payload["items"][0]["success_count"] is None
    assert payload["items"][0]["historical_success_rate"] is None
    assert payload["items"][0]["unranked_reason"] == "FORMALLY_CLOSED"
    assert payload["items"][1]["official_prize_counts"]["fourth"] == 1
    assert payload["items"][1]["official_rank"] == 2
    assert payload["items"][1]["official_any_prize_count"] == 4
    assert payload["items"][1]["official_any_prize_rate"] == (
        "0.400000000000000000"
    )
    assert payload["research_disclaimer"] == DISCLAIMER


def test_unavailable_projection_fails_closed_without_zero_filling() -> None:
    app = FastAPI()
    app.include_router(
        create_b649_multi_ticket_records_router(
            load_full_strategy_catalog(),
            None,
        )
    )
    client = TestClient(app)

    summary = client.get(SUMMARY_PATH)
    assert summary.status_code == 200
    assert summary.json()["records_available"] is False
    response = client.get(
        PATH,
        params={
            "prefix_count": 5,
            "window": "FULL",
            "criterion": "M3_PLUS",
        },
    )
    assert response.status_code == 503
    assert response.json() == {
        "error_code": "B649_MULTI_TICKET_RECORDS_UNAVAILABLE",
        "message": (
            "The checksum-pinned B649 aggregate record projection is unavailable."
        ),
    }


def test_openapi_exposes_read_only_get_operations_and_closed_enums() -> None:
    openapi = create_app().openapi()
    assert set(openapi["paths"][PATH]) == {"get"}
    assert set(openapi["paths"][SUMMARY_PATH]) == {"get"}
    assert openapi["paths"][PATH]["get"]["operationId"] == (
        "listB649MultiTicketRecords"
    )
    parameters = {
        parameter["name"]: parameter for parameter in openapi["paths"][PATH]["get"]["parameters"]
    }
    assert parameters["prefix_count"]["required"] is True
    assert parameters["window"]["required"] is True
    assert parameters["criterion"]["required"] is True


EXACT_NATIVE_PATH = "/api/v1/b649-exact-native-records"


def test_exact_native_records_api_live_k2_k3() -> None:
    client = TestClient(create_app())

    # K2 query under RECENT_300
    res_k2 = client.get(
        EXACT_NATIVE_PATH,
        params={"ticket_count": 2, "window": "RECENT_300", "limit": 100},
    )
    assert res_k2.status_code == 200
    payload_k2 = res_k2.json()
    assert payload_k2["total"] == 221
    assert payload_k2["ticket_count"] == 2
    assert payload_k2["window"] == "RECENT_300"
    assert payload_k2["criterion"] == "OFFICIAL_ANY_PRIZE"
    assert payload_k2["research_disclaimer"] == DISCLAIMER
    assert len(payload_k2["items"]) == 100

    # Check that ALL items have official_rank is None (strictly forbid rank fabrication)
    for item in payload_k2["items"]:
        assert item.get("official_rank") is None

    # Find an AVAILABLE K2 record
    avail_k2 = next(i for i in payload_k2["items"] if i["metric_status"] == "AVAILABLE")
    assert avail_k2["rankable"] is True
    assert avail_k2["unavailable_reason"] is None
    assert avail_k2["unranked_reason"] == "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
    assert avail_k2["official_any_prize_rate"] is not None
    assert len(avail_k2["official_any_prize_rate"].split(".")[1]) == 18
    assert avail_k2["official_random_baseline_delta"] is not None
    assert avail_k2["coverage"] is not None

    # Find an UNAVAILABLE K2 record
    unavail_k2 = next(i for i in payload_k2["items"] if i["metric_status"] == "UNAVAILABLE")
    assert unavail_k2["rankable"] is False
    assert unavail_k2["unavailable_reason"] is not None
    assert unavail_k2["official_any_prize_rate"] is None
    assert unavail_k2["official_random_baseline_delta"] is None

    # K3 query under FULL
    res_k3 = client.get(
        EXACT_NATIVE_PATH,
        params={"ticket_count": 3, "window": "FULL", "limit": 100},
    )
    assert res_k3.status_code == 200
    payload_k3 = res_k3.json()
    assert payload_k3["total"] == 221
    assert payload_k3["ticket_count"] == 3
    assert payload_k3["window"] == "FULL"
    for item in payload_k3["items"]:
        assert item.get("official_rank") is None


def test_exact_native_records_validation_errors() -> None:
    client = TestClient(create_app())

    # Disallowed ticket_count (5 is legacy prefix count, not exact native 2 or 3)
    res_5 = client.get(
        EXACT_NATIVE_PATH,
        params={"ticket_count": 5, "window": "RECENT_300"},
    )
    assert res_5.status_code == 422

    # Disallowed ticket_count (1)
    res_1 = client.get(
        EXACT_NATIVE_PATH,
        params={"ticket_count": 1, "window": "RECENT_300"},
    )
    assert res_1.status_code == 422

    # Disallowed window
    res_win = client.get(
        EXACT_NATIVE_PATH,
        params={"ticket_count": 2, "window": "INVALID_WINDOW"},
    )
    assert res_win.status_code == 422

    # Missing parameters
    res_missing = client.get(EXACT_NATIVE_PATH)
    assert res_missing.status_code == 422


def test_exact_native_records_unavailable_fails_closed() -> None:
    app = FastAPI()
    app.include_router(
        create_b649_multi_ticket_records_router(
            load_full_strategy_catalog(),
            None,
            exact_native_reader_factory=None,
        )
    )
    client = TestClient(app)
    res = client.get(
        EXACT_NATIVE_PATH,
        params={"ticket_count": 2, "window": "RECENT_300"},
    )
    assert res.status_code == 503
    assert res.json() == {
        "error_code": "B649_EXACT_NATIVE_RECORDS_UNAVAILABLE",
        "message": (
            "The checksum-pinned B649 exact-native record projection is unavailable."
        ),
    }


def test_exact_native_openapi_specification() -> None:
    openapi = create_app().openapi()
    assert set(openapi["paths"][EXACT_NATIVE_PATH]) == {"get"}
    assert openapi["paths"][EXACT_NATIVE_PATH]["get"]["operationId"] == (
        "listB649ExactNativeRecords"
    )
    parameters = {
        parameter["name"]: parameter
        for parameter in openapi["paths"][EXACT_NATIVE_PATH]["get"]["parameters"]
    }
    assert parameters["ticket_count"]["required"] is True
    assert parameters["window"]["required"] is True
