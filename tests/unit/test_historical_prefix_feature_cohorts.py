"""Walk-forward feature-cohort application contract tests."""

# pyright: reportPrivateUsage=false
# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

from dataclasses import replace

import pytest
from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

import lottolab.application.use_cases.evaluate_historical_prefix_success_windows as module
from lottolab.application.historical_prefix_success_windows import (
    FEATURE_COHORT_RELATION_ORDER,
    HistoricalPrefixRateRelation,
    HistoricalPrefixStrategyFeatureCohortResult,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessWindowsContractError,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixSuccessWindowsUnavailableError,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)

IMPORT_IDENTITY = "a" * 64


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


def _evaluate(
    source: HistoricalPrefixSuccessWindowSource,
    *,
    prefix_count: int = 1,
    criterion: HistoricalPrefixSuccessCriterion = HistoricalPrefixSuccessCriterion.M3_PLUS,
) -> tuple[HistoricalPrefixStrategyFeatureCohortResult, _Factory]:
    factory = _Factory(source)
    identity = source.strategies[0].identity
    result = EvaluateHistoricalPrefixSuccessWindows(factory).get_feature_cohorts(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id=identity.strategy_id,
        strategy_version=identity.strategy_version,
        replicate=identity.replicate,
        prefix_count=prefix_count,
        criterion=criterion,
    )
    return result, factory


def test_walk_forward_uses_only_prior_targets_and_freezes_snapshot_before_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(4)),)
    )
    evaluator_calls: list[tuple[str, ...]] = []
    event_order: list[str] = []
    original_evaluator = module.evaluate_strategy_success_windows
    original_snapshot = module._snapshot_feature_key
    original_label = module._current_target_succeeded

    def evaluator_spy(observations, criterion):
        evaluator_calls.append(
            tuple(item.provenance.target_draw or "" for item in observations)
        )
        return original_evaluator(observations, criterion)

    def snapshot_spy(**kwargs):
        event_order.append(
            f"snapshot:{len(kwargs['prior_observations'])}"
        )
        return original_snapshot(**kwargs)

    def label_spy(**kwargs):
        event_order.append(
            f"label:{kwargs['current_target'].target.draw_number}"
        )
        return original_label(**kwargs)

    monkeypatch.setattr(module, "evaluate_strategy_success_windows", evaluator_spy)
    monkeypatch.setattr(module, "_snapshot_feature_key", snapshot_spy)
    monkeypatch.setattr(module, "_current_target_succeeded", label_spy)

    result, _ = _evaluate(source)

    assert [len(items) for items in evaluator_calls] == [1, 2, 3]
    assert evaluator_calls == [
        ("2020-01-02#1",),
        ("2020-01-02#1", "2020-01-03#2"),
        ("2020-01-02#1", "2020-01-03#2", "2020-01-04#3"),
    ]
    assert event_order == [
        "snapshot:0",
        "label:1",
        "snapshot:1",
        "label:2",
        "snapshot:2",
        "label:3",
        "snapshot:3",
        "label:4",
    ]
    assert result.baseline.observation_count == 4


def test_canonical_64_cohorts_baseline_exact_deltas_and_provenance() -> None:
    observations = build_success_observations(
        751,
        outcome_factory=lambda observation, position: (
            (3, False)
            if position == 1 and (observation < 450 or 700 <= observation < 750)
            else (0, False)
        ),
    )
    source = build_success_source(
        (
            build_success_strategy(
                "alias",
                effective_strategy_id="base",
                alias_of_strategy_id="base",
                replicate=3,
                observations=tuple(reversed(observations)),
            ),
        )
    )

    result, factory = _evaluate(source)

    assert factory.calls == 1
    assert factory.reader.calls == [IMPORT_IDENTITY]
    assert result.strategy.strategy_id == "alias"
    assert result.strategy.effective_strategy_id == "base"
    assert result.strategy.alias_of_strategy_id == "base"
    assert result.strategy.replicate == 3
    assert result.prefix_count == 1
    assert result.criterion.criterion is HistoricalPrefixSuccessCriterion.M3_PLUS
    assert result.cohort_count == len(result.cohorts) == 64
    assert [cohort.feature_key for cohort in result.cohorts] == [
        module.HistoricalPrefixFeatureRelationTriple(
            long_to_medium=long_to_medium,
            medium_to_short=medium_to_short,
            long_to_short=long_to_short,
        )
        for long_to_medium in FEATURE_COHORT_RELATION_ORDER
        for medium_to_short in FEATURE_COHORT_RELATION_ORDER
        for long_to_short in FEATURE_COHORT_RELATION_ORDER
    ]
    assert result.baseline.observation_count == 751
    assert result.baseline.success_count == 500
    assert result.baseline.failure_count == 251
    assert (
        result.baseline.success_rate.numerator,
        result.baseline.success_rate.denominator,
        result.baseline.success_rate.available,
    ) == (500, 751, True)
    assert sum(item.observation_count for item in result.cohorts) == 751
    assert all(
        item.success_count + item.failure_count == item.observation_count
        for item in result.cohorts
    )

    unavailable = next(
        item
        for item in result.cohorts
        if item.feature_key.long_to_medium
        is HistoricalPrefixRateRelation.UNAVAILABLE
        and item.feature_key.medium_to_short
        is HistoricalPrefixRateRelation.UNAVAILABLE
        and item.feature_key.long_to_short
        is HistoricalPrefixRateRelation.UNAVAILABLE
    )
    assert (
        unavailable.observation_count,
        unavailable.success_count,
        unavailable.failure_count,
    ) == (300, 300, 0)
    assert unavailable.first_target is not None
    assert unavailable.last_target is not None
    assert unavailable.first_target.draw_number == 1
    assert unavailable.last_target.draw_number == 300
    assert (
        unavailable.delta_vs_baseline.numerator,
        unavailable.delta_vs_baseline.denominator,
        unavailable.relation_vs_baseline,
    ) == (251, 751, HistoricalPrefixRateRelation.HIGHER)

    mature = next(
        item
        for item in result.cohorts
        if item.feature_key.long_to_medium is HistoricalPrefixRateRelation.LOWER
        and item.feature_key.medium_to_short is HistoricalPrefixRateRelation.HIGHER
        and item.feature_key.long_to_short is HistoricalPrefixRateRelation.HIGHER
    )
    assert (
        mature.observation_count,
        mature.success_count,
        mature.failure_count,
    ) == (1, 0, 1)
    assert mature.first_target == mature.last_target
    assert mature.first_target is not None
    assert mature.first_target.draw_number == 751
    assert (
        mature.success_rate.numerator,
        mature.success_rate.denominator,
        mature.success_rate.available,
    ) == (0, 1, True)
    assert (
        mature.delta_vs_baseline.numerator,
        mature.delta_vs_baseline.denominator,
        mature.relation_vs_baseline,
    ) == (-500, 751, HistoricalPrefixRateRelation.LOWER)

    empty = result.cohorts[0]
    assert empty.observation_count == empty.success_count == empty.failure_count == 0
    assert (
        empty.success_rate.numerator,
        empty.success_rate.denominator,
        empty.success_rate.available,
    ) == (0, 0, False)
    assert (
        empty.delta_vs_baseline.numerator,
        empty.delta_vs_baseline.denominator,
        empty.delta_vs_baseline.available,
        empty.relation_vs_baseline,
    ) == (0, 0, False, HistoricalPrefixRateRelation.UNAVAILABLE)
    assert empty.first_target is empty.last_target is None


def test_prefix_criterion_and_same_ticket_semantics_label_current_target() -> None:
    observations = build_success_observations(
        1,
        outcome_factory=lambda _observation, position: (
            (2, False)
            if position == 1
            else (0, True)
            if position == 2
            else (6, False)
            if position == 20
            else (0, False)
        ),
    )
    source = build_success_source(
        (build_success_strategy(observations=observations),)
    )

    atomic, _ = _evaluate(
        source,
        prefix_count=2,
        criterion=HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL,
    )
    last_ticket_excluded, _ = _evaluate(
        source,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M6,
    )

    assert atomic.baseline.success_count == 0
    assert atomic.baseline.failure_count == 1
    assert last_ticket_excluded.baseline.success_count == 0
    assert last_ticket_excluded.baseline.failure_count == 1


def test_zero_observation_source_returns_one_empty_canonical_cohort_grid() -> None:
    result, _ = _evaluate(build_success_source((build_success_strategy(),)))

    assert result.baseline.observation_count == 0
    assert (
        result.baseline.success_rate.numerator,
        result.baseline.success_rate.denominator,
        result.baseline.success_rate.available,
    ) == (0, 0, False)
    assert len(result.cohorts) == 64
    assert all(
        cohort.observation_count == 0
        and cohort.first_target is None
        and cohort.last_target is None
        for cohort in result.cohorts
    )


@pytest.mark.parametrize("mutation", ["duplicate", "target-order", "cutoff"])
def test_walk_forward_chronology_fails_closed(mutation: str) -> None:
    first, second = build_success_observations(2, draw_number_offset=10)
    if mutation == "duplicate":
        observations = (first, first)
    elif mutation == "target-order":
        observations = (
            first,
            replace(
                second,
                target=replace(second.target, draw_number=9),
            ),
        )
    else:
        observations = (
            replace(first, cutoff=first.target),
            second,
        )
    source = build_success_source(
        (build_success_strategy(observations=observations),)
    )

    with pytest.raises(HistoricalPrefixSuccessWindowsUnavailableError):
        _evaluate(source)


def test_invalid_input_precedes_factory_and_exact_strategy_is_found_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(1)),)
    )
    factory = _Factory(source)
    evaluator = EvaluateHistoricalPrefixSuccessWindows(factory)

    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        evaluator.get_feature_cohorts(
            import_identity_sha256="invalid",
            strategy_id="strategy-a",
            strategy_version="v1",
            replicate=1,
            prefix_count=1,
            criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
        )
    assert factory.calls == 0

    find_calls = 0
    original_find = module._find_exact_strategy

    def find_spy(*args, **kwargs):
        nonlocal find_calls
        find_calls += 1
        return original_find(*args, **kwargs)

    monkeypatch.setattr(module, "_find_exact_strategy", find_spy)
    evaluator.get_feature_cohorts(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )
    assert find_calls == 1
    assert factory.calls == 1
    assert factory.reader.calls == [IMPORT_IDENTITY]
