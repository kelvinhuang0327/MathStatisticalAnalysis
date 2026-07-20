"""API contract tests for the bounded, DB-free /api/v1/generate-bet endpoint."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

import json
from pathlib import Path
from typing import Never, cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    build_production_generate_one_bet,
)
from lottolab.interfaces.api.app import create_app
from lottolab.strategies.adapters import (
    BigLottoDeviation2BetAdapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
)

ROOT = Path(__file__).resolve().parents[2]
PATH = "/api/v1/generate-bet"
APPROVED_FIELDS = {"strategy_id", "lottery_type", "seed", "status", "numbers", "reason_code"}


def _rows(count: int) -> list[dict[str, object]]:
    return [
        {"draw": str(index), "date": str(index), "numbers": [1, 2, 3, 4, 5, 6]}
        for index in range(count)
    ]


def _request(
    *, strategy_id: str, seed: int = 1, history: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "strategy_id": strategy_id,
        "seed": seed,
        "history": history if history is not None else _rows(100),
    }


def test_health_unaffected() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200


def test_happy_path_for_each_online_strategy() -> None:
    client = TestClient(create_app())
    for strategy_id in (
        BigLottoSocialWisdomAntiPopularityAdapter.strategy_id,
        BigLottoZoneSplit3BetBet1Adapter.strategy_id,
        BigLottoDeviation2BetAdapter.strategy_id,
    ):
        response = client.post(PATH, json=_request(strategy_id=strategy_id))
        assert response.status_code == 200
        payload = cast(dict[str, object], response.json())

        assert set(payload) == APPROVED_FIELDS
        assert payload["strategy_id"] == strategy_id
        assert payload["lottery_type"] == "BIG_LOTTO"
        assert payload["status"] == "OK"
        assert payload["reason_code"] is None

        numbers = cast(list[int], payload["numbers"])
        assert len(numbers) == 6
        assert len(set(numbers)) == 6
        assert all(1 <= number <= 49 for number in numbers)


def test_unknown_strategy_is_a_closed_200_result() -> None:
    client = TestClient(create_app())
    response = client.post(PATH, json=_request(strategy_id="does-not-exist"))

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["status"] == "STRATEGY_UNAVAILABLE"
    assert payload["reason_code"] == "UNKNOWN_STRATEGY"
    assert payload["numbers"] is None
    assert payload["seed"] == 1


def test_short_history_for_deviation_strategy_is_insufficient_history() -> None:
    client = TestClient(create_app())
    response = client.post(
        PATH,
        json=_request(
            strategy_id=BigLottoDeviation2BetAdapter.strategy_id,
            history=_rows(5),
        ),
    )

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["status"] == "INSUFFICIENT_HISTORY"
    assert payload["reason_code"] == "INSUFFICIENT_HISTORY"
    assert payload["numbers"] is None


def test_structurally_valid_rule_invalid_history_is_a_closed_invalid_output() -> None:
    client = TestClient(create_app())
    response = client.post(
        PATH,
        json=_request(
            strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
            history=[{"draw": "1", "date": "1", "numbers": [1, 2, 3]}],
        ),
    )

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["status"] == "INVALID_OUTPUT"
    assert payload["reason_code"] == "INVALID_OUTPUT"
    assert payload["numbers"] is None


def test_seed_is_metadata_only_and_echoed_verbatim() -> None:
    client = TestClient(create_app())
    strategy_id = BigLottoZoneSplit3BetBet1Adapter.strategy_id
    history = _rows(100)

    first = client.post(PATH, json=_request(strategy_id=strategy_id, seed=11, history=history))
    second = client.post(PATH, json=_request(strategy_id=strategy_id, seed=22, history=history))

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = cast(dict[str, object], first.json())
    second_payload = cast(dict[str, object], second.json())

    assert first_payload["seed"] == 11
    assert second_payload["seed"] == 22
    for key in ("strategy_id", "lottery_type", "status", "numbers", "reason_code"):
        assert first_payload[key] == second_payload[key]


def test_repeated_identical_request_is_deterministic() -> None:
    client = TestClient(create_app())
    request = _request(strategy_id=BigLottoSocialWisdomAntiPopularityAdapter.strategy_id)

    first = client.post(PATH, json=request)
    second = client.post(PATH, json=request)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_unknown_extra_request_field_is_sanitized_422() -> None:
    client = TestClient(create_app())
    request = _request(strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id)
    request["unexpected"] = "value"

    response = client.post(PATH, json=request)

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    assert payload["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert "detail" not in payload
    fields = cast(list[dict[str, str]], payload["fields"])
    assert {"location": "body.unexpected", "type": "extra_forbidden"} in fields


def test_unknown_extra_history_row_field_is_sanitized_422() -> None:
    client = TestClient(create_app())
    request = _request(
        strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
        history=[{"draw": "1", "date": "1", "numbers": [1, 2, 3, 4, 5, 6], "extra": True}],
    )

    response = client.post(PATH, json=request)

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    assert payload["error_code"] == "REQUEST_VALIDATION_FAILED"
    fields = cast(list[dict[str, str]], payload["fields"])
    assert any(field["type"] == "extra_forbidden" for field in fields)


def test_oversized_history_is_sanitized_422() -> None:
    client = TestClient(create_app())
    response = client.post(
        PATH,
        json=_request(
            strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
            history=_rows(5001),
        ),
    )

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    assert payload["error_code"] == "REQUEST_VALIDATION_FAILED"


def test_boolean_seed_is_rejected_as_non_strict_integer() -> None:
    client = TestClient(create_app())
    request = _request(strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id)
    request["seed"] = True

    response = client.post(PATH, json=request)

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    fields = cast(list[dict[str, str]], payload["fields"])
    assert {"location": "body.seed", "type": "int_type"} in fields


def test_boolean_number_value_is_rejected_as_non_strict_integer() -> None:
    client = TestClient(create_app())
    request = _request(
        strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
        history=[{"draw": "1", "date": "1", "numbers": [1, 2, 3, 4, 5, True]}],
    )

    response = client.post(PATH, json=request)

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    fields = cast(list[dict[str, str]], payload["fields"])
    assert any(field["type"] == "int_type" for field in fields)


def test_openapi_documents_sanitized_response_with_no_regression() -> None:
    document = create_app().openapi()
    response_422 = document["paths"][PATH]["post"]["responses"]["422"]

    assert response_422["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiValidationErrorResponse"
    }
    assert "#/components/schemas/HTTPValidationError" not in json.dumps(response_422)
    assert "HTTPValidationError" not in document["components"]["schemas"]


def test_generate_bet_is_db_and_data_path_free() -> None:
    forbidden_calls: list[None] = []

    def fail_data_paths() -> Never:
        forbidden_calls.append(None)
        raise AssertionError("generate-bet invoked the data-path provider")

    client = TestClient(create_app(data_paths_provider=fail_data_paths))
    response = client.post(
        PATH, json=_request(strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id)
    )

    assert response.status_code == 200
    assert forbidden_calls == []


def test_generate_one_bet_dependency_is_injected_once_and_reused() -> None:
    class _CountingUseCase:
        def __init__(self) -> None:
            self.execute_count = 0
            self._delegate = build_production_generate_one_bet()

        def execute(self, request: object) -> object:
            self.execute_count += 1
            return self._delegate.execute(request)  # type: ignore[arg-type]

    injected = _CountingUseCase()
    client = TestClient(create_app(generate_one_bet=cast(GenerateOneBet, injected)))

    for _ in range(3):
        response = client.post(
            PATH,
            json=_request(strategy_id=BigLottoSocialWisdomAntiPopularityAdapter.strategy_id),
        )
        assert response.status_code == 200

    assert injected.execute_count == 3


def test_generate_bet_use_case_is_not_rebuilt_when_injected(monkeypatch: MonkeyPatch) -> None:
    import lottolab.interfaces.api.app as app_module

    build_calls = {"count": 0}
    original_build = build_production_generate_one_bet

    def counting_build() -> GenerateOneBet:
        build_calls["count"] += 1
        return original_build()

    monkeypatch.setattr(app_module, "build_production_generate_one_bet", counting_build)

    create_app(generate_one_bet=original_build())

    assert build_calls["count"] == 0
