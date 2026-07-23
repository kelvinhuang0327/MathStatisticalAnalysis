"""HTTP contract tests for persisted Historical Prefix success windows."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import cast

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.interfaces.api.app import create_app

IMPORT_IDENTITY = "a" * 64
LIST_PATH = "/api/v1/historical-prefix-success-windows"
EXACT_OPENAPI_PATH = (
    f"{LIST_PATH}/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}"
)
MATRIX_OPENAPI_PATH = f"{EXACT_OPENAPI_PATH}/matrix"


def _strategy_path(
    strategy_id: str = "strategy-a",
    strategy_version: str = "v1",
    replicate: int = 1,
) -> str:
    return (
        f"{LIST_PATH}/strategies/{strategy_id}/{strategy_version}/{replicate}"
    )


def _matrix_path(
    strategy_id: str = "strategy-a",
    strategy_version: str = "v1",
    replicate: int = 1,
) -> str:
    return f"{_strategy_path(strategy_id, strategy_version, replicate)}/matrix"


class _Reader:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.source = source
        self.calls: list[str] = []

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        self.calls.append(import_identity_sha256)
        return self.source


class _Factory:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.reader = _Reader(source)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _source() -> HistoricalPrefixSuccessWindowSource:
    observations = build_success_observations(
        50,
        outcome_factory=lambda _observation, position: (
            (3, False) if position == 1 else (0, False)
        ),
    )
    return build_success_source(
        (
            build_success_strategy("z-first", observations=observations),
            build_success_strategy(
                "alias",
                observations=observations,
                effective_strategy_id="base",
                alias_of_strategy_id="base",
            ),
            build_success_strategy("base", observations=observations, replicate=2),
            build_success_strategy("zero"),
        )
    )


def _client(
    source: HistoricalPrefixSuccessWindowSource | None = None,
) -> tuple[TestClient, _Factory]:
    factory = _Factory(_source() if source is None else source)
    return (
        TestClient(
            create_app(
                historical_prefix_success_window_source_reader_factory=factory
            )
        ),
        factory,
    )


def _params(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "import_identity_sha256": IMPORT_IDENTITY,
        "prefix_count": 1,
        "criterion": "M3_PLUS",
    }
    values.update(overrides)
    return values


def _assert_no_float(value: object) -> None:
    if isinstance(value, dict):
        for item in cast(dict[object, object], value).values():
            _assert_no_float(item)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _assert_no_float(item)
    else:
        assert type(value) is not float


def test_app_construction_and_openapi_generation_do_not_call_factory() -> None:
    factory = _Factory(_source())
    app = create_app(historical_prefix_success_window_source_reader_factory=factory)

    document = app.openapi()

    assert factory.calls == 0
    assert factory.reader.calls == []
    assert LIST_PATH in document["paths"]
    assert EXACT_OPENAPI_PATH in document["paths"]
    assert MATRIX_OPENAPI_PATH in document["paths"]


def test_valid_list_request_calls_factory_and_reader_once_and_preserves_page_order() -> None:
    client, factory = _client()

    response = client.get(LIST_PATH, params=_params(limit=2, offset=1))

    assert response.status_code == 200
    assert factory.calls == 1
    assert factory.reader.calls == [IMPORT_IDENTITY]
    payload = response.json()
    assert payload["metadata"]["import_identity_sha256"] == IMPORT_IDENTITY
    assert payload["criterion"] == {
        "criterion": "M3_PLUS",
        "minimum_main_hits": 3,
        "require_special_hit": False,
        "measurement_mode": "LEGAL_TICKET_PRIZE",
    }
    assert payload["prefix_count"] == 1
    assert payload["total_count"] == 4
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert [item["strategy"]["strategy_id"] for item in payload["items"]] == [
        "alias",
        "base",
    ]
    assert payload["items"][0]["selection"]["strategy_id"] == "alias"
    assert payload["items"][0]["strategy"]["effective_strategy_id"] == "base"
    assert payload["items"][1]["selection"]["replicate"] == 2
    _assert_no_float(payload)


def test_exact_strategy_response_preserves_four_windows_rates_and_provenance() -> None:
    client, factory = _client()

    response = client.get(_strategy_path("alias"), params=_params(prefix_count=5))

    assert response.status_code == 200
    assert factory.calls == 1
    assert factory.reader.calls == [IMPORT_IDENTITY]
    payload = response.json()
    assert payload["strategy"]["strategy_id"] == "alias"
    assert payload["selection"] == {
        "lottery": "BIG_LOTTO",
        "strategy_id": "alias",
        "strategy_version": "v1",
        "replicate": 1,
        "ticket_count": 5,
        "max_bet_index": 5,
    }
    assert payload["status"] == "EVALUATED"
    assert payload["source_observation_count"] == 50
    assert [item["window_kind"] for item in payload["windows"]] == [
        "FULL_HISTORY",
        "LONG",
        "MEDIUM",
        "SHORT",
    ]
    assert [item["window_role"] for item in payload["windows"]] == [
        "REFERENCE_ONLY",
        "PRIMARY_EVIDENCE",
        "STABILITY_CONFIRMATION",
        "DEGRADATION_VETO",
    ]
    assert payload["windows"][0]["success_rate"] == {
        "numerator": 50,
        "denominator": 50,
        "available": True,
    }
    assert payload["windows"][1]["success_rate"] == {
        "numerator": 0,
        "denominator": 0,
        "available": False,
    }
    assert payload["windows"][0]["first_target"]["draw_number"] == 1
    assert payload["windows"][0]["last_target"]["draw_number"] == 50
    assert payload["windows"][0]["first_cutoff"]["draw_number"] == 1
    assert "rank" not in payload
    assert "promotion" not in payload


def test_zero_observation_descriptor_returns_200_with_empty_windows() -> None:
    client, _ = _client()

    response = client.get(_strategy_path("zero"), params=_params(prefix_count=20))

    assert response.status_code == 200
    assert response.json()["status"] == "NO_OBSERVATIONS"
    assert response.json()["source_observation_count"] == 0
    assert response.json()["windows"] == []


def test_matrix_response_loads_once_preserves_order_identity_and_exact_arithmetic() -> None:
    client, factory = _client()

    response = client.get(
        _matrix_path("alias"),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )

    assert response.status_code == 200
    assert factory.calls == 1
    assert factory.reader.calls == [IMPORT_IDENTITY]
    payload = response.json()
    assert payload["metadata"]["import_identity_sha256"] == IMPORT_IDENTITY
    assert payload["strategy"]["strategy_id"] == "alias"
    assert payload["strategy"]["effective_strategy_id"] == "base"
    assert payload["strategy"]["alias_of_strategy_id"] == "base"
    assert payload["source_observation_count"] == 50
    assert payload["prefix_counts"] == [1, 2, 3, 4, 5, 10, 15, 20]
    criteria = [
        "M3_PLUS",
        "M4_PLUS",
        "M5_PLUS",
        "M6",
        "M2_PLUS_SPECIAL",
        "M3_PLUS_SPECIAL",
        "M4_PLUS_SPECIAL",
        "M5_PLUS_SPECIAL",
    ]
    assert [item["criterion"] for item in payload["criteria"]] == criteria
    assert payload["cell_count"] == len(payload["cells"]) == 64
    assert [
        (cell["criterion"]["criterion"], cell["prefix_count"])
        for cell in payload["cells"]
    ] == [
        (criterion, prefix)
        for criterion in criteria
        for prefix in [1, 2, 3, 4, 5, 10, 15, 20]
    ]
    first = payload["cells"][0]
    assert [item["window_kind"] for item in first["windows"]] == [
        "FULL_HISTORY",
        "LONG",
        "MEDIUM",
        "SHORT",
    ]
    assert [item["comparison_kind"] for item in first["comparisons"]] == [
        "FULL_HISTORY_TO_LONG",
        "LONG_TO_MEDIUM",
        "MEDIUM_TO_SHORT",
        "LONG_TO_SHORT",
    ]
    assert first["comparisons"][0]["delta"] == {
        "numerator": 0,
        "denominator": 0,
        "available": False,
    }
    assert first["comparisons"][0]["relation"] == "UNAVAILABLE"
    _assert_no_float(payload)
    serialized = response.text.lower()
    for forbidden in ("winner", "ranking", "promotion", "prediction", "confidence"):
        assert forbidden not in serialized


def test_zero_observation_matrix_keeps_64_empty_cells() -> None:
    client, _ = _client()

    response = client.get(
        _matrix_path("zero"),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_observation_count"] == 0
    assert payload["cell_count"] == len(payload["cells"]) == 64
    assert all(
        cell["status"] == "NO_OBSERVATIONS"
        and cell["windows"] == []
        and cell["comparisons"] == []
        for cell in payload["cells"]
    )


@pytest.mark.parametrize(
    "params",
    [
        _params(import_identity_sha256="A" * 64),
        _params(import_identity_sha256=f" {'a' * 64}"),
        _params(import_identity_sha256=f"{'a' * 64} "),
        _params(import_identity_sha256="abc"),
        _params(prefix_count=6),
        _params(prefix_count="true"),
        _params(criterion="M1_PLUS"),
        _params(limit=0),
        _params(limit=201),
        _params(limit="true"),
        _params(offset=-1),
        _params(offset="false"),
    ],
)
def test_invalid_query_is_sanitized_422_before_factory(params: dict[str, object]) -> None:
    client, factory = _client()

    response = client.get(LIST_PATH, params=params)

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert factory.calls == 0
    assert factory.reader.calls == []


@pytest.mark.parametrize(
    "path",
    [
        _strategy_path(" padded "),
        _strategy_path(strategy_version=" padded "),
        _strategy_path(replicate=0),
        f"{LIST_PATH}/strategies/strategy-a/v1/true",
    ],
)
def test_invalid_strategy_path_is_sanitized_422_before_factory(path: str) -> None:
    client, factory = _client()

    response = client.get(path, params=_params())

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert factory.calls == 0


def test_matrix_rejects_extra_axis_query_before_factory() -> None:
    client, factory = _client()

    response = client.get(
        _matrix_path(),
        params={
            "import_identity_sha256": IMPORT_IDENTITY,
            "prefix_count": 1,
            "criterion": "M3_PLUS",
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert factory.calls == 0


@pytest.mark.parametrize(
    ("path", "selector"),
    [
        (_matrix_path(" padded "), IMPORT_IDENTITY),
        (_matrix_path(strategy_version=" padded "), IMPORT_IDENTITY),
        (_matrix_path(replicate=0), IMPORT_IDENTITY),
        (_matrix_path(), "A" * 64),
    ],
)
def test_invalid_matrix_identity_is_sanitized_422_before_factory(
    path: str,
    selector: str,
) -> None:
    client, factory = _client()

    response = client.get(path, params={"import_identity_sha256": selector})

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert factory.calls == 0


def test_missing_factory_absent_import_and_missing_strategy_have_distinct_errors() -> None:
    not_configured = TestClient(create_app()).get(LIST_PATH, params=_params())
    assert not_configured.status_code == 503
    assert not_configured.json() == {
        "error_code": "HISTORICAL_PREFIX_SUCCESS_WINDOWS_NOT_CONFIGURED",
        "message": "Historical prefix success windows are not configured.",
    }

    absent_factory = _Factory(None)
    absent = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=absent_factory
        )
    ).get(LIST_PATH, params=_params())
    assert absent.status_code == 404
    assert absent.json()["error_code"] == "HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND"

    client, _ = _client()
    missing = client.get(_strategy_path("missing"), params=_params())
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND"


def test_storage_failure_is_sanitized_without_exception_sql_table_or_path() -> None:
    class FailingReader:
        def load_source(self, import_identity_sha256: str) -> None:
            del import_identity_sha256
            raise RuntimeError(
                "sqlite3 /Users/owner/private.db SELECT * FROM historical_ticket"
            )

    client = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=FailingReader
        )
    )

    response = client.get(LIST_PATH, params=_params())

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE",
        "message": "Historical prefix success windows are unavailable.",
    }
    serialized = response.text
    for forbidden in ("sqlite", "SELECT", "historical_ticket", "/Users", ".db"):
        assert forbidden not in serialized

    matrix_response = client.get(
        _matrix_path(),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )
    assert matrix_response.status_code == 503
    assert matrix_response.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE"
    )
    for forbidden in ("sqlite", "SELECT", "historical_ticket", "/Users", ".db"):
        assert forbidden not in matrix_response.text


def test_matrix_distinguishes_missing_import_and_missing_exact_strategy() -> None:
    absent_factory = _Factory(None)
    absent = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=absent_factory
        )
    ).get(
        _matrix_path(),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )
    assert absent.status_code == 404
    assert absent.json()["error_code"] == "HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND"

    client, _ = _client()
    missing = client.get(
        _matrix_path("missing"),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )
    assert missing.status_code == 404
    assert missing.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND"
    )


def test_repeated_conversion_and_json_are_byte_identical() -> None:
    client, _ = _client()

    first = client.get(_strategy_path("z-first"), params=_params())
    second = client.get(_strategy_path("z-first"), params=_params())

    assert first.status_code == second.status_code == 200
    assert first.content == second.content

    first_matrix = client.get(
        _matrix_path("z-first"),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )
    second_matrix = client.get(
        _matrix_path("z-first"),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )
    assert first_matrix.status_code == second_matrix.status_code == 200
    assert first_matrix.content == second_matrix.content


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_both_routes_are_get_only(method: str) -> None:
    client, factory = _client()

    list_response = getattr(client, method)(LIST_PATH, params=_params())
    exact_response = getattr(client, method)(_strategy_path(), params=_params())
    matrix_response = getattr(client, method)(
        _matrix_path(),
        params={"import_identity_sha256": IMPORT_IDENTITY},
    )

    assert list_response.status_code == 405
    assert exact_response.status_code == 405
    assert matrix_response.status_code == 405
    assert factory.calls == 0


@pytest.mark.parametrize(
    "path",
    [
        f"{LIST_PATH}/latest",
        f"{LIST_PATH}/default",
        f"{LIST_PATH}/fallback",
        f"{LIST_PATH}/strategies/latest",
        f"{LIST_PATH}/strategies/default",
    ],
)
def test_latest_default_and_fallback_near_miss_routes_are_absent(path: str) -> None:
    client, factory = _client()

    response = client.get(path, params=_params())

    assert response.status_code in (404, 422)
    assert factory.calls == 0
