"""Immutable result models for legacy single- and multi-file draw imports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import DrawImportError, NormalizedDrawInput


class ImportFileStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    PARTIAL = "PARTIAL"
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

    @property
    def is_valid(self) -> bool:
        return bool(self.normalized_rows) and all(
            file.status is not ImportFileStatus.FAILED for file in self.files
        )


@dataclass(frozen=True, slots=True)
class BatchDrawImportCommit:
    run_id: str | None
    status: str
    manifest_sha256: str
    summary: ImportBatchSummary
    files: tuple[ImportFileResult, ...]
    completed_at: str
    error_summary: str | None = None


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
]
