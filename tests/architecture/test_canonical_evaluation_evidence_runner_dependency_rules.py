"""Architecture guards for the V1C canonical evaluation runner.

The runner's whole claim is that it orchestrates and nothing else. That claim
is only as good as its import surface, so these guards pin it statically:

* the runner composes the existing replay, V1A and V1B seams by name, so a
  second replay engine, evaluator, scoring table or canonical-JSON authority
  cannot appear without this failing;
* it never reaches the ResearchStore, the strategy evidence registry, the
  canonical evidence registry, any draw repository or schema initialiser, or
  the API/CLI layer, so it has no way to persist, promote or publish anything;
* it never resolves the production database path, which is what keeps
  ``ReplayResearchSession``'s production default out of reach.

Every assertion reads identifiers and imports out of the parsed module rather
than grepping its text, so the runner's own prose -- which names the very
surfaces it is forbidden to use -- can neither trip a guard nor satisfy one.

The runner does introduce the repository's first ``research -> interfaces``
edge. That direction is deliberate and is not forbidden by
tests/architecture/test_dependency_rules.py -- ``interfaces`` is the
composition root, and ``research`` carries no layering constraint there -- so
it is pinned here as an intentional, named edge rather than left implicit.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "research"
    / "canonical_evaluation_evidence_runner.py"
)

#: The only ``lottolab`` packages the orchestration is allowed to reach.
ALLOWED_PACKAGE_PREFIXES = (
    "lottolab.domain",
    "lottolab.evidence",
    "lottolab.infrastructure.persistence.draw_schema",
    "lottolab.interfaces.research.replay_research_session",
    "lottolab.research",
    "lottolab.strategies.catalog",
)

#: Persistence, registry, promotion and publication packages this module must
#: not be able to import at all.
FORBIDDEN_PACKAGE_PREFIXES = (
    "lottolab.api",
    "lottolab.application",
    "lottolab.infrastructure.persistence.repositories",
    "lottolab.infrastructure.persistence.research_repository",
    "lottolab.infrastructure.persistence.research_schema",
    "lottolab.infrastructure.strategy_evidence_registry",
    "lottolab.interfaces.api",
    "lottolab.interfaces.cli",
    "sqlite3",
)

#: Names whose presence anywhere in the runner's code would mean it had grown
#: a persistence, registry, production-path or ranking capability.
FORBIDDEN_IDENTIFIERS = (
    "ResearchStore",
    "SQLiteDrawDataRepository",
    "apply_valid_import",
    "canonical_evidence_registry",
    "initialize_schema",
    "load_approved_ranking_policy_registry",
    "load_canonical_evidence_registry",
    "open_database",
    "resolve_local_data_paths",
)

#: The existing seams the runner must be composing, checked as real code
#: references rather than as words in its docstring.
REQUIRED_IDENTIFIERS = (
    "ReplayResearchSession",
    "WINDOW_SIZES",
    "canonical_json",
    "evaluate_replayed_single_ticket_method",
    "materialize_method_evaluation_evidence",
    "validate_evidence_artifact",
)


def _module() -> ast.Module:
    return ast.parse(RUNNER.read_text(encoding="utf-8"))


def _imports(tree: ast.Module) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _identifiers(tree: ast.Module) -> set[str]:
    """Every name the module's *code* references, ignoring docstrings and comments."""

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
    return names


def test_runner_module_exists_and_parses() -> None:
    assert RUNNER.is_file()
    assert isinstance(_module(), ast.Module)


def test_runner_imports_only_the_named_composition_surfaces() -> None:
    for module in _imports(_module()):
        if module.startswith("lottolab"):
            assert module.startswith(ALLOWED_PACKAGE_PREFIXES), module


def test_runner_cannot_import_persistence_registry_or_api_surfaces() -> None:
    imports = _imports(_module())

    for module in imports:
        assert not module.startswith(FORBIDDEN_PACKAGE_PREFIXES), module


def test_runner_references_no_persistence_registry_or_production_path_name() -> None:
    identifiers = _identifiers(_module())

    for forbidden in FORBIDDEN_IDENTIFIERS:
        assert forbidden not in identifiers, forbidden


def test_runner_composes_the_existing_seams_by_name() -> None:
    identifiers = _identifiers(_module())

    for required in REQUIRED_IDENTIFIERS:
        assert required in identifiers, required


def test_runner_defines_no_ranking_promotion_or_scoring_function() -> None:
    tree = _module()

    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }
    for name in defined:
        assert not name.lstrip("_").startswith(
            ("rank", "promote", "admit", "reject", "score", "optimi", "compare")
        ), name


def test_runner_local_data_paths_is_an_input_never_a_resolution() -> None:
    tree = _module()

    assert "LocalDataPaths" in _identifiers(tree)
    assert "lottolab.infrastructure.persistence.draw_schema" in _imports(tree)
    assert "resolve_local_data_paths" not in _identifiers(tree)
