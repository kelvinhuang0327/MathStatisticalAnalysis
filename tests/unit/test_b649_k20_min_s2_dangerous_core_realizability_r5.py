"""Dangerous-profile selection and support-motif realization oracles."""

from __future__ import annotations

from itertools import combinations

import pytest

from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_PREVIOUS_R4_FAMILY_UPPER_BOUND,
    k20_min_s2_dangerous_core_certificate,
    linear_triple_profile_obstruction,
    rank_dangerous_profiles,
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
    support_motif_signature,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_TRIPLE_SUPPORT_COUNT,
    linear_triple_degree_sequence_passes_pair_capacity,
)

TOP_UNREALIZABLE_PROFILES = (
    (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 1, 0, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 6, 6, 5, 4, 4, 4, 4, 3, 0, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 4, 2, 0, 0, 0, 0, 0, 0, 0),
)

TOP_SURVIVING_PROFILES = (
    (6, 6, 6, 6, 6, 6, 6, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 6, 5, 5, 5, 4, 4, 4, 3, 0, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 4, 1, 1, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 3, 3, 0, 0, 0, 0, 0, 0, 0),
    (6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 2, 0, 0, 0, 0, 0, 0, 0),
)


def _exhaustive_linear_hypergraphs(
    vertex_count: int,
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    candidate_supports = tuple(combinations(range(vertex_count), 3))
    hypergraphs: list[tuple[tuple[int, ...], ...]] = []
    for mask in range(1 << len(candidate_supports)):
        supports = tuple(
            support for index, support in enumerate(candidate_supports) if mask & (1 << index)
        )
        used_pairs: set[tuple[int, int]] = set()
        is_linear = True
        for support in supports:
            for pair in combinations(support, 2):
                if pair in used_pairs:
                    is_linear = False
                    break
                used_pairs.add(pair)
            if not is_linear:
                break
        if not is_linear:
            continue
        hypergraphs.append(supports)
    return tuple(hypergraphs)


def _degree_profile(
    vertex_count: int,
    supports: tuple[tuple[int, ...], ...],
) -> tuple[int, ...]:
    degrees = [0] * vertex_count
    for support in supports:
        for vertex in support:
            degrees[vertex] += 1
    return tuple(sorted(degrees, reverse=True))


def test_dangerous_profile_selection_ranks_only_incumbent_exceeding_profiles() -> None:
    certificate = k20_min_s2_dangerous_core_certificate()
    ranked = rank_dangerous_profiles()

    assert certificate.total_bounded_profile_count == 5_126
    assert certificate.pair_capacity_compatible_profile_count == 4_850
    assert certificate.residual_capacity_compatible_profile_count == 4_850
    assert certificate.dangerous_profile_count == 4_850
    assert certificate.incumbent_s3_threshold_exclusive == 4_849_685
    assert certificate.s4_lower_bound_reused == 112
    assert certificate.fourth_order_credit == 64
    assert tuple(profile.degree_sequence for profile in ranked[:3]) == TOP_UNREALIZABLE_PROFILES
    assert tuple(profile.wedge_count for profile in ranked[:8]) == (
        841,
        838,
        838,
        837,
        837,
        837,
        837,
        837,
    )
    assert all(profile.family_upper_bound > certificate.incumbent for profile in ranked)
    assert all(
        simple_graph_degree_sequence_is_graphical(residual_double_ticket_degrees(profile))
        for profile in TOP_SURVIVING_PROFILES
    )
    assert all(
        linear_triple_degree_sequence_passes_pair_capacity(profile, K20_TRIPLE_SUPPORT_COUNT)
        for profile in TOP_SURVIVING_PROFILES
    )


def test_top_profile_obstructions_close_three_and_bound_the_first_survivor_class() -> None:
    certificate = k20_min_s2_dangerous_core_certificate()

    assert certificate.closed_dangerous_degree_sequences == TOP_UNREALIZABLE_PROFILES
    assert (
        tuple(profile.degree_sequence for profile in certificate.top_surviving_profiles)
        == TOP_SURVIVING_PROFILES
    )
    assert {profile.wedge_count for profile in certificate.top_surviving_profiles} == {837}
    assert {
        profile.noncore_triangle_upper_bound for profile in certificate.top_surviving_profiles
    } == {257}
    assert {profile.s3_upper_bound for profile in certificate.top_surviving_profiles} == {5_363_904}
    assert {profile.family_upper_bound for profile in certificate.top_surviving_profiles} == {
        313_753_880
    }
    assert certificate.family_upper_bound == 313_753_880
    assert certificate.family_upper_bound < K20_PREVIOUS_R4_FAMILY_UPPER_BOUND
    assert certificate.incumbent == 313_239_661
    assert certificate.remaining_family_gap == 514_219
    assert certificate.family_status == "OPEN_STRICTLY_TIGHTENED"

    obstructions = tuple(
        linear_triple_profile_obstruction(profile) for profile in TOP_UNREALIZABLE_PROFILES
    )
    assert all(obstruction is not None for obstruction in obstructions)
    assert tuple(obstruction.reason for obstruction in obstructions if obstruction) == (
        "DEGREE_SIX_HUB_COVER_REQUIREMENT",
        "DEGREE_SIX_HUB_COVER_REQUIREMENT",
        "DEGREE_SIX_HUB_COVER_REQUIREMENT",
    )
    assert tuple(
        obstruction.required_minimum_active_degree for obstruction in obstructions if obstruction
    ) == (3, 4, 3)


def test_motif_oracle_distinguishes_shared_vertices_loose_cycles_and_pasch() -> None:
    shared_vertex = support_motif_signature(((0, 1, 2), (0, 3, 4)))
    assert shared_vertex.shared_vertex_support_pair_count == 1
    assert shared_vertex.loose_three_cycle_count == 0
    assert shared_vertex.pasch_like_four_support_count == 0

    loose_cycle = support_motif_signature(((0, 1, 3), (1, 2, 4), (0, 2, 5)))
    assert loose_cycle.shadow_triangle_count == 4
    assert loose_cycle.noncore_shadow_triangle_count == 1
    assert loose_cycle.loose_three_cycle_count == 1

    pasch = support_motif_signature(((0, 1, 2), (0, 3, 4), (1, 3, 5), (2, 4, 5)))
    assert pasch.shared_vertex_support_pair_count == 6
    assert pasch.loose_three_cycle_count == 4
    assert pasch.pasch_like_four_support_count == 1


def test_exhaustive_small_linear_3_uniform_oracles_preserve_motif_identities() -> None:
    for vertex_count in (3, 4, 5):
        realizable_profiles: set[tuple[int, ...]] = set()
        for supports in _exhaustive_linear_hypergraphs(vertex_count):
            profile = _degree_profile(vertex_count, supports)
            signature = support_motif_signature(supports)
            realizable_profiles.add(profile)

            assert sum(profile) == 3 * len(supports)
            assert signature.triple_support_count == len(supports)
            assert signature.shadow_triangle_count >= len(supports)
            assert signature.noncore_shadow_triangle_count == signature.loose_three_cycle_count
            assert signature.pasch_like_four_support_count == 0

        assert (0,) * vertex_count in realizable_profiles
        assert all(sum(profile) % 3 == 0 for profile in realizable_profiles)


def test_support_oracle_rejects_reused_core_pairs_before_residual_double_supports() -> None:
    from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
        validate_k20_support_realization,
    )

    supports = ((0, 1, 2), (0, 1, 3), *tuple(combinations(range(4, 20), 3))[:20])
    with pytest.raises(ValueError, match="pair capacity <= 1"):
        validate_k20_support_realization(
            supports,
            ((0, 1),) * 27,
            (6,) * 11 + (0,) * 9,
        )
