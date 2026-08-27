from __future__ import annotations

import ast
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "lottolab"
    / "research"
    / "biglotto_l2_pairwise_sinkhorn_recurrence_dependence.py"
)
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "collections",
    "dataclasses",
    "json",
    "math",
    "types",
    "typing",
}
FORBIDDEN_IMPORT_ROOTS = {
    "lottolab",
    "numpy",
    "pandas",
    "random",
    "scipy",
    "socket",
    "sqlite3",
    "subprocess",
    "urllib",
}
FORBIDDEN_CALLS = {"__import__", "compile", "eval", "exec", "open"}
FORBIDDEN_SOURCE_MARKERS = (
    "canonical_database",
    "historical_outcomes",
    "forward_outcomes",
    "filesystem",
    "network",
)


def _import_root(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name.split(".", maxsplit=1)[0]
    return (node.module or "").split(".", maxsplit=1)[0]


def test_nf06_module_is_standalone_and_stdlib_only() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    roots = {_import_root(node) for node in imports}

    assert roots <= ALLOWED_IMPORT_ROOTS
    assert not roots & FORBIDDEN_IMPORT_ROOTS


def test_nf06_module_has_no_dynamic_loading_or_external_state_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))

    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not calls & FORBIDDEN_CALLS
    assert not any(marker in source.lower() for marker in FORBIDDEN_SOURCE_MARKERS)
