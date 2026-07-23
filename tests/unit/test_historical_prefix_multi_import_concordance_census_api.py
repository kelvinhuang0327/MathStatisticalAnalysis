"""HTTP contract for the ordered multi-import confirmation census."""

# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import dataclasses

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

import lottolab.application.use_cases.evaluate_historical_prefix_success_windows as module
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixFeatureRelationTriple,
    HistoricalPrefixRateRelation,
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.interfaces.api.app import create_app

IMPORTS = tuple(character * 64 for character in "abcd")
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
    "multi-import-concordance-census"
)
PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "alias-strategy/v1%20beta/3/feature-cohorts/multi-import-concordance-census"
)


class _Reader:
    def __init__(self, sources: dict[str, HistoricalPrefixSuccessWindowSource | None]) -> None:
        self.sources = sources
        self.calls: list[str] = []

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        self.calls.append(import_identity_sha256)
        return self.sources.get(import_identity_sha256)


class _Factory:
    def __init__(self, sources: dict[str, HistoricalPrefixSuccessWindowSource | None]) -> None:
        self.reader = _Reader(sources)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _source(import_identity: str, count: int) -> HistoricalPrefixSuccessWindowSource:
    source = build_success_source(
        (
            build_success_strategy(
                "alias-strategy",
                strategy_version="v1 beta",
                replicate=3,
                observations=build_success_observations(count),
            ),
        ),
        import_identity_sha256=import_identity,
    )
    return dataclasses.replace(
        source,
        metadata=dataclasses.replace(
            source.metadata,
            run_id=f"run-{import_identity[0]}",
        ),
    )


def _install_fast_assignments(monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "_snapshot_feature_key",
        lambda **_kwargs: HistoricalPrefixFeatureRelationTriple(
            long_to_medium=HistoricalPrefixRateRelation.HIGHER,
            medium_to_short=HistoricalPrefixRateRelation.EQUAL,
            long_to_short=HistoricalPrefixRateRelation.LOWER,
        ),
    )
    monkeypatch.setattr(
        module,
        "_current_target_succeeded",
        lambda **kwargs: kwargs["current_target"].target.draw_number % 3 == 0,
    )


def _query(identities: tuple[str, ...]) -> str:
    repeated = "&".join(
        f"import_identity_sha256={identity}" for identity in identities
    )
    return f"?{repeated}&prefix_count=2&criterion=M2_PLUS_SPECIAL"


def test_openapi_pins_repeated_ordered_sha_array_contract() -> None:
    operation = create_app().openapi()["paths"][OPENAPI_PATH]["get"]
    parameter = next(
        item
        for item in operation["parameters"]
        if item["name"] == "import_identity_sha256"
    )

    assert operation["operationId"] == (
        "getHistoricalPrefixStrategyMultiImportConcordanceCensus"
    )
    assert parameter["in"] == "query"
    assert parameter["required"] is True
    assert parameter["schema"]["type"] == "array"
    assert parameter["schema"]["minItems"] == 2
    assert parameter["schema"]["maxItems"] == 4
    assert parameter["schema"]["items"] == {
        "type": "string",
        "pattern": "^[0-9a-f]{64}$",
    }


@pytest.mark.parametrize(("import_count", "pair_count"), [(2, 1), (3, 3), (4, 6)])
def test_route_preserves_import_and_pair_order_with_exact_probabilities(
    monkeypatch,
    import_count: int,
    pair_count: int,
) -> None:
    _install_fast_assignments(monkeypatch)
    identities = IMPORTS[:import_count]
    factory = _Factory(
        {identity: _source(identity, 1050) for identity in identities}
    )
    client = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=factory
        )
    )

    response = client.get(f"{PATH}{_query(identities)}")

    assert response.status_code == 200
    assert factory.calls == 1
    assert factory.reader.calls == list(identities)
    payload = response.json()
    assert [
        item["metadata"]["import_identity_sha256"] for item in payload["imports"]
    ] == list(identities)
    assert payload["census_status"] == "COMPLETE"
    assert payload["pair_count"] == len(payload["pairs"]) == pair_count
    assert [
        (pair["left_import_index"], pair["right_import_index"])
        for pair in payload["pairs"]
    ] == [
        (left, right)
        for left in range(import_count)
        for right in range(left + 1, import_count)
    ]
    assert payload["cohort_census_count"] == len(payload["cohort_census"]) == 64
    assert all(
        [
            (item["import_index"], item["import_identity_sha256"])
            for item in row["confirmation_diagnostics"]
        ]
        == list(enumerate(identities))
        and sum(
            row[key]
            for key in (
                "higher_count",
                "equal_count",
                "lower_count",
                "unavailable_count",
            )
        )
        == import_count
        and all(
            isinstance(
                item["diagnostic"]["raw_p_value"]["numerator"],
                str,
            )
            and isinstance(
                item["diagnostic"]["adjusted_p_value"]["denominator"],
                str,
            )
            for item in row["confirmation_diagnostics"]
        )
        for row in payload["cohort_census"]
    )
    assert client.post(f"{PATH}{_query(identities)}").status_code == 405


@pytest.mark.parametrize(
    "query",
    [
        _query((IMPORTS[0],)),
        _query((*IMPORTS, "e" * 64)),
        _query((IMPORTS[0], IMPORTS[0])),
        _query(("A" * 64, IMPORTS[1])),
        f"{_query(IMPORTS[:2])}&combined_p_value=true",
    ],
)
def test_all_query_validation_precedes_factory(query: str) -> None:
    factory = _Factory({})
    response = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=factory
        )
    ).get(f"{PATH}{query}")

    assert response.status_code == 422
    assert factory.calls == 0
    assert factory.reader.calls == []
