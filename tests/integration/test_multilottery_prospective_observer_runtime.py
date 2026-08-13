"""Durable restart acceptance for the multi-lottery prospective runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lottolab.application.prospective_observer import (
    PredictionPhaseService,
    PredictionRequiredError,
    ScorePhaseRequest,
    ScoringPhaseService,
    repository_game_contracts,
)
from lottolab.application.prospective_observer_runtime import (
    ProspectivePredictionRunner,
    ProspectiveScoreRunner,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
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
    ScoreRecord,
    TemporalProvenance,
)
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
)

_FROZEN_AT = datetime(2026, 1, 1, tzinfo=UTC)
_TARGET_DATE = date(2026, 1, 2)
_PREDICTION_TIMES = tuple(
    datetime(2026, 1, 2, hour, tzinfo=UTC) for hour in range(8, 12)
)
_SCORE_TIMES = tuple(datetime(2026, 1, 3, hour, tzinfo=UTC) for hour in range(8, 12))


@dataclass(frozen=True, slots=True)
class _GameCase:
    lottery_type: LotteryType
    predicted_main: tuple[int, ...]
    predicted_special: int | None
    winning_main: tuple[int, ...]
    winning_special: int | None
    expected_hits: int
    expected_zone2_hit: bool
    expected_tier: str


_GAME_CASES = (
    _GameCase(
        LotteryType.BIG_LOTTO,
        (1, 2, 3, 4, 5, 6),
        None,
        (1, 2, 3, 4, 5, 7),
        6,
        5,
        True,
        "SECOND",
    ),
    _GameCase(
        LotteryType.DAILY_539,
        (1, 2, 3, 4, 5),
        None,
        (1, 2, 3, 6, 7),
        None,
        3,
        False,
        "THIRD",
    ),
    _GameCase(
        LotteryType.POWER_LOTTO,
        (1, 2, 3, 4, 5, 6),
        2,
        (1, 2, 3, 4, 5, 6),
        2,
        6,
        True,
        "FIRST",
    ),
)
_CASE_BY_LOTTERY = {case.lottery_type: case for case in _GAME_CASES}


class _SimulatedInterruption(RuntimeError):
    pass


class _NativeProducer:
    def __init__(self, *, interrupt_after: int | None = None) -> None:
        self._interrupt_after = interrupt_after
        self.calls = 0

    def predict(self, context: PredictionContext) -> PredictionDraft:
        if self._interrupt_after is not None and self.calls == self._interrupt_after:
            raise _SimulatedInterruption("simulated process interruption")
        self.calls += 1
        game = _CASE_BY_LOTTERY[context.target.lottery_type]
        baseline = MatchedBaselineRef(
            lottery_type=game.lottery_type,
            baseline_id=f"{game.lottery_type.value.lower()}-matched-random",
            baseline_version="v1",
            authority_sha256="3" * 64,
            ticket_count=1,
            candidate_sizes=(len(game.predicted_main),),
        )
        return PredictionDraft(
            (
                PredictionEntryDraft.available(
                    member_id="fixture-member",
                    selections=(
                        ProspectiveSelection(game.predicted_main, game.predicted_special),
                    ),
                    matched_baseline=baseline,
                ),
            )
        )


@dataclass
class _SequenceClock:
    values: tuple[datetime, ...]
    index: int = 0

    def __call__(self) -> datetime:
        if self.index == len(self.values):
            raise AssertionError("clock was called more often than expected")
        value = self.values[self.index]
        self.index += 1
        return value


def _never_clock() -> datetime:
    raise AssertionError("an exact no-op must preserve the persisted timestamp")


def _fingerprint() -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id="multi-lottery-runtime-fixture",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator="src/fixture/native_producer.py",
                source_sha256="1" * 64,
                load_bearing_role="deterministic game-native prediction behavior",
            ),
        ),
    )


def _prediction_request(
    lottery_type: LotteryType,
    cohort_id: str,
    fingerprint: ProducerFingerprint,
) -> PredictionPhaseRequest:
    return PredictionPhaseRequest(
        context=PredictionContext(
            target=ObservationTarget(lottery_type, "100", _TARGET_DATE),
            cohort=FrozenCohortRef(
                lottery_type=lottery_type,
                cohort_id=cohort_id,
                cohort_version="v1",
                authority_sha256="2" * 64,
                frozen_at=_FROZEN_AT,
                member_ids=("fixture-member",),
                checkpoint_sizes=(1, 2),
                checkpoint_provenance=(
                    TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,
                ),
            ),
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


def _identity(request: PredictionPhaseRequest) -> ProspectiveObservationIdentity:
    return ProspectiveObservationIdentity.from_context(request.context)


def _official_outcome(identity: ProspectiveObservationIdentity) -> OfficialOutcome:
    game = _CASE_BY_LOTTERY[identity.lottery_type]
    return OfficialOutcome.create(
        lottery_type=identity.lottery_type,
        draw_number=identity.target_draw_number,
        draw_date=identity.target_draw_date,
        main_numbers=game.winning_main,
        special_number=game.winning_special,
        source_id="official-multi-lottery-runtime-fixture",
        source_sha256="5" * 64,
    )


def _prediction_runner(
    store: FileSystemProspectiveObservationStore,
    requests: tuple[PredictionPhaseRequest, ...],
    producer: _NativeProducer,
    clock: Callable[[], datetime],
) -> ProspectivePredictionRunner:
    return ProspectivePredictionRunner(
        service=PredictionPhaseService(
            store=store,
            producer=producer,
            game_contracts=repository_game_contracts(),
            clock=clock,
        ),
        request_source=lambda: requests,
    )


def _score_requests(
    requests: tuple[PredictionPhaseRequest, ...],
    *,
    outcomes_available: bool,
) -> tuple[ScorePhaseRequest, ...]:
    return tuple(
        ScorePhaseRequest(
            identity=_identity(request),
            producer_fingerprint=request.context.producer_fingerprint,
            outcome=(
                _official_outcome(_identity(request)) if outcomes_available else None
            ),
        )
        for request in requests
    )


def _score_runner(
    store: FileSystemProspectiveObservationStore,
    requests: tuple[ScorePhaseRequest, ...],
    clock: Callable[[], datetime],
) -> ProspectiveScoreRunner:
    return ProspectiveScoreRunner(
        service=ScoringPhaseService(
            store=store,
            game_contracts=repository_game_contracts(),
            clock=clock,
        ),
        request_source=lambda: requests,
    )


def _predictions(
    store: FileSystemProspectiveObservationStore,
    identities: tuple[ProspectiveObservationIdentity, ...],
) -> dict[ProspectiveObservationIdentity, PredictionRecord]:
    records: dict[ProspectiveObservationIdentity, PredictionRecord] = {}
    for identity in identities:
        record = store.get_prediction(identity)
        assert record is not None
        records[identity] = record
    return records


def _scores(
    store: FileSystemProspectiveObservationStore,
    identities: tuple[ProspectiveObservationIdentity, ...],
) -> dict[ProspectiveObservationIdentity, ScoreRecord]:
    records: dict[ProspectiveObservationIdentity, ScoreRecord] = {}
    for identity in identities:
        record = store.get_score(identity)
        assert record is not None
        records[identity] = record
    return records


def _durable_bytes(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*.json"))
    }


def test_multilottery_runtime_resumes_and_restarts_as_exact_no_op(
    tmp_path: Path,
) -> None:
    root = tmp_path / "prospective-observer"
    assert root.resolve().is_relative_to(tmp_path.resolve())
    fingerprint = _fingerprint()
    requests = (
        _prediction_request(LotteryType.POWER_LOTTO, "shared-cohort", fingerprint),
        _prediction_request(LotteryType.BIG_LOTTO, "alternate-cohort", fingerprint),
        _prediction_request(LotteryType.DAILY_539, "shared-cohort", fingerprint),
        _prediction_request(LotteryType.BIG_LOTTO, "shared-cohort", fingerprint),
    )
    identities = tuple(_identity(request) for request in requests)
    assert len(set(identities)) == len(requests)
    assert {
        identity.lottery_type
        for identity in identities
        if identity.cohort_id == "shared-cohort"
    } == {LotteryType.BIG_LOTTO, LotteryType.DAILY_539, LotteryType.POWER_LOTTO}
    assert {
        identity.cohort_id
        for identity in identities
        if identity.lottery_type is LotteryType.BIG_LOTTO
    } == {"alternate-cohort", "shared-cohort"}

    store_a = FileSystemProspectiveObservationStore(root)
    interrupted = _prediction_runner(
        store_a,
        requests,
        _NativeProducer(interrupt_after=2),
        _SequenceClock(_PREDICTION_TIMES[:2]),
    )
    with pytest.raises(_SimulatedInterruption, match="simulated process interruption"):
        interrupted.run_cycle()

    partial = {
        identity: record
        for identity in identities
        if (record := store_a.get_prediction(identity)) is not None
    }
    assert len(partial) == 2
    assert len(tuple(root.rglob("*.json"))) == 2
    missing_identity = next(identity for identity in identities if identity not in partial)
    with pytest.raises(PredictionRequiredError, match="requires an immutable prediction"):
        _score_runner(
            store_a,
            (
                ScorePhaseRequest(
                    missing_identity,
                    fingerprint,
                    _official_outcome(missing_identity),
                ),
            ),
            _never_clock,
        ).run_cycle()

    store_b = FileSystemProspectiveObservationStore(root)
    resumed = _prediction_runner(
        store_b,
        requests,
        _NativeProducer(),
        _SequenceClock(_PREDICTION_TIMES[2:]),
    ).run_cycle()
    assert (resumed.prediction_created, resumed.prediction_exact_no_op) == (2, 2)
    assert resumed.prediction_unavailable == 0
    predictions = _predictions(store_b, identities)
    assert all(predictions[identity] == record for identity, record in partial.items())
    assert {record.predicted_at for record in predictions.values()} == set(_PREDICTION_TIMES)
    prediction_paths = tuple(sorted(root.rglob("*.json")))
    assert len(prediction_paths) == len(identities)
    assert all(path.resolve().is_relative_to(root.resolve()) for path in prediction_paths)

    store_c = FileSystemProspectiveObservationStore(root)
    unavailable = _score_runner(
        store_c,
        _score_requests(requests, outcomes_available=False),
        _never_clock,
    ).run_cycle()
    assert (unavailable.score_created, unavailable.score_exact_no_op) == (0, 0)
    assert unavailable.score_outcome_unavailable == len(requests)
    assert all(store_c.get_score(identity) is None for identity in identities)

    scored = _score_runner(
        store_c,
        _score_requests(requests, outcomes_available=True),
        _SequenceClock(_SCORE_TIMES),
    ).run_cycle()
    assert (scored.score_created, scored.score_exact_no_op) == (len(requests), 0)
    assert scored.score_outcome_unavailable == 0
    scores = _scores(store_c, identities)
    assert {record.scored_at for record in scores.values()} == set(_SCORE_TIMES)
    for identity, score in scores.items():
        game = _CASE_BY_LOTTERY[identity.lottery_type]
        prediction = predictions[identity]
        selection = prediction.entries[0].selections[0]
        result = score.entries[0].evaluation
        assert (selection.main_numbers, selection.special_number) == (
            game.predicted_main,
            game.predicted_special,
        )
        assert (score.outcome.main_numbers, score.outcome.special_number) == (
            game.winning_main,
            game.winning_special,
        )
        assert result is not None
        ticket = result.ticket_results[0]
        assert ticket.is_winner
        assert (ticket.zone1_hits, ticket.zone2_hit, ticket.prize_tier) == (
            game.expected_hits,
            game.expected_zone2_hit,
            game.expected_tier,
        )

    before_no_ops = _durable_bytes(root)
    assert len(before_no_ops) == len(identities) * 2
    store_d = FileSystemProspectiveObservationStore(root)
    for identity in identities:
        prediction = store_d.get_prediction(identity)
        score = store_d.get_score(identity)
        assert prediction == predictions[identity]
        assert score == scores[identity]
        assert prediction is not None
        assert score is not None
        assert (prediction.prediction_hash, prediction.predicted_at) == (
            predictions[identity].prediction_hash,
            predictions[identity].predicted_at,
        )
        assert (score.score_hash, score.scored_at) == (
            scores[identity].score_hash,
            scores[identity].scored_at,
        )

    prediction_no_op = _prediction_runner(
        store_d,
        requests,
        _NativeProducer(),
        _never_clock,
    ).run_cycle()
    score_no_op = _score_runner(
        store_d,
        _score_requests(requests, outcomes_available=True),
        _never_clock,
    ).run_cycle()
    assert (prediction_no_op.prediction_created, prediction_no_op.prediction_exact_no_op) == (
        0,
        len(requests),
    )
    assert (score_no_op.score_created, score_no_op.score_exact_no_op) == (0, len(requests))
    assert score_no_op.score_outcome_unavailable == 0
    assert _durable_bytes(root) == before_no_ops
