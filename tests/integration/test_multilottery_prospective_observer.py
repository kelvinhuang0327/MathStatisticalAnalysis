"""Cross-lottery acceptance for the two-phase prospective-observer core."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime
from threading import Barrier, Lock

import pytest

from lottolab.application.prospective_observer import (
    GameContractError,
    InMemoryProspectiveObservationStore,
    PredictionConflictError,
    PredictionPhaseService,
    PredictionRequiredError,
    PredictionSyncStatus,
    ProducerFingerprintDriftError,
    ProspectiveGameContract,
    ScoreConflictError,
    ScorePhaseRequest,
    ScoreSyncStatus,
    ScoringPhaseService,
    daily_539_game_contract,
    repository_game_contracts,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import LOTTERY_PRIZE_EVALUATOR, PrizeEvaluationResult
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
    MatchedBaselineRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntry,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ProspectiveSelection,
    ScoreAvailability,
    TemporalProvenance,
)

_FROZEN_AT = datetime(2026, 1, 1, tzinfo=UTC)
_CLOCK_VALUE = datetime(2026, 1, 2, 8, tzinfo=UTC)


class MutableProducer:
    def __init__(self, draft: PredictionDraft) -> None:
        self.draft = draft
        self.contexts: list[PredictionContext] = []

    def predict(self, context: PredictionContext) -> PredictionDraft:
        self.contexts.append(context)
        return self.draft


class BarrierProducer:
    def __init__(self, draft: PredictionDraft) -> None:
        self._draft = draft
        self._barrier = Barrier(2)

    def predict(self, context: PredictionContext) -> PredictionDraft:
        del context
        self._barrier.wait(timeout=5)
        return self._draft


class AdvancingClock:
    def __init__(self) -> None:
        self._next_hour = 8
        self._lock = Lock()

    def __call__(self) -> datetime:
        with self._lock:
            value = datetime(2026, 1, 2, self._next_hour, tzinfo=UTC)
            self._next_hour += 1
            return value


class AlteredDailyEvaluator:
    """Counterfactual DAILY_539 evaluator; delegates every other game unchanged."""

    def evaluate(
        self,
        *,
        lottery_type: LotteryType,
        predicted_main_numbers: tuple[int, ...],
        predicted_special_number: int | None,
        winning_main_numbers: tuple[int, ...],
        winning_special_number: int | None,
    ) -> PrizeEvaluationResult:
        result = LOTTERY_PRIZE_EVALUATOR.evaluate(
            lottery_type=lottery_type,
            predicted_main_numbers=predicted_main_numbers,
            predicted_special_number=predicted_special_number,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
        )
        if lottery_type is not LotteryType.DAILY_539:
            return result
        return replace(
            result,
            is_winner=False,
            prize_tier=None,
            prize_tier_order=None,
        )


def _fingerprint(source_digest: str = "1" * 64) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id="bounded-fixture-producer",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator="src/consumer/producer.py",
                source_sha256=source_digest,
                load_bearing_role="bounded prediction behavior",
            ),
        ),
    )


def _cohort(lottery_type: LotteryType) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"{lottery_type.value.lower()}-bounded-cohort",
        cohort_version="v1",
        authority_sha256="2" * 64,
        frozen_at=_FROZEN_AT,
        member_ids=("fixture-member",),
        checkpoint_sizes=(1, 2),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _baseline(lottery_type: LotteryType, candidate_size: int) -> MatchedBaselineRef:
    return MatchedBaselineRef(
        lottery_type=lottery_type,
        baseline_id=f"{lottery_type.value.lower()}-matched-random",
        baseline_version="v1",
        authority_sha256="3" * 64,
        ticket_count=1,
        candidate_sizes=(candidate_size,),
    )


def _draft(
    lottery_type: LotteryType,
    main_numbers: tuple[int, ...],
    special_number: int | None,
) -> PredictionDraft:
    return PredictionDraft(
        (
            PredictionEntryDraft.available(
                member_id="fixture-member",
                selections=(ProspectiveSelection(main_numbers, special_number),),
                matched_baseline=_baseline(lottery_type, len(main_numbers)),
            ),
        )
    )


def _request(
    lottery_type: LotteryType,
    fingerprint: ProducerFingerprint,
) -> PredictionPhaseRequest:
    return PredictionPhaseRequest(
        context=PredictionContext(
            target=ObservationTarget(lottery_type, "100", date(2026, 1, 2)),
            cohort=_cohort(lottery_type),
            producer_fingerprint=fingerprint,
            causal_history=CausalHistoryRef(
                draw_count=1,
                last_draw_number="99",
                last_draw_date=date(2025, 12, 31),
                history_sha256="4" * 64,
            ),
        ),
        outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
    )


def _outcome(
    lottery_type: LotteryType,
    main_numbers: tuple[int, ...],
    special_number: int | None,
    *,
    source_sha256: str = "5" * 64,
) -> OfficialOutcome:
    return OfficialOutcome.create(
        lottery_type=lottery_type,
        draw_number="100",
        draw_date=date(2026, 1, 2),
        main_numbers=main_numbers,
        special_number=special_number,
        source_id="bounded-official-fixture",
        source_sha256=source_sha256,
    )


def _services(
    producer: MutableProducer,
    store: InMemoryProspectiveObservationStore,
    contracts: dict[LotteryType, ProspectiveGameContract] | None = None,
) -> tuple[PredictionPhaseService, ScoringPhaseService]:
    resolved = contracts or dict(repository_game_contracts())
    return (
        PredictionPhaseService(
            store=store,
            producer=producer,
            game_contracts=resolved,
            clock=lambda: _CLOCK_VALUE,
        ),
        ScoringPhaseService(
            store=store,
            game_contracts=resolved,
            clock=lambda: _CLOCK_VALUE,
        ),
    )


@pytest.mark.parametrize(
    (
        "lottery_type",
        "predicted_main",
        "predicted_special",
        "winning_main",
        "winning_special",
        "expected_hits",
        "expected_zone2",
        "expected_tier",
    ),
    [
        (
            LotteryType.BIG_LOTTO,
            (1, 2, 3, 4, 5, 6),
            None,
            (1, 2, 3, 4, 5, 7),
            6,
            5,
            True,
            "SECOND",
        ),
        (
            LotteryType.DAILY_539,
            (1, 2, 3, 4, 5),
            None,
            (1, 2, 3, 6, 7),
            None,
            3,
            False,
            "THIRD",
        ),
        (
            LotteryType.POWER_LOTTO,
            (1, 2, 3, 4, 5, 6),
            2,
            (1, 2, 3, 4, 5, 6),
            2,
            6,
            True,
            "FIRST",
        ),
    ],
)
def test_two_phase_incremental_sync_preserves_each_lotterys_native_semantics(
    lottery_type: LotteryType,
    predicted_main: tuple[int, ...],
    predicted_special: int | None,
    winning_main: tuple[int, ...],
    winning_special: int | None,
    expected_hits: int,
    expected_zone2: bool,
    expected_tier: str,
) -> None:
    fingerprint = _fingerprint()
    request = _request(lottery_type, fingerprint)
    producer = MutableProducer(_draft(lottery_type, predicted_main, predicted_special))
    store = InMemoryProspectiveObservationStore()
    prediction_phase, scoring_phase = _services(producer, store)

    prediction_result = prediction_phase.sync(request)
    assert prediction_result.status == PredictionSyncStatus.CREATED
    assert store.scores == ()
    assert not hasattr(producer.contexts[0], "outcome")
    assert prediction_result.prediction.entries[0].matched_baseline is not None
    assert prediction_result.prediction.entries[0].matched_baseline.ticket_count == 1

    missing = scoring_phase.sync(
        ScorePhaseRequest(prediction_result.prediction.identity, fingerprint, None)
    )
    assert missing.status == ScoreSyncStatus.OUTCOME_UNAVAILABLE
    assert missing.score is None
    assert store.scores == ()

    outcome = _outcome(lottery_type, winning_main, winning_special)
    scored = scoring_phase.sync(
        ScorePhaseRequest(prediction_result.prediction.identity, fingerprint, outcome)
    )
    assert scored.status == ScoreSyncStatus.CREATED
    assert scored.score is not None
    evaluation = scored.score.entries[0].evaluation
    assert evaluation is not None
    ticket_result = evaluation.ticket_results[0]
    assert ticket_result.lottery_type is lottery_type
    assert ticket_result.zone1_hits == expected_hits
    assert ticket_result.zone2_hit is expected_zone2
    assert ticket_result.prize_tier == expected_tier

    prediction_again = prediction_phase.sync(request)
    score_again = scoring_phase.sync(
        ScorePhaseRequest(prediction_result.prediction.identity, fingerprint, outcome)
    )
    assert prediction_again.status == PredictionSyncStatus.EXACT_IDEMPOTENT_NO_OP
    assert score_again.status == ScoreSyncStatus.EXACT_IDEMPOTENT_NO_OP
    assert prediction_again.prediction == prediction_result.prediction
    assert score_again.score == scored.score


@pytest.mark.parametrize(
    ("lottery_type", "special_number", "message"),
    [
        (LotteryType.BIG_LOTTO, 1, "must not predict"),
        (LotteryType.DAILY_539, 1, "no special-number"),
        (LotteryType.POWER_LOTTO, None, "second-zone"),
    ],
)
def test_game_contracts_fail_closed_on_cross_lottery_special_number_assumptions(
    lottery_type: LotteryType,
    special_number: int | None,
    message: str,
) -> None:
    main_numbers = (
        (1, 2, 3, 4, 5)
        if lottery_type is LotteryType.DAILY_539
        else (1, 2, 3, 4, 5, 6)
    )
    producer = MutableProducer(_draft(lottery_type, main_numbers, special_number))
    prediction_phase, _ = _services(producer, InMemoryProspectiveObservationStore())

    with pytest.raises(GameContractError, match=message):
        prediction_phase.sync(_request(lottery_type, _fingerprint()))


def test_fingerprint_drift_blocks_prediction_and_score_before_silent_continuation() -> None:
    first_fingerprint = _fingerprint("1" * 64)
    changed_fingerprint = _fingerprint("9" * 64)
    producer = MutableProducer(
        _draft(LotteryType.BIG_LOTTO, (1, 2, 3, 4, 5, 6), None)
    )
    store = InMemoryProspectiveObservationStore()
    prediction_phase, scoring_phase = _services(producer, store)
    prediction = prediction_phase.sync(
        _request(LotteryType.BIG_LOTTO, first_fingerprint)
    ).prediction

    with pytest.raises(ProducerFingerprintDriftError, match="differs"):
        prediction_phase.sync(_request(LotteryType.BIG_LOTTO, changed_fingerprint))
    assert len(producer.contexts) == 1

    with pytest.raises(ProducerFingerprintDriftError, match="differs"):
        scoring_phase.sync(ScorePhaseRequest(prediction.identity, changed_fingerprint, None))


def test_conflicting_prediction_and_score_fail_closed_while_originals_remain() -> None:
    fingerprint = _fingerprint()
    producer = MutableProducer(
        _draft(LotteryType.BIG_LOTTO, (1, 2, 3, 4, 5, 6), None)
    )
    store = InMemoryProspectiveObservationStore()
    prediction_phase, scoring_phase = _services(producer, store)
    request = _request(LotteryType.BIG_LOTTO, fingerprint)
    original_prediction = prediction_phase.sync(request).prediction

    producer.draft = _draft(
        LotteryType.BIG_LOTTO,
        (7, 8, 9, 10, 11, 12),
        None,
    )
    with pytest.raises(PredictionConflictError, match="different"):
        prediction_phase.sync(request)
    assert store.get_prediction(original_prediction.identity) == original_prediction

    first_outcome = _outcome(
        LotteryType.BIG_LOTTO,
        (1, 2, 3, 4, 5, 7),
        6,
    )
    original_score = scoring_phase.sync(
        ScorePhaseRequest(original_prediction.identity, fingerprint, first_outcome)
    ).score
    assert original_score is not None
    conflicting_outcome = _outcome(
        LotteryType.BIG_LOTTO,
        (1, 2, 3, 4, 8, 9),
        7,
        source_sha256="6" * 64,
    )
    with pytest.raises(ScoreConflictError, match="different"):
        scoring_phase.sync(
            ScorePhaseRequest(
                original_prediction.identity,
                fingerprint,
                conflicting_outcome,
            )
        )
    assert store.get_score(original_prediction.identity) == original_score


def test_changing_daily_evaluator_does_not_change_big_lotto_semantics() -> None:
    standard = dict(repository_game_contracts())
    altered = dict(standard)
    altered[LotteryType.DAILY_539] = daily_539_game_contract(AlteredDailyEvaluator())

    big_entry = PredictionEntry.from_draft(
        _draft(LotteryType.BIG_LOTTO, (1, 2, 3, 4, 5, 6), None).entries[0]
    )
    big_outcome = _outcome(
        LotteryType.BIG_LOTTO,
        (1, 2, 3, 4, 5, 7),
        6,
    )
    assert standard[LotteryType.BIG_LOTTO].evaluate(
        big_entry, big_outcome
    ) == altered[LotteryType.BIG_LOTTO].evaluate(big_entry, big_outcome)

    daily_entry = PredictionEntry.from_draft(
        _draft(LotteryType.DAILY_539, (1, 2, 3, 4, 5), None).entries[0]
    )
    daily_outcome = _outcome(
        LotteryType.DAILY_539,
        (1, 2, 3, 6, 7),
        None,
    )
    assert standard[LotteryType.DAILY_539].evaluate(
        daily_entry, daily_outcome
    ) != altered[LotteryType.DAILY_539].evaluate(daily_entry, daily_outcome)


def test_unavailable_prediction_is_scored_as_explicit_unavailable_state() -> None:
    fingerprint = _fingerprint()
    producer = MutableProducer(
        PredictionDraft(
            (
                PredictionEntryDraft.unavailable(
                    member_id="fixture-member",
                    reason="NO_FORWARD_PRODUCER",
                ),
            )
        )
    )
    store = InMemoryProspectiveObservationStore()
    prediction_phase, scoring_phase = _services(producer, store)
    prediction = prediction_phase.sync(
        _request(LotteryType.BIG_LOTTO, fingerprint)
    ).prediction

    result = scoring_phase.sync(
        ScorePhaseRequest(
            prediction.identity,
            fingerprint,
            _outcome(
                LotteryType.BIG_LOTTO,
                (1, 2, 3, 4, 5, 7),
                6,
            ),
        )
    )

    assert result.score is not None
    assert result.score.entries[0].availability is ScoreAvailability.UNAVAILABLE_PREDICTION
    assert result.score.entries[0].evaluation is None


def test_score_without_prediction_is_rejected() -> None:
    fingerprint = _fingerprint()
    store = InMemoryProspectiveObservationStore()
    producer = MutableProducer(
        _draft(LotteryType.BIG_LOTTO, (1, 2, 3, 4, 5, 6), None)
    )
    _, scoring_phase = _services(producer, store)
    identity = ProspectiveObservationIdentity.from_context(
        _request(LotteryType.BIG_LOTTO, fingerprint).context
    )

    with pytest.raises(PredictionRequiredError, match="requires"):
        scoring_phase.sync(ScorePhaseRequest(identity, fingerprint, None))


def test_simultaneous_identical_first_predictions_are_one_create_and_one_exact_no_op() -> None:
    fingerprint = _fingerprint()
    request = _request(LotteryType.BIG_LOTTO, fingerprint)
    producer = BarrierProducer(
        _draft(LotteryType.BIG_LOTTO, (1, 2, 3, 4, 5, 6), None)
    )
    store = InMemoryProspectiveObservationStore()
    service = PredictionPhaseService(
        store=store,
        producer=producer,
        game_contracts=repository_game_contracts(),
        clock=AdvancingClock(),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(executor.submit(service.sync, request) for _ in range(2))
        results = tuple(future.result(timeout=5) for future in futures)

    assert {result.status for result in results} == {
        PredictionSyncStatus.CREATED,
        PredictionSyncStatus.EXACT_IDEMPOTENT_NO_OP,
    }
    persisted = store.get_prediction(results[0].prediction.identity)
    assert persisted is not None
    assert all(result.prediction == persisted for result in results)
