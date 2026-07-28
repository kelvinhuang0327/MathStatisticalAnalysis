"""Dependency-boundary contract for the P337 draw-data integrity inspection core.

Self-contained on purpose: this does not import helpers from
``test_dependency_rules.py`` so it stays independently verifiable.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

DOMAIN_FILE = SRC / "domain" / "draw_data_integrity.py"
APPLICATION_FILE = SRC / "application" / "use_cases" / "inspect_draw_data_integrity.py"
INFRASTRUCTURE_FILE = SRC / "infrastructure" / "persistence" / "draw_data_integrity_reader.py"

_FORBIDDEN_PREFIXES = (
    "lottolab.interfaces",
    "lottolab.strategies",
    "lottolab.domain.replay_history",
    "lottolab.domain.replay_predictions",
    "lottolab.domain.replay_scoring",
    "lottolab.domain.replay_scoring_projection",
    "lottolab.domain.replay_portfolio_ranking",
    "lottolab.domain.historical_results",
    "lottolab.domain.ordered_candidate_emission",
    "lottolab.domain.ordered_candidate_evidence",
    "lottolab.domain.ordered_candidate_materialization",
    "lottolab.domain.strategy_success_evaluation",
    "lottolab.domain.strategy_success_measurement",
    "lottolab.application.replay_historical_predictions",
    "lottolab.application.rank_replay_strategy_portfolios",
    "lottolab.application.materialize_ordered_candidate_emissions",
    "lottolab.application.generate_ordered_candidate_emission",
    "lottolab.application.query_historical_results",
    "lottolab.application.import_historical_results",
    "lottolab.infrastructure.persistence.ordered_candidate_materialization_reader",
    "lottolab.infrastructure.persistence.replay_history_reader",
    "lottolab.infrastructure.persistence.replay_target_outcome_reader",
    "lottolab.infrastructure.persistence.replay_scoring_projection_repository",
    "lottolab.infrastructure.persistence.historical_repositories",
    "lottolab.infrastructure.persistence.historical_prefix_success_window_reader",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = ".".join(path.parent.relative_to(REPO_ROOT / "src").parts)
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
            base_parts = package_parts[: len(package_parts) - parent_count]
            if node.module:
                modules.add(".".join((*base_parts, *node.module.split("."))))
            else:
                for alias in node.names:
                    modules.add(".".join((*base_parts, alias.name)))
    return modules


def test_the_seven_authorized_files_exist() -> None:
    assert DOMAIN_FILE.is_file()
    assert APPLICATION_FILE.is_file()
    assert INFRASTRUCTURE_FILE.is_file()
    assert (REPO_ROOT / "tests" / "unit" / "test_draw_data_integrity.py").is_file()
    assert (REPO_ROOT / "tests" / "unit" / "test_inspect_draw_data_integrity.py").is_file()
    assert (REPO_ROOT / "tests" / "integration" / "test_draw_data_integrity_reader.py").is_file()
    assert (
        REPO_ROOT / "tests" / "architecture" / "test_draw_data_integrity_dependency_rules.py"
    ).is_file()


def test_domain_module_imports_standard_library_only() -> None:
    imports = _imported_modules(DOMAIN_FILE)
    assert not any(module.startswith("lottolab") for module in imports), imports
    assert "sqlite3" not in imports


def test_application_module_imports_only_domain_and_standard_library() -> None:
    imports = _imported_modules(APPLICATION_FILE)
    lottolab_imports = {module for module in imports if module.startswith("lottolab")}
    assert lottolab_imports == {"lottolab.domain.draw_data_integrity"}
    assert "sqlite3" not in imports


def test_application_module_does_not_import_infrastructure_or_interfaces() -> None:
    imports = _imported_modules(APPLICATION_FILE)
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces", "lottolab.strategies"))
        for module in imports
    )


def test_reader_protocol_is_defined_locally_not_in_the_shared_ports_registry() -> None:
    ports_source = (SRC / "application" / "ports.py").read_text(encoding="utf-8")
    assert "DrawDataIntegrityReader" not in ports_source
    application_source = APPLICATION_FILE.read_text(encoding="utf-8")
    assert "class DrawDataIntegrityReader(Protocol)" in application_source


def test_infrastructure_reader_implements_the_protocol_structurally() -> None:
    source = INFRASTRUCTURE_FILE.read_text(encoding="utf-8")
    assert "class SQLiteDrawDataIntegrityReader" in source
    assert "def inspect(self, database" in source
    # No factory, no registry, no application-side registration call.
    assert "register" not in source.casefold()
    assert "Protocol" not in source


def test_infrastructure_reader_imports_only_domain_and_draw_schema() -> None:
    imports = _imported_modules(INFRASTRUCTURE_FILE)
    lottolab_imports = {module for module in imports if module.startswith("lottolab")}
    assert lottolab_imports == {
        "lottolab.domain.draw_data_integrity",
        "lottolab.infrastructure.persistence.draw_schema",
    }


def test_none_of_the_three_production_files_import_forbidden_scope() -> None:
    for path in (DOMAIN_FILE, APPLICATION_FILE, INFRASTRUCTURE_FILE):
        imports = _imported_modules(path)
        violations = [
            module
            for module in imports
            if module.startswith(_FORBIDDEN_PREFIXES)
        ]
        assert not violations, f"{path.name} imports forbidden scope: {violations}"


def test_cli_main_has_no_draw_data_integrity_registration() -> None:
    cli_main = (SRC / "interfaces" / "cli" / "main.py").read_text(encoding="utf-8")
    assert "draw_data_integrity" not in cli_main
    assert "DrawDataIntegrityReader" not in cli_main
    assert "InspectDrawDataIntegrity" not in cli_main


def test_api_layer_has_no_draw_data_integrity_registration() -> None:
    api_directory = SRC / "interfaces" / "api"
    for path in api_directory.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "draw_data_integrity" not in source, path
        assert "DrawDataIntegrityReader" not in source, path
        assert "InspectDrawDataIntegrity" not in source, path


def test_no_other_existing_repository_file_references_the_new_modules() -> None:
    """Guards the exact seven-path scope: nothing outside the new files wires this in."""

    needle = "draw_data_integrity"
    new_files = {DOMAIN_FILE, APPLICATION_FILE, INFRASTRUCTURE_FILE}
    violations: list[Path] = []
    for path in SRC.rglob("*.py"):
        if path in new_files:
            continue
        if needle in path.read_text(encoding="utf-8"):
            violations.append(path.relative_to(SRC))
    assert not violations, f"unexpected references outside the new files: {violations}"
