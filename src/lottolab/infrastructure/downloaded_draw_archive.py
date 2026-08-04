"""Deterministic, read-only audit of downloaded lottery draw archives.

The auditor intentionally does not reuse the import or persistence paths.  A
download archive is evidence to inventory and reconcile, not an input to the
production database.  ZIP members are parsed in place, reference SQLite files
are opened with read-only immutable URIs, and all report serialization is
stable for identical inputs and arguments.
"""

from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast

REPORT_SCHEMA_VERSION = "lottery-download-archive-audit-v1"
POWER_LOTTO = "POWER_LOTTO"
DAILY_539 = "DAILY_539"
BIG_LOTTO = "BIG_LOTTO"

EXIT_OK = 0
EXIT_OPERATIONAL_ERROR = 2
EXIT_REFERENCE_CONFLICT = 3
EXIT_DATA_CONFLICT = 4
EXIT_FAIL_ON_CONFLICT = 5

_ASCII_INTEGER = re.compile(r"[0-9]+", flags=re.ASCII)
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", flags=re.ASCII)
_RAW_DATE_FORMATS = ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d")


class DatasetClassification(StrEnum):
    """Classification derived from member headers and row content."""

    POWER_LOTTO = POWER_LOTTO
    DAILY_539 = DAILY_539
    BIG_LOTTO = BIG_LOTTO
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ArchiveFile:
    """One regular file directly under the configured download root."""

    relative_path: str
    byte_size: int
    sha256: str
    detected_format: str
    integrity_status: str


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    """Inventory metadata for one ZIP member."""

    archive_path: str
    member_path: str
    uncompressed_byte_size: int
    compressed_byte_size: int
    crc32: int
    member_sha256: str | None
    detected_encoding: str | None
    classification: DatasetClassification
    row_count: int
    header_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuralIssue:
    """A deterministic, location-aware parsing or validation observation."""

    code: str
    message: str
    archive_path: str | None = None
    member_path: str | None = None
    row_number: int | None = None
    draw_identity: str | None = None
    severity: str = "ERROR"
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedDraw:
    """One retained draw row with raw and normalized values side by side."""

    archive_path: str
    member_path: str
    row_number: int
    classification: DatasetClassification
    raw_lottery_name: str
    raw_draw_identity: str
    raw_date_text: str
    draw_identity: str | None
    draw_date: str | None
    raw_zone1: tuple[str, ...]
    zone1: tuple[int, ...]
    raw_zone2: str | None
    zone2: int | None
    raw_fields: tuple[str, ...]
    issues: tuple[StructuralIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class ReconciliationMismatch:
    """One candidate/reference mismatch or candidate structural finding."""

    code: str
    archive_path: str | None
    member_path: str | None
    row_number: int | None
    draw_identity: str
    message: str
    candidate_date: str | None = None
    reference_date: str | None = None
    candidate_zone1: tuple[int, ...] = ()
    reference_zone1: tuple[int, ...] = ()
    candidate_zone2: int | None = None
    reference_zone2: int | None = None


@dataclass(frozen=True, slots=True)
class CandidateAuditResult:
    """POWER_LOTTO candidate facts used by reference reconciliation."""

    valid_powerlotto_rows: int
    unique_valid_draws: int
    duplicate_identities: int
    malformed_rows: int
    source_order_violations: int
    candidate_draws: tuple[ParsedDraw, ...]
    mismatches: tuple[ReconciliationMismatch, ...]
    first_draw_identity: str | None
    last_draw_identity: str | None


@dataclass(frozen=True, slots=True)
class ReferenceAuditResult:
    """Read-only source/target reference comparison facts."""

    source_row_count: int
    target_row_count: int
    source_draws: tuple[ParsedDraw, ...]
    target_draws: tuple[ParsedDraw, ...]
    semantic_conflicts: tuple[ReconciliationMismatch, ...]
    structural_issues: tuple[StructuralIssue, ...]
    semantically_identical: bool
    source_query_only: bool
    target_query_only: bool
    first_draw_identity: str | None
    last_draw_identity: str | None


@dataclass(frozen=True, slots=True)
class AuditSummary:
    """Complete deterministic audit result."""

    archive_files: tuple[ArchiveFile, ...]
    archive_members: tuple[ArchiveMember, ...]
    structural_issues: tuple[StructuralIssue, ...]
    classification_member_counts: Mapping[str, int]
    classification_row_counts: Mapping[str, int]
    candidate: CandidateAuditResult
    reference: ReferenceAuditResult
    root_archive_count: int
    total_zip_bytes: int
    csv_member_count: int
    non_csv_member_count: int
    duplicate_member_name_count: int
    duplicate_member_content_count: int
    identical_root_file_count: int
    unsafe_member_count: int
    corrupt_archive_count: int
    missing_reference_draw_ranges: tuple[str, ...]
    coverage_status: str
    source_authority_recommendation: str
    source_db_sha256_before: str | None
    source_db_sha256_after: str | None
    target_db_sha256_before: str | None
    target_db_sha256_after: str | None
    source_db_bytes_before: int | None
    source_db_bytes_after: int | None
    target_db_bytes_before: int | None
    target_db_bytes_after: int | None
    operational_errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ReferenceDraw:
    draw_identity: str
    draw_date: str
    zone1: tuple[int, ...]
    zone2: int


@dataclass(frozen=True, slots=True)
class _MemberParseResult:
    member: ArchiveMember
    draws: tuple[ParsedDraw, ...]
    issues: tuple[StructuralIssue, ...]
    corrupt: bool


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


class _ReadableBinary(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class ArchiveAuditError(RuntimeError):
    """An operational input or authority problem prevented an audit."""

    def __init__(self, message: str, *, code: str = "OPERATIONAL_ERROR") -> None:
        super().__init__(message)
        self.code = code


def _issue(
    code: str,
    message: str,
    *,
    archive_path: str | None = None,
    member_path: str | None = None,
    row_number: int | None = None,
    draw_identity: str | None = None,
    severity: str = "ERROR",
    details: Mapping[str, object] | None = None,
) -> StructuralIssue:
    detail_items = (
        () if details is None else tuple((key, str(details[key])) for key in sorted(details))
    )
    return StructuralIssue(
        code=code,
        message=message,
        archive_path=archive_path,
        member_path=member_path,
        row_number=row_number,
        draw_identity=draw_identity,
        severity=severity,
        details=detail_items,
    )


def sha256_file(path: Path) -> str:
    """Hash a file without creating a copy or loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path) -> tuple[str, int, str]:
    stat = path.stat()
    return str(path), stat.st_size, sha256_file(path)


def _issue_dict(issue: StructuralIssue) -> dict[str, object]:
    return {
        "archive_path": issue.archive_path,
        "code": issue.code,
        "details": dict(issue.details),
        "draw_identity": issue.draw_identity,
        "member_path": issue.member_path,
        "message": issue.message,
        "row_number": issue.row_number,
        "severity": issue.severity,
    }


def _mismatch_dict(mismatch: ReconciliationMismatch) -> dict[str, object]:
    return {
        "archive_path": mismatch.archive_path,
        "candidate_date": mismatch.candidate_date,
        "candidate_zone1": list(mismatch.candidate_zone1),
        "candidate_zone2": mismatch.candidate_zone2,
        "code": mismatch.code,
        "draw_identity": mismatch.draw_identity,
        "member_path": mismatch.member_path,
        "message": mismatch.message,
        "reference_date": mismatch.reference_date,
        "reference_zone1": list(mismatch.reference_zone1),
        "reference_zone2": mismatch.reference_zone2,
        "row_number": mismatch.row_number,
    }


def _archive_file_dict(item: ArchiveFile) -> dict[str, object]:
    return {
        "byte_size": item.byte_size,
        "detected_format": item.detected_format,
        "integrity_status": item.integrity_status,
        "relative_path": item.relative_path,
        "sha256": item.sha256,
    }


def _archive_member_dict(item: ArchiveMember) -> dict[str, object]:
    return {
        "archive_path": item.archive_path,
        "classification": item.classification.value,
        "compressed_byte_size": item.compressed_byte_size,
        "crc32": item.crc32,
        "detected_encoding": item.detected_encoding,
        "header_fields": list(item.header_fields),
        "member_path": item.member_path,
        "member_sha256": item.member_sha256,
        "row_count": item.row_count,
        "uncompressed_byte_size": item.uncompressed_byte_size,
    }


def summary_to_dict(summary: AuditSummary) -> dict[str, object]:
    """Convert an audit result into a stable JSON-ready mapping."""

    return {
        "archive_inventory": {
            "files": [_archive_file_dict(item) for item in summary.archive_files],
            "members": [_archive_member_dict(item) for item in summary.archive_members],
            "root_archive_count": summary.root_archive_count,
            "total_zip_bytes": summary.total_zip_bytes,
        },
        "classification": {
            "member_counts": dict(sorted(summary.classification_member_counts.items())),
            "row_counts": dict(sorted(summary.classification_row_counts.items())),
        },
        "coverage": {
            "candidate_valid_rows": summary.candidate.valid_powerlotto_rows,
            "coverage_status": summary.coverage_status,
            "first_candidate_draw": summary.candidate.first_draw_identity,
            "first_reference_draw": summary.reference.first_draw_identity,
            "last_candidate_draw": summary.candidate.last_draw_identity,
            "last_reference_draw": summary.reference.last_draw_identity,
            "missing_reference_draw_ranges": list(summary.missing_reference_draw_ranges),
            "reference_rows": summary.reference.source_row_count,
        },
        "database_invariance": {
            "source": {
                "bytes_after": summary.source_db_bytes_after,
                "bytes_before": summary.source_db_bytes_before,
                "sha256_after": summary.source_db_sha256_after,
                "sha256_before": summary.source_db_sha256_before,
            },
            "target": {
                "bytes_after": summary.target_db_bytes_after,
                "bytes_before": summary.target_db_bytes_before,
                "sha256_after": summary.target_db_sha256_after,
                "sha256_before": summary.target_db_sha256_before,
            },
        },
        "issues": [_issue_dict(issue) for issue in summary.structural_issues],
        "operational_errors": list(summary.operational_errors),
        "recommendation": summary.source_authority_recommendation,
        "reference": {
            "semantic_conflicts": [
                _mismatch_dict(item) for item in summary.reference.semantic_conflicts
            ],
            "semantically_identical": summary.reference.semantically_identical,
            "source_query_only": summary.reference.source_query_only,
            "source_row_count": summary.reference.source_row_count,
            "structural_issues": [
                _issue_dict(issue) for issue in summary.reference.structural_issues
            ],
            "target_query_only": summary.reference.target_query_only,
            "target_row_count": summary.reference.target_row_count,
        },
        "reconciliation": {
            "candidate": {
                "duplicate_identities": summary.candidate.duplicate_identities,
                "malformed_rows": summary.candidate.malformed_rows,
                "source_order_violations": summary.candidate.source_order_violations,
                "unique_valid_draws": summary.candidate.unique_valid_draws,
                "valid_powerlotto_rows": summary.candidate.valid_powerlotto_rows,
            },
            "mismatch_counts": dict(
                sorted(Counter(item.code for item in summary.candidate.mismatches).items())
            ),
            "mismatches": [_mismatch_dict(item) for item in summary.candidate.mismatches],
        },
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary_counts": {
            "corrupt_archive_count": summary.corrupt_archive_count,
            "csv_member_count": summary.csv_member_count,
            "duplicate_member_content_count": summary.duplicate_member_content_count,
            "duplicate_member_name_count": summary.duplicate_member_name_count,
            "identical_root_file_count": summary.identical_root_file_count,
            "non_csv_member_count": summary.non_csv_member_count,
            "unsafe_member_count": summary.unsafe_member_count,
        },
    }


class _DigestReader(io.RawIOBase):
    def __init__(self, source: _ReadableBinary, digest: _Digest) -> None:
        super().__init__()
        self._source = source
        self._digest = digest

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        data = self._source.read(size)
        if data:
            self._digest.update(data)
        return data

    def readinto(self, buffer: Any) -> int | None:  # type: ignore[override]
        data = self.read(len(buffer))
        if not data:
            return 0
        buffer[: len(data)] = data
        return len(data)


class _ReplayReader(io.RawIOBase):
    def __init__(self, prefix: bytes, source: _ReadableBinary) -> None:
        super().__init__()
        self._prefix = prefix
        self._position = 0
        self._source = source

    def readable(self) -> bool:
        return True

    def _remaining_prefix(self) -> bytes:
        return self._prefix[self._position :]

    def read(self, size: int = -1) -> bytes:
        prefix = self._remaining_prefix()
        if size == 0:
            return b""
        if size < 0:
            self._position = len(self._prefix)
            return prefix + self._source.read()
        if prefix:
            take = min(size, len(prefix))
            self._position += take
            if take == size:
                return self._prefix[self._position - take : self._position]
            return self._prefix[self._position - take : self._position] + self._source.read(
                size - take
            )
        return self._source.read(size)

    def readinto(self, buffer: Any) -> int | None:  # type: ignore[override]
        data = self.read(len(buffer))
        if not data:
            return 0
        buffer[: len(data)] = data
        return len(data)


def _safe_member_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not path.is_absolute() and ".." not in path.parts


def _is_blank_row(row: Sequence[str]) -> bool:
    return not row or not any(value.strip() for value in row)


def _normalized_header(value: str) -> str:
    return value.strip().casefold()


def _known_header(header: str) -> bool:
    normalized = _normalized_header(header)
    if normalized in {
        "遊戲名稱",
        "活動名稱",
        "期別",
        "開獎日期",
        "銷售總額",
        "銷售注數",
        "總獎金",
        "特別號",
        "第二區",
        "超級獎號",
        "猜大小",
        "猜單雙",
    }:
        return True
    return bool(re.fullmatch(r"獎號[0-9]+", normalized))


def _find_header(headers: Sequence[str], names: set[str]) -> int | None:
    for index, header in enumerate(headers):
        if _normalized_header(header) in names:
            return index
    return None


def _find_main_headers(headers: Sequence[str], count: int) -> tuple[int, ...]:
    indexes: list[int] = []
    for number in range(1, count + 1):
        index = _find_header(headers, {f"獎號{number}"})
        if index is None:
            return ()
        indexes.append(index)
    return tuple(indexes)


def _classify_dataset(raw_name: str, headers: Sequence[str]) -> DatasetClassification:
    name = raw_name.strip().casefold()
    has_core = (
        _find_header(headers, {"遊戲名稱", "活動名稱"}) is not None
        and _find_header(headers, {"期別"}) is not None
        and _find_header(headers, {"開獎日期"}) is not None
    )
    if not has_core:
        return DatasetClassification.UNKNOWN
    if name in {"威力彩", "power_lotto", "power lotto", "super lotto 638"} and (
        _find_main_headers(headers, 6) and _find_header(headers, {"第二區", "第二區號"}) is not None
    ):
        return DatasetClassification.POWER_LOTTO
    if name in {"今彩539", "daily_539", "daily 539"} and _find_main_headers(headers, 5):
        return DatasetClassification.DAILY_539
    if name in {"大樂透", "big_lotto", "big lotto"} and (
        _find_main_headers(headers, 6) and _find_header(headers, {"特別號", "特別號碼"}) is not None
    ):
        return DatasetClassification.BIG_LOTTO
    return DatasetClassification.OTHER if raw_name.strip() else DatasetClassification.UNKNOWN


def _parse_date(raw: str) -> tuple[str | None, bool]:
    value = raw.strip()
    for fmt in _RAW_DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt).date()
        except ValueError:
            continue
        return parsed.isoformat(), True
    return None, False


def _parse_exact_integer(raw: str) -> int | None:
    value = raw.strip()
    if _ASCII_INTEGER.fullmatch(value) is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_draw_row(
    row: tuple[str, ...],
    *,
    archive_path: str,
    member_path: str,
    row_number: int,
    classification: DatasetClassification,
    headers: tuple[str, ...],
    unknown_columns_reported: set[str],
) -> ParsedDraw:
    game_index = _find_header(headers, {"遊戲名稱", "活動名稱"})
    identity_index = _find_header(headers, {"期別"})
    date_index = _find_header(headers, {"開獎日期"})
    raw_game = row[game_index] if game_index is not None and game_index < len(row) else ""
    raw_identity = (
        row[identity_index] if identity_index is not None and identity_index < len(row) else ""
    )
    raw_date = row[date_index] if date_index is not None and date_index < len(row) else ""
    issues: list[StructuralIssue] = []

    identity = raw_identity.strip() or None
    if identity is None or _ASCII_INTEGER.fullmatch(identity) is None:
        issues.append(
            _issue(
                "INVALID_DRAW_IDENTITY",
                "draw identity must be a non-empty ASCII decimal string",
                archive_path=archive_path,
                member_path=member_path,
                row_number=row_number,
                draw_identity=identity,
            )
        )

    normalized_date, valid_date = _parse_date(raw_date)
    if not valid_date:
        issues.append(
            _issue(
                "INVALID_DRAW_DATE",
                "draw date must use an explicit supported Gregorian format",
                archive_path=archive_path,
                member_path=member_path,
                row_number=row_number,
                draw_identity=identity,
            )
        )

    expected_main_count = {
        DatasetClassification.POWER_LOTTO: 6,
        DatasetClassification.DAILY_539: 5,
        DatasetClassification.BIG_LOTTO: 6,
    }.get(classification)
    main_indexes = (
        _find_main_headers(headers, expected_main_count) if expected_main_count is not None else ()
    )
    raw_zone1 = tuple(row[index].strip() if index < len(row) else "" for index in main_indexes)
    zone1_values: list[int] = []
    for position, raw_value in enumerate(raw_zone1, start=1):
        parsed = _parse_exact_integer(raw_value)
        if parsed is None:
            issues.append(
                _issue(
                    "INVALID_INTEGER",
                    f"zone-1 value {position} must be an exact ASCII integer",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                    details={"field": "zone1", "position": position},
                )
            )
        else:
            zone1_values.append(parsed)

    special_index = _find_header(headers, {"第二區", "第二區號", "特別號", "特別號碼"})
    raw_zone2 = (
        row[special_index].strip()
        if special_index is not None and special_index < len(row)
        else None
    )
    zone2 = _parse_exact_integer(raw_zone2) if raw_zone2 is not None and raw_zone2 else None
    if classification is DatasetClassification.POWER_LOTTO:
        if special_index is None or not raw_zone2:
            issues.append(
                _issue(
                    "MISSING_ZONE2",
                    "POWER_LOTTO requires exactly one zone-2 value",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        elif zone2 is None:
            issues.append(
                _issue(
                    "INVALID_INTEGER",
                    "zone-2 value must be an exact ASCII integer",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                    details={"field": "zone2"},
                )
            )
    elif classification is DatasetClassification.DAILY_539 and raw_zone2:
        issues.append(
            _issue(
                "UNEXPECTED_ZONE2",
                "DAILY_539 must not carry a second-zone value",
                archive_path=archive_path,
                member_path=member_path,
                row_number=row_number,
                draw_identity=identity,
            )
        )

    if expected_main_count is not None and len(main_indexes) != expected_main_count:
        issues.append(
            _issue(
                "MISSING_MAIN_NUMBER_COLUMNS",
                f"{classification.value} does not expose its required number columns",
                archive_path=archive_path,
                member_path=member_path,
                row_number=row_number,
                draw_identity=identity,
            )
        )

    if classification is DatasetClassification.POWER_LOTTO:
        if any(value < 1 or value > 38 for value in zone1_values):
            issues.append(
                _issue(
                    "ZONE1_OUT_OF_RANGE",
                    "POWER_LOTTO zone-1 values must be between 1 and 38",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        if len(zone1_values) == 6 and len(set(zone1_values)) != 6:
            issues.append(
                _issue(
                    "DUPLICATE_ZONE1_VALUE",
                    "POWER_LOTTO zone-1 values must be unique",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        if len(zone1_values) == 6 and tuple(zone1_values) != tuple(sorted(zone1_values)):
            issues.append(
                _issue(
                    "SOURCE_ORDER_VIOLATION",
                    "source zone-1 order differs from ascending canonical order",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                    severity="WARNING",
                )
            )
        if zone2 is not None and not 1 <= zone2 <= 8:
            issues.append(
                _issue(
                    "ZONE2_OUT_OF_RANGE",
                    "POWER_LOTTO zone-2 value must be between 1 and 8",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
    elif classification is DatasetClassification.DAILY_539:
        if any(value < 1 or value > 39 for value in zone1_values):
            issues.append(
                _issue(
                    "ZONE1_OUT_OF_RANGE",
                    "DAILY_539 values must be between 1 and 39",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        if len(zone1_values) == 5 and len(set(zone1_values)) != 5:
            issues.append(
                _issue(
                    "DUPLICATE_ZONE1_VALUE",
                    "DAILY_539 values must be unique",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
    elif classification is DatasetClassification.BIG_LOTTO:
        if any(value < 1 or value > 49 for value in zone1_values):
            issues.append(
                _issue(
                    "ZONE1_OUT_OF_RANGE",
                    "BIG_LOTTO values must be between 1 and 49",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        if len(zone1_values) == 6 and len(set(zone1_values)) != 6:
            issues.append(
                _issue(
                    "DUPLICATE_ZONE1_VALUE",
                    "BIG_LOTTO values must be unique",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        if zone2 is None:
            issues.append(
                _issue(
                    "MISSING_SPECIAL_NUMBER",
                    "BIG_LOTTO requires exactly one special number",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        elif not 1 <= zone2 <= 49:
            issues.append(
                _issue(
                    "SPECIAL_NUMBER_OUT_OF_RANGE",
                    "BIG_LOTTO special number must be between 1 and 49",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )
        if zone2 is not None and zone2 in zone1_values:
            issues.append(
                _issue(
                    "SPECIAL_NUMBER_OVERLAP",
                    "BIG_LOTTO special number must not overlap zone 1",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                )
            )

    known_indexes = {index for index, header in enumerate(headers) if _known_header(header)}
    for index, header in enumerate(headers):
        if index in known_indexes or not header.strip():
            continue
        value = row[index].strip() if index < len(row) else ""
        if value and header not in unknown_columns_reported:
            unknown_columns_reported.add(header)
            issues.append(
                _issue(
                    "UNKNOWN_NON_EMPTY_COLUMN",
                    "non-empty data was retained under an unknown header",
                    archive_path=archive_path,
                    member_path=member_path,
                    row_number=row_number,
                    draw_identity=identity,
                    severity="WARNING",
                    details={"header": header},
                )
            )
    if len(row) > len(headers) and any(value.strip() for value in row[len(headers) :]):
        issues.append(
            _issue(
                "EXTRA_NON_EMPTY_FIELDS",
                "row contains non-empty fields beyond the declared header",
                archive_path=archive_path,
                member_path=member_path,
                row_number=row_number,
                draw_identity=identity,
            )
        )

    return ParsedDraw(
        archive_path=archive_path,
        member_path=member_path,
        row_number=row_number,
        classification=classification,
        raw_lottery_name=raw_game,
        raw_draw_identity=raw_identity,
        raw_date_text=raw_date,
        draw_identity=identity,
        draw_date=normalized_date,
        raw_zone1=raw_zone1,
        zone1=tuple(zone1_values),
        raw_zone2=raw_zone2,
        zone2=zone2,
        raw_fields=row,
        issues=tuple(issues),
    )


def _parse_csv_member(
    raw_member: _ReadableBinary,
    *,
    archive_path: str,
    member_path: str,
    uncompressed_size: int,
    compressed_size: int,
    crc32: int,
) -> _MemberParseResult:
    digest = hashlib.sha256()
    digest_reader = _DigestReader(raw_member, digest)
    prefix = digest_reader.read(3)
    replay_reader = _ReplayReader(prefix, digest_reader)
    encoding = "UTF-8 with BOM" if prefix == b"\xef\xbb\xbf" else "UTF-8"
    issues: list[StructuralIssue] = []
    draws: list[ParsedDraw] = []
    headers: tuple[str, ...] = ()
    classification = DatasetClassification.UNKNOWN
    row_count = 0
    blank_rows = 0
    unknown_columns_reported: set[str] = set()
    buffered_reader = io.BufferedReader(replay_reader)
    text_stream = io.TextIOWrapper(
        buffered_reader,
        encoding="utf-8-sig",
        errors="strict",
        newline="",
    )
    try:
        reader = csv.reader(text_stream)
        try:
            raw_header = next(reader)
        except StopIteration:
            issues.append(
                _issue(
                    "EMPTY_CSV",
                    "CSV member has no header row",
                    archive_path=archive_path,
                    member_path=member_path,
                )
            )
            raw_header = []
        headers = tuple(value.strip() for value in raw_header)
        while headers and not headers[-1]:
            headers = headers[:-1]
            issues.append(
                _issue(
                    "TRAILING_EMPTY_HEADER_COLUMN",
                    "legacy trailing empty header column tolerated",
                    archive_path=archive_path,
                    member_path=member_path,
                    severity="WARNING",
                )
            )
        normalized_headers = tuple(_normalized_header(value) for value in headers)
        duplicate_headers = sorted(
            {value for value in normalized_headers if normalized_headers.count(value) > 1 and value}
        )
        if duplicate_headers:
            issues.append(
                _issue(
                    "DUPLICATE_HEADER",
                    "CSV header contains duplicate normalized names",
                    archive_path=archive_path,
                    member_path=member_path,
                    details={"headers": ",".join(duplicate_headers)},
                )
            )
        if not headers:
            return _finish_member(
                archive_path=archive_path,
                member_path=member_path,
                uncompressed_size=uncompressed_size,
                compressed_size=compressed_size,
                crc32=crc32,
                digest=digest,
                encoding=encoding,
                classification=classification,
                row_count=row_count,
                headers=headers,
                draws=draws,
                issues=issues,
            )

        for row_number, raw_row in enumerate(reader, start=2):
            row = tuple(raw_row)
            if _is_blank_row(row):
                blank_rows += 1
                continue
            row_count += 1
            game_index = _find_header(headers, {"遊戲名稱", "活動名稱"})
            raw_game = row[game_index] if game_index is not None and game_index < len(row) else ""
            row_classification = _classify_dataset(raw_game, headers)
            if classification is DatasetClassification.UNKNOWN and (
                row_classification is not DatasetClassification.UNKNOWN or raw_game.strip()
            ):
                classification = row_classification
            elif (
                row_classification is not classification
                and row_classification is not DatasetClassification.UNKNOWN
            ):
                issues.append(
                    _issue(
                        "MIXED_LOTTERY_CLASSIFICATION",
                        "one CSV member contains multiple recognized lottery names",
                        archive_path=archive_path,
                        member_path=member_path,
                        row_number=row_number,
                        severity="WARNING",
                        details={"row_classification": row_classification.value},
                    )
                )
            parsed = _parse_draw_row(
                row,
                archive_path=archive_path,
                member_path=member_path,
                row_number=row_number,
                classification=classification,
                headers=headers,
                unknown_columns_reported=unknown_columns_reported,
            )
            if classification in {
                DatasetClassification.POWER_LOTTO,
                DatasetClassification.DAILY_539,
                DatasetClassification.BIG_LOTTO,
            }:
                draws.append(parsed)
            issues.extend(parsed.issues)
        if blank_rows:
            issues.append(
                _issue(
                    "BLANK_ROWS_IGNORED",
                    "blank CSV rows were ignored",
                    archive_path=archive_path,
                    member_path=member_path,
                    severity="WARNING",
                    details={"count": blank_rows},
                )
            )
    except UnicodeDecodeError as exc:
        issues.append(
            _issue(
                "UNSUPPORTED_ENCODING",
                "CSV member is not valid UTF-8 or UTF-8 with BOM",
                archive_path=archive_path,
                member_path=member_path,
                details={"error": str(exc)},
            )
        )
    except csv.Error as exc:
        issues.append(
            _issue(
                "CSV_PARSE_ERROR",
                "CSV parser rejected the member",
                archive_path=archive_path,
                member_path=member_path,
                details={"error": str(exc)},
            )
        )
    finally:
        with suppress(ValueError):
            text_stream.detach()
        digest_reader.read()
    return _finish_member(
        archive_path=archive_path,
        member_path=member_path,
        uncompressed_size=uncompressed_size,
        compressed_size=compressed_size,
        crc32=crc32,
        digest=digest,
        encoding=encoding,
        classification=classification,
        row_count=row_count,
        headers=headers,
        draws=draws,
        issues=issues,
    )


def parse_csv_bytes(
    content: bytes,
    *,
    archive_path: str = "fixture.zip",
    member_path: str = "fixture.csv",
) -> tuple[ArchiveMember, tuple[ParsedDraw, ...], tuple[StructuralIssue, ...]]:
    """Parse one in-memory CSV for focused tests and small callers.

    The production archive path uses :func:`_parse_csv_member` directly on a
    ``ZipExtFile``.  This helper keeps tests independent from archive creation
    while preserving the same decoder, validator, and issue model.
    """

    result = _parse_csv_member(
        io.BytesIO(content),
        archive_path=archive_path,
        member_path=member_path,
        uncompressed_size=len(content),
        compressed_size=len(content),
        crc32=binascii.crc32(content) & 0xFFFFFFFF,
    )
    return result.member, result.draws, result.issues


def _finish_member(
    *,
    archive_path: str,
    member_path: str,
    uncompressed_size: int,
    compressed_size: int,
    crc32: int,
    digest: _Digest,
    encoding: str | None,
    classification: DatasetClassification,
    row_count: int,
    headers: tuple[str, ...],
    draws: Sequence[ParsedDraw],
    issues: Sequence[StructuralIssue],
) -> _MemberParseResult:
    return _MemberParseResult(
        member=ArchiveMember(
            archive_path=archive_path,
            member_path=member_path,
            uncompressed_byte_size=uncompressed_size,
            compressed_byte_size=compressed_size,
            crc32=crc32,
            member_sha256=digest.hexdigest(),
            detected_encoding=encoding,
            classification=classification,
            row_count=row_count,
            header_fields=headers,
        ),
        draws=tuple(draws),
        issues=tuple(issues),
        corrupt=False,
    )


def _hash_member(raw_member: _ReadableBinary) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: raw_member.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _parse_zip_file(
    path: Path,
    *,
    relative_path: str,
) -> tuple[tuple[ArchiveMember, ...], tuple[ParsedDraw, ...], tuple[StructuralIssue, ...], bool]:
    members: list[ArchiveMember] = []
    draws: list[ParsedDraw] = []
    issues: list[StructuralIssue] = []
    corrupt = False
    seen_names: set[str] = set()
    try:
        with zipfile.ZipFile(path, "r") as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                member_path = info.filename
                if member_path in seen_names:
                    issues.append(
                        _issue(
                            "DUPLICATE_MEMBER_NAME",
                            "ZIP archive contains duplicate member names",
                            archive_path=relative_path,
                            member_path=member_path,
                        )
                    )
                seen_names.add(member_path)
                if not _safe_member_name(member_path):
                    issues.append(
                        _issue(
                            "UNSAFE_MEMBER_PATH",
                            "unsafe ZIP member path was not opened or extracted",
                            archive_path=relative_path,
                            member_path=member_path,
                        )
                    )
                    members.append(
                        ArchiveMember(
                            archive_path=relative_path,
                            member_path=member_path,
                            uncompressed_byte_size=info.file_size,
                            compressed_byte_size=info.compress_size,
                            crc32=info.CRC,
                            member_sha256=None,
                            detected_encoding=None,
                            classification=DatasetClassification.UNKNOWN,
                            row_count=0,
                            header_fields=(),
                        )
                    )
                    continue
                if info.flag_bits & 0x1:
                    issues.append(
                        _issue(
                            "ENCRYPTED_MEMBER",
                            "encrypted ZIP member is unsupported and was not opened",
                            archive_path=relative_path,
                            member_path=member_path,
                        )
                    )
                    corrupt = True
                    members.append(
                        ArchiveMember(
                            archive_path=relative_path,
                            member_path=member_path,
                            uncompressed_byte_size=info.file_size,
                            compressed_byte_size=info.compress_size,
                            crc32=info.CRC,
                            member_sha256=None,
                            detected_encoding=None,
                            classification=DatasetClassification.UNKNOWN,
                            row_count=0,
                            header_fields=(),
                        )
                    )
                    continue
                try:
                    if info.is_dir():
                        member_hash = hashlib.sha256(b"").hexdigest()
                        members.append(
                            ArchiveMember(
                                archive_path=relative_path,
                                member_path=member_path,
                                uncompressed_byte_size=info.file_size,
                                compressed_byte_size=info.compress_size,
                                crc32=info.CRC,
                                member_sha256=member_hash,
                                detected_encoding=None,
                                classification=DatasetClassification.UNKNOWN,
                                row_count=0,
                                header_fields=(),
                            )
                        )
                        continue
                    with archive.open(info, "r") as raw_member:
                        if member_path.casefold().endswith(".csv"):
                            result = _parse_csv_member(
                                raw_member,
                                archive_path=relative_path,
                                member_path=member_path,
                                uncompressed_size=info.file_size,
                                compressed_size=info.compress_size,
                                crc32=info.CRC,
                            )
                        else:
                            member_hash = _hash_member(raw_member)
                            result = _MemberParseResult(
                                member=ArchiveMember(
                                    archive_path=relative_path,
                                    member_path=member_path,
                                    uncompressed_byte_size=info.file_size,
                                    compressed_byte_size=info.compress_size,
                                    crc32=info.CRC,
                                    member_sha256=member_hash,
                                    detected_encoding=None,
                                    classification=DatasetClassification.UNKNOWN,
                                    row_count=0,
                                    header_fields=(),
                                ),
                                draws=(),
                                issues=(),
                                corrupt=False,
                            )
                    members.append(result.member)
                    draws.extend(result.draws)
                    issues.extend(result.issues)
                except (NotImplementedError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
                    corrupt = True
                    issues.append(
                        _issue(
                            "CORRUPT_OR_UNSUPPORTED_MEMBER",
                            "ZIP member could not be read completely",
                            archive_path=relative_path,
                            member_path=member_path,
                            details={"error": str(exc)},
                        )
                    )
                    members.append(
                        ArchiveMember(
                            archive_path=relative_path,
                            member_path=member_path,
                            uncompressed_byte_size=info.file_size,
                            compressed_byte_size=info.compress_size,
                            crc32=info.CRC,
                            member_sha256=None,
                            detected_encoding=None,
                            classification=DatasetClassification.UNKNOWN,
                            row_count=0,
                            header_fields=(),
                        )
                    )
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        corrupt = True
        issues.append(
            _issue(
                "CORRUPT_ZIP_ARCHIVE",
                "ZIP archive could not be opened or enumerated",
                archive_path=relative_path,
                details={"error": str(exc)},
            )
        )
    return tuple(members), tuple(draws), tuple(issues), corrupt


def _inventory_download_root(
    download_root: Path,
) -> tuple[
    tuple[ArchiveFile, ...],
    tuple[ArchiveMember, ...],
    tuple[ParsedDraw, ...],
    tuple[StructuralIssue, ...],
    int,
    int,
    int,
    int,
    int,
    int,
]:
    root = download_root.resolve()
    if not root.is_dir():
        raise ArchiveAuditError(f"download root does not exist: {download_root}")
    archive_files: list[ArchiveFile] = []
    archive_members: list[ArchiveMember] = []
    candidate_draws: list[ParsedDraw] = []
    issues: list[StructuralIssue] = []
    zip_bytes = 0
    root_archive_count = 0
    corrupt_count = 0
    unsafe_count = 0
    duplicate_name_count = 0
    regular_files = sorted(
        (item for item in root.iterdir() if item.is_file() and not item.is_symlink()),
        key=lambda item: item.name,
    )
    identities: list[tuple[str, int, str]] = []
    for path in regular_files:
        relative = path.relative_to(root).as_posix()
        source, byte_size, digest = _file_identity(path)
        del source
        identities.append((relative, byte_size, digest))
        is_zip_name = path.suffix.casefold() == ".zip"
        is_zip = zipfile.is_zipfile(path)
        if is_zip:
            detected_format = "ZIP"
            integrity = "VALID"
            root_archive_count += 1
            zip_bytes += byte_size
            members, draws, zip_issues, corrupt = _parse_zip_file(path, relative_path=relative)
            archive_members.extend(members)
            candidate_draws.extend(draws)
            issues.extend(zip_issues)
            if corrupt:
                integrity = "CORRUPT"
                corrupt_count += 1
        elif is_zip_name:
            detected_format = "CORRUPT_ZIP"
            integrity = "CORRUPT"
            corrupt_count += 1
            issues.append(
                _issue(
                    "CORRUPT_ZIP_ARCHIVE",
                    "file has a .zip suffix but is not a readable ZIP archive",
                    archive_path=relative,
                )
            )
        else:
            detected_format = "NON_ZIP"
            integrity = "NOT_APPLICABLE"
        archive_files.append(
            ArchiveFile(
                relative_path=relative,
                byte_size=byte_size,
                sha256=digest,
                detected_format=detected_format,
                integrity_status=integrity,
            )
        )
    for relative, byte_size, digest in identities:
        same = [item[0] for item in identities if item[2] == digest]
        if len(same) > 1:
            issues.append(
                _issue(
                    "IDENTICAL_ROOT_FILES",
                    "root files have identical bytes",
                    archive_path=relative,
                    severity="WARNING",
                    details={"paths": ",".join(sorted(same)), "byte_size": byte_size},
                )
            )
    member_name_counts = Counter((item.archive_path, item.member_path) for item in archive_members)
    duplicate_name_count = sum(1 for count in member_name_counts.values() if count > 1)
    for (archive_path, member_path), count in sorted(member_name_counts.items()):
        if count > 1:
            issues.append(
                _issue(
                    "DUPLICATE_MEMBER_NAME",
                    "duplicate member name was retained in inventory",
                    archive_path=archive_path,
                    member_path=member_path,
                    details={"count": count},
                )
            )
    for item in archive_members:
        if any(
            issue.archive_path == item.archive_path
            and issue.member_path == item.member_path
            and issue.code == "UNSAFE_MEMBER_PATH"
            for issue in issues
        ):
            unsafe_count += 1
    member_hash_groups: dict[str, list[str]] = defaultdict(list)
    for item in archive_members:
        if item.member_sha256 is not None and not item.member_path.endswith("/"):
            member_hash_groups[item.member_sha256].append(f"{item.archive_path}:{item.member_path}")
    duplicate_content_count = 0
    for digest, paths in sorted(member_hash_groups.items()):
        if len(paths) > 1:
            duplicate_content_count += 1
            issues.append(
                _issue(
                    "IDENTICAL_MEMBER_CONTENTS",
                    "ZIP members have identical bytes",
                    severity="WARNING",
                    details={"sha256": digest, "paths": ",".join(sorted(paths))},
                )
            )
    csv_member_count = sum(
        1 for item in archive_members if item.member_path.casefold().endswith(".csv")
    )
    non_csv_member_count = len(archive_members) - csv_member_count
    return (
        tuple(sorted(archive_files, key=lambda item: item.relative_path)),
        tuple(sorted(archive_members, key=lambda item: (item.archive_path, item.member_path))),
        tuple(candidate_draws),
        tuple(issues),
        root_archive_count,
        zip_bytes,
        csv_member_count,
        non_csv_member_count,
        duplicate_name_count,
        duplicate_content_count,
    )


def _read_only_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ArchiveAuditError(f"reference database does not exist: {path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    query_only = int(connection.execute("PRAGMA query_only").fetchone()[0])
    if query_only != 1:
        connection.close()
        raise ArchiveAuditError(f"reference database is not query-only: {path}")
    return connection


def _reference_issue(
    code: str, message: str, *, details: Mapping[str, object] | None = None
) -> StructuralIssue:
    return _issue(code, message, details=details)


def _valid_reference_draw(
    draw: _ReferenceDraw,
    *,
    source_name: str,
) -> StructuralIssue | None:
    if not draw.draw_identity or _ASCII_INTEGER.fullmatch(draw.draw_identity) is None:
        return _reference_issue(
            "INVALID_REFERENCE_DRAW_IDENTITY",
            f"{source_name} reference draw identity is not an ASCII decimal string",
            details={"draw_identity": draw.draw_identity},
        )
    if _ISO_DATE.fullmatch(draw.draw_date) is None:
        return _reference_issue(
            "INVALID_REFERENCE_DRAW_DATE",
            f"{source_name} reference date is not ISO YYYY-MM-DD",
            details={"draw_identity": draw.draw_identity, "draw_date": draw.draw_date},
        )
    try:
        date.fromisoformat(draw.draw_date)
    except ValueError:
        return _reference_issue(
            "INVALID_REFERENCE_DRAW_DATE",
            f"{source_name} reference date is not a valid calendar date",
            details={"draw_identity": draw.draw_identity, "draw_date": draw.draw_date},
        )
    if len(draw.zone1) != 6 or any(value < 1 or value > 38 for value in draw.zone1):
        return _reference_issue(
            "INVALID_REFERENCE_ZONE1",
            f"{source_name} reference zone-1 values violate POWER_LOTTO rules",
            details={"draw_identity": draw.draw_identity, "zone1": draw.zone1},
        )
    if len(set(draw.zone1)) != 6:
        return _reference_issue(
            "DUPLICATE_REFERENCE_ZONE1",
            f"{source_name} reference zone-1 values are not unique",
            details={"draw_identity": draw.draw_identity},
        )
    if not 1 <= draw.zone2 <= 8:
        return _reference_issue(
            "INVALID_REFERENCE_ZONE2",
            f"{source_name} reference zone-2 value violates POWER_LOTTO rules",
            details={"draw_identity": draw.draw_identity, "zone2": draw.zone2},
        )
    return None


def _reference_draw_to_parsed(draw: _ReferenceDraw, source_name: str) -> ParsedDraw:
    return ParsedDraw(
        archive_path=source_name,
        member_path=source_name,
        row_number=0,
        classification=DatasetClassification.POWER_LOTTO,
        raw_lottery_name=POWER_LOTTO,
        raw_draw_identity=draw.draw_identity,
        raw_date_text=draw.draw_date,
        draw_identity=draw.draw_identity,
        draw_date=draw.draw_date,
        raw_zone1=tuple(str(value) for value in draw.zone1),
        zone1=draw.zone1,
        raw_zone2=str(draw.zone2),
        zone2=draw.zone2,
        raw_fields=(),
    )


def _read_source_reference(
    path: Path,
) -> tuple[tuple[_ReferenceDraw, ...], tuple[StructuralIssue, ...], bool]:
    issues: list[StructuralIssue] = []
    draws: list[_ReferenceDraw] = []
    try:
        connection = _read_only_connection(path)
    except (ArchiveAuditError, sqlite3.Error) as exc:
        return (), (_reference_issue("REFERENCE_SOURCE_OPEN_ERROR", str(exc)),), False
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if not {"draws", "run_metadata"}.issubset(tables):
            issues.append(
                _reference_issue(
                    "REFERENCE_SOURCE_SCHEMA_ERROR",
                    "source database does not expose draws and run_metadata tables",
                )
            )
            return (), tuple(issues), False
        metadata = connection.execute(
            "SELECT run_id, lottery_type FROM run_metadata ORDER BY run_id"
        ).fetchall()
        if len(metadata) != 1 or str(metadata[0][1]) != POWER_LOTTO:
            issues.append(
                _reference_issue(
                    "REFERENCE_SOURCE_METADATA_ERROR",
                    "source database must contain exactly one POWER_LOTTO run",
                    details={"metadata_rows": len(metadata)},
                )
            )
        for row in connection.execute(
            "SELECT run_id, draw_number, draw_date, main_numbers_json, second_number "
            "FROM draws ORDER BY draw_number"
        ):
            try:
                main = json.loads(str(row[3]))
                if not isinstance(main, list):
                    raise ValueError("main_numbers_json is not an integer list")
                main_values: list[int] = []
                for value in cast(list[object], main):
                    if type(value) is not int:
                        raise ValueError("main_numbers_json is not an integer list")
                    main_values.append(value)
                draw = _ReferenceDraw(
                    draw_identity=str(row[1]),
                    draw_date=str(row[2]),
                    zone1=tuple(main_values),
                    zone2=int(row[4]),
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                issues.append(
                    _reference_issue(
                        "REFERENCE_SOURCE_ROW_ERROR",
                        "source database row could not be normalized",
                        details={"error": str(exc), "draw_identity": str(row[1])},
                    )
                )
                continue
            validation = _valid_reference_draw(draw, source_name="source")
            if validation is not None:
                issues.append(validation)
            draws.append(draw)
    except sqlite3.Error as exc:
        issues.append(_reference_issue("REFERENCE_SOURCE_QUERY_ERROR", str(exc)))
    finally:
        connection.close()
    return tuple(sorted(draws, key=lambda item: item.draw_identity)), tuple(issues), not issues


def _read_target_reference(
    path: Path,
) -> tuple[tuple[_ReferenceDraw, ...], tuple[StructuralIssue, ...], bool]:
    issues: list[StructuralIssue] = []
    draws_by_id: dict[str, _ReferenceDraw] = {}
    numbers_by_id: defaultdict[int, list[tuple[int, int, int]]] = defaultdict(list)
    try:
        connection = _read_only_connection(path)
    except (ArchiveAuditError, sqlite3.Error) as exc:
        return (), (_reference_issue("REFERENCE_TARGET_OPEN_ERROR", str(exc)),), False
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if not {"lottery_draw", "lottery_draw_number"}.issubset(tables):
            issues.append(
                _reference_issue(
                    "REFERENCE_TARGET_SCHEMA_ERROR",
                    "target database does not expose lottery_draw and lottery_draw_number",
                )
            )
            return (), tuple(issues), False
        for row in connection.execute(
            "SELECT draw_id, lottery_type, draw_number, draw_date, status "
            "FROM lottery_draw ORDER BY draw_number"
        ):
            draw_id = int(row[0])
            identity = str(row[2])
            if identity in draws_by_id:
                issues.append(
                    _reference_issue(
                        "DUPLICATE_REFERENCE_TARGET_IDENTITY",
                        "target database contains duplicate draw identities",
                        details={"draw_identity": identity},
                    )
                )
            draws_by_id[identity] = _ReferenceDraw(
                draw_identity=identity,
                draw_date=str(row[3]),
                zone1=(),
                zone2=0,
            )
            if str(row[1]) != POWER_LOTTO or str(row[4]) != "COMPLETE":
                issues.append(
                    _reference_issue(
                        "REFERENCE_TARGET_ROW_STATE_ERROR",
                        "target row is not a COMPLETE POWER_LOTTO draw",
                        details={"draw_identity": identity, "status": str(row[4])},
                    )
                )
            for number in connection.execute(
                "SELECT zone, position, number FROM lottery_draw_number "
                "WHERE draw_id = ? ORDER BY zone, position",
                (draw_id,),
            ):
                numbers_by_id[draw_id].append((int(number[0]), int(number[1]), int(number[2])))
        draw_id_by_identity = {
            str(row[2]): int(row[0])
            for row in connection.execute(
                "SELECT draw_id, lottery_type, draw_number, draw_date, status "
                "FROM lottery_draw ORDER BY draw_number"
            )
        }
        normalized: list[_ReferenceDraw] = []
        for identity, base in sorted(draws_by_id.items()):
            numeric_rows = numbers_by_id[draw_id_by_identity[identity]]
            zone1 = tuple(value for zone, _position, value in numeric_rows if zone == 1)
            zone2_values = tuple(value for zone, _position, value in numeric_rows if zone == 2)
            if len(zone2_values) != 1:
                issues.append(
                    _reference_issue(
                        "REFERENCE_TARGET_ZONE2_ERROR",
                        "target draw does not expose exactly one zone-2 value",
                        details={"draw_identity": identity, "count": len(zone2_values)},
                    )
                )
                zone2 = zone2_values[0] if zone2_values else 0
            else:
                zone2 = zone2_values[0]
            draw = _ReferenceDraw(identity, base.draw_date, zone1, zone2)
            validation = _valid_reference_draw(draw, source_name="target")
            if validation is not None:
                issues.append(validation)
            normalized.append(draw)
        return tuple(normalized), tuple(issues), not issues
    except sqlite3.Error as exc:
        issues.append(_reference_issue("REFERENCE_TARGET_QUERY_ERROR", str(exc)))
        return (), tuple(issues), False
    finally:
        connection.close()


def _compare_reference_draws(
    source: Sequence[_ReferenceDraw],
    target: Sequence[_ReferenceDraw],
) -> tuple[ReconciliationMismatch, ...]:
    source_map = {item.draw_identity: item for item in source}
    target_map = {item.draw_identity: item for item in target}
    mismatches: list[ReconciliationMismatch] = []
    for identity in sorted(set(source_map) | set(target_map)):
        source_draw = source_map.get(identity)
        target_draw = target_map.get(identity)
        if source_draw is None and target_draw is not None:
            mismatches.append(
                ReconciliationMismatch(
                    code="REFERENCE_EXTRA_IN_TARGET",
                    archive_path=None,
                    member_path=None,
                    row_number=None,
                    draw_identity=identity,
                    message="target reference contains a draw absent from source reference",
                    reference_date=source_draw.draw_date if source_draw else None,
                    reference_zone1=source_draw.zone1 if source_draw else (),
                    reference_zone2=source_draw.zone2 if source_draw else None,
                    candidate_date=target_draw.draw_date,
                    candidate_zone1=target_draw.zone1,
                    candidate_zone2=target_draw.zone2,
                )
            )
            continue
        if target_draw is None and source_draw is not None:
            mismatches.append(
                ReconciliationMismatch(
                    code="REFERENCE_MISSING_IN_TARGET",
                    archive_path=None,
                    member_path=None,
                    row_number=None,
                    draw_identity=identity,
                    message="source reference contains a draw absent from target reference",
                    reference_date=source_draw.draw_date,
                    reference_zone1=source_draw.zone1,
                    reference_zone2=source_draw.zone2,
                )
            )
            continue
        assert source_draw is not None and target_draw is not None
        if source_draw.draw_date != target_draw.draw_date:
            code = "REFERENCE_DATE_MISMATCH"
        elif tuple(sorted(source_draw.zone1)) != tuple(sorted(target_draw.zone1)):
            code = "REFERENCE_ZONE1_MISMATCH"
        elif source_draw.zone2 != target_draw.zone2:
            code = "REFERENCE_ZONE2_MISMATCH"
        else:
            continue
        mismatches.append(
            ReconciliationMismatch(
                code=code,
                archive_path=None,
                member_path=None,
                row_number=None,
                draw_identity=identity,
                message="source and target reference values differ",
                candidate_date=source_draw.draw_date,
                reference_date=target_draw.draw_date,
                candidate_zone1=source_draw.zone1,
                reference_zone1=target_draw.zone1,
                candidate_zone2=source_draw.zone2,
                reference_zone2=target_draw.zone2,
            )
        )
    return tuple(mismatches)


def _reference_result(
    source_path: Path,
    target_path: Path,
) -> ReferenceAuditResult:
    source, source_issues, source_ok = _read_source_reference(source_path)
    target, target_issues, target_ok = _read_target_reference(target_path)
    semantic_conflicts = _compare_reference_draws(source, target)
    all_issues = tuple((*source_issues, *target_issues))
    source_draws = tuple(_reference_draw_to_parsed(item, "source-db") for item in source)
    target_draws = tuple(_reference_draw_to_parsed(item, "target-db") for item in target)
    ordered_source = sorted(
        source,
        key=lambda item: (
            int(item.draw_identity) if item.draw_identity.isdigit() else item.draw_identity
        ),
    )
    return ReferenceAuditResult(
        source_row_count=len(source),
        target_row_count=len(target),
        source_draws=source_draws,
        target_draws=target_draws,
        semantic_conflicts=semantic_conflicts,
        structural_issues=all_issues,
        semantically_identical=source_ok and target_ok and not semantic_conflicts,
        source_query_only=source_ok,
        target_query_only=target_ok,
        first_draw_identity=ordered_source[0].draw_identity if ordered_source else None,
        last_draw_identity=ordered_source[-1].draw_identity if ordered_source else None,
    )


def _sort_identity(value: str) -> tuple[int, object]:
    if value.isdigit():
        return (0, int(value))
    return (1, value)


def _candidate_result(
    candidate_draws: Sequence[ParsedDraw],
    reference: ReferenceAuditResult,
) -> CandidateAuditResult:
    candidate_draws = tuple(
        draw for draw in candidate_draws if draw.classification is DatasetClassification.POWER_LOTTO
    )
    by_identity: dict[str, ParsedDraw] = {}
    mismatches: list[ReconciliationMismatch] = []
    valid_rows = 0
    malformed_rows = 0
    duplicate_identities = 0
    source_order_violations = 0
    for draw in candidate_draws:
        identity = draw.draw_identity or draw.raw_draw_identity.strip()
        has_source_order = any(issue.code == "SOURCE_ORDER_VIOLATION" for issue in draw.issues)
        if has_source_order:
            source_order_violations += 1
            if identity:
                mismatches.append(
                    ReconciliationMismatch(
                        code="SOURCE_ORDER_VIOLATION",
                        archive_path=draw.archive_path,
                        member_path=draw.member_path,
                        row_number=draw.row_number,
                        draw_identity=identity,
                        message=(
                            "candidate preserved source order that differs from canonical order"
                        ),
                        candidate_date=draw.draw_date,
                        candidate_zone1=draw.zone1,
                        candidate_zone2=draw.zone2,
                    )
                )
        non_order_issues = tuple(
            issue for issue in draw.issues if issue.code != "SOURCE_ORDER_VIOLATION"
        )
        if not identity or non_order_issues:
            malformed_rows += 1
            mismatches.append(
                ReconciliationMismatch(
                    code="MALFORMED_ROW",
                    archive_path=draw.archive_path,
                    member_path=draw.member_path,
                    row_number=draw.row_number,
                    draw_identity=identity or draw.raw_draw_identity,
                    message="candidate row failed structural POWER_LOTTO validation",
                    candidate_date=draw.draw_date,
                    candidate_zone1=draw.zone1,
                    candidate_zone2=draw.zone2,
                )
            )
            continue
        valid_rows += 1
        if identity in by_identity:
            duplicate_identities += 1
            mismatches.append(
                ReconciliationMismatch(
                    code="DUPLICATE_DRAW_IDENTITY",
                    archive_path=draw.archive_path,
                    member_path=draw.member_path,
                    row_number=draw.row_number,
                    draw_identity=identity,
                    message="more than one valid candidate row has this draw identity",
                    candidate_date=draw.draw_date,
                    candidate_zone1=draw.zone1,
                    candidate_zone2=draw.zone2,
                )
            )
            continue
        by_identity[identity] = draw

    source_draws = {
        draw.draw_identity: draw
        for draw in reference.source_draws
        if draw.draw_identity is not None
    }
    for identity in sorted(set(by_identity) | set(source_draws), key=_sort_identity):
        candidate = by_identity.get(identity)
        reference_draw = source_draws.get(identity)
        if candidate is None and reference_draw is not None:
            mismatches.append(
                ReconciliationMismatch(
                    code="MISSING_FROM_CANDIDATE",
                    archive_path=None,
                    member_path=None,
                    row_number=None,
                    draw_identity=identity,
                    message="reference POWER_LOTTO draw is absent from candidate archives",
                    reference_date=reference_draw.draw_date,
                    reference_zone1=reference_draw.zone1,
                    reference_zone2=reference_draw.zone2,
                )
            )
            continue
        if candidate is not None and reference_draw is None:
            mismatches.append(
                ReconciliationMismatch(
                    code="EXTRA_IN_CANDIDATE",
                    archive_path=candidate.archive_path,
                    member_path=candidate.member_path,
                    row_number=candidate.row_number,
                    draw_identity=identity,
                    message="candidate POWER_LOTTO draw is absent from reference databases",
                    candidate_date=candidate.draw_date,
                    candidate_zone1=tuple(sorted(candidate.zone1)),
                    candidate_zone2=candidate.zone2,
                )
            )
            continue
        assert candidate is not None and reference_draw is not None
        if candidate.draw_date != reference_draw.draw_date:
            mismatches.append(
                ReconciliationMismatch(
                    code="DATE_MISMATCH",
                    archive_path=candidate.archive_path,
                    member_path=candidate.member_path,
                    row_number=candidate.row_number,
                    draw_identity=identity,
                    message="candidate draw date differs from reference",
                    candidate_date=candidate.draw_date,
                    reference_date=reference_draw.draw_date,
                    candidate_zone1=tuple(sorted(candidate.zone1)),
                    reference_zone1=reference_draw.zone1,
                    candidate_zone2=candidate.zone2,
                    reference_zone2=reference_draw.zone2,
                )
            )
        if tuple(sorted(candidate.zone1)) != tuple(sorted(reference_draw.zone1)):
            mismatches.append(
                ReconciliationMismatch(
                    code="ZONE1_MISMATCH",
                    archive_path=candidate.archive_path,
                    member_path=candidate.member_path,
                    row_number=candidate.row_number,
                    draw_identity=identity,
                    message="candidate zone-1 set differs from reference",
                    candidate_date=candidate.draw_date,
                    reference_date=reference_draw.draw_date,
                    candidate_zone1=tuple(sorted(candidate.zone1)),
                    reference_zone1=reference_draw.zone1,
                    candidate_zone2=candidate.zone2,
                    reference_zone2=reference_draw.zone2,
                )
            )
        if candidate.zone2 != reference_draw.zone2:
            mismatches.append(
                ReconciliationMismatch(
                    code="ZONE2_MISMATCH",
                    archive_path=candidate.archive_path,
                    member_path=candidate.member_path,
                    row_number=candidate.row_number,
                    draw_identity=identity,
                    message="candidate zone-2 value differs from reference",
                    candidate_date=candidate.draw_date,
                    reference_date=reference_draw.draw_date,
                    candidate_zone1=tuple(sorted(candidate.zone1)),
                    reference_zone1=reference_draw.zone1,
                    candidate_zone2=candidate.zone2,
                    reference_zone2=reference_draw.zone2,
                )
            )
    ordered = sorted(by_identity, key=_sort_identity)
    mismatches.sort(
        key=lambda item: (
            _sort_identity(item.draw_identity),
            item.code,
            item.archive_path or "",
            item.member_path or "",
            item.row_number or 0,
        )
    )
    return CandidateAuditResult(
        valid_powerlotto_rows=valid_rows,
        unique_valid_draws=len(by_identity),
        duplicate_identities=duplicate_identities,
        malformed_rows=malformed_rows,
        source_order_violations=source_order_violations,
        candidate_draws=tuple(
            sorted(
                candidate_draws,
                key=lambda item: (_sort_identity(item.draw_identity or ""), item.row_number),
            )
        ),
        mismatches=tuple(mismatches),
        first_draw_identity=ordered[0] if ordered else None,
        last_draw_identity=ordered[-1] if ordered else None,
    )


def _missing_ranges(mismatches: Sequence[ReconciliationMismatch]) -> tuple[str, ...]:
    missing = sorted(
        {item.draw_identity for item in mismatches if item.code == "MISSING_FROM_CANDIDATE"},
        key=_sort_identity,
    )
    if not missing:
        return ()
    ranges: list[str] = []
    start = missing[0]
    previous = missing[0]
    for current in missing[1:]:
        contiguous = (
            start.isdigit()
            and previous.isdigit()
            and current.isdigit()
            and int(current) == int(previous) + 1
        )
        if not contiguous:
            ranges.append(start if start == previous else f"{start} through {previous}")
            start = current
        previous = current
    ranges.append(start if start == previous else f"{start} through {previous}")
    return tuple(ranges)


def audit_downloaded_archives(
    download_root: Path | str,
    source_db: Path | str,
    target_db: Path | str,
) -> AuditSummary:
    """Inventory archives and reconcile POWER_LOTTO against both references."""

    download_path = Path(download_root).expanduser().resolve()
    source_path = Path(source_db).expanduser().resolve()
    target_path = Path(target_db).expanduser().resolve()
    source_before: tuple[str, int] | None = None
    target_before: tuple[str, int] | None = None
    source_after: tuple[str, int] | None = None
    target_after: tuple[str, int] | None = None
    operational_errors: list[str] = []
    try:
        source_before = (sha256_file(source_path), source_path.stat().st_size)
        target_before = (sha256_file(target_path), target_path.stat().st_size)
    except (OSError, ArchiveAuditError) as exc:
        operational_errors.append(str(exc))
    (
        archive_files,
        archive_members,
        candidate_draws,
        archive_issues,
        root_archive_count,
        total_zip_bytes,
        csv_member_count,
        non_csv_member_count,
        duplicate_member_name_count,
        duplicate_member_content_count,
    ) = _inventory_download_root(download_path)
    reference = _reference_result(source_path, target_path)
    candidate = _candidate_result(candidate_draws, reference)
    try:
        source_after = (sha256_file(source_path), source_path.stat().st_size)
        target_after = (sha256_file(target_path), target_path.stat().st_size)
    except OSError as exc:
        operational_errors.append(str(exc))
    invariance_issues: list[StructuralIssue] = []
    if source_before is not None and source_after is not None and source_before != source_after:
        invariance_issues.append(
            _issue("REFERENCE_SOURCE_DB_DRIFT", "source reference database changed during audit")
        )
    if target_before is not None and target_after is not None and target_before != target_after:
        invariance_issues.append(
            _issue("REFERENCE_TARGET_DB_DRIFT", "target reference database changed during audit")
        )
    all_issues = tuple((*archive_issues, *reference.structural_issues, *invariance_issues))
    member_counts = Counter(
        item.classification.value
        for item in archive_members
        if item.member_path.casefold().endswith(".csv")
    )
    row_counts: Counter[str] = Counter()
    for item in archive_members:
        row_counts[item.classification.value] += item.row_count
    data_conflict_codes = {
        "DATE_MISMATCH",
        "ZONE1_MISMATCH",
        "ZONE2_MISMATCH",
        "DUPLICATE_DRAW_IDENTITY",
        "MALFORMED_ROW",
        "SOURCE_ORDER_VIOLATION",
        "EXTRA_IN_CANDIDATE",
    }
    if reference.semantic_conflicts:
        coverage_status = "REFERENCE_SEMANTIC_CONFLICT"
        recommendation = "DO_NOT_USE_SOURCE_CONFLICT"
    elif any(
        item.code in {"DATE_MISMATCH", "ZONE1_MISMATCH", "ZONE2_MISMATCH"}
        for item in candidate.mismatches
    ):
        coverage_status = "CONFLICTING_OVERLAP"
        recommendation = "DO_NOT_USE_SOURCE_CONFLICT"
    elif candidate.unique_valid_draws == reference.source_row_count and not candidate.mismatches:
        coverage_status = "EXACT_CORROBORATION"
        recommendation = "CORROBORATING_SOURCE_CONFIRMED"
    elif (
        candidate.unique_valid_draws > 0
        and reference.source_row_count > candidate.unique_valid_draws
    ):
        coverage_status = "PARTIAL_CORROBORATION_ONLY"
        recommendation = "PARTIAL_CORROBORATION_ONLY"
    else:
        coverage_status = "NO_USABLE_CANDIDATE"
        recommendation = "NO_USABLE_SOURCE"
    if any(
        item.code in {"REFERENCE_SOURCE_DB_DRIFT", "REFERENCE_TARGET_DB_DRIFT"}
        for item in invariance_issues
    ):
        operational_errors.append("reference database bytes changed during audit")
    if any(item.code == "CORRUPT_ZIP_ARCHIVE" for item in archive_issues):
        operational_errors.append("one or more ZIP archives were corrupt")
    del data_conflict_codes
    return AuditSummary(
        archive_files=archive_files,
        archive_members=archive_members,
        structural_issues=all_issues,
        classification_member_counts=dict(sorted(member_counts.items())),
        classification_row_counts=dict(sorted(row_counts.items())),
        candidate=candidate,
        reference=reference,
        root_archive_count=root_archive_count,
        total_zip_bytes=total_zip_bytes,
        csv_member_count=csv_member_count,
        non_csv_member_count=non_csv_member_count,
        duplicate_member_name_count=duplicate_member_name_count,
        duplicate_member_content_count=duplicate_member_content_count,
        identical_root_file_count=sum(
            1 for issue in archive_issues if issue.code == "IDENTICAL_ROOT_FILES"
        ),
        unsafe_member_count=sum(
            1 for issue in archive_issues if issue.code == "UNSAFE_MEMBER_PATH"
        ),
        corrupt_archive_count=sum(
            1 for item in archive_files if item.integrity_status == "CORRUPT"
        ),
        missing_reference_draw_ranges=_missing_ranges(candidate.mismatches),
        coverage_status=coverage_status,
        source_authority_recommendation=recommendation,
        source_db_sha256_before=source_before[0] if source_before else None,
        source_db_sha256_after=source_after[0] if source_after else None,
        target_db_sha256_before=target_before[0] if target_before else None,
        target_db_sha256_after=target_after[0] if target_after else None,
        source_db_bytes_before=source_before[1] if source_before else None,
        source_db_bytes_after=source_after[1] if source_after else None,
        target_db_bytes_before=target_before[1] if target_before else None,
        target_db_bytes_after=target_after[1] if target_after else None,
        operational_errors=tuple(sorted(set(operational_errors))),
    )


def _markdown_report(summary: AuditSummary) -> str:
    mismatch_counts = Counter(item.code for item in summary.candidate.mismatches)
    lines = [
        "# Lottery download archive audit",
        "",
        f"- Coverage: `{summary.coverage_status}`",
        f"- Source recommendation: `{summary.source_authority_recommendation}`",
        f"- Root ZIP archives: {summary.root_archive_count}",
        f"- ZIP bytes: {summary.total_zip_bytes}",
        f"- CSV members: {summary.csv_member_count}",
        f"- POWER_LOTTO candidate rows: {summary.candidate.valid_powerlotto_rows}",
        f"- Reference POWER_LOTTO rows: {summary.reference.source_row_count}",
        "- Reference databases semantically identical: "
        f"`{summary.reference.semantically_identical}`",
        "",
        "## Classification totals",
        "",
        "| Classification | CSV members | Rows |",
        "| --- | ---: | ---: |",
    ]
    for classification in sorted(
        set(summary.classification_member_counts) | set(summary.classification_row_counts)
    ):
        lines.append(
            f"| {classification} | {summary.classification_member_counts.get(classification, 0)} "
            f"| {summary.classification_row_counts.get(classification, 0)} |"
        )
    lines.extend(
        [
            "",
            "## Reconciliation",
            "",
            "| Finding | Count |",
            "| --- | ---: |",
            f"| Valid candidate rows | {summary.candidate.valid_powerlotto_rows} |",
            f"| Unique candidate draws | {summary.candidate.unique_valid_draws} |",
            f"| Missing from candidate | {mismatch_counts.get('MISSING_FROM_CANDIDATE', 0)} |",
            f"| Extra in candidate | {mismatch_counts.get('EXTRA_IN_CANDIDATE', 0)} |",
            f"| Conflicting dates | {mismatch_counts.get('DATE_MISMATCH', 0)} |",
            f"| Conflicting zone-1 sets | {mismatch_counts.get('ZONE1_MISMATCH', 0)} |",
            f"| Conflicting zone-2 values | {mismatch_counts.get('ZONE2_MISMATCH', 0)} |",
            f"| Malformed rows | {summary.candidate.malformed_rows} |",
            f"| Duplicate identities | {summary.candidate.duplicate_identities} |",
            f"| Source-order violations | {summary.candidate.source_order_violations} |",
            "",
            "### Missing reference ranges",
            "",
        ]
    )
    if summary.missing_reference_draw_ranges:
        lines.extend(f"- `{item}`" for item in summary.missing_reference_draw_ranges)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Database invariance",
            "",
            "| Database | SHA-256 before | SHA-256 after | Bytes before | Bytes after |",
            "| --- | --- | --- | ---: | ---: |",
            f"| Source | `{summary.source_db_sha256_before}` | "
            f"`{summary.source_db_sha256_after}` | "
            f"{summary.source_db_bytes_before} | {summary.source_db_bytes_after} |",
            f"| Target | `{summary.target_db_sha256_before}` | "
            f"`{summary.target_db_sha256_after}` | "
            f"{summary.target_db_bytes_before} | {summary.target_db_bytes_after} |",
            "",
            "## Safety and operational observations",
            "",
            "- ZIP members were streamed in place; no archive member was extracted.",
            "- Reference SQLite files were opened with `mode=ro`, `immutable=1`, "
            "and `query_only=ON`.",
            "- This report is corroboration evidence only; it does not adopt or "
            "migrate database rows.",
        ]
    )
    if summary.operational_errors:
        lines.extend(["", "## Operational errors", ""])
        lines.extend(f"- {item}" for item in summary.operational_errors)
    return "\n".join(lines) + "\n"


def write_reports(
    summary: AuditSummary,
    output_dir: Path | str,
    *,
    write_human_report: bool = True,
) -> None:
    """Write deterministic required reports and bounded detail reports."""

    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    payload = summary_to_dict(summary)
    (destination / "audit_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    if write_human_report:
        (destination / "audit_report.md").write_text(
            _markdown_report(summary),
            encoding="utf-8",
        )
    (destination / "mismatches.json").write_text(
        json.dumps(
            [_mismatch_dict(item) for item in summary.candidate.mismatches],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "member_inventory.json").write_text(
        json.dumps(
            {
                "files": [_archive_file_dict(item) for item in summary.archive_files],
                "members": [_archive_member_dict(item) for item in summary.archive_members],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def exit_code(summary: AuditSummary, *, fail_on_conflict: bool = False) -> int:
    """Return the stable CLI exit code for an observed summary."""

    if summary.operational_errors or summary.reference.structural_issues:
        return EXIT_OPERATIONAL_ERROR
    if summary.reference.semantic_conflicts:
        return EXIT_REFERENCE_CONFLICT
    conflict_codes = {"DATE_MISMATCH", "ZONE1_MISMATCH", "ZONE2_MISMATCH"}
    if any(item.code in conflict_codes for item in summary.candidate.mismatches):
        return EXIT_DATA_CONFLICT
    if fail_on_conflict and summary.candidate.mismatches:
        return EXIT_FAIL_ON_CONFLICT
    return EXIT_OK


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-root", type=Path, required=True)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--target-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--format", choices=("both", "json", "markdown"), default="both")
    parser.add_argument("--fail-on-conflict", action="store_true")
    parser.add_argument("--powerlotto-only", action="store_true")
    parser.add_argument("--no-human-report", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        summary = audit_downloaded_archives(
            args.download_root,
            args.source_db,
            args.target_db,
        )
        write_reports(
            summary,
            args.output_dir,
            write_human_report=not args.no_human_report,
        )
    except (ArchiveAuditError, OSError, sqlite3.Error) as exc:
        print(f"archive audit failed: {exc}")
        return EXIT_OPERATIONAL_ERROR
    return exit_code(summary, fail_on_conflict=args.fail_on_conflict)


__all__ = [
    "BIG_LOTTO",
    "DAILY_539",
    "EXIT_DATA_CONFLICT",
    "EXIT_FAIL_ON_CONFLICT",
    "EXIT_OK",
    "EXIT_OPERATIONAL_ERROR",
    "EXIT_REFERENCE_CONFLICT",
    "POWER_LOTTO",
    "ArchiveAuditError",
    "ArchiveFile",
    "ArchiveMember",
    "AuditSummary",
    "CandidateAuditResult",
    "DatasetClassification",
    "ParsedDraw",
    "ReconciliationMismatch",
    "ReferenceAuditResult",
    "StructuralIssue",
    "audit_downloaded_archives",
    "build_argument_parser",
    "exit_code",
    "main",
    "parse_csv_bytes",
    "sha256_file",
    "summary_to_dict",
    "write_reports",
]
