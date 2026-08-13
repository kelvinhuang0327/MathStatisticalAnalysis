"""Application contracts for pre-outcome target registration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import UTC, date, datetime, timedelta, timezone
from threading import Barrier, Lock
from typing import cast

import pytest

from lottolab.application.pre_outcome_target import (
    CorruptAuthorityError,
    InvalidOutcomeAbsenceAttestationError,
    InvalidScheduleTimeError,
    OutcomeAlreadyAvailableError,
    PreOutcomeTargetAuthorityStore,
    PreOutcomeTargetRegistrationRequest,
    PreOutcomeTargetRegistrationService,
    RegistrationSyncStatus,
    TargetConflictError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)

_REGISTERED_AT = datetime(2026, 1, 2, 8, tzinfo=UTC)
_SCHEDULED_AT = datetime(2026, 1, 2, 12, tzinfo=UTC)


def _source(digest: str = "1" * 64) -> TargetSourceProvenance:
    return TargetSourceProvenance(
        source_id="explicit-synthetic-schedule-authority",
        source_version="v1",
        source_locator="fixture://schedule/100",
        source_sha256=digest,
        observed_at=datetime(2026, 1, 2, 7, tzinfo=UTC),
    )


def _announcement(*, digest: str = "1" * 64) -> TargetAnnouncement:
    return TargetAnnouncement(
        target=ObservationTarget(LotteryType.BIG_LOTTO, "100", date(2026, 1, 2)),
        schedule_timezone="Asia/Taipei",
        scheduled_at=_SCHEDULED_AT,
        source=_source(digest),
    )


def _history(digest: str = "2" * 64) -> CausalHistoryRef:
    return CausalHistoryRef(1, "99", date(2026, 1, 1), digest)


class _MemoryStore:
    def __init__(self) -> None:
        self.record: PreOutcomeTargetRegistration | None = None

    def get_registration(self, target: ObservationTarget) -> PreOutcomeTargetRegistration | None:
        if self.record is None or self.record.target != target:
            return None
        return self.record

    def create_registration(self, registration: PreOutcomeTargetRegistration) -> CreateOnceOutcome:
        if self.record is None:
            self.record = registration
            return CreateOnceOutcome.INSERTED
        if self.record == registration:
            return CreateOnceOutcome.ALREADY_PRESENT
        return CreateOnceOutcome.CONFLICT


class _ConflictStore(_MemoryStore):
    def create_registration(self, registration: PreOutcomeTargetRegistration) -> CreateOnceOutcome:
        del registration
        return CreateOnceOutcome.CONFLICT


class _RacingStore:
    """Force two services past their initial miss before either create."""

    def __init__(self) -> None:
        self.record: PreOutcomeTargetRegistration | None = None
        self._initial_reads = 0
        self._initial_read_barrier = Barrier(2)
        self._create_barrier = Barrier(2)
        self._lock = Lock()

    def get_registration(self, target: ObservationTarget) -> PreOutcomeTargetRegistration | None:
        with self._lock:
            initial_miss = self.record is None and self._initial_reads < 2
            if initial_miss:
                self._initial_reads += 1
            record = self.record
        if initial_miss:
            self._initial_read_barrier.wait(timeout=5)
            return None
        if record is None or record.target != target:
            return None
        return record

    def create_registration(self, registration: PreOutcomeTargetRegistration) -> CreateOnceOutcome:
        self._create_barrier.wait(timeout=5)
        with self._lock:
            if self.record is None:
                self.record = registration
                return CreateOnceOutcome.INSERTED
            if self.record == registration:
                return CreateOnceOutcome.ALREADY_PRESENT
            return CreateOnceOutcome.CONFLICT


class _AlreadyPresentContractViolationStore(_MemoryStore):
    def __init__(self, persisted: PreOutcomeTargetRegistration | None) -> None:
        super().__init__()
        self.persisted = persisted
        self.get_calls = 0

    def get_registration(self, target: ObservationTarget) -> PreOutcomeTargetRegistration | None:
        self.get_calls += 1
        if self.get_calls == 1:
            return None
        if self.persisted is None or self.persisted.target != target:
            return None
        return self.persisted

    def create_registration(self, registration: PreOutcomeTargetRegistration) -> CreateOnceOutcome:
        del registration
        return CreateOnceOutcome.ALREADY_PRESENT


class _InvalidOutcomeStore(_MemoryStore):
    def create_registration(self, registration: PreOutcomeTargetRegistration) -> CreateOnceOutcome:
        del registration
        return cast(CreateOnceOutcome, "UNSUPPORTED")


class _Probe:
    def __init__(self, presence: OutcomePresenceAtPrediction) -> None:
        self.presence = presence
        self.calls: list[tuple[ObservationTarget, datetime]] = []

    def probe(self, target: ObservationTarget, *, as_of: datetime) -> OutcomePresenceAttestation:
        self.calls.append((target, as_of))
        return OutcomePresenceAttestation(
            target=target,
            presence=self.presence,
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="synthetic-presence-only-probe",
                source_version="v1",
                source_locator="fixture://presence/100",
                source_sha256="3" * 64,
                observed_at=as_of,
            ),
        )


class _StaleProbe(_Probe):
    def probe(self, target: ObservationTarget, *, as_of: datetime) -> OutcomePresenceAttestation:
        attestation = super().probe(target, as_of=as_of)
        return OutcomePresenceAttestation(
            target=attestation.target,
            presence=attestation.presence,
            attested_at=datetime(2026, 1, 2, 7, 30, tzinfo=UTC),
            source=TargetSourceProvenance(
                source_id="stale-presence-only-probe",
                source_version="v1",
                source_locator="fixture://presence/stale/100",
                source_sha256="7" * 64,
                observed_at=datetime(2026, 1, 2, 7, 30, tzinfo=UTC),
            ),
        )


class _WrongTargetProbe(_Probe):
    def probe(self, target: ObservationTarget, *, as_of: datetime) -> OutcomePresenceAttestation:
        super().probe(target, as_of=as_of)
        return OutcomePresenceAttestation(
            target=ObservationTarget(
                target.lottery_type,
                str(int(target.draw_number) + 1),
                target.draw_date,
            ),
            presence=self.presence,
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="wrong-target-presence-only-probe",
                source_version="v1",
                source_locator="fixture://presence/wrong-target",
                source_sha256="6" * 64,
                observed_at=as_of,
            ),
        )


class _SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def _service(
    store: PreOutcomeTargetAuthorityStore,
    probe: _Probe,
    *,
    now: datetime = _REGISTERED_AT,
    clock: _SequenceClock | None = None,
) -> PreOutcomeTargetRegistrationService:
    return PreOutcomeTargetRegistrationService(
        store=store,
        outcome_presence_probe=probe,
        clock=clock or (lambda: now),
    )


def test_registration_service_creates_then_returns_original_exact_no_op() -> None:
    store = _MemoryStore()
    probe = _Probe(OutcomePresenceAtPrediction.ABSENT)
    request = PreOutcomeTargetRegistrationRequest(_announcement(), _history())
    service = _service(store, probe)

    created = service.register(request)
    replayed = _service(
        store,
        _Probe(OutcomePresenceAtPrediction.PRESENT),
        now=datetime(2026, 1, 2, 9, tzinfo=UTC),
    ).register(request)

    assert created.status is RegistrationSyncStatus.CREATED
    assert replayed.status is RegistrationSyncStatus.EXACT_IDEMPOTENT_NO_OP
    assert replayed.registration is created.registration
    assert replayed.registration.registered_at == _REGISTERED_AT
    assert probe.calls == [(request.announcement.target, _REGISTERED_AT)]


def test_presence_probe_is_structurally_presence_only_and_present_fails_closed() -> None:
    assert {field.name for field in fields(OutcomePresenceAttestation)} == {
        "target",
        "presence",
        "attested_at",
        "source",
    }
    assert not any(
        name in {"main_numbers", "special_number", "outcome_hash"}
        for name in {field.name for field in fields(OutcomePresenceAttestation)}
    )
    store = _MemoryStore()

    with pytest.raises(OutcomeAlreadyAvailableError, match="already available"):
        _service(store, _Probe(OutcomePresenceAtPrediction.PRESENT)).register(
            PreOutcomeTargetRegistrationRequest(_announcement(), _history())
        )

    assert store.record is None


@pytest.mark.parametrize(
    "probe",
    [
        _StaleProbe(OutcomePresenceAtPrediction.ABSENT),
        _WrongTargetProbe(OutcomePresenceAtPrediction.ABSENT),
    ],
)
def test_stale_or_wrong_target_attestation_fails_closed(probe: _Probe) -> None:
    store = _MemoryStore()

    with pytest.raises(InvalidOutcomeAbsenceAttestationError):
        _service(store, probe).register(
            PreOutcomeTargetRegistrationRequest(_announcement(), _history())
        )

    assert store.record is None


def test_probe_must_finish_before_schedule_and_clock_must_not_regress() -> None:
    request = PreOutcomeTargetRegistrationRequest(_announcement(), _history())
    before_schedule = datetime(2026, 1, 2, 11, 59, tzinfo=UTC)
    probe = _Probe(OutcomePresenceAtPrediction.ABSENT)

    with pytest.raises(InvalidScheduleTimeError, match="did not finish"):
        _service(
            _MemoryStore(),
            probe,
            clock=_SequenceClock(before_schedule, _SCHEDULED_AT),
        ).register(request)

    with pytest.raises(InvalidScheduleTimeError, match="regressed"):
        _service(
            _MemoryStore(),
            _Probe(OutcomePresenceAtPrediction.ABSENT),
            clock=_SequenceClock(_REGISTERED_AT, datetime(2026, 1, 2, 7, tzinfo=UTC)),
        ).register(request)


def test_registration_time_is_the_post_probe_clock_instant() -> None:
    probe_started_at = datetime(2026, 1, 2, 8, tzinfo=UTC)
    registered_at = datetime(2026, 1, 2, 8, 1, tzinfo=UTC)
    probe = _Probe(OutcomePresenceAtPrediction.ABSENT)

    result = _service(
        _MemoryStore(),
        probe,
        clock=_SequenceClock(probe_started_at, registered_at),
    ).register(PreOutcomeTargetRegistrationRequest(_announcement(), _history()))

    assert result.status is RegistrationSyncStatus.CREATED
    assert result.registration.absence_attestation.attested_at == probe_started_at
    assert result.registration.registered_at == registered_at


def test_domain_registration_cannot_bypass_present_outcome_rejection() -> None:
    announcement = _announcement()
    with pytest.raises(ValueError, match="requires an ABSENT"):
        PreOutcomeTargetRegistration.create(
            announcement=announcement,
            absence_attestation=OutcomePresenceAttestation(
                target=announcement.target,
                presence=OutcomePresenceAtPrediction.PRESENT,
                attested_at=_REGISTERED_AT,
                source=_source("8" * 64),
            ),
            causal_history=_history(),
            registered_at=_REGISTERED_AT,
        )


@pytest.mark.parametrize(
    "now",
    [
        _SCHEDULED_AT,
        datetime(2026, 1, 2, 13, tzinfo=UTC),
        datetime(2026, 1, 2, 20),
        datetime(
            2026,
            1,
            2,
            8,
            tzinfo=timezone(timedelta(0), name="ZERO_BUT_NOT_UTC"),
        ),
    ],
)
def test_non_utc_or_closed_schedule_time_is_rejected_before_probe(now: datetime) -> None:
    probe = _Probe(OutcomePresenceAtPrediction.ABSENT)

    with pytest.raises(InvalidScheduleTimeError):
        _service(_MemoryStore(), probe, now=now).register(
            PreOutcomeTargetRegistrationRequest(_announcement(), _history())
        )

    assert probe.calls == []


def test_different_authority_under_one_logical_target_fails_before_probe() -> None:
    store = _MemoryStore()
    first_probe = _Probe(OutcomePresenceAtPrediction.ABSENT)
    _service(store, first_probe).register(
        PreOutcomeTargetRegistrationRequest(_announcement(), _history())
    )
    second_probe = _Probe(OutcomePresenceAtPrediction.ABSENT)

    with pytest.raises(TargetConflictError, match="different immutable authority"):
        _service(store, second_probe).register(
            PreOutcomeTargetRegistrationRequest(
                _announcement(digest="9" * 64),
                _history(),
            )
        )

    assert second_probe.calls == []


def test_conflict_without_persisted_winner_is_corrupt_authority() -> None:
    store = _ConflictStore()
    probe = _Probe(OutcomePresenceAtPrediction.ABSENT)

    with pytest.raises(CorruptAuthorityError, match="without a persisted winner"):
        _service(store, probe).register(
            PreOutcomeTargetRegistrationRequest(_announcement(), _history())
        )

    assert len(probe.calls) == 1


def test_concurrent_identical_requests_return_created_and_original_no_op() -> None:
    store = _RacingStore()
    request = PreOutcomeTargetRegistrationRequest(_announcement(), _history())
    services = (
        _service(
            store,
            _Probe(OutcomePresenceAtPrediction.ABSENT),
            clock=_SequenceClock(
                datetime(2026, 1, 2, 8, tzinfo=UTC),
                datetime(2026, 1, 2, 8, 1, tzinfo=UTC),
            ),
        ),
        _service(
            store,
            _Probe(OutcomePresenceAtPrediction.ABSENT),
            clock=_SequenceClock(
                datetime(2026, 1, 2, 8, 2, tzinfo=UTC),
                datetime(2026, 1, 2, 8, 3, tzinfo=UTC),
            ),
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(service.register, request) for service in services]
        results = [future.result(timeout=5) for future in futures]

    assert {result.status for result in results} == {
        RegistrationSyncStatus.CREATED,
        RegistrationSyncStatus.EXACT_IDEMPOTENT_NO_OP,
    }
    assert store.record is not None
    assert all(result.registration == store.record for result in results)


def test_concurrent_different_requests_keep_target_conflict() -> None:
    store = _RacingStore()
    requests = (
        PreOutcomeTargetRegistrationRequest(_announcement(), _history()),
        PreOutcomeTargetRegistrationRequest(
            _announcement(digest="9" * 64),
            _history(),
        ),
    )
    services = tuple(
        _service(
            store,
            _Probe(OutcomePresenceAtPrediction.ABSENT),
            clock=_SequenceClock(
                datetime(2026, 1, 2, 8, index * 2, tzinfo=UTC),
                datetime(2026, 1, 2, 8, index * 2 + 1, tzinfo=UTC),
            ),
        )
        for index in range(2)
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(service.register, request)
            for service, request in zip(services, requests, strict=True)
        ]
        outcomes: list[object] = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=5))
            except TargetConflictError as exc:
                outcomes.append(exc)

    assert sum(isinstance(value, TargetConflictError) for value in outcomes) == 1
    assert (
        sum(getattr(value, "status", None) is RegistrationSyncStatus.CREATED for value in outcomes)
        == 1
    )


def test_broken_idempotence_and_invalid_store_outcomes_are_corrupt_authority() -> None:
    request = PreOutcomeTargetRegistrationRequest(_announcement(), _history())
    different_store = _MemoryStore()
    different = (
        _service(
            different_store,
            _Probe(OutcomePresenceAtPrediction.ABSENT),
        )
        .register(
            PreOutcomeTargetRegistrationRequest(
                _announcement(digest="9" * 64),
                _history(),
            )
        )
        .registration
    )

    for persisted in (None, different):
        with pytest.raises(CorruptAuthorityError, match="without the exact"):
            _service(
                _AlreadyPresentContractViolationStore(persisted),
                _Probe(OutcomePresenceAtPrediction.ABSENT),
            ).register(request)

    with pytest.raises(CorruptAuthorityError, match="unsupported"):
        _service(
            _InvalidOutcomeStore(),
            _Probe(OutcomePresenceAtPrediction.ABSENT),
        ).register(request)


def test_causal_history_must_end_strictly_before_announced_target() -> None:
    with pytest.raises(ValueError, match="strictly before"):
        PreOutcomeTargetRegistrationRequest(
            _announcement(),
            CausalHistoryRef(1, "100", date(2026, 1, 2), "2" * 64),
        )
