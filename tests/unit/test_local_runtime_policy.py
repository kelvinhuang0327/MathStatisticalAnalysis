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
COMMIT = "1" * 40


def make_policy(tmp_path: Path) -> LocalRuntimePolicy:
    repository = tmp_path / "repo"
    repository.mkdir()
    return LocalRuntimePolicy.for_repository(repository, runtime_dir=tmp_path / "runtime")


def make_identity(
    policy: LocalRuntimePolicy,
    role: ServiceRole,
    *,
    token: str = TOKEN,
    source_commit: str = COMMIT,
    pid: int | None = None,
) -> ProcessIdentity:
    selected_pid = pid if pid is not None else (41001 if role is ServiceRole.BACKEND else 41002)
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
        source_commit=COMMIT,
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
            "state_version": 3,
            "repository_root": "/tmp/repo",
            "source_commit": COMMIT,
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
            source_commit=COMMIT,
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
            source_commit=COMMIT,
            ownership_token=TOKEN,
            created_at_ns=1,
            services=(identity,),
        )


def test_commands_pin_localhost_ports_and_never_install(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    backend = policy.backend_command("/opt/bin/uv", TOKEN)
    frontend = policy.frontend_command("/opt/bin/node")
    launcher = policy.launcher_command(
        python_executable="/repo/.venv/bin/python",
        role=ServiceRole.BACKEND,
        token=TOKEN,
        source_commit=COMMIT,
        child_command=backend,
    )

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
    assert launcher[launcher.index("--source-commit") + 1] == COMMIT


def test_runtime_directory_inside_repository_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    with pytest.raises(LocalRuntimeSafetyError, match="outside"):
        LocalRuntimePolicy.for_repository(repository, runtime_dir=repository / ".runtime")


def test_runtime_directory_traversal_into_repository_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    traversal = tmp_path / "outside" / ".." / "repo" / ".runtime"
    with pytest.raises(LocalRuntimeSafetyError, match="traversal"):
        LocalRuntimePolicy.for_repository(repository, runtime_dir=traversal)


def test_runtime_directory_symlink_parent_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    alias = tmp_path / "repo-alias"
    alias.symlink_to(repository, target_is_directory=True)
    with pytest.raises(LocalRuntimeSafetyError, match="symlinked"):
        LocalRuntimePolicy.for_repository(repository, runtime_dir=alias / ".runtime")


def test_runtime_directory_non_directory_component_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    component = tmp_path / "not-a-directory"
    component.write_text("sentinel", encoding="utf-8")
    with pytest.raises(LocalRuntimeSafetyError, match="non-directory component"):
        LocalRuntimePolicy.for_repository(repository, runtime_dir=component / "runtime")


@pytest.mark.parametrize("source_commit", ["", "1" * 39, "g" * 40, "1" * 41])
def test_state_rejects_malformed_or_missing_source_commit(
    tmp_path: Path, source_commit: str
) -> None:
    policy = make_policy(tmp_path)
    with pytest.raises(LocalRuntimeSafetyError, match="full Git object ID"):
        RuntimeState(
            repository_root=str(policy.repository_root),
            source_commit=source_commit,
            ownership_token=TOKEN,
            created_at_ns=1,
            services=(make_identity(policy, ServiceRole.BACKEND),),
        )

    valid = RuntimeState(
        repository_root=str(policy.repository_root),
        source_commit=COMMIT,
        ownership_token=TOKEN,
        created_at_ns=1,
        services=(make_identity(policy, ServiceRole.BACKEND),),
    ).to_object()
    del valid["source_commit"]
    with pytest.raises(LocalRuntimeSafetyError, match="keys are invalid"):
        RuntimeState.from_object(valid)


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


def test_smoke_accepts_exact_authorized_openapi_surface_with_path_metadata() -> None:
    paths = authorized_openapi_paths()
    paths["/api/health"].update(
        {
            "summary": "Local health",
            "description": "DB-free readiness check",
            "servers": [{"url": "http://127.0.0.1:8000"}],
            "parameters": [],
            "x-lottolab-local": True,
        }
    )

    validate_openapi_payload({"paths": paths})


def authorized_openapi_paths() -> dict[str, dict[str, object]]:
    return {
        "/api/health": {"get": {}},
        "/api/v1/strategies": {"get": {}},
        "/api/v1/strategy-overview": {"get": {}},
        "/api/v1/draw-imports/preview": {"post": {}},
        "/api/v1/draw-imports/commit": {"post": {}},
        "/api/v1/draws": {"get": {}},
        "/api/v1/draws/{lottery_type}/{draw_number}": {"get": {}},
        "/api/v1/ingestion-runs": {"get": {}},
        "/api/v1/ingestion-runs/{run_id}": {"get": {}},
    }


@pytest.mark.parametrize(
    ("path", "path_item"),
    [
        (
            "/api/v1/referenced-path-item",
            {"$ref": "#/components/pathItems/AdditionalOperation"},
        ),
        (
            "/api/v1/strategies",
            {
                "get": {},
                "$ref": "#/components/pathItems/AdditionalOperation",
            },
        ),
    ],
    ids=("reference-alone", "reference-beside-approved-operation"),
)
def test_smoke_rejects_path_item_references(
    path: str, path_item: dict[str, object]
) -> None:
    paths = authorized_openapi_paths()
    paths[path] = path_item
    payload: dict[str, object] = {
        "paths": paths,
        "components": {
            "pathItems": {
                "AdditionalOperation": {"post": {}},
            }
        },
    }

    with pytest.raises(LocalRuntimeSafetyError, match="Path Item references"):
        validate_openapi_payload(payload)


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/health", "get"),
        ("/api/v1/strategies", "get"),
        ("/api/v1/strategy-overview", "get"),
        ("/api/v1/draw-imports/preview", "post"),
        ("/api/v1/draw-imports/commit", "post"),
        ("/api/v1/draws", "get"),
        ("/api/v1/draws/{lottery_type}/{draw_number}", "get"),
        ("/api/v1/ingestion-runs", "get"),
        ("/api/v1/ingestion-runs/{run_id}", "get"),
    ],
)
def test_smoke_rejects_each_missing_required_openapi_operation(path: str, method: str) -> None:
    paths = authorized_openapi_paths()
    del paths[path][method]

    with pytest.raises(LocalRuntimeSafetyError, match="exact approved surface"):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    ("path", "method", "message"),
    [
        ("/api/v1/strategies/", "get", "unapproved local runtime path"),
        ("/API/v1/strategies", "get", "unapproved local runtime path"),
        ("/api/v1/strategies", "GET", "duplicate or malformed"),
        ("/api/v1/strategies", "fetch", "duplicate or malformed"),
        ("/api/v1/strategy-overview/", "get", "unapproved local runtime path"),
        ("/API/v1/strategy-overview", "get", "unapproved local runtime path"),
    ],
)
def test_smoke_rejects_openapi_alias_case_and_malformed_operations(
    path: str, method: str, message: str
) -> None:
    paths = authorized_openapi_paths()
    approved_path = (
        "/api/v1/strategy-overview"
        if "strategy-overview" in path.casefold()
        else "/api/v1/strategies"
    )
    if path == approved_path:
        paths[path] = {method: {}}
    else:
        del paths[approved_path]
        paths[path] = {method: {}}

    with pytest.raises(LocalRuntimeSafetyError, match=message):
        validate_openapi_payload({"paths": paths})


def test_smoke_rejects_malformed_openapi_operation_object() -> None:
    paths = authorized_openapi_paths()
    paths["/api/v1/strategies"] = {"get": []}

    with pytest.raises(LocalRuntimeSafetyError, match="must be a string-keyed object"):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    ("path", "method", "message"),
    [
        ("/api/v1/unknown", "post", "unapproved local runtime path"),
        ("/api/v1/strategies", "post", "unapproved method/path"),
        ("/api/v1/strategy-overview", "post", "unapproved method/path"),
        ("/api/v1/generation", "post", "generation or execution"),
        ("/api/v1/prediction", "post", "generation or execution"),
    ],
)
def test_smoke_rejects_unknown_or_executable_openapi_operations(
    path: str, method: str, message: str
) -> None:
    with pytest.raises(LocalRuntimeSafetyError, match=message):
        validate_openapi_payload({"paths": {path: {method: {}}}})


def test_smoke_rejects_generation_or_mutating_openapi_paths() -> None:
    with pytest.raises(LocalRuntimeSafetyError, match="generation or execution"):
        validate_openapi_payload({"paths": {"/api/v1/generate": {"get": {}}}})
    with pytest.raises(LocalRuntimeSafetyError, match="unapproved method/path"):
        validate_openapi_payload({"paths": {"/api/v1/strategies": {"post": {}}}})


def test_listener_value_is_plain_identity_data() -> None:
    assert Listener(pid=42, address="127.0.0.1:8000") == Listener(pid=42, address="127.0.0.1:8000")
