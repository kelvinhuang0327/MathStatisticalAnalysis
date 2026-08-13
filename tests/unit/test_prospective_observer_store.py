"""Focused persistence contracts for the prospective-observation filesystem store."""

from __future__ import annotations

import json
import multiprocessing
import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import PrizeEvaluationResult
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    DiagnosticEvent,
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
    ProspectiveSelection,
    ScoreAvailability,
    ScoreEntry,
    ScoreRecord,
    TemporalProvenance,
)
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
    ProspectiveObservationStoreCorruptionError,
)

_FROZEN_AT = datetime(2026, 1, 1, tzinfo=UTC)
_PREDICTED_AT = datetime(2026, 1, 2, 1, 2, 3, 456789, tzinfo=UTC)
_SCORED_AT = datetime(2026, 1, 2, 2, 3, 4, 567890, tzinfo=UTC)


def _fingerprint() -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id="fixture-producer",
        producer_version="v1",
        dependencies=(
            ProducerDependency("src/a.py", "1" * 64, "prediction behavior"),
            ProducerDependency("src/z.py", "2" * 64, "orchestration"),
        ),
    )


def _cohort(
    *,
    cohort_id: str = "bounded-fixture",
    cohort_version: str = "v1",
) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=LotteryType.BIG_LOTTO,
        cohort_id=cohort_id,
        cohort_version=cohort_version,
        authority_sha256="3" * 64,
        frozen_at=_FROZEN_AT,
        member_ids=("candidate-1",),
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _prediction(
    *,
    draw_number: str = "100",
    draw_date: date = date(2026, 1, 2),
    numbers: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
    cohort: FrozenCohortRef | None = None,
    predicted_at: datetime = _PREDICTED_AT,
) -> PredictionRecord:
    frozen_cohort = cohort or _cohort()
    context = PredictionContext(
        target=ObservationTarget(LotteryType.BIG_LOTTO, draw_number, draw_date),
        cohort=frozen_cohort,
        producer_fingerprint=_fingerprint(),
        causal_history=CausalHistoryRef(1, "99", date(2025, 12, 31), "4" * 64),
    )
    baseline = MatchedBaselineRef(
        lottery_type=LotteryType.BIG_LOTTO,
        baseline_id="size-matched-random",
        baseline_version="v1",
        authority_sha256="5" * 64,
        ticket_count=1,
        candidate_sizes=(len(numbers),),
    )
    return PredictionRecord.create(
        request=PredictionPhaseRequest(context, OutcomePresenceAtPrediction.ABSENT),
        draft=PredictionDraft(
            (
                PredictionEntryDraft.available(
                    member_id="candidate-1",
                    selections=(ProspectiveSelection(numbers),),
                    matched_baseline=baseline,
                ),
            )
        ),
        predicted_at=predicted_at,
    )


def _score(
    prediction: PredictionRecord,
    *,
    scored_at: datetime = _SCORED_AT,
) -> ScoreRecord:
    outcome = OfficialOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=prediction.identity.target_draw_number,
        draw_date=prediction.identity.target_draw_date,
        main_numbers=(1, 2, 3, 4, 5, 7),
        special_number=6,
        source_id="bounded-official-fixture",
        source_sha256="6" * 64,
    )
    prediction_entry = prediction.entries[0]
    evaluation = GameEvaluation(
        LotteryType.BIG_LOTTO,
        (
            PrizeEvaluationResult(
                lottery_type=LotteryType.BIG_LOTTO,
                is_winner=True,
                prize_tier="SECOND",
                prize_tier_order=None,
                zone1_hits=5,
                zone2_hit=True,
                prize_rule_version="fixture-v1",
                prize_rule_provenance="bounded fixture",
            ),
        ),
        (DiagnosticEvent("B649_ANY_SPECIAL_HIT", True),),
    )
    return ScoreRecord.create(
        prediction=prediction,
        outcome=outcome,
        entries=(
            ScoreEntry(
                member_id=prediction_entry.member_id,
                prediction_hash=prediction_entry.prediction_hash,
                availability=ScoreAvailability.SCORED,
                evaluation=evaluation,
            ),
        ),
        scored_at=scored_at,
    )


def _record_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.json")))


def _prediction_file(root: Path, draw_number: str = "100") -> Path:
    for path in _record_files(root):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload["record_type"] == "prediction"
            and payload["record"]["identity"]["target_draw_number"] == draw_number
        ):
            return path
    raise AssertionError("prediction file was not found")


def _canonical_json(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _create_prediction_in_process(root: str, record: PredictionRecord) -> str:
    store = FileSystemProspectiveObservationStore(root)
    return store.create_prediction(record).value


def test_prediction_and_score_round_trip_across_restart_with_timestamps(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    prediction = _prediction()
    score = _score(prediction)

    first = FileSystemProspectiveObservationStore(root)
    assert first.get_prediction(prediction.identity) is None
    assert first.get_score(prediction.identity) is None
    assert first.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    assert first.create_score(score) is CreateOnceOutcome.INSERTED

    restarted = FileSystemProspectiveObservationStore(root)
    assert restarted.get_prediction(prediction.identity) == prediction
    assert restarted.get_prediction(prediction.identity).predicted_at == _PREDICTED_AT  # type: ignore[union-attr]
    assert restarted.get_score(prediction.identity) == score
    assert restarted.get_score(prediction.identity).scored_at == _SCORED_AT  # type: ignore[union-attr]

    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in _record_files(root)]
    assert {payload["schema_version"] for payload in payloads} == {
        "LOTTOLAB_PROSPECTIVE_OBSERVATION_STORE_V1"
    }
    assert all(path.read_bytes() == _canonical_json(payload) for path, payload in zip(
        _record_files(root), payloads, strict=True
    ))


def test_equal_canonical_retry_ignores_timestamp_but_preserves_first_record(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    first_prediction = _prediction()
    later_prediction = replace(
        first_prediction,
        predicted_at=datetime(2026, 1, 2, 8, tzinfo=UTC),
    )
    first_score = _score(first_prediction)
    later_score = replace(first_score, scored_at=datetime(2026, 1, 2, 9, tzinfo=UTC))
    store = FileSystemProspectiveObservationStore(root)

    assert store.create_prediction(first_prediction) is CreateOnceOutcome.INSERTED
    assert store.create_prediction(later_prediction) is CreateOnceOutcome.ALREADY_PRESENT
    assert store.get_prediction(first_prediction.identity) == first_prediction
    assert store.create_score(first_score) is CreateOnceOutcome.INSERTED
    assert store.create_score(later_score) is CreateOnceOutcome.ALREADY_PRESENT
    assert store.get_score(first_prediction.identity) == first_score


def test_different_canonical_material_conflicts_without_changing_files(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    first = _prediction()
    different = _prediction(numbers=(7, 8, 9, 10, 11, 12))
    store = FileSystemProspectiveObservationStore(root)

    assert store.create_prediction(first) is CreateOnceOutcome.INSERTED
    path = _prediction_file(root)
    before = path.read_bytes()

    assert store.create_prediction(different) is CreateOnceOutcome.CONFLICT
    assert path.read_bytes() == before
    assert store.get_prediction(first.identity) == first


def test_identity_segments_are_derived_and_cannot_traverse_the_root(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    prediction = _prediction(cohort=_cohort(
        cohort_id="../../escaped/cohort",
        cohort_version="v1/../../../outside\\segment",
    ))
    store = FileSystemProspectiveObservationStore(root)

    assert store.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    assert store.get_prediction(prediction.identity) == prediction
    paths = _record_files(root)
    assert len(paths) == 1
    assert not (tmp_path / "escaped").exists()
    assert "escaped" not in paths[0].relative_to(root).parts
    assert all(
        re.fullmatch(r"[.a-z0-9_-]+", part)
        for part in paths[0].relative_to(root).parts
    )


def test_identities_are_isolated_and_path_identity_mismatch_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    first = _prediction(draw_number="100", draw_date=date(2026, 1, 2))
    second = _prediction(draw_number="101", draw_date=date(2026, 1, 3))
    store = FileSystemProspectiveObservationStore(root)
    assert store.create_prediction(first) is CreateOnceOutcome.INSERTED
    assert store.create_prediction(second) is CreateOnceOutcome.INSERTED
    first_path = _prediction_file(root, "100")
    second_path = _prediction_file(root, "101")

    second_path.write_bytes(first_path.read_bytes())

    assert store.get_prediction(first.identity) == first
    with pytest.raises(ProspectiveObservationStoreCorruptionError, match="storage key"):
        store.get_prediction(second.identity)


@pytest.mark.parametrize(
    "damage",
    ["malformed", "missing", "unknown", "version", "hash", "timestamp"],
)
def test_malformed_or_schema_invalid_prediction_fails_closed(
    tmp_path: Path,
    damage: str,
) -> None:
    root = tmp_path / damage
    prediction = _prediction()
    store = FileSystemProspectiveObservationStore(root)
    assert store.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    path = _prediction_file(root)

    if damage == "malformed":
        path.write_bytes(b'{"schema_version":')
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if damage == "missing":
            del payload["record_type"]
        elif damage == "unknown":
            payload["unexpected"] = True
        elif damage == "version":
            payload["schema_version"] = "UNKNOWN"
        elif damage == "hash":
            payload["record"]["prediction_hash"] = "0" * 64
        else:
            payload["record"]["predicted_at"] = "2026-01-02T09:00:00Z"
        path.write_bytes(_canonical_json(payload))
    before = path.read_bytes()

    with pytest.raises(ProspectiveObservationStoreCorruptionError):
        store.get_prediction(prediction.identity)
    with pytest.raises(ProspectiveObservationStoreCorruptionError):
        store.create_prediction(prediction)
    assert path.read_bytes() == before


def test_score_requires_the_matching_immutable_prediction(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    stored_prediction = _prediction()
    different_prediction = _prediction(numbers=(7, 8, 9, 10, 11, 12))
    store = FileSystemProspectiveObservationStore(root)

    with pytest.raises(ProspectiveObservationStoreCorruptionError, match="prediction"):
        store.create_score(_score(stored_prediction))
    assert _record_files(root) == ()

    assert store.create_prediction(stored_prediction) is CreateOnceOutcome.INSERTED
    with pytest.raises(ProspectiveObservationStoreCorruptionError, match="link"):
        store.create_score(_score(different_prediction))
    assert len(_record_files(root)) == 1


def test_orphaned_score_fails_closed_on_read(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    prediction = _prediction()
    score = _score(prediction)
    store = FileSystemProspectiveObservationStore(root)
    assert store.create_prediction(prediction) is CreateOnceOutcome.INSERTED
    assert store.create_score(score) is CreateOnceOutcome.INSERTED
    _prediction_file(root).unlink()

    with pytest.raises(ProspectiveObservationStoreCorruptionError, match="prediction"):
        store.get_score(prediction.identity)


def test_equal_concurrent_process_creates_have_one_insert(tmp_path: Path) -> None:
    root = tmp_path / "observer-store"
    prediction = _prediction()
    records = [
        replace(prediction, predicted_at=datetime(2026, 1, 2, hour, tzinfo=UTC))
        for hour in range(1, 9)
    ]

    with ProcessPoolExecutor(
        max_workers=8,
        mp_context=multiprocessing.get_context("fork"),
    ) as executor:
        outcomes = tuple(executor.map(
            _create_prediction_in_process,
            [str(root)] * len(records),
            records,
        ))

    assert outcomes.count(CreateOnceOutcome.INSERTED.value) == 1
    assert outcomes.count(CreateOnceOutcome.ALREADY_PRESENT.value) == len(records) - 1
    persisted = FileSystemProspectiveObservationStore(root).get_prediction(prediction.identity)
    assert persisted is not None
    assert persisted.canonical_material() == prediction.canonical_material()


def test_conflicting_concurrent_process_creates_preserve_one_canonical_value(
    tmp_path: Path,
) -> None:
    root = tmp_path / "observer-store"
    first = _prediction(numbers=(1, 2, 3, 4, 5, 6))
    second = _prediction(numbers=(7, 8, 9, 10, 11, 12))
    records = [first, second] * 4

    with ProcessPoolExecutor(
        max_workers=8,
        mp_context=multiprocessing.get_context("fork"),
    ) as executor:
        outcomes = tuple(executor.map(
            _create_prediction_in_process,
            [str(root)] * len(records),
            records,
        ))

    assert outcomes.count(CreateOnceOutcome.INSERTED.value) == 1
    persisted = FileSystemProspectiveObservationStore(root).get_prediction(first.identity)
    assert persisted is not None
    for record, outcome in zip(records, outcomes, strict=True):
        if record.canonical_material() == persisted.canonical_material():
            assert outcome in {
                CreateOnceOutcome.INSERTED.value,
                CreateOnceOutcome.ALREADY_PRESENT.value,
            }
        else:
            assert outcome == CreateOnceOutcome.CONFLICT.value
