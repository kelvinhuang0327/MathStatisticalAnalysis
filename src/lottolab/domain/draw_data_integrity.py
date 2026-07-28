"""Closed, deterministic domain values for a read-only draw-data integrity report.

No timestamp, hostname, process identity, ambient path, or random identifier
ever belongs on these values: two inspections of the same unchanged database
must produce equal reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

REQUIRED_TABLE_NAMES: tuple[str, ...] = ("draws", "ingestion_runs", "ingestion_items")


class DrawDataIntegrityStatus(StrEnum):
    ABSENT = "ABSENT"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"


class DrawDataIntegrityFindingCode(StrEnum):
    SQLITE_QUICK_CHECK_FAILED = "SQLITE_QUICK_CHECK_FAILED"
    FOREIGN_KEY_VIOLATION = "FOREIGN_KEY_VIOLATION"
    DUPLICATE_DRAW_IDENTITY = "DUPLICATE_DRAW_IDENTITY"
    INVALID_DRAW_NUMBER = "INVALID_DRAW_NUMBER"
    INVALID_NORMALIZED_RECORD_HASH = "INVALID_NORMALIZED_RECORD_HASH"
    INVALID_NUMBERS_JSON = "INVALID_NUMBERS_JSON"


_REQUIRED_FINDING_CODES: tuple[DrawDataIntegrityFindingCode, ...] = tuple(
    DrawDataIntegrityFindingCode
)
_VALID_FINDING_CODES = frozenset(DrawDataIntegrityFindingCode)
_VALID_STATUSES = frozenset(DrawDataIntegrityStatus)


@dataclass(frozen=True, slots=True)
class DrawDataIntegrityFinding:
    """One closed-code integrity finding; never carries row contents."""

    code: DrawDataIntegrityFindingCode
    count: int

    def __post_init__(self) -> None:
        # A statically-typed field is not a runtime guarantee: an untyped
        # caller can still hand in a value the type checker never saw.
        if self.code not in _VALID_FINDING_CODES:
            raise ValueError(f"unknown draw-data integrity finding code: {self.code!r}")
        if self.count < 0:
            raise ValueError("draw-data integrity finding count must not be negative")


@dataclass(frozen=True, slots=True)
class DrawDataTableCount:
    """One required table's exact row count."""

    table_name: str
    row_count: int

    def __post_init__(self) -> None:
        if self.table_name not in REQUIRED_TABLE_NAMES:
            raise ValueError(f"unknown draw-data table name: {self.table_name!r}")
        if self.row_count < 0:
            raise ValueError("draw-data table row count must not be negative")


@dataclass(frozen=True, slots=True)
class DrawDataLotterySummary:
    """One lottery type's draw count and inclusive first/last draw range.

    First/last are ordered by ``draw_date`` then the numeric value of
    ``draw_number`` -- never lexicographically (see the draw-history reader
    for why lexicographic draw-number ordering is a known bug class).
    """

    lottery_type: str
    draw_count: int
    first_draw_number: str
    first_draw_date: str
    last_draw_number: str
    last_draw_date: str

    def __post_init__(self) -> None:
        if self.draw_count < 1:
            raise ValueError("draw-data lottery summary draw_count must be at least 1")


@dataclass(frozen=True, slots=True)
class DrawDataIntegrityReport:
    """One closed, deterministic read-only integrity report.

    ``ABSENT`` carries no schema version, counts, summaries, or findings.
    ``HEALTHY``/``UNHEALTHY`` always carry a schema version, the three
    required table counts in fixed order, lexicographically ordered lottery
    summaries, and all six closed finding codes exactly once.
    """

    status: DrawDataIntegrityStatus
    schema_version: int | None
    table_counts: tuple[DrawDataTableCount, ...]
    lottery_summaries: tuple[DrawDataLotterySummary, ...]
    findings: tuple[DrawDataIntegrityFinding, ...]

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"unknown draw-data integrity status: {self.status!r}")

        if self.status is DrawDataIntegrityStatus.ABSENT:
            if self.schema_version is not None:
                raise ValueError("an ABSENT report must not carry a schema_version")
            if self.table_counts or self.lottery_summaries or self.findings:
                raise ValueError("an ABSENT report must carry no counts, summaries or findings")
            return

        if self.schema_version is None:
            raise ValueError("a HEALTHY or UNHEALTHY report must carry a schema_version")

        observed_table_names = tuple(entry.table_name for entry in self.table_counts)
        if observed_table_names != REQUIRED_TABLE_NAMES:
            raise ValueError(
                "draw-data table counts must report draws, ingestion_runs, "
                "ingestion_items in that exact order"
            )

        observed_lottery_types = tuple(entry.lottery_type for entry in self.lottery_summaries)
        if observed_lottery_types != tuple(sorted(observed_lottery_types)):
            raise ValueError("draw-data lottery summaries must be lexicographically ordered")
        if len(set(observed_lottery_types)) != len(observed_lottery_types):
            raise ValueError("draw-data lottery summaries must not repeat a lottery type")

        observed_codes = tuple(finding.code for finding in self.findings)
        if observed_codes != _REQUIRED_FINDING_CODES:
            raise ValueError("draw-data integrity findings must report every closed code once")

        all_zero = all(finding.count == 0 for finding in self.findings)
        if self.status is DrawDataIntegrityStatus.HEALTHY and not all_zero:
            raise ValueError("a HEALTHY report must carry only zero-count findings")
        if self.status is DrawDataIntegrityStatus.UNHEALTHY and all_zero:
            raise ValueError("an UNHEALTHY report must carry at least one nonzero finding")
