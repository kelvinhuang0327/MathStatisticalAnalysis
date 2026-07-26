"""Architecture guards for the target-native Historical Results import CLI."""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "src" / "lottolab" / "interfaces" / "cli" / "historical_import.py"
MAIN_PATH = REPO_ROOT / "src" / "lottolab" / "interfaces" / "cli" / "main.py"


def _source() -> str:
    return CLI_PATH.read_text(encoding="utf-8")


def _tree() -> ast.Module:
    return ast.parse(_source())


def _absolute_imports() -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module)
    return imports


def _call_lines(name: str) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id == name:
            lines.append(node.lineno)
    return sorted(lines)


def test_cli_module_and_main_registration_exist_at_the_authorized_paths() -> None:
    assert CLI_PATH.is_file()
    main_source = MAIN_PATH.read_text(encoding="utf-8")
    assert 'app.command("import-historical-results")(historical_import_command)' in main_source


def test_cli_imports_only_existing_normalizer_use_case_domain_and_repository() -> None:
    lottolab_imports = {
        module for module in _absolute_imports() if module.startswith("lottolab.")
    }
    assert lottolab_imports == {
        "lottolab.application.use_cases.import_historical_results",
        "lottolab.domain.historical_results",
        "lottolab.infrastructure.persistence.historical_repositories",
        "lottolab.normalization.historical_import",
    }


def test_complete_normalization_precedes_repository_and_use_case_composition() -> None:
    normalizer_lines = _call_lines("verify_and_normalize_historical_import")
    repository_lines = _call_lines("SQLiteHistoricalResultRepository")
    use_case_lines = _call_lines("ImportHistoricalResults")

    assert len(normalizer_lines) == 1
    assert len(repository_lines) == 1
    assert len(use_case_lines) == 1
    assert normalizer_lines[0] < repository_lines[0] < use_case_lines[0]
    source = _source()
    assert "HistoricalImportOutcome.IMPORT_PASS" in source
    assert "verification.normalized_import" in source


def test_cli_contains_no_sql_persistence_or_envelope_reimplementation() -> None:
    source = _source()
    imports = _absolute_imports()

    assert "sqlite3" not in imports
    assert re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|PRAGMA)\b", source) is None
    assert "canonical_json" not in source
    assert "pydantic" not in source
    assert "manifest_sha256" in source
    assert "import_identity_sha256" in source


def test_cli_has_no_legacy_http_frontend_or_conversion_dependencies() -> None:
    source = _source()
    imports = _absolute_imports()

    assert not any(
        module.startswith(("httpx", "requests", "fastapi", "lottolab.interfaces.api"))
        for module in imports
    )
    assert "frontend" not in source.casefold()
    assert "legacy_" not in source.casefold()
    assert "lotterynew" in source.casefold()


def test_cli_has_no_default_environment_fallback_or_directory_scan() -> None:
    source = _source()
    tree = _tree()
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "os.environ" not in source
    assert not {"glob", "rglob", "iterdir"}.intersection(called_attributes)
    assert "latest" not in source.casefold()
    assert "newest" not in source.casefold()
    assert "default" not in source.casefold()
    assert ".db" not in source
