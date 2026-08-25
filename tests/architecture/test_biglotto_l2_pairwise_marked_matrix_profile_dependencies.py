"""Dependency firewall for the standalone frozen candidate."""

from __future__ import annotations

import ast
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "lottolab"
    / "research"
    / "biglotto_l2_pairwise_marked_matrix_profile.py"
)
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "collections",
    "dataclasses",
    "decimal",
    "functools",
    "hashlib",
    "itertools",
    "json",
    "typing",
}


def test_candidate_is_standard_library_only_and_has_no_empirical_path_access() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", 1)[0])

    assert imported_roots <= ALLOWED_IMPORT_ROOTS
    assert "sqlite" not in source.lower()
    assert "requests" not in source.lower()
    assert "httpx" not in source.lower()
    assert "numpy" not in source.lower()
    assert "canonical db" not in source.lower()


def test_candidate_module_is_present_at_the_frozen_handoff_path() -> None:
    assert MODULE_PATH.is_file()
