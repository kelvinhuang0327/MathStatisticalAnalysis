"""Focused exact checks for the K20 r_max=5 joint residual envelope."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations, product
from math import comb
from typing import cast

from lottolab.research.b649_k20_r5_joint_residual_envelope_r1 import (
    EXPECTED_ANCHOR_INCIDENCE_TYPE_COUNT,
    JointMassState,
    analyze_r5_joint_residual_envelope,
    joint_s2_s3_frontier_segments,
    r5_anchor_types,
    residual_pair_floor,
    residual_s3_upper_bound,
    residual_union_reduction,
)

ANCHOR_A = (0, 1, 2, 3, 4, 5)
ANCHOR_B = (0, 1, 2, 3, 4, 6)
ANCHOR_SHARED = frozenset(range(5))
ANCHOR_A_ONLY = 5
ANCHOR_B_ONLY = 6
OUTSIDE = frozenset(range(7, 13))


def _signature(ticket: tuple[int, ...]) -> tuple[int, int, int, int]:
    return (
        sum(label in ANCHOR_SHARED for label in ticket),
        int(ANCHOR_A_ONLY in ticket),
        int(ANCHOR_B_ONLY in ticket),
        sum(label in OUTSIDE for label in ticket),
    )


def _wins(
    ticket: tuple[int, ...],
    draw: tuple[int, ...],
    special: int,
    outright_matches: int = 3,
) -> bool:
    matches = sum(label in draw for label in ticket)
    return matches >= outright_matches or (
        matches == outright_matches - 1 and special in ticket
    )


def _result() -> dict[str, object]:
    return analyze_r5_joint_residual_envelope()


@lru_cache(maxsize=1)
def _cached_result() -> dict[str, object]:
    return _result()


def test_r5_anchor_types_and_capacities_match_small_exhaustive_model() -> None:
    pool_size = 13
    tickets = tuple(combinations(range(pool_size), 6))
    expected = Counter(
        _signature(ticket)
        for ticket in tickets
        if ticket not in (ANCHOR_A, ANCHOR_B)
    )
    actual = r5_anchor_types(pool_size=pool_size)

    assert len(actual) == len(expected)
    assert {row.signature for row in actual} == set(expected)
    assert {
        row.signature: row.distinct_ticket_capacity for row in actual
    } == dict(expected)
    assert all(row.signature not in (ANCHOR_A, ANCHOR_B) for row in actual)


def test_residual_pair_floor_is_below_exhaustive_small_outcome_counts() -> None:
    first = (0, 1, 2, 7, 8, 9)
    second = (0, 1, 3, 7, 8, 9)
    third = (0, 1, 6, 7, 8, 9)
    outside_tickets = (first, second, third)
    outcomes = tuple(
        (draw, special)
        for draw in combinations(range(13), 6)
        for special in range(13)
        if special not in draw
    )

    for left, right in combinations(outside_tickets, 2):
        exact_residual_pair = sum(
            not _wins(ANCHOR_A, draw, special)
            and not _wins(ANCHOR_B, draw, special)
            and _wins(left, draw, special)
            and _wins(right, draw, special)
            for draw, special in outcomes
        )
        lower_bound = residual_pair_floor(
            _signature(left),
            _signature(right),
            anchor_overlap=5,
            pool_size=13,
            draw_size=6,
        )

        assert 0 <= lower_bound <= exact_residual_pair


def test_small_joint_moment_oracle_covers_s2_s3_and_union() -> None:
    outcome_count = 4
    for multiplicity_cap in range(1, 7):
        maximum_s2 = outcome_count * comb(multiplicity_cap, 2)
        exact_s3_by_s2: dict[int, int] = {}
        for multiplicities in product(
            range(multiplicity_cap + 1), repeat=outcome_count
        ):
            residual_s1 = sum(multiplicities)
            residual_s2 = sum(comb(value, 2) for value in multiplicities)
            residual_s3 = sum(comb(value, 3) for value in multiplicities)
            exact_union = sum(value > 0 for value in multiplicities)
            exact_s3_by_s2[residual_s2] = max(
                exact_s3_by_s2.get(residual_s2, 0), residual_s3
            )

            assert (
                residual_union_reduction(residual_s2, multiplicity_cap)
                <= residual_s1 - exact_union
            )
            assert residual_s3 <= residual_s3_upper_bound(
                residual_s2, multiplicity_cap
            )

        state = JointMassState(
            outside_pair_mass=0,
            minimum_s2=0,
            maximum_s2=maximum_s2,
            maximum_selected_seven_frequency=3 * multiplicity_cap,
            residual_multiplicity_cap=multiplicity_cap,
            maximum_s3_at_minimum_s2=0,
            maximum_s3_at_maximum_s2=residual_s3_upper_bound(
                maximum_s2, multiplicity_cap
            ),
            union_reduction=0,
        )
        frontier = joint_s2_s3_frontier_segments((state,))
        assert len(frontier) == 1
        segment = frontier[0]
        for residual_s2, exact_s3 in exact_s3_by_s2.items():
            assert segment.s2_start <= residual_s2 <= segment.s2_end
            assert residual_s3_upper_bound(
                residual_s2, segment.residual_multiplicity_cap
            ) >= exact_s3


def test_joint_frontier_keeps_s2_s3_states_mass_indexed() -> None:
    result = _cached_result()
    frontier_rows = cast(
        list[dict[str, object]], result["S2_S3_FRONTIER_BY_GOOD_COUNT"]
    )
    assert [row["GOOD_TICKET_COUNT"] for row in frontier_rows] == list(range(19))
    assert all(cast(list[dict[str, int]], row["S2_S3_FRONTIER"]) for row in frontier_rows)
    assert all(
        type(row["S2_S3_FRONTIER_SHA256"]) is str
        and row["S2_S3_FRONTIER_SHA256"]
        for row in frontier_rows
    )
    assert result["RESIDUAL_STATE_COUNT"] == sum(
        cast(int, row["RESIDUAL_STATE_COUNT"]) for row in frontier_rows
    )
    assert result["S2_S3_FRONTIER_SIZE"] == sum(
        cast(int, row["S2_S3_FRONTIER_SIZE"]) for row in frontier_rows
    )


def test_r5_census_certifies_a_strict_bound_and_milestone() -> None:
    result = _cached_result()
    bound_rows = cast(
        list[dict[str, object]], result["BOUND_BY_GOOD_TICKET_COUNT"]
    )

    assert result["ANCHOR_INCIDENCE_TYPE_COUNT"] == (
        EXPECTED_ANCHOR_INCIDENCE_TYPE_COUNT
    )
    assert result["COMPRESSED_ANCHOR_TYPE_CLASS_COUNT"] == 16
    assert result["FEASIBLE_TYPE_COUNT_VECTOR_COUNT"] == 33_352_207_770
    assert result["R5_BOUND"] == 349_009_248
    assert result["R5_STATUS"] == "TIGHTENED_OPEN"
    assert result["TASK_STATUS"] == "COMPLETED_SUCCESS_B"
    assert result["MILESTONE_MET"] is True
    assert result["INCUMBENT"] == 313_239_661
    assert result["LEAF_GAP"] == 35_769_587
    assert result["SOLVER_CERTIFIED_BOUND"] == result["R5_BOUND"]
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert len(bound_rows) == 19
