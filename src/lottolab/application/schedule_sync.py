"""Application contracts for bounded official schedule synchronization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement

SCHEDULE_SYNC_PARSER_VERSION = "lottolab-b649-official-schedule-json-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class OfficialScheduleSyncError(RuntimeError):
    """Base class for sanitized official schedule synchronization failures."""


class OfficialScheduleProviderError(OfficialScheduleSyncError):
    """The official schedule provider could not return a trusted response."""


class OfficialScheduleUnavailableError(OfficialScheduleProviderError):
    """The official response is unavailable or contains no usable B649 target."""


class OfficialScheduleContractError(OfficialScheduleProviderError):
    """The official response violates the bounded schedule contract."""


@dataclass(frozen=True, slots=True)
class OfficialScheduleFetchResult:
    """One validated official response before canonical persistence."""

    provider_id: str
    provider_version: str
    source_url: str
    source_payload_sha256: str
    observed_at: datetime
    announcements: tuple[TargetAnnouncement, ...]

    def __post_init__(self) -> None:
        _require_text(self.provider_id, "provider_id")
        _require_text(self.provider_version, "provider_version")
        _require_text(self.source_url, "source_url")
        _require_sha256(self.source_payload_sha256, "source_payload_sha256")
        _require_utc(self.observed_at, "observed_at")
        if type(self.announcements) is not tuple or not self.announcements:
            raise ValueError("announcements must be a non-empty tuple")
        for announcement in self.announcements:
            if type(announcement) is not TargetAnnouncement:
                raise ValueError("announcements must contain TargetAnnouncement values")
            if announcement.target.lottery_type is not LotteryType.BIG_LOTTO:
                raise ValueError("official schedule synchronization supports BIG_LOTTO only")
            source = announcement.source
            if (
                source.source_id != self.provider_id
                or source.source_version != self.provider_version
                or source.source_locator != self.source_url
                or source.source_sha256 != self.source_payload_sha256
                or source.observed_at != self.observed_at
            ):
                raise ValueError("announcement provenance does not match the fetched response")


@dataclass(frozen=True, slots=True)
class OfficialScheduleSyncResult:
    """Audited result for one atomic canonical schedule synchronization."""

    run_id: str
    status: IngestionRunStatus
    provider_id: str
    provider_version: str
    source_url: str
    source_payload_sha256: str
    observed_at: datetime
    target_draw_numbers: tuple[str, ...]
    total_count: int
    inserted_count: int
    skipped_count: int
    exact_duplicate_count: int
    completed_count: int
    conflict_count: int
    failed_count: int

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if self.status not in {IngestionRunStatus.SUCCESS, IngestionRunStatus.FAILED}:
            raise ValueError("schedule sync result must be terminal")
        _require_text(self.provider_id, "provider_id")
        _require_text(self.provider_version, "provider_version")
        _require_text(self.source_url, "source_url")
        _require_sha256(self.source_payload_sha256, "source_payload_sha256")
        _require_utc(self.observed_at, "observed_at")
        if type(self.target_draw_numbers) is not tuple or any(
            type(value) is not str or not value for value in self.target_draw_numbers
        ):
            raise ValueError("target_draw_numbers must contain non-empty text")
        counts = (
            self.total_count,
            self.inserted_count,
            self.skipped_count,
            self.exact_duplicate_count,
            self.completed_count,
            self.conflict_count,
            self.failed_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("schedule sync counts must be non-negative integers")
        if self.exact_duplicate_count + self.completed_count != self.skipped_count:
            raise ValueError("schedule sync skipped detail counts are inconsistent")
        if self.total_count != (
            self.inserted_count
            + self.skipped_count
            + self.conflict_count
            + self.failed_count
        ):
            raise ValueError("schedule sync counts do not classify every target")
        if len(self.target_draw_numbers) != self.total_count:
            raise ValueError("schedule sync target count does not match total_count")

    @property
    def counts_are_consistent(self) -> bool:
        return self.total_count == (
            self.inserted_count
            + self.skipped_count
            + self.conflict_count
            + self.failed_count
        )


class OfficialScheduleProvider(Protocol):
    """Port for one bounded official B649 schedule response."""

    def fetch_schedule(self, *, observed_at: datetime) -> OfficialScheduleFetchResult: ...


class CanonicalScheduleSyncRepository(Protocol):
    """Atomic persistence port for official schedule identities."""

    def apply_official_schedule_sync(
        self,
        fetched: OfficialScheduleFetchResult,
    ) -> OfficialScheduleSyncResult: ...


class CanonicalScheduleSyncConflictError(OfficialScheduleSyncError):
    """An immutable schedule conflict was audited without partial schedule writes."""

    def __init__(self, result: OfficialScheduleSyncResult) -> None:
        super().__init__("official schedule synchronization conflicts with canonical authority")
        self.result = result


class SynchronizeOfficialSchedule:
    """Fetch and atomically apply one bounded official schedule response."""

    def __init__(
        self,
        provider: OfficialScheduleProvider,
        repository: CanonicalScheduleSyncRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def execute(self, *, observed_at: datetime) -> OfficialScheduleSyncResult:
        _require_utc(observed_at, "observed_at")
        fetched = self._provider.fetch_schedule(observed_at=observed_at)
        if type(fetched) is not OfficialScheduleFetchResult:
            raise OfficialScheduleProviderError(
                "official schedule provider returned an unsupported result"
            )
        return self._repository.apply_official_schedule_sync(fetched)


OfficialScheduleSyncUseCase = SynchronizeOfficialSchedule
CanonicalScheduleSyncUseCase = SynchronizeOfficialSchedule


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
    "SCHEDULE_SYNC_PARSER_VERSION",
    "CanonicalScheduleSyncConflictError",
    "CanonicalScheduleSyncRepository",
    "CanonicalScheduleSyncUseCase",
    "OfficialScheduleContractError",
    "OfficialScheduleFetchResult",
    "OfficialScheduleProvider",
    "OfficialScheduleProviderError",
    "OfficialScheduleSyncError",
    "OfficialScheduleSyncResult",
    "OfficialScheduleSyncUseCase",
    "OfficialScheduleUnavailableError",
    "SynchronizeOfficialSchedule",
]
