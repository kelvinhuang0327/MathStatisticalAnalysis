"""Architecture boundaries for persisted Historical Prefix success windows."""

from __future__ import annotations

import ast
from pathlib import Path

from lottolab.interfaces.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
READ_MODELS = ROOT / "src/lottolab/application/historical_prefix_success_windows.py"
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
READER = (
    ROOT
    / "src/lottolab/infrastructure/persistence/"
    "historical_prefix_success_window_reader.py"
)
ROUTER = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"
APP = ROOT / "src/lottolab/interfaces/api/app.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module)
    return imported


def test_all_vertical_modules_exist() -> None:
    assert all(path.is_file() for path in (READ_MODELS, USE_CASE, READER, ROUTER))


def test_read_models_are_pure_immutable_application_data() -> None:
    imports = _imports(READ_MODELS)
    forbidden = {
        "fastapi",
        "os",
        "pathlib",
        "pydantic",
        "random",
        "sqlite3",
        "subprocess",
        "time",
        "uuid",
    }

    assert not imports & forbidden
    assert not any(name.startswith("lottolab.infrastructure") for name in imports)
    assert not any(name.startswith("lottolab.interfaces") for name in imports)
    source = READ_MODELS.read_text(encoding="utf-8")
    assert "@dataclass(frozen=True, slots=True)" in source


def test_use_case_depends_on_port_and_domain_but_not_interface_or_infrastructure() -> None:
    imports = _imports(USE_CASE)

    assert "lottolab.application.ports" in imports
    assert not any(name.startswith("lottolab.infrastructure") for name in imports)
    assert not any(name.startswith("lottolab.interfaces") for name in imports)
    assert not imports & {"fastapi", "pathlib", "pydantic", "sqlite3"}


def test_sqlite_reader_has_no_write_schema_init_strategy_execution_or_analytics_recompute() -> None:
    source = READER.read_text(encoding="utf-8")
    imports = _imports(READER)

    assert not any(name.startswith("lottolab.interfaces") for name in imports)
    assert "read_only=True" in source
    for forbidden in (
        "initialize_schema",
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "CREATE TABLE",
        "BEGIN ",
        "TEMP TABLE",
        "execute_strategy",
        "analyze_historical_prefixes",
        "evaluate_strategy_success_windows",
    ):
        assert forbidden not in source


def test_router_is_thin_get_only_and_contains_no_sql_or_evaluator_logic() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    imports = _imports(ROUTER)

    assert not any(name.startswith("lottolab.infrastructure") for name in imports)
    assert "sqlite3" not in imports
    assert "@router.get" in source
    assert "@router.post" not in source
    assert "@router.put" not in source
    assert "@router.patch" not in source
    assert "@router.delete" not in source
    assert "SELECT " not in source
    assert "evaluate_strategy_success_windows" not in source


def test_app_and_openapi_keep_optional_reader_factory_lazy() -> None:
    calls = 0

    def forbidden_factory():
        nonlocal calls
        calls += 1
        raise AssertionError("reader factory must stay lazy")

    app = create_app(
        historical_prefix_success_window_source_reader_factory=forbidden_factory
    )
    paths = app.openapi()["paths"]

    assert calls == 0
    assert "/api/v1/historical-prefix-success-windows" in paths
    assert (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}"
    ) in paths
    assert (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/matrix"
    ) in paths
    assert (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts"
    ) in paths
    assert (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics"
    ) in paths
    assert (
        "/api/v1/historical-prefix-success-windows/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
        "cross-import-concordance"
    ) in paths


def test_vertical_does_not_change_existing_historical_prefix_provider_contract() -> None:
    app_source = APP.read_text(encoding="utf-8")
    paths = set(create_app().openapi()["paths"])

    assert "historical_prefix_analytics_result_provider" in app_source
    assert "/api/v1/historical-prefix-analytics/rankings" in paths
    assert "/api/v1/historical-prefix-analytics/strategies" in paths
    assert "/api/v1/historical-results/runs" in paths
