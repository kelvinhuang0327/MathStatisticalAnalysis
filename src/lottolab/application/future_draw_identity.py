"""Outcome-free canonical schedule identity models and manual-supplement results."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from lottolab.domain.ingestion import IngestionItemDisposition, IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class ScheduledDrawOutcomeState(StrEnum):
    """Outcome population state derived by joining schedules to completed draws."""

    NOT_POPULATED = "NOT_POPULATED"
    POPULATED = "POPULATED"


@dataclass(frozen=True, slots=True)
class ScheduledDrawIdentityRecord:
    """One immutable schedule fact plus its non-stored, derived outcome state."""

    internal_id: int
    announcement: TargetAnnouncement
    normalized_announcement_hash: str
    ingestion_run_id: str
    created_at: datetime
    outcome_state: ScheduledDrawOutcomeState
    outcome_draw_internal_id: int | None

    def __post_init__(self) -> None:
        if type(self.internal_id) is not int or self.internal_id < 1:
            raise ValueError("internal_id must be a positive exact integer")
        if type(self.announcement) is not TargetAnnouncement:
            raise ValueError("announcement must be a TargetAnnouncement")
        _require_sha256(self.normalized_announcement_hash, "normalized_announcement_hash")
        _require_text(self.ingestion_run_id, "ingestion_run_id")
        _require_utc(self.created_at, "created_at")
        if type(self.outcome_state) is not ScheduledDrawOutcomeState:
            raise ValueError("outcome_state must be a ScheduledDrawOutcomeState")
        if self.outcome_draw_internal_id is not None and (
            type(self.outcome_draw_internal_id) is not int
            or self.outcome_draw_internal_id < 1
        ):
            raise ValueError("outcome_draw_internal_id must be a positive integer or None")
        populated = self.outcome_state is ScheduledDrawOutcomeState.POPULATED
        has_outcome_identity = self.outcome_draw_internal_id is not None
        if populated != has_outcome_identity:
            raise ValueError("derived outcome state and outcome draw identity disagree")


@dataclass(frozen=True, slots=True)
class OwnerCertifiedFutureDrawIdentityInput:
    """Strict DB-free parse result for one owner-supplied announcement document."""

    source_filename: str
    input_sha256: str
    announcements: tuple[TargetAnnouncement, ...]

    def __post_init__(self) -> None:
        _require_text(self.source_filename, "source_filename")
        if "/" in self.source_filename or "\\" in self.source_filename:
            raise ValueError("source_filename must be a basename")
        _require_sha256(self.input_sha256, "input_sha256")
        if type(self.announcements) is not tuple or any(
            type(item) is not TargetAnnouncement for item in self.announcements
        ):
            raise ValueError("announcements must contain TargetAnnouncement values")
        targets = tuple(item.target for item in self.announcements)
        if len(targets) != len(set(targets)):
            raise ValueError("announcement targets must be unique")


@dataclass(frozen=True, slots=True)
class ManualFutureDrawIdentitySupplementPreview:
    """Read-only classification rendered before an explicitly requested commit."""

    announcement: TargetAnnouncement
    normalized_announcement_hash: str
    input_sha256: str
    disposition: IngestionItemDisposition
    zero_write: bool

    def __post_init__(self) -> None:
        if type(self.announcement) is not TargetAnnouncement:
            raise ValueError("announcement must be a TargetAnnouncement")
        _require_sha256(self.normalized_announcement_hash, "normalized_announcement_hash")
        _require_sha256(self.input_sha256, "input_sha256")
        if self.disposition not in {
            IngestionItemDisposition.INSERTED,
            IngestionItemDisposition.SKIPPED_DUPLICATE,
        }:
            raise ValueError("preview disposition must be insert or exact duplicate")
        if self.zero_write is not True:
            raise ValueError("manual supplement preview must be a zero-write result")


@dataclass(frozen=True, slots=True)
class ManualFutureDrawIdentitySupplementResult:
    """Audited commit receipt for one exact owner-selected schedule identity."""

    run_id: str
    status: IngestionRunStatus
    announcement: TargetAnnouncement
    normalized_announcement_hash: str
    input_sha256: str
    disposition: IngestionItemDisposition
    inserted_count: int
    skipped_count: int
    conflict_count: int

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if self.status not in {IngestionRunStatus.SUCCESS, IngestionRunStatus.FAILED}:
            raise ValueError("manual supplement result must be terminal")
        if type(self.announcement) is not TargetAnnouncement:
            raise ValueError("announcement must be a TargetAnnouncement")
        _require_sha256(self.normalized_announcement_hash, "normalized_announcement_hash")
        _require_sha256(self.input_sha256, "input_sha256")
        counts = (self.inserted_count, self.skipped_count, self.conflict_count)
        if any(type(value) is not int or value < 0 for value in counts) or sum(counts) != 1:
            raise ValueError("manual supplement counts must classify exactly one target")
        expected = {
            IngestionItemDisposition.INSERTED: (1, 0, 0, IngestionRunStatus.SUCCESS),
            IngestionItemDisposition.SKIPPED_DUPLICATE: (
                0,
                1,
                0,
                IngestionRunStatus.SUCCESS,
            ),
            IngestionItemDisposition.CONFLICT: (0, 0, 1, IngestionRunStatus.FAILED),
        }.get(self.disposition)
        if expected is None or (*counts, self.status) != expected:
            raise ValueError("manual supplement disposition, counts, and status disagree")


class FutureDrawIdentityError(RuntimeError):
    """Base error for canonical future-draw identity operations."""


class FutureDrawIdentityConflictError(FutureDrawIdentityError):
    """A conflicting immutable schedule identity was audited and rejected."""

    def __init__(self, result: ManualFutureDrawIdentitySupplementResult) -> None:
        super().__init__("canonical future draw identity conflicts with the stored schedule")
        self.result = result


class FutureDrawIdentityNotFutureError(FutureDrawIdentityError):
    """The selected identity already has a completed outcome."""


class FutureDrawIdentityPreviewConflictError(FutureDrawIdentityError):
    """A read-only preview found conflicting immutable schedule material."""


class FutureDrawIdentityUnavailableError(FutureDrawIdentityError):
    """The canonical schedule repository is absent, stale, or invalid."""


def normalized_announcement_sha256(announcement: TargetAnnouncement) -> str:
    """Hash the canonical TargetAnnouncement material without outcome values."""

    if type(announcement) is not TargetAnnouncement:
        raise ValueError("announcement must be a TargetAnnouncement")
    encoded = json.dumps(
        announcement.canonical_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{label} must be canonical non-empty text")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")


__all__ = [
    "FutureDrawIdentityConflictError",
    "FutureDrawIdentityError",
    "FutureDrawIdentityNotFutureError",
    "FutureDrawIdentityPreviewConflictError",
    "FutureDrawIdentityUnavailableError",
    "ManualFutureDrawIdentitySupplementPreview",
    "ManualFutureDrawIdentitySupplementResult",
    "OwnerCertifiedFutureDrawIdentityInput",
    "ScheduledDrawIdentityRecord",
    "ScheduledDrawOutcomeState",
    "normalized_announcement_sha256",
]
