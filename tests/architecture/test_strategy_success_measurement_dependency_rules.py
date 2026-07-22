"""Dependency and side-effect guards for strategy-success measurement contracts."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "src" / "lottolab" / "domain" / "strategy_success_measurement.py"


def _syntax_tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def _imports() -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_syntax_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_measurement_domain_module_exists_and_parses() -> None:
    assert MODULE.is_file()
    assert isinstance(_syntax_tree(), ast.Module)


def test_measurement_domain_imports_no_upper_or_legacy_layer() -> None:
    imports = _imports()
    forbidden_prefixes = (
        "lottolab.application",
        "lottolab.evidence",
        "lottolab.infrastructure",
        "lottolab.interfaces",
        "lottolab.strategies",
        "lottery_api",
        "number_pattern_research",
    )
    assert not any(module.startswith(forbidden_prefixes) for module in imports)
    assert not any(module.startswith("lottolab.domain.historical_") for module in imports)


def test_measurement_domain_imports_no_database_transport_or_runtime_library() -> None:
    imports = _imports()
    forbidden = {
        "http",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    assert not {module.partition(".")[0] for module in imports} & forbidden


def test_measurement_domain_performs_no_filesystem_or_environment_read() -> None:
    forbidden_calls = {
        "connect",
        "getenv",
        "open",
        "read_bytes",
        "read_text",
        "resolve_local_data_paths",
        "urlopen",
    }
    called_names: set[str] = set()
    for node in ast.walk(_syntax_tree()):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called_names.add(node.func.attr)
    assert not called_names & forbidden_calls


def test_measurement_domain_has_no_runtime_deployment_or_publication_dependency() -> None:
    source = MODULE.read_text(encoding="utf-8")
    forbidden_tokens = (
        "uvicorn",
        "FastAPI",
        "APIRouter",
        "ExecutableRegistry",
        "deploy(",
        "publish(",
    )
    assert not any(token in source for token in forbidden_tokens)
