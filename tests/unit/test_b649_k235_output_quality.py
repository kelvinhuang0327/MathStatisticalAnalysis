"""Unit tests for B649 K2/K3/K5 output quality component (AC3, AC4, AC6)."""

from __future__ import annotations

import json
from pathlib import Path

from lottolab.research.b649_k235_output_quality import (
    evaluate_candidate_quality,
    partition_k_entries,
)

FIXTURE_097_PATH = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/"
    "BIGLOTTO_115000096_K2_K3_K5_TOP3_115000097_PREDICTION_R1/predictions_115000097.json"
)


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


def test_ac4_predictions_115000097_fixture_evaluation() -> None:
    """AC4 requirement:

    Evaluating predictions_115000097.json yields:
    K2: accept rank 1, 2; reject rank 3
    K3: accept rank 1, 3; reject rank 2
    K5: accept rank 1, 2; reject rank 3
    Total: 6 accepted, 3 rejected.
    """
    assert FIXTURE_097_PATH.exists()
    payload = json.loads(FIXTURE_097_PATH.read_text(encoding="utf-8"))

    # K2
    k2_acc, k2_rej = partition_k_entries(payload["k2"]["entries"], 2)
    assert [e["rank"] for e in k2_acc] == [1, 2]
    assert [e["rank"] for e in k2_rej] == [3]
    assert len(k2_acc) == 2
    assert len(k2_rej) == 1
    # Check exact coverage fraction assigned to accepted K2
    for e in k2_acc:
        assert e["exact_coverage_fraction"] == "5302152/85900584"
    for e in k2_rej:
        assert e["exact_coverage_fraction"] is None

    # K3
    k3_acc, k3_rej = partition_k_entries(payload["k3"]["entries"], 3)
    assert [e["rank"] for e in k3_acc] == [1, 3]
    assert [e["rank"] for e in k3_rej] == [2]
    assert len(k3_acc) == 2
    assert len(k3_rej) == 1
    for e in k3_acc:
        assert e["exact_coverage_fraction"] == "7930128/85900584"
    for e in k3_rej:
        assert e["exact_coverage_fraction"] is None

    # K5
    k5_acc, k5_rej = partition_k_entries(payload["k5"]["entries"], 5)
    assert [e["rank"] for e in k5_acc] == [1, 2]
    assert [e["rank"] for e in k5_rej] == [3]
    assert len(k5_acc) == 2
    assert len(k5_rej) == 1
    for e in k5_acc:
        assert e["exact_coverage_fraction"] == "13139880/85900584"
    for e in k5_rej:
        assert e["exact_coverage_fraction"] is None

    total_acc = len(k2_acc) + len(k3_acc) + len(k5_acc)
    total_rej = len(k2_rej) + len(k3_rej) + len(k5_rej)
    assert total_acc == 6
    assert total_rej == 3
