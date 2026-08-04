from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import pytest
from tools.run_daily539_t539_wave1 import (
    LOTTERY_TYPE,
    RUN_ID,
    SourceDraw,
    StrategySpec,
    run_batch,
)

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow


def _draws(count: int = 9) -> tuple[SourceDraw, ...]:
    start = date(2020, 1, 1)
    return tuple(
        SourceDraw(
            draw_id=str(1000 + index),
            draw_date=(start + timedelta(days=index)).isoformat(),
            numbers=tuple(sorted(((index + step * 8) % 39) + 1 for step in range(5))),
        )
        for index in range(count)
    )


class _GoodPortfolio:
    strategy_id = "test_good_portfolio"
    strategy_name = "test good"
    strategy_version = "v-test"
    min_history = 3
    native_ticket_count = 2

    def get_bets(self, history: object, lottery_type: LotteryType) -> tuple[tuple[int, ...], ...]:
        assert lottery_type is LotteryType.DAILY_539
        rows = cast(tuple[CausalDrawRow, ...], history)
        return (rows[-1].numbers, (1, 2, 3, 4, 5))


class _FailingPortfolio(_GoodPortfolio):
    strategy_id = "test_failing_portfolio"

    def get_bets(self, history: object, lottery_type: LotteryType) -> tuple[tuple[int, ...], ...]:
        rows = cast(tuple[CausalDrawRow, ...], history)
        if len(rows) >= 5:
            raise RuntimeError("synthetic adapter failure")
        return super().get_bets(history, lottery_type)


def _spec(adapter: type[_GoodPortfolio], strategy_id: str) -> StrategySpec:
    return StrategySpec(
        strategy_id=strategy_id,
        strategy_name=strategy_id,
        strategy_version="v-test",
        lottery_type=LOTTERY_TYPE,
        min_history=3,
        native_ticket_count=2,
        adapter_factory=adapter,
        adapter_source_paths=("tests/unit/test_daily539_t539_wave1_runner.py",),
        selection_reason="synthetic runner contract",
    )


def _run_specs() -> tuple[StrategySpec, ...]:
    return (
        _spec(_GoodPortfolio, _GoodPortfolio.strategy_id),
        _spec(_FailingPortfolio, _FailingPortfolio.strategy_id),
    )


def _count(db_path: Path, sql: str, parameters: tuple[object, ...] = ()) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute(sql, parameters).fetchone()[0])


def test_batch_is_resumable_idempotent_and_reconciles_native_rows(tmp_path: Path) -> None:
    draws = _draws()
    runtime_root = tmp_path / "runtime"
    specs = _run_specs()

    partial = run_batch(
        runtime_root,
        draws,
        adapter_source_commit="adapter-commit-test",
        as_of_date="2020-01-09",
        specs=specs,
        max_targets_per_strategy=2,
    )
    assert partial["status"] == "PARTIAL"
    assert (runtime_root / "t539_wave1.sqlite3").exists()
    resumed = run_batch(
        runtime_root,
        draws,
        adapter_source_commit="adapter-commit-test",
        as_of_date="2020-01-09",
        specs=specs,
    )
    assert resumed["status"] == "COMPLETE"
    assert resumed["failure_count"] == 4

    db_path = runtime_root / "t539_wave1.sqlite3"
    assert _count(db_path, "SELECT COUNT(*) FROM source_draws") == 9
    assert _count(db_path, "SELECT COUNT(*) FROM target_completion") == 12
    assert _count(db_path, "SELECT COUNT(*) FROM prediction_tickets") == 24
    assert _count(db_path, "SELECT COUNT(*) FROM prediction_scores") == 16
    assert _count(db_path, "SELECT COUNT(*) FROM failure_ledger") == 4
    assert (
        _count(
            db_path,
            "SELECT COUNT(*) FROM (SELECT run_id, strategy_id, strategy_version, target_draw_id, "
            "ticket_position FROM prediction_tickets GROUP BY run_id, strategy_id, "
            "strategy_version, target_draw_id, ticket_position HAVING COUNT(*) > 1)",
        )
        == 0
    )
    assert (
        _count(db_path, "SELECT COUNT(*) FROM prediction_tickets WHERE execution_status = 'FAILED'")
        == 8
    )
    assert (
        _count(
            db_path,
            "SELECT COUNT(*) FROM prediction_tickets WHERE execution_status = 'FAILED' "
            "AND main_numbers_json IS NULL",
        )
        == 8
    )

    with sqlite3.connect(db_path) as connection:
        causal_row = connection.execute(
            "SELECT target_draw_id, cutoff_draw_id, main_numbers_json FROM prediction_tickets "
            "WHERE strategy_id = ? AND target_draw_id = ? AND ticket_position = 1",
            (_GoodPortfolio.strategy_id, "1003"),
        ).fetchone()
    assert causal_row == ("1003", "1002", json.dumps([3, 11, 19, 27, 35], separators=(",", ":")))

    before = db_path.read_bytes()
    again = run_batch(
        runtime_root,
        draws,
        adapter_source_commit="adapter-commit-test",
        as_of_date="2020-01-09",
        specs=specs,
    )
    assert again["status"] == "COMPLETE"
    assert db_path.read_bytes() == before

    reports = json.loads((runtime_root / "run_summary.json").read_text(encoding="utf-8"))
    assert reports["run_id"] == RUN_ID
    assert reports["status"] == "COMPLETE"
    assert len(json.loads((runtime_root / "failure_ledger.json").read_text(encoding="utf-8"))) == 4


def test_runner_rejects_non_daily539_specs_and_future_draws(tmp_path: Path) -> None:
    draws = _draws()
    bad_spec = StrategySpec(
        strategy_id="bad-lottery",
        strategy_name="bad",
        strategy_version="v1",
        lottery_type=LotteryType.BIG_LOTTO.value,
        min_history=3,
        native_ticket_count=1,
        adapter_factory=_GoodPortfolio,
        adapter_source_paths=("test",),
        selection_reason="test",
    )
    with pytest.raises(ValueError, match="DAILY_539 strategies only"):
        run_batch(
            tmp_path / "wrong-lottery",
            draws,
            adapter_source_commit="test",
            as_of_date="2020-01-09",
            specs=(bad_spec,),
        )

    future_draws = (*draws[:-1], SourceDraw("9999", "2020-01-10", draws[-1].numbers))
    with pytest.raises(ValueError, match="after the authorized as-of date"):
        run_batch(
            tmp_path / "future",
            future_draws,
            adapter_source_commit="test",
            as_of_date="2020-01-09",
            specs=_run_specs(),
        )
