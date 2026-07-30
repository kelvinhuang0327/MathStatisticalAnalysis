"""Dependency-boundary and scope contract for the P338B root-CLI registration.

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
CORE_ARCHITECTURE_TEST_FILE = (
    REPO_ROOT / "tests" / "architecture" / "test_draw_data_integrity_dependency_rules.py"
)

_AUTHORIZED_P338B_REFERENCE_FILES = {
    CLI_FILE,
    MAIN_FILE,
    UNIT_TEST_FILE,
    INTEGRATION_TEST_FILE,
    ARCHITECTURE_TEST_FILE,
    CORE_ARCHITECTURE_TEST_FILE,
}

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


def _main_source() -> str:
    return MAIN_FILE.read_text(encoding="utf-8")


def _main_tree() -> ast.Module:
    return ast.parse(_main_source())


def _root_registration_calls() -> list[ast.Call]:
    registrations: list[ast.Call] = []
    for node in ast.walk(_main_tree()):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Call):
            continue
        command_call = node.func
        if not isinstance(command_call.func, ast.Attribute):
            continue
        if not isinstance(command_call.func.value, ast.Name):
            continue
        if command_call.func.value.id != "app" or command_call.func.attr != "command":
            continue
        if len(command_call.args) != 1:
            continue
        command_name = command_call.args[0]
        if (
            isinstance(command_name, ast.Constant)
            and command_name.value == "inspect-draw-data-integrity"
        ):
            registrations.append(node)
    return registrations


def test_the_six_authorized_p338b_paths_exist() -> None:
    assert len(_AUTHORIZED_P338B_REFERENCE_FILES) == 6
    assert all(path.is_file() for path in _AUTHORIZED_P338B_REFERENCE_FILES)


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


def test_cli_main_registers_exactly_one_bounded_adapter_command() -> None:
    main_source = _main_source()
    main_tree = _main_tree()
    adapter_imports = [
        node
        for node in ast.walk(main_tree)
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module == "lottolab.interfaces.cli.draw_data_integrity"
    ]
    registrations = _root_registration_calls()
    command_name_constants = [
        node
        for node in ast.walk(main_tree)
        if isinstance(node, ast.Constant) and node.value == "inspect-draw-data-integrity"
    ]

    assert len(adapter_imports) == 1
    assert [alias.name for alias in adapter_imports[0].names] == [
        "draw_data_integrity_command"
    ]
    assert len(registrations) == 1
    assert len(registrations[0].args) == 1
    assert isinstance(registrations[0].args[0], ast.Name)
    assert registrations[0].args[0].id == "draw_data_integrity_command"
    assert registrations[0].keywords == []
    assert len(command_name_constants) == 1

    for forbidden in (
        "DrawDataIntegrityReader",
        "SQLiteDrawDataIntegrityReader",
        "InspectDrawDataIntegrity",
        "InspectDrawDataIntegrityRequest",
    ):
        assert forbidden not in main_source


def test_cli_main_contains_no_draw_data_inspection_or_database_logic() -> None:
    main_source = _main_source()
    main_imports: set[str] = set()
    for node in ast.walk(_main_tree()):
        if isinstance(node, ast.Import):
            main_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            main_imports.add(node.module)

    assert "sqlite3" not in main_imports
    assert "inspect_draw_data_integrity_report" not in main_source
    assert re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|PRAGMA)\b", main_source) is None


def test_no_other_repository_file_outside_p338b_references_the_cli_module() -> None:
    """Guard the exact six-path P338B registration scope."""

    needle = "interfaces.cli.draw_data_integrity"
    violations: list[Path] = []
    for path in (*SRC.rglob("*.py"), *(REPO_ROOT / "tests").rglob("*.py")):
        if path in _AUTHORIZED_P338B_REFERENCE_FILES:
            continue
        if needle in path.read_text(encoding="utf-8"):
            violations.append(path)
    assert not violations, f"unexpected references outside the P338B files: {violations}"
