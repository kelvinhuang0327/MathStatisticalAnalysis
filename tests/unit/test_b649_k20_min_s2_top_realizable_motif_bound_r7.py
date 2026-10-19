"""Focused identity and motif-oracle tests for the R7 K20 envelope."""

from __future__ import annotations

from itertools import combinations
from math import comb

from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    support_motif_signature,
)
from lottolab.research.b649_k20_min_s2_top_envelope_realizability_r6 import (
    TOP_PROFILE_1,
    TOP_PROFILE_2,
    TOP_PROFILE_4,
    TOP_PROFILE_5,
)
from lottolab.research.b649_k20_min_s2_top_realizable_motif_bound_r7 import (
    EXACTLY_ANALYZED_PROFILE_COUNT,
    NEXT_UNPROCESSED_FAMILY_UPPER_BOUND,
    NEXT_UNPROCESSED_PROFILE,
    PROFILE_GRAPH_TRIANGLE_UPPER_BOUNDS,
    TOP_PROFILE_COUNT,
    TOP_PROFILES,
    degree_class_open_wedge_certificate,
    inactive_ticket_s4_census,
    profile_envelope,
    profile_witness_motifs,
)


def test_only_the_four_proven_feasible_top_profiles_are_analyzed() -> None:
    expected_profiles = (TOP_PROFILE_1, TOP_PROFILE_2, TOP_PROFILE_4, TOP_PROFILE_5)

    assert TOP_PROFILE_COUNT == 5
    assert EXACTLY_ANALYZED_PROFILE_COUNT == 4
    assert expected_profiles == TOP_PROFILES
    assert tuple(PROFILE_GRAPH_TRIANGLE_UPPER_BOUNDS) == tuple(
        zip(expected_profiles, (275, 261, 275, 276), strict=True)
    )

    expected_witnesses = (
        (201, 182, 160, 4),
        (225, 183, 161, 4),
        (214, 186, 164, 2),
        (234, 186, 164, 4),
    )
    for profile, expected in zip(expected_profiles, expected_witnesses, strict=True):
        graph_triangles, signature = profile_witness_motifs(profile)
        assert (
            graph_triangles,
            signature.shadow_triangle_count,
            signature.loose_three_cycle_count,
            signature.pasch_like_four_support_count,
        ) == expected
        assert signature.triple_support_count == 22
        assert signature.shared_vertex_support_pair_count == 141
        assert signature.noncore_shadow_triangle_count == signature.loose_three_cycle_count


def test_degree_class_relaxation_certifies_profile_specific_triangle_caps() -> None:
    expected = (
        (12, 12, 275),
        (12, 12, 275),
        (12, 12, 275),
        (8, 9, 276),
    )

    for profile, target in zip(TOP_PROFILES, expected, strict=True):
        certificate = degree_class_open_wedge_certificate(profile)

        assert certificate.solver_status == "OPTIMAL"
        assert (
            certificate.weighted_open_wedge_lower_bound,
            certificate.open_wedge_lower_bound,
            certificate.graph_triangle_upper_bound,
        ) == target


def test_inactive_ticket_census_gives_a_forced_s4_floor() -> None:
    census = inactive_ticket_s4_census()

    assert census.labeled_missing_graphs_examined == 82_160
    assert census.minimum_s4 == 1_680
    assert census.minimizing_missing_edge_count == 6
    assert census.minimizing_missing_degree_sequence == (2, 2, 2, 2, 2, 1, 1)
    assert census.labeled_minimizer_count == 672


def test_profile_envelopes_activate_only_the_supplied_next_profile() -> None:
    envelopes = tuple(profile_envelope(profile) for profile in TOP_PROFILES)

    assert tuple(item.graph_triangle_upper_bound for item in envelopes) == (275, 261, 275, 276)
    assert tuple(
        item.noncore_graph_triangle_upper_bound for item in envelopes
    ) == (253, 239, 253, 254)
    assert tuple(item.loose_three_cycle_upper_bound for item in envelopes) == (
        253,
        239,
        253,
        254,
    )
    assert {item.shared_vertex_support_pair_count for item in envelopes} == {141}
    assert tuple(item.pasch_like_four_support_upper_bound for item in envelopes) == (
        63,
        59,
        63,
        63,
    )
    assert tuple(item.s3_upper_bound for item in envelopes) == (
        5_316_416,
        5_150_208,
        5_316_416,
        5_328_288,
    )
    assert {item.inactive_s4_lower_bound for item in envelopes} == {1_680}
    assert {item.fourth_order_credit for item in envelopes} == {960}
    assert tuple(item.family_upper_bound for item in envelopes) == (
        313_705_496,
        313_539_288,
        313_705_496,
        313_717_368,
    )
    assert max(item.family_upper_bound for item in envelopes) < NEXT_UNPROCESSED_FAMILY_UPPER_BOUND
    assert NEXT_UNPROCESSED_PROFILE == (
        6,
        6,
        6,
        6,
        6,
        6,
        6,
        5,
        4,
        4,
        4,
        4,
        2,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def test_small_linear_three_uniform_motif_oracles() -> None:
    for vertex_count in (3, 4, 5):
        candidates = tuple(combinations(range(vertex_count), 3))
        for mask in range(1 << len(candidates)):
            supports = tuple(
                support
                for index, support in enumerate(candidates)
                if mask & (1 << index)
            )
            used_pairs: set[tuple[int, int]] = set()
            linear = True
            degrees = [0] * vertex_count
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

            signature = support_motif_signature(supports)
            assert signature.triple_support_count == len(supports)
            assert signature.shared_vertex_support_pair_count == sum(
                comb(degree, 2) for degree in degrees
            )
            assert signature.shadow_triangle_count == (
                len(supports) + signature.loose_three_cycle_count
            )
            assert signature.pasch_like_four_support_count == 0

    pasch = ((0, 1, 2), (0, 3, 4), (5, 1, 3), (5, 2, 4))
    pasch_signature = support_motif_signature(pasch)
    assert pasch_signature.loose_three_cycle_count == 4
    assert pasch_signature.pasch_like_four_support_count == 1
