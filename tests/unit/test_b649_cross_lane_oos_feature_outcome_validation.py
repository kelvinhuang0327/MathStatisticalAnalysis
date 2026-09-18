"""Focused contract tests for the bounded B649 cross-lane OOS study."""

from __future__ import annotations

from dataclasses import replace

import pytest

from lottolab.research.b649_cross_lane_oos_feature_outcome_validation import (
    FEATURE_FAMILY_REGISTRY,
    PORTFOLIO_BUDGETS,
    Classification,
    ConsensusForecastRecord,
    CrossLaneValidationError,
    DrawOutcome,
    PortfolioForecastRecord,
    RankedNumber,
    build_decision_table,
    wilson_score_interval,
)

_STREAM_IDS = tuple(f"stream_{index}" for index in range(11))


def _ranking() -> tuple[RankedNumber, ...]:
    return tuple(
        RankedNumber(number=number, rank=rank, support_units=20 - (rank // 8))
        for rank, number in enumerate(range(1, 50), start=1)
    )


def _consensus(
    draw_number: str,
    target_date: str,
    cutoff_number: str,
    cutoff_date: str,
) -> ConsensusForecastRecord:
    return ConsensusForecastRecord(
        draw_number=draw_number,
        target_draw_date=target_date,
        scheduled_at_date=target_date,
        cutoff_draw_number=cutoff_number,
        cutoff_draw_date=cutoff_date,
        exact_stream_ids=_STREAM_IDS,
        final_decision_ranking=_ranking(),
        final_ticket=(1, 2, 3, 4, 5, 6),
        pre_outcome_temporal_integrity="PASS",
        target_result_used=False,
    )


def _ticket(start: int) -> tuple[int, ...]:
    return tuple(((start + offset) % 49) + 1 for offset in range(6))


def _portfolio() -> PortfolioForecastRecord:
    return PortfolioForecastRecord(
        draw_number="115000088",
        target_draw_date="2026-09-15",
        scheduled_at_date="2026-09-15",
        cutoff_draw_number="115000087",
        cutoff_draw_date="2026-09-11",
        tickets_by_budget={
            budget: tuple(_ticket(6 * index) for index in range(budget))
            for budget in PORTFOLIO_BUDGETS
        },
        target_result_used=False,
        outcome_used="NO",
    )


def test_wilson_interval_is_bounded_and_contains_observed_rate() -> None:
    lower, upper = wilson_score_interval(1, 2)

    assert 0.0 <= lower <= 0.5 <= upper <= 1.0


def test_forecast_rejects_future_cutoff_and_target_feedback() -> None:
    with pytest.raises(CrossLaneValidationError, match="cutoff_draw_date"):
        _consensus("115000088", "2026-09-15", "115000089", "2026-09-18")

    with pytest.raises(CrossLaneValidationError, match="target_result_used"):
        replace(
            _consensus("115000088", "2026-09-15", "115000087", "2026-09-11"),
            target_result_used=True,
        )


def test_portfolio_requires_all_supported_budgets() -> None:
    with pytest.raises(CrossLaneValidationError, match="exactly K"):
        PortfolioForecastRecord(
            draw_number="115000088",
            target_draw_date="2026-09-15",
            scheduled_at_date="2026-09-15",
            cutoff_draw_number="115000087",
            cutoff_draw_date="2026-09-11",
            tickets_by_budget={5: tuple(_ticket(6 * index) for index in range(5))},
            target_result_used=False,
        )


def test_decision_table_pairs_same_draws_and_reports_auxiliary_outcomes() -> None:
    consensus_records = (
        _consensus("115000087", "2026-09-11", "115000086", "2026-09-08"),
        _consensus("115000088", "2026-09-15", "115000087", "2026-09-11"),
    )
    outcomes = {
        "115000087": DrawOutcome("115000087", (1, 8, 9, 10, 11, 12)),
        "115000088": DrawOutcome("115000088", (20, 21, 22, 23, 24, 25)),
    }

    result = build_decision_table(
        consensus_records=consensus_records,
        portfolio_records=(_portfolio(),),
        outcomes=outcomes,
        method_family_lookup={"stream_0": "family_a", "stream_1": "family_b"},
    )

    assert result.consensus_pair_draw_numbers == ("115000087", "115000088")
    assert result.portfolio_pair_draw_numbers == ("115000088",)
    assert set(result.portfolio_evaluations) == set(PORTFOLIO_BUDGETS)

    rows = {row.row_id: row for row in result.decision_rows}
    assert rows["t1_t2_weighted_support"].classification is Classification.UNAVAILABLE
    assert rows["raw_vote_support__drawn_vs_field_mean"].sample_count == 2
    assert rows["cross_budget_persistence__k1_vs_k5_k10_k20_first_ticket"].sample_count == 1
    assert (
        rows["method_lift__consensus_k1_vs_random_baseline"].classification
        is Classification.INSUFFICIENT_POWER
    )
    assert set(rows["method_lift__portfolio_k20_vs_random_baseline"].auxiliary_outcomes or {}) >= {
        "max_hit_count_by_draw",
        "p_max_ge_3",
        "p_max_ge_4",
        "expected_max_main_matches_observed",
        "expected_max_main_matches_random_reference",
    }
    assert result.canonical_dict()["analysis_contract"]


def test_duplicate_forecast_draw_is_rejected_before_evaluation() -> None:
    record = _consensus("115000087", "2026-09-11", "115000086", "2026-09-08")

    with pytest.raises(CrossLaneValidationError, match="duplicate consensus"):
        build_decision_table(
            consensus_records=(record, record),
            portfolio_records=(),
            outcomes={record.draw_number: DrawOutcome(record.draw_number, (1, 8, 9, 10, 11, 12))},
            method_family_lookup={},
        )


def test_registry_keeps_every_requested_family_explicit() -> None:
    family_ids = {family.family_id for family in FEATURE_FAMILY_REGISTRY}

    assert len(family_ids) == 11
    assert "loo_robustness" in family_ids
    assert "pair_consensus" in family_ids
