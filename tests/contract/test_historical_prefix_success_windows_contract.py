"""OpenAPI and generated-TypeScript contract for success-window routes."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fastapi.testclient import TestClient
from tests.fixtures.historical.success_window_builder import (
    build_success_source,
    build_success_strategy,
)

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.interfaces.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
LIST_PATH = "/api/v1/historical-prefix-success-windows"
EXACT_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}"
)
MATRIX_PATH = f"{EXACT_PATH}/matrix"
RANDOM_BASELINE_PATH = f"{EXACT_PATH}/random-null-baseline"
FEATURE_COHORT_PATH = f"{EXACT_PATH}/feature-cohorts"
DIAGNOSTICS_PATH = f"{FEATURE_COHORT_PATH}/diagnostics"
TEMPORAL_HOLDOUT_PATH = f"{FEATURE_COHORT_PATH}/temporal-holdout"
RECENT_AUDIT_PATH = f"{FEATURE_COHORT_PATH}/recent-50-stability-audit"
CROSS_IMPORT_CONCORDANCE_PATH = f"{FEATURE_COHORT_PATH}/cross-import-concordance"
MULTI_IMPORT_CENSUS_PATH = f"{FEATURE_COHORT_PATH}/multi-import-concordance-census"
RESEARCH_QUALIFICATION_PATH = f"{EXACT_PATH}/research-qualification"
QUALIFICATION_RANDOM_BASELINE_PATH = f"{RESEARCH_QUALIFICATION_PATH}/random-baseline-evidence"
QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "strategy-a/v1/1/research-qualification/random-baseline-evidence"
)
QUALIFICATION_RANDOM_IMPORTS = ("a" * 64, "b" * 64)


class _ContractReader:
    def __init__(
        self,
        sources: Mapping[str, HistoricalPrefixSuccessWindowSource | None],
        *,
        fail: bool = False,
    ) -> None:
        self.sources = sources
        self.fail = fail
        self.calls: list[str] = []

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        self.calls.append(import_identity_sha256)
        if self.fail:
            raise RuntimeError("private reader detail")
        return self.sources.get(import_identity_sha256)


class _ContractFactory:
    def __init__(
        self,
        sources: Mapping[str, HistoricalPrefixSuccessWindowSource | None],
        *,
        fail: bool = False,
    ) -> None:
        self.reader = _ContractReader(sources, fail=fail)
        self.calls = 0

    def __call__(self) -> _ContractReader:
        self.calls += 1
        return self.reader


def _qualification_random_source(
    import_identity: str,
    *,
    strategy_id: str = "strategy-a",
) -> HistoricalPrefixSuccessWindowSource:
    return build_success_source(
        (build_success_strategy(strategy_id),),
        import_identity_sha256=import_identity,
    )


def _qualification_random_params(
    imports: tuple[str, ...] = QUALIFICATION_RANDOM_IMPORTS,
    **extra: object,
) -> list[tuple[str, object]]:
    params: list[tuple[str, object]] = [
        *(("import_identity_sha256", identity) for identity in imports),
        ("prefix_count", 1),
        ("criterion", "M3_PLUS"),
    ]
    params.extend(extra.items())
    return params


def _qualification_random_client(
    sources: Mapping[str, HistoricalPrefixSuccessWindowSource | None],
    *,
    fail: bool = False,
) -> tuple[TestClient, _ContractFactory]:
    factory = _ContractFactory(sources, fail=fail)
    return (
        TestClient(create_app(historical_prefix_success_window_source_reader_factory=factory)),
        factory,
    )


def test_openapi_exposes_exactly_twelve_get_operations_with_required_selectors() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths[LIST_PATH]) == {"get"}
    assert set(paths[EXACT_PATH]) == {"get"}
    assert set(paths[MATRIX_PATH]) == {"get"}
    assert set(paths[RANDOM_BASELINE_PATH]) == {"get"}
    assert set(paths[FEATURE_COHORT_PATH]) == {"get"}
    assert set(paths[DIAGNOSTICS_PATH]) == {"get"}
    assert set(paths[TEMPORAL_HOLDOUT_PATH]) == {"get"}
    assert set(paths[RECENT_AUDIT_PATH]) == {"get"}
    assert set(paths[CROSS_IMPORT_CONCORDANCE_PATH]) == {"get"}
    assert set(paths[MULTI_IMPORT_CENSUS_PATH]) == {"get"}
    assert set(paths[RESEARCH_QUALIFICATION_PATH]) == {"get"}
    assert set(paths[QUALIFICATION_RANDOM_BASELINE_PATH]) == {"get"}
    list_operation = paths[LIST_PATH]["get"]
    exact_operation = paths[EXACT_PATH]["get"]
    matrix_operation = paths[MATRIX_PATH]["get"]
    random_baseline_operation = paths[RANDOM_BASELINE_PATH]["get"]
    feature_cohort_operation = paths[FEATURE_COHORT_PATH]["get"]
    diagnostics_operation = paths[DIAGNOSTICS_PATH]["get"]
    temporal_holdout_operation = paths[TEMPORAL_HOLDOUT_PATH]["get"]
    recent_audit_operation = paths[RECENT_AUDIT_PATH]["get"]
    cross_import_operation = paths[CROSS_IMPORT_CONCORDANCE_PATH]["get"]
    multi_import_operation = paths[MULTI_IMPORT_CENSUS_PATH]["get"]
    qualification_operation = paths[RESEARCH_QUALIFICATION_PATH]["get"]
    qualification_random_operation = paths[QUALIFICATION_RANDOM_BASELINE_PATH]["get"]
    assert list_operation["operationId"] == "listHistoricalPrefixStrategySuccessWindows"
    assert exact_operation["operationId"] == "getHistoricalPrefixStrategySuccessWindows"
    assert matrix_operation["operationId"] == "getHistoricalPrefixStrategySuccessMatrix"
    assert random_baseline_operation["operationId"] == (
        "getHistoricalPrefixStrategyRandomNullBaseline"
    )
    assert feature_cohort_operation["operationId"] == "getHistoricalPrefixStrategyFeatureCohorts"
    assert diagnostics_operation["operationId"] == (
        "getHistoricalPrefixStrategyFeatureCohortDiagnostics"
    )
    assert temporal_holdout_operation["operationId"] == (
        "getHistoricalPrefixStrategyFeatureCohortTemporalHoldout"
    )
    assert recent_audit_operation["operationId"] == (
        "getHistoricalPrefixStrategyFeatureCohortRecent50StabilityAudit"
    )
    assert cross_import_operation["operationId"] == (
        "getHistoricalPrefixStrategyCrossImportConcordance"
    )
    assert multi_import_operation["operationId"] == (
        "getHistoricalPrefixStrategyMultiImportConcordanceCensus"
    )
    assert qualification_operation["operationId"] == (
        "getHistoricalPrefixStrategyResearchQualification"
    )
    assert qualification_random_operation["operationId"] == (
        "getHistoricalPrefixStrategyResearchQualificationRandomBaselineEvidence"
    )
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
    required_list = {item["name"]: item["required"] for item in list_operation["parameters"]}
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
    assert [item["name"] for item in random_baseline_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
        "window_kind",
    ]
    assert all(item["required"] is True for item in random_baseline_operation["parameters"])
    assert [item["name"] for item in feature_cohort_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in feature_cohort_operation["parameters"])
    assert [item["name"] for item in diagnostics_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in diagnostics_operation["parameters"])
    assert [item["name"] for item in temporal_holdout_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in temporal_holdout_operation["parameters"])
    assert [item["name"] for item in recent_audit_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in recent_audit_operation["parameters"])
    assert [item["name"] for item in cross_import_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "left_import_identity_sha256",
        "right_import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in cross_import_operation["parameters"])
    assert [item["name"] for item in multi_import_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in multi_import_operation["parameters"])
    multi_selector = multi_import_operation["parameters"][3]["schema"]
    assert multi_selector["type"] == "array"
    assert multi_selector["minItems"] == 2
    assert multi_selector["maxItems"] == 4
    assert multi_selector["items"] == {
        "type": "string",
        "pattern": "^[0-9a-f]{64}$",
    }
    assert [item["name"] for item in qualification_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in qualification_operation["parameters"])
    assert qualification_operation["parameters"][3]["schema"] == multi_selector
    assert [item["name"] for item in qualification_random_operation["parameters"]] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "import_identity_sha256",
        "prefix_count",
        "criterion",
    ]
    assert all(item["required"] is True for item in qualification_random_operation["parameters"])
    assert qualification_random_operation["parameters"][3]["schema"] == multi_selector
    selector = list_operation["parameters"][0]
    assert selector["in"] == "query"
    assert selector["schema"]["pattern"] == "^[0-9a-f]{64}$"
    assert "default" not in selector["schema"]


def test_qualification_random_baseline_route_preserves_order_and_closed_not_ready_cells() -> None:
    client, factory = _qualification_random_client(
        {
            identity: _qualification_random_source(identity)
            for identity in QUALIFICATION_RANDOM_IMPORTS
        }
    )

    response = client.get(
        QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH,
        params=_qualification_random_params(),
    )

    assert response.status_code == 200
    assert factory.calls == 1
    assert factory.reader.calls == list(QUALIFICATION_RANDOM_IMPORTS)
    payload = response.json()
    assert payload["qualification_identity"] == {
        "strategy_id": "strategy-a",
        "strategy_version": "v1",
        "replicate": 1,
        "prefix_count": 1,
        "criterion": "M3_PLUS",
    }
    assert payload["ordered_import_identity_sha256s"] == list(QUALIFICATION_RANDOM_IMPORTS)
    assert payload["availability_summary"] == {
        "availability_status": "ALL_NOT_READY",
        "evaluated_cell_count": 8,
        "ready_cell_count": 0,
        "raw_upper_tail_probability_count": 0,
        "multiple_testing_warning": (
            "This response evaluated 8 import × window cells. Each READY "  # noqa: RUF001
            "upper_tail_probability is a raw, unadjusted exact descriptive value. "
            "No multiplicity adjustment, threshold, pooled probability, combined "
            "decision, or random-advantage inference is authorized."
        ),
    }
    assert [
        (
            cell["import_index"],
            cell["window_index"],
            cell["qualification_random_role"],
            cell["baseline"]["cell"]["window_kind"],
        )
        for cell in payload["ordered_cells"]
    ] == [
        (0, 0, "REFERENCE_ONLY", "FULL_HISTORY"),
        (0, 1, "PRIMARY_DESCRIPTIVE_COMPARISON", "LONG"),
        (0, 2, "CONFIRMATION_DESCRIPTIVE_COMPARISON", "MEDIUM"),
        (0, 3, "AUDIT_ONLY_NON_BLOCKING", "SHORT"),
        (1, 0, "REFERENCE_ONLY", "FULL_HISTORY"),
        (1, 1, "PRIMARY_DESCRIPTIVE_COMPARISON", "LONG"),
        (1, 2, "CONFIRMATION_DESCRIPTIVE_COMPARISON", "MEDIUM"),
        (1, 3, "AUDIT_ONLY_NON_BLOCKING", "SHORT"),
    ]
    assert all(
        cell["baseline"]["readiness"] == "NOT_READY"
        and cell["baseline"]["observed_success_count"] is None
        and cell["baseline"]["expected_successes"] is None
        and cell["baseline"]["upper_tail_probability"] is None
        for cell in payload["ordered_cells"]
    )


def test_qualification_random_baseline_error_mapping_is_fail_closed_and_sanitized() -> None:
    not_configured = TestClient(create_app()).get(
        QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH,
        params=_qualification_random_params(),
    )
    invalid_client, invalid_factory = _qualification_random_client({})
    invalid = invalid_client.get(
        QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH,
        params=_qualification_random_params(extra_query="unexpected"),
    )
    duplicate = invalid_client.get(
        QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH,
        params=_qualification_random_params((QUALIFICATION_RANDOM_IMPORTS[0],) * 2),
    )
    missing_import = invalid_client.get(
        QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH,
        params=_qualification_random_params(),
    )
    missing_strategy_client, _ = _qualification_random_client(
        {
            identity: _qualification_random_source(identity, strategy_id="other")
            for identity in QUALIFICATION_RANDOM_IMPORTS
        }
    )
    missing_strategy = missing_strategy_client.get(
        QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH,
        params=_qualification_random_params(),
    )
    unavailable_client, _ = _qualification_random_client({}, fail=True)
    unavailable = unavailable_client.get(
        QUALIFICATION_RANDOM_BASELINE_REQUEST_PATH,
        params=_qualification_random_params(),
    )

    assert not_configured.status_code == 503
    assert invalid.status_code == duplicate.status_code == 422
    assert invalid_factory.calls == 1
    assert invalid_factory.reader.calls == [QUALIFICATION_RANDOM_IMPORTS[0]]
    assert missing_import.status_code == missing_strategy.status_code == 404
    assert unavailable.status_code == 503
    assert "private reader detail" not in unavailable.text


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
    assert schemas["WindowKind"]["enum"] == [
        "FULL_HISTORY",
        "LONG",
        "MEDIUM",
        "SHORT",
    ]
    assert schemas["HistoricalSuccessRandomBaselineReadiness"]["enum"] == [
        "READY",
        "NOT_READY",
    ]
    assert schemas["HistoricalSuccessRandomBaselineNotReadyReason"]["enum"] == [
        "NO_OBSERVATIONS",
        "WINDOW_INCOMPLETE",
        "EXCLUDED_OBSERVATIONS",
        "SOURCE_TICKET_SEMANTICS_CONFLICT",
        "EXACT_COMPUTATION_UNAVAILABLE",
    ]
    exact_baseline = schemas["HistoricalSuccessRandomBaselineExactRationalView"]
    assert exact_baseline["additionalProperties"] is False
    assert exact_baseline["required"] == ["numerator", "denominator", "decimal_18"]
    assert exact_baseline["properties"]["numerator"]["type"] == "string"
    assert exact_baseline["properties"]["denominator"]["type"] == "string"
    assert exact_baseline["properties"]["decimal_18"]["type"] == "string"
    random_baseline = schemas["HistoricalSuccessRandomBaselineResponse"]
    assert random_baseline["additionalProperties"] is False
    assert random_baseline["properties"]["legal_ticket_count"]["type"] == "string"
    assert random_baseline["properties"]["success_ticket_count"]["type"] == "string"
    assert schemas["HistoricalPrefixCrossImportPairStatus"]["enum"] == [
        "COMPLETE",
        "LEFT_NOT_READY",
        "RIGHT_NOT_READY",
        "BOTH_NOT_READY",
    ]
    assert schemas["HistoricalPrefixConfirmationOverlapRelation"]["enum"] == [
        "DISJOINT",
        "PARTIAL_OVERLAP",
        "IDENTICAL",
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
    feature_key = schemas["HistoricalPrefixFeatureRelationTripleView"]
    assert feature_key["required"] == [
        "long_to_medium",
        "medium_to_short",
        "long_to_short",
    ]
    cohort = schemas["HistoricalPrefixFeatureCohortView"]
    assert cohort["required"] == [
        "feature_key",
        "observation_count",
        "success_count",
        "failure_count",
        "success_rate",
        "delta_vs_baseline",
        "relation_vs_baseline",
        "first_target",
        "last_target",
    ]
    assert cohort["properties"]["first_target"]["anyOf"][-1] == {"type": "null"}
    assert cohort["properties"]["last_target"]["anyOf"][-1] == {"type": "null"}
    probability = schemas["HistoricalPrefixExactProbabilityView"]
    assert probability["required"] == ["numerator", "denominator"]
    assert probability["properties"]["numerator"]["type"] == "string"
    assert probability["properties"]["denominator"]["type"] == "string"
    assert schemas["HistoricalPrefixFeatureCohortTestStatus"]["enum"] == [
        "TESTED",
        "NOT_TESTABLE_EMPTY_COHORT",
        "NOT_TESTABLE_EMPTY_COMPLEMENT",
        "NOT_TESTABLE_NO_OUTCOME_VARIATION",
    ]
    diagnostics = schemas["HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse"]
    assert diagnostics["properties"]["family_size"]["const"] == 64
    assert diagnostics["properties"]["raw_test_method"]["const"] == (
        "FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING"
    )
    assert diagnostics["properties"]["adjustment_method"]["const"] == ("BENJAMINI_YEKUTIELI")
    holdout = schemas["HistoricalPrefixTemporalHoldoutResponse"]
    assert holdout["properties"]["family_size"]["const"] == 64
    split = schemas["HistoricalPrefixTemporalHoldoutSplitView"]
    assert split["properties"]["split_method"]["const"] == (
        "FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION"
    )
    assert schemas["HistoricalPrefixTemporalHoldoutStatus"]["enum"] == [
        "COMPLETE",
        "NOT_READY_INSUFFICIENT_HISTORY",
    ]
    assert schemas["HistoricalPrefixTemporalHoldoutRelationship"]["enum"] == [
        "SAME_HIGHER",
        "SAME_EQUAL",
        "SAME_LOWER",
        "DIFFERENT",
        "UNAVAILABLE",
    ]
    assert schemas["HistoricalSuccessQualificationPrimaryStatus"]["enum"] == [
        "NOT_READY",
        "EVIDENCE_INCOMPLETE",
        "RESEARCH_CANDIDATE",
    ]
    assert schemas["HistoricalSuccessQualificationInformationalFlag"]["enum"] == [
        "CROSS_IMPORT_UNRESOLVED",
        "HISTORICAL_CONCORDANCE_OBSERVED",
        "RECENT_RELATIONSHIP_DIFFERENCE",
    ]
    assert schemas["HistoricalSuccessQualificationEvidenceStatus"]["enum"] == [
        "COMPLETE",
        "NOT_READY",
    ]
    assert schemas["HistoricalSuccessQualificationRandomRole"]["enum"] == [
        "REFERENCE_ONLY",
        "PRIMARY_DESCRIPTIVE_COMPARISON",
        "CONFIRMATION_DESCRIPTIVE_COMPARISON",
        "AUDIT_ONLY_NON_BLOCKING",
    ]
    assert schemas["HistoricalSuccessQualificationRandomAvailabilityStatus"]["enum"] == [
        "COMPLETE",
        "PARTIAL",
        "ALL_NOT_READY",
    ]
    aggregate = schemas["HistoricalSuccessQualificationRandomBaselineEvidenceResponse"]
    assert aggregate["additionalProperties"] is False
    assert aggregate["required"] == [
        "qualification_identity",
        "ordered_import_identity_sha256s",
        "availability_summary",
        "ordered_cells",
    ]
    availability = schemas["HistoricalSuccessQualificationRandomBaselineAvailabilityView"]
    assert availability["additionalProperties"] is False
    assert availability["required"] == [
        "availability_status",
        "evaluated_cell_count",
        "ready_cell_count",
        "raw_upper_tail_probability_count",
        "multiple_testing_warning",
    ]
    cell = schemas["HistoricalSuccessQualificationRandomBaselineCellView"]
    assert cell["additionalProperties"] is False
    assert cell["required"] == [
        "import_index",
        "window_index",
        "qualification_random_role",
        "baseline",
    ]


def test_openapi_uses_sanitized_404_422_503_models_for_all_routes() -> None:
    paths = create_app().openapi()["paths"]

    for path in (
        LIST_PATH,
        EXACT_PATH,
        MATRIX_PATH,
        RANDOM_BASELINE_PATH,
        FEATURE_COHORT_PATH,
        DIAGNOSTICS_PATH,
        TEMPORAL_HOLDOUT_PATH,
        RECENT_AUDIT_PATH,
        CROSS_IMPORT_CONCORDANCE_PATH,
        MULTI_IMPORT_CENSUS_PATH,
        RESEARCH_QUALIFICATION_PATH,
        QUALIFICATION_RANDOM_BASELINE_PATH,
    ):
        operation = paths[path]["get"]
        for status, schema_name in {
            "404": "ApiErrorResponse",
            "422": "ApiValidationErrorResponse",
            "503": "ApiErrorResponse",
        }.items():
            assert operation["responses"][status]["content"]["application/json"]["schema"] == {
                "$ref": f"#/components/schemas/{schema_name}"
            }


def test_generated_types_keep_all_success_window_parameters_required() -> None:
    declaration = (ROOT / "frontend/src/api/generated/openapi.d.ts").read_text(encoding="utf-8")
    list_block = declaration.split(f'"{LIST_PATH}": {{', 1)[1].split(f'"{EXACT_PATH}": {{', 1)[0]
    exact_block = declaration.split(f'"{EXACT_PATH}": {{', 1)[1].split(f'"{MATRIX_PATH}": {{', 1)[0]
    matrix_block = declaration.split(f'"{MATRIX_PATH}": {{', 1)[1].split(
        '"/api/v1/replay-rankings/optimal": {', 1
    )[0]
    random_baseline_start = declaration.index(f'  "{RANDOM_BASELINE_PATH}": {{')
    random_baseline_end = declaration.find(
        '\n  "/api/',
        random_baseline_start + 1,
    )
    random_baseline_block = declaration[random_baseline_start:random_baseline_end]

    assert '"import_identity_sha256": string' in list_block
    assert '"prefix_count": components[\'schemas\']["HistoricalPrefixSuccessPrefixCount"]' in (
        list_block
    )
    assert '"criterion": components[\'schemas\']["HistoricalPrefixSuccessCriterion"]' in (
        list_block
    )
    assert '"limit"?: number' in list_block
    assert '"offset"?: number' in list_block
    assert '"window_kind": components[\'schemas\']["WindowKind"]' in random_baseline_block
    assert '"window_kind"?:' not in random_baseline_block
    assert (
        "\"application/json\": components['schemas']"
        '["HistoricalSuccessRandomBaselineResponse"]' in random_baseline_block
    )
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
    assert f'"{DIAGNOSTICS_PATH}": {{' in declaration
    assert f'"{TEMPORAL_HOLDOUT_PATH}": {{' in declaration
    assert f'"{RECENT_AUDIT_PATH}": {{' in declaration
    assert f'"{RESEARCH_QUALIFICATION_PATH}": {{' in declaration
    assert f'"{QUALIFICATION_RANDOM_BASELINE_PATH}": {{' in declaration
    assert (
        '"HistoricalSuccessQualificationPrimaryStatus": "NOT_READY" | '
        '"EVIDENCE_INCOMPLETE" | "RESEARCH_CANDIDATE"'
    ) in declaration
    assert (
        '"HistoricalSuccessQualificationInformationalFlag": '
        '"CROSS_IMPORT_UNRESOLVED" | "HISTORICAL_CONCORDANCE_OBSERVED" | '
        '"RECENT_RELATIONSHIP_DIFFERENCE"'
    ) in declaration
    assert (
        '"HistoricalSuccessQualificationRandomRole": "REFERENCE_ONLY" | '
        '"PRIMARY_DESCRIPTIVE_COMPARISON" | '
        '"CONFIRMATION_DESCRIPTIVE_COMPARISON" | "AUDIT_ONLY_NON_BLOCKING"'
    ) in declaration
    qualification_random_block = declaration.split(
        f'"{QUALIFICATION_RANDOM_BASELINE_PATH}": {{', 1
    )[1].split('\n  "/api/', 1)[0]
    assert '"import_identity_sha256": Array<string>' in qualification_random_block
    assert (
        "\"application/json\": components['schemas']"
        '["HistoricalSuccessQualificationRandomBaselineEvidenceResponse"]'
        in qualification_random_block
    )
    assert f'"{MULTI_IMPORT_CENSUS_PATH}": {{' in declaration
    multi_import_block = declaration.split(f'"{MULTI_IMPORT_CENSUS_PATH}": {{', 1)[1].split(
        f'"{TEMPORAL_HOLDOUT_PATH}": {{', 1
    )[0]
    assert '"import_identity_sha256": Array<string>' in multi_import_block
    assert (
        '"HistoricalPrefixFeatureCohortTestStatus": "TESTED" | '
        '"NOT_TESTABLE_EMPTY_COHORT" | "NOT_TESTABLE_EMPTY_COMPLEMENT" | '
        '"NOT_TESTABLE_NO_OUTCOME_VARIATION"'
    ) in declaration
    assert '"numerator": string' in declaration
    assert '"denominator": string' in declaration


def test_generator_remains_generic_without_success_window_special_cases() -> None:
    source = (ROOT / "frontend/scripts/generate-openapi-types.mjs").read_text(encoding="utf-8")

    assert "operation.parameters ?? []" in source
    assert "HistoricalPrefixSuccess" not in source
    assert LIST_PATH not in source
    assert MATRIX_PATH not in source
