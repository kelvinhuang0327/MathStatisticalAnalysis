"""Focused exact checks for the K20 r=3 anchor-incidence certificate."""

from __future__ import annotations

from itertools import combinations

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    pair_intersection_count,
    triple_intersection_count,
)
from lottolab.research.b649_k20_r3_anchor_incidence_bound_r5 import (
    EXPECTED_GOOD_PAIR_RESIDUAL_FLOORS,
    EXPECTED_GOOD_TRIPLES,
    EXPECTED_PAIR_COUNTS,
    anchor_incidence_profiles,
    anchor_tradeoff,
    exact_pair_counts,
    family_a_result_record,
    feasible_anchor_incidence_signatures,
    revised_r3_bound,
)

ToyOutcome = tuple[tuple[int, ...], int]


def _wins(ticket: tuple[int, ...], draw: tuple[int, ...], special: int) -> bool:
    matches = len(set(ticket) & set(draw))
    return matches >= 2 or (matches == 1 and special in ticket)


def _find_root(parent: list[int], node: int) -> int:
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


def test_exact_pair_triple_counts_and_all_anchor_incidence_types() -> None:
    assert exact_pair_counts() == EXPECTED_PAIR_COUNTS == (
        107_800,
        574_000,
        1_695_988,
        3_469_942,
        6_224_512,
        10_776_332,
        18_611_432,
    )
    assert tuple(
        triple_intersection_count((0, 0, overlap), 0)
        for overlap in range(1, 4)
    ) == EXPECTED_GOOD_TRIPLES == (0, 2_240, 9_485)
    assert tuple(
        exact_pair_counts()[overlap]
        - 2 * triple_intersection_count((0, 0, overlap), 0)
        for overlap in range(1, 4)
    ) == EXPECTED_GOOD_PAIR_RESIDUAL_FLOORS == (
        574_000,
        1_691_508,
        3_450_972,
    )

    profiles = anchor_incidence_profiles()
    assert len(profiles) == 30
    assert tuple(
        (
            profile.shared,
            profile.a_only,
            profile.b_only,
            profile.outside,
            profile.triple_recovery,
            profile.pair_recovery_cost,
            profile.net_recovery,
        )
        for profile in profiles
    ) == (
        (0, 0, 0, 6, 9_485, 215_600, -206_115),
        (0, 0, 1, 5, 32_795, 681_800, -649_005),
        (0, 0, 2, 4, 55_713, 1_803_788, -1_748_075),
        (0, 0, 3, 3, 76_692, 3_577_742, -3_501_050),
        (0, 1, 0, 5, 32_795, 681_800, -649_005),
        (0, 1, 1, 4, 109_893, 1_148_000, -1_038_107),
        (0, 1, 2, 3, 193_179, 2_269_988, -2_076_809),
        (0, 1, 3, 2, 286_482, 4_043_942, -3_757_460),
        (0, 2, 0, 4, 55_713, 1_803_788, -1_748_075),
        (0, 2, 1, 3, 193_179, 2_269_988, -2_076_809),
        (0, 2, 2, 2, 313_614, 3_391_976, -3_078_362),
        (0, 2, 3, 1, 419_349, 5_165_930, -4_746_581),
        (0, 3, 0, 3, 76_692, 3_577_742, -3_501_050),
        (0, 3, 1, 2, 286_482, 4_043_942, -3_757_460),
        (0, 3, 2, 1, 419_349, 5_165_930, -4_746_581),
        (0, 3, 3, 0, 466_032, 6_939_884, -6_473_852),
        (1, 0, 0, 5, 109_445, 1_148_000, -1_038_555),
        (1, 0, 1, 4, 226_317, 2_269_988, -2_043_671),
        (1, 0, 2, 3, 333_102, 4_043_942, -3_710_840),
        (1, 1, 0, 4, 226_317, 2_269_988, -2_043_671),
        (1, 1, 1, 3, 441_042, 3_391_976, -2_950_934),
        (1, 1, 2, 2, 655_557, 5_165_930, -4_510_373),
        (1, 2, 0, 3, 333_102, 4_043_942, -3_710_840),
        (1, 2, 1, 2, 655_557, 5_165_930, -4_510_373),
        (1, 2, 2, 1, 977_816, 6_939_884, -5_962_068),
        (2, 0, 0, 4, 580_713, 3_391_976, -2_811_263),
        (2, 0, 1, 3, 837_375, 5_165_930, -4_328_555),
        (2, 1, 0, 3, 837_375, 5_165_930, -4_328_555),
        (2, 1, 1, 2, 1_159_627, 6_939_884, -5_780_257),
        (3, 0, 0, 3, 1_585_689, 6_939_884, -5_354_195),
    )


def test_incidence_constraints_match_an_exhaustive_small_anchor_toy() -> None:
    pool = set(range(11))
    anchor_a = {0, 1, 2}
    anchor_b = {0, 3, 4}
    shared = anchor_a & anchor_b
    a_only = anchor_a - anchor_b
    b_only = anchor_b - anchor_a
    outside = pool - anchor_a - anchor_b
    observed: set[tuple[int, int, int, int]] = set()

    for ticket in combinations(sorted(pool), 3):
        labels = set(ticket)
        if len(labels & anchor_a) > 1 or len(labels & anchor_b) > 1:
            continue
        observed.add(
            (
                len(labels & shared),
                len(labels & a_only),
                len(labels & b_only),
                len(labels & outside),
            )
        )

    assert observed == set(feasible_anchor_incidence_signatures(1, 3))
    assert len(observed) == 5


def test_weighted_forest_census_proves_the_full_good_count_tradeoff() -> None:
    tradeoff = anchor_tradeoff()
    assert tradeoff.good_local_net_recovery == -206_115
    assert tradeoff.maximum_non_good_local_net_recovery == -649_005
    assert tradeoff.minimum_non_good_local_loss == 442_890
    assert tradeoff.good_ticket_collision_threshold == 7
    assert tradeoff.minimum_forced_penalty_at_or_above_threshold == 1_148_000
    assert tuple(case.minimum_label_pair_mass for case in tradeoff.cases) == (
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        2,
        8,
        14,
        20,
        26,
        32,
        38,
        48,
        60,
        72,
        84,
        96,
    )
    assert tuple(case.outside_overlap_penalty for case in tradeoff.cases) == (
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1_148_000,
        2_296_000,
        2_870_000,
        3_444_000,
        4_018_000,
        4_592_000,
        5_166_000,
        5_740_000,
        6_314_000,
        6_888_000,
        7_462_000,
        8_036_000,
    )
    assert tuple(case.total_recovery_reduction for case in tradeoff.cases) == (
        7_972_020,
        7_529_130,
        7_086_240,
        6_643_350,
        6_200_460,
        5_757_570,
        5_314_680,
        6_019_790,
        6_724_900,
        6_856_010,
        6_987_120,
        7_118_230,
        7_249_340,
        7_380_450,
        7_511_560,
        7_642_670,
        7_773_780,
        7_904_890,
        8_036_000,
    )
    assert tradeoff.worst_case_good_ticket_count == 6
    assert tradeoff.guaranteed_recovery_reduction == 5_314_680


def test_revised_r3_and_family_a_handoff_bounds() -> None:
    record = family_a_result_record()
    assert revised_r3_bound() == 351_926_868
    assert record["R3_PRIOR_BOUND"] == 356_667_548
    assert record["R3_BOUND"] == 351_926_868
    assert record["R4_BOUND"] == 354_779_928
    assert record["R5_BOUND"] == 350_778_728
    assert record["R6_BOUND"] == 343_869_728
    assert record["FAMILY_A_BOUND"] == 354_779_928
    assert record["FAMILY_A_STATUS"] == "TIGHTENED_OPEN"
    assert record["IMPROVEMENT_VS_CURRENT_R3_BOUND"] == 4_740_680
    assert record["REMAINING_GAP"] == 41_540_267
    assert record["SUCCESS_A"] is False
    assert record["SUCCESS_B"] is True
    assert record["SOLVER_STATUS"] == "NOT_NEEDED_ANALYTIC_EXACT_FINITE_CENSUS"
    assert record["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert record["PRODUCTION_MUTATION"] == "NONE"
    tradeoff_rows = record["OUTSIDE_OVERLAP_PENALTY"]["TRADEOFF_BY_GOOD_TICKET_COUNT"]
    assert len(tradeoff_rows) == 19
    assert tuple(int(value) for value in tradeoff_rows[6].split(",")) == (
        6,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        5_314_680,
        5_314_680,
    )


def test_exhaustive_toy_residual_events_obey_pair_and_forest_corrections() -> None:
    pool_size, draw_size = 11, 3
    pool = set(range(pool_size))
    anchor_a = (0, 1, 2)
    anchor_b = (0, 3, 4)
    anchor_union_labels = set(anchor_a) | set(anchor_b)
    outside_labels = pool - anchor_union_labels
    outside_tickets = tuple(combinations(sorted(outside_labels), draw_size))
    draws = tuple(combinations(range(pool_size), draw_size))
    outcomes: tuple[ToyOutcome, ...] = tuple(
        (draw, special)
        for draw in draws
        for special in pool - set(draw)
    )
    tickets = (anchor_a, anchor_b, *outside_tickets)
    events: dict[tuple[int, ...], frozenset[ToyOutcome]] = {
        ticket: frozenset(
            (draw, special) for draw, special in outcomes if _wins(ticket, draw, special)
        )
        for ticket in tickets
    }
    anchor_event_union = events[anchor_a] | events[anchor_b]
    residuals: dict[tuple[int, ...], frozenset[ToyOutcome]] = {
        ticket: events[ticket] - anchor_event_union for ticket in outside_tickets
    }
    neighborhood_count = 0

    for neighborhood in combinations(outside_tickets, 3):
        overlaps = tuple(
            len(set(left) & set(right)) for left, right in combinations(neighborhood, 2)
        )
        if max(overlaps) > 1:
            continue
        neighborhood_count += 1

        frequencies = tuple(
            sum(label in ticket for ticket in neighborhood) for label in outside_labels
        )
        label_pair_mass = sum(frequency * (frequency - 1) // 2 for frequency in frequencies)
        assert label_pair_mass >= 3

        parent = [0, 1, 2]
        forest_intersection_sum = 0
        for (left_index, left), (right_index, right) in combinations(
            tuple(enumerate(neighborhood)), 2
        ):
            overlap = len(set(left) & set(right))
            if overlap == 0:
                continue
            pair_count = pair_intersection_count(
                overlap,
                pool_size=pool_size,
                draw_size=draw_size,
                outright_matches=2,
            )
            anchor_triple = triple_intersection_count(
                (0, 0, overlap),
                0,
                pool_size=pool_size,
                draw_size=draw_size,
                outright_matches=2,
            )
            residual_pair_floor = pair_count - 2 * anchor_triple
            actual_intersection = len(residuals[left] & residuals[right])
            assert actual_intersection >= residual_pair_floor

            left_root = _find_root(parent, left_index)
            right_root = _find_root(parent, right_index)
            if left_root != right_root:
                parent[right_root] = left_root
                forest_intersection_sum += actual_intersection

        residual_union: set[ToyOutcome] = set()
        for ticket in neighborhood:
            residual_union.update(residuals[ticket])
        residual_sum = sum(len(residuals[ticket]) for ticket in neighborhood)
        assert len(residual_union) <= residual_sum - forest_intersection_sum

    assert neighborhood_count == 120
