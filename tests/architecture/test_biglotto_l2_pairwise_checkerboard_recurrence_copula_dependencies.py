"""Architecture guards for the standalone NF05 research constructor."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "research"
    / "biglotto_l2_pairwise_checkerboard_recurrence_copula.py"
)
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "collections",
    "dataclasses",
    "fractions",
    "json",
    "types",
    "typing",
}
FORBIDDEN_TOKENS = {
    "database",
    "filesystem",
    "network",
    "numpy",
    "pandas",
    "random",
    "scipy",
    "sqlite3",
    "subprocess",
    "urllib",
}


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def _import_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_only_declared_standard_library_imports_are_used() -> None:
    assert MODULE.is_file()
    modules = _import_modules(_tree())
    assert all(module.split(".", 1)[0] in ALLOWED_IMPORT_ROOTS for module in modules)


def test_research_constructor_has_no_forbidden_runtime_dependencies_or_side_effects() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    assert not any(token in source for token in FORBIDDEN_TOKENS)

    forbidden_call_names = {"__import__", "compile", "eval", "exec", "input", "open"}
    forbidden_attribute_roots = {"os", "pathlib", "socket", "subprocess", "sys"}
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_call_names
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            assert node.value.id not in forbidden_attribute_roots


def test_constructor_does_not_import_application_or_infrastructure_layers() -> None:
    modules = _import_modules(_tree())
    assert not any(module.startswith("lottolab") for module in modules)
    assert not any(module.startswith("pytest") for module in modules)
