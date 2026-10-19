"""Unit tests for Stage E prospective result join application service."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from lottolab.application.draw_data import DrawRecord
from lottolab.application.prospective_observer import (
    GameContractError,
    InMemoryProspectiveObservationStore,
    PredictionPhaseRequest,
    PredictionPhaseService,
    PredictionRequiredError,
    ProducerFingerprintDriftError,
    ScoreConflictError,
    ScoringPhaseService,
    repository_game_contracts,
)
from lottolab.application.prospective_result_join import (
    OfficialDrawReader,
    ProspectiveResultJoinService,
    ProspectiveResultJoinStatus,
    official_outcome_from_draw_record,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
    MatchedBaselineRef,
    ObservationTarget,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ProspectiveSelection,
    ScoreAvailability,
    TemporalProvenance,
)

_PREDICTED_AT = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
_SCORED_AT = datetime(2026, 1, 2, 22, 0, tzinfo=UTC)
_DRAW_NUMBER = "115000001"
_DRAW_DATE = date(2026, 1, 2)


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _cohort(
    lottery_type: LotteryType, member_ids: tuple[str, ...] = ("member-1",)
) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"test-cohort-{lottery_type.value.lower()}",
        cohort_version="v1",
        authority_sha256=_sha256(f"cohort:{lottery_type.value}"),
        frozen_at=datetime(2025, 12, 31, tzinfo=UTC),
        member_ids=member_ids,
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _fingerprint(lottery_type: LotteryType, version: str = "v1") -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id=f"test-producer-{lottery_type.value.lower()}",
        producer_version=version,
        dependencies=(
            ProducerDependency(
                locator=f"test://producer/{lottery_type.value}/{version}",
                source_sha256=_sha256(f"dep:{lottery_type.value}:{version}"),
                load_bearing_role="test prediction role",
            ),
        ),
    )


def _baseline(lottery_type: LotteryType, ticket_count: int = 1) -> MatchedBaselineRef:
    size = 5 if lottery_type is LotteryType.DAILY_539 else 6
    return MatchedBaselineRef(
        lottery_type=lottery_type,
        baseline_id=f"test-baseline-{lottery_type.value.lower()}",
        baseline_version="v1",
        authority_sha256=_sha256(f"baseline:{lottery_type.value}"),
        ticket_count=ticket_count,
        candidate_sizes=tuple(size for _ in range(ticket_count)),
    )


def _available_draft(
    lottery_type: LotteryType,
    member_id: str = "member-1",
    selections: tuple[ProspectiveSelection, ...] | None = None,
) -> PredictionDraft:
    if selections is None:
        if lottery_type is LotteryType.DAILY_539:
            selections = (ProspectiveSelection((1, 2, 3, 4, 5)),)
        elif lottery_type is LotteryType.POWER_LOTTO:
            selections = (ProspectiveSelection((1, 2, 3, 4, 5, 6), 2),)
        else:
            selections = (ProspectiveSelection((1, 2, 3, 4, 5, 6)),)
    return PredictionDraft(
        (
            PredictionEntryDraft.available(
                member_id=member_id,
                selections=selections,
                matched_baseline=_baseline(lottery_type, len(selections)),
            ),
        )
    )


def _unavailable_draft(member_id: str = "member-1") -> PredictionDraft:
    return PredictionDraft(
        (
            PredictionEntryDraft.unavailable(
                member_id=member_id,
                reason="test unavailable prediction",
            ),
        )
    )


class _StaticProducer:
    def __init__(self, draft: PredictionDraft) -> None:
        self._draft = draft

    def predict(self, context: PredictionContext) -> PredictionDraft:
        return self._draft


class _InMemoryDrawReader(OfficialDrawReader):
    def __init__(self, draws: list[DrawRecord] | None = None) -> None:
        self._draws: dict[tuple[LotteryType, str], DrawRecord] = {}
        if draws:
            for draw in draws:
                self._draws[(draw.lottery_type, draw.draw_number)] = draw

    def add(self, draw: DrawRecord) -> None:
        self._draws[(draw.lottery_type, draw.draw_number)] = draw

    def find(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None:
        return self._draws.get((lottery_type, draw_number))


def _draw_record(
    lottery_type: LotteryType,
    *,
    draw_number: str = _DRAW_NUMBER,
    draw_date: date = _DRAW_DATE,
    main_numbers: tuple[int, ...] | None = None,
    special_numbers: tuple[int, ...] | None = None,
    source_name: str | None = "synthetic-official-draw",
    source_reference: str | None = "run-001",
    ingestion_run_id: str = "ingestion-001",
) -> DrawRecord:
    if main_numbers is None:
        main_numbers = (
            (1, 2, 3, 4, 5) if lottery_type is LotteryType.DAILY_539 else (1, 2, 3, 4, 5, 6)
        )
    if special_numbers is None:
        special_numbers = () if lottery_type is LotteryType.DAILY_539 else (2,)
    return DrawRecord(
        internal_id=1,
        lottery_type=lottery_type,
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=main_numbers,
        special_numbers=special_numbers,
        normalized_record_hash=_sha256(f"draw:{lottery_type.value}:{draw_number}"),
        source_name=source_name,
        source_reference=source_reference,
        ingestion_run_id=ingestion_run_id,
        created_at=datetime(2026, 1, 2, 21, 0, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, 21, 0, tzinfo=UTC),
    )


def _seal_prediction(
    store: InMemoryProspectiveObservationStore,
    lottery_type: LotteryType,
    draft: PredictionDraft,
    *,
    cohort: FrozenCohortRef | None = None,
    fingerprint: ProducerFingerprint | None = None,
    draw_number: str = _DRAW_NUMBER,
    draw_date: date = _DRAW_DATE,
) -> PredictionRecord:
    selected_cohort = cohort or _cohort(lottery_type)
    selected_fingerprint = fingerprint or _fingerprint(lottery_type)
    target = ObservationTarget(lottery_type, draw_number, draw_date)
    last_num = str(int(draw_number) - 1)
    last_dt = date(draw_date.year, draw_date.month, draw_date.day - 1)
    causal_history = CausalHistoryRef(
        draw_count=1,
        last_draw_number=last_num,
        last_draw_date=last_dt,
        history_sha256=_sha256("causal-history"),
    )
    context = PredictionContext(
        target=target,
        cohort=selected_cohort,
        producer_fingerprint=selected_fingerprint,
        causal_history=causal_history,
    )
    service = PredictionPhaseService(
        store=store,
        producer=_StaticProducer(draft),
        game_contracts=repository_game_contracts(),
        clock=lambda: _PREDICTED_AT,
    )
    result = service.sync(
        PredictionPhaseRequest(
            context=context,
            outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
        )
    )
    return result.prediction


def _setup_service(
    lottery_type: LotteryType,
    store: InMemoryProspectiveObservationStore,
    draw_reader: OfficialDrawReader,
) -> ProspectiveResultJoinService:
    contracts = repository_game_contracts()
    scoring = ScoringPhaseService(
        store=store,
        game_contracts={lottery_type: contracts[lottery_type]},
        clock=lambda: _SCORED_AT,
    )
    return ProspectiveResultJoinService(
        draw_reader=draw_reader,
        scoring_service=scoring,
        store=store,
    )


# =============================================================================
# T539 Tests
# =============================================================================


def test_t539_exact_result_join_success() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    draw = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    result = service.join_prediction(prediction)

    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.lottery_type is LotteryType.DAILY_539
    assert result.identity == prediction.identity
    assert result.outcome is not None
    assert result.outcome.lottery_type is LotteryType.DAILY_539
    assert result.outcome.main_numbers == (1, 2, 3, 4, 5)
    assert result.outcome.special_number is None
    assert result.score is not None
    assert result.score.prediction_hash == prediction.prediction_hash
    assert result.score.outcome.outcome_hash == result.outcome.outcome_hash
    assert len(result.score.entries) == 1
    assert result.score.entries[0].availability is ScoreAvailability.SCORED
    assert result.score.entries[0].evaluation is not None
    assert result.score.entries[0].evaluation.is_winner is True
    assert result.score.entries[0].evaluation.ticket_results[0].prize_tier == "FIRST"


def test_t539_rejects_wrong_draw_number() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    draw = _draw_record(LotteryType.DAILY_539, draw_number="115000002")  # Mismatched draw number
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    # When reader has draw with another number, find("115000001") is None -> OUTCOME_UNAVAILABLE
    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE
    assert result.score is None


def test_t539_rejects_wrong_draw_date() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    draw = _draw_record(
        LotteryType.DAILY_539,
        draw_number=_DRAW_NUMBER,
        draw_date=date(2026, 1, 3),  # Mismatched date
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    with pytest.raises(GameContractError, match="official draw identity does not match prediction"):
        service.join_prediction(prediction)


def test_t539_rejects_wrong_lottery_type() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    # Draw has POWER_LOTTO type instead of DAILY_539
    draw = _draw_record(LotteryType.POWER_LOTTO, draw_number=_DRAW_NUMBER)
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    # reader.find(DAILY_539, _DRAW_NUMBER) is None because reader has POWER_LOTTO
    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE


def test_t539_special_number_unexpectedly_present_fails_closed() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    draw = _draw_record(
        LotteryType.DAILY_539,
        main_numbers=(1, 2, 3, 4, 5),
        special_numbers=(7,),  # Non-empty special numbers for T539!
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    with pytest.raises(GameContractError, match="DAILY_539 has no special-number semantics"):
        service.join_prediction(prediction)


def test_t539_winning_and_nonwinning_cases() -> None:
    store = InMemoryProspectiveObservationStore()
    # Ticket: (1, 2, 3, 4, 5)
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    # Non-winning draw: (10, 11, 12, 13, 14) -> 0 hits
    draw = _draw_record(
        LotteryType.DAILY_539, main_numbers=(10, 11, 12, 13, 14), special_numbers=()
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.score is not None
    evaluation = result.score.entries[0].evaluation
    assert evaluation is not None
    assert evaluation.is_winner is False
    assert evaluation.ticket_results[0].prize_tier is None
    assert evaluation.ticket_results[0].zone1_hits == 0
    # Diagnostic event: T539_ANY_M2_PLUS should be False
    diag = {d.name: d.occurred for d in evaluation.diagnostic_events}
    assert diag["T539_ANY_M2_PLUS"] is False


def test_t539_multi_ticket_order_preserved() -> None:
    store = InMemoryProspectiveObservationStore()
    selections = (
        ProspectiveSelection((1, 2, 3, 4, 5)),
        ProspectiveSelection((10, 20, 30, 35, 39)),
        ProspectiveSelection((2, 3, 4, 5, 6)),
    )
    prediction = _seal_prediction(
        store,
        LotteryType.DAILY_539,
        _available_draft(LotteryType.DAILY_539, selections=selections),
    )
    draw = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.score is not None
    evaluation = result.score.entries[0].evaluation
    assert evaluation is not None
    assert len(evaluation.ticket_results) == 3
    # First ticket: 5 hits -> FIRST
    assert evaluation.ticket_results[0].prize_tier == "FIRST"
    assert evaluation.ticket_results[0].zone1_hits == 5
    # Second ticket: 0 hits -> None
    assert evaluation.ticket_results[1].prize_tier is None
    assert evaluation.ticket_results[1].zone1_hits == 0
    # Third ticket: 4 hits (2, 3, 4, 5) -> SECOND
    assert evaluation.ticket_results[2].prize_tier == "SECOND"
    assert evaluation.ticket_results[2].zone1_hits == 4


def test_t539_unavailable_prediction_scored_as_unavailable() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(store, LotteryType.DAILY_539, _unavailable_draft())
    draw = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.score is not None
    assert len(result.score.entries) == 1
    entry = result.score.entries[0]
    assert entry.availability is ScoreAvailability.UNAVAILABLE_PREDICTION
    assert entry.evaluation is None


# =============================================================================
# P638 Tests
# =============================================================================


def test_p638_exact_result_join_success() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    )
    draw = _draw_record(
        LotteryType.POWER_LOTTO,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(2,),
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.POWER_LOTTO, store, reader)

    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.lottery_type is LotteryType.POWER_LOTTO
    assert result.outcome is not None
    assert result.outcome.lottery_type is LotteryType.POWER_LOTTO
    assert result.outcome.main_numbers == (1, 2, 3, 4, 5, 6)
    assert result.outcome.special_number == 2
    assert result.score is not None
    evaluation = result.score.entries[0].evaluation
    assert evaluation is not None
    assert evaluation.is_winner is True
    assert evaluation.ticket_results[0].prize_tier == "FIRST"
    diag = {d.name: d.occurred for d in evaluation.diagnostic_events}
    assert diag["P638_ANY_ZONE1_M2_PLUS"] is True
    assert diag["P638_ANY_ZONE2_HIT"] is True


def test_p638_missing_zone2_fails_closed() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    )
    draw = _draw_record(
        LotteryType.POWER_LOTTO,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(),  # Missing Zone-2!
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.POWER_LOTTO, store, reader)

    with pytest.raises(GameContractError, match="outcome special number is required"):
        service.join_prediction(prediction)


def test_p638_invalid_zone2_out_of_range_fails_closed() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    )
    draw = _draw_record(
        LotteryType.POWER_LOTTO,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(9,),  # Zone-2 must be 1..8, 9 is out of range!
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.POWER_LOTTO, store, reader)

    with pytest.raises(
        GameContractError, match="special number is outside the game contract range"
    ):
        service.join_prediction(prediction)


def test_p638_zone1_and_zone2_diagnostics() -> None:
    store = InMemoryProspectiveObservationStore()
    # Prediction: Zone-1 (1, 2, 3, 4, 5, 6), Zone-2: 5
    selections = (ProspectiveSelection((1, 2, 3, 4, 5, 6), 5),)
    prediction = _seal_prediction(
        store,
        LotteryType.POWER_LOTTO,
        _available_draft(LotteryType.POWER_LOTTO, selections=selections),
    )
    # Outcome: Zone-1 (1, 2, 10, 20, 30, 38) [2 hits], Zone-2: 5 [hit]
    draw = _draw_record(
        LotteryType.POWER_LOTTO,
        main_numbers=(1, 2, 10, 20, 30, 38),
        special_numbers=(5,),
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.POWER_LOTTO, store, reader)

    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.score is not None
    evaluation = result.score.entries[0].evaluation
    assert evaluation is not None
    diag = {d.name: d.occurred for d in evaluation.diagnostic_events}
    assert diag["P638_ANY_ZONE1_M2_PLUS"] is True
    assert diag["P638_ANY_ZONE2_HIT"] is True


def test_p638_multi_ticket_order_preserved() -> None:
    store = InMemoryProspectiveObservationStore()
    selections = (
        ProspectiveSelection((1, 2, 3, 4, 5, 6), 1),
        ProspectiveSelection((7, 8, 9, 10, 11, 12), 2),
        ProspectiveSelection((1, 2, 10, 11, 20, 21), 3),
    )
    prediction = _seal_prediction(
        store,
        LotteryType.POWER_LOTTO,
        _available_draft(LotteryType.POWER_LOTTO, selections=selections),
    )
    draw = _draw_record(
        LotteryType.POWER_LOTTO,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(1,),
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.POWER_LOTTO, store, reader)

    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.score is not None
    evaluation = result.score.entries[0].evaluation
    assert evaluation is not None
    assert len(evaluation.ticket_results) == 3
    # Ticket 1: 6+1 -> FIRST
    assert evaluation.ticket_results[0].prize_tier == "FIRST"
    # Ticket 2: 0+0 -> None
    assert evaluation.ticket_results[1].prize_tier is None
    # Ticket 3: 2+0 -> None (Zone-1 hits = 2, Zone-2 hit = False)
    assert evaluation.ticket_results[2].zone1_hits == 2
    assert evaluation.ticket_results[2].zone2_hit is False


def test_p638_unavailable_prediction_scored_as_unavailable() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(store, LotteryType.POWER_LOTTO, _unavailable_draft())
    draw = _draw_record(
        LotteryType.POWER_LOTTO,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(1,),
    )
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.POWER_LOTTO, store, reader)

    result = service.join_prediction(prediction)
    assert result.status is ProspectiveResultJoinStatus.CREATED
    assert result.score is not None
    assert len(result.score.entries) == 1
    assert result.score.entries[0].availability is ScoreAvailability.UNAVAILABLE_PREDICTION
    assert result.score.entries[0].evaluation is None


# =============================================================================
# Generic Result Join Tests
# =============================================================================


def test_prediction_and_outcome_hash_binding() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    draw = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    result = service.join_prediction(prediction)
    assert result.score is not None
    assert result.outcome is not None
    # ScoreRecord.prediction_hash must match exact PredictionRecord.prediction_hash
    assert result.score.prediction_hash == prediction.prediction_hash
    # ScoreRecord.outcome.outcome_hash must match exact OfficialOutcome.outcome_hash
    assert result.score.outcome.outcome_hash == result.outcome.outcome_hash


def test_exact_retry_idempotency() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    draw = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    result1 = service.join_prediction(prediction)
    assert result1.status is ProspectiveResultJoinStatus.CREATED

    result2 = service.join_prediction(prediction)
    assert result2.status is ProspectiveResultJoinStatus.EXACT_IDEMPOTENT_NO_OP
    assert result2.score == result1.score
    assert result2.outcome == result1.outcome


def test_conflicting_outcome_fails_closed() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = _seal_prediction(
        store, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    draw1 = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw1])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    result1 = service.join_prediction(prediction)
    assert result1.status is ProspectiveResultJoinStatus.CREATED

    # Second join attempt with conflicting draw numbers!
    draw2 = _draw_record(
        LotteryType.DAILY_539,
        main_numbers=(10, 20, 30, 31, 32),
        special_numbers=(),
    )
    reader2 = _InMemoryDrawReader([draw2])
    service2 = _setup_service(LotteryType.DAILY_539, store, reader2)

    with pytest.raises(
        ScoreConflictError, match="score identity already contains different immutable content"
    ):
        service2.join_prediction(prediction)


def test_producer_fingerprint_drift_fails_closed() -> None:
    store = InMemoryProspectiveObservationStore()
    fp_v1 = _fingerprint(LotteryType.DAILY_539, version="v1")
    prediction = _seal_prediction(
        store,
        LotteryType.DAILY_539,
        _available_draft(LotteryType.DAILY_539),
        fingerprint=fp_v1,
    )
    draw = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    # Attempt join with drifted producer fingerprint version v2
    fp_v2 = _fingerprint(LotteryType.DAILY_539, version="v2")
    with pytest.raises(
        ProducerFingerprintDriftError,
        match="producer fingerprint differs from immutable prediction authority",
    ):
        service.join_result(prediction.identity, fp_v2)


def test_scoring_before_prediction_fails_closed() -> None:
    store = InMemoryProspectiveObservationStore()
    identity = ProspectiveObservationIdentity(
        lottery_type=LotteryType.DAILY_539,
        cohort_id="test-cohort-daily_539",
        cohort_version="v1",
        target_draw_number=_DRAW_NUMBER,
        target_draw_date=_DRAW_DATE,
    )
    fp = _fingerprint(LotteryType.DAILY_539)
    draw = _draw_record(LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5), special_numbers=())
    reader = _InMemoryDrawReader([draw])
    service = _setup_service(LotteryType.DAILY_539, store, reader)

    with pytest.raises(PredictionRequiredError, match="score requires an immutable prediction"):
        service.join_result(identity, fp)


def test_official_outcome_from_draw_record_helper() -> None:
    draw = _draw_record(
        LotteryType.DAILY_539,
        draw_number="115000099",
        draw_date=date(2026, 3, 1),
        main_numbers=(5, 10, 15, 20, 25),
        special_numbers=(),
        source_name="official-source",
    )
    outcome = official_outcome_from_draw_record(draw)
    assert outcome.lottery_type is LotteryType.DAILY_539
    assert outcome.draw_number == "115000099"
    assert outcome.draw_date == date(2026, 3, 1)
    assert outcome.main_numbers == (5, 10, 15, 20, 25)
    assert outcome.special_number is None
    assert outcome.source_id == "official-source"
    assert outcome.source_sha256 == draw.normalized_record_hash
