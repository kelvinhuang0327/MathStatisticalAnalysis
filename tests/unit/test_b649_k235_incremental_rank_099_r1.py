from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from typing import Protocol, cast

import pytest

import lottolab.research.b649_k235_incremental_rank_099_r1 as incremental_rank
from lottolab.research.b649_k235_incremental_rank_099_r1 import (
    IncrementalRankInputError,
)

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]
type JSONObject = dict[str, JSONValue]


class CellEvidence(Protocol):
    status: str
    success: bool | None
    probability: Fraction | None
    overlap: bool | None
    reason: str | None
    ticket_count_violation: bool


class CellEvidenceFactory(Protocol):
    def __call__(
        self,
        status: str,
        success: bool | None = None,
        probability: Fraction | None = None,
        overlap: bool | None = None,
        reason: str | None = None,
        ticket_count_violation: bool = False,
    ) -> CellEvidence: ...


class AdvanceWindowMetric(Protocol):
    def __call__(
        self,
        metric: Mapping[str, JSONValue],
        *,
        expected_prior_draws: Sequence[str],
        removed: Sequence[CellEvidence],
        added: Sequence[CellEvidence],
        first_draw_id: str,
        last_draw_id: str,
        target_period_count: int,
        requested_target_periods: int | None,
        strategy_id: str,
        display_name: str,
        k: int,
        prior_ranking_status: str,
        current_ranking_class: str,
    ) -> JSONObject: ...


class NewCell(Protocol):
    def __call__(self, row: Mapping[str, JSONValue], expected_k: int) -> CellEvidence: ...


class RankingKey(Protocol):
    def __call__(
        self, row: Mapping[str, JSONValue], window: str = "FULL"
    ) -> tuple[object, ...]: ...


def _private_helper(name: str) -> object:
    return getattr(incremental_rank, name)


fraction_payload = cast(
    Callable[[Fraction | None], JSONObject | None], _private_helper("_fraction_payload")
)
cell_evidence = cast(CellEvidenceFactory, _private_helper("_CellEvidence"))
advance_window_metric = cast(AdvanceWindowMetric, _private_helper("_advance_window_metric"))
new_cell = cast(NewCell, _private_helper("_new_cell"))
ranking_key = cast(RankingKey, _private_helper("_ranking_key"))


def _base_metric() -> JSONObject:
    return {
        "strategy_id": "strategy",
        "window": "50",
        "target_period_count": 5,
        "first_draw_id": "1",
        "last_draw_id": "5",
        "official_any_prize_success_count": 3,
        "denominator": 5,
        "historical_win_rate": fraction_payload(Fraction(3, 5)),
        "random_baseline_probability": fraction_payload(Fraction(1, 5)),
        "relative_random_gain": fraction_payload(Fraction(2, 5)),
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
    updated = advance_window_metric(
        _base_metric(),
        expected_prior_draws=["1", "2", "3", "4", "5"],
        removed=[
            cell_evidence("COMPLETE", True, Fraction(1, 10), False),
            cell_evidence("COMPLETE", True, Fraction(1, 5), True),
            cell_evidence("COMPLETE", False, Fraction(3, 10), False),
        ],
        added=[
            cell_evidence("COMPLETE", True, Fraction(2, 5), True),
            cell_evidence("FAILED", reason="execution error"),
            cell_evidence("MISSING", reason="unverified source version"),
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
    historical_win_rate = updated["historical_win_rate"]
    assert isinstance(historical_win_rate, dict)
    assert historical_win_rate["numerator"] == 2
    assert historical_win_rate["denominator"] == 3
    random_baseline_probability = updated["random_baseline_probability"]
    assert isinstance(random_baseline_probability, dict)
    assert random_baseline_probability["numerator"] == 4
    assert random_baseline_probability["denominator"] == 15
    relative_random_gain = updated["relative_random_gain"]
    assert isinstance(relative_random_gain, dict)
    assert relative_random_gain["numerator"] == 2
    assert relative_random_gain["denominator"] == 5
    assert updated["failed_period_count"] == 1
    assert updated["missing_period_count"] == 1
    assert updated["state_counts"] == {"OBSERVED": 3, "SYNTHETIC": 0, "MISSING": 2}
    assert updated["status"] == "PARTIAL"
    assert updated["random_probability_method_counts"] == {
        "EXACT_OVERLAPPING_PORTFOLIO": 1,
        "ZERO_OVERLAP_REFERENCE": 2,
    }


def test_full_ranking_key_uses_exact_rate_then_denominator_then_identity() -> None:
    rows: list[JSONObject] = [
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

    assert [row["strategy_id"] for row in sorted(rows, key=ranking_key)] == [
        "b_long",
        "a_long",
        "z_short",
        "c_lower",
    ]


def test_missing_cell_has_no_success_or_random_baseline() -> None:
    missing_row: JSONObject = {
        "result_status": "MISSING",
        "missing_reason": "HISTORICAL_CAUSAL_HISTORY_FINGERPRINT_MISMATCH",
    }
    cell = new_cell(missing_row, expected_k=2)

    assert cell.status == "MISSING"
    assert cell.success is None
    assert cell.probability is None


def test_complete_cell_rejects_conflicting_official_evaluations() -> None:
    with pytest.raises(IncrementalRankInputError, match="conflicts"):
        complete_row: JSONObject = {
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
        }
        new_cell(complete_row, expected_k=2)
