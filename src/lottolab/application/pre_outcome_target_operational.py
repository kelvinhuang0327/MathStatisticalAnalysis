"""Operational selection around the immutable pre-outcome target service.

This module owns only outcome-free orchestration: load an explicit announcement
inventory, select the earliest still-future target for one lottery, re-read the
announcement to detect drift, bind strictly causal history, and invoke the
existing create-once registration service.  Infrastructure decides where the
inventory, history, presence evidence, and durable authority live.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from lottolab.application.pre_outcome_target import (
    PreOutcomeTargetRegistrationRequest,
    PreOutcomeTargetRegistrationService,
    RegistrationSyncStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
)
from lottolab.domain.prospective_observer import CausalHistoryRef, ObservationTarget


class PreOutcomeTargetOperationalError(RuntimeError):
    """Base class for fail-closed operational binding errors."""


class TargetAnnouncementDriftError(PreOutcomeTargetOperationalError):
    """The selected announcement changed during the final pre-write recheck."""


class TargetAnnouncementAuthorityError(PreOutcomeTargetOperationalError):
    """The configured announcement authority is present but invalid."""


class OutcomePresenceEvidenceUnavailableError(PreOutcomeTargetOperationalError):
    """No presence-only official-source evidence can attest to this target."""


class CausalHistoryAuthorityError(PreOutcomeTargetOperationalError):
    """The configured causal-history authority is absent, corrupt, or invalid."""


class TargetAnnouncementSourceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(frozen=True, slots=True)
class TargetAnnouncementInventory:
    """One bounded read from the canonical operational announcement source."""

    status: TargetAnnouncementSourceStatus
    announcements: tuple[TargetAnnouncement, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not TargetAnnouncementSourceStatus:
            raise ValueError("status must be a TargetAnnouncementSourceStatus")
        if type(self.announcements) is not tuple or any(
            type(item) is not TargetAnnouncement for item in self.announcements
        ):
            raise ValueError("announcements must contain TargetAnnouncement values")
        if (
            self.status is TargetAnnouncementSourceStatus.NOT_CONFIGURED
            and self.announcements
        ):
            raise ValueError("a missing announcement source cannot contain announcements")


@runtime_checkable
class TargetAnnouncementSource(Protocol):
    """Read an explicit announcement inventory without deriving target cadence."""

    def read(self) -> TargetAnnouncementInventory: ...


@runtime_checkable
class CausalHistoryAuthority(Protocol):
    """Resolve the immutable history identity strictly before one target."""

    def resolve(self, target: ObservationTarget) -> CausalHistoryRef: ...


class OperationalRegistrationStatus(StrEnum):
    CREATED = "CREATED"
    EXACT_IDEMPOTENT_NO_OP = "EXACT_IDEMPOTENT_NO_OP"
    NO_CANONICAL_TARGET_ANNOUNCEMENT = "NO_CANONICAL_TARGET_ANNOUNCEMENT"
    NO_REGISTERABLE_PRE_OUTCOME_TARGET = "NO_REGISTERABLE_PRE_OUTCOME_TARGET"


@dataclass(frozen=True, slots=True)
class OperationalRegistrationResult:
    status: OperationalRegistrationStatus
    announcement: TargetAnnouncement | None
    causal_history: CausalHistoryRef | None
    registration: PreOutcomeTargetRegistration | None

    def __post_init__(self) -> None:
        if type(self.status) is not OperationalRegistrationStatus:
            raise ValueError("status must be an OperationalRegistrationStatus")
        completed = self.status in {
            OperationalRegistrationStatus.CREATED,
            OperationalRegistrationStatus.EXACT_IDEMPOTENT_NO_OP,
        }
        values_present = (
            type(self.announcement) is TargetAnnouncement
            and type(self.causal_history) is CausalHistoryRef
            and type(self.registration) is PreOutcomeTargetRegistration
        )
        if completed != values_present:
            raise ValueError("completed registration results require all authority values")
        if not completed and any(
            value is not None
            for value in (self.announcement, self.causal_history, self.registration)
        ):
            raise ValueError("no-target results must not expose partial authority values")
        if completed:
            assert self.announcement is not None
            assert self.causal_history is not None
            assert self.registration is not None
            if self.registration.announcement != self.announcement:
                raise ValueError("registration announcement does not match the selected target")
            if self.registration.causal_history != self.causal_history:
                raise ValueError("registration history does not match the resolved authority")


@dataclass(frozen=True, slots=True)
class PreOutcomeTargetOperationalService:
    """Register the earliest explicit future announcement for one lottery."""

    announcement_source: TargetAnnouncementSource
    causal_history_authority: CausalHistoryAuthority
    registration_service: PreOutcomeTargetRegistrationService
    clock: Callable[[], datetime]

    def register_earliest(
        self,
        lottery_type: LotteryType,
    ) -> OperationalRegistrationResult:
        if type(lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")

        selection_time = self.clock()
        _require_utc(selection_time)
        inventory = self.announcement_source.read()
        if inventory.status is TargetAnnouncementSourceStatus.NOT_CONFIGURED:
            return _empty_result(
                OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT
            )

        candidates = tuple(
            announcement
            for announcement in inventory.announcements
            if announcement.target.lottery_type is lottery_type
            and announcement.scheduled_at > selection_time
        )
        if not candidates:
            return _empty_result(
                OperationalRegistrationStatus.NO_REGISTERABLE_PRE_OUTCOME_TARGET
            )
        selected = min(candidates, key=_announcement_key)

        final_inventory = self.announcement_source.read()
        if final_inventory.status is not TargetAnnouncementSourceStatus.AVAILABLE:
            raise TargetAnnouncementDriftError(
                "announcement authority disappeared during the pre-registration recheck"
            )
        if final_inventory != inventory:
            raise TargetAnnouncementDriftError(
                "announcement authority changed during the pre-registration recheck"
            )

        history = self.causal_history_authority.resolve(selected.target)
        if type(history) is not CausalHistoryRef:
            raise CausalHistoryAuthorityError(
                "causal-history authority returned an unsupported value"
            )
        try:
            history.validate_against(selected.target)
        except ValueError as exc:
            raise CausalHistoryAuthorityError(str(exc)) from exc

        result = self.registration_service.register(
            PreOutcomeTargetRegistrationRequest(
                announcement=selected,
                causal_history=history,
            )
        )
        status = (
            OperationalRegistrationStatus.CREATED
            if result.status is RegistrationSyncStatus.CREATED
            else OperationalRegistrationStatus.EXACT_IDEMPOTENT_NO_OP
        )
        return OperationalRegistrationResult(
            status=status,
            announcement=selected,
            causal_history=history,
            registration=result.registration,
        )


def _empty_result(status: OperationalRegistrationStatus) -> OperationalRegistrationResult:
    return OperationalRegistrationResult(
        status=status,
        announcement=None,
        causal_history=None,
        registration=None,
    )


def _announcement_key(
    announcement: TargetAnnouncement,
) -> tuple[datetime, str, int, str]:
    return (
        announcement.scheduled_at,
        announcement.target.draw_date.isoformat(),
        int(announcement.target.draw_number),
        announcement.target.draw_number,
    )


def _require_utc(value: object) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.tzinfo is not UTC:
        raise PreOutcomeTargetOperationalError(
            "the operational clock must return a timezone-aware UTC datetime"
        )


__all__ = [
    "CausalHistoryAuthority",
    "CausalHistoryAuthorityError",
    "OperationalRegistrationResult",
    "OperationalRegistrationStatus",
    "OutcomePresenceEvidenceUnavailableError",
    "PreOutcomeTargetOperationalError",
    "PreOutcomeTargetOperationalService",
    "TargetAnnouncementAuthorityError",
    "TargetAnnouncementDriftError",
    "TargetAnnouncementInventory",
    "TargetAnnouncementSource",
    "TargetAnnouncementSourceStatus",
]
