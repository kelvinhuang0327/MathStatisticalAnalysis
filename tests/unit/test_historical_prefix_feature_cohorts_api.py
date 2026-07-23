"""HTTP contract tests for walk-forward Historical Prefix feature cohorts."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

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
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts"
)
PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "alias-strategy/v1%20beta/3/feature-cohorts"
)
QUERY = (
    f"?import_identity_sha256={IMPORT_IDENTITY}"
    "&prefix_count=2&criterion=M2_PLUS_SPECIAL"
)


class _Reader:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.source = source
        self.calls = 0

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        assert import_identity_sha256 == IMPORT_IDENTITY
        self.calls += 1
        return self.source


class _Factory:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.reader = _Reader(source)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _source() -> HistoricalPrefixSuccessWindowSource:
    return build_success_source(
        (
            build_success_strategy(
                "alias-strategy",
                strategy_version="v1 beta",
                replicate=3,
                effective_strategy_id="base",
                alias_of_strategy_id="base",
                observations=build_success_observations(
                    2,
                    outcome_factory=lambda observation, position: (
                        (2, True)
                        if observation == 0 and position == 1
                        else (0, False)
                    ),
                ),
            ),
        )
    )


def test_feature_cohort_route_is_lazy_one_load_get_only_and_byte_deterministic() -> None:
    factory = _Factory(_source())
    app = create_app(
        historical_prefix_success_window_source_reader_factory=factory
    )
    assert factory.calls == 0
    operation = app.openapi()["paths"][OPENAPI_PATH]["get"]
    assert operation["operationId"] == "getHistoricalPrefixStrategyFeatureCohorts"
    assert factory.calls == 0
    client = TestClient(app)

    first = client.get(f"{PATH}{QUERY}")
    second = client.get(f"{PATH}{QUERY}")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert factory.calls == 2
    assert factory.reader.calls == 2
    payload = first.json()
    assert payload["metadata"]["import_identity_sha256"] == IMPORT_IDENTITY
    assert payload["strategy"]["strategy_id"] == "alias-strategy"
    assert payload["strategy"]["effective_strategy_id"] == "base"
    assert payload["strategy"]["alias_of_strategy_id"] == "base"
    assert payload["strategy"]["replicate"] == 3
    assert payload["prefix_count"] == 2
    assert payload["criterion"]["criterion"] == "M2_PLUS_SPECIAL"
    assert payload["baseline"] == {
        "observation_count": 2,
        "success_count": 1,
        "failure_count": 1,
        "success_rate": {
            "numerator": 1,
            "denominator": 2,
            "available": True,
        },
    }
    assert payload["cohort_count"] == len(payload["cohorts"]) == 64
    assert payload["cohorts"][-1]["feature_key"] == {
        "long_to_medium": "UNAVAILABLE",
        "medium_to_short": "UNAVAILABLE",
        "long_to_short": "UNAVAILABLE",
    }
    assert payload["cohorts"][-1]["observation_count"] == 2
    assert client.post(f"{PATH}{QUERY}").status_code == 405


def test_feature_cohort_input_validation_runs_before_factory() -> None:
    factory = _Factory(_source())
    client = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=factory
        )
    )

    for url in (
        f"{PATH}?import_identity_sha256=BAD&prefix_count=2&criterion=M3_PLUS",
        f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=6&criterion=M3_PLUS",
        f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=2&criterion=BAD",
        (
            "/api/v1/historical-prefix-success-windows/strategies/"
            f"strategy/v1/0/feature-cohorts{QUERY}"
        ),
    ):
        response = client.get(url)
        assert response.status_code == 422
    assert factory.calls == 0


def test_feature_cohort_missing_and_unavailable_fail_with_sanitized_errors() -> None:
    missing_import = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(None)
        )
    ).get(f"{PATH}{QUERY}")
    assert missing_import.status_code == 404
    assert missing_import.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND"
    )

    source = _source()
    missing_strategy = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(source)
        )
    ).get(
        "/api/v1/historical-prefix-success-windows/strategies/"
        f"missing/v1/1/feature-cohorts{QUERY}"
    )
    assert missing_strategy.status_code == 404
    assert missing_strategy.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND"
    )

    malformed = build_success_source(
        (
            build_success_strategy(
                "alias-strategy",
                strategy_version="v1 beta",
                replicate=3,
                observations=(
                    build_success_observations(1)[0],
                    build_success_observations(1)[0],
                ),
            ),
        )
    )
    unavailable = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(
                malformed
            )
        )
    ).get(f"{PATH}{QUERY}")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "error_code": "HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE",
        "message": "Historical prefix success windows are unavailable.",
    }


def test_feature_cohort_rejects_unexpected_query_without_loading_source() -> None:
    factory = _Factory(_source())
    response = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=factory
        )
    ).get(f"{PATH}{QUERY}&sort=success_rate")

    assert response.status_code == 422
    assert factory.calls == 0
    assert response.json()["fields"] == [
        {"location": "query.sort", "type": "extra_forbidden"}
    ]
