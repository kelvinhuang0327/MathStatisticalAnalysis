"""Project data-root and fail-closed write-policy tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import lottolab.infrastructure.persistence.production_migration_v51 as migration
import lottolab.infrastructure.persistence.project_database_paths as paths


def _database(root: Path) -> Path:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = root / "lottolab.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    database.chmod(0o600)
    return database


def _config(path: Path, writable: list[str]) -> None:
    path.write_text(json.dumps({"version": 1, "writable_databases": writable}), encoding="utf-8")


def test_canonical_project_root_resolves_main_checkout_from_worktree() -> None:
    assert paths.canonical_project_root() == Path(
        "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis"
    )


def test_project_database_boundary_is_narrow_and_rejects_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    databases = project / "data" / "databases"
    databases.mkdir(parents=True)
    monkeypatch.setattr(paths, "canonical_project_root", lambda: project)
    monkeypatch.setattr(paths, "project_database_directory", lambda: databases)

    assert paths.is_project_database_boundary(databases / "lottolab.db", project)
    assert not paths.is_project_database_boundary(project / "data" / "other.db", project)
    assert not paths.is_project_database_boundary(databases / "other.db", tmp_path)

    alias = project / "linked-data"
    alias.symlink_to(databases, target_is_directory=True)
    assert not paths.is_project_database_boundary(alias / "lottolab.db", project)


def test_configuration_is_fail_closed_for_invalid_json_and_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    databases = tmp_path / "data" / "databases"
    databases.mkdir(parents=True)
    monkeypatch.setattr(paths, "project_database_directory", lambda: databases)

    config = databases / paths.DATABASE_CONFIG_FILENAME
    config.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        paths._configuration({})  # pyright: ignore[reportPrivateUsage]

    config.unlink()
    alias = databases / "linked-config.json"
    alias.write_text('{"version":1}', encoding="utf-8")
    config.symlink_to(alias)
    with pytest.raises(ValueError, match="symlinks"):
        paths._configuration({})  # pyright: ignore[reportPrivateUsage]


def test_write_guard_requires_writable_policy_and_committed_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    databases = tmp_path / "data" / "databases"
    database = _database(databases)
    config = databases / paths.DATABASE_CONFIG_FILENAME
    _config(config, ["lottolab.db"])
    monkeypatch.setattr(paths, "project_database_directory", lambda: databases)
    monkeypatch.setenv(paths.DATABASE_CONFIG_ENV, str(config))
    committed: list[Path] = []

    def assert_committed(selected: Path) -> None:
        committed.append(selected)

    monkeypatch.setattr(migration, "assert_migration_committed", assert_committed)
    paths.require_project_database_write_ready(database)
    assert committed == [database]


def test_write_guard_blocks_uncommitted_migration_and_disabled_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    databases = tmp_path / "data" / "databases"
    database = _database(databases)
    config = databases / paths.DATABASE_CONFIG_FILENAME
    _config(config, [])
    monkeypatch.setattr(paths, "project_database_directory", lambda: databases)
    monkeypatch.setenv(paths.DATABASE_CONFIG_ENV, str(config))

    def unexpected_commit(_database: Path) -> None:
        raise AssertionError("migration marker must not be checked when policy denies writes")

    monkeypatch.setattr(migration, "assert_migration_committed", unexpected_commit)
    with pytest.raises(PermissionError, match="not enabled"):
        paths.require_project_database_write_ready(database)

    _config(config, ["lottolab.db"])

    def pending_commit(_database: Path) -> None:
        raise PermissionError("not committed")

    monkeypatch.setattr(migration, "assert_migration_committed", pending_commit)
    with pytest.raises(PermissionError, match="not committed"):
        paths.require_project_database_write_ready(database)


def test_non_project_database_keeps_existing_write_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    databases = tmp_path / "project" / "data" / "databases"
    monkeypatch.setattr(paths, "project_database_directory", lambda: databases)
    outside = tmp_path / "isolated-tests" / "lottolab.db"
    paths.require_project_database_write_ready(outside)
