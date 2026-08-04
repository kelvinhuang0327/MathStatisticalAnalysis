"""Architecture boundaries for the M2a research-backtest runner."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "lottolab"
APPLICATION = SRC / "application" / "research_backtest_runner.py"
PROVENANCE = SRC / "infrastructure" / "strategy_source_provenance.py"
CLI = SRC / "interfaces" / "cli" / "research_backtest_runner.py"
MAIN = SRC / "interfaces" / "cli" / "main.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _string_literals(path: Path) -> tuple[str, ...]:
    return tuple(
        node.value
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def test_runner_modules_exist_and_parse() -> None:
    for path in (APPLICATION, PROVENANCE, CLI, MAIN):
        assert path.is_file()
        assert isinstance(_tree(path), ast.Module)


def test_application_runner_imports_no_sqlite_or_interface_layer() -> None:
    imported = _imports(APPLICATION)

    assert "sqlite3" not in imported
    assert "subprocess" not in imported
    assert "pathlib" not in imported
    assert not any(
        module.startswith(
            (
                "lottolab.infrastructure",
                "lottolab.interfaces",
            )
        )
        for module in imported
    )


def test_application_uses_only_registry_selected_adapters() -> None:
    imported = _imports(APPLICATION)
    source = APPLICATION.read_text(encoding="utf-8")

    assert "lottolab.strategies.executable_registry" in imported
    assert "ExecutableRegistry" in source
    assert "load_adapter" in source
    assert not any(
        module.startswith("lottolab.strategies.adapters.biglotto")
        for module in imported
    )


def test_official_scorer_and_rule_remain_domain_owned() -> None:
    imported = _imports(APPLICATION)
    source = APPLICATION.read_text(encoding="utf-8")

    assert "lottolab.domain.lottery_rules" in imported
    assert "BIG_LOTTO_RULE_CONTRACT" in source
    assert "score_big_lotto_ticket" in source
    assert "resolve_big_lotto_prize_tier" in source
    assert "def score_" not in source


def test_application_never_mutates_current_pointer() -> None:
    source = APPLICATION.read_text(encoding="utf-8")

    assert "set_current_run" not in source
    assert "research_run_current_pointer" not in source


def test_cli_is_composition_only_without_sql_or_execution_policy() -> None:
    imported = _imports(CLI)
    source = CLI.read_text(encoding="utf-8")
    literals = _string_literals(CLI)

    assert "sqlite3" not in imported
    assert "RunBigLottoResearchBacktest" in source
    assert "SQLiteOrderedCandidateMaterializationReader" in source
    assert "SQLiteResearchRepository" in source
    assert not any("SELECT " in value or "INSERT " in value for value in literals)
    for forbidden in (
        "minimum_history_draws",
        "commit_target",
        "completed_target_keys",
        "score_big_lotto_ticket",
    ):
        assert forbidden not in source


def test_provenance_helper_is_narrow_and_does_not_import_interfaces_or_sqlite() -> None:
    imported = _imports(PROVENANCE)
    source = PROVENANCE.read_text(encoding="utf-8")

    assert "sqlite3" not in imported
    assert not any(
        module.startswith("lottolab.interfaces") for module in imported
    )
    assert "inspect.getsourcefile" in source
    assert "hashlib.sha256" in source
    assert "git" in source


def test_cli_command_is_registered_without_openapi_surface() -> None:
    main_source = MAIN.read_text(encoding="utf-8")
    openapi_source = (ROOT / "contracts" / "openapi.json").read_text(
        encoding="utf-8"
    )

    assert 'app.command("run-biglotto-research-backtest")' in main_source
    assert "run-biglotto-research-backtest" not in openapi_source
