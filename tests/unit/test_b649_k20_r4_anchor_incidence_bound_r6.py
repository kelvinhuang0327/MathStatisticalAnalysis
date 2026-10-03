"""Focused exact tests for the K20 r=4 anchor-incidence certificate."""

from __future__ import annotations

from itertools import combinations

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS,
    EXPECTED_PAIR_COUNTS,
    active_pair_residual_floors,
    anchor_incidence_profiles,
    exact_joint_win_count,
    exact_residual_pair_intersection,
    good_pair_anchor_four_way_count,
    legal_anchor_incidence_signatures,
    minimum_label_pair_mass,
    minimum_weighted_forest_census,
    pair_intersection_count,
    pair_intersection_table,
    r4_tradeoff,
    triple_intersection_count,
)

Outcome = tuple[tuple[int, ...], int]


def _outcomes(pool_size: int, draw_size: int) -> tuple[Outcome, ...]:
    return tuple(
        (draw, special)
        for draw in combinations(range(pool_size), draw_size)
        for special in range(pool_size)
        if special not in draw
    )


def _wins(ticket: tuple[int, ...], outcome: Outcome, outright_matches: int) -> bool:
    draw, special = outcome
    matches = sum(label in draw for label in ticket)
    return matches >= outright_matches or (
        matches == outright_matches - 1 and special in ticket
    )


def _brute_joint(
    tickets: tuple[tuple[int, ...], ...],
    pool_size: int,
    draw_size: int,
    outright_matches: int,
) -> int:
    return sum(
        all(_wins(ticket, outcome, outright_matches) for ticket in tickets)
        for outcome in _outcomes(pool_size, draw_size)
    )


def _membership_capacities(
    tickets: tuple[tuple[int, ...], ...], pool_size: int
) -> tuple[int, ...]:
    capacities = [0] * (1 << len(tickets))
    for label in range(pool_size):
        mask = sum(
            1 << index for index, ticket in enumerate(tickets) if label in ticket
        )
        capacities[mask] += 1
    return tuple(capacities)


def _ticket_for_signature(signature: tuple[int, int, int, int]) -> tuple[int, ...]:
    shared, a_only, b_only, outside = signature
    return tuple(
        sorted(
            (0, 1)[:shared]
            + (2,)[:a_only]
            + (3,)[:b_only]
            + tuple(range(4, 10))[:outside]
        )
    )


def test_exact_pair_table_and_all_r4_anchor_type_contributions() -> None:
    assert pair_intersection_table() == EXPECTED_PAIR_COUNTS
    assert pair_intersection_count(6) == 18_611_432

    profiles = anchor_incidence_profiles()
    assert len(profiles) == 32
    assert len({profile.signature for profile in profiles}) == 32
    assert tuple(profile.triple_recovery for profile in profiles) == (
        25_760, 55_860, 78_288, 55_860, 180_852, 292_740, 78_288, 292_740,
        440_370, 210_840, 330_036, 428_001, 330_036, 602_763, 870_891,
        428_001, 870_891, 1_301_412, 875_490, 1_107_099, 1_322_433,
        1_107_099, 1_482_957, 1_860_152, 1_322_433, 1_860_152,
        2_418_892, 2_127_342, 2_558_668, 2_558_668, 2_989_462, 4_540_102,
    )

    for profile in profiles:
        assert sum(profile.signature) == 6
        assert profile.overlap_with_a == profile.shared + profile.a_only
        assert profile.overlap_with_b == profile.shared + profile.b_only
        assert profile.pair_recovery_cost == (
            EXPECTED_PAIR_COUNTS[profile.overlap_with_a]
            + EXPECTED_PAIR_COUNTS[profile.overlap_with_b]
        )
        assert profile.net_recovery == (
            profile.triple_recovery - profile.pair_recovery_cost
        )
    assert active_pair_residual_floors() == EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS


def test_anchor_incidence_types_match_exhaustive_small_model() -> None:
    pool_size = 10
    draw_size = 3
    anchor_a = {0, 1, 2}
    anchor_b = {0, 1, 3}
    shared = anchor_a & anchor_b
    a_only = anchor_a - anchor_b
    b_only = anchor_b - anchor_a
    outside = set(range(pool_size)) - anchor_a - anchor_b

    observed: set[tuple[int, int, int, int]] = set()
    for ticket in combinations(range(pool_size), draw_size):
        labels = set(ticket)
        if len(labels & anchor_a) > 2 or len(labels & anchor_b) > 2:
            continue
        observed.add(
            (
                len(labels & shared),
                len(labels & a_only),
                len(labels & b_only),
                len(labels & outside),
            )
        )

    expected = set(legal_anchor_incidence_signatures(2, draw_size, pool_size))
    assert observed == expected
    assert len(observed) == 9


def test_exact_pair_triple_and_residual_counts_match_toy_outcomes() -> None:
    pool_size = 10
    draw_size = 3
    outright_matches = 2
    anchor_a = (0, 1, 2)
    anchor_b = (0, 1, 3)

    for overlap in range(draw_size + 1):
        outside = tuple(label for label in range(4, pool_size))
        second = tuple(anchor_a[:overlap]) + outside[: draw_size - overlap]
        assert pair_intersection_count(
            overlap, pool_size, draw_size, outright_matches
        ) == _brute_joint(
            (anchor_a, second), pool_size, draw_size, outright_matches
        )

    for signature in legal_anchor_incidence_signatures(2, draw_size, pool_size):
        ticket_c = _ticket_for_signature(signature)
        tickets = (anchor_a, anchor_b, ticket_c)
        overlaps = (
            len(set(anchor_a) & set(anchor_b)),
            len(set(anchor_a) & set(ticket_c)),
            len(set(anchor_b) & set(ticket_c)),
        )
        common = len(set(anchor_a) & set(anchor_b) & set(ticket_c))
        brute = _brute_joint(tickets, pool_size, draw_size, outright_matches)
        assert exact_joint_win_count(
            _membership_capacities(tickets, pool_size), draw_size, outright_matches
        ) == brute
        assert triple_intersection_count(
            overlaps, common, pool_size, draw_size, outright_matches
        ) == brute

    first = (4, 5, 6)
    good_type = (0, 0, 0, draw_size)
    toy_pairs = ((7, 8, 9), (4, 7, 8), (4, 5, 7))
    anchors = (anchor_a, anchor_b)
    anchor_events = {
        ticket: frozenset(
            outcome
            for outcome in _outcomes(pool_size, draw_size)
            if _wins(ticket, outcome, outright_matches)
        )
        for ticket in anchors
    }
    anchor_union = anchor_events[anchor_a] | anchor_events[anchor_b]

    for overlap, second in enumerate(toy_pairs):
        exact = exact_residual_pair_intersection(
            good_type,
            good_type,
            (0, 0, 0, overlap),
            2,
            pool_size,
            draw_size,
            outright_matches,
        )
        first_residual = frozenset(
            outcome
            for outcome in _outcomes(pool_size, draw_size)
            if _wins(first, outcome, outright_matches)
        ) - anchor_union
        second_residual = frozenset(
            outcome
            for outcome in _outcomes(pool_size, draw_size)
            if _wins(second, outcome, outright_matches)
        ) - anchor_union
        assert exact == len(first_residual & second_residual)

        four_way = good_pair_anchor_four_way_count(
            2, overlap, pool_size, draw_size, outright_matches
        )
        assert four_way == _brute_joint(
            (anchor_a, anchor_b, first, second),
            pool_size,
            draw_size,
            outright_matches,
        )
        inclusion_exclusion = (
            pair_intersection_count(overlap, pool_size, draw_size, outright_matches)
            - 2
            * triple_intersection_count(
                (0, 0, overlap), 0, pool_size, draw_size, outright_matches
            )
            + four_way
        )
        assert exact == inclusion_exclusion


def _rank_floor(edge_count: int) -> int:
    rank = 0
    while rank * (rank + 1) // 2 < edge_count:
        rank += 1
    return rank


def test_exhaustive_good_ticket_toys_obey_forest_census() -> None:
    pool_size = 10
    draw_size = 3
    outright_matches = 2
    anchor_a = (0, 1, 2)
    anchor_b = (0, 1, 3)
    outside_tickets = tuple(combinations(range(4, pool_size), draw_size))
    outcomes = _outcomes(pool_size, draw_size)

    events = {
        ticket: frozenset(
            outcome for outcome in outcomes if _wins(ticket, outcome, outright_matches)
        )
        for ticket in (anchor_a, anchor_b, *outside_tickets)
    }
    anchor_union = events[anchor_a] | events[anchor_b]
    residuals = {
        ticket: events[ticket] - anchor_union for ticket in outside_tickets
    }
    pair_weights = tuple(
        pair_intersection_count(overlap, pool_size, draw_size, outright_matches)
        - 2
        * triple_intersection_count(
            (0, 0, overlap), 0, pool_size, draw_size, outright_matches
        )
        + good_pair_anchor_four_way_count(
            2, overlap, pool_size, draw_size, outright_matches
        )
        for overlap in range(3)
    )
    assert pair_weights == tuple(sorted(pair_weights))
    outside_label_count = pool_size - (2 * draw_size - 2)
    pair_mass_floor = minimum_label_pair_mass(3 * draw_size, outside_label_count)
    census = minimum_weighted_forest_census(3, pair_mass_floor, pair_weights)

    neighborhood_count = 0
    for neighborhood in combinations(outside_tickets, 3):
        pair_rows = tuple(
            (
                len(set(left) & set(right)),
                len(residuals[left] & residuals[right]),
            )
            for left, right in combinations(neighborhood, 2)
        )
        overlaps = tuple(row[0] for row in pair_rows)
        weights = tuple(row[1] for row in pair_rows)
        assert sum(overlaps) >= pair_mass_floor
        assert all(weight >= pair_weights[overlap] for overlap, weight in pair_rows)

        maximum_forest = sum(sorted(weights, reverse=True)[:2])
        threshold_edges = tuple(
            sum(overlap >= threshold for overlap in overlaps)
            for threshold in (1, 2)
        )
        ranks = tuple(_rank_floor(count) for count in threshold_edges)
        forest_floor = 2 * pair_weights[0] + sum(
            (pair_weights[index + 1] - pair_weights[index]) * ranks[index]
            for index in range(2)
        )
        assert maximum_forest >= forest_floor
        assert maximum_forest >= census.lower_bound_penalty

        residual_union: set[Outcome] = set()
        for ticket in neighborhood:
            residual_union.update(residuals[ticket])
        residual_sum = sum(len(residuals[ticket]) for ticket in neighborhood)
        assert len(residual_union) <= residual_sum - maximum_forest
        neighborhood_count += 1

    assert neighborhood_count == 1_140


def test_finite_r4_tradeoff_certificate() -> None:
    tradeoff = r4_tradeoff()
    assert len(tradeoff.cases) == 190
    assert tradeoff.active_pair_residual_floors == EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS
    assert tradeoff.good_local_net_recovery == -189_840
    assert tradeoff.maximum_non_good_net_recovery == -625_940
    assert tradeoff.second_best_non_good_net_recovery == -937_160
    assert tradeoff.uncorrected_all_good_bound == 362_587_008
    assert tradeoff.guaranteed_recovery_reduction == 8_054_564
    assert tradeoff.minimizing_case.good_ticket_count == 17
    assert tradeoff.minimizing_case.best_non_good_count == 1
    assert tradeoff.minimizing_case.outside_label_pair_mass == 91
    assert tradeoff.minimizing_case.anchor_exclusive_pair_mass == 0
    assert tradeoff.minimizing_case.threshold_pair_counts == (91, 0, 0, 0)
    assert tradeoff.minimizing_case.threshold_rank_floors == (13, 0, 0, 0)
    assert tradeoff.minimizing_case.mandatory_outside_pair_penalty == 7_618_464
    assert tradeoff.minimizing_case.local_recovery_loss == 436_100
    assert tradeoff.r4_bound == 354_532_444
    assert tradeoff.r4_bound < 354_779_928
    assert tradeoff.family_a_bound == 354_532_444
    assert tradeoff.family_a_bottleneck_r == 4
    assert tradeoff.remaining_gap == 41_292_783

    assert tuple(case.total_recovery_reduction for case in tradeoff.best_by_good_count) == (
        12_521_880,
        11_879_560,
        11_237_240,
        10_594_920,
        10_158_820,
        9_722_720,
        9_286_620,
        9_299_248,
        10_003_112,
        9_809_520,
        9_615_928,
        9_422_336,
        9_022_524,
        8_828_932,
        8_392_832,
        8_647_968,
        8_454_376,
        8_054_564,
        8_067_192,
    )
