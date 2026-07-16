"""POSIX process, port, lock, state, and HTTP supervisor for local LottoLab."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from http.client import HTTPMessage
from pathlib import Path
from types import FrameType
from typing import IO, BinaryIO, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from lottolab.application.local_runtime import (
    BACKEND_PORT,
    FRONTEND_PORT,
    HEALTH_PATH,
    LOCAL_HOST,
    OPENAPI_PATH,
    STRATEGY_CATALOG_PATH,
    ConcurrentLocalRuntimeOperation,
    Listener,
    LocalRuntimeError,
    LocalRuntimePolicy,
    LocalRuntimeSafetyError,
    Ownership,
    ProcessIdentity,
    RuntimeState,
    RuntimeStatus,
    RuntimeStatusKind,
    ServiceRole,
    SmokeReport,
    validate_frontend_document,
    validate_git_object_id,
    validate_health_payload,
    validate_openapi_payload,
    validate_strategy_payloads,
)

_STARTUP_TIMEOUT_SECONDS = 20.0
_GRACEFUL_STOP_SECONDS = 5.0
_FORCED_STOP_SECONDS = 3.0
_HTTP_LIMIT_BYTES = 1_048_576
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_STATE_NAME = "state.json"
_LOCK_NAME = "controller.lock"


@dataclass(frozen=True)
class RuntimeDependencies:
    python: str
    uv: str
    node: str
    lsof: str


@dataclass(frozen=True)
class ProcessSnapshot:
    pgid: int
    start_marker: str
    command_line: str


@dataclass(frozen=True)
class ManagedLaunch:
    identity: ProcessIdentity
    process: subprocess.Popen[bytes] | None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str]
    effective_url: str = ""


SnapshotReader = Callable[[int], ProcessSnapshot | None]
RevisionReader = Callable[[Path], str]


class RuntimeStateStore:
    """Owner-only state with strict parsing and atomic replacement."""

    def __init__(self, policy: LocalRuntimePolicy) -> None:
        self._policy = policy
        self._directory_fd: int | None = None
        self._directory_identity: tuple[int, int] | None = None

    def ensure_runtime_dir(self) -> int:
        path = self._policy.runtime_dir
        if self._directory_fd is not None:
            return self._verified_directory_fd()

        descriptor, created = _open_or_create_runtime_directory(path)
        try:
            if created:
                os.fchmod(descriptor, 0o700)
            metadata = self._validate_directory_descriptor(descriptor)
            pathname_descriptor, _ = _open_or_create_runtime_directory(
                path, create=False
            )
            try:
                pathname_metadata = os.fstat(pathname_descriptor)
            finally:
                os.close(pathname_descriptor)
            if (pathname_metadata.st_dev, pathname_metadata.st_ino) != (
                metadata.st_dev,
                metadata.st_ino,
            ):
                raise LocalRuntimeSafetyError(
                    "runtime directory pathname does not match the verified directory inode"
                )
        except BaseException:
            os.close(descriptor)
            raise
        self._directory_fd = descriptor
        self._directory_identity = (metadata.st_dev, metadata.st_ino)
        return descriptor

    @property
    def directory_fd(self) -> int:
        return self.ensure_runtime_dir()

    def revalidate_directory(self) -> int:
        return self._verified_directory_fd()

    def _verified_directory_fd(self) -> int:
        descriptor = self._directory_fd
        identity = self._directory_identity
        if descriptor is None or identity is None:
            raise LocalRuntimeSafetyError("runtime directory anchor is unavailable")
        metadata = self._validate_directory_descriptor(descriptor)
        pathname_descriptor, _ = _open_or_create_runtime_directory(
            self._policy.runtime_dir, create=False
        )
        try:
            pathname_metadata = os.fstat(pathname_descriptor)
        finally:
            os.close(pathname_descriptor)
        if (
            (metadata.st_dev, metadata.st_ino) != identity
            or (pathname_metadata.st_dev, pathname_metadata.st_ino) != identity
        ):
            raise LocalRuntimeSafetyError(
                "runtime directory inode changed after verification"
            )
        return descriptor

    @staticmethod
    def _validate_directory_descriptor(descriptor: int) -> os.stat_result:
        try:
            metadata = os.fstat(descriptor)
        except OSError as exc:
            raise LocalRuntimeSafetyError(
                f"cannot inspect runtime directory descriptor: {exc}"
            ) from exc
        if not stat.S_ISDIR(metadata.st_mode):
            raise LocalRuntimeSafetyError("runtime directory is not a real directory")
        if metadata.st_uid != os.getuid():
            raise LocalRuntimeSafetyError("runtime directory has a foreign owner")
        if stat.S_IMODE(metadata.st_mode) != 0o700:
            raise LocalRuntimeSafetyError("runtime directory mode must be exactly 0700")
        return metadata

    def read(self) -> RuntimeState | None:
        directory_fd = self.directory_fd
        try:
            descriptor = _open_owned_regular_at(directory_fd, _STATE_NAME, os.O_RDONLY)
        except FileNotFoundError:
            return None
        try:
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                payload = cast(object, json.load(handle))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LocalRuntimeSafetyError(f"runtime state is corrupt: {exc}") from exc
        return RuntimeState.from_object(payload)

    def write(self, state: RuntimeState) -> None:
        directory_fd = self.directory_fd
        try:
            descriptor = _open_owned_regular_at(directory_fd, _STATE_NAME, os.O_RDONLY)
            os.close(descriptor)
        except FileNotFoundError:
            pass
        payload = (
            json.dumps(state.to_object(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")
        descriptor, temporary_name = _create_exclusive_file_at(directory_fd, ".state-")
        installed = False
        try:
            os.fchmod(descriptor, 0o600)
            _validate_owned_regular_descriptor(descriptor, temporary_name)
            remaining = memoryview(payload)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise LocalRuntimeSafetyError("atomic state write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            self._verified_directory_fd()
            os.replace(
                temporary_name,
                _STATE_NAME,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            installed = True
            os.fsync(directory_fd)
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            if not installed:
                with suppress(FileNotFoundError):
                    os.unlink(temporary_name, dir_fd=directory_fd)
            raise

    def delete(self) -> None:
        directory_fd = self.directory_fd
        try:
            descriptor = _open_owned_regular_at(directory_fd, _STATE_NAME, os.O_RDONLY)
        except FileNotFoundError:
            return
        try:
            if not _entry_matches_descriptor(directory_fd, _STATE_NAME, descriptor):
                raise LocalRuntimeSafetyError(
                    "runtime state changed before safe removal; preserving it"
                )
            os.unlink(_STATE_NAME, dir_fd=directory_fd)
            os.fsync(directory_fd)
        finally:
            os.close(descriptor)

    def open_fresh_log(self, role: ServiceRole) -> BinaryIO:
        directory_fd = self.directory_fd
        log_name = f"{role.value}.log"
        try:
            existing = _open_owned_regular_at(directory_fd, log_name, os.O_RDONLY)
        except FileNotFoundError:
            pass
        else:
            os.close(existing)

        descriptor, temporary_name = _create_exclusive_file_at(
            directory_fd, f".{role.value}-log-"
        )
        installed = False
        try:
            os.fchmod(descriptor, 0o600)
            _validate_owned_regular_descriptor(descriptor, temporary_name)
            self._verified_directory_fd()
            os.replace(
                temporary_name,
                log_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            installed = True
            os.fsync(directory_fd)
            return cast(BinaryIO, os.fdopen(descriptor, "wb", buffering=0))
        except BaseException:
            os.close(descriptor)
            if not installed:
                with suppress(FileNotFoundError):
                    os.unlink(temporary_name, dir_fd=directory_fd)
            raise

    def read_log_tail(self, role: ServiceRole) -> str:
        directory_fd = self.directory_fd
        descriptor = _open_owned_regular_at(
            directory_fd, f"{role.value}.log", os.O_RDONLY
        )
        try:
            size = os.fstat(descriptor).st_size
            os.lseek(descriptor, max(0, size - 4096), os.SEEK_SET)
            body = os.read(descriptor, 4096)
        finally:
            os.close(descriptor)
        return body.decode("utf-8", errors="replace").strip() or "<empty log>"


class RuntimeLock:
    """Non-blocking process lock used by every controller operation."""

    def __init__(self, policy: LocalRuntimePolicy, store: RuntimeStateStore) -> None:
        self._policy = policy
        self._store = store
        self._descriptor: int | None = None

    def __enter__(self) -> RuntimeLock:
        directory_fd = self._store.directory_fd
        created = False
        try:
            descriptor = os.open(
                _LOCK_NAME,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o600,
                dir_fd=directory_fd,
            )
            created = True
        except FileExistsError:
            try:
                descriptor = os.open(
                    _LOCK_NAME,
                    os.O_RDWR | _NOFOLLOW | _CLOEXEC,
                    dir_fd=directory_fd,
                )
            except OSError as exc:
                raise LocalRuntimeSafetyError(
                    f"cannot open controller lock safely: {exc}"
                ) from exc
        except OSError as exc:
            raise LocalRuntimeSafetyError(f"cannot open controller lock safely: {exc}") from exc
        try:
            if created:
                os.fchmod(descriptor, 0o600)
            _validate_owned_regular_descriptor(descriptor, _LOCK_NAME)
            self._store.revalidate_directory()
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}:
                    raise ConcurrentLocalRuntimeOperation(
                        "another local runtime operation holds the controller lock"
                    ) from exc
                raise LocalRuntimeSafetyError(f"cannot acquire controller lock: {exc}") from exc
        except BaseException:
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc_value, traceback
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


class ProcessInspector:
    """Capture and re-check process-group, start-time, and full-command identity."""

    def __init__(self, snapshot_reader: SnapshotReader | None = None) -> None:
        self._snapshot_reader = snapshot_reader or _read_process_snapshot

    def capture(
        self,
        *,
        pid: int,
        role: ServiceRole,
        log_path: Path,
    ) -> ProcessIdentity:
        deadline = time.monotonic() + 2.0
        not_before = time.monotonic() + 0.25
        snapshot: ProcessSnapshot | None = None
        previous: ProcessSnapshot | None = None
        stable_reads = 0
        while time.monotonic() < deadline:
            snapshot = self._snapshot_reader(pid)
            if snapshot is None:
                previous = None
                stable_reads = 0
            elif snapshot == previous:
                stable_reads += 1
            else:
                previous = snapshot
                stable_reads = 1
            if snapshot is not None and stable_reads >= 3 and time.monotonic() >= not_before:
                break
            time.sleep(0.05)
        if snapshot is None or stable_reads < 3:
            raise LocalRuntimeError(f"{role.value} launcher identity did not stabilize")
        if snapshot.pgid != pid:
            raise LocalRuntimeSafetyError(f"{role.value} launcher is not a new process group")
        return ProcessIdentity(
            role=role,
            pid=pid,
            pgid=snapshot.pgid,
            port=role.port,
            start_marker=snapshot.start_marker,
            command_line=snapshot.command_line,
            log_path=str(log_path),
        )

    def ownership(self, identity: ProcessIdentity) -> Ownership:
        snapshot = self._snapshot_reader(identity.pid)
        if snapshot is None:
            return Ownership.DEAD
        if (
            snapshot.pgid == identity.pgid
            and snapshot.start_marker == identity.start_marker
            and snapshot.command_line == identity.command_line
        ):
            return Ownership.OWNED
        return Ownership.MISMATCH


class LocalRuntimeSupervisor:
    """Fail-closed lifecycle supervisor; it never installs dependencies."""

    def __init__(
        self,
        policy: LocalRuntimePolicy,
        *,
        state_store: RuntimeStateStore | None = None,
        inspector: ProcessInspector | None = None,
        revision_reader: RevisionReader | None = None,
    ) -> None:
        self.policy = policy
        self.store = state_store or RuntimeStateStore(policy)
        self.inspector = inspector or ProcessInspector()
        self._revision_reader = revision_reader or _read_git_revision

    def start(self) -> RuntimeStatus:
        with RuntimeLock(self.policy, self.store):
            dependencies = self._assert_dependencies()
            source_commit = self._current_source_commit()
            self._prepare_start()
            self._assert_all_ports_free()
            token = secrets.token_hex(16)
            started: list[ManagedLaunch] = []
            state: RuntimeState | None = None
            try:
                backend = self._spawn_service(
                    ServiceRole.BACKEND, token, source_commit, dependencies
                )
                started.append(backend)
                state = self.policy.initial_state(token, source_commit, backend.identity)
                self.store.write(state)
                self._wait_for_backend(state, backend.identity)

                frontend = self._spawn_service(
                    ServiceRole.FRONTEND, token, source_commit, dependencies
                )
                started.append(frontend)
                state = state.with_service(frontend.identity)
                self.store.write(state)
                self._wait_for_frontend(state, frontend.identity)
                current_revision = self._require_matching_revision(state)
                final_status = self._status_for_state(
                    state, current_revision=current_revision
                )
                if final_status.kind is not RuntimeStatusKind.RUNNING:
                    raise LocalRuntimeError(
                        "startup final status must be running; "
                        f"observed {final_status.kind.value}: {final_status.detail}"
                    )
                return final_status
            except BaseException as original:
                try:
                    self._cleanup_partial_start(started, state)
                except Exception as cleanup_error:
                    raise LocalRuntimeSafetyError(
                        f"startup failed and safe partial cleanup failed: {cleanup_error}"
                    ) from cleanup_error
                raise original

    def status(self) -> RuntimeStatus:
        with RuntimeLock(self.policy, self.store):
            state = self.store.read()
            if state is None:
                return self._status_without_state()
            self._require_same_repository(state)
            current_revision = self._require_matching_revision(state)
            return self._status_for_state(state, current_revision=current_revision)

    def smoke(self) -> SmokeReport:
        with RuntimeLock(self.policy, self.store):
            state = self.store.read()
            if state is None:
                raise LocalRuntimeError("local runtime is stopped")
            self._require_same_repository(state)
            self._require_matching_revision(state)
            backend = self._require_owned_service(state, ServiceRole.BACKEND)
            frontend = self._require_owned_service(state, ServiceRole.FRONTEND)
            self._assert_owned_listener(backend)
            self._assert_owned_listener(frontend)

            backend_url = f"http://{LOCAL_HOST}:{BACKEND_PORT}"
            frontend_url = f"http://{LOCAL_HOST}:{FRONTEND_PORT}"
            health = self._required_http_get(f"{backend_url}{HEALTH_PATH}")
            self._require_backend_token(health, state.ownership_token)
            validate_health_payload(_json_payload(health, "health"))

            frontend_root = self._required_http_get(f"{frontend_url}/")
            validate_frontend_document(frontend_root.body)

            direct = self._required_http_get(f"{backend_url}{STRATEGY_CATALOG_PATH}")
            self._require_backend_token(direct, state.ownership_token)
            proxied = self._required_http_get(f"{frontend_url}{STRATEGY_CATALOG_PATH}")
            strategy_ids = validate_strategy_payloads(
                _json_payload(direct, "direct Strategy Catalog"),
                _json_payload(proxied, "proxied Strategy Catalog"),
            )

            openapi = self._required_http_get(f"{backend_url}{OPENAPI_PATH}")
            self._require_backend_token(openapi, state.ownership_token)
            validate_openapi_payload(_json_payload(openapi, "OpenAPI"))
            return SmokeReport(
                strategy_ids=strategy_ids,
                backend_url=backend_url,
                frontend_url=frontend_url,
            )

    def stop(self) -> RuntimeStatus:
        with RuntimeLock(self.policy, self.store):
            state = self.store.read()
            if state is None:
                status = self._status_without_state()
                if status.kind is RuntimeStatusKind.FOREIGN:
                    raise LocalRuntimeSafetyError(
                        "foreign listener present; no controller-owned state to stop"
                    )
                return status
            self._require_same_repository(state)

            ownership_by_role: dict[ServiceRole, Ownership] = {}
            for role in (ServiceRole.FRONTEND, ServiceRole.BACKEND):
                identity = state.service(role)
                listeners = self._listeners(role.port)
                if identity is None:
                    if listeners:
                        raise LocalRuntimeSafetyError(
                            f"foreign listener occupies {LOCAL_HOST}:{role.port}"
                        )
                    continue
                ownership = self.inspector.ownership(identity)
                ownership_by_role[role] = ownership
                if ownership is Ownership.MISMATCH:
                    raise LocalRuntimeSafetyError(
                        f"{role.value} PID identity mismatch; refusing termination"
                    )
                if listeners:
                    if ownership is not Ownership.OWNED:
                        raise LocalRuntimeSafetyError(
                            f"foreign listener replaced dead {role.value} process"
                        )
                    self._assert_owned_listener(identity, listeners=listeners)

            for role in (ServiceRole.FRONTEND, ServiceRole.BACKEND):
                identity = state.service(role)
                if identity is not None and ownership_by_role.get(role) is Ownership.OWNED:
                    self._terminate_identity(identity, state=state)

            self._assert_all_ports_free()
            self.store.delete()
            return RuntimeStatus(
                kind=RuntimeStatusKind.STOPPED,
                ownership_proven=False,
                backend="stopped",
                frontend="stopped",
                detail="controller-owned services stopped; ports 8000 and 5173 are free",
            )

    def _assert_dependencies(self) -> RuntimeDependencies:
        root = self.policy.repository_root
        git_metadata = root / ".git"
        virtual_environment = root / ".venv"
        node_modules = root / "frontend" / "node_modules"
        python = virtual_environment / "bin" / "python"
        vite = node_modules / "vite" / "bin" / "vite.js"
        vite_config = root / "frontend" / "vite.config.ts"

        if not git_metadata.exists() or git_metadata.is_symlink():
            raise LocalRuntimeSafetyError("repository Git metadata is absent or unsafe")
        if virtual_environment.is_symlink() or not virtual_environment.is_dir():
            raise LocalRuntimeError(
                "task-local .venv is absent or is a symlink; run locked bootstrap"
            )
        if node_modules.is_symlink() or not node_modules.is_dir():
            raise LocalRuntimeError(
                "task-local frontend/node_modules is absent or is a symlink; run locked bootstrap"
            )
        if not python.is_file() or not vite.is_file() or not vite_config.is_file():
            raise LocalRuntimeError("locked Python or frontend dependencies are incomplete")

        uv = shutil.which("uv")
        node = shutil.which("node")
        lsof = shutil.which("lsof")
        if uv is None or node is None or lsof is None:
            raise LocalRuntimeError("required local executables (uv, node, lsof) are unavailable")
        return RuntimeDependencies(python=str(python), uv=uv, node=node, lsof=lsof)

    def _prepare_start(self) -> None:
        state = self.store.read()
        if state is None:
            return
        self._require_same_repository(state)
        ownerships = [self.inspector.ownership(service) for service in state.services]
        if any(ownership is Ownership.MISMATCH for ownership in ownerships):
            raise LocalRuntimeSafetyError("stale state contains a reused or foreign PID")
        if any(ownership is Ownership.OWNED for ownership in ownerships):
            raise LocalRuntimeError("controller-owned local runtime is already active or partial")
        self._assert_all_ports_free()
        self.store.delete()

    def _spawn_service(
        self,
        role: ServiceRole,
        token: str,
        source_commit: str,
        dependencies: RuntimeDependencies,
    ) -> ManagedLaunch:
        child_command = (
            self.policy.backend_command(dependencies.uv, token)
            if role is ServiceRole.BACKEND
            else self.policy.frontend_command(dependencies.node)
        )
        launcher_command = self.policy.launcher_command(
            python_executable=dependencies.python,
            role=role,
            token=token,
            source_commit=source_commit,
            child_command=child_command,
        )
        environment = os.environ.copy()
        environment["UV_NO_SYNC"] = "1"
        environment["NO_COLOR"] = "1"
        log_path = self.policy.log_path(role)
        with self.store.open_fresh_log(role) as log:
            process = subprocess.Popen(
                launcher_command,
                cwd=self.policy.repository_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        try:
            identity = self.inspector.capture(pid=process.pid, role=role, log_path=log_path)
        except BaseException as original:
            try:
                _terminate_uncaptured_process_group(process)
            except LocalRuntimeSafetyError as cleanup_error:
                raise LocalRuntimeSafetyError(
                    "launcher identity capture failed and startup rollback refused "
                    f"unverified escalation: {cleanup_error}"
                ) from cleanup_error
            raise original
        return ManagedLaunch(identity=identity, process=process)

    def _wait_for_backend(self, state: RuntimeState, identity: ProcessIdentity) -> None:
        backend_url = f"http://{LOCAL_HOST}:{BACKEND_PORT}"

        def ready() -> bool:
            response = self._optional_http_get(f"{backend_url}{HEALTH_PATH}")
            if response is None:
                return False
            if response.status != 200:
                return False
            self._require_backend_token(response, state.ownership_token)
            validate_health_payload(_json_payload(response, "health"))
            return self._owned_listener_ready(identity)

        self._wait_for_service(identity, ready)

    def _wait_for_frontend(self, state: RuntimeState, identity: ProcessIdentity) -> None:
        backend_url = f"http://{LOCAL_HOST}:{BACKEND_PORT}"
        frontend_url = f"http://{LOCAL_HOST}:{FRONTEND_PORT}"

        def ready() -> bool:
            root = self._optional_http_get(f"{frontend_url}/")
            direct = self._optional_http_get(f"{backend_url}{STRATEGY_CATALOG_PATH}")
            proxied = self._optional_http_get(f"{frontend_url}{STRATEGY_CATALOG_PATH}")
            if root is None or direct is None or proxied is None:
                return False
            if root.status != 200 or direct.status != 200 or proxied.status != 200:
                return False
            validate_frontend_document(root.body)
            self._require_backend_token(direct, state.ownership_token)
            validate_strategy_payloads(
                _json_payload(direct, "direct Strategy Catalog"),
                _json_payload(proxied, "proxied Strategy Catalog"),
            )
            return self._owned_listener_ready(identity)

        self._wait_for_service(identity, ready)

    def _wait_for_service(self, identity: ProcessIdentity, ready: Callable[[], bool]) -> None:
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
        last_error: LocalRuntimeError | None = None
        while time.monotonic() < deadline:
            ownership = self.inspector.ownership(identity)
            if ownership is Ownership.DEAD:
                raise LocalRuntimeError(
                    f"{identity.role.value} exited during startup: {self._log_tail(identity)}"
                )
            if ownership is Ownership.MISMATCH:
                raise LocalRuntimeSafetyError(
                    f"{identity.role.value} identity changed during startup"
                )
            try:
                if ready():
                    return
            except LocalRuntimeSafetyError:
                raise
            except LocalRuntimeError as exc:
                last_error = exc
            time.sleep(0.1)
        detail = f": {last_error}" if last_error is not None else ""
        raise LocalRuntimeError(
            f"{identity.role.value} did not become ready within the timeout{detail}; "
            f"log={self._log_tail(identity)}"
        )

    def _cleanup_partial_start(
        self, started: Sequence[ManagedLaunch], state: RuntimeState | None
    ) -> None:
        cleanup_errors: list[str] = []
        for managed in reversed(started):
            ownership = self.inspector.ownership(managed.identity)
            if ownership is Ownership.MISMATCH:
                cleanup_errors.append(
                    f"cannot clean {managed.identity.role.value}: PID identity mismatch"
                )
                continue
            if ownership is Ownership.DEAD:
                continue
            if state is None:
                cleanup_errors.append(
                    f"cannot clean {managed.identity.role.value}: runtime state is unavailable"
                )
                continue
            try:
                self._terminate_identity(
                    managed.identity, state=state, process=managed.process
                )
            except LocalRuntimeSafetyError as exc:
                cleanup_errors.append(str(exc))

        try:
            self._assert_all_ports_free()
        except LocalRuntimeSafetyError as exc:
            cleanup_errors.append(str(exc))
        if cleanup_errors:
            raise LocalRuntimeSafetyError("; ".join(cleanup_errors))
        if state is not None:
            self.store.delete()

    def _terminate_identity(
        self,
        identity: ProcessIdentity,
        *,
        state: RuntimeState,
        process: subprocess.Popen[bytes] | None = None,
    ) -> None:
        ownership = self._revalidate_signal_ownership(
            state, identity, escalation="SIGTERM"
        )
        if ownership is Ownership.DEAD:
            return
        if ownership is Ownership.MISMATCH:
            raise LocalRuntimeSafetyError(
                f"refusing to signal foreign {identity.role.value} process"
            )
        try:
            os.killpg(identity.pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        if not self._wait_for_group_exit(identity.pgid, _GRACEFUL_STOP_SECONDS, process):
            ownership = self._revalidate_signal_ownership(
                state, identity, escalation="SIGKILL"
            )
            if ownership is Ownership.DEAD:
                self._reconcile_dead_before_escalation(identity)
                return
            if ownership is Ownership.MISMATCH:
                raise LocalRuntimeSafetyError(
                    f"{identity.role.value} ownership became ambiguous before SIGKILL; "
                    "state was preserved"
                )
            try:
                os.killpg(identity.pgid, signal.SIGKILL)
            except ProcessLookupError:
                return
            if not self._wait_for_group_exit(identity.pgid, _FORCED_STOP_SECONDS, process):
                raise LocalRuntimeSafetyError(
                    f"owned {identity.role.value} process group did not terminate"
                )

    def _revalidate_signal_ownership(
        self,
        state: RuntimeState,
        identity: ProcessIdentity,
        *,
        escalation: str,
    ) -> Ownership:
        self._require_same_repository(state)
        if state.service(identity.role) != identity:
            raise LocalRuntimeSafetyError(
                f"{identity.role.value} {escalation} evidence is not bound to runtime state"
            )
        ownership = self.inspector.ownership(identity)
        if ownership is not Ownership.OWNED:
            return ownership
        try:
            current_pgid = os.getpgid(identity.pid)
        except ProcessLookupError:
            return Ownership.DEAD
        except OSError as exc:
            raise LocalRuntimeSafetyError(
                f"cannot revalidate {identity.role.value} process group before {escalation}: {exc}"
            ) from exc
        if current_pgid != identity.pgid or current_pgid != identity.pid:
            return Ownership.MISMATCH
        if escalation == "SIGKILL":
            expected_address = f"{LOCAL_HOST}:{identity.port}"
            for listener in self._listeners(identity.port):
                if listener.address != expected_address:
                    return Ownership.MISMATCH
                try:
                    listener_pgid = os.getpgid(listener.pid)
                except ProcessLookupError:
                    return Ownership.MISMATCH
                except OSError as exc:
                    raise LocalRuntimeSafetyError(
                        f"cannot revalidate listener process group before {escalation}: {exc}"
                    ) from exc
                if listener_pgid != identity.pgid:
                    return Ownership.MISMATCH
        return Ownership.OWNED

    def _reconcile_dead_before_escalation(self, identity: ProcessIdentity) -> None:
        listeners = self._listeners(identity.port)
        if listeners:
            raise LocalRuntimeSafetyError(
                f"{identity.role.value} leader died before escalation while a listener remains; "
                "SIGKILL was not sent and state was preserved"
            )
        if _process_group_alive(identity.pgid):
            raise LocalRuntimeSafetyError(
                f"{identity.role.value} leader died before escalation and PGID may be reused; "
                "SIGKILL was not sent and state was preserved"
            )

    def _wait_for_group_exit(
        self,
        pgid: int,
        timeout: float,
        process: subprocess.Popen[bytes] | None,
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process is not None:
                process.poll()
            if not _process_group_alive(pgid):
                if process is not None:
                    with suppress(subprocess.TimeoutExpired):
                        process.wait(timeout=0.2)
                return True
            time.sleep(0.05)
        return not _process_group_alive(pgid)

    def _status_without_state(self) -> RuntimeStatus:
        backend = self._listeners(BACKEND_PORT)
        frontend = self._listeners(FRONTEND_PORT)
        if backend or frontend:
            return RuntimeStatus(
                kind=RuntimeStatusKind.FOREIGN,
                ownership_proven=False,
                backend="foreign-listener" if backend else "stopped",
                frontend="foreign-listener" if frontend else "stopped",
                detail="listener exists without controller-owned state",
            )
        return RuntimeStatus(
            kind=RuntimeStatusKind.STOPPED,
            ownership_proven=False,
            backend="stopped",
            frontend="stopped",
            detail="no controller state and both ports are free",
        )

    def _status_for_state(
        self, state: RuntimeState, *, current_revision: str
    ) -> RuntimeStatus:
        observations: dict[ServiceRole, str] = {}
        has_foreign = False
        for role in (ServiceRole.BACKEND, ServiceRole.FRONTEND):
            identity = state.service(role)
            listeners = self._listeners(role.port)
            if identity is None:
                observations[role] = "foreign-listener" if listeners else "missing"
                has_foreign = has_foreign or bool(listeners)
                continue
            ownership = self.inspector.ownership(identity)
            if ownership is Ownership.MISMATCH:
                observations[role] = "pid-identity-mismatch"
                has_foreign = True
            elif ownership is Ownership.DEAD:
                observations[role] = "foreign-listener" if listeners else "dead"
                has_foreign = has_foreign or bool(listeners)
            elif not listeners:
                observations[role] = "owned-no-listener"
            else:
                try:
                    self._assert_owned_listener(identity, listeners=listeners)
                except LocalRuntimeSafetyError:
                    observations[role] = "foreign-or-nonlocal-listener"
                    has_foreign = True
                else:
                    observations[role] = "owned-local-listener"

        values = set(observations.values())
        if has_foreign:
            kind = RuntimeStatusKind.FOREIGN
        elif values == {"owned-local-listener"}:
            kind = RuntimeStatusKind.RUNNING
        elif values <= {"dead", "missing"}:
            kind = RuntimeStatusKind.STALE
        else:
            kind = RuntimeStatusKind.PARTIAL
        return RuntimeStatus(
            kind=kind,
            ownership_proven=kind is RuntimeStatusKind.RUNNING,
            backend=observations[ServiceRole.BACKEND],
            frontend=observations[ServiceRole.FRONTEND],
            detail=(
                f"runtime state is {kind.value}; repository, source revision, and PID "
                f"identity were checked; running_revision={state.source_commit} "
                f"current_revision={current_revision} revision_match=yes"
            ),
        )

    def _require_owned_service(
        self, state: RuntimeState, role: ServiceRole
    ) -> ProcessIdentity:
        identity = state.service(role)
        if identity is None:
            raise LocalRuntimeSafetyError(f"runtime state has no {role.value} identity")
        ownership = self.inspector.ownership(identity)
        if ownership is not Ownership.OWNED:
            raise LocalRuntimeSafetyError(
                f"{role.value} ownership is {ownership.value}; refusing smoke request"
            )
        return identity

    def _require_same_repository(self, state: RuntimeState) -> None:
        if state.repository_root != str(self.policy.repository_root):
            raise LocalRuntimeSafetyError(
                "runtime state belongs to a different repository or worktree"
            )

    def _require_matching_revision(self, state: RuntimeState) -> str:
        current_revision = self._current_source_commit()
        if state.source_commit != current_revision:
            raise LocalRuntimeSafetyError(
                "runtime revision mismatch: "
                f"running_revision={state.source_commit} "
                f"current_revision={current_revision} revision_match=no"
            )
        return current_revision

    def _current_source_commit(self) -> str:
        revision = self._revision_reader(self.policy.repository_root)
        validate_git_object_id(revision)
        return revision

    def _assert_all_ports_free(self) -> None:
        for port in (BACKEND_PORT, FRONTEND_PORT):
            listeners = self._listeners(port)
            if listeners:
                summary = ", ".join(
                    f"pid={listener.pid} address={listener.address}" for listener in listeners
                )
                raise LocalRuntimeSafetyError(f"foreign listener occupies port {port}: {summary}")
            if not _port_bindable(port):
                raise LocalRuntimeSafetyError(f"port {port} cannot be bound exclusively")

    def _listeners(self, port: int) -> tuple[Listener, ...]:
        lsof = shutil.which("lsof")
        if lsof is None:
            raise LocalRuntimeError("lsof is required for fail-closed listener ownership checks")
        completed = subprocess.run(
            [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpn"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode not in {0, 1}:
            raise LocalRuntimeSafetyError(
                f"lsof listener inspection failed for port {port}: {completed.stderr.strip()}"
            )
        current_pid: int | None = None
        listeners: list[Listener] = []
        for line in completed.stdout.splitlines():
            if line.startswith("p") and line[1:].isdigit():
                current_pid = int(line[1:])
            elif line.startswith("n") and current_pid is not None:
                listeners.append(Listener(pid=current_pid, address=line[1:]))
        return tuple(listeners)

    def _owned_listener_ready(self, identity: ProcessIdentity) -> bool:
        listeners = self._listeners(identity.port)
        if not listeners:
            return False
        self._assert_owned_listener(identity, listeners=listeners)
        return True

    def _assert_owned_listener(
        self,
        identity: ProcessIdentity,
        *,
        listeners: Sequence[Listener] | None = None,
    ) -> None:
        selected = tuple(listeners) if listeners is not None else self._listeners(identity.port)
        if not selected:
            raise LocalRuntimeSafetyError(f"{identity.role.value} has no listener")
        expected_address = f"{LOCAL_HOST}:{identity.port}"
        for listener in selected:
            if listener.address != expected_address:
                raise LocalRuntimeSafetyError(
                    f"{identity.role.value} listener is not localhost-only: {listener.address}"
                )
            try:
                listener_pgid = os.getpgid(listener.pid)
            except ProcessLookupError as exc:
                raise LocalRuntimeSafetyError(
                    "listener disappeared during ownership check"
                ) from exc
            if listener_pgid != identity.pgid:
                raise LocalRuntimeSafetyError(
                    f"{identity.role.value} port is owned by a foreign process group"
                )

    def _optional_http_get(self, url: str) -> HttpResponse | None:
        try:
            return _http_get(url)
        except LocalRuntimeSafetyError:
            raise
        except LocalRuntimeError:
            return None

    def _required_http_get(self, url: str) -> HttpResponse:
        response = _http_get(url)
        if response.status != 200:
            raise LocalRuntimeError(f"HTTP smoke request failed: {url} returned {response.status}")
        return response

    def _require_backend_token(self, response: HttpResponse, token: str) -> None:
        if response.headers.get("x-lottolab-owner") != token:
            raise LocalRuntimeSafetyError(
                "backend HTTP response lacks the controller ownership token"
            )

    def _log_tail(self, identity: ProcessIdentity) -> str:
        if Path(identity.log_path) != self.policy.log_path(identity.role):
            return "<log path does not match the anchored controller log>"
        try:
            return self.store.read_log_tail(identity.role)
        except (OSError, LocalRuntimeSafetyError):
            return "<log unavailable>"


def _open_or_create_runtime_directory(
    path: Path, *, create: bool = True
) -> tuple[int, bool]:
    if not path.is_absolute() or len(path.parts) < 2:
        raise LocalRuntimeSafetyError("runtime directory must be a non-root absolute path")
    try:
        parent_fd = os.open(
            path.anchor, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
        )
    except OSError as exc:
        raise LocalRuntimeSafetyError(f"cannot open runtime filesystem root: {exc}") from exc
    try:
        for component in path.parts[1:-1]:
            try:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
                    dir_fd=parent_fd,
                )
            except OSError as exc:
                raise LocalRuntimeSafetyError(
                    f"cannot anchor runtime parent component {component}: {exc}"
                ) from exc
            os.close(parent_fd)
            parent_fd = next_fd

        final_name = path.parts[-1]
        created = False
        if create:
            try:
                os.mkdir(final_name, 0o700, dir_fd=parent_fd)
                created = True
            except FileExistsError:
                pass
            except OSError as exc:
                raise LocalRuntimeSafetyError(
                    f"cannot create runtime directory: {exc}"
                ) from exc
        try:
            descriptor = os.open(
                final_name,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise LocalRuntimeSafetyError(
                f"cannot open runtime directory safely: {exc}"
            ) from exc
        return descriptor, created
    finally:
        os.close(parent_fd)


def _open_owned_regular_at(directory_fd: int, name: str, flags: int) -> int:
    _validate_relative_controller_name(name)
    try:
        descriptor = os.open(
            name,
            flags | _NOFOLLOW | _CLOEXEC,
            dir_fd=directory_fd,
        )
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise LocalRuntimeSafetyError(
            f"cannot open controller file safely ({name}): {exc}"
        ) from exc
    try:
        _validate_owned_regular_descriptor(descriptor, name)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _validate_owned_regular_descriptor(descriptor: int, name: str) -> None:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalRuntimeSafetyError(f"controller path is not a regular file: {name}")
    if metadata.st_uid != os.getuid():
        raise LocalRuntimeSafetyError(f"controller path has a foreign owner: {name}")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise LocalRuntimeSafetyError(f"controller path mode must be exactly 0600: {name}")
    if metadata.st_nlink != 1:
        raise LocalRuntimeSafetyError(f"controller path must have one link: {name}")


def _create_exclusive_file_at(directory_fd: int, prefix: str) -> tuple[int, str]:
    for _ in range(128):
        name = f"{prefix}{secrets.token_hex(12)}"
        _validate_relative_controller_name(name)
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o600,
                dir_fd=directory_fd,
            )
        except FileExistsError:
            continue
        except OSError as exc:
            raise LocalRuntimeSafetyError(
                f"cannot create fresh controller file safely ({name}): {exc}"
            ) from exc
        return descriptor, name
    raise LocalRuntimeSafetyError("cannot allocate an exclusive controller filename")


def _entry_matches_descriptor(directory_fd: int, name: str, descriptor: int) -> bool:
    try:
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    opened = os.fstat(descriptor)
    return (entry.st_dev, entry.st_ino) == (opened.st_dev, opened.st_ino)


def _validate_relative_controller_name(name: str) -> None:
    path = Path(name)
    if not name or path.name != name or name in {".", ".."}:
        raise LocalRuntimeSafetyError("controller filename must be one safe relative name")


def _read_process_snapshot(pid: int) -> ProcessSnapshot | None:
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return None
    except OSError as exc:
        raise LocalRuntimeSafetyError(f"cannot inspect PID {pid}: {exc}") from exc
    completed = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    line = completed.stdout.strip().splitlines()[0]
    if len(line) <= 24:
        raise LocalRuntimeSafetyError(f"process identity output for PID {pid} is incomplete")
    return ProcessSnapshot(
        pgid=pgid,
        start_marker=line[:24].strip(),
        command_line=line[24:].strip(),
    )


def _port_bindable(port: int) -> bool:
    candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        candidate.bind((LOCAL_HOST, port))
    except OSError:
        return False
    finally:
        candidate.close()
    return True


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


def _http_get(url: str) -> HttpResponse:
    _validate_loopback_http_url(url)
    opener = build_opener(ProxyHandler({}), _RejectRedirectHandler())
    request = Request(url, headers={"Accept": "application/json, text/html"}, method="GET")
    try:
        with opener.open(request, timeout=2.0) as response:
            status_code = response.getcode()
            effective_url = response.url
            body = response.read(_HTTP_LIMIT_BYTES + 1)
            headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as exc:
        status_code = exc.code
        effective_url = exc.url
        body = exc.read(_HTTP_LIMIT_BYTES + 1)
        headers = {key.lower(): value for key, value in exc.headers.items()}
    except (URLError, TimeoutError, OSError) as exc:
        raise LocalRuntimeError(f"HTTP request failed for {url}: {exc}") from exc
    _validate_loopback_http_url(effective_url)
    if effective_url != url:
        raise LocalRuntimeSafetyError(
            f"HTTP effective URL changed from {url} to {effective_url}"
        )
    if 300 <= int(status_code) < 400:
        raise LocalRuntimeSafetyError(
            f"HTTP redirect response is forbidden: {url} returned {status_code}"
        )
    if len(body) > _HTTP_LIMIT_BYTES:
        raise LocalRuntimeSafetyError(f"HTTP response exceeded size limit: {url}")
    return HttpResponse(
        status=int(status_code),
        body=body,
        headers=headers,
        effective_url=effective_url,
    )


def _validate_loopback_http_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise LocalRuntimeSafetyError(f"HTTP URL is invalid: {url}") from exc
    allowed_paths = {
        BACKEND_PORT: {HEALTH_PATH, STRATEGY_CATALOG_PATH, OPENAPI_PATH},
        FRONTEND_PORT: {"/", STRATEGY_CATALOG_PATH},
    }
    exact_url = f"http://{LOCAL_HOST}:{port}{parsed.path}"
    if (
        parsed.scheme != "http"
        or parsed.hostname != LOCAL_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in allowed_paths
        or parsed.netloc != f"{LOCAL_HOST}:{port}"
        or parsed.path not in allowed_paths[port]
        or parsed.query
        or parsed.fragment
        or url != exact_url
    ):
        raise LocalRuntimeSafetyError(
            f"HTTP request is not an exact fixed loopback endpoint: {url}"
        )


def _json_payload(response: HttpResponse, label: str) -> object:
    try:
        return cast(object, json.loads(response.body.decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LocalRuntimeSafetyError(f"{label} response is not valid JSON") from exc


def _process_group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise LocalRuntimeSafetyError(f"cannot verify process group {pgid}: {exc}") from exc
    return True


def _terminate_uncaptured_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        current_pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return
    if current_pgid != process.pid:
        raise LocalRuntimeSafetyError(
            "uncaptured launcher is not its expected process-group leader; no signal sent"
        )
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired as exc:
        raise LocalRuntimeSafetyError(
            "uncaptured launcher did not exit after SIGTERM; SIGKILL was not sent"
        ) from exc


def _read_git_revision(repository: Path) -> str:
    git = shutil.which("git")
    if git is None:
        raise LocalRuntimeError("git is required to bind runtime state to source revision")
    completed = subprocess.run(
        [git, "-C", str(repository), "rev-parse", "--verify", "HEAD^{commit}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        raise LocalRuntimeSafetyError(
            f"cannot resolve current Git commit: {completed.stderr.strip()}"
        )
    revision = completed.stdout.strip()
    validate_git_object_id(revision)
    return revision


def _validate_launcher_child(role: ServiceRole, child: Sequence[str]) -> None:
    if role is ServiceRole.BACKEND:
        if len(child) < 8 or Path(child[0]).name != "uv" or tuple(child[1:3]) != (
            "run",
            "--no-sync",
        ):
            raise LocalRuntimeSafetyError("backend launcher requires exactly uv run --no-sync")
        if "uvicorn" not in child or _option_value(child, "--host") != LOCAL_HOST:
            raise LocalRuntimeSafetyError("backend launcher host or executable is invalid")
        if _option_value(child, "--port") != str(BACKEND_PORT):
            raise LocalRuntimeSafetyError("backend launcher port is invalid")
    else:
        if len(child) < 7 or not child[1].endswith("/node_modules/vite/bin/vite.js"):
            raise LocalRuntimeSafetyError("frontend launcher requires the locked Vite executable")
        if _option_value(child, "--host") != LOCAL_HOST:
            raise LocalRuntimeSafetyError("frontend launcher host is invalid")
        if _option_value(child, "--port") != str(FRONTEND_PORT) or "--strictPort" not in child:
            raise LocalRuntimeSafetyError("frontend launcher requires strict port 5173")

    lowered = [part.lower() for part in child]
    if "install" in lowered or "update" in lowered or "ci" in lowered or "sync" in lowered:
        raise LocalRuntimeSafetyError("runtime launcher cannot install or synchronize dependencies")
    if any(Path(part).name in {"pip", "pip3", "npm", "npx"} for part in child):
        raise LocalRuntimeSafetyError("runtime launcher cannot invoke a package installer")


def _option_value(command: Sequence[str], option: str) -> str | None:
    try:
        index = command.index(option)
    except ValueError:
        return None
    return command[index + 1] if index + 1 < len(command) else None


def _launcher_main(arguments: Sequence[str]) -> int:
    if len(arguments) < 12 or tuple(arguments[0::2][:5]) != (
        "--role",
        "--token",
        "--repository",
        "--source-commit",
        "--cwd",
    ):
        raise LocalRuntimeSafetyError("invalid internal launcher arguments")
    if arguments[10] != "--":
        raise LocalRuntimeSafetyError("internal launcher child separator is missing")
    try:
        role = ServiceRole(arguments[1])
    except ValueError as exc:
        raise LocalRuntimeSafetyError("invalid internal launcher role") from exc
    token = arguments[3]
    repository = Path(arguments[5]).resolve(strict=True)
    source_commit = arguments[7]
    child_cwd = Path(arguments[9]).resolve(strict=True)
    child = tuple(arguments[11:])
    if not token or not child:
        raise LocalRuntimeSafetyError("internal launcher token or child command is missing")
    validate_git_object_id(source_commit)
    current_commit = _read_git_revision(repository)
    if current_commit != source_commit:
        raise LocalRuntimeSafetyError(
            "internal launcher source revision differs from the requested start revision"
        )
    if child_cwd != repository and repository not in child_cwd.parents:
        raise LocalRuntimeSafetyError("internal launcher working directory escapes the repository")
    _validate_launcher_child(role, child)

    child_process = subprocess.Popen(child, cwd=child_cwd, start_new_session=False)

    def forward(signum: int, frame: FrameType | None) -> None:
        del frame
        if child_process.poll() is None:
            child_process.send_signal(signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    signal.signal(signal.SIGHUP, forward)
    return child_process.wait()


def main(arguments: Sequence[str] | None = None) -> int:
    selected = tuple(sys.argv[1:] if arguments is None else arguments)
    if not selected or selected[0] != "_launch":
        raise LocalRuntimeSafetyError("this infrastructure module is not a public CLI")
    return _launcher_main(selected[1:])


if __name__ == "__main__":
    raise SystemExit(main())
