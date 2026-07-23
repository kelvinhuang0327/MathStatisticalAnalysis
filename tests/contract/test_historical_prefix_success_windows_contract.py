"""OpenAPI and generated-TypeScript contract for success-window routes."""

from __future__ import annotations

from pathlib import Path

from lottolab.interfaces.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
LIST_PATH = "/api/v1/historical-prefix-success-windows"
EXACT_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}"
)
MATRIX_PATH = f"{EXACT_PATH}/matrix"


def test_openapi_exposes_exactly_three_get_operations_with_required_selectors() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths[LIST_PATH]) == {"get"}
    assert set(paths[EXACT_PATH]) == {"get"}
    assert set(paths[MATRIX_PATH]) == {"get"}
    list_operation = paths[LIST_PATH]["get"]
    exact_operation = paths[EXACT_PATH]["get"]
    matrix_operation = paths[MATRIX_PATH]["get"]
    assert list_operation["operationId"] == "listHistoricalPrefixStrategySuccessWindows"
    assert exact_operation["operationId"] == "getHistoricalPrefixStrategySuccessWindows"
    assert matrix_operation["operationId"] == "getHistoricalPrefixStrategySuccessMatrix"
    assert [item["name"] for item in list_operation["parameters"]] == [
        "import_identity_sha256",
        "prefix_count",
        "criterion",
        "limit",
        "offset",
    ]
    assert [item["name"] for item in exact_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    required_list = {
        item["name"]: item["required"] for item in list_operation["parameters"]
    }
    assert required_list == {
        "import_identity_sha256": True,
        "prefix_count": True,
        "criterion": True,
        "limit": False,
        "offset": False,
    }
    assert all(item["required"] is True for item in exact_operation["parameters"])
    assert [item["name"] for item in matrix_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
    ]
    assert all(item["required"] is True for item in matrix_operation["parameters"])
    selector = list_operation["parameters"][0]
    assert selector["in"] == "query"
    assert selector["schema"]["pattern"] == "^[0-9a-f]{64}$"
    assert "default" not in selector["schema"]


def test_openapi_pins_closed_prefix_criterion_and_nullable_rate_contract() -> None:
    document = create_app().openapi()
    schemas = document["components"]["schemas"]

    assert schemas["HistoricalPrefixSuccessPrefixCount"]["enum"] == [
        1,
        2,
        3,
        4,
        5,
        10,
        15,
        20,
    ]
    assert schemas["HistoricalPrefixSuccessCriterion"]["enum"] == [
        "M3_PLUS",
        "M4_PLUS",
        "M5_PLUS",
        "M6",
        "M2_PLUS_SPECIAL",
        "M3_PLUS_SPECIAL",
        "M4_PLUS_SPECIAL",
        "M5_PLUS_SPECIAL",
    ]
    rate = schemas["HistoricalPrefixExactSuccessRateView"]
    assert rate["required"] == ["numerator", "denominator", "available"]
    assert rate["properties"]["numerator"]["type"] == "integer"
    assert rate["properties"]["denominator"]["type"] == "integer"
    assert rate["properties"]["available"]["type"] == "boolean"
    window = schemas["HistoricalPrefixSuccessWindowSummaryView"]
    requested = window["properties"]["requested_draw_count"]
    assert requested["anyOf"] == [{"type": "integer"}, {"type": "null"}]
    assert schemas["HistoricalPrefixRateRelation"]["enum"] == [
        "HIGHER",
        "EQUAL",
        "LOWER",
        "UNAVAILABLE",
    ]
    assert schemas["HistoricalPrefixWindowRateComparisonKind"]["enum"] == [
        "FULL_HISTORY_TO_LONG",
        "LONG_TO_MEDIUM",
        "MEDIUM_TO_SHORT",
        "LONG_TO_SHORT",
    ]
    delta = schemas["HistoricalPrefixSignedRateDeltaView"]
    assert delta["required"] == ["numerator", "denominator", "available"]
    assert delta["properties"]["numerator"]["type"] == "integer"
    matrix = schemas["HistoricalPrefixStrategySuccessMatrixResponse"]
    assert matrix["required"] == [
        "metadata",
        "strategy",
        "source_observation_count",
        "prefix_counts",
        "criteria",
        "cell_count",
        "cells",
    ]


def test_openapi_uses_sanitized_404_422_503_models_for_both_routes() -> None:
    paths = create_app().openapi()["paths"]

    for path in (LIST_PATH, EXACT_PATH, MATRIX_PATH):
        operation = paths[path]["get"]
        for status, schema_name in {
            "404": "ApiErrorResponse",
            "422": "ApiValidationErrorResponse",
            "503": "ApiErrorResponse",
        }.items():
            assert operation["responses"][status]["content"]["application/json"][
                "schema"
            ] == {"$ref": f"#/components/schemas/{schema_name}"}


def test_generated_types_keep_all_success_window_parameters_required() -> None:
    declaration = (ROOT / "frontend/src/api/generated/openapi.d.ts").read_text(
        encoding="utf-8"
    )
    list_block = declaration.split(f'"{LIST_PATH}": {{', 1)[1].split(
        f'"{EXACT_PATH}": {{', 1
    )[0]
    exact_block = declaration.split(f'"{EXACT_PATH}": {{', 1)[1].split(
        f'"{MATRIX_PATH}": {{', 1
    )[0]
    matrix_block = declaration.split(f'"{MATRIX_PATH}": {{', 1)[1].split(
        '"/api/v1/replay-rankings/optimal": {', 1
    )[0]

    assert '"import_identity_sha256": string' in list_block
    assert '"prefix_count": components[\'schemas\']["HistoricalPrefixSuccessPrefixCount"]' in (
        list_block
    )
    assert '"criterion": components[\'schemas\']["HistoricalPrefixSuccessCriterion"]' in (
        list_block
    )
    assert '"limit"?: number' in list_block
    assert '"offset"?: number' in list_block
    for name in (
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ):
        assert f'"{name}"?:' not in exact_block
    assert '"strategy_id": string' in exact_block
    assert '"strategy_version": string' in exact_block
    assert '"replicate": number' in exact_block
    for name in (
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
    ):
        assert f'"{name}"?:' not in matrix_block
    assert '"prefix_count"' not in matrix_block
    assert '"criterion"' not in matrix_block
    assert '"HistoricalPrefixRateRelation": "HIGHER" | "EQUAL" | "LOWER" | "UNAVAILABLE"' in (
        declaration
    )
    assert (
        '"HistoricalPrefixSuccessCriterion": "M3_PLUS" | "M4_PLUS" | "M5_PLUS" | '
        '"M6" | "M2_PLUS_SPECIAL" | "M3_PLUS_SPECIAL" | "M4_PLUS_SPECIAL" | '
        '"M5_PLUS_SPECIAL"'
    ) in declaration


def test_generator_remains_generic_without_success_window_special_cases() -> None:
    source = (ROOT / "frontend/scripts/generate-openapi-types.mjs").read_text(
        encoding="utf-8"
    )

    assert "operation.parameters ?? []" in source
    assert "HistoricalPrefixSuccess" not in source
    assert LIST_PATH not in source
    assert MATRIX_PATH not in source
