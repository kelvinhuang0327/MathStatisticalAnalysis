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
    CURRENT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    MIGRATION_CHECKSUM,
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


def test_schema_v1_creation_security_shape_and_idempotency(tmp_path: Path) -> None:
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
        }
        migration = connection.execute(
            "SELECT version, name, checksum, applied_at FROM schema_migrations"
        ).fetchone()
        assert migration is not None
        assert migration[0] == CURRENT_SCHEMA_VERSION
        assert migration[1] == "create_local_draw_data_schema"
        assert migration[2] == MIGRATION_CHECKSUM
        assert str(migration[3]).endswith("Z")
        applied_at = migration[3]

    initialize_schema(paths)
    with sqlite3.connect(paths.database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone() == (1,)
        assert connection.execute("SELECT applied_at FROM schema_migrations").fetchone() == (
            applied_at,
        )
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
            VALUES (2, 'future', ?, '2099-01-01T00:00:00Z')
            """,
            ("f" * 64,),
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
