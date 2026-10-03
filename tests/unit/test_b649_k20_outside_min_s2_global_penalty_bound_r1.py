"""Focused structural checks for the K=20 outside-minimum-S2 bound."""

from __future__ import annotations

from itertools import combinations, pairwise
from math import comb

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    INCUMBENT,
    PORTFOLIO_S1,
    SINGLE_TICKET_OUTCOMES,
    TICKET_COUNT,
    TRIPLE_COUNT,
    maximum_triple_intersection,
    minimum_pair_overlap_mass,
    outside_min_s2_bounds,
    pair_intersection_count,
    pair_intersection_table,
    triple_intersection_count,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    evaluate_single_ticket_closed_form,
)


def _wins(ticket: tuple[int, ...], draw: tuple[int, ...], special: int, outright: int) -> bool:
    hits = len(set(ticket) & set(draw))
    return hits >= outright or (hits == outright - 1 and special in ticket)


def test_single_ticket_count_is_derived_from_canonical_closed_form() -> None:
    canonical_probability = evaluate_single_ticket_closed_form()
    total_outcomes = comb(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE) * (
        BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE
    )
    canonical_count = canonical_probability * total_outcomes

    assert canonical_count.denominator == 1
    assert canonical_count.numerator == 18_611_432
    assert canonical_count.numerator == SINGLE_TICKET_OUTCOMES
    assert TICKET_COUNT * canonical_count.numerator == PORTFOLIO_S1

    bounds = outside_min_s2_bounds()
    reported_s1 = bounds["S1"]
    max_net_recovery = bounds["MAX_NET_HIGHER_ORDER_RECOVERY_AFTER_S2_PENALTY"]
    low_upper_bound = bounds["LOW_OVERLAP_FAMILY_UPPER_BOUND"]
    assert isinstance(reported_s1, int)
    assert isinstance(max_net_recovery, int)
    assert isinstance(low_upper_bound, int)
    s2_minimum = 97 * pair_intersection_count(0) + 93 * pair_intersection_count(1)
    assert reported_s1 == TICKET_COUNT * canonical_count.numerator
    assert low_upper_bound == reported_s1 - s2_minimum + max_net_recovery
    assert low_upper_bound == 319_242_373


def test_exact_official_pair_intersections_and_minimum_s2() -> None:
    assert TRIPLE_COUNT == 1_140
    pair_counts = pair_intersection_table()
    assert pair_counts == (
        107_800,
        574_000,
        1_695_988,
        3_469_942,
        6_224_512,
        10_776_332,
        18_611_432,
    )
    first_differences = tuple(right - left for left, right in pairwise(pair_counts))
    assert first_differences == (466_200, 1_121_988, 1_773_954, 2_754_570, 4_551_820, 7_835_100)
    convexity_excess = tuple(
        count - pair_counts[0] - overlap * first_differences[0]
        for overlap, count in enumerate(pair_counts)
    )
    assert convexity_excess == (0, 0, 655_788, 1_963_542, 4_251_912, 8_337_532, 15_706_432)
    mass, frequencies = minimum_pair_overlap_mass()
    assert mass == 93
    assert frequencies == (2,) * 27 + (3,) * 22
    assert 97 * pair_intersection_count(0) + 93 * pair_intersection_count(1) == 63_838_600


def test_pairwise_overlap_at_most_one_has_exact_triple_cap() -> None:
    assert maximum_triple_intersection((0, 0, 0)) == 0
    assert maximum_triple_intersection((0, 0, 1)) == 0
    assert maximum_triple_intersection((0, 1, 1)) == 2_800
    assert maximum_triple_intersection((1, 1, 1)) == 20_272
    profiles = (
        (0, 0, 0),
        (0, 0, 1),
        (0, 1, 0),
        (1, 0, 0),
        (0, 1, 1),
        (1, 0, 1),
        (1, 1, 0),
        (1, 1, 1),
    )
    assert max(maximum_triple_intersection(edges) for edges in profiles) == 20_272


def test_small_toy_pair_and_triple_counts_match_exhaustive_outcomes() -> None:
    pool_size = 7
    draw_size = 3
    outright = 2
    tickets = tuple(combinations(range(1, pool_size + 1), draw_size))
    draws = tuple(combinations(range(1, pool_size + 1), draw_size))

    for left, right in combinations(tickets, 2):
        overlap = len(set(left) & set(right))
        brute = sum(
            _wins(left, draw, special, outright) and _wins(right, draw, special, outright)
            for draw in draws
            for special in set(range(1, pool_size + 1)) - set(draw)
        )
        assert pair_intersection_count(
            overlap,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright,
        ) == brute

    for first, second, third in combinations(tickets, 3):
        first_set, second_set, third_set = map(set, (first, second, third))
        overlaps = (
            len(first_set & second_set),
            len(first_set & third_set),
            len(second_set & third_set),
        )
        triple_common = len(first_set & second_set & third_set)
        brute = sum(
            _wins(first, draw, special, outright)
            and _wins(second, draw, special, outright)
            and _wins(third, draw, special, outright)
            for draw in draws
            for special in set(range(1, pool_size + 1)) - set(draw)
        )
        assert triple_intersection_count(
            overlaps,
            triple_common,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright,
        ) == brute


def test_reported_bound_and_remaining_gap_are_exact() -> None:
    result = outside_min_s2_bounds()
    assert result == {
        "DEVIATION_FAMILY_COUNT": 2,
        "CLOSED_FAMILY_COUNT": 0,
        "SINGLE_TICKET_OUTCOMES": 18_611_432,
        "S1": 372_228_640,
        "MIN_EXTRA_S2": 466_200,
        "MAX_HIGHER_ORDER_RECOVERY": 23_110_080,
        "MAX_NET_HIGHER_ORDER_RECOVERY_AFTER_S2_PENALTY": 10_852_333,
        "OVERLAP_EDGE_COUNT_AT_MAX_NET_RECOVERY": 94,
        "LOW_OVERLAP_MAX_PAIRWISE_OVERLAP": 1,
        "LOW_OVERLAP_FAMILY_UPPER_BOUND": 319_242_373,
        "HIGH_OVERLAP_FAMILY_UPPER_BOUND": 365_779_201,
        "OUTSIDE_FAMILY_UPPER_BOUND": 365_779_201,
        "UNRESOLVED_FAMILIES": (
            "all ticket-pair overlaps are at most one, or at least one pair overlap is >= 2"
        ),
        "REMAINING_GAP": 52_539_540,
    }
    outside_bound = result["OUTSIDE_FAMILY_UPPER_BOUND"]
    remaining_gap = result["REMAINING_GAP"]
    assert isinstance(outside_bound, int)
    assert isinstance(remaining_gap, int)
    assert outside_bound - INCUMBENT == remaining_gap
