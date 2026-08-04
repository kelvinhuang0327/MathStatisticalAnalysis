"""Task-owned POWER_LOTTO replay, coverage, and idempotence tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from lottolab.research.powerlotto_wave1 import (
    PowerLottoDrawRecord,
    run_replay,
)
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES
from lottolab.strategies.powerlotto_second_zone import MIN_HISTORY


def _draws(count: int = 80) -> tuple[PowerLottoDrawRecord, ...]:
    start = date(2026, 1, 1)
    return tuple(
        PowerLottoDrawRecord(
            draw_number=str(index + 1),
            draw_date=(start + timedelta(days=index)).isoformat(),
            main_numbers=tuple(sorted(((index * 7 + offset * 5) % 38) + 1 for offset in range(6))),
            second_number=(index % 8) + 1,
            source_reference="synthetic-test-source",
        )
        for index in range(count)
    )


def test_replay_writes_complete_native_portfolios_and_is_idempotent(tmp_path: Path) -> None:
    draws = _draws()
    first = run_replay(
        draws=draws,
        strategy_objects=WAVE1_STRATEGIES,
        runtime_root=tmp_path,
    )
    first_db_sha256 = hashlib.sha256(first.db_path.read_bytes()).hexdigest()
    second = run_replay(
        draws=draws,
        strategy_objects=WAVE1_STRATEGIES,
        runtime_root=tmp_path,
    )
    second_db_sha256 = hashlib.sha256(second.db_path.read_bytes()).hexdigest()

    assert first.run_id == second.run_id
    assert first.source_sha256 == second.source_sha256
    assert first.failed_target_count == second.failed_target_count == 0
    assert first.complete_target_count == second.complete_target_count
    assert first.ticket_count == second.ticket_count
    assert first_db_sha256 == second_db_sha256

    effective_minimum = max(MIN_HISTORY, *(spec.min_history for spec in WAVE1_STRATEGIES))
    eligible_per_strategy = max(0, len(draws) - effective_minimum)
    expected_tickets = eligible_per_strategy * sum(
        spec.native_ticket_count for spec in WAVE1_STRATEGIES
    )
    assert first.complete_target_count == eligible_per_strategy * len(WAVE1_STRATEGIES)
    assert first.excluded_target_count == effective_minimum * len(WAVE1_STRATEGIES)
    assert first.ticket_count == expected_tickets

    with sqlite3.connect(first.db_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM strategy_targets WHERE status = 'COMPLETE'"
            ).fetchone()[0]
            == first.complete_target_count
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == first.ticket_count
        )
        assert connection.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == first.ticket_count
        replay_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(replay_output)").fetchall()
        }
        assert {
            "run_id",
            "lottery_type",
            "strategy_id",
            "strategy_version",
            "target_draw_number",
            "cutoff_draw_number",
            "native_ticket_count",
            "ticket_position",
            "predicted_main_numbers_json",
            "predicted_second_number",
            "zone1_hits",
            "zone2_hit",
            "status",
            "failure_reason",
            "provenance",
            "ssot_version",
            "source_commit",
        } <= replay_columns
        assert (
            connection.execute("SELECT COUNT(*) FROM replay_output").fetchone()[0]
            == first.ticket_count
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM replay_output WHERE lottery_type != 'POWER_LOTTO'"
            ).fetchone()[0]
            == 0
        )
        assert connection.execute("SELECT COUNT(DISTINCT draw_number) FROM draws").fetchone()[
            0
        ] == len(draws)
        assert (
            connection.execute(
                """
            SELECT COUNT(*) FROM strategy_targets AS target
            JOIN strategy_ledger AS ledger
              ON ledger.run_id = target.run_id
             AND ledger.strategy_id = target.strategy_id
             AND ledger.strategy_version = target.strategy_version
            WHERE ledger.lottery_type = 'POWER_LOTTO'
            """
            ).fetchone()[0]
            == first.complete_target_count + first.excluded_target_count
        )

        duplicate_keys = connection.execute(
            """
            SELECT COUNT(*) - COUNT(DISTINCT run_id || ':' || strategy_id || ':' ||
                strategy_version || ':' || target_draw_number || ':' || ticket_position)
            FROM tickets
            """
        ).fetchone()[0]
        assert duplicate_keys == 0
        first_target = connection.execute(
            """
            SELECT cutoff_index, cutoff_draw_number, target_draw_number
            FROM strategy_targets
            WHERE status = 'COMPLETE'
            ORDER BY cutoff_index, strategy_id
            LIMIT 1
            """
        ).fetchone()
        assert first_target == (MIN_HISTORY, str(MIN_HISTORY), str(MIN_HISTORY + 1))

    summary = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["lottery_type"] == "POWER_LOTTO"
    assert summary["deterministic_identity"]
    assert (tmp_path / "strategy_coverage.json").exists()
    assert (tmp_path / "failure_ledger.json").exists()
    assert (tmp_path / "source_ledger.json").exists()
    assert (tmp_path / "second_zone_contract.json").exists()


def test_replay_rejects_a_database_outside_the_task_runtime(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inside the task runtime root"):
        run_replay(
            draws=_draws(40),
            strategy_objects=WAVE1_STRATEGIES,
            runtime_root=tmp_path,
            db_path=tmp_path.parent / "outside-p638.sqlite3",
        )
