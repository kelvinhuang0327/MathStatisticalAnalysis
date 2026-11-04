from __future__ import annotations

import hashlib
import json
import os
import runpy
import shutil
import subprocess
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


def _git_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    ignored: bool = True,
) -> Path:
    repo = tmp_path / "scratch-checkout"
    repo.mkdir()
    subprocess.run(("git", "init", "--quiet", str(repo)), check=True)
    if ignored:
        (repo / ".gitignore").write_text(".task-data/\n", encoding="utf-8")
    monkeypatch.setattr(locations, "PROJECT_ROOT", repo)
    return repo


@pytest.mark.parametrize(
    "case",
    [
        "other_git_worktree",
        "parent_component",
        "symlink_component",
        "other_checkout_scratch",
        "task_data_non_scratch",
        "canonical_root_other_directory",
        "b649_uppercase",
        "b649_lowercase",
        "lotterynew_uppercase_component",
        "lotterynew_lowercase_component",
        "unignored_scratch_root",
    ],
)
def test_project_scratch_database_boundary_rejects_unsafe_paths(
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _git_project(tmp_path, monkeypatch, ignored=case != "unignored_scratch_root")
    scratch = repo / ".task-data" / "_scratch"
    path = scratch / "unit_db_01" / "test.sqlite3"
    git_ancestor = repo

    if case == "other_git_worktree":
        linked = tmp_path / "linked-worktree"
        linked.mkdir()
        git_directory = repo / ".git" / "worktrees" / "linked-worktree"
        git_directory.mkdir(parents=True)
        (git_directory / "commondir").write_text("../..\n", encoding="utf-8")
        (linked / ".git").write_text(f"gitdir: {git_directory}\n", encoding="utf-8")
        monkeypatch.setattr(locations, "PROJECT_ROOT", linked)
        path = linked / ".task-data" / "_scratch" / "unit_db_01" / "test.sqlite3"
        git_ancestor = linked
    elif case == "parent_component":
        path = scratch / "unit_db_01" / ".." / "test.sqlite3"
    elif case == "symlink_component":
        (scratch / "target").mkdir(parents=True)
        (scratch / "linked").symlink_to(scratch / "target", target_is_directory=True)
        path = scratch / "linked" / "test.sqlite3"
    elif case == "other_checkout_scratch":
        other = tmp_path / "other-checkout"
        other.mkdir()
        subprocess.run(("git", "init", "--quiet", str(other)), check=True)
        (other / ".gitignore").write_text(".task-data/\n", encoding="utf-8")
        path = other / ".task-data" / "_scratch" / "unit_db_01" / "test.sqlite3"
        git_ancestor = other
    elif case == "task_data_non_scratch":
        path = repo / ".task-data" / "unit_db_01" / "test.sqlite3"
    elif case == "canonical_root_other_directory":
        path = repo / "var" / "unit_db_01" / "test.sqlite3"
    elif case == "b649_uppercase":
        path = scratch / "unit_B649_db" / "test.sqlite3"
    elif case == "b649_lowercase":
        path = scratch / "unit_b649_db" / "test.sqlite3"
    elif case == "lotterynew_uppercase_component":
        path = scratch / "LotteryNew" / "test.sqlite3"
    elif case == "lotterynew_lowercase_component":
        path = scratch / "lotterynew" / "test.sqlite3"
    elif case == "unignored_scratch_root":
        pass

    assert not locations.is_project_scratch_database_boundary(path, git_ancestor)


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


def _write_legacy_index(project: Path, records: dict[str, object]) -> None:
    index = project / "data/databases/legacy/INDEX.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"original_path_lookup": records}), encoding="utf-8")


def test_legacy_resolver_prefers_keeper_when_original_and_keeper_exist(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "retired" / "old.sqlite3"
    original.parent.mkdir()
    original.touch()
    keeper = project / "data/databases/legacy/group/keeper.sqlite3"
    keeper.parent.mkdir(parents=True)
    keeper.touch()
    _write_legacy_index(
        project,
        {str(original.resolve()): {"keeper_path": str(keeper), "keeper_status": "PASS"}},
    )

    assert locations.resolve_legacy_database(original) == keeper


def test_legacy_resolver_uses_keeper_when_original_is_already_missing(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "retired" / "old.sqlite3"
    keeper = project / "data/databases/legacy/group/keeper.sqlite3"
    keeper.parent.mkdir(parents=True)
    keeper.touch()
    _write_legacy_index(
        project,
        {str(original.resolve()): {"keeper_path": str(keeper), "keeper_status": "PASS"}},
    )

    assert locations.resolve_legacy_database(original) == keeper


def test_legacy_resolver_fails_closed_when_registered_keeper_is_missing(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "retired" / "old.sqlite3"
    keeper = project / "data/databases/legacy/group/missing.sqlite3"
    _write_legacy_index(
        project,
        {str(original.resolve()): {"keeper_path": str(keeper), "keeper_status": "PASS"}},
    )

    with pytest.raises(FileNotFoundError) as error:
        locations.resolve_legacy_database(original)
    assert str(original) in str(error.value)
    assert str(keeper) in str(error.value)
    assert "CLOUD_BACKUP_RESTORE.md" in str(error.value)
    assert not original.exists()
    assert not keeper.exists()


def test_legacy_resolver_keeps_existing_unregistered_path(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "unregistered.sqlite3"
    original.touch()
    _write_legacy_index(project, {})

    assert locations.resolve_legacy_database(original) == original.resolve()


def test_legacy_resolver_rejects_missing_unregistered_path(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "unregistered.sqlite3"
    _write_legacy_index(project, {})

    with pytest.raises(FileNotFoundError, match="not registered and does not exist"):
        locations.resolve_legacy_database(original)
    assert not original.exists()


def test_legacy_resolver_rejects_malformed_index(
    project: Path,
    tmp_path: Path,
) -> None:
    index = project / "data/databases/legacy/INDEX.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="unreadable or invalid"):
        locations.resolve_legacy_database(tmp_path / "unregistered.sqlite3")


def test_legacy_resolver_rejects_missing_index(project: Path, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="legacy database index is missing"):
        locations.resolve_legacy_database(tmp_path / "unregistered.sqlite3")


def test_legacy_resolver_rejects_wrong_index_shape(
    project: Path,
    tmp_path: Path,
) -> None:
    index = project / "data/databases/legacy/INDEX.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"original_path_lookup": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid format"):
        locations.resolve_legacy_database(tmp_path / "unregistered.sqlite3")


def test_legacy_default_path_without_index_returns_original_and_creates_nothing(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "retired" / "old.sqlite3"

    assert locations.default_legacy_database_path(original) == original.resolve()
    assert not original.exists()
    assert not (project / "data/databases").exists()


def test_legacy_default_path_returns_existing_keeper(project: Path, tmp_path: Path) -> None:
    original = tmp_path / "retired" / "old.sqlite3"
    keeper = project / "data/databases/legacy/group/keeper.sqlite3"
    keeper.parent.mkdir(parents=True)
    keeper.touch()
    _write_legacy_index(
        project,
        {str(original.resolve()): {"keeper_path": str(keeper), "keeper_status": "PASS"}},
    )

    assert locations.default_legacy_database_path(original) == keeper


def test_legacy_default_path_never_falls_back_to_the_retired_file(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "retired" / "old.sqlite3"
    original.parent.mkdir()
    original.touch()
    keeper = project / "data/databases/legacy/group/missing.sqlite3"
    _write_legacy_index(
        project,
        {str(original.resolve()): {"keeper_path": str(keeper), "keeper_status": "PASS"}},
    )

    resolved = locations.default_legacy_database_path(original)

    assert resolved == keeper
    assert not resolved.exists()


def test_legacy_default_path_returns_unregistered_original_even_when_missing(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "unregistered.sqlite3"
    _write_legacy_index(project, {})

    assert locations.default_legacy_database_path(original) == original.resolve()
    assert not original.exists()


def test_legacy_default_path_still_fails_for_unverified_keeper_or_bad_index(
    project: Path,
    tmp_path: Path,
) -> None:
    original = tmp_path / "retired" / "old.sqlite3"
    keeper = project / "data/databases/legacy/group/keeper.sqlite3"
    keeper.parent.mkdir(parents=True)
    keeper.touch()
    _write_legacy_index(
        project,
        {str(original.resolve()): {"keeper_path": str(keeper), "keeper_status": "FAIL"}},
    )
    with pytest.raises(FileNotFoundError, match="keeper is unavailable"):
        locations.default_legacy_database_path(original)

    (project / "data/databases/legacy/INDEX.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable or invalid"):
        locations.default_legacy_database_path(original)


@pytest.mark.parametrize(
    "module",
    ["lottolab.research.b649_eh01_eh10_dataset", "lottolab.research.b649_eh02_dataset"],
)
def test_research_dataset_modules_import_without_a_keeper_index(
    module: str, tmp_path: Path
) -> None:
    source_root = Path(locations.__file__).resolve().parents[3]
    code = (
        "import importlib, pathlib, sys\n"
        "import lottolab.infrastructure.persistence.project_database_paths as paths\n"
        "root = pathlib.Path(sys.argv[1]) / 'data' / 'databases'\n"
        "paths.project_database_directory = lambda: root\n"
        "importlib.import_module(sys.argv[2])\n"
    )
    environment = {**os.environ, "PYTHONPATH": str(source_root), "PYTHONDONTWRITEBYTECODE": "1"}

    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), module],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "data").exists()


def test_legacy_keeper_preserves_original_source_identity_from_index(
    project: Path,
) -> None:
    keeper = project / "data/databases/legacy/group/keeper.sqlite3"
    keeper.parent.mkdir(parents=True)
    keeper.write_bytes(b"keeper bytes")
    keeper_sha256 = hashlib.sha256(keeper.read_bytes()).hexdigest()
    original_sha256 = "a" * 64
    _write_legacy_index(
        project,
        {
            "/retired/original.sqlite3": {
                "keeper_path": str(keeper),
                "keeper_status": "PASS",
                "original_sha256": original_sha256,
                "group_key": "group-1",
            }
        },
    )
    index = project / "data/databases/legacy/INDEX.json"
    payload = json.loads(index.read_text(encoding="utf-8"))
    payload["groups"] = [{"group_key": "group-1", "keeper_sha256": keeper_sha256}]
    index.write_text(json.dumps(payload), encoding="utf-8")

    assert locations.is_verified_legacy_keeper_for_source(
        keeper, original_sha256=original_sha256, keeper_sha256=keeper_sha256
    )
    assert not locations.is_verified_legacy_keeper_for_source(
        keeper, original_sha256="b" * 64, keeper_sha256=keeper_sha256
    )


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


@pytest.fixture
def tmp_path(outside_git_tmp_path: Path) -> Path:
    """Use a neutral external path for tests that exercise outside-checkout behavior."""
    return outside_git_tmp_path
