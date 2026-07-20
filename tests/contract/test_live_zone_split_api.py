"""API contract tests for the bounded, DB-free /api/v1/live-zone-split-bets endpoint."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

import json
from pathlib import Path
from typing import Never, cast

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from lottolab.application import local_runtime
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    build_production_generate_one_bet,
)
from lottolab.application.use_cases.generate_live_zone_split_bets import (
    GenerateLiveZoneSplitBets,
    GenerateLiveZoneSplitBetsReason,
    GenerateLiveZoneSplitBetsResult,
    GenerateLiveZoneSplitBetsStatus,
    build_production_generate_live_zone_split_bets,
)
from lottolab.interfaces.api.app import create_app
from lottolab.strategies.adapters import BigLottoZoneSplit3BetBet1Adapter
from lottolab.strategies.live.biglotto_zone_split import (
    LiveZoneSplitResult,
    MalformedSamplerOutput,
)

ROOT = Path(__file__).resolve().parents[2]
PATH = "/api/v1/live-zone-split-bets"
APPROVED_FIELDS = {
    "status",
    "bets",
    "coverage_rate",
    "total_unique_numbers",
    "method",
    "philosophy",
    "reason_code",
}
_POOL_SIZE = 49


def _core_result(num_bets: int) -> LiveZoneSplitResult:
    bets = tuple(
        tuple(((offset + index) % _POOL_SIZE) + 1 for offset in range(6))
        for index in range(num_bets)
    )
    all_numbers = {number for bet in bets for number in bet}
    return LiveZoneSplitResult(
        bets=bets,
        coverage_rate=round(len(all_numbers) / _POOL_SIZE, 4),
        total_unique_numbers=len(all_numbers),
        method="fixture-method",
        philosophy="fixture-philosophy",
    )


class _CountingGenerateLiveZoneSplitBets:
    """A fake use case, matching the injected interface, that counts calls."""

    def __init__(self) -> None:
        self.execute_count = 0
        self._delegate = build_production_generate_live_zone_split_bets()

    def execute(self, request: object) -> object:
        self.execute_count += 1
        return self._delegate.execute(request)  # type: ignore[arg-type]


class _FixedResultUseCase:
    """A fake use case that always returns the same closed result, regardless of input."""

    def __init__(self, result: GenerateLiveZoneSplitBetsResult) -> None:
        self._result = result

    def execute(self, request: object) -> GenerateLiveZoneSplitBetsResult:
        del request
        return self._result


def _client_with_generator(outcome: object) -> TestClient:
    def generator(num_bets: int) -> LiveZoneSplitResult:
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome  # type: ignore[return-value]

    use_case = GenerateLiveZoneSplitBets(generator)
    return TestClient(create_app(generate_live_zone_split_bets=use_case))


# --- 1. valid num_bets map every application payload field exactly ---------


def test_valid_num_bets_map_every_application_payload_field_exactly() -> None:
    for num_bets in (1, 3, 10):
        core_result = _core_result(num_bets)
        client = _client_with_generator(core_result)

        response = client.post(PATH, json={"num_bets": num_bets})

        assert response.status_code == 200
        payload = cast(dict[str, object], response.json())
        assert set(payload) == APPROVED_FIELDS
        assert payload["status"] == "OK"
        assert payload["bets"] == [list(bet) for bet in core_result.bets]
        assert payload["coverage_rate"] == core_result.coverage_rate
        assert payload["total_unique_numbers"] == core_result.total_unique_numbers
        assert payload["method"] == core_result.method
        assert payload["philosophy"] == core_result.philosophy
        assert payload["reason_code"] is None


# --- 2. every application outcome returns HTTP 200 -------------------------


def test_ok_outcome_is_http_200() -> None:
    client = _client_with_generator(_core_result(3))
    response = client.post(PATH, json={"num_bets": 3})
    assert response.status_code == 200
    assert cast(dict[str, object], response.json())["status"] == "OK"


def test_invalid_request_outcome_is_http_200() -> None:
    fixed = _FixedResultUseCase(
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
            bets=None,
            coverage_rate=None,
            total_unique_numbers=None,
            method=None,
            philosophy=None,
            reason_code=GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS,
        )
    )
    client = TestClient(
        create_app(generate_live_zone_split_bets=cast(GenerateLiveZoneSplitBets, fixed))
    )

    response = client.post(PATH, json={"num_bets": 1})

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["status"] == "INVALID_REQUEST"
    assert payload["reason_code"] == "INVALID_NUM_BETS"
    assert payload["bets"] is None


def test_invalid_output_outcome_is_http_200() -> None:
    client = _client_with_generator(MalformedSamplerOutput())
    response = client.post(PATH, json={"num_bets": 2})

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["status"] == "INVALID_OUTPUT"
    assert payload["reason_code"] == "MALFORMED_OUTPUT"
    assert payload["bets"] is None


def test_execution_error_outcome_is_http_200() -> None:
    client = _client_with_generator(RuntimeError("boom"))
    response = client.post(PATH, json={"num_bets": 2})

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["status"] == "EXECUTION_ERROR"
    assert payload["reason_code"] == "EXECUTION_ERROR"
    assert payload["bets"] is None


# --- 3. extra fields are a sanitized 422 ------------------------------------


def test_unknown_extra_request_field_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": 1, "unexpected": "value"})

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    assert payload["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert "detail" not in payload
    fields = cast(list[dict[str, str]], payload["fields"])
    assert {"location": "body.unexpected", "type": "extra_forbidden"} in fields


# --- 4. invalid transport values are a sanitized 422 ------------------------


def test_zero_num_bets_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": 0})
    assert response.status_code == 422


def test_eleven_num_bets_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": 11})
    assert response.status_code == 422


def test_negative_num_bets_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": -1})
    assert response.status_code == 422


def test_boolean_num_bets_is_rejected_as_non_strict_integer() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": True})

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    fields = cast(list[dict[str, str]], payload["fields"])
    assert {"location": "body.num_bets", "type": "int_type"} in fields


def test_float_num_bets_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": 1.5})
    assert response.status_code == 422


def test_string_num_bets_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": "3"})
    assert response.status_code == 422


def test_null_num_bets_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": None})
    assert response.status_code == 422


def test_missing_num_bets_is_sanitized_422() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={})

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    fields = cast(list[dict[str, str]], payload["fields"])
    assert {"location": "body.num_bets", "type": "missing"} in fields


# --- 5. sanitized 422 contains no raw input or exception message -----------


def test_sanitized_422_contains_no_raw_input_or_exception_message() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": 999, "secret_marker": "raw-value-xyz"})

    assert response.status_code == 422
    body_text = response.text
    assert "raw-value-xyz" not in body_text
    assert "999" not in body_text
    assert "Traceback" not in body_text
    payload = cast(dict[str, object], response.json())
    assert set(payload) == {"error_code", "message", "fields", "preview"}
    assert payload["preview"] is None


# --- 6. response fields are exact -------------------------------------------


def test_response_has_no_extra_strategy_or_history_fields() -> None:
    client = _client_with_generator(_core_result(1))
    response = client.post(PATH, json={"num_bets": 1})
    payload = cast(dict[str, object], response.json())

    assert set(payload) == APPROVED_FIELDS
    assert not ({"strategy_id", "lottery_type", "seed", "history", "numbers"} & set(payload))


# --- 7. router uses the injected use case and composes nothing itself ------


def test_generate_live_zone_split_bets_dependency_is_injected_once_and_reused() -> None:
    injected = _CountingGenerateLiveZoneSplitBets()
    client = TestClient(
        create_app(generate_live_zone_split_bets=cast(GenerateLiveZoneSplitBets, injected))
    )

    for _ in range(3):
        response = client.post(PATH, json={"num_bets": 1})
        assert response.status_code == 200

    assert injected.execute_count == 3


# --- 8. create_app() default composition uses the production P605E builder -


def test_generate_live_zone_split_bets_use_case_is_not_rebuilt_when_injected(
    monkeypatch: MonkeyPatch,
) -> None:
    import lottolab.interfaces.api.app as app_module

    build_calls = {"count": 0}
    original_build = build_production_generate_live_zone_split_bets

    def counting_build() -> GenerateLiveZoneSplitBets:
        build_calls["count"] += 1
        return original_build()

    monkeypatch.setattr(
        app_module, "build_production_generate_live_zone_split_bets", counting_build
    )

    create_app(generate_live_zone_split_bets=original_build())

    assert build_calls["count"] == 0


def test_default_composition_calls_the_production_builder(monkeypatch: MonkeyPatch) -> None:
    import lottolab.interfaces.api.app as app_module

    build_calls = {"count": 0}
    original_build = build_production_generate_live_zone_split_bets

    def counting_build() -> GenerateLiveZoneSplitBets:
        build_calls["count"] += 1
        return original_build()

    monkeypatch.setattr(
        app_module, "build_production_generate_live_zone_split_bets", counting_build
    )

    create_app()

    assert build_calls["count"] == 1


# --- 9. existing /api/v1/generate-bet behavior and schema are unchanged ----


def test_existing_generate_bet_endpoint_is_unaffected() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/generate-bet",
        json={
            "strategy_id": BigLottoZoneSplit3BetBet1Adapter.strategy_id,
            "seed": 1,
            "history": [
                {"draw": str(index), "date": str(index), "numbers": [1, 2, 3, 4, 5, 6]}
                for index in range(100)
            ],
        },
    )
    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert set(payload) == {
        "strategy_id",
        "lottery_type",
        "seed",
        "status",
        "numbers",
        "reason_code",
    }


def test_generate_one_bet_default_composition_is_unaffected(monkeypatch: MonkeyPatch) -> None:
    import lottolab.interfaces.api.app as app_module

    build_calls = {"count": 0}
    original_build = build_production_generate_one_bet

    def counting_build() -> GenerateOneBet:
        build_calls["count"] += 1
        return original_build()

    monkeypatch.setattr(app_module, "build_production_generate_one_bet", counting_build)

    create_app()

    assert build_calls["count"] == 1


# --- 10. OpenAPI operation set includes exactly the new POST operation -----


def test_openapi_adds_exactly_one_new_operation() -> None:
    document = create_app().openapi()
    paths = cast(dict[str, dict[str, dict[str, object]]], document["paths"])

    assert PATH in paths
    assert set(paths[PATH]) == {"post"}
    assert paths[PATH]["post"]["operationId"] == "generateLiveZoneSplitBets"


# --- 11. forbidden-word exception remains exactly one path -----------------


def test_forbidden_word_exception_remains_only_generate_bet() -> None:
    # A path with no forbidden route word needs no exception and must validate
    # as-is; the exact-operation-set check stays load-bearing for both paths.
    response = TestClient(create_app()).get("/openapi.json")
    document = cast(dict[str, object], response.json())
    local_runtime.validate_openapi_payload(document)

    paths = cast(dict[str, object], document["paths"])
    tampered_paths = dict(paths)
    tampered_paths["/api/v1/live-zone-split-bets-generate"] = {"post": {}}
    with pytest.raises(
        local_runtime.LocalRuntimeSafetyError, match="generation or execution"
    ):
        local_runtime.validate_openapi_payload({"paths": tampered_paths})


# --- 12. no DB/data-path access occurs -------------------------------------


def test_live_zone_split_bets_is_db_and_data_path_free() -> None:
    forbidden_calls: list[None] = []

    def fail_data_paths() -> Never:
        forbidden_calls.append(None)
        raise AssertionError("live-zone-split-bets invoked the data-path provider")

    client = TestClient(create_app(data_paths_provider=fail_data_paths))
    response = client.post(PATH, json={"num_bets": 1})

    assert response.status_code == 200
    assert forbidden_calls == []


def test_openapi_documents_sanitized_response_with_no_regression() -> None:
    document = create_app().openapi()
    response_422 = document["paths"][PATH]["post"]["responses"]["422"]

    assert response_422["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiValidationErrorResponse"
    }
    assert "#/components/schemas/HTTPValidationError" not in json.dumps(response_422)
    assert "HTTPValidationError" not in document["components"]["schemas"]
