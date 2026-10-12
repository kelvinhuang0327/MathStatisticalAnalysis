"""Focused checks for the K20 r_max >= 3 anchor-pair certificate."""

from __future__ import annotations

from itertools import combinations
from math import comb

from lottolab.research.b649_k20_heavy_pair_r3plus_global_bound_r3 import (
    EXPECTED_PAIR_COUNTS,
    exact_pair_counts,
    exact_s2_floors_by_r,
    family_a_result_record,
    heavy_pair_case,
    local_heavy_pair_profiles,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    pair_intersection_count,
    triple_intersection_count,
)

ToyOutcome = tuple[tuple[int, ...], int]


def _independent_pair_count(overlap: int) -> int:
    outside_size = 49 - (12 - overlap)
    total = 0
    for common_hits in range(overlap + 1):
        for left_hits in range(7 - overlap):
            for right_hits in range(7 - overlap):
                outside_hits = 6 - common_hits - left_hits - right_hits
                if not 0 <= outside_hits <= outside_size:
                    continue
                ways = (
                    comb(overlap, common_hits)
                    * comb(6 - overlap, left_hits)
                    * comb(6 - overlap, right_hits)
                    * comb(outside_size, outside_hits)
                )
                left_total = common_hits + left_hits
                right_total = common_hits + right_hits
                if left_total >= 3 and right_total >= 3:
                    specials = 43
                elif (left_total >= 3 and right_total == 2) or (
                    right_total >= 3 and left_total == 2
                ):
                    specials = 4
                elif left_total == 2 and right_total == 2:
                    specials = overlap - common_hits
                else:
                    specials = 0
                total += ways * specials
    return total


def _wins(
    ticket: tuple[int, ...], draw: tuple[int, ...], special: int, outright: int
) -> bool:
    matches = len(set(ticket) & set(draw))
    return matches >= outright or (matches == outright - 1 and special in ticket)


def _toy_event_sets() -> tuple[
    tuple[tuple[int, ...], ...], dict[tuple[int, ...], frozenset[ToyOutcome]]
]:
    pool_size, draw_size, outright = 6, 3, 2
    tickets = tuple(combinations(range(pool_size), draw_size))
    outcomes = tuple(
        (draw, special)
        for draw in combinations(range(pool_size), draw_size)
        for special in set(range(pool_size)) - set(draw)
    )
    events = {
        ticket: frozenset(
            (draw, special)
            for draw, special in outcomes
            if _wins(ticket, draw, special, outright)
        )
        for ticket in tickets
    }
    return tickets, events


def test_pair_counts_are_recomputed_independently() -> None:
    independent = tuple(_independent_pair_count(overlap) for overlap in range(7))
    assert independent == EXPECTED_PAIR_COUNTS
    assert exact_pair_counts() == independent
    assert tuple(pair_intersection_count(overlap) for overlap in range(7)) == independent


def test_exact_s2_floors_condition_on_each_maximum_overlap() -> None:
    assert exact_s2_floors_by_r() == {
        3: 65_802_142,
        4: 68_090_512,
        5: 72_176_132,
        6: 79_545_032,
    }


def test_local_s3_caps_and_anchor_net_maxima_are_exact() -> None:
    expected = {
        3: (1_585_689, 28_542_402, -206_115, 357_241_548),
        4: (4_540_102, 81_721_836, -189_840, 354_779_928),
        5: (10_030_132, 180_542_376, -159_250, 350_778_728),
        6: (18_611_432, 335_005_776, -107_800, 343_869_728),
    }
    for overlap, values in expected.items():
        case = heavy_pair_case(overlap)
        assert (
            case.maximum_triple_recovery_per_third_ticket,
            case.local_s3_recovery_ceiling,
            case.maximum_net_recovery_per_third_ticket,
            case.upper_bound,
        ) == values
        assert case.s3_maximizing_profile.shared_labels == overlap
        assert case.s3_maximizing_profile.left_only_labels == 0
        assert case.s3_maximizing_profile.right_only_labels == 0
        assert case.net_maximizing_profile.shared_labels == 0


def test_each_local_profile_is_a_feasible_anchor_pair_venn_profile() -> None:
    for overlap in range(3, 7):
        profiles = local_heavy_pair_profiles(overlap)
        assert profiles
        for profile in profiles:
            assert profile.shared_labels <= overlap
            assert profile.left_only_labels <= 6 - overlap
            assert profile.right_only_labels <= 6 - overlap
            assert profile.left_overlap <= overlap
            assert profile.right_overlap <= overlap
            assert (
                profile.shared_labels
                + profile.left_only_labels
                + profile.right_only_labels
                + profile.outside_labels
                == 6
            )
            assert profile.triple_recovery == triple_intersection_count(
                (overlap, profile.left_overlap, profile.right_overlap),
                profile.shared_labels,
            )


def test_small_exhaustive_toy_portfolios_satisfy_anchor_inclusion_exclusion() -> None:
    tickets, events = _toy_event_sets()
    for left, right in combinations(tickets, 2):
        overlap = len(set(left) & set(right))
        assert len(events[left] & events[right]) == pair_intersection_count(
            overlap,
            pool_size=6,
            draw_size=3,
            outright_matches=2,
        )
    for first, second, third in combinations(tickets, 3):
        first_set, second_set, third_set = map(set, (first, second, third))
        overlaps = (
            len(first_set & second_set),
            len(first_set & third_set),
            len(second_set & third_set),
        )
        common = len(first_set & second_set & third_set)
        assert len(events[first] & events[second] & events[third]) == (
            triple_intersection_count(
                overlaps,
                common,
                pool_size=6,
                draw_size=3,
                outright_matches=2,
            )
        )

    for portfolio in combinations(tickets, 4):
        overlaps = {
            (left, right): len(set(left) & set(right))
            for left, right in combinations(portfolio, 2)
        }
        maximum_overlap = max(overlaps.values())
        portfolio_union: set[ToyOutcome] = set()
        for ticket in portfolio:
            portfolio_union.update(events[ticket])
        union_size = len(portfolio_union)
        for left, right in combinations(portfolio, 2):
            if overlaps[(left, right)] != maximum_overlap:
                continue
            anchor_union: set[ToyOutcome] = set(events[left] | events[right])
            bound = len(anchor_union)
            for third in portfolio:
                if third in (left, right):
                    continue
                outside_anchor = events[third] - anchor_union
                overlap_left = len(events[left] & events[third])
                overlap_right = len(events[right] & events[third])
                triple = len(events[left] & events[right] & events[third])
                assert len(outside_anchor) == (
                    len(events[third]) - overlap_left - overlap_right + triple
                )
                bound += len(outside_anchor)
            assert union_size <= bound


def test_result_record_reports_a_certified_strict_family_a_improvement() -> None:
    record = family_a_result_record()
    assert record["R3_BOUND"] == 357_241_548
    assert record["R4_BOUND"] == 354_779_928
    assert record["R5_BOUND"] == 350_778_728
    assert record["R6_BOUND"] == 343_869_728
    assert record["FAMILY_A_BOUND"] == 357_241_548
    assert record["FAMILY_A_STATUS"] == "TIGHTENED_OPEN"
    assert record["SUCCESS_A"] is False
    assert record["SUCCESS_B"] is True
    assert record["IMPROVEMENT_VS_PRIOR_BOUND"] == 599_797
    assert record["REMAINING_GAP"] == 44_001_887
