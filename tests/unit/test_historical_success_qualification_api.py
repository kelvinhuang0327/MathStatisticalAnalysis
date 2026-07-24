"""API tests for Historical Success research qualification."""

# pyright: reportUnusedFunction=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownLambdaType=false

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

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

IMPORTS = ("a" * 64, "b" * 64)
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/research-qualification"
)
REQUEST_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "strategy-a/v1/1/research-qualification"
)


class _Reader:
    def __init__(
        self,
        sources: Mapping[str, HistoricalPrefixSuccessWindowSource | None],
    ) -> None:
        self.sources = sources
        self.calls: list[str] = []

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        self.calls.append(import_identity_sha256)
        return self.sources.get(import_identity_sha256)


class _Factory:
    def __init__(
        self,
        sources: Mapping[str, HistoricalPrefixSuccessWindowSource | None],
    ) -> None:
        self.reader = _Reader(sources)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _source(
    import_identity: str,
    index: int,
    *,
    strategy_id: str = "strategy-a",
) -> HistoricalPrefixSuccessWindowSource:
    source = build_success_source(
        (
            build_success_strategy(
                strategy_id,
                observations=build_success_observations(
                    1050,
                    draw_number_offset=1 + (index * 2000),
                ),
            ),
        ),
        import_identity_sha256=import_identity,
    )
    return dataclasses.replace(
        source,
        metadata=dataclasses.replace(
            source.metadata,
            run_id=f"run-{index}",
            dataset_sha256="ef"[index] * 64,
            source_artifact_sha256="34"[index] * 64,
        ),
    )


def _params(
    imports: tuple[str, ...] = IMPORTS,
    **extra: object,
) -> list[tuple[str, object]]:
    values: list[tuple[str, object]] = [
        *(("import_identity_sha256", identity) for identity in imports),
        ("prefix_count", 1),
        ("criterion", "M3_PLUS"),
    ]
    values.extend(extra.items())
    return values


def _client(
    sources: Mapping[str, HistoricalPrefixSuccessWindowSource | None],
) -> tuple[TestClient, _Factory]:
    factory = _Factory(sources)
    return (
        TestClient(
            create_app(
                historical_prefix_success_window_source_reader_factory=factory
            )
        ),
        factory,
    )


@pytest.fixture(autouse=True)
def _fast_assignments(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_openapi_exposes_exact_one_get_route_without_invoking_factory() -> None:
    factory = _Factory({})
    app = create_app(
        historical_prefix_success_window_source_reader_factory=factory
    )

    operation = app.openapi()["paths"][OPENAPI_PATH]

    assert set(operation) == {"get"}
    assert operation["get"]["operationId"] == (
        "getHistoricalPrefixStrategyResearchQualification"
    )
    assert factory.calls == 0
    assert factory.reader.calls == []


def test_valid_request_preserves_order_and_returns_deterministic_projection() -> None:
    client, factory = _client(
        {
            identity: _source(identity, index)
            for index, identity in enumerate(IMPORTS)
        }
    )

    first = client.get(REQUEST_PATH, params=_params())
    second = client.get(REQUEST_PATH, params=_params())

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert factory.calls == 2
    assert factory.reader.calls == [*IMPORTS, *IMPORTS]
    payload = first.json()
    assert payload["identity"] == {
        "strategy_id": "strategy-a",
        "strategy_version": "v1",
        "replicate": 1,
        "prefix_count": 1,
        "criterion": "M3_PLUS",
    }
    assert [
        item["import_identity_sha256"]
        for item in payload["ordered_import_evidence"]
    ] == list(IMPORTS)
    assert payload["expected_pair_count"] == payload["actual_pair_count"] == 1
    assert payload["pair_evidence"] == [
        {
            "left_import_index": 0,
            "right_import_index": 1,
            "pair_status": "COMPLETE",
            "same_dataset_sha256": False,
            "same_source_artifact_sha256": False,
            "confirmation_overlap_relation": "DISJOINT",
            "r1_comparable": True,
        }
    ]
    assert payload["primary_status"] == "EVIDENCE_INCOMPLETE"
    assert payload["informational_flags"][0] == "CROSS_IMPORT_UNRESOLVED"
    assert payload["random_baseline_caveat"] is None
    assert "cohort_census" not in payload
    assert "rank" not in payload
    assert "score" not in payload
    assert "production_eligible" not in payload


@pytest.mark.parametrize(
    "params",
    [
        _params((IMPORTS[0],)),
        _params((IMPORTS[0], IMPORTS[0])),
        _params(("A" * 64, IMPORTS[1])),
        _params((*IMPORTS, "c" * 64, "d" * 64, "e" * 64)),
        _params(extra_query="unexpected"),
    ],
)
def test_invalid_identity_duplicate_cardinality_or_extra_query_is_422_before_factory(
    params: list[tuple[str, object]],
) -> None:
    client, factory = _client({})

    response = client.get(REQUEST_PATH, params=params)

    assert response.status_code == 422
    assert factory.calls == 0
    assert factory.reader.calls == []


def test_missing_import_or_strategy_is_404() -> None:
    missing_import_client, missing_import_factory = _client(
        {IMPORTS[0]: _source(IMPORTS[0], 0)}
    )
    missing_strategy_client, missing_strategy_factory = _client(
        {
            identity: _source(identity, index, strategy_id="other")
            for index, identity in enumerate(IMPORTS)
        }
    )

    missing_import = missing_import_client.get(REQUEST_PATH, params=_params())
    missing_strategy = missing_strategy_client.get(REQUEST_PATH, params=_params())

    assert missing_import.status_code == 404
    assert missing_import_factory.calls == 1
    assert missing_import_factory.reader.calls == list(IMPORTS)
    assert missing_strategy.status_code == 404
    assert missing_strategy_factory.calls == 1
    assert missing_strategy_factory.reader.calls == list(IMPORTS)


def test_inconsistent_or_unavailable_composition_is_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(
        module.EvaluateHistoricalPrefixSuccessWindows,
        "get_research_qualification",
        unavailable,
    )
    client, _ = _client({})

    response = client.get(REQUEST_PATH, params=_params())

    assert response.status_code == 503
    assert "sensitive internal detail" not in response.text
