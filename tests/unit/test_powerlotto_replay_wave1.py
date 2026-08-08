"""Task-owned POWER_LOTTO replay, coverage, and idempotence tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from lottolab.research.powerlotto_wave1 import (
    TARGET_STATUS_EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE,
    PowerLottoDrawRecord,
    run_replay,
)
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGIES
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

    # Each strategy's own effective minimum is the max of its declared
    # min_history and the second-zone SSOT's MIN_HISTORY; strategies differ
    # (e.g. power_fourier_rhythm_2bet needs 100), so eligibility is computed
    # per strategy rather than from one shared global threshold.
    effective_minimums = {
        spec.strategy_id: max(MIN_HISTORY, spec.min_history) for spec in WAVE1_STRATEGIES
    }
    eligible_counts = {
        strategy_id: max(0, len(draws) - minimum)
        for strategy_id, minimum in effective_minimums.items()
    }
    expected_tickets = sum(
        eligible_counts[spec.strategy_id] * spec.native_ticket_count for spec in WAVE1_STRATEGIES
    )
    expected_excluded = sum(
        len(draws) - eligible_counts[spec.strategy_id] for spec in WAVE1_STRATEGIES
    )
    assert first.complete_target_count == sum(eligible_counts.values())
    assert first.excluded_target_count == expected_excluded
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


def test_replay_accounts_source_native_portfolio_closure_without_failure(
    tmp_path: Path,
) -> None:
    start = date(2026, 1, 1)
    draws = tuple(
        PowerLottoDrawRecord(
            draw_number=str(index + 1),
            draw_date=(start + timedelta(days=index)).isoformat(),
            main_numbers=tuple(
                sorted(((index + offset * 3) % 38) + 1 for offset in range(6))
            ),
            second_number=(index % 8) + 1,
            source_reference="synthetic-source-native-closure",
        )
        for index in range(51)
    )
    spec = next(
        spec for spec in WAVE2_STRATEGIES if spec.strategy_id == "power_apriori_ext_4bet"
    )

    first = run_replay(
        draws=draws,
        strategy_objects=(spec,),
        runtime_root=tmp_path,
        selected_strategy_ids=(spec.strategy_id,),
    )
    first_db_sha256 = hashlib.sha256(first.db_path.read_bytes()).hexdigest()
    second = run_replay(
        draws=draws,
        strategy_objects=(spec,),
        runtime_root=tmp_path,
        selected_strategy_ids=(spec.strategy_id,),
    )

    assert first == second
    assert hashlib.sha256(second.db_path.read_bytes()).hexdigest() == first_db_sha256
    assert first.eligible_attempt_count == 1
    assert first.complete_target_count == 0
    assert first.excluded_target_count == 51
    assert first.failed_target_count == 0
    assert first.ticket_count == 0

    with sqlite3.connect(first.db_path) as connection:
        statuses = dict(
            connection.execute(
                "SELECT status, COUNT(*) FROM strategy_targets GROUP BY status"
            ).fetchall()
        )
        assert statuses == {
            "EXCLUDED_INSUFFICIENT_HISTORY": 50,
            TARGET_STATUS_EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE: 1,
        }
        target = connection.execute(
            """
            SELECT target_draw_number, cutoff_draw_number, cutoff_index,
                   expected_ticket_count, status, failure_reason
            FROM strategy_targets
            WHERE status = ?
            """,
            (TARGET_STATUS_EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE,),
        ).fetchone()
        assert target[:5] == (
            "51",
            "50",
            50,
            4,
            TARGET_STATUS_EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE,
        )
        assert target[5].startswith("SourceNativePortfolioClosure: ")

    coverage = json.loads((tmp_path / "strategy_coverage.json").read_text(encoding="utf-8"))
    assert coverage["completion_accounting"] == {
        "selected": 1,
        "eligible_attempts": 1,
        "complete": 0,
        "excluded": 51,
        "failed": 0,
    }
    assert coverage["strategies"][0]["status"] == "COMPLETE"
    assert coverage["strategies"][0]["eligible_targets"] == 1
