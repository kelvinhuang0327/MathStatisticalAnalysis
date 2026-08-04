"""Neutral archive-parser facts shared by application and infrastructure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DatasetClassification(StrEnum):
    """Classification derived from member headers and row content."""

    POWER_LOTTO = "POWER_LOTTO"
    DAILY_539 = "DAILY_539"
    BIG_LOTTO = "BIG_LOTTO"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    """Inventory metadata for one ZIP member or in-memory CSV input."""

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


__all__ = ["ArchiveMember", "DatasetClassification", "ParsedDraw", "StructuralIssue"]
