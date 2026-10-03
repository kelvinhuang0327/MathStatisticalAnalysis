"""Focused exact checks for the K20 r=3 anchor-neighborhood envelope."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations, product

from lottolab.research.b649_k20_r3_anchor_incidence_bound_r5 import (
    AnchorIncidenceProfile,
    anchor_incidence_profiles,
)
from lottolab.research.b649_k20_r3_exact_anchor_neighborhood_envelope_r6 import (
    OUTSIDE_PAIR_SLOPE,
    aggregate_count_vector_is_feasible,
    balanced_pair_mass,
    candidate_type_count_vectors,
    critical_type_count_envelope,
    dangerous_type_count_envelopes,
    family_a_result_record,
    feasible_pair_overlap_vectors,
    full_type_count_vector_count,
    guaranteed_recovery_reduction,
    iter_type_count_vectors,
    local_losses,
    minimum_outside_pair_slope,
    residual_pair_intersection_floor,
    revised_r3_bound,
    type_pair_certificate,
)


def test_independent_type_count_generator_matches_a_small_brute_force_census() -> None:
    losses = (0, 2, 5)
    observed = set(iter_type_count_vectors(losses, ticket_count=4, loss_limit=7))
    expected = {
        counts
        for counts in product(range(5), repeat=3)
        if sum(counts) == 4
        and sum(
            count * loss for count, loss in zip(counts, losses, strict=True)
        )
        <= 7
    }

    assert observed == expected
    assert len(observed) == len(list(iter_type_count_vectors(losses, 4, 7)))


def test_30_type_cost_table_and_outside_label_dual_slope_are_exact() -> None:
    profiles = anchor_incidence_profiles()
    losses = local_losses(profiles)
    assert len(profiles) == 30
    assert all(
        profile.shared + profile.a_only + profile.b_only + profile.outside == 6
        and profile.shared + profile.a_only <= 3
        and profile.shared + profile.b_only <= 3
        for profile in profiles
    )
    assert min(loss for loss in losses if loss > 0) == 442_890
    assert minimum_outside_pair_slope() == Fraction(OUTSIDE_PAIR_SLOPE, 1) == 1_036

    eligible = tuple(index for index, loss in enumerate(losses) if loss <= 5_314_680)
    for left_index in eligible:
        for right_index in range(left_index, len(profiles)):
            if right_index not in eligible:
                continue
            certificate = type_pair_certificate(left_index, right_index)
            if certificate is None:
                continue
            left, right = profiles[left_index], profiles[right_index]
            for overlap in feasible_pair_overlap_vectors(left_index, right_index):
                floor = residual_pair_intersection_floor(left, right, overlap)
                assert floor >= certificate.minimum_residual_intersection
                assert floor >= (
                    certificate.minimum_residual_intersection
                    + OUTSIDE_PAIR_SLOPE * overlap[3]
                )


def _toy_profile(
    ticket: frozenset[int],
    anchor_a: frozenset[int],
    anchor_b: frozenset[int],
    cells: tuple[frozenset[int], frozenset[int], frozenset[int], frozenset[int]],
) -> AnchorIncidenceProfile:
    return AnchorIncidenceProfile(
        shared=len(ticket & cells[0]),
        a_only=len(ticket & cells[1]),
        b_only=len(ticket & cells[2]),
        outside=len(ticket & cells[3]),
        overlap_with_a=len(ticket & anchor_a),
        overlap_with_b=len(ticket & anchor_b),
        triple_recovery=0,
        pair_recovery_cost=0,
        net_recovery=0,
    )


def _toy_wins(
    ticket: frozenset[int], draw: frozenset[int], special: int
) -> bool:
    matches = len(ticket & draw)
    return matches >= 2 or (matches == 1 and special in ticket)


def test_small_exact_anchor_neighborhood_toy_bounds_every_residual_pair() -> None:
    pool = frozenset(range(8))
    anchor_a = frozenset((0, 1, 2))
    anchor_b = frozenset((0, 3, 4))
    cells = (frozenset((0,)), frozenset((1, 2)), frozenset((3, 4)), frozenset((5, 6, 7)))
    draws = tuple(frozenset(draw) for draw in combinations(sorted(pool), 3))
    outcomes = tuple(
        (draw, special)
        for draw in draws
        for special in pool - draw
    )

    def winning_outcomes(ticket: frozenset[int]) -> frozenset[tuple[frozenset[int], int]]:
        return frozenset(
            (draw, special)
            for draw, special in outcomes
            if _toy_wins(ticket, draw, special)
        )

    anchor_wins = winning_outcomes(anchor_a) | winning_outcomes(anchor_b)
    tickets = tuple(
        frozenset(ticket)
        for ticket in combinations(sorted(pool), 3)
        if len(set(ticket) & anchor_a) <= 1 and len(set(ticket) & anchor_b) <= 1
    )
    ticket_events = {ticket: winning_outcomes(ticket) - anchor_wins for ticket in tickets}

    checked = 0
    for left, right in combinations(tickets, 2):
        if len(left & right) > 1:
            continue
        overlap = (
            len(left & right & cells[0]),
            len(left & right & cells[1]),
            len(left & right & cells[2]),
            len(left & right & cells[3]),
        )
        left_profile = _toy_profile(left, anchor_a, anchor_b, cells)
        right_profile = _toy_profile(right, anchor_a, anchor_b, cells)
        certified_floor = residual_pair_intersection_floor(
            left_profile,
            right_profile,
            overlap,
            pool_size=8,
            draw_size=3,
            outright_matches=2,
        )
        exact_residual_intersection = len(ticket_events[left] & ticket_events[right])
        assert certified_floor <= exact_residual_intersection
        checked += 1

    assert checked > 0


def test_dangerous_type_census_and_global_r3_bound() -> None:
    vectors = candidate_type_count_vectors()
    envelopes = dangerous_type_count_envelopes()
    critical = critical_type_count_envelope()

    assert len(vectors) == 2_683
    assert len(set(vectors)) == len(vectors)
    assert len(envelopes) == len(vectors)
    assert all(aggregate_count_vector_is_feasible(vector) for vector in vectors)
    assert full_type_count_vector_count() == 4_568_648_125_690
    assert balanced_pair_mass(97, 40) == 74
    assert [(index, count) for index, count in enumerate(critical.counts) if count] == [
        (0, 7),
        (4, 11),
    ]
    assert critical.local_loss == 4_871_790
    assert critical.outside_label_incidence_count == 97
    assert critical.outside_label_pair_mass_floor == 74
    assert critical.pair_intersection_mass_floor == 16_416_064
    assert critical.pair_union_penalty == 1_824_008
    assert critical.prior_forest_penalty == 1_148_000
    assert critical.total_recovery_reduction == 6_695_798
    assert sum(
        envelope.total_recovery_reduction <= 5_314_680 for envelope in envelopes
    ) == 0
    assert guaranteed_recovery_reduction() == 5_757_570
    assert revised_r3_bound() == 351_483_978

    record = family_a_result_record()
    assert record["TYPE_COUNT_VECTOR_COUNT"] == 2_683
    assert record["DANGEROUS_VECTOR_COUNT"] == 0
    assert record["FAMILY_A_RECOMPUTED_BOUND"] == 354_779_928
    assert record["FAMILY_A_BOTTLENECK_R"] == "R4"
    assert record["REMAINING_GAP"] == 41_540_267
    assert record["SOLVER_STATUS"] == "NOT_USED_COMPLETE_FINITE_CENSUS"
