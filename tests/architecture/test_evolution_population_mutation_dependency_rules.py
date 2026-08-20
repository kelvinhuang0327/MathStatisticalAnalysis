"""Architecture boundary for the pure evolution-mutation mechanism."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/lottolab/domain/evolution_population_mutation.py"


def _imported_modules() -> set[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_mutation_transition_has_only_explicit_stdlib_dependencies() -> None:
    assert _imported_modules() == {
        "__future__",
        "collections.abc",
        "dataclasses",
        "math",
        "numbers",
        "typing",
    }


def test_mutation_transition_has_no_runtime_or_other_lottolab_layer_dependency() -> None:
    imports = _imported_modules()
    forbidden_prefixes = (
        "apscheduler",
        "http",
        "requests",
        "socket",
        "sqlite3",
        "lottolab.application",
        "lottolab.infrastructure",
        "lottolab.interfaces",
        "lottolab.strategies",
    )

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in forbidden_prefixes
    )
