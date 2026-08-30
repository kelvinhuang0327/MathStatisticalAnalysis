"""Focused contracts for Stage A-bound runnable prediction seals."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationResult,
    OperationalRegistrationStatus,
)
from lottolab.application.prospective_observer import (
    GameContractError,
    InMemoryProspectiveObservationStore,
    PredictionConflictError,
    ProducerFingerprintDriftError,
    repository_game_contracts,
)
from lottolab.application.prospective_prediction_seal import (
    SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE,
    PredictionSealCausalityError,
    RunnablePredictionSealResult,
    RunnablePredictionSealService,
    RunnablePredictionSealStatus,
    ScheduleAuthorityDigestUnavailableError,
    bind_stage_a_schedule_authority,
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
    FrozenCohortRef,
    MatchedBaselineRef,
    ObservationTarget,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
    TemporalProvenance,
)
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
)

_NOW = datetime(2099, 1, 1, 8, tzinfo=UTC)
_TARGET_DATE = date(2099, 1, 2)
_SCHEDULED_AT = datetime(2099, 1, 2, 12, 30, tzinfo=UTC)
_SCHEDULE_DIGEST = "a" * 64


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _announcement(lottery_type: LotteryType) -> TargetAnnouncement:
    return TargetAnnouncement(
        target=ObservationTarget(lottery_type, "999999901", _TARGET_DATE),
        schedule_timezone="Asia/Taipei",
        scheduled_at=_SCHEDULED_AT,
        source=TargetSourceProvenance(
            source_id="synthetic-stage-a",
            source_version="v1",
            source_locator=f"fixture://stage-a/{lottery_type.value}",
            source_sha256=_sha256(f"schedule:{lottery_type.value}"),
            observed_at=datetime(2099, 1, 1, 6, tzinfo=UTC),
        ),
    )


def _history(lottery_type: LotteryType) -> CausalHistoryRef:
    return CausalHistoryRef(
        draw_count=1,
        last_draw_number="999999900",
        last_draw_date=date(2099, 1, 1),
        history_sha256=_sha256(f"history:{lottery_type.value}"),
    )


def _registration(lottery_type: LotteryType) -> PreOutcomeTargetRegistration:
    announcement = _announcement(lottery_type)
    presence_source = TargetSourceProvenance(
        source_id="synthetic-presence-audit",
        source_version="v1",
        source_locator=f"fixture://presence/{lottery_type.value}",
        source_sha256=_sha256(f"presence:{lottery_type.value}"),
        observed_at=_NOW,
    )
    return PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            target=announcement.target,
            presence=OutcomePresenceAtPrediction.ABSENT,
            attested_at=_NOW,
            source=presence_source,
        ),
        causal_history=_history(lottery_type),
        registered_at=_NOW,
    )


def _authority(
    lottery_type: LotteryType,
    *,
    digest: str | None = _SCHEDULE_DIGEST,
) -> OperationalRegistrationResult:
    registration = _registration(lottery_type)
    return OperationalRegistrationResult(
        status=OperationalRegistrationStatus.CREATED,
        announcement=registration.announcement,
        causal_history=registration.causal_history,
        registration=registration,
        immutable_schedule_sha256=digest,
    )


def _no_target_authority() -> OperationalRegistrationResult:
    return OperationalRegistrationResult(
        status=OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT,
        announcement=None,
        causal_history=None,
        registration=None,
        immutable_schedule_sha256=None,
    )


class _RegistrationService:
    def __init__(self, result: OperationalRegistrationResult) -> None:
        self.result = result
        self.calls: list[LotteryType] = []

    def register_earliest(
        self,
        lottery_type: LotteryType,
    ) -> OperationalRegistrationResult:
        self.calls.append(lottery_type)
        return self.result


class _Producer:
    def __init__(self, draft: PredictionDraft) -> None:
        self.draft = draft
        self.calls: list[PredictionContext] = []

    def predict(self, context: PredictionContext) -> PredictionDraft:
        self.calls.append(context)
        return self.draft


class _ProducerFactory:
    def __init__(self, draft: PredictionDraft) -> None:
        self.draft = draft
        self.calls: list[tuple[TargetAnnouncement, datetime]] = []
        self.producers: list[_Producer] = []

    def __call__(
        self,
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> _Producer:
        self.calls.append((announcement, reference_time))
        producer = _Producer(self.draft)
        self.producers.append(producer)
        return producer


def _cohort(lottery_type: LotteryType) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"synthetic-stage-c-{lottery_type.value.lower()}",
        cohort_version="v1",
        authority_sha256=_sha256(f"cohort:{lottery_type.value}"),
        frozen_at=datetime(2098, 12, 31, tzinfo=UTC),
        member_ids=("synthetic-member",),
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _fingerprint(lottery_type: LotteryType) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id=f"synthetic-stage-c-{lottery_type.value.lower()}",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator=f"fixture://producer/{lottery_type.value}",
                source_sha256=_sha256(f"producer:{lottery_type.value}"),
                load_bearing_role="synthetic deterministic producer behavior",
            ),
        ),
    )


def _valid_selection(lottery_type: LotteryType) -> ProspectiveSelection:
    if lottery_type is LotteryType.DAILY_539:
        return ProspectiveSelection((1, 2, 3, 4, 5))
    return ProspectiveSelection((1, 2, 3, 4, 5, 6), 2)


def _invalid_selection(lottery_type: LotteryType) -> ProspectiveSelection:
    if lottery_type is LotteryType.DAILY_539:
        return ProspectiveSelection((1, 2, 3, 4, 5, 6))
    return ProspectiveSelection((1, 2, 3, 4, 5, 6), 9)


def _draft(
    lottery_type: LotteryType,
    *,
    selection: ProspectiveSelection | None = None,
) -> PredictionDraft:
    selected = _valid_selection(lottery_type) if selection is None else selection
    return PredictionDraft(
        (
            PredictionEntryDraft.available(
                member_id="synthetic-member",
                selections=(selected,),
                matched_baseline=MatchedBaselineRef(
                    lottery_type=lottery_type,
                    baseline_id="synthetic-shape-matched-baseline",
                    baseline_version="v1",
                    authority_sha256=_sha256(f"baseline:{lottery_type.value}"),
                    ticket_count=1,
                    candidate_sizes=(len(selected.main_numbers),),
                ),
            ),
        )
    )


def _service(
    lottery_type: LotteryType,
    *,
    authority: OperationalRegistrationResult | None = None,
    draft: PredictionDraft | None = None,
    store: (
        InMemoryProspectiveObservationStore
        | FileSystemProspectiveObservationStore
        | None
    ) = None,
    now: datetime = _NOW,
) -> tuple[RunnablePredictionSealService, _RegistrationService, _ProducerFactory]:
    registration = _RegistrationService(authority or _authority(lottery_type))
    factory = _ProducerFactory(draft or _draft(lottery_type))
    service = RunnablePredictionSealService(
        lottery_type=lottery_type,
        registration_service=registration,
        store=store or InMemoryProspectiveObservationStore(),
        producer_factory=factory,
        cohort=_cohort(lottery_type),
        base_producer_fingerprint=_fingerprint(lottery_type),
        game_contracts=repository_game_contracts(),
        clock=lambda: now,
    )
    return service, registration, factory


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_complete_runnable_target_binds_digest_and_seals_valid_game_ticket(
    lottery_type: LotteryType,
) -> None:
    store = InMemoryProspectiveObservationStore()
    service, registration, factory = _service(lottery_type, store=store)

    result = service.seal_earliest()

    assert result.status is RunnablePredictionSealStatus.CREATED
    assert result.immutable_schedule_sha256 == _SCHEDULE_DIGEST
    assert registration.calls == [lottery_type]
    assert factory.calls == [(_announcement(lottery_type), _NOW)]
    assert len(store.predictions) == 1
    prediction = store.predictions[0]
    schedule_dependencies = tuple(
        dependency
        for dependency in prediction.producer_fingerprint.dependencies
        if dependency.load_bearing_role == SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE
    )
    assert len(schedule_dependencies) == 1
    assert schedule_dependencies[0].source_sha256 == _SCHEDULE_DIGEST
    assert schedule_dependencies[0].locator.endswith(
        f"/{lottery_type.value}/999999901"
    )
    assert prediction.entries[0].selections == (_valid_selection(lottery_type),)


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_no_runnable_target_returns_without_constructing_or_calling_producer(
    lottery_type: LotteryType,
) -> None:
    store = InMemoryProspectiveObservationStore()
    service, registration, factory = _service(
        lottery_type,
        authority=_no_target_authority(),
        store=store,
    )

    result = service.seal_earliest()

    assert result.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert registration.calls == [lottery_type]
    assert factory.calls == []
    assert store.predictions == ()


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_missing_complete_stage_a_digest_fails_before_producer(
    lottery_type: LotteryType,
) -> None:
    service, _, factory = _service(
        lottery_type,
        authority=_authority(lottery_type, digest=None),
    )

    with pytest.raises(
        ScheduleAuthorityDigestUnavailableError,
        match="complete immutable Stage A",
    ):
        service.seal_earliest()

    assert factory.calls == []


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_late_target_fails_before_producer(
    lottery_type: LotteryType,
) -> None:
    service, _, factory = _service(lottery_type, now=_SCHEDULED_AT)

    with pytest.raises(PredictionSealCausalityError, match="strictly before"):
        service.seal_earliest()

    assert factory.calls == []


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_invalid_game_ticket_is_rejected_before_durable_seal(
    lottery_type: LotteryType,
    tmp_path: Path,
) -> None:
    root = tmp_path / "prediction-store"
    store = FileSystemProspectiveObservationStore(root)
    service, _, factory = _service(
        lottery_type,
        draft=_draft(lottery_type, selection=_invalid_selection(lottery_type)),
        store=store,
    )

    with pytest.raises(GameContractError):
        service.seal_earliest()

    assert len(factory.producers) == 1
    assert len(factory.producers[0].calls) == 1
    assert tuple(root.rglob("*.json")) == ()


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_restart_is_exact_no_op_and_conflicting_second_payload_is_rejected(
    lottery_type: LotteryType,
    tmp_path: Path,
) -> None:
    root = tmp_path / "prediction-store"
    first_store = FileSystemProspectiveObservationStore(root)
    first_service, _, _ = _service(lottery_type, store=first_store)
    created = first_service.seal_earliest()
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")}

    restarted_store = FileSystemProspectiveObservationStore(root)
    restarted_service, _, _ = _service(lottery_type, store=restarted_store)
    replayed = restarted_service.seal_earliest()

    assert created.status is RunnablePredictionSealStatus.CREATED
    assert replayed.status is RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP
    assert replayed.prediction == created.prediction
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")} == before

    conflicting_numbers = (
        ProspectiveSelection((6, 7, 8, 9, 10))
        if lottery_type is LotteryType.DAILY_539
        else ProspectiveSelection((7, 8, 9, 10, 11, 12), 3)
    )
    conflicting_service, _, _ = _service(
        lottery_type,
        draft=_draft(lottery_type, selection=conflicting_numbers),
        store=FileSystemProspectiveObservationStore(root),
    )
    with pytest.raises(PredictionConflictError, match="different immutable content"):
        conflicting_service.seal_earliest()
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")} == before


def test_changed_stage_a_digest_cannot_reuse_existing_prediction_identity() -> None:
    store = InMemoryProspectiveObservationStore()
    first, _, _ = _service(LotteryType.DAILY_539, store=store)
    assert first.seal_earliest().status is RunnablePredictionSealStatus.CREATED
    changed, _, changed_factory = _service(
        LotteryType.DAILY_539,
        authority=_authority(LotteryType.DAILY_539, digest="b" * 64),
        store=store,
    )

    with pytest.raises(ProducerFingerprintDriftError, match="differs"):
        changed.seal_earliest()

    assert len(changed_factory.producers) == 1
    assert changed_factory.producers[0].calls == []
    assert len(store.predictions) == 1


def test_schedule_authority_binding_is_deterministic_and_counterfactual_sensitive() -> None:
    announcement = _announcement(LotteryType.DAILY_539)
    base = _fingerprint(LotteryType.DAILY_539)

    first = bind_stage_a_schedule_authority(
        base,
        announcement=announcement,
        immutable_schedule_sha256="a" * 64,
    )
    repeated = bind_stage_a_schedule_authority(
        base,
        announcement=announcement,
        immutable_schedule_sha256="a" * 64,
    )
    changed = bind_stage_a_schedule_authority(
        base,
        announcement=announcement,
        immutable_schedule_sha256="b" * 64,
    )

    assert first == repeated
    assert first.digest != changed.digest
    with pytest.raises(ValueError, match="schedule-independent"):
        bind_stage_a_schedule_authority(
            first,
            announcement=announcement,
            immutable_schedule_sha256="a" * 64,
        )


@pytest.mark.parametrize(
    ("invalid_lottery", "valid_lottery"),
    (
        (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
        (LotteryType.POWER_LOTTO, LotteryType.DAILY_539),
    ),
)
def test_game_failure_is_isolated_from_other_valid_game(
    invalid_lottery: LotteryType,
    valid_lottery: LotteryType,
    tmp_path: Path,
) -> None:
    store = FileSystemProspectiveObservationStore(tmp_path / "shared-store")
    invalid, _, _ = _service(
        invalid_lottery,
        draft=_draft(invalid_lottery, selection=_invalid_selection(invalid_lottery)),
        store=store,
    )
    valid, _, _ = _service(valid_lottery, store=store)

    with pytest.raises(GameContractError):
        invalid.seal_earliest()
    result = valid.seal_earliest()

    assert result.status is RunnablePredictionSealStatus.CREATED
    assert result.prediction is not None
    assert result.prediction.identity.lottery_type is valid_lottery
    prediction_files = tuple((tmp_path / "shared-store").rglob("prediction.json"))
    assert len(prediction_files) == 1


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_concurrent_seal_uses_existing_atomic_create_once_contract(
    lottery_type: LotteryType,
    tmp_path: Path,
) -> None:
    store = FileSystemProspectiveObservationStore(tmp_path / "concurrent-store")
    service, _, _ = _service(lottery_type, store=store)

    def seal_once(_index: int) -> RunnablePredictionSealResult:
        return service.seal_earliest()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(seal_once, range(8)))

    statuses = [result.status for result in results]
    assert statuses.count(RunnablePredictionSealStatus.CREATED) == 1
    assert statuses.count(RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP) == 7
    assert len(tuple((tmp_path / "concurrent-store").rglob("prediction.json"))) == 1
