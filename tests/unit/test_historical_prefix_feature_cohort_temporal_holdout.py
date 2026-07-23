"""Fixed 750/300 temporal holdout application contract tests."""

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
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixTemporalHoldoutRelationship,
    HistoricalPrefixTemporalHoldoutStatus,
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


def _key(relation: HistoricalPrefixRateRelation) -> HistoricalPrefixFeatureRelationTriple:
    return HistoricalPrefixFeatureRelationTriple(
        long_to_medium=relation,
        medium_to_short=relation,
        long_to_short=relation,
    )


def _evaluate(
    source: HistoricalPrefixSuccessWindowSource,
) -> tuple[module.HistoricalPrefixTemporalHoldoutResult, _Factory]:
    factory = _Factory(source)
    result = EvaluateHistoricalPrefixSuccessWindows(factory).get_feature_cohort_temporal_holdout(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )
    return result, factory


def test_complete_holdout_builds_once_keeps_warmup_context_and_splits_exactly(
    monkeypatch,
) -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(1100)),)
    )
    snapshot_prior_counts: list[int] = []
    assignment_calls = 0
    original_assignments = module._build_walk_forward_assignments

    def snapshot_spy(**kwargs):
        prior_count = len(kwargs["prior_observations"])
        snapshot_prior_counts.append(prior_count)
        return _key(
            HistoricalPrefixRateRelation.HIGHER
            if prior_count % 2 == 0
            else HistoricalPrefixRateRelation.LOWER
        )

    def label_spy(**kwargs):
        return kwargs["current_target"].target.draw_number % 3 == 0

    def assignment_spy(**kwargs):
        nonlocal assignment_calls
        assignment_calls += 1
        return original_assignments(**kwargs)

    monkeypatch.setattr(module, "_snapshot_feature_key", snapshot_spy)
    monkeypatch.setattr(module, "_current_target_succeeded", label_spy)
    monkeypatch.setattr(module, "_build_walk_forward_assignments", assignment_spy)

    result, factory = _evaluate(source)

    assert factory.calls == factory.reader.calls == assignment_calls == 1
    assert snapshot_prior_counts == list(range(1100))
    assert result.evaluation_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
    assert result.split.split_method == ("FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION")
    assert (
        result.split.total_assignment_count,
        result.split.warmup_count,
        result.split.discovery_count,
        result.split.confirmation_count,
    ) == (1100, 50, 750, 300)
    assert result.split.discovery_first_target is not None
    assert result.split.discovery_last_target is not None
    assert result.split.confirmation_first_target is not None
    assert result.split.confirmation_last_target is not None
    assert result.split.discovery_first_target.draw_number == 51
    assert result.split.discovery_last_target.draw_number == 800
    assert result.split.confirmation_first_target.draw_number == 801
    assert result.split.confirmation_last_target.draw_number == 1100
    assert result.discovery is not None
    assert result.confirmation is not None
    assert result.discovery.baseline.observation_count == 750
    assert result.confirmation.baseline.observation_count == 300
    assert result.family_size == len(result.comparisons) == 64
    assert [item.cohort_index for item in result.comparisons] == list(range(64))
    assert sum(item.cohort_counts.observation_count for item in result.discovery.diagnostics) == 750
    assert (
        sum(item.cohort_counts.observation_count for item in result.confirmation.diagnostics) == 300
    )
    assert all(
        comparison.discovery_diagnostic.feature_key
        == comparison.feature_key
        == comparison.confirmation_diagnostic.feature_key
        for comparison in result.comparisons
    )
    assert all(
        comparison.relationship
        in {
            HistoricalPrefixTemporalHoldoutRelationship.SAME_HIGHER,
            HistoricalPrefixTemporalHoldoutRelationship.SAME_EQUAL,
            HistoricalPrefixTemporalHoldoutRelationship.SAME_LOWER,
            HistoricalPrefixTemporalHoldoutRelationship.DIFFERENT,
            HistoricalPrefixTemporalHoldoutRelationship.UNAVAILABLE,
        }
        for comparison in result.comparisons
    )


def test_insufficient_history_never_shortens_phases_or_runs_diagnostics(
    monkeypatch,
) -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(1049)),)
    )
    monkeypatch.setattr(
        module,
        "_snapshot_feature_key",
        lambda **_kwargs: _key(HistoricalPrefixRateRelation.UNAVAILABLE),
    )
    monkeypatch.setattr(
        module,
        "_current_target_succeeded",
        lambda **_kwargs: False,
    )

    result, _ = _evaluate(source)

    assert result.evaluation_status is (
        HistoricalPrefixTemporalHoldoutStatus.NOT_READY_INSUFFICIENT_HISTORY
    )
    assert (
        result.split.total_assignment_count,
        result.split.warmup_count,
        result.split.discovery_count,
        result.split.confirmation_count,
    ) == (1049, 1049, 0, 0)
    assert result.discovery is result.confirmation is None
    assert result.comparisons == ()
    assert result.split.discovery_first_target is None
    assert result.split.discovery_last_target is None
    assert result.split.confirmation_first_target is None
    assert result.split.confirmation_last_target is None


def test_holdout_effect_change_and_neutral_relationship_are_exact() -> None:
    assert module._effect_change(
        module.HistoricalPrefixSignedRateDelta(1, 1, True),
        module.HistoricalPrefixSignedRateDelta(1, 3, True),
    ) == module.HistoricalPrefixSignedRateDelta(-2, 3, True)
    assert (
        module._temporal_relationship(
            HistoricalPrefixRateRelation.HIGHER,
            HistoricalPrefixRateRelation.HIGHER,
        )
        is HistoricalPrefixTemporalHoldoutRelationship.SAME_HIGHER
    )
