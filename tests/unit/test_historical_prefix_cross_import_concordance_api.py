"""HTTP contract for exact pairwise cross-import temporal concordance."""

# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import copy
import dataclasses

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
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
from lottolab.interfaces.api.historical_prefix_success_windows import (
    HistoricalPrefixCrossImportConcordanceResponse,
)

LEFT_IMPORT = "a" * 64
RIGHT_IMPORT = "b" * 64
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
    "cross-import-concordance"
)
PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "alias-strategy/v1%20beta/3/feature-cohorts/cross-import-concordance"
)
QUERY = (
    f"?left_import_identity_sha256={LEFT_IMPORT}"
    f"&right_import_identity_sha256={RIGHT_IMPORT}"
    "&prefix_count=2&criterion=M2_PLUS_SPECIAL"
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
        lambda **kwargs: HistoricalPrefixFeatureRelationTriple(
            long_to_medium=(
                HistoricalPrefixRateRelation.HIGHER
                if len(kwargs["prior_observations"]) % 2 == 0
                else HistoricalPrefixRateRelation.LOWER
            ),
            medium_to_short=HistoricalPrefixRateRelation.EQUAL,
            long_to_short=HistoricalPrefixRateRelation.UNAVAILABLE,
        ),
    )
    monkeypatch.setattr(
        module,
        "_current_target_succeeded",
        lambda **kwargs: kwargs["current_target"].target.draw_number % 3 == 0,
    )


def test_route_is_get_only_one_reader_two_ordered_loads_and_deterministic(
    monkeypatch,
) -> None:
    _install_fast_assignments(monkeypatch)
    factory = _Factory(
        {
            LEFT_IMPORT: _source(LEFT_IMPORT, 1050),
            RIGHT_IMPORT: _source(RIGHT_IMPORT, 1050),
        }
    )
    app = create_app(historical_prefix_success_window_source_reader_factory=factory)
    operation = app.openapi()["paths"][OPENAPI_PATH]["get"]
    assert operation["operationId"] == "getHistoricalPrefixStrategyCrossImportConcordance"
    assert factory.calls == 0
    client = TestClient(app)

    first = client.get(f"{PATH}{QUERY}")
    second = client.get(f"{PATH}{QUERY}")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert factory.calls == 2
    assert factory.reader.calls == [
        LEFT_IMPORT,
        RIGHT_IMPORT,
        LEFT_IMPORT,
        RIGHT_IMPORT,
    ]
    payload = first.json()
    assert payload["metadata"]["left"]["import_identity_sha256"] == LEFT_IMPORT
    assert payload["metadata"]["right"]["import_identity_sha256"] == RIGHT_IMPORT
    assert payload["metadata"]["same_dataset_sha256"] is True
    assert payload["metadata"]["same_source_artifact_sha256"] is True
    assert payload["strategy"]["strategy_id"] == "alias-strategy"
    assert payload["pair_status"] == "COMPLETE"
    assert payload["left_holdout_status"] == payload["right_holdout_status"] == "COMPLETE"
    assert payload["confirmation_target_overlap"] == {
        "left_confirmation_target_count": 300,
        "right_confirmation_target_count": 300,
        "overlap_count": 300,
        "left_only_count": 0,
        "right_only_count": 0,
        "relation": "IDENTICAL",
    }
    assert len(payload["comparisons"]) == 64
    assert all(
        isinstance(
            comparison["left_confirmation_diagnostic"]["raw_p_value"]["numerator"],
            str,
        )
        and isinstance(
            comparison["right_confirmation_diagnostic"]["adjusted_p_value"][
                "denominator"
            ],
            str,
        )
        for comparison in payload["comparisons"]
    )
    assert client.post(f"{PATH}{QUERY}").status_code == 405


def test_not_ready_pair_has_null_overlap_and_empty_comparisons(monkeypatch) -> None:
    _install_fast_assignments(monkeypatch)
    response = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(
                {
                    LEFT_IMPORT: _source(LEFT_IMPORT, 9),
                    RIGHT_IMPORT: _source(RIGHT_IMPORT, 1050),
                }
            )
        )
    ).get(f"{PATH}{QUERY}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pair_status"] == "LEFT_NOT_READY"
    assert payload["confirmation_target_overlap"] is None
    assert payload["comparisons"] == []


def test_validation_and_identical_imports_precede_factory() -> None:
    factory = _Factory({})
    client = TestClient(create_app(historical_prefix_success_window_source_reader_factory=factory))
    for url in (
        f"{PATH}?left_import_identity_sha256=BAD&right_import_identity_sha256={RIGHT_IMPORT}"
        "&prefix_count=2&criterion=M3_PLUS",
        f"{PATH}?left_import_identity_sha256={LEFT_IMPORT}"
        f"&right_import_identity_sha256={LEFT_IMPORT}&prefix_count=2&criterion=M3_PLUS",
        f"{PATH}{QUERY}&combined_p_value=true",
    ):
        assert client.get(url).status_code == 422
    assert factory.calls == 0
    assert factory.reader.calls == []


@pytest.mark.parametrize("missing_import", [LEFT_IMPORT, RIGHT_IMPORT])
def test_either_missing_import_is_sanitized_404(missing_import: str) -> None:
    sources: dict[str, HistoricalPrefixSuccessWindowSource | None] = {
        LEFT_IMPORT: _source(LEFT_IMPORT, 1),
        RIGHT_IMPORT: _source(RIGHT_IMPORT, 1),
    }
    sources[missing_import] = None
    response = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(sources)
        )
    ).get(f"{PATH}{QUERY}")
    assert response.status_code == 404
    assert response.json()["error_code"] == "HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND"


def test_view_rejects_overlap_order_identity_and_numeric_probabilities(
    monkeypatch,
) -> None:
    _install_fast_assignments(monkeypatch)
    payload = (
        TestClient(
            create_app(
                historical_prefix_success_window_source_reader_factory=_Factory(
                    {
                        LEFT_IMPORT: _source(LEFT_IMPORT, 1050),
                        RIGHT_IMPORT: _source(RIGHT_IMPORT, 1050),
                    }
                )
            )
        )
        .get(f"{PATH}{QUERY}")
        .json()
    )

    bad_overlap = copy.deepcopy(payload)
    bad_overlap["confirmation_target_overlap"]["overlap_count"] = 299
    with pytest.raises(ValidationError):
        HistoricalPrefixCrossImportConcordanceResponse.model_validate(bad_overlap)

    wrong_order = copy.deepcopy(payload)
    wrong_order["comparisons"][0], wrong_order["comparisons"][1] = (
        wrong_order["comparisons"][1],
        wrong_order["comparisons"][0],
    )
    with pytest.raises(ValidationError):
        HistoricalPrefixCrossImportConcordanceResponse.model_validate(wrong_order)

    identity_mismatch = copy.deepcopy(payload)
    identity_mismatch["metadata"]["right"]["import_identity_sha256"] = LEFT_IMPORT
    with pytest.raises(ValidationError):
        HistoricalPrefixCrossImportConcordanceResponse.model_validate(identity_mismatch)

    numeric_probability = copy.deepcopy(payload)
    numeric_probability["comparisons"][0]["left_confirmation_diagnostic"]["raw_p_value"][
        "numerator"
    ] = 1
    with pytest.raises(ValidationError):
        HistoricalPrefixCrossImportConcordanceResponse.model_validate(numeric_probability)
