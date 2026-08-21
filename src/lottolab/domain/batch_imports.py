"""Immutable result models for legacy single- and multi-file draw imports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import DrawImportError, NormalizedDrawInput


class ImportFileStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    IMPORTED = "IMPORTED"
    PARTIAL = "PARTIAL"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    DUPLICATE = "DUPLICATE"
    CONFLICTED = "CONFLICTED"
    EXCLUDED = "EXCLUDED"
    INVALID = "INVALID"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ImportFilePayload:
    filename: str
    content: bytes


class ImportExclusionReason(StrEnum):
    UNSUPPORTED_EXTENSION = "UNSUPPORTED_EXTENSION"
    UNSUPPORTED_LOTTERY = "UNSUPPORTED_LOTTERY"
    BINGO_EXCLUDED = "BINGO_EXCLUDED"
    BIG_LOTTO_BONUS_EXCLUDED = "BIG_LOTTO_BONUS_EXCLUDED"
    DUPLICATE_ARCHIVE_MEMBER = "DUPLICATE_ARCHIVE_MEMBER"
    UNSAFE_ARCHIVE_MEMBER = "UNSAFE_ARCHIVE_MEMBER"
    CORRUPT_ARCHIVE = "CORRUPT_ARCHIVE"
    ARCHIVE_MEMBER_LIMIT_EXCEEDED = "ARCHIVE_MEMBER_LIMIT_EXCEEDED"
    FILE_SIZE_LIMIT_EXCEEDED = "FILE_SIZE_LIMIT_EXCEEDED"


@dataclass(frozen=True, slots=True)
class ImportIssue:
    code: str
    message: str
    row_number: int | None = None
    member_name: str | None = None


@dataclass(frozen=True, slots=True)
class ImportFileResult:
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
    imported_rows: int = 0
    issues: tuple[ImportIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportBatchSummary:
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


@dataclass(frozen=True, slots=True)
class BatchDrawImportPreview:
    source_filename: str
    manifest_sha256: str
    files: tuple[ImportFileResult, ...]
    normalized_rows: tuple[NormalizedDrawInput, ...]
    summary: ImportBatchSummary
    row_file_indexes: tuple[int, ...] = ()

    @property
    def is_valid(self) -> bool:
        return bool(self.normalized_rows) and all(
            file.status is not ImportFileStatus.FAILED for file in self.files
        )


@dataclass(frozen=True, slots=True)
class BatchDrawImportCommit:
    run_id: str | None
    status: Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED"]
    manifest_sha256: str
    summary: ImportBatchSummary
    files: tuple[ImportFileResult, ...]
    completed_at: str
    error_summary: str | None = None
    run_ids: tuple[str, ...] = ()
    committed_chunks: int = 0
    failed_chunks: int = 0


def summarize_import_files(
    files: tuple[ImportFileResult, ...] | list[ImportFileResult],
) -> ImportBatchSummary:
    """Build one truthful aggregate from preview or committed file outcomes."""

    return ImportBatchSummary(
        discovered_files=len(files),
        accepted_files=sum(file.accepted_rows > 0 for file in files),
        excluded_files=sum(file.status is ImportFileStatus.EXCLUDED for file in files),
        parsed_rows=sum(file.discovered_rows for file in files),
        accepted_rows=sum(file.accepted_rows for file in files),
        excluded_rows=sum(file.excluded_rows for file in files),
        duplicate_rows=sum(file.duplicate_rows for file in files),
        conflict_rows=sum(file.conflict_rows for file in files),
        imported_rows=sum(file.imported_rows for file in files),
        failed_rows=sum(file.failed_rows for file in files),
    )


def issues_from_errors(errors: tuple[DrawImportError, ...]) -> tuple[ImportIssue, ...]:
    return tuple(
        ImportIssue(
            code=error.code.value,
            message=error.message,
            row_number=error.row_number,
        )
        for error in errors
    )


__all__ = [
    "BatchDrawImportCommit",
    "BatchDrawImportPreview",
    "ImportBatchSummary",
    "ImportExclusionReason",
    "ImportFilePayload",
    "ImportFileResult",
    "ImportFileStatus",
    "ImportIssue",
    "issues_from_errors",
    "summarize_import_files",
]
