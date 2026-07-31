from __future__ import annotations

import ast
from pathlib import Path

from lottolab.interfaces.api.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
API_MODULE = (
    REPO_ROOT / "src/lottolab/interfaces/api/b649_multi_ticket_records.py"
)
READER_MODULE = (
    REPO_ROOT
    / "src/lottolab/infrastructure/biglotto_multi_ticket_record_reader.py"
)
PATH = "/api/v1/b649-multi-ticket-records"
SUMMARY_PATH = f"{PATH}/summary"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_http_adapter_cannot_reach_execution_backtest_or_persistence_modules() -> None:
    imports = _imports(API_MODULE)

    assert not any("biglotto_multi_ticket_backtest" in name for name in imports)
    assert not any(".persistence" in name for name in imports)
    assert not any("strategies.catalog" in name for name in imports)
    assert not any("generate" in name for name in imports)


def test_runtime_reader_uses_one_fixed_resource_without_discovery_language() -> None:
    source = READER_MODULE.read_text(encoding="utf-8")
    forbidden_fragments = (
        ".glob(",
        ".rglob(",
        "latest",
        "newest",
        "sqlite",
        "biglotto_multi_ticket_backtest",
    )

    assert 'PROJECTION_RESOURCE_NAME = "biglotto_multi_ticket_historical_records_v1.json"' in source
    assert all(fragment not in source.casefold() for fragment in forbidden_fragments)


def test_openapi_surface_is_get_only_and_has_no_execution_variant() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths[PATH]) == {"get"}
    assert set(paths[SUMMARY_PATH]) == {"get"}
    assert not any(
        candidate.startswith(PATH)
        and any(token in candidate for token in ("execute", "generate", "backtest"))
        for candidate in paths
    )
