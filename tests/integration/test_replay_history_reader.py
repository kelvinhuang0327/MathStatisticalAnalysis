"""Temporary-DB integration tests for SQLiteDrawHistoryReader.

Uses pytest's ``tmp_path`` fixture and the existing schema/insert machinery
(``initialize_schema``, ``open_database``, ``SQLiteDrawDataRepository``) —
no second schema-init or insert path is introduced here.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from lottolab.application.ports import TargetDrawNotFoundError
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.replay_history_reader import SQLiteDrawHistoryReader
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository

HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "replay-history-data")}
    )


def row(
    draw_number: str,
    draw_date: str,
    main_numbers: str = "1|3|9|17|24|49",
    special_number: str = "7",
    source: str = "synthetic-reference",
) -> str:
    return f"BIG_LOTTO,{draw_number},{draw_date},{main_numbers},{special_number},{source}"


def _insert(paths: LocalDataPaths, *rows: str) -> None:
    document = parse_draw_csv("\n".join((HEADER, *rows, "")), filename="synthetic.csv")
    assert document.is_valid, document.errors
    SQLiteDrawDataRepository(paths).apply_valid_import(document)


def _table_snapshot(paths: LocalDataPaths) -> dict[str, list[tuple[object, ...]]]:
    with open_database(paths, read_only=True) as connection:
        snapshot: dict[str, list[tuple[object, ...]]] = {}
        for table in ("draws", "schema_migrations", "ingestion_runs", "ingestion_items"):
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            snapshot[table] = [tuple(r) for r in rows]
    return snapshot


def _seed_standard_history(paths: LocalDataPaths) -> None:
    _insert(
        paths,
        row("1", "2026-01-01", main_numbers="1|2|3|4|5|6", special_number="10"),
        row("2", "2026-01-02", main_numbers="2|3|4|5|6|7", special_number="11"),
        # Same draw_date, but numerically 10 > 9: lexical string ordering of
        # draw_number would put "10" before "9" (since "1" < "9"); a correct
        # numeric ordering must put 9 before 10.
        row("9", "2026-01-10", main_numbers="9|10|11|12|13|14", special_number="20"),
        row("10", "2026-01-10", main_numbers="10|11|12|13|14|15", special_number="21"),
        row("15", "2026-01-11", main_numbers="15|16|17|18|19|20", special_number="25"),
        row("20", "2026-01-12", main_numbers="20|21|22|23|24|25", special_number="30"),
        # Future draw relative to target "20": must never be returned.
        row("25", "2026-01-13", main_numbers="25|26|27|28|29|30", special_number="35"),
    )


def test_exact_target_resolution_and_ascending_order(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    history = reader.read_causal_history(LotteryType.BIG_LOTTO, "20")

    assert [row.draw_number for row in history] == ["1", "2", "9", "10", "15"]


def test_lexical_vs_numeric_tie_break_on_shared_draw_date(tmp_path: Path) -> None:
    """draw_number "9" and "10" share a draw_date; numeric order must win."""

    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    history = reader.read_causal_history(LotteryType.BIG_LOTTO, "20")
    same_date_rows = [r for r in history if r.draw_date == date(2026, 1, 10)]

    assert [r.draw_number for r in same_date_rows] == ["9", "10"]
    # A naive lexical comparison ("10" < "9") would have produced ["10", "9"].
    assert [r.draw_number for r in same_date_rows] != ["10", "9"]


def test_target_and_future_draws_are_excluded(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    history = reader.read_causal_history(LotteryType.BIG_LOTTO, "20")

    draw_numbers = {row.draw_number for row in history}
    assert "20" not in draw_numbers
    assert "25" not in draw_numbers


def test_main_and_special_numbers_are_preserved_exactly(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    history = reader.read_causal_history(LotteryType.BIG_LOTTO, "20")
    by_draw = {row.draw_number: row for row in history}

    assert by_draw["9"].main_numbers == (9, 10, 11, 12, 13, 14)
    assert by_draw["9"].special_number == 20
    assert by_draw["15"].main_numbers == (15, 16, 17, 18, 19, 20)
    assert by_draw["15"].special_number == 25


def test_repeat_query_gives_identical_results(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    first = reader.read_causal_history(LotteryType.BIG_LOTTO, "20")
    second = reader.read_causal_history(LotteryType.BIG_LOTTO, "20")

    assert first == second


def test_maximum_history_draws_returns_most_recent_n_ascending(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    history = reader.read_causal_history(LotteryType.BIG_LOTTO, "20", maximum_history_draws=2)

    assert [row.draw_number for row in history] == ["10", "15"]


def test_missing_target_raises_target_draw_not_found(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    with pytest.raises(TargetDrawNotFoundError):
        reader.read_causal_history(LotteryType.BIG_LOTTO, "does-not-exist")


def test_target_with_zero_pre_target_history_returns_empty_tuple(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _insert(paths, row("1", "2026-01-01"))
    reader = SQLiteDrawHistoryReader(paths)

    history = reader.read_causal_history(LotteryType.BIG_LOTTO, "1")

    assert history == ()


def test_read_only_queries_never_mutate_draws_or_ingestion_tables(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    before = _table_snapshot(paths)
    reader.read_causal_history(LotteryType.BIG_LOTTO, "20")
    reader.read_causal_history(LotteryType.BIG_LOTTO, "20", maximum_history_draws=2)
    with pytest.raises(TargetDrawNotFoundError):
        reader.read_causal_history(LotteryType.BIG_LOTTO, "missing")
    after = _table_snapshot(paths)

    assert before == after
    for table, rows in before.items():
        assert len(rows) == len(after[table]), table
    assert not Path(f"{paths.database}-wal").exists()
    assert not Path(f"{paths.database}-shm").exists()


def test_different_lottery_type_target_is_not_found(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    # DAILY_539 shares no rows with the BIG_LOTTO fixture, so draw_number "20"
    # must resolve as not-found under a different lottery_type.
    with pytest.raises(TargetDrawNotFoundError):
        reader.read_causal_history(LotteryType.DAILY_539, "20")


def test_maximum_history_draws_rejects_non_positive_values(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    with pytest.raises(ValueError):
        reader.read_causal_history(LotteryType.BIG_LOTTO, "20", maximum_history_draws=0)


def test_unbounded_query_does_not_use_sqlite_row_factory_row_type(tmp_path: Path) -> None:
    """Regression guard: results must decode to plain domain rows, not sqlite3.Row."""

    paths = task_paths(tmp_path)
    _seed_standard_history(paths)
    reader = SQLiteDrawHistoryReader(paths)

    history = reader.read_causal_history(LotteryType.BIG_LOTTO, "20")

    assert all(not isinstance(row, sqlite3.Row) for row in history)
