"""Safe project-relative database paths for the production scheduler."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import cast

PROJECT_CHECKOUT = Path(__file__).resolve().parents[4]
DATABASE_CONFIG_ENV = "LOTTOLAB_DATABASE_CONFIG"
DATABASE_CONFIG_FILENAME = "database-locations.json"
WRITABLE_DATABASES_KEY = "writable_databases"


def _json_object(value: object) -> dict[str, object] | None:
    """Return a JSON object without accepting arrays or scalar configuration."""
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"cannot inspect project database path: {current}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"project database path cannot contain symlinks: {current}")


def canonical_project_root() -> Path:
    """Resolve a linked checkout to the main checkout without creating anything."""
    checkout = PROJECT_CHECKOUT.resolve(strict=True)
    marker = checkout / ".git"
    try:
        marker_info = os.lstat(marker)
    except OSError as exc:
        raise ValueError("project Git metadata cannot be inspected") from exc
    if stat.S_ISLNK(marker_info.st_mode):
        raise ValueError("project Git metadata must not be a symlink")
    if stat.S_ISDIR(marker_info.st_mode):
        return checkout
    if not stat.S_ISREG(marker_info.st_mode):
        raise ValueError("project Git metadata must be a directory or worktree file")

    try:
        reference = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise ValueError("project worktree metadata is unreadable") from exc
    if not reference.startswith("gitdir: "):
        raise ValueError("invalid project worktree metadata")
    git_directory = Path(reference.removeprefix("gitdir: "))
    if not git_directory.is_absolute():
        git_directory = checkout / git_directory
    _reject_symlink_components(git_directory)
    try:
        git_directory = git_directory.resolve(strict=True)
        common_file = git_directory / "commondir"
        common_info = os.lstat(common_file)
        if not stat.S_ISREG(common_info.st_mode):
            raise ValueError("project common Git directory reference is not a regular file")
        common_reference = common_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise ValueError("project common Git directory cannot be identified") from exc
    if not common_reference:
        raise ValueError("missing common Git directory")
    common_directory = Path(common_reference)
    if not common_directory.is_absolute():
        common_directory = git_directory / common_directory
    _reject_symlink_components(common_directory)
    try:
        common_directory = common_directory.resolve(strict=True)
        common_info = os.lstat(common_directory)
    except OSError as exc:
        raise ValueError("canonical project Git directory cannot be inspected") from exc
    if (
        common_directory.name != ".git"
        or not stat.S_ISDIR(common_info.st_mode)
        or stat.S_ISLNK(common_info.st_mode)
    ):
        raise ValueError("canonical project Git directory cannot be identified")
    return common_directory.parent


def project_database_directory() -> Path:
    """Return the canonical project database root; never create it."""
    return canonical_project_root() / "data" / "databases"


def is_project_database_boundary(path: Path, git_ancestor: Path) -> bool:
    """Permit only the canonical project's data/databases subtree in a checkout."""
    try:
        root = canonical_project_root()
        directory = project_database_directory()
        selected = Path(path)
        ancestor = Path(git_ancestor)
        if (
            not selected.is_absolute()
            or not ancestor.is_absolute()
            or ".." in selected.parts
            or not selected.is_relative_to(directory)
            or ancestor.resolve(strict=True) != root
        ):
            return False
        _reject_symlink_components(selected)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _configuration(environment: Mapping[str, str]) -> dict[str, object]:
    """Load the optional v1 project database policy, failing closed if malformed."""
    configured = environment.get(DATABASE_CONFIG_ENV)
    if configured == "":
        raise ValueError(f"{DATABASE_CONFIG_ENV} must not be empty")
    path = (
        project_database_directory() / DATABASE_CONFIG_FILENAME
        if configured is None
        else Path(configured)
    )
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("database configuration must be an absolute path without traversal")
    _reject_symlink_components(path)
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("database configuration must be a regular file")
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if configured is None:
            return {}
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("database configuration is unreadable or invalid") from exc
    payload = _json_object(parsed)
    if payload is None or payload.get("version") != 1:
        raise ValueError("unsupported project database configuration")
    return payload


def require_project_database_write_ready(database: Path) -> None:
    """Require both writable_databases policy and a verified COMMITTED migration."""
    root = project_database_directory()
    selected = Path(database)
    if not selected.is_absolute() or not selected.is_relative_to(root):
        return
    if selected.parent != root:
        raise PermissionError("only the canonical project database root may be writable")
    _reject_symlink_components(selected)
    try:
        info = os.lstat(selected)
    except OSError as exc:
        raise FileNotFoundError("canonical project database is missing") from exc
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
        raise PermissionError("canonical project database must be a private, unlinked regular file")

    policy = _configuration(os.environ)
    writable = policy.get(WRITABLE_DATABASES_KEY, [])
    if not isinstance(writable, list):
        raise ValueError("writable_databases must be a list of filenames")
    writable_items = cast(list[object], writable)
    if any(not isinstance(item, str) for item in writable_items):
        raise ValueError("writable_databases must be a list of filenames")
    if selected.name not in cast(list[str], writable_items):
        raise PermissionError("canonical project database is not enabled for writes")

    from lottolab.infrastructure.persistence.production_migration_v51 import (
        assert_migration_committed,
    )

    assert_migration_committed(selected)


__all__ = [
    "canonical_project_root",
    "is_project_database_boundary",
    "project_database_directory",
    "require_project_database_write_ready",
]
