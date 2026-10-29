from __future__ import annotations

from fractions import Fraction

import pytest

from lottolab.research.b649_k235_incremental_rank_099_r1 import (
    IncrementalRankInputError,
    _advance_window_metric,
    _CellEvidence,
    _fraction_payload,
    _new_cell,
    _ranking_key,
)


def _base_metric() -> dict[str, object]:
    return {
        "strategy_id": "strategy",
        "window": "50",
        "target_period_count": 5,
        "first_draw_id": "1",
        "last_draw_id": "5",
        "official_any_prize_success_count": 3,
        "denominator": 5,
        "historical_win_rate": _fraction_payload(Fraction(3, 5)),
        "random_baseline_probability": _fraction_payload(Fraction(1, 5)),
        "relative_random_gain": _fraction_payload(Fraction(2, 5)),
        "failed_period_count": 0,
        "missing_period_count": 0,
        "not_evaluable_period_count": 0,
        "overlap_period_count": 1,
        "random_probability_method_counts": {
            "EXACT_OVERLAPPING_PORTFOLIO": 1,
            "ZERO_OVERLAP_REFERENCE": 4,
        },
        "source_counts": {
            "effective_denominator": 5,
            "success_count": 3,
            "failure_count": 2,
            "source_draw_count": 5,
            "execution_failure_count": 0,
            "missing_cell_count": 0,
            "ineligible_draw_count": 0,
            "unknown_status_count": 0,
            "ticket_count_violation_count": 0,
        },
    }


def test_increment_removes_old_targets_and_excludes_failed_and_missing_cells() -> None:
    updated = _advance_window_metric(
        _base_metric(),
        expected_prior_draws=["1", "2", "3", "4", "5"],
        removed=[
            _CellEvidence("COMPLETE", True, Fraction(1, 10), False),
            _CellEvidence("COMPLETE", True, Fraction(1, 5), True),
            _CellEvidence("COMPLETE", False, Fraction(3, 10), False),
        ],
        added=[
            _CellEvidence("COMPLETE", True, Fraction(2, 5), True),
            _CellEvidence("FAILED", reason="execution error"),
            _CellEvidence("MISSING", reason="unverified source version"),
        ],
        first_draw_id="4",
        last_draw_id="8",
        target_period_count=5,
        requested_target_periods=5,
        strategy_id="strategy",
        display_name="Strategy",
        k=2,
        prior_ranking_status="RANKABLE",
        current_ranking_class="PARTIAL",
    )

    assert updated["official_any_prize_success_count"] == 2
    assert updated["denominator"] == 3
    assert updated["historical_win_rate"]["numerator"] == 2
    assert updated["historical_win_rate"]["denominator"] == 3
    assert updated["random_baseline_probability"]["numerator"] == 4
    assert updated["random_baseline_probability"]["denominator"] == 15
    assert updated["relative_random_gain"]["numerator"] == 2
    assert updated["relative_random_gain"]["denominator"] == 5
    assert updated["failed_period_count"] == 1
    assert updated["missing_period_count"] == 1
    assert updated["state_counts"] == {"OBSERVED": 3, "SYNTHETIC": 0, "MISSING": 2}
    assert updated["status"] == "PARTIAL"
    assert updated["random_probability_method_counts"] == {
        "EXACT_OVERLAPPING_PORTFOLIO": 1,
        "ZERO_OVERLAP_REFERENCE": 2,
    }


def test_full_ranking_key_uses_exact_rate_then_denominator_then_identity() -> None:
    rows = [
        {
            "strategy_id": "z_short",
            "windows": {"FULL": {"official_any_prize_success_count": 1, "denominator": 2}},
        },
        {
            "strategy_id": "a_long",
            "windows": {"FULL": {"official_any_prize_success_count": 2, "denominator": 4}},
        },
        {
            "strategy_id": "b_long",
            "windows": {"FULL": {"official_any_prize_success_count": 3, "denominator": 6}},
        },
        {
            "strategy_id": "c_lower",
            "windows": {"FULL": {"official_any_prize_success_count": 1, "denominator": 3}},
        },
    ]

    assert [row["strategy_id"] for row in sorted(rows, key=_ranking_key)] == [
        "b_long",
        "a_long",
        "z_short",
        "c_lower",
    ]


def test_missing_cell_has_no_success_or_random_baseline() -> None:
    cell = _new_cell(
        {
            "result_status": "MISSING",
            "missing_reason": "HISTORICAL_CAUSAL_HISTORY_FINGERPRINT_MISMATCH",
        },
        expected_k=2,
    )

    assert cell.status == "MISSING"
    assert cell.success is None
    assert cell.probability is None


def test_complete_cell_rejects_conflicting_official_evaluations() -> None:
    with pytest.raises(IncrementalRankInputError, match="conflicts"):
        _new_cell(
            {
                "result_status": "COMPLETE",
                "replay_status": "COMPLETE",
                "replay_attempted": True,
                "target_outcome_excluded": True,
                "native_ticket_count": 2,
                "official_any_prize": True,
                "tickets": [
                    {"main_numbers": [1, 2, 3, 4, 5, 6]},
                    {"main_numbers": [7, 8, 9, 10, 11, 12]},
                ],
                "ticket_evaluations": [{"is_winner": False}, {"is_winner": False}],
            },
            expected_k=2,
        )
