"""HTTP adapters for DB-free import preview and local draw-data operations."""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from lottolab.application.draw_automation import (
    AutomationNotConfiguredError,
    DrawProviderContractError,
    DrawProviderUnavailableError,
    DrawSyncRequest,
    DrawSyncResult,
    InvalidDrawSyncRequestError,
)
from lottolab.application.draw_data import (
    MAX_HISTORY_PAGE_SIZE,
    DigestMismatchError,
    DrawHistoryPage,
    DrawHistoryQuery,
    DrawRecord,
    ExistingDrawConflictError,
    ImportCommitResult,
    IngestionItemRecord,
    IngestionRunDetail,
    IngestionRunPage,
    IngestionRunQuery,
    IngestionRunRecord,
    InvalidDrawImportError,
    ParserVersionMismatchError,
    RepositoryBusyError,
    RepositoryUnavailableError,
)
from lottolab.application.ports import DrawDataProviderFactory, DrawDataRepositoryFactory
from lottolab.application.use_cases.batch_draw_imports import (
    BATCH_PARSER_VERSION,
    BatchImportDigestMismatchError,
    CommitBatchDrawImport,
    InvalidBatchDrawImportError,
    PreviewBatchDrawImport,
)
from lottolab.application.use_cases.draw_automation import (
    BackfillDrawRange,
    FetchDrawData,
    ScanMissingDraws,
    ScheduledDrawSync,
)
from lottolab.application.use_cases.draw_history import (
    GetDraw,
    GetIngestionRun,
    ListDraws,
    ListIngestionRuns,
)
from lottolab.application.use_cases.draw_imports import (
    CommitDrawImport,
    PreviewDrawImport,
)
from lottolab.domain.batch_imports import (
    BatchDrawImportCommit,
    BatchDrawImportPreview,
    ImportBatchSummary,
    ImportFilePayload,
    ImportFileResult,
    ImportFileStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    ConflictPolicy,
    DrawCsvParseResult,
    DrawImportError,
    IngestionItemDisposition,
    IngestionOperationType,
    IngestionRunStatus,
    NormalizedDrawInput,
)
from lottolab.infrastructure.imports.batch_files import preview_import_batch
from lottolab.infrastructure.imports.csv_draws import (
    PARSER_VERSION,
    SUPPORTED_LOTTERY_TYPES,
    parse_draw_csv,
)
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

MAX_PREVIEW_RECORDS = 50
MAX_PREVIEW_ERRORS = 100

_STRICT_BODY = ConfigDict(extra="forbid", strict=True)
_COERCING_BODY = ConfigDict(extra="forbid")
_FROZEN_RESPONSE = ConfigDict(frozen=True)
class DrawImportPreviewRequest(BaseModel):
    model_config = _STRICT_BODY

    filename: str = Field(min_length=1, max_length=255)
    csv_text: str
    declared_parser_version: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("filename")
    @classmethod
    def filename_is_display_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("filename must contain display text")
        if any(ord(character) < 32 for character in value):
            raise ValueError("filename must not contain control characters")
        return value


class DrawImportCommitRequest(BaseModel):
    model_config = _STRICT_BODY

    filename: str = Field(min_length=1, max_length=255)
    csv_text: str
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_version: str = Field(min_length=1, max_length=100)
    conflict_policy: ConflictPolicy = Field(strict=False)

    @field_validator("filename")
    @classmethod
    def filename_is_display_text(cls, value: str) -> str:
        return DrawImportPreviewRequest.filename_is_display_text(value)


class DrawImportErrorView(BaseModel):
    model_config = _FROZEN_RESPONSE

    code: str
    message: str
    row_number: int | None
    field: str | None

    @classmethod
    def from_error(cls, error: DrawImportError) -> DrawImportErrorView:
        return cls(
            code=error.code.value,
            message=error.message,
            row_number=error.row_number,
            field=error.field,
        )


class NormalizedDrawPreviewView(BaseModel):
    model_config = _FROZEN_RESPONSE

    source_row_number: int
    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: list[int]
    special_numbers: list[int]
    source_reference: str | None
    normalized_record_hash: str

    @classmethod
    def from_row(cls, row: NormalizedDrawInput) -> NormalizedDrawPreviewView:
        return cls(
            source_row_number=row.source_row_number,
            lottery_type=row.lottery_type,
            draw_number=row.draw_number,
            draw_date=row.draw_date,
            main_numbers=list(row.main_numbers),
            special_numbers=list(row.special_numbers),
            source_reference=row.source,
            normalized_record_hash=row.normalized_record_hash,
        )


class DrawImportPreviewResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    filename: str
    is_valid: bool
    content_sha256: str
    parser_version: str
    supported_lottery_types: list[LotteryType]
    total_rows: int
    valid_rows: int
    blank_rows: int
    duplicate_rows: int
    conflict_rows_inside_input: int
    validation_error_count: int
    ignored_columns: list[str]
    normalized_preview: list[NormalizedDrawPreviewView]
    validation_errors: list[DrawImportErrorView]
    preview_truncated: bool
    errors_truncated: bool

    @classmethod
    def from_result(cls, result: DrawCsvParseResult) -> DrawImportPreviewResponse:
        return cls(
            filename=result.source_filename,
            is_valid=result.is_valid,
            content_sha256=result.content_sha256,
            parser_version=result.parser_version,
            supported_lottery_types=list(SUPPORTED_LOTTERY_TYPES),
            total_rows=result.total_rows,
            valid_rows=result.valid_rows,
            blank_rows=result.blank_rows,
            duplicate_rows=result.duplicate_input_rows,
            conflict_rows_inside_input=result.conflicting_input_rows,
            validation_error_count=result.validation_error_count,
            ignored_columns=list(result.ignored_columns),
            normalized_preview=[
                NormalizedDrawPreviewView.from_row(row)
                for row in result.normalized_rows[:MAX_PREVIEW_RECORDS]
            ],
            validation_errors=[
                DrawImportErrorView.from_error(error)
                for error in result.errors[:MAX_PREVIEW_ERRORS]
            ],
            preview_truncated=len(result.normalized_rows) > MAX_PREVIEW_RECORDS,
            errors_truncated=len(result.errors) > MAX_PREVIEW_ERRORS,
        )


class BatchImportFileRequest(BaseModel):
    model_config = _STRICT_BODY

    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)

    @field_validator("filename")
    @classmethod
    def filename_is_display_text(cls, value: str) -> str:
        return DrawImportPreviewRequest.filename_is_display_text(value)


class BatchImportPreviewRequest(BaseModel):
    model_config = _STRICT_BODY

    files: list[BatchImportFileRequest] = Field(min_length=1, max_length=250)
    declared_parser_version: str | None = Field(default=None, min_length=1, max_length=100)


class BatchImportCommitRequest(BaseModel):
    model_config = _STRICT_BODY

    files: list[BatchImportFileRequest] = Field(min_length=1, max_length=250)
    expected_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_version: str = Field(min_length=1, max_length=100)


class BatchImportIssueView(BaseModel):
    model_config = _FROZEN_RESPONSE

    code: str
    message: str
    row_number: int | None
    member_name: str | None


class BatchImportFileView(BaseModel):
    model_config = _FROZEN_RESPONSE

    source_filename: str
    source_locator: str
    source_sha256: str
    status: ImportFileStatus
    lottery_type: LotteryType | None
    discovered_rows: int
    accepted_rows: int
    excluded_rows: int
    duplicate_rows: int
    conflict_rows: int
    failed_rows: int
    imported_rows: int
    issues: list[BatchImportIssueView]

    @classmethod
    def from_result(cls, result: ImportFileResult) -> BatchImportFileView:
        return cls(
            source_filename=result.source_filename,
            source_locator=result.source_locator,
            source_sha256=result.source_sha256,
            status=result.status,
            lottery_type=result.lottery_type,
            discovered_rows=result.discovered_rows,
            accepted_rows=result.accepted_rows,
            excluded_rows=result.excluded_rows,
            duplicate_rows=result.duplicate_rows,
            conflict_rows=result.conflict_rows,
            failed_rows=result.failed_rows,
            imported_rows=result.imported_rows,
            issues=[
                BatchImportIssueView(
                    code=issue.code,
                    message=issue.message,
                    row_number=issue.row_number,
                    member_name=issue.member_name,
                )
                for issue in result.issues
            ],
        )


class BatchImportSummaryView(BaseModel):
    model_config = _FROZEN_RESPONSE

    discovered_files: int
    accepted_files: int
    excluded_files: int
    parsed_rows: int
    accepted_rows: int
    excluded_rows: int
    duplicate_rows: int
    conflict_rows: int
    imported_rows: int
    failed_rows: int

    @classmethod
    def from_summary(cls, summary: ImportBatchSummary) -> BatchImportSummaryView:
        return cls(
            discovered_files=summary.discovered_files,
            accepted_files=summary.accepted_files,
            excluded_files=summary.excluded_files,
            parsed_rows=summary.parsed_rows,
            accepted_rows=summary.accepted_rows,
            excluded_rows=summary.excluded_rows,
            duplicate_rows=summary.duplicate_rows,
            conflict_rows=summary.conflict_rows,
            imported_rows=summary.imported_rows,
            failed_rows=summary.failed_rows,
        )


class BatchImportPreviewResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    source_filename: str
    is_valid: bool
    manifest_sha256: str
    parser_version: str
    files: list[BatchImportFileView]
    summary: BatchImportSummaryView
    normalized_preview: list[NormalizedDrawPreviewView]
    preview_truncated: bool

    @classmethod
    def from_preview(cls, preview: BatchDrawImportPreview) -> BatchImportPreviewResponse:
        return cls(
            source_filename=preview.source_filename,
            is_valid=preview.is_valid,
            manifest_sha256=preview.manifest_sha256,
            parser_version=BATCH_PARSER_VERSION,
            files=[BatchImportFileView.from_result(file) for file in preview.files],
            summary=BatchImportSummaryView.from_summary(preview.summary),
            normalized_preview=[
                NormalizedDrawPreviewView.from_row(row)
                for row in preview.normalized_rows[:MAX_PREVIEW_RECORDS]
            ],
            preview_truncated=len(preview.normalized_rows) > MAX_PREVIEW_RECORDS,
        )


class BatchImportCommitResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str | None
    status: Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED"]
    manifest_sha256: str
    summary: BatchImportSummaryView
    files: list[BatchImportFileView]
    completed_at: str
    error_summary: str | None
    run_ids: list[str]
    committed_chunks: int
    failed_chunks: int

    @classmethod
    def from_commit(cls, commit: BatchDrawImportCommit) -> BatchImportCommitResponse:
        return cls(
            run_id=commit.run_id,
            status=commit.status,
            manifest_sha256=commit.manifest_sha256,
            summary=BatchImportSummaryView.from_summary(commit.summary),
            files=[BatchImportFileView.from_result(file) for file in commit.files],
            completed_at=commit.completed_at,
            error_summary=commit.error_summary,
            run_ids=list(commit.run_ids),
            committed_chunks=commit.committed_chunks,
            failed_chunks=commit.failed_chunks,
        )


class ApiErrorResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    error_code: str
    message: str


class RequestValidationIssueView(BaseModel):
    model_config = _FROZEN_RESPONSE

    location: str
    type: str


def _empty_validation_issues() -> list[RequestValidationIssueView]:
    return []


class ApiValidationErrorResponse(ApiErrorResponse):
    preview: DrawImportPreviewResponse | None = None
    fields: list[RequestValidationIssueView] = Field(default_factory=_empty_validation_issues)


class BatchImportValidationErrorResponse(ApiErrorResponse):
    preview: BatchImportPreviewResponse | None = None
    fields: list[RequestValidationIssueView] = Field(default_factory=_empty_validation_issues)


class ImportCommitResultView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str | None
    status: IngestionRunStatus
    lottery_type: LotteryType | None
    total_count: int
    inserted_count: int
    skipped_count: int
    conflict_count: int
    failed_count: int
    first_draw_number: str | None
    last_draw_number: str | None
    completed_at: datetime

    @classmethod
    def from_result(cls, result: ImportCommitResult) -> ImportCommitResultView:
        return cls(
            run_id=result.run_id,
            status=result.status,
            lottery_type=result.lottery_type,
            total_count=result.total_count,
            inserted_count=result.inserted_count,
            skipped_count=result.skipped_count,
            conflict_count=result.conflict_count,
            failed_count=result.failed_count,
            first_draw_number=result.first_draw_number,
            last_draw_number=result.last_draw_number,
            completed_at=result.completed_at,
        )


class DrawSyncRequestView(BaseModel):
    model_config = _COERCING_BODY

    lottery_type: LotteryType
    date_from: date
    date_to: date


class DrawSyncResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    operation_type: IngestionOperationType
    provider: str
    requested_start: date
    requested_end: date
    resolved_start: date | None
    resolved_end: date | None
    fetched_count: int
    result: ImportCommitResultView

    @classmethod
    def from_result(cls, result: DrawSyncResult) -> DrawSyncResponse:
        return cls(
            operation_type=result.operation_type,
            provider=result.provider_id,
            requested_start=result.requested_start,
            requested_end=result.requested_end,
            resolved_start=result.resolved_start,
            resolved_end=result.resolved_end,
            fetched_count=result.fetched_count,
            result=ImportCommitResultView.from_result(result.ingestion),
        )


class CommitConflictResponse(ApiErrorResponse):
    result: ImportCommitResultView | None


class DrawRecordView(BaseModel):
    model_config = _FROZEN_RESPONSE

    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: list[int]
    special_numbers: list[int]
    source_name: str | None
    source_reference: str | None
    ingestion_run_id: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: DrawRecord) -> DrawRecordView:
        return cls(
            lottery_type=record.lottery_type,
            draw_number=record.draw_number,
            draw_date=record.draw_date,
            main_numbers=list(record.main_numbers),
            special_numbers=list(record.special_numbers),
            source_name=record.source_name,
            source_reference=record.source_reference,
            ingestion_run_id=record.ingestion_run_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class DrawHistoryResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    records: list[DrawRecordView]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    sort: list[str]

    @classmethod
    def from_page(cls, page: DrawHistoryPage) -> DrawHistoryResponse:
        return cls(
            records=[DrawRecordView.from_record(record) for record in page.records],
            page=page.page,
            page_size=page.page_size,
            total_count=page.total_count,
            total_pages=page.total_pages,
            sort=list(page.sort),
        )


class IngestionRunView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    operation_type: IngestionOperationType
    status: IngestionRunStatus
    lottery_type: LotteryType | None
    source_filename: str
    source_sha256: str
    parser_version: str
    trigger: IngestionOperationType
    provider: str | None
    provider_version: str | None
    requested_start: str | None
    requested_end: str | None
    resolved_start: str | None
    resolved_end: str | None
    fetched_count: int
    total_count: int
    inserted_count: int
    skipped_count: int
    conflict_count: int
    failed_count: int
    first_draw_number: str | None
    last_draw_number: str | None
    started_at: datetime
    completed_at: datetime | None
    error_summary: str | None

    @classmethod
    def from_record(cls, record: IngestionRunRecord) -> IngestionRunView:
        return cls(
            run_id=record.run_id,
            operation_type=record.operation_type,
            status=record.status,
            lottery_type=record.lottery_type,
            source_filename=record.source_filename,
            source_sha256=record.source_sha256,
            parser_version=record.parser_version,
            trigger=record.operation_type,
            provider=record.provider,
            provider_version=record.provider_version,
            requested_start=record.requested_start,
            requested_end=record.requested_end,
            resolved_start=record.resolved_start,
            resolved_end=record.resolved_end,
            fetched_count=record.fetched_count,
            total_count=record.total_count,
            inserted_count=record.inserted_count,
            skipped_count=record.skipped_count,
            conflict_count=record.conflict_count,
            failed_count=record.failed_count,
            first_draw_number=record.first_draw_number,
            last_draw_number=record.last_draw_number,
            started_at=record.started_at,
            completed_at=record.completed_at,
            error_summary=record.error_summary,
        )


class IngestionRunPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    records: list[IngestionRunView]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    sort: list[str]

    @classmethod
    def from_page(cls, page: IngestionRunPage) -> IngestionRunPageResponse:
        return cls(
            records=[IngestionRunView.from_record(record) for record in page.records],
            page=page.page,
            page_size=page.page_size,
            total_count=page.total_count,
            total_pages=page.total_pages,
            sort=list(page.sort),
        )


class IngestionItemView(BaseModel):
    model_config = _FROZEN_RESPONSE

    source_row_number: int
    lottery_type: LotteryType | None
    draw_number: str | None
    source: str | None
    disposition: IngestionItemDisposition
    normalized_record_hash: str | None
    message: str | None

    @classmethod
    def from_record(
        cls,
        record: IngestionItemRecord,
        *,
        fallback_source: str | None = None,
    ) -> IngestionItemView:
        return cls(
            source_row_number=record.source_row_number,
            lottery_type=record.lottery_type,
            draw_number=record.draw_number,
            source=record.source or fallback_source,
            disposition=record.disposition,
            normalized_record_hash=record.normalized_record_hash,
            message=record.message,
        )


class IngestionRunDetailResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run: IngestionRunView
    items: list[IngestionItemView]
    item_count: int
    items_truncated: bool

    @classmethod
    def from_detail(cls, detail: IngestionRunDetail) -> IngestionRunDetailResponse:
        fallback_source = detail.run.provider or detail.run.source_filename
        return cls(
            run=IngestionRunView.from_record(detail.run),
            items=[
                IngestionItemView.from_record(item, fallback_source=fallback_source)
                for item in detail.items
            ],
            item_count=detail.item_count,
            items_truncated=detail.items_truncated,
        )


Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_HISTORY_PAGE_SIZE)]
DrawNumberFilter = Annotated[
    str | None,
    Query(min_length=1, max_length=32, pattern=r"^[0-9]+$"),
]


def _decode_batch_payloads(
    files: Sequence[BatchImportFileRequest],
) -> tuple[ImportFilePayload, ...]:
    payloads: list[ImportFilePayload] = []
    for file in files:
        try:
            content = base64.b64decode(file.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"content_base64 is invalid for {file.filename}") from exc
        payloads.append(ImportFilePayload(filename=file.filename, content=content))
    return tuple(payloads)


def create_draw_data_router(
    repository_factory: DrawDataRepositoryFactory,
    provider_factory: DrawDataProviderFactory | None = None,
) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["draw-data"])
    resolved_provider_factory: DrawDataProviderFactory = (
        provider_factory if provider_factory is not None else lambda: None
    )
    preview_import = PreviewDrawImport(parse_draw_csv, PARSER_VERSION)
    commit_import = CommitDrawImport(parse_draw_csv, PARSER_VERSION, repository_factory)
    preview_batch_import = PreviewBatchDrawImport(preview_import_batch)
    commit_batch_import = CommitBatchDrawImport(preview_import_batch, repository_factory)
    fetch_draw_data = FetchDrawData(
        resolved_provider_factory, repository_factory, parse_draw_csv
    )
    scan_missing_draws = ScanMissingDraws(
        resolved_provider_factory, repository_factory, parse_draw_csv
    )
    backfill_draw_range = BackfillDrawRange(
        resolved_provider_factory, repository_factory, parse_draw_csv
    )
    scheduled_draw_sync = ScheduledDrawSync(
        resolved_provider_factory, repository_factory, parse_draw_csv
    )
    list_draws_use_case = ListDraws(repository_factory)
    get_draw_use_case = GetDraw(repository_factory)
    list_runs_use_case = ListIngestionRuns(repository_factory)
    get_run_use_case = GetIngestionRun(repository_factory)

    @router.post(
        "/draw-imports/preview",
        response_model=DrawImportPreviewResponse,
        responses={422: {"model": ApiValidationErrorResponse}},
        operation_id="previewDrawImport",
    )
    def preview_draw_import(
        request: DrawImportPreviewRequest,
    ) -> DrawImportPreviewResponse | JSONResponse:
        try:
            parsed = preview_import.execute(
                filename=request.filename,
                csv_text=request.csv_text,
                declared_parser_version=request.declared_parser_version,
            )
        except ParserVersionMismatchError:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="PARSER_VERSION_MISMATCH",
                    message="The declared parser version is not current.",
                    preview=None,
                ),
            )
        preview = DrawImportPreviewResponse.from_result(parsed)
        if not parsed.is_valid:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="CSV_VALIDATION_FAILED",
                    message="CSV validation failed; no data was persisted.",
                    preview=preview,
                ),
            )
        return preview

    @router.post(
        "/draw-imports/commit",
        response_model=ImportCommitResultView,
        responses={
            409: {"model": CommitConflictResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="commitDrawImport",
    )
    def commit_draw_import(
        request: DrawImportCommitRequest,
    ) -> ImportCommitResultView | JSONResponse:
        try:
            result = commit_import.execute(
                filename=request.filename,
                csv_text=request.csv_text,
                expected_sha256=request.expected_sha256,
                parser_version=request.parser_version,
            )
        except DigestMismatchError:
            return _json_response(
                409,
                CommitConflictResponse(
                    error_code="DIGEST_MISMATCH",
                    message="CSV content does not match the preview digest.",
                    result=None,
                ),
            )
        except ParserVersionMismatchError:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="PARSER_VERSION_MISMATCH",
                    message="The parser version is not current.",
                    preview=None,
                ),
            )
        except InvalidDrawImportError as exc:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="CSV_VALIDATION_FAILED",
                    message="CSV validation failed; no data was persisted.",
                    preview=DrawImportPreviewResponse.from_result(exc.result),
                ),
            )
        except ExistingDrawConflictError as exc:
            return _json_response(
                409,
                CommitConflictResponse(
                    error_code="EXISTING_DRAW_CONFLICT",
                    message="Existing draw data conflicts; the batch inserted no draws.",
                    result=ImportCommitResultView.from_result(exc.result),
                ),
            )
        except RepositoryBusyError:
            return _repository_error("REPOSITORY_BUSY", "Local draw data is temporarily busy.")
        except RepositoryUnavailableError:
            return _repository_error("REPOSITORY_UNAVAILABLE", "Local draw data is unavailable.")
        return ImportCommitResultView.from_result(result)

    @router.post(
        "/draw-imports/batch/preview",
        response_model=BatchImportPreviewResponse,
        responses={422: {"model": BatchImportValidationErrorResponse}},
        operation_id="previewBatchDrawImport",
    )
    def preview_batch_draw_import(
        request: BatchImportPreviewRequest,
    ) -> BatchImportPreviewResponse | JSONResponse:
        if (
            request.declared_parser_version is not None
            and request.declared_parser_version != BATCH_PARSER_VERSION
        ):
            return _json_response(
                422,
                BatchImportValidationErrorResponse(
                    error_code="PARSER_VERSION_MISMATCH",
                    message="The declared batch parser version is not current.",
                ),
            )
        try:
            payloads = _decode_batch_payloads(request.files)
        except ValueError as exc:
            return _json_response(
                422,
                BatchImportValidationErrorResponse(
                    error_code="INVALID_BASE64_PAYLOAD",
                    message=str(exc),
                ),
            )
        preview = preview_batch_import.execute(payloads)
        response = BatchImportPreviewResponse.from_preview(preview)
        if not preview.is_valid:
            return _json_response(
                422,
                BatchImportValidationErrorResponse(
                    error_code="BATCH_VALIDATION_FAILED",
                    message="The batch contains no safely importable draw rows or a failed file.",
                    preview=response,
                ),
            )
        return response

    @router.post(
        "/draw-imports/batch/commit",
        response_model=BatchImportCommitResponse,
        responses={
            409: {"model": ApiErrorResponse},
            422: {"model": BatchImportValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="commitBatchDrawImport",
    )
    def commit_batch_draw_import(
        request: BatchImportCommitRequest,
    ) -> BatchImportCommitResponse | JSONResponse:
        try:
            payloads = _decode_batch_payloads(request.files)
        except ValueError as exc:
            return _json_response(
                422,
                BatchImportValidationErrorResponse(
                    error_code="INVALID_BASE64_PAYLOAD",
                    message=str(exc),
                ),
            )
        try:
            commit = commit_batch_import.execute(
                payloads=payloads,
                expected_manifest_sha256=request.expected_manifest_sha256,
                parser_version=request.parser_version,
            )
        except BatchImportDigestMismatchError:
            return _json_response(
                409,
                ApiErrorResponse(
                    error_code="BATCH_DIGEST_MISMATCH",
                    message="Batch content does not match the preview manifest.",
                ),
            )
        except InvalidBatchDrawImportError as exc:
            return _json_response(
                422,
                BatchImportValidationErrorResponse(
                    error_code="BATCH_VALIDATION_FAILED",
                    message="The batch contains no safely importable draw rows or a failed file.",
                    preview=BatchImportPreviewResponse.from_preview(exc.preview),
                ),
            )
        except RepositoryBusyError:
            return _repository_error("REPOSITORY_BUSY", "Local draw data is temporarily busy.")
        except RepositoryUnavailableError:
            return _repository_error("REPOSITORY_UNAVAILABLE", "Local draw data is unavailable.")
        return BatchImportCommitResponse.from_commit(commit)

    def run_sync(
        request: DrawSyncRequestView,
        use_case: FetchDrawData | ScanMissingDraws | BackfillDrawRange | ScheduledDrawSync,
    ) -> DrawSyncResponse | JSONResponse:
        try:
            result = use_case.execute(
                DrawSyncRequest(
                    lottery_type=request.lottery_type,
                    date_from=request.date_from,
                    date_to=request.date_to,
                )
            )
        except InvalidDrawSyncRequestError:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="INVALID_SYNC_RANGE",
                    message="The requested draw sync range is invalid or unbounded.",
                ),
            )
        except AutomationNotConfiguredError:
            return _json_response(
                503,
                ApiErrorResponse(
                    error_code="AUTOMATION_NOT_CONFIGURED",
                    message="Draw automation is not configured.",
                ),
            )
        except DrawProviderContractError:
            return _json_response(
                502,
                ApiErrorResponse(
                    error_code="PROVIDER_CONTRACT_INVALID",
                    message="The configured draw provider returned invalid data.",
                ),
            )
        except DrawProviderUnavailableError:
            return _json_response(
                503,
                ApiErrorResponse(
                    error_code="PROVIDER_UNAVAILABLE",
                    message="The configured draw provider is unavailable.",
                ),
            )
        except ExistingDrawConflictError as exc:
            return _json_response(
                409,
                CommitConflictResponse(
                    error_code="EXISTING_DRAW_CONFLICT",
                    message="Existing draw data conflicts; the sync inserted no draws.",
                    result=ImportCommitResultView.from_result(exc.result),
                ),
            )
        except RepositoryBusyError:
            return _repository_error("REPOSITORY_BUSY", "Local draw data is temporarily busy.")
        except RepositoryUnavailableError:
            return _repository_error("REPOSITORY_UNAVAILABLE", "Local draw data is unavailable.")
        return DrawSyncResponse.from_result(result)

    @router.post(
        "/draw-sync/manual",
        response_model=DrawSyncResponse,
        responses={
            409: {"model": CommitConflictResponse},
            422: {"model": ApiValidationErrorResponse},
            502: {"model": ApiErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="fetchDrawData",
    )
    def manual_sync(request: DrawSyncRequestView) -> DrawSyncResponse | JSONResponse:
        return run_sync(request, fetch_draw_data)

    @router.post(
        "/draw-sync/missing-scan",
        response_model=DrawSyncResponse,
        responses={
            409: {"model": CommitConflictResponse},
            422: {"model": ApiValidationErrorResponse},
            502: {"model": ApiErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="scanMissingDraws",
    )
    def missing_draw_scan(request: DrawSyncRequestView) -> DrawSyncResponse | JSONResponse:
        return run_sync(request, scan_missing_draws)

    @router.post(
        "/draw-sync/backfill",
        response_model=DrawSyncResponse,
        responses={
            409: {"model": CommitConflictResponse},
            422: {"model": ApiValidationErrorResponse},
            502: {"model": ApiErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="backfillDrawRange",
    )
    def bounded_backfill(request: DrawSyncRequestView) -> DrawSyncResponse | JSONResponse:
        return run_sync(request, backfill_draw_range)

    @router.post(
        "/draw-sync/scheduled",
        response_model=DrawSyncResponse,
        responses={
            409: {"model": CommitConflictResponse},
            422: {"model": ApiValidationErrorResponse},
            502: {"model": ApiErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="runScheduledDrawSync",
    )
    def scheduled_sync(request: DrawSyncRequestView) -> DrawSyncResponse | JSONResponse:
        return run_sync(request, scheduled_draw_sync)

    @router.get(
        "/draws",
        response_model=DrawHistoryResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listDraws",
    )
    def list_draw_history(
        lottery_type: LotteryType | None = None,
        draw_number: DrawNumberFilter = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: Page = 1,
        page_size: PageSize = 25,
    ) -> DrawHistoryResponse | JSONResponse:
        if date_from is not None and date_to is not None and date_from > date_to:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="INVALID_DATE_RANGE",
                    message="date_from must not be after date_to.",
                ),
            )
        try:
            history = list_draws_use_case.execute(
                DrawHistoryQuery(
                    lottery_type=lottery_type,
                    draw_number=draw_number,
                    date_from=date_from,
                    date_to=date_to,
                    page=page,
                    page_size=page_size,
                )
            )
        except RepositoryBusyError:
            return _repository_error("REPOSITORY_BUSY", "Local draw data is temporarily busy.")
        except RepositoryUnavailableError:
            return _repository_error("REPOSITORY_UNAVAILABLE", "Local draw data is unavailable.")
        return DrawHistoryResponse.from_page(history)

    @router.get(
        "/draws/{lottery_type}/{draw_number}",
        response_model=DrawRecordView,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getDraw",
    )
    def get_draw(
        lottery_type: LotteryType,
        draw_number: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[0-9]+$")],
    ) -> DrawRecordView | JSONResponse:
        try:
            record = get_draw_use_case.execute(lottery_type, draw_number)
        except RepositoryBusyError:
            return _repository_error("REPOSITORY_BUSY", "Local draw data is temporarily busy.")
        except RepositoryUnavailableError:
            return _repository_error("REPOSITORY_UNAVAILABLE", "Local draw data is unavailable.")
        if record is None:
            return _json_response(
                404,
                ApiErrorResponse(error_code="DRAW_NOT_FOUND", message="Draw was not found."),
            )
        return DrawRecordView.from_record(record)

    @router.get(
        "/ingestion-runs",
        response_model=IngestionRunPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listIngestionRuns",
    )
    def list_ingestion_runs(
        status: IngestionRunStatus | None = None,
        operation_type: IngestionOperationType | None = None,
        lottery_type: LotteryType | None = None,
        source: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: Page = 1,
        page_size: PageSize = 25,
    ) -> IngestionRunPageResponse | JSONResponse:
        if date_from is not None and date_to is not None and date_from > date_to:
            return _json_response(
                422,
                ApiValidationErrorResponse(
                    error_code="INVALID_DATE_RANGE",
                    message="date_from must not be after date_to.",
                ),
            )
        try:
            runs = list_runs_use_case.execute(
                IngestionRunQuery(
                    status=status,
                    operation_type=operation_type,
                    lottery_type=lottery_type,
                    source=source,
                    date_from=date_from,
                    date_to=date_to,
                    page=page,
                    page_size=page_size,
                )
            )
        except RepositoryBusyError:
            return _repository_error("REPOSITORY_BUSY", "Local draw data is temporarily busy.")
        except RepositoryUnavailableError:
            return _repository_error("REPOSITORY_UNAVAILABLE", "Local draw data is unavailable.")
        return IngestionRunPageResponse.from_page(runs)

    @router.get(
        "/ingestion-runs/{run_id}",
        response_model=IngestionRunDetailResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getIngestionRun",
    )
    def get_ingestion_run(
        run_id: Annotated[str, Field(min_length=1, max_length=64)],
    ) -> IngestionRunDetailResponse | JSONResponse:
        try:
            detail = get_run_use_case.execute(run_id)
        except RepositoryBusyError:
            return _repository_error("REPOSITORY_BUSY", "Local draw data is temporarily busy.")
        except RepositoryUnavailableError:
            return _repository_error("REPOSITORY_UNAVAILABLE", "Local draw data is unavailable.")
        if detail is None:
            return _json_response(
                404,
                ApiErrorResponse(
                    error_code="INGESTION_RUN_NOT_FOUND",
                    message="Ingestion run was not found.",
                ),
            )
        return IngestionRunDetailResponse.from_detail(detail)

    return router


def _repository_error(error_code: str, message: str) -> JSONResponse:
    return _json_response(503, ApiErrorResponse(error_code=error_code, message=message))


def _json_response(status_code: int, model: BaseModel) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


def response_models() -> Sequence[type[BaseModel]]:
    """Expose explicit DTOs for architecture/contract assertions."""

    return (
        DrawImportPreviewResponse,
        BatchImportPreviewResponse,
        BatchImportCommitResponse,
        ImportCommitResultView,
        DrawSyncResponse,
        DrawHistoryResponse,
        IngestionRunPageResponse,
        IngestionRunDetailResponse,
    )
