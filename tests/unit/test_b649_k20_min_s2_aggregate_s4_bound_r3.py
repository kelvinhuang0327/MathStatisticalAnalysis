"""Focused checks and independent small incidence oracles for the K20 bound."""

from __future__ import annotations

import itertools
from math import ceil, comb

from lottolab.research.b649_k20_min_s2_aggregate_s4_bound_r3 import (
    K20_LOCAL_PROFILE_WITNESS_CAPACITIES_AND_WEIGHTS,
    bonferroni_fourth_order_credit,
    family_upper_bound_from_s4,
    k20_min_s2_aggregate_weighted_s4_certificate,
    minimum_collision_count,
    minimum_degree_square_sum,
    minimum_pair_collision_count,
    weighted_s4_lower_bound_from_witnesses,
)
from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import (
    compressed_four_ticket_intersection_count,
    k20_min_s2_s4_lower_bound_certificate,
)


def _compositions(total: int, slots: int) -> tuple[tuple[int, ...], ...]:
    if slots == 1:
        return ((total,),)
    return tuple(
        (first, *tail)
        for first in range(total + 1)
        for tail in _compositions(total - first, slots - 1)
    )


def _profile_from_supports(supports: tuple[int, ...]) -> tuple[int, ...]:
    counts = [0] * 16
    loads = [0] * 4
    for mask in supports:
        counts[mask] += 1
        for ticket_index in range(4):
            loads[ticket_index] += int(bool(mask & (1 << ticket_index)))
    for ticket_index, load in enumerate(loads):
        assert load <= 6
        counts[1 << ticket_index] += 6 - load
    counts[0] += 49 - sum(counts)
    return tuple(counts)


def test_aggregate_certificate_reproduces_weighted_bound_and_remaining_gap() -> None:
    certificate = k20_min_s2_aggregate_weighted_s4_certificate()

    assert (
        certificate.minimum_triple_degree_square_sum,
        certificate.cross_incidence_lower_bound,
        certificate.support_outside_pair_count,
        certificate.aggregate_common_neighbor_incidence_lower_bound,
        certificate.core_edge_count,
        certificate.aggregate_collision_witness_lower_bound,
    ) == (222, 486, 374, 112, 66, 46)
    assert certificate.previous_s4_lower_bound == 112
    assert certificate.aggregate_weighted_s4_lower_bound == 1120
    assert certificate.bonferroni_fourth_order_credit == 640
    assert certificate.previous_family_upper_bound == 313_916_056
    assert certificate.family_upper_bound == 313_915_480
    assert certificate.incumbent == 313_239_661
    assert certificate.remaining_family_gap == 675_819
    assert certificate.family_status == "OPEN_STRICTLY_TIGHTENED"


def test_balanced_square_floor_matches_exhaustive_small_degree_oracle() -> None:
    for slots in range(1, 5):
        for total in range(0, 6 * slots + 1):
            expected = min(
                sum(value * value for value in values)
                for values in itertools.product(range(7), repeat=slots)
                if sum(values) == total
            )
            assert minimum_degree_square_sum(total, slots, maximum_per_slot=6) == expected


def test_cross_incidence_convexity_matches_exhaustive_small_oracle() -> None:
    for slots in range(1, 5):
        for total in range(0, 3 * slots + 1):
            expected = min(
                sum(comb(value, 2) for value in values)
                for values in itertools.product(range(4), repeat=slots)
                if sum(values) == total
            )
            assert minimum_collision_count(total, slots, maximum_per_slot=3) == expected


def test_core_edge_pair_collision_floor_matches_composition_oracle() -> None:
    for slots in range(1, 5):
        for total in range(0, 13):
            expected = min(
                sum(comb(value, 2) for value in values) for values in _compositions(total, slots)
            )
            assert minimum_pair_collision_count(total, slots) == expected


def test_weighted_witness_rule_matches_small_profile_assignment_oracle() -> None:
    profile_types = (
        (5, 112),
        (6, 679),
        (3, 448),
    )
    assert profile_types == K20_LOCAL_PROFILE_WITNESS_CAPACITIES_AND_WEIGHTS

    # Dynamic programming is an independent small oracle over quartet types:
    # each selected quartet pays its exact local S4 weight and covers at most
    # the listed number of collision witnesses.
    for witness_count in range(1, 47):
        best = [10**9] * (witness_count + 1)
        best[0] = 0
        for covered in range(witness_count + 1):
            for capacity, weight in profile_types:
                for take in range(1, min(capacity, witness_count - covered) + 1):
                    best[covered + take] = min(best[covered + take], best[covered] + weight)
        assert weighted_s4_lower_bound_from_witnesses(witness_count) <= best[witness_count]
        assert weighted_s4_lower_bound_from_witnesses(witness_count) == (
            112 * ceil(witness_count / 5)
        )


def test_exact_local_profile_weights_match_compressed_49_label_oracle() -> None:
    all_pairs = tuple(itertools.combinations(range(4), 2))
    diamond_pairs = tuple(pair for pair in all_pairs if pair != (2, 3))
    triple_pairs = {(0, 1), (0, 2), (1, 2)}

    profile_cases = (
        (
            tuple((1 << left) | (1 << right) for left, right in diamond_pairs),
            112,
        ),
        (
            tuple((1 << left) | (1 << right) for left, right in all_pairs),
            679,
        ),
        (
            (
                0b0111,
                *(
                    (1 << left) | (1 << right)
                    for left, right in all_pairs
                    if (left, right) not in triple_pairs
                ),
            ),
            448,
        ),
    )
    for supports, expected in profile_cases:
        profile = _profile_from_supports(supports)
        assert (
            compressed_four_ticket_intersection_count(
                profile,
                pool_size=49,
                draw_size=6,
                outright_matches=3,
            )
            == expected
        )


def test_bonferroni_credit_preserves_previous_floor_and_tightens_aggregate() -> None:
    assert k20_min_s2_s4_lower_bound_certificate().s4_lower_bound == 112
    assert bonferroni_fourth_order_credit(112) == 64
    assert family_upper_bound_from_s4(112) == 313_916_056
    assert bonferroni_fourth_order_credit(1120) == 640
    assert family_upper_bound_from_s4(1120) == 313_915_480
