"""Stable result models for historical CSV/ZIP draw imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from lottolab.domain.historical_results import HistoricalLotteryType


class HistoricalImportFilter(StrEnum):
    ALL = "ALL"
    DAILY_539 = "DAILY_539"
    BIG_LOTTO = "BIG_LOTTO"
    POWER_LOTTO = "POWER_LOTTO"


class HistoricalImportDisposition(StrEnum):
    ACCEPTED = "ACCEPTED"
    EXCLUDED = "EXCLUDED"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    CONFLICT_REJECTED = "CONFLICT_REJECTED"
    FAILED = "FAILED"


class HistoricalImportFileStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    EXCLUDED = "EXCLUDED"
    FAILED = "FAILED"


class HistoricalImportBatchStatus(StrEnum):
    PREVIEW = "PREVIEW"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class HistoricalImportChunkStatus(StrEnum):
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"


class HistoricalImportReason(StrEnum):
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    EMPTY_FILE = "EMPTY_FILE"
    CORRUPT_ZIP = "CORRUPT_ZIP"
    UNSAFE_ARCHIVE_MEMBER = "UNSAFE_ARCHIVE_MEMBER"
    ENCRYPTED_ARCHIVE_MEMBER = "ENCRYPTED_ARCHIVE_MEMBER"
    BINGO_EXCLUDED = "BINGO_EXCLUDED"
    LOTTERY_FILTER_MISMATCH = "LOTTERY_FILTER_MISMATCH"
    UNKNOWN_GAME_TYPE = "UNKNOWN_GAME_TYPE"
    UNSUPPORTED_TARGET_LOTTERY = "UNSUPPORTED_TARGET_LOTTERY"
    UNSUPPORTED_BONUS_DRAW = "UNSUPPORTED_BONUS_DRAW"
    INVALID_DRAW_IDENTITY = "INVALID_DRAW_IDENTITY"
    INVALID_DRAW_DATE = "INVALID_DRAW_DATE"
    INVALID_NUMBER_COUNT = "INVALID_NUMBER_COUNT"
    INVALID_NUMBER_VALUE = "INVALID_NUMBER_VALUE"
    INVALID_NUMBER_RANGE = "INVALID_NUMBER_RANGE"
    DUPLICATE_NUMBER = "DUPLICATE_NUMBER"
    INVALID_SPECIAL_NUMBER = "INVALID_SPECIAL_NUMBER"
    INVALID_SECOND_NUMBER = "INVALID_SECOND_NUMBER"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    CONFLICT_REJECTED = "CONFLICT_REJECTED"
    PARSE_ERROR = "PARSE_ERROR"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"


@dataclass(frozen=True, slots=True)
class HistoricalImportInput:
    """One web-provided file; ``filename`` is display text, never a path."""

    filename: str
    content: bytes


@dataclass(frozen=True, slots=True)
class HistoricalDrawCandidate:
    """One structurally valid draw before duplicate/conflict resolution."""

    source_filename: str
    source_sha256: str
    member_path: str
    member_sha256: str | None
    source_row_number: int
    lottery_type: HistoricalLotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    normalized_record_hash: str


@dataclass(frozen=True, slots=True)
class ExistingHistoricalDraw:
    lottery_type: HistoricalLotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    normalized_record_hash: str
    historical_run_id: str


@dataclass(frozen=True, slots=True)
class HistoricalImportRowResult:
    source_filename: str
    source_sha256: str
    member_path: str
    member_sha256: str | None
    source_row_number: int | None
    lottery_type: HistoricalLotteryType | None
    draw_number: str | None
    disposition: HistoricalImportDisposition
    reason_code: HistoricalImportReason | None
    normalized_record_hash: str | None
    message: str | None
    historical_run_id: str | None = None
    draw_date: date | None = None
    main_numbers: tuple[int, ...] = ()
    special_numbers: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalImportFileResult:
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
    rows: tuple[HistoricalImportRowResult, ...]


@dataclass(frozen=True, slots=True)
class HistoricalImportChunkResult:
    chunk_index: int
    candidate_rows: int
    imported_rows: int
    failed_rows: int
    status: HistoricalImportChunkStatus
    historical_run_ids: tuple[str, ...]
    error_code: HistoricalImportReason | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalImportSummary:
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


@dataclass(frozen=True, slots=True)
class HistoricalImportResult:
    run_id: str | None
    status: HistoricalImportBatchStatus
    lottery_filter: HistoricalImportFilter
    files: tuple[HistoricalImportFileResult, ...]
    chunks: tuple[HistoricalImportChunkResult, ...]
    summary: HistoricalImportSummary
    row_results: tuple[HistoricalImportRowResult, ...]


@dataclass(frozen=True, slots=True)
class ImportRunStorage:
    """Storage identifiers returned after import metadata is created."""

    run_id: str
    file_ids: tuple[str, ...]
    row_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StoredImportRun:
    """Persisted import state reconstructed without exposing SQLite rows."""

    run_id: str
    status: HistoricalImportBatchStatus
    lottery_filter: HistoricalImportFilter
    import_identity_sha256: str
    files: tuple[HistoricalImportFileResult, ...]
    chunks: tuple[HistoricalImportChunkResult, ...]
    rows: tuple[HistoricalImportRowResult, ...]
