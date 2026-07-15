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
import tempfile
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import BinaryIO, cast
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

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
    validate_health_payload,
    validate_openapi_payload,
    validate_strategy_payloads,
)

_STARTUP_TIMEOUT_SECONDS = 20.0
_GRACEFUL_STOP_SECONDS = 5.0
_FORCED_STOP_SECONDS = 3.0
_HTTP_LIMIT_BYTES = 1_048_576
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


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


SnapshotReader = Callable[[int], ProcessSnapshot | None]


class RuntimeStateStore:
    """Owner-only state with strict parsing and atomic replacement."""

    def __init__(self, policy: LocalRuntimePolicy) -> None:
        self._policy = policy

    def ensure_runtime_dir(self) -> None:
        path = self._policy.runtime_dir
        with suppress(FileExistsError):
            os.mkdir(path, 0o700)
        try:
            metadata = os.lstat(path)
        except OSError as exc:
            raise LocalRuntimeSafetyError(f"cannot inspect runtime directory: {exc}") from exc
        if not stat.S_ISDIR(metadata.st_mode):
            raise LocalRuntimeSafetyError("runtime directory is not a real directory")
        if metadata.st_uid != os.getuid():
            raise LocalRuntimeSafetyError("runtime directory has a foreign owner")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise LocalRuntimeSafetyError("runtime directory permissions are not owner-only")

    def read(self) -> RuntimeState | None:
        self.ensure_runtime_dir()
        if not os.path.lexists(self._policy.state_path):
            return None
        descriptor = _open_owned_regular(self._policy.state_path, os.O_RDONLY)
        try:
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                payload = cast(object, json.load(handle))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LocalRuntimeSafetyError(f"runtime state is corrupt: {exc}") from exc
        return RuntimeState.from_object(payload)

    def write(self, state: RuntimeState) -> None:
        self.ensure_runtime_dir()
        if os.path.lexists(self._policy.state_path):
            descriptor = _open_owned_regular(self._policy.state_path, os.O_RDONLY)
            os.close(descriptor)
        payload = (
            json.dumps(state.to_object(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".state-", dir=self._policy.runtime_dir
        )
        temporary_path = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            remaining = memoryview(payload)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise LocalRuntimeSafetyError("atomic state write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary_path, self._policy.state_path)
            directory_descriptor = os.open(self._policy.runtime_dir, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.lexists(temporary_path):
                os.unlink(temporary_path)
            raise

    def delete(self) -> None:
        self.ensure_runtime_dir()
        if not os.path.lexists(self._policy.state_path):
            return
        descriptor = _open_owned_regular(self._policy.state_path, os.O_RDONLY)
        os.close(descriptor)
        os.unlink(self._policy.state_path)


class RuntimeLock:
    """Non-blocking process lock used by every controller operation."""

    def __init__(self, policy: LocalRuntimePolicy, store: RuntimeStateStore) -> None:
        self._policy = policy
        self._store = store
        self._descriptor: int | None = None

    def __enter__(self) -> RuntimeLock:
        self._store.ensure_runtime_dir()
        try:
            descriptor = os.open(
                self._policy.lock_path,
                os.O_RDWR | os.O_CREAT | _NOFOLLOW,
                0o600,
            )
        except OSError as exc:
            raise LocalRuntimeSafetyError(f"cannot open controller lock safely: {exc}") from exc
        try:
            _validate_owned_regular_descriptor(descriptor, self._policy.lock_path)
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
    ) -> None:
        self.policy = policy
        self.store = state_store or RuntimeStateStore(policy)
        self.inspector = inspector or ProcessInspector()

    def start(self) -> RuntimeStatus:
        with RuntimeLock(self.policy, self.store):
            dependencies = self._assert_dependencies()
            self._prepare_start()
            self._assert_all_ports_free()
            token = secrets.token_hex(16)
            started: list[ManagedLaunch] = []
            state: RuntimeState | None = None
            try:
                backend = self._spawn_service(ServiceRole.BACKEND, token, dependencies)
                started.append(backend)
                state = self.policy.initial_state(token, backend.identity)
                self.store.write(state)
                self._wait_for_backend(state, backend.identity)

                frontend = self._spawn_service(ServiceRole.FRONTEND, token, dependencies)
                started.append(frontend)
                state = state.with_service(frontend.identity)
                self.store.write(state)
                self._wait_for_frontend(state, frontend.identity)
                return self._status_for_state(state)
            except BaseException as original:
                try:
                    self._cleanup_partial_start(started, state is not None)
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
            return self._status_for_state(state)

    def smoke(self) -> SmokeReport:
        with RuntimeLock(self.policy, self.store):
            state = self.store.read()
            if state is None:
                raise LocalRuntimeError("local runtime is stopped")
            self._require_same_repository(state)
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
                    self._terminate_identity(identity)

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
            child_command=child_command,
        )
        environment = os.environ.copy()
        environment["UV_NO_SYNC"] = "1"
        environment["NO_COLOR"] = "1"
        log_path = self.policy.log_path(role)
        with _open_controller_log(log_path) as log:
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
        except BaseException:
            _terminate_new_process_group(process)
            raise
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
        self, started: Sequence[ManagedLaunch], state_was_written: bool
    ) -> None:
        for managed in started:
            ownership = self.inspector.ownership(managed.identity)
            if ownership is Ownership.MISMATCH:
                raise LocalRuntimeSafetyError(
                    f"cannot clean {managed.identity.role.value}: PID identity mismatch"
                )
            listeners = self._listeners(managed.identity.port)
            if listeners:
                if ownership is not Ownership.OWNED:
                    raise LocalRuntimeSafetyError(
                        f"cannot clean {managed.identity.role.value}: foreign listener present"
                    )
                self._assert_owned_listener(managed.identity, listeners=listeners)

        for managed in reversed(started):
            if self.inspector.ownership(managed.identity) is Ownership.OWNED:
                self._terminate_identity(managed.identity, process=managed.process)
        self._assert_all_ports_free()
        if state_was_written:
            self.store.delete()

    def _terminate_identity(
        self,
        identity: ProcessIdentity,
        *,
        process: subprocess.Popen[bytes] | None = None,
    ) -> None:
        ownership = self.inspector.ownership(identity)
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
            try:
                os.killpg(identity.pgid, signal.SIGKILL)
            except ProcessLookupError:
                return
            if not self._wait_for_group_exit(identity.pgid, _FORCED_STOP_SECONDS, process):
                raise LocalRuntimeSafetyError(
                    f"owned {identity.role.value} process group did not terminate"
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

    def _status_for_state(self, state: RuntimeState) -> RuntimeStatus:
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
            detail=f"runtime state is {kind.value}; repository and PID identity were checked",
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
        path = Path(identity.log_path)
        try:
            descriptor = _open_owned_regular(path, os.O_RDONLY)
            try:
                size = os.fstat(descriptor).st_size
                os.lseek(descriptor, max(0, size - 4096), os.SEEK_SET)
                body = os.read(descriptor, 4096)
            finally:
                os.close(descriptor)
        except OSError:
            return "<log unavailable>"
        return body.decode("utf-8", errors="replace").strip() or "<empty log>"


def _open_owned_regular(path: Path, flags: int) -> int:
    try:
        descriptor = os.open(path, flags | _NOFOLLOW)
    except OSError as exc:
        raise LocalRuntimeSafetyError(
            f"cannot open controller file safely ({path.name}): {exc}"
        ) from exc
    try:
        _validate_owned_regular_descriptor(descriptor, path)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _validate_owned_regular_descriptor(descriptor: int, path: Path) -> None:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalRuntimeSafetyError(f"controller path is not a regular file: {path.name}")
    if metadata.st_uid != os.getuid():
        raise LocalRuntimeSafetyError(f"controller path has a foreign owner: {path.name}")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LocalRuntimeSafetyError(f"controller path permissions are unsafe: {path.name}")


def _open_controller_log(path: Path) -> BinaryIO:
    if os.path.lexists(path):
        descriptor = _open_owned_regular(path, os.O_WRONLY)
        os.close(descriptor)
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _NOFOLLOW,
            0o600,
        )
    except OSError as exc:
        raise LocalRuntimeSafetyError(f"cannot open {path.name} safely: {exc}") from exc
    try:
        _validate_owned_regular_descriptor(descriptor, path)
        return cast(BinaryIO, os.fdopen(descriptor, "wb", buffering=0))
    except BaseException:
        os.close(descriptor)
        raise


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


def _http_get(url: str) -> HttpResponse:
    opener = build_opener(ProxyHandler({}))
    request = Request(url, headers={"Accept": "application/json, text/html"}, method="GET")
    try:
        with opener.open(request, timeout=2.0) as response:
            status_code = response.getcode()
            body = response.read(_HTTP_LIMIT_BYTES + 1)
            headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as exc:
        status_code = exc.code
        body = exc.read(_HTTP_LIMIT_BYTES + 1)
        headers = {key.lower(): value for key, value in exc.headers.items()}
    except (URLError, TimeoutError, OSError) as exc:
        raise LocalRuntimeError(f"HTTP request failed for {url}: {exc}") from exc
    if len(body) > _HTTP_LIMIT_BYTES:
        raise LocalRuntimeSafetyError(f"HTTP response exceeded size limit: {url}")
    return HttpResponse(status=int(status_code), body=body, headers=headers)


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


def _terminate_new_process_group(process: subprocess.Popen[bytes]) -> None:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)


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
    if len(arguments) < 10 or tuple(arguments[0::2][:4]) != (
        "--role",
        "--token",
        "--repository",
        "--cwd",
    ):
        raise LocalRuntimeSafetyError("invalid internal launcher arguments")
    if arguments[8] != "--":
        raise LocalRuntimeSafetyError("internal launcher child separator is missing")
    try:
        role = ServiceRole(arguments[1])
    except ValueError as exc:
        raise LocalRuntimeSafetyError("invalid internal launcher role") from exc
    token = arguments[3]
    repository = Path(arguments[5]).resolve(strict=True)
    child_cwd = Path(arguments[7]).resolve(strict=True)
    child = tuple(arguments[9:])
    if not token or not child:
        raise LocalRuntimeSafetyError("internal launcher token or child command is missing")
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
