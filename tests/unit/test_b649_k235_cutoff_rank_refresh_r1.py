from __future__ import annotations

import json

from lottolab.research.b649_k235_cutoff_rank_refresh_r1 import (
    INELIGIBLE_STATUS,
    ReplayCell,
    build_cutoff_rank_refresh,
)

DRAW_096 = "115000096"
DRAW_097 = "115000097"
DRAW_098 = "115000098"
DRAW_099 = "115000099"


def _history(
    strategies: dict[str, tuple[int, str]], draws: list[str]
) -> dict[str, object]:
    return {
        "ids": {
            strategy_id: [k_value, name]
            for strategy_id, (k_value, name) in strategies.items()
        },
        "cutoffs": draws,
        "hist": {},
    }


def _cell(
    strategy_id: str,
    k_value: int,
    draw: str,
    success: bool | None,
    *,
    status: str = "COMPLETE",
) -> ReplayCell:
    return ReplayCell(
        strategy_id=strategy_id,
        target_draw_number=draw,
        native_ticket_count=k_value,
        replay_status=status,
        official_any_prize=success,
    )


def _three_per_k_fixture() -> tuple[dict[str, object], list[ReplayCell]]:
    draws = [DRAW_096, DRAW_097, DRAW_098, DRAW_099]
    strategies: dict[str, tuple[int, str]] = {}
    cells: list[ReplayCell] = []
    for k_value in (2, 3, 5):
        for label in ("a", "b", "c"):
            strategy_id = f"k{k_value}_{label}"
            strategies[strategy_id] = (k_value, strategy_id)
            for draw in draws:
                if label == "a":
                    success = draw == DRAW_096
                elif label == "b":
                    success = draw != DRAW_096
                else:
                    success = False
                cells.append(_cell(strategy_id, k_value, draw, success))
    return _history(strategies, draws), cells


def test_cutoff_is_inclusive_and_later_outcomes_do_not_leak() -> None:
    history, cells = _three_per_k_fixture()
    at_096 = build_cutoff_rank_refresh(history, cells, DRAW_096)
    at_099 = build_cutoff_rank_refresh(history, cells, DRAW_099)

    assert at_096["cutoff"]["actual_cutoff_applied"] == DRAW_096
    assert at_096["cutoff"]["future_draw_count_excluded"] == 3
    assert at_096["cutoff"]["future_outcomes_used"] is False
    assert at_099["cutoff"]["actual_cutoff_applied"] == DRAW_099
    for k_value in (2, 3, 5):
        early_top = at_096["rankings"][f"K{k_value}"]["top3"]
        later_top = at_099["rankings"][f"K{k_value}"]["top3"]
        assert early_top[0]["strategy_id"] == f"k{k_value}_a"
        assert later_top[0]["strategy_id"] == f"k{k_value}_b"
        assert early_top[0]["windows"]["FULL"]["effective_denominator"] == 1
        assert early_top[0]["windows"]["50"]["effective_denominator"] == 1
        assert later_top[0]["windows"]["FULL"]["effective_denominator"] == 4
        assert later_top[0]["windows"]["1500"]["effective_denominator"] == 4

    changed_future = [
        ReplayCell(
            strategy_id=cell.strategy_id,
            target_draw_number=cell.target_draw_number,
            native_ticket_count=cell.native_ticket_count,
            replay_status=cell.replay_status,
            official_any_prize=(
                not cell.official_any_prize
                if cell.target_draw_number > DRAW_096
                else cell.official_any_prize
            ),
        )
        for cell in cells
    ]
    early_with_changed_future = build_cutoff_rank_refresh(
        history, changed_future, DRAW_096
    )
    assert json.loads(json.dumps(at_096)) == json.loads(
        json.dumps(early_with_changed_future)
    )


def test_ties_use_denominator_then_strategy_id_and_missing_is_not_zero() -> None:
    strategies = {
        "a_short": (2, "A short sample"),
        "b_long": (2, "B long sample"),
        "c_short": (2, "C short sample"),
        "z_no_data": (2, "No data"),
    }
    cells = [
        _cell("b_long", 2, DRAW_096, True),
        _cell("b_long", 2, DRAW_097, True),
        _cell("a_short", 2, DRAW_096, None, status=INELIGIBLE_STATUS),
        _cell("a_short", 2, DRAW_097, True),
        _cell("c_short", 2, DRAW_096, None, status=INELIGIBLE_STATUS),
        _cell("c_short", 2, DRAW_097, True),
    ]
    artifact = build_cutoff_rank_refresh(
        _history(strategies, [DRAW_096, DRAW_097]), cells, DRAW_097
    )

    ranked_ids = [
        row["strategy_id"] for row in artifact["rankings"]["K2"]["top3"]
    ]
    assert ranked_ids == ["b_long", "a_short", "c_short"]
    rows = {row["strategy_id"]: row for row in artifact["strategies"]}
    assert rows["b_long"]["windows"]["FULL"]["effective_denominator"] == 2
    assert rows["a_short"]["windows"]["FULL"]["effective_denominator"] == 1
    assert rows["z_no_data"]["ranking_status"] == "MISSING"
    assert rows["z_no_data"]["windows"]["FULL"]["success_rate"] is None
    assert rows["z_no_data"]["windows"]["FULL"]["effective_denominator"] == 0


def test_fatal_replay_status_is_reported_as_missing_without_rate() -> None:
    strategies = {
        "has_data": (2, "Has data"),
        "failed": (2, "Failed"),
    }
    cells = [
        _cell("has_data", 2, DRAW_096, True),
        _cell("failed", 2, DRAW_096, None, status="EXECUTION_FAILURE"),
    ]
    artifact = build_cutoff_rank_refresh(
        _history(strategies, [DRAW_096]), cells, DRAW_096
    )
    failed = next(row for row in artifact["strategies"] if row["strategy_id"] == "failed")

    assert failed["ranking_status"] == "MISSING"
    assert failed["missing_reason"] == "FATAL_REPLAY_STATUS_PRESENT"
    assert failed["windows"]["FULL"]["success_rate"] is None
    assert artifact["rankings"]["K2"]["missing_strategy_ids"] == ["failed"]


def test_cutoff_without_any_outcome_data_returns_missing() -> None:
    strategies = {"candidate": (2, "Candidate")}
    artifact = build_cutoff_rank_refresh(
        _history(strategies, [DRAW_096]),
        [_cell("candidate", 2, DRAW_096, True)],
        DRAW_099,
    )

    assert artifact["status"] == "MISSING"
    assert artifact["cutoff"]["actual_cutoff_applied"] is None
    assert artifact["cutoff"]["latest_evidence_draw_number"] == DRAW_096
    assert artifact["strategy_pool"]["missing_strategy_count"] == 1
    assert artifact["rankings"]["K2"]["top3"] == []
    assert artifact["strategies"][0]["ranking_status"] == "MISSING"
    assert artifact["strategies"][0]["windows"] == {}
