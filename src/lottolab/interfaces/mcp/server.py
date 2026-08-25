"""Minimal stdio MCP adapter for LottoLab's read-only query service.

The transport is intentionally local and stdio-only in R1.  The adapter never
accepts a database path, SQL text, filesystem path, or execution command from
the MCP client.  Its only data sources are authorities resolved by the
canonical storage registry; unresolved authorities are not promoted by MCP.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import IO, cast

from lottolab import __version__
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessCriterion,
)
from lottolab.application.lottolab_mcp import (
    EVIDENCE_UNAVAILABLE,
    INVALID_ARGUMENTS,
    SCHEMA_MISMATCH,
    STORAGE_UNAVAILABLE,
    LottoLabMcpQueryError,
    LottoLabMcpQueryService,
    ReadOnlyAuthorityDescriptor,
    ReadOnlyHistoricalSources,
)
from lottolab.application.ports import (
    DrawDataRepository,
    HistoricalResultQueryRepository,
    P638CurrentRankingQueryRepository,
    P638HistoricalQueryRepository,
    T539HistoricalQueryRepository,
)
from lottolab.domain.strategy_success_evaluation import WindowKind
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    PackagedB649MultiTicketRecordReader,
)
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
)
from lottolab.infrastructure.persistence.historical_schema import (
    verify_schema_read_only,
)
from lottolab.infrastructure.persistence.p638_base_data_repositories import (
    SQLiteP638BaseDataQueryRepository,
)
from lottolab.infrastructure.persistence.p638_current_ranking_repositories import (
    SQLiteP638CurrentRankingQueryRepository,
)
from lottolab.infrastructure.persistence.p638_historical_repositories import (
    SQLiteP638HistoricalQueryRepository,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.infrastructure.persistence.storage_authorities import (
    StorageAuthorityError,
    StorageAuthorityRegistry,
    StorageAuthorityResolver,
)
from lottolab.infrastructure.persistence.t539_historical_repositories import (
    SQLiteT539HistoricalQueryRepository,
)
from lottolab.strategies.catalog import production_catalog

HISTORICAL_RESULTS_DB_ENV = "LOTTOLAB_HISTORICAL_RESULTS_DB"
_SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def _json_schema(*, required: tuple[str, ...], properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": properties,
    }


def _tool_definitions() -> tuple[dict[str, object], ...]:
    lottery_type = {
        "type": "string",
        "description": "Exact canonical LottoLab lottery type; aliases are not accepted.",
    }
    authority = {
        "type": "string",
        "description": "Exact run_id or import identity; required when authorities compete.",
    }
    strategy_id = {"type": "string", "minLength": 1}
    window = {
        "type": "string",
        "enum": [
            item.value
            for item in WindowKind
        ]
        + ["FULL", "LONG_750", "MEDIUM_300", "SHORT_50", "RECENT_750", "RECENT_300", "RECENT_50"],
    }
    criterion = {
        "type": "string",
        "enum": [
            *(item.value for item in HistoricalPrefixSuccessCriterion),
            "ANY_OFFICIAL_PRIZE",
        ],
    }
    return (
        {
            "name": "list_lottery_types",
            "description": (
                "List canonical LottoLab lottery types and observed read-only capabilities."
            ),
            "inputSchema": _json_schema(required=(), properties={}),
        },
        {
            "name": "list_historical_runs",
            "description": (
                "List every completed historical authority for one canonical lottery type."
            ),
            "inputSchema": _json_schema(
                required=("lottery_type",),
                properties={
                    "lottery_type": lottery_type,
                    "strategy_id": strategy_id,
                    "status": {"type": "string", "enum": ["COMPLETED"]},
                    "authority": authority,
                },
            ),
        },
        {
            "name": "get_strategy_window_ranking",
            "description": (
                "Rank persisted strategy replay evidence for one canonical window and criterion."
            ),
            "inputSchema": _json_schema(
                required=("lottery_type", "window", "criterion"),
                properties={
                    "lottery_type": lottery_type,
                    "window": window,
                    "criterion": criterion,
                    "authority": authority,
                },
            ),
        },
        {
            "name": "get_strategy_replay_summary",
            "description": (
                "Return aggregate historical replay evidence without dumping raw replay rows."
            ),
            "inputSchema": _json_schema(
                required=("lottery_type", "strategy_id"),
                properties={
                    "lottery_type": lottery_type,
                    "strategy_id": strategy_id,
                    "authority": authority,
                },
            ),
        },
        {
            "name": "get_strategy_match_summary",
            "description": (
                "Summarize exact and threshold main-number matches with draw and ticket "
                "counts separate."
            ),
            "inputSchema": _json_schema(
                required=("lottery_type", "strategy_id"),
                properties={
                    "lottery_type": lottery_type,
                    "strategy_id": strategy_id,
                    "min_main_matches": {"type": "integer", "minimum": 0, "default": 4},
                    "authority": authority,
                },
            ),
        },
        {
            "name": "get_strategies_by_match_threshold",
            "description": "Search all persisted strategies for a main-match threshold query.",
            "inputSchema": _json_schema(
                required=("lottery_type", "min_main_matches"),
                properties={
                    "lottery_type": lottery_type,
                    "min_main_matches": {"type": "integer", "minimum": 0},
                    "authority": authority,
                    "window": window,
                },
            ),
        },
        {
            "name": "get_strategy_best_prize",
            "description": (
                "Return the highest observed official prize using the canonical lottery evaluator."
            ),
            "inputSchema": _json_schema(
                required=("lottery_type", "strategy_id"),
                properties={
                    "lottery_type": lottery_type,
                    "strategy_id": strategy_id,
                    "authority": authority,
                },
            ),
        },
        {
            "name": "get_draw",
            "description": "Return one canonical persisted draw using a generic lottery envelope.",
            "inputSchema": _json_schema(
                required=("lottery_type", "draw_number"),
                properties={
                    "lottery_type": lottery_type,
                    "draw_number": {"type": "string", "minLength": 1},
                    "authority": authority,
                },
            ),
        },
    )


_TOOL_ALLOWED_ARGUMENTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "list_lottery_types": ((), ()),
    "list_historical_runs": (
        ("lottery_type",),
        ("strategy_id", "status", "authority"),
    ),
    "get_strategy_window_ranking": (
        ("lottery_type", "window", "criterion"),
        ("authority",),
    ),
    "get_strategy_replay_summary": (
        ("lottery_type", "strategy_id"),
        ("authority",),
    ),
    "get_strategy_match_summary": (
        ("lottery_type", "strategy_id"),
        ("min_main_matches", "authority"),
    ),
    "get_strategies_by_match_threshold": (
        ("lottery_type", "min_main_matches"),
        ("authority", "window"),
    ),
    "get_strategy_best_prize": (
        ("lottery_type", "strategy_id"),
        ("authority",),
    ),
    "get_draw": (
        ("lottery_type", "draw_number"),
        ("authority",),
    ),
}


def _validate_tool_arguments(name: str, arguments: Mapping[str, object]) -> None:
    definition = _TOOL_ALLOWED_ARGUMENTS.get(name)
    if definition is None:
        raise LottoLabMcpQueryError("INVALID_TOOL", "Unknown MCP tool.")
    required, optional = definition
    keys = tuple(arguments)
    if any(type(key) is not str for key in keys):
        raise LottoLabMcpQueryError(INVALID_ARGUMENTS, "tool arguments must use named fields.")
    allowed = set(required) | set(optional)
    if any(key not in allowed for key in keys):
        raise LottoLabMcpQueryError(
            INVALID_ARGUMENTS,
            "the tool accepts only its documented read-only arguments.",
        )
    if any(key not in arguments for key in required):
        raise LottoLabMcpQueryError(
            INVALID_ARGUMENTS,
            "a required tool argument is missing.",
        )
    for key in (*required, *optional):
        if key not in arguments:
            continue
        value = arguments[key]
        if key in {
            "lottery_type",
            "strategy_id",
            "window",
            "criterion",
            "draw_number",
            "status",
            "authority",
        }:
            if type(value) is not str or not value.strip():
                raise LottoLabMcpQueryError(
                    INVALID_ARGUMENTS,
                    "text tool arguments must be non-empty strings.",
                )
            if key == "authority" and (
                "/" in value or "\\" in value or value.startswith("~")
            ):
                raise LottoLabMcpQueryError(
                    INVALID_ARGUMENTS,
                    "authority must be a logical authority identity.",
                )
        if key == "min_main_matches" and (
            type(value) is not int or isinstance(value, bool) or value < 0
        ):
            raise LottoLabMcpQueryError(
                INVALID_ARGUMENTS,
                "min_main_matches must be a non-negative integer.",
            )


def _sanitize_public_value(value: object) -> object:
    if isinstance(value, str):
        if (
            value.startswith("/")
            or value.startswith("~")
            or "file:" in value
            or ".runs" in value
            or ".runtime" in value
            or "Library/Application Support" in value
        ):
            return "REDACTED_PRIVATE_LOCATION"
        return value
    if isinstance(value, Mapping):
        typed = cast(Mapping[object, object], value)
        return {
            str(key): _sanitize_public_value(item) for key, item in typed.items()
        }
    if isinstance(value, list):
        typed = cast(list[object], value)
        return [_sanitize_public_value(item) for item in typed]
    if isinstance(value, tuple):
        typed = cast(tuple[object, ...], value)
        return [_sanitize_public_value(item) for item in typed]
    return value


def _strategy_name(strategy_id: str) -> str | None:
    try:
        return production_catalog().get(strategy_id).strategy_name
    except Exception:
        return None


def _verify_configured_database(database: Path) -> None:
    if not database.is_absolute():
        raise LottoLabMcpQueryError(
            SCHEMA_MISMATCH,
            "Historical Results database configuration must be an absolute path.",
        )
    try:
        available = verify_schema_read_only(database)
    except Exception as exc:
        raise LottoLabMcpQueryError(
            SCHEMA_MISMATCH,
            "Historical Results schema verification failed.",
        ) from exc
    if not available:
        raise LottoLabMcpQueryError(
            STORAGE_UNAVAILABLE,
            "Historical Results storage is unavailable.",
        )


def _configured_generic_repository(database: Path) -> HistoricalResultQueryRepository:
    _verify_configured_database(database)
    return SQLiteHistoricalResultQueryRepository(database)


def _configured_p638_repository(database: Path) -> P638HistoricalQueryRepository:
    _verify_configured_database(database)
    return SQLiteP638HistoricalQueryRepository(database)


def build_production_service(
    environ: Mapping[str, str] | None = None,
) -> LottoLabMcpQueryService:
    """Build lazy read-only providers from named registry capabilities only."""

    selected_environment = os.environ if environ is None else environ
    registry = StorageAuthorityRegistry.from_file()
    resolver = StorageAuthorityResolver(registry, environ=selected_environment)
    resolutions: dict[str, object] = {}
    descriptors: list[ReadOnlyAuthorityDescriptor] = []
    for authority in registry.authorities:
        try:
            resolution = resolver.resolve(authority.authority_id)
        except StorageAuthorityError:
            resolution = None
        resolutions[authority.capability] = resolution
        descriptors.append(
            ReadOnlyAuthorityDescriptor(
                authority_id=authority.authority_id,
                capability=authority.capability,
                lottery_type=authority.lottery_type,
                status=authority.status,
                schema=authority.schema,
                run_id=authority.run_id,
                immutable=authority.immutable,
                resolved=resolution is not None and resolution.path is not None,
                strategy_count=authority.strategy_count,
                draw_count=authority.draw_count,
                target_count=authority.target_count,
                ticket_count=authority.ticket_count,
                provenance=authority.provenance,
            )
        )

    def resolved_path(capability: str) -> Path | None:
        resolution = resolutions.get(capability)
        path = getattr(resolution, "path", None)
        return path if isinstance(path, Path) else None

    draw_path = resolved_path("DRAW_DATA")
    b649_path = resolved_path("BIG_LOTTO_PACKAGED_RECORDS")
    p638_replay_path = resolved_path("POWER_LOTTO_CURRENT_REPLAY")
    p638_ranking_path = resolved_path("POWER_LOTTO_CURRENT_RANKING")
    t539_path = resolved_path("DAILY_539_HISTORICAL")
    historical_path = resolved_path("POWER_LOTTO_HISTORICAL_RESULTS_V2")

    draw_factory: Callable[[], DrawDataRepository] | None = None
    if draw_path is not None:
        def make_draw_factory() -> DrawDataRepository:
            return SQLiteDrawDataRepository(LocalDataPaths(draw_path.parent, draw_path))

        draw_factory = make_draw_factory

    b649_factory: Callable[[], PackagedB649MultiTicketRecordReader] | None = None
    if b649_path is not None:
        def make_b649_factory() -> PackagedB649MultiTicketRecordReader:
            return PackagedB649MultiTicketRecordReader()

        b649_factory = make_b649_factory

    p638_current_factory: Callable[[], P638HistoricalQueryRepository] | None = None
    if p638_replay_path is not None and p638_ranking_path is not None:
        def make_p638_current_factory() -> P638HistoricalQueryRepository:
            return SQLiteP638BaseDataQueryRepository(
                p638_ranking_path,
                replay_database=p638_replay_path,
            )

        p638_current_factory = make_p638_current_factory

    p638_ranking_factory: Callable[[], P638CurrentRankingQueryRepository] | None = None
    if p638_ranking_path is not None:
        def make_p638_ranking_factory() -> P638CurrentRankingQueryRepository:
            return SQLiteP638CurrentRankingQueryRepository(p638_ranking_path)

        p638_ranking_factory = make_p638_ranking_factory

    t539_factory: Callable[[], T539HistoricalQueryRepository] | None = None
    if t539_path is not None:
        def make_t539_factory() -> T539HistoricalQueryRepository:
            return SQLiteT539HistoricalQueryRepository(t539_path)

        t539_factory = make_t539_factory

    generic_factory: Callable[[], HistoricalResultQueryRepository] | None = None
    p638_factory: Callable[[], P638HistoricalQueryRepository] | None = None
    if historical_path is not None:
        def make_generic_factory() -> HistoricalResultQueryRepository:
            return _configured_generic_repository(historical_path)

        def make_p638_factory() -> P638HistoricalQueryRepository:
            return _configured_p638_repository(historical_path)

        generic_factory = make_generic_factory
        p638_factory = make_p638_factory

    sources = ReadOnlyHistoricalSources(
        generic_factory=generic_factory,
        p638_factory=p638_factory,
        draw_factory=draw_factory,
        b649_factory=b649_factory,
        p638_current_factory=p638_current_factory,
        p638_ranking_factory=p638_ranking_factory,
        t539_factory=t539_factory,
        authority_descriptors=tuple(descriptors),
    )
    return LottoLabMcpQueryService(sources, strategy_name_resolver=_strategy_name)


class LottoLabMcpServer:
    """Small JSON-RPC/MCP dispatcher suitable for local stdio transport."""

    def __init__(self, service: LottoLabMcpQueryService) -> None:
        self._service = service

    @property
    def tools(self) -> tuple[dict[str, object], ...]:
        return _tool_definitions()

    def dispatch(self, message: object) -> dict[str, object] | None:
        if not isinstance(message, Mapping):
            return self.error_response(None, -32600, "Invalid JSON-RPC request.")
        request = cast(Mapping[str, object], message)
        request_id = request.get("id")
        method = request.get("method")
        if not isinstance(method, str):
            return self.error_response(request_id, -32600, "Invalid JSON-RPC request.")
        if method.startswith("notifications/"):
            return None
        if method == "initialize":
            return self._initialize(request_id, request.get("params"))
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": list(self.tools)}}
        if method == "tools/call":
            return self._call_tool(request_id, request.get("params"))
        return self.error_response(request_id, -32601, "Method not found.")

    def _initialize(
        self, request_id: object, raw_params: object
    ) -> dict[str, object]:
        requested = None
        if isinstance(raw_params, Mapping):
            params = cast(Mapping[str, object], raw_params)
            candidate = params.get("protocolVersion")
            if isinstance(candidate, str):
                requested = candidate
        protocol_version = (
            requested
            if requested in _SUPPORTED_PROTOCOL_VERSIONS
            else _SUPPORTED_PROTOCOL_VERSIONS[0]
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "lottolab", "version": __version__},
            },
        }

    def _call_tool(self, request_id: object, raw_params: object) -> dict[str, object]:
        if not isinstance(raw_params, Mapping):
            return self.error_response(request_id, -32602, "Invalid tool call parameters.")
        params = cast(Mapping[str, object], raw_params)
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, Mapping):
            return self.error_response(request_id, -32602, "Invalid tool call parameters.")
        try:
            typed_arguments = dict(cast(Mapping[str, object], arguments))
            _validate_tool_arguments(name, typed_arguments)
            result = self._invoke_tool(name, typed_arguments)
        except LottoLabMcpQueryError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                _sanitize_public_value(exc.as_payload()),
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        }
                    ],
                },
            }
        except (TypeError, ValueError, KeyError) as exc:
            del exc
            error = LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the tool request could not be processed safely.",
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": json.dumps(error.as_payload())}],
                },
            }
        except Exception as exc:
            del exc
            error = LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the requested evidence is unavailable.",
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                _sanitize_public_value(error.as_payload())
                            ),
                        }
                    ],
                },
            }
        safe_result = cast(dict[str, object], _sanitize_public_value(result))
        text = json.dumps(safe_result, ensure_ascii=False, sort_keys=True)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": text}],
                "structuredContent": safe_result,
            },
        }

    def _invoke_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        if name == "list_lottery_types":
            return self._service.list_lottery_types()
        if name == "list_historical_runs":
            return self._service.list_historical_runs(
                lottery_type=cast(str, arguments.get("lottery_type")),
                strategy_id=cast(str | None, arguments.get("strategy_id")),
                status=cast(str | None, arguments.get("status")),
                authority=cast(str | None, arguments.get("authority")),
            )
        if name == "get_strategy_window_ranking":
            return self._service.get_strategy_window_ranking(
                lottery_type=cast(str, arguments.get("lottery_type")),
                window=cast(str, arguments.get("window")),
                criterion=cast(str, arguments.get("criterion")),
                authority=cast(str | None, arguments.get("authority")),
            )
        if name == "get_strategy_replay_summary":
            return self._service.get_strategy_replay_summary(
                lottery_type=cast(str, arguments.get("lottery_type")),
                strategy_id=cast(str, arguments.get("strategy_id")),
                authority=cast(str | None, arguments.get("authority")),
            )
        if name == "get_strategy_match_summary":
            threshold = arguments.get("min_main_matches", 4)
            return self._service.get_strategy_match_summary(
                lottery_type=cast(str, arguments.get("lottery_type")),
                strategy_id=cast(str, arguments.get("strategy_id")),
                min_main_matches=cast(int, threshold),
                authority=cast(str | None, arguments.get("authority")),
            )
        if name == "get_strategies_by_match_threshold":
            return self._service.get_strategies_by_match_threshold(
                lottery_type=cast(str, arguments.get("lottery_type")),
                min_main_matches=cast(int, arguments.get("min_main_matches")),
                authority=cast(str | None, arguments.get("authority")),
                window=cast(str | None, arguments.get("window")),
            )
        if name == "get_strategy_best_prize":
            return self._service.get_strategy_best_prize(
                lottery_type=cast(str, arguments.get("lottery_type")),
                strategy_id=cast(str, arguments.get("strategy_id")),
                authority=cast(str | None, arguments.get("authority")),
            )
        if name == "get_draw":
            return self._service.get_draw(
                lottery_type=cast(str, arguments.get("lottery_type")),
                draw_number=cast(str, arguments.get("draw_number")),
                authority=cast(str | None, arguments.get("authority")),
            )
        raise LottoLabMcpQueryError("INVALID_TOOL", "Unknown MCP tool.")

    @staticmethod
    def error_response(request_id: object, code: int, message: str) -> dict[str, object]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }


def serve_stdio(
    server: LottoLabMcpServer | None = None,
    *,
    stdin: IO[str] | None = None,
    stdout: IO[str] | None = None,
) -> None:
    """Serve newline-delimited JSON-RPC messages on stdin/stdout only."""

    active_server = server if server is not None else LottoLabMcpServer(build_production_service())
    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    for line in input_stream:
        if not line.strip():
            continue
        try:
            message: object = json.loads(line)
        except (TypeError, ValueError):
            response = active_server.error_response(None, -32700, "Parse error.")
        else:
            response = active_server.dispatch(message)
        if response is not None:
            output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
            output_stream.write("\n")
            output_stream.flush()


__all__ = [
    "HISTORICAL_RESULTS_DB_ENV",
    "LottoLabMcpServer",
    "build_production_service",
    "serve_stdio",
]
