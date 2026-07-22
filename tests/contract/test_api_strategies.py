"""API contract tests — the payload shape the frontend TypeScript types rely on."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

import json
from pathlib import Path
from typing import Never, cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.interfaces.api.app import create_app
from lottolab.strategies.catalog import StrategyCatalog

ROOT = Path(__file__).resolve().parents[2]


def fixture_catalog() -> StrategyCatalog:
    return StrategyCatalog(
        [
            StrategyDescriptor(
                strategy_id="fixture_observation_strategy",
                strategy_name="Fixture Observation Strategy",
                version="v0.1",
                lottery_types=(LotteryType.BIG_LOTTO,),
                lifecycle_status=LifecycleStatus.OBSERVATION,
                executable=False,
                provenance=("fixture:strategy-catalog",),
            )
        ]
    )


def test_health() -> None:
    client = TestClient(create_app(fixture_catalog()))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "api_version": "v1"}


def test_strategies_contract_shape() -> None:
    client = TestClient(create_app(fixture_catalog()))
    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    assert response.json() == [
        {
            "strategy_id": "fixture_observation_strategy",
            "display_name": "Fixture Observation Strategy",
            "version": "v0.1",
            "supported_lottery_types": ["BIG_LOTTO"],
            "minimum_history": 1,
            "lifecycle_status": "OBSERVATION",
            "executable": False,
        }
    ]


def test_strategy_overview_contract_shape_and_provenance() -> None:
    client = TestClient(create_app(fixture_catalog()))
    response = client.get("/api/v1/strategy-overview")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "strategy_id": "fixture_observation_strategy",
                "display_name": "Fixture Observation Strategy",
                "version": "v0.1",
                "supported_lottery_types": ["BIG_LOTTO"],
                "minimum_history": 1,
                "lifecycle_status": "OBSERVATION",
                "executable": False,
                "provenance": ["fixture:strategy-catalog"],
            }
        ],
        "summary": {
            "total": 1,
            "executable_count": 0,
            "metadata_only_count": 1,
            "lifecycle_counts": {
                "IDEA": 0,
                "OBSERVATION": 1,
                "ONLINE": 0,
                "REJECTED": 0,
                "RETIRED": 0,
            },
            "lottery_type_counts": {
                "DAILY_539": 0,
                "BIG_LOTTO": 1,
                "POWER_LOTTO": 0,
            },
        },
        "capabilities": {
            "evaluation_metrics_available": False,
            "d3_status_available": False,
            "best_strategy_ranking_available": False,
            "unavailable_reason_codes": [
                "NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE"
            ],
        },
    }


def test_strategy_overview_combines_trimmed_query_filters() -> None:
    client = TestClient(create_app(fixture_catalog()))
    response = client.get(
        "/api/v1/strategy-overview",
        params={
            "q": "  OBSERVATION  ",
            "lottery_type": "BIG_LOTTO",
            "lifecycle_status": "OBSERVATION",
            "executable": "false",
        },
    )

    assert response.status_code == 200
    assert [item["strategy_id"] for item in response.json()["items"]] == [
        "fixture_observation_strategy"
    ]


def test_strategy_overview_filtered_empty_is_successful() -> None:
    response = TestClient(create_app(fixture_catalog())).get(
        "/api/v1/strategy-overview", params={"q": "not-present"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["summary"]["total"] == 0


def test_strategy_overview_rejects_blank_overlong_and_unknown_query_properties() -> None:
    client = TestClient(create_app(fixture_catalog()))

    for params, expected_location, expected_type in (
        ({"q": "   "}, "query.q", "string_too_short"),
        ({"q": "x" * 101}, "query.q", "string_too_long"),
        ({"unknown": "value"}, "query.unknown", "extra_forbidden"),
    ):
        response = client.get("/api/v1/strategy-overview", params=params)
        assert response.status_code == 422
        payload = cast(dict[str, object], response.json())
        assert payload["error_code"] == "REQUEST_VALIDATION_FAILED"
        assert payload["message"] == "Request validation failed."
        assert "detail" not in payload

        fields = cast(list[dict[str, str]], payload["fields"])
        assert isinstance(fields, list)
        assert {
            "location": expected_location,
            "type": expected_type,
        } in fields
        assert all(set(field) == {"location", "type"} for field in fields)


def test_strategy_overview_documents_sanitized_validation_response() -> None:
    document = create_app(fixture_catalog()).openapi()
    response_422 = document["paths"]["/api/v1/strategy-overview"]["get"][
        "responses"
    ]["422"]

    assert response_422["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiValidationErrorResponse"
    }
    assert "#/components/schemas/HTTPValidationError" not in json.dumps(response_422)

    schemas = document["components"]["schemas"]
    validation_response = schemas["ApiValidationErrorResponse"]
    assert {"error_code", "message", "fields"} <= set(
        validation_response["properties"]
    )
    assert validation_response["properties"]["fields"] == {
        "items": {"$ref": "#/components/schemas/RequestValidationIssueView"},
        "type": "array",
        "title": "Fields",
    }
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas


def test_strategy_overview_generated_declaration_uses_sanitized_response() -> None:
    declaration = (ROOT / "frontend/src/api/generated/openapi.d.ts").read_text(
        encoding="utf-8"
    )
    overview_declaration = declaration.split('"/api/v1/strategy-overview": {', 1)[
        1
    ].split('"/api/v1/draw-imports/preview": {', 1)[0]

    assert (
        '"application/json": components[\'schemas\']["ApiValidationErrorResponse"]'
        in overview_declaration
    )
    assert "HTTPValidationError" not in overview_declaration


def test_generate_bet_generated_declaration_documents_operation_and_sanitized_response() -> None:
    declaration = (ROOT / "frontend/src/api/generated/openapi.d.ts").read_text(
        encoding="utf-8"
    )
    generate_bet_declaration = declaration.split('"/api/v1/generate-bet": {', 1)[
        1
    ].split("export interface components", 1)[0]

    assert "post:" in generate_bet_declaration
    assert (
        '"application/json": components[\'schemas\']["ApiValidationErrorResponse"]'
        in generate_bet_declaration
    )
    assert "HTTPValidationError" not in generate_bet_declaration


def test_strategy_overview_is_db_and_data_path_free(tmp_path: Path) -> None:
    forbidden_data_path = tmp_path / "must-not-exist"

    def fail_data_paths() -> Never:
        forbidden_data_path.mkdir()
        raise AssertionError("Strategy Overview invoked the data-path provider")

    client = TestClient(
        create_app(fixture_catalog(), data_paths_provider=fail_data_paths)
    )
    response = client.get("/api/v1/strategy-overview", params={"executable": "false"})

    assert response.status_code == 200
    assert not forbidden_data_path.exists()


def test_strategy_overview_does_not_expose_measured_result_fields() -> None:
    response = TestClient(create_app(fixture_catalog())).get("/api/v1/strategy-overview")
    payload = cast(dict[str, object], response.json())
    items = cast(list[dict[str, object]], payload["items"])
    item = items[0]

    assert set(item) == {
        "strategy_id",
        "display_name",
        "version",
        "supported_lottery_types",
        "minimum_history",
        "lifecycle_status",
        "executable",
        "provenance",
    }
    assert not ({"score", "rank", "d3", "hit_rate", "prediction"} & set(item))


def test_default_strategy_endpoint_is_db_free(monkeypatch: MonkeyPatch) -> None:
    import sqlite3

    def fail_on_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"unexpected sqlite connect: {args!r} {kwargs!r}")

    monkeypatch.setattr(sqlite3, "connect", fail_on_connect)
    client = TestClient(create_app())
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "api_version": "v1"}
    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    manifest = cast(
        dict[str, object],
        json.loads(
            (ROOT / "tests/fixtures/legacy/p600b/manifest.json").read_text(encoding="utf-8")
        ),
    )
    scope = cast(dict[str, object], manifest["scope"])
    target_ids = cast(list[str], scope["strategy_ids"])
    records = cast(list[dict[str, object]], response.json())
    records_by_id = {str(record["strategy_id"]): record for record in records}
    assert set(target_ids) <= records_by_id.keys()
    assert [
        record["strategy_id"] for record in records if record["strategy_id"] in target_ids
    ] == target_ids
    assert all(
        records_by_id[strategy_id]["lifecycle_status"] == "ONLINE" for strategy_id in target_ids
    )
    assert all(records_by_id[strategy_id]["executable"] is True for strategy_id in target_ids)


def test_openapi_exposes_exact_local_runtime_operation_set() -> None:
    response = TestClient(create_app()).get("/openapi.json")
    assert response.status_code == 200
    document = cast(dict[str, object], response.json())
    paths = cast(dict[str, dict[str, object]], document["paths"])
    operations: set[tuple[str, str]] = {
        (method, path)
        for path, path_item in paths.items()
        for method in path_item
        if method in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    }
    assert operations == {
        ("get", "/api/health"),
        ("get", "/api/v1/strategies"),
        ("get", "/api/v1/strategy-overview"),
        ("post", "/api/v1/draw-imports/preview"),
        ("post", "/api/v1/draw-imports/commit"),
        ("get", "/api/v1/draws"),
        ("get", "/api/v1/draws/{lottery_type}/{draw_number}"),
        ("get", "/api/v1/ingestion-runs"),
        ("get", "/api/v1/ingestion-runs/{run_id}"),
        ("post", "/api/v1/generate-bet"),
        ("post", "/api/v1/live-zone-split-bets"),
        ("get", "/api/v1/historical-results/runs"),
        ("get", "/api/v1/historical-results/runs/{run_id}/strategies"),
        ("get", "/api/v1/historical-results/runs/{run_id}/replay"),
        ("get", "/api/v1/historical-results/portfolios/{portfolio_id}"),
        ("get", "/api/v1/replay-rankings/optimal"),
        ("get", "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}"),
        (
            "get",
            "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions",
        ),
        (
            "get",
            "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates",
        ),
        (
            "get",
            "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate",
        ),
    }
    assert len(operations) == 20


def test_replay_ranking_openapi_requires_exact_persisted_scoring_sha() -> None:
    operation = create_app().openapi()["paths"]["/api/v1/replay-rankings/optimal"][
        "get"
    ]

    assert operation["operationId"] == "getOptimalReplayPortfolioRankings"
    assert [parameter["name"] for parameter in operation["parameters"]] == [
        "scoring_artifact_sha256",
        "top_k",
    ]
    selector = operation["parameters"][0]
    assert selector["in"] == "query"
    assert selector["required"] is True
    assert selector["schema"]["pattern"] == "^[0-9a-f]{64}$"
    assert "default" not in selector["schema"]
    for status, schema_name in {
        "404": "ApiErrorResponse",
        "422": "ApiValidationErrorResponse",
        "503": "ApiErrorResponse",
    }.items():
        assert operation["responses"][status]["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{schema_name}"
        }


def test_generated_types_preserve_operation_parameter_location_and_requiredness() -> None:
    declaration = (ROOT / "frontend/src/api/generated/openapi.d.ts").read_text(
        encoding="utf-8"
    )
    ranking_block = declaration.split('"/api/v1/replay-rankings/optimal": {', 1)[1].split(
        '"/api/v1/replay-scoring/{scoring_artifact_payload_sha256}": {', 1
    )[0]

    assert '"query": {' in ranking_block
    assert '"scoring_artifact_sha256": string' in ranking_block
    assert '"scoring_artifact_sha256"?:' not in ranking_block
    assert '"top_k"?: number' in ranking_block

    draw_block = declaration.split('"/api/v1/draws/{lottery_type}/{draw_number}": {', 1)[
        1
    ].split('"/api/v1/ingestion-runs": {', 1)[0]
    assert '"path": {' in draw_block
    assert '"lottery_type": components[\'schemas\']["LotteryType"]' in draw_block
    assert '"draw_number": string' in draw_block


def test_openapi_generator_handles_parameters_generically_without_replay_special_cases() -> None:
    source = (ROOT / "frontend/scripts/generate-openapi-types.mjs").read_text(
        encoding="utf-8"
    )

    assert "operation.parameters ?? []" in source
    assert "schemaType(schema)" in source
    assert "['query', 'path', 'header', 'cookie']" in source
    assert "scoring_artifact_sha256" not in source
    assert "/api/v1/replay-rankings/optimal" not in source
    assert "Unsupported OpenAPI operation parameter" in source


def test_replay_scoring_openapi_pins_exact_sha_get_contract_and_sanitized_errors() -> None:
    document = create_app().openapi()
    paths = document["paths"]
    run_path = paths["/api/v1/replay-scoring/{scoring_artifact_payload_sha256}"]

    assert set(run_path) == {"get"}
    assert run_path["get"]["operationId"] == "getReplayScoringRun"
    selector = next(
        parameter
        for parameter in run_path["get"]["parameters"]
        if parameter["name"] == "scoring_artifact_payload_sha256"
    )
    assert selector["required"] is True
    assert selector["schema"]["pattern"] == "^[0-9a-f]{64}$"

    expected_operations = {
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions": (
            "listReplayScoringPredictions"
        ),
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates": (
            "listReplayScoringStrategyAggregates"
        ),
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate": (
            "getReplayScoringOverallAggregate"
        ),
    }
    for path, operation_id in expected_operations.items():
        operation = paths[path]["get"]
        assert operation["operationId"] == operation_id
        assert operation["responses"]["422"]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ApiValidationErrorResponse"}
        assert operation["responses"]["503"]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ApiErrorResponse"}


def test_replay_scoring_generated_types_include_all_read_only_operations() -> None:
    declaration = (ROOT / "frontend/src/api/generated/openapi.d.ts").read_text(
        encoding="utf-8"
    )

    expected_success_types = {
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}": (
            "components['schemas'][\"ReplayScoringRunResponse\"]"
        ),
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions": (
            "Array<components['schemas'][\"ReplayScoredPredictionView\"]>"
        ),
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates": (
            "Array<components['schemas'][\"ReplayStrategyAggregateView\"]>"
        ),
        "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate": (
            "components['schemas'][\"ReplayOverallAggregateResponse\"]"
        ),
    }
    expected_response_types = {
        404: "components['schemas'][\"ApiErrorResponse\"]",
        422: "components['schemas'][\"ApiValidationErrorResponse\"]",
        503: "components['schemas'][\"ApiErrorResponse\"]",
    }

    for path, success_type in expected_success_types.items():
        marker = f'  "{path}": {{'
        start = declaration.index(marker)
        next_path = declaration.find('\n  "/api/', start + len(marker))
        paths_end = declaration.index("\n}\n\nexport interface components", start)
        end = paths_end if next_path == -1 else min(next_path, paths_end)
        path_block = declaration[start:end]

        assert path_block.count("get: {") == 1
        assert not any(
            f"{method}: {{" in path_block
            for method in ("post", "put", "patch", "delete")
        )
        for status, response_type in {200: success_type, **expected_response_types}.items():
            lines = path_block.splitlines()
            response_start = next(
                index for index, line in enumerate(lines) if line.strip() == f"{status}: {{"
            )
            response_lines: list[str] = []
            for line in lines[response_start + 1 :]:
                stripped = line.strip()
                if stripped[:3].isdigit() and stripped[3:] == ": {":
                    break
                response_lines.append(line)
            response_block = "\n".join(response_lines)
            assert f'"application/json": {response_type}' in response_block


def test_committed_openapi_contract_is_current() -> None:
    committed = cast(
        dict[str, object],
        json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8")),
    )
    assert committed == create_app().openapi()
