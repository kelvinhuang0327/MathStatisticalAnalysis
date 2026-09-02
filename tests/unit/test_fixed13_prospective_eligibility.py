"""Fixed-13 prospective eligibility and create-once persistence acceptance tests."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.fixed13_pre_outcome_timing_receipt import (
    PreOutcomeTimingReceiptReasonCode,
    PreOutcomeTimingReceiptVerdict,
)
from lottolab.application.fixed13_prospective_eligibility import (
    PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256,
    PINNED_FREEZE_ARTIFACT_FILE_SHA256,
    Fixed13EligibilityStatus,
    Fixed13ProspectiveEligibilityRecord,
    PreOutcomeTimingProofRef,
    build_fixed13_prospective_eligibility,
)
from lottolab.application.fixed13_prospective_producer import (
    FIXED_13_COHORT_STRATEGY_IDS,
    RNG_DOMAIN_TAG,
    RNG_POLICY_ID,
    RNG_REQUIRED_STRATEGY_IDS,
    RNG_SEED_DERIVATION_FORMULA,
    AdapterConstruction,
    Fixed13ProspectiveProducerRecord,
    ProducerImplementationIdentity,
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
    FrozenCohortRef,
    MatchedBaselineRef,
    ObservationTarget,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
    TemporalProvenance,
)
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
    ProspectiveObservationStoreCorruptionError,
)
from lottolab.strategies.adapters.base import BetAdapterExecution

_TARGET_DRAW_NUMBER = "115000083"
_TARGET_DATE = date(2026, 9, 3)
_FROZEN_AT = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)
_PREDICTED_AT = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
_ELIGIBILITY_SEALED_AT = datetime(2026, 9, 3, 11, 0, tzinfo=UTC)
_SCHEDULED_AT = datetime(2026, 9, 3, 12, 30, tzinfo=UTC)
_CAUSAL_HISTORY = CausalHistoryRef(
    draw_count=2,
    last_draw_number="115000082",
    last_draw_date=date(2026, 9, 1),
    history_sha256="4" * 64,
)
_DEFAULT_TICKETS: tuple[tuple[int, ...], ...] = tuple(
    tuple(range(index + 1, index + 7)) for index in range(13)
)
_PRODUCER_HEAD = "50039797664efeabc6ddb3954322fb7a1d7632a6"
_PRODUCER_TREE = "e22829407ae76204460e49e5dd3c73c123b27032"


def _fingerprint() -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id="fixed13-test-producer",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                "src/lottolab/application/fixed13_prospective_producer.py",
                "5" * 64,
                "fixed-13 production behavior",
            ),
        ),
    )


def _available_entry(strategy_id: str, ticket: tuple[int, ...]) -> PredictionEntryDraft:
    selection = ProspectiveSelection(ticket)
    return PredictionEntryDraft.available(
        member_id=strategy_id,
        selections=(selection,),
        matched_baseline=MatchedBaselineRef(
            lottery_type=LotteryType.BIG_LOTTO,
            baseline_id="fixed13-size-matched-random",
            baseline_version="v1",
            authority_sha256="6" * 64,
            ticket_count=1,
            candidate_sizes=(len(ticket),),
        ),
    )


def _prediction(
    *,
    member_ids: tuple[str, ...] = FIXED_13_COHORT_STRATEGY_IDS,
    tickets: Sequence[tuple[int, ...]] = _DEFAULT_TICKETS,
    entries: tuple[PredictionEntryDraft, ...] | None = None,
    frozen_at: datetime = _FROZEN_AT,
    outcome_presence: OutcomePresenceAtPrediction = OutcomePresenceAtPrediction.ABSENT,
    predicted_at: datetime = _PREDICTED_AT,
    draw_number: str = _TARGET_DRAW_NUMBER,
    draw_date: date = _TARGET_DATE,
) -> PredictionRecord:
    cohort = FrozenCohortRef(
        lottery_type=LotteryType.BIG_LOTTO,
        cohort_id="next-draw-r2-fixed-13",
        cohort_version="v1",
        authority_sha256=PINNED_FREEZE_ARTIFACT_FILE_SHA256,
        frozen_at=frozen_at,
        member_ids=member_ids,
        checkpoint_sizes=(20, 40, 60, 100),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )
    draft_entries = entries or tuple(
        _available_entry(strategy_id, ticket)
        for strategy_id, ticket in zip(member_ids, tickets, strict=True)
    )
    context = PredictionContext(
        target=ObservationTarget(LotteryType.BIG_LOTTO, draw_number, draw_date),
        cohort=cohort,
        producer_fingerprint=_fingerprint(),
        causal_history=_CAUSAL_HISTORY,
    )
    return PredictionRecord.create(
        request=PredictionPhaseRequest(context, outcome_presence),
        draft=PredictionDraft(draft_entries),
        predicted_at=predicted_at,
    )


def _source(observed_at: datetime, suffix: str) -> TargetSourceProvenance:
    return TargetSourceProvenance(
        source_id=f"fixed13-test-{suffix}",
        source_version="v1",
        source_locator=f"fixture://fixed13/{suffix}",
        source_sha256=hashlib.sha256(suffix.encode("utf-8")).hexdigest(),
        observed_at=observed_at,
    )


def _registration(
    prediction: PredictionRecord,
    *,
    draw_number: str | None = None,
    draw_date: date | None = None,
    scheduled_at: datetime = _SCHEDULED_AT,
) -> PreOutcomeTargetRegistration:
    target = ObservationTarget(
        LotteryType.BIG_LOTTO,
        draw_number or prediction.identity.target_draw_number,
        draw_date or prediction.identity.target_draw_date,
    )
    announcement = TargetAnnouncement(
        target=target,
        schedule_timezone="Asia/Taipei",
        scheduled_at=scheduled_at,
        source=_source(_REGISTERED_AT - timedelta(hours=2), "schedule"),
    )
    absence = OutcomePresenceAttestation(
        target=target,
        presence=OutcomePresenceAtPrediction.ABSENT,
        attested_at=_REGISTERED_AT - timedelta(minutes=30),
        source=_source(_REGISTERED_AT - timedelta(hours=1), "absence"),
    )
    return PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=absence,
        causal_history=prediction.causal_history,
        registered_at=_REGISTERED_AT,
    )


def _producer_records(
    prediction: PredictionRecord,
) -> tuple[Fixed13ProspectiveProducerRecord, ...]:
    last_draw = prediction.causal_history.last_draw_number
    assert last_draw is not None
    records: list[Fixed13ProspectiveProducerRecord] = []
    for index, strategy_id in enumerate(FIXED_13_COHORT_STRATEGY_IDS):
        rng_required = strategy_id in RNG_REQUIRED_STRATEGY_IDS
        ticket = _DEFAULT_TICKETS[index]
        records.append(
            Fixed13ProspectiveProducerRecord(
                strategy_id=strategy_id,
                official_draw_identity=prediction.identity.target_draw_number,
                execution=BetAdapterExecution(ticket, ticket, None),
                rng_policy_id=RNG_POLICY_ID,
                rng_domain_tag=RNG_DOMAIN_TAG,
                rng_seed_derivation_formula=RNG_SEED_DERIVATION_FORMULA,
                per_member_rng_required=rng_required,
                per_member_rng_seed_sha256_hex=(
                    hashlib.sha256(strategy_id.encode("utf-8")).hexdigest()
                    if rng_required
                    else None
                ),
                per_member_adapter_path=f"fixture.adapters:{strategy_id}",
                per_member_adapter_construction=(
                    AdapterConstruction.RNG_INJECTED
                    if rng_required
                    else AdapterConstruction.ZERO_ARG_DEFAULT
                ),
                per_member_causal_history_digest=prediction.causal_history.history_sha256,
                causal_history_row_count=prediction.causal_history.draw_count,
                causal_history_last_draw_identity=last_draw,
                producer_implementation_identity=ProducerImplementationIdentity(
                    repository_head=_PRODUCER_HEAD,
                    repository_tree=_PRODUCER_TREE,
                    module_path="lottolab.application.fixed13_prospective_producer",
                ),
                python_implementation_identity="CPython 3.11.14",
                rng_selfcheck_vector=(0.125, 0.25, 0.5) if rng_required else None,
                historical_r2_ticket_parity_note=(
                    "NOT_ASSERTED_FOR_THE_THREE_MEMBERS"
                    if rng_required
                    else "NOT_APPLICABLE_ZERO_ARG_MEMBER"
                ),
            )
        )
    return tuple(records)


def _timing_ref() -> PreOutcomeTimingProofRef:
    return PreOutcomeTimingProofRef(
        proof_type="EXTERNAL_APPEND_ONLY_RECEIPT",
        reference="receipt://fixed13/115000083/eligibility",
        reference_sha256="7" * 64,
    )


def _verified_receipt_verdict() -> PreOutcomeTimingReceiptVerdict:
    return PreOutcomeTimingReceiptVerdict(
        verified=True,
        reason_code=PreOutcomeTimingReceiptReasonCode.OK,
        commitment_sha256=None,
        gen_time=None,
    )


def _unverified_receipt_verdict(
    reason_code: PreOutcomeTimingReceiptReasonCode = (
        PreOutcomeTimingReceiptReasonCode.SIGNATURE_OR_CHAIN_INVALID
    ),
) -> PreOutcomeTimingReceiptVerdict:
    return PreOutcomeTimingReceiptVerdict(
        verified=False,
        reason_code=reason_code,
        commitment_sha256=None,
        gen_time=None,
    )


def _build(
    *,
    prediction: PredictionRecord | None = None,
    registration: PreOutcomeTargetRegistration | None = None,
    producer_records: tuple[Fixed13ProspectiveProducerRecord, ...] | None = None,
    freeze_sha256: str = PINNED_FREEZE_ARTIFACT_FILE_SHA256,
    membership_sha256: str = PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256,
    sealed_at: datetime = _ELIGIBILITY_SEALED_AT,
    timing_ref: PreOutcomeTimingProofRef | None = None,
    receipt_verdict: PreOutcomeTimingReceiptVerdict | None = None,
) -> Fixed13ProspectiveEligibilityRecord:
    resolved_prediction = prediction or _prediction()
    return build_fixed13_prospective_eligibility(
        prediction=resolved_prediction,
        target_registration=registration or _registration(resolved_prediction),
        producer_records=producer_records or _producer_records(resolved_prediction),
        freeze_artifact_file_sha256=freeze_sha256,
        cohort_membership_strategy_ids_lcj1_sha256=membership_sha256,
        eligibility_sealed_at=sealed_at,
        pre_outcome_timing_proof_ref=timing_ref or _timing_ref(),
        pre_outcome_timing_receipt_verdict=receipt_verdict or _verified_receipt_verdict(),
    )


def _assert_ineligible(record: Fixed13ProspectiveEligibilityRecord) -> None:
    assert record.eligibility_status is Fixed13EligibilityStatus.PRE_OUTCOME_INELIGIBLE
    assert record.ineligibility_reasons


def test_exact_fixed_13_prediction_is_eligible_and_binds_all_authorities() -> None:
    prediction = _prediction()
    registration = _registration(prediction)
    records = _producer_records(prediction)

    eligibility = _build(
        prediction=prediction,
        registration=registration,
        producer_records=records,
    )

    assert eligibility.eligibility_status is Fixed13EligibilityStatus.ELIGIBLE
    assert eligibility.ineligibility_reasons == ()
    assert eligibility.official_draw_identity == _TARGET_DRAW_NUMBER
    assert eligibility.lottery_type is LotteryType.BIG_LOTTO
    assert eligibility.prediction_record_digest == prediction.prediction_hash
    assert eligibility.target_registration_digest == registration.registration_digest
    assert eligibility.canonical_member_order == FIXED_13_COHORT_STRATEGY_IDS
    assert eligibility.observed_member_order == FIXED_13_COHORT_STRATEGY_IDS
    assert len(eligibility.per_member_rng_provenance) == 13


@pytest.mark.parametrize(
    ("member_ids", "tickets", "expected_reason"),
    [
        (
            FIXED_13_COHORT_STRATEGY_IDS[:-1],
            _DEFAULT_TICKETS[:-1],
            "FIXED_MEMBER_COUNT_MISMATCH",
        ),
        (
            (*FIXED_13_COHORT_STRATEGY_IDS, "extra-fixed13-member"),
            (*_DEFAULT_TICKETS, (30, 31, 32, 33, 34, 35)),
            "FIXED_MEMBER_COUNT_MISMATCH",
        ),
        (
            (
                *FIXED_13_COHORT_STRATEGY_IDS[:6],
                "substituted-fixed13-member",
                *FIXED_13_COHORT_STRATEGY_IDS[7:],
            ),
            _DEFAULT_TICKETS,
            "FROZEN_COHORT_MEMBERSHIP_MISMATCH",
        ),
        (
            (
                FIXED_13_COHORT_STRATEGY_IDS[1],
                FIXED_13_COHORT_STRATEGY_IDS[0],
                *FIXED_13_COHORT_STRATEGY_IDS[2:],
            ),
            (
                _DEFAULT_TICKETS[1],
                _DEFAULT_TICKETS[0],
                *_DEFAULT_TICKETS[2:],
            ),
            "PREDICTION_MEMBER_ORDER_MISMATCH",
        ),
    ],
    ids=["twelve-members", "extra-member", "substituted-member", "order-mismatch"],
)
def test_fixed_member_completeness_violations_fail_closed(
    member_ids: tuple[str, ...],
    tickets: tuple[tuple[int, ...], ...],
    expected_reason: str,
) -> None:
    record = _build(prediction=_prediction(member_ids=member_ids, tickets=tickets))

    _assert_ineligible(record)
    assert expected_reason in record.ineligibility_reasons


def test_unavailable_member_fails_closed() -> None:
    entries = tuple(
        PredictionEntryDraft.unavailable(member_id=strategy_id, reason="fixture unavailable")
        if index == 4
        else _available_entry(strategy_id, _DEFAULT_TICKETS[index])
        for index, strategy_id in enumerate(FIXED_13_COHORT_STRATEGY_IDS)
    )

    record = _build(prediction=_prediction(entries=entries))

    _assert_ineligible(record)
    assert any(
        reason.startswith("PREDICTION_MEMBER_UNAVAILABLE:")
        for reason in record.ineligibility_reasons
    )


@pytest.mark.parametrize("selection_count", [0, 2])
def test_zero_or_two_selections_fail_closed(selection_count: int) -> None:
    prediction = _prediction()
    first_entry = prediction.entries[0]
    selections = (
        ()
        if selection_count == 0
        else (
            first_entry.selections[0],
            ProspectiveSelection((20, 21, 22, 23, 24, 25)),
        )
    )
    object.__setattr__(first_entry, "selections", selections)

    record = _build(prediction=prediction)

    _assert_ineligible(record)
    assert any(
        reason.startswith("PREDICTION_SELECTION_COUNT_INVALID:")
        for reason in record.ineligibility_reasons
    )


@pytest.mark.parametrize(
    "damaged_ticket",
    [
        (1, 2, 3, 4, 5),
        (1, 1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 50),
        (2, 1, 3, 4, 5, 6),
    ],
    ids=["wrong-length", "duplicate-number", "outside-range", "not-ascending"],
)
def test_malformed_native_ticket_fails_closed(damaged_ticket: tuple[int, ...]) -> None:
    tickets = list(_DEFAULT_TICKETS)
    tickets[0] = damaged_ticket
    if len(damaged_ticket) in {5, 6} and damaged_ticket == tuple(sorted(set(damaged_ticket))):
        prediction = _prediction(tickets=tuple(tickets))
    else:
        prediction = _prediction()
        object.__setattr__(prediction.entries[0].selections[0], "main_numbers", damaged_ticket)

    record = _build(prediction=prediction)

    _assert_ineligible(record)
    assert any(
        reason.startswith("PREDICTION_NATIVE_TICKET_INVALID:")
        for reason in record.ineligibility_reasons
    )


@pytest.mark.parametrize(
    ("freeze_sha256", "membership_sha256", "expected_reason"),
    [
        (
            "0" * 64,
            PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256,
            "FREEZE_ARTIFACT_SHA256_MISMATCH",
        ),
        (
            PINNED_FREEZE_ARTIFACT_FILE_SHA256,
            "0" * 64,
            "COHORT_MEMBERSHIP_SHA256_MISMATCH",
        ),
    ],
)
def test_freeze_and_membership_hash_mismatches_fail_closed(
    freeze_sha256: str,
    membership_sha256: str,
    expected_reason: str,
) -> None:
    record = _build(freeze_sha256=freeze_sha256, membership_sha256=membership_sha256)

    _assert_ineligible(record)
    assert expected_reason in record.ineligibility_reasons


def test_thirteen_distinct_tickets_have_k_d_13_and_no_duplicate_groups() -> None:
    record = _build()

    assert record.k_d == 13
    assert record.distinct_canonical_tickets == tuple(sorted(_DEFAULT_TICKETS))
    assert record.duplicate_groups == ()


def test_one_duplicate_pair_has_exact_group_and_k_d_12() -> None:
    tickets = list(_DEFAULT_TICKETS)
    tickets[1] = tickets[0]

    record = _build(prediction=_prediction(tickets=tuple(tickets)))

    assert record.eligibility_status is Fixed13EligibilityStatus.ELIGIBLE
    assert record.k_d == 12
    assert len(record.duplicate_groups) == 1
    assert record.duplicate_groups[0].canonical_ticket == tickets[0]
    assert record.duplicate_groups[0].member_ids == FIXED_13_COHORT_STRATEGY_IDS[:2]


def test_multiple_duplicate_groups_are_exact_and_deterministic() -> None:
    tickets = list(_DEFAULT_TICKETS)
    tickets[1] = tickets[0]
    tickets[4] = tickets[3]
    tickets[5] = tickets[3]

    first = _build(prediction=_prediction(tickets=tuple(tickets)))
    second = _build(prediction=_prediction(tickets=tuple(tickets)))

    assert first.k_d == 10
    assert first.duplicate_groups == second.duplicate_groups
    assert tuple(group.member_ids for group in first.duplicate_groups) == (
        FIXED_13_COHORT_STRATEGY_IDS[:2],
        FIXED_13_COHORT_STRATEGY_IDS[3:6],
    )


def test_all_identical_tickets_have_k_d_1() -> None:
    ticket = _DEFAULT_TICKETS[0]
    record = _build(prediction=_prediction(tickets=(ticket,) * 13))

    assert record.eligibility_status is Fixed13EligibilityStatus.ELIGIBLE
    assert record.k_d == 1
    assert record.distinct_canonical_tickets == (ticket,)
    assert record.duplicate_groups[0].member_ids == FIXED_13_COHORT_STRATEGY_IDS


def test_rng_membership_is_exactly_three_injected_and_ten_zero_arg() -> None:
    record = _build()
    by_id = {item.strategy_id: item for item in record.per_member_rng_provenance}

    assert len(RNG_REQUIRED_STRATEGY_IDS) == 3
    assert set(by_id) == set(FIXED_13_COHORT_STRATEGY_IDS)
    assert {
        strategy_id
        for strategy_id, item in by_id.items()
        if item.per_member_rng_required
    } == set(RNG_REQUIRED_STRATEGY_IDS)
    for strategy_id in RNG_REQUIRED_STRATEGY_IDS:
        item = by_id[strategy_id]
        assert item.rng_policy_id == "TARGET_BOUND_DETERMINISTIC_V1"
        assert item.adapter_construction == "RNG_INJECTED"
        assert item.rng_seed_sha256_hex is not None
        assert len(item.rng_seed_sha256_hex) == 64
    for strategy_id in set(FIXED_13_COHORT_STRATEGY_IDS) - RNG_REQUIRED_STRATEGY_IDS:
        item = by_id[strategy_id]
        assert item.adapter_construction == "ZERO_ARG_DEFAULT"
        assert item.per_member_rng_required is False
        assert item.rng_seed_sha256_hex is None


def test_wrong_rng_policy_fails_closed() -> None:
    prediction = _prediction()
    records = list(_producer_records(prediction))
    rng_index = next(
        index
        for index, record in enumerate(records)
        if record.strategy_id in RNG_REQUIRED_STRATEGY_IDS
    )
    records[rng_index] = replace(records[rng_index], rng_policy_id="WRONG_POLICY")

    record = _build(prediction=prediction, producer_records=tuple(records))

    _assert_ineligible(record)
    assert any(
        reason.startswith("PRODUCER_RNG_POLICY_INVALID:")
        for reason in record.ineligibility_reasons
    )


def test_missing_rng_seed_for_stochastic_member_fails_closed() -> None:
    prediction = _prediction()
    records = list(_producer_records(prediction))
    rng_record = next(
        item for item in records if item.strategy_id in RNG_REQUIRED_STRATEGY_IDS
    )
    object.__setattr__(rng_record, "per_member_rng_seed_sha256_hex", None)

    record = _build(prediction=prediction, producer_records=tuple(records))

    _assert_ineligible(record)
    assert any(
        reason.startswith("PRODUCER_RNG_SEED_INVALID:")
        for reason in record.ineligibility_reasons
    )


def test_fabricated_rng_seed_for_zero_arg_member_fails_closed() -> None:
    prediction = _prediction()
    records = list(_producer_records(prediction))
    zero_arg = next(
        item for item in records if item.strategy_id not in RNG_REQUIRED_STRATEGY_IDS
    )
    object.__setattr__(zero_arg, "per_member_rng_seed_sha256_hex", "f" * 64)

    record = _build(prediction=prediction, producer_records=tuple(records))

    _assert_ineligible(record)
    assert any(
        reason.startswith("PRODUCER_ZERO_ARG_RNG_SEED_FABRICATED:")
        for reason in record.ineligibility_reasons
    )


def test_reordered_rng_provenance_cannot_silently_pass() -> None:
    prediction = _prediction()
    records = list(_producer_records(prediction))
    records[0], records[1] = records[1], records[0]

    record = _build(prediction=prediction, producer_records=tuple(records))

    _assert_ineligible(record)
    assert "PRODUCER_PROVENANCE_MEMBER_ORDER_MISMATCH" in record.ineligibility_reasons


@pytest.mark.parametrize(
    ("sealed_at", "expected_status"),
    [
        (_SCHEDULED_AT - timedelta(microseconds=1), Fixed13EligibilityStatus.ELIGIBLE),
        (_SCHEDULED_AT, Fixed13EligibilityStatus.PRE_OUTCOME_INELIGIBLE),
        (_SCHEDULED_AT + timedelta(seconds=1), Fixed13EligibilityStatus.PRE_OUTCOME_INELIGIBLE),
    ],
    ids=["strictly-before", "equal", "after"],
)
def test_eligibility_timing_boundary_is_strict(
    sealed_at: datetime,
    expected_status: Fixed13EligibilityStatus,
) -> None:
    record = _build(sealed_at=sealed_at)

    assert record.eligibility_status is expected_status


def test_missing_timing_proof_is_ineligible() -> None:
    prediction = _prediction()
    record = build_fixed13_prospective_eligibility(
        prediction=prediction,
        target_registration=_registration(prediction),
        producer_records=_producer_records(prediction),
        freeze_artifact_file_sha256=PINNED_FREEZE_ARTIFACT_FILE_SHA256,
        cohort_membership_strategy_ids_lcj1_sha256=(
            PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256
        ),
        eligibility_sealed_at=_ELIGIBILITY_SEALED_AT,
        pre_outcome_timing_proof_ref=None,
        pre_outcome_timing_receipt_verdict=None,
    )

    _assert_ineligible(record)
    assert "PRE_OUTCOME_TIMING_PROOF_MISSING" in record.ineligibility_reasons


def test_malformed_timing_proof_reference_is_ineligible() -> None:
    prediction = _prediction()
    record = build_fixed13_prospective_eligibility(
        prediction=prediction,
        target_registration=_registration(prediction),
        producer_records=_producer_records(prediction),
        freeze_artifact_file_sha256=PINNED_FREEZE_ARTIFACT_FILE_SHA256,
        cohort_membership_strategy_ids_lcj1_sha256=(
            PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256
        ),
        eligibility_sealed_at=_ELIGIBILITY_SEALED_AT,
        pre_outcome_timing_proof_ref=cast(PreOutcomeTimingProofRef, "malformed-ref"),
        pre_outcome_timing_receipt_verdict=None,
    )

    _assert_ineligible(record)
    assert "PRE_OUTCOME_TIMING_PROOF_INVALID" in record.ineligibility_reasons


def test_structurally_valid_but_unverified_timing_proof_is_ineligible() -> None:
    record = _build(receipt_verdict=_unverified_receipt_verdict())

    _assert_ineligible(record)
    assert "PRE_OUTCOME_TIMING_PROOF_UNVERIFIED" in record.ineligibility_reasons
    assert record.pre_outcome_timing_proof_ref is None


def test_missing_receipt_verdict_for_a_structurally_valid_proof_is_ineligible() -> None:
    prediction = _prediction()
    record = build_fixed13_prospective_eligibility(
        prediction=prediction,
        target_registration=_registration(prediction),
        producer_records=_producer_records(prediction),
        freeze_artifact_file_sha256=PINNED_FREEZE_ARTIFACT_FILE_SHA256,
        cohort_membership_strategy_ids_lcj1_sha256=(
            PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256
        ),
        eligibility_sealed_at=_ELIGIBILITY_SEALED_AT,
        pre_outcome_timing_proof_ref=_timing_ref(),
        pre_outcome_timing_receipt_verdict=None,
    )

    _assert_ineligible(record)
    assert "PRE_OUTCOME_TIMING_PROOF_UNVERIFIED" in record.ineligibility_reasons


def test_fabricated_structural_reference_cannot_reach_eligible_without_a_verdict() -> None:
    """A syntactically valid but never-semantically-verified ref must fail closed.

    ``fabricated`` here means exactly what the CTO decision describes: a
    ``PreOutcomeTimingProofRef`` with well-formed fields (non-empty
    proof_type/reference, a valid-looking 64-hex reference_sha256) that was
    never actually confirmed by RFC3161 semantic verification.
    """

    fabricated = PreOutcomeTimingProofRef(
        proof_type="RFC3161_TSA_TOKEN_V1",
        reference="rfc3161/" + ("a" * 64) + "/" + ("b" * 64) + ".tst",
        reference_sha256="c" * 64,
    )
    prediction = _prediction()

    record = build_fixed13_prospective_eligibility(
        prediction=prediction,
        target_registration=_registration(prediction),
        producer_records=_producer_records(prediction),
        freeze_artifact_file_sha256=PINNED_FREEZE_ARTIFACT_FILE_SHA256,
        cohort_membership_strategy_ids_lcj1_sha256=(
            PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256
        ),
        eligibility_sealed_at=_ELIGIBILITY_SEALED_AT,
        pre_outcome_timing_proof_ref=fabricated,
        pre_outcome_timing_receipt_verdict=None,
    )

    _assert_ineligible(record)
    assert "PRE_OUTCOME_TIMING_PROOF_UNVERIFIED" in record.ineligibility_reasons
    assert record.eligibility_status is not Fixed13EligibilityStatus.ELIGIBLE


@pytest.mark.parametrize(
    "prediction",
    [
        _prediction(frozen_at=datetime(2026, 9, 3, 0, 0, tzinfo=UTC)),
        _prediction(outcome_presence=OutcomePresenceAtPrediction.PRESENT),
    ],
    ids=["freeze-date-ambiguous", "retrospective-outcome-present"],
)
def test_ambiguous_or_retrospective_temporal_provenance_is_ineligible(
    prediction: PredictionRecord,
) -> None:
    record = _build(prediction=prediction)

    _assert_ineligible(record)
    assert "TEMPORAL_PROVENANCE_NOT_PROSPECTIVE" in record.ineligibility_reasons


def test_prediction_for_a_different_official_draw_is_ineligible() -> None:
    prediction = _prediction()
    wrong_registration = _registration(prediction, draw_number="115000084")

    record = _build(prediction=prediction, registration=wrong_registration)

    _assert_ineligible(record)
    assert "OFFICIAL_DRAW_IDENTITY_MISMATCH" in record.ineligibility_reasons


def test_public_builder_has_no_outcome_or_winning_number_input() -> None:
    parameters = inspect.signature(build_fixed13_prospective_eligibility).parameters

    assert tuple(parameters) == (
        "prediction",
        "target_registration",
        "producer_records",
        "freeze_artifact_file_sha256",
        "cohort_membership_strategy_ids_lcj1_sha256",
        "eligibility_sealed_at",
        "pre_outcome_timing_proof_ref",
        "pre_outcome_timing_receipt_verdict",
    )
    forbidden_payload_fields = {
        "official_outcome",
        "official_winning_numbers",
        "outcome",
        "winning_numbers",
    }
    assert forbidden_payload_fields.isdisjoint(parameters)
    assert forbidden_payload_fields.isdisjoint(_build().canonical_dict())


def test_eligibility_record_digest_binds_all_semantics_except_itself() -> None:
    record = _build()
    material = record.canonical_dict()
    digest = cast(str, material.pop("eligibility_record_digest"))
    expected = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()

    assert digest == record.eligibility_record_digest == expected


@pytest.mark.parametrize("damage", ["freeze", "timing-proof", "timing", "rng-policy"])
def test_eligible_record_self_validation_rejects_forged_gate_bypass(damage: str) -> None:
    record = _build()

    with pytest.raises(ValueError):
        if damage == "freeze":
            replace(record, freeze_artifact_file_sha256="0" * 64)
        elif damage == "timing-proof":
            replace(record, pre_outcome_timing_proof_ref=None)
        elif damage == "timing":
            replace(record, eligibility_sealed_at=record.target_scheduled_at)
        else:
            provenance = list(record.per_member_rng_provenance)
            provenance[0] = replace(provenance[0], rng_policy_id="FORGED_POLICY")
            replace(record, per_member_rng_provenance=tuple(provenance))


def _eligibility_path(root: Path) -> Path:
    matches = tuple(root.rglob("eligibility.json"))
    assert len(matches) == 1
    return matches[0]


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def test_store_creates_once_reads_back_and_serializes_deterministically(tmp_path: Path) -> None:
    root = tmp_path / "fixed13-store"
    prediction = _prediction()
    eligibility = _build(prediction=prediction)
    store = FileSystemProspectiveObservationStore(root)

    assert store.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    assert store.get_eligibility(prediction.identity) is None
    assert store.create_eligibility(eligibility) is CreateOnceOutcome.INSERTED
    path = _eligibility_path(root)
    first_bytes = path.read_bytes()

    assert store.create_eligibility(eligibility) is CreateOnceOutcome.ALREADY_PRESENT
    assert path.read_bytes() == first_bytes
    assert FileSystemProspectiveObservationStore(root).get_eligibility(
        prediction.identity
    ) == eligibility
    payload = json.loads(first_bytes)
    assert first_bytes == (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def test_store_conflicting_second_eligibility_never_overwrites(tmp_path: Path) -> None:
    root = tmp_path / "fixed13-conflict"
    prediction = _prediction()
    first = _build(prediction=prediction)
    second = _build(
        prediction=prediction,
        sealed_at=_ELIGIBILITY_SEALED_AT + timedelta(minutes=1),
    )
    store = FileSystemProspectiveObservationStore(root)
    assert store.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    assert store.create_eligibility(first) is CreateOnceOutcome.INSERTED
    path = _eligibility_path(root)
    before = path.read_bytes()

    assert store.create_eligibility(second) is CreateOnceOutcome.CONFLICT
    assert path.read_bytes() == before
    assert store.get_eligibility(prediction.identity) == first


def test_store_requires_existing_matching_prediction(tmp_path: Path) -> None:
    prediction = _prediction()
    eligibility = _build(prediction=prediction)
    store = FileSystemProspectiveObservationStore(tmp_path / "missing-prediction")

    with pytest.raises(ProspectiveObservationStoreCorruptionError, match="prediction"):
        store.create_eligibility(eligibility)


def test_store_rejects_rehashed_eligibility_with_different_causal_history(
    tmp_path: Path,
) -> None:
    root = tmp_path / "fixed13-cross-record-binding"
    prediction = _prediction()
    eligibility = _build(prediction=prediction)
    store = FileSystemProspectiveObservationStore(root)
    assert store.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    assert store.create_eligibility(eligibility) is CreateOnceOutcome.INSERTED
    path = _eligibility_path(root)
    payload = cast(dict[str, object], json.loads(path.read_bytes()))
    stored_record = cast(dict[str, object], payload["record"])
    provenance = cast(
        list[dict[str, object]],
        stored_record["per_member_rng_provenance"],
    )
    for item in provenance:
        item["causal_history_digest"] = "8" * 64
    record_material = {
        key: value
        for key, value in stored_record.items()
        if key != "eligibility_record_digest"
    }
    stored_record["eligibility_record_digest"] = hashlib.sha256(
        json.dumps(
            record_material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    envelope_material = {
        "record": stored_record,
        "record_type": payload["record_type"],
        "schema_version": payload["schema_version"],
    }
    payload["envelope_sha256"] = hashlib.sha256(
        _canonical_json_bytes(envelope_material)
    ).hexdigest()
    path.write_bytes(_canonical_json_bytes(payload))

    with pytest.raises(ProspectiveObservationStoreCorruptionError, match="history digest"):
        store.get_eligibility(prediction.identity)


def test_store_rejects_symlinked_eligibility_without_touching_target(tmp_path: Path) -> None:
    root = tmp_path / "fixed13-symlink"
    outside = tmp_path / "outside-authority.json"
    outside.write_bytes(b"outside-authority\n")
    prediction = _prediction()
    eligibility = _build(prediction=prediction)
    store = FileSystemProspectiveObservationStore(root)
    assert store.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    prediction_path = next(root.rglob("prediction.json"))
    eligibility_path = prediction_path.with_name("eligibility.json")
    eligibility_path.symlink_to(outside)

    with pytest.raises(ProspectiveObservationStoreCorruptionError):
        store.create_eligibility(eligibility)
    assert outside.read_bytes() == b"outside-authority\n"
    assert eligibility_path.is_symlink()
