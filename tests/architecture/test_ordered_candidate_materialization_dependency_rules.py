"""Architecture guards for the P336 materialization runtime chain."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"
MODULES = {
    "domain": SRC / "domain" / "ordered_candidate_materialization.py",
    "application": (
        SRC
        / "application"
        / "use_cases"
        / "materialize_ordered_candidate_emissions.py"
    ),
    "evidence": SRC / "evidence" / "ordered_candidate_emission_package.py",
    "reader": (
        SRC
        / "infrastructure"
        / "persistence"
        / "ordered_candidate_materialization_reader.py"
    ),
    "writer": SRC / "infrastructure" / "ordered_candidate_package_writer.py",
    "cli": SRC / "interfaces" / "cli" / "ordered_candidate_materialization.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_all_exact_runtime_modules_exist_and_parse() -> None:
    assert all(path.is_file() for path in MODULES.values())
    for path in MODULES.values():
        assert isinstance(ast.parse(path.read_text(encoding="utf-8")), ast.Module)


def test_domain_is_pure_and_imports_only_domain_contracts() -> None:
    imports = _imports(MODULES["domain"])

    for module in imports:
        if module.startswith("lottolab"):
            assert module.startswith("lottolab.domain"), module
    assert not imports & {"os", "sqlite3", "subprocess"}


def test_application_has_no_infrastructure_or_interface_dependency() -> None:
    imports = _imports(MODULES["application"])

    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
        for module in imports
    )


def test_evidence_has_no_application_infrastructure_or_interface_dependency() -> None:
    imports = _imports(MODULES["evidence"])

    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "lottolab.strategies",
            )
        )
        for module in imports
    )


def test_infrastructure_never_imports_interfaces_or_initializes_schema() -> None:
    for name in ("reader", "writer"):
        path = MODULES[name]
        imports = _imports(path)
        source = path.read_text(encoding="utf-8")
        assert not any(
            module.startswith("lottolab.interfaces") for module in imports
        )
        assert "initialize_schema" not in source
        assert "apply_valid_import" not in source


def test_cli_is_composition_only_and_does_not_open_sqlite_directly() -> None:
    imports = _imports(MODULES["cli"])
    source = MODULES["cli"].read_text(encoding="utf-8")

    assert "sqlite3" not in imports
    assert "open_database" not in source
    assert "initialize_schema" not in source
    assert "apply_valid_import" not in source
    assert "MaterializeOrderedCandidateEmissions" in source
    assert "SQLiteOrderedCandidateMaterializationReader" in source
    assert "OrderedCandidatePackageWriter" in source
