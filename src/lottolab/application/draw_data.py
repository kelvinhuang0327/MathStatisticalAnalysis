"""Application-owned commands and read models for local draw data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    DrawCsvParseResult,
    IngestionItemDisposition,
    IngestionOperationType,
    IngestionRunStatus,
)

MAX_HISTORY_PAGE_SIZE = 100
MAX_INGESTION_ITEM_DETAILS = 500
DRAW_HISTORY_SORT = (
    "draw_date:desc",
    "draw_number:string_desc",
    "id:desc",
)
INGESTION_RUN_SORT = ("started_at:desc", "id:desc")


@dataclass(frozen=True, slots=True)
class DrawHistoryQuery:
    lottery_type: LotteryType | None = None
    draw_number: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = 1
    page_size: int = 25


@dataclass(frozen=True, slots=True)
class DrawRecord:
    internal_id: int
    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    normalized_record_hash: str
    source_name: str | None
    source_reference: str | None
    ingestion_run_id: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DrawHistoryPage:
    records: tuple[DrawRecord, ...]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    sort: tuple[str, ...] = DRAW_HISTORY_SORT


@dataclass(frozen=True, slots=True)
class IngestionRunQuery:
    status: IngestionRunStatus | None = None
    lottery_type: LotteryType | None = None
    page: int = 1
    page_size: int = 25


@dataclass(frozen=True, slots=True)
class IngestionRunRecord:
    run_id: str
    operation_type: IngestionOperationType
    status: IngestionRunStatus
    lottery_type: LotteryType | None
    source_filename: str
    source_sha256: str
    parser_version: str
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


@dataclass(frozen=True, slots=True)
class IngestionRunPage:
    records: tuple[IngestionRunRecord, ...]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    sort: tuple[str, ...] = INGESTION_RUN_SORT


@dataclass(frozen=True, slots=True)
class IngestionItemRecord:
    source_row_number: int
    lottery_type: LotteryType | None
    draw_number: str | None
    disposition: IngestionItemDisposition
    normalized_record_hash: str | None
    message: str | None


@dataclass(frozen=True, slots=True)
class IngestionRunDetail:
    run: IngestionRunRecord
    items: tuple[IngestionItemRecord, ...]
    item_count: int
    items_truncated: bool


@dataclass(frozen=True, slots=True)
class ImportCommitResult:
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

    @property
    def counts_are_consistent(self) -> bool:
        return self.total_count == (
            self.inserted_count
            + self.skipped_count
            + self.conflict_count
            + self.failed_count
        )


class DrawDataApplicationError(RuntimeError):
    """Base class for sanitized application failures."""


class DigestMismatchError(DrawDataApplicationError):
    """The commit content differs from the previewed content."""


class ParserVersionMismatchError(DrawDataApplicationError):
    """The client did not commit with the current parser version."""


class InvalidDrawImportError(DrawDataApplicationError):
    """Canonical parsing found at least one document or row error."""

    def __init__(self, result: DrawCsvParseResult) -> None:
        super().__init__("CSV validation failed")
        self.result = result


class ExistingDrawConflictError(DrawDataApplicationError):
    """At least one persisted draw differs from the submitted record."""

    def __init__(self, result: ImportCommitResult) -> None:
        super().__init__("Existing draw data conflicts with this import")
        self.result = result


class RepositoryBusyError(DrawDataApplicationError):
    """The bounded SQLite busy timeout elapsed."""


class RepositoryUnavailableError(DrawDataApplicationError):
    """Persistence failed without exposing storage internals."""
