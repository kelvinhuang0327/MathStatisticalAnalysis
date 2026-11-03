"""Project-relative database locations; resolving a path never creates a database."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATABASE_CONFIG_ENV = "LOTTOLAB_DATABASE_CONFIG"
DATABASE_CONFIG_FILENAME = "database-locations.json"


def canonical_project_root() -> Path:
    """A linked checkout shares the main project's data, not another empty store."""
    marker = PROJECT_ROOT / ".git"
    if marker.is_symlink():
        raise ValueError("project Git metadata must not be a symlink")
    if not marker.is_file():
        return PROJECT_ROOT
    reference = marker.read_text(encoding="utf-8").strip()
    if not reference.startswith("gitdir: "):
        raise ValueError("invalid project worktree metadata")
    git_directory = Path(reference.removeprefix("gitdir: "))
    if not git_directory.is_absolute():
        git_directory = PROJECT_ROOT / git_directory
    common_reference = (git_directory / "commondir").read_text(encoding="utf-8").strip()
    if not common_reference:
        raise ValueError("missing common Git directory")
    common_directory = (git_directory / common_reference).resolve(strict=True)
    if common_directory.name != ".git" or not common_directory.is_dir():
        raise ValueError("canonical project Git directory cannot be identified")
    return common_directory.parent


def project_database_directory() -> Path:
    return canonical_project_root() / "data" / "databases"


def resolve_legacy_database(original: Path) -> Path:
    """Resolve an archived absolute database path through the project keeper index."""
    original_path = Path(original).expanduser().resolve()
    index_path = project_database_directory() / "legacy" / "INDEX.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"legacy database index is missing: {index_path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"legacy database index is unreadable or invalid: {index_path}") from exc

    if not isinstance(index, dict) or not isinstance(index.get("original_path_lookup"), dict):
        raise ValueError(f"legacy database index has an invalid format: {index_path}")
    record = index["original_path_lookup"].get(str(original_path))
    if record is not None:
        if not isinstance(record, dict):
            raise ValueError(f"legacy database index record is invalid for {original_path}")
        keeper_raw = record.get("keeper_path")
        keeper = Path(keeper_raw) if isinstance(keeper_raw, str) else None
        if record.get("keeper_status") == "PASS" and keeper is not None:
            legacy_root = (project_database_directory() / "legacy").resolve()
            if not keeper.resolve().is_relative_to(legacy_root):
                raise ValueError(f"legacy keeper escapes the project legacy directory: {keeper}")
            if keeper.is_file():
                return keeper
        keeper_label = str(keeper) if keeper is not None else "<missing keeper_path>"
        raise FileNotFoundError(
            f"legacy database keeper is unavailable for {original_path}: {keeper_label}. "
            "可依 data/databases/CLOUD_BACKUP_RESTORE.md 從雲端還原"
        )
    if original_path.is_file():
        return original_path
    raise FileNotFoundError(f"database is not registered and does not exist: {original_path}")


def is_verified_legacy_keeper_for_source(
    keeper_path: Path, *, original_sha256: str, keeper_sha256: str
) -> bool:
    """Check that INDEX verifies this keeper for a frozen original-file hash."""
    index_path = project_database_directory() / "legacy" / "INDEX.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"legacy database index is unreadable or invalid: {index_path}") from exc
    lookup = index.get("original_path_lookup") if isinstance(index, dict) else None
    groups = index.get("groups") if isinstance(index, dict) else None
    if not isinstance(lookup, dict) or not isinstance(groups, list):
        raise ValueError(f"legacy database index has an invalid format: {index_path}")
    keeper_hashes = {
        item.get("group_key"): item.get("keeper_sha256")
        for item in groups
        if isinstance(item, dict)
    }

    selected = keeper_path.resolve()
    legacy_root = (project_database_directory() / "legacy").resolve()
    if not selected.is_relative_to(legacy_root):
        return False
    return any(
        isinstance(record, dict)
        and record.get("keeper_status") == "PASS"
        and record.get("original_sha256") == original_sha256
        and keeper_hashes.get(record.get("group_key")) == keeper_sha256
        and isinstance(record.get("keeper_path"), str)
        and Path(record["keeper_path"]).resolve() == selected
        for record in lookup.values()
    )


def is_project_database_boundary(path: Path, git_ancestor: Path) -> bool:
    """Permit only this source checkout's database subtree, not another checkout."""
    return (
        ".." not in path.parts
        and path.is_relative_to(project_database_directory())
        and git_ancestor == canonical_project_root()
    )


def _configuration(environment: Mapping[str, str]) -> dict[str, object]:
    configured = environment.get(DATABASE_CONFIG_ENV)
    if configured == "":
        return {}
    path = (
        project_database_directory() / DATABASE_CONFIG_FILENAME
        if configured is None
        else Path(configured)
    )
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("database configuration must be an absolute path without traversal")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("database configuration must not contain symlinks")
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if configured is None:
            return {}
        raise
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("unsupported project database configuration")
    return payload


def project_database_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Supply verified optional API locations; explicit environment values win."""
    result = dict(environment)
    bindings = _configuration(environment).get("read_databases", {})
    if not isinstance(bindings, dict):
        raise ValueError("read_databases must be an object")
    for key, relative in bindings.items():
        if not isinstance(key, str) or not key.startswith("LOTTOLAB_") or not key.endswith("_DB"):
            raise ValueError("unsupported database environment key")
        if not isinstance(relative, str) or not relative:
            raise ValueError("database location must be a nonempty project-relative path")
        selected = Path(relative)
        if selected.is_absolute() or ".." in selected.parts or selected.parts[0] == "backups":
            raise ValueError("database location must stay inside the project database directory")
        target = project_database_directory() / selected
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError("project database location must not contain symlinks")
        result.setdefault(key, str(target))
    return result


def require_project_database_write_ready(database: Path) -> None:
    """Keep staged copies read-only until all legacy writers have been cut over.

    Explicit test stores outside the canonical directory retain their existing
    initialization contract. A missing canonical database is never bootstrapped.
    """
    root = project_database_directory()
    if not database.is_relative_to(root):
        return
    if database.parent != root or not database.is_file():
        raise FileNotFoundError("canonical database is missing or is an archived read-only source")
    ready = _configuration({}).get("writable_databases", [])
    if not isinstance(ready, list) or database.name not in ready:
        raise PermissionError(
            "canonical database cutover is pending; the preserved snapshot is read-only"
        )


__all__ = [
    "is_project_database_boundary",
    "is_verified_legacy_keeper_for_source",
    "project_database_directory",
    "project_database_environment",
    "require_project_database_write_ready",
    "resolve_legacy_database",
]
