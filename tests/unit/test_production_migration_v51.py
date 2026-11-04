"""Isolated, tmp_path-only coverage for the v5.1 first-start migration gate."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest
from tools.b649_goalc_local_scheduler import AdvisoryProcessLock, SchedulerAlreadyRunning

import lottolab.infrastructure.persistence.production_migration_v51 as migration


@pytest.fixture
def migration_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    source = tmp_path / "Library" / "Application Support" / "LottoLab"
    source.mkdir(mode=0o700, parents=True)
    source.chmod(0o700)
    project_root = tmp_path / "project"
    database_directory = project_root / "data" / "databases"
    monkeypatch.setattr(migration, "project_database_directory", lambda: database_directory)

    database = source / "lottolab.db"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 7")
        connection.execute(
            "CREATE TABLE draws (id INTEGER PRIMARY KEY, value TEXT, amount REAL, payload BLOB)"
        )
        connection.execute("INSERT INTO draws VALUES (1, 'source', 1.25, X'00FF')")
    database.chmod(0o600)

    authority = source / "authorities" / "nested"
    authority.mkdir(mode=0o700, parents=True)
    (authority / "seal.json").write_text('{"sealed":true}\n', encoding="utf-8")
    (authority / "seal.json").chmod(0o644)

    research_database = source / "lottolab_research.db"
    with sqlite3.connect(research_database) as connection:
        connection.execute(
            "CREATE TABLE research_sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO research_sample VALUES (1, 'preserve')")
    research_database.chmod(0o600)

    optional_backup = source / "lottolab.sqlite"
    optional_backup.write_bytes(b"optional old sqlite")
    optional_backup.chmod(0o644)
    backups = source / "migration-backups"
    backups.mkdir(mode=0o700)
    (backups / "must-not-copy.bin").write_bytes(b"historical backup")
    (backups / "must-not-copy.bin").chmod(0o644)
    return source, project_root, database_directory


def _run(source: Path) -> dict[str, object]:
    return migration.ensure_migration_complete(
        lock_validator=lambda: None,
        source_directory=source,
    )


def _read_marker(database_directory: Path) -> dict[str, object]:
    return json.loads((database_directory / migration.MARKER_FILENAME).read_text(encoding="utf-8"))


def _snapshot(path: Path) -> dict[str, object]:
    snapshot, _digest = migration._database_snapshot(path, immutable=False)  # pyright: ignore[reportPrivateUsage]
    return snapshot


def test_migration_walks_all_states_preserves_backup_and_restarts_after_normal_work(
    migration_case: tuple[Path, Path, Path],
) -> None:
    source, _project_root, database_directory = migration_case
    source_identity = migration._file_identity(source / "lottolab.db")  # pyright: ignore[reportPrivateUsage]

    result = _run(source)
    target = database_directory / "lottolab.db"
    marker = _read_marker(database_directory)

    assert result["status"] == "COMMITTED"
    assert marker["state_history"] == [
        "NOT_STARTED",
        "STARTED",
        "STAGED_VERIFIED",
        "REPLACED_PENDING_COMMIT",
        "COMMITTED",
    ]
    assert _snapshot(target) == _snapshot(source / "lottolab.db")
    assert migration._file_identity(source / "lottolab.db") == source_identity  # pyright: ignore[reportPrivateUsage]
    assert (database_directory / "authorities/nested/seal.json").read_text() == '{"sealed":true}\n'
    assert (database_directory / "authorities/nested/seal.json").stat().st_mode & 0o777 == 0o600
    assert (database_directory / "lottolab_research.db").is_file()
    assert not (database_directory / "lottolab.sqlite").exists()
    assert not (database_directory / "migration-backups/must-not-copy.bin").exists()
    marker_history = cast(list[object], marker["state_history"])
    assert set(str(key) for key in marker_history) == {
        "NOT_STARTED",
        "STARTED",
        "STAGED_VERIFIED",
        "REPLACED_PENDING_COMMIT",
        "COMMITTED",
    }

    with sqlite3.connect(target) as connection:
        connection.execute("INSERT INTO draws VALUES (2, 'normal cycle', 2.5, X'01')")
    assert _run(source)["status"] == "NO_OP_ALREADY_COMMITTED"


def test_existing_target_is_backed_up_before_atomic_replacement(
    migration_case: tuple[Path, Path, Path],
) -> None:
    source, _project_root, database_directory = migration_case
    database_directory.mkdir(mode=0o700, parents=True)
    target = database_directory / "lottolab.db"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE old_project (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO old_project VALUES (1, 'keep')")
    target.chmod(0o600)
    old_snapshot = _snapshot(target)

    _run(source)
    marker = _read_marker(database_directory)
    backup_record = marker["pre_migration_backup"]
    assert isinstance(backup_record, dict)
    backup_payload = cast(dict[str, object], backup_record)
    backup = Path(str(backup_payload["path"]))
    assert backup.exists()
    assert _snapshot(backup) == old_snapshot
    assert _snapshot(target) == _snapshot(source / "lottolab.db")


@pytest.mark.parametrize("fault", ["complete_stage", "truncate_stage", "modify_row"])
def test_stage_interruption_corruption_and_content_mismatch_never_publish(
    migration_case: tuple[Path, Path, Path], fault: str
) -> None:
    source, _project_root, database_directory = migration_case
    target = database_directory / "lottolab.db"

    def inject(event: str, stage: Path) -> None:
        if event != "stage_written" or stage.name != "lottolab.db":
            return
        if fault == "complete_stage":
            raise RuntimeError("injected stop after stage completion")
        if fault == "truncate_stage":
            with stage.open("r+b") as stream:
                stream.truncate(max(1, stage.stat().st_size // 2))
                stream.flush()
                os.fsync(stream.fileno())
        if fault == "modify_row":
            with sqlite3.connect(stage) as connection:
                connection.execute("UPDATE draws SET value = 'tampered' WHERE id = 1")

    expected = RuntimeError if fault == "complete_stage" else migration.ProductionMigrationError
    with pytest.raises(expected):
        migration.ensure_migration_complete(
            lock_validator=lambda: None,
            source_directory=source,
            _fault_hook=inject,
        )

    assert not target.exists()
    marker = _read_marker(database_directory)
    assert marker["state"] == "STARTED"
    assert list(database_directory.glob(f"{migration.STAGE_PREFIX}*.staging"))
    with pytest.raises(migration.ProductionMigrationError, match="operator review"):
        _run(source)


def test_interrupted_backup_progress_leaves_evidence_and_blocks_retry(
    migration_case: tuple[Path, Path, Path],
) -> None:
    source, _project_root, database_directory = migration_case
    progress_calls = 0

    def inject(event: str, stage: Path) -> None:
        nonlocal progress_calls
        if event == "backup_progress" and stage.name == "lottolab.db":
            progress_calls += 1
            if progress_calls == 1:
                raise migration.ProductionMigrationError("injected backup interruption")

    with pytest.raises(migration.ProductionMigrationError, match="backup failed"):
        migration.ensure_migration_complete(
            lock_validator=lambda: None,
            source_directory=source,
            _fault_hook=inject,
        )
    assert progress_calls == 1
    assert _read_marker(database_directory)["state"] == "STARTED"
    with pytest.raises(migration.ProductionMigrationError, match="operator review"):
        _run(source)


def test_insufficient_space_and_lock_loss_stop_before_database_publish(
    migration_case: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _project_root, database_directory = migration_case

    def no_space(_path: Path) -> int:
        return 0

    def enough_space(_path: Path) -> int:
        return 10**12

    monkeypatch.setattr(migration, "_available_bytes", no_space)
    with pytest.raises(migration.ProductionMigrationError, match="insufficient free space"):
        _run(source)
    assert not (database_directory / migration.MARKER_FILENAME).exists()
    assert not (database_directory / "lottolab.db").exists()

    monkeypatch.setattr(migration, "_available_bytes", enough_space)

    def lock_lost() -> None:
        raise migration.ProductionMigrationError("scheduler lock was replaced")

    with pytest.raises(migration.ProductionMigrationError, match="replaced"):
        migration.ensure_migration_complete(lock_validator=lock_lost, source_directory=source)
    assert not (database_directory / migration.MARKER_FILENAME).exists()
    assert not (database_directory / "lottolab.db").exists()


def test_unsafe_project_directory_permissions_fail_closed(
    migration_case: tuple[Path, Path, Path],
) -> None:
    source, _project_root, database_directory = migration_case
    database_directory.mkdir(mode=0o755, parents=True)
    database_directory.chmod(0o755)
    with pytest.raises(migration.ProductionMigrationError, match="mode 0700"):
        _run(source)
    assert not (database_directory / migration.MARKER_FILENAME).exists()


def test_concurrent_scheduler_start_cannot_enter_migration(
    migration_case: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    source, _project_root, _database_directory = migration_case
    lock_path = tmp_path / "scheduler" / "b649-goalc.lock"
    lock_path.parent.mkdir(mode=0o700)
    first = AdvisoryProcessLock(lock_path)
    first.__enter__()
    try:
        first.assert_held()
        assert _run(source)["status"] == "COMMITTED"
        second = AdvisoryProcessLock(lock_path)
        with pytest.raises(SchedulerAlreadyRunning):
            second.__enter__()
    finally:
        first.__exit__(None, None, None)


def test_static_conflict_sidecar_and_source_replacement_fail_closed(
    migration_case: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, project_root, database_directory = migration_case
    database_directory.mkdir(mode=0o700, parents=True)
    database_directory.chmod(0o700)
    conflict = database_directory / "authorities/nested/seal.json"
    conflict.parent.parent.mkdir(mode=0o700)
    conflict.parent.mkdir(mode=0o700)
    conflict.write_text("owner version\n", encoding="utf-8")
    conflict.chmod(0o600)
    with pytest.raises(migration.ProductionMigrationError, match="target conflicts"):
        _run(source)
    assert conflict.read_text() == "owner version\n"

    source2 = project_root / "second-library"
    source2.mkdir(mode=0o700)
    source_database = source2 / "lottolab.db"
    with sqlite3.connect(source_database) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    source_database.chmod(0o600)
    (source2 / "lottolab.db-wal").write_bytes(b"pending WAL")
    database_directory2 = project_root / "data-sidecar" / "databases"
    monkeypatch.setattr(migration, "project_database_directory", lambda: database_directory2)
    with pytest.raises(migration.ProductionMigrationError, match="sidecar"):
        migration.ensure_migration_complete(
            lock_validator=lambda: None,
            source_directory=source2,
        )


def test_source_replacement_after_backup_fails_before_publish(
    migration_case: tuple[Path, Path, Path],
) -> None:
    source, _project_root, database_directory = migration_case
    replacement = source / "replacement.sqlite"
    with sqlite3.connect(replacement) as connection:
        connection.execute("CREATE TABLE replacement (id INTEGER PRIMARY KEY)")
    replacement.chmod(0o600)

    def inject(event: str, stage: Path) -> None:
        if event == "stage_written" and stage.name == "lottolab.db":
            os.replace(replacement, source / "lottolab.db")

    with pytest.raises(migration.ProductionMigrationError):
        migration.ensure_migration_complete(
            lock_validator=lambda: None,
            source_directory=source,
            _fault_hook=inject,
        )
    assert not (database_directory / "lottolab.db").exists()
    assert _read_marker(database_directory)["state"] == "STARTED"


def test_marker_commit_write_failure_leaves_replaced_state_blocked(
    migration_case: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _project_root, database_directory = migration_case
    original = cast(
        Callable[[Path, Mapping[str, object]], None],
        migration._atomic_marker_write,  # pyright: ignore[reportPrivateUsage]
    )

    def fail_commit(marker_path: Path, payload: object) -> None:
        if (
            isinstance(payload, dict)
            and cast(dict[str, object], payload).get("state") == "COMMITTED"
        ):
            raise OSError("injected marker fsync/write failure")
        original(marker_path, payload)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(migration, "_atomic_marker_write", fail_commit)
    with pytest.raises(OSError, match="marker"):
        _run(source)
    assert (database_directory / "lottolab.db").is_file()
    assert _read_marker(database_directory)["state"] == "REPLACED_PENDING_COMMIT"
    monkeypatch.setattr(migration, "_atomic_marker_write", original)
    with pytest.raises(migration.ProductionMigrationError, match="operator review"):
        _run(source)
