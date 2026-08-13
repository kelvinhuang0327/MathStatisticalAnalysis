"""Registration orchestration for immutable pre-outcome target authority.

The service accepts an explicit source announcement and a presence-only probe.
It never receives official outcome content, derives draw schedules, produces a
prediction, or scores a result.  Exact existing registrations are returned as
idempotent no-ops; competing authority for the same logical draw fails closed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)


class PreOutcomeTargetAuthorityError(RuntimeError):
    """Base class for fail-closed target-authority application errors."""


class TargetConflictError(PreOutcomeTargetAuthorityError):
    """The logical target already has different immutable authority."""


class OutcomeAlreadyAvailableError(PreOutcomeTargetAuthorityError):
    """The presence-only probe found the target outcome before registration."""


class InvalidScheduleTimeError(PreOutcomeTargetAuthorityError):
    """The injected registration time is invalid or outside the pre-draw window."""


class InvalidOutcomeAbsenceAttestationError(PreOutcomeTargetAuthorityError):
    """The presence-only probe returned stale or mismatched authority evidence."""


class CorruptAuthorityError(PreOutcomeTargetAuthorityError):
    """The authority store violated its create-once persistence contract."""


class RegistrationSyncStatus(StrEnum):
    CREATED = "CREATED"
    EXACT_IDEMPOTENT_NO_OP = "EXACT_IDEMPOTENT_NO_OP"


@dataclass(frozen=True, slots=True)
class PreOutcomeTargetRegistrationRequest:
    """Caller-supplied authority inputs, deliberately excluding outcome content."""

    announcement: TargetAnnouncement
    causal_history: CausalHistoryRef

    def __post_init__(self) -> None:
        if type(self.announcement) is not TargetAnnouncement:
            raise ValueError("announcement must be a TargetAnnouncement")
        if type(self.causal_history) is not CausalHistoryRef:
            raise ValueError("causal_history must be a CausalHistoryRef")
        self.causal_history.validate_against(self.announcement.target)


@dataclass(frozen=True, slots=True)
class RegistrationSyncResult:
    status: RegistrationSyncStatus
    registration: PreOutcomeTargetRegistration

    def __post_init__(self) -> None:
        if type(self.status) is not RegistrationSyncStatus:
            raise ValueError("status must be a RegistrationSyncStatus")
        if type(self.registration) is not PreOutcomeTargetRegistration:
            raise ValueError("registration must be a PreOutcomeTargetRegistration")


@runtime_checkable
class OutcomePresenceProbe(Protocol):
    """Phase-A port exposing presence and attestation evidence, never outcome data."""

    def probe(
        self,
        target: ObservationTarget,
        *,
        as_of: datetime,
    ) -> OutcomePresenceAttestation: ...


@runtime_checkable
class PreOutcomeTargetAuthorityStore(Protocol):
    """Durable create-once boundary for accepted target registrations."""

    def get_registration(
        self,
        target: ObservationTarget,
    ) -> PreOutcomeTargetRegistration | None: ...

    def create_registration(
        self,
        registration: PreOutcomeTargetRegistration,
    ) -> CreateOnceOutcome: ...


class PreOutcomeTargetRegistrationService:
    """Accept one explicit future target after a presence-only absence check."""

    def __init__(
        self,
        *,
        store: PreOutcomeTargetAuthorityStore,
        outcome_presence_probe: OutcomePresenceProbe,
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._outcome_presence_probe = outcome_presence_probe
        self._clock = clock

    def register(
        self,
        request: PreOutcomeTargetRegistrationRequest,
    ) -> RegistrationSyncResult:
        if type(request) is not PreOutcomeTargetRegistrationRequest:
            raise ValueError("request must be a PreOutcomeTargetRegistrationRequest")

        existing = self._store.get_registration(request.announcement.target)
        if existing is not None:
            if existing.matches_request(
                announcement=request.announcement,
                causal_history=request.causal_history,
            ):
                return RegistrationSyncResult(
                    RegistrationSyncStatus.EXACT_IDEMPOTENT_NO_OP,
                    existing,
                )
            raise TargetConflictError(
                "target identity already contains different immutable authority"
            )

        probe_started_at = self._clock()
        _require_utc_registration_time(probe_started_at)
        if probe_started_at >= request.announcement.scheduled_at:
            raise InvalidScheduleTimeError(
                "registration must occur strictly before the announced schedule"
            )

        attestation = self._outcome_presence_probe.probe(
            request.announcement.target,
            as_of=probe_started_at,
        )
        registered_at = self._clock()
        _require_utc_registration_time(registered_at)
        if registered_at < probe_started_at:
            raise InvalidScheduleTimeError("registration clock regressed during the presence check")
        if registered_at >= request.announcement.scheduled_at:
            raise InvalidScheduleTimeError(
                "presence check did not finish strictly before the announced schedule"
            )
        if type(attestation) is not OutcomePresenceAttestation:
            raise ValueError("outcome presence probe must return an OutcomePresenceAttestation")
        if attestation.target != request.announcement.target:
            raise InvalidOutcomeAbsenceAttestationError(
                "outcome presence attestation target does not match the announced target"
            )
        if attestation.attested_at != probe_started_at:
            raise InvalidOutcomeAbsenceAttestationError(
                "outcome presence attestation must bind the requested as_of instant"
            )
        if attestation.presence is OutcomePresenceAtPrediction.PRESENT:
            raise OutcomeAlreadyAvailableError(
                "official outcome was already available at target registration"
            )

        try:
            registration = PreOutcomeTargetRegistration.create(
                announcement=request.announcement,
                absence_attestation=attestation,
                causal_history=request.causal_history,
                registered_at=registered_at,
            )
        except ValueError as exc:
            if "time" in str(exc) or "scheduled" in str(exc) or "registered" in str(exc):
                raise InvalidScheduleTimeError(str(exc)) from exc
            raise

        outcome = self._store.create_registration(registration)
        if type(outcome) is not CreateOnceOutcome:
            raise CorruptAuthorityError(
                "authority store returned an unsupported create-once outcome"
            )
        if outcome is CreateOnceOutcome.INSERTED:
            return RegistrationSyncResult(RegistrationSyncStatus.CREATED, registration)
        if outcome is CreateOnceOutcome.CONFLICT:
            persisted = self._store.get_registration(registration.target)
            if persisted is None:
                raise CorruptAuthorityError(
                    "authority store reported conflict without a persisted winner"
                )
            if persisted.matches_request(
                announcement=request.announcement,
                causal_history=request.causal_history,
            ):
                return RegistrationSyncResult(
                    RegistrationSyncStatus.EXACT_IDEMPOTENT_NO_OP,
                    persisted,
                )
            raise TargetConflictError(
                "target identity already contains different immutable authority"
            )

        persisted = self._store.get_registration(registration.target)
        if persisted is None or persisted != registration:
            raise CorruptAuthorityError(
                "authority store reported idempotence without the exact persisted record"
            )
        return RegistrationSyncResult(
            RegistrationSyncStatus.EXACT_IDEMPOTENT_NO_OP,
            persisted,
        )


def _require_utc_registration_time(value: object) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.tzinfo is not UTC:
        raise InvalidScheduleTimeError(
            "the injected registration clock must return a timezone-aware UTC datetime"
        )
