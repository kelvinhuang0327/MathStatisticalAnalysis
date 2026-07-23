"""Policy and validated state for the DB-free local runtime controller."""

from __future__ import annotations

import os
import re
import stat
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

LOCAL_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
HEALTH_PATH = "/api/health"
STRATEGY_CATALOG_PATH = "/api/v1/strategies"
OPENAPI_PATH = "/openapi.json"
EXPECTED_STRATEGY_IDS = (
    "biglotto_social_wisdom_anti_popularity",
    "biglotto_zone_split_3bet_bet1",
    "biglotto_deviation_2bet",
)
EXECUTABLE_STRATEGY_IDS = frozenset(EXPECTED_STRATEGY_IDS)
STATE_VERSION = 2
_TOKEN_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_GIT_OBJECT_ID_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_FORBIDDEN_ROUTE_WORDS = (
    "backfill",
    "evaluation",
    "execute",
    "generate",
    "generation",
    "optimizer",
    "prediction",
    "replay",
    "scheduler",
    "training",
)
_ALLOWED_OPENAPI_OPERATIONS = {
    "/api/health": frozenset({"get"}),
    "/api/v1/strategies": frozenset({"get"}),
    "/api/v1/strategy-overview": frozenset({"get"}),
    "/api/v1/draw-imports/preview": frozenset({"post"}),
    "/api/v1/draw-imports/commit": frozenset({"post"}),
    "/api/v1/draws": frozenset({"get"}),
    "/api/v1/draws/{lottery_type}/{draw_number}": frozenset({"get"}),
    "/api/v1/ingestion-runs": frozenset({"get"}),
    "/api/v1/ingestion-runs/{run_id}": frozenset({"get"}),
    "/api/v1/generate-bet": frozenset({"post"}),
    "/api/v1/live-zone-split-bets": frozenset({"post"}),
    "/api/v1/historical-results/runs": frozenset({"get"}),
    "/api/v1/historical-results/runs/{run_id}/strategies": frozenset({"get"}),
    "/api/v1/historical-results/runs/{run_id}/replay": frozenset({"get"}),
    "/api/v1/historical-results/portfolios/{portfolio_id}": frozenset({"get"}),
    "/api/v1/historical-prefix-analytics/rankings": frozenset({"get"}),
    "/api/v1/historical-prefix-analytics/strategies": frozenset({"get"}),
    (
        "/api/v1/historical-prefix-analytics/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/replay"
    ): frozenset({"get"}),
    "/api/v1/historical-prefix-success-windows": frozenset({"get"}),
    (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}"
    ): frozenset({"get"}),
    (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/matrix"
    ): frozenset({"get"}),
    (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts"
    ): frozenset({"get"}),
    "/api/v1/replay-rankings/optimal": frozenset({"get"}),
    "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}": frozenset({"get"}),
    "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions": frozenset(
        {"get"}
    ),
    "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates": (
        frozenset({"get"})
    ),
    "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate": frozenset(
        {"get"}
    ),
}
_FORBIDDEN_ROUTE_WORD_EXCEPTION_PATHS = frozenset(
    {
        "/api/v1/generate-bet",
        "/api/v1/historical-results/runs/{run_id}/replay",
        (
            "/api/v1/historical-prefix-analytics/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/replay"
        ),
        "/api/v1/replay-rankings/optimal",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate",
    }
)
"""The narrow, approved paths exempt from the forbidden-word screen.

``/api/v1/generate-bet`` is the one approved execution path.
``/api/v1/historical-results/runs/{run_id}/replay`` is a read-only projection
view over an already-committed historical-results portfolio (BLHQ R2) — it
never consumes or modifies Replay's ``DrawHistoryReader`` and executes no
strategy, but its path segment happens to contain the forbidden word
"replay". ``/api/v1/replay-rankings/optimal`` is a read-only, strictly
post-hoc ranking over an already-validated ``ReplayScoringArtifact`` — it
generates no numbers, executes no strategy, and persists nothing, but its
path segment likewise contains "replay". The four exact
``/api/v1/replay-scoring/{scoring_artifact_payload_sha256}`` paths are GET-only
queries over saved Replay-scoring projections. They execute no strategy,
generate no numbers, perform no rescoring, write no database state, and offer
no latest or fallback selection. The Historical Prefix strategy replay path is
also a GET-only projection over one exact strategy identity. Only the exact
paths above are exempted;
every other path containing a forbidden word (including
"/api/v1/generate", "/api/v1/generation", "/api/v1/replay-rankings/execute",
and "/api/v1/replay-rankings/optimize") is still rejected, and the
exact-operation-set check below still fails closed on method or path drift.
"""
_ALLOWED_OPENAPI_OPERATION_SET = frozenset(
    (method, path) for path, methods in _ALLOWED_OPENAPI_OPERATIONS.items() for method in methods
)
_HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
_OPENAPI_PATH_ITEM_FIELDS = frozenset({"summary", "description", "servers", "parameters"})


class LocalRuntimeError(RuntimeError):
    """A local runtime operation could not complete."""


class LocalRuntimeSafetyError(LocalRuntimeError):
    """A fail-closed ownership, state, or network check failed."""


class ConcurrentLocalRuntimeOperation(LocalRuntimeSafetyError):
    """Another controller operation currently holds the runtime lock."""


class ServiceRole(StrEnum):
    BACKEND = "backend"
    FRONTEND = "frontend"

    @property
    def port(self) -> int:
        return BACKEND_PORT if self is ServiceRole.BACKEND else FRONTEND_PORT


class Ownership(StrEnum):
    OWNED = "owned"
    DEAD = "dead"
    MISMATCH = "mismatch"


class RuntimeStatusKind(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    PARTIAL = "partial"
    STALE = "stale"
    FOREIGN = "foreign"


@dataclass(frozen=True)
class ProcessIdentity:
    role: ServiceRole
    pid: int
    pgid: int
    port: int
    start_marker: str
    command_line: str
    log_path: str

    def __post_init__(self) -> None:
        if isinstance(self.pid, bool) or self.pid <= 1:
            raise LocalRuntimeSafetyError("process PID must be greater than one")
        if isinstance(self.pgid, bool) or self.pgid != self.pid:
            raise LocalRuntimeSafetyError("launcher must be its process-group leader")
        if self.port != self.role.port:
            raise LocalRuntimeSafetyError("service role and port do not match")
        if not self.start_marker.strip() or not self.command_line.strip():
            raise LocalRuntimeSafetyError("process identity is incomplete")
        if not Path(self.log_path).is_absolute():
            raise LocalRuntimeSafetyError("process log path must be absolute")

    def to_object(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "pid": self.pid,
            "pgid": self.pgid,
            "port": self.port,
            "start_marker": self.start_marker,
            "command_line": self.command_line,
            "log_path": self.log_path,
        }

    @classmethod
    def from_object(cls, value: object) -> ProcessIdentity:
        record = _object_mapping(value, "process identity")
        _require_exact_keys(
            record,
            {"role", "pid", "pgid", "port", "start_marker", "command_line", "log_path"},
            "process identity",
        )
        try:
            role = ServiceRole(_required_string(record, "role"))
        except ValueError as exc:
            raise LocalRuntimeSafetyError("process identity has an unknown role") from exc
        return cls(
            role=role,
            pid=_required_integer(record, "pid"),
            pgid=_required_integer(record, "pgid"),
            port=_required_integer(record, "port"),
            start_marker=_required_string(record, "start_marker"),
            command_line=_required_string(record, "command_line"),
            log_path=_required_string(record, "log_path"),
        )


@dataclass(frozen=True)
class RuntimeState:
    repository_root: str
    source_commit: str
    ownership_token: str
    created_at_ns: int
    services: tuple[ProcessIdentity, ...]
    state_version: int = STATE_VERSION

    def __post_init__(self) -> None:
        repository = Path(self.repository_root)
        if not repository.is_absolute():
            raise LocalRuntimeSafetyError("runtime repository path must be absolute")
        validate_git_object_id(self.source_commit)
        if not _TOKEN_PATTERN.fullmatch(self.ownership_token):
            raise LocalRuntimeSafetyError("runtime ownership token is invalid")
        if isinstance(self.created_at_ns, bool) or self.created_at_ns <= 0:
            raise LocalRuntimeSafetyError("runtime creation timestamp is invalid")
        if self.state_version != STATE_VERSION:
            raise LocalRuntimeSafetyError("unsupported runtime state version")
        if not self.services:
            raise LocalRuntimeSafetyError("runtime state must contain at least one service")

        roles = [service.role for service in self.services]
        if len(set(roles)) != len(roles):
            raise LocalRuntimeSafetyError("runtime state contains duplicate service roles")
        if ServiceRole.FRONTEND in roles and ServiceRole.BACKEND not in roles:
            raise LocalRuntimeSafetyError("frontend state cannot exist without backend state")

        for service in self.services:
            command = service.command_line
            required_fragments = (
                self.repository_root,
                self.ownership_token,
                f"--role {service.role.value}",
                f"--source-commit {self.source_commit}",
            )
            if not all(fragment in command for fragment in required_fragments):
                raise LocalRuntimeSafetyError(
                    f"{service.role.value} command does not prove repository ownership"
                )

    def service(self, role: ServiceRole) -> ProcessIdentity | None:
        return next((service for service in self.services if service.role is role), None)

    def with_service(self, identity: ProcessIdentity) -> RuntimeState:
        retained = tuple(service for service in self.services if service.role is not identity.role)
        ordered = tuple(
            service
            for role in (ServiceRole.BACKEND, ServiceRole.FRONTEND)
            for service in (*retained, identity)
            if service.role is role
        )
        return RuntimeState(
            repository_root=self.repository_root,
            source_commit=self.source_commit,
            ownership_token=self.ownership_token,
            created_at_ns=self.created_at_ns,
            services=ordered,
        )

    def to_object(self) -> dict[str, object]:
        return {
            "state_version": self.state_version,
            "repository_root": self.repository_root,
            "source_commit": self.source_commit,
            "ownership_token": self.ownership_token,
            "created_at_ns": self.created_at_ns,
            "services": [service.to_object() for service in self.services],
        }

    @classmethod
    def from_object(cls, value: object) -> RuntimeState:
        record = _object_mapping(value, "runtime state")
        _require_exact_keys(
            record,
            {
                "state_version",
                "repository_root",
                "source_commit",
                "ownership_token",
                "created_at_ns",
                "services",
            },
            "runtime state",
        )
        raw_services = record["services"]
        if not isinstance(raw_services, list):
            raise LocalRuntimeSafetyError("runtime services must be a list")
        service_values = cast(list[object], raw_services)
        return cls(
            state_version=_required_integer(record, "state_version"),
            repository_root=_required_string(record, "repository_root"),
            source_commit=_required_string(record, "source_commit"),
            ownership_token=_required_string(record, "ownership_token"),
            created_at_ns=_required_integer(record, "created_at_ns"),
            services=tuple(ProcessIdentity.from_object(item) for item in service_values),
        )


@dataclass(frozen=True)
class LocalRuntimePolicy:
    repository_root: Path
    runtime_dir: Path

    @classmethod
    def for_repository(
        cls, repository_root: Path, *, runtime_dir: Path | None = None
    ) -> LocalRuntimePolicy:
        root = repository_root.resolve(strict=True)
        requested_runtime = (
            runtime_dir
            if runtime_dir is not None
            else Path(tempfile.gettempdir()).resolve(strict=True) / f"lottolab-local-{os.getuid()}"
        )
        selected_runtime = _canonical_runtime_directory(requested_runtime)
        if selected_runtime == root or root in selected_runtime.parents:
            raise LocalRuntimeSafetyError("runtime directory must be outside the repository")
        return cls(repository_root=root, runtime_dir=selected_runtime)

    @property
    def state_path(self) -> Path:
        return self.runtime_dir / "state.json"

    @property
    def lock_path(self) -> Path:
        return self.runtime_dir / "controller.lock"

    def log_path(self, role: ServiceRole) -> Path:
        return self.runtime_dir / f"{role.value}.log"

    def initial_state(
        self, token: str, source_commit: str, identity: ProcessIdentity
    ) -> RuntimeState:
        return RuntimeState(
            repository_root=str(self.repository_root),
            source_commit=source_commit,
            ownership_token=token,
            created_at_ns=time.time_ns(),
            services=(identity,),
        )

    def backend_command(self, uv_executable: str, token: str) -> tuple[str, ...]:
        return (
            uv_executable,
            "run",
            "--no-sync",
            "uvicorn",
            "--factory",
            "lottolab.interfaces.api.local_app:create_local_app",
            "--app-dir",
            str(self.repository_root / "src"),
            "--host",
            LOCAL_HOST,
            "--port",
            str(BACKEND_PORT),
            "--header",
            f"X-LottoLab-Owner:{token}",
            "--no-access-log",
            "--log-level",
            "warning",
        )

    def frontend_command(self, node_executable: str) -> tuple[str, ...]:
        frontend = self.repository_root / "frontend"
        return (
            node_executable,
            str(frontend / "node_modules" / "vite" / "bin" / "vite.js"),
            "--host",
            LOCAL_HOST,
            "--port",
            str(FRONTEND_PORT),
            "--strictPort",
            "--config",
            str(frontend / "vite.config.ts"),
        )

    def launcher_command(
        self,
        *,
        python_executable: str,
        role: ServiceRole,
        token: str,
        source_commit: str,
        child_command: Sequence[str],
    ) -> tuple[str, ...]:
        working_directory = (
            self.repository_root
            if role is ServiceRole.BACKEND
            else self.repository_root / "frontend"
        )
        return (
            python_executable,
            "-m",
            "lottolab.infrastructure.local_runtime",
            "_launch",
            "--role",
            role.value,
            "--token",
            token,
            "--repository",
            str(self.repository_root),
            "--source-commit",
            source_commit,
            "--cwd",
            str(working_directory),
            "--",
            *child_command,
        )


@dataclass(frozen=True)
class Listener:
    pid: int
    address: str


@dataclass(frozen=True)
class RuntimeStatus:
    kind: RuntimeStatusKind
    ownership_proven: bool
    backend: str
    frontend: str
    detail: str


@dataclass(frozen=True)
class SmokeReport:
    strategy_ids: tuple[str, ...]
    backend_url: str
    frontend_url: str


def validate_health_payload(payload: object) -> None:
    record = _object_mapping(payload, "health response")
    if record != {"status": "ok", "api_version": "v1"}:
        raise LocalRuntimeSafetyError("backend health payload is not the expected DB-free API")


def validate_strategy_payloads(direct: object, proxied: object) -> tuple[str, ...]:
    if direct != proxied:
        raise LocalRuntimeSafetyError("direct and proxied Strategy Catalog responses differ")
    if not isinstance(direct, list):
        raise LocalRuntimeSafetyError("Strategy Catalog response must be a list")

    items = cast(list[object], direct)
    records = [_object_mapping(item, "strategy record") for item in items]
    ids = tuple(_required_string(record, "strategy_id") for record in records)
    if ids != EXPECTED_STRATEGY_IDS:
        raise LocalRuntimeSafetyError("Strategy Catalog IDs or deterministic order changed")
    for record in records:
        strategy_id = _required_string(record, "strategy_id")
        executable = strategy_id in EXECUTABLE_STRATEGY_IDS
        expected_status = "ONLINE" if executable else "OBSERVATION"
        if record.get("lifecycle_status") != expected_status:
            raise LocalRuntimeSafetyError(
                f"{strategy_id} must report lifecycle_status={expected_status}"
            )
        if record.get("executable") is not executable:
            raise LocalRuntimeSafetyError(f"{strategy_id} must report executable={executable}")
        if any(word in str(key).lower() for key in record for word in _FORBIDDEN_ROUTE_WORDS):
            raise LocalRuntimeSafetyError("Strategy Catalog exposed an execution control field")
    return ids


def validate_openapi_payload(payload: object) -> None:
    document = _object_mapping(payload, "OpenAPI response")
    paths = _object_mapping(document.get("paths"), "OpenAPI paths")
    operation_set: set[tuple[str, str]] = set()
    for path, raw_operations in paths.items():
        operations = _object_mapping(raw_operations, f"OpenAPI operations for {path}")
        if "$ref" in operations:
            raise LocalRuntimeSafetyError("OpenAPI Path Item references are not supported")
        lowered_path = path.lower()
        if path not in _FORBIDDEN_ROUTE_WORD_EXCEPTION_PATHS and any(
            word in lowered_path for word in _FORBIDDEN_ROUTE_WORDS
        ):
            raise LocalRuntimeSafetyError("OpenAPI exposes a generation or execution path")
        allowed_methods = _ALLOWED_OPENAPI_OPERATIONS.get(path)
        if allowed_methods is None:
            raise LocalRuntimeSafetyError("OpenAPI exposes an unapproved local runtime path")
        normalized_methods: set[str] = set()
        for method, operation in operations.items():
            normalized_method = method.casefold()
            if normalized_method in _HTTP_METHODS:
                if method != normalized_method or normalized_method in normalized_methods:
                    raise LocalRuntimeSafetyError(
                        "OpenAPI contains a duplicate or malformed operation declaration"
                    )
                normalized_methods.add(normalized_method)
                _object_mapping(operation, f"OpenAPI operation {method} {path}")
                if normalized_method not in allowed_methods:
                    raise LocalRuntimeSafetyError(
                        "OpenAPI exposes an unapproved method/path operation"
                    )
                operation_set.add((normalized_method, path))
            elif method not in _OPENAPI_PATH_ITEM_FIELDS and not method.startswith("x-"):
                raise LocalRuntimeSafetyError(
                    "OpenAPI contains a duplicate or malformed operation declaration"
                )

    if frozenset(operation_set) != _ALLOWED_OPENAPI_OPERATION_SET:
        raise LocalRuntimeSafetyError(
            "OpenAPI operation set does not match the exact approved surface"
        )


def validate_frontend_document(body: bytes) -> None:
    try:
        document = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LocalRuntimeSafetyError("frontend root is not UTF-8") from exc
    if '<div id="app"></div>' not in document:
        raise LocalRuntimeSafetyError("frontend root is not the LottoLab Vite application")


def validate_git_object_id(value: str) -> None:
    """Require an unabbreviated SHA-1 or SHA-256 Git object identifier."""
    if not _GIT_OBJECT_ID_PATTERN.fullmatch(value):
        raise LocalRuntimeSafetyError("runtime source commit is not a full Git object ID")


def _canonical_runtime_directory(requested: Path) -> Path:
    expanded = requested.expanduser()
    if ".." in expanded.parts:
        raise LocalRuntimeSafetyError("runtime directory traversal is not allowed")
    absolute = expanded if expanded.is_absolute() else Path.cwd() / expanded
    if absolute == Path(absolute.anchor):
        raise LocalRuntimeSafetyError("runtime directory cannot be the filesystem root")

    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as exc:
            raise LocalRuntimeSafetyError(
                f"cannot inspect runtime directory component: {exc}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise LocalRuntimeSafetyError("runtime directory cannot have a symlinked component")
        if not stat.S_ISDIR(metadata.st_mode):
            raise LocalRuntimeSafetyError(
                "runtime directory path contains a non-directory component"
            )
    return absolute.resolve(strict=False)


def _object_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise LocalRuntimeSafetyError(f"{label} must be a string-keyed object")
    record = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in record):
        raise LocalRuntimeSafetyError(f"{label} must be a string-keyed object")
    return cast(Mapping[str, object], record)


def _require_exact_keys(record: Mapping[str, object], keys: set[str], label: str) -> None:
    actual = set(record)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise LocalRuntimeSafetyError(
            f"{label} keys are invalid (missing={missing!r}, extra={extra!r})"
        )


def _required_string(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise LocalRuntimeSafetyError(f"{key} must be a non-empty string")
    return value


def _required_integer(record: Mapping[str, object], key: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise LocalRuntimeSafetyError(f"{key} must be an integer")
    return value
