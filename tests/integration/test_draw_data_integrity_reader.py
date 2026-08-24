"""Temporary-DB integration tests for the read-only draw-data integrity reader.

Every database in this module is created under ``tmp_path``; none of these
tests ever resolves or opens a default/canonical database.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from lottolab.domain.draw_data_integrity import (
    DrawDataIntegrityFindingCode,
    DrawDataIntegrityStatus,
)
from lottolab.infrastructure.persistence.draw_data_integrity_reader import (
    SQLiteDrawDataIntegrityReader,
    _run_integrity_checks,  # pyright: ignore[reportPrivateUsage]
)
from lottolab.infrastructure.persistence.draw_schema import (
    CONTEXT_MIGRATION_CHECKSUM,
    CONTEXT_MIGRATION_NAME,
    CONTEXT_MIGRATION_STATEMENTS,
    CONTEXT_SCHEMA_VERSION,
    CURRENT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    MIGRATION_CHECKSUM,
    MIGRATION_NAME,
    MIGRATION_STATEMENTS,
    LocalDataError,
    LocalDataPaths,
    NewerSchemaVersionError,
    SchemaMigrationError,
    initialize_schema,
    resolve_local_data_paths,
)

_TIMESTAMP = "2026-01-01T00:00:00.000000Z"


def _task_paths(tmp_path: Path, suffix: str = "task-integrity-data") -> LocalDataPaths:
    return resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / suffix)})


def _hash_for(lottery_type: str, draw_number: str) -> str:
    return hashlib.sha256(f"{lottery_type}:{draw_number}".encode()).hexdigest()


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
    main_numbers_json: str = "[1,2,3,4,5,6]",
    special_numbers_json: str = "[7]",
    normalized_record_hash: str | None = None,
    run_id: str = "run-1",
) -> None:
    connection.execute(
        """
        INSERT INTO draws (
            lottery_type, draw_number, draw_date, main_numbers_json, special_numbers_json,
            normalized_record_hash, source_name, source_reference, ingestion_run_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
        """,
        (
            lottery_type,
            draw_number,
            draw_date,
            main_numbers_json,
            special_numbers_json,
            normalized_record_hash or _hash_for(lottery_type, draw_number),
            run_id,
            _TIMESTAMP,
            _TIMESTAMP,
        ),
    )


def _raw_connection(paths: LocalDataPaths) -> sqlite3.Connection:
    # Fixture-only: bypasses the production read/write safety wrapper on
    # purpose, so tests can seed rows the validated import path would reject.
    return sqlite3.connect(str(paths.database))


def _create_v2_schema(paths: LocalDataPaths) -> None:
    paths.data_directory.mkdir(mode=0o700, parents=True)
    paths.data_directory.chmod(0o700)
    descriptor = os.open(paths.database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    paths.database.chmod(0o600)
    with sqlite3.connect(paths.database) as connection:
        for statement in MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (1, ?, ?, '2099-01-01T00:00:00Z')
            """,
            (MIGRATION_NAME, MIGRATION_CHECKSUM),
        )
        for statement in CONTEXT_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (?, ?, ?, '2099-01-01T00:00:01Z')
            """,
            (CONTEXT_SCHEMA_VERSION, CONTEXT_MIGRATION_NAME, CONTEXT_MIGRATION_CHECKSUM),
        )


def test_absent_database_returns_absent_and_creates_nothing(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    reader = SQLiteDrawDataIntegrityReader()

    report = reader.inspect(paths.database)

    assert report.status is DrawDataIntegrityStatus.ABSENT
    assert report.schema_version is None
    assert report.table_counts == ()
    assert report.lottery_summaries == ()
    assert report.findings == ()
    assert not paths.data_directory.exists()
    assert not paths.database.exists()


def test_valid_v2_database_reports_its_actual_version_without_migration(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path, suffix="valid-v2-data")
    _create_v2_schema(paths)
    before = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)

    after = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )
    assert report.status is DrawDataIntegrityStatus.HEALTHY
    assert report.schema_version == CONTEXT_SCHEMA_VERSION
    assert after == before
    with sqlite3.connect(f"file:{paths.database}?mode=ro", uri=True) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'draw_schedules'"
        ).fetchone() is None


def test_healthy_database_reports_exact_counts_and_ranges(tmp_path: Path) -> None:
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

    reader = SQLiteDrawDataIntegrityReader()
    report = reader.inspect(paths.database)

    assert report.status is DrawDataIntegrityStatus.HEALTHY
    assert report.schema_version == CURRENT_SCHEMA_VERSION
    assert [(entry.table_name, entry.row_count) for entry in report.table_counts] == [
        ("draws", 2),
        ("ingestion_runs", 1),
        ("ingestion_items", 0),
    ]
    assert len(report.lottery_summaries) == 1
    summary = report.lottery_summaries[0]
    assert summary.lottery_type == "BIG_LOTTO"
    assert summary.draw_count == 2
    assert summary.first_draw_number == "0001"
    assert summary.first_draw_date == "2026-01-01"
    assert summary.last_draw_number == "0002"
    assert summary.last_draw_date == "2026-01-08"
    assert all(finding.count == 0 for finding in report.findings)


def test_multiple_lottery_types_are_ordered_lexicographically(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        _insert_draw(
            connection, lottery_type="POWER_LOTTO", draw_number="1", draw_date="2026-01-01"
        )
        _insert_draw(connection, lottery_type="BIG_LOTTO", draw_number="1", draw_date="2026-01-01")
        _insert_draw(
            connection, lottery_type="DAILY_539", draw_number="1", draw_date="2026-01-01"
        )
        connection.commit()
    finally:
        connection.close()

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)

    assert [entry.lottery_type for entry in report.lottery_summaries] == [
        "BIG_LOTTO",
        "DAILY_539",
        "POWER_LOTTO",
    ]


def test_first_last_ordering_uses_numeric_draw_number_not_lexical(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        # Same draw_date on purpose: lexical ordering would rank "10" before
        # "9" (since "1" < "9"); numeric ordering must rank 9 before 10.
        _insert_draw(connection, lottery_type="BIG_LOTTO", draw_number="9", draw_date="2026-01-01")
        _insert_draw(connection, lottery_type="BIG_LOTTO", draw_number="10", draw_date="2026-01-01")
        connection.commit()
    finally:
        connection.close()

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)

    summary = report.lottery_summaries[0]
    assert summary.first_draw_number == "9"
    assert summary.last_draw_number == "10"


def test_foreign_key_violation_is_reported(tmp_path: Path) -> None:
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

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)

    assert report.status is DrawDataIntegrityStatus.UNHEALTHY
    findings_by_code = {finding.code: finding.count for finding in report.findings}
    assert findings_by_code[DrawDataIntegrityFindingCode.FOREIGN_KEY_VIOLATION] == 1


def test_invalid_draw_number_is_reported(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        _insert_draw(connection, lottery_type="BIG_LOTTO", draw_number="", draw_date="2026-01-01")
        _insert_draw(
            connection, lottery_type="BIG_LOTTO", draw_number="12a", draw_date="2026-01-02"
        )
        connection.commit()
    finally:
        connection.close()

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)

    assert report.status is DrawDataIntegrityStatus.UNHEALTHY
    findings_by_code = {finding.code: finding.count for finding in report.findings}
    assert findings_by_code[DrawDataIntegrityFindingCode.INVALID_DRAW_NUMBER] == 2


def test_invalid_normalized_hash_is_reported(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        _insert_draw(
            connection,
            lottery_type="BIG_LOTTO",
            draw_number="0001",
            draw_date="2026-01-01",
            normalized_record_hash="A" * 64,
        )
        _insert_draw(
            connection,
            lottery_type="BIG_LOTTO",
            draw_number="0002",
            draw_date="2026-01-02",
            normalized_record_hash="short",
        )
        connection.commit()
    finally:
        connection.close()

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)

    assert report.status is DrawDataIntegrityStatus.UNHEALTHY
    findings_by_code = {finding.code: finding.count for finding in report.findings}
    assert findings_by_code[DrawDataIntegrityFindingCode.INVALID_NORMALIZED_RECORD_HASH] == 2


def test_invalid_numbers_json_is_reported(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        _insert_run(connection)
        _insert_draw(
            connection,
            lottery_type="BIG_LOTTO",
            draw_number="0001",
            draw_date="2026-01-01",
            main_numbers_json="not json",
        )
        connection.commit()
    finally:
        connection.close()

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)

    assert report.status is DrawDataIntegrityStatus.UNHEALTHY
    findings_by_code = {finding.code: finding.count for finding in report.findings}
    assert findings_by_code[DrawDataIntegrityFindingCode.INVALID_NUMBERS_JSON] == 1


def test_duplicate_draw_identity_detection_against_an_unconstrained_fixture_table() -> None:
    """The production ``draws`` schema declares ``UNIQUE(lottery_type, draw_number)``,
    so a genuine duplicate cannot be persisted through any SQLite write path while
    the schema stays byte-identical to version 1 -- the reader's schema-verification
    gate would otherwise have to accept a modified schema to let one through, which
    contradicts the "schema mismatch fails closed" requirement tested separately.
    This exercises the reader's actual duplicate-counting query directly against an
    in-memory fixture table with the same relevant columns but no unique constraint,
    which is the only way to make a genuine duplicate physically exist."""

    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE draws (
                lottery_type TEXT NOT NULL,
                draw_number TEXT NOT NULL,
                normalized_record_hash TEXT NOT NULL,
                main_numbers_json TEXT NOT NULL,
                special_numbers_json TEXT NOT NULL
            )
            """
        )
        for _ in range(2):
            connection.execute(
                "INSERT INTO draws VALUES ('BIG_LOTTO', '0001', ?, '[1,2,3,4,5,6]', '[7]')",
                (_hash_for("BIG_LOTTO", "0001"),),
            )
        connection.commit()

        findings = {finding.code: finding.count for finding in _run_integrity_checks(connection)}
    finally:
        connection.close()

    assert findings[DrawDataIntegrityFindingCode.DUPLICATE_DRAW_IDENTITY] == 1
    assert findings[DrawDataIntegrityFindingCode.INVALID_DRAW_NUMBER] == 0
    assert findings[DrawDataIntegrityFindingCode.INVALID_NORMALIZED_RECORD_HASH] == 0
    assert findings[DrawDataIntegrityFindingCode.INVALID_NUMBERS_JSON] == 0


def test_schema_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        connection.execute("ALTER TABLE draws ADD COLUMN unexpected_extra_column TEXT")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(SchemaMigrationError):
        SQLiteDrawDataIntegrityReader().inspect(paths.database)


def test_newer_schema_version_fails_closed(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    initialize_schema(paths)
    connection = _raw_connection(paths)
    try:
        connection.execute(
            "UPDATE schema_migrations SET version = ? WHERE version = ?",
            (CURRENT_SCHEMA_VERSION + 1, CURRENT_SCHEMA_VERSION),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(NewerSchemaVersionError):
        SQLiteDrawDataIntegrityReader().inspect(paths.database)


def test_symlinked_data_directory_is_rejected(tmp_path: Path) -> None:
    real_target = tmp_path / "real-target"
    real_target.mkdir(mode=0o700)
    linked = tmp_path / "linked-data"
    linked.symlink_to(real_target, target_is_directory=True)

    with pytest.raises(LocalDataError, match="symlink"):
        SQLiteDrawDataIntegrityReader().inspect(linked / "lottolab.db")


def test_wrong_directory_permissions_are_rejected(tmp_path: Path) -> None:
    data_directory = tmp_path / "wrong-mode-data"
    data_directory.mkdir(mode=0o700)
    os.chmod(data_directory, 0o755)

    with pytest.raises(LocalDataError, match="mode"):
        SQLiteDrawDataIntegrityReader().inspect(data_directory / "lottolab.db")


def test_protected_path_component_is_rejected(tmp_path: Path) -> None:
    protected = tmp_path / "LotteryNew"

    with pytest.raises(LocalDataError, match="LotteryNew"):
        SQLiteDrawDataIntegrityReader().inspect(protected / "lottolab.db")


def test_database_bytes_size_schema_and_row_counts_are_unchanged_by_inspection(
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
    before_stat = paths.database.stat()

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

    report = SQLiteDrawDataIntegrityReader().inspect(paths.database)
    assert report.status is DrawDataIntegrityStatus.HEALTHY

    after_bytes = paths.database.read_bytes()
    after_stat = paths.database.stat()

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
    assert after_stat.st_size == before_stat.st_size
    assert after_counts == before_counts
    assert after_schema == before_schema


def test_no_sqlite_sidecars_remain_after_inspection(tmp_path: Path) -> None:
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

    SQLiteDrawDataIntegrityReader().inspect(paths.database)

    assert not Path(f"{paths.database}-wal").exists()
    assert not Path(f"{paths.database}-shm").exists()
    assert not Path(f"{paths.database}-journal").exists()


def test_repeated_inspection_returns_equal_reports(tmp_path: Path) -> None:
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

    reader = SQLiteDrawDataIntegrityReader()
    first = reader.inspect(paths.database)
    second = reader.inspect(paths.database)

    assert first == second
