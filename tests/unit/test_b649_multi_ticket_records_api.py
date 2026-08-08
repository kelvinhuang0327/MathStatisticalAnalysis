"""Contract tests for the checksum-pinned B649 read-only API."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
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
