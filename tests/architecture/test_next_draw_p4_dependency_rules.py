"""Architecture guardrails for sealed-ticket-only P4 attribution."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from lottolab.infrastructure.persistence.next_draw_p4_schema import TABLE_NAMES

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "lottolab"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_p4_domain_has_no_outward_layer_dependencies() -> None:
    imports = _imports(SRC / "domain" / "next_draw_outcome_attribution.py")
    forbidden = (
        "lottolab.application",
        "lottolab.infrastructure",
        "lottolab.interfaces",
        "lottolab.strategies",
    )
    assert not any(name.startswith(forbidden) for name in imports)


def test_attribution_use_case_cannot_import_ranking_generation_or_adapters() -> None:
    imports = _imports(
        SRC / "application" / "use_cases" / "attribute_sealed_next_draw_outcome.py"
    )
    forbidden_fragments = (
        "build_next_draw_recommendation",
        "generate_next_draw",
        "ranking",
        "strategies",
        "infrastructure",
    )
    assert not any(
        fragment in imported
        for imported in imports
        for fragment in forbidden_fragments
    )


def test_p4_api_declares_get_routes_only_and_imports_no_infrastructure() -> None:
    path = SRC / "interfaces" / "api" / "next_draw_p4_attributions.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    decorators = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "router"
    ]
    assert decorators == ["get", "get"]
    assert not any(
        name.startswith("lottolab.infrastructure") for name in _imports(path)
    )


def test_p4_repository_has_no_mutating_overwrite_statements() -> None:
    source = (
        SRC / "infrastructure" / "persistence" / "next_draw_p4_repository.py"
    ).read_text(encoding="utf-8")
    normalized = " ".join(source.upper().split())
    assert "UPDATE NEXT_DRAW_P4_ATTRIBUTIONS" not in normalized
    assert "DELETE FROM NEXT_DRAW_P4_ATTRIBUTIONS" not in normalized
    assert "REPLACE INTO NEXT_DRAW_P4_ATTRIBUTIONS" not in normalized
    assert "INSERT OR REPLACE" not in normalized
    assert "BEGIN IMMEDIATE" in normalized


def test_isolated_p4_schema_owns_only_the_two_frozen_tables() -> None:
    assert TABLE_NAMES == (
        "next_draw_p4_schema_migrations",
        "next_draw_p4_attributions",
    )


def test_committed_openapi_and_generated_client_expose_get_only_p4_contracts() -> None:
    contract = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))
    exact_path = (
        "/api/v1/next-draw-p4-attributions/"
        "{lottery_type}/{target_draw_number}/{target_draw_date}"
    )
    history_path = "/api/v1/next-draw-p4-attributions"

    assert set(contract["paths"][exact_path]) == {"get"}
    assert set(contract["paths"][history_path]) == {"get"}
    schemas = contract["components"]["schemas"]
    assert "NextDrawP4AttributionResponse" in schemas
    assert "NextDrawP4AttributionHistoryResponse" in schemas
    declaration = (
        ROOT / "frontend" / "src" / "api" / "generated" / "openapi.d.ts"
    ).read_text(encoding="utf-8")
    assert exact_path in declaration
    assert history_path in declaration
    assert '"NextDrawP4AttributionResponse"' in declaration
