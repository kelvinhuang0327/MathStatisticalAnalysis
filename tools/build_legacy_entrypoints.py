"""Build the P600A legacy entrypoint inventory using static source inspection only.

This tool never imports LotteryNew modules and never opens a database.  It is
intended to run against an isolated detached checkout at the exact pinned
legacy commit.  The generated document is JSON, which is a valid YAML subset.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PINNED_LEGACY_COMMIT = "520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f"
EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "coverage",
        "archive",
        "backups",
        "artifacts",
        "outputs",
        "tests",
        "__pycache__",
    }
)
UNKNOWN_CAPABILITIES = frozenset(
    {
        "lottery.legacy_cli.unknown",
        "lottery.legacy_module_cli.unknown",
    }
)

UI_CAPABILITIES: dict[str, str] = {
    "upload": "lottery.draw_data.manage",
    "history": "lottery.draw_data.manage",
    "analysis": "lottery.research.execution",
    "simulation": "lottery.backtest.evaluate",
    "prediction": "lottery.prediction.generate",
    "smartbetting": "lottery.prediction.generate",
    "autolearning": "lottery.optimization.manage",
    "next-draw": "lottery.prediction.generate",
    "tracking": "lottery.replay.read_models",
    "replay": "lottery.replay.read_models",
    "reviews": "lottery.evidence.reporting",
    "orchestration": "lottery.optimization.manage",
    "cto-review": "lottery.evidence.reporting",
    "p257-overview": "lottery.evidence.reporting",
    "p251-evidence-dashboard": "lottery.evidence.reporting",
    "p333-scoreboard": "lottery.evidence.reporting",
    "p536e-lift-extension": "lottery.evidence.reporting",
    "p536l-lift-candidate-shortlist": "lottery.evidence.reporting",
    "p537b-robustness-review": "lottery.evidence.reporting",
    "p263b-d3-ssot": "lottery.evidence.reporting",
    "p258-d3-audit": "lottery.evidence.reporting",
    "p259a-replay-overview": "lottery.replay.read_models",
    "lottery-d5": "lottery.evidence.reporting",
    "big649-measurement": "lottery.evidence.reporting",
}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _source_files(root: Path, suffix: str) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(f"*{suffix}")
        if not EXCLUDED_PARTS.intersection(path.relative_to(root).parts)
    )


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return None


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _status_for(capability_id: str) -> str:
    return "UNKNOWN_NEEDS_AUDIT" if capability_id in UNKNOWN_CAPABILITIES else "MAPPED"


def _entry(
    *,
    entrypoint_id: str,
    kind: str,
    capability_id: str,
    source_path: str,
    line: int | None = None,
    contract: str | None = None,
    evidence: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "entrypoint_id": entrypoint_id,
        "kind": kind,
        "capability_id": capability_id,
        "source_path": source_path,
        "status": _status_for(capability_id),
        "evidence": evidence,
    }
    if line is not None:
        result["line"] = line
    if contract is not None:
        result["contract"] = contract
    if result["status"] == "UNKNOWN_NEEDS_AUDIT":
        result["unknown_reason"] = (
            "Legacy executable surface is inventoried but requires per-command side-effect "
            "classification before migration."
        )
    return result


def _router_prefix(tree: ast.Module) -> str:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "router" for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if (
                keyword.arg == "prefix"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                return keyword.value.value
    return ""


def _api_capability(source_path: str, method: str, route: str) -> str:
    filename = Path(source_path).name
    if filename == "admin.py":
        return "lottery.runtime.health_cache"
    if filename == "data.py":
        return "lottery.draw_data.manage"
    if filename == "ingest.py":
        return "lottery.ingestion.manage"
    if filename == "optimization.py":
        return "lottery.optimization.manage"
    if filename == "backtest.py":
        return "lottery.backtest.evaluate"
    if filename == "prediction.py":
        return "lottery.prediction.generate"
    if filename == "best_strategy_overview.py":
        if method == "GET" and route.endswith("/next-prediction"):
            return "lottery.prediction.generate"
        return "lottery.evidence.reporting"
    if filename == "p542b_scoreboard.py":
        return "lottery.evidence.reporting"
    if filename == "replay.py":
        if route in {"/api/replay/strategies", "/api/replay/strategy-lifecycle"}:
            return "lottery.strategy_catalog.list"
        if route in {
            "/api/replay/history",
            "/api/replay/summary",
            "/api/replay/runs",
            "/api/replay/run/{run_id}/status",
            "/api/replay/freshness",
            "/api/replay/history-overview",
            "/api/replay/history-detail",
            "/api/replay/history-detail-grouped",
        }:
            return "lottery.replay.read_models"
        return "lottery.evidence.reporting"
    return "lottery.legacy_module_cli.unknown"


def _api_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    routes_root = root / "lottery_api" / "routes"
    for path in sorted(routes_root.glob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        prefix = _router_prefix(tree)
        source_path = _relative(path, root)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(
                    decorator.func, ast.Attribute
                ):
                    continue
                method = decorator.func.attr.upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "WEBSOCKET"}:
                    continue
                if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                    continue
                value = decorator.args[0].value
                if not isinstance(value, str):
                    continue
                route = prefix + value
                contract = f"{method} {route}"
                entries.append(
                    _entry(
                        entrypoint_id=f"api:{contract}",
                        kind="api",
                        capability_id=_api_capability(source_path, method, route),
                        source_path=source_path,
                        line=node.lineno,
                        contract=contract,
                        evidence=f"FastAPI route handler {node.name}",
                    )
                )
    return entries


def _ui_entries(root: Path) -> list[dict[str, Any]]:
    path = root / "index.html"
    text = path.read_text(encoding="utf-8", errors="replace")
    entries: list[dict[str, Any]] = []
    for match in re.finditer(r'data-section="([a-z0-9][a-z0-9-]*)"', text):
        section = match.group(1)
        if f'id="{section}-section"' not in text:
            raise ValueError(f"navigation section has no matching page section: {section}")
        capability_id = UI_CAPABILITIES.get(section, "lottery.legacy_module_cli.unknown")
        line = text.count("\n", 0, match.start()) + 1
        entries.append(
            _entry(
                entrypoint_id=f"ui:index.html#{section}",
                kind="ui",
                capability_id=capability_id,
                source_path="index.html",
                line=line,
                contract=f"data-section={section}",
                evidence=(
                    "Top-level navigation entry; matching section checked by the catalog "
                    "validator"
                ),
            )
        )
    deduplicated = {entry["entrypoint_id"]: entry for entry in entries}
    return list(deduplicated.values())


def _frontend_api_capability(route: str) -> str:
    if route in {"/", "/health"} or route.startswith(("/api/ping", "/api/cache/")):
        return "lottery.runtime.health_cache"
    if route.startswith(("/api/history", "/api/data/", "/api/draws")):
        return "lottery.draw_data.manage"
    if route.startswith("/api/ingest/"):
        return "lottery.ingestion.manage"
    if route.startswith(("/api/auto-learning/", "/api/smart-learning/")):
        return "lottery.optimization.manage"
    if route.startswith("/api/backtest/"):
        return "lottery.backtest.evaluate"
    if route.startswith(
        (
            "/api/predict",
            "/api/models",
            "/api/enhanced-methods",
            "/api/optimal-configs",
            "/api/wheel/",
            "/api/performance/",
        )
    ):
        return "lottery.prediction.generate"
    if route.startswith("/api/replay/"):
        if route in {"/api/replay/strategies", "/api/replay/strategy-lifecycle"}:
            return "lottery.strategy_catalog.list"
        if route.startswith(
            (
                "/api/replay/history",
                "/api/replay/summary",
                "/api/replay/runs",
                "/api/replay/run/",
                "/api/replay/freshness",
            )
        ):
            return "lottery.replay.read_models"
        return "lottery.evidence.reporting"
    if route.startswith(("/api/research/", "/api/best-strategy-overview")):
        return "lottery.evidence.reporting"
    return "lottery.frontend.legacy_shell"


def _frontend_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    source_paths = [root / "index.html"]
    source_paths.extend(
        path
        for path in _source_files(root / "src", ".js")
        if path.is_file()
    )
    for path in sorted(set(source_paths)):
        source_path = _relative(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        seen_routes: set[str] = set()
        for match in re.finditer(r"/api/[A-Za-z0-9_./{}$-]+", text):
            route = match.group(0).rstrip("./")
            if route in seen_routes:
                continue
            seen_routes.add(route)
            entries.append(
                _entry(
                    entrypoint_id=f"frontend_api:{source_path}:{route}",
                    kind="frontend_api",
                    capability_id=_frontend_api_capability(route),
                    source_path=source_path,
                    line=text.count("\n", 0, match.start()) + 1,
                    contract=route,
                    evidence="Static frontend API path literal",
                )
            )
        for match in re.finditer(r"\b(?:fetch|axios\.(?:get|post|put|patch|delete))\s*\(", text):
            line = text.count("\n", 0, match.start()) + 1
            entries.append(
                _entry(
                    entrypoint_id=f"frontend_http_call:{source_path}:{line}",
                    kind="frontend_http_call",
                    capability_id="lottery.frontend.legacy_shell",
                    source_path=source_path,
                    line=line,
                    evidence="Static frontend HTTP call site",
                )
            )
        for match in re.finditer(r"addEventListener\s*\(\s*['\"]([^'\"]+)['\"]", text):
            line = text.count("\n", 0, match.start()) + 1
            event_name = match.group(1)
            entries.append(
                _entry(
                    entrypoint_id=f"ui_handler:{source_path}:{line}:{event_name}",
                    kind="ui_handler",
                    capability_id="lottery.frontend.legacy_shell",
                    source_path=source_path,
                    line=line,
                    contract=event_name,
                    evidence="Static addEventListener registration",
                )
            )
        for match in re.finditer(r"\sonclick=", text):
            line = text.count("\n", 0, match.start()) + 1
            entries.append(
                _entry(
                    entrypoint_id=f"ui_handler:{source_path}:{line}:onclick",
                    kind="ui_handler",
                    capability_id="lottery.frontend.legacy_shell",
                    source_path=source_path,
                    line=line,
                    contract="onclick",
                    evidence="Static inline click-handler registration",
                )
            )
    return entries


def _has_main_guard(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        try:
            expression = ast.unparse(node.test)
        except ValueError:
            continue
        if "__name__" in expression and "__main__" in expression:
            return True
    return False


def _cli_capability(source_path: str) -> str:
    if source_path == "lottery_api/app.py":
        return "lottery.runtime.local_service"
    if source_path.startswith("analysis/"):
        return "lottery.research.execution"
    if source_path.startswith("recovered_strategies/"):
        return "lottery.evidence.reporting"
    if source_path.startswith(("tools/", "scripts/")):
        return "lottery.legacy_cli.unknown"
    return "lottery.legacy_module_cli.unknown"


def _cli_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in _source_files(root, ".py"):
        tree = _parse(path)
        if tree is None or not _has_main_guard(tree):
            continue
        source_path = _relative(path, root)
        entries.append(
            _entry(
                entrypoint_id=f"cli:python:{source_path}",
                kind="cli",
                capability_id=_cli_capability(source_path),
                source_path=source_path,
                evidence="Static AST detection of a __main__ guard",
            )
        )
    for path in _source_files(root, ".sh"):
        source_path = _relative(path, root)
        entries.append(
            _entry(
                entrypoint_id=f"cli:shell:{source_path}",
                kind="cli",
                capability_id="lottery.runtime.local_service",
                source_path=source_path,
                evidence="Executable shell surface in the pinned tree",
            )
        )
    return entries


def _scheduler_and_hook_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in _source_files(root, ".py"):
        tree = _parse(path)
        if tree is None:
            continue
        source_path = _relative(path, root)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_job"
            ):
                entries.append(
                    _entry(
                        entrypoint_id=f"scheduler:{source_path}:{node.lineno}",
                        kind="scheduler",
                        capability_id="lottery.automation.schedulers",
                        source_path=source_path,
                        line=node.lineno,
                        evidence="Static AST detection of APScheduler add_job registration",
                    )
                )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                "_refresh_after_insert",
                "startup_event",
            }:
                entries.append(
                    _entry(
                        entrypoint_id=f"hook:{source_path}:{node.name}",
                        kind="hook",
                        capability_id=(
                            "lottery.ingestion.manage"
                            if node.name == "_refresh_after_insert"
                            else "lottery.runtime.local_service"
                        ),
                        source_path=source_path,
                        line=node.lineno,
                        evidence=f"Static AST detection of runtime hook {node.name}",
                    )
                )
    for path in sorted(root.glob("*.plist")):
        source_path = _relative(path, root)
        entries.append(
            _entry(
                entrypoint_id=f"job:launchd:{source_path}",
                kind="job",
                capability_id="lottery.runtime.local_service",
                source_path=source_path,
                evidence="Committed launchd service definition",
            )
        )
    return entries


def _db_capability(source_path: str) -> str:
    if source_path.startswith("analysis/"):
        return "lottery.research.execution"
    if source_path.startswith("recovered_strategies/"):
        return "lottery.evidence.reporting"
    if source_path.startswith(("tools/", "scripts/")):
        return "lottery.legacy_cli.unknown"
    if source_path.startswith("lottery_api/routes/ingest.py"):
        return "lottery.ingestion.manage"
    if source_path.startswith(("lottery_api/routes/data.py", "lottery_api/database.py")):
        return "lottery.draw_data.manage"
    if source_path.startswith("lottery_api/routes/replay.py"):
        return "lottery.replay.read_models"
    if source_path.startswith("lottery_api/routes/optimization.py"):
        return "lottery.optimization.manage"
    if "backtest" in source_path:
        return "lottery.backtest.evaluate"
    if source_path.startswith(("lottery_api/models/", "lottery_api/routes/prediction.py")):
        return "lottery.prediction.generate"
    return "lottery.legacy_module_cli.unknown"


def _db_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    read_pattern = re.compile(r"sqlite3\.connect\s*\(|DatabaseManager\s*\(")
    write_pattern = re.compile(
        r"\b(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|UPDATE\s+[A-Za-z_]|DELETE\s+FROM|"
        r"REPLACE\s+INTO|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE)\b",
        re.IGNORECASE,
    )
    for path in _source_files(root, ".py"):
        source_path = _relative(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        for kind, pattern in (("db_reader", read_pattern), ("db_writer", write_pattern)):
            match = pattern.search(text)
            if match is None:
                continue
            line = text.count("\n", 0, match.start()) + 1
            entries.append(
                _entry(
                    entrypoint_id=f"{kind}:{source_path}",
                    kind=kind,
                    capability_id=_db_capability(source_path),
                    source_path=source_path,
                    line=line,
                    evidence=(
                        "High-signal static DB connection token"
                        if kind == "db_reader"
                        else (
                            "High-signal static SQL mutation token; candidate requires "
                            "runtime-path audit"
                        )
                    ),
                )
            )
    return entries


def _external_entries() -> list[dict[str, Any]]:
    return [
        _entry(
            entrypoint_id="docs:legacy-wiki-index",
            kind="docs",
            capability_id="lottery.wiki.documentation",
            source_path="wiki/README.md",
            evidence=(
                "Declared historical wiki index; absent at the pinned commit and audited "
                "separately"
            ),
        ),
        _entry(
            entrypoint_id="external:ai-system-lotterynew-worker",
            kind="external",
            capability_id="lottery.external_agent.integration",
            source_path="external-ai-system (content not copied)",
            evidence="External prompt/rule integration recorded as metadata only",
        ),
    ]


def _digest(entries: Iterable[dict[str, Any]]) -> str:
    encoded = json.dumps(list(entries), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_inventory(root: Path) -> dict[str, Any]:
    head = _git_head(root)
    if head != PINNED_LEGACY_COMMIT:
        raise ValueError(f"legacy HEAD {head} does not match pinned {PINNED_LEGACY_COMMIT}")
    entries = (
        _api_entries(root)
        + _ui_entries(root)
        + _frontend_entries(root)
        + _cli_entries(root)
        + _scheduler_and_hook_entries(root)
        + _db_entries(root)
        + _external_entries()
    )
    entries.sort(key=lambda item: str(item["entrypoint_id"]))
    kinds = sorted({str(entry["kind"]) for entry in entries})
    coverage = {
        kind: {
            "total": sum(entry["kind"] == kind for entry in entries),
            "mapped": sum(
                entry["kind"] == kind and entry["status"] == "MAPPED" for entry in entries
            ),
            "unknown": sum(
                entry["kind"] == kind and entry["status"] == "UNKNOWN_NEEDS_AUDIT"
                for entry in entries
            ),
        }
        for kind in kinds
    }
    return {
        "schema_version": 1,
        "legacy_commit_oid": head,
        "generation_mode": "STATIC_AST_AND_TEXT_ONLY_NO_IMPORT_NO_DB_OPEN",
        "generator": "tools/build_legacy_entrypoints.py",
        "scope_exclusions": sorted(EXCLUDED_PARTS),
        "coverage": coverage,
        "entrypoint_digest_sha256": _digest(entries),
        "entrypoints": entries,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    legacy_root: Path = args.legacy_root.resolve()
    output: Path = args.output.resolve()
    payload = json.dumps(build_inventory(legacy_root), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != payload:
            print(f"inventory mismatch: {output}")
            return 1
        print(f"inventory verified: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
