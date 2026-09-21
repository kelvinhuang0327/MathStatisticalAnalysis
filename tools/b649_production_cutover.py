"""Hermetic plan/apply/rollback orchestration for the B649 LaunchAgent.

The module owns the cutover control plane only.  It never runs the scheduler,
touches the database, changes prediction records, or performs a production
cutover during tests.  The launchd surface is one injectable command runner;
tests provide a fake runner and isolated fixture paths.

``plan`` is read-only.  ``apply`` and ``rollback`` are intentionally explicit
state-changing operations and are not invoked by this repository task.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import errno
import fcntl
import hashlib
import json
import os
import plistlib
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast
from uuid import uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.b649_cutover_checkpoint as checkpoint
import tools.b649_goalc_local_scheduler as scheduler
import tools.b649_pair_rule_forward_shadow as shadow

TASK_ID = "B649_MANAGED_PRODUCTION_CUTOVER_ENTRYPOINT_R1"
PLAN_SCHEMA_VERSION = "b649-managed-production-cutover-plan-v1"
RECEIPT_SCHEMA_VERSION = "b649-managed-production-cutover-receipt-v1"
COMMAND_TIMEOUT = 10
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_RECEIPT_BYTES = 4 * 1024 * 1024
HEX40 = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
DOMAIN = f"gui/{os.getuid()}"

LABEL = scheduler.SCHEDULER_LABEL
CANONICAL_REPOSITORY = scheduler.CANONICAL_REPOSITORY
DEFAULT_PLIST_PATH = scheduler.PLIST_PATH
DEFAULT_OPERATION_ROOT = scheduler.GOALC_ROOT
DEFAULT_RECEIPT_PATH = scheduler.SCHEDULER_ROOT / "b649-production-cutover-receipt.json"
DEFAULT_CUTOVER_LOCK_PATH = scheduler.SCHEDULER_ROOT / "b649-production-cutover.lock"
DEFAULT_PRIMARY_LOCK_PATH = scheduler.LOCK_PATH
DEFAULT_SHADOW_LOCK_PATH = shadow.RUNTIME_SUBROOT / shadow.SHADOW_LOCK_FILE

type Record = dict[str, object]
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class CutoverError(RuntimeError):
    """Base class for fail-closed cutover errors."""


class CutoverSafetyError(CutoverError):
    """A target, identity, ownership, or state precondition failed."""


class CutoverAlreadyRunning(CutoverError):
    """Another apply or rollback currently owns the cutover lock."""


class MutationError(CutoverError):
    """A state-changing action failed or became ambiguous."""


class ActiveCycleError(CutoverSafetyError):
    """A scheduler or descendant is still active and must not be killed."""


def _record(value: object, label: str = "value") -> Record:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise CutoverSafetyError(f"{label} must be an object with string keys")
    return cast(Record, value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CutoverSafetyError(f"{label} must be non-empty text")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _now() -> datetime:
    return datetime.now(UTC)


def run_command(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run one exact command without a shell and with bounded output."""

    return subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        check=False,
        timeout=COMMAND_TIMEOUT,
        env={**os.environ, "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"},
    )


def _bounded_command(runner: Runner, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(argv)
    except Exception as exc:
        raise CutoverSafetyError(f"command {argv[0]} failed: {type(exc).__name__}: {exc}") from exc
    if len(result.stdout) + len(result.stderr) > MAX_OUTPUT_BYTES:
        raise CutoverSafetyError(f"command {argv[0]} exceeded the output bound")
    return result


def _checked_read(runner: Runner, argv: Sequence[str]) -> str:
    result = _bounded_command(runner, argv)
    if result.returncode != 0 or result.stderr.strip():
        detail = result.stderr.strip() or result.stdout.strip()
        raise CutoverSafetyError(f"{argv[0]} failed ({result.returncode}): {detail}")
    return result.stdout


def _normalized_absolute(path: Path) -> bool:
    return (
        path.is_absolute() and str(path) == os.path.normpath(str(path)) and ".." not in path.parts
    )


@dataclass(frozen=True, slots=True)
class CutoverConfig:
    """All mutable and immutable paths for one exact B649 target."""

    source_worktree: Path
    label: str = LABEL
    launch_domain: str = DOMAIN
    plist_path: Path = DEFAULT_PLIST_PATH
    canonical_repository: Path = CANONICAL_REPOSITORY
    operation_root: Path = DEFAULT_OPERATION_ROOT
    scheduler_root: Path = scheduler.SCHEDULER_ROOT
    data_root: Path = scheduler.DATA_ROOT
    database: Path = scheduler.DATABASE_PATH
    announcement: Path = scheduler.ANNOUNCEMENT_PATH
    health_path: Path = scheduler.HEALTH_PATH
    stdout_path: Path = scheduler.STDOUT_PATH
    stderr_path: Path = scheduler.STDERR_PATH
    primary_lock_path: Path = DEFAULT_PRIMARY_LOCK_PATH
    shadow_lock_path: Path = DEFAULT_SHADOW_LOCK_PATH
    cutover_lock_path: Path = DEFAULT_CUTOVER_LOCK_PATH
    receipt_path: Path = DEFAULT_RECEIPT_PATH
    expected_head: str | None = None
    expected_tree: str | None = None
    durable_ref: str | None = None
    strict_release_layout: bool = False

    def __post_init__(self) -> None:
        path_values = (
            self.source_worktree,
            self.plist_path,
            self.canonical_repository,
            self.operation_root,
            self.scheduler_root,
            self.data_root,
            self.database,
            self.announcement,
            self.health_path,
            self.stdout_path,
            self.stderr_path,
            self.primary_lock_path,
            self.shadow_lock_path,
            self.cutover_lock_path,
            self.receipt_path,
        )
        if any(not _normalized_absolute(path) for path in path_values):
            raise ValueError("all cutover paths must be normalized absolute paths")
        if self.label != LABEL:
            raise ValueError(f"label is fixed at {LABEL}")
        if re.fullmatch(r"(?:gui|user)/[0-9]+", self.launch_domain) is None:
            raise ValueError("launch_domain must be gui/UID or user/UID")
        if self.plist_path.name != f"{self.label}.plist":
            raise ValueError("plist_path must be the exact B649 user plist")
        if self.receipt_path in {self.plist_path, self.cutover_lock_path}:
            raise ValueError("receipt_path must be separate from plist and cutover lock")
        if self.expected_head is not None and HEX40.fullmatch(self.expected_head) is None:
            raise ValueError("expected_head must be a full lowercase commit ID")
        if self.expected_tree is not None and HEX40.fullmatch(self.expected_tree) is None:
            raise ValueError("expected_tree must be a full lowercase tree ID")
        if (
            self.durable_ref is not None
            and re.fullmatch(r"refs/heads/runtime/b649/[0-9a-f]{40}", self.durable_ref) is None
        ):
            raise ValueError("durable_ref must be refs/heads/runtime/b649/<FULL_HEAD>")

    @property
    def target(self) -> str:
        return f"{self.launch_domain}/{self.label}"

    @property
    def python_executable(self) -> Path:
        return self.source_worktree / ".venv/bin/python"

    @property
    def script_path(self) -> Path:
        return self.source_worktree / "tools/b649_goalc_local_scheduler.py"

    @property
    def pythonpath(self) -> Path:
        return self.source_worktree / "src"


@dataclass(frozen=True, slots=True)
class FileIdentity:
    path: str
    device: int
    inode: int
    mode: int
    uid: int
    links: int
    size: int
    modified_ns: int
    changed_ns: int
    sha256: str

    def key(self) -> tuple[object, ...]:
        return (
            self.path,
            self.device,
            self.inode,
            self.mode,
            self.uid,
            self.links,
            self.size,
            self.modified_ns,
            self.changed_ns,
            self.sha256,
        )

    def to_dict(self) -> Record:
        return {
            "path": self.path,
            "device": self.device,
            "inode": self.inode,
            "mode": self.mode,
            "uid": self.uid,
            "links": self.links,
            "size": self.size,
            "modified_ns": self.modified_ns,
            "changed_ns": self.changed_ns,
            "sha256": self.sha256,
        }

    @classmethod
    def from_value(cls, value: object) -> FileIdentity:
        item = _record(value, "file identity")
        fields = (
            "path",
            "device",
            "inode",
            "mode",
            "uid",
            "links",
            "size",
            "modified_ns",
            "changed_ns",
            "sha256",
        )
        if any(field not in item for field in fields):
            raise CutoverSafetyError("file identity is incomplete")
        sha256 = _text(item["sha256"], "file identity sha256")
        if re.fullmatch(r"[0-9a-f]{64}", sha256, re.ASCII) is None:
            raise CutoverSafetyError("file identity sha256 is invalid")
        return cls(
            path=_text(item["path"], "file identity path"),
            device=_int(item["device"], "file identity device"),
            inode=_int(item["inode"], "file identity inode"),
            mode=_int(item["mode"], "file identity mode"),
            uid=_int(item["uid"], "file identity uid"),
            links=_int(item["links"], "file identity links"),
            size=_int(item["size"], "file identity size"),
            modified_ns=_int(item["modified_ns"], "file identity modified_ns"),
            changed_ns=_int(item["changed_ns"], "file identity changed_ns"),
            sha256=sha256,
        )


def _int(value: object, label: str) -> int:
    if type(value) is not int:
        raise CutoverSafetyError(f"{label} must be an integer")
    return value


def _lstat_key(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_bounded_bytes(path: Path, *, max_bytes: int = MAX_RECEIPT_BYTES) -> bytes:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        raise CutoverSafetyError(f"cannot open regular file: {path}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise CutoverSafetyError(f"path must be one regular file: {path}")
        if before.st_uid != os.getuid():
            raise CutoverSafetyError(f"path must be owned by current user: {path}")
        data = os.read(descriptor, max_bytes + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        current = os.lstat(path)
    except OSError as exc:
        raise CutoverSafetyError(f"file disappeared during read: {path}") from exc
    if (
        len(data) > max_bytes
        or _lstat_key(before) != _lstat_key(after)
        or _lstat_key(before) != _lstat_key(current)
    ):
        raise CutoverSafetyError(f"file changed or exceeded bound during read: {path}")
    return data


def _file_identity(
    path: Path,
    *,
    missing_ok: bool,
    require_mode: int | None = None,
) -> tuple[FileIdentity | None, bytes | None]:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        if missing_ok:
            return None, None
        raise CutoverSafetyError(f"required file does not exist: {path}") from None
    except OSError as exc:
        raise CutoverSafetyError(f"cannot inspect file: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise CutoverSafetyError(f"path must be a regular single-link file: {path}")
    if metadata.st_uid != os.getuid():
        raise CutoverSafetyError(f"file must be owned by current user: {path}")
    if require_mode is not None and stat.S_IMODE(metadata.st_mode) != require_mode:
        raise CutoverSafetyError(f"file mode must be {require_mode:04o}: {path}")
    data = _read_bounded_bytes(path)
    after = os.lstat(path)
    if _lstat_key(metadata) != _lstat_key(after):
        raise CutoverSafetyError(f"file changed during identity read: {path}")
    identity = FileIdentity(
        path=str(path),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
        uid=metadata.st_uid,
        links=metadata.st_nlink,
        size=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
        changed_ns=metadata.st_ctime_ns,
        sha256=_sha256_bytes(data),
    )
    return identity, data


def _identity_from_record(value: object, label: str) -> FileIdentity:
    return FileIdentity.from_value(_record(value, label))


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = os.lstat(path)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise CutoverSafetyError(f"directory must be current-user owned with mode 0700: {path}")


def _atomic_write(path: Path, data: bytes, *, expected: FileIdentity | None) -> FileIdentity:
    if not path.parent.is_dir():
        raise CutoverSafetyError(f"destination directory does not exist: {path.parent}")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.fchmod(descriptor, 0o600)
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise CutoverSafetyError(f"short write while replacing {path}")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        observed, _ = _file_identity(path, missing_ok=True)
        if (observed is None) != (expected is None) or (
            observed is not None and expected is not None and observed.key() != expected.key()
        ):
            raise CutoverSafetyError(f"destination changed before replace: {path}")
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        identity, readback = _file_identity(path, missing_ok=False, require_mode=0o600)
        if readback != data or identity is None:
            raise CutoverSafetyError(f"readback differs after replace: {path}")
        return identity
    finally:
        if descriptor is not None:
            os.close(descriptor)
        with suppress(FileNotFoundError):
            temporary.unlink()


def _write_json(path: Path, value: Record, *, expected: FileIdentity | None) -> FileIdentity:
    return _atomic_write(path, (_canonical_json(value) + "\n").encode("utf-8"), expected=expected)


def _load_json(path: Path) -> tuple[Record, FileIdentity, bytes]:
    identity, raw = _file_identity(path, missing_ok=False, require_mode=0o600)
    if identity is None or raw is None:
        raise CutoverSafetyError(f"JSON file is unavailable: {path}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CutoverSafetyError(f"JSON file is invalid: {path}") from exc
    return _record(value, "JSON file"), identity, raw


def _git_value(runner: Runner, worktree: Path, revision: str) -> str:
    value = _checked_read(
        runner,
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(worktree),
            "rev-parse",
            "--verify",
            "--end-of-options",
            revision,
        ],
    ).strip()
    if not value:
        raise CutoverSafetyError(f"git returned an empty value for {revision}")
    return value


def _source_layout_error(config: CutoverConfig, head: str) -> str | None:
    if not config.strict_release_layout:
        return None
    expected_parent = (
        config.canonical_repository.parent / ".worktrees" / config.canonical_repository.name
    )
    if config.source_worktree.parent != expected_parent:
        return f"production source must be below {expected_parent}"
    if config.source_worktree.name != f"B649_PRODUCTION_{head}":
        return "production source directory must be B649_PRODUCTION_<FULL_RELEASE_HEAD>"
    return None


def _validate_runtime_tuple(config: CutoverConfig) -> bool:
    values = (
        config.source_worktree,
        config.python_executable,
        config.script_path,
        config.pythonpath,
    )
    try:
        for path in values:
            path.relative_to(config.source_worktree)
        return True
    except ValueError:
        return False


def _validate_real_runtime_paths(
    source: Path,
    role: str,
    paths: Mapping[str, Path],
) -> None:
    try:
        source_root = source.resolve(strict=True)
    except OSError as exc:
        raise CutoverSafetyError(f"{role} source worktree cannot be resolved") from exc
    if source_root != source:
        raise CutoverSafetyError(f"{role} source worktree path is not canonical")
    for name, path in paths.items():
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise CutoverSafetyError(f"{role} {name} cannot be resolved") from exc
        try:
            resolved.relative_to(source_root)
        except ValueError as exc:
            raise CutoverSafetyError(f"{role} {name} resolves outside the source worktree") from exc


def _validate_source(
    config: CutoverConfig,
    runner: Runner,
    *,
    role: str,
    expected_head: str | None = None,
    expected_tree: str | None = None,
    expected_ref: str | None = None,
    strict_release_layout: bool | None = None,
) -> Record:
    source = config.source_worktree
    if not source.is_dir() or source.is_symlink():
        raise CutoverSafetyError(f"{role} source worktree is not a real directory: {source}")
    canonical = config.canonical_repository.resolve(strict=False)
    if source.resolve(strict=False) == canonical or source.resolve(strict=False).is_relative_to(
        canonical
    ):
        raise CutoverSafetyError(
            f"{role} source cannot be the canonical or nested primary checkout"
        )
    root = _checked_read(
        runner,
        ["git", "--no-optional-locks", "-C", str(source), "rev-parse", "--show-toplevel"],
    ).strip()
    if root != str(source):
        raise CutoverSafetyError(f"{role} git root differs: {root}")
    head = _git_value(runner, source, "HEAD")
    tree = _git_value(runner, source, "HEAD^{tree}")
    if HEX40.fullmatch(head) is None or HEX40.fullmatch(tree) is None:
        raise CutoverSafetyError(f"{role} source identity is not a full object ID")
    if expected_head is not None and head != expected_head:
        raise CutoverSafetyError(f"{role} HEAD drifted: expected {expected_head}, observed {head}")
    if expected_tree is not None and tree != expected_tree:
        raise CutoverSafetyError(f"{role} tree drifted: expected {expected_tree}, observed {tree}")
    status = _checked_read(
        runner,
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(source),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
    )
    if status:
        raise CutoverSafetyError(f"{role} source is not clean: {status.splitlines()[0]}")
    ref = expected_ref or f"refs/heads/runtime/b649/{head}"
    if ref != f"refs/heads/runtime/b649/{head}":
        raise CutoverSafetyError(f"{role} durable ref is not bound to HEAD")
    _checked_read(runner, ["git", "check-ref-format", ref])
    durable_head = _git_value(runner, source, ref + "^{commit}")
    if durable_head != head:
        raise CutoverSafetyError(f"{role} durable ref does not resolve to HEAD")
    layout_error = (
        _source_layout_error(config, head) if strict_release_layout is not False else None
    )
    if layout_error:
        raise CutoverSafetyError(layout_error)
    if not _validate_runtime_tuple(
        config if role == "new" else replace(config, source_worktree=source)
    ):
        raise CutoverSafetyError(f"{role} runtime tuple escapes source worktree")
    interpreter = config.python_executable if role == "new" else source / ".venv/bin/python"
    script = config.script_path if role == "new" else source / "tools/b649_goalc_local_scheduler.py"
    pythonpath = config.pythonpath if role == "new" else source / "src"
    _validate_real_runtime_paths(
        source,
        role,
        {"interpreter": interpreter, "scheduler script": script, "PYTHONPATH": pythonpath},
    )
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise CutoverSafetyError(
            f"{role} worktree-owned venv interpreter is unavailable: {interpreter}"
        )
    if not script.is_file() or script.is_symlink():
        raise CutoverSafetyError(f"{role} scheduler script is unavailable or symlinked: {script}")
    if not pythonpath.is_dir() or pythonpath.is_symlink():
        raise CutoverSafetyError(
            f"{role} PYTHONPATH root is unavailable or symlinked: {pythonpath}"
        )
    return {
        "role": role,
        "source_worktree": str(source),
        "head": head,
        "tree": tree,
        "durable_ref": ref,
        "clean": True,
        "runtime_tuple": {
            "working_directory": str(source),
            "interpreter": str(interpreter),
            "script": str(script),
            "pythonpath": str(pythonpath),
            "arguments": [str(interpreter), str(script), "run"],
        },
    }


def _scheduler_config(config: CutoverConfig) -> scheduler.SchedulerConfig:
    base = scheduler.production_config()
    return replace(
        base,
        source_worktree=config.source_worktree,
        python_executable=config.python_executable,
        script_path=config.script_path,
        operation_root=config.operation_root,
        data_root=config.data_root,
        database=config.database,
        announcement=config.announcement,
        scheduler_root=config.scheduler_root,
        lock_path=config.primary_lock_path,
        health_path=config.health_path,
        stdout_path=config.stdout_path,
        stderr_path=config.stderr_path,
        plist_path=config.plist_path,
    )


def _runtime_tuple(binding: Mapping[str, object], label: str) -> Record:
    label_value = binding.get("Label")
    arguments_value = binding.get("ProgramArguments")
    working_directory = binding.get("WorkingDirectory")
    environment_value = binding.get("EnvironmentVariables")
    if label_value != LABEL:
        raise CutoverSafetyError(f"{label} plist label differs")
    if not isinstance(arguments_value, list):
        raise CutoverSafetyError(f"{label} ProgramArguments is invalid")
    argument_values = cast(list[object], arguments_value)
    arguments = [value for value in argument_values if isinstance(value, str)]
    if len(arguments) != len(argument_values):
        raise CutoverSafetyError(f"{label} ProgramArguments is invalid")
    if len(arguments) != 3 or arguments[2] != "run":
        raise CutoverSafetyError(f"{label} ProgramArguments must be python, scheduler, run")
    if not isinstance(working_directory, str):
        raise CutoverSafetyError(f"{label} WorkingDirectory is invalid")
    environment = _record(environment_value, f"{label} EnvironmentVariables")
    pythonpath = environment.get("PYTHONPATH")
    if not isinstance(pythonpath, str):
        raise CutoverSafetyError(f"{label} PYTHONPATH is invalid")
    return {
        "working_directory": working_directory,
        "interpreter": arguments[0],
        "script": arguments[1],
        "pythonpath": pythonpath,
        "arguments": arguments,
    }


def _parse_plist(data: bytes, label: str) -> tuple[Record, Record]:
    try:
        value = plistlib.loads(data)
    except (plistlib.InvalidFileException, ValueError) as exc:
        raise CutoverSafetyError(f"{label} plist is invalid") from exc
    binding = _record(value, f"{label} plist")
    if binding.get("RunAtLoad") is not True:
        raise CutoverSafetyError(f"{label} plist RunAtLoad must be true")
    if binding.get("StartInterval") != scheduler.START_INTERVAL_SECONDS:
        raise CutoverSafetyError(f"{label} plist StartInterval must be 300")
    if binding.get("KeepAlive") is not False:
        raise CutoverSafetyError(f"{label} plist KeepAlive must be false")
    runtime = _runtime_tuple(binding, label)
    return binding, runtime


def _launch_args(config: CutoverConfig, source: Record | None = None) -> argparse.Namespace:
    source_path = "" if source is None else str(source.get("source_worktree", ""))
    head = "" if source is None else str(source.get("head", ""))
    return argparse.Namespace(
        launch_domain=config.launch_domain,
        expected_label=config.label,
        expected_rollback_worktree=source_path,
        expected_rollback_head=head,
        primary_lock_path=str(config.primary_lock_path),
        shadow_lock_path=str(config.shadow_lock_path),
        old_primary_identity=None,
        old_scheduler_identity=None,
        old_shadow_identity=None,
    )


def _launch_snapshot(config: CutoverConfig, runner: Runner, source: Record | None) -> Record:
    if source is None:
        raise CutoverSafetyError("cannot observe launchd ownership without an old source")
    args = _launch_args(config, source)
    snapshot = checkpoint.launch_snapshot(args, runner)
    return _record(snapshot, "launchd snapshot")


def _enabled_snapshot(config: CutoverConfig, runner: Runner) -> bool:
    args = argparse.Namespace(launch_domain=config.launch_domain, expected_label=config.label)
    value = checkpoint.enabled_snapshot(args, runner)
    if type(value) is not bool:
        raise CutoverSafetyError("launchd enabled state is not boolean")
    return value


def _loaded_runtime(snapshot: Record) -> Record | None:
    if snapshot.get("state") != "LOADED":
        return None
    raw = snapshot.get("raw")
    if not isinstance(raw, str):
        raise CutoverSafetyError("loaded launchd snapshot has no raw binding")
    fields = checkpoint.launch_fields(raw)
    arguments_value = fields.get("arguments")
    environment_value = fields.get("environment")
    if not isinstance(arguments_value, list) or not isinstance(environment_value, list):
        raise CutoverSafetyError("loaded launchd binding lacks arguments or environment")
    arguments = arguments_value
    environment = environment_value
    pythonpath = [
        line[len("PYTHONPATH => ") :] for line in environment if line.startswith("PYTHONPATH => ")
    ]
    if len(pythonpath) != 1:
        raise CutoverSafetyError("loaded launchd binding has ambiguous PYTHONPATH")
    program = fields.get("program")
    working = fields.get("working directory")
    if (
        not isinstance(program, str)
        or not isinstance(working, str)
        or len(arguments) != 3
        or arguments[0] != program
    ):
        raise CutoverSafetyError("loaded launchd binding is incomplete")
    return {
        "working_directory": working,
        "interpreter": program,
        "script": arguments[1],
        "pythonpath": pythonpath[0],
        "arguments": arguments,
    }


def _probe_lock(path: Path) -> Record:
    """Probe one existing advisory lock without creating a missing lock."""

    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return {"path": str(path), "state": "IDLE", "exists": False}
    except OSError as exc:
        raise CutoverSafetyError(f"cannot inspect lock: {path}") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
    ):
        raise CutoverSafetyError(f"lock has unsafe identity: {path}")
    try:
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise CutoverSafetyError(f"cannot open lock: {path}") from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}:
                return {"path": str(path), "state": "ACTIVE", "exists": True}
            raise CutoverSafetyError(f"cannot probe lock: {path}") from exc
        finally:
            with suppress(OSError):
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
    return {"path": str(path), "state": "IDLE", "exists": True}


def _ownership_snapshot(config: CutoverConfig, runner: Runner, source: Record) -> Record:
    args = _launch_args(config, source)
    process = _record(checkpoint.process_snapshot(args, runner), "process snapshot")
    runtime = _record(process.get("runtime"), "runtime ownership")
    primary = _record(process.get("primary"), "primary ownership")
    scheduler_process = _record(process.get("scheduler"), "scheduler ownership")
    shadow_process = _record(process.get("shadow"), "shadow ownership")
    return {
        "process": process,
        "runtime": runtime,
        "primary": primary,
        "scheduler": scheduler_process,
        "shadow": shadow_process,
        "primary_lock": _probe_lock(config.primary_lock_path),
        "shadow_lock": _probe_lock(config.shadow_lock_path),
    }


def _assert_idle(ownership: Record, *, include_runtime: bool = True) -> None:
    keys = (
        ("runtime", "primary", "scheduler", "shadow")
        if include_runtime
        else ("primary", "scheduler", "shadow")
    )
    for key in keys:
        value = _record(ownership.get(key), f"ownership {key}")
        if value.get("classification") != "ABSENT":
            raise ActiveCycleError(f"{key} ownership is not idle: {value.get('classification')}")
    for key in ("primary_lock", "shadow_lock"):
        value = _record(ownership.get(key), f"{key} lock")
        if value.get("state") != "IDLE":
            raise ActiveCycleError(f"{key} is active: {value.get('state')}")


def _same_root(runtime: Record, source: Record) -> bool:
    try:
        root = Path(_text(source.get("source_worktree"), "source worktree")).resolve(strict=False)
        paths = tuple(
            Path(value).resolve(strict=False)
            for value in (
                _text(runtime.get("working_directory"), "working directory"),
                _text(runtime.get("interpreter"), "interpreter"),
                _text(runtime.get("script"), "script"),
                _text(runtime.get("pythonpath"), "PYTHONPATH"),
            )
        )
        for path in paths:
            path.relative_to(root)
    except OSError as exc:
        raise CutoverSafetyError("runtime tuple cannot be resolved") from exc
    except ValueError:
        return False
    return paths[0] == root


def _same_root_or_false(runtime: Record | None, source: Record | None) -> bool:
    if runtime is None or source is None or not runtime or not source:
        return False
    try:
        return _same_root(runtime, source)
    except CutoverSafetyError:
        return False


def _prestate_digest(prestate: Record) -> str:
    digest_input = dict(prestate)
    digest_input.pop("observed_at", None)
    return _sha256_json(digest_input)


def _candidate_plist(config: CutoverConfig) -> tuple[bytes, Record, Record]:
    encoded = scheduler.build_launchd_plist(_scheduler_config(config))
    binding, runtime = _parse_plist(encoded, "new")
    if binding.get("Label") != config.label or runtime != {
        "working_directory": str(config.source_worktree),
        "interpreter": str(config.python_executable),
        "script": str(config.script_path),
        "pythonpath": str(config.pythonpath),
        "arguments": [str(config.python_executable), str(config.script_path), "run"],
    }:
        raise CutoverSafetyError("scheduler builder produced a different runtime tuple")
    if not _same_root(runtime, {"source_worktree": str(config.source_worktree)}):
        raise CutoverSafetyError("new plist runtime tuple escapes the source root")
    return encoded, binding, runtime


def _base_plan(config: CutoverConfig, now: datetime) -> Record:
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "task": TASK_ID,
        "command": "plan",
        "status": "FAIL",
        "observed_at": _utc_text(now),
        "target": {
            "label": config.label,
            "launch_domain": config.launch_domain,
            "launch_target": config.target,
            "plist_path": str(config.plist_path),
        },
        "failures": [],
    }


def build_plan(
    config: CutoverConfig,
    *,
    runner: Runner = run_command,
    now: datetime | None = None,
) -> Record:
    """Render a complete plan without creating a directory, lock, receipt, or plist."""

    observed_at = now or _now()
    result = _base_plan(config, observed_at)
    failures = cast(list[str], result["failures"])
    new_source: Record | None = None
    old_source: Record | None = None
    old_identity: FileIdentity | None = None
    old_bytes: bytes | None = None
    old_binding: Record | None = None
    old_runtime: Record | None = None
    launch: Record | None = None
    loaded_runtime: Record | None = None
    enabled: bool | None = None
    ownership: Record | None = None
    try:
        _validate_config(config)
        new_source = _validate_source(
            config,
            runner,
            role="new",
            expected_head=config.expected_head,
            expected_tree=config.expected_tree,
            expected_ref=config.durable_ref,
            strict_release_layout=config.strict_release_layout,
        )
    except Exception as exc:
        failures.append(f"new_source: {type(exc).__name__}: {exc}")
    try:
        encoded, new_binding, new_runtime = _candidate_plist(config)
        new_plist = {
            "path": str(config.plist_path),
            "exists": False,
            "sha256": _sha256_bytes(encoded),
            "size": len(encoded),
            "binding": new_binding,
        }
    except Exception as exc:
        encoded = b""
        new_binding = {}
        new_runtime = {}
        new_plist = {"path": str(config.plist_path), "exists": False}
        failures.append(f"new_plist: {type(exc).__name__}: {exc}")
    try:
        old_identity, old_bytes = _file_identity(
            config.plist_path,
            missing_ok=True,
            require_mode=0o600,
        )
        if old_bytes is None or old_identity is None:
            raise CutoverSafetyError("exact user plist is not installed")
        old_binding, old_runtime = _parse_plist(old_bytes, "old")
        old_source_path = Path(_text(old_runtime.get("working_directory"), "old source worktree"))
        old_config = replace(config, source_worktree=old_source_path, strict_release_layout=False)
        old_source = _validate_source(
            old_config,
            runner,
            role="old",
            expected_head=None,
            expected_tree=None,
            expected_ref=None,
            strict_release_layout=False,
        )
        if not _same_root(old_runtime, old_source):
            raise CutoverSafetyError("old plist runtime tuple is not same-root")
        launch = _launch_snapshot(config, runner, old_source)
        enabled = _enabled_snapshot(config, runner)
        loaded_runtime = _loaded_runtime(launch)
        if loaded_runtime is not None and loaded_runtime != old_runtime:
            raise CutoverSafetyError("launchd loaded binding differs from on-disk old plist")
        ownership = _ownership_snapshot(config, runner, old_source)
        _assert_idle(ownership)
    except Exception as exc:
        failures.append(f"old_state: {type(exc).__name__}: {exc}")
    if new_source is not None:
        result["source"] = {"new": new_source, "old": old_source}
    else:
        result["source"] = {"new": None, "old": old_source}
    result["runtime"] = {
        "new": new_runtime,
        "old": old_runtime,
        "new_same_root": _same_root_or_false(new_runtime, new_source),
        "old_same_root": _same_root_or_false(old_runtime, old_source),
    }
    result["plist"] = {
        "old": (
            {"identity": old_identity.to_dict(), "binding": old_binding}
            if old_identity is not None and old_binding is not None
            else None
        ),
        "new": new_plist,
    }
    result["launchd"] = {
        "target": config.target,
        "old_state": None if launch is None else launch.get("state"),
        "old_enabled": enabled,
        "loaded_binding": loaded_runtime,
    }
    result["ownership"] = ownership
    rollback_preconditions: Record = {
        "old_plist_bytes_preserved": old_bytes is not None,
        "old_source_present": old_source is not None,
        "old_venv_present": bool(old_source and old_runtime and old_runtime.get("interpreter")),
        "old_identity_bound": old_source is not None,
        "receipt_required_for_rollback": True,
        "database_rollback": False,
        "prediction_rollback": False,
        "schedule_row_rollback": False,
    }
    result["rollback_preconditions"] = rollback_preconditions
    if old_identity is not None and old_bytes is not None and new_source is not None:
        prestate: Record = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "target": result["target"],
            "old_plist_identity": old_identity.to_dict(),
            "old_plist_bytes_b64": base64.b64encode(old_bytes).decode("ascii"),
            "old_binding": old_binding,
            "old_runtime": old_runtime,
            "old_source": old_source,
            "old_launch_state": None if launch is None else launch.get("state"),
            "old_enabled": enabled,
            "new_source": new_source,
            "new_plist_bytes_b64": base64.b64encode(encoded).decode("ascii"),
            "new_plist_sha256": _sha256_bytes(encoded),
            "primary_lock_path": str(config.primary_lock_path),
            "shadow_lock_path": str(config.shadow_lock_path),
        }
        result["prestate"] = prestate
        result["prestate_digest"] = _prestate_digest(prestate)
        result["plan_digest"] = _sha256_json(
            {
                "schema_version": PLAN_SCHEMA_VERSION,
                "target": result["target"],
                "prestate_digest": result["prestate_digest"],
                "new_source": new_source,
                "new_plist_sha256": prestate["new_plist_sha256"],
            }
        )
    else:
        result["prestate"] = None
        result["prestate_digest"] = None
        result["plan_digest"] = None
    if not failures:
        result["status"] = "PASS"
    return result


def _validate_config(config: CutoverConfig) -> None:
    if config.plist_path.name != f"{config.label}.plist" or config.label != LABEL:
        raise CutoverSafetyError("cutover target is not the exact B649 LaunchAgent")
    if config.source_worktree.resolve(strict=False) == config.canonical_repository.resolve(
        strict=False
    ):
        raise CutoverSafetyError("source worktree cannot be the primary checkout")
    if config.python_executable != config.source_worktree / ".venv/bin/python":
        raise CutoverSafetyError("interpreter must be the source worktree's own .venv")
    if config.script_path != config.source_worktree / "tools/b649_goalc_local_scheduler.py":
        raise CutoverSafetyError("scheduler script must be inside the source worktree")
    if config.pythonpath != config.source_worktree / "src":
        raise CutoverSafetyError("PYTHONPATH must be inside the source worktree")
    if not _validate_runtime_tuple(config):
        raise CutoverSafetyError("runtime tuple is not same-root")
    if config.strict_release_layout:
        exact_paths = {
            "launch domain": (config.launch_domain, DOMAIN),
            "plist path": (config.plist_path, DEFAULT_PLIST_PATH),
            "operation root": (config.operation_root, DEFAULT_OPERATION_ROOT),
            "scheduler root": (config.scheduler_root, scheduler.SCHEDULER_ROOT),
            "data root": (config.data_root, scheduler.DATA_ROOT),
            "database": (config.database, scheduler.DATABASE_PATH),
            "announcement": (config.announcement, scheduler.ANNOUNCEMENT_PATH),
            "health path": (config.health_path, scheduler.HEALTH_PATH),
            "stdout path": (config.stdout_path, scheduler.STDOUT_PATH),
            "stderr path": (config.stderr_path, scheduler.STDERR_PATH),
            "primary lock path": (config.primary_lock_path, DEFAULT_PRIMARY_LOCK_PATH),
            "shadow lock path": (config.shadow_lock_path, DEFAULT_SHADOW_LOCK_PATH),
            "cutover lock path": (config.cutover_lock_path, DEFAULT_CUTOVER_LOCK_PATH),
            "receipt path": (config.receipt_path, DEFAULT_RECEIPT_PATH),
        }
        for name, (observed, expected) in exact_paths.items():
            if observed != expected:
                raise CutoverSafetyError(f"{name} is not the exact production path")


class CutoverLock:
    """Non-blocking owner-only serialization lock for apply/rollback."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.descriptor: int | None = None
        self.created = False

    def __enter__(self) -> CutoverLock:
        _ensure_private_directory(self.path.parent)
        try:
            self.descriptor = os.open(
                self.path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except OSError as exc:
            raise CutoverSafetyError(f"cannot open cutover lock: {self.path}") from exc
        metadata = os.fstat(self.descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
        ):
            self.__exit__(None, None, None)
            raise CutoverSafetyError(f"cutover lock has unsafe identity: {self.path}")
        os.fchmod(self.descriptor, 0o600)
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.__exit__(None, None, None)
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}:
                raise CutoverAlreadyRunning(
                    "another B649 cutover owns the serialization lock"
                ) from exc
            raise CutoverSafetyError("cannot acquire cutover serialization lock") from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc_value, traceback
        if self.descriptor is not None:
            with suppress(OSError):
                fcntl.flock(self.descriptor, fcntl.LOCK_UN)
            with suppress(OSError):
                os.close(self.descriptor)
            self.descriptor = None


@dataclass
class ActionRecorder:
    actions: list[Record]
    mutation_count: int = 0

    def event(self, name: str, **fields: object) -> None:
        item: Record = {
            "name": name,
            "observed_at": _utc_text(_now()),
            **fields,
        }
        self.actions.append(item)

    def command(
        self, name: str, argv: Sequence[str], runner: Runner
    ) -> subprocess.CompletedProcess[str]:
        started = _now()
        try:
            result = runner(argv)
        except BaseException as exc:
            self.mutation_count += 1
            self.actions.append(
                {
                    "name": name,
                    "argv": list(argv),
                    "started_at": _utc_text(started),
                    "finished_at": _utc_text(_now()),
                    "status": "INTERRUPTED"
                    if isinstance(exc, (KeyboardInterrupt, SystemExit))
                    else "EXCEPTION",
                    "error": f"{type(exc).__name__}: {exc}",
                    "interrupted": isinstance(exc, (KeyboardInterrupt, SystemExit)),
                    "mutation": True,
                }
            )
            raise MutationError(f"{name} raised {type(exc).__name__}: {exc}") from exc
        self.mutation_count += 1
        self.actions.append(
            {
                "name": name,
                "argv": list(argv),
                "started_at": _utc_text(started),
                "finished_at": _utc_text(_now()),
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "returncode": result.returncode,
                "stdout": result.stdout[-4096:],
                "stderr": result.stderr[-4096:],
                "mutation": True,
            }
        )
        return result


def _plan_target_matches(config: CutoverConfig, plan: Record) -> None:
    target = _record(plan.get("target"), "plan target")
    if (
        target.get("label") != config.label
        or target.get("launch_domain") != config.launch_domain
        or target.get("launch_target") != config.target
        or target.get("plist_path") != str(config.plist_path)
    ):
        raise CutoverSafetyError("plan target is not the exact configured B649 target")
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION or plan.get("task") != TASK_ID:
        raise CutoverSafetyError("plan schema or task differs")
    if plan.get("status") != "PASS":
        raise CutoverSafetyError("plan did not pass its read-only preconditions")
    prestate = _record(plan.get("prestate"), "plan prestate")
    if plan.get("prestate_digest") != _prestate_digest(prestate):
        raise CutoverSafetyError("plan prestate digest is invalid")
    new_source = _record(
        _record(plan.get("source"), "plan source").get("new"),
        "plan new source",
    )
    expected_plan_digest = _sha256_json(
        {
            "schema_version": PLAN_SCHEMA_VERSION,
            "target": target,
            "prestate_digest": plan.get("prestate_digest"),
            "new_source": new_source,
            "new_plist_sha256": prestate.get("new_plist_sha256"),
        }
    )
    if plan.get("plan_digest") != expected_plan_digest:
        raise CutoverSafetyError("plan digest is invalid")


def _fresh_plan_matches(
    config: CutoverConfig,
    expected: Record,
    *,
    runner: Runner,
) -> Record:
    fresh = build_plan(config, runner=runner)
    if fresh.get("status") != "PASS":
        raise CutoverSafetyError(
            "fresh plan prestate is not safe: " + "; ".join(cast(list[str], fresh["failures"]))
        )
    if fresh.get("prestate_digest") != expected.get("prestate_digest"):
        raise CutoverSafetyError("plan prestate drifted before mutation")
    if fresh.get("plan_digest") != expected.get("plan_digest"):
        raise CutoverSafetyError("plan digest drifted before mutation")
    expected_source = _record(
        _record(expected.get("source"), "expected source").get("new"), "expected new source"
    )
    fresh_source = _record(
        _record(fresh.get("source"), "fresh source").get("new"), "fresh new source"
    )
    if fresh_source != expected_source:
        raise CutoverSafetyError("new source identity drifted before mutation")
    return fresh


def _assert_expected_plist(
    path: Path,
    expected: FileIdentity,
    *,
    expected_bytes: bytes | None = None,
) -> tuple[FileIdentity, bytes]:
    observed, data = _file_identity(path, missing_ok=False, require_mode=0o600)
    if observed is None or data is None or observed.key() != expected.key():
        raise CutoverSafetyError(f"plist identity drifted: {path}")
    if expected_bytes is not None and data != expected_bytes:
        raise CutoverSafetyError(f"plist bytes drifted: {path}")
    return observed, data


def _assert_loaded_binding(
    config: CutoverConfig, runner: Runner, source: Record, expected_runtime: Record
) -> Record:
    launch = _launch_snapshot(config, runner, source)
    if launch.get("state") != "LOADED":
        raise CutoverSafetyError("LaunchAgent is not loaded")
    loaded = _loaded_runtime(launch)
    if loaded != expected_runtime:
        raise CutoverSafetyError("loaded LaunchAgent runtime tuple differs")
    return launch


def _assert_enabled(config: CutoverConfig, runner: Runner, expected: bool) -> None:
    observed = _enabled_snapshot(config, runner)
    if observed is not expected:
        raise CutoverSafetyError(
            f"LaunchAgent enabled state differs: expected {expected}, observed {observed}"
        )


def _assert_runtime_binding(
    config: CutoverConfig,
    runner: Runner,
    source: Record,
    expected_runtime: Record,
) -> Record:
    launch = _launch_snapshot(config, runner, source)
    state = launch.get("state")
    if state not in {"LOADED", "UNLOADED"}:
        raise CutoverSafetyError("launchd returned an unknown service state")
    if state == "LOADED" and _loaded_runtime(launch) != expected_runtime:
        raise CutoverSafetyError("loaded LaunchAgent runtime tuple differs")
    return launch


def _assert_quiescent(config: CutoverConfig, runner: Runner, source: Record) -> Record:
    ownership = _ownership_snapshot(config, runner, source)
    _assert_idle(ownership)
    return ownership


def _after_state(
    config: CutoverConfig,
    runner: Runner,
    source: Record,
    expected_runtime: Record,
) -> Record:
    identity, data = _file_identity(config.plist_path, missing_ok=False, require_mode=0o600)
    if identity is None or data is None:
        raise CutoverSafetyError("final plist is unavailable")
    binding, runtime = _parse_plist(data, "final")
    if runtime != expected_runtime:
        raise CutoverSafetyError("final plist runtime tuple differs")
    launch = _assert_runtime_binding(config, runner, source, expected_runtime)
    enabled = _enabled_snapshot(config, runner)
    return {
        "observed_at": _utc_text(_now()),
        "source": source,
        "runtime": runtime,
        "plist": {
            "identity": identity.to_dict(),
            "sha256": identity.sha256,
            "size": identity.size,
            "binding": binding,
        },
        "launchd": {
            "target": config.target,
            "state": launch.get("state"),
            "loaded_runtime": _loaded_runtime(launch),
        },
        "enabled": enabled,
    }


def _run_launch_mutation(
    recorder: ActionRecorder,
    runner: Runner,
    name: str,
    argv: Sequence[str],
    *,
    observe_satisfied: Callable[[], bool] | None = None,
) -> None:
    result = recorder.command(name, argv, runner)
    if result.returncode == 0:
        return
    if observe_satisfied is not None:
        try:
            if observe_satisfied():
                recorder.event(name + "-postattempt-satisfied", returncode=result.returncode)
                return
        except BaseException as exc:
            recorder.event(name + "-postattempt-unverifiable", error=f"{type(exc).__name__}: {exc}")
    raise MutationError(f"{name} failed with exit {result.returncode}")


def _observe_after_identity(path: Path) -> tuple[Record, str]:
    """Observe the destination after an ambiguous replacement attempt."""

    try:
        identity, _ = _file_identity(path, missing_ok=True, require_mode=0o600)
        if identity is None:
            return {"state": "ABSENT", "path": str(path)}, "ABSENT"
        return identity.to_dict(), "OBSERVED"
    except BaseException as exc:
        return {
            "state": "UNVERIFIABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }, "UNVERIFIABLE"


def _replace_plist(
    path: Path,
    data: bytes,
    *,
    expected: FileIdentity,
    before: FileIdentity,
    name: str,
    recorder: ActionRecorder,
) -> FileIdentity:
    """Replace a plist while conservatively accounting for ambiguous writes."""

    recorder.mutation_count += 1
    try:
        identity = _atomic_write(path, data, expected=expected)
    except BaseException as exc:
        after, after_observation = _observe_after_identity(path)
        recorder.event(
            name,
            status="EXCEPTION",
            before=before.to_dict(),
            after=after,
            after_observation=after_observation,
            error=f"{type(exc).__name__}: {exc}",
            mutation=True,
        )
        raise MutationError(f"{name} failed: {type(exc).__name__}: {exc}") from exc
    recorder.event(
        name,
        status="PASS",
        before=before.to_dict(),
        after=identity.to_dict(),
        sha256=identity.sha256,
        mutation=True,
    )
    return identity


def _decode_bytes(value: object, label: str) -> bytes:
    encoded = _text(value, label)
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CutoverSafetyError(f"{label} is not valid base64") from exc


def _mutation_summary(actions: Sequence[Record]) -> Record:
    names = [str(action.get("name", "")) for action in actions]
    return {
        "launchd": any(
            name.startswith(("disable", "bootout", "bootstrap", "enable")) for name in names
        ),
        "plist": any(name in {"install-plist", "restore-plist"} for name in names),
        "control_files": True,
    }


def _prestate_runtime(prestate: Record, key: str) -> Record:
    return _record(prestate.get(key), f"prestate {key}")


def _apply_or_restore(
    config: CutoverConfig,
    plan: Record,
    *,
    runner: Runner,
    recorder: ActionRecorder,
    restoring: bool,
    allow_old_prestate: bool = False,
) -> Record:
    prestate = _record(plan.get("prestate"), "plan prestate")
    old_identity = _identity_from_record(prestate.get("old_plist_identity"), "old plist identity")
    old_bytes = _decode_bytes(prestate.get("old_plist_bytes_b64"), "old plist bytes")
    new_bytes = _decode_bytes(prestate.get("new_plist_bytes_b64"), "new plist bytes")
    if old_identity.path != str(config.plist_path):
        raise CutoverSafetyError("old plist identity is bound to a different target")
    if old_identity.sha256 != _sha256_bytes(old_bytes):
        raise CutoverSafetyError("old plist identity does not match its preserved bytes")
    old_source = _prestate_runtime(prestate, "old_source")
    new_source = _prestate_runtime(prestate, "new_source")
    old_runtime = _prestate_runtime(prestate, "old_runtime")
    new_runtime = _record(_record(plan.get("runtime"), "plan runtime").get("new"), "new runtime")
    new_sha = _text(prestate.get("new_plist_sha256"), "new plist sha256")
    if new_sha != _sha256_bytes(new_bytes):
        raise CutoverSafetyError("new plist digest does not match its preserved bytes")
    old_loaded = prestate.get("old_launch_state") == "LOADED"
    old_enabled = prestate.get("old_enabled")
    if type(old_enabled) is not bool:
        raise CutoverSafetyError("old enabled state is invalid")
    current_identity, current_bytes = _file_identity(
        config.plist_path,
        missing_ok=False,
        require_mode=0o600,
    )
    if current_identity is None or current_bytes is None:
        raise CutoverSafetyError("current plist disappeared before restore")
    restoring_old_prestate = False
    if restoring:
        new_sha = _text(prestate.get("new_plist_sha256"), "new plist sha256")
        if current_identity.sha256 == old_identity.sha256 and current_bytes == old_bytes:
            restoring_old_prestate = allow_old_prestate
        if not restoring_old_prestate and (
            current_identity.sha256 != new_sha or current_bytes != new_bytes
        ):
            raise CutoverSafetyError("rollback receipt is not bound to current plist identity")
    else:
        if current_identity.key() != old_identity.key() or current_bytes != old_bytes:
            raise CutoverSafetyError("apply prestate plist drifted")
    restoring_new = restoring and not restoring_old_prestate
    current_source = new_source if restoring_new else old_source
    current_runtime = new_runtime if restoring_new else old_runtime
    expected_current_bytes = new_bytes if restoring_new else old_bytes
    current_launch = _assert_runtime_binding(config, runner, current_source, current_runtime)
    current_enabled = _enabled_snapshot(config, runner)
    if not restoring:
        if current_launch.get("state") != ("LOADED" if old_loaded else "UNLOADED"):
            raise CutoverSafetyError("apply launchd state drifted from the plan prestate")
        if current_enabled is not old_enabled:
            raise CutoverSafetyError("apply enabled state drifted from the plan prestate")
    _assert_quiescent(config, runner, current_source)
    if current_launch.get("state") == "LOADED" and current_enabled:
        _run_launch_mutation(
            recorder,
            runner,
            "disable-before-restore" if restoring else "disable-before-apply",
            ["launchctl", "disable", config.target],
            observe_satisfied=lambda: _enabled_snapshot(config, runner) is False,
        )
        _assert_enabled(config, runner, False)
    elif current_enabled:
        _run_launch_mutation(
            recorder,
            runner,
            "disable-unloaded-before-restore" if restoring else "disable-unloaded-before-apply",
            ["launchctl", "disable", config.target],
            observe_satisfied=lambda: _enabled_snapshot(config, runner) is False,
        )
        _assert_enabled(config, runner, False)
    else:
        recorder.event("disable-skip", reason="already disabled")
    stable_identity, _ = _assert_expected_plist(
        config.plist_path,
        current_identity,
        expected_bytes=expected_current_bytes,
    )
    current_launch = _assert_runtime_binding(config, runner, current_source, current_runtime)
    if current_launch.get("state") == "LOADED":
        _assert_quiescent(config, runner, current_source)
        _run_launch_mutation(
            recorder,
            runner,
            "bootout-before-restore" if restoring else "bootout-before-apply",
            ["launchctl", "bootout", config.target],
            observe_satisfied=lambda: (
                _launch_snapshot(config, runner, current_source).get("state") == "UNLOADED"
            ),
        )
        current_launch = _launch_snapshot(config, runner, current_source)
        if current_launch.get("state") != "UNLOADED":
            raise MutationError("LaunchAgent remained loaded after bootout")
        _assert_quiescent(config, runner, current_source)
    else:
        recorder.event("bootout-skip", reason="already unloaded")
    stable_identity, _ = _assert_expected_plist(
        config.plist_path,
        stable_identity,
        expected_bytes=expected_current_bytes,
    )
    current_launch = _assert_runtime_binding(config, runner, current_source, current_runtime)
    if current_launch.get("state") != "UNLOADED":
        raise MutationError("LaunchAgent was rebound during the mutation boundary")
    _assert_quiescent(config, runner, current_source)
    if restoring:
        _replace_plist(
            config.plist_path,
            old_bytes,
            expected=stable_identity,
            before=stable_identity,
            name="restore-plist",
            recorder=recorder,
        )
    else:
        _replace_plist(
            config.plist_path,
            new_bytes,
            expected=stable_identity,
            before=stable_identity,
            name="install-plist",
            recorder=recorder,
        )
    installed_identity, installed_bytes = _file_identity(
        config.plist_path,
        missing_ok=False,
        require_mode=0o600,
    )
    if installed_identity is None or installed_bytes is None:
        raise MutationError("installed plist cannot be read back")
    if restoring:
        if installed_bytes != old_bytes:
            raise MutationError("restored plist readback differs")
    elif installed_bytes != new_bytes:
        raise MutationError("installed plist readback differs")
    installed_runtime = _parse_plist(installed_bytes, "installed")[1]
    expected_runtime = old_runtime if restoring else new_runtime
    if installed_runtime != expected_runtime:
        raise MutationError("installed plist runtime tuple differs")
    if _launch_snapshot(config, runner, current_source).get("state") != "UNLOADED":
        raise MutationError("LaunchAgent was loaded during the plist mutation boundary")
    desired_loaded = old_loaded
    expected_source = old_source if restoring else new_source
    for source in (current_source, expected_source):
        _assert_quiescent(config, runner, source)
    if desired_loaded:
        _validate_bound_source(
            config,
            expected_source,
            runner,
            role="bootstrap-old" if restoring else "bootstrap-new",
            legacy_prestate=restoring,
        )
        _assert_quiescent(config, runner, expected_source)
        _run_launch_mutation(
            recorder,
            runner,
            "bootstrap-old" if restoring else "bootstrap-new",
            ["launchctl", "bootstrap", config.launch_domain, str(config.plist_path)],
            observe_satisfied=lambda: (
                _launch_snapshot(config, runner, current_source).get("state") == "LOADED"
            ),
        )
        _assert_loaded_binding(config, runner, expected_source, expected_runtime)
    else:
        recorder.event("bootstrap-skip", reason="prestate was unloaded")
    if old_enabled:
        _assert_quiescent(config, runner, expected_source)
        _run_launch_mutation(
            recorder,
            runner,
            "enable-restored" if restoring else "enable-new",
            ["launchctl", "enable", config.target],
            observe_satisfied=lambda: _enabled_snapshot(config, runner) is True,
        )
        _assert_enabled(config, runner, True)
    else:
        recorder.event("enable-skip", reason="prestate was disabled")
        _assert_enabled(config, runner, False)
    final_launch = _launch_snapshot(config, runner, expected_source)
    if desired_loaded:
        if (
            final_launch.get("state") != "LOADED"
            or _loaded_runtime(final_launch) != expected_runtime
        ):
            raise MutationError("final loaded binding does not match requested release")
    elif final_launch.get("state") != "UNLOADED":
        raise MutationError("final LaunchAgent state does not preserve unloaded prestate")
    _assert_enabled(config, runner, bool(old_enabled))
    return _after_state(config, runner, expected_source, expected_runtime)


def _receipt_base(config: CutoverConfig, plan: Record, operation_id: str) -> Record:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "task": TASK_ID,
        "operation_id": operation_id,
        # This receipt is durably staged before any launchd or plist mutation.
        # An interrupted process therefore cannot leave an authoritative
        # NOT_STARTED receipt after entering the state-changing operation.
        "status": "IN_PROGRESS",
        "phase": "IN_PROGRESS",
        "created_at": _utc_text(_now()),
        "updated_at": _utc_text(_now()),
        "target": plan["target"],
        "plan_digest": plan.get("plan_digest"),
        "prestate_digest": plan.get("prestate_digest"),
        "prestate": plan.get("prestate"),
        "source": plan.get("source"),
        "runtime": plan.get("runtime"),
        "actions": [],
        "failures": [],
        "mutation_summary": {"launchd": False, "plist": False, "control_files": True},
    }


def _receipt_status(path: Path) -> tuple[Record, FileIdentity] | None:
    if not path.exists():
        return None
    value, identity, _ = _load_json(path)
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise CutoverSafetyError("existing receipt schema differs")
    if value.get("task") != TASK_ID:
        raise CutoverSafetyError("existing receipt task differs")
    return value, identity


def _validate_bound_source(
    config: CutoverConfig,
    source: Record,
    runner: Runner,
    *,
    role: str,
    legacy_prestate: bool = False,
) -> Record:
    """Re-validate one frozen source Record before a mutation boundary.

    ``legacy_prestate`` must be set exactly when ``source`` is the receipt-
    bound OLD/PRESTATE side, never for a NEW release: NEW materialization
    always keeps ``config.strict_release_layout``'s ``B649_PRODUCTION_<HEAD>``
    directory requirement, but a receipt-bound OLD source predates that
    convention and is already pinned by its own exact HEAD/tree/durable-ref/
    cleanliness/runtime-tuple containment instead -- the same exemption
    ``build_plan``'s and ``rollback``'s own inline OLD-role validation already
    grant by passing ``strict_release_layout=False`` directly. Every other
    check is unaffected.
    """

    source_path = Path(_text(source.get("source_worktree"), f"{role} source worktree"))
    bound_config = replace(config, source_worktree=source_path)
    return _validate_source(
        bound_config,
        runner,
        role=role,
        expected_head=_text(source.get("head"), f"{role} head"),
        expected_tree=_text(source.get("tree"), f"{role} tree"),
        expected_ref=_text(source.get("durable_ref"), f"{role} durable ref"),
        strict_release_layout=False if legacy_prestate else config.strict_release_layout,
    )


def _save_receipt(
    config: CutoverConfig, receipt: Record, *, expected: FileIdentity | None
) -> FileIdentity:
    receipt["updated_at"] = _utc_text(_now())
    identity = _write_json(config.receipt_path, receipt, expected=expected)
    return identity


def _append_failure(receipt: Record, message: str) -> None:
    cast(list[str], receipt.setdefault("failures", [])).append(message)


def _best_effort_recovery_receipt(
    config: CutoverConfig,
    receipt: Record,
    *,
    expected: FileIdentity,
) -> None:
    """Persist recovery provenance only if the receipt identity is unchanged."""

    try:
        current, _ = _file_identity(config.receipt_path, missing_ok=False, require_mode=0o600)
        if current is None or current.key() != expected.key():
            raise CutoverSafetyError("receipt identity changed before recovery write")
        _save_receipt(config, receipt, expected=current)
    except BaseException as exc:
        _append_failure(receipt, f"receipt recovery write: {type(exc).__name__}: {exc}")


def _apply_existing_receipt(
    config: CutoverConfig,
    receipt: Record,
    *,
    runner: Runner,
) -> Record | None:
    status = receipt.get("status")
    if status not in {
        "SUCCESS",
        "ROLLBACK_SUCCESS",
        "ROLLBACK_IN_PROGRESS",
        "RECOVERED",
        "RECOVERY_REQUIRED",
        "PARTIAL",
        "IN_PROGRESS",
        "NOT_STARTED",
    }:
        raise CutoverSafetyError("existing receipt status is invalid")
    plan = _record(receipt, "receipt")
    prestate = _record(plan.get("prestate"), "receipt prestate")
    source = _prestate_runtime(prestate, "new_source")
    _validate_bound_source(config, source, runner, role="existing-new", legacy_prestate=False)
    if status == "SUCCESS":
        current_identity, current_bytes = _file_identity(
            config.plist_path,
            missing_ok=True,
            require_mode=0o600,
        )
        new_bytes = _decode_bytes(prestate.get("new_plist_bytes_b64"), "receipt new plist bytes")
        if current_identity is not None and current_bytes == new_bytes:
            launch = _launch_snapshot(config, runner, source)
            enabled = _enabled_snapshot(config, runner)
            desired_loaded = prestate.get("old_launch_state") == "LOADED"
            desired_enabled = prestate.get("old_enabled") is True
            loaded_ok = (not desired_loaded and launch.get("state") == "UNLOADED") or (
                desired_loaded and launch.get("state") == "LOADED"
            )
            if loaded_ok and desired_loaded:
                loaded_ok = _loaded_runtime(launch) == _record(
                    _record(receipt.get("runtime"), "receipt runtime").get("new"),
                    "receipt new runtime",
                )
            if loaded_ok and enabled is desired_enabled:
                return {
                    "command": "apply",
                    "task": TASK_ID,
                    "status": "ALREADY_APPLIED",
                    "receipt_status": status,
                    "operation_id": receipt.get("operation_id"),
                    "actions": [],
                }
        raise CutoverSafetyError("successful receipt exists but live state does not match it")
    if status in {
        "RECOVERY_REQUIRED",
        "PARTIAL",
        "IN_PROGRESS",
        "NOT_STARTED",
        "RECOVERED",
        "ROLLBACK_SUCCESS",
        "ROLLBACK_IN_PROGRESS",
    }:
        return {
            "command": "apply",
            "task": TASK_ID,
            "status": "RECOVERY_REQUIRED"
            if status in {"RECOVERY_REQUIRED", "PARTIAL", "IN_PROGRESS"}
            else "NOT_STARTED",
            "receipt_status": status,
            "operation_id": receipt.get("operation_id"),
            "failures": ["existing receipt requires explicit reconciliation; blind retry refused"],
            "actions": [],
        }
    return None


def _reconcile_completed_receipt(
    config: CutoverConfig,
    receipt: Record,
    *,
    runner: Runner,
) -> None:
    """Prove a completed receipt still describes the live state before reuse."""

    after = _record(receipt.get("after"), "receipt after")
    source = _record(after.get("source"), "receipt after source")
    runtime = _record(after.get("runtime"), "receipt after runtime")
    plist = _record(after.get("plist"), "receipt after plist")
    identity = _identity_from_record(plist.get("identity"), "receipt after plist identity")
    if identity.path != str(config.plist_path):
        raise CutoverSafetyError("completed receipt is bound to a different plist")
    current_identity, current_bytes = _file_identity(
        config.plist_path,
        missing_ok=False,
        require_mode=0o600,
    )
    if (
        current_identity is None
        or current_bytes is None
        or current_identity.sha256 != identity.sha256
        or current_identity.size != identity.size
    ):
        raise CutoverSafetyError("completed receipt does not match the current plist")
    # "after.source" is frozen from whichever side the last completed
    # operation actually left running -- a successful apply leaves NEW, a
    # successful rollback (or a recovery restoring the prestate) leaves OLD --
    # so legacy_prestate must be bound to that recorded side, not guessed from
    # role alone, or a completed rollback onto a legacy-layout OLD source
    # would have NEW's strict layout wrongly reapplied to it here.
    prestate = _record(receipt.get("prestate"), "receipt prestate")
    old_source_prestate = _prestate_runtime(prestate, "old_source")
    new_source_prestate = _prestate_runtime(prestate, "new_source")
    if source == old_source_prestate:
        legacy_prestate = True
    elif source == new_source_prestate:
        legacy_prestate = False
    else:
        raise CutoverSafetyError("completed receipt after-source matches neither prestate side")
    _validate_bound_source(
        config, source, runner, role="existing-after", legacy_prestate=legacy_prestate
    )
    _, current_runtime = _parse_plist(current_bytes, "existing-after")
    if current_runtime != runtime:
        raise CutoverSafetyError("completed receipt runtime differs from the current plist")
    expected_launchd = _record(after.get("launchd"), "receipt after launchd")
    expected_state = _text(expected_launchd.get("state"), "receipt after launchd state")
    current_launch = _launch_snapshot(config, runner, source)
    if current_launch.get("state") != expected_state:
        raise CutoverSafetyError("completed receipt LaunchAgent state differs from live state")
    if expected_state == "LOADED" and _loaded_runtime(current_launch) != runtime:
        raise CutoverSafetyError("completed receipt loaded runtime differs from live state")
    enabled = after.get("enabled")
    if type(enabled) is not bool or _enabled_snapshot(config, runner) is not enabled:
        raise CutoverSafetyError("completed receipt enabled state differs from live state")


def apply(
    config: CutoverConfig,
    *,
    plan: Record | None = None,
    runner: Runner = run_command,
    now: datetime | None = None,
) -> Record:
    """Apply one validated plan, retaining a bounded receipt and recovery path."""

    _validate_config(config)
    selected_plan = plan if plan is not None else build_plan(config, runner=runner, now=now)
    _plan_target_matches(config, selected_plan)
    recorder = ActionRecorder([])
    try:
        with CutoverLock(config.cutover_lock_path):
            recorder.event("cutover-lock-acquired", path=str(config.cutover_lock_path))
            receipt_expected: FileIdentity | None = None
            existing_record = _receipt_status(config.receipt_path)
            if existing_record is not None:
                existing, existing_identity = existing_record
                existing_plan = _receipt_to_plan(config, existing)
                _plan_target_matches(config, existing_plan)
                if existing_plan.get("plan_digest") != selected_plan.get("plan_digest"):
                    if existing.get("status") not in {
                        "SUCCESS",
                        "RECOVERED",
                        "ROLLBACK_SUCCESS",
                    }:
                        raise CutoverSafetyError("existing receipt is not safely reusable")
                    _reconcile_completed_receipt(config, existing, runner=runner)
                    receipt_expected = existing_identity
                    already = None
                else:
                    already = _apply_existing_receipt(config, existing, runner=runner)
                if already is not None:
                    already["actions"] = recorder.actions
                    return already

            fresh = _fresh_plan_matches(config, selected_plan, runner=runner)
            receipt = _receipt_base(config, fresh, uuid4().hex)
            try:
                receipt_identity = _save_receipt(config, receipt, expected=receipt_expected)
            except BaseException as exc:
                return {
                    "command": "apply",
                    "task": TASK_ID,
                    "status": "NOT_STARTED",
                    "failures": [f"receipt prestate write failed: {type(exc).__name__}: {exc}"],
                    "actions": recorder.actions,
                    "mutation_summary": {
                        "launchd": False,
                        "plist": False,
                        "control_files": True,
                    },
                }

            try:
                after = _apply_or_restore(
                    config,
                    fresh,
                    runner=runner,
                    recorder=recorder,
                    restoring=False,
                )
            except BaseException as exc:
                receipt["status"] = "PARTIAL" if recorder.mutation_count else "NOT_STARTED"
                receipt["phase"] = "RECOVERY_REQUIRED" if recorder.mutation_count else "NOT_STARTED"
                cast(list[str], receipt["failures"]).append(f"{type(exc).__name__}: {exc}")
                receipt["actions"] = recorder.actions
                receipt["mutation_summary"] = _mutation_summary(recorder.actions)
                if receipt["status"] == "PARTIAL":
                    recovery_recorder = ActionRecorder(
                        recorder.actions,
                        recorder.mutation_count,
                    )
                    try:
                        recovered_after = _apply_or_restore(
                            config,
                            fresh,
                            runner=runner,
                            recorder=recovery_recorder,
                            restoring=True,
                            allow_old_prestate=True,
                        )
                        receipt["status"] = "RECOVERED"
                        receipt["phase"] = "COMPLETED"
                        receipt["after"] = recovered_after
                    except BaseException as recovery_exc:
                        receipt["status"] = "RECOVERY_REQUIRED"
                        receipt["phase"] = "RECOVERY_REQUIRED"
                        cast(list[str], receipt["failures"]).append(
                            f"recovery: {type(recovery_exc).__name__}: {recovery_exc}"
                        )
                    receipt["actions"] = recovery_recorder.actions
                    receipt["mutation_summary"] = _mutation_summary(recovery_recorder.actions)
                try:
                    _save_receipt(config, receipt, expected=receipt_identity)
                except BaseException as receipt_exc:
                    receipt["status"] = "RECOVERY_REQUIRED"
                    receipt["phase"] = "RECOVERY_REQUIRED"
                    _append_failure(
                        receipt, f"receipt final write: {type(receipt_exc).__name__}: {receipt_exc}"
                    )
                    _best_effort_recovery_receipt(config, receipt, expected=receipt_identity)
                return {
                    "command": "apply",
                    "task": TASK_ID,
                    "status": receipt["status"],
                    "receipt_path": str(config.receipt_path),
                    "operation_id": receipt["operation_id"],
                    "before": fresh.get("prestate"),
                    "after": receipt.get("after"),
                    "failures": receipt["failures"],
                    "actions": receipt["actions"],
                    "mutation_summary": receipt["mutation_summary"],
                }

            receipt["status"] = "SUCCESS"
            receipt["phase"] = "COMPLETED"
            receipt["after"] = after
            receipt["actions"] = recorder.actions
            receipt["mutation_summary"] = _mutation_summary(recorder.actions)
            try:
                _save_receipt(config, receipt, expected=receipt_identity)
            except BaseException as receipt_exc:
                receipt["status"] = "RECOVERY_REQUIRED"
                receipt["phase"] = "RECOVERY_REQUIRED"
                _append_failure(
                    receipt, f"receipt final write: {type(receipt_exc).__name__}: {receipt_exc}"
                )
                _best_effort_recovery_receipt(config, receipt, expected=receipt_identity)
                return {
                    "command": "apply",
                    "task": TASK_ID,
                    "status": "RECOVERY_REQUIRED",
                    "receipt_path": str(config.receipt_path),
                    "operation_id": receipt["operation_id"],
                    "before": fresh.get("prestate"),
                    "after": after,
                    "failures": receipt["failures"],
                    "actions": recorder.actions,
                    "mutation_summary": receipt["mutation_summary"],
                }
            return {
                "command": "apply",
                "task": TASK_ID,
                "status": "SUCCESS",
                "receipt_path": str(config.receipt_path),
                "operation_id": receipt["operation_id"],
                "before": fresh.get("prestate"),
                "after": after,
                "actions": recorder.actions,
                "mutation_summary": receipt["mutation_summary"],
            }
    except CutoverAlreadyRunning as exc:
        return {
            "command": "apply",
            "task": TASK_ID,
            "status": "NOT_STARTED",
            "failures": [f"CONCURRENT_APPLY: {exc}"],
            "actions": recorder.actions,
            "mutation_summary": {
                "launchd": False,
                "plist": False,
                "control_files": False,
            },
        }


def _receipt_to_plan(config: CutoverConfig, receipt: Record) -> Record:
    target = _record(receipt.get("target"), "receipt target")
    prestate = _record(receipt.get("prestate"), "receipt prestate")
    runtime = _record(receipt.get("runtime"), "receipt runtime")
    source = _record(receipt.get("source"), "receipt source")
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "task": TASK_ID,
        "status": "PASS",
        "target": target,
        "prestate": prestate,
        "prestate_digest": receipt.get("prestate_digest"),
        "plan_digest": receipt.get("plan_digest"),
        "runtime": runtime,
        "source": source,
    }


def rollback(
    config: CutoverConfig,
    *,
    receipt: Record | None = None,
    runner: Runner = run_command,
    now: datetime | None = None,
) -> Record:
    """Restore only the exact prestate bound to one cutover receipt."""

    del now
    _validate_config(config)
    stored_receipt, receipt_identity, _ = _load_json(config.receipt_path)
    loaded_receipt = stored_receipt if receipt is None else receipt
    if receipt is not None and _canonical_json(receipt) != _canonical_json(stored_receipt):
        raise CutoverSafetyError("supplied receipt differs from the durable receipt")
    if (
        loaded_receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or loaded_receipt.get("task") != TASK_ID
    ):
        raise CutoverSafetyError("receipt schema or task differs")
    _plan_target_matches(config, _receipt_to_plan(config, loaded_receipt))
    status = loaded_receipt.get("status")
    if status == "ROLLBACK_SUCCESS":
        return {
            "command": "rollback",
            "task": TASK_ID,
            "status": "ALREADY_ROLLED_BACK",
            "receipt_path": str(config.receipt_path),
            "operation_id": loaded_receipt.get("operation_id"),
            "actions": [],
        }
    if status not in {
        "SUCCESS",
        "PARTIAL",
        "RECOVERY_REQUIRED",
        "RECOVERED",
        "ROLLBACK_IN_PROGRESS",
        "IN_PROGRESS",
    }:
        raise CutoverSafetyError("receipt is not eligible for explicit rollback")
    plan = _receipt_to_plan(config, loaded_receipt)
    prestate = _record(plan.get("prestate"), "receipt prestate")
    old_source = _prestate_runtime(prestate, "old_source")
    new_source = _prestate_runtime(prestate, "new_source")
    old_config = replace(
        config,
        source_worktree=Path(_text(old_source.get("source_worktree"), "old source")),
        strict_release_layout=False,
    )
    recorder = ActionRecorder([])
    try:
        with CutoverLock(config.cutover_lock_path):
            recorder.event("cutover-lock-acquired", path=str(config.cutover_lock_path))
            _validate_source(
                old_config,
                runner,
                role="rollback-old",
                expected_head=_text(old_source.get("head"), "old head"),
                expected_tree=_text(old_source.get("tree"), "old tree"),
                expected_ref=_text(old_source.get("durable_ref"), "old durable ref"),
                strict_release_layout=False,
            )
            current_identity, current_bytes = _file_identity(
                config.plist_path,
                missing_ok=False,
                require_mode=0o600,
            )
            if current_identity is None or current_bytes is None:
                raise CutoverSafetyError("current plist is missing for rollback")
            new_bytes = _decode_bytes(prestate.get("new_plist_bytes_b64"), "new plist bytes")
            old_bytes = _decode_bytes(prestate.get("old_plist_bytes_b64"), "old plist bytes")
            current_is_new = current_bytes == new_bytes
            current_is_old = current_bytes == old_bytes
            if not current_is_new and not current_is_old:
                raise CutoverSafetyError("current plist differs from receipt-bound new plist")
            new_runtime = _record(
                _record(plan.get("runtime"), "receipt runtime").get("new"),
                "receipt new runtime",
            )
            old_runtime = _prestate_runtime(prestate, "old_runtime")
            rollback_source = new_source if current_is_new else old_source
            rollback_runtime = new_runtime if current_is_new else old_runtime
            current_ownership = _ownership_snapshot(config, runner, rollback_source)
            _assert_idle(current_ownership)
            current_binding, current_runtime = _parse_plist(current_bytes, "rollback-current")
            if current_runtime != rollback_runtime:
                raise CutoverSafetyError(
                    "current plist runtime differs from receipt-bound recovery runtime"
                )
            current_launch = _assert_runtime_binding(
                config, runner, rollback_source, rollback_runtime
            )
            current_enabled = _enabled_snapshot(config, runner)
            rollback_before: Record = {
                "observed_at": _utc_text(_now()),
                "source": rollback_source,
                "runtime": current_runtime,
                "plist": {
                    "identity": current_identity.to_dict(),
                    "sha256": current_identity.sha256,
                    "size": current_identity.size,
                    "binding": current_binding,
                },
                "launchd": {
                    "target": config.target,
                    "state": current_launch.get("state"),
                    "loaded_runtime": _loaded_runtime(current_launch),
                },
                "enabled": current_enabled,
            }
            loaded_receipt["status"] = "ROLLBACK_IN_PROGRESS"
            loaded_receipt["before"] = rollback_before
            loaded_receipt["actions"] = recorder.actions
            try:
                receipt_identity = _save_receipt(
                    config,
                    loaded_receipt,
                    expected=receipt_identity,
                )
            except BaseException as receipt_exc:
                loaded_receipt["status"] = "RECOVERY_REQUIRED"
                _append_failure(
                    loaded_receipt,
                    f"rollback prestage receipt write: {type(receipt_exc).__name__}: {receipt_exc}",
                )
                loaded_receipt["mutation_summary"] = _mutation_summary(recorder.actions)
                _best_effort_recovery_receipt(
                    config,
                    loaded_receipt,
                    expected=receipt_identity,
                )
                return {
                    "command": "rollback",
                    "task": TASK_ID,
                    "status": "RECOVERY_REQUIRED",
                    "receipt_path": str(config.receipt_path),
                    "operation_id": loaded_receipt.get("operation_id"),
                    "before": rollback_before,
                    "failures": loaded_receipt["failures"],
                    "actions": recorder.actions,
                    "mutation_summary": loaded_receipt["mutation_summary"],
                }
            try:
                after = _apply_or_restore(
                    config,
                    plan,
                    runner=runner,
                    recorder=recorder,
                    restoring=True,
                    allow_old_prestate=current_is_old,
                )
            except BaseException as exc:
                loaded_receipt["status"] = "RECOVERY_REQUIRED"
                cast(list[str], loaded_receipt.setdefault("failures", [])).append(
                    f"rollback: {type(exc).__name__}: {exc}"
                )
                loaded_receipt["actions"] = recorder.actions
                loaded_receipt["mutation_summary"] = _mutation_summary(recorder.actions)
                try:
                    _save_receipt(
                        config,
                        loaded_receipt,
                        expected=receipt_identity,
                    )
                except BaseException as receipt_exc:
                    _append_failure(
                        loaded_receipt,
                        f"receipt final write: {type(receipt_exc).__name__}: {receipt_exc}",
                    )
                    _best_effort_recovery_receipt(
                        config,
                        loaded_receipt,
                        expected=receipt_identity,
                    )
                return {
                    "command": "rollback",
                    "task": TASK_ID,
                    "status": "RECOVERY_REQUIRED",
                    "receipt_path": str(config.receipt_path),
                    "operation_id": loaded_receipt.get("operation_id"),
                    "before": rollback_before,
                    "after": loaded_receipt.get("after"),
                    "failures": loaded_receipt["failures"],
                    "actions": recorder.actions,
                }
            loaded_receipt["status"] = "ROLLBACK_SUCCESS"
            loaded_receipt["phase"] = "COMPLETED"
            loaded_receipt["after"] = after
            loaded_receipt["actions"] = recorder.actions
            loaded_receipt["mutation_summary"] = _mutation_summary(recorder.actions)
            loaded_receipt["rollback_completed_at"] = _utc_text(_now())
            try:
                _save_receipt(
                    config,
                    loaded_receipt,
                    expected=receipt_identity,
                )
            except BaseException as receipt_exc:
                loaded_receipt["status"] = "RECOVERY_REQUIRED"
                loaded_receipt["phase"] = "RECOVERY_REQUIRED"
                _append_failure(
                    loaded_receipt,
                    f"receipt final write: {type(receipt_exc).__name__}: {receipt_exc}",
                )
                _best_effort_recovery_receipt(
                    config,
                    loaded_receipt,
                    expected=receipt_identity,
                )
                return {
                    "command": "rollback",
                    "task": TASK_ID,
                    "status": "RECOVERY_REQUIRED",
                    "receipt_path": str(config.receipt_path),
                    "operation_id": loaded_receipt.get("operation_id"),
                    "before": rollback_before,
                    "after": after,
                    "failures": loaded_receipt["failures"],
                    "actions": recorder.actions,
                    "business_state": "UNCHANGED",
                }
            return {
                "command": "rollback",
                "task": TASK_ID,
                "status": "ROLLBACK_SUCCESS",
                "receipt_path": str(config.receipt_path),
                "operation_id": loaded_receipt.get("operation_id"),
                "before": rollback_before,
                "after": after,
                "actions": recorder.actions,
                "business_state": "UNCHANGED",
            }
    except ActiveCycleError as exc:
        return {
            "command": "rollback",
            "task": TASK_ID,
            "status": "ROLLBACK_BLOCKED_ACTIVE_CYCLE",
            "receipt_path": str(config.receipt_path),
            "operation_id": loaded_receipt.get("operation_id"),
            "failures": [str(exc)],
            "actions": recorder.actions,
            "kill_attempted": False,
        }
    except CutoverAlreadyRunning as exc:
        return {
            "command": "rollback",
            "task": TASK_ID,
            "status": "NOT_STARTED",
            "failures": [f"CONCURRENT_APPLY: {exc}"],
            "actions": recorder.actions,
        }


def reconcile_restored(
    config: CutoverConfig,
    *,
    expected_operation_id: str,
    expected_receipt_sha256: str,
    receipt: Record | None = None,
    runner: Runner = run_command,
    now: datetime | None = None,
) -> Record:
    """Finalize a RECOVERY_REQUIRED receipt whose OLD prestate is already live.

    Receipt-only: proves the live plist, runtime tuple, LaunchAgent state, and
    ownership already equal the receipt-bound OLD prestate, then transitions
    the receipt to ROLLBACK_SUCCESS. Never mutates launchd or the plist, and
    never routes through ``_apply_or_restore`` -- this is a receipt-
    finalization path, not a state-restoration path.
    """

    del now
    _validate_config(config)
    stored_receipt, receipt_identity, raw_bytes = _load_json(config.receipt_path)
    loaded_receipt = stored_receipt if receipt is None else receipt
    if receipt is not None and _canonical_json(receipt) != _canonical_json(stored_receipt):
        raise CutoverSafetyError("supplied receipt differs from the durable receipt")
    if (
        loaded_receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or loaded_receipt.get("task") != TASK_ID
    ):
        raise CutoverSafetyError("receipt schema or task differs")
    if _sha256_bytes(raw_bytes) != expected_receipt_sha256:
        raise CutoverSafetyError("receipt sha256 does not match the expected identity")
    if loaded_receipt.get("operation_id") != expected_operation_id:
        raise CutoverSafetyError("receipt operation_id does not match the expected identity")

    recorder = ActionRecorder([])
    try:
        with CutoverLock(config.cutover_lock_path):
            plan = _receipt_to_plan(config, loaded_receipt)
            _plan_target_matches(config, plan)
            status = loaded_receipt.get("status")
            if status == "ROLLBACK_SUCCESS":
                _reconcile_completed_receipt(config, loaded_receipt, runner=runner)
                return {
                    "command": "reconcile-restored",
                    "task": TASK_ID,
                    "status": "ALREADY_RECONCILED",
                    "receipt_path": str(config.receipt_path),
                    "operation_id": loaded_receipt.get("operation_id"),
                    "actions": [],
                }
            if status != "RECOVERY_REQUIRED":
                raise CutoverSafetyError(
                    f"receipt status is not eligible for reconcile-restored: {status}"
                )

            prestate = _record(plan.get("prestate"), "receipt prestate")
            old_source = _prestate_runtime(prestate, "old_source")
            old_runtime = _prestate_runtime(prestate, "old_runtime")
            old_bytes = _decode_bytes(prestate.get("old_plist_bytes_b64"), "old plist bytes")
            old_loaded = prestate.get("old_launch_state") == "LOADED"
            old_enabled = prestate.get("old_enabled")
            if type(old_enabled) is not bool:
                raise CutoverSafetyError("old enabled state is invalid")

            _validate_bound_source(
                config, old_source, runner, role="reconcile-old", legacy_prestate=True
            )

            current_identity, current_bytes = _file_identity(
                config.plist_path, missing_ok=False, require_mode=0o600
            )
            if current_identity is None or current_bytes is None:
                raise CutoverSafetyError("current plist is unavailable for reconcile-restored")
            if current_bytes != old_bytes:
                raise CutoverSafetyError(
                    "current plist bytes differ from the receipt-bound OLD prestate"
                )
            _, current_runtime = _parse_plist(current_bytes, "reconcile-current")
            if current_runtime != old_runtime:
                raise CutoverSafetyError(
                    "current plist runtime tuple differs from the receipt-bound OLD prestate"
                )

            current_launch = _assert_runtime_binding(config, runner, old_source, old_runtime)
            expected_state = "LOADED" if old_loaded else "UNLOADED"
            if current_launch.get("state") != expected_state:
                raise CutoverSafetyError(
                    "current LaunchAgent state differs from the receipt-bound OLD prestate"
                )
            current_enabled = _enabled_snapshot(config, runner)
            if current_enabled is not old_enabled:
                raise CutoverSafetyError(
                    "current LaunchAgent enabled state differs from the receipt-bound OLD prestate"
                )
            _assert_quiescent(config, runner, old_source)

            after = _after_state(config, runner, old_source, old_runtime)

            recorder.event("reconcile-restored-verified", target=config.target)
            loaded_receipt["status"] = "ROLLBACK_SUCCESS"
            loaded_receipt["phase"] = "COMPLETED"
            loaded_receipt["after"] = after
            loaded_receipt["actions"] = recorder.actions
            loaded_receipt["mutation_summary"] = _mutation_summary(recorder.actions)
            loaded_receipt["rollback_completed_at"] = _utc_text(_now())
            _save_receipt(config, loaded_receipt, expected=receipt_identity)
            return {
                "command": "reconcile-restored",
                "task": TASK_ID,
                "status": "ROLLBACK_SUCCESS",
                "receipt_path": str(config.receipt_path),
                "operation_id": loaded_receipt.get("operation_id"),
                "before": prestate,
                "after": after,
                "actions": recorder.actions,
                "mutation_summary": loaded_receipt["mutation_summary"],
                "business_state": "UNCHANGED",
            }
    except CutoverAlreadyRunning as exc:
        return {
            "command": "reconcile-restored",
            "task": TASK_ID,
            "status": "NOT_STARTED",
            "failures": [f"CONCURRENT_APPLY: {exc}"],
            "actions": recorder.actions,
        }


class JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _add_common(parser: argparse.ArgumentParser, *, source_required: bool) -> None:
    parser.add_argument("--source-worktree", required=source_required)
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-tree")
    parser.add_argument("--durable-ref")
    parser.add_argument("--launch-domain", default=DOMAIN)
    parser.add_argument("--plist-path", default=str(DEFAULT_PLIST_PATH))
    parser.add_argument("--receipt-path", default=str(DEFAULT_RECEIPT_PATH))
    parser.add_argument("--cutover-lock-path", default=str(DEFAULT_CUTOVER_LOCK_PATH))
    parser.add_argument("--primary-lock-path", default=str(DEFAULT_PRIMARY_LOCK_PATH))
    parser.add_argument("--shadow-lock-path", default=str(DEFAULT_SHADOW_LOCK_PATH))


def parser() -> JsonParser:
    cli = JsonParser(description=__doc__, allow_abbrev=False)
    commands = cli.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", allow_abbrev=False, help="Read and render a cutover plan.")
    _add_common(plan, source_required=True)
    apply_parser = commands.add_parser(
        "apply", allow_abbrev=False, help="Apply one validated plan."
    )
    _add_common(apply_parser, source_required=True)
    apply_parser.add_argument("--plan-file")
    rollback_parser = commands.add_parser(
        "rollback", allow_abbrev=False, help="Restore one receipt-bound prestate."
    )
    _add_common(rollback_parser, source_required=False)
    rollback_parser.add_argument("--receipt-file")
    reconcile_parser = commands.add_parser(
        "reconcile-restored",
        allow_abbrev=False,
        help="Finalize a receipt whose OLD prestate is already live.",
    )
    _add_common(reconcile_parser, source_required=False)
    reconcile_parser.add_argument("--receipt-file")
    reconcile_parser.add_argument("--expected-operation-id", required=True)
    reconcile_parser.add_argument("--expected-receipt-sha256", required=True)
    return cli


def _config_from_args(
    args: argparse.Namespace, *, source_worktree: Path | None = None
) -> CutoverConfig:
    source_value = source_worktree or (
        None if args.source_worktree is None else Path(args.source_worktree)
    )
    if source_value is None:
        raise ValueError(
            "--source-worktree is required unless rollback derives it from the receipt"
        )
    return CutoverConfig(
        source_worktree=source_value,
        launch_domain=args.launch_domain,
        plist_path=Path(args.plist_path),
        receipt_path=Path(args.receipt_path),
        cutover_lock_path=Path(args.cutover_lock_path),
        primary_lock_path=Path(args.primary_lock_path),
        shadow_lock_path=Path(args.shadow_lock_path),
        expected_head=args.expected_head,
        expected_tree=args.expected_tree,
        durable_ref=args.durable_ref,
        strict_release_layout=True,
    )


def _error_result(command_name: str, status: str, exc: Exception) -> Record:
    return {
        "command": command_name,
        "task": TASK_ID,
        "status": status,
        "failures": [f"{type(exc).__name__}: {exc}"],
        "actions": [],
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner = run_command,
    now: datetime | None = None,
) -> int:
    command_name = "UNKNOWN"
    try:
        args = parser().parse_args(argv)
        command_name = args.command
        if args.command == "plan":
            result = build_plan(_config_from_args(args), runner=runner, now=now)
            print(_canonical_json(result))
            return 0 if result.get("status") == "PASS" else 1
        if args.command == "apply":
            config = _config_from_args(args)
            selected_plan: Record | None = None
            if args.plan_file:
                selected_plan, _, _ = _load_json(Path(args.plan_file))
            result = apply(config, plan=selected_plan, runner=runner, now=now)
            print(_canonical_json(result))
            return 0 if result.get("status") in {"SUCCESS", "ALREADY_APPLIED"} else 1
        if args.command == "reconcile-restored":
            receipt_file = Path(args.receipt_file) if args.receipt_file else Path(args.receipt_path)
            receipt, _, _ = _load_json(receipt_file)
            new_source = Path(
                _text(
                    _record(
                        _record(receipt.get("prestate"), "receipt prestate").get("new_source"),
                        "new source",
                    ).get("source_worktree"),
                    "new source worktree",
                )
            )
            config = _config_from_args(args, source_worktree=new_source)
            result = reconcile_restored(
                config,
                expected_operation_id=args.expected_operation_id,
                expected_receipt_sha256=args.expected_receipt_sha256,
                receipt=receipt,
                runner=runner,
                now=now,
            )
            print(_canonical_json(result))
            return 0 if result.get("status") in {"ROLLBACK_SUCCESS", "ALREADY_RECONCILED"} else 1
        receipt_file = Path(args.receipt_file) if args.receipt_file else Path(args.receipt_path)
        receipt, _, _ = _load_json(receipt_file)
        new_source = Path(
            _text(
                _record(
                    _record(receipt.get("prestate"), "receipt prestate").get("new_source"),
                    "new source",
                ).get("source_worktree"),
                "new source worktree",
            )
        )
        config = _config_from_args(args, source_worktree=new_source)
        result = rollback(config, receipt=receipt, runner=runner, now=now)
        print(_canonical_json(result))
        return 0 if result.get("status") in {"ROLLBACK_SUCCESS", "ALREADY_ROLLED_BACK"} else 1
    except ValueError as exc:
        result = _error_result(command_name, "FAIL", exc)
        print(_canonical_json(result))
        return 2
    except Exception as exc:
        result = _error_result(command_name, "NOT_STARTED", exc)
        print(_canonical_json(result))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PLAN_SCHEMA_VERSION",
    "RECEIPT_SCHEMA_VERSION",
    "ActiveCycleError",
    "CutoverAlreadyRunning",
    "CutoverConfig",
    "CutoverError",
    "CutoverSafetyError",
    "FileIdentity",
    "apply",
    "build_plan",
    "main",
    "parser",
    "reconcile_restored",
    "rollback",
    "run_command",
]
