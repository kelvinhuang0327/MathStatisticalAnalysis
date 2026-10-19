"""Focused tests for the R8 active-profile obstruction and one-step promotion."""

from __future__ import annotations

from itertools import combinations
from math import comb

from lottolab.research.b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    ACTIVE_PROFILE,
    ACTIVE_PROFILE_COARSE_FAMILY_BOUND,
    ACTIVE_PROFILE_COARSE_S3_BOUND,
    ACTIVE_PROFILE_COARSE_TRIANGLE_BOUND,
    ACTIVE_PROFILE_WEDGE_COUNT,
    EXPECTED_NEXT_PROFILE,
    ErdosGallaiViolation,
    active_profile_realizability_certificate,
    coarse_profile_envelope,
    erdos_gallai_first_violation,
    next_ranked_same_wedge_profile,
    triple_shadow_degree_sequence,
)


def test_packet_profile_identity_and_existing_coarse_envelope() -> None:
    envelope = coarse_profile_envelope(ACTIVE_PROFILE)

    assert len(ACTIVE_PROFILE) == 20
    assert sum(ACTIVE_PROFILE) == 66
    assert envelope.triple_support_count == 22
    assert envelope.residual_double_incidence_count == 54
    assert envelope.residual_double_incidence_count // 2 == 27
    assert envelope.wedge_count == ACTIVE_PROFILE_WEDGE_COUNT == 836
    assert envelope.graph_triangle_upper_bound == ACTIVE_PROFILE_COARSE_TRIANGLE_BOUND == 278
    assert envelope.noncore_triangle_upper_bound == 256
    assert envelope.s3_upper_bound == ACTIVE_PROFILE_COARSE_S3_BOUND == 5_349_232
    assert envelope.fourth_order_credit == 64
    assert envelope.family_upper_bound == ACTIVE_PROFILE_COARSE_FAMILY_BOUND == 313_739_208


def test_shadow_graph_obstruction_proves_active_profile_unrealizable() -> None:
    expected_shadow_degrees = (
        12,
        12,
        12,
        12,
        12,
        12,
        12,
        10,
        8,
        8,
        8,
        8,
        4,
        2,
        0,
        0,
        0,
        0,
        0,
        0,
    )

    profile, violation = active_profile_realizability_certificate()

    assert profile == ACTIVE_PROFILE
    assert triple_shadow_degree_sequence(profile) == expected_shadow_degrees
    assert violation == ErdosGallaiViolation(
        prefix_size=7,
        left_hand_side=84,
        right_hand_side=83,
    )
    assert erdos_gallai_first_violation(expected_shadow_degrees) == violation


def test_only_the_immediate_same_bound_ranked_successor_is_promoted() -> None:
    successor = next_ranked_same_wedge_profile()

    assert successor.degree_profile == EXPECTED_NEXT_PROFILE == (
        6,
        6,
        6,
        6,
        6,
        6,
        5,
        5,
        4,
        4,
        4,
        4,
        4,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    assert successor.wedge_count == 836
    assert successor.s3_upper_bound == 5_349_232
    assert successor.family_upper_bound == 313_739_208
    assert successor.complete_profiles_examined == 2
    assert successor.eligible_candidates_checked == 1


def test_small_linear_three_uniform_realization_oracles() -> None:
    for vertex_count in (3, 4, 5):
        candidate_supports = tuple(combinations(range(vertex_count), 3))
        for support_mask in range(1 << len(candidate_supports)):
            supports = tuple(
                support
                for index, support in enumerate(candidate_supports)
                if support_mask & (1 << index)
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
            assert sum(shadow_degrees) == 6 * len(supports)
            assert erdos_gallai_first_violation(shadow_degrees) is None
            assert len(used_pairs) == 3 * len(supports)
            assert sum(comb(degree, 2) for degree in degrees) == sum(
                len(set(first).intersection(second)) == 1
                for first, second in combinations(supports, 2)
            )
