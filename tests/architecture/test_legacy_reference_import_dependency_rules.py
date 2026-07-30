"""Architecture guards for the Phase 2a legacy reference importer."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPLICATION = (
    ROOT / "src" / "lottolab" / "application" / "legacy_reference_import.py"
)
CLI = ROOT / "src" / "lottolab" / "interfaces" / "cli" / "legacy_reference_import.py"
MAIN = ROOT / "src" / "lottolab" / "interfaces" / "cli" / "main.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            result.add(node.module)
    return result


def test_application_mapping_has_no_infrastructure_or_interface_dependency() -> None:
    imports = _imports(APPLICATION)

    assert not any(
        module.startswith(
            ("lottolab.infrastructure", "lottolab.interfaces")
        )
        for module in imports
    )


def test_cli_is_thin_and_command_is_registered() -> None:
    source = CLI.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")

    assert "sqlite3" not in _imports(CLI)
    assert "predicted_numbers" not in source
    assert "history_cutoff_draw" not in source
    assert 'app.command("import-biglotto-legacy-reference")' in main_source


def test_prohibited_legacy_database_paths_are_absent_from_implementation() -> None:
    source = APPLICATION.read_text(encoding="utf-8") + CLI.read_text(encoding="utf-8")

    assert "lottery_v2.db" not in source
    assert ".local/snapshots" not in source
