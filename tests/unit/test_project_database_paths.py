from __future__ import annotations

import json
import runpy
import shutil
import sys
from pathlib import Path

import pytest

from lottolab.infrastructure.persistence import project_database_paths as locations
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
    verify_schema_read_only,
)
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SQLiteBackfillStore,
    validate_database_path,
)
from lottolab.infrastructure.persistence.research_schema import (
    initialize_schema as initialize_research_schema,
)
from lottolab.infrastructure.persistence.research_schema import (
    resolve_research_data_paths,
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "checkout"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(locations, "PROJECT_ROOT", repo)
    return repo


def test_project_default_ignores_cwd_and_home_without_creating_empty_db(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = project / "data/databases"
    paths = resolve_local_data_paths(environ={}, home=tmp_path / "unused-home")
    research = resolve_research_data_paths(environ={}, home=tmp_path / "unused-home")
    assert paths.database == root / "lottolab.db"
    assert research.database == root / "lottolab_research.db"
    assert verify_schema_read_only(paths) is False
    with pytest.raises(FileNotFoundError, match="canonical database"):
        initialize_schema(paths)
    with pytest.raises(FileNotFoundError, match="canonical database"):
        initialize_research_schema(research)
    assert not root.exists()


def test_only_exact_project_database_subtree_is_allowed(project: Path) -> None:
    root = project / "data/databases"
    assert validate_database_path(root / "replay.sqlite3") == root / "replay.sqlite3"
    for denied in (project / "data/other.db", project / "data/databases/../escape.db"):
        with pytest.raises(ValueError, match="Git checkout"):
            validate_database_path(denied)
    nested = root / "nested"
    (nested / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="Git checkout"):
        validate_database_path(nested / "db.sqlite3")


def test_preserved_snapshot_is_readable_but_cannot_become_second_writer(
    project: Path, tmp_path: Path
) -> None:
    fixture = tmp_path / "fixture"
    paths = LocalDataPaths(fixture, fixture / "lottolab.db")
    initialize_schema(paths)
    root = project / "data/databases"
    root.mkdir(mode=0o700, parents=True)
    target = root / "lottolab.db"
    shutil.copyfile(paths.database, target)
    target.chmod(0o600)
    restored = LocalDataPaths(root, target)
    assert verify_schema_read_only(restored)
    before = target.read_bytes()
    with open_database(restored, read_only=True) as connection:
        assert connection.execute("SELECT count(*) FROM draws").fetchone() == (0,)
    with pytest.raises(PermissionError, match="cutover is pending"):
        initialize_schema(restored)
    with pytest.raises(PermissionError, match="cutover is pending"), open_database(restored):
        pytest.fail("a staged copy must not become writable")
    assert target.read_bytes() == before


def test_replay_backfill_writer_rejects_unregistered_canonical_database(
    project: Path,
) -> None:
    root = project / "data/databases"
    root.mkdir(parents=True)
    target = root / "replay-backfill.sqlite3"
    target.write_bytes(b"preserved snapshot")
    before = target.read_bytes()

    with pytest.raises(PermissionError, match="cutover is pending"):
        SQLiteBackfillStore(target).prepare({})

    assert target.read_bytes() == before


def test_read_configuration_uses_project_paths_and_preserves_explicit_overrides(
    project: Path,
) -> None:
    root = project / "data/databases"
    root.mkdir(parents=True)
    (root / locations.DATABASE_CONFIG_FILENAME).write_text(
        json.dumps(
            {
                "version": 1,
                "read_databases": {"LOTTOLAB_P638_CURRENT_REPLAY_DB": "p638.sqlite3"},
                "writable_databases": [],
            }
        )
    )
    key = "LOTTOLAB_P638_CURRENT_REPLAY_DB"
    assert locations.project_database_environment({})[key] == str(root / "p638.sqlite3")
    assert locations.project_database_environment({key: ""})[key] == ""
    assert locations.project_database_environment({locations.DATABASE_CONFIG_ENV: ""}) == {
        locations.DATABASE_CONFIG_ENV: ""
    }
    assert not (root / "p638.sqlite3").exists()


@pytest.mark.parametrize("relative", ["../old.db", "/old/db.sqlite3", "backups/research.db"])
def test_bad_bindings_fail_closed(project: Path, relative: str) -> None:
    root = project / "data/databases"
    root.mkdir(parents=True)
    (root / locations.DATABASE_CONFIG_FILENAME).write_text(
        json.dumps(
            {
                "version": 1,
                "read_databases": {"LOTTOLAB_REPLAY_SCORING_DB": relative},
            }
        )
    )
    with pytest.raises(ValueError, match="inside the project database"):
        locations.project_database_environment({})


def test_project_binding_rejects_symlink(project: Path, tmp_path: Path) -> None:
    root = project / "data/databases"
    root.mkdir(parents=True)
    (root / "escape.db").symlink_to(tmp_path / "elsewhere.db")
    (root / locations.DATABASE_CONFIG_FILENAME).write_text(
        json.dumps(
            {
                "version": 1,
                "read_databases": {"LOTTOLAB_REPLAY_SCORING_DB": "escape.db"},
            }
        )
    )
    with pytest.raises(ValueError, match="symlinks"):
        locations.project_database_environment({})


def test_linked_source_checkout_uses_main_project_database_directory(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Metadata fixture only; no git worktree is created or registered.
    linked_source = tmp_path / "linked-source"
    linked_source.mkdir()
    metadata = project / ".git/worktrees/linked-source"
    metadata.mkdir(parents=True)
    (metadata / "commondir").write_text("../..\n")
    (linked_source / ".git").write_text(f"gitdir: {metadata}\n")
    monkeypatch.setattr(locations, "PROJECT_ROOT", linked_source)
    assert locations.project_database_directory() == project / "data/databases"
    assert resolve_local_data_paths(environ={}).database == project / "data/databases/lottolab.db"
    assert not (linked_source / "data").exists()


def test_k235_cli_uses_shared_default_from_linked_source(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate linked metadata without running git init/commit/worktree commands.
    linked_source = tmp_path / "linked-cli-source"
    (linked_source / "tools").mkdir(parents=True)
    metadata = project / ".git/worktrees/linked-cli-source"
    metadata.mkdir(parents=True)
    (metadata / "commondir").write_text("../..\n")
    (linked_source / ".git").write_text(f"gitdir: {metadata}\n")
    tool = linked_source / "tools/b649_k235_predict.py"
    original = Path(__file__).resolve().parents[2] / "tools/b649_k235_predict.py"
    tool.write_bytes(original.read_bytes())
    monkeypatch.setattr(locations, "PROJECT_ROOT", linked_source)
    monkeypatch.setattr(sys, "path", list(sys.path))
    loaded = runpy.run_path(str(tool))
    assert loaded["REPO_ROOT"] == linked_source
    assert loaded["DEFAULT_DB_PATH"] == project / "data/databases/lottolab.db"
    assert not (linked_source / "data").exists()
