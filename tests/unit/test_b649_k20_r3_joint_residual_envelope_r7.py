"""Focused oracles for the K20 r3 joint residual S2/S3 envelope."""

from __future__ import annotations

from itertools import combinations, product
from math import comb

from lottolab.research.b649_k20_r3_exact_anchor_neighborhood_envelope_r6 import (
    balanced_pair_mass,
    candidate_type_count_vectors,
)
from lottolab.research.b649_k20_r3_joint_residual_envelope_r7 import (
    CURRENT_R3_BOUND,
    JOINT_LOCAL_LOSS_CUTOFF,
    balanced_frequency_histogram,
    joint_residual_census,
    pareto_s2_s3_pairs,
    reused_exact_type_count_vectors,
)


def test_balanced_outside_frequency_floor_matches_a_small_exact_oracle() -> None:
    histogram = balanced_frequency_histogram(5, 3)
    observed_pair_mass = sum(
        labels * comb(frequency, 2) for frequency, labels in histogram
    )
    exact_pair_masses = tuple(
        sum(comb(frequency, 2) for frequency in frequencies)
        for frequencies in product(range(6), repeat=3)
        if sum(frequencies) == 5
    )

    assert histogram == ((1, 1), (2, 2))
    assert observed_pair_mass == min(exact_pair_masses) == 2
    assert observed_pair_mass == balanced_pair_mass(5, 3)


def test_joint_s2_s3_frontier_matches_all_three_event_toy_states() -> None:
    universe = range(4)
    events = tuple(frozenset(pair) for pair in combinations(universe, 2))
    moment_pairs: list[tuple[int, int]] = []
    exact_union_bounds: list[int] = []
    single_event_mass = 3 * len(events[0])

    for configuration in product(events, repeat=3):
        s2 = sum(
            len(left & right)
            for left, right in combinations(configuration, 2)
        )
        s3 = len(configuration[0] & configuration[1] & configuration[2])
        exact_union = len(configuration[0] | configuration[1] | configuration[2])
        moment_pairs.append((s2, s3))
        exact_union_bounds.append(single_event_mass - s2 + s3)
        assert single_event_mass - s2 + s3 == exact_union

    frontier = pareto_s2_s3_pairs(moment_pairs)
    frontier_union_bound = max(single_event_mass - s2 + s3 for s2, s3 in frontier)
    assert frontier_union_bound == max(exact_union_bounds)

    incompatible_extremes = ((10, 0), (15, 50), (20, 100), (20, 90))
    compatible_frontier = pareto_s2_s3_pairs(incompatible_extremes)
    joint_maximum = max(s3 - s2 for s2, s3 in compatible_frontier)
    invalid_cross_state_maximum = max(
        s3 for _, s3 in incompatible_extremes
    ) - min(s2 for s2, _ in incompatible_extremes)

    assert compatible_frontier == ((10, 0), (15, 50), (20, 100))
    assert joint_maximum == 80
    assert invalid_cross_state_maximum == 90
    assert joint_maximum < invalid_cross_state_maximum


def test_exact_r6_type_count_vectors_are_reused_and_jointly_compressed() -> None:
    reused = reused_exact_type_count_vectors()
    census = joint_residual_census()

    assert reused == candidate_type_count_vectors()
    assert census.reused_vector_count == len(reused) == 2_683
    assert census.reused_vector_sha256 == (
        "6e6dbdf5bb9cdf2905a7c8dbc061a032cb0dce005b3fb80b062f40eb64e1581f"
    )
    assert census.candidate_vector_count == 10_816
    assert census.supplemental_vector_count == 8_133
    assert census.feasible_reused_vector_count == 2_683
    assert census.feasible_supplemental_vector_count == 8_133
    assert census.feasible_vector_count == 10_816
    assert len(census.states) == 10_117
    assert len(census.s2_s3_envelope) == census.s2_level_count == 398
    assert len(census.frontier) == 23
    maximum_s3_by_s2: dict[int, int] = {}
    for state in census.states:
        maximum_s3_by_s2[state.joint_s2] = max(
            state.joint_s3, maximum_s3_by_s2.get(state.joint_s2, -1)
        )
    assert tuple(
        (point.joint_s2, point.maximum_joint_s3)
        for point in census.s2_s3_envelope
    ) == tuple(sorted(maximum_s3_by_s2.items()))
    assert all(
        any(
            state.joint_s2 == point.joint_s2
            and state.joint_s3 == point.maximum_joint_s3
            and state.witness_counts == point.witness_counts
            for state in census.states
        )
        for point in census.s2_s3_envelope
    )
    assert all(
        point.maximizing_vector_count
        == sum(
            state.represented_vector_count
            for state in census.states
            if state.joint_s2 == point.joint_s2
            and state.joint_s3 == point.maximum_joint_s3
        )
        for point in census.s2_s3_envelope
    )
    assert sum(
        state.represented_vector_count for state in census.states
    ) == census.feasible_vector_count


def test_critical_anchor_state_keeps_s2_s3_and_cell_consumption_together() -> None:
    census = joint_residual_census()
    critical_counts = (7,) + (0,) * 3 + (11,) + (0,) * 25
    state = next(
        state for state in census.states if state.witness_counts == critical_counts
    )

    assert state.local_loss == 4_871_790
    assert state.anchor_pair_s2 == 9_009_000
    assert state.anchor_triple_s3 == 427_140
    assert state.residual_pair_intersection_mass_floor == 16_416_064
    assert state.residual_pair_union_penalty == 1_824_008
    assert state.complementary_forest_floor == 1_148_000
    assert state.applied_residual_union_penalty == 1_824_008
    assert state.joint_s2 == 10_833_008
    assert state.joint_s3 == 427_140
    assert state.cell_incidences == (0, 11, 0, 97)
    assert state.outside_multiplicity_floor == ((2, 23), (3, 17))
    assert state.upper_bound == 350_545_750


def test_result_maximizes_the_realized_frontier_and_bounds_the_omitted_tail() -> None:
    census = joint_residual_census()
    frontier_bound = max(point.upper_bound for point in census.frontier)
    expected_tail_bound = 357_241_548 - JOINT_LOCAL_LOSS_CUTOFF - 1

    assert census.tail_bound == expected_tail_bound == 350_545_749
    assert frontier_bound == 350_545_750
    assert census.r3_bound == max(frontier_bound, expected_tail_bound)
    assert census.r3_bound < CURRENT_R3_BOUND
    assert census.bound_source == "JOINT_S2_S3_FRONTIER"
