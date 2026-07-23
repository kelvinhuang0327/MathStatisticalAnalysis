"""Exact inferential diagnostics for walk-forward feature cohorts."""

# pyright: reportPrivateUsage=false
# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

import lottolab.application.use_cases.evaluate_historical_prefix_success_windows as module
from lottolab.application.historical_prefix_success_windows import (
    BENJAMINI_YEKUTIELI_METHOD,
    FISHER_EXACT_TWO_SIDED_METHOD,
    HistoricalPrefixExactProbability,
    HistoricalPrefixExactSuccessRate,
    HistoricalPrefixFeatureCohortTestStatus,
    HistoricalPrefixOutcomeCounts,
    HistoricalPrefixRateRelation,
    HistoricalPrefixSignedRateDelta,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixWalkForwardBaseline,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)

IMPORT_IDENTITY = "a" * 64


class _Reader:
    def __init__(self, source: object) -> None:
        self.source = source
        self.calls = 0

    def load_source(self, import_identity_sha256: str) -> object:
        assert import_identity_sha256 == IMPORT_IDENTITY
        self.calls += 1
        return self.source


class _Factory:
    def __init__(self, source: object) -> None:
        self.reader = _Reader(source)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _counts(observations: int, successes: int) -> HistoricalPrefixOutcomeCounts:
    return HistoricalPrefixOutcomeCounts(
        observation_count=observations,
        success_count=successes,
        failure_count=observations - successes,
    )


def test_exact_fisher_probability_ordering_reproduces_known_tables() -> None:
    assert module._fisher_exact_two_sided(_counts(2, 2), _counts(2, 0)) == (
        HistoricalPrefixExactProbability(1, 3)
    )
    assert module._fisher_exact_two_sided(_counts(3, 3), _counts(3, 0)) == (
        HistoricalPrefixExactProbability(1, 10)
    )


def test_test_status_precedence_and_non_testable_probability_contract() -> None:
    assert module._diagnostic_test_status(_counts(0, 0), _counts(0, 0)) is (
        HistoricalPrefixFeatureCohortTestStatus.NOT_TESTABLE_EMPTY_COHORT
    )
    assert module._diagnostic_test_status(_counts(2, 1), _counts(0, 0)) is (
        HistoricalPrefixFeatureCohortTestStatus.NOT_TESTABLE_EMPTY_COMPLEMENT
    )
    assert module._diagnostic_test_status(_counts(2, 0), _counts(2, 0)) is (
        HistoricalPrefixFeatureCohortTestStatus.NOT_TESTABLE_NO_OUTCOME_VARIATION
    )
    assert module._diagnostic_test_status(_counts(2, 1), _counts(2, 0)) is (
        HistoricalPrefixFeatureCohortTestStatus.TESTED
    )


def test_fixed_family_benjamini_yekutieli_uses_exact_harmonic_factor() -> None:
    raw = (HistoricalPrefixExactProbability(1, 10_000),) + (
        HistoricalPrefixExactProbability(1, 1),
    ) * 63

    adjusted = module._adjust_benjamini_yekutieli(raw)

    harmonic = sum(
        (Fraction(1, rank) for rank in range(1, 65)),
        start=Fraction(0, 1),
    )
    expected = Fraction(1, 10_000) * 64 * harmonic
    assert adjusted[0] == HistoricalPrefixExactProbability(
        expected.numerator,
        expected.denominator,
    )
    assert adjusted[1:] == (HistoricalPrefixExactProbability(1, 1),) * 63


def test_complete_family_uses_disjoint_complements_and_preserves_order() -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(1)),)
    )
    cohorts = module._feature_cohorts(
        source=source,
        strategy=source.strategies[0],
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )
    first = replace(
        cohorts.cohorts[0],
        observation_count=2,
        success_count=2,
        failure_count=0,
        success_rate=HistoricalPrefixExactSuccessRate(2, 2, True),
        delta_vs_baseline=HistoricalPrefixSignedRateDelta(1, 2, True),
        relation_vs_baseline=HistoricalPrefixRateRelation.HIGHER,
    )
    second = replace(
        cohorts.cohorts[1],
        observation_count=2,
        success_count=0,
        failure_count=2,
        success_rate=HistoricalPrefixExactSuccessRate(0, 2, True),
        delta_vs_baseline=HistoricalPrefixSignedRateDelta(-1, 2, True),
        relation_vs_baseline=HistoricalPrefixRateRelation.LOWER,
    )
    synthetic = replace(
        cohorts,
        baseline=HistoricalPrefixWalkForwardBaseline(
            observation_count=4,
            success_count=2,
            failure_count=2,
            success_rate=HistoricalPrefixExactSuccessRate(2, 4, True),
        ),
        cohorts=(first, second, *cohorts.cohorts[2:]),
    )

    result = module._feature_cohort_diagnostics(synthetic)

    assert result.family_size == len(result.diagnostics) == 64
    assert result.raw_test_method == FISHER_EXACT_TWO_SIDED_METHOD
    assert result.adjustment_method == BENJAMINI_YEKUTIELI_METHOD
    assert [item.cohort_index for item in result.diagnostics] == list(range(64))
    assert [item.feature_key for item in result.diagnostics] == [
        item.feature_key for item in synthetic.cohorts
    ]
    assert result.diagnostics[0].cohort_counts == _counts(2, 2)
    assert result.diagnostics[0].outside_counts == _counts(2, 0)
    assert result.diagnostics[0].raw_p_value == HistoricalPrefixExactProbability(1, 3)
    assert result.diagnostics[0].risk_difference == (
        HistoricalPrefixSignedRateDelta(1, 1, True)
    )
    assert result.diagnostics[0].relation_vs_outside is (
        HistoricalPrefixRateRelation.HIGHER
    )
    assert all(
        item.raw_p_value == HistoricalPrefixExactProbability(1, 1)
        for item in result.diagnostics[2:]
    )


def test_public_use_case_validates_then_loads_and_builds_cohorts_once(
    monkeypatch,
) -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(2)),)
    )
    factory = _Factory(source)
    calls = 0
    original = module._feature_cohorts

    def spy(**kwargs):
        nonlocal calls
        calls += 1
        return original(**kwargs)

    monkeypatch.setattr(module, "_feature_cohorts", spy)
    identity = source.strategies[0].identity
    result = EvaluateHistoricalPrefixSuccessWindows(
        factory  # type: ignore[arg-type]
    ).get_feature_cohort_diagnostics(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id=identity.strategy_id,
        strategy_version=identity.strategy_version,
        replicate=identity.replicate,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )

    assert result.family_size == 64
    assert factory.calls == factory.reader.calls == calls == 1
