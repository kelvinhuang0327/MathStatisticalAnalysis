"""Exact-mathematics and contract tests for the base-method evaluation pipeline.

Where possible, expected values are cross-checked against constants already
sealed elsewhere in this project (the EH02/EH18 Track B closure and the
production ``historical_success_random_baseline`` module) rather than
re-derived from the same formula under test, so these tests catch a wrong
formula, not just a wrong transcription.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from lottolab.application.historical_prefix_success_windows import HistoricalPrefixSuccessCriterion
from lottolab.application.historical_success_random_baseline import (
    LEGAL_TICKET_COUNT,
    criterion_success_ticket_count,
)
from lottolab.research import base_method_evaluation
from lottolab.research.base_method_evaluation import (
    AVG_MATCH_ID,
    BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
    BIG_LOTTO_MATCH_CONTRACT,
    MINIMUM_EXPECTED_NULL_SUCCESSES,
    MINIMUM_SUPPORTED_DRAWS,
    BaselineMethod,
    BaseMethodEvaluationError,
    EvaluableStatus,
    ExposureKind,
    HitTierDefinition,
    LotteryMatchContract,
    MethodDrawObservation,
    MethodExposure,
    MethodIdentity,
    MethodTargetCoverage,
    MetricCell,
    OutputShape,
    RandomStatus,
    ReplayStatus,
    WindowKind,
    WindowRole,
    WindowStatus,
    average_match_reference,
    evaluate_method,
    portfolio_tier_probability,
    single_ticket_tier_probability,
)

# Sealed, independently-authored reference values this pilot must reproduce:
#   B649_TRACK_D_POST_EH18_METHOD_UNIVERSE_TRANSITION_R1/queue_policy.json ->
#       eh18_closure precedent: "p0 = 2111774/13983816 ... P(>=2 of 6 match)"
#   .task-data/B649_HIT_DEPTH_PROJECTION_R1/report.md BASELINE table (M1+ main p fraction)
_SEALED_M1_PLUS_FRACTION = Fraction(563_383, 998_844)
_SEALED_M2_PLUS_FRACTION = Fraction(2_111_774, 13_983_816)


def _tier(tier_id: str) -> HitTierDefinition:
    return next(tier for tier in BIG_LOTTO_MATCH_CONTRACT.hit_tiers if tier.tier_id == tier_id)


def test_m1_plus_matches_sealed_hit_depth_projection_baseline() -> None:
    probability = single_ticket_tier_probability(BIG_LOTTO_MATCH_CONTRACT, _tier("M1_PLUS"))
    assert probability == _SEALED_M1_PLUS_FRACTION


def test_m2_plus_matches_sealed_eh18_closure_precedent() -> None:
    probability = single_ticket_tier_probability(BIG_LOTTO_MATCH_CONTRACT, _tier("M2_PLUS"))
    assert probability == _SEALED_M2_PLUS_FRACTION


@pytest.mark.parametrize(
    ("tier_id", "criterion"),
    [
        ("M3_PLUS", HistoricalPrefixSuccessCriterion.M3_PLUS),
        ("M4_PLUS", HistoricalPrefixSuccessCriterion.M4_PLUS),
    ],
)
def test_m3_and_m4_plus_match_existing_production_frozen_counts(
    tier_id: str, criterion: HistoricalPrefixSuccessCriterion
) -> None:
    probability = single_ticket_tier_probability(BIG_LOTTO_MATCH_CONTRACT, _tier(tier_id))
    expected = Fraction(criterion_success_ticket_count(criterion), LEGAL_TICKET_COUNT)
    assert probability == expected
    assert BIG_LOTTO_MATCH_CONTRACT.legal_ticket_count == LEGAL_TICKET_COUNT


def test_tier_probabilities_are_strictly_monotonic_decreasing() -> None:
    probabilities = [
        single_ticket_tier_probability(BIG_LOTTO_MATCH_CONTRACT, _tier(tier_id))
        for tier_id in ("M1_PLUS", "M2_PLUS", "M3_PLUS", "M4_PLUS")
    ]
    assert probabilities == sorted(probabilities, reverse=True)
    assert len(set(probabilities)) == 4


def test_average_match_reference_is_the_exact_hypergeometric_mean() -> None:
    assert average_match_reference(BIG_LOTTO_MATCH_CONTRACT) == Fraction(36, 49)


def test_portfolio_tier_probability_single_ticket_is_identity() -> None:
    p = single_ticket_tier_probability(BIG_LOTTO_MATCH_CONTRACT, _tier("M2_PLUS"))
    assert portfolio_tier_probability(p, 1) == p
    assert portfolio_tier_probability(p, 0) == 0


def test_portfolio_tier_probability_matches_inclusion_exclusion_for_two_tickets() -> None:
    p = single_ticket_tier_probability(BIG_LOTTO_MATCH_CONTRACT, _tier("M1_PLUS"))
    assert portfolio_tier_probability(p, 2) == 1 - (1 - p) * (1 - p)


def test_lottery_match_contract_rejects_duplicate_tier_ids() -> None:
    with pytest.raises(BaseMethodEvaluationError):
        LotteryMatchContract(
            lottery_type="TOY",
            population_size=5,
            winning_number_count=2,
            ticket_number_count=2,
            hit_tiers=(HitTierDefinition("M1_PLUS", 1), HitTierDefinition("M1_PLUS", 1)),
        )


def test_method_identity_rejects_output_shape_exposure_mismatch() -> None:
    exposure = MethodExposure(ExposureKind.FIXED, 1, 1)
    coverage = MethodTargetCoverage(1, "D1", "D1")
    with pytest.raises(BaseMethodEvaluationError):
        MethodIdentity(
            method_id="toy",
            method_version="v1",
            method_family="toy_family",
            output_shape=OutputShape.PORTFOLIO,
            exposure=exposure,
            target_coverage=coverage,
            replay_status=ReplayStatus.BASELINE_RECORDED,
        )


def test_metric_cell_rejects_delta_that_does_not_match_observed_minus_reference() -> None:
    with pytest.raises(BaseMethodEvaluationError):
        MetricCell(
            evaluable_status=EvaluableStatus.EVALUABLE,
            eligible_draw_count=10,
            success_draw_count=1,
            observed_value=Fraction(1, 10),
            random_reference=Fraction(1, 20),
            delta_vs_random=Fraction(999),
            random_status=RandomStatus.ABOVE_RANDOM,
            baseline_method=BaselineMethod.BINOMIAL_EXACT,
        )


# --- Toy end-to-end contract (small enough to hand-compute) ----------------
#
# population=5, pick 2, winning=2 -> legal_ticket_count = C(5,2) = 10
# M1+ (>=1 hit):  [C(2,1)*C(3,1) + C(2,2)*C(3,0)] / 10 = (6 + 1)/10 = 7/10
# M2+ (>=2 hits): C(2,2)*C(3,0) / 10 = 1/10
# avg_match reference = 2*2/5 = 4/5

_TOY_CONTRACT = LotteryMatchContract(
    lottery_type="TOY_5_PICK_2",
    population_size=5,
    winning_number_count=2,
    ticket_number_count=2,
    hit_tiers=(HitTierDefinition("M1_PLUS", 1), HitTierDefinition("M2_PLUS", 2)),
)


def test_toy_contract_single_ticket_probabilities_match_hand_calculation() -> None:
    m1_plus, m2_plus = _TOY_CONTRACT.hit_tiers
    assert single_ticket_tier_probability(_TOY_CONTRACT, m1_plus) == Fraction(7, 10)
    assert single_ticket_tier_probability(_TOY_CONTRACT, m2_plus) == Fraction(1, 10)
    assert average_match_reference(_TOY_CONTRACT) == Fraction(4, 5)


def _toy_identity(eligible_draw_count: int) -> MethodIdentity:
    return MethodIdentity(
        method_id="toy_method",
        method_version="v1",
        method_family="toy_family",
        output_shape=OutputShape.SINGLE_OUTPUT,
        exposure=MethodExposure(ExposureKind.FIXED, 1, 1),
        target_coverage=MethodTargetCoverage(eligible_draw_count, "D1", f"D{eligible_draw_count}"),
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )


def test_evaluate_method_toy_history_matches_hand_calculation() -> None:
    # Three draws, single ticket each: hits 2 (M2+ success), 1 (M1+ only), 0 (neither).
    history = (
        MethodDrawObservation("D1", "2020-01-01", 1, 1, (2,)),
        MethodDrawObservation("D2", "2020-01-02", 1, 1, (1,)),
        MethodDrawObservation("D3", "2020-01-03", 1, 1, (0,)),
    )
    record = evaluate_method(_TOY_CONTRACT, _toy_identity(3), history)

    full = record.windows[WindowKind.FULL_HISTORY]
    assert full.window_status is WindowStatus.COMPLETE
    assert full.window_role is WindowRole.DESCRIPTIVE_REFERENCE_ONLY
    assert full.eligible_draw_count == 3

    m1 = full.metrics["M1_PLUS"]
    assert m1.success_draw_count == 2  # draws with hits=2 and hits=1 both satisfy >=1
    assert m1.observed_value == Fraction(2, 3)
    # D_i=1 for all draws, so the portfolio baseline collapses to the single-ticket probability.
    assert m1.random_reference == Fraction(7, 10)
    assert m1.delta_vs_random == Fraction(2, 3) - Fraction(7, 10)
    assert m1.random_status is RandomStatus.BELOW_RANDOM
    assert m1.baseline_method is BaselineMethod.BINOMIAL_EXACT
    # Below the data-sufficiency floor even though the window itself is COMPLETE.
    assert m1.evaluable_status is EvaluableStatus.INSUFFICIENT

    m2 = full.metrics["M2_PLUS"]
    assert m2.success_draw_count == 1
    assert m2.observed_value == Fraction(1, 3)
    assert m2.random_reference == Fraction(1, 10)
    assert m2.random_status is RandomStatus.ABOVE_RANDOM

    avg = full.metrics[AVG_MATCH_ID]
    assert avg.observed_value == Fraction(1)  # (2+1+0)/3
    assert avg.random_reference == Fraction(4, 5)
    assert avg.random_status is RandomStatus.ABOVE_RANDOM
    assert avg.baseline_method is BaselineMethod.HYPERGEOMETRIC_MEAN_EXACT

    # WINDOW_50/300/750 all request more draws than exist -> INSUFFICIENT_WINDOW_HISTORY,
    # but the 3 real draws are still selected and still carry computed numbers.
    for window_kind in (WindowKind.WINDOW_50, WindowKind.WINDOW_300, WindowKind.WINDOW_750):
        block = record.windows[window_kind]
        assert block.window_status is WindowStatus.INSUFFICIENT_WINDOW_HISTORY
        assert block.eligible_draw_count == 3
        assert block.metrics["M1_PLUS"].observed_value == Fraction(2, 3)
        assert block.metrics["M1_PLUS"].evaluable_status is EvaluableStatus.INSUFFICIENT


def test_evaluate_method_empty_history_raises() -> None:
    with pytest.raises(BaseMethodEvaluationError):
        evaluate_method(_TOY_CONTRACT, _toy_identity(0), ())


def test_evaluate_method_cell_becomes_evaluable_once_thresholds_clear() -> None:
    # 30 draws all hitting M1+ (hits=1): eligible_draw_count meets MINIMUM_SUPPORTED_DRAWS,
    # and expected successes (30 * 7/10 = 21) clears MINIMUM_EXPECTED_NULL_SUCCESSES.
    assert MINIMUM_SUPPORTED_DRAWS == 30
    assert MINIMUM_EXPECTED_NULL_SUCCESSES == 5
    history = tuple(
        MethodDrawObservation(f"D{i}", f"2020-01-{i:02d}", 1, 1, (1,)) for i in range(1, 31)
    )
    record = evaluate_method(_TOY_CONTRACT, _toy_identity(30), history)
    m1 = record.windows[WindowKind.FULL_HISTORY].metrics["M1_PLUS"]
    assert m1.evaluable_status is EvaluableStatus.EVALUABLE
    assert m1.observed_value == Fraction(1, 1)
    assert m1.random_status is RandomStatus.ABOVE_RANDOM

    # M2+ never fires (hits=1 never satisfies >=2): observed 0, still EVALUABLE only if
    # expected successes clear the floor -- here expected = 30 * 1/10 = 3 < 5, so INSUFFICIENT.
    m2 = record.windows[WindowKind.FULL_HISTORY].metrics["M2_PLUS"]
    assert m2.observed_value == Fraction(0)
    assert m2.evaluable_status is EvaluableStatus.INSUFFICIENT


def test_metric_cell_no_eligible_draws_has_no_inferential_values() -> None:
    # evaluate_method requires non-empty history, so every window it produces has
    # at least one eligible draw; NO_ELIGIBLE_DRAWS is exercised directly against
    # the public MetricCell contract instead (e.g. for a method with zero draws
    # in a caller-constructed record).
    cell = MetricCell(
        evaluable_status=EvaluableStatus.NO_ELIGIBLE_DRAWS,
        eligible_draw_count=0,
        success_draw_count=None,
        observed_value=None,
        random_reference=None,
        delta_vs_random=None,
        random_status=RandomStatus.NOT_EVALUABLE,
        baseline_method=BaselineMethod.NOT_EVALUABLE,
    )
    assert cell.observed_value is None
    assert cell.random_reference is None
    assert cell.delta_vs_random is None


def test_evaluate_method_single_draw_history_is_insufficient_not_empty() -> None:
    history = (MethodDrawObservation("D1", "2020-01-01", 1, 1, (0,)),)
    record = evaluate_method(_TOY_CONTRACT, _toy_identity(1), history)
    full = record.windows[WindowKind.FULL_HISTORY]
    assert full.eligible_draw_count == 1
    assert full.metrics["M1_PLUS"].evaluable_status is EvaluableStatus.INSUFFICIENT
    assert full.metrics["M1_PLUS"].observed_value == Fraction(0)


def test_variable_exposure_uses_poisson_binomial_baseline_method() -> None:
    history = (
        MethodDrawObservation("D1", "2020-01-01", 3, 3, (0, 1, 2)),
        MethodDrawObservation("D2", "2020-01-02", 2, 2, (0, 0)),
    )
    record = evaluate_method(_TOY_CONTRACT, _toy_identity(2), history)
    m1 = record.windows[WindowKind.FULL_HISTORY].metrics["M1_PLUS"]
    assert m1.baseline_method is BaselineMethod.POISSON_BINOMIAL_EXACT
    # Draw 1: q = 1-(1-7/10)^3 ; Draw 2: q = 1-(1-7/10)^2 ; expected = sum / 2 draws.
    p = Fraction(7, 10)
    expected = ((1 - (1 - p) ** 3) + (1 - (1 - p) ** 2)) / 2
    assert m1.random_reference == expected


def test_fixed_exposure_uses_binomial_exact_baseline_method() -> None:
    history = (
        MethodDrawObservation("D1", "2020-01-01", 4, 4, (0, 1, 2, 0)),
        MethodDrawObservation("D2", "2020-01-02", 4, 4, (0, 0, 1, 1)),
    )
    record = evaluate_method(_TOY_CONTRACT, _toy_identity(2), history)
    m1 = record.windows[WindowKind.FULL_HISTORY].metrics["M1_PLUS"]
    assert m1.baseline_method is BaselineMethod.BINOMIAL_EXACT


def test_evaluator_semantic_version_is_declared_and_distinct_from_strategy_versions():
    """The evaluator's own semantics need an identity separate from any
    strategy's METHOD_VERSION, or two records computed under different
    evaluator meanings would be indistinguishable."""

    assert isinstance(BASE_METHOD_EVALUATOR_SEMANTIC_VERSION, str)
    assert BASE_METHOD_EVALUATOR_SEMANTIC_VERSION
    assert BASE_METHOD_EVALUATOR_SEMANTIC_VERSION.startswith("base_method_evaluation/")
    assert "BASE_METHOD_EVALUATOR_SEMANTIC_VERSION" in base_method_evaluation.__all__
