"""HTTP contract for the fixed 750/300 temporal cohort holdout."""

# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import copy

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
    HistoricalPrefixTemporalHoldoutResponse,
)

IMPORT_IDENTITY = "a" * 64
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/temporal-holdout"
)
PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "alias-strategy/v1%20beta/3/feature-cohorts/temporal-holdout"
)
QUERY = f"?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=2&criterion=M2_PLUS_SPECIAL"


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


def _source(count: int) -> HistoricalPrefixSuccessWindowSource:
    return build_success_source(
        (
            build_success_strategy(
                "alias-strategy",
                strategy_version="v1 beta",
                replicate=3,
                observations=build_success_observations(count),
            ),
        )
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


def test_temporal_holdout_route_is_one_load_get_only_and_deterministic(
    monkeypatch,
) -> None:
    _install_fast_assignments(monkeypatch)
    factory = _Factory(_source(1050))
    app = create_app(historical_prefix_success_window_source_reader_factory=factory)
    operation = app.openapi()["paths"][OPENAPI_PATH]["get"]
    assert operation["operationId"] == ("getHistoricalPrefixStrategyFeatureCohortTemporalHoldout")
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
    assert payload["evaluation_status"] == "COMPLETE"
    assert payload["split"]["split_method"] == ("FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION")
    assert payload["split"]["total_assignment_count"] == 1050
    assert payload["split"]["warmup_count"] == 0
    assert payload["split"]["discovery_count"] == 750
    assert payload["split"]["confirmation_count"] == 300
    assert payload["family_size"] == len(payload["comparisons"]) == 64
    assert payload["discovery"]["baseline"]["observation_count"] == 750
    assert payload["confirmation"]["baseline"]["observation_count"] == 300
    assert all(
        isinstance(item["discovery_diagnostic"]["raw_p_value"]["numerator"], str)
        and isinstance(
            item["confirmation_diagnostic"]["adjusted_p_value"]["denominator"],
            str,
        )
        for item in payload["comparisons"]
    )
    assert client.post(f"{PATH}{QUERY}").status_code == 405


def test_temporal_holdout_not_ready_has_no_partial_diagnostics(monkeypatch) -> None:
    _install_fast_assignments(monkeypatch)
    response = TestClient(
        create_app(historical_prefix_success_window_source_reader_factory=_Factory(_source(9)))
    ).get(f"{PATH}{QUERY}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_status"] == "NOT_READY_INSUFFICIENT_HISTORY"
    assert payload["split"]["total_assignment_count"] == 9
    assert payload["split"]["warmup_count"] == 9
    assert payload["split"]["discovery_count"] == 0
    assert payload["split"]["confirmation_count"] == 0
    assert payload["discovery"] is None
    assert payload["confirmation"] is None
    assert payload["comparisons"] == []


def test_temporal_holdout_validation_precedes_factory() -> None:
    factory = _Factory(_source(1))
    client = TestClient(create_app(historical_prefix_success_window_source_reader_factory=factory))
    for url in (
        f"{PATH}?import_identity_sha256=BAD&prefix_count=2&criterion=M3_PLUS",
        (f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=6&criterion=M3_PLUS"),
        (f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=2&criterion=BAD"),
        f"{PATH}{QUERY}&alpha=0.05",
    ):
        assert client.get(url).status_code == 422
    assert factory.calls == 0


def test_temporal_holdout_view_rejects_negative_counts_and_reversed_boundaries(
    monkeypatch,
) -> None:
    _install_fast_assignments(monkeypatch)
    payload = (
        TestClient(
            create_app(
                historical_prefix_success_window_source_reader_factory=_Factory(_source(1050))
            )
        )
        .get(f"{PATH}{QUERY}")
        .json()
    )

    negative_warmup = copy.deepcopy(payload)
    negative_warmup["split"]["total_assignment_count"] = 1049
    negative_warmup["split"]["warmup_count"] = -1
    with pytest.raises(ValidationError):
        HistoricalPrefixTemporalHoldoutResponse.model_validate(negative_warmup)

    below_required_total = copy.deepcopy(payload)
    below_required_total["split"]["total_assignment_count"] = 1049
    with pytest.raises(ValidationError):
        HistoricalPrefixTemporalHoldoutResponse.model_validate(below_required_total)

    reversed_boundaries = copy.deepcopy(payload)
    reversed_boundaries["split"]["discovery_first_target"] = payload["split"][
        "confirmation_first_target"
    ]
    reversed_boundaries["split"]["confirmation_first_target"] = payload["split"][
        "discovery_first_target"
    ]
    with pytest.raises(ValidationError):
        HistoricalPrefixTemporalHoldoutResponse.model_validate(reversed_boundaries)
