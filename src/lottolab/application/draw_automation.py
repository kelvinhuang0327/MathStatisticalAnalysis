"""Application-owned requests and read models for bounded draw-provider ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lottolab.application.draw_data import ImportCommitResult
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType

MAX_SYNC_RANGE_DAYS = 366


@dataclass(frozen=True, slots=True)
class ProviderDrawRecord:
    """One provider row before backend-authoritative canonical CSV validation."""

    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    source_reference: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderFetchResult:
    provider_id: str
    provider_version: str
    records: tuple[ProviderDrawRecord, ...]


@dataclass(frozen=True, slots=True)
class DrawSyncRequest:
    lottery_type: LotteryType
    date_from: date
    date_to: date

    def __post_init__(self) -> None:
        if self.date_from > self.date_to:
            raise InvalidDrawSyncRequestError("date_from must not be after date_to")
        inclusive_days = (self.date_to - self.date_from).days + 1
        if inclusive_days > MAX_SYNC_RANGE_DAYS:
            raise InvalidDrawSyncRequestError(
                f"draw sync ranges must not exceed {MAX_SYNC_RANGE_DAYS} days"
            )


@dataclass(frozen=True, slots=True)
class IngestionAuditContext:
    operation_type: IngestionOperationType
    lottery_type: LotteryType
    provider_id: str
    provider_version: str
    requested_start: date
    requested_end: date
    resolved_start: date | None
    resolved_end: date | None
    fetched_count: int


@dataclass(frozen=True, slots=True)
class DrawSyncResult:
    operation_type: IngestionOperationType
    provider_id: str
    requested_start: date
    requested_end: date
    resolved_start: date | None
    resolved_end: date | None
    fetched_count: int
    ingestion: ImportCommitResult


class DrawAutomationError(RuntimeError):
    """Base class for sanitized provider-sync failures."""


class AutomationNotConfiguredError(DrawAutomationError):
    """No provider adapter is configured for this local runtime."""


class InvalidDrawSyncRequestError(DrawAutomationError):
    """A caller requested an invalid or unbounded synchronization range."""


class DrawProviderUnavailableError(DrawAutomationError):
    """The configured provider failed without exposing transport details."""


class DrawProviderContractError(DrawAutomationError):
    """Provider output did not satisfy the backend canonical draw contract."""
