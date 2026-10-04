"""Focused checks for the K20 r=4 count-vector realizability bound."""

from __future__ import annotations

from itertools import combinations, product
from math import comb

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    anchor_incidence_profiles,
    minimum_label_pair_mass,
)
from lottolab.research.b649_k20_r4_exact_anchor_realizability_r7 import (
    EXPECTED_GLOBAL_PAIR_RESIDUAL_FLOORS,
    analyze_r4_realizability,
    component_assignment_penalty_floor,
    count_vector_space_size,
    enumerate_count_vectors_with_good_floor,
    maximum_overlap_components,
    type_count_metrics,
)


def _independent_count_vectors(
    type_count: int,
    ticket_count: int,
    good_type_index: int,
    minimum_good_count: int,
) -> set[tuple[int, ...]]:
    """Brute-force a small ordered assignment space as a generator oracle."""

    result: set[tuple[int, ...]] = set()
    for assignment in product(range(type_count), repeat=ticket_count):
        if assignment.count(good_type_index) < minimum_good_count:
            continue
        counts = [0] * type_count
        for type_index in assignment:
            counts[type_index] += 1
        result.add(tuple(counts))
    return result


def test_count_vector_generator_matches_independent_small_oracle() -> None:
    generated = set(
        enumerate_count_vectors_with_good_floor(
            type_count=3,
            ticket_count=4,
            good_type_index=1,
            minimum_good_count=2,
        )
    )
    expected = _independent_count_vectors(3, 4, 1, 2)
    assert generated == expected
    assert len(generated) == 6
    assert count_vector_space_size(32, 18) == comb(49, 18)


def test_anchor_cell_mass_and_component_facts_exhaustive_toy_assignments() -> None:
    pool_size = 10
    draw_size = 3
    maximum_overlap = 2
    anchor_a = frozenset((0, 1, 2))
    anchor_b = frozenset((0, 1, 3))
    cells = (
        anchor_a & anchor_b,
        anchor_a - anchor_b,
        anchor_b - anchor_a,
        frozenset(range(4, pool_size)),
    )
    ticket_candidates = tuple(
        ticket
        for ticket in combinations(range(pool_size), draw_size)
        if len(set(ticket) & anchor_a) <= maximum_overlap
        and len(set(ticket) & anchor_b) <= maximum_overlap
    )
    total_assignments = 0

    for left, right in combinations(ticket_candidates, 2):
        left_set = frozenset(left)
        right_set = frozenset(right)
        overlap = len(left_set & right_set)
        if overlap > maximum_overlap:
            continue
        total_assignments += 1
        tickets = (left_set, right_set)
        cell_incidences = tuple(
            sum(len(ticket & cell) for ticket in tickets) for cell in cells
        )
        actual_cell_pair_mass = sum(
            sum(
                count * (count - 1) // 2
                for count in (
                    sum(label in ticket for ticket in tickets) for label in cell
                )
            )
            for cell in cells
        )
        cellwise_floor = sum(
            minimum_label_pair_mass(incidences, len(cell))
            for incidences, cell in zip(cell_incidences, cells, strict=True)
        )
        assert actual_cell_pair_mass == overlap
        assert actual_cell_pair_mass >= cellwise_floor

        overlap_components = 1 if overlap else 2
        component_edge_capacity = comb(2 - overlap_components + 1, 2)
        assert int(overlap > 0) <= component_edge_capacity

        full_portfolio = (anchor_a, anchor_b, *tickets)
        full_pair_mass = sum(
            count * (count - 1) // 2
            for count in (
                sum(label in ticket for ticket in full_portfolio)
                for label in range(pool_size)
            )
        )
        assert full_pair_mass >= minimum_label_pair_mass(
            len(full_portfolio) * draw_size, pool_size
        )

    assert total_assignments > 0


def test_dangerous_type_vector_cell_masses_use_full_system_floor() -> None:
    profiles = anchor_incidence_profiles()
    good_index = next(
        index
        for index, profile in enumerate(profiles)
        if profile.shared == profile.a_only == profile.b_only == 0
    )
    best_non_good_index = next(
        index
        for index, profile in enumerate(profiles)
        if profile.signature == (0, 0, 1, 5)
    )

    all_good = [0] * len(profiles)
    all_good[good_index] = 18
    good_metrics = type_count_metrics(
        tuple(all_good), profiles, EXPECTED_GLOBAL_PAIR_RESIDUAL_FLOORS
    )
    assert good_metrics.local_recovery_loss == 0
    assert good_metrics.cell_incidences == (0, 0, 0, 108)
    assert good_metrics.cellwise_pair_mass_floor == 93
    assert good_metrics.full_system_pair_mass_floor == 89
    assert good_metrics.outside_pair_mass_floor == 93

    one_best = [0] * len(profiles)
    one_best[good_index] = 17
    one_best[best_non_good_index] = 1
    best_metrics = type_count_metrics(
        tuple(one_best), profiles, EXPECTED_GLOBAL_PAIR_RESIDUAL_FLOORS
    )
    assert best_metrics.local_recovery_loss == 436_100
    assert best_metrics.cell_incidences == (0, 0, 1, 107)
    assert best_metrics.cellwise_pair_mass_floor == 91
    assert best_metrics.full_system_pair_mass_floor == 88
    assert best_metrics.outside_pair_mass_floor == 91


def test_bounded_component_assignment_tightens_only_dangerous_cases() -> None:
    assert maximum_overlap_components(18) == 6
    assert maximum_overlap_components(18, special_outside_degree=5) == 6

    good_floor, good_cases = component_assignment_penalty_floor(18, 108, False)
    special_floor, special_cases = component_assignment_penalty_floor(18, 107, True)
    assert good_floor == 8_067_192
    assert special_floor == 8_067_192
    assert len(good_cases) == len(special_cases) == 6

    good_by_component_count = {case.component_count: case for case in good_cases}
    assert good_by_component_count[4].threshold_one_rank == 14
    assert good_by_component_count[4].pair_penalty_floor == 8_067_192
    assert not good_by_component_count[4].repeated_overlap_forced
    assert good_by_component_count[5].repeated_overlap_forced
    assert good_by_component_count[6].repeated_overlap_forced

    special_by_component_count = {case.component_count: case for case in special_cases}
    assert special_by_component_count[5].distinct_pair_capacity == 91
    assert special_by_component_count[5].repeated_overlap_forced
    assert special_by_component_count[6].repeated_overlap_forced


def test_exact_r4_realizability_certificate() -> None:
    certificate = analyze_r4_realizability()
    assert certificate.total_type_count_vector_space == comb(49, 18)
    assert certificate.type_count_vector_count == 52_360
    assert certificate.pruned_lower_good_vector_count == comb(49, 18) - 52_360
    assert certificate.dangerous_vector_count == 3
    assert certificate.realizable_dangerous_vector_count == 3
    assert certificate.mandatory_outside_pair_penalty == 8_067_192
    assert certificate.r4_bound == 354_519_816
    assert certificate.r4_status == "TIGHTENED_OPEN_SUCCESS_B"
    assert certificate.family_a_recomputed_bound == 354_519_816
    assert certificate.family_a_bottleneck_r == 4
    assert certificate.remaining_gap == 41_280_155

    by_label = {result.label: result for result in certificate.dangerous_vectors}
    assert by_label["18_GOOD"].local_recovery_loss == 0
    assert by_label["18_GOOD"].outside_pair_mass_floor == 93
    assert by_label["18_GOOD"].total_recovery_reduction == 8_067_192
    assert by_label["18_GOOD"].r4_bound == 354_519_816
    assert by_label["17_GOOD_PLUS_ONE_BEST_NON_GOOD"].local_recovery_loss == 436_100
    assert by_label["17_GOOD_PLUS_ONE_BEST_NON_GOOD"].outside_pair_mass_floor == 91
    assert by_label["17_GOOD_PLUS_ONE_BEST_NON_GOOD"].total_recovery_reduction == 8_503_292
    assert by_label["17_GOOD_PLUS_ONE_BEST_NON_GOOD"].r4_bound == 354_083_716


__all__ = [
    "test_anchor_cell_mass_and_component_facts_exhaustive_toy_assignments",
    "test_bounded_component_assignment_tightens_only_dangerous_cases",
    "test_count_vector_generator_matches_independent_small_oracle",
    "test_dangerous_type_vector_cell_masses_use_full_system_floor",
    "test_exact_r4_realizability_certificate",
]
