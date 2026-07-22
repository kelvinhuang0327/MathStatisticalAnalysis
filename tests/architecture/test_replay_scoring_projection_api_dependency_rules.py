"""Architecture boundaries for the Replay-scoring projection query API."""

from __future__ import annotations

import ast
from pathlib import Path

from lottolab.interfaces.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
APPLICATION = ROOT / "src/lottolab/application/use_cases/query_replay_scoring_projection.py"
ROUTER = ROOT / "src/lottolab/interfaces/api/replay_scoring_projections.py"
APP = ROOT / "src/lottolab/interfaces/api/app.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_application_query_has_no_interface_or_infrastructure_dependency() -> None:
    imports = _imports(APPLICATION)

    assert not any(name.startswith("lottolab.interfaces") for name in imports)
    assert not any(name.startswith("lottolab.infrastructure") for name in imports)


def test_api_boundary_contains_no_sql_scoring_prize_or_ranking_logic() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    imports = _imports(ROUTER)

    assert "sqlite3" not in imports
    assert not any(name.startswith("lottolab.infrastructure") for name in imports)
    assert "SELECT " not in source
    assert "INSERT " not in source
    assert "UPDATE " not in source
    assert "recompute_" not in source
    assert "resolve_big_lotto_prize" not in source
    assert "rank_replay" not in source


def test_query_path_has_no_writer_schema_setup_or_mutating_endpoint() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (APPLICATION, ROUTER, APP)
    )
    router_source = ROUTER.read_text(encoding="utf-8")

    assert "ReplayScoringProjectionWriter" not in combined
    assert "initialize_schema" not in combined
    assert "persist_replay_scoring_artifact" not in combined
    assert "@router.post" not in router_source
    assert "@router.put" not in router_source
    assert "@router.patch" not in router_source
    assert "@router.delete" not in router_source


def test_app_construction_and_openapi_generation_do_not_call_reader_factory() -> None:
    calls = 0

    def forbidden_factory():
        nonlocal calls
        calls += 1
        raise AssertionError("reader factory must stay lazy")

    app = create_app(replay_scoring_projection_reader_factory=forbidden_factory)
    schema = app.openapi()

    assert calls == 0
    assert "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}" in schema["paths"]


def test_replay_scoring_routes_coexist_with_historical_and_ranking_routes() -> None:
    paths = set(create_app().openapi()["paths"])

    assert {
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates",
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate",
    }.issubset(paths)
    assert "/api/v1/historical-results/runs" in paths
    assert "/api/v1/replay-rankings/optimal" in paths
