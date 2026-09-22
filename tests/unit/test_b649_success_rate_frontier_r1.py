"""Exact OFFICIAL_ANY_PRIZE checks for the fixed-K frontier prototypes.

Fractions come from the canonical evaluator. The locked baselines are the
HARD_DIV radius-2 portfolios, not the older sealed 1.0.0 buckets.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.research.b649_success_rate_frontier_r1 import (
    FAMILY_STATUS,
    NOVELTY_STATUS,
    affine_shortened_portfolio,
    canonical_portfolio_sha256,
    chord_inequality_holds,
    comparison_label,
    disjoint_packing,
    load_frontier_record,
    minimum_pair_incidence,
    one_number_exchange,
    pair_incidence,
    pairwise_winning_intersections,
    render_handoff,
    triangle_free_k10,
    two_ticket_union_outcomes,
)

REQUIRED_FAMILIES = (
    "greedy overlap minimization",
    "HARD_DIV / pairwise overlap",
    "exact 1-exchange",
    "multi-start",
    "tabu search",
    "simulated annealing",
    "set cover",
    "ILP / MIP",
    "CP / CP-SAT",
    "ALNS / LNS",
    "ACO",
    "GRASP",
    "genetic / evolutionary search",
    "Lagrangian methods",
    "covering-design methods",
    "GKP / known covering bounds",
    "path relinking",
    "local-search neighborhoods",
    "Fourier / spectral methods",
    "portfolio selectors / ranking methods",
    "prediction ensembles / Hedge / Fixed-Share / DMA / regime weighting",
)
LOCKED_BASELINES = {
    5: Fraction(547495, 3579191),
    10: Fraction(536005, 1827672),
    20: Fraction(22345625, 42950292),
}
HANDOFF_PARTS = (
    "1. CURRENT BEST BASELINE",
    "2. DISCOVERY COVERAGE",
    "3. TOP NEW METHODS",
    "4. STRICT IMPROVEMENTS FOUND",
    "5. USEFUL NEGATIVE RESULTS",
    "6. TRUE PRE-DRAW SIGNAL OPPORTUNITIES",
    "7. BEST OPEN-SOURCE ASSETS TO IMPORT",
    "8. NEXT 3 IMPLEMENTATION TASKS",
    "9. SINGLE HIGHEST-VALUE NEXT TASK",
)


@pytest.fixture(scope="module")
def record() -> dict:
    return load_frontier_record()


@pytest.fixture(scope="module")
def draws():
    return all_main_draw_masks(49, 6)


def _tickets(row: dict) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(ticket) for ticket in row["tickets"])


def test_inventory_taxonomy_and_saturation(record: dict) -> None:
    families = record["families"]
    by_name = [row["family"] for row in families]
    assert by_name == list(REQUIRED_FAMILIES)
    assert len(set(by_name)) == len(REQUIRED_FAMILIES)
    for row in families:
        assert row["status"] in FAMILY_STATUS

    taxonomy = record["taxonomy"]
    assert [row["id"] for row in taxonomy] == list("ABCDEFGHIJKLM")
    searched_all = all(row["searched"] is True for row in taxonomy)
    assert searched_all
    remaining = record["remaining_high_value_families"]
    assert record["discovery_saturation"] == "NOT_REACHED"
    assert remaining
    if record["discovery_saturation"] == "REACHED":
        assert searched_all and not remaining

    assert {row["status"] for row in record["section_m"]} == {"OUT_OF_PRIMARY_SCOPE"}
    assert len(record["section_m"]) == 7

    prototyped = [row for row in record["methods"] if row["prototyped"] is True]
    assert prototyped
    assert len({row["method_id"] for row in prototyped}) == 3
    for row in record["methods"]:
        assert row["novelty_status"] in NOVELTY_STATUS
        if row["prototyped"] is True:
            assert row["novelty_status"] in {"NEW", "STRONGER_VARIANT"}


def test_pairwise_chord_matches_the_canonical_evaluator(draws) -> None:
    intersections = pairwise_winning_intersections()
    pairs = (
        (0, ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))),
        (1, ((1, 2, 3, 4, 5, 6), (6, 7, 8, 9, 10, 11))),
    )
    for intersection, pair in pairs:
        result = evaluate_portfolio(pair, draws=draws)
        assert two_ticket_union_outcomes(intersection) == result.official_any_prize_outcome_count
        single = evaluate_portfolio(((1, 2, 3, 4, 5, 6),), draws=draws)
        expected_intersection = (
            2 * single.official_any_prize_outcome_count - result.official_any_prize_outcome_count
        )
        assert intersections[intersection] == expected_intersection
    assert chord_inequality_holds(intersections)
    assert intersections[2] > intersections[0] + 2 * (intersections[1] - intersections[0])


def test_baselines_and_prototypes_match_the_canonical_evaluator(record: dict, draws) -> None:
    for row in record["baselines"]:
        portfolio = _tickets(row)
        _assert_legal(portfolio, row["k"])
        result = evaluate_portfolio(portfolio, draws=draws)
        assert result.official_any_prize == Fraction(row["official_any_prize"])
        assert result.official_any_prize == LOCKED_BASELINES[row["k"]]
        assert canonical_portfolio_sha256(portfolio) == row["portfolio_sha256"]
        assert pair_incidence(portfolio) == minimum_pair_incidence(row["k"])
        assert row["triple_structure"]["edge_triangles"] >= 0
        assert "number_frequency" in row
        assert set(row["number_frequency"]) != set(row["intersection_histogram"])

    constructed = {
        canonical_portfolio_sha256(disjoint_packing(5)),
        canonical_portfolio_sha256(triangle_free_k10()),
        canonical_portfolio_sha256(affine_shortened_portfolio(10)),
        canonical_portfolio_sha256(affine_shortened_portfolio(20)),
        canonical_portfolio_sha256(
            one_number_exchange(
                _tickets(next(row for row in record["baselines"] if row["k"] == 10)),
                0,
                21,
                3,
            )
        ),
    }
    stored_hashes = {row["portfolio_sha256"] for row in record["prototypes"]}
    assert constructed <= stored_hashes

    for row in record["prototypes"]:
        portfolio = _tickets(row)
        _assert_legal(portfolio, row["k"])
        result = evaluate_portfolio(portfolio, draws=draws)
        assert result.official_any_prize == Fraction(row["official_any_prize"])
        assert row["comparison_label"] == comparison_label(
            result.official_any_prize.numerator,
            result.official_any_prize.denominator,
            row["k"],
        )
        assert comparison_label(
            result.official_any_prize.numerator,
            result.official_any_prize.denominator,
            row["k"],
        ) == (
            "STRICT_IMPROVEMENT"
            if result.official_any_prize > LOCKED_BASELINES[row["k"]]
            else "TIE"
            if result.official_any_prize == LOCKED_BASELINES[row["k"]]
            else "NO_IMPROVEMENT"
        )
        assert row["objective_evaluations"] >= 1
        assert row["restarts"] >= 1
        assert row["parallelism"] == 1
        assert "cpu_time_sec" in row and "wall_time_sec" in row
        assert row["triple_structure"]
        assert row["number_frequency"]
        assert row["intersection_histogram"]


def test_handoff_has_one_primary_task_and_no_forbidden_claims(record: dict) -> None:
    text = render_handoff(record)
    for part in HANDOFF_PARTS:
        assert text.count(part) == 1
    section_9 = text.split("9. SINGLE HIGHEST-VALUE NEXT TASK", maxsplit=1)[1].strip()
    assert section_9 == record["primary_next_task"]
    assert section_9.count("\n") == 0
    assert len(record["next_tasks"]) == 3
    for forbidden in ("GLOBAL_OPTIMUM", "PREDICTIVE_EDGE", "OOS_SUCCESS"):
        assert forbidden not in text
    improvements = [
        row for row in record["prototypes"] if row["comparison_label"] == "STRICT_IMPROVEMENT"
    ]
    assert improvements == []
    for row in record["baselines"]:
        assert row["official_any_prize"] in text
        assert str(row["triple_structure"]) in text


def _assert_legal(portfolio: tuple[tuple[int, ...], ...], k: int) -> None:
    assert len(portfolio) == k
    assert len(set(portfolio)) == k
    for ticket in portfolio:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(type(number) is int and 1 <= number <= 49 for number in ticket)
        assert ticket == tuple(sorted(ticket))
