"""K=10 minimum-overlap exhaustive search: derivation, reconstruction, exact scores."""

from __future__ import annotations

from fractions import Fraction

import pytest

from lottolab.application.b649_sealed_geometry_portfolio import SEALED_GEOMETRY_PORTFOLIOS
from lottolab.research.b649_k10_min_overlap_exhaustive_r1 import (
    BASELINE_FRACTION,
    RECORD_PATH,
    assert_k10_minimum_profile,
    canonical_portfolio_sha256,
    class_set_sha256,
    comparison_label,
    enumerate_small_multigraphs,
    graph_is_admissible,
    minimum_overlap_derivation,
    overlap_mass,
    pair_intersection_histogram,
    parse_multig_line,
    permute_tickets,
    portfolio_from_edges,
    produces_duplicate_ticket,
    relabel_numbers,
    score_portfolio,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

PARALLEL = ((0, 1, 2), (2, 3, 3), (4, 5, 1), (6, 7, 5))
# 2+3+1+5 = 11 edges. Degrees: 0:2, 1:2, 2:3, 3:3, 4:1, 5:1, 6:5, 7:5, 8:0, 9:0.


def test_minimum_overlap_profile_is_eleven_doubles() -> None:
    derived = assert_k10_minimum_profile()
    assert derived["minimum_mass"] == 11
    assert derived["histogram"] == {"1": 38, "2": 11}
    assert derived["profile_unique"] is True
    smaller = minimum_overlap_derivation(pool_size=9, draw_size=3, ticket_count=4)
    assert (
        smaller["minimum_mass"]
        == minimum_overlap_derivation(pool_size=9, draw_size=3, ticket_count=4)["minimum_mass"]
    )


def test_parallel_edges_reconstruct_distinct_legal_tickets() -> None:
    edges = PARALLEL
    assert graph_is_admissible(edges)
    assert not produces_duplicate_ticket(edges)
    portfolio = portfolio_from_edges(edges)
    assert len(portfolio) == 10
    assert len(set(portfolio)) == 10
    for ticket in portfolio:
        assert len(ticket) == 6 and len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)
    assert overlap_mass(portfolio) == 11
    histogram = pair_intersection_histogram(portfolio)
    assert histogram["2"] == 1
    assert histogram["3"] == 1
    assert histogram["5"] == 1
    duplicate = ((0, 1, 6), (2, 3, 5))
    assert produces_duplicate_ticket(duplicate)
    with pytest.raises(ValueError, match="duplicate"):
        portfolio_from_edges(duplicate)


def test_label_and_ticket_permutation_keep_the_exact_fraction() -> None:
    portfolio = portfolio_from_edges(PARALLEL)
    permutation = {number: ((number + 10 - 1) % 49) + 1 for number in range(1, 50)}
    relabeled = relabel_numbers(portfolio, permutation)
    order = (3, 1, 4, 0, 2, 9, 8, 7, 6, 5)
    reordered = permute_tickets(portfolio, order)
    original = score_portfolio(portfolio)
    assert evaluate_portfolio(relabeled).official_any_prize == original.official_any_prize
    assert evaluate_portfolio(reordered).official_any_prize == original.official_any_prize


def test_small_enumerator_digest_is_stable_and_canonical() -> None:
    first = enumerate_small_multigraphs(5, 4, 3)
    second = enumerate_small_multigraphs(5, 4, 3)
    assert first == second
    assert class_set_sha256(first) == class_set_sha256(second)
    assert len(first) == len(set(first))
    line = "5 2  0 1 2 2 3 2"
    group, edges = parse_multig_line(line)
    assert group is None
    assert edges == ((0, 1, 2), (2, 3, 2))
    assert graph_is_admissible(edges, vertex_count=5, edge_count=4, max_degree=3)


def test_record_matches_canonical_evaluator() -> None:
    import json

    assert RECORD_PATH.is_file(), RECORD_PATH
    certificate = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    record = certificate["shells"]["mass_11"]["historical_record"]
    assert record["class_set_sha256_run_1"] == record["class_set_sha256_run_2"]
    assert record["labelg_class_set_sha256_run_1"] == record["labelg_class_set_sha256_run_2"]
    assert record["parallel_edges_included"] is True
    assert record["global_optimum_status"] == "UNKNOWN"
    assert record["next_task_started"] is False
    assert record["final_decision"] in {
        "STRICT_IMPROVEMENT_FOUND",
        "NO_IMPROVEMENT_WITHIN_EXHAUSTED_MIN_OVERLAP_K10_FAMILY",
        "BOUNDED_SEARCH_ONLY",
    }
    if record["final_decision"] != "BOUNDED_SEARCH_ONLY":
        assert record["exhaustive_status"] == "PROVEN"
        assert record["exact_evaluation_count"] == record["unlabeled_class_count"]
    else:
        assert record["exhaustive_status"] == "NOT_PROVEN"
    best = tuple(tuple(ticket) for ticket in record["best_tickets"])
    got = evaluate_portfolio(best).official_any_prize
    assert got == Fraction(record["best_exact"])
    assert comparison_label(got.numerator, got.denominator) == (
        "STRICT_IMPROVEMENT"
        if got > Fraction(*BASELINE_FRACTION)
        else "TIE"
        if got == Fraction(*BASELINE_FRACTION)
        else "NO_IMPROVEMENT"
    )
    assert canonical_portfolio_sha256(best) == record["best_portfolio_sha256"]
    if record["baseline_in_family"]:
        assert record["hard_div_exact"] == f"{BASELINE_FRACTION[0]}/{BASELINE_FRACTION[1]}"
        tickets = SEALED_GEOMETRY_PORTFOLIOS[10].tickets
        assert canonical_portfolio_sha256(tickets) == record["hard_div_sha256"]
        assert evaluate_portfolio(tickets).official_any_prize == Fraction(*BASELINE_FRACTION)
        assert overlap_mass(tickets) == 11
