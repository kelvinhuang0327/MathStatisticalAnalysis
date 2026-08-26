"""Architecture proof for the DB-free pairwise Hawkes research boundary."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "src" / "lottolab" / "research" / "biglotto_l2_pairwise_hawkes.py"


def _source() -> str:
    return MODULE.read_text(encoding="utf-8")


def _tree() -> ast.Module:
    return ast.parse(_source())


def _imports() -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
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


def test_candidate_module_exists_in_research_layer() -> None:
    assert MODULE.is_file()


def test_candidate_imports_no_database_network_or_external_runtime() -> None:
    imports = _imports()
    assert imports.isdisjoint(
        {
            "numpy",
            "scipy",
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


def test_candidate_has_no_persistence_network_or_random_calls() -> None:
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
    source = _source()
    assert "random." not in source
    assert "np.random" not in source
    assert "docs/research/matrix-native-results" not in source
    assert "canonical DB" not in source
    assert "BMSGV1_L2_PAIRWISE_30ba58a14f494ef4" not in source


def test_candidate_contains_no_library_optimizer_surface() -> None:
    source = _source()
    assert "scipy.optimize" not in source
    assert "minimize(" not in source
    assert "numpy" not in _imports()
