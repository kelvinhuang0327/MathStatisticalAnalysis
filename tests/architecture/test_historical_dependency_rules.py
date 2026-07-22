"""Architecture boundary tests scoped to the BLHQ R1 historical-results modules.

A task-owned counterpart to the shared ``tests/architecture/test_dependency_rules.py``
(protected, not modified by this task). Re-implements a tiny, self-contained AST
import walker rather than importing that protected module, keeping this file
fully independent of it.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

HISTORICAL_MODULE_PATHS: dict[str, Path] = {
    "lottolab.domain.historical_results": SRC / "domain" / "historical_results.py",
    "lottolab.normalization.historical_import": SRC / "normalization" / "historical_import.py",
    "lottolab.application.use_cases.import_historical_results": (
        SRC / "application" / "use_cases" / "import_historical_results.py"
    ),
    "lottolab.infrastructure.persistence.historical_schema": (
        SRC / "infrastructure" / "persistence" / "historical_schema.py"
    ),
    "lottolab.infrastructure.persistence.historical_repositories": (
        SRC / "infrastructure" / "persistence" / "historical_repositories.py"
    ),
}


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


def test_all_five_historical_modules_exist() -> None:
    for name, path in HISTORICAL_MODULE_PATHS.items():
        assert path.is_file(), f"{name} missing at {path}"


def test_domain_historical_results_imports_no_other_lottolab_layer() -> None:
    imports = _imported_modules(HISTORICAL_MODULE_PATHS["lottolab.domain.historical_results"])
    assert not any(module.startswith("lottolab") for module in imports)


def test_normalization_historical_import_imports_only_domain_and_evidence_canonical_json() -> None:
    path = HISTORICAL_MODULE_PATHS["lottolab.normalization.historical_import"]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("lottolab"):
                    assert alias.name.startswith("lottolab.domain.historical_results"), alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if not node.module.startswith("lottolab"):
                continue
            if node.module == "lottolab.evidence":
                assert {alias.name for alias in node.names} <= {"canonical_json"}
            else:
                assert node.module.startswith("lottolab.domain.historical_results"), node.module


def test_application_use_case_imports_neither_normalization_nor_evidence() -> None:
    path = HISTORICAL_MODULE_PATHS["lottolab.application.use_cases.import_historical_results"]
    imports = _imported_modules(path)
    assert not any(
        module.startswith(("lottolab.normalization", "lottolab.evidence")) for module in imports
    )
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces")) for module in imports
    )


def test_infrastructure_historical_modules_import_no_evidence_or_canonical_hashing() -> None:
    for name in (
        "lottolab.infrastructure.persistence.historical_schema",
        "lottolab.infrastructure.persistence.historical_repositories",
    ):
        path = HISTORICAL_MODULE_PATHS[name]
        imports = _imported_modules(path)
        assert not any(module.startswith("lottolab.evidence") for module in imports), name
        assert "canonical_json" not in path.read_text(encoding="utf-8"), name


def test_infrastructure_historical_modules_do_not_import_normalization_or_interfaces() -> None:
    for name in (
        "lottolab.infrastructure.persistence.historical_schema",
        "lottolab.infrastructure.persistence.historical_repositories",
    ):
        imports = _imported_modules(HISTORICAL_MODULE_PATHS[name])
        assert not any(
            module.startswith(("lottolab.normalization", "lottolab.interfaces"))
            for module in imports
        ), name


def test_no_historical_module_imports_strategies_interfaces_or_generate_one_bet() -> None:
    for name, path in HISTORICAL_MODULE_PATHS.items():
        imports = _imported_modules(path)
        assert not any(
            module.startswith(("lottolab.strategies", "lottolab.interfaces")) for module in imports
        ), name
        assert "GenerateOneBet" not in path.read_text(encoding="utf-8"), name


def test_application_ports_declares_historical_result_repository_protocol() -> None:
    ports_source = (SRC / "application" / "ports.py").read_text(encoding="utf-8")
    assert "class HistoricalResultRepository(Protocol)" in ports_source
    assert "commit_import" in ports_source


def test_historical_repositories_and_schema_never_open_a_default_or_canonical_database() -> None:
    for name in (
        "lottolab.infrastructure.persistence.historical_schema",
        "lottolab.infrastructure.persistence.historical_repositories",
    ):
        path = HISTORICAL_MODULE_PATHS[name]
        source = path.read_text(encoding="utf-8")
        assert "os.environ" not in source, name
        assert "resolve_local_data_paths" not in source, name
        imports = _imported_modules(path)
        assert not any("draw_schema" in module for module in imports), name
