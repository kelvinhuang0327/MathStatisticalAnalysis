"""Architecture boundary tests for the canonicalized exact-native BIG_LOTTO replay layers.

Mirrors the existing ``tests/architecture/test_replay_portfolio_execution_dependency_rules.py``
pattern: a tiny, self-contained AST import walker, kept independent of any
protected module. Also covered project-wide by the shared
``tests/architecture/test_dependency_rules.py`` (not modified by this task).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

DOMAIN_PATH = SRC / "domain" / "exact_native_replay.py"
EVIDENCE_PATH = SRC / "evidence" / "exact_native_replay_manifest.py"
REPLAY_USE_CASE_PATH = SRC / "application" / "use_cases" / "replay_exact_native_targets.py"
SHARD_USE_CASE_PATH = SRC / "application" / "use_cases" / "shard_exact_native_replay.py"
CLI_MAIN_PATH = SRC / "interfaces" / "cli" / "exact_native_replay.py"

ALL_NEW_PATHS = (
    DOMAIN_PATH,
    EVIDENCE_PATH,
    REPLAY_USE_CASE_PATH,
    SHARD_USE_CASE_PATH,
    CLI_MAIN_PATH,
)

FORBIDDEN_LITERAL_SUBSTRINGS = (
    ".task-data",
    "/.worktrees/",
    "sys.path.insert",
    "sys.path.append",
    "__path__.append",
)


def _imported_modules(path: Path) -> set[str]:
    relative_parent = path.parent.relative_to(REPO_ROOT / "src")
    package = ".".join(relative_parent.parts)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    modules.add(node.module)
                continue
            package_parts = package.split(".") if package else []
            parent_count = node.level - 1
            if parent_count > len(package_parts):
                if node.module:
                    modules.add(node.module)
                continue
            resolved = package_parts[: len(package_parts) - parent_count]
            if node.module:
                resolved.extend(node.module.split("."))
                modules.add(".".join(resolved))
            elif resolved:
                for alias in node.names:
                    modules.add(f"{'.'.join(resolved)}.{alias.name}")
            else:
                modules.update(alias.name for alias in node.names)
    return modules


def test_every_new_module_exists() -> None:
    for path in ALL_NEW_PATHS:
        assert path.is_file(), path


def test_domain_module_imports_nothing_upward() -> None:
    imports = _imported_modules(DOMAIN_PATH)
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.interfaces",
                "lottolab.evidence",
                "lottolab.strategies",
            )
        )
        for module in imports
    )


def test_domain_module_has_no_hashing_or_canonical_json_logic() -> None:
    """ "the evidence layer may depend on domain; domain must never depend on
    evidence" (see ``lottolab.domain.replay_predictions``): hashing and JSON
    serialization stay entirely in the evidence layer."""

    imports = _imported_modules(DOMAIN_PATH)
    source = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "hashlib" not in imports
    assert "json" not in imports
    assert "hashlib" not in source
    assert "json.dumps" not in source


def test_evidence_module_may_depend_on_domain_but_not_upward() -> None:
    imports = _imported_modules(EVIDENCE_PATH)
    assert not any(
        module.startswith(("lottolab.application", "lottolab.interfaces", "lottolab.strategies"))
        for module in imports
    )
    assert any(module.startswith("lottolab.domain") for module in imports)


def test_use_cases_import_nothing_from_interfaces() -> None:
    for path in (REPLAY_USE_CASE_PATH, SHARD_USE_CASE_PATH):
        imports = _imported_modules(path)
        assert not any(module.startswith("lottolab.interfaces") for module in imports), path


def test_use_cases_may_depend_on_domain_and_evidence() -> None:
    for path in (REPLAY_USE_CASE_PATH, SHARD_USE_CASE_PATH):
        imports = _imported_modules(path)
        assert any(module.startswith("lottolab.domain") for module in imports), path


def test_cli_module_delegates_to_application_use_cases() -> None:
    imports = _imported_modules(CLI_MAIN_PATH)
    assert any(
        module.startswith("lottolab.application.use_cases.replay_exact_native_targets")
        or module.startswith("lottolab.application.use_cases.shard_exact_native_replay")
        for module in imports
    )


def test_cli_module_defines_no_replay_cell_or_seed_metadata() -> None:
    """CLI owns presentation/command parsing only -- never re-implements engine logic."""

    source = CLI_MAIN_PATH.read_text(encoding="utf-8")
    assert "def replay_cell(" not in source
    assert "def seed_metadata(" not in source
    assert "def runtime_bindings(" not in source


def test_no_forbidden_literal_substrings_anywhere() -> None:
    for path in ALL_NEW_PATHS:
        source = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_LITERAL_SUBSTRINGS:
            assert forbidden not in source, f"{path} contains forbidden substring {forbidden!r}"


def test_no_import_of_unavailable_storage_authorities() -> None:
    """No real import edge to the unpublished module; docstrings may still
    name it in prose explaining why it was deliberately not ported."""

    for path in ALL_NEW_PATHS:
        imports = _imported_modules(path)
        assert not any("storage_authorities" in module for module in imports), path
        source = path.read_text(encoding="utf-8")
        assert "StorageAuthorityRegistry(" not in source, path
        assert "StorageAuthorityRegistry.from_file" not in source, path


def test_no_apply_runtime_optimizations_reference() -> None:
    """No call or definition; docstrings may still name it in prose
    explaining why the monkeypatch was deliberately not ported."""

    for path in ALL_NEW_PATHS:
        source = path.read_text(encoding="utf-8")
        assert "_apply_runtime_optimizations(" not in source, path
        assert "def _apply_runtime_optimizations" not in source, path
