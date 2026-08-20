"""Architecture proof for the DB-decoupled Smart Multi-Bet execution path."""

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
    / "biglotto_smart_multi_bet.py"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_smart_multi_bet_adapter_exists_in_strategy_layer() -> None:
    assert ADAPTER.is_file()


def test_smart_multi_bet_imports_no_database_runtime_or_outer_layer() -> None:
    imports = _imports(ADAPTER)
    assert imports.isdisjoint(
        {
            "sqlite3",
            "sqlalchemy",
            "pathlib",
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


def test_smart_multi_bet_has_no_persistence_or_network_call_surface() -> None:
    calls = _called_names(ADAPTER)
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
        }
    )


def test_smart_multi_bet_uses_only_isolated_rng_calls() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    assert "random.sample(" not in source
    assert "random.choice(" not in source
    assert "rng.sample(" in source
    assert "rng.choice(" in source
