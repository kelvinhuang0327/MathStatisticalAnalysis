"""Application-policy tests for the local runtime safety contract."""

from pathlib import Path

import pytest

from lottolab.application.local_runtime import (
    BACKEND_PORT,
    EXPECTED_STRATEGY_IDS,
    FRONTEND_PORT,
    LOCAL_HOST,
    Listener,
    LocalRuntimePolicy,
    LocalRuntimeSafetyError,
    ProcessIdentity,
    RuntimeState,
    ServiceRole,
    validate_frontend_document,
    validate_health_payload,
    validate_openapi_payload,
    validate_strategy_payloads,
)

TOKEN = "a" * 32


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
) -> ProcessIdentity:
    selected_pid = pid if pid is not None else (41001 if role is ServiceRole.BACKEND else 41002)
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
        start_marker="Wed Jul 15 23:00:00 2026",
        command_line=command,
        log_path=str(policy.log_path(role)),
    )


def expected_catalog() -> list[dict[str, object]]:
    return [
        {
            "strategy_id": strategy_id,
            "display_name": strategy_id,
            "version": "v0.1",
            "supported_lottery_types": ["BIG_LOTTO"],
            "minimum_history": 1,
            "lifecycle_status": "OBSERVATION",
            "executable": False,
        }
        for strategy_id in EXPECTED_STRATEGY_IDS
    ]


def test_state_serialization_validation_and_service_order(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    backend = make_identity(policy, ServiceRole.BACKEND)
    frontend = make_identity(policy, ServiceRole.FRONTEND)
    state = RuntimeState(
        repository_root=str(policy.repository_root),
        ownership_token=TOKEN,
        created_at_ns=1,
        services=(backend,),
    ).with_service(frontend)

    assert RuntimeState.from_object(state.to_object()) == state
    assert [service.role for service in state.services] == [
        ServiceRole.BACKEND,
        ServiceRole.FRONTEND,
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "state_version": 1,
            "repository_root": "/tmp/repo",
            "ownership_token": "bad",
            "created_at_ns": 1,
            "services": [],
        },
        {
            "state_version": 2,
            "repository_root": "/tmp/repo",
            "ownership_token": TOKEN,
            "created_at_ns": 1,
            "services": [],
        },
    ],
)
def test_state_rejects_corrupt_or_unsupported_payload(payload: object) -> None:
    with pytest.raises(LocalRuntimeSafetyError):
        RuntimeState.from_object(payload)


def test_state_rejects_frontend_without_backend(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    with pytest.raises(LocalRuntimeSafetyError, match="frontend state"):
        RuntimeState(
            repository_root=str(policy.repository_root),
            ownership_token=TOKEN,
            created_at_ns=1,
            services=(make_identity(policy, ServiceRole.FRONTEND),),
        )


def test_state_rejects_pid_identity_or_repository_token_mismatch(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    with pytest.raises(LocalRuntimeSafetyError, match="process-group leader"):
        ProcessIdentity(
            role=ServiceRole.BACKEND,
            pid=42,
            pgid=43,
            port=BACKEND_PORT,
            start_marker="start",
            command_line="command",
            log_path=str(policy.log_path(ServiceRole.BACKEND)),
        )

    identity = make_identity(policy, ServiceRole.BACKEND, token="b" * 32)
    with pytest.raises(LocalRuntimeSafetyError, match="repository ownership"):
        RuntimeState(
            repository_root=str(policy.repository_root),
            ownership_token=TOKEN,
            created_at_ns=1,
            services=(identity,),
        )


def test_commands_pin_localhost_ports_and_never_install(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    backend = policy.backend_command("/opt/bin/uv", TOKEN)
    frontend = policy.frontend_command("/opt/bin/node")

    assert backend[:3] == ("/opt/bin/uv", "run", "--no-sync")
    assert backend[backend.index("--host") + 1] == LOCAL_HOST
    assert backend[backend.index("--port") + 1] == str(BACKEND_PORT)
    assert frontend[frontend.index("--host") + 1] == LOCAL_HOST
    assert frontend[frontend.index("--port") + 1] == str(FRONTEND_PORT)
    assert "--strictPort" in frontend
    combined = " ".join((*backend, *frontend)).lower()
    assert "0.0.0.0" not in combined
    assert "npm install" not in combined
    assert "npm ci" not in combined
    assert "uv sync" not in combined
    assert "pip install" not in combined


def test_runtime_directory_inside_repository_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    with pytest.raises(LocalRuntimeSafetyError, match="outside"):
        LocalRuntimePolicy.for_repository(repository, runtime_dir=repository / ".runtime")


def test_smoke_payload_contract_and_deterministic_order() -> None:
    direct = expected_catalog()
    proxied = [dict(record) for record in direct]
    assert validate_strategy_payloads(direct, proxied) == EXPECTED_STRATEGY_IDS
    validate_health_payload({"status": "ok", "api_version": "v1"})
    validate_frontend_document(b'<!doctype html><div id="app"></div>')


@pytest.mark.parametrize("mutation", ["order", "lifecycle", "executable", "proxy"])
def test_smoke_rejects_catalog_contract_drift(mutation: str) -> None:
    direct = expected_catalog()
    proxied = [dict(record) for record in direct]
    if mutation == "order":
        direct.reverse()
        proxied.reverse()
    elif mutation == "lifecycle":
        direct[0]["lifecycle_status"] = "ONLINE"
        proxied[0]["lifecycle_status"] = "ONLINE"
    elif mutation == "executable":
        direct[0]["executable"] = True
        proxied[0]["executable"] = True
    else:
        proxied[0]["version"] = "different"
    with pytest.raises(LocalRuntimeSafetyError):
        validate_strategy_payloads(direct, proxied)


def test_smoke_rejects_generation_or_mutating_openapi_paths() -> None:
    validate_openapi_payload(
        {
            "paths": {
                "/api/health": {"get": {}},
                "/api/v1/strategies": {"get": {}},
            }
        }
    )
    with pytest.raises(LocalRuntimeSafetyError, match="generation or execution"):
        validate_openapi_payload({"paths": {"/api/v1/generate": {"get": {}}}})
    with pytest.raises(LocalRuntimeSafetyError, match="mutating"):
        validate_openapi_payload({"paths": {"/api/v1/strategies": {"post": {}}}})


def test_listener_value_is_plain_identity_data() -> None:
    assert Listener(pid=42, address="127.0.0.1:8000") == Listener(
        pid=42, address="127.0.0.1:8000"
    )
