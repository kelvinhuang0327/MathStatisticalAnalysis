"""Focused contracts for the shared prospective-observer domain."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import PrizeEvaluationResult
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    DiagnosticEvent,
    FrozenCohortRef,
    GameEvaluation,
    MatchedBaselineRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionAvailability,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
    ScoreAvailability,
    ScoreEntry,
    ScoreRecord,
    TemporalProvenance,
    build_checkpoint_summaries,
    classify_temporal_provenance,
)

_FROZEN_AT = datetime(2026, 1, 1, tzinfo=UTC)
_PREDICTED_AT = datetime(2026, 1, 2, 1, tzinfo=UTC)
_SCORED_AT = datetime(2026, 1, 2, 2, tzinfo=UTC)


def _fingerprint(source_digest: str = "1" * 64) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id="fixture-producer",
        producer_version="v1",
        dependencies=(
            ProducerDependency("src/z.py", "2" * 64, "orchestration"),
            ProducerDependency("src/a.py", source_digest, "prediction behavior"),
        ),
    )


def _cohort(
    *,
    member_ids: tuple[str, ...] = ("candidate-1",),
    checkpoints: tuple[int, ...] = (2, 3),
) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=LotteryType.BIG_LOTTO,
        cohort_id="bounded-fixture",
        cohort_version="v1",
        authority_sha256="3" * 64,
        frozen_at=_FROZEN_AT,
        member_ids=member_ids,
        checkpoint_sizes=checkpoints,
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _context(draw_number: str, draw_date: date, *, cohort: FrozenCohortRef) -> PredictionContext:
    return PredictionContext(
        target=ObservationTarget(LotteryType.BIG_LOTTO, draw_number, draw_date),
        cohort=cohort,
        producer_fingerprint=_fingerprint(),
        causal_history=CausalHistoryRef(1, "99", date(2025, 12, 31), "4" * 64),
    )


def _baseline() -> MatchedBaselineRef:
    return MatchedBaselineRef(
        lottery_type=LotteryType.BIG_LOTTO,
        baseline_id="size-matched-random",
        baseline_version="v1",
        authority_sha256="5" * 64,
        ticket_count=1,
        candidate_sizes=(6,),
    )


def _available_draft(numbers: tuple[int, ...] = (1, 2, 3, 4, 5, 6)) -> PredictionDraft:
    return PredictionDraft(
        (
            PredictionEntryDraft.available(
                member_id="candidate-1",
                selections=(ProspectiveSelection(numbers),),
                matched_baseline=_baseline(),
            ),
        )
    )


def _prediction(
    draw_number: str,
    draw_date: date,
    *,
    cohort: FrozenCohortRef,
    draft: PredictionDraft | None = None,
) -> PredictionRecord:
    request = PredictionPhaseRequest(
        _context(draw_number, draw_date, cohort=cohort),
        OutcomePresenceAtPrediction.ABSENT,
    )
    return PredictionRecord.create(
        request=request,
        draft=draft or _available_draft(),
        predicted_at=_PREDICTED_AT,
    )


def _outcome(draw_number: str, draw_date: date) -> OfficialOutcome:
    return OfficialOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=(1, 2, 3, 4, 5, 7),
        special_number=6,
        source_id="bounded-official-fixture",
        source_sha256="6" * 64,
    )


def _game_evaluation(*, winner: bool = True) -> GameEvaluation:
    result = PrizeEvaluationResult(
        lottery_type=LotteryType.BIG_LOTTO,
        is_winner=winner,
        prize_tier="SECOND" if winner else None,
        prize_tier_order=None,
        zone1_hits=5 if winner else 0,
        zone2_hit=winner,
        prize_rule_version="fixture-v1",
        prize_rule_provenance="bounded fixture",
    )
    return GameEvaluation(
        LotteryType.BIG_LOTTO,
        (result,),
        (DiagnosticEvent("B649_ANY_SPECIAL_HIT", winner),),
    )


def _score(prediction: PredictionRecord) -> ScoreRecord:
    prediction_entry = prediction.entries[0]
    entry = (
        ScoreEntry(
            member_id=prediction_entry.member_id,
            prediction_hash=prediction_entry.prediction_hash,
            availability=ScoreAvailability.SCORED,
            evaluation=_game_evaluation(),
        )
        if prediction_entry.availability is PredictionAvailability.AVAILABLE
        else ScoreEntry(
            member_id=prediction_entry.member_id,
            prediction_hash=prediction_entry.prediction_hash,
            availability=ScoreAvailability.UNAVAILABLE_PREDICTION,
            evaluation=None,
        )
    )
    return ScoreRecord.create(
        prediction=prediction,
        outcome=_outcome(
            prediction.identity.target_draw_number,
            prediction.identity.target_draw_date,
        ),
        entries=(entry,),
        scored_at=_SCORED_AT,
    )


def test_producer_fingerprint_is_closed_sorted_and_counterfactual_sensitive() -> None:
    first = _fingerprint("1" * 64)
    second = _fingerprint("9" * 64)

    assert tuple(item.locator for item in first.dependencies) == ("src/a.py", "src/z.py")
    assert first.digest != second.digest
    with pytest.raises(ValueError, match="does not match"):
        replace(first, digest="0" * 64)


def test_prediction_context_is_structurally_outcome_free_and_immutable() -> None:
    context = _context("100", date(2026, 1, 2), cohort=_cohort())

    assert {field.name for field in fields(PredictionContext)} == {
        "target",
        "cohort",
        "producer_fingerprint",
        "causal_history",
    }
    assert not any("outcome" in field.name for field in fields(PredictionContext))
    with pytest.raises(FrozenInstanceError):
        context.target.draw_number = "101"  # type: ignore[misc]


def test_causal_history_must_end_strictly_before_target() -> None:
    cohort = _cohort()
    with pytest.raises(ValueError, match="strictly before"):
        PredictionContext(
            target=ObservationTarget(LotteryType.BIG_LOTTO, "100", date(2026, 1, 2)),
            cohort=cohort,
            producer_fingerprint=_fingerprint(),
            causal_history=CausalHistoryRef(1, "100", date(2026, 1, 2), "4" * 64),
        )


def test_prediction_hash_is_stable_across_volatile_recording_times() -> None:
    cohort = _cohort()
    request = PredictionPhaseRequest(
        _context("100", date(2026, 1, 2), cohort=cohort),
        OutcomePresenceAtPrediction.ABSENT,
    )
    first = PredictionRecord.create(
        request=request,
        draft=_available_draft(),
        predicted_at=_PREDICTED_AT,
    )
    second = PredictionRecord.create(
        request=request,
        draft=_available_draft(),
        predicted_at=datetime(2026, 1, 2, 3, tzinfo=UTC),
    )

    assert first.prediction_hash == second.prediction_hash
    assert first.entries[0].prediction_hash == second.entries[0].prediction_hash
    assert first != second
    with pytest.raises(ValueError, match="record content"):
        replace(first, prediction_hash="0" * 64)


def test_unavailable_prediction_is_explicit_and_shape_matched_baseline_is_required() -> None:
    unavailable = PredictionEntryDraft.unavailable(
        member_id="candidate-1",
        reason="NO_FORWARD_PRODUCER",
    )
    assert unavailable.availability is PredictionAvailability.UNAVAILABLE
    assert unavailable.unavailable_reason == "NO_FORWARD_PRODUCER"

    with pytest.raises(ValueError, match="match ticket count"):
        PredictionEntryDraft.available(
            member_id="candidate-1",
            selections=(ProspectiveSelection((1, 2, 3, 4, 5, 6)),),
            matched_baseline=replace(_baseline(), candidate_sizes=(5,)),
        )


@pytest.mark.parametrize(
    ("target_date", "presence", "expected"),
    [
        (
            date(2025, 12, 31),
            OutcomePresenceAtPrediction.PRESENT,
            TemporalProvenance.PRE_FREEZE_DATE_UNSEEN_HOLDOUT,
        ),
        (
            date(2026, 1, 2),
            OutcomePresenceAtPrediction.ABSENT,
            TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,
        ),
        (
            date(2026, 1, 2),
            OutcomePresenceAtPrediction.PRESENT,
            TemporalProvenance.POST_FREEZE_DATE_RETROSPECTIVE_AVAILABLE_OUTCOME,
        ),
        (
            date(2026, 1, 1),
            OutcomePresenceAtPrediction.ABSENT,
            TemporalProvenance.FREEZE_DATE_NON_PROSPECTIVE_AMBIGUOUS,
        ),
    ],
)
def test_temporal_provenance_is_explicit(
    target_date: date,
    presence: OutcomePresenceAtPrediction,
    expected: TemporalProvenance,
) -> None:
    assert (
        classify_temporal_provenance(
            target_date=target_date,
            frozen_at=_FROZEN_AT,
            outcome_presence=presence,
        )
        is expected
    )


def test_official_outcome_and_score_hashes_are_self_verifying() -> None:
    prediction = _prediction("100", date(2026, 1, 2), cohort=_cohort())
    outcome = _outcome("100", date(2026, 1, 2))
    score = _score(prediction)

    assert score.prediction_hash == prediction.prediction_hash
    assert score.outcome.outcome_hash == outcome.outcome_hash
    with pytest.raises(ValueError, match="official outcome content"):
        replace(outcome, outcome_hash="0" * 64)
    with pytest.raises(ValueError, match="score record content"):
        replace(score, score_hash="0" * 64)


def test_configured_checkpoint_engine_conserves_scored_unavailable_and_pending() -> None:
    cohort = _cohort(checkpoints=(2, 3, 5))
    first = _prediction("100", date(2026, 1, 2), cohort=cohort)
    unavailable_draft = PredictionDraft(
        (
            PredictionEntryDraft.unavailable(
                member_id="candidate-1",
                reason="NO_FORWARD_PRODUCER",
            ),
        )
    )
    second = _prediction(
        "101",
        date(2026, 1, 3),
        cohort=cohort,
        draft=unavailable_draft,
    )
    third = _prediction("102", date(2026, 1, 4), cohort=cohort)

    summaries = build_checkpoint_summaries(
        (third, first, second),
        (_score(first), _score(second)),
    )

    assert tuple(summary.checkpoint_size for summary in summaries) == (2, 3)
    checkpoint_two, checkpoint_three = summaries
    assert (
        checkpoint_two.scored_count,
        checkpoint_two.unavailable_count,
        checkpoint_two.pending_outcome_count,
        checkpoint_two.winning_count,
        checkpoint_two.nonwinning_count,
    ) == (1, 1, 0, 1, 0)
    assert checkpoint_two.diagnostic_counts[0].name == "B649_ANY_SPECIAL_HIT"
    assert checkpoint_two.diagnostic_counts[0].occurred_count == 1
    assert (
        checkpoint_three.scored_count,
        checkpoint_three.unavailable_count,
        checkpoint_three.pending_outcome_count,
    ) == (1, 1, 1)
