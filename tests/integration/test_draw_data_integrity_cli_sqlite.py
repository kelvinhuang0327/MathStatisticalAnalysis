"""Real-SQLite integration tests through the registered LottoLab root CLI.

Every database here lives under ``tmp_path``; none of these tests ever
resolves or opens a default/canonical database.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from lottolab.domain.draw_data_integrity import DrawDataIntegrityFindingCode
from lottolab.infrastructure.persistence.draw_schema import (
    CURRENT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    resolve_local_data_paths,
)
from lottolab.interfaces.cli.main import app as root_app

runner = CliRunner()

_TIMESTAMP = "2026-01-01T00:00:00.000000Z"


def _task_paths(tmp_path: Path, suffix: str = "task-integrity-cli-data") -> LocalDataPaths:
    return resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / suffix)})


def _invoke(database: Path) -> Result:
    return runner.invoke(
        root_app,
        ["inspect-draw-data-integrity", "--database", str(database)],
    )


def _raw_connection(paths: LocalDataPaths) -> sqlite3.Connection:
    return sqlite3.connect(str(paths.database))


def _insert_run(connection: sqlite3.Connection, run_id: str = "run-1") -> None:
    connection.execute(
        """
        INSERT INTO ingestion_runs (
            id, operation_type, status, lottery_type, source_filename, source_sha256,
            parser_version, total_count, inserted_count, skipped_count, conflict_count,
            failed_count, first_draw_number, last_draw_number, started_at, completed_at,
            error_summary
        ) VALUES (?, 'IMPORT', 'SUCCESS', NULL, 'fixture.csv', 'deadbeef', 'v1',
                   1, 1, 0, 0, 0, NULL, NULL, ?, ?, NULL)
        """,
        (run_id, _TIMESTAMP, _TIMESTAMP),
    )


def _insert_draw(
    connection: sqlite3.Connection,
    *,
    lottery_type: str,
    draw_number: str,
    draw_date: str,
    run_id: str = "run-1",
) -> None:
    connection.execute(
        """
        INSERT INTO draws (
            lottery_type, draw_number, draw_date, main_numbers_json, special_numbers_json,
            normalized_record_hash, source_name, source_reference, ingestion_run_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, '[1,2,3,4,5,6]', '[7]', ?, NULL, NULL, ?, ?, ?)
        """,
        (
            lottery_type,
            draw_number,
            draw_date,
            hashlib.sha256(f"{lottery_type}:{draw_number}".encode()).hexdigest(),
            run_id,
            _TIMESTAMP,
            _TIMESTAMP,
        ),
    )


def test_absent_database_exits_one_and_creates_nothing(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)

    result = _invoke(paths.database)

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "ABSENT",
        "schema_version": None,
        "table_counts": [],
        "lottery_summaries": [],
        "findings": [],
    }
    assert result.stderr == ""
    assert not paths.data_directory.exists()
    assert not paths.database.exists()


def test_root_cli_does_not_open_an_ambient_default_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ambient_data_directory = tmp_path / "ambient-default"
    explicit_database = tmp_path / "explicit" / "lottolab.db"
    monkeypatch.setenv(DATA_DIRECTORY_ENV, str(ambient_data_directory))

    result = _invoke(explicit_database)

    assert result.exit_code == 1
    assert not ambient_data_directory.exists()
    assert not explicit_database.parent.exists()


def test_healthy_database_exits_zero_with_exact_report(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        _insert_draw(
            connection, lottery_type="BIG_LOTTO", draw_number="0001", draw_date="2026-01-01"
        )
        _insert_draw(
            connection, lottery_type="BIG_LOTTO", draw_number="0002", draw_date="2026-01-08"
        )
        connection.commit()
    finally:
        connection.close()

    result = _invoke(paths.database)

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "HEALTHY"
    assert payload["schema_version"] == CURRENT_SCHEMA_VERSION
    assert payload["table_counts"] == [
        {"table_name": "draws", "row_count": 2},
        {"table_name": "ingestion_runs", "row_count": 1},
        {"table_name": "ingestion_items", "row_count": 0},
    ]
    assert payload["lottery_summaries"] == [
        {
            "lottery_type": "BIG_LOTTO",
            "draw_count": 2,
            "first_draw_number": "0001",
            "first_draw_date": "2026-01-01",
            "last_draw_number": "0002",
            "last_draw_date": "2026-01-08",
        }
    ]
    assert all(entry["count"] == 0 for entry in payload["findings"])
    assert result.stderr == ""


def test_unhealthy_database_exits_one_with_the_violation_reported(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        # No PRAGMA foreign_keys here: the fixture connection intentionally
        # allows a dangling ingestion_run_id the validated write path forbids.
        _insert_draw(
            connection,
            lottery_type="BIG_LOTTO",
            draw_number="0001",
            draw_date="2026-01-01",
            run_id="missing-run",
        )
        connection.commit()
    finally:
        connection.close()

    result = _invoke(paths.database)

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "UNHEALTHY"
    findings_by_code = {entry["code"]: entry["count"] for entry in payload["findings"]}
    assert findings_by_code[DrawDataIntegrityFindingCode.FOREIGN_KEY_VIOLATION.value] == 1
    assert result.stderr == ""


def test_symlinked_data_directory_fails_closed_with_a_sanitized_message(
    tmp_path: Path,
) -> None:
    real_target = tmp_path / "real-target"
    real_target.mkdir(mode=0o700)
    linked = tmp_path / "linked-data"
    linked.symlink_to(real_target, target_is_directory=True)

    result = _invoke(linked / "lottolab.db")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "inspect-draw-data-integrity error: local data path cannot contain symlinks\n"
    )
    assert "Traceback" not in result.stderr
    assert str(linked) not in result.stderr


def test_protected_path_component_fails_closed_with_a_sanitized_message(
    tmp_path: Path,
) -> None:
    protected = tmp_path / "LotteryNew"

    result = _invoke(protected / "lottolab.db")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "inspect-draw-data-integrity error: LotteryNew paths are forbidden\n"


def test_database_bytes_schema_and_row_counts_are_unchanged_by_the_cli(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        _insert_draw(
            connection, lottery_type="BIG_LOTTO", draw_number="0001", draw_date="2026-01-01"
        )
        connection.commit()
    finally:
        connection.close()

    before_bytes = paths.database.read_bytes()
    verify_connection = sqlite3.connect(f"file:{paths.database}?mode=ro", uri=True)
    try:
        before_counts = {
            table: verify_connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("draws", "ingestion_runs", "ingestion_items")
        }
        before_schema = verify_connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
        ).fetchall()
    finally:
        verify_connection.close()

    result = _invoke(paths.database)
    assert result.exit_code == 0

    after_bytes = paths.database.read_bytes()
    verify_connection = sqlite3.connect(f"file:{paths.database}?mode=ro", uri=True)
    try:
        after_counts = {
            table: verify_connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("draws", "ingestion_runs", "ingestion_items")
        }
        after_schema = verify_connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
        ).fetchall()
    finally:
        verify_connection.close()

    assert after_bytes == before_bytes
    assert after_counts == before_counts
    assert after_schema == before_schema
    assert not Path(f"{paths.database}-wal").exists()
    assert not Path(f"{paths.database}-shm").exists()
    assert not Path(f"{paths.database}-journal").exists()


def test_repeated_cli_execution_is_byte_identical(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        _insert_draw(
            connection, lottery_type="BIG_LOTTO", draw_number="0001", draw_date="2026-01-01"
        )
        connection.commit()
    finally:
        connection.close()

    first = _invoke(paths.database)
    second = _invoke(paths.database)

    assert first.exit_code == second.exit_code == 0
    assert first.stdout == second.stdout
    assert first.stdout != ""
