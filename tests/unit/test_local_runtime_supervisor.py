"""Infrastructure and orchestration tests without starting real web services."""

from __future__ import annotations

import io
import json
import os
import signal
from http.client import HTTPMessage
from pathlib import Path
from typing import cast
from urllib.error import HTTPError
from urllib.request import Request

import pytest
import typer
from pytest import MonkeyPatch

import lottolab.infrastructure.local_runtime as local_infra
import lottolab.interfaces.cli.main as cli_main
from lottolab.application.local_runtime import (
    BACKEND_PORT,
    EXPECTED_STRATEGY_IDS,
    FRONTEND_PORT,
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
)
from lottolab.infrastructure.local_runtime import (
    HttpResponse,
    LocalRuntimeSupervisor,
    ManagedLaunch,
    ProcessInspector,
    ProcessSnapshot,
    RuntimeDependencies,
    RuntimeLock,
    RuntimeStateStore,
)

TOKEN = "c" * 32
COMMIT = "2" * 40


@pytest.fixture(autouse=True)
def stable_git_revision(monkeypatch: MonkeyPatch) -> None:
    def revision(repository: Path) -> str:
        del repository
        return COMMIT

    monkeypatch.setattr(local_infra, "_read_git_revision", revision)


class HelperLocalRuntimeSupervisor(LocalRuntimeSupervisor):
    def prepare_start_for_test(self) -> None:
        self._prepare_start()

    def assert_owned_listener_for_test(
        self, identity: ProcessIdentity, listeners: tuple[Listener, ...]
    ) -> None:
        self._assert_owned_listener(identity, listeners=listeners)

    def terminate_identity_for_test(
        self, identity: ProcessIdentity, state: RuntimeState
    ) -> None:
        self._terminate_identity(identity, state=state)

    def required_http_get_for_test(self, url: str) -> HttpResponse:
        return self._required_http_get(url)


class NonRunningStartSupervisor:
    def start(self) -> RuntimeStatus:
        return RuntimeStatus(
            kind=RuntimeStatusKind.STOPPED,
            ownership_proven=False,
            backend="stopped",
            frontend="stopped",
            detail="defensive CLI test",
        )


def make_policy(tmp_path: Path) -> LocalRuntimePolicy:
    repository = tmp_path / "repo"
    repository.mkdir(parents=True)
    return LocalRuntimePolicy.for_repository(repository, runtime_dir=tmp_path / "runtime")


def make_identity(
    policy: LocalRuntimePolicy,
    role: ServiceRole,
    *,
    token: str = TOKEN,
    source_commit: str = COMMIT,
    pid: int | None = None,
    start_marker: str = "Wed Jul 15 23:10:00 2026",
) -> ProcessIdentity:
    selected_pid = pid if pid is not None else (42001 if role is ServiceRole.BACKEND else 42002)
    command = (
        f"{policy.repository_root}/.venv/bin/python -m "
        "lottolab.infrastructure.local_runtime _launch "
        f"--role {role.value} --token {token} "
        f"--repository {policy.repository_root} --source-commit {source_commit} "
        f"--cwd {policy.repository_root} -- child"
    )
    return ProcessIdentity(
        role=role,
        pid=selected_pid,
        pgid=selected_pid,
        port=role.port,
        start_marker=start_marker,
        command_line=command,
        log_path=str(policy.log_path(role)),
    )


def snapshot(identity: ProcessIdentity) -> ProcessSnapshot:
    return ProcessSnapshot(
        pgid=identity.pgid,
        start_marker=identity.start_marker,
        command_line=identity.command_line,
    )


def make_state(
    policy: LocalRuntimePolicy,
    *,
    include_frontend: bool = True,
    token: str = TOKEN,
) -> RuntimeState:
    backend = make_identity(policy, ServiceRole.BACKEND, token=token)
    services = (backend,)
    if include_frontend:
        services += (make_identity(policy, ServiceRole.FRONTEND, token=token),)
    return RuntimeState(
        repository_root=str(policy.repository_root),
        source_commit=COMMIT,
        ownership_token=token,
        created_at_ns=1,
        services=services,
    )


def test_state_store_uses_atomic_replacement(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    replacements: list[tuple[str, str, int | None, int | None]] = []
    real_replace = os.replace

    def recording_replace(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        replacements.append((source, destination, src_dir_fd, dst_dir_fd))
        real_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(local_infra.os, "replace", recording_replace)
    backend_only = make_state(policy, include_frontend=False)
    complete = make_state(policy)
    store.write(backend_only)
    store.write(complete)

    assert store.read() == complete
    assert len(replacements) == 2
    assert all(destination == "state.json" for _, destination, _, _ in replacements)
    assert all(
        source_fd == store.directory_fd and destination_fd == store.directory_fd
        for _, _, source_fd, destination_fd in replacements
    )
    assert not list(policy.runtime_dir.glob(".state-*"))
    assert policy.state_path.stat().st_mode & 0o077 == 0


def test_state_store_rejects_corrupt_state(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    store.ensure_runtime_dir()
    policy.state_path.write_text("{not-json", encoding="utf-8")
    policy.state_path.chmod(0o600)
    with pytest.raises(LocalRuntimeSafetyError, match="corrupt"):
        store.read()


def test_runtime_directory_replacement_fails_closed_and_operations_stay_anchored(
    tmp_path: Path,
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy)
    store.write(state)
    anchored_directory = tmp_path / "anchored-runtime-inode"
    policy.runtime_dir.rename(anchored_directory)
    policy.runtime_dir.mkdir(mode=0o700)

    with pytest.raises(LocalRuntimeSafetyError, match="inode changed"):
        store.read()
    with pytest.raises(LocalRuntimeSafetyError, match="inode changed"):
        store.write(state)
    with (
        pytest.raises(LocalRuntimeSafetyError, match="inode changed"),
        RuntimeLock(policy, store),
    ):
        pass

    assert not list(policy.runtime_dir.iterdir())
    assert (anchored_directory / "state.json").is_file()


def test_runtime_directory_rejects_unsafe_mode_and_foreign_owner(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    unsafe_policy = make_policy(tmp_path / "unsafe")
    unsafe_policy.runtime_dir.mkdir(mode=0o755)
    unsafe_policy.runtime_dir.chmod(0o755)
    with pytest.raises(LocalRuntimeSafetyError, match="exactly 0700"):
        RuntimeStateStore(unsafe_policy).ensure_runtime_dir()

    foreign_policy = make_policy(tmp_path / "foreign")
    foreign_policy.runtime_dir.mkdir(mode=0o700)
    owner = os.getuid()
    monkeypatch.setattr(local_infra.os, "getuid", lambda: owner + 1)
    with pytest.raises(LocalRuntimeSafetyError, match="foreign owner"):
        RuntimeStateStore(foreign_policy).ensure_runtime_dir()


def test_fresh_log_rejects_hardlink_and_symlink_without_modifying_target(
    tmp_path: Path,
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    store.ensure_runtime_dir()
    target = tmp_path / "diagnostic-target"
    target.write_bytes(b"must remain unchanged")
    target.chmod(0o600)
    os.link(target, policy.log_path(ServiceRole.BACKEND))

    with pytest.raises(LocalRuntimeSafetyError, match="one link"):
        store.open_fresh_log(ServiceRole.BACKEND)
    assert target.read_bytes() == b"must remain unchanged"

    policy.log_path(ServiceRole.BACKEND).unlink()
    policy.log_path(ServiceRole.BACKEND).symlink_to(target)
    with pytest.raises(LocalRuntimeSafetyError, match="cannot open controller file safely"):
        store.open_fresh_log(ServiceRole.BACKEND)
    assert target.read_bytes() == b"must remain unchanged"


def test_fresh_log_installs_new_0600_inode_and_captures_output(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    store.ensure_runtime_dir()
    existing_log = policy.log_path(ServiceRole.FRONTEND)
    existing_log.write_bytes(b"old log")
    existing_log.chmod(0o600)
    old_inode = existing_log.stat().st_ino

    with store.open_fresh_log(ServiceRole.FRONTEND) as log:
        log.write(b"new captured output")

    metadata = existing_log.stat()
    assert metadata.st_ino != old_inode
    assert metadata.st_mode & 0o777 == 0o600
    assert metadata.st_nlink == 1
    assert existing_log.read_bytes() == b"new captured output"


def test_log_target_swap_before_install_is_harmless(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    store.ensure_runtime_dir()
    log_path = policy.log_path(ServiceRole.BACKEND)
    log_path.write_bytes(b"old")
    log_path.chmod(0o600)
    target = tmp_path / "hardlink-target"
    target.write_bytes(b"target sentinel")
    target.chmod(0o600)
    real_replace = os.replace
    swapped = False

    def swap_then_replace(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal swapped
        if destination == "backend.log" and not swapped:
            swapped = True
            log_path.unlink()
            os.link(target, log_path)
        real_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(local_infra.os, "replace", swap_then_replace)
    with store.open_fresh_log(ServiceRole.BACKEND) as log:
        log.write(b"fresh")

    assert swapped
    assert target.read_bytes() == b"target sentinel"
    assert log_path.read_bytes() == b"fresh"


def test_lock_exclusivity_and_concurrent_start_rejection(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    supervisor = LocalRuntimeSupervisor(policy, state_store=store)
    with RuntimeLock(policy, store):
        with (
            pytest.raises(ConcurrentLocalRuntimeOperation, match="controller lock"),
            RuntimeLock(policy, store),
        ):
            pass
        with pytest.raises(ConcurrentLocalRuntimeOperation, match="controller lock"):
            supervisor.start()


def test_process_inspector_detects_pid_reuse_command_mismatch_and_stale_process(
    tmp_path: Path,
) -> None:
    policy = make_policy(tmp_path)
    identity = make_identity(policy, ServiceRole.BACKEND)
    current: ProcessSnapshot | None = snapshot(identity)

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        assert pid == identity.pid
        return current

    inspector = ProcessInspector(read_snapshot)
    assert inspector.ownership(identity) is Ownership.OWNED
    current = ProcessSnapshot(
        pgid=identity.pgid,
        start_marker="Thu Jul 16 00:00:00 2026",
        command_line=identity.command_line,
    )
    assert inspector.ownership(identity) is Ownership.MISMATCH
    current = ProcessSnapshot(
        pgid=identity.pgid,
        start_marker=identity.start_marker,
        command_line="foreign executable",
    )
    assert inspector.ownership(identity) is Ownership.MISMATCH
    current = None
    assert inspector.ownership(identity) is Ownership.DEAD


def test_process_identity_capture_waits_for_stable_executable_title(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    role = ServiceRole.BACKEND
    stable_command = (
        f"/framework/Python -m lottolab.infrastructure.local_runtime _launch "
        f"--role backend --token {TOKEN} --repository {policy.repository_root}"
    )
    values = [
        ProcessSnapshot(44001, "Wed Jul 15 23:20:00 2026", "/venv/python -m launcher"),
        ProcessSnapshot(44001, "Wed Jul 15 23:20:00 2026", stable_command),
    ]

    def read_snapshot(pid: int) -> ProcessSnapshot:
        assert pid == 44001
        return values.pop(0) if values else ProcessSnapshot(
            44001, "Wed Jul 15 23:20:00 2026", stable_command
        )

    identity = ProcessInspector(read_snapshot).capture(
        pid=44001,
        role=role,
        log_path=policy.log_path(role),
    )
    assert identity.command_line == stable_command


def test_status_classifies_running_partial_stale_and_foreign(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy)
    store.write(state)
    snapshots: dict[int, ProcessSnapshot | None] = {
        identity.pid: snapshot(identity) for identity in state.services
    }

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    listeners_by_port: dict[int, tuple[Listener, ...]] = {
        identity.port: (Listener(identity.pid, f"127.0.0.1:{identity.port}"),)
        for identity in state.services
    }

    def listeners(port: int) -> tuple[Listener, ...]:
        return listeners_by_port.get(port, ())

    def pgid(pid: int) -> int:
        return pid

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(local_infra.os, "getpgid", pgid)

    assert supervisor.status().kind is RuntimeStatusKind.RUNNING

    backend = cast(ProcessIdentity, state.service(ServiceRole.BACKEND))
    store.write(make_state(policy, include_frontend=False))
    snapshots.pop(42002)
    listeners_by_port.pop(FRONTEND_PORT)
    assert supervisor.status().kind is RuntimeStatusKind.PARTIAL

    snapshots[backend.pid] = None
    listeners_by_port.clear()
    assert supervisor.status().kind is RuntimeStatusKind.STALE

    snapshots[backend.pid] = ProcessSnapshot(
        pgid=backend.pgid,
        start_marker="reused start",
        command_line=backend.command_line,
    )
    assert supervisor.status().kind is RuntimeStatusKind.FOREIGN


def test_status_without_state_distinguishes_stopped_and_foreign_listener(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    supervisor = LocalRuntimeSupervisor(policy)
    listeners_by_port: dict[int, tuple[Listener, ...]] = {}

    def listeners(port: int) -> tuple[Listener, ...]:
        return listeners_by_port.get(port, ())

    monkeypatch.setattr(supervisor, "_listeners", listeners)
    assert supervisor.status().kind is RuntimeStatusKind.STOPPED
    listeners_by_port[BACKEND_PORT] = (Listener(90001, "127.0.0.1:8000"),)
    assert supervisor.status().kind is RuntimeStatusKind.FOREIGN


def test_revision_mismatch_makes_status_and_smoke_fail_closed(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    store.write(make_state(policy))
    current_commit = "3" * 40
    supervisor = LocalRuntimeSupervisor(
        policy,
        state_store=store,
        revision_reader=lambda repository: current_commit,
    )

    for operation in (supervisor.status, supervisor.smoke):
        with pytest.raises(LocalRuntimeSafetyError, match="revision mismatch") as failure:
            operation()
        assert f"running_revision={COMMIT}" in str(failure.value)
        assert f"current_revision={current_commit}" in str(failure.value)
        assert "revision_match=no" in str(failure.value)


def test_foreign_listener_is_refused_and_never_terminated(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    supervisor = LocalRuntimeSupervisor(policy)
    terminated = False

    def listeners(port: int) -> tuple[Listener, ...]:
        if port == BACKEND_PORT:
            return (Listener(90001, "127.0.0.1:8000"),)
        return ()

    def dependencies() -> RuntimeDependencies:
        return RuntimeDependencies("python", "uv", "node", "lsof")

    def terminate(
        identity: ProcessIdentity,
        *,
        state: RuntimeState,
        process: object | None = None,
    ) -> None:
        nonlocal terminated
        del identity, state, process
        terminated = True

    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_assert_dependencies", dependencies)
    monkeypatch.setattr(supervisor, "_terminate_identity", terminate)
    with pytest.raises(LocalRuntimeSafetyError, match="foreign listener"):
        supervisor.start()
    with pytest.raises(LocalRuntimeSafetyError, match="foreign listener"):
        supervisor.stop()
    assert not terminated


def test_unbindable_occupied_port_is_refused_before_spawn(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    supervisor = LocalRuntimeSupervisor(policy)
    spawned = False

    def dependencies() -> RuntimeDependencies:
        return RuntimeDependencies("python", "uv", "node", "lsof")

    def listeners(port: int) -> tuple[Listener, ...]:
        del port
        return ()

    def bindable(port: int) -> bool:
        return port != BACKEND_PORT

    def spawn(
        role: ServiceRole,
        token: str,
        source_commit: str,
        dependencies_value: RuntimeDependencies,
    ) -> ManagedLaunch:
        nonlocal spawned
        del role, token, source_commit, dependencies_value
        spawned = True
        raise AssertionError("spawn must not be reached")

    monkeypatch.setattr(supervisor, "_assert_dependencies", dependencies)
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_spawn_service", spawn)
    monkeypatch.setattr(local_infra, "_port_bindable", bindable)
    with pytest.raises(LocalRuntimeSafetyError, match="cannot be bound"):
        supervisor.start()
    assert not spawned


@pytest.mark.parametrize(
    "failing_role",
    [ServiceRole.BACKEND, ServiceRole.FRONTEND],
    ids=["backend-startup-failure", "frontend-startup-failure"],
)
def test_partial_start_failure_cleans_every_owned_process(
    tmp_path: Path, monkeypatch: MonkeyPatch, failing_role: ServiceRole
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    snapshots: dict[int, ProcessSnapshot | None] = {}

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )
    terminated: list[ServiceRole] = []

    def dependencies() -> RuntimeDependencies:
        return RuntimeDependencies("python", "uv", "node", "lsof")

    def ports_free() -> None:
        return None

    def listeners(port: int) -> tuple[Listener, ...]:
        del port
        return ()

    def spawn(
        role: ServiceRole,
        token: str,
        source_commit: str,
        dependencies_value: RuntimeDependencies,
    ) -> ManagedLaunch:
        del dependencies_value
        pid = 43001 if role is ServiceRole.BACKEND else 43002
        identity = make_identity(
            policy, role, token=token, source_commit=source_commit, pid=pid
        )
        snapshots[pid] = snapshot(identity)
        return ManagedLaunch(identity=identity, process=None)

    def wait_backend(state: RuntimeState, identity: ProcessIdentity) -> None:
        del state, identity
        if failing_role is ServiceRole.BACKEND:
            raise LocalRuntimeError("backend failed")

    def wait_frontend(state: RuntimeState, identity: ProcessIdentity) -> None:
        del state, identity
        if failing_role is ServiceRole.FRONTEND:
            raise LocalRuntimeError("frontend failed")

    def terminate(
        identity: ProcessIdentity,
        *,
        state: RuntimeState,
        process: object | None = None,
    ) -> None:
        del state, process
        terminated.append(identity.role)
        snapshots[identity.pid] = None

    monkeypatch.setattr(supervisor, "_assert_dependencies", dependencies)
    monkeypatch.setattr(supervisor, "_assert_all_ports_free", ports_free)
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_spawn_service", spawn)
    monkeypatch.setattr(supervisor, "_wait_for_backend", wait_backend)
    monkeypatch.setattr(supervisor, "_wait_for_frontend", wait_frontend)
    monkeypatch.setattr(supervisor, "_terminate_identity", terminate)

    with pytest.raises(LocalRuntimeError, match=f"{failing_role.value} failed"):
        supervisor.start()
    expected = (
        [ServiceRole.BACKEND]
        if failing_role is ServiceRole.BACKEND
        else [ServiceRole.FRONTEND, ServiceRole.BACKEND]
    )
    assert terminated == expected
    assert store.read() is None


def test_successful_start_records_exact_revision_and_finishes_running(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    snapshots: dict[int, ProcessSnapshot] = {}
    listeners_by_port: dict[int, tuple[Listener, ...]] = {}

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )

    def dependencies() -> RuntimeDependencies:
        return RuntimeDependencies("python", "uv", "node", "lsof")

    def listeners(port: int) -> tuple[Listener, ...]:
        return listeners_by_port.get(port, ())

    def spawn(
        role: ServiceRole,
        token: str,
        source_commit: str,
        dependencies_value: RuntimeDependencies,
    ) -> ManagedLaunch:
        del dependencies_value
        pid = 44501 if role is ServiceRole.BACKEND else 44502
        identity = make_identity(
            policy, role, token=token, source_commit=source_commit, pid=pid
        )
        snapshots[pid] = snapshot(identity)
        listeners_by_port[role.port] = (
            Listener(pid, f"127.0.0.1:{role.port}"),
        )
        return ManagedLaunch(identity=identity, process=None)

    def wait_ready(state: RuntimeState, identity: ProcessIdentity) -> None:
        del state, identity

    def pgid(pid: int) -> int:
        return pid

    def bindable(port: int) -> bool:
        del port
        return True

    monkeypatch.setattr(supervisor, "_assert_dependencies", dependencies)
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_spawn_service", spawn)
    monkeypatch.setattr(supervisor, "_wait_for_backend", wait_ready)
    monkeypatch.setattr(supervisor, "_wait_for_frontend", wait_ready)
    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra, "_port_bindable", bindable)

    started = supervisor.start()
    state = store.read()
    assert started.kind is RuntimeStatusKind.RUNNING
    assert state is not None
    assert state.source_commit == COMMIT
    assert all(f"--source-commit {COMMIT}" in item.command_line for item in state.services)
    current = supervisor.status()
    assert current.kind is RuntimeStatusKind.RUNNING
    assert f"running_revision={COMMIT}" in current.detail
    assert "revision_match=yes" in current.detail


def test_cli_start_defensively_rejects_non_running_result(
    monkeypatch: MonkeyPatch,
) -> None:
    def supervisor() -> NonRunningStartSupervisor:
        return NonRunningStartSupervisor()

    monkeypatch.setattr(cli_main, "_local_supervisor", supervisor)
    with pytest.raises(typer.Exit) as failure:
        cli_main.local_start()
    assert failure.value.exit_code == 1


@pytest.mark.parametrize(
    ("scenario", "expected_terminated", "state_preserved"),
    [
        ("backend-exits-after-readiness", [ServiceRole.FRONTEND], False),
        ("frontend-exits-after-readiness", [ServiceRole.BACKEND], False),
        ("both-exit-after-readiness", [], False),
        (
            "listener-disappears-after-readiness",
            [ServiceRole.FRONTEND, ServiceRole.BACKEND],
            False,
        ),
        (
            "unexpected-stopped-status",
            [ServiceRole.FRONTEND, ServiceRole.BACKEND],
            False,
        ),
        ("foreign-listener-replacement", [ServiceRole.FRONTEND], True),
    ],
)
def test_start_requires_final_running_state_and_safely_cleans(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    scenario: str,
    expected_terminated: list[ServiceRole],
    state_preserved: bool,
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    snapshots: dict[int, ProcessSnapshot | None] = {}
    listeners_by_port: dict[int, tuple[Listener, ...]] = {}
    terminated: list[ServiceRole] = []

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )

    def dependencies() -> RuntimeDependencies:
        return RuntimeDependencies("python", "uv", "node", "lsof")

    def listeners(port: int) -> tuple[Listener, ...]:
        return listeners_by_port.get(port, ())

    def spawn(
        role: ServiceRole,
        token: str,
        source_commit: str,
        dependencies_value: RuntimeDependencies,
    ) -> ManagedLaunch:
        del dependencies_value
        pid = 45001 if role is ServiceRole.BACKEND else 45002
        identity = make_identity(
            policy, role, token=token, source_commit=source_commit, pid=pid
        )
        snapshots[pid] = snapshot(identity)
        listeners_by_port[role.port] = (
            Listener(pid, f"127.0.0.1:{role.port}"),
        )
        return ManagedLaunch(identity=identity, process=None)

    def wait_backend(state: RuntimeState, identity: ProcessIdentity) -> None:
        del state, identity

    def wait_frontend(state: RuntimeState, identity: ProcessIdentity) -> None:
        del state, identity
        backend = 45001
        frontend = 45002
        if scenario in {"backend-exits-after-readiness", "both-exit-after-readiness"}:
            snapshots[backend] = None
            listeners_by_port[BACKEND_PORT] = ()
        if scenario in {"frontend-exits-after-readiness", "both-exit-after-readiness"}:
            snapshots[frontend] = None
            listeners_by_port[FRONTEND_PORT] = ()
        if scenario == "listener-disappears-after-readiness":
            listeners_by_port[FRONTEND_PORT] = ()
        if scenario == "foreign-listener-replacement":
            snapshots[backend] = None
            listeners_by_port[BACKEND_PORT] = (
                Listener(99001, "127.0.0.1:8000"),
            )

    def terminate(
        identity: ProcessIdentity,
        *,
        state: RuntimeState,
        process: object | None = None,
    ) -> None:
        del state, process
        terminated.append(identity.role)
        snapshots[identity.pid] = None
        selected = listeners_by_port.get(identity.port, ())
        if selected and selected[0].pid == identity.pid:
            listeners_by_port[identity.port] = ()

    def pgid(pid: int) -> int:
        return pid

    def bindable(port: int) -> bool:
        del port
        return True

    def stopped_status(
        state: RuntimeState, *, current_revision: str
    ) -> RuntimeStatus:
        del state, current_revision
        return RuntimeStatus(
            kind=RuntimeStatusKind.STOPPED,
            ownership_proven=False,
            backend="stopped",
            frontend="stopped",
            detail="unexpected stopped status",
        )

    monkeypatch.setattr(supervisor, "_assert_dependencies", dependencies)
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_spawn_service", spawn)
    monkeypatch.setattr(supervisor, "_wait_for_backend", wait_backend)
    monkeypatch.setattr(supervisor, "_wait_for_frontend", wait_frontend)
    monkeypatch.setattr(supervisor, "_terminate_identity", terminate)
    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra, "_port_bindable", bindable)
    if scenario == "unexpected-stopped-status":
        monkeypatch.setattr(supervisor, "_status_for_state", stopped_status)

    expected_error = (
        LocalRuntimeSafetyError if state_preserved else LocalRuntimeError
    )
    expected_message = (
        "safe partial cleanup failed" if state_preserved else "must be running"
    )
    with pytest.raises(expected_error, match=expected_message):
        supervisor.start()

    assert terminated == expected_terminated
    assert (store.read() is not None) is state_preserved


def test_stop_is_graceful_ordered_and_repeated_stop_is_safe(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy)
    store.write(state)
    snapshots: dict[int, ProcessSnapshot | None] = {
        identity.pid: snapshot(identity) for identity in state.services
    }
    listeners_by_port: dict[int, tuple[Listener, ...]] = {
        identity.port: (Listener(identity.pid, f"127.0.0.1:{identity.port}"),)
        for identity in state.services
    }

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    def listeners(port: int) -> tuple[Listener, ...]:
        return listeners_by_port.get(port, ())

    def pgid(pid: int) -> int:
        return pid

    terminated: list[ServiceRole] = []

    def terminate(
        identity: ProcessIdentity,
        *,
        state: RuntimeState,
        process: object | None = None,
    ) -> None:
        del state, process
        terminated.append(identity.role)
        snapshots[identity.pid] = None
        listeners_by_port[identity.port] = ()

    def bindable(port: int) -> bool:
        del port
        return True

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_terminate_identity", terminate)
    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra, "_port_bindable", bindable)

    assert supervisor.stop().kind is RuntimeStatusKind.STOPPED
    assert terminated == [ServiceRole.FRONTEND, ServiceRole.BACKEND]
    assert store.read() is None
    assert supervisor.stop().kind is RuntimeStatusKind.STOPPED


def test_revision_mismatch_does_not_weaken_safe_stop(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy)
    store.write(state)
    snapshots: dict[int, ProcessSnapshot | None] = {
        identity.pid: snapshot(identity) for identity in state.services
    }
    listeners_by_port: dict[int, tuple[Listener, ...]] = {
        identity.port: (Listener(identity.pid, f"127.0.0.1:{identity.port}"),)
        for identity in state.services
    }
    terminated: list[ServiceRole] = []

    def unexpected_revision(repository: Path) -> str:
        del repository
        raise AssertionError("safe stop must not resolve the current worktree revision")

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    def listeners(port: int) -> tuple[Listener, ...]:
        return listeners_by_port.get(port, ())

    def terminate(
        identity: ProcessIdentity,
        *,
        state: RuntimeState,
        process: object | None = None,
    ) -> None:
        del state, process
        terminated.append(identity.role)
        snapshots[identity.pid] = None
        listeners_by_port[identity.port] = ()

    def pgid(pid: int) -> int:
        return pid

    def bindable(port: int) -> bool:
        del port
        return True

    supervisor = LocalRuntimeSupervisor(
        policy,
        state_store=store,
        inspector=ProcessInspector(read_snapshot),
        revision_reader=unexpected_revision,
    )
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_terminate_identity", terminate)
    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra, "_port_bindable", bindable)

    assert supervisor.stop().kind is RuntimeStatusKind.STOPPED
    assert terminated == [ServiceRole.FRONTEND, ServiceRole.BACKEND]
    assert store.read() is None


def test_stop_refuses_pid_identity_mismatch_before_any_signal(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy)
    store.write(state)
    snapshots = {
        identity.pid: ProcessSnapshot(
            pgid=identity.pgid,
            start_marker="reused",
            command_line=identity.command_line,
        )
        for identity in state.services
    }
    signalled = False

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    def listeners(port: int) -> tuple[Listener, ...]:
        del port
        return ()

    def terminate(
        identity: ProcessIdentity,
        *,
        state: RuntimeState,
        process: object | None = None,
    ) -> None:
        nonlocal signalled
        del identity, state, process
        signalled = True

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_terminate_identity", terminate)
    with pytest.raises(LocalRuntimeSafetyError, match="PID identity mismatch"):
        supervisor.stop()
    assert not signalled


def test_escalation_revalidates_owned_then_dead_and_sends_no_sigkill(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    state = make_state(policy, include_frontend=False)
    identity = cast(ProcessIdentity, state.service(ServiceRole.BACKEND))
    observations: list[ProcessSnapshot | None] = [snapshot(identity), None]
    sent: list[int] = []
    supervisor = HelperLocalRuntimeSupervisor(
        policy,
        inspector=ProcessInspector(lambda pid: observations.pop(0)),
    )

    def pgid(pid: int) -> int:
        del pid
        return identity.pgid

    def killpg(group: int, signum: int) -> None:
        del group
        sent.append(signum)

    def wait_for_exit(group: int, timeout: float, process: object | None) -> bool:
        del group, timeout, process
        return False

    def listeners(port: int) -> tuple[Listener, ...]:
        del port
        return ()

    def group_alive(group: int) -> bool:
        del group
        return False

    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra.os, "killpg", killpg)
    monkeypatch.setattr(supervisor, "_wait_for_group_exit", wait_for_exit)
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(local_infra, "_process_group_alive", group_alive)

    supervisor.terminate_identity_for_test(identity, state)
    assert sent == [signal.SIGTERM]
    assert signal.SIGKILL not in sent


def test_escalation_owned_then_mismatch_preserves_state_and_sends_no_sigkill(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy, include_frontend=False)
    store.write(state)
    identity = cast(ProcessIdentity, state.service(ServiceRole.BACKEND))
    mismatch = ProcessSnapshot(
        pgid=identity.pgid,
        start_marker="replacement start marker",
        command_line=identity.command_line,
    )
    observations: list[ProcessSnapshot | None] = [snapshot(identity), mismatch]
    sent: list[int] = []
    supervisor = HelperLocalRuntimeSupervisor(
        policy,
        state_store=store,
        inspector=ProcessInspector(lambda pid: observations.pop(0)),
    )

    def pgid(pid: int) -> int:
        del pid
        return identity.pgid

    def killpg(group: int, signum: int) -> None:
        del group
        sent.append(signum)

    def wait_for_exit(group: int, timeout: float, process: object | None) -> bool:
        del group, timeout, process
        return False

    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra.os, "killpg", killpg)
    monkeypatch.setattr(supervisor, "_wait_for_group_exit", wait_for_exit)

    with pytest.raises(LocalRuntimeSafetyError, match="ambiguous before SIGKILL"):
        supervisor.terminate_identity_for_test(identity, state)
    assert sent == [signal.SIGTERM]
    assert signal.SIGKILL not in sent
    assert store.read() == state


def test_reused_pgid_after_leader_death_is_never_signalled(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy, include_frontend=False)
    store.write(state)
    identity = cast(ProcessIdentity, state.service(ServiceRole.BACKEND))
    observations: list[ProcessSnapshot | None] = [snapshot(identity), None]
    sent: list[int] = []
    supervisor = HelperLocalRuntimeSupervisor(
        policy,
        state_store=store,
        inspector=ProcessInspector(lambda pid: observations.pop(0)),
    )

    def pgid(pid: int) -> int:
        del pid
        return identity.pgid

    def killpg(group: int, signum: int) -> None:
        del group
        sent.append(signum)

    def wait_for_exit(group: int, timeout: float, process: object | None) -> bool:
        del group, timeout, process
        return False

    def listeners(port: int) -> tuple[Listener, ...]:
        del port
        return ()

    def group_alive(group: int) -> bool:
        del group
        return True

    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra.os, "killpg", killpg)
    monkeypatch.setattr(supervisor, "_wait_for_group_exit", wait_for_exit)
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(local_infra, "_process_group_alive", group_alive)

    with pytest.raises(LocalRuntimeSafetyError, match="PGID may be reused"):
        supervisor.terminate_identity_for_test(identity, state)
    assert sent == [signal.SIGTERM]
    assert signal.SIGKILL not in sent
    assert store.read() == state


def test_stale_state_is_removed_only_when_ports_are_free(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    store.write(make_state(policy, include_frontend=False))
    supervisor = HelperLocalRuntimeSupervisor(
        policy,
        state_store=store,
        inspector=ProcessInspector(lambda pid: None),
    )

    def listeners(port: int) -> tuple[Listener, ...]:
        del port
        return ()

    def bindable(port: int) -> bool:
        del port
        return True

    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(local_infra, "_port_bindable", bindable)
    supervisor.prepare_start_for_test()
    assert store.read() is None


def test_listener_validation_rejects_nonlocal_and_foreign_process_group(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    identity = make_identity(policy, ServiceRole.BACKEND)
    supervisor = HelperLocalRuntimeSupervisor(policy)
    with pytest.raises(LocalRuntimeSafetyError, match="not localhost-only"):
        supervisor.assert_owned_listener_for_test(
            identity, (Listener(identity.pid, "*:8000"),)
        )

    def foreign_pgid(pid: int) -> int:
        del pid
        return identity.pgid + 1

    monkeypatch.setattr(local_infra.os, "getpgid", foreign_pgid)
    with pytest.raises(LocalRuntimeSafetyError, match="foreign process group"):
        supervisor.assert_owned_listener_for_test(
            identity,
            (Listener(identity.pid + 10, "127.0.0.1:8000"),),
        )


def test_smoke_verifies_health_proxy_catalog_openapi_and_local_listeners(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    state = make_state(policy)
    store.write(state)
    snapshots = {identity.pid: snapshot(identity) for identity in state.services}

    def read_snapshot(pid: int) -> ProcessSnapshot | None:
        return snapshots.get(pid)

    def listeners(port: int) -> tuple[Listener, ...]:
        identity = next(service for service in state.services if service.port == port)
        return (Listener(identity.pid, f"127.0.0.1:{port}"),)

    def pgid(pid: int) -> int:
        return pid

    catalog = [
        {
            "strategy_id": strategy_id,
            "lifecycle_status": "OBSERVATION",
            "executable": False,
        }
        for strategy_id in EXPECTED_STRATEGY_IDS
    ]
    backend_headers = {"x-lottolab-owner": TOKEN}
    responses = {
        "http://127.0.0.1:8000/api/health": HttpResponse(
            200, json.dumps({"status": "ok", "api_version": "v1"}).encode(), backend_headers
        ),
        "http://127.0.0.1:5173/": HttpResponse(
            200, b'<html><div id="app"></div></html>', {}
        ),
        "http://127.0.0.1:8000/api/v1/strategies": HttpResponse(
            200, json.dumps(catalog).encode(), backend_headers
        ),
        "http://127.0.0.1:5173/api/v1/strategies": HttpResponse(
            200, json.dumps(catalog).encode(), {}
        ),
        "http://127.0.0.1:8000/openapi.json": HttpResponse(
            200,
            json.dumps(
                {
                    "paths": {
                        "/api/health": {"get": {}},
                        "/api/v1/strategies": {"get": {}},
                    }
                }
            ).encode(),
            backend_headers,
        ),
    }

    def http_get(url: str) -> HttpResponse:
        return responses[url]

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(local_infra.os, "getpgid", pgid)
    monkeypatch.setattr(local_infra, "_http_get", http_get)

    report = supervisor.smoke()
    assert report.strategy_ids == EXPECTED_STRATEGY_IDS


@pytest.mark.parametrize(
    "location",
    [
        "https://example.invalid/escape",
        "http://127.0.0.1:8000/api/v1/strategies",
    ],
    ids=["external-target", "alternate-local-path"],
)
def test_http_redirect_is_rejected_without_a_second_request(
    tmp_path: Path, monkeypatch: MonkeyPatch, location: str
) -> None:
    url = "http://127.0.0.1:8000/api/health"
    supervisor = HelperLocalRuntimeSupervisor(make_policy(tmp_path))
    headers = HTTPMessage()
    headers["Location"] = location
    calls: list[str] = []

    class RedirectingOpener:
        def open(self, request: object, *, timeout: float) -> object:
            del timeout
            calls.append(cast(Request, request).full_url)
            raise HTTPError(url, 302, "Found", headers, io.BytesIO(b"redirect"))

    def fake_build_opener(*handlers: object) -> RedirectingOpener:
        assert any(type(handler).__name__ == "_RejectRedirectHandler" for handler in handlers)
        return RedirectingOpener()

    monkeypatch.setattr(local_infra, "build_opener", fake_build_opener)
    with pytest.raises(LocalRuntimeSafetyError, match="redirect response is forbidden"):
        supervisor.required_http_get_for_test(url)
    assert calls == [url]


def test_http_effective_url_mismatch_and_non_loopback_request_are_rejected(
    tmp_path: Path, monkeypatch: MonkeyPatch,
) -> None:
    requested = "http://127.0.0.1:8000/api/health"
    supervisor = HelperLocalRuntimeSupervisor(make_policy(tmp_path))
    opened = False

    class MismatchedResponse:
        url = "http://127.0.0.1:8000/api/v1/strategies"

        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def __enter__(self) -> MismatchedResponse:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: object | None,
        ) -> None:
            del exc_type, exc_value, traceback

        def getcode(self) -> int:
            return 200

        def read(self, limit: int) -> bytes:
            del limit
            return b"{}"

    class MismatchedOpener:
        def open(self, request: object, *, timeout: float) -> MismatchedResponse:
            nonlocal opened
            del request, timeout
            opened = True
            return MismatchedResponse()

    def fake_build_opener(*handlers: object) -> MismatchedOpener:
        del handlers
        return MismatchedOpener()

    monkeypatch.setattr(local_infra, "build_opener", fake_build_opener)
    with pytest.raises(LocalRuntimeSafetyError, match="effective URL changed"):
        supervisor.required_http_get_for_test(requested)
    assert opened

    opened = False
    with pytest.raises(LocalRuntimeSafetyError, match="fixed loopback endpoint"):
        supervisor.required_http_get_for_test("http://example.invalid/api/health")
    assert not opened


def test_http_normal_loopback_200_remains_valid(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    requested = "http://127.0.0.1:8000/api/health"
    supervisor = HelperLocalRuntimeSupervisor(make_policy(tmp_path))

    class LoopbackResponse:
        url = requested

        def __init__(self) -> None:
            self.headers = {"X-LottoLab-Owner": TOKEN}

        def __enter__(self) -> LoopbackResponse:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: object | None,
        ) -> None:
            del exc_type, exc_value, traceback

        def getcode(self) -> int:
            return 200

        def read(self, limit: int) -> bytes:
            del limit
            return b'{"status":"ok","api_version":"v1"}'

    class LoopbackOpener:
        def open(self, request: object, *, timeout: float) -> LoopbackResponse:
            del request, timeout
            return LoopbackResponse()

    def fake_build_opener(*handlers: object) -> LoopbackOpener:
        del handlers
        return LoopbackOpener()

    monkeypatch.setattr(local_infra, "build_opener", fake_build_opener)
    response = supervisor.required_http_get_for_test(requested)
    assert response.status == 200
    assert response.effective_url == requested
    assert response.headers == {"x-lottolab-owner": TOKEN}
