"""Contract tests for the checksum-pinned B649 read-only API."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

import json
from dataclasses import replace
from importlib.resources import files

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.application.biglotto_multi_ticket_records import (
    B649_EXACT_NATIVE_TICKET_COUNTS,
    B649HistoryWindow,
    B649K5RecordDataset,
    B649K10RecordDataset,
    B649MultiTicketRecord,
    B649MultiTicketRecordDataset,
    B649OfficialPrizeCounts,
    B649SuccessCriterion,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    K5_PROJECTION_RESOURCE_NAME,
    K10_PROJECTION_RESOURCE_NAME,
    B649ExactNativeRecordProjectionError,
    PackagedB649K5RecordReader,
    PackagedB649K10RecordReader,
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

    # Disallowed ticket_count (20 remains legacy prefix only)
    res_20 = client.get(
        EXACT_NATIVE_PATH,
        params={"ticket_count": 20, "window": "RECENT_300"},
    )
    assert res_20.status_code == 422

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


@pytest.mark.parametrize("window", list(B649HistoryWindow))
def test_k10_formal_app_preserves_every_packaged_field_and_source_order(
    window: B649HistoryWindow,
) -> None:
    client = TestClient(create_app())
    response = client.get(EXACT_NATIVE_PATH, params={"ticket_count": 10, "window": window.value})
    assert response.status_code == 200
    payload = response.json()
    raw = json.loads(
        files("lottolab.strategies.data").joinpath(K10_PROJECTION_RESOURCE_NAME).read_bytes()
    )
    assert payload["items"] == [r for r in raw["records"] if r["window"] == window.value]
    assert payload["total"] == 2
    assert set(payload) == {
        "items",
        "total",
        "limit",
        "offset",
        "ticket_count",
        "window",
        "criterion",
        "research_disclaimer",
    }
    assert [r["official_rank"] for r in payload["items"]] == [1, 2]
    assert [r["source_order"] for r in payload["items"]] == [1, 2]
    leader = payload["items"][0]["strategy_id"]
    assert ("10bet_biglotto" in leader) == (window is B649HistoryWindow.FULL)
    params = {"ticket_count": 10, "window": window.value, "limit": 1, "offset": 1}
    assert client.get(EXACT_NATIVE_PATH, params=params).json()["items"] == payload["items"][1:]
    params.update(offset=0, q=payload["items"][0]["strategy_id"])
    assert client.get(EXACT_NATIVE_PATH, params=params).json()["items"] == payload["items"][:1]
    params.update(q="no-such-strategy")
    empty = client.get(EXACT_NATIVE_PATH, params=params)
    assert empty.status_code == 200 and empty.json()["total"] == 0 and empty.json()["items"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"ticket_count": 20},
        {"window": "bad"},
        {"sort": "rate"},
        {"cutoff": "115000084"},
        {"replay": True},
        {"limit": 0},
        {"offset": -1},
    ],
)
def test_k10_invalid_queries_are_422(params: dict[str, object]) -> None:
    response = TestClient(create_app()).get(
        EXACT_NATIVE_PATH, params={"ticket_count": 10, "window": "FULL", **params}
    )
    assert response.status_code == 422


def test_k10_null_zero_and_unavailable_are_200_without_synthetic_rank() -> None:
    dataset = PackagedB649K10RecordReader().read(B649HistoryWindow.FULL)
    zero = replace(
        dataset.records[0],
        rank=None,
        official_rank=None,
        unranked_reason="PRODUCER_UNRANKED",
        official_any_prize_numerator=0,
        official_any_prize_rate="0.000000000000000000",
    )
    unavailable = replace(
        dataset.records[1],
        rank=None,
        official_rank=None,
        metric_status="UNAVAILABLE",
        unranked_reason="PRODUCER_UNAVAILABLE",
        unavailable_reason="FAILED_METRIC",
        official_any_prize_rate=None,
        official_random_baseline=None,
        baseline_delta=None,
        coverage=None,
        official_any_prize_numerator=None,
        official_any_prize_denominator=None,
        best_prize_counts=None,
    )

    class Reader:
        def read(self, window: B649HistoryWindow | None = None) -> B649K10RecordDataset:
            return replace(dataset, records=(zero, unavailable))

    response = TestClient(create_app(b649_k10_record_reader_factory=Reader)).get(
        EXACT_NATIVE_PATH, params={"ticket_count": 10, "window": "FULL"}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["official_any_prize_numerator"] == 0
    assert items[0]["official_any_prize_rate"] == "0.000000000000000000"
    assert items[0]["official_rank"] is None and items[0]["source_order"] == 1
    assert items[1]["official_any_prize_rate"] is None
    assert items[1]["unavailable_reason"] == "FAILED_METRIC"


def test_k10_and_k2_k3_availability_are_independent() -> None:
    def broken_factory() -> PackagedB649K10RecordReader:
        raise B649ExactNativeRecordProjectionError("selected projection invalid")

    client = TestClient(create_app(b649_k10_record_reader_factory=broken_factory))
    assert (
        client.get(EXACT_NATIVE_PATH, params={"ticket_count": 10, "window": "FULL"}).status_code
        == 503
    )
    assert (
        client.get(EXACT_NATIVE_PATH, params={"ticket_count": 2, "window": "FULL"}).status_code
        == 200
    )

    app = FastAPI()
    app.include_router(
        create_b649_multi_ticket_records_router(
            load_full_strategy_catalog(),
            None,
            exact_native_reader_factory=None,
            k10_reader_factory=PackagedB649K10RecordReader,
        )
    )
    independent = TestClient(app)
    assert (
        independent.get(EXACT_NATIVE_PATH, params={"ticket_count": 2, "window": "FULL"}).status_code
        == 503
    )
    assert (
        independent.get(
            EXACT_NATIVE_PATH, params={"ticket_count": 10, "window": "FULL"}
        ).status_code
        == 200
    )
    assert independent.post(EXACT_NATIVE_PATH).status_code == 405


@pytest.mark.parametrize("ticket_count", [2, 3])
@pytest.mark.parametrize("window", list(B649HistoryWindow))
def test_v3_universe_all_windows_order_pagination_and_null_rank(
    ticket_count: int, window: B649HistoryWindow
) -> None:
    assert B649_EXACT_NATIVE_TICKET_COUNTS == (2, 3)
    client = TestClient(create_app())
    items: list[dict[str, object]] = []
    for offset in (0, 100, 200):
        page = client.get(
            EXACT_NATIVE_PATH,
            params={
                "ticket_count": ticket_count,
                "window": window.value,
                "limit": 100,
                "offset": offset,
            },
        ).json()
        assert page["total"] == 221
        items.extend(page["items"])
    assert len(items) == 221
    assert [r["strategy_id"] for r in items] == sorted(str(r["strategy_id"]) for r in items)
    assert all(r["official_rank"] is None and "source_order" not in r for r in items)


@pytest.mark.parametrize("window", list(B649HistoryWindow))
def test_k5_api_preserves_complete_publication_and_filtered_ties(window: B649HistoryWindow) -> None:
    client = TestClient(create_app())
    params: dict[str, object] = {"ticket_count": 5, "window": window.value}
    response = client.get(EXACT_NATIVE_PATH, params=params)
    assert response.status_code == 200
    page = response.json()
    document = json.loads(
        files("lottolab.strategies.data").joinpath(K5_PROJECTION_RESOURCE_NAME).read_bytes()
    )
    expected = [r for r in document["records"] if r["window"] == window.value]
    assert page["items"] == expected
    assert page["total"] == 5 and page["ticket_count"] == 5
    assert page["projection_sha256"] == document["projection_sha256"]
    assert page["provenance"] == document["provenance"]
    assert page["window_boundary"] == expected[0]["window_boundary"]
    assert page["ties"] == document["ties_by_window"][window.value]
    assert page["criterion"] == "OFFICIAL_ANY_PRIZE"
    for offset in range(5):
        filtered = client.get(
            EXACT_NATIVE_PATH, params={**params, "limit": 1, "offset": offset}
        ).json()
        assert filtered["items"] == expected[offset : offset + 1]
        assert filtered["ties"] == page["ties"]
    composite = next(r for r in expected if r["strategy_id"].startswith("legacy_composite__"))
    assert composite["reproduction_status"] is composite["method_family"] is None
    result = client.get(
        EXACT_NATIVE_PATH, params={**params, "q": composite["strategy_id"].upper()}
    ).json()
    assert result["items"] == [composite] and result["ties"] == page["ties"]
    enriched = next(r for r in expected if r["method_family"] is not None)
    for key in ("method_family", "reproduction_status"):
        result = client.get(EXACT_NATIVE_PATH, params={**params, key: enriched[key]}).json()
        assert result["items"] == [r for r in expected if r[key] == enriched[key]]
        assert composite not in result["items"]
    for key in ("legacy_method_id", "source_path"):
        result = client.get(EXACT_NATIVE_PATH, params={**params, "q": enriched[key].upper()}).json()
        assert result["items"] == [
            r
            for r in expected
            if enriched[key].casefold()
            in " ".join(
                r[k] or "" for k in ("strategy_id", "legacy_method_id", "source_path")
            ).casefold()
        ]
    for filters in ({"q": "unknown"}, {"method_family": "no-such-method-family"}, {"offset": 5}):
        empty = client.get(EXACT_NATIVE_PATH, params={**params, **filters})
        assert empty.status_code == 200 and empty.json()["items"] == []
        assert empty.json()["ties"] == page["ties"]


@pytest.mark.parametrize(
    "params",
    [
        {"ticket_count": 4},
        {"window": "bad"},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"criterion": "M3_PLUS"},
        {"prefix_count": 5},
        {"q": ""},
        {"method_family": ""},
        {"reproduction_status": "AVAILABLE"},
        {"sort": "rank"},
    ],
)
def test_k5_invalid_query_is_422(params: dict[str, object]) -> None:
    response = TestClient(create_app()).get(
        EXACT_NATIVE_PATH, params={"ticket_count": 5, "window": "FULL", **params}
    )
    assert response.status_code == 422


def test_k5_availability_is_independent_in_both_directions() -> None:
    def broken() -> PackagedB649K5RecordReader:
        raise B649ExactNativeRecordProjectionError("invalid packaged K5")

    client = TestClient(create_app(b649_k5_record_reader_factory=broken))
    assert (
        client.get(EXACT_NATIVE_PATH, params={"ticket_count": 5, "window": "FULL"}).status_code
        == 503
    )
    for k in (2, 3, 10):
        assert (
            client.get(EXACT_NATIVE_PATH, params={"ticket_count": k, "window": "FULL"}).status_code
            == 200
        )
    assert (
        client.get(
            PATH, params={"prefix_count": 20, "window": "FULL", "criterion": "M3_PLUS"}
        ).status_code
        == 200
    )
    app = FastAPI()
    app.include_router(
        create_b649_multi_ticket_records_router(
            load_full_strategy_catalog(), None, k5_reader_factory=PackagedB649K5RecordReader
        )
    )
    isolated = TestClient(app)
    assert (
        isolated.get(EXACT_NATIVE_PATH, params={"ticket_count": 5, "window": "FULL"}).status_code
        == 200
    )
    for k in (2, 3, 10):
        assert (
            isolated.get(
                EXACT_NATIVE_PATH, params={"ticket_count": k, "window": "FULL"}
            ).status_code
            == 503
        )
    assert (
        isolated.get(
            PATH, params={"prefix_count": 20, "window": "FULL", "criterion": "M3_PLUS"}
        ).status_code
        == 503
    )


def test_k5_valid_unavailable_row_and_zero_are_200() -> None:
    dataset = PackagedB649K5RecordReader().read(B649HistoryWindow.FULL)
    zero = replace(
        dataset.records[0],
        official_any_prize_numerator=0,
        official_any_prize_rate="0.000000000000000000",
    )
    unavailable = replace(
        dataset.records[1],
        rank=None,
        official_rank=None,
        metric_status="UNAVAILABLE",
        metric_unavailable_reason="EXECUTION_FAILURE",
        official_any_prize_rate=None,
        official_random_baseline=None,
        baseline_delta=None,
        coverage=None,
        official_any_prize_numerator=None,
        official_any_prize_denominator=None,
        best_prize_counts=None,
    )

    class Reader:
        def read(self, window: B649HistoryWindow | None = None) -> B649K5RecordDataset:
            return replace(dataset, records=(zero, unavailable))

    response = TestClient(create_app(b649_k5_record_reader_factory=Reader)).get(
        EXACT_NATIVE_PATH, params={"ticket_count": 5, "window": "FULL"}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["official_any_prize_rate"] == "0.000000000000000000"
    assert items[0]["official_any_prize_numerator"] == 0
    assert items[0]["typed_replay_failures_count"] == 500
    assert items[1]["official_any_prize_rate"] is None
    assert items[1]["metric_unavailable_reason"] == "EXECUTION_FAILURE"


@pytest.mark.parametrize("failure", ["missing", "invalid"])
def test_k5_packaged_resource_failure_is_503(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    from pathlib import Path

    import lottolab.infrastructure.biglotto_multi_ticket_record_reader as reader

    read = Path.read_bytes

    def fail(path: Path) -> bytes:
        if path.name == K5_PROJECTION_RESOURCE_NAME:
            if failure == "missing":
                raise FileNotFoundError(path)
            return b"{}"
        return read(path)

    reader._read_packaged_k5_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(Path, "read_bytes", fail)
    response = TestClient(create_app()).get(
        EXACT_NATIVE_PATH, params={"ticket_count": 5, "window": "FULL"}
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "B649_EXACT_NATIVE_RECORDS_UNAVAILABLE"
    reader._read_packaged_k5_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]
