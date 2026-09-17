"""Focused tests for B649 rank-stability diagnostics."""

from __future__ import annotations

import pytest

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
)
from lottolab.research.b649_rank_stability import (
    compute_cross_budget_persistence,
    compute_loo_stability,
    compute_selection_boundary,
    compute_stream_support_matrix,
    compute_window_stability,
)

# ---------------------------------------------------------------------------
# A. Stream support matrix
# ---------------------------------------------------------------------------


def test_stream_support_matrix_is_deterministic() -> None:
    candidates = [
        StrategyCandidate("s1", [(1, 2, 3, 4, 5, 6)]),
        StrategyCandidate("s2", [(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)]),
    ]
    first = compute_stream_support_matrix(candidates)
    second = compute_stream_support_matrix(candidates)
    assert first == second


def test_duplicate_ticket_in_same_stream_does_not_multiply_stream_support() -> None:
    candidates = [
        StrategyCandidate(
            "s1",
            [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6)],
        ),
    ]
    matrix = compute_stream_support_matrix(candidates)
    row = matrix.ticket_rows[0]
    assert row.ticket == (1, 2, 3, 4, 5, 6)
    assert row.stream_support_count == 1
    assert row.supporting_streams == ("s1",)
    assert row.ticket_occurrence_count == 3


def test_ticket_frequency_and_number_frequency_are_distinct() -> None:
    candidates = [
        StrategyCandidate("s1", [(1, 2, 3, 4, 5, 6)]),
        StrategyCandidate("s2", [(1, 7, 8, 9, 10, 11)]),
    ]
    matrix = compute_stream_support_matrix(candidates)
    number_by_value = {row.number: row for row in matrix.number_rows}
    assert number_by_value[1].ticket_count == 2
    assert number_by_value[1].occurrence_count == 2
    assert number_by_value[2].ticket_count == 1
    assert number_by_value[2].occurrence_count == 1
    assert len(matrix.ticket_rows) == 2


def test_stream_support_matrix_is_input_order_invariant() -> None:
    c1 = StrategyCandidate("s1", [(6, 5, 4, 3, 2, 1), (1, 2, 3, 4, 5, 6)])
    c2 = StrategyCandidate("s2", [(12, 11, 10, 9, 8, 7)])
    forward = compute_stream_support_matrix([c1, c2])
    backward = compute_stream_support_matrix([c2, c1])
    assert forward == backward


# ---------------------------------------------------------------------------
# B. Cross-budget persistence
# ---------------------------------------------------------------------------


def test_cross_budget_persistence_tracks_independent_rankings() -> None:
    a: Ticket = (1, 2, 3, 4, 5, 6)
    b: Ticket = (7, 8, 9, 10, 11, 12)
    c: Ticket = (13, 14, 15, 16, 17, 18)
    rankings = {
        2: [a, b],
        3: [b, a, c],
        5: [a, b, c],
    }
    report = compute_cross_budget_persistence(rankings, budgets=(2, 3, 5))
    assert report.available_budgets == (2, 3, 5)
    rows = {row.ticket: row for row in report.ticket_rows}

    assert dict(rows[a].rank_by_budget) == {2: 1, 3: 2, 5: 1}
    assert rows[a].survival_count == 3
    assert rows[a].min_rank == 1
    assert rows[a].max_rank == 2
    assert rows[a].entry_budgets == ()
    assert rows[a].exit_budgets == ()

    assert dict(rows[b].rank_by_budget) == {2: 2, 3: 1, 5: 2}

    assert dict(rows[c].rank_by_budget) == {2: None, 3: 3, 5: 3}
    assert rows[c].entry_budgets == (3,)
    assert rows[c].exit_budgets == ()


def test_missing_budget_is_reported_unavailable() -> None:
    a: Ticket = (1, 2, 3, 4, 5, 6)
    rankings: dict[int, list[Ticket] | None] = {2: [a], 3: None}
    report = compute_cross_budget_persistence(rankings, budgets=(2, 3, 5))
    assert report.available_budgets == (2,)
    assert report.unavailable_budgets == (3, 5)


# ---------------------------------------------------------------------------
# C. Leave-one-stream-out stability
# ---------------------------------------------------------------------------


def test_loo_robust_case_has_zero_worst_rank_delta() -> None:
    core = [(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)]
    candidates = [StrategyCandidate(f"s{i}", list(core)) for i in range(1, 6)]
    report = compute_loo_stability(candidates, budgets=(2,))
    assert report.baseline_feasible_budgets == (2,)
    assert len(report.omissions) == 5
    for omission in report.omissions:
        result = omission.budgets[0]
        assert result.available
        assert result.worst_rank_delta == 0
        assert result.additions == ()
        assert result.removals == ()


def test_loo_sensitive_case_shows_nonzero_rank_delta_for_pivotal_stream() -> None:
    a: Ticket = (1, 2, 3, 4, 5, 6)
    b: Ticket = (20, 21, 22, 23, 24, 25)
    c: Ticket = (7, 8, 9, 10, 11, 12)
    d: Ticket = (13, 14, 15, 16, 17, 18)
    candidates = [
        StrategyCandidate("s_ab", [a, b]),
        StrategyCandidate("s_a", [a]),
        StrategyCandidate("s_b", [b]),
        StrategyCandidate("s_c", [c]),
        StrategyCandidate("s_d", [d]),
    ]
    report = compute_loo_stability(candidates, budgets=(3,))
    pivot = next(o for o in report.omissions if o.omitted_stream_id == "s_ab").budgets[0]
    assert pivot.available
    assert pivot.worst_rank_delta is not None and pivot.worst_rank_delta > 0
    assert pivot.removals is not None
    assert b in pivot.removals
    assert report.worst_perturbation_rank_delta is not None
    assert report.worst_perturbation_rank_delta > 0


def test_loo_insufficient_tickets_after_omission_is_unavailable_per_k() -> None:
    candidates = [
        StrategyCandidate("s1", [(1, 2, 3, 4, 5, 6)]),
        StrategyCandidate("s2", [(7, 8, 9, 10, 11, 12)]),
    ]
    report = compute_loo_stability(candidates, budgets=(2,))
    assert report.baseline_feasible_budgets == (2,)
    for omission in report.omissions:
        result = omission.budgets[0]
        assert result.budget == 2
        assert result.available is False
        assert result.top_k_retained is None
        assert result.worst_rank_delta is None


# ---------------------------------------------------------------------------
# D. Window stability
# ---------------------------------------------------------------------------


def test_window_stability_tracks_rank_swap_across_named_windows() -> None:
    a: Ticket = (1, 2, 3, 4, 5, 6)
    b: Ticket = (7, 8, 9, 10, 11, 12)
    c: Ticket = (13, 14, 15, 16, 17, 18)
    rankings = {
        "FULL": [a, b, c],
        "RECENT_750": [b, a, c],
        "RECENT_300": [a, b, c],
    }
    report = compute_window_stability(rankings)
    assert report.available_windows == ("FULL", "RECENT_750", "RECENT_300")
    rows = {row.ticket: row for row in report.ticket_rows}

    assert dict(rows[a].rank_by_window) == {"FULL": 1, "RECENT_750": 2, "RECENT_300": 1}
    assert dict(rows[b].rank_by_window) == {"FULL": 2, "RECENT_750": 1, "RECENT_300": 2}
    assert rows[a].min_rank == 1 and rows[a].max_rank == 2
    assert rows[a].rank_range == 1


def test_window_stability_missing_window_is_unavailable() -> None:
    a: Ticket = (1, 2, 3, 4, 5, 6)
    rankings: dict[str, list[Ticket] | None] = {
        "FULL": [a],
        "RECENT_750": [a],
        "RECENT_300": None,
    }
    report = compute_window_stability(rankings)
    assert report.available_windows == ("FULL", "RECENT_750")
    assert report.unavailable_windows == ("RECENT_300",)


# ---------------------------------------------------------------------------
# E. Selection boundary
# ---------------------------------------------------------------------------


def test_selection_boundary_exact_tie_without_quality() -> None:
    candidates = [
        StrategyCandidate("s1", [(1, 2, 3, 4, 5, 6)]),
        StrategyCandidate("s2", [(7, 8, 9, 10, 11, 12)]),
    ]
    report = compute_selection_boundary(candidates, budgets=(1, 2))
    pair = report.pairs[0]
    assert pair.available
    assert pair.lower_budget == 1 and pair.upper_budget == 2
    assert pair.support_difference == 0
    assert pair.same_support_band is True
    assert pair.exact_tie is True
    assert pair.quality_sum_difference is None


def test_selection_boundary_same_support_different_quality() -> None:
    a = (1, 2, 3, 4, 5, 6)
    b = (7, 8, 9, 10, 11, 12)
    candidates = [
        StrategyCandidate("s1", [a]),
        StrategyCandidate("s2", [a]),
        StrategyCandidate("s3", [b]),
        StrategyCandidate("s4", [b]),
    ]
    quality = {"s1": 0.9, "s2": 0.1, "s3": 0.9, "s4": 0.05}
    report = compute_selection_boundary(candidates, quality_by_strategy=quality, budgets=(1, 2))
    pair = report.pairs[0]
    assert pair.available
    assert pair.selected_boundary_ticket == a
    assert pair.first_excluded_ticket == b
    assert pair.support_difference == 0
    assert pair.same_support_band is True
    assert pair.exact_tie is False
    assert pair.quality_sum_difference == pytest.approx(0.05)


def test_selection_boundary_unavailable_pair_when_not_enough_tickets() -> None:
    candidates = [StrategyCandidate("s1", [(1, 2, 3, 4, 5, 6)])]
    report = compute_selection_boundary(candidates, budgets=(1, 2))
    pair = report.pairs[0]
    assert pair.available is False
    assert pair.selected_boundary_ticket is None
    assert pair.exact_tie is None


def test_rejects_malformed_ticket_consistently_with_selector() -> None:
    candidates = [StrategyCandidate("s1", [(1, 2, 3, 4, 5)])]
    with pytest.raises(ValueError):
        compute_stream_support_matrix(candidates)
