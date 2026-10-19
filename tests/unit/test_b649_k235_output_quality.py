"""Unit tests for B649 K2/K3/K5 output quality component (AC3, AC4, AC6)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from lottolab.research.b649_k235_output_quality import (
    evaluate_candidate_quality,
    partition_k_entries,
)

HISTORICAL_097_INPUT_ENV = "B649_K235_HISTORICAL_097_PREDICTION"


def _valid_tickets(k: int) -> list[list[int]]:
    return [list(range(start, start + 6)) for start in range(1, 6 * k + 1, 6)]


def _overlapping_tickets(k: int) -> list[list[int]]:
    tickets = _valid_tickets(k)
    tickets[1][0] = tickets[0][0]
    return tickets


def _synthetic_entries_by_k() -> dict[str, dict[str, list[dict[str, Any]]]]:
    accepted_ranks = {"k2": {1, 2}, "k3": {1, 3}, "k5": {1, 2}}
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for category, valid_ranks in accepted_ranks.items():
        k = int(category[1:])
        result[category] = {
            "entries": [
                {
                    "rank": rank,
                    "strategy_id": f"synthetic_{category}_rank_{rank}",
                    "tickets": (
                        _valid_tickets(k)
                        if rank in valid_ranks
                        else _overlapping_tickets(k)
                    ),
                }
                for rank in (1, 2, 3)
            ]
        }
    return result


def _assert_k235_quality_outcomes(payload: dict[str, Any]) -> None:
    expectations = {
        "k2": (2, [1, 2], [3], 5302152, 85900584),
        "k3": (3, [1, 3], [2], 7930128, 85900584),
        "k5": (5, [1, 2], [3], 13139880, 85900584),
    }
    total_accepted = 0
    total_rejected = 0

    for category, (k, accepted_ranks, rejected_ranks, numerator, denominator) in (
        expectations.items()
    ):
        accepted, rejected = partition_k_entries(payload[category]["entries"], k)
        fraction = f"{numerator}/{denominator}"
        assert [entry["rank"] for entry in accepted] == accepted_ranks
        assert [entry["rank"] for entry in rejected] == rejected_ranks

        for entry in accepted:
            evaluation = entry["quality_evaluation"]
            assert entry["quality_status"] == "ACCEPTED"
            assert evaluation["is_valid"] is True
            assert evaluation["unique_number_count"] == 6 * k
            assert evaluation["expected_unique_count"] == 6 * k
            assert entry["exact_coverage_fraction"] == fraction
            assert entry["coverage_probability"] == numerator / denominator
            assert evaluation["exact_numerator"] == numerator
            assert evaluation["exact_denominator"] == denominator

        for entry in rejected:
            evaluation = entry["quality_evaluation"]
            assert entry["quality_status"] == "REJECTED"
            assert evaluation["is_valid"] is False
            assert any(
                "CROSS_TICKET_OVERLAP" in reason
                for reason in entry["rejection_reasons"]
            )
            assert entry["exact_coverage_fraction"] is None
            assert entry["coverage_probability"] is None
            assert evaluation["exact_numerator"] is None
            assert evaluation["exact_denominator"] is None

        total_accepted += len(accepted)
        total_rejected += len(rejected)

    assert total_accepted == 6
    assert total_rejected == 3


def test_valid_disjoint_portfolios_pass_and_receive_exact_fractions() -> None:
    # K=2
    k2_tickets = [
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
    ]
    res_k2 = evaluate_candidate_quality(k2_tickets, 2)
    assert res_k2.is_valid is True
    assert res_k2.rejection_reasons == ()
    assert res_k2.exact_fraction == "5302152/85900584"
    assert res_k2.exact_numerator == 5302152
    assert res_k2.exact_denominator == 85900584
    assert res_k2.coverage_probability == 5302152 / 85900584

    # K=3
    k3_tickets = [
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
    ]
    res_k3 = evaluate_candidate_quality(k3_tickets, 3)
    assert res_k3.is_valid is True
    assert res_k3.exact_fraction == "7930128/85900584"
    assert res_k3.coverage_probability == 7930128 / 85900584

    # K=5
    k5_tickets = [
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
        [19, 20, 21, 22, 23, 24],
        [25, 26, 27, 28, 29, 30],
    ]
    res_k5 = evaluate_candidate_quality(k5_tickets, 5)
    assert res_k5.is_valid is True
    assert res_k5.exact_fraction == "13139880/85900584"
    assert res_k5.coverage_probability == 13139880 / 85900584


def test_rejects_wrong_ticket_count() -> None:
    # Expected 2 tickets, got 1
    res1 = evaluate_candidate_quality([[1, 2, 3, 4, 5, 6]], 2)
    assert res1.is_valid is False
    assert any("TICKET_COUNT_MISMATCH" in r for r in res1.rejection_reasons)
    assert res1.exact_fraction is None

    # Expected 2 tickets, got 3
    res3 = evaluate_candidate_quality(
        [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [13, 14, 15, 16, 17, 18]],
        2,
    )
    assert res3.is_valid is False
    assert any("TICKET_COUNT_MISMATCH" in r for r in res3.rejection_reasons)


def test_rejects_wrong_ticket_length() -> None:
    # Ticket has length 5 instead of 6
    tickets = [
        [1, 2, 3, 4, 5],
        [7, 8, 9, 10, 11, 12],
    ]
    res = evaluate_candidate_quality(tickets, 2)
    assert res.is_valid is False
    assert any("LENGTH_INVALID" in r for r in res.rejection_reasons)


def test_rejects_intra_ticket_duplicates() -> None:
    # Ticket has duplicate numbers
    tickets = [
        [1, 2, 3, 4, 5, 5],
        [7, 8, 9, 10, 11, 12],
    ]
    res = evaluate_candidate_quality(tickets, 2)
    assert res.is_valid is False
    assert any("DUPLICATE_NUMBERS" in r for r in res.rejection_reasons)


def test_rejects_cross_ticket_overlap() -> None:
    # Cross-ticket overlap on number 7
    tickets = [
        [1, 2, 3, 4, 5, 7],
        [7, 8, 9, 10, 11, 12],
    ]
    res = evaluate_candidate_quality(tickets, 2)
    assert res.is_valid is False
    assert any("CROSS_TICKET_OVERLAP" in r for r in res.rejection_reasons)


def test_rejects_out_of_range_numbers() -> None:
    # 0 is out of range
    res0 = evaluate_candidate_quality(
        [[0, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], 2
    )
    assert res0.is_valid is False
    assert any("NUMBER_OUT_OF_RANGE" in r for r in res0.rejection_reasons)

    # 50 is out of range
    res50 = evaluate_candidate_quality(
        [[1, 2, 3, 4, 5, 50], [7, 8, 9, 10, 11, 12]], 2
    )
    assert res50.is_valid is False
    assert any("NUMBER_OUT_OF_RANGE" in r for r in res50.rejection_reasons)


def test_rejects_wrong_types_including_bool_float_str() -> None:
    # Bool True (which is an int subclass in Python) must be rejected
    res_bool = evaluate_candidate_quality(
        [[True, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], 2
    )
    assert res_bool.is_valid is False
    assert any("INVALID_NUMBER_TYPE" in r for r in res_bool.rejection_reasons)

    # Float 3.0 must be rejected
    res_float = evaluate_candidate_quality(
        [[1, 2, 3.0, 4, 5, 6], [7, 8, 9, 10, 11, 12]], 2
    )
    assert res_float.is_valid is False
    assert any("INVALID_NUMBER_TYPE" in r for r in res_float.rejection_reasons)

    # String "5" must be rejected
    res_str = evaluate_candidate_quality(
        [[1, 2, 3, 4, "5", 6], [7, 8, 9, 10, 11, 12]], 2
    )
    assert res_str.is_valid is False
    assert any("INVALID_NUMBER_TYPE" in r for r in res_str.rejection_reasons)


def test_rejects_malformed_shapes_with_6k_distinct_numbers() -> None:
    # 12 distinct numbers, but shaped as [7 numbers] and [5 numbers]
    tickets_7_5 = [
        [1, 2, 3, 4, 5, 6, 7],
        [8, 9, 10, 11, 12],
    ]
    res_7_5 = evaluate_candidate_quality(tickets_7_5, 2)
    assert res_7_5.is_valid is False
    assert any("LENGTH_INVALID" in r for r in res_7_5.rejection_reasons)

    # 12 distinct numbers, but shaped as 3 tickets of 4 numbers
    tickets_4_4_4 = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
    ]
    res_4_4_4 = evaluate_candidate_quality(tickets_4_4_4, 2)
    assert res_4_4_4.is_valid is False
    assert any("TICKET_COUNT_MISMATCH" in r for r in res_4_4_4.rejection_reasons)


def test_portable_synthetic_k235_quality_classification() -> None:
    """Synthetic unit contract; it does not claim 097 historical performance."""
    _assert_k235_quality_outcomes(_synthetic_entries_by_k())


def test_local_integration_historical_097_golden() -> None:
    """Optional local integration check against an explicitly supplied 097 JSON."""
    fixture_value = os.environ.get(HISTORICAL_097_INPUT_ENV)
    if not fixture_value:
        pytest.skip(
            f"Set {HISTORICAL_097_INPUT_ENV} to run the private historical 097 Golden"
        )

    fixture_path = Path(fixture_value)
    assert fixture_path.is_file(), f"Historical input does not exist: {fixture_path}"
    payload: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    _assert_k235_quality_outcomes(payload)
