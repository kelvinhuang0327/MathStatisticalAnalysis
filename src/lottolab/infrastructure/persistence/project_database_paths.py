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
    "project_database_directory",
    "project_database_environment",
    "require_project_database_write_ready",
]
