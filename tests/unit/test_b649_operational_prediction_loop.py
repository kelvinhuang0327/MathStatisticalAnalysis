"""Focused behavior tests for the minimal B649 operational loop."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from tools.b649_operational_prediction_loop import (
    HistorySnapshot,
    PredictionTarget,
    StrategyStream,
    build_current_target_freshness_report,
    classify_prediction_temporal,
    compute_history_freshness,
    create_prediction_payload,
    rebuild_history_freshness_ledger,
    resolve_latest_known_draw,
    resolve_latest_known_draw_at,
    run_all_enabled_streams,
    run_strategy_stream,
    save_prediction,
    save_strategy_prediction,
    update_outcome,
)

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow, PortfolioBetAdapter

TAIPEI = ZoneInfo("Asia/Taipei")


class _FakePortfolioAdapter(PortfolioBetAdapter):
    """Deterministic two-ticket fake, independent of any real strategy."""

    strategy_id = "fake_portfolio_a"
    strategy_name = "Fake Portfolio A"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))


class _FakeSingleAdapter(BetAdapter):
    """Deterministic one-ticket fake, independent of any real strategy."""

    strategy_id = "fake_single_b"
    strategy_name = "Fake Single B"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[int, ...]:
        return (13, 14, 15, 16, 17, 18)


class _FakeFailingAdapter(BetAdapter):
    """Always raises a plain technical failure, never a BetAdapterError."""

    strategy_id = "fake_failing_c"
    strategy_name = "Fake Failing C"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[int, ...]:
        raise RuntimeError("synthetic technical failure")


class _FakeUnavailableAdapter(BetAdapter):
    """min_history gates every realistic test fixture before `_predict` runs."""

    strategy_id = "fake_unavailable_d"
    strategy_name = "Fake Unavailable D"
    strategy_version = "v0.1"
    min_history = 10_000
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[int, ...]:
        raise AssertionError("must not be reached: min_history should gate first")


def _stream(
    adapter_class: type[BetAdapter | PortfolioBetAdapter], native_ticket_count: int
) -> StrategyStream:
    return StrategyStream(
        strategy_id=adapter_class.strategy_id,
        strategy_version=adapter_class.strategy_version,
        enabled=True,
        adapter_factory=adapter_class,
        native_ticket_count=native_ticket_count,
    )


def _target(draw_number: str = "115000080") -> PredictionTarget:
    return PredictionTarget(
        lottery_type="BIG_LOTTO",
        draw_number=draw_number,
        draw_date="2026-08-18",
        scheduled_at="2026-08-18T20:30:00+08:00",
    )


def _history() -> HistorySnapshot:
    rows = tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"history-{index + 1}",
            numbers=tuple(
                sorted((((index + 7 * offset) % 49) + 1) for offset in range(6))
            ),
        )
        for index in range(200)
    )
    return HistorySnapshot(
        rows=rows,
        cutoff_draw="115000078",
        cutoff_date="2026-08-11",
        draw_count=200,
        history_sha256="1" * 64,
    )


def _history_with_cutoff(cutoff_draw: str) -> HistorySnapshot:
    base = _history()
    return HistorySnapshot(
        rows=base.rows,
        cutoff_draw=cutoff_draw,
        cutoff_date=base.cutoff_date,
        draw_count=base.draw_count,
        history_sha256=base.history_sha256,
    )


def _read_object(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _object(value: dict[str, object], key: str) -> dict[str, object]:
    result = value[key]
    assert isinstance(result, dict)
    return cast(dict[str, object], result)


def _object_list(value: dict[str, object], key: str) -> list[dict[str, object]]:
    result = value[key]
    assert isinstance(result, list)
    result_list = cast(list[object], result)
    assert all(isinstance(item, dict) for item in result_list)
    return cast(list[dict[str, object]], result_list)


def _numbers(value: dict[str, object], key: str) -> tuple[int, ...]:
    result = value[key]
    assert isinstance(result, list)
    result_list = cast(list[object], result)
    assert all(type(item) is int for item in result_list)
    return tuple(cast(list[int], result_list))


def _available_special(main_numbers: tuple[int, ...]) -> int:
    return next(number for number in range(1, 50) if number not in main_numbers)


def test_prediction_saves_two_native_tickets_with_time_and_history_identity(
    tmp_path: Path,
) -> None:
    created_at = datetime.fromisoformat("2026-08-14T19:00:00+08:00")
    prediction = create_prediction_payload(
        _history(),
        created_at=created_at,
    )

    path = save_prediction(tmp_path, prediction)
    stored = _read_object(path)

    assert str(stored["prediction_run_id"]).startswith(
        "115000079-20260814T190000000000p0800-"
    )
    assert stored["prediction_created_at"] == "2026-08-14T19:00:00.000000+08:00"
    assert stored["prediction_temporal_class"] == "PRE_DRAW"
    assert stored["history_draw_count"] == 200
    assert stored["history_sha256"] == "1" * 64
    assert _object(stored, "history_cutoff") == {
        "draw_date": "2026-08-11",
        "draw_number": "115000078",
    }
    tickets = _object_list(stored, "tickets")
    assert len(tickets) == 2
    assert [ticket["ticket_position"] for ticket in tickets] == [1, 2]
    assert all(len(_numbers(ticket, "predicted_numbers")) == 6 for ticket in tickets)
    assert (tmp_path / "performance.jsonl").is_file()
    assert (tmp_path / "research-summary.json").is_file()


def test_later_prediction_run_does_not_replace_the_older_run(tmp_path: Path) -> None:
    first = create_prediction_payload(
        _history(),
        created_at=datetime.fromisoformat("2026-08-14T19:00:00+08:00"),
        prediction_run_id="run-one",
    )
    second = create_prediction_payload(
        _history(),
        created_at=datetime.fromisoformat("2026-08-14T21:00:00+08:00"),
        prediction_run_id="run-two",
    )

    first_path = save_prediction(tmp_path, first)
    original = first_path.read_bytes()
    second_path = save_prediction(tmp_path, second)

    assert first_path != second_path
    assert first_path.read_bytes() == original
    assert _read_object(first_path)["prediction_temporal_class"] == "PRE_DRAW"
    assert _read_object(second_path)["prediction_temporal_class"] == "POST_DRAW"
    ledger = [
        cast(dict[str, object], json.loads(line))
        for line in (tmp_path / "performance.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert ledger[0]["prediction_count"] == 2
    assert ledger[0]["PRE_DRAW_count"] == 1
    assert ledger[0]["POST_DRAW_count"] == 1


def test_outcome_creation_and_correction_automatically_replace_current_scores(
    tmp_path: Path,
) -> None:
    prediction = create_prediction_payload(
        _history(),
        created_at=datetime.fromisoformat("2026-08-14T19:00:00+08:00"),
        prediction_run_id="rescore-run",
    )
    prediction_path = save_prediction(tmp_path, prediction)
    stored_prediction = _read_object(prediction_path)
    tickets = _object_list(stored_prediction, "tickets")
    first_ticket = _numbers(tickets[0], "predicted_numbers")
    second_ticket = _numbers(tickets[1], "predicted_numbers")

    outcome_path, first_scores = update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=first_ticket,
        special_number=_available_special(first_ticket),
        source="owner-entry-v1",
        updated_at=datetime.fromisoformat("2026-08-14T21:00:00+08:00"),
    )
    first_score = _read_object(first_scores[0])
    assert _read_object(outcome_path)["revision"] == 1
    assert _object(first_score, "portfolio_score")["M6"] is True

    _, corrected_scores = update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=second_ticket,
        special_number=_available_special(second_ticket),
        source="owner-correction-v2",
        updated_at=datetime.fromisoformat("2026-08-14T21:05:00+08:00"),
    )
    corrected_outcome = _read_object(outcome_path)
    corrected_score = _read_object(corrected_scores[0])

    assert corrected_outcome["revision"] == 2
    assert corrected_outcome["source"] == "owner-correction-v2"
    assert corrected_score["outcome_revision"] == 2
    assert corrected_score["outcome_source"] == "owner-correction-v2"
    assert _object(corrected_score, "portfolio_score")["M6"] is True
    assert first_scores == corrected_scores
    summary = _read_object(tmp_path / "research-summary.json")
    assert summary["number_of_forward_observations"] == 1
    assert summary["M2+_rate"] == 1.0


def test_temporal_classification_uses_strict_pre_draw_boundary() -> None:
    scheduled_at = datetime.fromisoformat("2026-08-14T20:30:00+08:00")

    assert (
        classify_prediction_temporal(
            datetime.fromisoformat("2026-08-14T20:29:59.999999+08:00"),
            scheduled_at,
        )
        == "PRE_DRAW"
    )
    assert classify_prediction_temporal(scheduled_at, scheduled_at) == "POST_DRAW"
    assert (
        classify_prediction_temporal(
            datetime(2026, 8, 14, 12, 30, tzinfo=ZoneInfo("UTC")),
            scheduled_at,
        )
        == "POST_DRAW"
    )


def test_multiple_strategy_streams_predict_independently_and_isolate_failures(
    tmp_path: Path,
) -> None:
    streams = (
        _stream(_FakePortfolioAdapter, 2),
        _stream(_FakeSingleAdapter, 1),
        _stream(_FakeFailingAdapter, 1),
        _stream(_FakeUnavailableAdapter, 1),
        StrategyStream(
            strategy_id="fake_disabled_e",
            strategy_version="v0.1",
            enabled=False,
            adapter_factory=_FakeSingleAdapter,
            native_ticket_count=1,
        ),
    )
    target = _target()
    history = _history()
    created_at = datetime.fromisoformat("2026-08-18T19:00:00+08:00")

    results = run_all_enabled_streams(
        tmp_path,
        target=target,
        history=history,
        streams=streams,
        created_at=created_at,
    )

    by_strategy = {cast(str, result["strategy_id"]): result for result in results}
    assert set(by_strategy) == {
        "fake_portfolio_a",
        "fake_single_b",
        "fake_failing_c",
        "fake_unavailable_d",
    }
    assert by_strategy["fake_portfolio_a"]["availability"] == "AVAILABLE"
    assert by_strategy["fake_single_b"]["availability"] == "AVAILABLE"
    assert by_strategy["fake_failing_c"]["availability"] == "TECHNICAL_FAILURE"
    assert "RuntimeError" in cast(str, by_strategy["fake_failing_c"]["unavailable_reason"])
    assert by_strategy["fake_unavailable_d"]["availability"] == "UNAVAILABLE"
    assert "InsufficientHistory" in cast(
        str, by_strategy["fake_unavailable_d"]["unavailable_reason"]
    )

    assert len(_object_list(by_strategy["fake_portfolio_a"], "tickets")) == 2
    assert len(_object_list(by_strategy["fake_single_b"], "tickets")) == 1
    assert by_strategy["fake_failing_c"]["tickets"] == []
    assert by_strategy["fake_unavailable_d"]["tickets"] == []

    for strategy_id in (
        "fake_portfolio_a",
        "fake_single_b",
        "fake_failing_c",
        "fake_unavailable_d",
    ):
        stored_dir = tmp_path / "predictions" / target.draw_number / strategy_id
        stored_files = list(stored_dir.glob("*.json"))
        assert len(stored_files) == 1
        stored = _read_object(stored_files[0])
        assert stored["history_cutoff"] == {
            "draw_date": history.cutoff_date,
            "draw_number": history.cutoff_draw,
        }
        assert stored["history_draw_count"] == history.draw_count
        assert stored["history_sha256"] == history.history_sha256


def test_run_all_enabled_streams_refuses_the_protected_draw_number(tmp_path: Path) -> None:
    target = PredictionTarget(
        lottery_type="BIG_LOTTO",
        draw_number="115000079",
        draw_date="2026-08-14",
        scheduled_at="2026-08-14T20:30:00+08:00",
    )
    with pytest.raises(ValueError, match="115000079"):
        run_all_enabled_streams(
            tmp_path,
            target=target,
            history=_history(),
            streams=(_stream(_FakeSingleAdapter, 1),),
            created_at=datetime.fromisoformat("2026-08-14T19:10:00+08:00"),
        )
    assert not (tmp_path / "predictions").exists()


def test_run_strategy_stream_classifies_temporal_class_from_real_timestamps() -> None:
    stream = _stream(_FakeSingleAdapter, 1)
    target = _target()

    pre = run_strategy_stream(
        stream,
        _history(),
        target,
        created_at=datetime.fromisoformat("2026-08-18T19:00:00+08:00"),
        prediction_run_id="pre-run",
    )
    post = run_strategy_stream(
        stream,
        _history(),
        target,
        created_at=datetime.fromisoformat("2026-08-18T21:00:00+08:00"),
        prediction_run_id="post-run",
    )

    assert pre["prediction_temporal_class"] == "PRE_DRAW"
    assert post["prediction_temporal_class"] == "POST_DRAW"


def test_save_strategy_prediction_never_overwrites_an_existing_run(tmp_path: Path) -> None:
    record = run_strategy_stream(
        _stream(_FakeSingleAdapter, 1),
        _history(),
        _target(),
        created_at=datetime.fromisoformat("2026-08-18T19:00:00+08:00"),
        prediction_run_id="dup-run",
    )
    save_strategy_prediction(tmp_path, record)
    with pytest.raises(FileExistsError):
        save_strategy_prediction(tmp_path, record)


def test_legacy_flat_prediction_remains_readable_alongside_nested_multi_strategy_layout(
    tmp_path: Path,
) -> None:
    """Regression guard for backward compatibility: this operates entirely
    inside an isolated tmp_path sandbox and never touches the real protected
    115000079 forward record; draw_number 115000079 is reused only because
    `create_prediction_payload` always targets it, which is exactly the
    legacy/nested mixed-layout scenario worth proving works together."""

    legacy = create_prediction_payload(
        _history(),
        created_at=datetime.fromisoformat("2026-08-14T19:00:00+08:00"),
        prediction_run_id="legacy-run",
    )
    legacy_path = save_prediction(tmp_path, legacy)
    assert legacy_path == tmp_path / "predictions" / "115000079" / "legacy-run.json"

    new_record = run_strategy_stream(
        _stream(_FakeSingleAdapter, 1),
        _history(),
        PredictionTarget(
            lottery_type="BIG_LOTTO",
            draw_number="115000079",
            draw_date="2026-08-14",
            scheduled_at="2026-08-14T20:30:00+08:00",
        ),
        created_at=datetime.fromisoformat("2026-08-14T19:10:00+08:00"),
        prediction_run_id="fake-single-run",
    )
    nested_path = save_strategy_prediction(tmp_path, new_record)
    assert nested_path == (
        tmp_path / "predictions" / "115000079" / "fake_single_b" / "fake-single-run.json"
    )
    assert _read_object(legacy_path)["prediction_run_id"] == "legacy-run"

    _, score_paths = update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=(20, 21, 22, 23, 24, 25),
        special_number=49,
        source="test-owner-entry",
        updated_at=datetime.fromisoformat("2026-08-14T21:00:00+08:00"),
    )
    assert len(score_paths) == 2
    scored_run_ids = {_read_object(path)["prediction_run_id"] for path in score_paths}
    assert scored_run_ids == {"legacy-run", "fake-single-run"}

    ledger_rows = [
        cast(dict[str, object], json.loads(line))
        for line in (tmp_path / "performance.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["strategy_id"] for row in ledger_rows} == {
        "b649_new_horizon_minimax_disagreement_r1",
        "fake_single_b",
    }


def test_outcome_update_and_correction_rescore_every_strategy_stream(tmp_path: Path) -> None:
    streams = (_stream(_FakePortfolioAdapter, 2), _stream(_FakeSingleAdapter, 1))
    target = _target("115000081")
    results = run_all_enabled_streams(
        tmp_path,
        target=target,
        history=_history(),
        streams=streams,
        created_at=datetime.fromisoformat("2026-08-21T09:00:00+08:00"),
    )
    assert {result["availability"] for result in results} == {"AVAILABLE"}

    _, score_paths = update_outcome(
        tmp_path,
        draw_number=target.draw_number,
        main_numbers=(1, 2, 3, 4, 5, 6),  # exact match for fake_portfolio_a's first ticket
        special_number=49,
        source="test-owner-entry-v1",
        updated_at=datetime.fromisoformat("2026-08-21T21:00:00+08:00"),
    )
    assert len(score_paths) == 2
    scores_by_strategy = {
        _read_object(path)["strategy_id"]: _read_object(path) for path in score_paths
    }
    assert _object(scores_by_strategy["fake_portfolio_a"], "portfolio_score")["M6"] is True
    assert _object(scores_by_strategy["fake_single_b"], "portfolio_score")["M1+"] is False

    _, corrected_paths = update_outcome(
        tmp_path,
        draw_number=target.draw_number,
        main_numbers=(13, 14, 15, 16, 17, 18),  # exact match for fake_single_b instead
        special_number=49,
        source="test-owner-correction-v2",
        updated_at=datetime.fromisoformat("2026-08-21T21:05:00+08:00"),
    )
    assert len(corrected_paths) == 2
    corrected_by_strategy = {
        _read_object(path)["strategy_id"]: _read_object(path) for path in corrected_paths
    }
    assert corrected_by_strategy["fake_portfolio_a"]["outcome_revision"] == 2
    assert corrected_by_strategy["fake_single_b"]["outcome_revision"] == 2
    assert _object(corrected_by_strategy["fake_single_b"], "portfolio_score")["M6"] is True
    assert _object(corrected_by_strategy["fake_portfolio_a"], "portfolio_score")["M6"] is False

    ledger_rows = [
        cast(dict[str, object], json.loads(line))
        for line in (tmp_path / "performance.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ledger_by_strategy = {row["strategy_id"]: row for row in ledger_rows}
    assert ledger_by_strategy["fake_portfolio_a"]["scored_count"] == 1
    assert ledger_by_strategy["fake_single_b"]["scored_count"] == 1
    # ledger reflects the latest rescore (post-correction), not the first outcome
    assert _object(ledger_by_strategy["fake_portfolio_a"], "combined")["M6_count"] == 0
    assert _object(ledger_by_strategy["fake_single_b"], "combined")["M6_count"] == 1
    assert _object(ledger_by_strategy["fake_portfolio_a"], "availability_counts") == {
        "AVAILABLE": 1,
        "UNAVAILABLE": 0,
        "TECHNICAL_FAILURE": 0,
    }


def test_head_to_head_summary_computes_pairwise_wins_losses_and_ties(
    tmp_path: Path,
) -> None:
    history = _history()

    def _raw_prediction(
        draw_number: str, strategy_id: str, run_id: str, ticket: tuple[int, ...]
    ) -> dict[str, object]:
        return {
            "schema_version": "b649-operational-prediction-v1",
            "task_id": "TEST",
            "prediction_run_id": run_id,
            "lottery_type": "BIG_LOTTO",
            "draw_number": draw_number,
            "draw_date": "2026-09-01",
            "scheduled_at": "2026-09-01T20:30:00+08:00",
            "prediction_created_at": "2026-09-01T09:00:00.000000+08:00",
            "strategy_id": strategy_id,
            "strategy_version": "v0.1",
            "strategy_config": {},
            "history_cutoff": {
                "draw_number": history.cutoff_draw,
                "draw_date": history.cutoff_date,
            },
            "history_draw_count": history.draw_count,
            "history_sha256": history.history_sha256,
            "history_caveat": history.history_caveat,
            "producer_fingerprint": None,
            "pinned_implementation": None,
            "prediction_temporal_class": "PRE_DRAW",
            "native_ticket_count": 1,
            "availability": "AVAILABLE",
            "unavailable_reason": None,
            "tickets": [{"ticket_position": 1, "predicted_numbers": list(ticket)}],
        }

    # a_better on 200001 (3 hits => GENERAL prize), b_better on 200002 (2 hits,
    # no prize either side), tie on 200003 (0 hits both sides).
    scenarios = (
        ("200001", (1, 2, 3, 4, 5, 6), (1, 2, 3, 20, 21, 22), (30, 31, 32, 33, 34, 35)),
        ("200002", (10, 11, 12, 13, 14, 15), (1, 2, 3, 4, 5, 6), (10, 11, 40, 41, 42, 43)),
        ("200003", (20, 21, 22, 23, 24, 25), (1, 2, 3, 4, 5, 6), (7, 8, 9, 40, 41, 42)),
    )
    for draw_number, outcome_numbers, ticket_a, ticket_b in scenarios:
        save_strategy_prediction(
            tmp_path, _raw_prediction(draw_number, "strategy_a", f"{draw_number}-a", ticket_a)
        )
        save_strategy_prediction(
            tmp_path, _raw_prediction(draw_number, "strategy_b", f"{draw_number}-b", ticket_b)
        )
        update_outcome(
            tmp_path,
            draw_number=draw_number,
            main_numbers=outcome_numbers,
            special_number=49,  # outside every scenario's numbers: keeps special_hit False
            source="test",
            updated_at=datetime.fromisoformat("2026-09-01T21:00:00+08:00"),
        )

    rows = [
        cast(dict[str, object], json.loads(line))
        for line in (tmp_path / "head_to_head.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    by_metric = {row["metric"]: row for row in rows}

    assert by_metric["M2+"]["common_scored_targets"] == 3
    assert by_metric["M2+"]["a_better"] == 1
    assert by_metric["M2+"]["b_better"] == 1
    assert by_metric["M2+"]["ties"] == 1

    assert by_metric["official_any_prize"]["common_scored_targets"] == 3
    assert by_metric["official_any_prize"]["a_better"] == 1
    assert by_metric["official_any_prize"]["b_better"] == 0
    assert by_metric["official_any_prize"]["ties"] == 2


def test_compute_history_freshness_classifies_fresh_stale_and_unknown() -> None:
    fresh = compute_history_freshness("115000078", "115000078")
    assert fresh["history_lag_draws"] == 0
    assert fresh["history_freshness_status"] == "FRESH"
    assert fresh["history_freshness_warning"] == "NONE"

    stale = compute_history_freshness("115000078", "115000079")
    assert stale["history_lag_draws"] == 1
    assert stale["history_freshness_status"] == "STALE_HISTORY"
    assert stale["history_freshness_warning"] == "LATEST_DRAW_NOT_INCLUDED"

    unknown = compute_history_freshness("115000078", None)
    assert unknown["history_lag_draws"] is None
    assert unknown["history_freshness_status"] == "UNKNOWN"
    assert unknown["history_freshness_warning"] == "HISTORY_FRESHNESS_UNKNOWN"


def test_stale_or_unknown_history_freshness_never_blocks_saving_a_prediction(
    tmp_path: Path,
) -> None:
    record = run_strategy_stream(
        _stream(_FakeSingleAdapter, 1),
        _history_with_cutoff("115000078"),
        _target("115000080"),
        created_at=datetime.fromisoformat("2026-08-18T19:00:00+08:00"),
        prediction_run_id="never-blocked-run",
    )
    assert (
        compute_history_freshness("115000078", "115000079")["history_freshness_status"]
        == "STALE_HISTORY"
    )
    assert (
        compute_history_freshness("115000078", None)["history_freshness_status"]
        == "UNKNOWN"
    )

    path = save_strategy_prediction(tmp_path, record)

    assert path.is_file()
    assert record["availability"] == "AVAILABLE"
    assert len(_object_list(record, "tickets")) == 1


def test_pre_draw_classification_is_independent_of_history_freshness() -> None:
    record = run_strategy_stream(
        _stream(_FakeSingleAdapter, 1),
        _history_with_cutoff("115000078"),
        _target(),
        created_at=datetime.fromisoformat("2026-08-18T19:00:00+08:00"),
        prediction_run_id="pre-draw-stale-run",
    )
    cutoff_draw = cast(str, _object(record, "history_cutoff")["draw_number"])
    freshness = compute_history_freshness(cutoff_draw, "115000079")

    assert record["prediction_temporal_class"] == "PRE_DRAW"
    assert freshness["history_freshness_status"] == "STALE_HISTORY"


def test_history_freshness_ledger_never_rewrites_stored_prediction_files(
    tmp_path: Path,
) -> None:
    prediction = create_prediction_payload(
        _history(),
        created_at=datetime.fromisoformat("2026-08-14T19:00:00+08:00"),
        prediction_run_id="freshness-untouched-run",
    )
    path = save_prediction(tmp_path, prediction)
    original_bytes = path.read_bytes()

    rebuild_history_freshness_ledger(tmp_path, database=tmp_path / "no-such.db")

    assert path.read_bytes() == original_bytes
    assert _read_object(path)["prediction_run_id"] == "freshness-untouched-run"


def test_history_freshness_ledger_counts_use_prediction_time_not_current_time(
    tmp_path: Path,
) -> None:
    """Regression guard for the prediction-time bug: an old prediction must
    not be reclassified as more stale just because a later outcome arrived
    after it was made, and a prediction made before any local evidence
    existed must classify as UNKNOWN rather than borrowing evidence from the
    future."""

    database = _seed_local_draws_database(
        tmp_path / "lottolab-data", draw_number="115000078", draw_date="2026-08-11"
    )
    update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=49,
        source="test-owner-entry",
        updated_at=datetime.fromisoformat("2026-08-15T02:21:09+08:00"),
    )
    stream = _stream(_FakeSingleAdapter, 1)

    save_strategy_prediction(
        tmp_path,
        run_strategy_stream(
            stream,
            _history_with_cutoff("115000078"),
            _target("115000079"),
            created_at=datetime.fromisoformat("2026-08-14T19:53:29+08:00"),
            prediction_run_id="fresh-before-outcome-run",
        ),
    )
    save_strategy_prediction(
        tmp_path,
        run_strategy_stream(
            stream,
            _history_with_cutoff("115000078"),
            _target("115000080"),
            created_at=datetime.fromisoformat("2026-08-15T02:21:20+08:00"),
            prediction_run_id="stale-one-after-outcome-run",
        ),
    )
    save_strategy_prediction(
        tmp_path,
        run_strategy_stream(
            stream,
            _history_with_cutoff("115000077"),
            _target("115000081"),
            created_at=datetime.fromisoformat("2026-08-16T09:00:00+08:00"),
            prediction_run_id="stale-two-run",
        ),
    )
    save_strategy_prediction(
        tmp_path,
        run_strategy_stream(
            stream,
            _history_with_cutoff("115000078"),
            _target("115000082"),
            created_at=datetime.fromisoformat("2026-07-01T00:00:00+08:00"),
            prediction_run_id="unknown-before-everything-run",
        ),
    )

    ledger_path = rebuild_history_freshness_ledger(tmp_path, database=database)
    rows = {
        cast(str, row["strategy_id"]): row
        for row in (
            cast(dict[str, object], json.loads(line))
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
        )
    }
    bucket = rows["fake_single_b"]
    assert bucket["fresh_prediction_count"] == 1
    assert bucket["stale_prediction_count"] == 2
    assert bucket["stale_1_draw_count"] == 1
    assert bucket["stale_2_plus_count"] == 1
    assert bucket["unknown_freshness_count"] == 1


def test_current_target_freshness_report_uses_prediction_time_freshness(
    tmp_path: Path,
) -> None:
    """Matches the real 115000080 case: history cutoff 078, but the 079
    outcome was already recorded by the time this batch of predictions ran,
    so it counts as known and the target is correctly STALE_HISTORY."""

    database = _seed_local_draws_database(
        tmp_path / "lottolab-data", draw_number="115000078", draw_date="2026-08-11"
    )
    update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=49,
        source="test-owner-entry",
        updated_at=datetime.fromisoformat("2026-08-15T02:21:09+08:00"),
    )
    save_strategy_prediction(
        tmp_path,
        run_strategy_stream(
            _stream(_FakeSingleAdapter, 1),
            _history_with_cutoff("115000078"),
            _target("115000080"),
            created_at=datetime.fromisoformat("2026-08-15T02:21:20+08:00"),
            prediction_run_id="current-target-run",
        ),
    )

    report = build_current_target_freshness_report(
        tmp_path, draw_number="115000080", database=database
    )

    assert report == {
        "draw_number": "115000080",
        "history_cutoff_draw": "115000078",
        "latest_known_draw": "115000079",
        "history_lag_draws": 1,
        "history_freshness_status": "STALE_HISTORY",
        "history_freshness_warning": "LATEST_DRAW_NOT_INCLUDED",
        "latest_known_draw_at_prediction_time": "115000079",
        "history_lag_draws_at_prediction_time": 1,
        "history_freshness_status_at_prediction_time": "STALE_HISTORY",
        "history_freshness_warning_at_prediction_time": "LATEST_DRAW_NOT_INCLUDED",
    }


def test_current_target_freshness_report_is_fresh_when_prediction_precedes_the_next_outcome(
    tmp_path: Path,
) -> None:
    """Matches the real 115000079 case, and is the direct regression proof
    for the bug this task fixes: the 079 outcome existing *today* must not
    make a prediction that predates it look stale."""

    database = _seed_local_draws_database(
        tmp_path / "lottolab-data", draw_number="115000078", draw_date="2026-08-11"
    )
    save_strategy_prediction(
        tmp_path,
        run_strategy_stream(
            _stream(_FakeSingleAdapter, 1),
            _history_with_cutoff("115000078"),
            _target("115000079"),
            created_at=datetime.fromisoformat("2026-08-14T19:53:29+08:00"),
            prediction_run_id="fresh-before-outcome-run",
        ),
    )
    # Recorded *after* the prediction above; must not retroactively taint it.
    update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=49,
        source="test-owner-entry",
        updated_at=datetime.fromisoformat("2026-08-15T02:21:09+08:00"),
    )

    report = build_current_target_freshness_report(
        tmp_path, draw_number="115000079", database=database
    )

    assert report["history_freshness_status_at_prediction_time"] == "FRESH"
    assert report["history_lag_draws_at_prediction_time"] == 0
    assert report["latest_known_draw_at_prediction_time"] == "115000078"


def test_resolve_latest_known_draw_at_ignores_an_outcome_recorded_after_as_of(
    tmp_path: Path,
) -> None:
    database = _seed_local_draws_database(
        tmp_path / "lottolab-data", draw_number="115000078", draw_date="2026-08-11"
    )
    update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=49,
        source="test-owner-entry",
        updated_at=datetime.fromisoformat("2026-08-15T02:21:09+08:00"),
    )

    before_outcome = resolve_latest_known_draw_at(
        tmp_path, database, datetime.fromisoformat("2026-08-14T19:53:29+08:00")
    )
    after_outcome = resolve_latest_known_draw_at(
        tmp_path, database, datetime.fromisoformat("2026-08-15T02:21:20+08:00")
    )

    assert before_outcome == "115000078"
    assert after_outcome == "115000079"


def test_resolve_latest_known_draw_uses_the_max_of_outcomes_when_database_is_absent(
    tmp_path: Path,
) -> None:
    missing_database = tmp_path / "does-not-exist.db"

    assert resolve_latest_known_draw(tmp_path, missing_database) is None

    update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=49,
        source="test-owner-entry",
        updated_at=datetime.fromisoformat("2026-08-15T02:21:09+08:00"),
    )

    assert resolve_latest_known_draw(tmp_path, missing_database) == "115000079"


def _seed_local_draws_database(
    data_root: Path, *, draw_number: str, draw_date: str
) -> Path:
    """A minimal fully-migrated local database with one ingested BIG_LOTTO draw."""

    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_root)})
    initialize_schema(paths)
    run_id = "seed-run-1"
    timestamp = "2026-08-01T00:00:00.000000Z"
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 0, 0, 0, ?, ?, ?, ?, NULL)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                IngestionRunStatus.SUCCESS.value,
                LotteryType.BIG_LOTTO.value,
                "seed.json",
                "0" * 64,
                "test-parser-v1",
                draw_number,
                draw_number,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                LotteryType.BIG_LOTTO.value,
                draw_number,
                draw_date,
                json.dumps([1, 2, 3, 4, 5, 6], separators=(",", ":")),
                json.dumps([7], separators=(",", ":")),
                "1" * 64,
                "test-history",
                None,
                run_id,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()
    return paths.database


def test_resolve_latest_known_draw_prefers_a_newer_recorded_outcome_over_the_database(
    tmp_path: Path,
) -> None:
    database = _seed_local_draws_database(
        tmp_path / "lottolab-data", draw_number="115000078", draw_date="2026-08-11"
    )

    assert resolve_latest_known_draw(tmp_path, database) == "115000078"

    update_outcome(
        tmp_path,
        draw_number="115000079",
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=49,
        source="test-owner-entry",
        updated_at=datetime.fromisoformat("2026-08-15T02:21:09+08:00"),
    )

    assert resolve_latest_known_draw(tmp_path, database) == "115000079"
