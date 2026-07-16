"""Domain values shared by draw-import validation and persistence.

Lottery-specific validation remains explicit.  A syntactically normalized row is
not valid for import until its lottery has a proven rule contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from lottolab.domain.draws import LotteryType


class LotteryRuleStatus(StrEnum):
    """Whether LottoLab has committed evidence for a lottery's draw rules."""

    PROVEN = "PROVEN"
    UNKNOWN = "UNKNOWN"


class IngestionOperationType(StrEnum):
    """Stable operation identifiers stored in the local ingestion log."""

    DRAW_CSV_IMPORT = "DRAW_CSV_IMPORT"


class IngestionRunStatus(StrEnum):
    """Lifecycle states for one transactional ingestion attempt."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class IngestionItemDisposition(StrEnum):
    """Outcome for one normalized source row."""

    INSERTED = "INSERTED"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
    CONFLICT = "CONFLICT"
    FAILED = "FAILED"


class ConflictPolicy(StrEnum):
    """Import collision behavior supported by the current release."""

    REJECT = "REJECT"


class DrawImportErrorCode(StrEnum):
    """Stable machine-readable validation failures returned by import parsing."""

    EMPTY_FILE = "EMPTY_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_UTF8 = "INVALID_UTF8"
    MALFORMED_CSV = "MALFORMED_CSV"
    MISSING_REQUIRED_COLUMN = "MISSING_REQUIRED_COLUMN"
    DUPLICATE_HEADER = "DUPLICATE_HEADER"
    ROW_LIMIT_EXCEEDED = "ROW_LIMIT_EXCEEDED"
    COLUMN_COUNT_MISMATCH = "COLUMN_COUNT_MISMATCH"
    MISSING_REQUIRED_VALUE = "MISSING_REQUIRED_VALUE"
    UNSUPPORTED_LOTTERY_TYPE = "UNSUPPORTED_LOTTERY_TYPE"
    RULE_CONTRACT_UNKNOWN = "RULE_CONTRACT_UNKNOWN"
    INVALID_DRAW_NUMBER = "INVALID_DRAW_NUMBER"
    INVALID_DRAW_DATE = "INVALID_DRAW_DATE"
    INVALID_NUMBER = "INVALID_NUMBER"
    NUMBER_COUNT_MISMATCH = "NUMBER_COUNT_MISMATCH"
    NUMBER_OUT_OF_RANGE = "NUMBER_OUT_OF_RANGE"
    DUPLICATE_NUMBER = "DUPLICATE_NUMBER"
    MAIN_SPECIAL_OVERLAP = "MAIN_SPECIAL_OVERLAP"
    DUPLICATE_INPUT_ROW = "DUPLICATE_INPUT_ROW"
    CONFLICTING_INPUT_ROW = "CONFLICTING_INPUT_ROW"


@dataclass(frozen=True, slots=True)
class DrawImportError:
    """A document- or row-level import error with stable source coordinates."""

    code: DrawImportErrorCode
    message: str
    row_number: int | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedDrawInput:
    """A generic normalized row awaiting lottery-specific rule validation."""

    source_row_number: int
    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    source: str | None
    normalized_record_hash: str
    rule_status: LotteryRuleStatus


@dataclass(frozen=True, slots=True)
class DrawCsvParseResult:
    """Deterministic, DB-free result of parsing one canonical CSV document."""

    source_filename: str
    content_sha256: str
    parser_version: str
    total_rows: int
    blank_rows: int
    duplicate_input_rows: int
    conflicting_input_rows: int
    ignored_columns: tuple[str, ...]
    normalized_rows: tuple[NormalizedDrawInput, ...]
    errors: tuple[DrawImportError, ...]

    @property
    def validation_error_count(self) -> int:
        return len(self.errors)

    @property
    def valid_rows(self) -> int:
        """Count candidates without row errors; UNKNOWN rule rows never qualify."""

        document_error = any(error.row_number is None for error in self.errors)
        if document_error:
            return 0
        invalid_rows = {error.row_number for error in self.errors if error.row_number is not None}
        return sum(row.source_row_number not in invalid_rows for row in self.normalized_rows)

    @property
    def is_valid(self) -> bool:
        return not self.errors and self.valid_rows == len(self.normalized_rows)
