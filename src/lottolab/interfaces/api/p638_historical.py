"""FastAPI adapters for the P638-only Historical Results V2 projections."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.p638_historical import (
    P638HistoricalQueryError,
    P638ReplayPage,
    P638ReplayRecord,
    P638RunPage,
    P638RunSummary,
    P638StrategyMetrics,
    P638StrategyPage,
    P638StrategyRecord,
    P638TicketRecord,
)
from lottolab.application.ports import P638HistoricalQueryRepositoryFactory
from lottolab.application.use_cases.query_p638_historical import (
    MAX_LIMIT,
    MIN_LIMIT,
    GetP638Metrics,
    GetP638Target,
    ListP638Replay,
    ListP638Runs,
    ListP638Strategies,
)
from lottolab.infrastructure.persistence.p638_historical_repositories import (
    P638HistoricalResultsUnavailableError,
)
from lottolab.interfaces.api.draw_data import ApiErrorResponse, ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_FROZEN_RESPONSE = ConfigDict(frozen=True)
P638Status = Literal["COMPLETE", "EXCLUDED_INSUFFICIENT_HISTORY", "FAILED"]
StatusFilter = Annotated[P638Status | None, Query()]
Limit = Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)]
Offset = Annotated[int, Query(ge=0)]
RunId = Annotated[str, Path(min_length=1, max_length=128)]
TargetId = Annotated[str, Path(min_length=1, max_length=128)]
StrategyFilter = Annotated[str | None, Query(min_length=1, max_length=200)]
DateFilter = Annotated[str | None, Query(min_length=10, max_length=10)]


class P638RunView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    import_identity_sha256: str
    manifest_sha256: str
    contract_version: str
    source_run_id: str
    source_replay_sha256: str
    source_draw_db_sha256: str
    source_commit_oid: str
    source_content_sha256: str
    second_zone_ssot_version: str
    status: str
    started_at: str
    completed_at: str
    strategy_count: int
    draw_count: int
    complete_target_count: int
    excluded_target_count: int
    failed_target_count: int
    ticket_count: int
    first_draw_number: str
    first_draw_date: str
    last_draw_number: str
    last_draw_date: str
    is_idempotent_replay: bool

    @classmethod
    def from_summary(cls, value: P638RunSummary) -> P638RunView:
        return cls(
            run_id=value.run_id,
            import_identity_sha256=value.import_identity_sha256,
            manifest_sha256=value.manifest_sha256,
            contract_version=value.contract_version,
            source_run_id=value.source_run_id,
            source_replay_sha256=value.source_replay_sha256,
            source_draw_db_sha256=value.source_draw_db_sha256,
            source_commit_oid=value.source_commit_oid,
            source_content_sha256=value.source_content_sha256,
            second_zone_ssot_version=value.second_zone_ssot_version,
            status=value.status,
            started_at=value.started_at,
            completed_at=value.completed_at,
            strategy_count=value.strategy_count,
            draw_count=value.draw_count,
            complete_target_count=value.complete_target_count,
            excluded_target_count=value.excluded_target_count,
            failed_target_count=value.failed_target_count,
            ticket_count=value.ticket_count,
            first_draw_number=value.first_draw_number,
            first_draw_date=value.first_draw_date,
            last_draw_number=value.last_draw_number,
            last_draw_date=value.last_draw_date,
            is_idempotent_replay=value.is_idempotent_replay,
        )


class P638RunPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    items: list[P638RunView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: P638RunPage) -> P638RunPageResponse:
        return cls(
            items=[P638RunView.from_summary(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class P638HitDistributionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    value: int
    count: int


class P638StrategyView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_snapshot_id: str
    run_id: str
    strategy_id: str
    display_label: str
    strategy_version: str
    executable: bool
    adapter_path: str | None
    native_ticket_count: int | None
    min_history: int | None
    zone1_contract: str
    zone2_contract: str
    lifecycle_status: str
    replay_status: str
    source_run_id: str | None
    source_replay_sha256: str | None
    source_paths: list[str]
    provenance: str
    exclusion_reason: str | None
    complete_target_count: int
    excluded_target_count: int
    failed_target_count: int
    ticket_count: int
    zone1_hit_distribution: list[P638HitDistributionView]
    zone2_hit_distribution: list[P638HitDistributionView]
    first_draw_number: str | None
    first_draw_date: str | None
    last_draw_number: str | None
    last_draw_date: str | None

    @classmethod
    def from_record(cls, value: P638StrategyRecord) -> P638StrategyView:
        return cls(
            strategy_snapshot_id=value.strategy_snapshot_id,
            run_id=value.run_id,
            strategy_id=value.strategy_id,
            display_label=value.display_label,
            strategy_version=value.strategy_version,
            executable=value.executable,
            adapter_path=value.adapter_path,
            native_ticket_count=value.native_ticket_count,
            min_history=value.min_history,
            zone1_contract=value.zone1_contract,
            zone2_contract=value.zone2_contract,
            lifecycle_status=value.lifecycle_status,
            replay_status=value.replay_status,
            source_run_id=value.source_run_id,
            source_replay_sha256=value.source_replay_sha256,
            source_paths=list(value.source_paths),
            provenance=value.provenance,
            exclusion_reason=value.exclusion_reason,
            complete_target_count=value.complete_target_count,
            excluded_target_count=value.excluded_target_count,
            failed_target_count=value.failed_target_count,
            ticket_count=value.ticket_count,
            zone1_hit_distribution=[
                P638HitDistributionView(value=value_, count=count)
                for value_, count in value.zone1_hit_distribution
            ],
            zone2_hit_distribution=[
                P638HitDistributionView(value=value_, count=count)
                for value_, count in value.zone2_hit_distribution
            ],
            first_draw_number=value.first_draw_number,
            first_draw_date=value.first_draw_date,
            last_draw_number=value.last_draw_number,
            last_draw_date=value.last_draw_date,
        )


class P638StrategyPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    items: list[P638StrategyView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: P638StrategyPage) -> P638StrategyPageResponse:
        return cls(
            run_id=page.run_id,
            items=[P638StrategyView.from_record(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class P638TicketView(BaseModel):
    model_config = _FROZEN_RESPONSE

    ticket_id: str
    ticket_position: int
    predicted_zone1_numbers: list[int]
    predicted_zone2_number: int
    actual_zone1_numbers: list[int]
    actual_zone2_number: int
    zone1_hit_count: int
    zone2_hit: bool
    status: str
    source_run_id: str
    source_replay_sha256: str
    source_record_locator: str | None
    second_zone_ssot_version: str
    provenance: str

    @classmethod
    def from_record(cls, value: P638TicketRecord) -> P638TicketView:
        return cls(
            ticket_id=value.ticket_id,
            ticket_position=value.ticket_position,
            predicted_zone1_numbers=list(value.predicted_zone1_numbers),
            predicted_zone2_number=value.predicted_zone2_number,
            actual_zone1_numbers=list(value.actual_zone1_numbers),
            actual_zone2_number=value.actual_zone2_number,
            zone1_hit_count=value.zone1_hit_count,
            zone2_hit=value.zone2_hit,
            status=value.status,
            source_run_id=value.source_run_id,
            source_replay_sha256=value.source_replay_sha256,
            source_record_locator=value.source_record_locator,
            second_zone_ssot_version=value.second_zone_ssot_version,
            provenance=value.provenance,
        )


class P638ReplayView(BaseModel):
    model_config = _FROZEN_RESPONSE

    target_id: str
    run_id: str
    strategy_snapshot_id: str
    strategy_id: str
    strategy_version: str
    target_draw_number: str
    target_draw_date: str
    history_boundary_draw_number: str | None
    history_boundary_date: str | None
    history_length: int
    expected_ticket_count: int
    status: str
    exclusion_reason: str | None
    failure_reason: str | None
    actual_zone1_numbers: list[int]
    actual_zone2_number: int
    source_target_locator: str | None
    source_run_id: str | None
    source_replay_sha256: str | None
    provenance: str
    tickets: list[P638TicketView]

    @classmethod
    def from_record(cls, value: P638ReplayRecord) -> P638ReplayView:
        return cls(
            target_id=value.target_id,
            run_id=value.run_id,
            strategy_snapshot_id=value.strategy_snapshot_id,
            strategy_id=value.strategy_id,
            strategy_version=value.strategy_version,
            target_draw_number=value.target_draw_number,
            target_draw_date=value.target_draw_date,
            history_boundary_draw_number=value.history_boundary_draw_number,
            history_boundary_date=value.history_boundary_date,
            history_length=value.history_length,
            expected_ticket_count=value.expected_ticket_count,
            status=value.status,
            exclusion_reason=value.exclusion_reason,
            failure_reason=value.failure_reason,
            actual_zone1_numbers=list(value.actual_zone1_numbers),
            actual_zone2_number=value.actual_zone2_number,
            source_target_locator=value.source_target_locator,
            source_run_id=value.source_run_id,
            source_replay_sha256=value.source_replay_sha256,
            provenance=value.provenance,
            tickets=[P638TicketView.from_record(ticket) for ticket in value.tickets],
        )


class P638ReplayPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    items: list[P638ReplayView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page: P638ReplayPage) -> P638ReplayPageResponse:
        return cls(
            run_id=page.run_id,
            items=[P638ReplayView.from_record(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


class P638MetricsResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    strategy_id: str | None
    target_count: int
    complete_target_count: int
    excluded_target_count: int
    failed_target_count: int
    ticket_count: int
    combined_zone1_4plus_zone2_hit_count: int
    zone1_hit_distribution: list[P638HitDistributionView]
    zone2_hit_distribution: list[P638HitDistributionView]
    first_draw_number: str | None
    first_draw_date: str | None
    last_draw_number: str | None
    last_draw_date: str | None

    @classmethod
    def from_metrics(cls, value: P638StrategyMetrics) -> P638MetricsResponse:
        return cls(
            run_id=value.run_id,
            strategy_id=value.strategy_id,
            target_count=value.target_count,
            complete_target_count=value.complete_target_count,
            excluded_target_count=value.excluded_target_count,
            failed_target_count=value.failed_target_count,
            ticket_count=value.ticket_count,
            combined_zone1_4plus_zone2_hit_count=value.combined_zone1_4plus_zone2_hit_count,
            zone1_hit_distribution=[
                P638HitDistributionView(value=value_, count=count)
                for value_, count in value.zone1_hit_distribution
            ],
            zone2_hit_distribution=[
                P638HitDistributionView(value=value_, count=count)
                for value_, count in value.zone2_hit_distribution
            ],
            first_draw_number=value.first_draw_number,
            first_draw_date=value.first_draw_date,
            last_draw_number=value.last_draw_number,
            last_draw_date=value.last_draw_date,
        )


def create_p638_historical_router(
    repository_factory: P638HistoricalQueryRepositoryFactory | None,
) -> APIRouter:
    router = APIRouter(prefix=f"{API_PREFIX}/p638-historical", tags=["p638-historical"])
    list_runs = ListP638Runs(repository_factory) if repository_factory is not None else None
    list_strategies = (
        ListP638Strategies(repository_factory) if repository_factory is not None else None
    )
    list_replay = ListP638Replay(repository_factory) if repository_factory is not None else None
    get_target = GetP638Target(repository_factory) if repository_factory is not None else None
    get_metrics = GetP638Metrics(repository_factory) if repository_factory is not None else None

    @router.get(
        "/runs",
        response_model=P638RunPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listP638HistoricalRuns",
    )
    def list_p638_runs(limit: Limit = 50, offset: Offset = 0) -> P638RunPageResponse | JSONResponse:
        if list_runs is None:
            return _not_configured()
        try:
            return P638RunPageResponse.from_page(list_runs.execute(limit=limit, offset=offset))
        except P638HistoricalResultsUnavailableError:
            return _unavailable()
        except P638HistoricalQueryError:
            return _invalid()

    @router.get(
        "/runs/{run_id}/strategies",
        response_model=P638StrategyPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listP638HistoricalStrategies",
    )
    def list_p638_strategies(
        run_id: RunId, limit: Limit = 200, offset: Offset = 0
    ) -> P638StrategyPageResponse | JSONResponse:
        if list_strategies is None:
            return _not_configured()
        try:
            page = list_strategies.execute(run_id, limit=limit, offset=offset)
        except P638HistoricalResultsUnavailableError:
            return _unavailable()
        except P638HistoricalQueryError:
            return _invalid()
        return (
            _not_found("P638_RUN_NOT_FOUND")
            if page is None
            else P638StrategyPageResponse.from_page(page)
        )

    @router.get(
        "/runs/{run_id}/replay",
        response_model=P638ReplayPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listP638HistoricalReplay",
    )
    def list_p638_replay(
        run_id: RunId,
        strategy_id: StrategyFilter = None,
        date_from: DateFilter = None,
        date_to: DateFilter = None,
        status: StatusFilter = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> P638ReplayPageResponse | JSONResponse:
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
        except P638HistoricalResultsUnavailableError:
            return _unavailable()
        except P638HistoricalQueryError:
            return _invalid()
        return (
            _not_found("P638_RUN_NOT_FOUND")
            if page is None
            else P638ReplayPageResponse.from_page(page)
        )

    @router.get(
        "/runs/{run_id}/targets/{target_id}",
        response_model=P638ReplayView,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getP638HistoricalTarget",
    )
    def get_p638_target(run_id: RunId, target_id: TargetId) -> P638ReplayView | JSONResponse:
        if get_target is None:
            return _not_configured()
        try:
            value = get_target.execute(run_id, target_id)
        except P638HistoricalResultsUnavailableError:
            return _unavailable()
        except P638HistoricalQueryError:
            return _invalid()
        return (
            _not_found("P638_TARGET_NOT_FOUND")
            if value is None
            else P638ReplayView.from_record(value)
        )

    @router.get(
        "/runs/{run_id}/metrics",
        response_model=P638MetricsResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getP638HistoricalMetrics",
    )
    def get_p638_metrics(
        run_id: RunId, strategy_id: StrategyFilter = None
    ) -> P638MetricsResponse | JSONResponse:
        if get_metrics is None:
            return _not_configured()
        try:
            value = get_metrics.execute(run_id, strategy_id=strategy_id)
        except P638HistoricalResultsUnavailableError:
            return _unavailable()
        except P638HistoricalQueryError:
            return _invalid()
        return (
            _not_found("P638_RUN_NOT_FOUND")
            if value is None
            else P638MetricsResponse.from_metrics(value)
        )

    return router


def _not_configured() -> JSONResponse:
    return _json_error(
        503, "P638_HISTORICAL_NOT_CONFIGURED", "P638 Historical Results are not configured."
    )


def _unavailable() -> JSONResponse:
    return _json_error(
        503, "P638_HISTORICAL_UNAVAILABLE", "P638 Historical Results are unavailable."
    )


def _invalid() -> JSONResponse:
    return _json_error(
        422, "P638_HISTORICAL_INVALID_QUERY", "The P638 historical query is invalid."
    )


def _not_found(code: str) -> JSONResponse:
    return _json_error(404, code, "The requested P638 historical record was not found.")


def _json_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(error_code=code, message=message).model_dump(mode="json"),
    )


__all__ = ["create_p638_historical_router"]
