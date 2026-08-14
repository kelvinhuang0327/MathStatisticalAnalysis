"""Unit contracts for outcome-free operational target selection."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from lottolab.application.pre_outcome_target import PreOutcomeTargetRegistrationService
from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationStatus,
    PreOutcomeTargetOperationalError,
    PreOutcomeTargetOperationalService,
    TargetAnnouncementDriftError,
    TargetAnnouncementInventory,
    TargetAnnouncementSourceStatus,
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

NOW = datetime(2099, 1, 1, 8, tzinfo=UTC)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _announcement(
    lottery_type: LotteryType,
    *,
    draw_number: str,
    draw_date: date,
    scheduled_at: datetime,
    variant: str = "canonical",
) -> TargetAnnouncement:
    return TargetAnnouncement(
        target=ObservationTarget(lottery_type, draw_number, draw_date),
        schedule_timezone="Asia/Taipei",
        scheduled_at=scheduled_at,
        source=TargetSourceProvenance(
            source_id="official-schedule",
            source_version="v1",
            source_locator=f"https://example.test/{variant}/{draw_number}",
            source_sha256=_sha256(f"announcement:{variant}:{draw_number}"),
            observed_at=datetime(2099, 1, 1, 6, tzinfo=UTC),
        ),
    )


def _history(target: ObservationTarget) -> CausalHistoryRef:
    return CausalHistoryRef(
        draw_count=1,
        last_draw_number=str(int(target.draw_number) - 1),
        last_draw_date=target.draw_date.replace(day=target.draw_date.day - 1),
        history_sha256=_sha256(f"history:{target.lottery_type.value}"),
    )


class _Source:
    def __init__(self, *inventories: TargetAnnouncementInventory) -> None:
        self._inventories = inventories
        self.calls = 0

    def read(self) -> TargetAnnouncementInventory:
        index = min(self.calls, len(self._inventories) - 1)
        self.calls += 1
        return self._inventories[index]


class _HistoryAuthority:
    def __init__(self) -> None:
        self.calls: list[ObservationTarget] = []

    def resolve(self, target: ObservationTarget) -> CausalHistoryRef:
        self.calls.append(target)
        return _history(target)


class _Probe:
    def __init__(self) -> None:
        self.calls: list[tuple[ObservationTarget, datetime]] = []

    def probe(
        self,
        target: ObservationTarget,
        *,
        as_of: datetime,
    ) -> OutcomePresenceAttestation:
        self.calls.append((target, as_of))
        return OutcomePresenceAttestation(
            target=target,
            presence=OutcomePresenceAtPrediction.ABSENT,
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="presence",
                source_version="v1",
                source_locator="fixture://presence",
                source_sha256=_sha256("presence"),
                observed_at=as_of,
            ),
        )


class _Store:
    def __init__(self) -> None:
        self.record: PreOutcomeTargetRegistration | None = None
        self.create_calls = 0

    def get_registration(
        self,
        target: ObservationTarget,
    ) -> PreOutcomeTargetRegistration | None:
        return self.record if self.record is not None and self.record.target == target else None

    def create_registration(
        self,
        registration: PreOutcomeTargetRegistration,
    ) -> CreateOnceOutcome:
        self.create_calls += 1
        if self.record is None:
            self.record = registration
            return CreateOnceOutcome.INSERTED
        return (
            CreateOnceOutcome.ALREADY_PRESENT
            if self.record == registration
            else CreateOnceOutcome.CONFLICT
        )


def _inventory(
    *announcements: TargetAnnouncement,
    status: TargetAnnouncementSourceStatus = TargetAnnouncementSourceStatus.AVAILABLE,
) -> TargetAnnouncementInventory:
    return TargetAnnouncementInventory(status, announcements)


def _service(
    source: _Source,
) -> tuple[PreOutcomeTargetOperationalService, _HistoryAuthority, _Probe, _Store]:
    history = _HistoryAuthority()
    probe = _Probe()
    store = _Store()
    registration = PreOutcomeTargetRegistrationService(
        store=store,
        outcome_presence_probe=probe,
        clock=lambda: NOW,
    )
    return (
        PreOutcomeTargetOperationalService(
            announcement_source=source,
            causal_history_authority=history,
            registration_service=registration,
            clock=lambda: NOW,
        ),
        history,
        probe,
        store,
    )


def test_missing_canonical_source_is_a_closed_no_write_result() -> None:
    source = _Source(
        _inventory(status=TargetAnnouncementSourceStatus.NOT_CONFIGURED)
    )
    service, history, probe, store = _service(source)

    result = service.register_earliest(LotteryType.BIG_LOTTO)

    assert result.status is OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT
    assert result.announcement is None
    assert result.causal_history is None
    assert result.registration is None
    assert source.calls == 1
    assert history.calls == []
    assert probe.calls == []
    assert store.create_calls == 0


def test_no_matching_future_target_is_a_closed_no_write_result() -> None:
    past = _announcement(
        LotteryType.BIG_LOTTO,
        draw_number="999999900",
        draw_date=date(2099, 1, 1),
        scheduled_at=datetime(2099, 1, 1, 7, tzinfo=UTC),
    )
    other_lottery = _announcement(
        LotteryType.DAILY_539,
        draw_number="999999901",
        draw_date=date(2099, 1, 2),
        scheduled_at=datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
    )
    source = _Source(_inventory(past, other_lottery))
    service, history, probe, store = _service(source)

    result = service.register_earliest(LotteryType.BIG_LOTTO)

    assert result.status is OperationalRegistrationStatus.NO_REGISTERABLE_PRE_OUTCOME_TARGET
    assert source.calls == 1
    assert history.calls == []
    assert probe.calls == []
    assert store.create_calls == 0


@pytest.mark.parametrize("lottery_type", tuple(LotteryType))
def test_each_lottery_selects_the_earliest_future_announcement_and_registers(
    lottery_type: LotteryType,
) -> None:
    later = _announcement(
        lottery_type,
        draw_number="999999902",
        draw_date=date(2099, 1, 3),
        scheduled_at=datetime(2099, 1, 3, 12, 30, tzinfo=UTC),
    )
    earliest = _announcement(
        lottery_type,
        draw_number="999999901",
        draw_date=date(2099, 1, 2),
        scheduled_at=datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
    )
    source = _Source(_inventory(later, earliest))
    service, history, probe, store = _service(source)

    result = service.register_earliest(lottery_type)

    assert result.status is OperationalRegistrationStatus.CREATED
    assert result.announcement == earliest
    assert result.registration is store.record
    assert result.registration is not None
    assert result.registration.target == earliest.target
    assert result.causal_history == _history(earliest.target)
    assert source.calls == 2
    assert history.calls == [earliest.target]
    assert probe.calls == [(earliest.target, NOW)]
    assert store.create_calls == 1


def test_selected_announcement_drift_fails_before_history_or_registration() -> None:
    selected = _announcement(
        LotteryType.BIG_LOTTO,
        draw_number="999999901",
        draw_date=date(2099, 1, 2),
        scheduled_at=datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
    )
    changed = _announcement(
        LotteryType.BIG_LOTTO,
        draw_number="999999901",
        draw_date=date(2099, 1, 2),
        scheduled_at=datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
        variant="changed",
    )
    source = _Source(_inventory(selected), _inventory(changed))
    service, history, probe, store = _service(source)

    with pytest.raises(TargetAnnouncementDriftError, match="changed"):
        service.register_earliest(LotteryType.BIG_LOTTO)

    assert history.calls == []
    assert probe.calls == []
    assert store.create_calls == 0


def test_inventory_drift_that_adds_an_earlier_target_fails_before_write() -> None:
    selected = _announcement(
        LotteryType.BIG_LOTTO,
        draw_number="999999902",
        draw_date=date(2099, 1, 3),
        scheduled_at=datetime(2099, 1, 3, 12, 30, tzinfo=UTC),
    )
    newly_earlier = _announcement(
        LotteryType.BIG_LOTTO,
        draw_number="999999901",
        draw_date=date(2099, 1, 2),
        scheduled_at=datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
    )
    source = _Source(_inventory(selected), _inventory(newly_earlier, selected))
    service, history, probe, store = _service(source)

    with pytest.raises(TargetAnnouncementDriftError, match="authority changed"):
        service.register_earliest(LotteryType.BIG_LOTTO)

    assert history.calls == []
    assert probe.calls == []
    assert store.create_calls == 0


def test_operational_clock_must_be_exact_utc() -> None:
    source = _Source(_inventory())
    service, _, _, _ = _service(source)
    object.__setattr__(service, "clock", lambda: datetime(2099, 1, 1, 8))

    with pytest.raises(PreOutcomeTargetOperationalError, match="UTC"):
        service.register_earliest(LotteryType.BIG_LOTTO)

    assert source.calls == 0
