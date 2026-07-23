"""HTTP contract for exact feature-cohort inferential diagnostics."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.historical_prefix_success_windows import (
    HistoricalPrefixExactProbabilityView,
)

IMPORT_IDENTITY = "a" * 64
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics"
)
PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "alias-strategy/v1%20beta/3/feature-cohorts/diagnostics"
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
                observations=build_success_observations(2),
            ),
        )
    )


def test_diagnostics_route_is_lazy_one_load_get_only_and_deterministic() -> None:
    factory = _Factory(_source())
    app = create_app(
        historical_prefix_success_window_source_reader_factory=factory
    )
    operation = app.openapi()["paths"][OPENAPI_PATH]["get"]
    assert operation["operationId"] == (
        "getHistoricalPrefixStrategyFeatureCohortDiagnostics"
    )
    assert factory.calls == 0
    client = TestClient(app)

    first = client.get(f"{PATH}{QUERY}")
    second = client.get(f"{PATH}{QUERY}")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert factory.calls == factory.reader.calls == 2
    payload = first.json()
    assert payload["metadata"]["import_identity_sha256"] == IMPORT_IDENTITY
    assert payload["strategy"]["strategy_id"] == "alias-strategy"
    assert payload["strategy"]["strategy_version"] == "v1 beta"
    assert payload["strategy"]["replicate"] == 3
    assert payload["prefix_count"] == 2
    assert payload["criterion"]["criterion"] == "M2_PLUS_SPECIAL"
    assert payload["family_size"] == len(payload["diagnostics"]) == 64
    assert payload["raw_test_method"] == (
        "FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING"
    )
    assert payload["adjustment_method"] == "BENJAMINI_YEKUTIELI"
    assert [item["cohort_index"] for item in payload["diagnostics"]] == list(
        range(64)
    )
    assert all(
        isinstance(item["raw_p_value"]["numerator"], str)
        and isinstance(item["raw_p_value"]["denominator"], str)
        and isinstance(item["adjusted_p_value"]["numerator"], str)
        and isinstance(item["adjusted_p_value"]["denominator"], str)
        for item in payload["diagnostics"]
    )
    assert client.post(f"{PATH}{QUERY}").status_code == 405


def test_diagnostics_input_validation_precedes_factory() -> None:
    factory = _Factory(_source())
    client = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=factory
        )
    )
    for url in (
        f"{PATH}?import_identity_sha256=BAD&prefix_count=2&criterion=M3_PLUS",
        (
            f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}"
            "&prefix_count=6&criterion=M3_PLUS"
        ),
        (
            f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}"
            "&prefix_count=2&criterion=BAD"
        ),
        f"{PATH}{QUERY}&rank=p_value",
    ):
        assert client.get(url).status_code == 422
    assert factory.calls == 0


def test_diagnostics_missing_import_and_strategy_are_sanitized() -> None:
    missing_import = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(None)
        )
    ).get(f"{PATH}{QUERY}")
    assert missing_import.status_code == 404
    assert missing_import.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND"
    )

    missing_strategy = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(_source())
        )
    ).get(
        "/api/v1/historical-prefix-success-windows/strategies/"
        f"missing/v1/1/feature-cohorts/diagnostics{QUERY}"
    )
    assert missing_strategy.status_code == 404
    assert missing_strategy.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND"
    )


def test_probability_view_preserves_big_integers_and_rejects_noncanonical_values() -> None:
    above_javascript_safe_integer = "900719925474099312345678901234567890"
    view = HistoricalPrefixExactProbabilityView(
        numerator=above_javascript_safe_integer,
        denominator=f"{above_javascript_safe_integer}1",
    )
    assert view.numerator == above_javascript_safe_integer
    assert int(view.numerator) > 2**53

    for payload in (
        {"numerator": "01", "denominator": "2"},
        {"numerator": "1", "denominator": "0"},
        {"numerator": "3", "denominator": "2"},
        {"numerator": "2", "denominator": "4"},
        {"numerator": 1, "denominator": 2},
    ):
        with pytest.raises(ValidationError):
            HistoricalPrefixExactProbabilityView.model_validate(payload)
