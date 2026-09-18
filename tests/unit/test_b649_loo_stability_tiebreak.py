"""Frozen ordering contract and outcome-free integration over synthetic tickets."""

from __future__ import annotations

from itertools import permutations

import pytest

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.research.b649_loo_stability_tiebreak import (
    BUDGETS,
    METHOD_ID,
    LooTicketRank,
    build_loo_stability_tiebreak,
    frozen_sort_key,
)
from lottolab.research.b649_rank_stability import compute_loo_stability

A: Ticket = (1, 2, 3, 4, 5, 6)
B: Ticket = (7, 8, 9, 10, 11, 12)
C: Ticket = (13, 14, 15, 16, 17, 18)
D: Ticket = (19, 20, 21, 22, 23, 24)
E: Ticket = (25, 26, 27, 28, 29, 30)


def _equal_support_pool() -> list[StrategyCandidate]:
    return [
        StrategyCandidate("s1", [A]),
        StrategyCandidate("s2", [A]),
        StrategyCandidate("s3", [B, C, D]),
        StrategyCandidate("s4", [B, C, D]),
    ]


@pytest.mark.parametrize(
    ("preferred", "other"),
    [
        ((3, 1, 9.0, 10, B), (2, 4, 1.0, 1, A)),
        ((2, 4, 9.0, 10, B), (2, 3, 1.0, 1, A)),
        ((2, 4, 2.0, 10, B), (2, 4, 3.0, 3, A)),
        ((2, 4, 2.0, 3, B), (2, 4, 2.0, 4, A)),
        ((2, 4, 2.0, 3, A), (2, 4, 2.0, 3, B)),
    ],
    ids=["support", "survival", "median", "worst", "lexical"],
)
def test_each_frozen_dimension_dominates_every_later_dimension(
    preferred: tuple[int, int, float, int, Ticket],
    other: tuple[int, int, float, int, Ticket],
) -> None:
    # Counterfactual metric rows test the key itself. Full raw-majority LOO
    # cannot yield different survival counts within an equal-support band.
    def row(values: tuple[int, int, float, int, Ticket]) -> LooTicketRank:
        support, survival, median_rank, worst_rank, ticket = values
        return LooTicketRank(ticket, support, survival, median_rank, worst_rank, ())

    first, second = row(preferred), row(other)
    assert sorted((second, first), key=frozen_sort_key) == [first, second]


def test_higher_support_wins_despite_worse_loo_median_and_worst_rank() -> None:
    report = build_loo_stability_tiebreak(
        [
            StrategyCandidate("s1", [A, E]),
            StrategyCandidate("s2", [A, E]),
            StrategyCandidate("s3", [B, C, D, E]),
            StrategyCandidate("s4", [B, C, D]),
        ]
    )
    rows = {row.ticket: row for row in report.ticket_rows}
    assert rows[E].distinct_stream_support == 3
    assert rows[B].distinct_stream_support == 2
    assert rows[E].loo_median_rank == 3.0 > rows[B].loo_median_rank == 2.0
    assert rows[E].loo_worst_rank == 4 > rows[B].loo_worst_rank == 3
    assert report.ranking[0] == E
    supports = [row.distinct_stream_support for row in report.ticket_rows]
    assert supports == sorted(supports, reverse=True)


def test_median_then_worst_rank_reorders_only_the_equal_support_band() -> None:
    pool = _equal_support_pool()
    report = build_loo_stability_tiebreak(pool)
    rows = {row.ticket: row for row in report.ticket_rows}
    assert build_portfolio(pool, {}, bucket_sizes=(4,))[4] == [A, B, C, D]
    assert {row.distinct_stream_support for row in report.ticket_rows} == {2}
    assert {row.loo_survival for row in report.ticket_rows} == {4}
    assert dict(rows[A].penalized_rank_by_omission) == {"s1": 4, "s2": 4, "s3": 1, "s4": 1}
    assert dict(rows[B].penalized_rank_by_omission) == {"s1": 1, "s2": 1, "s3": 2, "s4": 2}
    assert rows[B].loo_median_rank == 1.5
    assert rows[A].loo_median_rank == rows[C].loo_median_rank == 2.5
    assert rows[C].loo_worst_rank == 3 < rows[A].loo_worst_rank == 4
    assert report.ranking == (B, C, A, D)


def test_omission_ranks_agree_with_existing_diagnostics_deltas() -> None:
    pool = _equal_support_pool()
    report = build_loo_stability_tiebreak(pool)
    diagnostics = compute_loo_stability(pool, budgets=(4,))
    baseline = {ticket: rank for rank, ticket in enumerate((A, B, C, D), start=1)}
    for omission, diagnostic in zip(report.omissions, diagnostics.omissions, strict=True):
        assert omission.omitted_stream_id == diagnostic.omitted_stream_id
        result = diagnostic.budgets[0]
        assert result.available
        assert result.comparable_rank_deltas == tuple(
            sorted(
                (ticket, rank - baseline[ticket])
                for rank, ticket in enumerate(omission.ranking, start=1)
            )
        )


def test_missing_occurrence_uses_each_omissions_observed_count_plus_one() -> None:
    report = build_loo_stability_tiebreak(
        [StrategyCandidate("a", [A, B]), StrategyCandidate("b", [C])]
    )
    rows = {row.ticket: row for row in report.ticket_rows}
    assert [(o.omitted_stream_id, o.observed_distinct_ticket_count) for o in report.omissions] == [
        ("a", 1),
        ("b", 2),
    ]
    assert rows[A].penalized_rank_by_omission == (("a", 2), ("b", 1))
    assert rows[B].penalized_rank_by_omission == (("a", 2), ("b", 2))
    assert rows[C].penalized_rank_by_omission == (("a", 1), ("b", 3))
    assert {row.loo_survival for row in report.ticket_rows} == {1}
    assert rows[A].loo_median_rank == 1.5
    assert rows[C].loo_median_rank == 2.0
    assert rows[C].loo_worst_rank == 3


def test_empty_omission_has_penalty_one_and_lexical_final_tie_break() -> None:
    report = build_loo_stability_tiebreak([StrategyCandidate("only", [B, A])])
    assert report.omissions[0].ranking == ()
    assert report.omissions[0].observed_distinct_ticket_count == 0
    assert report.ranking == (A, B)
    for row in report.ticket_rows:
        assert row.loo_survival == 0
        assert row.loo_median_rank == row.loo_worst_rank == 1
        assert row.penalized_rank_by_omission == (("only", 1),)


def test_duplicate_records_and_ticket_occurrences_do_not_multiply_support() -> None:
    canonical = [StrategyCandidate("s1", [A, B]), StrategyCandidate("s2", [B, C])]
    repeated = [
        StrategyCandidate("s1", [A, tuple(reversed(A)), B]),
        StrategyCandidate("s1", [A]),
        StrategyCandidate("s2", [B, C]),
    ]
    report = build_loo_stability_tiebreak(repeated)
    assert report == build_loo_stability_tiebreak(canonical)
    assert len(report.omissions) == 2
    rows = {row.ticket: row for row in report.ticket_rows}
    assert rows[A].distinct_stream_support == rows[C].distinct_stream_support == 1
    assert rows[B].distinct_stream_support == 2
    assert rows[A].loo_survival == rows[C].loo_survival == 1
    assert rows[B].loo_survival == 2
    assert report.omissions[0].ranking == (B, C)


def test_equivalent_stream_ticket_and_number_permutations_have_identical_outputs() -> None:
    pool = _equal_support_pool()
    expected = build_loo_stability_tiebreak(pool)
    for permutation in permutations(pool):
        permuted = [
            StrategyCandidate(
                candidate.strategy_id,
                [tuple(reversed(ticket)) for ticket in reversed(candidate.tickets)],
            )
            for candidate in permutation
        ]
        before = [(candidate.strategy_id, tuple(candidate.tickets)) for candidate in permuted]
        assert build_loo_stability_tiebreak(permuted) == expected
        assert [
            (candidate.strategy_id, tuple(candidate.tickets)) for candidate in permuted
        ] == before


def test_all_five_budgets_are_prefixes_of_one_complete_order() -> None:
    tickets = tuple((1, 2, 3, 4, 5, last) for last in range(6, 28))
    report = build_loo_stability_tiebreak(
        [StrategyCandidate("s1", tickets), StrategyCandidate("s2", tickets)]
    )
    assert report.method_id == METHOD_ID == "LOO_STABILITY_TIEBREAK_V1"
    assert report.ranking == tickets
    assert len(report.ranking) == 22  # The total order and LOO ranks are not capped at K20.
    assert all(omission.ranking == tickets for omission in report.omissions)
    assert [result.budget for result in report.budgets] == [2, 3, 5, 10, 20]
    for result in report.budgets:
        assert result.status == "AVAILABLE"
        assert result.tickets == tickets[: result.budget]
    assert report.ticket_rows[-1].loo_median_rank == report.ticket_rows[-1].loo_worst_rank == 22


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 5, 9, 10, 19, 20])
def test_insufficient_distinct_ticket_counts_are_unavailable_per_k(count: int) -> None:
    tickets = [(1, 2, 3, 4, 5, last) for last in range(6, 6 + count)]
    report = build_loo_stability_tiebreak([StrategyCandidate("s", tickets * 2)])
    assert len(report.ranking) == count
    assert tuple(result.budget for result in report.budgets) == BUDGETS
    for result in report.budgets:
        if result.budget > count:
            assert result.status == "UNAVAILABLE"
            assert result.tickets is None
        else:
            assert result.status == "AVAILABLE"
            assert result.tickets == report.ranking[: result.budget]


def test_no_streams_returns_empty_ranking_and_all_budgets_unavailable() -> None:
    report = build_loo_stability_tiebreak([])
    assert report.ranking == report.ticket_rows == report.omissions == ()
    assert len(report.budgets) == 5
    assert all(
        result.status == "UNAVAILABLE" and result.tickets is None for result in report.budgets
    )


def test_empty_stream_still_has_one_omission_run() -> None:
    report = build_loo_stability_tiebreak(
        [StrategyCandidate("empty", []), StrategyCandidate("only", [A])]
    )
    row = report.ticket_rows[0]
    assert row.distinct_stream_support == row.loo_survival == 1
    assert row.penalized_rank_by_omission == (("empty", 1), ("only", 1))
    assert [omission.omitted_stream_id for omission in report.omissions] == ["empty", "only"]


def test_only_strategy_id_and_tickets_are_read_never_outcomes_or_results() -> None:
    accessed: set[str] = set()

    class PreDrawOnlyCandidate(StrategyCandidate):
        def __getattribute__(self, name: str) -> object:
            assert name in {"strategy_id", "tickets"}, f"forbidden candidate field read: {name}"
            accessed.add(name)
            return super().__getattribute__(name)

    guarded = [
        PreDrawOnlyCandidate(candidate.strategy_id, candidate.tickets)
        for candidate in _equal_support_pool()
    ]
    assert build_loo_stability_tiebreak(guarded) == build_loo_stability_tiebreak(
        _equal_support_pool()
    )
    assert accessed == {"strategy_id", "tickets"}


@pytest.mark.parametrize("ticket", [(1, 2, 3, 4, 5), (1, 2, 3, 4, 5, 5)])
def test_malformed_tickets_preserve_existing_validation(ticket: Ticket) -> None:
    with pytest.raises(ValueError, match="invalid ticket"):
        build_loo_stability_tiebreak([StrategyCandidate("s", [ticket])])
