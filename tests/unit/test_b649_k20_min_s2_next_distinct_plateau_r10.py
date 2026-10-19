"""Focused proof and small-oracle checks for the R10 minimum-S2 plateau."""

from __future__ import annotations

import json
from itertools import combinations, pairwise
from math import ceil, comb
from pathlib import Path
from typing import Any

from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_REUSED_S4_LOWER_BOUND,
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
    support_motif_signature,
    validate_k20_support_realization,
)
from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from lottolab.research.b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    coarse_profile_envelope,
    erdos_gallai_first_violation,
)
from lottolab.research.b649_k20_min_s2_next_distinct_plateau_r10 import (
    CURRENT_PLATEAU,
    FIRST_UNPROCESSED_PROFILE,
    PLATEAU_BOUND,
    PLATEAU_WEDGE_COUNT,
    SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND,
    compact_top_plateau_result,
    enumerate_current_top_plateau,
    find_next_distinct_profile,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_INCUMBENT,
    K20_TRIPLE_SUPPORT_COUNT,
    linear_triple_degree_sequence_passes_pair_capacity,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
    s3_upper_bound_from_wedges,
)

RESULT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-next-distinct-plateau-r10-result.json"
)

EXPECTED_PLATEAU = (
    (6, 6, 6, 6, 6, 6, 6, 5, 4, 4, 4, 4, 1, 1, 1, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 6, 6, 5, 4, 4, 4, 3, 3, 1, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 6, 5, 5, 5, 4, 4, 4, 2, 1, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 3, 2, 1, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 4, 3, 0, 0, 0, 0, 0, 0, 0),
)


def test_unrealizable_profile_compacts_without_witness_rows() -> None:
    profile = list(FIRST_UNPROCESSED_PROFILE)
    result = compact_top_plateau_result(
        {
            "PROFILE_BOUNDS": [
                {
                    "PROFILE": profile,
                    "REALIZABILITY": "UNREALIZABLE",
                    "SUPPORT_SOLVER_STATUS": "INFEASIBLE",
                }
            ]
        }
    )

    assert result["PROFILE_BOUNDS"] == [
        {
            "PROFILE": profile,
            "REALIZABILITY": "UNREALIZABLE",
            "SUPPORT_SOLVER_STATUS": "INFEASIBLE",
        }
    ]


def test_ranked_plateau_membership_is_deterministic_and_bounded() -> None:
    plateau = enumerate_current_top_plateau()

    assert plateau.profiles == EXPECTED_PLATEAU == CURRENT_PLATEAU
    assert plateau.profiles[0] == FIRST_UNPROCESSED_PROFILE
    assert all(
        coarse_profile_envelope(profile).family_upper_bound == PLATEAU_BOUND
        for profile in plateau.profiles
    )
    assert plateau.complete_profiles_examined == 6
    assert plateau.pair_capacity_profiles_checked == len(plateau.profiles) == 6
    assert plateau.complete_profiles_examined < 4_850


def test_coarse_family_bound_is_monotone_below_the_plateau() -> None:
    family_bounds = tuple(
        K20_S1
        - K20_S2
        + s3_upper_bound_from_wedges(wedge_count)[1]
        - (4 * K20_REUSED_S4_LOWER_BOUND) // 7
        for wedge_count in range(66, PLATEAU_WEDGE_COUNT + 1)
    )

    assert all(first < second for first, second in pairwise(family_bounds))
    assert family_bounds[-2] == 313_733_608
    assert family_bounds[-1] == PLATEAU_BOUND


def _read_result() -> dict[str, Any]:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def _overlap_edges(
    triples: tuple[tuple[int, int, int], ...],
    doubles: tuple[tuple[int, int], ...],
) -> frozenset[tuple[int, int]]:
    return frozenset(
        (min(first, second), max(first, second))
        for support in (*triples, *doubles)
        for first, second in combinations(support, 2)
    )


def _graph_triangle_count(edges: frozenset[tuple[int, int]]) -> int:
    return sum(
        all(tuple(sorted(pair)) in edges for pair in combinations(triangle, 2))
        for triangle in combinations(range(20), 3)
    )


def _decode_support_rows(encoded: str) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(int(vertex) for vertex in support.split(",")) for support in encoded.split(";")
    )


def _decode_triples(encoded: str) -> tuple[tuple[int, int, int], ...]:
    return tuple((row[0], row[1], row[2]) for row in _decode_support_rows(encoded))


def _decode_pairs(encoded: str) -> tuple[tuple[int, int], ...]:
    return tuple((row[0], row[1]) for row in _decode_support_rows(encoded))


def test_every_plateau_profile_has_a_verified_realizability_and_motif_bound() -> None:
    result = _read_result()
    assert result["TASK_ID"] == "B649_K20_MIN_S2_NEXT_DISTINCT_PLATEAU_R10"
    assert result["BASE_HEAD"] == "2449c68f89b86d3c564958fca4a14133e6170d7e"
    assert result["BASE_TREE"] == "0032522b048a8fdd884647c810a21d74397694e4"
    assert result["PLATEAU_BOUND"] == PLATEAU_BOUND
    assert tuple(tuple(profile) for profile in result["PLATEAU_PROFILES"]) == EXPECTED_PLATEAU
    assert result["PLATEAU_PROCESSED_COUNT"] == len(EXPECTED_PLATEAU)
    assert result["PLATEAU_REMAINING_COUNT"] == 0
    assert result["PLATEAU_ENUMERATION"]["COMPLETE_PROFILES_EXAMINED"] == 6
    assert result["PLATEAU_ENUMERATION"]["PAIR_CAPACITY_PROFILES_CHECKED"] == 6
    assert result["PLATEAU_ENUMERATION"]["FULL_4850_PROFILE_RANKING_RERUN"] is False
    assert result["PREVIOUS_PLATEAU_BOUND"] == 313_739_208
    assert result["PREVIOUS_PLATEAU_PROFILE_COUNT"] == 3
    assert result["PREVIOUS_PLATEAU_PROCESSED_COUNT"] == 3
    assert result["PREVIOUS_PLATEAU_REMAINING_COUNT"] == 0
    assert result["ACTUAL_PROMOTIONS"] == len(EXPECTED_PLATEAU)
    assert (
        result["UNREALIZABLE_PROFILE_COUNT"] + result["REALIZABLE_PROFILE_COUNT"]
        == len(EXPECTED_PLATEAU)
    )
    assert result["TASK_STATUS"] in (
        "SUCCESS_A_FAMILY_CLOSED",
        "SUCCESS_B_BOUND_STRICTLY_DROPPED",
        "SUCCESS_C_PLATEAU_EXHAUSTED",
    )
    assert result["FAMILY_UPPER_BOUND"] <= PLATEAU_BOUND

    resolutions = result["PROFILE_BOUNDS"]
    assert tuple(tuple(item["PROFILE"]) for item in resolutions) == EXPECTED_PLATEAU
    for item in resolutions:
        profile = tuple(item["PROFILE"])
        if item["REALIZABILITY"] == "UNREALIZABLE":
            assert item["SUPPORT_SOLVER_STATUS"] == "INFEASIBLE"
            assert item["COARSE_FAMILY_UPPER_BOUND"] == PLATEAU_BOUND
            assert item["FAMILY_UPPER_BOUND"] is None
            assert "WITNESS_TRIPLES" not in item
            assert "MOTIF_SOLVER" not in item
            continue
        assert item["REALIZABILITY"] == "REALIZABLE"
        assert item["SUPPORT_SOLVER_STATUS"] in ("OPTIMAL", "FEASIBLE")
        assert item["MOTIF_SOLVER"]["SOLVER_STATUS"] in ("OPTIMAL", "FEASIBLE")
        assert item["DEGREE_CLASS_RELAXATION"]["SOLVER_STATUS"] in (
            "OPTIMAL",
            "FEASIBLE",
        )
        triples = _decode_triples(item["WITNESS_TRIPLES"])
        doubles = _decode_pairs(item["WITNESS_DOUBLE_SUPPORTS"])
        assert len(triples) == K20_TRIPLE_SUPPORT_COUNT
        assert len(doubles) == K20_DOUBLE_SUPPORT_COUNT == 27
        for ticket, degree in enumerate(profile):
            assert sum(ticket in pair for pair in doubles) == 6 - degree
        signature = validate_k20_support_realization(triples, doubles, profile)
        assert item["WITNESS_MOTIFS"] == {
            field: getattr(signature, field) for field in signature.__dataclass_fields__
        }
        assert signature.loose_three_cycle_count == signature.shadow_triangle_count - 22
        assert signature.shared_vertex_support_pair_count == sum(
            comb(degree, 2) for degree in profile
        )
        assert item["WITNESS_GRAPH_TRIANGLE_COUNT"] == _graph_triangle_count(
            _overlap_edges(triples, doubles)
        )
        objective_bound = item["MOTIF_SOLVER"]["SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"]
        if item["MOTIF_SOLVER"]["SOLVER_STATUS"] == "OPTIMAL":
            assert objective_bound == item["MOTIF_SOLVER"]["WITNESS_GRAPH_TRIANGLE_COUNT"]
            assert item["MOTIF_SOLVER"]["BOUND_KIND"] == "OPTIMAL_OBJECTIVE"
        else:
            assert objective_bound >= item["MOTIF_SOLVER"]["WITNESS_GRAPH_TRIANGLE_COUNT"]
            assert item["MOTIF_SOLVER"]["BOUND_KIND"] == "BEST_OBJECTIVE_UPPER_BOUND"
        motif_triples = _decode_triples(item["MOTIF_SOLVER"]["MOTIF_WITNESS_TRIPLES"])
        motif_doubles = _decode_pairs(item["MOTIF_SOLVER"]["MOTIF_WITNESS_DOUBLE_SUPPORTS"])
        motif_signature = validate_k20_support_realization(motif_triples, motif_doubles, profile)
        assert item["MOTIF_SOLVER"]["MOTIF_WITNESS_MOTIFS"] == {
            field: getattr(motif_signature, field) for field in motif_signature.__dataclass_fields__
        }
        assert item["MOTIF_SOLVER"]["WITNESS_GRAPH_TRIANGLE_COUNT"] == _graph_triangle_count(
            _overlap_edges(motif_triples, motif_doubles)
        )
        class_certificate = item["DEGREE_CLASS_RELAXATION"]
        weighted_open_wedge_lower_bound = class_certificate[
            "WEIGHTED_OPEN_WEDGE_LOWER_BOUND"
        ]
        wedge_count = overlap_wedge_count(profile)
        residue = wedge_count % 3
        expected_open_wedge_lower_bound = residue + 3 * max(
            0, ceil((weighted_open_wedge_lower_bound - residue) / 3)
        )
        assert class_certificate["OPEN_WEDGE_LOWER_BOUND"] == expected_open_wedge_lower_bound
        expected_class_triangle_bound = (wedge_count - expected_open_wedge_lower_bound) // 3
        assert class_certificate["GRAPH_TRIANGLE_UPPER_BOUND"] == expected_class_triangle_bound
        assert item["GRAPH_TRIANGLE_UPPER_BOUND"] == min(
            PLATEAU_WEDGE_COUNT // 3,
            objective_bound,
            expected_class_triangle_bound,
        )
        assert item["GRAPH_TRIANGLE_UPPER_BOUND"] <= PLATEAU_WEDGE_COUNT // 3
        assert item["NONCORE_TRIANGLE_UPPER_BOUND"] == (
            item["GRAPH_TRIANGLE_UPPER_BOUND"] - K20_TRIPLE_SUPPORT_COUNT
        )
        assert item["LOOSE_THREE_CYCLE_UPPER_BOUND"] == item["NONCORE_TRIANGLE_UPPER_BOUND"]
        assert item["PASCH_LIKE_FOUR_SUPPORT_UPPER_BOUND"] == (
            item["NONCORE_TRIANGLE_UPPER_BOUND"] // 4
        )
        expected_s3 = s3_sum_from_wedges_and_triangles(
            overlap_wedge_count(profile), item["NONCORE_TRIANGLE_UPPER_BOUND"]
        )
        assert item["S3_UPPER_BOUND"] == expected_s3
        expected_s4 = (
            SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND
            if profile.count(0) == 7
            else K20_REUSED_S4_LOWER_BOUND
        )
        assert item["S4_LOWER_BOUND"] == expected_s4
        expected_credit = (4 * expected_s4) // 7
        assert item["FOURTH_ORDER_CREDIT"] == expected_credit
        assert item["FAMILY_UPPER_BOUND"] == K20_S1 - K20_S2 + expected_s3 - expected_credit
        assert item["FAMILY_UPPER_BOUND"] < PLATEAU_BOUND

    next_distinct = find_next_distinct_profile()
    next_profile = tuple(result["NEXT_ACTIVE_PROFILE"])
    assert next_profile == next_distinct.degree_profile
    assert result["NEXT_DISTINCT_BOUND"] == next_distinct.family_upper_bound
    assert result["NEXT_DISTINCT_BOUND"] == coarse_profile_envelope(next_profile).family_upper_bound
    assert result["NEXT_DISTINCT_BOUND"] < PLATEAU_BOUND
    assert result["NEXT_PROFILE_SEARCH"]["WEDGE_COUNT"] == next_distinct.wedge_count
    assert linear_triple_degree_sequence_passes_pair_capacity(next_profile, 22)
    assert simple_graph_degree_sequence_is_graphical(residual_double_ticket_degrees(next_profile))
    surviving_profile_bounds = [
        item["FAMILY_UPPER_BOUND"]
        for item in resolutions
        if item["REALIZABILITY"] == "REALIZABLE"
    ]
    assert result["FAMILY_UPPER_BOUND"] == max(
        result["NEXT_DISTINCT_BOUND"],
        *surviving_profile_bounds,
    )
    assert result["INCUMBENT"] == K20_INCUMBENT


def test_small_linear_hypergraph_oracle_checks_shadow_and_motif_identities() -> None:
    for vertex_count in (3, 4, 5):
        candidates = tuple(combinations(range(vertex_count), 3))
        for support_mask in range(1 << len(candidates)):
            supports = tuple(
                support for index, support in enumerate(candidates) if support_mask & (1 << index)
            )
            used_pairs: set[tuple[int, int]] = set()
            degrees = [0] * vertex_count
            linear = True
            for support in supports:
                for vertex in support:
                    degrees[vertex] += 1
                for pair in combinations(support, 2):
                    if pair in used_pairs:
                        linear = False
                        break
                    used_pairs.add(pair)
                if not linear:
                    break
            if not linear:
                continue

            shadow_degrees = tuple(sorted((2 * degree for degree in degrees), reverse=True))
            observed_shadow_degrees = tuple(
                sorted(
                    (sum(vertex in pair for pair in used_pairs) for vertex in range(vertex_count)),
                    reverse=True,
                )
            )
            assert shadow_degrees == observed_shadow_degrees
            assert erdos_gallai_first_violation(shadow_degrees) is None
            signature = support_motif_signature(supports)
            assert signature.triple_support_count == len(supports)
            assert signature.shadow_triangle_count == (
                len(supports) + signature.loose_three_cycle_count
            )
            assert signature.shared_vertex_support_pair_count == sum(
                comb(degree, 2) for degree in degrees
            )

    pasch = ((0, 1, 2), (0, 3, 4), (5, 1, 3), (5, 2, 4))
    pasch_signature = support_motif_signature(pasch)
    assert pasch_signature.loose_three_cycle_count == 4
    assert pasch_signature.pasch_like_four_support_count == 1
