"""Contract tests for the bounded, incremental B649 M0/M2 K5 adapter."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_k5_incremental_evaluation as incremental
from lottolab.research.b649_k235_shared_evaluation import (
    causal_history,
    generator,
    native_adapters,
)

FIXED_NOW = datetime(2026, 10, 20, 5, 0, tzinfo=UTC)
WINNING_TICKETS = [
    [1, 2, 3, 4, 5, 6],
    [8, 9, 10, 11, 12, 13],
    [14, 15, 16, 17, 18, 19],
    [20, 21, 22, 23, 24, 25],
    [26, 27, 28, 29, 30, 31],
]
LOSING_TICKETS = [
    [8, 9, 10, 11, 12, 13],
    [14, 15, 16, 17, 18, 19],
    [20, 21, 22, 23, 24, 25],
    [26, 27, 28, 29, 30, 31],
    [32, 33, 34, 35, 36, 37],
]
OVERLAPPING_TICKETS = [
    [1, 2, 3, 4, 5, 6],
    [1, 8, 9, 10, 11, 12],
    [14, 15, 16, 17, 18, 19],
    [20, 21, 22, 23, 24, 25],
    [26, 27, 28, 29, 30, 31],
]
WINNING_RESULT = {
    "draw": "115000097",
    "date": "2026-10-16",
    "numbers": [1, 2, 3, 4, 5, 6],
    "special": 7,
    "result_version": "synthetic-v1",
}


def _clock() -> datetime:
    return FIXED_NOW


def _synthetic_snapshot(
    target_draw: str = "115000097",
    target_date: str = "2026-10-16",
    history_n: int = 12,
) -> list[dict[str, Any]]:
    target = int(target_draw)
    last_day = date.fromisoformat(target_date)
    rows: list[dict[str, Any]] = []
    for index in range(history_n):
        draw_number = target - history_n + index
        drawn = sorted(((draw_number + offset) % 49) + 1 for offset in range(6))
        rows.append(
            {
                "draw": str(draw_number),
                "date": (last_day - timedelta(days=history_n - index)).isoformat(),
                "numbers": drawn,
                "special": (draw_number % 49) + 1,
                "source_revision": f"history-{draw_number}",
            }
        )
    rows.extend(
        [
            {
                "draw": target_draw,
                "date": target_date,
                "numbers": [1, 2, 3, 4, 5, 6],
                "special": 7,
                "source_revision": "target-v1",
            },
            {
                "draw": str(target + 1),
                "date": (last_day + timedelta(days=3)).isoformat(),
                "numbers": [7, 8, 9, 10, 11, 12],
                "special": 13,
                "source_revision": "future-v1",
            },
        ]
    )
    return rows


def _generator_for(
    m0: Any = WINNING_TICKETS, m2: Any = WINNING_TICKETS
) -> Callable[[str, int, tuple[Any, ...]], Any]:
    def run(model: str, _k: int, _history: tuple[Any, ...]) -> Any:
        value = m0 if model == "M0" else m2
        if isinstance(value, BaseException):
            raise value
        return value

    return run


def _predict(
    output_root: Path,
    *,
    target_draw: str = "115000097",
    target_date: str = "2026-10-16",
    snapshot: list[dict[str, Any]] | None = None,
    record_class: str = "SYNTHETIC_TEST",
    generate: Any = None,
) -> dict[str, Any]:
    return incremental.predict_compare(
        snapshot or _synthetic_snapshot(target_draw, target_date),
        target_draw=target_draw,
        target_date=target_date,
        output_root=output_root,
        record_class=record_class,
        generator_fn=generate or _generator_for(),
        clock=_clock,
    )


def _result_for(target_draw: str, target_date: str) -> dict[str, Any]:
    return {**WINNING_RESULT, "draw": target_draw, "date": target_date}


def test_fixed_method_identity_and_quality_are_recorded(tmp_path: Path) -> None:
    package = _predict(tmp_path)
    assert package["classification"] == "SYNTHETIC_TEST"
    assert package["game"] == "B649"
    assert package["request_identity"]["source_identity"]["commit"] == (
        incremental.FIXED_SOURCE_COMMIT
    )
    assert package["methods"]["M0"]["method_identity"]["strategy_id"] == (
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e"
    )
    assert package["methods"]["M2"]["method_identity"]["fixed_config"]["half_life_draws"] == 50
    for method in package["methods"].values():
        quality = method["ticket_quality"]
        assert method["generation_status"] == "OK"
        assert len(method["generated_tickets"]) == 5
        assert all(len(ticket) == 6 for ticket in method["generated_tickets"])
        assert quality["is_valid"] is True
        assert quality["unique_number_count"] == 30
        assert quality["expected_unique_count"] == 30


def test_target_and_future_outcomes_cannot_change_actual_generated_tickets() -> None:
    snapshot = _synthetic_snapshot(history_n=2178)
    target_draw, target_date = "115000097", "2026-10-16"
    first_history = incremental.prepare_strict_history(snapshot, target_draw, target_date)
    first_rows = causal_history(first_history, {"draw": target_draw, "date": target_date})
    source_generator = generator(native_adapters())
    before = {model: source_generator(model, 5, first_rows) for model in ("M0", "M2")}

    altered = copy.deepcopy(snapshot)
    altered[-2]["numbers"] = [44, 45, 46, 47, 48, 49]
    altered[-2]["special"] = 43
    altered[-1]["numbers"] = [13, 14, 15, 16, 17, 18]
    altered[-1]["special"] = 19
    second_history = incremental.prepare_strict_history(altered, target_draw, target_date)
    second_rows = causal_history(second_history, {"draw": target_draw, "date": target_date})
    after = {model: source_generator(model, 5, second_rows) for model in ("M0", "M2")}

    assert len(first_history) == len(second_history) == 2178
    assert first_history == second_history
    assert before == after


def test_predict_is_idempotent_and_conflicting_input_is_rejected(tmp_path: Path) -> None:
    snapshot = _synthetic_snapshot()
    calls: list[str] = []

    def generate_for_count(model: str, k: int, history: tuple[Any, ...]) -> Any:
        calls.append(model)
        return _generator_for()(model, k, history)

    first = incremental.predict_compare(
        snapshot,
        target_draw="115000097",
        target_date="2026-10-16",
        output_root=tmp_path,
        record_class="SYNTHETIC_TEST",
        generator_fn=generate_for_count,
        clock=_clock,
    )
    prediction_file = incremental.prediction_path(tmp_path, "SYNTHETIC_TEST", "115000097")
    original_bytes = prediction_file.read_bytes()
    def forbidden_generation(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("regenerated")

    second = _predict(tmp_path, snapshot=snapshot, generate=forbidden_generation)
    assert calls == ["M0", "M2"]
    assert prediction_file.read_bytes() == original_bytes
    assert second == first

    changed = copy.deepcopy(snapshot)
    changed[0]["numbers"] = [7, 8, 9, 10, 11, 12]
    with pytest.raises(incremental.RecordConflictError):
        _predict(tmp_path, snapshot=changed)
    with pytest.raises(incremental.RecordConflictError):
        _predict(tmp_path, snapshot=snapshot, target_date="2026-10-17")
    assert prediction_file.read_bytes() == original_bytes


def test_failed_or_invalid_method_attempts_are_preserved(tmp_path: Path) -> None:
    package = _predict(
        tmp_path,
        generate=_generator_for(RuntimeError("M0 fixture failure"), WINNING_TICKETS),
    )
    assert package["methods"]["M0"]["generation_status"] == "TECHNICAL_FAILURE"
    assert "M0 fixture failure" in package["methods"]["M0"]["failure_reason"]
    assert package["methods"]["M2"]["generation_status"] == "OK"
    scored = incremental.score_fixed_prediction(
        target_draw="115000097",
        output_root=tmp_path,
        record_class="SYNTHETIC_TEST",
        official_result=_result_for("115000097", "2026-10-16"),
        clock=_clock,
    )
    assert scored["methods"]["M0"]["result_status"] == "DELIVERY_FAILURE"
    assert scored["methods"]["M0"]["successful"] is False
    assert scored["methods"]["M2"]["result_status"] == "SCORED"
    assert scored["methods"]["M2"]["successful"] is True

    another_root = tmp_path / "invalid"
    invalid = _predict(
        another_root,
        generate=_generator_for(OVERLAPPING_TICKETS, WINNING_TICKETS),
    )
    method = invalid["methods"]["M0"]
    assert method["generation_status"] == "INVALID_TICKETS"
    assert method["ticket_quality"]["is_valid"] is False
    assert any(
        "CROSS_TICKET_OVERLAP" in reason
        for reason in method["ticket_quality"]["rejection_reasons"]
    )
    assert method["generated_tickets"] == OVERLAPPING_TICKETS
    assert invalid["methods"]["M2"]["generation_status"] == "OK"


def test_interrupted_atomic_write_leaves_no_complete_prediction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(_temporary: Path, _destination: Path) -> None:
        raise OSError("injected interruption before atomic publish")

    monkeypatch.setattr(incremental.os, "replace", interrupted)
    with pytest.raises(OSError, match="injected interruption"):
        _predict(tmp_path)
    prediction_dir = tmp_path / "SYNTHETIC_TEST" / "predictions"
    assert not incremental.prediction_path(tmp_path, "SYNTHETIC_TEST", "115000097").exists()
    assert list(prediction_dir.glob("*.tmp")) == []


def test_score_requires_prediction_and_never_calls_any_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(incremental.MissingPredictionError):
        incremental.score_fixed_prediction(
            target_draw="115000097",
            output_root=tmp_path,
            record_class="SYNTHETIC_TEST",
            official_result=_result_for("115000097", "2026-10-16"),
        )

    _predict(tmp_path)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("score attempted prediction generation")

    monkeypatch.setattr(incremental.shared, "generator", forbidden)
    monkeypatch.setattr(incremental.shared, "native_adapters", forbidden)
    first = incremental.score_fixed_prediction(
        target_draw="115000097",
        output_root=tmp_path,
        record_class="SYNTHETIC_TEST",
        official_result=_result_for("115000097", "2026-10-16"),
        clock=_clock,
    )
    score_file = incremental.score_path(tmp_path, "SYNTHETIC_TEST", "115000097")
    original_bytes = score_file.read_bytes()
    repeated = incremental.score_fixed_prediction(
        target_draw="115000097",
        output_root=tmp_path,
        record_class="SYNTHETIC_TEST",
        official_result=_result_for("115000097", "2026-10-16"),
        clock=_clock,
    )
    assert first["score_status"] == "SCORED"
    assert first["methods"]["M0"]["successful"] is True
    assert first["methods"]["M2"]["successful"] is True
    assert repeated == first
    assert score_file.read_bytes() == original_bytes
    assert incremental.build_summary(tmp_path, "SYNTHETIC_TEST")["known_result_n"] == 1


def test_pending_result_advances_once_and_conflicting_versions_are_rejected(tmp_path: Path) -> None:
    _predict(tmp_path)
    pending = incremental.score_fixed_prediction(
        target_draw="115000097",
        output_root=tmp_path,
        record_class="SYNTHETIC_TEST",
        clock=_clock,
    )
    assert pending["score_status"] == "PENDING"
    assert pending["methods"]["M0"]["successful"] is None

    known = incremental.score_fixed_prediction(
        target_draw="115000097",
        output_root=tmp_path,
        record_class="SYNTHETIC_TEST",
        official_result=_result_for("115000097", "2026-10-16"),
        clock=_clock,
    )
    assert known["score_status"] == "SCORED"
    assert known["created_at"] == pending["created_at"]
    changed_version = {**_result_for("115000097", "2026-10-16"), "result_version": "synthetic-v2"}
    with pytest.raises(incremental.RecordConflictError, match="Result-version conflict"):
        incremental.score_fixed_prediction(
            target_draw="115000097",
            output_root=tmp_path,
            record_class="SYNTHETIC_TEST",
            official_result=changed_version,
            clock=_clock,
        )
    with pytest.raises(incremental.EvaluationError, match="does not match"):
        incremental.score_fixed_prediction(
            target_draw="115000097",
            output_root=tmp_path,
            record_class="SYNTHETIC_TEST",
            official_result=_result_for("115000098", "2026-10-17"),
            clock=_clock,
        )


def test_summary_matches_manual_paired_counts_and_keeps_mode_boundaries(tmp_path: Path) -> None:
    cases = [
        ("115000101", WINNING_TICKETS, WINNING_TICKETS, True),
        ("115000102", LOSING_TICKETS, WINNING_TICKETS, True),
        ("115000103", WINNING_TICKETS, LOSING_TICKETS, True),
        ("115000104", LOSING_TICKETS, LOSING_TICKETS, True),
        ("115000105", OVERLAPPING_TICKETS, LOSING_TICKETS, True),
        ("115000106", LOSING_TICKETS, LOSING_TICKETS, False),
    ]
    for draw, m0, m2, has_result in cases:
        target_date = (date(2026, 10, 16) + timedelta(days=int(draw) - 115000101)).isoformat()
        _predict(
            tmp_path,
            target_draw=draw,
            target_date=target_date,
            snapshot=_synthetic_snapshot(draw, target_date),
            generate=_generator_for(m0, m2),
        )
        if has_result:
            incremental.score_fixed_prediction(
                target_draw=draw,
                output_root=tmp_path,
                record_class="SYNTHETIC_TEST",
                official_result=_result_for(draw, target_date),
                clock=_clock,
            )

    _predict(
        tmp_path,
        snapshot=_synthetic_snapshot(),
        record_class="HISTORICAL_DEMO",
        generate=_generator_for(),
    )
    _predict(
        tmp_path,
        snapshot=_synthetic_snapshot(),
        record_class="LOCAL_RECORDED_UNATTESTED",
        generate=_generator_for(),
    )

    summary = incremental.build_summary(tmp_path, "SYNTHETIC_TEST")
    assert summary["registered_target_n"] == 6
    assert summary["pending_result_n"] == 1
    assert summary["known_result_n"] == 5
    assert summary["methods"]["M0"]["usable_success_n"] == 2
    assert summary["methods"]["M2"]["usable_success_n"] == 2
    assert summary["methods"]["M0"]["usable_hit_rate"] == pytest.approx(0.4)
    assert summary["methods"]["M2"]["usable_hit_rate"] == pytest.approx(0.4)
    assert summary["methods"]["M0"]["invalid_ticket_n"] == 1
    assert summary["paired_known_results"]["denominator"] == 5
    assert summary["paired_known_results"]["both_success_n"] == 1
    assert summary["paired_known_results"]["both_unsuccessful_n"] == 2
    assert summary["paired_known_results"]["m2_only_success_b"] == 1
    assert summary["paired_known_results"]["m0_only_success_c"] == 1
    assert summary["paired_known_results"]["difference_percentage_points"] == 0
    assert summary["paired_known_results"]["at_least_one_delivery_failure_n"] == 1
    assert summary["qualified_pair_supplement"]["denominator"] == 4
    assert summary["qualified_pair_supplement"]["both_success_n"] == 1
    assert summary["qualified_pair_supplement"]["both_unsuccessful_n"] == 1
    assert summary["qualified_pair_supplement"]["m2_only_success_b"] == 1
    assert summary["qualified_pair_supplement"]["m0_only_success_c"] == 1
    assert summary["decision"] is None
    assert incremental.build_summary(tmp_path, "HISTORICAL_DEMO")["registered_target_n"] == 1
    assert (
        incremental.build_summary(tmp_path, "LOCAL_RECORDED_UNATTESTED")["registered_target_n"]
        == 1
    )
