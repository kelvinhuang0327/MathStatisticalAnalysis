"""Read-only HTTP routes for verified formal B649 per-draw backtests."""

# FastAPI route functions are referenced through route registration decorators.
# pyright: reportUnusedFunction=false

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.infrastructure.b649_research_record_archive_reader import (
    B649ResearchBacktestRecord,
    B649ResearchRecordArchiveDataError,
    B649ResearchRecordArchiveDataset,
    B649ResearchRecordArchiveReader,
    B649ResearchRecordInvalidFilter,
    B649ResearchRecordSource,
    B649ResearchRecordSourceNotFound,
)
from lottolab.interfaces.api.draw_data import (
    ApiValidationErrorResponse,
    RequestValidationIssueView,
)


class B649ResearchRecordSourceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    record_count: int
    research_class: str
    artifact_sha256: str
    availability_status: str


class B649ResearchRecordSourcesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[B649ResearchRecordSourceView]


class B649ResearchBacktestRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    source_record_identity: str
    target_draw: str | None
    arm_or_method_identity: str | None
    K: int | None
    predicted_tickets: Any
    actual_main_numbers: Any
    actual_special_number: Any
    official_prize_result: dict[str, Any]
    any_official_prize: bool | None
    execution_status: str | None
    original_source_sha256: str
    null_reasons: dict[str, str]


class B649ResearchBacktestRecordsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    total: int
    limit: int
    offset: int
    items: list[B649ResearchBacktestRecordView]


class B649ResearchRecordArchiveErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str


def create_b649_research_record_archive_router(
    reader: B649ResearchRecordArchiveReader | None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/b649-research-backtests", tags=["b649-research-backtests"])

    @router.get(
        "/record-sources",
        response_model=B649ResearchRecordSourcesResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": B649ResearchRecordArchiveErrorResponse},
        },
        operation_id="listB649ResearchBacktestRecordSources",
    )
    def record_sources(request: Request) -> B649ResearchRecordSourcesResponse | JSONResponse:
        invalid = _reject_unknown_query(request, set())
        if invalid is not None:
            return invalid
        dataset = _read_dataset(reader)
        if isinstance(dataset, JSONResponse):
            return dataset
        return B649ResearchRecordSourcesResponse(
            items=[_source_view(source) for source in dataset.sources]
        )

    @router.get(
        "/records",
        response_model=B649ResearchBacktestRecordsResponse,
        responses={
            404: {"model": B649ResearchRecordArchiveErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": B649ResearchRecordArchiveErrorResponse},
        },
        operation_id="listB649ResearchBacktestRecords",
    )
    def records(
        request: Request,
        source_task_id: Annotated[str, Query(min_length=1, max_length=120)],
        target_draw: Annotated[
            str | None,
            Query(min_length=9, max_length=9, pattern=r"^[0-9]{9}$"),
        ] = None,
        arm: Annotated[
            str | None,
            Query(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:@+-]+$"),
        ] = None,
        K: Annotated[int | None, Query(ge=1)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> B649ResearchBacktestRecordsResponse | JSONResponse:
        allowed = {"source_task_id", "target_draw", "arm", "K", "limit", "offset"}
        invalid = _reject_unknown_query(request, allowed)
        if invalid is not None:
            return invalid
        invalid = _reject_duplicate_query(request, allowed)
        if invalid is not None:
            return invalid
        if _is_path_like(source_task_id) or (arm is not None and _is_path_like(arm)):
            return _validation_error(
                [RequestValidationIssueView(location="query", type="value_error")]
            )

        dataset = _read_dataset(reader)
        if isinstance(dataset, JSONResponse):
            return dataset
        try:
            selected, total = dataset.query_records(
                source_task_id,
                target_draw=target_draw,
                arm=arm,
                K=K,
                limit=limit,
                offset=offset,
            )
        except B649ResearchRecordSourceNotFound:
            return _error(
                404,
                "B649_RESEARCH_BACKTEST_SOURCE_NOT_FOUND",
                "The requested formal backtest source is not available.",
            )
        except B649ResearchRecordInvalidFilter:
            return _validation_error(
                [RequestValidationIssueView(location="query.K", type="value_error")]
            )
        return B649ResearchBacktestRecordsResponse(
            source_task_id=source_task_id,
            total=total,
            limit=limit,
            offset=offset,
            items=[_record_view(record) for record in selected],
        )

    return router


def _source_view(source: B649ResearchRecordSource) -> B649ResearchRecordSourceView:
    return B649ResearchRecordSourceView(
        source_task_id=source.source_task_id,
        record_count=source.record_count,
        research_class=source.research_class,
        artifact_sha256=source.artifact_sha256,
        availability_status=source.availability_status,
    )


def _record_view(record: B649ResearchBacktestRecord) -> B649ResearchBacktestRecordView:
    return B649ResearchBacktestRecordView.model_validate(
        {
            "source_task_id": record.source_task_id,
            "source_record_identity": record.source_record_identity,
            "target_draw": record.target_draw,
            "arm_or_method_identity": record.arm_or_method_identity,
            "K": record.K,
            "predicted_tickets": record.predicted_tickets,
            "actual_main_numbers": record.actual_main_numbers,
            "actual_special_number": record.actual_special_number,
            "official_prize_result": record.official_prize_result,
            "any_official_prize": record.any_official_prize,
            "execution_status": record.execution_status,
            "original_source_sha256": record.original_source_sha256,
            "null_reasons": record.null_reasons,
        }
    )


def _read_dataset(
    reader: B649ResearchRecordArchiveReader | None,
) -> B649ResearchRecordArchiveDataset | JSONResponse:
    if reader is None:
        return _error(
            503,
            "B649_RESEARCH_BACKTEST_ARCHIVE_NOT_CONFIGURED",
            "The formal B649 backtest archive root is not configured.",
        )
    try:
        return reader.read()
    except B649ResearchRecordArchiveDataError:
        return _error(
            503,
            "B649_RESEARCH_BACKTEST_ARCHIVE_UNAVAILABLE",
            "The configured formal B649 backtest archive is unavailable or failed verification.",
        )


def _reject_unknown_query(request: Request, allowed: set[str]) -> JSONResponse | None:
    unknown = sorted(set(request.query_params) - allowed)
    if not unknown:
        return None
    return _validation_error(
        [
            RequestValidationIssueView(location=f"query.{key}", type="extra_forbidden")
            for key in unknown
        ]
    )


def _reject_duplicate_query(request: Request, allowed: set[str]) -> JSONResponse | None:
    duplicate = sorted(key for key in allowed if len(request.query_params.getlist(key)) > 1)
    if not duplicate:
        return None
    return _validation_error(
        [
            RequestValidationIssueView(location=f"query.{key}", type="multiple_values")
            for key in duplicate
        ]
    )


def _is_path_like(value: str) -> bool:
    return "/" in value or "\\" in value or ".." in value


def _validation_error(fields: list[RequestValidationIssueView]) -> JSONResponse:
    response = ApiValidationErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        fields=fields,
    )
    return JSONResponse(status_code=422, content=response.model_dump(mode="json"))


def _error(status_code: int, error_code: str, message: str) -> JSONResponse:
    response = B649ResearchRecordArchiveErrorResponse(
        error_code=error_code,
        message=message,
    )
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))
