"""Focused contracts for immutable pre-outcome target authority records."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta, timezone
from typing import cast

import pytest

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

_TARGET = ObservationTarget(LotteryType.BIG_LOTTO, "115000080", date(2026, 8, 14))
_SCHEDULED_AT = datetime(2026, 8, 14, 12, 30, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 8, 14, 9, 2, tzinfo=UTC)


def _source(
    *,
    source_id: str,
    observed_at: datetime,
    digest: str,
    source_version: str = "v1",
) -> TargetSourceProvenance:
    return TargetSourceProvenance(
        source_id=source_id,
        source_version=source_version,
        source_locator=f"fixture://{source_id}",
        source_sha256=digest,
        observed_at=observed_at,
    )


def _announcement(
    *,
    target: ObservationTarget = _TARGET,
    scheduled_at: datetime = _SCHEDULED_AT,
    source: TargetSourceProvenance | None = None,
) -> TargetAnnouncement:
    return TargetAnnouncement(
        target=target,
        schedule_timezone="Asia/Taipei",
        scheduled_at=scheduled_at,
        source=source
        or _source(
            source_id="schedule-fixture",
            observed_at=datetime(2026, 8, 14, 8, tzinfo=UTC),
            digest="1" * 64,
        ),
    )


def _attestation(
    *,
    target: ObservationTarget = _TARGET,
    presence: OutcomePresenceAtPrediction = OutcomePresenceAtPrediction.ABSENT,
    attested_at: datetime = datetime(2026, 8, 14, 9, 1, tzinfo=UTC),
    source: TargetSourceProvenance | None = None,
) -> OutcomePresenceAttestation:
    return OutcomePresenceAttestation(
        target=target,
        presence=presence,
        attested_at=attested_at,
        source=source
        or _source(
            source_id="presence-fixture",
            observed_at=datetime(2026, 8, 14, 9, tzinfo=UTC),
            digest="2" * 64,
        ),
    )


def _history(*, digest: str = "3" * 64) -> CausalHistoryRef:
    return CausalHistoryRef(
        draw_count=10,
        last_draw_number="115000079",
        last_draw_date=date(2026, 8, 11),
        history_sha256=digest,
    )


def _registration(
    *,
    announcement: TargetAnnouncement | None = None,
    absence_attestation: OutcomePresenceAttestation | None = None,
    causal_history: CausalHistoryRef | None = None,
    registered_at: datetime = _REGISTERED_AT,
) -> PreOutcomeTargetRegistration:
    return PreOutcomeTargetRegistration.create(
        announcement=announcement or _announcement(),
        absence_attestation=absence_attestation or _attestation(),
        causal_history=causal_history or _history(),
        registered_at=registered_at,
    )


def _fingerprint() -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id="fixture-producer",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator="fixture://producer",
                source_sha256="4" * 64,
                load_bearing_role="prediction behavior",
            ),
        ),
    )


def _context(
    *,
    target: ObservationTarget = _TARGET,
    causal_history: CausalHistoryRef | None = None,
) -> PredictionContext:
    return PredictionContext(
        target=target,
        cohort=FrozenCohortRef(
            lottery_type=target.lottery_type,
            cohort_id="fixture-cohort",
            cohort_version="v1",
            authority_sha256="5" * 64,
            frozen_at=datetime(2026, 8, 13, tzinfo=UTC),
            member_ids=("fixture-member",),
            checkpoint_sizes=(1,),
            checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
        ),
        producer_fingerprint=_fingerprint(),
        causal_history=causal_history or _history(),
    )


def _outcome(
    *,
    target: ObservationTarget = _TARGET,
    numbers: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
) -> OfficialOutcome:
    return OfficialOutcome.create(
        lottery_type=target.lottery_type,
        draw_number=target.draw_number,
        draw_date=target.draw_date,
        main_numbers=numbers,
        special_number=7 if target.lottery_type is LotteryType.BIG_LOTTO else None,
        source_id="official-outcome-fixture",
        source_sha256="6" * 64,
    )


def test_registration_is_immutable_canonical_and_self_verifying() -> None:
    registration = _registration()

    assert registration.schema_version == PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION
    assert registration.target == _TARGET
    assert registration.to_observation_target() is registration.target
    assert registration.announcement.target_timezone == "Asia/Taipei"
    assert registration.announcement.source.source_payload_sha256 == "1" * 64
    assert registration.absence_attestation.as_of == datetime(2026, 8, 14, 9, 1, tzinfo=UTC)
    assert len(registration.prediction_input_identity) == 64
    assert len(registration.outcome_binding_identity) == 64
    assert len(registration.registration_digest) == 64
    assert tuple(json.loads(registration.canonical_json())) == tuple(
        sorted(registration.canonical_dict())
    )
    assert (
        PreOutcomeTargetRegistration.from_canonical_dict(registration.canonical_dict())
        == registration
    )

    with pytest.raises(FrozenInstanceError):
        registration.registered_at = _SCHEDULED_AT  # type: ignore[misc]
    with pytest.raises(ValueError, match="registration_digest"):
        replace(registration, registration_digest="0" * 64)


def test_canonical_decoder_rejects_unknown_fields_and_tampered_nested_content() -> None:
    registration = _registration()
    unknown = registration.canonical_dict()
    unknown["unknown"] = True
    with pytest.raises(ValueError, match="fields differ"):
        PreOutcomeTargetRegistration.from_canonical_dict(unknown)

    tampered = deepcopy(registration.canonical_dict())
    announcement = cast(dict[str, object], tampered["announcement"])
    source = cast(dict[str, object], announcement["source"])
    source["source_version"] = "counterfactual-v2"
    with pytest.raises(ValueError, match="prediction_input_identity"):
        PreOutcomeTargetRegistration.from_canonical_dict(tampered)

    noncanonical_time = registration.canonical_dict()
    noncanonical_time["registered_at"] = "2026-08-14T17:02:00+08:00"
    with pytest.raises(ValueError, match="canonical UTC"):
        PreOutcomeTargetRegistration.from_canonical_dict(noncanonical_time)


@pytest.mark.parametrize("presence", tuple(OutcomePresenceAtPrediction))
def test_presence_attestation_accepts_both_presence_states(
    presence: OutcomePresenceAtPrediction,
) -> None:
    attestation = _attestation(presence=presence)

    assert attestation.presence is presence
    assert {field.name for field in fields(OutcomePresenceAttestation)} == {
        "attested_at",
        "presence",
        "source",
        "target",
    }
    assert not any(
        name in {"main_numbers", "special_number", "outcome_hash"}
        for name in attestation.canonical_dict()
    )


def test_registration_fails_closed_when_presence_attestation_is_present() -> None:
    with pytest.raises(ValueError, match="requires an ABSENT"):
        _registration(
            absence_attestation=_attestation(presence=OutcomePresenceAtPrediction.PRESENT)
        )


def test_announcement_requires_utc_and_matching_iana_local_date() -> None:
    with pytest.raises(ValueError, match="IANA timezone"):
        replace(_announcement(), schedule_timezone="Not/A_Timezone")
    with pytest.raises(ValueError, match="local date"):
        replace(
            _announcement(),
            scheduled_at=datetime(2026, 8, 13, 12, 30, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="must use UTC"):
        replace(
            _announcement(),
            scheduled_at=datetime(
                2026,
                8,
                14,
                20,
                30,
                tzinfo=timezone(timedelta(hours=8)),
            ),
        )
    with pytest.raises(ValueError, match="must use UTC"):
        replace(
            _announcement(),
            scheduled_at=datetime(
                2026,
                8,
                14,
                12,
                30,
                tzinfo=timezone(timedelta(0), name="ZERO_BUT_NOT_UTC"),
            ),
        )
    with pytest.raises(ValueError, match="observed before"):
        _announcement(
            source=_source(
                source_id="late-schedule",
                observed_at=_SCHEDULED_AT,
                digest="7" * 64,
            )
        )


def test_provenance_and_presence_attestation_require_utc_causal_timestamps() -> None:
    with pytest.raises(ValueError, match="source_sha256"):
        _source(
            source_id="bad-digest",
            observed_at=datetime(2026, 8, 14, 8, tzinfo=UTC),
            digest="not-a-digest",
        )
    with pytest.raises(ValueError, match="must use UTC"):
        _source(
            source_id="offset-time",
            observed_at=datetime(
                2026,
                8,
                14,
                16,
                tzinfo=timezone(timedelta(hours=8)),
            ),
            digest="8" * 64,
        )
    with pytest.raises(ValueError, match="must use UTC"):
        _source(
            source_id="named-zero-offset-time",
            observed_at=datetime(
                2026,
                8,
                14,
                8,
                tzinfo=timezone(timedelta(0), name="ZERO_BUT_NOT_UTC"),
            ),
            digest="8" * 64,
        )
    with pytest.raises(ValueError, match="after attested_at"):
        _attestation(
            source=_source(
                source_id="future-probe",
                observed_at=datetime(2026, 8, 14, 9, 1, 1, tzinfo=UTC),
                digest="9" * 64,
            )
        )


def test_registration_enforces_source_and_absence_before_registration_before_schedule() -> None:
    with pytest.raises(ValueError, match="target source"):
        _registration(
            announcement=_announcement(
                source=_source(
                    source_id="late-announcement",
                    observed_at=_REGISTERED_AT + timedelta(seconds=1),
                    digest="a" * 64,
                )
            )
        )
    with pytest.raises(ValueError, match="presence source"):
        _registration(
            absence_attestation=_attestation(
                attested_at=_REGISTERED_AT + timedelta(seconds=2),
                source=_source(
                    source_id="late-presence-source",
                    observed_at=_REGISTERED_AT + timedelta(seconds=1),
                    digest="b" * 64,
                ),
            )
        )
    with pytest.raises(ValueError, match="attested"):
        _registration(
            absence_attestation=_attestation(attested_at=_REGISTERED_AT + timedelta(seconds=1))
        )
    with pytest.raises(ValueError, match="strictly before"):
        _registration(registered_at=_SCHEDULED_AT)
    with pytest.raises(ValueError, match="must use UTC"):
        _registration(
            registered_at=datetime(
                2026,
                8,
                14,
                17,
                2,
                tzinfo=timezone(timedelta(hours=8)),
            )
        )


def test_registration_requires_attestation_and_history_for_exact_target() -> None:
    other_target = replace(_TARGET, draw_number="115000081")
    with pytest.raises(ValueError, match="must match announced"):
        _registration(absence_attestation=_attestation(target=other_target))

    noncausal = CausalHistoryRef(
        draw_count=1,
        last_draw_number=_TARGET.draw_number,
        last_draw_date=_TARGET.draw_date,
        history_sha256="c" * 64,
    )
    with pytest.raises(ValueError, match="strictly before"):
        _registration(causal_history=noncausal)


def test_prediction_and_outcome_identities_have_distinct_deterministic_scope() -> None:
    original = _registration()
    later_recording = _registration(registered_at=_REGISTERED_AT + timedelta(minutes=1))
    changed_history = _registration(causal_history=_history(digest="d" * 64))
    changed_source = _registration(
        announcement=_announcement(
            source=_source(
                source_id="schedule-fixture",
                source_version="v2",
                observed_at=datetime(2026, 8, 14, 8, tzinfo=UTC),
                digest="1" * 64,
            )
        )
    )

    assert original.prediction_input_identity != later_recording.prediction_input_identity
    assert original.registration_digest != later_recording.registration_digest
    assert original.prediction_input_identity != changed_history.prediction_input_identity
    assert original.prediction_input_identity != changed_source.prediction_input_identity
    assert {
        original.outcome_binding_identity,
        later_recording.outcome_binding_identity,
        changed_history.outcome_binding_identity,
        changed_source.outcome_binding_identity,
    } == {original.outcome_binding_identity}

    assert original.matches_request(original.announcement, original.causal_history)
    assert not original.matches_request(changed_source.announcement, original.causal_history)
    assert not original.matches_request(original.announcement, changed_history.causal_history)


def test_prediction_context_binding_is_pure_and_uses_distinct_error() -> None:
    registration = _registration()
    context = _context()

    assert validate_prediction_context_binding(registration, context) is None
    assert context.target == _TARGET

    with pytest.raises(PredictionContextBindingMismatchError, match="target") as target_error:
        validate_prediction_context_binding(
            registration,
            _context(target=replace(_TARGET, draw_number="115000081")),
        )
    assert not isinstance(target_error.value, TargetBindingMismatchError)

    with pytest.raises(PredictionContextBindingMismatchError, match="causal history"):
        validate_prediction_context_binding(
            registration,
            _context(causal_history=_history(digest="e" * 64)),
        )


def test_official_outcome_binding_uses_only_registered_target_identity() -> None:
    registration = _registration()

    assert validate_official_outcome_binding(registration, _outcome()) is None
    assert (
        validate_official_outcome_binding(
            registration,
            _outcome(numbers=(8, 9, 10, 11, 12, 13)),
        )
        is None
    )
    with pytest.raises(TargetBindingMismatchError, match="official outcome target") as error:
        validate_official_outcome_binding(
            registration,
            _outcome(target=replace(_TARGET, draw_number="115000081")),
        )
    assert not isinstance(error.value, PredictionContextBindingMismatchError)
