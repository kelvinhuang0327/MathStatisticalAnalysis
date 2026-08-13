"""End-to-end contracts for the shared pre-outcome target authority.

Every target in this module is synthetic, every store is rooted under
``tmp_path``, and an autouse network tripwire proves that registration needs no
live source client.  Official outcomes appear only after registration to test
the pure identity-binding boundary; no game or prize evaluator is composed.
"""

from __future__ import annotations

import hashlib
import inspect
import socket
from collections.abc import Mapping
from dataclasses import fields
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NoReturn, cast

import pytest

from lottolab.application.pre_outcome_target import (
    OutcomeAlreadyAvailableError,
    OutcomePresenceProbe,
    PreOutcomeTargetRegistrationRequest,
    PreOutcomeTargetRegistrationService,
    RegistrationSyncStatus,
    TargetConflictError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION,
    OutcomePresenceAttestation,
    PredictionContextBindingMismatchError,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetBindingMismatchError,
    TargetSourceProvenance,
    validate_official_outcome_binding,
    validate_prediction_context_binding,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionContext,
    ProducerDependency,
    ProducerFingerprint,
    TemporalProvenance,
)
from lottolab.infrastructure.pre_outcome_target_store import (
    FileSystemPreOutcomeTargetAuthorityStore,
)

_LOTTERIES = (
    LotteryType.BIG_LOTTO,
    LotteryType.DAILY_539,
    LotteryType.POWER_LOTTO,
)
_DRAW_NUMBER = "999999901"
_DRAW_DATE = date(2099, 1, 2)
_SOURCE_OBSERVED_AT = datetime(2099, 1, 1, 6, tzinfo=UTC)
_REGISTERED_AT = datetime(2099, 1, 1, 8, tzinfo=UTC)
_SCHEDULED_AT = datetime(2099, 1, 2, 12, 30, tzinfo=UTC)
_FORBIDDEN_PRIZE_OR_OUTCOME_KEYS = {
    "main_numbers",
    "main_hits",
    "outcome_hash",
    "payout",
    "predicted_main_numbers",
    "predicted_special_number",
    "prize_result",
    "prize_tier",
    "score",
    "special_hit",
    "special_number",
    "ticket_results",
    "winning_main_numbers",
    "winning_special_number",
    "zone1_hits",
    "zone2_hit",
}


@pytest.fixture(autouse=True)
def _network_is_forbidden(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Turn an accidental source fetch into an immediate integration failure."""

    def forbidden_network(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("pre-outcome target registration must not access the network")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "socket", forbidden_network)


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _target(lottery_type: LotteryType) -> ObservationTarget:
    return ObservationTarget(lottery_type, _DRAW_NUMBER, _DRAW_DATE)


def _source(
    lottery_type: LotteryType,
    *,
    role: str,
    variant: str = "canonical",
    observed_at: datetime = _SOURCE_OBSERVED_AT,
) -> TargetSourceProvenance:
    return TargetSourceProvenance(
        source_id=f"synthetic-{role}-authority",
        source_version="v1",
        source_locator=(
            f"fixture://pre-outcome/{role}/{lottery_type.value.lower()}/{_DRAW_NUMBER}"
        ),
        source_sha256=_sha256(f"{lottery_type.value}:{role}:{variant}"),
        observed_at=observed_at,
    )


def _announcement(
    lottery_type: LotteryType,
    *,
    source_variant: str = "canonical",
) -> TargetAnnouncement:
    return TargetAnnouncement(
        target=_target(lottery_type),
        schedule_timezone="Asia/Taipei",
        scheduled_at=_SCHEDULED_AT,
        source=_source(
            lottery_type,
            role="schedule",
            variant=source_variant,
        ),
    )


def _history(*, digest_variant: str = "canonical") -> CausalHistoryRef:
    return CausalHistoryRef(
        draw_count=1,
        last_draw_number="999999900",
        last_draw_date=date(2099, 1, 1),
        history_sha256=_sha256(f"strictly-pre-target-history:{digest_variant}"),
    )


def _request(
    lottery_type: LotteryType,
    *,
    source_variant: str = "canonical",
    history_variant: str = "canonical",
) -> PreOutcomeTargetRegistrationRequest:
    return PreOutcomeTargetRegistrationRequest(
        announcement=_announcement(lottery_type, source_variant=source_variant),
        causal_history=_history(digest_variant=history_variant),
    )


class _RecordingPresenceProbe:
    def __init__(self, presence: OutcomePresenceAtPrediction) -> None:
        self.presence = presence
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
            presence=self.presence,
            attested_at=as_of,
            source=_source(
                target.lottery_type,
                role="presence",
                observed_at=as_of,
            ),
        )


def _service(
    store: FileSystemPreOutcomeTargetAuthorityStore,
    probe: _RecordingPresenceProbe,
    *,
    now: datetime = _REGISTERED_AT,
) -> PreOutcomeTargetRegistrationService:
    return PreOutcomeTargetRegistrationService(
        store=store,
        outcome_presence_probe=probe,
        clock=lambda: now,
    )


def _prediction_context(
    target: ObservationTarget,
    history: CausalHistoryRef,
) -> PredictionContext:
    cohort = FrozenCohortRef(
        lottery_type=target.lottery_type,
        cohort_id="synthetic-integration-cohort",
        cohort_version="v1",
        authority_sha256=_sha256(f"cohort:{target.lottery_type.value}"),
        frozen_at=datetime(2098, 12, 31, tzinfo=UTC),
        member_ids=("synthetic-member",),
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )
    fingerprint = ProducerFingerprint.create(
        producer_id="synthetic-integration-producer",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator="fixture://pre-outcome/producer",
                source_sha256=_sha256("synthetic-producer-source"),
                load_bearing_role="integration binding fixture",
            ),
        ),
    )
    return PredictionContext(
        target=target,
        cohort=cohort,
        producer_fingerprint=fingerprint,
        causal_history=history,
    )


def _official_outcome(target: ObservationTarget) -> OfficialOutcome:
    # The one-number payload is intentionally not lottery-legal.  Target
    # authority performs identity binding only and must not invoke prize rules.
    return OfficialOutcome.create(
        lottery_type=target.lottery_type,
        draw_number=target.draw_number,
        draw_date=target.draw_date,
        main_numbers=(1,),
        special_number=None,
        source_id="synthetic-later-outcome-identity",
        source_sha256=_sha256(f"later-outcome:{target.lottery_type.value}"),
    )


def _canonical_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        keys.update(mapping)
        for item in mapping.values():
            keys.update(_canonical_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in cast(list[object] | tuple[object, ...], value):
            keys.update(_canonical_keys(item))
    return keys


@pytest.mark.parametrize("lottery_type", _LOTTERIES)
def test_each_lottery_uses_the_same_outcome_free_registration_and_binding_mechanism(
    tmp_path: Path,
    lottery_type: LotteryType,
) -> None:
    authority_root = tmp_path / "synthetic-authority"
    store = FileSystemPreOutcomeTargetAuthorityStore(authority_root)
    probe = _RecordingPresenceProbe(OutcomePresenceAtPrediction.ABSENT)
    request = _request(lottery_type)

    result = _service(store, probe).register(request)
    registration = result.registration

    assert result.status is RegistrationSyncStatus.CREATED
    assert registration.schema_version == PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION
    assert registration.registered_at == _REGISTERED_AT
    assert registration.absence_attestation.presence is OutcomePresenceAtPrediction.ABSENT
    assert probe.calls == [(request.announcement.target, _REGISTERED_AT)]
    assert store.root == authority_root.absolute()
    assert tmp_path in store.root.parents

    projected = registration.to_observation_target()
    assert projected is registration.target
    assert projected == request.announcement.target
    validate_prediction_context_binding(
        registration,
        _prediction_context(projected, request.causal_history),
    )
    validate_official_outcome_binding(registration, _official_outcome(projected))

    assert _canonical_keys(registration.canonical_dict()).isdisjoint(
        _FORBIDDEN_PRIZE_OR_OUTCOME_KEYS
    )
    record_paths = tuple(authority_root.rglob("registration.json"))
    assert len(record_paths) == 1
    assert all(tmp_path in path.parents for path in record_paths)


def test_presence_port_is_structurally_presence_only_and_present_fails_closed(
    tmp_path: Path,
) -> None:
    assert {field.name for field in fields(PreOutcomeTargetRegistrationRequest)} == {
        "announcement",
        "causal_history",
    }
    assert {field.name for field in fields(OutcomePresenceAttestation)} == {
        "target",
        "presence",
        "attested_at",
        "source",
    }
    parameters = inspect.signature(OutcomePresenceProbe.probe).parameters
    assert tuple(parameters) == ("self", "target", "as_of")
    assert parameters["as_of"].kind is inspect.Parameter.KEYWORD_ONLY
    assert set(parameters).isdisjoint(_FORBIDDEN_PRIZE_OR_OUTCOME_KEYS)

    authority_root = tmp_path / "present-rejection"
    store = FileSystemPreOutcomeTargetAuthorityStore(authority_root)
    probe = _RecordingPresenceProbe(OutcomePresenceAtPrediction.PRESENT)
    request = _request(LotteryType.BIG_LOTTO)

    with pytest.raises(OutcomeAlreadyAvailableError, match="already available"):
        _service(store, probe).register(request)

    assert probe.calls == [(request.announcement.target, _REGISTERED_AT)]
    assert store.get_registration(request.announcement.target) is None
    assert tuple(authority_root.rglob("registration.json")) == ()


def test_durable_service_create_replay_conflict_and_restart_are_create_once(
    tmp_path: Path,
) -> None:
    authority_root = tmp_path / "durable-authority"
    request = _request(LotteryType.BIG_LOTTO)
    first_probe = _RecordingPresenceProbe(OutcomePresenceAtPrediction.ABSENT)
    first_store = FileSystemPreOutcomeTargetAuthorityStore(authority_root)

    created = _service(first_store, first_probe).register(request)
    record_path = next(authority_root.rglob("registration.json"))
    first_bytes = record_path.read_bytes()

    restarted_store = FileSystemPreOutcomeTargetAuthorityStore(authority_root)
    replay_probe = _RecordingPresenceProbe(OutcomePresenceAtPrediction.PRESENT)
    replayed = _service(
        restarted_store,
        replay_probe,
        now=datetime(2099, 1, 1, 9, tzinfo=UTC),
    ).register(request)

    assert created.status is RegistrationSyncStatus.CREATED
    assert replayed.status is RegistrationSyncStatus.EXACT_IDEMPOTENT_NO_OP
    assert replayed.registration == created.registration
    assert replayed.registration.registered_at == _REGISTERED_AT
    assert replay_probe.calls == []
    assert record_path.read_bytes() == first_bytes

    conflict_probe = _RecordingPresenceProbe(OutcomePresenceAtPrediction.ABSENT)
    with pytest.raises(TargetConflictError, match="different immutable authority"):
        _service(restarted_store, conflict_probe).register(
            _request(
                LotteryType.BIG_LOTTO,
                source_variant="competing-authority",
            )
        )

    assert conflict_probe.calls == []
    assert record_path.read_bytes() == first_bytes
    assert restarted_store.get_registration(request.announcement.target) == created.registration
    assert len(tuple(authority_root.rglob("registration.json"))) == 1

    with pytest.raises(PredictionContextBindingMismatchError, match="causal history"):
        validate_prediction_context_binding(
            created.registration,
            _prediction_context(
                created.registration.target,
                _history(digest_variant="silently-substituted-history"),
            ),
        )


def test_same_draw_identity_is_isolated_by_lottery_and_cross_bindings_fail_closed(
    tmp_path: Path,
) -> None:
    authority_root = tmp_path / "cross-lottery-authority"
    store = FileSystemPreOutcomeTargetAuthorityStore(authority_root)
    registrations: dict[LotteryType, PreOutcomeTargetRegistration] = {}

    for lottery_type in _LOTTERIES:
        request = _request(lottery_type)
        result = _service(
            store,
            _RecordingPresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        ).register(request)
        registrations[lottery_type] = result.registration

    assert len(tuple(authority_root.rglob("registration.json"))) == 3
    assert all(
        (authority_root / lottery_type.value.lower()).is_dir() for lottery_type in _LOTTERIES
    )
    assert len({registration.registration_digest for registration in registrations.values()}) == 3
    assert (
        len({registration.outcome_binding_identity for registration in registrations.values()}) == 3
    )
    assert all(
        store.get_registration(_target(lottery_type)) == registrations[lottery_type]
        for lottery_type in _LOTTERIES
    )

    big_lotto_registration = registrations[LotteryType.BIG_LOTTO]
    daily_target = _target(LotteryType.DAILY_539)
    with pytest.raises(PredictionContextBindingMismatchError, match="target"):
        validate_prediction_context_binding(
            big_lotto_registration,
            _prediction_context(daily_target, _history()),
        )
    with pytest.raises(TargetBindingMismatchError, match="target"):
        validate_official_outcome_binding(
            big_lotto_registration,
            _official_outcome(daily_target),
        )

    assert all(
        _canonical_keys(registration.canonical_dict()).isdisjoint(_FORBIDDEN_PRIZE_OR_OUTCOME_KEYS)
        for registration in registrations.values()
    )
