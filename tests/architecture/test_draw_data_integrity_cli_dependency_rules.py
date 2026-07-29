"""Dependency-boundary and scope contract for the P338A draw-data integrity CLI adapter.

Self-contained on purpose, mirroring ``test_draw_data_integrity_dependency_rules.py``:
this file does not import helpers from other architecture tests so it stays
independently verifiable.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

CLI_FILE = SRC / "interfaces" / "cli" / "draw_data_integrity.py"
MAIN_FILE = SRC / "interfaces" / "cli" / "main.py"
UNIT_TEST_FILE = REPO_ROOT / "tests" / "unit" / "test_draw_data_integrity_cli.py"
INTEGRATION_TEST_FILE = (
    REPO_ROOT / "tests" / "integration" / "test_draw_data_integrity_cli_sqlite.py"
)
ARCHITECTURE_TEST_FILE = Path(__file__).resolve()

_ALLOWED_LOTTOLAB_IMPORTS = {
    "lottolab.application.use_cases.inspect_draw_data_integrity",
    "lottolab.domain.draw_data_integrity",
    "lottolab.infrastructure.persistence.draw_data_integrity_reader",
    "lottolab.infrastructure.persistence.draw_schema",
}


def _source() -> str:
    return CLI_FILE.read_text(encoding="utf-8")


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


def test_the_four_authorized_paths_exist() -> None:
    assert CLI_FILE.is_file()
    assert UNIT_TEST_FILE.is_file()
    assert INTEGRATION_TEST_FILE.is_file()
    assert ARCHITECTURE_TEST_FILE.is_file()


def test_cli_imports_only_the_merged_p337_core_and_standard_library() -> None:
    lottolab_imports = {
        module for module in _absolute_imports() if module.startswith("lottolab.")
    }
    assert lottolab_imports == _ALLOWED_LOTTOLAB_IMPORTS


def test_cli_has_no_strategies_api_or_other_domain_dependency() -> None:
    imports = _absolute_imports()
    assert not any(
        module.startswith(
            (
                "lottolab.strategies",
                "lottolab.interfaces.api",
                "lottolab.normalization",
            )
        )
        for module in imports
    )


def test_cli_does_not_reimplement_database_checking_logic() -> None:
    source = _source()
    imports = _absolute_imports()

    assert "sqlite3" not in imports
    assert re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|PRAGMA)\b", source) is None


def test_cli_uses_the_p337_core_symbols_it_is_required_to_delegate_to() -> None:
    source = _source()
    assert "InspectDrawDataIntegrity" in source
    assert "InspectDrawDataIntegrityRequest" in source
    assert "SQLiteDrawDataIntegrityReader" in source


def test_cli_has_no_default_environment_home_or_ambient_path_resolution() -> None:
    source = _source()
    tree = _tree()
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "os.environ" not in source
    assert "getenv" not in source
    assert "environ" not in source
    assert "Path.home" not in source
    assert "expanduser" not in source
    assert "resolve_local_data_paths" not in source
    assert not {"glob", "rglob", "iterdir"}.intersection(called_attributes)
    assert "LOTTOLAB_DATA_DIR" not in source


def test_cli_option_does_not_pre_reject_a_missing_file() -> None:
    source = _source()
    assert "exists=True" not in source
    assert "exists =True" not in source.replace(" ", " ")


def test_cli_never_creates_or_migrates_storage() -> None:
    source = _source()
    assert "initialize_schema" not in source
    assert "mkdir" not in source
    assert "open_database" not in source
    assert "apply_migration" not in source.casefold()
    assert "run_migration" not in source.casefold()


def test_cli_output_never_carries_timestamp_hostname_or_process_identity() -> None:
    source = _source()
    for forbidden in ("hostname", "socket.gethostname", "os.getpid", "datetime", "platform"):
        assert forbidden not in source


def test_cli_main_has_no_draw_data_integrity_registration_yet() -> None:
    main_source = MAIN_FILE.read_text(encoding="utf-8")
    assert "draw_data_integrity" not in main_source
    assert "DrawDataIntegrityReader" not in main_source
    assert "InspectDrawDataIntegrity" not in main_source
    assert "draw-data-integrity" not in main_source


def test_no_other_existing_repository_file_outside_p338a_references_the_cli_module() -> None:
    """Guards the exact four-path P338A scope, mirroring the P337 core's own guard."""

    needle = "interfaces.cli.draw_data_integrity"
    authorized_files = {CLI_FILE, UNIT_TEST_FILE, INTEGRATION_TEST_FILE, ARCHITECTURE_TEST_FILE}
    violations: list[Path] = []
    for path in (*SRC.rglob("*.py"), *(REPO_ROOT / "tests").rglob("*.py")):
        if path in authorized_files:
            continue
        if needle in path.read_text(encoding="utf-8"):
            violations.append(path)
    assert not violations, f"unexpected references outside the P338A files: {violations}"
