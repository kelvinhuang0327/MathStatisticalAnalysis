"""Auditable database registry operations with explicit paths for safe testing."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

REGISTRY_FILENAME = "database-locations.json"
CHANGELOG_FILENAME = "REGISTRY_CHANGELOG.jsonl"
LEASE_FILENAME = "database-locations.json.lease.json"
MODULE_NAME = "lottolab.infrastructure.persistence.database_registry"

VERIFY_EXIT_CODES = {
    "OK": 0,
    "UNRECORDED_CHANGE": 2,
    "NO_CHANGELOG": 3,
    "BROKEN_CHAIN": 4,
    "WAITING_ON_LEASE": 75,
}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class RegistryError(Exception):
    """A rejected registry operation with a stable machine-readable status."""

    def __init__(self, message: str, *, status: str = "ERROR", exit_code: int = 1) -> None:
        super().__init__(message)
        self.status = status
        self.exit_code = exit_code


@dataclass(frozen=True)
class VerificationResult:
    """Read-only verification outcome and the hashes that were compared."""

    status: str
    registry_sha256: str | None
    changelog_after_sha256: str | None
    task_id: str | None
    detail: str | None = None

    @property
    def exit_code(self) -> int:
        """CLI exit code for this status."""
        return VERIFY_EXIT_CODES[self.status]


@dataclass(frozen=True)
class OperationResult:
    """Summary of a completed registry write."""

    operation: str
    before_sha256: str
    after_sha256: str
    task_id: str
    entries_written: int = 1


@dataclass(frozen=True)
class _ParsedChangelog:
    rows: tuple[dict[str, object], ...]
    status: str
    detail: str | None = None


def database_directory(project_root: Path) -> Path:
    """Return the database directory for an explicitly selected project root."""
    return project_root / "data" / "databases"


def registry_path(project_root: Path) -> Path:
    """Return the registry path for an explicitly selected project root."""
    return database_directory(project_root) / REGISTRY_FILENAME


def changelog_path(project_root: Path) -> Path:
    """Return the changelog path for an explicitly selected project root."""
    return database_directory(project_root) / CHANGELOG_FILENAME


def verify_registry(project_root: Path) -> VerificationResult:
    """Compare the registry hash to the last valid changelog entry without writing."""
    data_directory = project_root / "data"
    directory = database_directory(project_root)
    registry = directory / REGISTRY_FILENAME
    changelog = directory / CHANGELOG_FILENAME
    _reject_symlink(project_root, "project root")
    _reject_symlink(data_directory, "data directory")
    _reject_symlink(directory, "database directory")
    _reject_symlink(registry, "registry")
    _reject_symlink(changelog, "changelog")

    try:
        registry_bytes = registry.read_bytes()
    except OSError as exc:
        raise RegistryError(f"cannot read registry {registry}: {exc}") from exc
    registry_hash = hashlib.sha256(registry_bytes).hexdigest()

    try:
        changelog_bytes = changelog.read_bytes()
    except FileNotFoundError:
        return VerificationResult("NO_CHANGELOG", registry_hash, None, None, "changelog is absent")
    except OSError as exc:
        raise RegistryError(f"cannot read changelog {changelog}: {exc}") from exc

    if not changelog_bytes:
        return VerificationResult("NO_CHANGELOG", registry_hash, None, None, "changelog is empty")

    parsed = _parse_changelog(changelog_bytes)
    if parsed.status == "BROKEN_CHAIN":
        last = parsed.rows[-1] if parsed.rows else {}
        after = _string_field(last, "after_sha256")
        task_id = _string_field(last, "task_id")
        return VerificationResult(
            "BROKEN_CHAIN",
            registry_hash,
            after,
            task_id,
            parsed.detail,
        )

    last = parsed.rows[-1]
    after_hash = _string_field(last, "after_sha256")
    task_id = _string_field(last, "task_id")
    if after_hash != registry_hash:
        return VerificationResult(
            "UNRECORDED_CHANGE",
            registry_hash,
            after_hash,
            task_id,
            "registry hash does not match the last changelog after_sha256",
        )
    return VerificationResult("OK", registry_hash, after_hash, task_id)


def add_writable(
    project_root: Path,
    database_filename: str,
    *,
    task_id: str,
    authorization_file: Path,
    repository_root: Path | None = None,
) -> OperationResult:
    """Add one database basename to writable_databases under an exclusive lease."""
    authorization_path = _check_authorization(task_id, authorization_file)
    with _write_lease(project_root, task_id, authorization_path):
        registry = registry_path(project_root)
        original = _read_registry(registry)
        before_hash = hashlib.sha256(original).hexdigest()
        _require_verified(project_root)
        _validate_database_filename(database_filename)
        payload = _updated_registry(original, database_filename, add=True)
        _atomic_replace_registry(registry, payload, before_hash)
        after_hash = hashlib.sha256(payload).hexdigest()
        row = _change_row(
            operation="add",
            task_id=task_id,
            before_hash=before_hash,
            after_hash=after_hash,
            authorization_path=authorization_path,
            repository_root=repository_root or project_root,
            evidence=[],
            note=f"Added {database_filename} to writable_databases.",
        )
        _append_changelog(changelog_path(project_root), (row,))
        return OperationResult("add", before_hash, after_hash, task_id)


def remove_writable(
    project_root: Path,
    database_filename: str,
    *,
    task_id: str,
    authorization_file: Path,
    repository_root: Path | None = None,
) -> OperationResult:
    """Remove one database basename from writable_databases under a lease."""
    authorization_path = _check_authorization(task_id, authorization_file)
    with _write_lease(project_root, task_id, authorization_path):
        registry = registry_path(project_root)
        original = _read_registry(registry)
        before_hash = hashlib.sha256(original).hexdigest()
        _require_verified(project_root)
        _validate_database_filename(database_filename)
        payload = _updated_registry(original, database_filename, add=False)
        _atomic_replace_registry(registry, payload, before_hash)
        after_hash = hashlib.sha256(payload).hexdigest()
        row = _change_row(
            operation="remove",
            task_id=task_id,
            before_hash=before_hash,
            after_hash=after_hash,
            authorization_path=authorization_path,
            repository_root=repository_root or project_root,
            evidence=[],
            note=f"Removed {database_filename} from writable_databases.",
        )
        _append_changelog(changelog_path(project_root), (row,))
        return OperationResult("remove", before_hash, after_hash, task_id)


def backfill_changelog(
    project_root: Path,
    entries_file: Path,
    *,
    task_id: str,
    authorization_file: Path,
    repository_root: Path | None = None,
) -> OperationResult:
    """Append validated historical entries without modifying the registry."""
    authorization_path = _check_authorization(task_id, authorization_file)
    with _write_lease(project_root, task_id, authorization_path):
        registry = registry_path(project_root)
        registry_bytes = _read_registry(registry)
        current_hash = hashlib.sha256(registry_bytes).hexdigest()
        try:
            parsed_entries: object = json.loads(entries_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RegistryError(f"cannot read entries JSON {entries_file}: {exc}") from exc
        entries = _validate_backfill_entries(parsed_entries, current_hash)

        verification = verify_registry(project_root)
        if verification.status == "BROKEN_CHAIN":
            raise RegistryError(
                f"cannot backfill a broken changelog: {verification.detail}",
                status="BROKEN_CHAIN",
                exit_code=VERIFY_EXIT_CODES["BROKEN_CHAIN"],
            )
        previous_after = verification.changelog_after_sha256
        if previous_after is not None and entries[0]["before_sha256"] != previous_after:
            raise RegistryError(
                "backfill chain does not continue from the existing changelog",
                status="BACKFILL_CHAIN_MISMATCH",
            )

        rows: list[dict[str, object]] = []
        git_root = repository_root or project_root
        for entry in entries:
            original_task_id = cast(str, entry["task_id"])
            entry_note = entry.get("note")
            note = entry_note if isinstance(entry_note, str) else ""
            note = f"{note} Backfilled by {task_id}." if note else f"Backfilled by {task_id}."
            row = _change_row(
                operation="backfill",
                task_id=original_task_id,
                before_hash=cast(str, entry["before_sha256"]),
                after_hash=cast(str, entry["after_sha256"]),
                authorization_path=authorization_path,
                repository_root=git_root,
                evidence=cast(list[str], entry["evidence"]),
                note=note,
                time_utc=cast(str, entry["time"]),
                status=cast(str, entry["status"]),
            )
            row["authorized_by_task_id"] = task_id
            rows.append(row)

        if _file_sha256(registry) != current_hash:
            raise RegistryError(
                "REGISTRY_CHANGED_DURING_EDIT",
                status="REGISTRY_CHANGED_DURING_EDIT",
            )
        _append_changelog(changelog_path(project_root), tuple(rows))
        return OperationResult(
            "backfill",
            cast(str, entries[0]["before_sha256"]),
            cast(str, entries[-1]["after_sha256"]),
            task_id,
            len(entries),
        )


def _parse_changelog(raw: bytes) -> _ParsedChangelog:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _ParsedChangelog((), "BROKEN_CHAIN", "changelog is not UTF-8")
    rows: list[dict[str, object]] = []
    previous_after: str | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError:
            return _ParsedChangelog(
                tuple(rows), "BROKEN_CHAIN", f"line {line_number} is not valid JSON"
            )
        if not isinstance(value, dict):
            return _ParsedChangelog(
                tuple(rows), "BROKEN_CHAIN", f"line {line_number} is not an object"
            )
        row = cast(dict[str, object], value)
        before_hash = _string_field(row, "before_sha256")
        after_hash = _string_field(row, "after_sha256")
        if (
            before_hash is None
            or after_hash is None
            or not _SHA256_PATTERN.fullmatch(before_hash)
            or not _SHA256_PATTERN.fullmatch(after_hash)
        ):
            return _ParsedChangelog(
                tuple(rows), "BROKEN_CHAIN", f"line {line_number} has invalid SHA-256 fields"
            )
        if _string_field(row, "task_id") is None:
            return _ParsedChangelog(
                tuple(rows), "BROKEN_CHAIN", f"line {line_number} has no task_id"
            )
        if previous_after is not None and before_hash != previous_after:
            return _ParsedChangelog(
                tuple(rows), "BROKEN_CHAIN", f"line {line_number} does not continue the prior hash"
            )
        rows.append(row)
        previous_after = after_hash
    if not rows:
        return _ParsedChangelog((), "BROKEN_CHAIN", "changelog contains no JSON records")
    return _ParsedChangelog(tuple(rows), "OK")


def _validate_backfill_entries(value: object, current_hash: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        raise RegistryError("entries must be a nonempty JSON array")
    entries: list[dict[str, object]] = []
    previous_after: str | None = None
    for index, item in enumerate(cast(list[object], value)):
        if not isinstance(item, dict):
            raise RegistryError(f"entry {index + 1} must be a JSON object")
        entry = cast(dict[str, object], item)
        required = ("time", "task_id", "before_sha256", "after_sha256", "evidence", "status")
        if any(field not in entry for field in required):
            raise RegistryError(f"entry {index + 1} is missing a required field")
        for field in required:
            if field == "evidence":
                continue
            field_value = entry[field]
            if not isinstance(field_value, str) or not field_value:
                raise RegistryError(f"entry {index + 1} has an invalid text field")
        before_hash = cast(str, entry["before_sha256"])
        after_hash = cast(str, entry["after_sha256"])
        if not _SHA256_PATTERN.fullmatch(before_hash) or not _SHA256_PATTERN.fullmatch(after_hash):
            raise RegistryError(f"entry {index + 1} has an invalid SHA-256")
        evidence = entry["evidence"]
        if not isinstance(evidence, list):
            raise RegistryError(f"entry {index + 1} evidence must be a list of paths")
        evidence_paths: list[str] = []
        for evidence_path in cast(list[object], evidence):
            if not isinstance(evidence_path, str):
                raise RegistryError(f"entry {index + 1} evidence must be a list of paths")
            evidence_paths.append(evidence_path)
        if previous_after is not None and before_hash != previous_after:
            raise RegistryError(f"entry {index + 1} does not continue the prior backfill hash")
        entry["evidence"] = evidence_paths
        entries.append(entry)
        previous_after = after_hash
    if cast(str, entries[-1]["after_sha256"]) != current_hash:
        raise RegistryError("the last backfill after_sha256 does not match the current registry")
    return entries


def _require_verified(project_root: Path) -> None:
    result = verify_registry(project_root)
    if result.status != "OK":
        raise RegistryError(
            f"registry verification is {result.status}; run backfill before add/remove",
            status="VERIFY_NOT_OK",
        )


def _updated_registry(original: bytes, database_filename: str, *, add: bool) -> bytes:
    try:
        text = original.decode("utf-8")
        parsed: object = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryError("registry is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise RegistryError("registry must be a JSON object")
    document = cast(dict[str, object], parsed)
    writable = document.get("writable_databases")
    if not isinstance(writable, list):
        raise RegistryError("writable_databases must be a list of filenames")
    values: list[str] = []
    for item in cast(list[object], writable):
        if not isinstance(item, str):
            raise RegistryError("writable_databases must be a list of filenames")
        values.append(item)
    document["writable_databases"] = values
    if add:
        if database_filename in values:
            raise RegistryError(f"{database_filename} is already writable")
        values.append(database_filename)
    else:
        if database_filename not in values:
            raise RegistryError(f"{database_filename} is not writable")
        values.remove(database_filename)

    indent = _detect_indent(text)
    ensure_ascii = "\\u" in text
    rendered = json.dumps(document, ensure_ascii=ensure_ascii, indent=indent)
    if text.endswith("\r\n"):
        rendered += "\r\n"
    elif text.endswith("\n"):
        rendered += "\n"
    return rendered.encode("utf-8")


def _detect_indent(text: str) -> int | str | None:
    indents = re.findall(r"(?m)^([ \t]+)\S", text)
    if not indents:
        return None
    return min(indents, key=len)


def _validate_database_filename(filename: str) -> None:
    if (
        not filename
        or filename in {".", ".."}
        or Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise RegistryError("DB filename must be a basename without path separators")


def _check_authorization(task_id: str, authorization_file: Path) -> Path:
    if not task_id or task_id.strip() != task_id:
        raise RegistryError(
            "task-id must be a nonempty, trimmed value", status="AUTHORIZATION_REQUIRED"
        )
    if not authorization_file.is_absolute():
        raise RegistryError(
            "authorization-file must be an absolute path",
            status="AUTHORIZATION_REQUIRED",
        )
    if not authorization_file.is_file():
        raise RegistryError(
            f"authorization-file does not exist: {authorization_file}",
            status="AUTHORIZATION_REQUIRED",
        )
    try:
        contents = authorization_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RegistryError(
            f"cannot read authorization-file: {exc}",
            status="AUTHORIZATION_REQUIRED",
        ) from exc
    required_phrase = f"我授權 {task_id}"
    if required_phrase not in contents:
        raise RegistryError(
            f"authorization-file must contain {required_phrase}",
            status="AUTHORIZATION_REQUIRED",
        )
    return authorization_file


@contextmanager
def _write_lease(project_root: Path, task_id: str, authorization_path: Path) -> Generator[None]:
    data_directory = project_root / "data"
    directory = database_directory(project_root)
    _reject_symlink(project_root, "project root")
    for path, label in ((data_directory, "data directory"), (directory, "database directory")):
        _reject_symlink(path, label)
        try:
            path.mkdir(exist_ok=True)
        except OSError as exc:
            raise RegistryError(f"cannot create {label} {path}: {exc}") from exc

    locks = directory / "locks"
    _reject_symlink(locks, "locks directory")
    try:
        locks.mkdir(exist_ok=True)
    except OSError as exc:
        raise RegistryError(f"cannot create locks directory {locks}: {exc}") from exc

    lease = locks / LEASE_FILENAME
    _reject_symlink(lease, "lease")
    lease_bytes = (
        json.dumps(
            {
                "task_id": task_id,
                "mode": "WRITE",
                "started_at": _utc_now(),
                "expected_end_at": (datetime.now(UTC) + timedelta(minutes=30))
                .isoformat()
                .replace("+00:00", "Z"),
                "authorization_path": str(authorization_path),
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    identity: tuple[int, int] | None = None
    try:
        with lease.open("x", encoding="utf-8") as handle:
            identity_stat = os.fstat(handle.fileno())
            identity = (identity_stat.st_dev, identity_stat.st_ino)
            handle.write(lease_bytes)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        if lease.is_symlink():
            content = "<lease path is a symlink; target was not read>"
        else:
            try:
                content = lease.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as read_error:
                content = f"<cannot read existing lease: {read_error}>"
        raise RegistryError(
            f"WAITING_ON_LEASE\n{content}",
            status="WAITING_ON_LEASE",
            exit_code=VERIFY_EXIT_CODES["WAITING_ON_LEASE"],
        ) from exc
    except OSError as exc:
        if identity is not None:
            _release_lease(lease, locks, identity)
        raise RegistryError(f"cannot create lease {lease}: {exc}") from exc

    assert identity is not None
    try:
        yield
    finally:
        _release_lease(lease, locks, identity)


def _release_lease(lease: Path, locks: Path, identity: tuple[int, int]) -> None:
    try:
        metadata = lease.lstat()
        if stat.S_ISLNK(metadata.st_mode) or (metadata.st_dev, metadata.st_ino) != identity:
            return
        lease.unlink()
        _fsync_directory(locks)
    except FileNotFoundError:
        return
    except OSError:
        return


def _read_registry(path: Path) -> bytes:
    _reject_symlink(path.parent, "database directory")
    _reject_symlink(path, "registry")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise RegistryError(f"cannot read registry {path}: {exc}") from exc


def _atomic_replace_registry(path: Path, payload: bytes, expected_hash: str) -> None:
    _reject_symlink(path.parent, "database directory")
    _reject_symlink(path, "registry")
    try:
        file_mode = stat.S_IMODE(path.stat().st_mode)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{REGISTRY_FILENAME}.", suffix=".tmp", dir=path.parent
        )
    except OSError as exc:
        raise RegistryError(f"cannot prepare atomic registry write: {exc}") from exc
    temporary = Path(temp_name)
    replaced = False
    try:
        os.fchmod(descriptor, file_mode)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1

        if _file_sha256(path) != expected_hash:
            raise RegistryError(
                "REGISTRY_CHANGED_DURING_EDIT",
                status="REGISTRY_CHANGED_DURING_EDIT",
            )
        os.replace(temporary, path)
        replaced = True
        _fsync_directory(path.parent)
    except RegistryError:
        raise
    except OSError as exc:
        raise RegistryError(f"atomic registry write failed: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not replaced:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _append_changelog(path: Path, rows: tuple[dict[str, object], ...]) -> None:
    _reject_symlink(path.parent, "database directory")
    _reject_symlink(path, "changelog")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise RegistryError(f"cannot open changelog for append: {exc}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RegistryError("changelog must be a regular file")
        payload = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ).encode("utf-8")
        _write_all(descriptor, payload)
        os.fsync(descriptor)
    except RegistryError:
        raise
    except OSError as exc:
        raise RegistryError(f"changelog append failed: {exc}") from exc
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("write returned no progress")
        view = view[written:]


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _change_row(
    *,
    operation: str,
    task_id: str,
    before_hash: str,
    after_hash: str,
    authorization_path: Path,
    repository_root: Path,
    evidence: list[str],
    note: str,
    time_utc: str | None = None,
    status: str = "RECORDED",
) -> dict[str, object]:
    return {
        "time_utc": time_utc or _utc_now(),
        "task_id": task_id,
        "file": REGISTRY_FILENAME,
        "operation": operation,
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "authorization_path": str(authorization_path),
        "tool": _tool_info(repository_root),
        "status": status,
        "evidence": evidence,
        "note": note,
    }


def _tool_info(repository_root: Path) -> dict[str, str] | None:
    try:
        completed = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = completed.stdout.strip()
    if not commit:
        return None
    return {"module": MODULE_NAME, "git_commit": commit}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _string_field(row: dict[str, object], field: str) -> str | None:
    value = row.get(field)
    return value if isinstance(value, str) else None


def _reject_symlink(path: Path, label: str) -> None:
    try:
        if path.is_symlink():
            raise RegistryError(f"{label} must not be a symlink: {path}", status="SYMLINK_REJECTED")
    except OSError as exc:
        raise RegistryError(f"cannot inspect {label} {path}: {exc}") from exc
