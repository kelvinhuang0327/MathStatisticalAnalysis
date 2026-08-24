"""Focused acceptance tests for the T539/P638 shared-core adapters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import cast

import pytest
from tools.p638_forward_auto_cycle_adapter import (
    P638_ENABLED_STRATEGY_IDS,
    P638_STRATEGY_STREAMS,
    P638ForwardAutoCycleAdapter,
)
from tools.t539_forward_auto_cycle_adapter import (
    T539_ENABLED_STRATEGY_IDS,
    T539_STRATEGY_STREAMS,
    T539ForwardAutoCycleAdapter,
)

from lottolab.application.forward_auto_cycle_core import ForwardAutoCycleCore
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.forward_auto_cycle_operational import (
    ForwardCycleHistorySnapshot,
    ForwardCycleStrategyStream,
    ForwardCycleTarget,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.powerlotto_wave1 import P638HistoryRow

_CLOCK = datetime.fromisoformat("2026-08-18T19:00:00+08:00")


class _T539Single:
    strategy_id = "daily539_markov_cold"
    strategy_version = "v0.1"

    def get_one_bet(
        self, _history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]:
        assert lottery_type is LotteryType.DAILY_539
        return (1, 2, 3, 4, 5), None


class _T539Failing:
    strategy_id = "markov_1bet_539"
    strategy_version = "v0.1-p36"

    def get_one_bet(
        self, _history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]:
        assert lottery_type is LotteryType.DAILY_539
        raise RuntimeError("synthetic T539 failure")


class _P638Portfolio:
    strategy_id = "zonal_entropy_2bet"
    strategy_version = "v0.1-p638-wave1"

    def get_bets(
        self, _history: object, lottery_type: LotteryType
    ) -> tuple[tuple[tuple[int, ...], int], ...]:
        assert lottery_type is LotteryType.POWER_LOTTO
        return (
            ((1, 2, 3, 4, 5, 6), 3),
            ((7, 8, 9, 10, 11, 12), 4),
        )


def _stream(
    strategy_id: str,
    strategy_version: str,
    factory: Callable[[], object],
    native_ticket_count: int,
) -> ForwardCycleStrategyStream:
    return ForwardCycleStrategyStream(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        enabled=True,
        adapter_factory=factory,
        native_ticket_count=native_ticket_count,
    )


def _t539_target() -> ForwardCycleTarget:
    return ForwardCycleTarget(
        lottery_type="DAILY_539",
        draw_number="115000081",
        draw_date="2026-08-18",
        scheduled_at="2026-08-18T20:30:00+08:00",
    )


def _p638_target() -> ForwardCycleTarget:
    return ForwardCycleTarget(
        lottery_type="POWER_LOTTO",
        draw_number="115000081",
        draw_date="2026-08-18",
        scheduled_at="2026-08-18T20:30:00+08:00",
    )


def _t539_history(*, stale: bool = False) -> ForwardCycleHistorySnapshot[CausalDrawRow]:
    row = CausalDrawRow(draw="115000080", date="2026-08-15", numbers=(1, 2, 3, 4, 5))
    return ForwardCycleHistorySnapshot(
        rows=(row,),
        cutoff_draw="115000080",
        cutoff_date="2026-08-15",
        draw_count=1,
        history_sha256="1" * 64,
        latest_known_draw_at_prediction_time="115000081" if stale else "115000080",
        history_lag_draws=1 if stale else 0,
        freshness_status="STALE_HISTORY" if stale else "FRESH",
        freshness_warning="LATEST_DRAW_NOT_INCLUDED" if stale else "NONE",
    )


def _p638_history() -> ForwardCycleHistorySnapshot[P638HistoryRow]:
    row = P638HistoryRow(
        draw="115000080",
        date="2026-08-15",
        numbers=(1, 2, 3, 4, 5, 6),
        second_number=2,
    )
    return ForwardCycleHistorySnapshot(
        rows=(row,),
        cutoff_draw="115000080",
        cutoff_date="2026-08-15",
        draw_count=1,
        history_sha256="2" * 64,
        latest_known_draw_at_prediction_time="115000080",
        history_lag_draws=0,
        freshness_status="FRESH",
        freshness_warning="NONE",
    )


def _t539_outcome(numbers: tuple[int, ...]) -> dict[str, object]:
    return {
        "lottery_type": "DAILY_539",
        "draw_number": "115000081",
        "draw_date": "2026-08-18",
        "main_numbers": list(numbers),
        "source": "official:test",
    }


def _p638_outcome(
    zone1: tuple[int, ...], zone2: int
) -> dict[str, object]:
    return {
        "lottery_type": "POWER_LOTTO",
        "draw_number": "115000081",
        "draw_date": "2026-08-18",
        "zone1_numbers": list(zone1),
        "zone2_number": zone2,
        "source": "official:test",
    }


def test_t539_preserves_native_ticket_shape_and_correction_rescores_without_rewriting_prediction(
    tmp_path: Path,
) -> None:
    official = {"value": _t539_outcome((1, 2, 3, 4, 5))}
    adapter = T539ForwardAutoCycleAdapter(
        tmp_path,
        target=_t539_target(),
        streams=(
            _stream(
                "daily539_markov_cold",
                "v0.1",
                _T539Single,
                1,
            ),
        ),
        history_builder=lambda _target: _t539_history(),
        official_outcome_resolver=lambda _target: official["value"],
        clock=lambda: _CLOCK,
    )

    first = ForwardAutoCycleCore(adapter).run()
    first_prediction = cast_dict(first.created_predictions[0])
    prediction_path = Path(cast_str(first_prediction["prediction_path"]))
    prediction_before = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    prediction = _read(prediction_path)
    assert prediction["history_cutoff"] == {
        "draw_number": "115000080",
        "draw_date": "2026-08-15",
    }
    assert prediction["latest_known_draw_at_prediction_time"] == "115000080"
    assert prediction["history_lag_draws"] == 0
    assert prediction["freshness_status"] == "FRESH"
    assert prediction["tickets"] == [
        {"ticket_position": 1, "predicted_numbers": [1, 2, 3, 4, 5]}
    ]
    assert first.outcome_status == "NEW_OUTCOME"
    first_score = _read(next((tmp_path / "scores").rglob("*.json")))
    first_ticket_score = cast_list(first_score["ticket_scores"])[0]
    assert first_ticket_score["main_hits"] == 5
    assert first_ticket_score["official_prize_tier"] == "FIRST"

    second = ForwardAutoCycleCore(adapter).run()
    assert second.created_predictions == ()
    assert second.outcome_status == "IDENTICAL_OUTCOME"
    assert second.next_action == "NO_OP"
    assert hashlib.sha256(prediction_path.read_bytes()).hexdigest() == prediction_before

    official["value"] = _t539_outcome((6, 7, 8, 9, 10))
    corrected = ForwardAutoCycleCore(adapter).run()
    assert corrected.outcome_status == "CORRECTED_OUTCOME"
    assert corrected.rescore_results
    corrected_score = _read(next((tmp_path / "scores").rglob("*.json")))
    assert corrected_score["outcome_revision"] == 2
    assert cast_list(corrected_score["ticket_scores"])[0]["main_hits"] == 0
    assert hashlib.sha256(prediction_path.read_bytes()).hexdigest() == prediction_before


def test_t539_strategy_failure_is_recorded_and_does_not_block_sibling(tmp_path: Path) -> None:
    adapter = T539ForwardAutoCycleAdapter(
        tmp_path,
        target=_t539_target(),
        streams=(
            _stream("markov_1bet_539", "v0.1-p36", _T539Failing, 1),
            _stream("daily539_markov_cold", "v0.1", _T539Single, 1),
        ),
        history_builder=lambda _target: _t539_history(),
        clock=lambda: _CLOCK,
    )

    result = ForwardAutoCycleCore(adapter).run()

    by_strategy = {
        cast_str(cast_dict(prediction)["strategy_id"]): cast_dict(prediction)
        for prediction in result.created_predictions
    }
    assert by_strategy["markov_1bet_539"]["availability"] == "TECHNICAL_FAILURE"
    assert "synthetic T539 failure" in cast_str(
        by_strategy["markov_1bet_539"]["unavailable_reason"]
    )
    assert by_strategy["daily539_markov_cold"]["availability"] == "AVAILABLE"


def test_p638_preserves_zone1_zone2_positions_and_uses_official_scoring(
    tmp_path: Path,
) -> None:
    adapter = P638ForwardAutoCycleAdapter(
        tmp_path,
        target=_p638_target(),
        streams=(
            _stream(
                "zonal_entropy_2bet",
                "v0.1-p638-wave1",
                _P638Portfolio,
                2,
            ),
        ),
        history_builder=lambda _target: _p638_history(),
        official_outcome_resolver=lambda _target: _p638_outcome(
            (1, 2, 3, 4, 5, 6), 3
        ),
        clock=lambda: _CLOCK,
    )

    result = ForwardAutoCycleCore(adapter).run()
    prediction = result.created_predictions[0]
    assert prediction["tickets"] == [
        {
            "ticket_position": 1,
            "zone1_numbers": [1, 2, 3, 4, 5, 6],
            "zone2_number": 3,
            "predicted_numbers": [1, 2, 3, 4, 5, 6],
            "predicted_special_number": 3,
        },
        {
            "ticket_position": 2,
            "zone1_numbers": [7, 8, 9, 10, 11, 12],
            "zone2_number": 4,
            "predicted_numbers": [7, 8, 9, 10, 11, 12],
            "predicted_special_number": 4,
        },
    ]
    score = _read(next((tmp_path / "scores").rglob("*.json")))
    ticket_scores = sorted(
        cast_list(score["ticket_scores"]),
        key=lambda ticket: cast_int(ticket["ticket_position"]),
    )
    assert ticket_scores[0]["zone1_hits"] == 6
    assert ticket_scores[0]["zone2_hit"] is True
    assert ticket_scores[0]["official_prize_tier"] == "FIRST"
    assert ticket_scores[1]["zone1_hits"] == 0
    assert ticket_scores[1]["zone2_hit"] is False


def test_stale_history_warns_but_does_not_block_t539_prediction(tmp_path: Path) -> None:
    adapter = T539ForwardAutoCycleAdapter(
        tmp_path,
        target=_t539_target(),
        streams=(_stream("daily539_markov_cold", "v0.1", _T539Single, 1),),
        history_builder=lambda _target: _t539_history(stale=True),
        clock=lambda: _CLOCK,
    )

    result = ForwardAutoCycleCore(adapter).run()

    assert len(result.created_predictions) == 1
    assert result.warnings == ("LATEST_DRAW_NOT_INCLUDED",)
    assert result.next_action == "PREDICTIONS_CREATED_WAITING_FOR_OUTCOME"


def test_shared_default_target_resolution_ignores_unfinished_prediction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "missing-database.db"
    ForwardAutoCycleCore(
        T539ForwardAutoCycleAdapter(
            tmp_path,
            database=database,
            target=_t539_target(),
            streams=(
                _stream("daily539_markov_cold", "v0.1", _T539Single, 1),
            ),
            history_builder=lambda _target: _t539_history(),
            official_outcome_resolver=lambda _target: None,
            clock=lambda: _CLOCK,
        )
    ).run()
    canonical_target = ForwardCycleTarget(
        lottery_type="DAILY_539",
        draw_number="115000080",
        draw_date="2026-08-17",
        scheduled_at="2026-08-17T20:30:00+08:00",
    )
    adapter = T539ForwardAutoCycleAdapter(
        tmp_path,
        database=database,
        streams=(
            _stream("daily539_markov_cold", "v0.1", _T539Single, 1),
        ),
        history_builder=lambda _target: _t539_history(),
        clock=lambda: _CLOCK,
    )
    monkeypatch.setattr(
        adapter,
        "_resolve_canonical_future_target",
        lambda: canonical_target,
    )

    assert adapter.resolve_next_target() == canonical_target


def test_operation_roots_isolate_lotteries_and_reject_cross_owner_reuse(tmp_path: Path) -> None:
    t539_root = tmp_path / "t539"
    p638_root = tmp_path / "p638"
    t539 = T539ForwardAutoCycleAdapter(
        t539_root,
        target=_t539_target(),
        streams=(_stream("daily539_markov_cold", "v0.1", _T539Single, 1),),
        history_builder=lambda _target: _t539_history(),
        clock=lambda: _CLOCK,
    )
    p638 = P638ForwardAutoCycleAdapter(
        p638_root,
        target=_p638_target(),
        streams=(_stream("zonal_entropy_2bet", "v0.1-p638-wave1", _P638Portfolio, 2),),
        history_builder=lambda _target: _p638_history(),
        clock=lambda: _CLOCK,
    )
    ForwardAutoCycleCore(t539).run()
    ForwardAutoCycleCore(p638).run()

    assert not (t539_root / "predictions" / "115000081" / "zonal_entropy_2bet").exists()
    assert not (p638_root / "predictions" / "115000081" / "daily539_markov_cold").exists()
    assert _read(t539_root / "config.json")["lottery_type"] == "DAILY_539"
    assert _read(p638_root / "config.json")["lottery_type"] == "POWER_LOTTO"

    with_same_root = P638ForwardAutoCycleAdapter(
        t539_root,
        target=_p638_target(),
        streams=(_stream("zonal_entropy_2bet", "v0.1-p638-wave1", _P638Portfolio, 2),),
        history_builder=lambda _target: _p638_history(),
        clock=lambda: _CLOCK,
    )
    try:
        ForwardAutoCycleCore(with_same_root).run()
    except ValueError as exc:
        assert "another lottery" in str(exc)
    else:
        raise AssertionError("cross-lottery root reuse must fail closed")


def test_enabled_streams_are_existing_canonical_adapter_identities() -> None:
    assert (
        tuple(stream.strategy_id for stream in T539_STRATEGY_STREAMS)
        == T539_ENABLED_STRATEGY_IDS
    )
    assert (
        tuple(stream.strategy_id for stream in P638_STRATEGY_STREAMS)
        == P638_ENABLED_STRATEGY_IDS
    )
    assert T539_ENABLED_STRATEGY_IDS == (
        "daily539_markov_cold",
        "daily539_f4cold_3bet",
    )
    assert P638_ENABLED_STRATEGY_IDS == (
        "zonal_entropy_2bet",
        "power_orthogonal_5bet",
    )


def test_shared_core_has_no_lottery_specific_scoring_rules() -> None:
    core_source = Path(
        "src/lottolab/application/forward_auto_cycle_core.py"
    ).read_text(encoding="utf-8")
    assert "B649" not in core_source
    assert "T539" not in core_source
    assert "P638" not in core_source
    assert "evaluate_" not in core_source


def _read(path: Path) -> dict[str, object]:
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    assert type(parsed) is dict
    return cast(dict[str, object], parsed)


def cast_dict(value: object) -> dict[str, object]:
    assert type(value) is dict
    return cast(dict[str, object], value)


def cast_str(value: object) -> str:
    assert type(value) is str
    return value


def cast_int(value: object) -> int:
    assert type(value) is int
    return value


def cast_list(value: object) -> list[dict[str, object]]:
    assert type(value) is list
    values = cast(list[object], value)
    result: list[dict[str, object]] = []
    for item in values:
        assert type(item) is dict
        result.append(cast_dict(cast(object, item)))
    return result
