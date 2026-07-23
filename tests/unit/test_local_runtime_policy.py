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
            "lifecycle_status": "ONLINE",
            "executable": True,
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
    assert "lottolab.interfaces.api.local_app:create_local_app" in backend
    assert "lottolab.interfaces.api.app:create_app" not in backend
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
        direct[0]["lifecycle_status"] = "OBSERVATION"
        proxied[0]["lifecycle_status"] = "OBSERVATION"
    elif mutation == "executable":
        direct[0]["executable"] = False
        proxied[0]["executable"] = False
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
        "/api/v1/generate-bet": {"post": {}},
        "/api/v1/live-zone-split-bets": {"post": {}},
        "/api/v1/historical-results/runs": {"get": {}},
        "/api/v1/historical-results/runs/{run_id}/strategies": {"get": {}},
        "/api/v1/historical-results/runs/{run_id}/replay": {"get": {}},
        "/api/v1/historical-results/portfolios/{portfolio_id}": {"get": {}},
        "/api/v1/historical-prefix-analytics/rankings": {"get": {}},
        "/api/v1/historical-prefix-analytics/strategies": {"get": {}},
        (
            "/api/v1/historical-prefix-analytics/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/replay"
        ): {"get": {}},
        "/api/v1/historical-prefix-success-windows": {"get": {}},
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}"
        ): {"get": {}},
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/matrix"
        ): {"get": {}},
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts"
        ): {"get": {}},
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics"
        ): {"get": {}},
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "cross-import-concordance"
        ): {"get": {}},
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "multi-import-concordance-census"
        ): {"get": {}},
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "temporal-holdout"
        ): {"get": {}},
        "/api/v1/replay-rankings/optimal": {"get": {}},
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}": {"get": {}},
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions": {
            "get": {}
        },
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates": {
            "get": {}
        },
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate": {
            "get": {}
        },
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
        ("/api/v1/generate-bet", "post"),
        ("/api/v1/live-zone-split-bets", "post"),
        ("/api/v1/historical-results/runs", "get"),
        ("/api/v1/historical-results/runs/{run_id}/strategies", "get"),
        ("/api/v1/historical-results/runs/{run_id}/replay", "get"),
        ("/api/v1/historical-results/portfolios/{portfolio_id}", "get"),
        ("/api/v1/historical-prefix-analytics/rankings", "get"),
        ("/api/v1/historical-prefix-analytics/strategies", "get"),
        (
            "/api/v1/historical-prefix-analytics/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/replay",
            "get",
        ),
        ("/api/v1/historical-prefix-success-windows", "get"),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}",
            "get",
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/matrix",
            "get",
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts",
            "get",
        ),
        ("/api/v1/replay-rankings/optimal", "get"),
        ("/api/v1/replay-scoring/{scoring_artifact_payload_sha256}", "get"),
        (
            "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions",
            "get",
        ),
        (
            "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates",
            "get",
        ),
        (
            "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate",
            "get",
        ),
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


def test_smoke_accepts_exact_approved_generate_bet_operation() -> None:
    validate_openapi_payload({"paths": authorized_openapi_paths()})


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_smoke_rejects_non_post_methods_on_generate_bet(method: str) -> None:
    paths = authorized_openapi_paths()
    paths["/api/v1/generate-bet"] = {method: {}}

    with pytest.raises(LocalRuntimeSafetyError, match="unapproved method/path"):
        validate_openapi_payload({"paths": paths})


def test_smoke_rejects_other_paths_containing_generate_word() -> None:
    paths = authorized_openapi_paths()
    paths["/api/v1/generate-bet-extra"] = {"post": {}}

    with pytest.raises(LocalRuntimeSafetyError, match="generation or execution"):
        validate_openapi_payload({"paths": paths})


def test_smoke_accepts_exact_approved_historical_results_replay_operation() -> None:
    """BLHQ R2: the read-only /replay projection path is the second narrow exception."""
    validate_openapi_payload({"paths": authorized_openapi_paths()})


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_smoke_rejects_non_get_methods_on_historical_results_replay(method: str) -> None:
    paths = authorized_openapi_paths()
    paths["/api/v1/historical-results/runs/{run_id}/replay"] = {method: {}}

    with pytest.raises(LocalRuntimeSafetyError, match="unapproved method/path"):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/replay",
        "/api/v1/replay/execute",
        "/api/v1/historical-results/replay/execute",
    ],
)
def test_smoke_rejects_unrelated_replay_or_execute_paths(path: str) -> None:
    """Only the two named exceptions bypass the forbidden-word screen; every other
    path containing "replay" or "execute" -- including near-miss historical-results
    paths -- must still fail closed."""
    with pytest.raises(LocalRuntimeSafetyError, match="generation or execution"):
        validate_openapi_payload({"paths": {path: {"get": {}}}})


def test_smoke_accepts_exact_approved_replay_portfolio_ranking_operation() -> None:
    """The read-only /replay-rankings/optimal path is the third narrow exception."""
    validate_openapi_payload({"paths": authorized_openapi_paths()})


def test_smoke_accepts_exact_historical_prefix_operations() -> None:
    paths = authorized_openapi_paths()
    historical_prefix_paths = {
        "/api/v1/historical-prefix-analytics/rankings",
        "/api/v1/historical-prefix-analytics/strategies",
        (
            "/api/v1/historical-prefix-analytics/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/replay"
        ),
    }

    assert {path for path in paths if path.startswith(
        "/api/v1/historical-prefix-analytics"
    )} == historical_prefix_paths
    assert all(paths[path] == {"get": {}} for path in historical_prefix_paths)
    validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_smoke_rejects_mutating_historical_prefix_methods(method: str) -> None:
    paths = authorized_openapi_paths()
    paths["/api/v1/historical-prefix-analytics/rankings"] = {method: {}}

    with pytest.raises(LocalRuntimeSafetyError, match="unapproved method/path"):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/historical-prefix-analytics/replay",
        "/api/v1/historical-prefix-analytics/strategies/latest",
        "/api/v1/historical-prefix-analytics/strategies/default",
        "/api/v1/historical-prefix-analytics/strategies/fallback",
        "/api/v1/historical-prefix-analytics/strategies/{strategy_id}/replay",
        (
            "/api/v1/historical-prefix-analytics/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/execute"
        ),
    ],
)
def test_smoke_rejects_historical_prefix_near_miss_paths(path: str) -> None:
    paths = authorized_openapi_paths()
    paths[path] = {"get": {}}

    with pytest.raises(LocalRuntimeSafetyError):
        validate_openapi_payload({"paths": paths})


def test_smoke_admits_exactly_eight_historical_prefix_success_window_gets() -> None:
    paths = authorized_openapi_paths()
    expected = {
        "/api/v1/historical-prefix-success-windows",
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/matrix"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "cross-import-concordance"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "temporal-holdout"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "multi-import-concordance-census"
        ),
    }

    assert {
        path
        for path in paths
        if path.startswith("/api/v1/historical-prefix-success-windows")
    } == expected
    assert all(paths[path] == {"get": {}} for path in expected)
    validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/historical-prefix-success-windows",
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/matrix"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics"
        ),
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "temporal-holdout"
        ),
    ],
)
def test_smoke_rejects_mutating_historical_prefix_success_window_methods(
    path: str, method: str
) -> None:
    paths = authorized_openapi_paths()
    paths[path] = {method: {}}

    with pytest.raises(LocalRuntimeSafetyError, match="unapproved method/path"):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/historical-prefix-success-windows/latest",
        "/api/v1/historical-prefix-success-windows/default",
        "/api/v1/historical-prefix-success-windows/fallback",
        "/api/v1/historical-prefix-success-windows/strategies/latest",
        "/api/v1/historical-prefix-success-windows/strategies/default",
        "/api/v1/historical-prefix-success-windows/execute",
        "/api/v1/historical-prefix-success-windows/promote",
    ],
)
def test_smoke_rejects_historical_prefix_success_window_near_misses(path: str) -> None:
    paths = authorized_openapi_paths()
    paths[path] = {"get": {}}

    with pytest.raises(LocalRuntimeSafetyError):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_smoke_rejects_non_get_methods_on_replay_portfolio_ranking(method: str) -> None:
    paths = authorized_openapi_paths()
    paths["/api/v1/replay-rankings/optimal"] = {method: {}}

    with pytest.raises(LocalRuntimeSafetyError, match="unapproved method/path"):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/replay-rankings/execute",
        "/api/v1/replay-rankings/optimize",
        "/api/v1/replay-ranking/optimal",
        "/api/v1/replay-rankings/optimal/run",
    ],
)
def test_smoke_rejects_replay_portfolio_ranking_near_miss_paths(path: str) -> None:
    """Only the exact approved path bypasses the forbidden-word screen; near
    misses -- wrong verb, wrong singular/plural, an extra path segment -- still
    fail closed, with no prefix or wildcard exception."""
    with pytest.raises(LocalRuntimeSafetyError, match="generation or execution"):
        validate_openapi_payload({"paths": {path: {"get": {}}}})


def test_smoke_accepts_all_exact_replay_scoring_get_operations_together() -> None:
    paths = authorized_openapi_paths()
    replay_scoring_paths = {
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate",
    }

    assert {path for path in paths if path.startswith("/api/v1/replay-scoring/")} == (
        replay_scoring_paths
    )
    assert all(paths[path] == {"get": {}} for path in replay_scoring_paths)
    validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate",
    ],
)
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_smoke_rejects_mutating_methods_on_each_replay_scoring_path(
    path: str, method: str
) -> None:
    paths = authorized_openapi_paths()
    paths[path] = {method: {}}

    with pytest.raises(LocalRuntimeSafetyError, match="unapproved method/path"):
        validate_openapi_payload({"paths": paths})


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/replay-scoring",
        "/api/v1/replay-scoring/latest",
        "/api/v1/replay-scoring/{sha}",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/execute",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/prediction",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregate",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions/",
    ],
)
def test_smoke_rejects_replay_scoring_near_miss_paths(path: str) -> None:
    with pytest.raises(LocalRuntimeSafetyError, match="generation or execution"):
        validate_openapi_payload({"paths": {path: {"get": {}}}})


def test_listener_value_is_plain_identity_data() -> None:
    assert Listener(pid=42, address="127.0.0.1:8000") == Listener(pid=42, address="127.0.0.1:8000")
