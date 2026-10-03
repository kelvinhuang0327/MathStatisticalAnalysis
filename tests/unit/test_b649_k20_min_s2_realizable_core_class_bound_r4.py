"""Focused degree-profile bounds and exhaustive small hypergraph oracles."""

from __future__ import annotations

import itertools
from math import comb

from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_PROFILE_DEGREE_SQUARE_CASE_TABLE,
    bounded_nonincreasing_degree_sequences,
    k20_min_s2_realizable_core_class_certificate,
    linear_triple_degree_sequence_passes_pair_capacity,
    minimum_internal_pair_uses,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
    s3_upper_bound_from_wedges,
)


def _linear_hypergraphs(vertex_count: int) -> tuple[tuple[tuple[int, ...], ...], ...]:
    triples = tuple(itertools.combinations(range(vertex_count), 3))
    hypergraphs: list[tuple[tuple[int, ...], ...]] = []
    for selected in range(1 << len(triples)):
        supports = tuple(triple for index, triple in enumerate(triples) if selected & (1 << index))
        used_pairs: set[tuple[int, int]] = set()
        is_linear = True
        for support in supports:
            for pair in itertools.combinations(support, 2):
                if pair in used_pairs:
                    is_linear = False
                    break
                used_pairs.add(pair)
            if not is_linear:
                break
        if is_linear:
            hypergraphs.append(supports)
    return tuple(hypergraphs)


def _degrees_from_supports(
    vertex_count: int, supports: tuple[tuple[int, ...], ...]
) -> tuple[int, ...]:
    degrees = [0] * vertex_count
    for support in supports:
        for vertex in support:
            degrees[vertex] += 1
    return tuple(degrees)


def test_k20_degree_sequence_envelope_is_strictly_tighter() -> None:
    certificate = k20_min_s2_realizable_core_class_certificate()

    assert certificate.degree_sequence_count == 5_126
    assert certificate.pair_capacity_compatible_degree_sequence_count == 4_850
    assert certificate.maximum_wedge_count == 841
    assert certificate.maximizing_degree_sequences == (
        (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 1, 0, 0, 0, 0, 0, 0, 0),
    )
    assert certificate.maximum_noncore_triangle_count == 258
    assert certificate.s3_upper_bound == 5_386_976
    assert certificate.s4_lower_bound_used == 0
    assert certificate.fourth_order_correction_used == 0
    assert certificate.family_upper_bound == 313_777_016
    assert certificate.incumbent == 313_239_661
    assert certificate.remaining_family_gap == 537_355
    assert certificate.family_status == "OPEN_STRICTLY_TIGHTENED"
    assert certificate.family_upper_bound < 313_915_480


def test_profile_enumerator_matches_small_unordered_composition_oracle() -> None:
    for slots in range(1, 5):
        for maximum in range(0, 4):
            for total in range(slots * maximum + 1):
                expected = tuple(
                    tuple(sorted(values, reverse=True))
                    for values in itertools.product(range(maximum + 1), repeat=slots)
                    if sum(values) == total
                )
                expected = tuple(sorted(set(expected), reverse=True))
                assert bounded_nonincreasing_degree_sequences(total, slots, maximum) == expected


def test_minimum_pair_uses_matches_exhaustive_support_intersections() -> None:
    for support_count in range(1, 5):
        for incidence_count in range(3 * support_count + 1):
            expected = min(
                sum(comb(intersection_size, 2) for intersection_size in sizes)
                for sizes in itertools.product(range(4), repeat=support_count)
                if sum(sizes) == incidence_count
            )
            assert minimum_internal_pair_uses(incidence_count, support_count) == expected


def test_all_small_linear_3_uniform_hypergraphs_pass_pair_capacity_inequalities() -> None:
    for vertex_count in (3, 4, 5):
        for supports in _linear_hypergraphs(vertex_count):
            degrees = _degrees_from_supports(vertex_count, supports)
            assert linear_triple_degree_sequence_passes_pair_capacity(degrees, len(supports))

            for subset_size in range(1, vertex_count + 1):
                for subset in itertools.combinations(range(vertex_count), subset_size):
                    incidence_count = sum(degrees[vertex] for vertex in subset)
                    actual_internal_pairs = sum(
                        comb(sum(vertex in support for vertex in subset), 2) for support in supports
                    )
                    assert actual_internal_pairs <= comb(subset_size, 2)
                    assert (
                        minimum_internal_pair_uses(incidence_count, len(supports))
                        <= actual_internal_pairs
                    )


def test_degree_square_case_table_and_wedge_formula_are_exact() -> None:
    certificate = k20_min_s2_realizable_core_class_certificate()
    assert K20_PROFILE_DEGREE_SQUARE_CASE_TABLE == (
        (0, None),
        (1, None),
        (2, 338),
        (3, 344),
        (4, 350),
        (5, 356),
        (6, None),
    )
    assert overlap_wedge_count(certificate.maximizing_degree_sequences[0]) == 841
    assert s3_upper_bound_from_wedges(841) == (258, 5_386_976)


def test_pair_capacity_filter_rejects_the_unconstrained_convex_extremum() -> None:
    unconstrained_maximum = (6,) * 11 + (0,) * 9
    assert sum(unconstrained_maximum) == 66
    assert not linear_triple_degree_sequence_passes_pair_capacity(unconstrained_maximum, 22)
    assert minimum_internal_pair_uses(66, 22) == 66
    assert comb(11, 2) == 55


def _three_ticket_intersection_count(profile: tuple[int, ...]) -> int:
    total = 0
    for special_mask, special_count in enumerate(profile):
        if special_count == 0:
            continue
        thresholds: tuple[int, int, int] = (
            3 - int(bool(special_mask & 1)),
            3 - int(bool(special_mask & 2)),
            3 - int(bool(special_mask & 4)),
        )
        available = list(profile)
        available[special_mask] -= 1
        states: dict[tuple[int, int, int, int], int] = {(0, 0, 0, 0): 1}
        for incidence_mask, label_count in enumerate(available):
            if label_count == 0:
                continue
            following: dict[tuple[int, int, int, int], int] = {}
            for state, ways in states.items():
                used = state[0]
                hits = (state[1], state[2], state[3])
                for take in range(min(label_count, 6 - used) + 1):
                    new_hits: tuple[int, int, int] = (
                        min(thresholds[0], hits[0] + (take if incidence_mask & 1 else 0)),
                        min(thresholds[1], hits[1] + (take if incidence_mask & 2 else 0)),
                        min(thresholds[2], hits[2] + (take if incidence_mask & 4 else 0)),
                    )
                    new_state: tuple[int, int, int, int] = (used + take, *new_hits)
                    following[new_state] = following.get(new_state, 0) + ways * comb(
                        label_count, take
                    )
            states = following
        target = (6, thresholds[0], thresholds[1], thresholds[2])
        total += special_count * states.get(target, 0)
    return total


def test_exact_three_ticket_profiles_match_independent_outcome_oracle() -> None:
    profiles = (
        ((33, 4, 5, 1, 5, 1, 0, 0), 2_800),
        ((34, 4, 4, 1, 4, 1, 1, 0), 20_272),
        ((33, 5, 5, 0, 5, 0, 0, 1), 7_000),
    )
    for profile, expected in profiles:
        assert sum(profile) == 49
        for ticket_index in range(3):
            assert (
                sum(count for mask, count in enumerate(profile) if mask & (1 << ticket_index)) == 6
            )
        assert _three_ticket_intersection_count(profile) == expected

    assert s3_sum_from_wedges_and_triangles(67, 0) == 2_800 + 22 * 7_000
    assert s3_sum_from_wedges_and_triangles(69, 1) == 20_272 + 22 * 7_000
