"""Focused checks for the K20 top-envelope realization certificate."""

from __future__ import annotations

from itertools import combinations

from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    support_motif_signature,
    validate_k20_support_realization,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_INCUMBENT,
)
from lottolab.research.b649_k20_min_s2_top_envelope_realizability_r6 import (
    TOP_PROFILE_1,
    TOP_PROFILE_2,
    TOP_PROFILE_3,
    TOP_PROFILE_4,
    TOP_PROFILE_5,
    erdos_gallai_first_violation,
    k20_min_s2_top_envelope_certificate,
    shared_vertex_support_pair_count,
    triple_shadow_degree_sequence,
)

EXPECTED_TOP_PROFILES = (
    TOP_PROFILE_1,
    TOP_PROFILE_2,
    TOP_PROFILE_3,
    TOP_PROFILE_4,
    TOP_PROFILE_5,
)


def test_ranking_resolves_only_the_five_profiles_at_the_top_envelope() -> None:
    certificate = k20_min_s2_top_envelope_certificate()

    assert certificate.total_bounded_profile_count == 5_126
    assert certificate.ranked_dangerous_profile_count == 4_850
    assert certificate.exactly_analyzed_profile_count == 5
    assert certificate.previously_closed_profile_count == 3
    assert certificate.newly_closed_profile_count == 1
    assert certificate.closed_dangerous_profile_count == 4
    assert tuple(
        profile.degree_sequence for profile in certificate.top_surviving_profiles
    ) == EXPECTED_TOP_PROFILES
    assert certificate.next_unprocessed_profile == (
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
    assert certificate.next_unprocessed_family_upper_bound == 313_739_208


def test_four_top_profiles_have_full_support_witnesses_and_one_fails_shadow_graphicality() -> None:
    certificate = k20_min_s2_top_envelope_certificate()
    resolutions = certificate.profile_resolutions

    assert tuple(item.degree_sequence for item in resolutions) == EXPECTED_TOP_PROFILES
    assert tuple(item.degree_sequence for item in resolutions if item.realizable) == (
        TOP_PROFILE_1,
        TOP_PROFILE_2,
        TOP_PROFILE_4,
        TOP_PROFILE_5,
    )
    assert tuple(item.degree_sequence for item in resolutions if not item.realizable) == (
        TOP_PROFILE_3,
    )

    for resolution in resolutions:
        if not resolution.realizable:
            assert resolution.triple_supports == ()
            assert resolution.double_supports == ()
            continue
        signature = validate_k20_support_realization(
            resolution.triple_supports,
            resolution.double_supports,
            resolution.degree_sequence,
        )
        assert signature.triple_support_count == 22
        assert len(resolution.double_supports) == 27
        assert sum(resolution.degree_sequence) == 66
        assert all(
            len(set(triple)) == 3 for triple in resolution.triple_supports
        )

    shadow_degrees = triple_shadow_degree_sequence(TOP_PROFILE_3)
    assert erdos_gallai_first_violation(shadow_degrees) is not None
    violation = erdos_gallai_first_violation(shadow_degrees)
    assert violation is not None
    assert (violation.prefix_size, violation.left_hand_side, violation.right_hand_side) == (
        5,
        60,
        59,
    )
    assert all(
        erdos_gallai_first_violation(triple_shadow_degree_sequence(profile)) is None
        for profile in (TOP_PROFILE_1, TOP_PROFILE_2, TOP_PROFILE_4, TOP_PROFILE_5)
    )


def test_motif_caps_and_family_bound_use_the_strict_wedge_closure_argument() -> None:
    certificate = k20_min_s2_top_envelope_certificate()

    assert len(certificate.profile_motif_envelopes) == 4
    assert {item.wedge_count for item in certificate.profile_motif_envelopes} == {837}
    assert {
        item.total_graph_triangle_upper_bound for item in certificate.profile_motif_envelopes
    } == {278}
    assert {item.noncore_triangle_upper_bound for item in certificate.profile_motif_envelopes} == {
        256
    }
    assert {item.loose_three_cycle_upper_bound for item in certificate.profile_motif_envelopes} == {
        256
    }
    assert {
        item.pasch_like_four_support_upper_bound for item in certificate.profile_motif_envelopes
    } == {64}
    assert {
        item.shared_vertex_support_pair_count for item in certificate.profile_motif_envelopes
    } == {141}
    assert all(
        item.witness_motif_signature.noncore_shadow_triangle_count
        == item.witness_motif_signature.loose_three_cycle_count
        for item in certificate.profile_motif_envelopes
    )
    assert {item.s3_upper_bound for item in certificate.profile_motif_envelopes} == {5_352_032}
    assert {item.s4_lower_bound for item in certificate.profile_motif_envelopes} == {112}
    assert {item.fourth_order_credit for item in certificate.profile_motif_envelopes} == {64}
    assert certificate.family_upper_bound == 313_742_008
    assert certificate.family_upper_bound < 313_753_880
    assert certificate.incumbent == K20_INCUMBENT == 313_239_661
    assert certificate.remaining_family_gap == 502_347
    assert certificate.family_status == "OPEN_STRICTLY_TIGHTENED"


def test_shared_vertex_motif_count_is_exact_for_each_realizable_profile() -> None:
    certificate = k20_min_s2_top_envelope_certificate()
    expected_counts = {
        TOP_PROFILE_1: 141,
        TOP_PROFILE_2: 141,
        TOP_PROFILE_4: 141,
        TOP_PROFILE_5: 141,
    }

    assert {
        item.degree_sequence: item.shared_vertex_support_pair_count
        for item in certificate.profile_motif_envelopes
    } == expected_counts
    assert all(
        shared_vertex_support_pair_count(profile) == expected
        for profile, expected in expected_counts.items()
    )


def test_small_linear_hypergraph_oracle_preserves_motif_identities() -> None:
    for vertex_count in (3, 4, 5):
        candidate_supports = tuple(combinations(range(vertex_count), 3))
        for mask in range(1 << len(candidate_supports)):
            supports = tuple(
                support
                for index, support in enumerate(candidate_supports)
                if mask & (1 << index)
            )
            used_pairs: set[tuple[int, int]] = set()
            linear = True
            for support in supports:
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
            assert signature.shadow_triangle_count >= len(supports)
            assert signature.noncore_shadow_triangle_count == signature.loose_three_cycle_count
            assert signature.pasch_like_four_support_count == 0
