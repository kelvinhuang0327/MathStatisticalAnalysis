"""Fail-closed first-start migration from the retired Library data root.

The scheduler calls this only after holding its process lock. This module never
starts launchd, modifies the Library source, or performs a recovery guess for an
incomplete migration. A non-COMMITTED marker always requires operator review.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import struct
from collections.abc import Callable, Mapping
from contextlib import closing
from pathlib import Path
from typing import cast
from urllib.parse import quote
from uuid import uuid4

from lottolab.infrastructure.persistence.project_database_paths import (
    project_database_directory,
)

LEGACY_DATA_DIRECTORY = Path.home() / "Library" / "Application Support" / "LottoLab"
MARKER_FILENAME = ".lottolab-migration-v51.json"
DATABASE_FILENAME = "lottolab.db"
STAGE_PREFIX = ".lottolab-migration-v51-"
PRE_MIGRATION_PREFIX = "lottolab.db.pre-migration-"
CONFIG_FILENAME = "database-locations.json"
RESERVED_FREE_BYTES = 1024 * 1024 * 1024
RELEASE_ID = "v51-data-root-migration-r1"
EXCLUDED_RELATIVE_PATHS = {"lottolab.sqlite"}
EXCLUDED_TOP_LEVEL_DIRECTORIES = {"migration-backups"}
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
RELEASE_FILES = (
    "src/lottolab/infrastructure/persistence/production_migration_v51.py",
    "src/lottolab/infrastructure/persistence/project_database_paths.py",
    "src/lottolab/infrastructure/persistence/draw_schema.py",
    "tools/b649_goalc_local_scheduler.py",
)
FaultHook = Callable[[str, Path], None]
LockValidator = Callable[[], None]


class ProductionMigrationError(RuntimeError):
    """The migration cannot be proved safe to start or continue."""


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_roundtrip(value: object) -> object:
    return json.loads(json.dumps(value))


def _json_object_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProductionMigrationError("migration marker contains an invalid JSON object")
    keys = cast(dict[object, object], value).keys()
    if not all(isinstance(key, str) for key in keys):
        raise ProductionMigrationError("migration marker contains an invalid JSON object")
    return cast(dict[str, object], value)


def _required_int(value: object, description: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProductionMigrationError(f"migration record has an invalid {description}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, int]:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ProductionMigrationError(f"cannot inspect migration file: {path}") from exc
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
        raise ProductionMigrationError(f"migration file must be an unlinked regular file: {path}")
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "size": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
        "mode": stat.S_IMODE(info.st_mode),
    }


def _private_file_mode(source_mode: int) -> int:
    """Retain owner permissions and read-only status, while removing group access."""
    mode = source_mode & 0o700
    if mode & 0o400 == 0:
        raise ProductionMigrationError("legacy data file is not readable by its owner")
    return mode


def _directory_identity(path: Path) -> dict[str, int]:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ProductionMigrationError(f"cannot inspect migration directory: {path}") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ProductionMigrationError(f"migration path must be a real directory: {path}")
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
        "mode": stat.S_IMODE(info.st_mode),
    }


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ProductionMigrationError(f"cannot inspect path component: {current}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise ProductionMigrationError(f"migration paths cannot contain symlinks: {current}")


def _ensure_database_directory(path: Path) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise ProductionMigrationError("project database directory is not a safe absolute path")
    _reject_symlink_components(path)
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = os.lstat(path)
    except OSError as exc:
        raise ProductionMigrationError("cannot prepare project database directory") from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ProductionMigrationError("project database directory must be owner-only mode 0700")


def _sync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ProductionMigrationError(f"cannot durably sync directory: {path}") from exc


def _ensure_owner_directory(path: Path, *, mode: int = 0o700) -> None:
    _reject_symlink_components(path)
    missing: list[Path] = []
    current = path
    while True:
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            missing.append(current)
            current = current.parent
            continue
        except OSError as exc:
            raise ProductionMigrationError(
                f"cannot inspect migration directory: {current}"
            ) from exc
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ProductionMigrationError(
                f"migration directory is not a real directory: {current}"
            )
        if missing and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode):
            raise ProductionMigrationError(f"migration parent directory is unsafe: {current}")
        break
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=mode)
            info = os.lstat(directory)
        except OSError as exc:
            raise ProductionMigrationError(
                f"cannot create migration directory: {directory}"
            ) from exc
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != mode
        ):
            raise ProductionMigrationError(
                f"migration directory has unsafe ownership or mode: {directory}"
            )


def _sidecar_paths(database: Path) -> tuple[Path, ...]:
    return tuple(Path(f"{database}{suffix}") for suffix in SIDECAR_SUFFIXES)


def _reject_sidecars(database: Path) -> None:
    for sidecar in _sidecar_paths(database):
        try:
            os.lstat(sidecar)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ProductionMigrationError(f"cannot inspect SQLite sidecar: {sidecar}") from exc
        raise ProductionMigrationError(f"SQLite sidecar blocks migration: {sidecar.name}")


def _iter_inventory(source_root: Path) -> list[dict[str, object]]:
    _reject_symlink_components(source_root)
    try:
        root_info = os.lstat(source_root)
    except OSError as exc:
        raise ProductionMigrationError("legacy Library data directory is unavailable") from exc
    if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
        raise ProductionMigrationError("legacy Library data root must be a real directory")
    if root_info.st_uid != os.getuid():
        raise ProductionMigrationError("legacy Library data root must belong to the current user")

    records: list[dict[str, object]] = []
    pending: list[Path] = [source_root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as scan:
                children = sorted(scan, key=lambda entry: entry.name)
        except OSError as exc:
            raise ProductionMigrationError(f"cannot enumerate legacy source: {directory}") from exc
        for child in children:
            path = Path(child.path)
            relative = path.relative_to(source_root).as_posix()
            try:
                info = os.lstat(path)
            except OSError as exc:
                raise ProductionMigrationError(f"cannot inspect legacy source: {relative}") from exc
            if stat.S_ISLNK(info.st_mode):
                raise ProductionMigrationError(f"legacy source contains a symlink: {relative}")
            if stat.S_ISDIR(info.st_mode):
                if info.st_uid != os.getuid():
                    raise ProductionMigrationError(
                        f"legacy source directory has a different owner: {relative}"
                    )
                record: dict[str, object] = {
                    "path": relative,
                    "kind": "directory",
                    "identity": _directory_identity(path),
                }
                records.append(record)
                if relative not in EXCLUDED_TOP_LEVEL_DIRECTORIES:
                    pending.append(path)
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ProductionMigrationError(
                    f"legacy source is not a private regular file: {relative}"
                )
            if info.st_uid != os.getuid():
                raise ProductionMigrationError(
                    f"legacy source file has a different owner: {relative}"
                )
            if relative.endswith(SIDECAR_SUFFIXES):
                raise ProductionMigrationError(
                    f"legacy source contains a SQLite sidecar: {relative}"
                )
            if (
                relative in EXCLUDED_RELATIVE_PATHS
                or relative.split("/", 1)[0] in EXCLUDED_TOP_LEVEL_DIRECTORIES
            ):
                continue
            records.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": info.st_size,
                    "identity": _file_identity(path),
                }
            )
    return sorted(records, key=lambda item: str(item["path"]))


def _source_record_map(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for item in records:
        relative = item.get("path")
        if not isinstance(relative, str):
            raise ProductionMigrationError("source inventory contains an invalid path")
        result[relative] = item
    return result


def _inventory_size(records: list[dict[str, object]]) -> int:
    size = 0
    for item in records:
        if item.get("kind") == "file":
            size += _required_int(item.get("size"), "file size")
    return size


def _available_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError as exc:
        raise ProductionMigrationError("cannot determine available project disk space") from exc


def _sqlite_uri(path: Path, *, immutable: bool) -> str:
    uri = f"file:{quote(str(path), safe='/')}?mode=ro"
    if immutable:
        uri += "&immutable=1"
    return uri


def _connect_read_only(path: Path, *, immutable: bool) -> sqlite3.Connection:
    connection = sqlite3.connect(_sqlite_uri(path, immutable=immutable), uri=True, timeout=5)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    return connection


def _qi(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _typed_snapshot(connection: sqlite3.Connection) -> dict[str, object]:
    """Hash typed rows, complete schema, versions, and row counts deterministically."""
    schema = [
        list(row)
        for row in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
        )
    ]
    result: dict[str, object] = {
        "schema": schema,
        "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
        "application_id": connection.execute("PRAGMA application_id").fetchone()[0],
        "tables": {},
    }
    tables = cast(dict[str, object], result["tables"])
    for kind, name, _table_name, create_sql in schema:
        if kind != "table":
            continue
        columns = list(connection.execute(f"PRAGMA table_info({_qi(name)})"))
        column_names = {str(row[1]).casefold() for row in columns}
        without_rowid = "WITHOUT ROWID" in str(create_sql or "").upper()
        rowid_column = next(
            (
                candidate
                for candidate in ("rowid", "_rowid_", "oid")
                if candidate not in column_names
            ),
            None,
        )
        if not without_rowid and rowid_column is not None:
            query = f"SELECT {rowid_column},* FROM {_qi(name)} ORDER BY {rowid_column}"
            ordering = "ROWID_INCLUDED"
        else:
            primary_keys = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
            if not primary_keys:
                raise ProductionMigrationError(f"SQLite table has no deterministic order: {name}")
            query = f"SELECT * FROM {_qi(name)} ORDER BY " + ",".join(
                _qi(str(key)) for key in primary_keys
            )
            ordering = "PRIMARY_KEY"
        digest = hashlib.sha256()
        row_count = 0
        for row in connection.execute(query):
            digest.update(b"R" + struct.pack(">I", len(row)))
            for value in row:
                if value is None:
                    kind_tag, payload = b"N", b""
                elif isinstance(value, int):
                    kind_tag, payload = b"I", str(value).encode("ascii")
                elif isinstance(value, float):
                    kind_tag, payload = b"F", struct.pack(">d", value)
                elif isinstance(value, str):
                    kind_tag, payload = b"T", value.encode("utf-8")
                elif isinstance(value, bytes):
                    kind_tag, payload = b"B", value
                else:
                    raise ProductionMigrationError(
                        f"unsupported SQLite value in {name}: {type(value)}"
                    )
                digest.update(kind_tag + struct.pack(">Q", len(payload)))
                digest.update(payload)
            row_count += 1
        tables[str(name)] = {
            "rows": row_count,
            "sha256": digest.hexdigest(),
            "ordering": ordering,
        }
    return json.loads(json.dumps(result))


def _database_snapshot(path: Path, *, immutable: bool) -> tuple[dict[str, object], str]:
    _reject_sidecars(path)
    try:
        with closing(_connect_read_only(path, immutable=immutable)) as connection:
            integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
            foreign = [list(row) for row in connection.execute("PRAGMA foreign_key_check")]
            snapshot = _typed_snapshot(connection)
    except (OSError, sqlite3.Error, ProductionMigrationError) as exc:
        raise ProductionMigrationError(f"cannot verify SQLite database: {path.name}") from exc
    if integrity != ["ok"] or foreign:
        raise ProductionMigrationError(f"SQLite integrity or foreign-key check failed: {path.name}")
    return snapshot, _sha256_bytes(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    )


def _flush_file(path: Path) -> None:
    try:
        descriptor = os.open(
            path, os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ProductionMigrationError(f"cannot durably sync migration file: {path}") from exc


def _copy_file_exclusive(source: Path, destination: Path, *, mode: int) -> str:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(destination, flags, mode)
    except OSError as exc:
        raise ProductionMigrationError(
            f"cannot create staged file without replacement: {destination}"
        ) from exc
    source_digest = hashlib.sha256()
    try:
        os.fchmod(descriptor, mode)
        with (
            source.open("rb") as input_stream,
            os.fdopen(descriptor, "wb", closefd=False) as output_stream,
        ):
            for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                source_digest.update(block)
                output_stream.write(block)
            output_stream.flush()
            os.fsync(descriptor)
    except OSError as exc:
        raise ProductionMigrationError(f"cannot stage static source: {source}") from exc
    finally:
        os.close(descriptor)
    _sync_directory(destination.parent)
    return source_digest.hexdigest()


def _backup_database(
    source: Path, destination: Path, *, immutable_source: bool, fault_hook: FaultHook | None
) -> None:
    _reject_sidecars(source)
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(destination, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        with (
            closing(_connect_read_only(source, immutable=immutable_source)) as source_connection,
            closing(sqlite3.connect(str(destination), timeout=5)) as destination_connection,
        ):
            destination_connection.execute("PRAGMA journal_mode=DELETE")

            def progress(_status: int, remaining: int, total: int) -> None:
                if fault_hook is not None:
                    fault_hook("backup_progress", destination)
                if remaining < 0 or total < 0:
                    raise ProductionMigrationError("SQLite backup reported invalid progress")

            source_connection.backup(
                destination_connection, pages=128, progress=progress, sleep=0.05
            )
        os.chmod(destination, 0o600)
        _flush_file(destination)
        _sync_directory(destination.parent)
    except (OSError, sqlite3.Error, ProductionMigrationError) as exc:
        raise ProductionMigrationError(f"SQLite backup failed: {source.name}") from exc


def _atomic_marker_write(marker_path: Path, payload: Mapping[str, object]) -> None:
    marker_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = marker_path.with_name(f"{marker_path.name}.tmp-{uuid4().hex}")
    data = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(temporary, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, marker_path)
        _sync_directory(marker_path.parent)
    except OSError as exc:
        raise ProductionMigrationError("cannot durably write migration marker") from exc


def _load_marker(marker_path: Path) -> dict[str, object] | None:
    try:
        info = os.lstat(marker_path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ProductionMigrationError("cannot inspect migration marker") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ProductionMigrationError("migration marker is not a private regular file")
    try:
        parsed: object = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionMigrationError("migration marker is unreadable or invalid") from exc
    if not isinstance(parsed, dict):
        raise ProductionMigrationError("migration marker must contain a JSON object")
    return cast(dict[str, object], parsed)


def _runtime_release_hash() -> str:
    checkout = Path(__file__).resolve().parents[4]
    digest = hashlib.sha256()
    for relative in RELEASE_FILES:
        path = checkout / relative
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise ProductionMigrationError(
                f"candidate release file is unavailable: {relative}"
            ) from exc
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ProductionMigrationError(f"candidate release file is unsafe: {relative}")
        digest.update(relative.encode() + b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def _schema_digest(snapshot: Mapping[str, object]) -> str:
    shape = {
        "schema": snapshot.get("schema"),
        "user_version": snapshot.get("user_version"),
        "application_id": snapshot.get("application_id"),
    }
    return _sha256_bytes(json.dumps(shape, sort_keys=True, separators=(",", ":")).encode())


def _target_identity(path: Path) -> dict[str, int]:
    identity = _file_identity(path)
    if identity["mode"] != 0o600:
        raise ProductionMigrationError("project database must have mode 0600")
    return {key: identity[key] for key in ("device", "inode", "mode")}


def _state_history(marker: Mapping[str, object]) -> list[str]:
    history = marker.get("state_history")
    if not isinstance(history, list):
        raise ProductionMigrationError("migration marker has an invalid state history")
    history_items = cast(list[object], history)
    if any(not isinstance(item, str) for item in history_items):
        raise ProductionMigrationError("migration marker has an invalid state history")
    return cast(list[str], history_items)


def _write_state(marker_path: Path, marker: dict[str, object], state: str) -> None:
    history = list(_state_history(marker))
    if not history:
        history.append("NOT_STARTED")
    if history[-1] != state:
        history.append(state)
    marker["state"] = state
    marker["state_history"] = history
    marker["updated_at_utc"] = _utc_now()
    _atomic_marker_write(marker_path, marker)


def _sqlite_file(relative: str) -> bool:
    return Path(relative).suffix.casefold() in {".db", ".sqlite", ".sqlite3"}


def _assert_inventory_unchanged(source_root: Path, expected: list[dict[str, object]]) -> None:
    current = _json_roundtrip(_iter_inventory(source_root))
    expected_json = _json_roundtrip(expected)
    if current != expected_json:
        raise ProductionMigrationError("legacy Library inventory changed during migration")


def _validate_target_directory(
    root: Path, relative: str, source_identity: Mapping[str, object]
) -> Path:
    target = root / relative
    _reject_symlink_components(target)
    source_mode = _required_int(source_identity.get("mode", 0o700), "directory mode")
    if source_mode & 0o100 == 0:
        raise ProductionMigrationError(
            f"legacy source directory is not searchable by its owner: {relative}"
        )
    try:
        info = os.lstat(target)
    except FileNotFoundError:
        target.mkdir(mode=0o700)
        _sync_directory(target.parent)
        info = os.lstat(target)
    except OSError as exc:
        raise ProductionMigrationError(f"cannot inspect target directory: {relative}") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        raise ProductionMigrationError(f"static target directory conflicts: {relative}")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise ProductionMigrationError(f"static target directory must have mode 0700: {relative}")
    return target


def _ensure_parent_directories(
    root: Path,
    relative: str,
    source_records: Mapping[str, dict[str, object]],
) -> Path:
    current = root
    accumulated = Path()
    for component in Path(relative).parent.parts:
        accumulated /= component
        rel = accumulated.as_posix()
        record = source_records.get(rel)
        if record is None or record.get("kind") != "directory":
            raise ProductionMigrationError(f"source directory is missing from inventory: {rel}")
        identity = record.get("identity")
        if not isinstance(identity, dict):
            raise ProductionMigrationError(f"source directory identity is invalid: {rel}")
        current = _validate_target_directory(
            current, component, cast(Mapping[str, object], identity)
        )
    return current


def _preflight_static_targets(
    database_directory: Path,
    stage_root: Path,
    records: list[dict[str, object]],
    source_root: Path,
) -> dict[str, dict[str, object]]:
    identities: dict[str, dict[str, object]] = {}
    for record in records:
        if record.get("kind") != "file" or record.get("path") == DATABASE_FILENAME:
            continue
        relative = str(record["path"])
        target = database_directory / relative
        _reject_symlink_components(target)
        stage = stage_root / "static" / relative
        _ensure_owner_directory(stage.parent)
        source = source_root / relative
        before = _file_identity(source)
        destination_mode = _private_file_mode(before["mode"])
        if _sqlite_file(relative):
            source_snapshot, source_schema = _database_snapshot(source, immutable=True)
        else:
            source_snapshot, source_schema = {}, ""
        digest = _copy_file_exclusive(source, stage, mode=destination_mode)
        if _file_identity(source) != before or digest != _file_sha256(stage):
            raise ProductionMigrationError(
                f"static source changed or stage hash differs: {relative}"
            )
        if _sqlite_file(relative):
            stage_snapshot, _stage_schema = _database_snapshot(stage, immutable=True)
            if source_snapshot != stage_snapshot:
                raise ProductionMigrationError(
                    f"static SQLite content differs after staging: {relative}"
                )
        if source_schema:
            identities[relative] = {
                "sha256": digest,
                "source_identity": before,
                "target_mode": destination_mode,
                "stage_identity": _file_identity(stage),
                "snapshot_sha256": source_schema,
            }
        else:
            identities[relative] = {
                "sha256": digest,
                "source_identity": before,
                "target_mode": destination_mode,
                "stage_identity": _file_identity(stage),
            }
        if target.exists():
            target_info = _file_identity(target)
            if target_info["mode"] != destination_mode or _file_sha256(target) != digest:
                raise ProductionMigrationError(f"static project target conflicts: {relative}")
            if _sqlite_file(relative):
                _reject_sidecars(target)
                target_snapshot, _target_hash = _database_snapshot(target, immutable=True)
                if target_snapshot != source_snapshot:
                    raise ProductionMigrationError(
                        f"static SQLite target differs from source: {relative}"
                    )
            identities[relative]["existing_target_identity"] = target_info
    return identities


def _publish_static_files(
    database_directory: Path,
    stage_root: Path,
    records: list[dict[str, object]],
    identities: dict[str, dict[str, object]],
    source_records: Mapping[str, dict[str, object]],
    marker_path: Path,
    marker: dict[str, object],
    lock_validator: LockValidator,
) -> dict[str, dict[str, object]]:
    published: dict[str, dict[str, object]] = {}
    directories: dict[str, dict[str, int]] = {}
    for record in records:
        relative = str(record.get("path", ""))
        if record.get("kind") == "directory":
            if relative in EXCLUDED_TOP_LEVEL_DIRECTORIES:
                continue
            lock_validator()
            identity = record.get("identity")
            if not isinstance(identity, dict):
                raise ProductionMigrationError(f"source directory identity is invalid: {relative}")
            parent = _ensure_parent_directories(
                database_directory, f"{relative}/placeholder", source_records
            )
            target_directory = _validate_target_directory(
                parent, Path(relative).name, cast(Mapping[str, object], identity)
            )
            directories[relative] = _directory_identity(target_directory)
            continue
        if record.get("kind") != "file" or relative == DATABASE_FILENAME:
            continue
        target = database_directory / relative
        stage = stage_root / "static" / relative
        _ensure_parent_directories(database_directory, relative, source_records)
        _reject_symlink_components(target)
        if target.exists():
            current = _file_identity(target)
            if current != identities[relative].get("existing_target_identity"):
                raise ProductionMigrationError(
                    f"static project target changed before publish: {relative}"
                )
            if _file_sha256(target) != identities[relative]["sha256"]:
                raise ProductionMigrationError(
                    f"static project target content changed before publish: {relative}"
                )
            published[relative] = cast(dict[str, object], current)
            stage.unlink()
            _sync_directory(stage.parent)
        else:
            lock_validator()
            try:
                os.link(stage, target, follow_symlinks=False)
            except FileExistsError as exc:
                raise ProductionMigrationError(
                    f"static target appeared during publish: {relative}"
                ) from exc
            except OSError as exc:
                raise ProductionMigrationError(
                    f"cannot atomically publish static file: {relative}"
                ) from exc
            linked_info = os.lstat(target)
            if stat.S_IMODE(linked_info.st_mode) != _required_int(
                identities[relative].get("target_mode"), "static target mode"
            ):
                raise ProductionMigrationError(
                    f"static target mode changed during publish: {relative}"
                )
            if _file_sha256(target) != identities[relative]["sha256"]:
                raise ProductionMigrationError(
                    f"static target hash differs after publish: {relative}"
                )
            stage.unlink()
            _sync_directory(target.parent)
            _sync_directory(stage.parent)
            published[relative] = cast(dict[str, object], _file_identity(target))
        marker["published_static"] = dict(published)
        marker["published_directories"] = {
            relative: cast(dict[str, object], identity)
            for relative, identity in directories.items()
        }
        lock_validator()
        _write_state(marker_path, marker, "STAGED_VERIFIED")
    directories = {
        relative: _directory_identity(database_directory / relative) for relative in directories
    }
    marker["published_directories"] = {
        relative: cast(dict[str, object], identity)
        for relative, identity in directories.items()
    }
    return published


def _marker_for_root(marker_path: Path, *, deep: bool, verify_source: bool) -> dict[str, object]:
    marker = _load_marker(marker_path)
    if marker is None or marker.get("state") != "COMMITTED":
        raise ProductionMigrationError("migration is not COMMITTED")
    if marker.get("schema_version") != 1:
        raise ProductionMigrationError("committed marker schema version is unsupported")
    migration_id = marker.get("migration_id")
    if not isinstance(migration_id, str) or len(migration_id) != 32:
        raise ProductionMigrationError("committed marker migration ID is invalid")
    if marker.get("state_history") != [
        "NOT_STARTED",
        "STARTED",
        "STAGED_VERIFIED",
        "REPLACED_PENDING_COMMIT",
        "COMMITTED",
    ]:
        raise ProductionMigrationError("committed marker state history is invalid")
    if (
        marker.get("release_id") != RELEASE_ID
        or marker.get("release_sha256") != _runtime_release_hash()
    ):
        raise ProductionMigrationError("committed marker belongs to another candidate release")
    database_directory = marker_path.parent
    if marker.get("database_directory") != str(database_directory):
        raise ProductionMigrationError("committed marker belongs to another project data root")
    target = database_directory / DATABASE_FILENAME
    expected_target = marker.get("target_identity")
    current_target = _target_identity(target)
    if current_target != _json_object_mapping(expected_target):
        raise ProductionMigrationError("committed target inode or file identity changed")
    if deep:
        snapshot, _snapshot_hash = _database_snapshot(target, immutable=False)
        if marker.get("target_schema_sha256") != _schema_digest(snapshot):
            raise ProductionMigrationError("committed target schema or SQLite identity changed")

    backup_info = marker.get("pre_migration_backup")
    if deep and backup_info is not None:
        backup_info = _json_object_mapping(backup_info)
        backup_path_raw = backup_info.get("path")
        if not isinstance(backup_path_raw, str):
            raise ProductionMigrationError("pre-migration backup path is invalid")
        backup_path = Path(backup_path_raw)
        if backup_path.parent != database_directory or not backup_path.name.startswith(
            PRE_MIGRATION_PREFIX
        ):
            raise ProductionMigrationError("pre-migration backup escapes the project database root")
        if _file_identity(backup_path) != backup_info.get("identity"):
            raise ProductionMigrationError("pre-migration backup identity changed")
        if _file_sha256(backup_path) != backup_info.get("sha256"):
            raise ProductionMigrationError("pre-migration backup content changed")

    if verify_source:
        source_root_raw = marker.get("source_directory")
        source_inventory = marker.get("source_inventory")
        if not isinstance(source_root_raw, str) or not isinstance(source_inventory, list):
            raise ProductionMigrationError("committed marker has an invalid source inventory")
        current_inventory = _json_roundtrip(_iter_inventory(Path(source_root_raw)))
        source_inventory_json = _json_roundtrip(cast(list[object], source_inventory))
        if current_inventory != source_inventory_json:
            raise ProductionMigrationError("legacy Library source identity changed after migration")
        static_files = marker.get("published_static")
        static_files = _json_object_mapping(static_files)
        for relative, raw_record in static_files.items():
            raw_record = _json_object_mapping(raw_record)
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ProductionMigrationError(
                    "committed static target path escapes the project root"
                )
            expected_identity = raw_record.get("identity")
            expected_hash = raw_record.get("sha256")
            if not isinstance(expected_hash, str):
                raise ProductionMigrationError("committed static target identity is invalid")
            expected_identity = _json_object_mapping(expected_identity)
            static_target = database_directory / relative
            if _file_identity(static_target) != expected_identity:
                raise ProductionMigrationError(
                    f"committed static target identity changed: {relative}"
                )
            if _file_sha256(static_target) != expected_hash:
                raise ProductionMigrationError(
                    f"committed static target content changed: {relative}"
                )
        static_directories = _json_object_mapping(marker.get("published_directories"))
        for relative, expected_identity in static_directories.items():
            expected_identity = _json_object_mapping(expected_identity)
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ProductionMigrationError(
                    "committed static directory path escapes the project root"
                )
            if _directory_identity(database_directory / relative) != expected_identity:
                raise ProductionMigrationError(
                    f"committed static directory identity changed: {relative}"
                )
    return marker


def assert_migration_committed(database: Path) -> None:
    """Cheap committed-state check used by the ordinary write guard."""
    selected = Path(database)
    _marker_for_root(selected.parent / MARKER_FILENAME, deep=False, verify_source=False)


def ensure_migration_complete(
    *,
    lock_validator: LockValidator,
    database_directory: Path | None = None,
    source_directory: Path | None = None,
    _fault_hook: FaultHook | None = None,
) -> dict[str, object]:
    """Run or verify the one-time migration while the scheduler process lock is held."""
    source_root = LEGACY_DATA_DIRECTORY if source_directory is None else Path(source_directory)
    canonical_database_directory = project_database_directory()
    if database_directory is not None and Path(database_directory) != canonical_database_directory:
        raise ProductionMigrationError(
            "scheduler database root differs from the canonical project root"
        )
    database_directory = canonical_database_directory
    _reject_symlink_components(source_root)
    lock_validator()
    _ensure_database_directory(database_directory)
    marker_path = database_directory / MARKER_FILENAME
    existing_marker = _load_marker(marker_path)
    if existing_marker is not None:
        if existing_marker.get("state") != "COMMITTED":
            raise ProductionMigrationError("incomplete migration marker requires operator review")
        verified = _marker_for_root(marker_path, deep=True, verify_source=True)
        lock_validator()
        return {
            "status": "NO_OP_ALREADY_COMMITTED",
            "migration_id": verified.get("migration_id"),
            "state_history": verified.get("state_history"),
        }

    orphan_stages = list(database_directory.glob(f"{STAGE_PREFIX}*"))
    orphan_backups = list(database_directory.glob(f"{PRE_MIGRATION_PREFIX}*"))
    marker_temps = list(database_directory.glob(f"{MARKER_FILENAME}.tmp-*"))
    if orphan_stages or orphan_backups or marker_temps:
        raise ProductionMigrationError(
            "orphan migration evidence exists without an authoritative marker"
        )

    source_inventory = cast(list[dict[str, object]], _json_roundtrip(_iter_inventory(source_root)))
    source_records = _source_record_map(source_inventory)
    source_database = source_root / DATABASE_FILENAME
    source_database_record = source_records.get(DATABASE_FILENAME)
    if source_database_record is None or source_database_record.get("kind") != "file":
        raise ProductionMigrationError("legacy lottolab.db is missing from the source inventory")
    source_database_identity = cast(dict[str, int], source_database_record["identity"])
    _reject_sidecars(source_database)

    target_database = database_directory / DATABASE_FILENAME
    _reject_symlink_components(target_database)
    target_exists = target_database.exists()
    target_before: dict[str, int] | None = None
    target_size = 0
    if target_exists:
        target_before = _file_identity(target_database)
        if target_before["mode"] != 0o600:
            raise ProductionMigrationError("existing project lottolab.db must be mode 0600")
        _reject_sidecars(target_database)
        target_size = target_before["size"]

    required_space = _inventory_size(source_inventory) + target_size + RESERVED_FREE_BYTES
    if _available_bytes(database_directory) < required_space:
        raise ProductionMigrationError("insufficient free space for the stage and safety reserve")

    source_before_snapshot, source_before_snapshot_sha = _database_snapshot(
        source_database, immutable=False
    )
    if _file_identity(source_database) != source_database_identity:
        raise ProductionMigrationError(
            "legacy lottolab.db changed while taking the source snapshot"
        )
    existing_project_snapshot: dict[str, object] | None = None
    if target_exists:
        existing_project_snapshot, _existing_hash = _database_snapshot(
            target_database, immutable=False
        )
        if _file_identity(target_database) != target_before:
            raise ProductionMigrationError(
                "project lottolab.db changed while taking its pre-migration snapshot"
            )

    migration_id = uuid4().hex
    stage_root = database_directory / f"{STAGE_PREFIX}{migration_id}.staging"
    try:
        stage_root.mkdir(mode=0o700)
    except OSError as exc:
        raise ProductionMigrationError("cannot create unique project staging directory") from exc
    _ensure_owner_directory(stage_root)
    marker: dict[str, object] = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "release_sha256": _runtime_release_hash(),
        "migration_id": migration_id,
        "source_directory": str(source_root),
        "source_inventory": source_inventory,
        "source_database_identity": source_database_identity,
        "source_database_snapshot_sha256": source_before_snapshot_sha,
        "database_directory": str(database_directory),
        "stage_directory": str(stage_root),
        "target_before_identity": target_before,
        "target_before_snapshot": existing_project_snapshot,
        "pre_migration_backup": None,
        "state": "NOT_STARTED",
        "state_history": ["NOT_STARTED"],
        "created_at_utc": _utc_now(),
        "updated_at_utc": _utc_now(),
    }
    _write_state(marker_path, marker, "STARTED")
    lock_validator()

    backup_record: dict[str, object] | None = None
    if target_exists:
        backup_path = database_directory / (
            f"{PRE_MIGRATION_PREFIX}"
            f"{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{migration_id}"
        )
        _backup_database(
            target_database, backup_path, immutable_source=False, fault_hook=_fault_hook
        )
        backup_snapshot, backup_snapshot_sha = _database_snapshot(backup_path, immutable=False)
        if backup_snapshot != existing_project_snapshot:
            raise ProductionMigrationError(
                "pre-migration SQLite backup differs from the existing project DB"
            )
        backup_record = {
            "path": str(backup_path),
            "identity": _file_identity(backup_path),
            "sha256": _file_sha256(backup_path),
            "snapshot_sha256": backup_snapshot_sha,
        }
        marker["pre_migration_backup"] = backup_record
        _write_state(marker_path, marker, "STARTED")

    stage_database = stage_root / DATABASE_FILENAME
    _backup_database(
        source_database, stage_database, immutable_source=False, fault_hook=_fault_hook
    )
    if _fault_hook is not None:
        _fault_hook("stage_written", stage_database)
    stage_snapshot, stage_snapshot_sha = _database_snapshot(stage_database, immutable=False)
    source_after_snapshot, _source_after_hash = _database_snapshot(source_database, immutable=False)
    if source_after_snapshot != source_before_snapshot:
        raise ProductionMigrationError("legacy lottolab.db content changed during its backup")
    if _file_identity(source_database) != source_database_identity:
        raise ProductionMigrationError("legacy lottolab.db identity changed during its backup")
    if stage_snapshot != source_before_snapshot:
        raise ProductionMigrationError(
            "staged lottolab.db differs from the read-only Library source"
        )
    stage_database_hash = _file_sha256(stage_database)

    static_identities = _preflight_static_targets(
        database_directory, stage_root, source_inventory, source_root
    )
    static_identities = cast(dict[str, dict[str, object]], _json_roundtrip(static_identities))
    _assert_inventory_unchanged(source_root, source_inventory)
    marker["stage_database_identity"] = _file_identity(stage_database)
    marker["stage_database_sha256"] = stage_database_hash
    marker["stage_database_snapshot_sha256"] = stage_snapshot_sha
    marker["stage_database_schema_sha256"] = _schema_digest(stage_snapshot)
    marker["static_files"] = static_identities
    marker["static_snapshot_sha256"] = _sha256_bytes(
        json.dumps(static_identities, sort_keys=True, separators=(",", ":")).encode()
    )
    if _fault_hook is not None:
        _fault_hook("before_staged_verified", stage_database)
    _write_state(marker_path, marker, "STAGED_VERIFIED")
    lock_validator()

    published_static = _publish_static_files(
        database_directory,
        stage_root,
        source_inventory,
        static_identities,
        source_records,
        marker_path,
        marker,
        lock_validator,
    )
    marker["published_static"] = published_static
    _assert_inventory_unchanged(source_root, source_inventory)
    if _fault_hook is not None:
        _fault_hook("before_database_replace", stage_database)
    lock_validator()
    if target_exists:
        if target_before is None or _file_identity(target_database) != target_before:
            raise ProductionMigrationError(
                "project lottolab.db changed after its preserved snapshot"
            )
        if backup_record is None:
            raise ProductionMigrationError("pre-migration database backup is missing")
    elif target_database.exists():
        raise ProductionMigrationError("project lottolab.db appeared during migration")
    os.replace(stage_database, target_database)
    _sync_directory(database_directory)
    target_after_identity = _target_identity(target_database)
    if target_after_identity["device"] != int(marker["stage_database_identity"]["device"]):
        raise ProductionMigrationError("replaced project DB is on a different filesystem")
    if target_after_identity["inode"] != int(marker["stage_database_identity"]["inode"]):
        raise ProductionMigrationError(
            "atomic replacement did not preserve the verified stage inode"
        )
    target_after_snapshot, target_after_snapshot_sha = _database_snapshot(
        target_database, immutable=False
    )
    if target_after_snapshot != stage_snapshot:
        raise ProductionMigrationError("replaced project DB differs from the verified stage")
    marker["target_identity"] = target_after_identity
    marker["target_content_sha256"] = _sha256_bytes(
        json.dumps(target_after_snapshot, sort_keys=True, separators=(",", ":")).encode()
    )
    marker["target_snapshot_sha256"] = target_after_snapshot_sha
    marker["target_schema_sha256"] = _schema_digest(target_after_snapshot)
    marker["published_static"] = {
        relative: {
            "identity": identity,
            "sha256": static_identities[relative]["sha256"],
        }
        for relative, identity in published_static.items()
    }
    _write_state(marker_path, marker, "REPLACED_PENDING_COMMIT")
    if _fault_hook is not None:
        _fault_hook("after_replace", target_database)
        _fault_hook("before_commit", target_database)
    lock_validator()
    _assert_inventory_unchanged(source_root, source_inventory)
    _write_state(marker_path, marker, "COMMITTED")
    _marker_for_root(marker_path, deep=True, verify_source=True)
    lock_validator()
    return {
        "status": "COMMITTED",
        "migration_id": migration_id,
        "state_history": marker["state_history"],
        "target": str(target_database),
    }


__all__ = [
    "ProductionMigrationError",
    "assert_migration_committed",
    "ensure_migration_complete",
]
