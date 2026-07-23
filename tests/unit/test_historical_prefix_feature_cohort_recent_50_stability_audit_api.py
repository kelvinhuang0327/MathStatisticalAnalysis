"""HTTP contract for the fixed recent-50 feature-cohort stability audit."""

# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportIndexIssue=false

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
    HistoricalPrefixRecentStabilityAuditResponse,
)

IMPORT_IDENTITY = "a" * 64
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
    "recent-50-stability-audit"
)
PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "alias-strategy/v1%20beta/3/feature-cohorts/recent-50-stability-audit"
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
    relations = tuple(HistoricalPrefixRateRelation)
    monkeypatch.setattr(
        module,
        "_snapshot_feature_key",
        lambda **kwargs: HistoricalPrefixFeatureRelationTriple(
            long_to_medium=relations[len(kwargs["prior_observations"]) % 4],
            medium_to_short=HistoricalPrefixRateRelation.EQUAL,
            long_to_short=HistoricalPrefixRateRelation.UNAVAILABLE,
        ),
    )
    monkeypatch.setattr(
        module,
        "_current_target_succeeded",
        lambda **kwargs: kwargs["current_target"].target.draw_number % 3 == 0,
    )


def _payload(monkeypatch, count: int = 1050) -> dict[str, object]:
    _install_fast_assignments(monkeypatch)
    response = TestClient(
        create_app(
            historical_prefix_success_window_source_reader_factory=_Factory(_source(count))
        )
    ).get(f"{PATH}{QUERY}")
    assert response.status_code == 200
    return response.json()


def test_recent_50_audit_route_is_one_load_get_only_and_byte_deterministic(
    monkeypatch,
) -> None:
    _install_fast_assignments(monkeypatch)
    factory = _Factory(_source(1050))
    app = create_app(historical_prefix_success_window_source_reader_factory=factory)
    operation = app.openapi()["paths"][OPENAPI_PATH]["get"]
    assert operation["operationId"] == (
        "getHistoricalPrefixStrategyFeatureCohortRecent50StabilityAudit"
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
    assert payload["audit_status"] == "COMPLETE"
    assert payload["split"]["source_temporal_split_method"] == (
        "FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION"
    )
    assert payload["split"]["audit_split_method"] == (
        "FIXED_CONFIRMATION_FIRST_250_REFERENCE_LAST_50_RECENT"
    )
    assert (
        payload["split"]["total_assignment_count"],
        payload["split"]["warmup_count"],
        payload["split"]["discovery_count"],
        payload["split"]["confirmation_count"],
        payload["split"]["reference_count"],
        payload["split"]["recent_count"],
    ) == (1050, 0, 750, 300, 250, 50)
    assert payload["reference"]["baseline"]["observation_count"] == 250
    assert payload["recent"]["baseline"]["observation_count"] == 50
    assert len(payload["reference"]["diagnostics"]) == 64
    assert len(payload["recent"]["diagnostics"]) == 64
    assert len(payload["comparisons"]) == 64
    assert all(
        comparison["cohort_index"] == index
        and isinstance(
            comparison["reference_diagnostic"]["raw_p_value"]["numerator"], str
        )
        and isinstance(
            comparison["recent_diagnostic"]["adjusted_p_value"]["denominator"], str
        )
        for index, comparison in enumerate(payload["comparisons"])
    )
    assert client.post(f"{PATH}{QUERY}").status_code == 405


def test_recent_50_audit_not_ready_has_no_partial_diagnostics(monkeypatch) -> None:
    payload = _payload(monkeypatch, 1049)

    assert payload["audit_status"] == "NOT_READY_INSUFFICIENT_HISTORY"
    assert (
        payload["split"]["total_assignment_count"],
        payload["split"]["warmup_count"],
        payload["split"]["discovery_count"],
        payload["split"]["confirmation_count"],
        payload["split"]["reference_count"],
        payload["split"]["recent_count"],
    ) == (1049, 1049, 0, 0, 0, 0)
    assert payload["reference"] is None
    assert payload["recent"] is None
    assert payload["comparisons"] == []


def test_recent_50_audit_validation_precedes_factory() -> None:
    factory = _Factory(_source(1))
    client = TestClient(
        create_app(historical_prefix_success_window_source_reader_factory=factory)
    )
    for url in (
        f"{PATH}?import_identity_sha256=BAD&prefix_count=2&criterion=M3_PLUS",
        f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=6&criterion=M3_PLUS",
        f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=2&criterion=BAD",
        f"{PATH}{QUERY}&reference_count=249",
    ):
        assert client.get(url).status_code == 422
    assert factory.calls == 0


def test_recent_50_audit_view_rejects_overlap_reversed_effect_and_family_pooling(
    monkeypatch,
) -> None:
    payload = _payload(monkeypatch)

    overlapping = copy.deepcopy(payload)
    overlapping["split"]["recent_first_target"] = overlapping["split"][
        "reference_last_target"
    ]
    with pytest.raises(ValidationError):
        HistoricalPrefixRecentStabilityAuditResponse.model_validate(overlapping)

    reversed_effect = copy.deepcopy(payload)
    reversed_effect["comparisons"][0]["effect_change"]["numerator"] += 1
    with pytest.raises(ValidationError):
        HistoricalPrefixRecentStabilityAuditResponse.model_validate(reversed_effect)

    missing_recent = copy.deepcopy(payload)
    missing_recent["recent"] = None
    with pytest.raises(ValidationError):
        HistoricalPrefixRecentStabilityAuditResponse.model_validate(missing_recent)

    pooled_family = copy.deepcopy(payload)
    pooled_family["family_size"] = 128
    with pytest.raises(ValidationError):
        HistoricalPrefixRecentStabilityAuditResponse.model_validate(pooled_family)
