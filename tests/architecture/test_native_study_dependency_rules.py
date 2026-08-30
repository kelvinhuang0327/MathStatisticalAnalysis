"""Static dependency and determinism guards for the native Study/Trial core."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "src" / "lottolab" / "research" / "native_study.py"

REQUIRED_IMPORTS = {
    "lottolab.application.candidate_success_matrix",
    "lottolab.application.historical_prefix_success_windows",
    "lottolab.evidence",
    "lottolab.research.base_method_evaluation",
}

FORBIDDEN_IMPORT_ROOTS = {
    "fastapi",
    "numpy",
    "optuna",
    "ortools",
    "os",
    "pathlib",
    "river",
    "scipy",
    "sklearn",
    "sqlite3",
}

FORBIDDEN_PROJECT_PREFIXES = (
    "lottolab.infrastructure",
    "lottolab.interfaces",
    "lottolab.strategies",
)

FORBIDDEN_IDENTIFIERS = {
    "FastAPI",
    "Path",
    "ResearchStore",
    "Session",
    "connect",
    "getenv",
    "now",
    "open",
    "read_bytes",
    "read_text",
    "today",
    "utcnow",
    "write_bytes",
    "write_text",
}

REQUIRED_IDENTIFIERS = {
    "BASE_METHOD_EVALUATOR_SEMANTIC_VERSION",
    "ExactRational",
    "HistoricalPrefixTemporalHoldoutSplit",
    "MethodDrawObservation",
    "MethodEvaluationRecord",
    "canonical_bytes",
    "sha256_hex",
}


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def _imports(tree: ast.Module) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def _identifiers(tree: ast.Module) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            result.add(node.id)
        elif isinstance(node, ast.Attribute):
            result.add(node.attr)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            result.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            result.update(alias.asname or alias.name for alias in node.names)
    return result


def test_native_study_module_exists_and_parses() -> None:
    assert MODULE.is_file()
    assert isinstance(_tree(), ast.Module)


def test_native_study_reuses_the_named_existing_contract_boundaries() -> None:
    tree = _tree()

    assert _imports(tree) >= REQUIRED_IMPORTS
    assert _identifiers(tree) >= REQUIRED_IDENTIFIERS


def test_native_study_has_no_database_api_filesystem_runtime_or_strategy_import() -> None:
    imports = _imports(_tree())

    assert not {item.partition(".")[0] for item in imports} & FORBIDDEN_IMPORT_ROOTS
    assert not any(
        imported == prefix or imported.startswith(prefix + ".")
        for imported in imports
        for prefix in FORBIDDEN_PROJECT_PREFIXES
    )
    assert not any("adapter" in imported.casefold() for imported in imports)
    assert not any("database" in imported.casefold() for imported in imports)
    assert not any("persistence" in imported.casefold() for imported in imports)


def test_native_study_uses_only_stdlib_and_lottolab_modules() -> None:
    allowed_roots = set(sys.stdlib_module_names) | {"__future__", "lottolab"}
    roots = {item.partition(".")[0] for item in _imports(_tree())}

    assert roots <= allowed_roots


def test_native_study_has_no_filesystem_clock_network_or_runtime_calls() -> None:
    identifiers = _identifiers(_tree())

    assert not identifiers & FORBIDDEN_IDENTIFIERS


def test_native_study_has_no_binary_float_authority() -> None:
    tree = _tree()

    assert not any(
        isinstance(node, ast.Constant) and type(node.value) is float
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "float"
        for node in ast.walk(tree)
    )


def test_native_study_does_not_reference_legacy_auto_optimize() -> None:
    source = MODULE.read_text(encoding="utf-8").casefold()

    assert "auto_optimize" not in source
    assert "autooptimize" not in source
