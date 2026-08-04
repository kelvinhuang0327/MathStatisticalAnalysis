"""HTTP boundary for legacy single- and multi-file Historical V2 imports."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from lottolab.application.use_cases.historical_draw_import import (
    HistoricalDrawImportError,
    HistoricalDrawImportInputError,
    HistoricalDrawImportService,
)
from lottolab.domain.historical_draw_import import (
    HistoricalImportBatchStatus,
    HistoricalImportChunkResult,
    HistoricalImportDisposition,
    HistoricalImportFileResult,
    HistoricalImportFileStatus,
    HistoricalImportFilter,
    HistoricalImportInput,
    HistoricalImportReason,
    HistoricalImportResult,
    HistoricalImportRowResult,
    HistoricalImportSummary,
)
from lottolab.infrastructure.persistence.historical_draw_import_repository import (
    HistoricalDrawImportRepositoryError,
)
from lottolab.interfaces.api.draw_data import ApiErrorResponse, ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_STRICT_BODY = ConfigDict(extra="forbid", strict=True)
_FROZEN_RESPONSE = ConfigDict(frozen=True)
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024


class HistoricalImportFileRequest(BaseModel):
    model_config = _STRICT_BODY

    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=0)

    @field_validator("filename")
    @classmethod
    def filename_is_display_text(cls, value: str) -> str:
        if not value.strip() or value in {".", ".."}:
            raise ValueError("filename must contain display text")
        if any(ord(character) < 32 for character in value):
            raise ValueError("filename must not contain control characters")
        if "/" in value or "\\" in value:
            raise ValueError("filename must not contain a path")
        return value


class HistoricalImportRequest(BaseModel):
    model_config = _STRICT_BODY

    files: list[HistoricalImportFileRequest] = Field(min_length=1, max_length=100)
    lottery_filter: HistoricalImportFilter = Field(
        default=HistoricalImportFilter.ALL,
        strict=False,
    )


class HistoricalImportRowView(BaseModel):
    model_config = _FROZEN_RESPONSE

    source_filename: str
    source_sha256: str
    member_path: str
    member_sha256: str | None
    source_row_number: int | None
    lottery_type: str | None
    draw_number: str | None
    draw_date: date | None
    main_numbers: list[int]
    special_numbers: list[int]
    disposition: HistoricalImportDisposition
    reason_code: HistoricalImportReason | None
    normalized_record_hash: str | None
    message: str | None
    historical_run_id: str | None

    @classmethod
    def from_result(cls, result: HistoricalImportRowResult) -> HistoricalImportRowView:
        return cls(
            source_filename=result.source_filename,
            source_sha256=result.source_sha256,
            member_path=result.member_path,
            member_sha256=result.member_sha256,
            source_row_number=result.source_row_number,
            lottery_type=None if result.lottery_type is None else result.lottery_type.value,
            draw_number=result.draw_number,
            draw_date=result.draw_date,
            main_numbers=list(result.main_numbers),
            special_numbers=list(result.special_numbers),
            disposition=result.disposition,
            reason_code=result.reason_code,
            normalized_record_hash=result.normalized_record_hash,
            message=result.message,
            historical_run_id=result.historical_run_id,
        )


class HistoricalImportFileView(BaseModel):
    model_config = _FROZEN_RESPONSE

    filename: str
    source_sha256: str
    status: HistoricalImportFileStatus
    discovered_members: int
    accepted_files: int
    excluded_files: int
    parsed_rows: int
    valid_rows: int
    excluded_rows: int
    duplicate_rows: int
    conflict_rows: int
    imported_rows: int
    failed_rows: int
    rows: list[HistoricalImportRowView]

    @classmethod
    def from_result(cls, result: HistoricalImportFileResult) -> HistoricalImportFileView:
        return cls(
            filename=result.filename,
            source_sha256=result.source_sha256,
            status=result.status,
            discovered_members=result.discovered_members,
            accepted_files=result.accepted_files,
            excluded_files=result.excluded_files,
            parsed_rows=result.parsed_rows,
            valid_rows=result.valid_rows,
            excluded_rows=result.excluded_rows,
            duplicate_rows=result.duplicate_rows,
            conflict_rows=result.conflict_rows,
            imported_rows=result.imported_rows,
            failed_rows=result.failed_rows,
            rows=[HistoricalImportRowView.from_result(row) for row in result.rows],
        )


class HistoricalImportChunkView(BaseModel):
    model_config = _FROZEN_RESPONSE

    chunk_index: int
    candidate_rows: int
    imported_rows: int
    failed_rows: int
    status: str
    historical_run_ids: list[str]
    error_code: HistoricalImportReason | None
    error_message: str | None

    @classmethod
    def from_result(cls, result: HistoricalImportChunkResult) -> HistoricalImportChunkView:
        return cls(
            chunk_index=result.chunk_index,
            candidate_rows=result.candidate_rows,
            imported_rows=result.imported_rows,
            failed_rows=result.failed_rows,
            status=result.status.value,
            historical_run_ids=list(result.historical_run_ids),
            error_code=result.error_code,
            error_message=result.error_message,
        )


class HistoricalImportSummaryView(BaseModel):
    model_config = _FROZEN_RESPONSE

    discovered_files: int
    accepted_files: int
    excluded_files: int
    parsed_rows: int
    valid_rows: int
    excluded_rows: int
    duplicate_rows: int
    conflict_rows: int
    imported_rows: int
    failed_rows: int
    committed_chunks: int
    failed_chunks: int

    @classmethod
    def from_result(cls, result: HistoricalImportSummary) -> HistoricalImportSummaryView:
        return cls(
            discovered_files=result.discovered_files,
            accepted_files=result.accepted_files,
            excluded_files=result.excluded_files,
            parsed_rows=result.parsed_rows,
            valid_rows=result.valid_rows,
            excluded_rows=result.excluded_rows,
            duplicate_rows=result.duplicate_rows,
            conflict_rows=result.conflict_rows,
            imported_rows=result.imported_rows,
            failed_rows=result.failed_rows,
            committed_chunks=result.committed_chunks,
            failed_chunks=result.failed_chunks,
        )


class HistoricalImportResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str | None
    status: HistoricalImportBatchStatus
    lottery_filter: HistoricalImportFilter
    files: list[HistoricalImportFileView]
    chunks: list[HistoricalImportChunkView]
    summary: HistoricalImportSummaryView
    row_results: list[HistoricalImportRowView]

    @classmethod
    def from_result(cls, result: HistoricalImportResult) -> HistoricalImportResponse:
        return cls(
            run_id=result.run_id,
            status=result.status,
            lottery_filter=result.lottery_filter,
            files=[HistoricalImportFileView.from_result(item) for item in result.files],
            chunks=[HistoricalImportChunkView.from_result(item) for item in result.chunks],
            summary=HistoricalImportSummaryView.from_result(result.summary),
            row_results=[HistoricalImportRowView.from_result(item) for item in result.row_results],
        )


def _decode_request_files(request: HistoricalImportRequest) -> tuple[HistoricalImportInput, ...]:
    decoded: list[HistoricalImportInput] = []
    total_bytes = 0
    for item in request.files:
        try:
            content = base64.b64decode(item.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HistoricalDrawImportInputError(
                f"{item.filename}: content_base64 is invalid"
            ) from exc
        if not content:
            decoded.append(HistoricalImportInput(filename=item.filename, content=b""))
            continue
        if len(content) > MAX_FILE_BYTES:
            raise HistoricalDrawImportInputError(f"{item.filename}: file is too large")
        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_BYTES:
            raise HistoricalDrawImportInputError("total upload size is too large")
        decoded.append(HistoricalImportInput(filename=item.filename, content=content))
    return tuple(decoded)


def _json_response(status_code: int, model: BaseModel) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


def create_historical_draw_import_router(
    service: HistoricalDrawImportService | None,
) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["historical-draw-imports"])

    def unavailable() -> JSONResponse:
        return _json_response(
            503,
            ApiErrorResponse(
                error_code="HISTORICAL_DRAW_IMPORT_NOT_CONFIGURED",
                message="Historical draw import storage is not configured.",
            ),
        )

    def run_request(
        request: HistoricalImportRequest, *, commit: bool
    ) -> HistoricalImportResponse | JSONResponse:
        if service is None:
            return unavailable()
        try:
            inputs = _decode_request_files(request)
            result = (
                service.import_inputs(inputs, lottery_filter=request.lottery_filter)
                if commit
                else service.preview(inputs, lottery_filter=request.lottery_filter)
            )
        except HistoricalDrawImportInputError as exc:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="HISTORICAL_IMPORT_INPUT_INVALID",
                    message=str(exc),
                ),
            )
        except (HistoricalDrawImportError, HistoricalDrawImportRepositoryError) as exc:
            del exc
            return _json_response(
                503,
                ApiErrorResponse(
                    error_code="HISTORICAL_DRAW_IMPORT_UNAVAILABLE",
                    message="Historical draw import storage is unavailable.",
                ),
            )
        return HistoricalImportResponse.from_result(result)

    @router.post(
        "/historical-results/imports/preview",
        response_model=HistoricalImportResponse,
        responses={422: {"model": ApiValidationErrorResponse}, 503: {"model": ApiErrorResponse}},
        operation_id="previewHistoricalDrawImport",
    )
    def preview_historical_draw_import(
        request: HistoricalImportRequest,
    ) -> HistoricalImportResponse | JSONResponse:
        return run_request(request, commit=False)

    @router.post(
        "/historical-results/imports",
        response_model=HistoricalImportResponse,
        responses={422: {"model": ApiValidationErrorResponse}, 503: {"model": ApiErrorResponse}},
        operation_id="commitHistoricalDrawImport",
    )
    def commit_historical_draw_import(
        request: HistoricalImportRequest,
    ) -> HistoricalImportResponse | JSONResponse:
        return run_request(request, commit=True)

    @router.get(
        "/historical-results/imports/{run_id}",
        response_model=HistoricalImportResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getHistoricalDrawImport",
    )
    def get_historical_draw_import(
        run_id: Annotated[str, Field(min_length=1, max_length=64)],
    ) -> HistoricalImportResponse | JSONResponse:
        if service is None:
            return unavailable()
        try:
            result = service.get_run(run_id)
        except (HistoricalDrawImportError, HistoricalDrawImportRepositoryError) as exc:
            del exc
            return _json_response(
                503,
                ApiErrorResponse(
                    error_code="HISTORICAL_DRAW_IMPORT_UNAVAILABLE",
                    message="Historical draw import storage is unavailable.",
                ),
            )
        if result is None:
            return _json_response(
                404,
                ApiErrorResponse(
                    error_code="HISTORICAL_DRAW_IMPORT_NOT_FOUND",
                    message="Historical draw import was not found.",
                ),
            )
        return HistoricalImportResponse.from_result(result)

    return router


def response_models() -> Sequence[type[BaseModel]]:
    """Expose DTOs for contract and architecture checks."""

    return (
        HistoricalImportRequest,
        HistoricalImportResponse,
        HistoricalImportFileView,
        HistoricalImportRowView,
    )


__all__ = [
    "HistoricalImportRequest",
    "HistoricalImportResponse",
    "create_historical_draw_import_router",
]
