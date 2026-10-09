"""Fail-closed source identity and machine-level ownership gates for B649 heavy work."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AUTHORITY_HEAD_ENV = "LOTTOLAB_B649_EXECUTION_AUTHORITY_HEAD"
AUTHORITY_TREE_ENV = "LOTTOLAB_B649_EXECUTION_AUTHORITY_TREE"
DEFAULT_HEAVY_LOCK_PATH = (
    Path.home() / ".codex" / "locks" / "b649-heavy-execution.lock"
)
LEGACY_CENSUS_MODULE = "lottolab.research.b649_k20_fiber_near_top_s3_census"
R30_TAG_PREFIX = "b649-r30-source-"


class SafetyGateError(RuntimeError):
    """An execution source or ownership precondition failed closed."""


class LockCollisionError(SafetyGateError):
    """Another B649 heavy execution currently owns the machine-level lock."""


class LockIntegrityError(SafetyGateError):
    """The machine-level lock path no longer names the inode held by this FD."""


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Exact source paths and immutable artifact pins required before B649 work."""

    repository_root: Path
    module_files: Mapping[str, tuple[Path, str]]
    engine_path: Path
    manifest_path: Path
    overlay_path: Path
    engine_sha256: str
    manifest_sha256: str
    overlay_sha256: str
    r30_source_tag: str
    r30_task_head: str
    r30_result_relative: str
    r30_result_sha256: str
    census_durable_relative: str


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Observed exact execution authority and verified input-byte identities."""

    head: str
    tree: str
    engine_sha256: str
    manifest_sha256: str
    overlay_sha256: str
    r30_result_sha256: str


def _git_output(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SafetyGateError(f"cannot verify Git execution identity: {args[0]}") from error
    return result.stdout.strip()


def _read_authority(environ: Mapping[str, str]) -> tuple[str, str]:
    head = environ.get(AUTHORITY_HEAD_ENV, "").strip().lower()
    tree = environ.get(AUTHORITY_TREE_ENV, "").strip().lower()
    if not head or not tree:
        raise SafetyGateError(
            "explicit execution authority is required in "
            f"{AUTHORITY_HEAD_ENV} and {AUTHORITY_TREE_ENV}"
        )
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise SafetyGateError("execution authority HEAD must be one exact 40-character Git SHA")
    if re.fullmatch(r"[0-9a-f]{40}", tree) is None:
        raise SafetyGateError("execution authority TREE must be one exact 40-character Git SHA")
    return head, tree


def _resolve_existing(path: Path, label: str) -> Path:
    try:
        return path.resolve(strict=True)
    except OSError as error:
        raise SafetyGateError(f"{label} does not resolve to an existing source file") from error


def _digest(path: Path, label: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise SafetyGateError(f"cannot read pinned {label} bytes") from error


def _git_blob(root: Path, revision: str, relative_path: str, label: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"{revision}:{relative_path}"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SafetyGateError(f"cannot read {label} from its pinned Git source") from error
    return result.stdout


def _live_legacy_pids(process_lines: Sequence[str]) -> tuple[int, ...]:
    pids: list[int] = []
    for line in process_lines:
        pid_text, separator, command = line.strip().partition(" ")
        if not separator:
            continue
        try:
            pid = int(pid_text)
            argv = shlex.split(command)
        except ValueError:
            continue
        if pid == os.getpid() or not argv:
            continue
        if not Path(argv[0]).name.lower().startswith("python"):
            continue
        for index, token in enumerate(argv[:-2]):
            if (
                token == "-m"
                and argv[index + 1] == LEGACY_CENSUS_MODULE
                and argv[index + 2] == "run"
            ):
                pids.append(pid)
                break
            if (
                argv[index].endswith("b649_k20_fiber_near_top_s3_census.py")
                and argv[index + 1] == "run"
            ):
                pids.append(pid)
                break
    return tuple(sorted(set(pids)))


def _process_table() -> tuple[str, ...]:
    try:
        result = subprocess.run(
            ["ps", "-Ao", "pid=,command="],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SafetyGateError(
            "cannot inspect process table for a live census predecessor"
        ) from error
    return tuple(result.stdout.splitlines())


def preflight_source_identity(
    spec: SourceSpec,
    *,
    durable_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    process_lines: Sequence[str] | None = None,
) -> SourceIdentity:
    """Verify caller-provided Git authority, import paths, pinned bytes, and predecessor state."""

    environment = os.environ if environ is None else environ
    authority_head, authority_tree = _read_authority(environment)
    try:
        root = spec.repository_root.resolve(strict=True)
    except OSError as error:
        raise SafetyGateError("repository root does not resolve") from error
    git_root_text = _git_output(root, "rev-parse", "--show-toplevel")
    git_root = Path(git_root_text).resolve()
    if git_root != root:
        raise SafetyGateError("Git root differs from the execution worktree root")

    head = _git_output(root, "rev-parse", "--verify", "HEAD").lower()
    tree = _git_output(root, "rev-parse", "--verify", "HEAD^{tree}").lower()
    if head != authority_head or tree != authority_tree:
        raise SafetyGateError("Git HEAD/TREE differs from the exact external execution authority")
    if _git_output(root, "status", "--porcelain=v1", "--untracked-files=no"):
        raise SafetyGateError("tracked source is dirty; execution requires a clean source tree")

    for label, (actual_path, expected_relative) in spec.module_files.items():
        actual = _resolve_existing(actual_path, f"{label} module __file__")
        expected = _resolve_existing(root / expected_relative, f"expected {label} module")
        if actual != expected:
            raise SafetyGateError(f"{label} module __file__ points outside the authorized worktree")

    engine_path = _resolve_existing(spec.engine_path, "engine module __file__")
    manifest_path = _resolve_existing(spec.manifest_path, "frozen manifest")
    overlay_path = _resolve_existing(spec.overlay_path, "certificate overlay")
    if not engine_path.is_relative_to(root) or not manifest_path.is_relative_to(root):
        raise SafetyGateError("engine or manifest source escapes the authorized worktree")
    if not overlay_path.is_relative_to(root):
        raise SafetyGateError("overlay source escapes the authorized worktree")

    engine_digest = _digest(engine_path, "census engine")
    manifest_digest = _digest(manifest_path, "frozen manifest")
    overlay_digest = _digest(overlay_path, "certificate overlay")
    for label, actual, expected in (
        ("engine", engine_digest, spec.engine_sha256),
        ("manifest", manifest_digest, spec.manifest_sha256),
        ("overlay", overlay_digest, spec.overlay_sha256),
    ):
        if actual != expected:
            raise SafetyGateError(f"{label} SHA-256 differs from its exact source pin")

    tag_suffix = spec.r30_source_tag.removeprefix(R30_TAG_PREFIX)
    if (
        not spec.r30_source_tag.startswith(R30_TAG_PREFIX)
        or tag_suffix != spec.r30_task_head
        or re.fullmatch(r"[0-9a-f]{40}", spec.r30_task_head) is None
    ):
        raise SafetyGateError("R30 source tag does not identify the pinned R30 task head")
    r30_result = _git_blob(root, spec.r30_task_head, spec.r30_result_relative, "R30 result")
    r30_result_digest = hashlib.sha256(r30_result).hexdigest()
    if r30_result_digest != spec.r30_result_sha256:
        raise SafetyGateError("R30 tagged result SHA-256 differs from its exact source pin")

    if durable_root is not None:
        durable = durable_root.resolve()
        frozen_census_root = (root / spec.census_durable_relative).resolve()
        if (
            durable == frozen_census_root
            or durable.name == Path(spec.census_durable_relative).name
            or durable.is_relative_to(frozen_census_root)
        ):
            raise SafetyGateError("successor durable root aliases the frozen census RUN1 result")

    lines = _process_table() if process_lines is None else process_lines
    live_pids = _live_legacy_pids(lines)
    if live_pids:
        joined = ", ".join(str(pid) for pid in live_pids)
        raise SafetyGateError(f"legacy census RUN1 predecessor is still live (PID {joined})")

    return SourceIdentity(
        head=head,
        tree=tree,
        engine_sha256=engine_digest,
        manifest_sha256=manifest_digest,
        overlay_sha256=overlay_digest,
        r30_result_sha256=r30_result_digest,
    )


def _check_lock_directory(path: Path) -> None:
    try:
        information = path.lstat()
    except OSError as error:
        raise SafetyGateError("machine-level lock directory is unavailable") from error
    if (
        not stat.S_ISDIR(information.st_mode)
        or stat.S_ISLNK(information.st_mode)
        or information.st_uid != os.getuid()
        or stat.S_IMODE(information.st_mode) & 0o077
    ):
        raise SafetyGateError("machine-level lock directory is not private and owner-controlled")


class MachineHeavyClaim:
    """An open, nonblocking exclusive claim whose path remains bound to its FD inode."""

    def __init__(self, path: Path, descriptor: int) -> None:
        self.path = path
        self.descriptor = descriptor
        self._released = False

    def assert_path_matches_fd(self) -> None:
        if self._released:
            raise LockIntegrityError("machine-level heavy claim is already released")
        try:
            descriptor_info = os.fstat(self.descriptor)
            path_info = self.path.lstat()
        except OSError as error:
            raise LockIntegrityError("machine lock path or held FD disappeared") from error
        if (
            not stat.S_ISREG(descriptor_info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or descriptor_info.st_dev != path_info.st_dev
            or descriptor_info.st_ino != path_info.st_ino
        ):
            raise LockIntegrityError(
                "machine lock pathname no longer names the inode held by its FD"
            )

    def release(self) -> None:
        if self._released:
            return
        identity_error: LockIntegrityError | None = None
        try:
            self.assert_path_matches_fd()
        except LockIntegrityError as error:
            identity_error = error
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_UN)
        finally:
            os.close(self.descriptor)
            self._released = True
        if identity_error is not None:
            raise identity_error

    def __enter__(self) -> MachineHeavyClaim:
        self.assert_path_matches_fd()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            self.release()
        except LockIntegrityError:
            if exc_type is None:
                raise


def acquire_machine_heavy_claim(
    path: Path = DEFAULT_HEAVY_LOCK_PATH,
    *,
    head: str | None = None,
    tree: str | None = None,
) -> MachineHeavyClaim:
    """Acquire the stable user-global B649 lock using an atomic nonblocking flock."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as error:
        raise SafetyGateError("cannot create the stable machine-level lock directory") from error
    _check_lock_directory(path.parent)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise SafetyGateError("cannot open the stable machine-level heavy lock") from error

    try:
        information = os.fstat(descriptor)
        path_information = path.lstat()
        if (
            not stat.S_ISREG(information.st_mode)
            or stat.S_ISLNK(path_information.st_mode)
            or information.st_uid != os.getuid()
            or stat.S_IMODE(information.st_mode) & 0o077
            or (information.st_dev, information.st_ino)
            != (path_information.st_dev, path_information.st_ino)
        ):
            raise LockIntegrityError("machine lock path and FD identity is not private and stable")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise LockCollisionError(
                "another B649 heavy writer holds the machine-level lock"
            ) from error
        claim = MachineHeavyClaim(path, descriptor)
        claim.assert_path_matches_fd()
        metadata = json.dumps(
            {"pid": os.getpid(), "head": head, "tree": tree},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        os.ftruncate(descriptor, 0)
        os.write(descriptor, metadata)
        os.fsync(descriptor)
        claim.assert_path_matches_fd()
        return claim
    except BaseException:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
        raise


_ACTIVE_CLAIM: ContextVar[MachineHeavyClaim | None] = ContextVar(
    "b649_active_machine_heavy_claim", default=None
)


@contextmanager
def protected_heavy_execution(
    spec: SourceSpec,
    *,
    durable_root: Path | None = None,
    lock_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    process_lines: Sequence[str] | None = None,
) -> Generator[SourceIdentity]:
    """Gate inputs and hold machine ownership for the complete protected call chain."""

    identity = preflight_source_identity(
        spec,
        durable_root=durable_root,
        environ=environ,
        process_lines=process_lines,
    )
    active = _ACTIVE_CLAIM.get()
    if active is not None:
        active.assert_path_matches_fd()
        yield identity
        return

    claim = acquire_machine_heavy_claim(
        lock_path or DEFAULT_HEAVY_LOCK_PATH, head=identity.head, tree=identity.tree
    )
    try:
        claim.assert_path_matches_fd()
        identity = preflight_source_identity(
            spec,
            durable_root=durable_root,
            environ=environ,
            process_lines=process_lines,
        )
        claim.assert_path_matches_fd()
        token = _ACTIVE_CLAIM.set(claim)
        try:
            yield identity
        finally:
            _ACTIVE_CLAIM.reset(token)
    finally:
        claim.release()


def active_claim() -> MachineHeavyClaim | None:
    """Return the context's current claim so direct solver entrypoints can assert ownership."""

    return _ACTIVE_CLAIM.get()
