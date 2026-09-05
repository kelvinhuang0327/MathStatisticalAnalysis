"""HTTP projection for checksum-pinned B649 multi-ticket history."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from enum import IntEnum
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from lottolab.application.biglotto_multi_ticket_records import (
    B649_HISTORY_WINDOWS,
    B649_PREFIX_COUNTS,
    B649_REPRODUCTION_STATUSES,
    B649_RESEARCH_DISCLAIMER_ZH_TW,
    B649_SUCCESS_CRITERIA,
    B649ExactNativeRecord,
    B649ExactNativeRecordQuery,
    B649HistoryWindow,
    B649MultiTicketRecord,
    B649MultiTicketRecordQuery,
    B649SuccessCriterion,
    query_b649_exact_native_records,
    query_b649_multi_ticket_records,
)
from lottolab.application.ports import (
    B649ExactNativeRecordReaderFactory,
    B649MultiTicketRecordReaderFactory,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalog,
    ReproductionStatus,
)
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX


class B649PrefixCount(IntEnum):
    FIVE = 5
    TEN = 10
    FIFTEEN = 15
    TWENTY = 20


class B649ExactNativeTicketCount(IntEnum):
    TWO = 2
    THREE = 3


B649ReproductionStatusFilter = Literal[
    "BACKTESTED",
    "CLOSED_UNEXECUTABLE",
    "DUPLICATE_ALIAS",
]


class B649ResearchProgressView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_strategy_count: int
    reproduced_count: int
    backtested_count: int
    closed_count: int
    duplicate_alias_count: int
    owner_decision_required_count: int
    uncompleted_count: int


class B649MultiTicketSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress: B649ResearchProgressView
    prefix_counts: list[int]
    windows: list[B649HistoryWindow]
    success_criteria: list[B649SuccessCriterion]
    method_families: list[str]
    reproduction_statuses: list[B649ReproductionStatusFilter]
    catalog_sha256: str
    records_available: bool
    projection_sha256: str | None
    source_report_count: int | None
    metrics_available_strategy_count: int | None
    metrics_unavailable_strategy_count: int | None
    primary_ranking_criterion: Literal["OFFICIAL_ANY_PRIZE"]
    research_disclaimer: str


class B649OfficialPrizeCountsView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    first: int
    second: int
    third: int
    fourth: int
    fifth: int
    sixth: int
    seventh: int
    general: int


class B649MultiTicketRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    strategy_id: str
    strategy_version: str
    legacy_method_id: str
    source_path: str
    method_family: str
    reproduction_status: B649ReproductionStatusFilter
    duplicate_alias_target: str | None
    prefix_count: int
    window: B649HistoryWindow
    criterion: B649SuccessCriterion
    rank: int | None
    official_rank: int | None
    official_any_prize_count: int | None
    official_any_prize_rate: str | None
    official_random_baseline_probability: str | None
    official_random_baseline_delta: str | None
    unranked_reason: str | None
    success_count: int | None
    effective_backtest_draw_count: int | None
    successful_execution_count: int | None
    historical_success_rate: str | None
    random_baseline_success_rate: str | None
    random_baseline_rate_difference: str | None
    coverage: str | None
    window_available_draws: int | None
    window_requested_draws: int | None
    window_complete: bool | None
    official_prize_counts: B649OfficialPrizeCountsView | None
    no_prize_count: int | None
    report_sha256: str | None
    report_file_sha256: str | None
    catalog_sha256: str
    authority_mode: str | None
    metrics_unavailable_reason: str | None


class B649MultiTicketRecordPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[B649MultiTicketRecordView]
    total: int
    limit: int
    offset: int
    prefix_count: int
    window: B649HistoryWindow
    criterion: B649SuccessCriterion
    research_disclaimer: str


class B649MultiTicketRecordQueryView(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prefix_count: B649PrefixCount
    window: B649HistoryWindow
    criterion: B649SuccessCriterion
    q: str | None = Field(default=None, min_length=1, max_length=200)
    method_family: str | None = Field(default=None, min_length=1, max_length=200)
    reproduction_status: B649ReproductionStatusFilter | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class B649MultiTicketApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str


class B649ExactNativeRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    strategy_id: str
    strategy_version: str
    legacy_method_id: str
    source_path: str
    method_family: str
    reproduction_status: B649ReproductionStatusFilter
    duplicate_alias_target: str | None
    ticket_count: int
    window: B649HistoryWindow
    criterion: Literal["OFFICIAL_ANY_PRIZE"]
    metric_status: Literal["AVAILABLE", "UNAVAILABLE"]
    rankable: bool
    unavailable_reason: str | None
    metrics_unavailable_reason: str | None
    unranked_reason: str | None
    official_any_prize_count: int | None
    official_any_prize_rate: str | None
    official_random_baseline_probability: str | None
    official_random_baseline_delta: str | None
    coverage: str | None
    official_prize_counts: B649OfficialPrizeCountsView | None
    no_prize_count: int | None
    available_observation_count: int | None
    effective_backtest_draw_count: int | None
    successful_observation_count: int | None
    window_available_draws: int | None
    window_requested_draws: int | None
    window_complete: bool | None
    native_ticket_count_classification: str | None
    authority_mode: str | None
    catalog_sha256: str
    official_rank: None = None


class B649ExactNativeRecordPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[B649ExactNativeRecordView]
    total: int
    limit: int
    offset: int
    ticket_count: int
    window: B649HistoryWindow
    criterion: Literal["OFFICIAL_ANY_PRIZE"]
    research_disclaimer: str


class B649ExactNativeRecordQueryView(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ticket_count: B649ExactNativeTicketCount
    window: B649HistoryWindow
    q: str | None = Field(default=None, min_length=1, max_length=200)
    method_family: str | None = Field(default=None, min_length=1, max_length=200)
    reproduction_status: B649ReproductionStatusFilter | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class B649ExactNativeApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str


def create_b649_multi_ticket_records_router(
    catalog: FullStrategyCatalog,
    reader_factory: B649MultiTicketRecordReaderFactory | None,
    exact_native_reader_factory: B649ExactNativeRecordReaderFactory | None = None,
) -> APIRouter:
    """Expose summary and exact-selection queries without eager artifact reads."""

    router = APIRouter(prefix=API_PREFIX, tags=["b649-multi-ticket-records"])

    @router.get(
        "/b649-multi-ticket-records/summary",
        response_model=B649MultiTicketSummaryResponse,
        operation_id="getB649MultiTicketRecordSummary",
    )
    def summary() -> B649MultiTicketSummaryResponse:
        projection_sha256: str | None = None
        source_report_count: int | None = None
        metrics_available_strategy_count: int | None = None
        metrics_unavailable_strategy_count: int | None = None
        records_available = False
        if reader_factory is not None:
            try:
                dataset = reader_factory().read()
            except Exception:
                pass
            else:
                records_available = True
                projection_sha256 = dataset.projection_sha256
                source_report_count = dataset.source_report_count
                metrics_available_strategy_count = (
                    dataset.metrics_available_strategy_count
                )
                metrics_unavailable_strategy_count = (
                    dataset.metrics_unavailable_strategy_count
                )
        progress = catalog.progress
        return B649MultiTicketSummaryResponse(
            progress=B649ResearchProgressView(**progress.canonical_dict()),
            prefix_counts=list(B649_PREFIX_COUNTS),
            windows=list(B649_HISTORY_WINDOWS),
            success_criteria=list(B649_SUCCESS_CRITERIA),
            method_families=sorted({row.method_family for row in catalog.records}),
            reproduction_statuses=[
                status.value for status in B649_REPRODUCTION_STATUSES
            ],
            catalog_sha256=catalog.catalog_sha256,
            records_available=records_available,
            projection_sha256=projection_sha256,
            source_report_count=source_report_count,
            metrics_available_strategy_count=metrics_available_strategy_count,
            metrics_unavailable_strategy_count=metrics_unavailable_strategy_count,
            primary_ranking_criterion="OFFICIAL_ANY_PRIZE",
            research_disclaimer=B649_RESEARCH_DISCLAIMER_ZH_TW,
        )

    @router.get(
        "/b649-multi-ticket-records",
        response_model=B649MultiTicketRecordPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": B649MultiTicketApiErrorResponse},
        },
        operation_id="listB649MultiTicketRecords",
    )
    def records(
        query: Annotated[B649MultiTicketRecordQueryView, Query()],
    ) -> B649MultiTicketRecordPageResponse | JSONResponse:
        if reader_factory is None:
            return _unavailable_response()
        try:
            dataset = reader_factory().read()
        except Exception:
            return _unavailable_response()
        application_query = B649MultiTicketRecordQuery(
            prefix_count=int(query.prefix_count),
            window=query.window,
            criterion=query.criterion,
            q=query.q,
            method_family=query.method_family,
            reproduction_status=(
                ReproductionStatus(query.reproduction_status)
                if query.reproduction_status is not None
                else None
            ),
            limit=query.limit,
            offset=query.offset,
        )
        page = query_b649_multi_ticket_records(dataset, application_query)
        return B649MultiTicketRecordPageResponse(
            items=[_record_view(row) for row in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
            prefix_count=int(query.prefix_count),
            window=query.window,
            criterion=query.criterion,
            research_disclaimer=B649_RESEARCH_DISCLAIMER_ZH_TW,
        )

    @router.get(
        "/b649-exact-native-records",
        response_model=B649ExactNativeRecordPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": B649ExactNativeApiErrorResponse},
        },
        operation_id="listB649ExactNativeRecords",
    )
    def exact_native_records(
        query: Annotated[B649ExactNativeRecordQueryView, Query()],
    ) -> B649ExactNativeRecordPageResponse | JSONResponse:
        if exact_native_reader_factory is None:
            return _exact_native_unavailable_response()
        try:
            dataset = exact_native_reader_factory().read()
        except Exception:
            return _exact_native_unavailable_response()
        application_query = B649ExactNativeRecordQuery(
            ticket_count=int(query.ticket_count),
            window=query.window,
            q=query.q,
            method_family=query.method_family,
            reproduction_status=(
                ReproductionStatus(query.reproduction_status)
                if query.reproduction_status is not None
                else None
            ),
            limit=query.limit,
            offset=query.offset,
        )
        page = query_b649_exact_native_records(dataset, application_query)
        return B649ExactNativeRecordPageResponse(
            items=[_exact_native_record_view(row) for row in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
            ticket_count=int(query.ticket_count),
            window=query.window,
            criterion="OFFICIAL_ANY_PRIZE",
            research_disclaimer=B649_RESEARCH_DISCLAIMER_ZH_TW,
        )

    return router


def _record_view(record: B649MultiTicketRecord) -> B649MultiTicketRecordView:
    return B649MultiTicketRecordView.model_validate(record, from_attributes=True)


def _exact_native_record_view(
    record: B649ExactNativeRecord,
) -> B649ExactNativeRecordView:
    return B649ExactNativeRecordView.model_validate(record, from_attributes=True)


def _unavailable_response() -> JSONResponse:
    response = B649MultiTicketApiErrorResponse(
        error_code="B649_MULTI_TICKET_RECORDS_UNAVAILABLE",
        message="The checksum-pinned B649 aggregate record projection is unavailable.",
    )
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))


def _exact_native_unavailable_response() -> JSONResponse:
    response = B649ExactNativeApiErrorResponse(
        error_code="B649_EXACT_NATIVE_RECORDS_UNAVAILABLE",
        message="The checksum-pinned B649 exact-native record projection is unavailable.",
    )
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))


__all__ = [
    "B649ExactNativeApiErrorResponse",
    "B649ExactNativeRecordPageResponse",
    "B649ExactNativeRecordView",
    "B649ExactNativeTicketCount",
    "B649MultiTicketApiErrorResponse",
    "B649MultiTicketRecordPageResponse",
    "B649MultiTicketRecordView",
    "B649MultiTicketSummaryResponse",
    "create_b649_multi_ticket_records_router",
]
