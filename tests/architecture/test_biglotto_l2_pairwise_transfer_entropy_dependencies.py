from __future__ import annotations

import ast
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "lottolab"
    / "research"
    / "biglotto_l2_pairwise_transfer_entropy.py"
)
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "collections",
    "dataclasses",
    "decimal",
    "itertools",
    "json",
    "types",
    "typing",
}
FORBIDDEN_IMPORT_ROOTS = {
    "lottolab",
    "numpy",
    "pandas",
    "random",
    "scipy",
    "sqlite3",
    "subprocess",
    "urllib",
}
FORBIDDEN_RUNTIME_CALLS = {"__import__", "compile", "eval", "exec", "open"}


def _module_tree() -> tuple[str, ast.Module]:
    source = MODULE_PATH.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(MODULE_PATH))


def test_nf02_module_exists_at_the_authorized_research_path() -> None:
    assert MODULE_PATH.is_file()


def test_nf02_module_is_standard_library_only() -> None:
    source, tree = _module_tree()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots = [alias.name.split(".", maxsplit=1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module is not None
            imported_roots = [node.module.split(".", maxsplit=1)[0]]
        else:
            continue
        assert set(imported_roots) <= ALLOWED_IMPORT_ROOTS
        assert not FORBIDDEN_IMPORT_ROOTS.intersection(imported_roots)

    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in FORBIDDEN_RUNTIME_CALLS
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"os", "pathlib", "socket", "sys"}
        for node in ast.walk(tree)
    )
    assert "sqlite3" not in source
    assert "import random" not in source
    assert "from random" not in source
    assert "numpy" not in source
    assert "pandas" not in source


def test_nf02_module_has_no_empirical_or_runtime_integration_surface() -> None:
    source, _ = _module_tree()

    assert "canonical_database" not in source
    assert "historical_outcomes" not in source
    assert "forward_outcomes" not in source
    assert "network" not in source.lower()
    assert "filesystem" not in source.lower()
    assert "database" not in source.lower()
