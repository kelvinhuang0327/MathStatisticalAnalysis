"""Fixed confirmation first-250/reference last-50/recent audit contracts."""

# pyright: reportPrivateUsage=false
# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

import lottolab.application.use_cases.evaluate_historical_prefix_success_windows as module
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixFeatureRelationTriple,
    HistoricalPrefixRateRelation,
    HistoricalPrefixRecentStabilityAuditStatus,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)

IMPORT_IDENTITY = "a" * 64


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


def _key(index: int) -> HistoricalPrefixFeatureRelationTriple:
    relations = tuple(HistoricalPrefixRateRelation)
    return HistoricalPrefixFeatureRelationTriple(
        long_to_medium=relations[(index // 16) % 4],
        medium_to_short=relations[(index // 4) % 4],
        long_to_short=relations[index % 4],
    )


def _evaluate(
    source: HistoricalPrefixSuccessWindowSource,
) -> tuple[module.HistoricalPrefixRecentStabilityAuditResult, _Factory]:
    factory = _Factory(source)
    result = EvaluateHistoricalPrefixSuccessWindows(
        factory
    ).get_feature_cohort_recent_50_stability_audit(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )
    return result, factory


def test_complete_audit_reuses_one_assignment_sequence_and_exact_confirmation_slices(
    monkeypatch,
) -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(1100)),)
    )
    snapshot_prior_counts: list[int] = []
    assignment_calls = 0
    temporal_calls = 0
    diagnostic_baselines: list[int] = []
    original_assignments = module._build_walk_forward_assignments
    original_temporal = module._temporal_holdout
    original_diagnostics = module._feature_cohort_diagnostics

    def snapshot_spy(**kwargs):
        prior_count = len(kwargs["prior_observations"])
        snapshot_prior_counts.append(prior_count)
        return _key(prior_count % 64)

    def assignment_spy(**kwargs):
        nonlocal assignment_calls
        assignment_calls += 1
        return original_assignments(**kwargs)

    def temporal_spy(**kwargs):
        nonlocal temporal_calls
        temporal_calls += 1
        assert kwargs["assignments"] is not None
        return original_temporal(**kwargs)

    def diagnostic_spy(result):
        diagnostic_baselines.append(result.baseline.observation_count)
        return original_diagnostics(result)

    monkeypatch.setattr(module, "_snapshot_feature_key", snapshot_spy)
    monkeypatch.setattr(
        module,
        "_current_target_succeeded",
        lambda **kwargs: kwargs["current_target"].target.draw_number % 3 == 0,
    )
    monkeypatch.setattr(module, "_build_walk_forward_assignments", assignment_spy)
    monkeypatch.setattr(module, "_temporal_holdout", temporal_spy)
    monkeypatch.setattr(module, "_feature_cohort_diagnostics", diagnostic_spy)

    result, factory = _evaluate(source)

    assert factory.calls == factory.reader.calls == assignment_calls == temporal_calls == 1
    assert snapshot_prior_counts == list(range(1100))
    assert diagnostic_baselines == [750, 300, 250, 50]
    assert result.audit_status is HistoricalPrefixRecentStabilityAuditStatus.COMPLETE
    assert result.split.source_temporal_split_method == (
        "FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION"
    )
    assert result.split.audit_split_method == (
        "FIXED_CONFIRMATION_FIRST_250_REFERENCE_LAST_50_RECENT"
    )
    assert (
        result.split.total_assignment_count,
        result.split.warmup_count,
        result.split.discovery_count,
        result.split.confirmation_count,
        result.split.reference_count,
        result.split.recent_count,
    ) == (1100, 50, 750, 300, 250, 50)
    assert result.split.discovery_first_target is not None
    assert result.split.discovery_last_target is not None
    assert result.split.confirmation_first_target is not None
    assert result.split.confirmation_last_target is not None
    assert result.split.reference_first_target is not None
    assert result.split.reference_last_target is not None
    assert result.split.recent_first_target is not None
    assert result.split.recent_last_target is not None
    assert (
        result.split.discovery_first_target.draw_number,
        result.split.discovery_last_target.draw_number,
        result.split.confirmation_first_target.draw_number,
        result.split.reference_first_target.draw_number,
        result.split.reference_last_target.draw_number,
        result.split.recent_first_target.draw_number,
        result.split.recent_last_target.draw_number,
        result.split.confirmation_last_target.draw_number,
    ) == (51, 800, 801, 801, 1050, 1051, 1100, 1100)
    assert result.reference is not None
    assert result.recent is not None
    assert result.reference.baseline.observation_count == 250
    assert result.recent.baseline.observation_count == 50
    assert result.family_size == len(result.reference.diagnostics) == 64
    assert result.family_size == len(result.recent.diagnostics) == 64
    assert result.family_size == len(result.comparisons) == 64
    assert [comparison.cohort_index for comparison in result.comparisons] == list(range(64))
    assert all(
        comparison.feature_key
        == comparison.reference_diagnostic.feature_key
        == comparison.recent_diagnostic.feature_key
        for comparison in result.comparisons
    )
    assert sum(
        diagnostic.cohort_counts.observation_count
        for diagnostic in result.reference.diagnostics
    ) == 250
    assert sum(
        diagnostic.cohort_counts.observation_count
        for diagnostic in result.recent.diagnostics
    ) == 50


def test_audit_1049_assignments_is_not_ready_without_partial_diagnostics(
    monkeypatch,
) -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(1049)),)
    )
    monkeypatch.setattr(
        module,
        "_snapshot_feature_key",
        lambda **kwargs: _key(len(kwargs["prior_observations"]) % 64),
    )
    monkeypatch.setattr(module, "_current_target_succeeded", lambda **_kwargs: False)

    result, factory = _evaluate(source)

    assert factory.calls == factory.reader.calls == 1
    assert result.audit_status is (
        HistoricalPrefixRecentStabilityAuditStatus.NOT_READY_INSUFFICIENT_HISTORY
    )
    assert (
        result.split.total_assignment_count,
        result.split.warmup_count,
        result.split.discovery_count,
        result.split.confirmation_count,
        result.split.reference_count,
        result.split.recent_count,
    ) == (1049, 1049, 0, 0, 0, 0)
    assert result.reference is result.recent is None
    assert result.comparisons == ()
    assert all(
        boundary is None
        for boundary in (
            result.split.discovery_first_target,
            result.split.discovery_last_target,
            result.split.confirmation_first_target,
            result.split.confirmation_last_target,
            result.split.reference_first_target,
            result.split.reference_last_target,
            result.split.recent_first_target,
            result.split.recent_last_target,
        )
    )
