"""Architecture proof for the DB-free Frontend Frequency adapter boundary."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "strategies"
    / "adapters"
    / "biglotto_frontend_frequency.py"
)


def _tree() -> ast.Module:
    return ast.parse(ADAPTER.read_text(encoding="utf-8"))


def _imports() -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _called_names() -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_adapter_exists_only_in_strategy_layer() -> None:
    assert ADAPTER.is_file()


def test_adapter_imports_no_database_outer_layer_network_rng_or_numeric_dependency() -> None:
    imports = _imports()
    assert imports.isdisjoint(
        {
            "numpy",
            "scipy",
            "random",
            "sqlite3",
            "sqlalchemy",
            "subprocess",
            "socket",
            "requests",
            "httpx",
        }
    )
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
            )
        )
        for module in imports
    )


def test_adapter_has_no_persistence_network_rng_retry_or_fallback_call_surface() -> None:
    calls = _called_names()
    assert calls.isdisjoint(
        {
            "connect",
            "execute",
            "executemany",
            "commit",
            "rollback",
            "open",
            "write_text",
            "write_bytes",
            "request",
            "urlopen",
            "seed",
            "sample",
            "choice",
            "retry",
            "fallback",
        }
    )
