from __future__ import annotations

import ast
from pathlib import Path

from lottolab.interfaces.api.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
API_MODULE = REPO_ROOT / "src/lottolab/interfaces/api/b649_multi_ticket_records.py"
READER_MODULE = REPO_ROOT / "src/lottolab/infrastructure/biglotto_multi_ticket_record_reader.py"
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


def test_k10_runtime_has_no_materialization_or_external_authority_read_path() -> None:
    imports = _imports(READER_MODULE) | _imports(API_MODULE)
    assert not any("projection_builder" in name or "backtest" in name for name in imports)
    source = READER_MODULE.read_text()
    tree = ast.parse(source)
    assert not any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"open", "Path"}
        for n in ast.walk(tree)
    )
    paths = create_app().openapi()["paths"]
    endpoint = "/api/v1/b649-exact-native-records"
    assert set(paths[endpoint]) == {"get"}
    assert [p for p in paths if "exact-native-records" in p] == [endpoint]
    assert create_app().openapi()["components"]["schemas"]["B649ExactNativeTicketCount"][
        "enum"
    ] == [2, 3, 5, 10]


def test_k5_runtime_reads_only_packaged_resource_and_never_catalog_or_task_data() -> None:
    from unittest.mock import patch

    import lottolab.infrastructure.biglotto_multi_ticket_record_reader as reader
    from lottolab.application.biglotto_multi_ticket_records import B649_EXACT_NATIVE_TICKET_COUNTS
    from lottolab.infrastructure.biglotto_multi_ticket_record_reader import parse_b649_k5_projection
    from lottolab.interfaces.api.b649_multi_ticket_records import B649ExactNativeTicketCount

    assert B649_EXACT_NATIVE_TICKET_COUNTS == (2, 3)
    assert B649ExactNativeTicketCount.FIVE == 5
    reader._read_packaged_k5_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]
    read = Path.read_bytes
    accessed: list[str] = []

    def guarded(path: Path) -> bytes:
        accessed.append(str(path))
        assert ".task-data" not in str(path)
        assert path.name == reader.K5_PROJECTION_RESOURCE_NAME
        return read(path)

    with (
        patch.object(Path, "read_bytes", guarded),
        patch.object(
            reader,
            "load_full_strategy_catalog",
            side_effect=AssertionError("catalog admission gate"),
        ),
    ):
        dataset = reader.PackagedB649K5RecordReader().read()
    assert len(dataset.records) == 20
    assert len(accessed) == 1
    assert parse_b649_k5_projection.__module__ == reader.__name__
    reader._read_packaged_k5_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]
