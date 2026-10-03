"""Focused checks for the K20 r=3 anchor-neighborhood tradeoff."""

from __future__ import annotations

from itertools import combinations

from lottolab.research.b649_k20_heavy_pair_r3plus_global_bound_r3 import (
    EXPECTED_PAIR_COUNTS,
    exact_pair_counts,
    local_heavy_pair_profiles,
)
from lottolab.research.b649_k20_heavy_pair_r3plus_higher_order_bound_r4 import (
    anchor_tradeoff,
    family_a_result_record,
    revised_r3_bound,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    pair_intersection_count,
    triple_intersection_count,
)

ToyOutcome = tuple[tuple[int, ...], int]


def _wins(
    ticket: tuple[int, ...], draw: tuple[int, ...], special: int, outright: int
) -> bool:
    matches = len(set(ticket) & set(draw))
    return matches >= outright or (matches == outright - 1 and special in ticket)


def test_exact_k20_pair_and_disjoint_anchor_triple_counts() -> None:
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
    ) == (0, 2_240, 9_485)


def test_local_profile_tradeoff_forces_a_574000_recovery_reduction() -> None:
    profiles = local_heavy_pair_profiles(3)
    good = tuple(
        profile
        for profile in profiles
        if profile.left_overlap == 0 and profile.right_overlap == 0
    )
    non_good = tuple(
        profile
        for profile in profiles
        if profile.left_overlap > 0 or profile.right_overlap > 0
    )
    tradeoff = anchor_tradeoff()

    assert len(good) == 1
    assert good[0].net_recovery == -206_115
    assert max(profile.net_recovery for profile in non_good) == -649_005
    assert tradeoff.outside_label_capacity == 40
    assert tradeoff.good_ticket_collision_threshold == 7
    assert tradeoff.minimum_non_good_local_loss == 442_890
    assert tradeoff.non_good_case_minimum_loss == 5_314_680
    assert tradeoff.collision_pair_recovery_floor == 574_000
    assert tradeoff.guaranteed_recovery_improvement == 574_000
    assert tuple(
        row.residual_pair_intersection_lower_bound
        for row in tradeoff.collision_profiles
    ) == (574_000, 1_691_508, 3_450_972)


def test_revised_family_a_bound_preserves_the_frozen_r4_to_r6_bounds() -> None:
    record = family_a_result_record()
    assert revised_r3_bound() == 356_667_548
    assert record["R3_PRIOR_BOUND"] == 357_241_548
    assert record["R3_BOUND"] == 356_667_548
    assert record["R4_BOUND"] == 354_779_928
    assert record["R5_BOUND"] == 350_778_728
    assert record["R6_BOUND"] == 343_869_728
    assert record["FAMILY_A_BOUND"] == 356_667_548
    assert record["FAMILY_A_STATUS"] == "TIGHTENED_OPEN"
    assert record["IMPROVEMENT_VS_PRIOR_BOUND"] == 574_000
    assert record["REMAINING_GAP"] == 43_427_887
    assert record["SUCCESS_A"] is False
    assert record["SUCCESS_B"] is True
    assert record["CP_SAT_STATUS"] == "NOT_RUN"
    assert record["CP_SAT_CERTIFIED_BOUND"] is None


def test_exhaustive_toy_anchor_neighborhoods_obey_residual_collision_bound() -> None:
    pool_size, draw_size, outright = 11, 3, 2
    pool = set(range(pool_size))
    anchor_a = (0, 1, 2)
    anchor_b = (0, 3, 4)
    anchors = set(anchor_a) | set(anchor_b)
    outside_tickets = tuple(combinations(sorted(pool - anchors), draw_size))
    draws = tuple(combinations(range(pool_size), draw_size))
    outcomes: tuple[ToyOutcome, ...] = tuple(
        (draw, special)
        for draw in draws
        for special in pool - set(draw)
    )
    tickets = (anchor_a, anchor_b, *outside_tickets)
    events = {
        ticket: frozenset(
            (draw, special)
            for draw, special in outcomes
            if _wins(ticket, draw, special, outright)
        )
        for ticket in tickets
    }
    anchor_union = events[anchor_a] | events[anchor_b]
    residuals = {ticket: events[ticket] - anchor_union for ticket in outside_tickets}
    neighborhood_count = 0

    for neighborhood in combinations(outside_tickets, 3):
        pair_rows = tuple(
            (
                left,
                right,
                len(set(left) & set(right)),
            )
            for left, right in combinations(neighborhood, 2)
        )
        # The toy anchor overlap is one, so retain neighborhoods where it is
        # still a maximum pair overlap, as in the K20 r=3 argument.
        if max(overlap for _, _, overlap in pair_rows) > 1:
            continue
        neighborhood_count += 1
        colliding_pairs = tuple(row for row in pair_rows if row[2] > 0)
        assert colliding_pairs

        left, right, overlap = colliding_pairs[0]
        pair_count = pair_intersection_count(
            overlap,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright,
        )
        anchor_triple = triple_intersection_count(
            (0, 0, overlap),
            0,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright,
        )
        residual_pair_floor = pair_count - 2 * anchor_triple
        actual_residual_pair = len(residuals[left] & residuals[right])
        assert actual_residual_pair >= residual_pair_floor

        residual_union = (
            residuals[neighborhood[0]]
            | residuals[neighborhood[1]]
            | residuals[neighborhood[2]]
        )
        residual_sum = sum(len(residuals[ticket]) for ticket in neighborhood)
        assert len(residual_union) <= residual_sum - actual_residual_pair
        assert len(residual_union) <= residual_sum - residual_pair_floor

    assert neighborhood_count == 120
