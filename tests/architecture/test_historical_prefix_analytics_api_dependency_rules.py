"""Architecture guards for the Historical Prefix API shell."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "src/lottolab/interfaces/api/historical_prefix_analytics.py"
APP = ROOT / "src/lottolab/interfaces/api/app.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def test_api_shell_has_no_storage_environment_or_execution_dependencies() -> None:
    imports = _imports(API)
    assert not any(module.startswith("lottolab.infrastructure") for module in imports)
    assert not imports & {"os", "pathlib", "sqlite3", "subprocess"}
    source = API.read_text(encoding="utf-8")
    for forbidden in (
        "execute_strategy",
        "getenv",
        "latest",
        "fallback",
        "SQLite",
    ):
        assert forbidden not in source


def test_app_wires_the_optional_provider_without_invoking_it() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "create_historical_prefix_analytics_router(" in source
    assert source.count("historical_prefix_analytics_result_provider") == 2
    assert "historical_prefix_analytics_result_provider()" not in source


def test_api_uses_merged_query_use_cases_without_reranking() -> None:
    source = API.read_text(encoding="utf-8")
    for use_case in (
        "GetHistoricalPrefixBestRankings",
        "ListHistoricalPrefixStrategyOverview",
        "ListHistoricalPrefixReplay",
    ):
        assert use_case in source
    assert ".sort(" not in source
    assert "sorted(" not in source
