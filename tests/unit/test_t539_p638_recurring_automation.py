"""Unit tests for T539 and P638 recurring automation state machine and runner."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from lottolab.application.forward_evidence_ledger import (
    ForwardEvidenceLedgerAppendResult,
    ForwardEvidenceLedgerAppendStatus,
    ForwardEvidenceLedgerService,
)
from lottolab.application.ports import FutureDrawIdentityReader
from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationStatus,
)
from lottolab.application.prospective_observer import (
    ProspectiveObservationStore,
)
from lottolab.application.prospective_prediction_seal import (
    RunnablePredictionSealResult,
    RunnablePredictionSealService,
    RunnablePredictionSealStatus,
)
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinResult,
    ProspectiveResultJoinService,
    ProspectiveResultJoinStatus,
)
from lottolab.application.t539_p638_recurring_automation import (
    CanonicalCycleTarget,
    RecurringCycleState,
    SingleGameCycleResult,
    SingleGameRecurringRunner,
    T539P638RecurringAutomationService,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.forward_evidence_ledger import ForwardEvidenceLedgerEntry
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prize_evaluation import PrizeEvaluationResult
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
    GameEvaluation,
    MatchedBaselineRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ProspectiveSelection,
    ScoreAvailability,
    ScoreEntry,
    ScoreRecord,
    TemporalProvenance,
)

_NOW = datetime(2099, 1, 1, 8, tzinfo=UTC)
_SCHEDULED = datetime(2099, 1, 1, 12, 30, tzinfo=UTC)  # 20:30 Asia/Taipei
_DRAW_DATE = date(2099, 1, 1)
_DRAW_NUMBER = "113000001"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_cohort(lottery_type: LotteryType, member_id: str = "member_1") -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"cohort_{lottery_type.value.lower()}",
        cohort_version="1.0",
        authority_sha256=_sha256("cohort_auth"),
        frozen_at=datetime(2099, 1, 1, 0, 0, tzinfo=UTC),
        member_ids=(member_id,),
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _build_baseline(lottery_type: LotteryType) -> MatchedBaselineRef:
    return MatchedBaselineRef(
        lottery_type=lottery_type,
        baseline_id="unit_baseline",
        baseline_version="1.0",
        authority_sha256=_sha256("unit_baseline_auth"),
        ticket_count=1,
        candidate_sizes=(5,) if lottery_type is LotteryType.DAILY_539 else (6,),
    )


def _build_fingerprint(lottery_type: LotteryType) -> ProducerFingerprint:
    dep = ProducerDependency(
        locator=f"schedule://{lottery_type.value}",
        source_sha256=_sha256("sched_auth"),
        load_bearing_role="SCHEDULE_AUTHORITY",
    )
    return ProducerFingerprint.create(
        producer_id=f"producer_{lottery_type.value.lower()}",
        producer_version="1.0",
        dependencies=(dep,),
    )


def _build_target(
    lottery_type: LotteryType = LotteryType.DAILY_539,
    draw_number: str = _DRAW_NUMBER,
    draw_date: date = _DRAW_DATE,
    scheduled_at: datetime = _SCHEDULED,
) -> CanonicalCycleTarget:
    return CanonicalCycleTarget(
        lottery_type=lottery_type,
        draw_number=draw_number,
        draw_date=draw_date,
        scheduled_at=scheduled_at,
    )


def _build_prediction(
    target: CanonicalCycleTarget,
    cohort: FrozenCohortRef,
    fingerprint: ProducerFingerprint,
    predicted_at: datetime = _NOW,
    available: bool = True,
) -> PredictionRecord:
    obs_target = target.observation_target
    causal = CausalHistoryRef(
        draw_count=100,
        last_draw_number="113000000",
        last_draw_date=date(2098, 12, 31),
        history_sha256=_sha256("history"),
    )
    context = PredictionContext(
        target=obs_target,
        cohort=cohort,
        producer_fingerprint=fingerprint,
        causal_history=causal,
    )
    request = PredictionPhaseRequest(
        context=context,
        outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
    )
    if available:
        sel = (
            ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5))
            if target.lottery_type is LotteryType.DAILY_539
            else ProspectiveSelection(main_numbers=(1, 2, 3, 4, 5, 6), special_number=1)
        )
        entries = (
            PredictionEntryDraft.available(
                member_id=cohort.member_ids[0],
                selections=(sel,),
                matched_baseline=_build_baseline(target.lottery_type),
            ),
        )
    else:
        entries = (
            PredictionEntryDraft.unavailable(
                member_id=cohort.member_ids[0],
                reason="Unavailable in fixture",
            ),
        )
    return PredictionRecord.create(
        request=request,
        draft=PredictionDraft(entries=entries),
        predicted_at=predicted_at,
    )


def _build_game_evaluation(lottery_type: LotteryType) -> GameEvaluation:
    return GameEvaluation(
        lottery_type=lottery_type,
        ticket_results=(
            PrizeEvaluationResult(
                lottery_type=lottery_type,
                is_winner=True,
                prize_tier="頭獎",
                prize_tier_order=1,
                zone1_hits=5 if lottery_type is LotteryType.DAILY_539 else 6,
                zone2_hit=lottery_type is not LotteryType.DAILY_539,
                prize_rule_version="v1",
                prize_rule_provenance="unit_fixture",
            ),
        ),
        diagnostic_events=(),
    )


def test_canonical_cycle_target_validation() -> None:
    target = _build_target()
    assert target.lottery_type is LotteryType.DAILY_539
    assert target.draw_number == _DRAW_NUMBER
    assert target.draw_date == _DRAW_DATE
    assert target.scheduled_at == _SCHEDULED
    assert target.observation_target == ObservationTarget(
        lottery_type=LotteryType.DAILY_539,
        draw_number=_DRAW_NUMBER,
        draw_date=_DRAW_DATE,
    )

    # Rejects invalid inputs
    with pytest.raises(ValueError, match="Unsupported lottery type"):
        CanonicalCycleTarget(
            lottery_type=LotteryType.BIG_LOTTO,  # Stage H supports only DAILY_539 & POWER_LOTTO
            draw_number="100",
            draw_date=date(2099, 1, 1),
            scheduled_at=_SCHEDULED,
        )

    with pytest.raises(ValueError, match="draw_number must be non-empty text"):
        CanonicalCycleTarget(
            lottery_type=LotteryType.DAILY_539,
            draw_number="",
            draw_date=date(2099, 1, 1),
            scheduled_at=_SCHEDULED,
        )


def test_recurring_cycle_state_values() -> None:
    assert RecurringCycleState.AWAITING_SCHEDULE == "AWAITING_SCHEDULE"
    assert RecurringCycleState.PRE_DRAW_SEAL_COMPLETED == "PRE_DRAW_SEAL_COMPLETED"
    assert RecurringCycleState.AWAITING_OFFICIAL_OUTCOME == "AWAITING_OFFICIAL_OUTCOME"
    assert RecurringCycleState.POST_DRAW_JOIN_COMPLETED == "POST_DRAW_JOIN_COMPLETED"
    assert RecurringCycleState.EVIDENCE_LEDGER_APPENDED == "EVIDENCE_LEDGER_APPENDED"
    assert RecurringCycleState.CYCLE_ADVANCED == "CYCLE_ADVANCED"


def test_pre_draw_wake_creates_prediction_seal() -> None:
    lottery_type = LotteryType.DAILY_539
    cohort = _build_cohort(lottery_type)
    fp = _build_fingerprint(lottery_type)
    target = _build_target(lottery_type)
    prediction = _build_prediction(target, cohort, fp)

    mock_future_reader = MagicMock(spec=FutureDrawIdentityReader)
    mock_seal_service = MagicMock(spec=RunnablePredictionSealService)
    mock_pred_store = MagicMock(spec=ProspectiveObservationStore)
    mock_join_service = MagicMock(spec=ProspectiveResultJoinService)
    mock_ledger_service = MagicMock(spec=ForwardEvidenceLedgerService)

    # Initial state: no prediction in store
    mock_pred_store.get_prediction.return_value = None
    mock_pred_store.get_score.return_value = None

    source_prov = TargetSourceProvenance(
        source_id="test_source",
        source_version="v1",
        source_locator="fixture://test",
        source_sha256=_sha256("source"),
        observed_at=_NOW,
    )
    announcement = TargetAnnouncement(
        target=target.observation_target,
        scheduled_at=target.scheduled_at,
        schedule_timezone="Asia/Taipei",
        source=source_prov,
    )
    attestation = OutcomePresenceAttestation(
        target=target.observation_target,
        presence=OutcomePresenceAtPrediction.ABSENT,
        attested_at=_NOW,
        source=source_prov,
    )
    registration = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=attestation,
        causal_history=prediction.causal_history,
        registered_at=_NOW,
    )

    seal_res = RunnablePredictionSealResult(
        status=RunnablePredictionSealStatus.CREATED,
        lottery_type=lottery_type,
        registration_status=OperationalRegistrationStatus.CREATED,
        registration=registration,
        immutable_schedule_sha256=_sha256("sched_digest"),
        prediction=prediction,
    )
    mock_seal_service.seal_earliest.return_value = seal_res

    # Result join returns OUTCOME_UNAVAILABLE in pre-draw
    join_res = ProspectiveResultJoinResult(
        status=ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE,
        lottery_type=lottery_type,
        identity=ProspectiveObservationIdentity(
            lottery_type=lottery_type,
            cohort_id=cohort.cohort_id,
            cohort_version=cohort.cohort_version,
            target_draw_number=target.draw_number,
            target_draw_date=target.draw_date,
        ),
        outcome=None,
        score=None,
    )
    mock_join_service.join_result.return_value = join_res

    runner = SingleGameRecurringRunner(
        lottery_type=lottery_type,
        future_draw_reader=mock_future_reader,
        seal_service=mock_seal_service,
        prediction_store=mock_pred_store,
        join_service=mock_join_service,
        ledger_service=mock_ledger_service,
        cohort=cohort,
        base_producer_fingerprint=fp,
        clock=lambda: _NOW,  # Pre-draw clock < scheduled_at
    )

    result = runner.run_wake(target=target)

    assert result.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
    assert result.seal_result == seal_res
    assert result.join_result == join_res
    assert result.ledger_results == ()
    assert result.cycle_action == "PRE_DRAW_SEAL_COMPLETED"
    mock_seal_service.seal_earliest.assert_called_once()
    mock_ledger_service.record_score.assert_not_called()


def test_awaiting_result_wake_when_outcome_absent() -> None:
    lottery_type = LotteryType.DAILY_539
    cohort = _build_cohort(lottery_type)
    fp = _build_fingerprint(lottery_type)
    target = _build_target(lottery_type)
    prediction = _build_prediction(target, cohort, fp)

    mock_future_reader = MagicMock(spec=FutureDrawIdentityReader)
    mock_seal_service = MagicMock(spec=RunnablePredictionSealService)
    mock_pred_store = MagicMock(spec=ProspectiveObservationStore)
    mock_join_service = MagicMock(spec=ProspectiveResultJoinService)
    mock_ledger_service = MagicMock(spec=ForwardEvidenceLedgerService)

    # Prediction exists from earlier pre-draw seal
    mock_pred_store.get_prediction.return_value = prediction
    mock_pred_store.get_score.return_value = None

    # Post-draw clock: scheduled_at + 1 hour, but outcome still unavailable
    post_draw_time = _SCHEDULED + timedelta(hours=1)
    identity = ProspectiveObservationIdentity(
        lottery_type=lottery_type,
        cohort_id=cohort.cohort_id,
        cohort_version=cohort.cohort_version,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
    )
    join_res = ProspectiveResultJoinResult(
        status=ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE,
        lottery_type=lottery_type,
        identity=identity,
        outcome=None,
        score=None,
    )
    mock_join_service.join_result.return_value = join_res

    runner = SingleGameRecurringRunner(
        lottery_type=lottery_type,
        future_draw_reader=mock_future_reader,
        seal_service=mock_seal_service,
        prediction_store=mock_pred_store,
        join_service=mock_join_service,
        ledger_service=mock_ledger_service,
        cohort=cohort,
        base_producer_fingerprint=fp,
        clock=lambda: post_draw_time,
    )

    result = runner.run_wake(target=target)

    assert result.state is RecurringCycleState.AWAITING_OFFICIAL_OUTCOME
    assert result.seal_result is None
    assert result.join_result == join_res
    assert result.ledger_results == ()
    assert result.cycle_action == "AWAITING_OFFICIAL_OUTCOME"
    mock_seal_service.seal_earliest.assert_not_called()
    mock_ledger_service.record_score.assert_not_called()


def test_post_result_wake_joins_and_appends_evidence() -> None:
    lottery_type = LotteryType.DAILY_539
    cohort = _build_cohort(lottery_type)
    fp = _build_fingerprint(lottery_type)
    target = _build_target(lottery_type)
    prediction = _build_prediction(target, cohort, fp)

    mock_future_reader = MagicMock(spec=FutureDrawIdentityReader)
    mock_seal_service = MagicMock(spec=RunnablePredictionSealService)
    mock_pred_store = MagicMock(spec=ProspectiveObservationStore)
    mock_join_service = MagicMock(spec=ProspectiveResultJoinService)
    mock_ledger_service = MagicMock(spec=ForwardEvidenceLedgerService)

    mock_pred_store.get_prediction.return_value = prediction
    mock_pred_store.get_score.return_value = None

    outcome = OfficialOutcome.create(
        lottery_type=lottery_type,
        draw_number=target.draw_number,
        draw_date=target.draw_date,
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="official_src",
        source_sha256=_sha256("official"),
    )
    score = ScoreRecord.create(
        prediction=prediction,
        outcome=outcome,
        entries=(
            ScoreEntry(
                member_id=cohort.member_ids[0],
                prediction_hash=prediction.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=_build_game_evaluation(lottery_type),
            ),
        ),
        scored_at=_SCHEDULED + timedelta(hours=2),
    )
    identity = ProspectiveObservationIdentity(
        lottery_type=lottery_type,
        cohort_id=cohort.cohort_id,
        cohort_version=cohort.cohort_version,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
    )
    join_res = ProspectiveResultJoinResult(
        status=ProspectiveResultJoinStatus.CREATED,
        lottery_type=lottery_type,
        identity=identity,
        outcome=outcome,
        score=score,
    )
    mock_join_service.join_result.return_value = join_res

    entry = ForwardEvidenceLedgerEntry.from_records(
        prediction=prediction,
        score=score,
        member_id=cohort.member_ids[0],
        entry_created_at=_SCHEDULED + timedelta(hours=2),
    )
    append_res = (
        ForwardEvidenceLedgerAppendResult(
            status=ForwardEvidenceLedgerAppendStatus.APPENDED,
            entry=entry,
        ),
    )
    mock_ledger_service.record_score.return_value = append_res

    runner = SingleGameRecurringRunner(
        lottery_type=lottery_type,
        future_draw_reader=mock_future_reader,
        seal_service=mock_seal_service,
        prediction_store=mock_pred_store,
        join_service=mock_join_service,
        ledger_service=mock_ledger_service,
        cohort=cohort,
        base_producer_fingerprint=fp,
        clock=lambda: _SCHEDULED + timedelta(hours=2),
    )

    result = runner.run_wake(target=target)

    assert result.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
    assert result.join_result == join_res
    assert result.ledger_results == append_res
    assert result.cycle_action == "POST_DRAW_JOIN_AND_EVIDENCE_APPENDED"
    mock_ledger_service.record_score.assert_called_once_with(
        prediction=prediction,
        score=score,
    )


def test_redundant_completed_wake_is_idempotent() -> None:
    lottery_type = LotteryType.DAILY_539
    cohort = _build_cohort(lottery_type)
    fp = _build_fingerprint(lottery_type)
    target = _build_target(lottery_type)
    prediction = _build_prediction(target, cohort, fp)

    outcome = OfficialOutcome.create(
        lottery_type=lottery_type,
        draw_number=target.draw_number,
        draw_date=target.draw_date,
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        source_id="official_src",
        source_sha256=_sha256("official"),
    )
    score = ScoreRecord.create(
        prediction=prediction,
        outcome=outcome,
        entries=(
            ScoreEntry(
                member_id=cohort.member_ids[0],
                prediction_hash=prediction.entries[0].prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=_build_game_evaluation(lottery_type),
            ),
        ),
        scored_at=_SCHEDULED + timedelta(hours=2),
    )

    mock_future_reader = MagicMock(spec=FutureDrawIdentityReader)
    mock_seal_service = MagicMock(spec=RunnablePredictionSealService)
    mock_pred_store = MagicMock(spec=ProspectiveObservationStore)
    mock_join_service = MagicMock(spec=ProspectiveResultJoinService)
    mock_ledger_service = MagicMock(spec=ForwardEvidenceLedgerService)

    # Both prediction and score exist in store
    mock_pred_store.get_prediction.return_value = prediction
    mock_pred_store.get_score.return_value = score

    entry = ForwardEvidenceLedgerEntry.from_records(
        prediction=prediction,
        score=score,
        member_id=cohort.member_ids[0],
        entry_created_at=_SCHEDULED + timedelta(hours=2),
    )
    # Ledger returns EXACT_IDEMPOTENT_NO_OP
    append_res = (
        ForwardEvidenceLedgerAppendResult(
            status=ForwardEvidenceLedgerAppendStatus.EXACT_IDEMPOTENT_NO_OP,
            entry=entry,
        ),
    )
    mock_ledger_service.record_score.return_value = append_res

    runner = SingleGameRecurringRunner(
        lottery_type=lottery_type,
        future_draw_reader=mock_future_reader,
        seal_service=mock_seal_service,
        prediction_store=mock_pred_store,
        join_service=mock_join_service,
        ledger_service=mock_ledger_service,
        cohort=cohort,
        base_producer_fingerprint=fp,
        clock=lambda: _SCHEDULED + timedelta(hours=3),
    )

    result = runner.run_wake(target=target)

    assert result.state is RecurringCycleState.EVIDENCE_LEDGER_APPENDED
    assert result.cycle_action == "REDUNDANT_WAKE_IDEMPOTENT_NO_OP"
    mock_seal_service.seal_earliest.assert_not_called()
    mock_join_service.join_result.assert_not_called()


def test_game_isolation_in_multi_game_coordinator() -> None:
    t539_runner = MagicMock(spec=SingleGameRecurringRunner)
    p638_runner = MagicMock(spec=SingleGameRecurringRunner)

    t539_runner.run_wake.return_value = SingleGameCycleResult(
        lottery_type=LotteryType.DAILY_539,
        target=_build_target(LotteryType.DAILY_539),
        state=RecurringCycleState.PRE_DRAW_SEAL_COMPLETED,
        seal_result=None,
        join_result=None,
        ledger_results=(),
        error=None,
        cycle_action="PRE_DRAW_SEAL_COMPLETED",
    )
    # P638 fails with an unexpected exception
    p638_runner.run_wake.side_effect = RuntimeError("P638 synthetic fixture failure")

    service = T539P638RecurringAutomationService(
        runners={
            LotteryType.DAILY_539: t539_runner,
            LotteryType.POWER_LOTTO: p638_runner,
        },
        clock=lambda: _NOW,
    )

    cycle_result = service.run_cycle_wake()

    assert cycle_result.t539 is not None
    assert cycle_result.t539.state is RecurringCycleState.PRE_DRAW_SEAL_COMPLETED
    assert cycle_result.t539.error is None

    assert cycle_result.p638 is not None
    assert cycle_result.p638.error == "RuntimeError: P638 synthetic fixture failure"
    assert cycle_result.p638.cycle_action == "GAME_CYCLE_ERROR"


def test_unsealed_target_past_scheduled_at_fails_closed() -> None:
    lottery_type = LotteryType.DAILY_539
    cohort = _build_cohort(lottery_type)
    fp = _build_fingerprint(lottery_type)
    target = _build_target(lottery_type)

    mock_future_reader = MagicMock(spec=FutureDrawIdentityReader)
    mock_seal_service = MagicMock(spec=RunnablePredictionSealService)
    mock_pred_store = MagicMock(spec=ProspectiveObservationStore)
    mock_join_service = MagicMock(spec=ProspectiveResultJoinService)
    mock_ledger_service = MagicMock(spec=ForwardEvidenceLedgerService)

    # No prediction sealed
    mock_pred_store.get_prediction.return_value = None
    mock_pred_store.get_score.return_value = None

    # Clock is AFTER scheduled_at
    runner = SingleGameRecurringRunner(
        lottery_type=lottery_type,
        future_draw_reader=mock_future_reader,
        seal_service=mock_seal_service,
        prediction_store=mock_pred_store,
        join_service=mock_join_service,
        ledger_service=mock_ledger_service,
        cohort=cohort,
        base_producer_fingerprint=fp,
        clock=lambda: _SCHEDULED + timedelta(minutes=10),
    )

    result = runner.run_wake(target=target)

    assert result.error == "PREDICTION_WINDOW_EXPIRED"
    assert result.cycle_action == "UNSEALED_TARGET_PAST_SCHEDULED_AT"
    mock_seal_service.seal_earliest.assert_not_called()
