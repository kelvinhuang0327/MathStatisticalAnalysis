"""Integration tests for the historical-results SQLite repository (BLHQ R1).

Every database in this file lives under pytest's own ``tmp_path`` and is
discarded automatically at test teardown; nothing here ever opens a
canonical or default production database.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from tests.fixtures.historical.builder import (
    CUTOFF_DRAW_NUMBER,
    CUTOFF_MAIN_NUMBERS,
    CUTOFF_SPECIAL_NUMBERS,
    REAL_STRATEGY_IDS,
    TARGET_DRAW_NUMBER,
    TARGET_MAIN_NUMBERS,
    TARGET_SPECIAL_NUMBERS,
    build_baseline_envelope,
    build_draw_snapshot,
    build_envelope,
    build_portfolio,
    build_strategy_descriptor,
    build_tickets,
    envelope_bytes,
)
from tests.fixtures.historical.builder import build_small_envelope as _build_small_envelope

from lottolab.application.use_cases.import_historical_results import ImportHistoricalResults
from lottolab.domain.historical_results import HistoricalRunImport, HistoricalRunStatus
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultRepository,
)
from lottolab.infrastructure.persistence.historical_schema import open_database
from lottolab.normalization.historical_import import verify_and_normalize_historical_import


def _normalized_import(envelope: dict[str, Any] | None = None) -> HistoricalRunImport:
    envelope = build_baseline_envelope() if envelope is None else envelope
    result = verify_and_normalize_historical_import(envelope_bytes(envelope))
    assert result.normalized_import is not None
    return result.normalized_import


def test_fresh_valid_import_creates_one_completed_run_and_all_six_table_rows(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    repository = SQLiteHistoricalResultRepository(database)
    use_case = ImportHistoricalResults(repository)
    run_import = _normalized_import()

    result = use_case(run_import)

    assert result.status is HistoricalRunStatus.COMPLETED
    assert result.is_idempotent_replay is False

    with open_database(database, read_only=True) as connection:
        run_count = connection.execute(
            "SELECT COUNT(*) FROM historical_result_run WHERE status = 'COMPLETED'"
        ).fetchone()[0]
        strategy_count = connection.execute(
            "SELECT COUNT(*) FROM historical_strategy_snapshot"
        ).fetchone()[0]
        draw_count = connection.execute("SELECT COUNT(*) FROM historical_draw_snapshot").fetchone()[
            0
        ]
        portfolio_count = connection.execute(
            "SELECT COUNT(*) FROM historical_portfolio"
        ).fetchone()[0]
        ticket_count = connection.execute("SELECT COUNT(*) FROM historical_ticket").fetchone()[0]
        summary_count = connection.execute(
            "SELECT COUNT(*) FROM historical_count_summary"
        ).fetchone()[0]

    assert run_count == 1
    assert strategy_count == len(run_import.strategy_descriptors)
    assert draw_count == len(run_import.draw_snapshots)
    assert portfolio_count == len(run_import.portfolios)
    assert ticket_count == len(run_import.portfolios) * 20
    distinct_strategy_snapshots = {
        (p.strategy_id, p.strategy_version, p.replicate) for p in run_import.portfolios
    }
    assert summary_count == len(distinct_strategy_snapshots) * 3


def test_exact_completed_reimport_is_idempotent_no_op(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    repository = SQLiteHistoricalResultRepository(database)
    run_import = _normalized_import()

    first = repository.commit_import(run_import)
    second = repository.commit_import(run_import)

    assert first.is_idempotent_replay is False
    assert second.is_idempotent_replay is True
    assert first.run_id == second.run_id
    with open_database(database, read_only=True) as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM historical_result_run").fetchone()[0]
    assert run_count == 1


def test_two_different_shape_envelopes_yield_distinct_identities_and_both_commit(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    repository = SQLiteHistoricalResultRepository(database)

    small_result = repository.commit_import(_normalized_import(_build_small_envelope()))
    big_result = repository.commit_import(_normalized_import(build_baseline_envelope()))

    assert small_result.import_identity_sha256 != big_result.import_identity_sha256
    assert small_result.status is HistoricalRunStatus.COMPLETED
    assert big_result.status is HistoricalRunStatus.COMPLETED
    with open_database(database, read_only=True) as connection:
        run_count = connection.execute(
            "SELECT COUNT(*) FROM historical_result_run WHERE status = 'COMPLETED'"
        ).fetchone()[0]
    assert run_count == 2


def test_mid_transaction_persistence_failure_leaves_zero_child_rows_and_one_failed_audit_row(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    repository = SQLiteHistoricalResultRepository(database)
    run_import = _normalized_import()
    # Bypass normalization's own duplicate-draw-number guard by constructing
    # the domain object directly, exercising the SQLite
    # UNIQUE(run_id, lottery_type, draw_number) constraint mid-transaction.
    tampered_draws = (*run_import.draw_snapshots, run_import.draw_snapshots[0])
    tampered = dataclasses.replace(run_import, draw_snapshots=tampered_draws)

    result = repository.commit_import(tampered)

    assert result.status is HistoricalRunStatus.FAILED
    assert result.error_code is not None
    with open_database(database, read_only=True) as connection:
        statuses = [
            row[0] for row in connection.execute("SELECT status FROM historical_result_run")
        ]
        strategy_count = connection.execute(
            "SELECT COUNT(*) FROM historical_strategy_snapshot"
        ).fetchone()[0]
        draw_count = connection.execute("SELECT COUNT(*) FROM historical_draw_snapshot").fetchone()[
            0
        ]
        portfolio_count = connection.execute(
            "SELECT COUNT(*) FROM historical_portfolio"
        ).fetchone()[0]
        ticket_count = connection.execute("SELECT COUNT(*) FROM historical_ticket").fetchone()[0]

    assert statuses == ["FAILED"]
    assert strategy_count == 0
    assert draw_count == 0
    assert portfolio_count == 0
    assert ticket_count == 0


def test_failed_attempt_may_later_retry_successfully(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    repository = SQLiteHistoricalResultRepository(database)
    run_import = _normalized_import()
    tampered_draws = (*run_import.draw_snapshots, run_import.draw_snapshots[0])
    tampered = dataclasses.replace(run_import, draw_snapshots=tampered_draws)

    failed = repository.commit_import(tampered)
    assert failed.status is HistoricalRunStatus.FAILED

    retried = repository.commit_import(run_import)
    assert retried.status is HistoricalRunStatus.COMPLETED
    assert retried.is_idempotent_replay is False

    with open_database(database, read_only=True) as connection:
        statuses = sorted(
            row[0] for row in connection.execute("SELECT status FROM historical_result_run")
        )
    assert statuses == ["COMPLETED", "FAILED"]


def test_same_draw_number_with_different_values_coexists_across_runs(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    repository = SQLiteHistoricalResultRepository(database)

    first_result = repository.commit_import(_normalized_import(build_baseline_envelope()))
    assert first_result.status is HistoricalRunStatus.COMPLETED

    different_target_main = (2, 3, 4, 5, 6, 7)
    draw_snapshots = [
        build_draw_snapshot(
            draw_number=CUTOFF_DRAW_NUMBER,
            draw_date="2026-01-01",
            main_numbers=CUTOFF_MAIN_NUMBERS,
            special_numbers=CUTOFF_SPECIAL_NUMBERS,
        ),
        build_draw_snapshot(
            draw_number=TARGET_DRAW_NUMBER,
            draw_date="2026-01-10",
            main_numbers=different_target_main,
            special_numbers=TARGET_SPECIAL_NUMBERS,
        ),
    ]
    strategy_descriptors = [
        build_strategy_descriptor(
            strategy_id=REAL_STRATEGY_IDS[0], identity_kind="REAL", governance_status="UNKNOWN"
        )
    ]
    portfolios = [
        build_portfolio(
            strategy_id=REAL_STRATEGY_IDS[0],
            tickets=build_tickets(
                target_main=different_target_main, target_special=TARGET_SPECIAL_NUMBERS
            ),
        )
    ]
    second_envelope = build_envelope(
        strategy_descriptors=strategy_descriptors,
        draw_snapshots=draw_snapshots,
        portfolios=portfolios,
    )
    second_result = repository.commit_import(_normalized_import(second_envelope))
    assert second_result.status is HistoricalRunStatus.COMPLETED

    with open_database(database, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT run_id, main_numbers_json FROM historical_draw_snapshot
            WHERE draw_number = ? ORDER BY run_id
            """,
            (str(TARGET_DRAW_NUMBER),),
        ).fetchall()
    assert len(rows) == 2
    assert {row[1] for row in rows} == {
        json.dumps(list(TARGET_MAIN_NUMBERS), separators=(",", ":")),
        json.dumps(list(different_target_main), separators=(",", ":")),
    }


def test_count_summary_rows_use_defined_ticket_tiers_and_m4plus_semantics(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    repository = SQLiteHistoricalResultRepository(database)
    run_import = _normalized_import()
    repository.commit_import(run_import)

    with open_database(database, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT c.ticket_count, c.evaluated_draws, c.complete_portfolios, c.m4plus_hit_count
            FROM historical_count_summary c
            """
        ).fetchall()

    assert {row[0] for row in rows} == {10, 15, 20}
    assert len(rows) == 5 * 3  # 5 distinct strategy_snapshots in the baseline fixture
    for ticket_count, evaluated_draws, complete_portfolios, m4plus_hit_count in rows:
        assert ticket_count in (10, 15, 20)
        assert evaluated_draws == 1
        assert complete_portfolios == 1
        # position-1 ticket always has 6 hits against TARGET_MAIN_NUMBERS in every
        # baseline portfolio, so every tier counts exactly one M4+ portfolio.
        assert m4plus_hit_count == 1
