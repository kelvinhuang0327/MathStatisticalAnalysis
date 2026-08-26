from __future__ import annotations

import ast
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[2] / "src" / "lottolab" / "research" / "biglotto_l2_pairwise_eighth.py"
)
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "collections",
    "dataclasses",
    "fractions",
    "json",
    "math",
    "types",
    "typing",
}
FORBIDDEN_RUNTIME_CALLS = {"__import__", "eval", "exec", "open"}


def test_nf01_module_is_a_stdlib_only_standalone_research_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))

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

    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in FORBIDDEN_RUNTIME_CALLS
        for node in ast.walk(tree)
    )
    assert "sqlite3" not in source
    assert "import random" not in source
    assert "from random" not in source
    assert "numpy" not in source
    assert "pandas" not in source
