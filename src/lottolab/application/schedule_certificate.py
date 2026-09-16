"""Strict Owner certificate contracts for T539/P638 manual schedule authority."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from lottolab.application.schedule_sync import CanonicalScheduleFact
from lottolab.domain.ingestion import IngestionRunStatus

OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION = "LOTTOLAB_T539_P638_SCHEDULE_CERTIFICATE_V1"
OWNER_SCHEDULE_CERTIFYING_AUTHORITY = "PROJECT_OWNER:kelvinhuang0327"

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class ScheduleCertificateReason(StrEnum):
    """Closed reasons under which Owner fallback may be considered."""

    OFFICIAL_AUTHORITY_ABSENT = "OFFICIAL_AUTHORITY_ABSENT"
    OFFICIAL_AUTHORITY_UNAVAILABLE = "OFFICIAL_AUTHORITY_UNAVAILABLE"
    OFFICIAL_AUTHORITY_INCOMPLETE = "OFFICIAL_AUTHORITY_INCOMPLETE"
    OFFICIAL_TIME_CHANGE = "OFFICIAL_TIME_CHANGE"
    OFFICIAL_EXTRAORDINARY_DRAW = "OFFICIAL_EXTRAORDINARY_DRAW"
    OFFICIAL_HOLIDAY_SCHEDULE = "OFFICIAL_HOLIDAY_SCHEDULE"


class OfficialSupportArtifactType(StrEnum):
    """Evidence kinds permitted by the frozen Owner certification contract."""

    OFFICIAL_TAIWAN_LOTTERY_HTTPS_PAYLOAD = (
        "OFFICIAL_TAIWAN_LOTTERY_HTTPS_PAYLOAD"
    )
    OFFICIAL_TAIWAN_LOTTERY_PAGE = "OFFICIAL_TAIWAN_LOTTERY_PAGE"
    OFFICIAL_TAIWAN_LOTTERY_WRITTEN_NOTICE = (
        "OFFICIAL_TAIWAN_LOTTERY_WRITTEN_NOTICE"
    )
    TAIWAN_LOTTERY_TICKET_RECEIPT = "TAIWAN_LOTTERY_TICKET_RECEIPT"


class ManualScheduleCertificateDisposition(StrEnum):
    """One schedule-certificate application decision."""

    INSERTED = "INSERTED"
    CONFIRMED = "CONFIRMED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class OwnerScheduleCertificate:
    """DB-free validated Owner certificate plus its exact hash bindings."""

    schema_version: str
    source_filename: str
    certificate_input_sha256: str
    certificate_document_sha256: str
    fact: CanonicalScheduleFact
    supporting_artifact_type: OfficialSupportArtifactType
    certified_at: datetime
    certifying_authority: str
    certification_reason: ScheduleCertificateReason

    def __post_init__(self) -> None:
        if self.schema_version != OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION:
            raise ValueError("certificate schema_version is unsupported")
        _require_text(self.source_filename, "source_filename")
        if "/" in self.source_filename or "\\" in self.source_filename:
            raise ValueError("source_filename must be a basename")
        _require_sha256(self.certificate_input_sha256, "certificate_input_sha256")
        _require_sha256(self.certificate_document_sha256, "certificate_document_sha256")
        if type(self.fact) is not CanonicalScheduleFact:
            raise ValueError("fact must be a CanonicalScheduleFact")
        if type(self.supporting_artifact_type) is not OfficialSupportArtifactType:
            raise ValueError("supporting_artifact_type is unsupported")
        _require_utc(self.certified_at, "certified_at")
        if self.certifying_authority != OWNER_SCHEDULE_CERTIFYING_AUTHORITY:
            raise ValueError("certifying_authority is not the authorized Project Owner")
        if type(self.certification_reason) is not ScheduleCertificateReason:
            raise ValueError("certification_reason is unsupported")
        if self.certified_at >= self.fact.announcement.scheduled_at:
            raise ValueError("certification must precede scheduled_at")

    @property
    def supporting_artifact_sha256(self) -> str:
        return self.fact.announcement.source.source_payload_sha256


@dataclass(frozen=True, slots=True)
class ManualScheduleCertificatePreview:
    """Zero-write preview for one exact Owner certificate."""

    certificate: OwnerScheduleCertificate
    disposition: ManualScheduleCertificateDisposition
    zero_write: bool

    def __post_init__(self) -> None:
        if type(self.certificate) is not OwnerScheduleCertificate:
            raise ValueError("certificate must be OwnerScheduleCertificate")
        if self.disposition not in {
            ManualScheduleCertificateDisposition.INSERTED,
            ManualScheduleCertificateDisposition.CONFIRMED,
        }:
            raise ValueError("preview disposition must be INSERTED or CONFIRMED")
        if self.zero_write is not True:
            raise ValueError("certificate preview must be zero-write")


@dataclass(frozen=True, slots=True)
class ManualScheduleCertificateResult:
    """Audited result of an explicitly applied schedule certificate."""

    run_id: str
    status: IngestionRunStatus
    certificate: OwnerScheduleCertificate
    disposition: ManualScheduleCertificateDisposition
    inserted_count: int
    confirmed_count: int
    conflict_count: int

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if type(self.certificate) is not OwnerScheduleCertificate:
            raise ValueError("certificate must be OwnerScheduleCertificate")
        counts = (self.inserted_count, self.confirmed_count, self.conflict_count)
        if any(type(item) is not int or item < 0 for item in counts) or sum(counts) != 1:
            raise ValueError("certificate result counts must classify exactly one fact")
        expected = {
            ManualScheduleCertificateDisposition.INSERTED: (
                IngestionRunStatus.SUCCESS,
                1,
                0,
                0,
            ),
            ManualScheduleCertificateDisposition.CONFIRMED: (
                IngestionRunStatus.SUCCESS,
                0,
                1,
                0,
            ),
            ManualScheduleCertificateDisposition.CONFLICT: (
                IngestionRunStatus.FAILED,
                0,
                0,
                1,
            ),
        }[self.disposition]
        if (self.status, *counts) != expected:
            raise ValueError("certificate result status, disposition, and counts disagree")


class ScheduleCertificateError(RuntimeError):
    """Base class for sanitized schedule-certificate failures."""


class ScheduleCertificateInputError(ScheduleCertificateError):
    """Certificate bytes, supporting evidence, or hash pins are invalid."""


class ScheduleCertificateUnavailableError(ScheduleCertificateError):
    """Canonical persistence is absent, invalid, or unavailable."""


class ScheduleCertificateCompletedOutcomeError(ScheduleCertificateError):
    """A completed official outcome already occupies the requested identity."""


class ScheduleCertificateConflictError(ScheduleCertificateError):
    """The certificate conflicts with immutable or higher-precedence authority."""

    def __init__(self, result: ManualScheduleCertificateResult | None = None) -> None:
        super().__init__("schedule certificate conflicts with canonical authority")
        self.result = result


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
    "OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION",
    "OWNER_SCHEDULE_CERTIFYING_AUTHORITY",
    "ManualScheduleCertificateDisposition",
    "ManualScheduleCertificatePreview",
    "ManualScheduleCertificateResult",
    "OfficialSupportArtifactType",
    "OwnerScheduleCertificate",
    "ScheduleCertificateCompletedOutcomeError",
    "ScheduleCertificateConflictError",
    "ScheduleCertificateError",
    "ScheduleCertificateInputError",
    "ScheduleCertificateReason",
    "ScheduleCertificateUnavailableError",
]
