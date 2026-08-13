"""Focused unit contracts for generic prospective-observer runtime cycles."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, fields
from datetime import UTC, date, datetime

import pytest

from lottolab.application.prospective_observer import (
    InMemoryProspectiveObservationStore,
    PredictionPhaseService,
    PredictionRequiredError,
    ProducerFingerprintDriftError,
    ScorePhaseRequest,
    ScoringPhaseService,
    repository_game_contracts,
)
from lottolab.application.prospective_observer_runtime import (
    CheckpointProgress,
    PredictionCycleSummary,
    ProspectivePredictionRunner,
    ProspectiveScoreRunner,
    ScoreCycleSummary,
    project_checkpoint_progress,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    TemporalProvenance,
)

_FROZEN_AT = datetime(2026, 1, 1, tzinfo=UTC)
_NOW = datetime(2026, 1, 10, tzinfo=UTC)


def _clock() -> datetime:
    return _NOW


def _fingerprint(source_sha256: str = "1" * 64) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id="runtime-fixture",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator="src/runtime_fixture.py",
                source_sha256=source_sha256,
                load_bearing_role="prediction behavior",
            ),
        ),
    )


def _prediction_request(
    lottery_type: LotteryType,
    cohort_id: str,
    draw_number: str,
    draw_date: date,
    *,
    fingerprint: ProducerFingerprint | None = None,
) -> PredictionPhaseRequest:
    cohort = FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=cohort_id,
        cohort_version="v1",
        authority_sha256="2" * 64,
        frozen_at=_FROZEN_AT,
        member_ids=("candidate-a", "candidate-b"),
        checkpoint_sizes=(2, 5, 10),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )
    return PredictionPhaseRequest(
        context=PredictionContext(
            target=ObservationTarget(lottery_type, draw_number, draw_date),
            cohort=cohort,
            producer_fingerprint=fingerprint or _fingerprint(),
            causal_history=CausalHistoryRef(0, None, None, "3" * 64),
        ),
        outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
    )


class _UnavailableProducer:
    def __init__(self) -> None:
        self.contexts: list[PredictionContext] = []

    def predict(self, context: PredictionContext) -> PredictionDraft:
        self.contexts.append(context)
        return PredictionDraft(
            tuple(
                PredictionEntryDraft.unavailable(
                    member_id=member_id,
                    reason="insufficient causal history",
                )
                for member_id in context.cohort.member_ids
            )
        )


@dataclass
class _PredictionRequestSource:
    requests: tuple[PredictionPhaseRequest, ...]
    calls: int = 0

    def __call__(self) -> tuple[PredictionPhaseRequest, ...]:
        self.calls += 1
        return self.requests


@dataclass
class _ScoreRequestSource:
    requests: tuple[ScorePhaseRequest, ...]
    calls: int = 0

    def __call__(self) -> tuple[ScorePhaseRequest, ...]:
        self.calls += 1
        return self.requests


def _prediction_service(
    store: InMemoryProspectiveObservationStore,
    producer: _UnavailableProducer,
) -> PredictionPhaseService:
    return PredictionPhaseService(
        store=store,
        producer=producer,
        game_contracts=repository_game_contracts(),
        clock=_clock,
    )


def _score_service(store: InMemoryProspectiveObservationStore) -> ScoringPhaseService:
    return ScoringPhaseService(
        store=store,
        game_contracts=repository_game_contracts(),
        clock=_clock,
    )


def _identity(request: PredictionPhaseRequest) -> ProspectiveObservationIdentity:
    return ProspectiveObservationIdentity.from_context(request.context)


def _outcome(identity: ProspectiveObservationIdentity) -> OfficialOutcome:
    if identity.lottery_type is LotteryType.DAILY_539:
        main_numbers = (1, 2, 3, 4, 5)
        special_number = None
    elif identity.lottery_type is LotteryType.POWER_LOTTO:
        main_numbers = (1, 2, 3, 4, 5, 6)
        special_number = 1
    else:
        main_numbers = (1, 2, 3, 4, 5, 6)
        special_number = 7
    return OfficialOutcome.create(
        lottery_type=identity.lottery_type,
        draw_number=identity.target_draw_number,
        draw_date=identity.target_draw_date,
        main_numbers=main_numbers,
        special_number=special_number,
        source_id="official-runtime-fixture",
        source_sha256="4" * 64,
    )


def _unsorted_prediction_requests() -> tuple[PredictionPhaseRequest, ...]:
    return (
        _prediction_request(
            LotteryType.DAILY_539,
            "cohort-a",
            "1",
            date(2026, 1, 2),
        ),
        _prediction_request(
            LotteryType.BIG_LOTTO,
            "cohort-z",
            "1",
            date(2026, 1, 2),
        ),
        _prediction_request(
            LotteryType.BIG_LOTTO,
            "cohort-a",
            "10",
            date(2026, 1, 3),
        ),
        _prediction_request(
            LotteryType.BIG_LOTTO,
            "cohort-a",
            "2",
            date(2026, 1, 3),
        ),
    )


def test_prediction_runner_is_outcome_free_ordered_sequential_and_counts_entries() -> None:
    requests = _unsorted_prediction_requests()
    source = _PredictionRequestSource(requests)
    store = InMemoryProspectiveObservationStore()
    producer = _UnavailableProducer()
    runner = ProspectivePredictionRunner(
        service=_prediction_service(store, producer),
        request_source=source,
    )

    summary = runner.run_cycle()

    expected_order = (
        (LotteryType.BIG_LOTTO, "cohort-a", date(2026, 1, 3), "2"),
        (LotteryType.BIG_LOTTO, "cohort-a", date(2026, 1, 3), "10"),
        (LotteryType.BIG_LOTTO, "cohort-z", date(2026, 1, 2), "1"),
        (LotteryType.DAILY_539, "cohort-a", date(2026, 1, 2), "1"),
    )
    assert tuple(
        (
            context.target.lottery_type,
            context.cohort.cohort_id,
            context.target.draw_date,
            context.target.draw_number,
        )
        for context in producer.contexts
    ) == expected_order
    assert summary == PredictionCycleSummary(
        requested_targets=4,
        processed_targets=4,
        prediction_created=4,
        prediction_idempotent=0,
        prediction_unavailable=8,
        technical_failures=0,
        first_target=_identity(requests[3]),
        last_target=_identity(requests[0]),
    )
    assert source.calls == 1
    with pytest.raises(FrozenInstanceError):
        summary.processed_targets = 0  # type: ignore[misc]

    second = runner.run_cycle()

    assert second.prediction_created == 0
    assert second.prediction_idempotent == 4
    assert second.prediction_unavailable == 8


def test_prediction_runner_dependency_graph_has_no_outcome_member_or_source() -> None:
    runner_fields = fields(ProspectivePredictionRunner)

    assert tuple(field.name for field in runner_fields) == ("service", "request_source")
    assert all("outcome" not in field.name.lower() for field in runner_fields)
    assert all("outcome" not in str(field.type).lower() for field in runner_fields)


def test_prediction_runner_preserves_fingerprint_drift_as_a_failure() -> None:
    original = _prediction_request(
        LotteryType.BIG_LOTTO,
        "cohort-a",
        "2",
        date(2026, 1, 3),
    )
    drifted = _prediction_request(
        LotteryType.BIG_LOTTO,
        "cohort-a",
        "2",
        date(2026, 1, 3),
        fingerprint=_fingerprint("9" * 64),
    )
    store = InMemoryProspectiveObservationStore()
    producer = _UnavailableProducer()
    service = _prediction_service(store, producer)
    ProspectivePredictionRunner(service, _PredictionRequestSource((original,))).run_cycle()

    with pytest.raises(ProducerFingerprintDriftError):
        ProspectivePredictionRunner(service, _PredictionRequestSource((drifted,))).run_cycle()

    assert len(store.predictions) == 1


def test_score_runner_orders_requests_counts_statuses_and_never_creates_predictions() -> None:
    prediction_requests = _unsorted_prediction_requests()
    store = InMemoryProspectiveObservationStore()
    producer = _UnavailableProducer()
    prediction_runner = ProspectivePredictionRunner(
        _prediction_service(store, producer),
        _PredictionRequestSource(prediction_requests),
    )
    prediction_runner.run_cycle()
    prediction_count = len(store.predictions)
    score_requests = tuple(
        ScorePhaseRequest(
            identity=_identity(request),
            producer_fingerprint=request.context.producer_fingerprint,
            outcome=(None if request is prediction_requests[1] else _outcome(_identity(request))),
        )
        for request in prediction_requests
    )
    source = _ScoreRequestSource(tuple(reversed(score_requests)))
    runner = ProspectiveScoreRunner(
        service=_score_service(store),
        request_source=source,
    )

    summary = runner.run_cycle()

    assert summary == ScoreCycleSummary(
        requested_targets=4,
        processed_targets=4,
        score_created=3,
        score_idempotent=0,
        outcome_unavailable=1,
        technical_failures=0,
        first_target=_identity(prediction_requests[3]),
        last_target=_identity(prediction_requests[0]),
    )
    expected_scored_order = (
        _identity(prediction_requests[3]),
        _identity(prediction_requests[2]),
        _identity(prediction_requests[0]),
    )
    assert tuple(record.identity for record in store.scores) == expected_scored_order
    assert len(store.predictions) == prediction_count
    assert source.calls == 1

    second = runner.run_cycle()

    assert second.score_created == 0
    assert second.score_idempotent == 3
    assert second.outcome_unavailable == 1
    assert len(store.predictions) == prediction_count


def test_score_runner_requires_an_existing_prediction_and_fails_closed() -> None:
    store = InMemoryProspectiveObservationStore()
    request = _prediction_request(
        LotteryType.POWER_LOTTO,
        "missing-cohort",
        "7",
        date(2026, 1, 5),
    )
    score_request = ScorePhaseRequest(
        identity=_identity(request),
        producer_fingerprint=request.context.producer_fingerprint,
        outcome=_outcome(_identity(request)),
    )

    with pytest.raises(PredictionRequiredError):
        ProspectiveScoreRunner(
            _score_service(store),
            _ScoreRequestSource((score_request,)),
        ).run_cycle()

    assert store.predictions == ()
    assert store.scores == ()


def test_empty_cycles_are_exact_and_have_no_target_bounds() -> None:
    store = InMemoryProspectiveObservationStore()
    prediction = ProspectivePredictionRunner(
        _prediction_service(store, _UnavailableProducer()),
        _PredictionRequestSource(()),
    ).run_cycle()
    score = ProspectiveScoreRunner(
        _score_service(store),
        _ScoreRequestSource(()),
    ).run_cycle()

    assert (prediction.requested_targets, prediction.processed_targets) == (0, 0)
    assert prediction.first_target is prediction.last_target is None
    assert (score.requested_targets, score.processed_targets) == (0, 0)
    assert score.first_target is score.last_target is None


def test_checkpoint_progress_is_generic_deterministic_and_immutable() -> None:
    progress = project_checkpoint_progress(
        eligible_scored_count=6,
        configured_checkpoints=(2, 5, 10, 20),
    )

    assert progress == CheckpointProgress(
        eligible_scored_count=6,
        configured_checkpoints=(2, 5, 10, 20),
        reached_checkpoints=(2, 5),
        next_checkpoint=10,
        remaining_to_next_checkpoint=4,
        remaining_checkpoints=(10, 20),
    )
    assert progress.reached == (2, 5)
    assert progress.remaining == 4
    with pytest.raises(FrozenInstanceError):
        progress.next_checkpoint = 20  # type: ignore[misc]

    complete = project_checkpoint_progress(
        eligible_scored_count=20,
        configured_checkpoints=(2, 5, 10, 20),
    )
    assert complete.reached_checkpoints == (2, 5, 10, 20)
    assert complete.next_checkpoint is None
    assert complete.remaining_to_next_checkpoint is None
    assert complete.remaining_checkpoints == ()


@pytest.mark.parametrize(
    ("eligible_scored_count", "configured_checkpoints"),
    (
        (-1, (1,)),
        (True, (1,)),
        (0, ()),
        (0, (0, 1)),
        (0, (2, 2)),
        (0, (3, 2)),
        (0, (1, True)),
    ),
)
def test_checkpoint_progress_rejects_invalid_generic_inputs(
    eligible_scored_count: int,
    configured_checkpoints: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError):
        project_checkpoint_progress(
            eligible_scored_count=eligible_scored_count,
            configured_checkpoints=configured_checkpoints,
        )
