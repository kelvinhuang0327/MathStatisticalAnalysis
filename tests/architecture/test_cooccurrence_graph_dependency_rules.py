"""Architecture proof for the native Cooccurrence Graph boundary."""

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
    / "biglotto_cooccurrence_graph.py"
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


def test_cooccurrence_graph_adapter_exists_only_in_strategy_layer() -> None:
    assert ADAPTER.is_file()


def test_adapter_imports_no_db_outer_layer_network_or_numpy() -> None:
    imports = _imports()
    assert imports.isdisjoint(
        {
            "numpy",
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


def test_adapter_has_no_persistence_network_or_module_global_rng_calls() -> None:
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
        }
    )
    source = ADAPTER.read_text(encoding="utf-8")
    assert "np.random" not in source
    assert "random.sample(" not in source
    assert "random.choice(" not in source
    assert "random.seed(" not in source
    assert "python_rng.sample" in source
    assert "numpy_rng.choice_without_replacement" in source


def test_both_rng_families_are_explicit_generator_parameters() -> None:
    generator = next(
        node
        for node in _tree().body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_cooccurrence_graph_tickets"
    )
    assert [argument.arg for argument in generator.args.args] == [
        "history",
        "numpy_rng",
        "python_rng",
    ]


def test_no_rng_instance_is_created_at_module_scope() -> None:
    for node in _tree().body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            assert not any(
                isinstance(candidate, ast.Call)
                and isinstance(candidate.func, ast.Attribute)
                and isinstance(candidate.func.value, ast.Name)
                and candidate.func.value.id == "random"
                for candidate in ast.walk(node)
            )
