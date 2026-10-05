"""Focused oracles for load-bearing R3 frontier realizability."""

from __future__ import annotations

from itertools import combinations, product
from math import comb

from lottolab.research.b649_k20_r3_anchor_incidence_bound_r5 import (
    anchor_incidence_profiles,
)
from lottolab.research.b649_k20_r3_frontier_realizability_bound_r8 import (
    JOINT_EXPRESSION_CONSTANT,
    R7_FRONTIER_POINTS,
    SUPPORT_WITNESS_BITMASKS,
    decode_support_witness_bitmasks,
    four_ticket_event_intersection_count,
    frozen_frontier_digest,
    load_bearing_frontier_states,
    run_compact_with_external_timeout,
    select_load_bearing_frontier,
    state_moment_floor,
    support_model_status,
    swap_anchor_sides,
    validate_support_assignment,
    witness_costs,
)


def _brute_support_exists(
    cell_capacities: tuple[int, ...],
    row_demands: tuple[tuple[int, ...], ...],
    maximum_pair_overlap: int,
) -> bool:
    cell_ranges: list[range] = []
    offset = 0
    for capacity in cell_capacities:
        cell_ranges.append(range(offset, offset + capacity))
        offset += capacity

    row_options: list[tuple[tuple[int, ...], ...]] = []
    for demands in row_demands:
        cell_choices = tuple(
            tuple(combinations(labels, demand))
            for labels, demand in zip(cell_ranges, demands, strict=True)
        )
        row_options.append(
            tuple(
                tuple(label for cell in selected for label in cell)
                for selected in product(*cell_choices)
            )
        )

    for supports in product(*row_options):
        if all(
            len(set(supports[left]) & set(supports[right])) <= maximum_pair_overlap
            for left in range(len(supports))
            for right in range(left + 1, len(supports))
        ):
            return True
    return False


def test_load_bearing_state_selection_is_frozen_and_anchor_symmetric() -> None:
    selected = select_load_bearing_frontier()
    states = load_bearing_frontier_states()

    assert len(R7_FRONTIER_POINTS) == 23
    assert frozen_frontier_digest() == (
        "271c3950b6d30d58d4baa5bb534894a60f17111b8458586fda0089447d1bc7d3"
    )
    assert tuple(point.identifier for point in selected) == tuple(
        state.identifier for state in states
    )
    assert tuple(point.upper_bound for point in selected) == (
        350_545_750,
        350_106_513,
        350_156_879,
        349_717_641,
        349_768_318,
        349_329_080,
        349_380_068,
    )
    assert all(point.upper_bound > 349_009_248 for point in selected)
    assert all(
        point.upper_bound <= 349_009_248
        for point in R7_FRONTIER_POINTS
        if point not in selected
    )

    profiles = anchor_incidence_profiles()
    for state in states:
        assert swap_anchor_sides(state.witness_counts) == state.mirrored_counts
        assert swap_anchor_sides(state.mirrored_counts) == state.witness_counts
        assert state.witness_counts != state.mirrored_counts
        assert sum(state.witness_counts) == sum(state.mirrored_counts) == 18
        for counts in (state.witness_counts, state.mirrored_counts):
            assert sum(
                count * profile.triple_recovery
                for count, profile in zip(counts, profiles, strict=True)
            ) == state.maximum_joint_s3


def test_reduced_support_model_matches_exhaustive_toy_realizability_oracle() -> None:
    cases = (
        ((2, 2), ((1, 1), (1, 1), (1, 1)), 1, True),
        ((1, 1), ((1, 1), (1, 1), (1, 1)), 1, False),
    )
    for capacities, demands, maximum_overlap, expected in cases:
        exact = _brute_support_exists(capacities, demands, maximum_overlap)
        status = support_model_status(
            capacities,
            demands,
            maximum_pair_overlap=maximum_overlap,
            wall_limit_seconds=2.0,
        )
        observed = status in {"OPTIMAL", "FEASIBLE"}

        assert exact is expected
        assert observed is expected


def test_compact_support_witness_bitmasks_round_trip() -> None:
    supports = ((0, 2, 48), (3, 12, 47), (8, 19, 25))
    bitmasks = tuple(sum(1 << label for label in support) for support in supports)

    assert decode_support_witness_bitmasks(bitmasks) == supports


def test_frozen_frontier_supports_are_realizable_and_have_expected_s4() -> None:
    states = load_bearing_frontier_states()
    observed_s4: list[int] = []
    expected_s4 = (0, 0, 0, 0, 2016, 2016, 5208)

    assert tuple(SUPPORT_WITNESS_BITMASKS) == tuple(
        state.identifier for state in states
    )
    for state, expected in zip(states, expected_s4, strict=True):
        supports = decode_support_witness_bitmasks(
            SUPPORT_WITNESS_BITMASKS[state.identifier]
        )

        assert validate_support_assignment(state.witness_counts, supports)
        residual_s2, s4 = witness_costs(state.witness_counts, supports)
        assert residual_s2 >= state_moment_floor(
            state.witness_counts
        ).residual_s2_lower_bound
        observed_s4.append(s4)
        assert s4 == expected

    assert tuple(observed_s4) == expected_s4


def test_compact_s4_relaxation_certifies_last_three_state_bounds() -> None:
    states = load_bearing_frontier_states()[-3:]
    observed = tuple(
        run_compact_with_external_timeout(state.identifier) for state in states
    )

    assert tuple(run["status"] for run in observed) == ("OPTIMAL",) * 3
    assert tuple(
        run["certified_minimum_lower_bound"] for run in observed
    ) == (2016, 2016, 4368)
    assert tuple(run["witness_s4"] for run in observed) == (2016, 2016, 5208)
    assert tuple(run["minimum_proven"] for run in observed) == (True, True, False)


def test_reduced_pair_tables_prove_state_specific_joint_moment_bounds() -> None:
    states = load_bearing_frontier_states()
    floors = tuple(state_moment_floor(state.witness_counts) for state in states)

    assert tuple(floor.residual_s2_lower_bound for floor in floors) == (
        49_545_272,
        48_617_016,
        48_491_576,
        47_567_660,
        46_647_356,
        45_750_544,
        45_776_416,
    )
    assert tuple(str(floor.minimum_outside_slope) for floor in floors) == (
        "448728",
        "448728",
        "446558",
        "446558",
        "433006",
        "433006",
        "433006",
    )
    assert tuple(floor.s4_pairwise_minimum_floor for floor in floors) == (
        0,
        0,
        0,
        0,
        336,
        336,
        1008,
    )
    assert tuple(
        JOINT_EXPRESSION_CONSTANT
        - sum(
            count * profile.pair_recovery_cost
            for count, profile in zip(
                state.witness_counts,
                anchor_incidence_profiles(),
                strict=True,
            )
        )
        + state.maximum_joint_s3
        - (floor.residual_s2_lower_bound + 8) // 9
        for state, floor in zip(states, floors, strict=True)
    ) == (
        346_864_727,
        346_524_977,
        346_592_703,
        346_252_470,
        346_408_514,
        346_065_270,
        346_116_183,
    )


def test_four_event_dp_matches_a_small_draw_special_enumeration() -> None:
    tickets = (
        frozenset((0, 1, 2)),
        frozenset((0, 3, 4)),
        frozenset((1, 3, 5)),
        frozenset((2, 4, 5)),
    )
    profile = [0] * 16
    for label in range(8):
        mask = sum(
            1 << ticket_index
            for ticket_index, ticket in enumerate(tickets)
            if label in ticket
        )
        profile[mask] += 1

    exact_dp = four_ticket_event_intersection_count(
        tuple(profile),
        pool_size=8,
        draw_size=3,
        outright_matches=2,
    )
    exact_oracle = sum(
        all(
            len(set(main_draw) & ticket) + int(special in ticket) >= 2
            for ticket in tickets
        )
        for main_draw in combinations(range(8), 3)
        for special in set(range(8)) - set(main_draw)
    )

    assert sum(profile) == 8
    assert exact_dp == exact_oracle


def test_pair_multiplicity_correction_is_valid_for_every_r3_state() -> None:
    assert all(
        9 * multiplicity - comb(multiplicity, 2) >= 9
        for multiplicity in range(1, 19)
    )
    assert 9 * 1 - comb(1, 2) == 9
    assert 9 * 18 - comb(18, 2) == 9
