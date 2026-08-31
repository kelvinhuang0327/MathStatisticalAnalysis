"""Bind one runnable schedule authority to the immutable prediction seal.

This application service is deliberately game-neutral.  It consumes the
existing pre-outcome runnable-target gate, adds the complete Stage A schedule
fact digest to the caller's producer fingerprint, validates the registered
target/history binding, and only then invokes the generic prediction phase.
It owns no ticket shape, prize rule, schedule inference, outcome reader, or
scheduler policy.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationResult,
    OperationalRegistrationStatus,
)
from lottolab.application.prospective_observer import (
    PredictionPhaseService,
    PredictionProducer,
    PredictionSyncStatus,
    ProspectiveGameContract,
    ProspectiveObservationStore,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    validate_prediction_context_binding,
)
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionPhaseRequest,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
)

_SCHEDULE_DEPENDENCY_PREFIX = "lottolab://stage-a-schedule/"
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE = "complete immutable Stage A schedule fact"


class RunnablePredictionSealError(RuntimeError):
    """Base class for fail-closed runnable-target seal errors."""


class ScheduleAuthorityDigestUnavailableError(RunnablePredictionSealError):
    """A runnable T539/P638 target lacks its complete Stage A fact digest."""


class PredictionSealCausalityError(RunnablePredictionSealError):
    """Prediction production did not begin strictly before the scheduled draw."""


class RunnablePredictionSealStatus(StrEnum):
    CREATED = "CREATED"
    EXACT_IDEMPOTENT_NO_OP = "EXACT_IDEMPOTENT_NO_OP"
    NO_RUNNABLE_TARGET = "NO_RUNNABLE_TARGET"


@runtime_checkable
class ScheduledPredictionProducerFactory(Protocol):
    """Build one outcome-free producer only after all runnable gates pass."""

    def __call__(
        self,
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> PredictionProducer: ...


@runtime_checkable
class RunnableTargetRegistrationService(Protocol):
    """Resolve and register only the canonical earliest runnable target."""

    def register_earliest(
        self,
        lottery_type: LotteryType,
    ) -> OperationalRegistrationResult: ...


@dataclass(frozen=True, slots=True)
class RunnablePredictionSealResult:
    status: RunnablePredictionSealStatus
    lottery_type: LotteryType
    registration_status: OperationalRegistrationStatus
    registration: PreOutcomeTargetRegistration | None
    immutable_schedule_sha256: str | None
    prediction: PredictionRecord | None

    def __post_init__(self) -> None:
        if type(self.status) is not RunnablePredictionSealStatus:
            raise ValueError("status must be a RunnablePredictionSealStatus")
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.registration_status) is not OperationalRegistrationStatus:
            raise ValueError("registration_status must be an OperationalRegistrationStatus")
        completed = self.status in {
            RunnablePredictionSealStatus.CREATED,
            RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP,
        }
        values_present = (
            type(self.registration) is PreOutcomeTargetRegistration
            and type(self.immutable_schedule_sha256) is str
            and type(self.prediction) is PredictionRecord
        )
        if completed != values_present:
            raise ValueError("completed seal results require complete authority and prediction")
        if not completed and any(
            value is not None
            for value in (
                self.registration,
                self.immutable_schedule_sha256,
                self.prediction,
            )
        ):
            raise ValueError("no-target seal results must not expose partial authority")
        if completed:
            assert self.registration is not None
            assert self.immutable_schedule_sha256 is not None
            assert self.prediction is not None
            if _SHA256.fullmatch(self.immutable_schedule_sha256) is None:
                raise ValueError(
                    "immutable_schedule_sha256 must be a lowercase SHA-256 digest"
                )
            if self.registration.target.lottery_type is not self.lottery_type:
                raise ValueError("registration belongs to another lottery")
            if self.prediction.identity.lottery_type is not self.lottery_type:
                raise ValueError("prediction belongs to another lottery")


@dataclass(frozen=True, slots=True)
class RunnablePredictionSealService:
    """Seal the earliest explicitly runnable target for one configured game."""

    lottery_type: LotteryType
    registration_service: RunnableTargetRegistrationService
    store: ProspectiveObservationStore
    producer_factory: ScheduledPredictionProducerFactory
    cohort: FrozenCohortRef
    base_producer_fingerprint: ProducerFingerprint
    game_contracts: Mapping[LotteryType, ProspectiveGameContract]
    clock: Callable[[], datetime]

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if self.cohort.lottery_type is not self.lottery_type:
            raise ValueError("cohort belongs to another lottery")
        if self.lottery_type not in self.game_contracts:
            raise ValueError("game contract is missing for configured lottery")
        _require_callable_member(
            self.registration_service,
            "register_earliest",
            "registration_service",
        )
        _require_callable_member(self.producer_factory, "__call__", "producer_factory")

    def seal_earliest(self) -> RunnablePredictionSealResult:
        cycle_started_at = self.clock()
        _require_utc(cycle_started_at)
        authority = self.registration_service.register_earliest(self.lottery_type)
        if authority.registration is None:
            return _no_target_result(self.lottery_type, authority)

        announcement = authority.announcement
        causal_history = authority.causal_history
        schedule_digest = authority.immutable_schedule_sha256
        assert announcement is not None
        assert causal_history is not None
        if schedule_digest is None:
            raise ScheduleAuthorityDigestUnavailableError(
                "runnable target lacks the complete immutable Stage A schedule fact digest"
            )

        reference_time = self.clock()
        _require_utc(reference_time)
        if reference_time < cycle_started_at:
            raise PredictionSealCausalityError("prediction reference clock regressed")
        if reference_time >= announcement.scheduled_at:
            raise PredictionSealCausalityError(
                "prediction production must begin strictly before scheduled_at"
            )

        fingerprint = bind_stage_a_schedule_authority(
            self.base_producer_fingerprint,
            announcement=announcement,
            immutable_schedule_sha256=schedule_digest,
        )
        context = PredictionContext(
            target=announcement.target,
            cohort=self.cohort,
            producer_fingerprint=fingerprint,
            causal_history=causal_history,
        )
        validate_prediction_context_binding(authority.registration, context)
        producer = self.producer_factory(announcement, reference_time)
        _require_callable_member(producer, "predict", "producer_factory result")
        phase = PredictionPhaseService(
            store=self.store,
            producer=producer,
            game_contracts=self.game_contracts,
            clock=lambda: reference_time,
        )
        sealed = phase.sync(
            PredictionPhaseRequest(
                context=context,
                outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
            )
        )
        if sealed.status is PredictionSyncStatus.CREATED:
            status = RunnablePredictionSealStatus.CREATED
        elif sealed.status is PredictionSyncStatus.EXACT_IDEMPOTENT_NO_OP:
            status = RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP
        else:
            raise RuntimeError(f"unsupported prediction sync status: {sealed.status!r}")
        return RunnablePredictionSealResult(
            status=status,
            lottery_type=self.lottery_type,
            registration_status=authority.status,
            registration=authority.registration,
            immutable_schedule_sha256=schedule_digest,
            prediction=sealed.prediction,
        )


def bind_stage_a_schedule_authority(
    base: ProducerFingerprint,
    *,
    announcement: TargetAnnouncement,
    immutable_schedule_sha256: str,
) -> ProducerFingerprint:
    """Add exactly one target-specific Stage A digest to a producer manifest."""

    if type(base) is not ProducerFingerprint:
        raise ValueError("base must be a ProducerFingerprint")
    if type(announcement) is not TargetAnnouncement:
        raise ValueError("announcement must be a TargetAnnouncement")
    if any(
        dependency.locator.startswith(_SCHEDULE_DEPENDENCY_PREFIX)
        or dependency.load_bearing_role == SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE
        for dependency in base.dependencies
    ):
        raise ValueError("base producer fingerprint must be schedule-independent")
    target = announcement.target
    dependency = ProducerDependency(
        locator=(
            f"{_SCHEDULE_DEPENDENCY_PREFIX}{target.lottery_type.value}/"
            f"{target.draw_number}"
        ),
        source_sha256=immutable_schedule_sha256,
        load_bearing_role=SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE,
    )
    return ProducerFingerprint.create(
        producer_id=base.producer_id,
        producer_version=base.producer_version,
        dependencies=(*base.dependencies, dependency),
    )


def _no_target_result(
    lottery_type: LotteryType,
    authority: OperationalRegistrationResult,
) -> RunnablePredictionSealResult:
    if authority.status not in {
        OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT,
        OperationalRegistrationStatus.NO_REGISTERABLE_PRE_OUTCOME_TARGET,
    }:
        raise ValueError("missing registration has an incompatible operational status")
    return RunnablePredictionSealResult(
        status=RunnablePredictionSealStatus.NO_RUNNABLE_TARGET,
        lottery_type=lottery_type,
        registration_status=authority.status,
        registration=None,
        immutable_schedule_sha256=None,
        prediction=None,
    )


def _require_utc(value: object) -> None:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise PredictionSealCausalityError(
            "prediction seal clock must return a timezone-aware UTC datetime"
        )


def _require_callable_member(value: object, member: str, label: str) -> None:
    if not callable(getattr(value, member, None)):
        raise ValueError(f"{label} must provide callable {member}")


__all__ = [
    "SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE",
    "PredictionSealCausalityError",
    "RunnablePredictionSealError",
    "RunnablePredictionSealResult",
    "RunnablePredictionSealService",
    "RunnablePredictionSealStatus",
    "RunnableTargetRegistrationService",
    "ScheduleAuthorityDigestUnavailableError",
    "ScheduledPredictionProducerFactory",
    "bind_stage_a_schedule_authority",
]
