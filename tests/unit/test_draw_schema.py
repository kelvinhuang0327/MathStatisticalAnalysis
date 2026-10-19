"""Focused tests for the generic local draw-data schema foundation."""

from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

import pytest
from pytest import MonkeyPatch

import lottolab.infrastructure.persistence.draw_schema as draw_schema
from lottolab.infrastructure.persistence.draw_schema import (
    BUSY_TIMEOUT_MS,
    CONTEXT_MIGRATION_CHECKSUM,
    CONTEXT_MIGRATION_NAME,
    CONTEXT_MIGRATION_STATEMENTS,
    CONTEXT_SCHEMA_VERSION,
    CURRENT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    DRAW_SCHEDULE_MIGRATION_CHECKSUM,
    DRAW_SCHEDULE_MIGRATION_NAME,
    DRAW_SCHEDULE_MIGRATION_STATEMENTS,
    DRAW_SCHEDULE_SCHEMA_VERSION,
    MIGRATION_CHECKSUM,
    MIGRATION_NAME,
    MIGRATION_STATEMENTS,
    SCHEDULE_AUTHORITY_MIGRATION_CHECKSUM,
    SCHEDULE_AUTHORITY_MIGRATION_NAME,
    LocalDataError,
    LocalDataPaths,
    MigrationChecksumError,
    NewerSchemaVersionError,
    SchemaMigrationError,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
    verify_schema_read_only,
)


def task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / "lottolab-data")})


def create_lookalike_schema(
    paths: LocalDataPaths,
    *,
    replacement: tuple[int, str, str] | None = None,
    extra_sql: str | None = None,
) -> None:
    paths.data_directory.mkdir(mode=0o700, parents=True)
    paths.data_directory.chmod(0o700)
    descriptor = os.open(paths.database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    paths.database.chmod(0o600)

    statements: list[str] = list(MIGRATION_STATEMENTS)
    if replacement is not None:
        index, original, altered = replacement
        assert original in statements[index]
        statements[index] = statements[index].replace(original, altered)
    with sqlite3.connect(paths.database) as connection:
        for statement in statements:
            connection.execute(statement)
        if extra_sql is not None:
            connection.execute(extra_sql)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (?, ?, ?, '2026-07-16T00:00:00Z')
            """,
            (1, MIGRATION_NAME, MIGRATION_CHECKSUM),
        )


def create_v2_schema(paths: LocalDataPaths) -> None:
    create_lookalike_schema(paths)
    with sqlite3.connect(paths.database) as connection:
        for statement in CONTEXT_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (?, ?, ?, '2026-07-17T00:00:00Z')
            """,
            (CONTEXT_SCHEMA_VERSION, CONTEXT_MIGRATION_NAME, CONTEXT_MIGRATION_CHECKSUM),
        )


def create_v3_schema(paths: LocalDataPaths) -> None:
    create_v2_schema(paths)
    with sqlite3.connect(paths.database) as connection:
        for statement in DRAW_SCHEDULE_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (?, ?, ?, '2026-07-18T00:00:00Z')
            """,
            (
                DRAW_SCHEDULE_SCHEMA_VERSION,
                DRAW_SCHEDULE_MIGRATION_NAME,
                DRAW_SCHEDULE_MIGRATION_CHECKSUM,
            ),
        )


def test_resolver_is_lazy_and_uses_override_or_mac_default(tmp_path: Path) -> None:
    overridden = task_paths(tmp_path)
    assert overridden.data_directory == tmp_path / "lottolab-data"
    assert overridden.database == overridden.data_directory / "lottolab.db"
    assert not overridden.data_directory.exists()

    fake_home = tmp_path / "fake-home"
    defaulted = resolve_local_data_paths(environ={}, home=fake_home)
    assert defaulted.data_directory == (fake_home / "Library" / "Application Support" / "LottoLab")
    assert not fake_home.exists()


@pytest.mark.parametrize(
    ("configured", "message"),
    [
        ("relative/data", "absolute"),
        ("/tmp/safe/../escape", "traversal"),
        ("/tmp/LotteryNew/data", "LotteryNew"),
    ],
)
def test_resolver_rejects_unsafe_path_syntax(configured: str, message: str) -> None:
    with pytest.raises(LocalDataError, match=message):
        resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: configured})


def test_resolver_rejects_symlinked_and_git_worktree_paths(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(LocalDataError, match="symlinks"):
        resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(alias / "lottolab-data")})

    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    with pytest.raises(LocalDataError, match="outside Git worktrees"):
        resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(repository / "user-data")})


def test_existing_paths_must_be_owner_only_regular_files(tmp_path: Path) -> None:
    data_directory = tmp_path / "unsafe-data"
    data_directory.mkdir(mode=0o755)
    data_directory.chmod(0o755)
    with pytest.raises(LocalDataError, match="0700"):
        resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_directory)})

    data_directory.chmod(0o700)
    target = tmp_path / "database-target"
    target.write_bytes(b"")
    target.chmod(0o600)
    (data_directory / "lottolab.db").symlink_to(target)
    with pytest.raises(LocalDataError, match="regular file"):
        resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_directory)})


def test_empty_read_is_noncreating(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    assert verify_schema_read_only(paths) is False
    assert not paths.data_directory.exists()
    assert not paths.database.exists()


def test_schema_v4_creation_security_shape_and_idempotency(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    initialize_schema(paths)

    assert stat.S_IMODE(paths.data_directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(paths.database.stat().st_mode) == 0o600
    assert paths.database.stat().st_nlink == 1
    assert not Path(f"{paths.database}-wal").exists()
    assert not Path(f"{paths.database}-shm").exists()

    with sqlite3.connect(paths.database) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """
            )
        }
        assert tables == {
            "schema_migrations",
            "draws",
            "ingestion_runs",
            "ingestion_items",
            "ingestion_run_context",
            "draw_schedules",
            "draw_schedule_facts",
            "draw_schedule_authority_evidence",
        }
        migrations = connection.execute(
            """
            SELECT version, name, checksum, applied_at
            FROM schema_migrations ORDER BY version
            """
        ).fetchall()
        assert [(row[0], row[1], row[2]) for row in migrations] == [
            (1, MIGRATION_NAME, MIGRATION_CHECKSUM),
            (CONTEXT_SCHEMA_VERSION, CONTEXT_MIGRATION_NAME, CONTEXT_MIGRATION_CHECKSUM),
            (
                DRAW_SCHEDULE_SCHEMA_VERSION,
                DRAW_SCHEDULE_MIGRATION_NAME,
                DRAW_SCHEDULE_MIGRATION_CHECKSUM,
            ),
            (
                CURRENT_SCHEMA_VERSION,
                SCHEDULE_AUTHORITY_MIGRATION_NAME,
                SCHEDULE_AUTHORITY_MIGRATION_CHECKSUM,
            ),
        ]
        assert connection.execute("SELECT COUNT(*) FROM draw_schedules").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM draw_schedule_facts").fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM draw_schedule_authority_evidence"
        ).fetchone() == (0,)
        assert all(str(row[3]).endswith("Z") for row in migrations)
        applied_at = [row[3] for row in migrations]

    initialize_schema(paths)
    with sqlite3.connect(paths.database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone() == (4,)
        assert [
            row[0]
            for row in connection.execute(
                "SELECT applied_at FROM schema_migrations ORDER BY version"
            )
        ] == applied_at
    assert verify_schema_read_only(paths) is True


def test_connection_policy_enforces_fk_timeout_delete_journal_and_read_only(
    tmp_path: Path,
) -> None:
    paths = task_paths(tmp_path)
    initialize_schema(paths)

    with open_database(paths) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert connection.execute("PRAGMA busy_timeout").fetchone() == (BUSY_TIMEOUT_MS,)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ingestion_items (
                    ingestion_run_id, source_row_number, disposition
                ) VALUES ('missing-run', 1, 'FAILED')
                """
            )

    with open_database(paths, read_only=True) as connection:
        assert connection.execute("PRAGMA query_only").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM ingestion_runs")


def test_existing_v1_is_verified_read_only_then_upgraded_only_by_write(
    tmp_path: Path,
) -> None:
    paths = task_paths(tmp_path)
    create_lookalike_schema(paths)

    assert verify_schema_read_only(paths) is True
    with sqlite3.connect(paths.database) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'ingestion_run_context'"
        ).fetchone() is None
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone() == (1,)

    initialize_schema(paths)

    with sqlite3.connect(paths.database) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'ingestion_run_context'"
        ).fetchone() == ("ingestion_run_context",)
        assert connection.execute(
            """
            SELECT name, checksum FROM schema_migrations
            WHERE version = ?
            """,
            (CONTEXT_SCHEMA_VERSION,),
        ).fetchone() == (CONTEXT_MIGRATION_NAME, CONTEXT_MIGRATION_CHECKSUM)
        assert connection.execute(
            """
            SELECT name, checksum FROM schema_migrations
            WHERE version = ?
            """,
            (DRAW_SCHEDULE_SCHEMA_VERSION,),
        ).fetchone() == (
            DRAW_SCHEDULE_MIGRATION_NAME,
            DRAW_SCHEDULE_MIGRATION_CHECKSUM,
        )
        assert connection.execute(
            """
            SELECT name, checksum FROM schema_migrations
            WHERE version = ?
            """,
            (CURRENT_SCHEMA_VERSION,),
        ).fetchone() == (
            SCHEDULE_AUTHORITY_MIGRATION_NAME,
            SCHEDULE_AUTHORITY_MIGRATION_CHECKSUM,
        )


def test_existing_v2_upgrade_is_add_only_and_preserves_completed_data(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    create_v2_schema(paths)
    with sqlite3.connect(paths.database) as connection:
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (
                'run-v2', 'DRAW_CSV_IMPORT', 'SUCCESS', 'BIG_LOTTO',
                'synthetic.csv', ?, 'parser-v1', 1, 1, 0, 0, 0,
                '209900001', '209900001', '2099-01-01T00:00:00Z',
                '2099-01-01T00:00:00Z', NULL
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO ingestion_run_context (
                ingestion_run_id, trigger, fetched_count
            ) VALUES ('run-v2', 'DRAW_CSV_IMPORT', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO ingestion_items (
                ingestion_run_id, source_row_number, lottery_type, draw_number,
                disposition, normalized_record_hash, message
            ) VALUES ('run-v2', 1, 'BIG_LOTTO', '209900001', 'INSERTED', ?, 'inserted')
            """,
            ("b" * 64,),
        )
        connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (
                'BIG_LOTTO', '209900001', '2099-01-01', '[1,2,3,4,5,6]',
                '[7]', ?, 'synthetic.csv', 'synthetic', 'run-v2',
                '2099-01-01T00:00:00Z', '2099-01-01T00:00:00Z'
            )
            """,
            ("b" * 64,),
        )
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in (
                "draws",
                "ingestion_runs",
                "ingestion_items",
                "ingestion_run_context",
            )
        }

    assert verify_schema_read_only(paths) is True
    initialize_schema(paths)

    with sqlite3.connect(paths.database) as connection:
        after = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in before
        }
        assert after == before
        assert connection.execute("SELECT COUNT(*) FROM draw_schedules").fetchone() == (0,)
        assert connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()[-2:] == [
            (
                DRAW_SCHEDULE_SCHEMA_VERSION,
                DRAW_SCHEDULE_MIGRATION_NAME,
                DRAW_SCHEDULE_MIGRATION_CHECKSUM,
            ),
            (
                CURRENT_SCHEMA_VERSION,
                SCHEDULE_AUTHORITY_MIGRATION_NAME,
                SCHEDULE_AUTHORITY_MIGRATION_CHECKSUM,
            ),
        ]


def test_existing_v3_upgrade_preserves_schedule_and_adds_immutable_authority_tables(
    tmp_path: Path,
) -> None:
    paths = task_paths(tmp_path)
    create_v3_schema(paths)
    with sqlite3.connect(paths.database) as connection:
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (
                'run-v3', 'OFFICIAL_SCHEDULE_SYNC', 'SUCCESS', 'BIG_LOTTO',
                'fixture', ?, 'parser-v1', 1, 1, 0, 0, 0, '209900001',
                '209900001', '2099-01-01T00:00:00Z',
                '2099-01-01T00:00:00Z', NULL
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO draw_schedules (
                lottery_type, draw_number, draw_date, scheduled_at,
                schedule_timezone, source_id, source_version, source_locator,
                source_payload_sha256, source_observed_at,
                normalized_announcement_hash, ingestion_run_id, created_at
            ) VALUES (
                'BIG_LOTTO', '209900001', '2099-01-02',
                '2099-01-02T12:30:00.000000Z', 'Asia/Taipei',
                'TAIWAN_LOTTERY_OFFICIAL_SCHEDULE', 'fixture-v1',
                'https://api.taiwanlottery.com/fixture', ?,
                '2099-01-01T00:00:00.000000Z', ?, 'run-v3',
                '2099-01-01T00:00:00.000000Z'
            )
            """,
            ("b" * 64, "c" * 64),
        )
        original = connection.execute("SELECT * FROM draw_schedules").fetchone()

    initialize_schema(paths)

    with sqlite3.connect(paths.database) as connection:
        assert connection.execute("SELECT * FROM draw_schedules").fetchone() == original
        assert connection.execute("SELECT COUNT(*) FROM draw_schedule_facts").fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM draw_schedule_authority_evidence"
        ).fetchone() == (0,)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE draw_schedules SET draw_date = '2099-01-03' WHERE id = 1"
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute("DELETE FROM draw_schedules WHERE id = 1")


def test_checksum_mismatch_and_newer_version_fail_closed(tmp_path: Path) -> None:
    checksum_paths = task_paths(tmp_path / "checksum")
    initialize_schema(checksum_paths)
    with sqlite3.connect(checksum_paths.database) as connection:
        connection.execute(
            "UPDATE schema_migrations SET checksum = ? WHERE version = 1",
            ("0" * 64,),
        )
    with pytest.raises(MigrationChecksumError, match="checksum"):
        verify_schema_read_only(checksum_paths)

    newer_paths = task_paths(tmp_path / "newer")
    initialize_schema(newer_paths)
    with sqlite3.connect(newer_paths.database) as connection:
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (?, 'future', ?, '2099-01-01T00:00:00Z')
            """,
            (CURRENT_SCHEMA_VERSION + 1, "f" * 64),
        )
    with pytest.raises(NewerSchemaVersionError, match="newer"):
        verify_schema_read_only(newer_paths)


def test_migration_failure_rolls_back_all_schema_objects(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = task_paths(tmp_path)
    paths.data_directory.mkdir(mode=0o700)
    paths.data_directory.chmod(0o700)
    descriptor = os.open(paths.database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    paths.database.chmod(0o600)
    monkeypatch.setattr(
        draw_schema,
        "MIGRATION_STATEMENTS",
        (*draw_schema.MIGRATION_STATEMENTS, "CREATE TABL invalid_syntax"),
    )

    with pytest.raises(SchemaMigrationError, match="migration failed"):
        initialize_schema(paths)

    with sqlite3.connect(paths.database) as connection:
        assert (
            connection.execute(
                """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
            ).fetchall()
            == []
        )


def test_wal_database_fails_closed(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    initialize_schema(paths)
    with sqlite3.connect(paths.database) as connection:
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)

    with pytest.raises(SchemaMigrationError, match="DELETE journal mode"):
        verify_schema_read_only(paths)


@pytest.mark.parametrize(
    ("label", "replacement", "extra_sql"),
    [
        (
            "column type",
            (2, "draw_date TEXT NOT NULL", "draw_date BLOB NOT NULL"),
            None,
        ),
        (
            "column nullability",
            (2, "draw_date TEXT NOT NULL", "draw_date TEXT"),
            None,
        ),
        (
            "column default",
            (2, "draw_date TEXT NOT NULL", "draw_date TEXT NOT NULL DEFAULT ''"),
            None,
        ),
        (
            "unique index order",
            (2, "UNIQUE (lottery_type, draw_number)", "UNIQUE (draw_number, lottery_type)"),
            None,
        ),
        (
            "foreign-key delete action",
            (2, "ON DELETE RESTRICT", "ON DELETE CASCADE"),
            None,
        ),
        (
            "foreign-key update action",
            (
                2,
                "REFERENCES ingestion_runs(id) ON DELETE RESTRICT",
                "REFERENCES ingestion_runs(id) ON UPDATE CASCADE ON DELETE RESTRICT",
            ),
            None,
        ),
        (
            "missing check",
            (
                3,
                "source_row_number INTEGER NOT NULL CHECK (source_row_number >= 1)",
                "source_row_number INTEGER NOT NULL",
            ),
            None,
        ),
        (
            "partial index",
            (
                4,
                "ON draws (lottery_type, draw_date DESC, draw_number DESC)",
                "ON draws (lottery_type, draw_date DESC, draw_number DESC) "
                "WHERE lottery_type IS NOT NULL",
            ),
            None,
        ),
        (
            "unexpected trigger",
            None,
            """
            CREATE TRIGGER unexpected_draw_trigger AFTER INSERT ON draws
            BEGIN SELECT 1; END
            """,
        ),
        (
            "unexpected view",
            None,
            "CREATE VIEW unexpected_draw_view AS SELECT draw_number FROM draws",
        ),
        (
            "extra semantic object",
            None,
            "CREATE INDEX unexpected_draw_date_index ON draws (draw_date)",
        ),
    ],
)
def test_lookalike_schema_semantic_changes_fail_closed(
    tmp_path: Path,
    label: str,
    replacement: tuple[int, str, str] | None,
    extra_sql: str | None,
) -> None:
    paths = task_paths(tmp_path / label.replace(" ", "-"))
    create_lookalike_schema(paths, replacement=replacement, extra_sql=extra_sql)

    with sqlite3.connect(paths.database) as connection:
        assert connection.execute(
            "SELECT name, checksum FROM schema_migrations WHERE version = 1"
        ).fetchone() == (MIGRATION_NAME, MIGRATION_CHECKSUM)
    with pytest.raises(SchemaMigrationError):
        verify_schema_read_only(paths)
