"""Infrastructure and orchestration tests without starting real web services."""

import json
import os
from pathlib import Path
from typing import cast

import pytest
from pytest import MonkeyPatch

import lottolab.infrastructure.local_runtime as local_infra
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


class HelperLocalRuntimeSupervisor(LocalRuntimeSupervisor):
    def prepare_start_for_test(self) -> None:
        self._prepare_start()

    def assert_owned_listener_for_test(
        self, identity: ProcessIdentity, listeners: tuple[Listener, ...]
    ) -> None:
        self._assert_owned_listener(identity, listeners=listeners)


def make_policy(tmp_path: Path) -> LocalRuntimePolicy:
    repository = tmp_path / "repo"
    repository.mkdir()
    return LocalRuntimePolicy.for_repository(repository, runtime_dir=tmp_path / "runtime")


def make_identity(
    policy: LocalRuntimePolicy,
    role: ServiceRole,
    *,
    token: str = TOKEN,
    pid: int | None = None,
    start_marker: str = "Wed Jul 15 23:10:00 2026",
) -> ProcessIdentity:
    selected_pid = pid if pid is not None else (42001 if role is ServiceRole.BACKEND else 42002)
    command = (
        f"{policy.repository_root}/.venv/bin/python -m "
        "lottolab.infrastructure.local_runtime _launch "
        f"--role {role.value} --token {token} "
        f"--repository {policy.repository_root} --cwd {policy.repository_root} -- child"
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
        ownership_token=token,
        created_at_ns=1,
        services=services,
    )


def test_state_store_uses_atomic_replacement(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    policy = make_policy(tmp_path)
    store = RuntimeStateStore(policy)
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(local_infra.os, "replace", recording_replace)
    backend_only = make_state(policy, include_frontend=False)
    complete = make_state(policy)
    store.write(backend_only)
    store.write(complete)

    assert store.read() == complete
    assert len(replacements) == 2
    assert all(destination == policy.state_path for _, destination in replacements)
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
        identity: ProcessIdentity, *, process: object | None = None
    ) -> None:
        nonlocal terminated
        del identity, process
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
        role: ServiceRole, token: str, dependencies_value: RuntimeDependencies
    ) -> ManagedLaunch:
        nonlocal spawned
        del role, token, dependencies_value
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
        role: ServiceRole, token: str, dependencies_value: RuntimeDependencies
    ) -> ManagedLaunch:
        del dependencies_value
        pid = 43001 if role is ServiceRole.BACKEND else 43002
        identity = make_identity(policy, role, token=token, pid=pid)
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
        identity: ProcessIdentity, *, process: object | None = None
    ) -> None:
        del process
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
        identity: ProcessIdentity, *, process: object | None = None
    ) -> None:
        del process
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
        identity: ProcessIdentity, *, process: object | None = None
    ) -> None:
        nonlocal signalled
        del identity, process
        signalled = True

    supervisor = LocalRuntimeSupervisor(
        policy, state_store=store, inspector=ProcessInspector(read_snapshot)
    )
    monkeypatch.setattr(supervisor, "_listeners", listeners)
    monkeypatch.setattr(supervisor, "_terminate_identity", terminate)
    with pytest.raises(LocalRuntimeSafetyError, match="PID identity mismatch"):
        supervisor.stop()
    assert not signalled


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
