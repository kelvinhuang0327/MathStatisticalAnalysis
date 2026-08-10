"""FastAPI adapters for the sealed T539 Strategy Analysis vertical."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.ports import T539HistoricalQueryRepositoryFactory
from lottolab.application.t539_historical import (
    T539CoverageBlockedEntry,
    T539CoverageExecutedEntry,
    T539CoverageLedger,
    T539DrawPage,
    T539DrawRecord,
    T539HistoricalQueryError,
    T539HistoricalResultsUnavailableError,
    T539RankingPage,
    T539RankingRecord,
    T539ReplayPage,
    T539ReplayRecord,
    T539RunPage,
    T539RunSummary,
    T539StrategyMetrics,
    T539StrategyPage,
    T539StrategyRecord,
    T539TicketRecord,
)
from lottolab.application.use_cases.query_t539_historical import (
    MAX_LIMIT,
    MIN_LIMIT,
    GetT539CoverageLedger,
    GetT539Draw,
    GetT539Metrics,
    GetT539Target,
    ListT539Draws,
    ListT539Rankings,
    ListT539Replay,
    ListT539Runs,
    ListT539Strategies,
)
from lottolab.interfaces.api.draw_data import ApiErrorResponse, ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_FROZEN_RESPONSE = ConfigDict(frozen=True)
T539Status = Literal[
    "SUCCESS",
    "FAILED",
    "COMPLETE_CAUSAL_REPLAY",
    "PRE_ELIGIBILITY",
]
StatusFilter = Annotated[T539Status | None, Query()]
Limit = Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)]
Offset = Annotated[int, Query(ge=0)]
RunId = Annotated[str, Path(min_length=1, max_length=128)]
TargetId = Annotated[str, Path(min_length=1, max_length=128)]
StrategyFilter = Annotated[str | None, Query(min_length=1, max_length=200)]
StrategyId = Annotated[str, Path(min_length=1, max_length=200)]
StrategyVersion = Annotated[str, Path(min_length=1, max_length=200)]
DateFilter = Annotated[str | None, Query(min_length=10, max_length=10)]


class T539RunView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    schema_version: str
    lottery_type: str
    source_endpoint: str
    source_sha256: str
    as_of_date: str
    adapter_source_commit: str
    strategy_set_fingerprint: str
    status: str
    strategy_count: int
    draw_count: int
    eligible_target_count: int
    ticket_count: int
    failure_count: int
    first_draw_id: str | None
    first_draw_date: str | None
    last_draw_id: str | None
    last_draw_date: str | None

    @classmethod
    def from_summary(cls, value: T539RunSummary) -> T539RunView:
        return cls(
            run_id=value.run_id,
            schema_version=value.schema_version,
            lottery_type=value.lottery_type,
            source_endpoint=value.source_endpoint,
            source_sha256=value.source_sha256,
            as_of_date=value.as_of_date,
            adapter_source_commit=value.adapter_source_commit,
            strategy_set_fingerprint=value.strategy_set_fingerprint,
            status=value.status,
            strategy_count=value.strategy_count,
            draw_count=value.draw_count,
            eligible_target_count=value.eligible_target_count,
            ticket_count=value.ticket_count,
            failure_count=value.failure_count,
            first_draw_id=value.first_draw_id,
            first_draw_date=value.first_draw_date,
            last_draw_id=value.last_draw_id,
            last_draw_date=value.last_draw_date,
        )


class T539RunPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    items: list[T539RunView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: T539RunPage) -> T539RunPageResponse:
        return cls(
            items=[T539RunView.from_summary(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class T539DrawView(BaseModel):
    model_config = _FROZEN_RESPONSE

    draw_id: str
    draw_date: str
    winning_numbers: list[int]

    @classmethod
    def from_record(cls, value: T539DrawRecord) -> T539DrawView:
        return cls(
            draw_id=value.draw_id,
            draw_date=value.draw_date,
            winning_numbers=list(value.winning_numbers),
        )


class T539DrawPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    items: list[T539DrawView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: T539DrawPage) -> T539DrawPageResponse:
        return cls(
            run_id=page.run_id,
            items=[T539DrawView.from_record(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class T539HitDistributionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    value: int
    count: int


class T539StrategyView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    first_eligible_target_draw_id: str | None
    expected_target_draw_count: int
    processed_target_draw_count: int
    successful_target_draw_count: int
    failed_target_draw_count: int
    status: str
    ticket_count: int
    winning_ticket_count: int
    hit_distribution: list[T539HitDistributionView]
    first_target_draw_date: str | None
    last_target_draw_date: str | None

    @classmethod
    def from_record(cls, value: T539StrategyRecord) -> T539StrategyView:
        return cls(
            run_id=value.run_id,
            strategy_id=value.strategy_id,
            strategy_version=value.strategy_version,
            native_ticket_count=value.native_ticket_count,
            min_history=value.min_history,
            first_eligible_target_draw_id=value.first_eligible_target_draw_id,
            expected_target_draw_count=value.expected_target_draw_count,
            processed_target_draw_count=value.processed_target_draw_count,
            successful_target_draw_count=value.successful_target_draw_count,
            failed_target_draw_count=value.failed_target_draw_count,
            status=value.status,
            ticket_count=value.ticket_count,
            winning_ticket_count=value.winning_ticket_count,
            hit_distribution=[
                T539HitDistributionView(value=value_, count=count)
                for value_, count in value.hit_distribution
            ],
            first_target_draw_date=value.first_target_draw_date,
            last_target_draw_date=value.last_target_draw_date,
        )


class T539StrategyPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    items: list[T539StrategyView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: T539StrategyPage) -> T539StrategyPageResponse:
        return cls(
            run_id=page.run_id,
            items=[T539StrategyView.from_record(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class T539TicketView(BaseModel):
    model_config = _FROZEN_RESPONSE

    ticket_position: int
    predicted_numbers: list[int]
    actual_numbers: list[int]
    hit_numbers: list[int]
    hits: int
    is_winner: bool
    prize_tier: str | None
    prize_tier_order: int | None
    prize_amount: int | None

    @classmethod
    def from_record(cls, value: T539TicketRecord) -> T539TicketView:
        return cls(
            ticket_position=value.ticket_position,
            predicted_numbers=list(value.predicted_numbers),
            actual_numbers=list(value.actual_numbers),
            hit_numbers=list(value.hit_numbers),
            hits=value.hits,
            is_winner=value.is_winner,
            prize_tier=value.prize_tier,
            prize_tier_order=value.prize_tier_order,
            prize_amount=value.prize_amount,
        )


class T539ReplayView(BaseModel):
    model_config = _FROZEN_RESPONSE

    target_id: str
    run_id: str
    strategy_id: str
    strategy_version: str
    target_draw_id: str
    target_draw_date: str | None
    cutoff_draw_id: str | None
    cutoff_draw_date: str | None
    status: str
    native_ticket_count: int
    history_length: int | None
    reason_type: str | None
    reason: str | None
    target_success: bool | None
    tickets: list[T539TicketView]

    @classmethod
    def from_record(cls, value: T539ReplayRecord) -> T539ReplayView:
        return cls(
            target_id=value.target_id,
            run_id=value.run_id,
            strategy_id=value.strategy_id,
            strategy_version=value.strategy_version,
            target_draw_id=value.target_draw_id,
            target_draw_date=value.target_draw_date,
            cutoff_draw_id=value.cutoff_draw_id,
            cutoff_draw_date=value.cutoff_draw_date,
            status=_public_status(value.status),
            native_ticket_count=value.native_ticket_count,
            history_length=value.history_length,
            reason_type=value.reason_type,
            reason=value.reason,
            target_success=value.target_success,
            tickets=[T539TicketView.from_record(ticket) for ticket in value.tickets],
        )


class T539ReplayPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    items: list[T539ReplayView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: T539ReplayPage) -> T539ReplayPageResponse:
        return cls(
            run_id=page.run_id,
            items=[T539ReplayView.from_record(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class T539PrizeTierCountView(BaseModel):
    model_config = _FROZEN_RESPONSE

    prize_tier: str
    count: int


class T539MetricsResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    strategy_id: str | None
    target_count: int
    ticket_count: int
    winning_ticket_count: int
    winning_target_count: int
    hit_distribution: list[T539HitDistributionView]
    prize_tier_counts: list[T539PrizeTierCountView]
    first_target_draw_date: str | None
    last_target_draw_date: str | None

    @classmethod
    def from_metrics(cls, value: T539StrategyMetrics) -> T539MetricsResponse:
        return cls(
            run_id=value.run_id,
            strategy_id=value.strategy_id,
            target_count=value.target_count,
            ticket_count=value.ticket_count,
            winning_ticket_count=value.winning_ticket_count,
            winning_target_count=value.winning_target_count,
            hit_distribution=[
                T539HitDistributionView(value=value_, count=count)
                for value_, count in value.hit_distribution
            ],
            prize_tier_counts=[
                T539PrizeTierCountView(prize_tier=tier_id, count=count)
                for tier_id, count in value.prize_tier_counts
            ],
            first_target_draw_date=value.first_target_draw_date,
            last_target_draw_date=value.last_target_draw_date,
        )


class T539RankingView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    rank: int
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    eligible_target_count: int
    winning_target_count: int
    winning_target_rate: float
    total_ticket_count: int
    winning_ticket_count: int
    ticket_winning_rate: float
    prize_tier_counts: list[T539PrizeTierCountView]
    highest_prize_tier_achieved: str | None
    first_eligible_draw: str | None
    last_eligible_draw: str | None
    prize_rule_version: str
    prize_rule_provenance: str

    @classmethod
    def from_record(cls, value: T539RankingRecord) -> T539RankingView:
        return cls(
            run_id=value.run_id,
            rank=value.rank,
            strategy_id=value.strategy_id,
            strategy_version=value.strategy_version,
            native_ticket_count=value.native_ticket_count,
            eligible_target_count=value.eligible_target_count,
            winning_target_count=value.winning_target_count,
            winning_target_rate=value.winning_target_rate,
            total_ticket_count=value.total_ticket_count,
            winning_ticket_count=value.winning_ticket_count,
            ticket_winning_rate=value.ticket_winning_rate,
            prize_tier_counts=[
                T539PrizeTierCountView(prize_tier=tier_id, count=count)
                for tier_id, count in value.prize_tier_counts
            ],
            highest_prize_tier_achieved=value.highest_prize_tier_achieved,
            first_eligible_draw=value.first_eligible_draw,
            last_eligible_draw=value.last_eligible_draw,
            prize_rule_version=value.prize_rule_version,
            prize_rule_provenance=value.prize_rule_provenance,
        )


class T539RankingPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    items: list[T539RankingView]
    disclaimer: str = (
        "Historical winning rank describes past replay only and does not "
        "guarantee future winning. There is no universal cross-lottery hit threshold."
    )

    @classmethod
    def from_page(cls, page: T539RankingPage) -> T539RankingPageResponse:
        return cls(
            run_id=page.run_id,
            items=[T539RankingView.from_record(item) for item in page.items],
        )


class T539CoverageExecutedView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    selection_reason: str

    @classmethod
    def from_record(cls, value: T539CoverageExecutedEntry) -> T539CoverageExecutedView:
        return cls(
            strategy_id=value.strategy_id,
            strategy_version=value.strategy_version,
            native_ticket_count=value.native_ticket_count,
            min_history=value.min_history,
            selection_reason=value.selection_reason,
        )


class T539CoverageBlockedView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_id: str
    reason_code: str
    reason: str

    @classmethod
    def from_record(cls, value: T539CoverageBlockedEntry) -> T539CoverageBlockedView:
        return cls(
            strategy_id=value.strategy_id,
            reason_code=value.reason_code,
            reason=value.reason,
        )


class T539CoverageLedgerResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    executed: list[T539CoverageExecutedView]
    blocked: list[T539CoverageBlockedView]
    coverage_complete: bool

    @classmethod
    def from_ledger(cls, value: T539CoverageLedger) -> T539CoverageLedgerResponse:
        return cls(
            run_id=value.run_id,
            executed=[T539CoverageExecutedView.from_record(item) for item in value.executed],
            blocked=[T539CoverageBlockedView.from_record(item) for item in value.blocked],
            coverage_complete=value.coverage_complete,
        )


def create_t539_historical_router(
    repository_factory: T539HistoricalQueryRepositoryFactory | None,
) -> APIRouter:
    router = APIRouter(prefix=f"{API_PREFIX}/t539-historical", tags=["t539-historical"])
    list_runs = ListT539Runs(repository_factory) if repository_factory is not None else None
    list_draws = ListT539Draws(repository_factory) if repository_factory is not None else None
    get_draw = GetT539Draw(repository_factory) if repository_factory is not None else None
    list_strategies = (
        ListT539Strategies(repository_factory) if repository_factory is not None else None
    )
    list_replay = ListT539Replay(repository_factory) if repository_factory is not None else None
    get_target = GetT539Target(repository_factory) if repository_factory is not None else None
    get_metrics = GetT539Metrics(repository_factory) if repository_factory is not None else None
    list_rankings = ListT539Rankings(repository_factory) if repository_factory is not None else None
    get_coverage_ledger = (
        GetT539CoverageLedger(repository_factory) if repository_factory is not None else None
    )

    @router.get(
        "/runs",
        response_model=T539RunPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listT539HistoricalRuns",
    )
    def list_t539_runs(limit: Limit = 50, offset: Offset = 0) -> T539RunPageResponse | JSONResponse:
        if list_runs is None:
            return _not_configured()
        try:
            return T539RunPageResponse.from_page(list_runs.execute(limit=limit, offset=offset))
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()

    @router.get(
        "/runs/{run_id}/strategies",
        response_model=T539StrategyPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listT539HistoricalStrategies",
    )
    def list_t539_strategies(
        run_id: RunId, limit: Limit = 200, offset: Offset = 0
    ) -> T539StrategyPageResponse | JSONResponse:
        if list_strategies is None:
            return _not_configured()
        try:
            page = list_strategies.execute(run_id, limit=limit, offset=offset)
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_RUN_NOT_FOUND")
            if page is None
            else T539StrategyPageResponse.from_page(page)
        )

    @router.get(
        "/runs/{run_id}/draws",
        response_model=T539DrawPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listT539HistoricalDraws",
    )
    def list_t539_draws(
        run_id: RunId, limit: Limit = 50, offset: Offset = 0
    ) -> T539DrawPageResponse | JSONResponse:
        if list_draws is None:
            return _not_configured()
        try:
            page = list_draws.execute(run_id, limit=limit, offset=offset)
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_RUN_NOT_FOUND")
            if page is None
            else T539DrawPageResponse.from_page(page)
        )

    @router.get(
        "/runs/{run_id}/draws/{draw_id}",
        response_model=T539DrawView,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getT539HistoricalDraw",
    )
    def get_t539_draw(run_id: RunId, draw_id: TargetId) -> T539DrawView | JSONResponse:
        if get_draw is None:
            return _not_configured()
        try:
            value = get_draw.execute(run_id, draw_id)
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_DRAW_NOT_FOUND")
            if value is None
            else T539DrawView.from_record(value)
        )

    @router.get(
        "/runs/{run_id}/replay",
        response_model=T539ReplayPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listT539HistoricalReplay",
    )
    def list_t539_replay(
        run_id: RunId,
        strategy_id: StrategyFilter = None,
        date_from: DateFilter = None,
        date_to: DateFilter = None,
        status: StatusFilter = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> T539ReplayPageResponse | JSONResponse:
        if list_replay is None:
            return _not_configured()
        try:
            page = list_replay.execute(
                run_id,
                strategy_id=strategy_id,
                date_from=date_from,
                date_to=date_to,
                status=status,
                limit=limit,
                offset=offset,
            )
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_RUN_NOT_FOUND")
            if page is None
            else T539ReplayPageResponse.from_page(page)
        )

    @router.get(
        "/runs/{run_id}/targets/{target_id}",
        response_model=T539ReplayView,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getT539HistoricalTarget",
    )
    def get_t539_target(run_id: RunId, target_id: TargetId) -> T539ReplayView | JSONResponse:
        if get_target is None:
            return _not_configured()
        try:
            value = get_target.execute(run_id, target_id)
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_TARGET_NOT_FOUND")
            if value is None
            else T539ReplayView.from_record(value)
        )

    @router.get(
        "/runs/{run_id}/strategies/{strategy_id}/{strategy_version}/targets/{draw_id}",
        response_model=T539ReplayView,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getT539HistoricalStrategyTarget",
    )
    def get_t539_strategy_target(
        run_id: RunId,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        draw_id: TargetId,
    ) -> T539ReplayView | JSONResponse:
        if get_target is None:
            return _not_configured()
        try:
            value = get_target.execute(
                run_id, f"{strategy_id}:{strategy_version}:{draw_id}"
            )
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_TARGET_NOT_FOUND")
            if value is None
            else T539ReplayView.from_record(value)
        )

    @router.get(
        "/runs/{run_id}/metrics",
        response_model=T539MetricsResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getT539HistoricalMetrics",
    )
    def get_t539_metrics(
        run_id: RunId, strategy_id: StrategyFilter = None
    ) -> T539MetricsResponse | JSONResponse:
        if get_metrics is None:
            return _not_configured()
        try:
            value = get_metrics.execute(run_id, strategy_id=strategy_id)
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_RUN_NOT_FOUND")
            if value is None
            else T539MetricsResponse.from_metrics(value)
        )

    @router.get(
        "/runs/{run_id}/rankings",
        response_model=T539RankingPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listT539HistoricalRankings",
    )
    def list_t539_rankings(run_id: RunId) -> T539RankingPageResponse | JSONResponse:
        if list_rankings is None:
            return _not_configured()
        try:
            page = list_rankings.execute(run_id)
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_RUN_NOT_FOUND")
            if page is None
            else T539RankingPageResponse.from_page(page)
        )

    @router.get(
        "/runs/{run_id}/coverage",
        response_model=T539CoverageLedgerResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getT539HistoricalCoverage",
    )
    def get_t539_coverage(run_id: RunId) -> T539CoverageLedgerResponse | JSONResponse:
        if get_coverage_ledger is None:
            return _not_configured()
        try:
            value = get_coverage_ledger.execute(run_id)
        except T539HistoricalResultsUnavailableError:
            return _unavailable()
        except T539HistoricalQueryError:
            return _invalid()
        return (
            _not_found("T539_RUN_NOT_FOUND")
            if value is None
            else T539CoverageLedgerResponse.from_ledger(value)
        )

    return router


def _not_configured() -> JSONResponse:
    return _json_error(
        503, "T539_HISTORICAL_NOT_CONFIGURED", "T539 Historical Results are not configured."
    )


def _unavailable() -> JSONResponse:
    return _json_error(
        503, "T539_HISTORICAL_UNAVAILABLE", "T539 Historical Results are unavailable."
    )


def _invalid() -> JSONResponse:
    return _json_error(
        422, "T539_HISTORICAL_INVALID_QUERY", "The T539 historical query is invalid."
    )


def _not_found(code: str) -> JSONResponse:
    return _json_error(404, code, "The requested T539 historical record was not found.")


def _json_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(error_code=code, message=message).model_dump(mode="json"),
    )


def _public_status(status: str) -> str:
    return {
        "SUCCESS": "COMPLETE_CAUSAL_REPLAY",
        "COMPLETE_CAUSAL_REPLAY": "COMPLETE_CAUSAL_REPLAY",
        "PRE_ELIGIBILITY": "PRE_ELIGIBILITY",
        "FAILED": "FAILED",
    }.get(status, status)


__all__ = ["create_t539_historical_router"]
