"""Exercise the guarded K3 entry point, including its fail-closed boundaries."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict, cast
from unittest.mock import Mock

import pytest

import lottolab.application.k3_predraw_guard as guard
from lottolab.application.k3_prospective_cohort import (
    MEMBERS,
    GuardedK3CohortProducer,
    capture_version_manifest,
    create_local_prediction,
    make_cohort,
)
from lottolab.application.prospective_observer import (
    GameContractError,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionRecord,
)
from lottolab.infrastructure import k3_sealed_scoring
from lottolab.infrastructure.k3_rfc3161 import TimestampProof
from lottolab.infrastructure.prospective_observer_store import FileSystemProspectiveObservationStore
from lottolab.strategies.adapters.base import CausalDrawRow

NOW = datetime(2028, 11, 15, 12, tzinfo=UTC)
TARGET = ObservationTarget(LotteryType.BIG_LOTTO, "117000061", date(2028, 11, 16))


class K3Request(TypedDict):
    policy: guard.K3Policy
    registration: PreOutcomeTargetRegistration
    history: tuple[guard.K3HistoryRow, ...]
    absence: OutcomePresenceAttestation
    clock: Callable[[], datetime]


class ScoreArguments(TypedDict):
    store: FileSystemProspectiveObservationStore
    prediction: PredictionRecord
    registration: PreOutcomeTargetRegistration
    outcome: OfficialOutcome
    proof: TimestampProof
    openssl: Path
    ca_file: Path
    scratch_root: Path
    clock: Callable[[], datetime]


def _score(
    arguments: ScoreArguments,
    *,
    clock: Callable[[], datetime] | None = None,
    outcome: OfficialOutcome | None = None,
) -> k3_sealed_scoring.ScoreSyncResult:
    return k3_sealed_scoring.score_timestamped_prediction(
        store=arguments["store"],
        prediction=arguments["prediction"],
        registration=arguments["registration"],
        outcome=arguments["outcome"] if outcome is None else outcome,
        proof=arguments["proof"],
        openssl=arguments["openssl"],
        ca_file=arguments["ca_file"],
        scratch_root=arguments["scratch_root"],
        clock=arguments["clock"] if clock is None else clock,
    )


def _generate(request: K3Request) -> guard.GuardedK3Result:
    return guard.generate_guarded_k3(
        policy=request["policy"],
        registration=request["registration"],
        history=request["history"],
        absence=request["absence"],
        clock=request["clock"],
    )


def _with_request(
    request: K3Request,
    *,
    policy: guard.K3Policy | None = None,
    registration: PreOutcomeTargetRegistration | None = None,
    history: tuple[guard.K3HistoryRow, ...] | None = None,
    absence: OutcomePresenceAttestation | None = None,
    clock: Callable[[], datetime] | None = None,
) -> K3Request:
    return {
        "policy": request["policy"] if policy is None else policy,
        "registration": request["registration"] if registration is None else registration,
        "history": request["history"] if history is None else history,
        "absence": request["absence"] if absence is None else absence,
        "clock": request["clock"] if clock is None else clock,
    }


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _source(observed_at: datetime) -> TargetSourceProvenance:
    return TargetSourceProvenance("test", "1", "fixture", "a" * 64, observed_at)


def _history() -> tuple[guard.K3HistoryRow, ...]:
    rng = random.Random(27)
    result: list[guard.K3HistoryRow] = []
    for index in range(60):
        drawn_at = datetime(2028, 9, 1, 12, tzinfo=UTC) + timedelta(days=index)
        numbers = tuple(sorted(rng.sample(range(1, 50), 6)))
        special = next(number for number in range(1, 50) if number not in numbers)
        result.append(
            guard.K3HistoryRow(
                draw_number=f"117{index + 1:06d}",
                draw_date=drawn_at.date(),
                main_numbers=numbers,
                special_number=special,
                drawn_at=drawn_at,
                available_at=drawn_at + timedelta(minutes=10),
            )
        )
    return tuple(result)


def _registration(
    history: tuple[guard.K3HistoryRow, ...],
) -> PreOutcomeTargetRegistration:
    # Independently build the canonical identity used by the existing
    # pre-outcome history authority, including the winning-number payload.
    material: list[dict[str, object]] = []
    for row in history:
        record = {
            "draw_date": row.draw_date.isoformat(),
            "draw_number": row.draw_number,
            "lottery_type": "BIG_LOTTO",
            "main_numbers": list(row.main_numbers),
            "special_numbers": [row.special_number],
        }
        material.append(
            {
                "draw_date": row.draw_date.isoformat(),
                "draw_number": row.draw_number,
                "normalized_record_hash": _digest(record),
            }
        )
    history_digest = _digest(
        {
            "draws": material,
            "lottery_type": "BIG_LOTTO",
            "schema_version": "LOTTOLAB_PRE_OUTCOME_CAUSAL_HISTORY_V1",
            "target": TARGET.canonical_dict(),
        }
    )
    source = _source(NOW - timedelta(seconds=20))
    announcement = TargetAnnouncement(
        TARGET, "Asia/Taipei", datetime(2028, 11, 16, 12, tzinfo=UTC), source
    )
    absence = OutcomePresenceAttestation(
        TARGET, OutcomePresenceAtPrediction.ABSENT, NOW - timedelta(seconds=10), source
    )
    ref = CausalHistoryRef(
        len(history), history[-1].draw_number, history[-1].draw_date, history_digest
    )
    return PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=absence,
        causal_history=ref,
        registered_at=NOW,
    )


def _absence(
    target: ObservationTarget = TARGET,
    *,
    when: datetime = NOW + timedelta(seconds=1),
    presence: OutcomePresenceAtPrediction = OutcomePresenceAtPrediction.ABSENT,
) -> OutcomePresenceAttestation:
    return OutcomePresenceAttestation(target, presence, when, _source(when))


@pytest.fixture
def valid_request() -> K3Request:
    history = _history()
    return {
        "policy": guard.K3Policy.OPTIMIZED_ENSEMBLE,
        "registration": _registration(history),
        "history": history,
        "absence": _absence(),
        "clock": lambda: NOW + timedelta(seconds=2),
    }


@pytest.mark.parametrize(
    ("policy", "native_count"),
    [
        (guard.K3Policy.OPTIMIZED_ENSEMBLE, 1),
        (guard.K3Policy.BACKTEST_STRATEGY_1, 2),
        (guard.K3Policy.EXHAUSTIVE, 3),
    ],
)
def test_guarded_three_portfolio_paths(
    valid_request: K3Request, policy: guard.K3Policy, native_count: int
) -> None:
    result = _generate(_with_request(valid_request, policy=policy))
    assert len(result.native_tickets) == native_count
    assert len(result.tickets) == 3
    assert result.tickets[:native_count] == result.native_tickets
    assert len({frozenset(ticket) for ticket in result.tickets}) == 3
    assert result.registration_digest == valid_request["registration"].registration_digest
    assert len(result.availability_sha256) == 64
    assert len(result.producer_source_sha256) == 64
    assert result.absence_attested_at == valid_request["absence"].attested_at


@pytest.mark.parametrize("case", ["target", "future", "unordered", "duplicate", "late_data"])
def test_rejects_leakage_before_producer_is_called(
    valid_request: K3Request, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    history = valid_request["history"]
    if case == "target":
        history = (*history[:-1], replace(history[-1], draw_number=TARGET.draw_number))
    elif case == "future":
        history = (*history[:-1], replace(history[-1], draw_number="117000062"))
    elif case == "unordered":
        history = (*history[:-2], history[-1], history[-2])
    elif case == "duplicate":
        history = (*history[:-1], history[-2])
    else:
        history = (*history[:-1], replace(history[-1], available_at=NOW + timedelta(seconds=1)))
    producer = Mock(side_effect=AssertionError("producer should not be called"))
    monkeypatch.setattr(guard, "generate_legacy_history_native_portfolio", producer)
    with pytest.raises(guard.K3PreDrawError):
        _generate(_with_request(valid_request, history=history))
    producer.assert_not_called()


def test_rejects_changed_history_payload_even_when_identity_unchanged(
    valid_request: K3Request,
) -> None:
    history = valid_request["history"]
    row = history[-1]
    replacement = next(
        number
        for number in range(1, 50)
        if number not in row.main_numbers and number != row.special_number
    )
    changed = tuple(sorted((*row.main_numbers[:-1], replacement)))
    with pytest.raises(guard.K3PreDrawError, match="registered authority"):
        _generate(
            _with_request(
                valid_request, history=(*history[:-1], replace(row, main_numbers=changed))
            )
        )


@pytest.mark.parametrize(
    "case", ["present", "wrong_target", "stale", "future_attestation", "naive_clock", "after_draw"]
)
def test_rejects_invalid_or_stale_authority(valid_request: K3Request, case: str) -> None:
    request: K3Request = {**valid_request}
    if case == "present":
        request["absence"] = _absence(presence=OutcomePresenceAtPrediction.PRESENT)
    elif case == "wrong_target":
        request["absence"] = _absence(
            ObservationTarget(LotteryType.BIG_LOTTO, "117000062", TARGET.draw_date)
        )
    elif case == "stale":
        request["clock"] = lambda: NOW + timedelta(minutes=6)
    elif case == "future_attestation":
        request["absence"] = _absence(when=NOW + timedelta(seconds=10))
    elif case == "naive_clock":
        request["clock"] = lambda: datetime(2028, 11, 15, 12)
    else:
        request["clock"] = lambda: datetime(2028, 11, 16, 12, tzinfo=UTC)
    with pytest.raises(guard.K3PreDrawError):
        _generate(request)


def test_production_crossing_draw_time_is_not_returned(valid_request: K3Request) -> None:
    moments = iter([NOW + timedelta(seconds=2), datetime(2028, 11, 16, 12, tzinfo=UTC)])
    with pytest.raises(guard.K3PreDrawError, match="passed the draw"):
        _generate(_with_request(valid_request, clock=lambda: next(moments)))


def test_production_outlasting_absence_attestation_is_not_returned(
    valid_request: K3Request,
) -> None:
    moments = iter([NOW + timedelta(seconds=2), NOW + timedelta(minutes=6)])
    with pytest.raises(guard.K3PreDrawError, match="absence became stale"):
        _generate(_with_request(valid_request, clock=lambda: next(moments)))


def test_clock_regression_during_production_is_not_returned(valid_request: K3Request) -> None:
    moments = iter([NOW + timedelta(seconds=3), NOW + timedelta(seconds=2)])
    with pytest.raises(guard.K3PreDrawError, match="clock"):
        _generate(_with_request(valid_request, clock=lambda: next(moments)))


def test_rejects_non_utc_and_impossible_publication_time(valid_request: K3Request) -> None:
    history = valid_request["history"]
    row = history[-1]
    for bad in (
        replace(row, drawn_at=row.drawn_at.replace(tzinfo=timezone(timedelta(hours=8)))),
        replace(row, available_at=row.drawn_at - timedelta(seconds=1)),
    ):
        with pytest.raises(guard.K3PreDrawError):
            _generate(_with_request(valid_request, history=(*history[:-1], bad)))


def test_duplicate_native_and_unsupported_policy_fail_closed(
    valid_request: K3Request, monkeypatch: pytest.MonkeyPatch
) -> None:
    generated = Mock(tickets=((1, 2, 3, 4, 5, 6), (6, 5, 4, 3, 2, 1)))
    monkeypatch.setattr(
        guard, "generate_legacy_history_native_portfolio", Mock(return_value=generated)
    )
    with pytest.raises(guard.K3PreDrawError, match="distinct"):
        _generate(valid_request)
    with pytest.raises(guard.K3PreDrawError, match="unsupported"):
        _generate(cast(K3Request, valid_request | {"policy": "ANALYZE"}))


def test_analyze_candidate_can_generate_for_an_unseen_target(
    valid_request: K3Request, monkeypatch: pytest.MonkeyPatch
) -> None:
    rng = random.Random(414)
    rows: list[guard.K3HistoryRow] = []
    for index in range(500):
        drawn = datetime(2026, 1, 1, 12, tzinfo=UTC) + timedelta(days=index)
        numbers = tuple(sorted(rng.sample(range(1, 50), 6)))
        special = next(number for number in range(1, 50) if number not in numbers)
        rows.append(
            guard.K3HistoryRow(f"116{index + 1:06d}", drawn.date(), numbers, special, drawn, drawn)
        )
    history = tuple(rows)
    request = _with_request(
        valid_request,
        policy=guard.K3Policy.ANALYZE_CANDIDATE,
        history=history,
        registration=_registration(history),
    )
    result = _generate(request)
    assert result.target_draw == TARGET.draw_number
    assert len(result.tickets) == len(set(result.tickets)) == 3
    assert result.producer_protocol == "legacy-analyze-14-prefix3-dedup-greedy-v2"
    assert result.producer_source_sha256 == guard.ANALYZE_DONOR_SHA256
    assert len(result.source_native_tickets) == 14
    assert result.source_native_tickets[2:5] == result.source_native_tickets[5:8]
    assert result.source_native_tickets[2:5] == result.source_native_tickets[9:12]
    assert result.source_native_tickets[8] == result.source_native_tickets[12]
    assert result.native_positions == (1, 2, 3)
    def duplicate_native_rows(_rows: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6),) * 14

    monkeypatch.setattr(guard, "analyze_native_14", duplicate_native_rows)
    deduped = _generate(request)
    assert deduped.native_positions == (1,)
    assert deduped.tickets == guard.GREEDY_K3
    assert deduped.supplement_indices == (1, 2)
    leaked = (*history[:-1], replace(history[-1], draw_number=TARGET.draw_number))
    with pytest.raises(guard.K3PreDrawError, match="strictly prior"):
        _generate(_with_request(request, history=leaked))


def test_analyze_candidate_rejects_short_history(valid_request: K3Request) -> None:
    with pytest.raises(guard.K3PreDrawError, match="500 historical draws"):
        _generate(_with_request(valid_request, policy=guard.K3Policy.ANALYZE_CANDIDATE))


@pytest.mark.parametrize("kind", ["same", "future", "unordered", "nonnumeric"])
@pytest.mark.parametrize(
    "policy",
    [
        guard.K3Policy.EXHAUSTIVE,
        guard.K3Policy.BACKTEST_STRATEGY_1,
        guard.K3Policy.OPTIMIZED_ENSEMBLE,
    ],
)
def test_low_level_ports_reject_invalid_numeric_history(
    valid_request: K3Request, policy: guard.K3Policy, kind: str
) -> None:
    rows = valid_request["history"]
    native = tuple(
        guard.LegacyHistoryDraw(row.draw_number, cast(Ticket, row.main_numbers)) for row in rows
    )
    if kind == "same":
        native = (*native[:-1], replace(native[-1], draw_number=TARGET.draw_number))
    elif kind == "future":
        native = (*native[:-1], replace(native[-1], draw_number="117000062"))
    elif kind == "unordered":
        native = (*native[:-2], native[-1], native[-2])
    else:
        native = (*native[:-1], replace(native[-1], draw_number="not-a-draw"))
    if policy is guard.K3Policy.BACKTEST_STRATEGY_1:
        request = guard.LegacySourceNativeWave21Request(
            guard.POST_SELECTION_FILTER_METHOD_ID, TARGET.draw_number, native
        )
        with pytest.raises(ValueError):
            guard.generate_legacy_source_native_wave21_portfolio(request)
    else:
        method = (
            guard.EXHAUSTIVE_AUDIT_METHOD_ID
            if policy is guard.K3Policy.EXHAUSTIVE
            else guard.OPTIMIZED_ENSEMBLE_METHOD_ID
        )
        with pytest.raises(ValueError):
            guard.generate_legacy_history_native_portfolio(
                guard.LegacyHistoryNativeRequest(method, TARGET.draw_number, native)
            )


def test_synthetic_five_policy_local_prediction_and_scoring(
    valid_request: K3Request, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rng = random.Random(414)
    rows: list[guard.K3HistoryRow] = []
    for index in range(500):
        drawn = datetime(2026, 1, 1, 12, tzinfo=UTC) + timedelta(days=index)
        numbers = tuple(sorted(rng.sample(range(1, 50), 6)))
        special = next(n for n in range(1, 50) if n not in numbers)
        rows.append(
            guard.K3HistoryRow(f"116{index + 1:06d}", drawn.date(), numbers, special, drawn, drawn)
        )
    history = tuple(rows)
    repo = Path(__file__).resolve().parents[2]
    manifest = capture_version_manifest(repo)
    producer = GuardedK3CohortProducer(
        repo,
        manifest,
        _registration(history),
        history,
        _absence(),
        lambda: NOW + timedelta(seconds=2),
    )
    cohort = make_cohort(manifest, frozen_at=NOW - timedelta(days=1))
    store = FileSystemProspectiveObservationStore(tmp_path / "synthetic")
    prediction = create_local_prediction(store=store, producer=producer, cohort=cohort).prediction
    assert tuple(entry.member_id for entry in prediction.entries) == MEMBERS
    assert all(len(entry.selections) == 3 for entry in prediction.entries)
    assert tuple(s.main_numbers for s in prediction.entries[-1].selections) == guard.GREEDY_K3
    outcome = OfficialOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=TARGET.draw_number,
        draw_date=TARGET.draw_date,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
        source_id="synthetic-test-only",
        source_sha256="a" * 64,
    )
    def timestamp_after_prediction(*args: object, **kwargs: object) -> datetime:
        return NOW + timedelta(seconds=3)

    monkeypatch.setattr(k3_sealed_scoring, "verify_timestamp", timestamp_after_prediction)
    proof = TimestampProof(b"synthetic-query", b"synthetic-response", NOW + timedelta(seconds=3))
    arguments: ScoreArguments = {
        "store": store,
        "prediction": prediction,
        "registration": producer.registration,
        "outcome": outcome,
        "proof": proof,
        "openssl": Path("/synthetic/openssl"),
        "ca_file": Path("/synthetic/root"),
        "scratch_root": tmp_path,
        "clock": lambda: datetime(2028, 11, 17, tzinfo=UTC),
    }
    scored = _score(arguments)
    assert scored.score is not None
    assert len(scored.score.entries) == 5
    assert scored.score.prediction_hash == prediction.prediction_hash
    with pytest.raises(ValueError, match="required side"):
        _score(arguments, clock=lambda: NOW)

    def timestamp_at_draw(*args: object, **kwargs: object) -> datetime:
        return producer.registration.announcement.scheduled_at

    monkeypatch.setattr(k3_sealed_scoring, "verify_timestamp", timestamp_at_draw)
    with pytest.raises(ValueError, match="required side"):
        _score(arguments)
    monkeypatch.setattr(k3_sealed_scoring, "verify_timestamp", timestamp_after_prediction)
    wrong = OfficialOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="117000062",
        draw_date=TARGET.draw_date,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
        source_id="synthetic",
        source_sha256="a" * 64,
    )
    with pytest.raises(GameContractError):
        _score(arguments, outcome=wrong)


def test_frozen_manifest_drift_rejected_before_prediction(
    valid_request: K3Request, tmp_path: Path
) -> None:
    repo = Path(__file__).resolve().parents[2]
    manifest = capture_version_manifest(repo)
    manifest["policy"] = "tampered"
    producer = GuardedK3CohortProducer(
        repo,
        manifest,
        valid_request["registration"],
        valid_request["history"],
        valid_request["absence"],
        valid_request["clock"],
    )
    cohort = make_cohort(manifest, frozen_at=NOW - timedelta(days=1))
    store = FileSystemProspectiveObservationStore(tmp_path / "synthetic")
    with pytest.raises(ValueError, match="drifted"):
        create_local_prediction(store=store, producer=producer, cohort=cohort)
