"""Architecture proof for the native Anti-Consensus RNG boundary."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER = REPO_ROOT / "src" / "lottolab" / "strategies" / "adapters" / "biglotto_anti_consensus.py"


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


def test_anti_consensus_adapter_exists_only_in_strategy_layer() -> None:
    assert ADAPTER.is_file()


def test_anti_consensus_imports_no_db_outer_layer_or_external_rng() -> None:
    imports = _imports(ADAPTER)
    assert imports.isdisjoint(
        {
            "numpy",
            "random",
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


def test_anti_consensus_has_no_persistence_network_or_global_rng_calls() -> None:
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
            "sample",
            "choice",
            "seed",
        }
    )
    source = ADAPTER.read_text(encoding="utf-8")
    assert "np.random" not in source
    assert "random.sample(" not in source
    assert "random.choice(" not in source
    assert "rng.choice_without_replacement" in source


def test_anti_consensus_rng_is_an_explicit_function_parameter() -> None:
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    generator = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_anti_consensus_tickets"
    )
    assert [argument.arg for argument in generator.args.args] == ["rng"]
