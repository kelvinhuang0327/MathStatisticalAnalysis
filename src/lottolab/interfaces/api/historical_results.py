"""BLHQ R2: HTTP adapters for the read-only historical-results query API.

Queries only the already-committed historical-results projection (BLHQ-R1's
``SQLiteHistoricalResultRepository``/``historical_schema``). The
``/runs/{run_id}/replay`` path is a read-only projection view over already-
committed portfolios: it never consumes or modifies Replay's
``DrawHistoryReader`` and executes no strategy.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from enum import IntEnum
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from lottolab.application.historical_queries import (
    MAX_PAGE_LIMIT,
    MIN_PAGE_LIMIT,
    HistoricalDrawIdentity,
    HistoricalPortfolioRecord,
    HistoricalReplayPage,
    HistoricalResultsUnavailableError,
    HistoricalRunPage,
    HistoricalRunSummary,
    HistoricalStrategySummary,
    HistoricalStrategySummaryList,
    HistoricalTicketRecord,
)
from lottolab.application.ports import HistoricalResultQueryRepositoryFactory
from lottolab.application.use_cases.query_historical_results import (
    GetHistoricalPortfolio,
    ListHistoricalReplayPortfolios,
    ListHistoricalRuns,
    ListHistoricalStrategies,
)
from lottolab.interfaces.api.draw_data import ApiErrorResponse, ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_FROZEN_RESPONSE = ConfigDict(frozen=True)


class TicketCount(IntEnum):
    """The closed ticket_count set (10/15/20).

    A bare ``Literal[10, 15, 20]`` does not coerce a query string like
    "10" to the matching int literal and always 422s; ``IntEnum`` does
    coerce correctly and still round-trips as a plain int in responses.
    """

    TEN = 10
    FIFTEEN = 15
    TWENTY = 20


Limit = Annotated[int, Query(ge=MIN_PAGE_LIMIT, le=MAX_PAGE_LIMIT)]
Offset = Annotated[int, Query(ge=0)]
RunId = Annotated[str, Field(min_length=1, max_length=64)]
PortfolioId = Annotated[str, Field(min_length=1, max_length=64)]
StrategyIdFilter = Annotated[str, Query(min_length=1, max_length=200)]


class HistoricalRunView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    import_identity_sha256: str
    manifest_sha256: str
    contract_version: str
    source_kind: str
    source_repository: str
    source_commit_oid: str
    source_artifact_sha256: str
    dataset_identity: str
    dataset_sha256: str
    legacy_run_id: str | None
    lottery_type: str
    started_at: str
    completed_at: str

    @classmethod
    def from_summary(cls, summary: HistoricalRunSummary) -> HistoricalRunView:
        return cls(
            run_id=summary.run_id,
            import_identity_sha256=summary.import_identity_sha256,
            manifest_sha256=summary.manifest_sha256,
            contract_version=summary.contract_version,
            source_kind=summary.source_kind,
            source_repository=summary.source_repository,
            source_commit_oid=summary.source_commit_oid,
            source_artifact_sha256=summary.source_artifact_sha256,
            dataset_identity=summary.dataset_identity,
            dataset_sha256=summary.dataset_sha256,
            legacy_run_id=summary.legacy_run_id,
            lottery_type=summary.lottery_type,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
        )


class HistoricalRunPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    items: list[HistoricalRunView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: HistoricalRunPage) -> HistoricalRunPageResponse:
        return cls(
            items=[HistoricalRunView.from_summary(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class HistoricalStrategySummaryView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_snapshot_id: str
    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    identity_kind: str
    governance_status: str
    alias_of_strategy_id: str | None
    equivalence_group: str | None
    nested_prefix_supported: bool
    ticket_count: int
    evaluated_draws: int
    complete_portfolios: int
    m4plus_hit_count: int

    @classmethod
    def from_summary(cls, summary: HistoricalStrategySummary) -> HistoricalStrategySummaryView:
        return cls(
            strategy_snapshot_id=summary.strategy_snapshot_id,
            strategy_id=summary.strategy_id,
            effective_strategy_id=summary.effective_strategy_id,
            strategy_version=summary.strategy_version,
            replicate=summary.replicate,
            identity_kind=summary.identity_kind,
            governance_status=summary.governance_status,
            alias_of_strategy_id=summary.alias_of_strategy_id,
            equivalence_group=summary.equivalence_group,
            nested_prefix_supported=summary.nested_prefix_supported,
            ticket_count=summary.ticket_count,
            evaluated_draws=summary.evaluated_draws,
            complete_portfolios=summary.complete_portfolios,
            m4plus_hit_count=summary.m4plus_hit_count,
        )


class HistoricalStrategySummaryListResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    ticket_count: int
    items: list[HistoricalStrategySummaryView]

    @classmethod
    def from_list(
        cls, summaries: HistoricalStrategySummaryList
    ) -> HistoricalStrategySummaryListResponse:
        return cls(
            run_id=summaries.run_id,
            ticket_count=summaries.ticket_count,
            items=[HistoricalStrategySummaryView.from_summary(item) for item in summaries.items],
        )


class HistoricalDrawIdentityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    draw_number: str
    draw_date: str
    main_numbers: list[int]
    special_numbers: list[int]
    draw_sha256: str

    @classmethod
    def from_identity(cls, identity: HistoricalDrawIdentity) -> HistoricalDrawIdentityView:
        return cls(
            draw_number=identity.draw_number,
            draw_date=identity.draw_date,
            main_numbers=list(identity.main_numbers),
            special_numbers=list(identity.special_numbers),
            draw_sha256=identity.draw_sha256,
        )


class HistoricalTicketView(BaseModel):
    model_config = _FROZEN_RESPONSE

    portfolio_position: int
    main_numbers: list[int]
    special_numbers: list[int]
    main_hit_count: int
    special_hit: bool
    ticket_sha256: str
    legacy_row_id: str | None
    legacy_storage_bet_index: int | None

    @classmethod
    def from_record(cls, record: HistoricalTicketRecord) -> HistoricalTicketView:
        return cls(
            portfolio_position=record.portfolio_position,
            main_numbers=list(record.main_numbers),
            special_numbers=list(record.special_numbers),
            main_hit_count=record.main_hit_count,
            special_hit=record.special_hit,
            ticket_sha256=record.ticket_sha256,
            legacy_row_id=record.legacy_row_id,
            legacy_storage_bet_index=record.legacy_storage_bet_index,
        )


class HistoricalPortfolioView(BaseModel):
    model_config = _FROZEN_RESPONSE

    portfolio_id: str
    run_id: str
    strategy_snapshot_id: str
    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    constructor_identifier: str
    source_record_locator: str | None
    portfolio_sha256: str
    prefix10_sha256: str
    prefix15_sha256: str
    target_draw: HistoricalDrawIdentityView
    cutoff_draw: HistoricalDrawIdentityView
    requested_ticket_count: int
    m4plus: bool
    tickets: list[HistoricalTicketView]

    @classmethod
    def from_record(cls, record: HistoricalPortfolioRecord) -> HistoricalPortfolioView:
        return cls(
            portfolio_id=record.portfolio_id,
            run_id=record.run_id,
            strategy_snapshot_id=record.strategy_snapshot_id,
            strategy_id=record.strategy_id,
            effective_strategy_id=record.effective_strategy_id,
            strategy_version=record.strategy_version,
            replicate=record.replicate,
            constructor_identifier=record.constructor_identifier,
            source_record_locator=record.source_record_locator,
            portfolio_sha256=record.portfolio_sha256,
            prefix10_sha256=record.prefix10_sha256,
            prefix15_sha256=record.prefix15_sha256,
            target_draw=HistoricalDrawIdentityView.from_identity(record.target_draw),
            cutoff_draw=HistoricalDrawIdentityView.from_identity(record.cutoff_draw),
            requested_ticket_count=record.requested_ticket_count,
            m4plus=record.m4plus,
            tickets=[HistoricalTicketView.from_record(ticket) for ticket in record.tickets],
        )


class HistoricalReplayPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    strategy_id: str
    ticket_count: int
    items: list[HistoricalPortfolioView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: HistoricalReplayPage) -> HistoricalReplayPageResponse:
        return cls(
            run_id=page.run_id,
            strategy_id=page.strategy_id,
            ticket_count=page.ticket_count,
            items=[HistoricalPortfolioView.from_record(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


def create_historical_results_router(
    repository_factory: HistoricalResultQueryRepositoryFactory | None,
) -> APIRouter:
    """Always exposes the four routes; ``repository_factory=None`` -> 503 NOT_CONFIGURED."""

    router = APIRouter(prefix=API_PREFIX, tags=["historical-results"])
    list_runs_use_case = (
        ListHistoricalRuns(repository_factory) if repository_factory is not None else None
    )
    list_strategies_use_case = (
        ListHistoricalStrategies(repository_factory) if repository_factory is not None else None
    )
    list_replay_use_case = (
        ListHistoricalReplayPortfolios(repository_factory)
        if repository_factory is not None
        else None
    )
    get_portfolio_use_case = (
        GetHistoricalPortfolio(repository_factory) if repository_factory is not None else None
    )

    @router.get(
        "/historical-results/runs",
        response_model=HistoricalRunPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listHistoricalRuns",
    )
    def list_historical_runs(
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> HistoricalRunPageResponse | JSONResponse:
        if list_runs_use_case is None:
            return _not_configured_error()
        try:
            page = list_runs_use_case.execute(limit=limit, offset=offset)
        except HistoricalResultsUnavailableError:
            return _unavailable_error()
        return HistoricalRunPageResponse.from_page(page)

    @router.get(
        "/historical-results/runs/{run_id}/strategies",
        response_model=HistoricalStrategySummaryListResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listHistoricalRunStrategies",
    )
    def list_historical_run_strategies(
        run_id: RunId,
        ticket_count: TicketCount,
    ) -> HistoricalStrategySummaryListResponse | JSONResponse:
        if list_strategies_use_case is None:
            return _not_configured_error()
        try:
            summaries = list_strategies_use_case.execute(run_id, ticket_count=int(ticket_count))
        except HistoricalResultsUnavailableError:
            return _unavailable_error()
        if summaries is None:
            return _run_not_found()
        return HistoricalStrategySummaryListResponse.from_list(summaries)

    @router.get(
        "/historical-results/runs/{run_id}/replay",
        response_model=HistoricalReplayPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listHistoricalRunReplayPortfolios",
    )
    def list_historical_run_replay_portfolios(
        run_id: RunId,
        strategy_id: StrategyIdFilter,
        ticket_count: TicketCount,
        m4plus_only: bool = False,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> HistoricalReplayPageResponse | JSONResponse:
        if list_replay_use_case is None:
            return _not_configured_error()
        try:
            page = list_replay_use_case.execute(
                run_id,
                strategy_id=strategy_id,
                ticket_count=int(ticket_count),
                m4plus_only=m4plus_only,
                limit=limit,
                offset=offset,
            )
        except HistoricalResultsUnavailableError:
            return _unavailable_error()
        if page is None:
            return _run_not_found()
        return HistoricalReplayPageResponse.from_page(page)

    @router.get(
        "/historical-results/portfolios/{portfolio_id}",
        response_model=HistoricalPortfolioView,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getHistoricalPortfolio",
    )
    def get_historical_portfolio(
        portfolio_id: PortfolioId,
        ticket_count: TicketCount,
    ) -> HistoricalPortfolioView | JSONResponse:
        if get_portfolio_use_case is None:
            return _not_configured_error()
        try:
            record = get_portfolio_use_case.execute(portfolio_id, ticket_count=int(ticket_count))
        except HistoricalResultsUnavailableError:
            return _unavailable_error()
        if record is None:
            return _json_response(
                404,
                ApiErrorResponse(
                    error_code="HISTORICAL_PORTFOLIO_NOT_FOUND",
                    message="Historical portfolio was not found.",
                ),
            )
        return HistoricalPortfolioView.from_record(record)

    return router


def _run_not_found() -> JSONResponse:
    return _json_response(
        404,
        ApiErrorResponse(
            error_code="HISTORICAL_RUN_NOT_FOUND", message="Historical run was not found."
        ),
    )


def _not_configured_error() -> JSONResponse:
    return _json_response(
        503,
        ApiErrorResponse(
            error_code="HISTORICAL_RESULTS_NOT_CONFIGURED",
            message="Historical results storage is not configured.",
        ),
    )


def _unavailable_error() -> JSONResponse:
    return _json_response(
        503,
        ApiErrorResponse(
            error_code="HISTORICAL_RESULTS_UNAVAILABLE",
            message="Historical results storage is unavailable.",
        ),
    )


def _json_response(status_code: int, model: BaseModel) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))
