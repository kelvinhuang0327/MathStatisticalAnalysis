"""Focused independent checks for the K20 heavy-pair structural bound."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from itertools import combinations, product
from math import comb

from lottolab.research.b649_k20_heavy_pair_defect_global_bound_r2 import (
    EXPECTED_HEAVY_PAIR_EXCESS,
    EXPECTED_MIN_EXTRA_S2,
    EXPECTED_PAIR_COUNTS,
    c_wedge_certificate,
    certified_integer_upper_bound,
    exact_family_s2_floors,
    exact_pair_costs,
    exact_triple_profile_table,
    pair_cost_convexity_excess,
    preliminary_family_bounds,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    pair_intersection_count,
    triple_intersection_count,
)


def _independent_pair_count(overlap: int) -> int:
    outside_size = 49 - (12 - overlap)
    count = 0
    for shared_hits in range(overlap + 1):
        for left_only_hits in range(7 - overlap):
            for right_only_hits in range(7 - overlap):
                outside_hits = 6 - shared_hits - left_only_hits - right_only_hits
                if not 0 <= outside_hits <= outside_size:
                    continue
                draw_ways = (
                    comb(overlap, shared_hits)
                    * comb(6 - overlap, left_only_hits)
                    * comb(6 - overlap, right_only_hits)
                    * comb(outside_size, outside_hits)
                )
                left_hits = shared_hits + left_only_hits
                right_hits = shared_hits + right_only_hits
                if left_hits >= 3 and right_hits >= 3:
                    special_ways = 43
                elif (left_hits >= 3 and right_hits == 2) or (
                    right_hits >= 3 and left_hits == 2
                ):
                    special_ways = 4
                elif left_hits == 2 and right_hits == 2:
                    special_ways = overlap - shared_hits
                else:
                    special_ways = 0
                count += draw_ways * special_ways
    return count


def _bounded_compositions(capacities: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
    suffix_capacity = [0] * (len(capacities) + 1)
    for index in range(len(capacities) - 1, -1, -1):
        suffix_capacity[index] = suffix_capacity[index + 1] + capacities[index]

    def visit(index: int, remaining: int, prefix: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
        if index == len(capacities) - 1:
            if remaining <= capacities[index]:
                yield (*prefix, remaining)
            return
        maximum = min(capacities[index], remaining)
        for selected in range(maximum + 1):
            next_remaining = remaining - selected
            if next_remaining <= suffix_capacity[index + 1]:
                yield from visit(index + 1, next_remaining, (*prefix, selected))

    yield from visit(0, 6, ())


def _independent_triple_count(
    overlaps: tuple[int, int, int], common: int
) -> int | None:
    ab, ac, bc = overlaps
    cells = [0] * 8
    cells[7] = common
    cells[3] = ab - common
    cells[5] = ac - common
    cells[6] = bc - common
    cells[1] = 6 - ab - ac + common
    cells[2] = 6 - ab - bc + common
    cells[4] = 6 - ac - bc + common
    if min(cells[1:]) < 0:
        return None
    cells[0] = 49 - sum(cells[1:])
    if cells[0] < 0:
        return None

    total = 0
    capacities = tuple(cells)
    for allocation in _bounded_compositions(capacities):
        hits = tuple(
            sum(allocation[mask] for mask in range(1, 8) if mask & (1 << ticket))
            for ticket in range(3)
        )
        if min(hits) < 2:
            continue
        rescued_mask = sum(1 << ticket for ticket, value in enumerate(hits) if value == 2)
        if rescued_mask:
            special_ways = sum(
                capacities[mask] - allocation[mask]
                for mask in range(1, 8)
                if mask & rescued_mask == rescued_mask
            )
        else:
            special_ways = 43
        draw_ways = 1
        for capacity, selected in zip(capacities, allocation, strict=True):
            draw_ways *= comb(capacity, selected)
        total += draw_ways * special_ways
    return total


def _independent_triple_table() -> tuple[tuple[int, int, int, int], ...]:
    table: list[tuple[int, int, int, int]] = []
    for ab, ac, bc in product(range(7), repeat=3):
        feasible: list[int] = []
        for common in range(min(ab, ac, bc) + 1):
            value = _independent_triple_count((ab, ac, bc), common)
            if value is not None:
                feasible.append(value)
        table.append((ab, ac, bc, max(feasible, default=0)))
    return tuple(table)


def _wins(ticket: tuple[int, ...], draw: tuple[int, ...], special: int, outright: int) -> bool:
    matches = len(set(ticket) & set(draw))
    return matches >= outright or (matches == outright - 1 and special in ticket)


def test_pair_counts_are_recomputed_by_an_independent_formula() -> None:
    independent = tuple(_independent_pair_count(overlap) for overlap in range(7))
    assert independent == EXPECTED_PAIR_COUNTS
    assert exact_pair_costs() == EXPECTED_PAIR_COUNTS
    assert tuple(pair_intersection_count(overlap) for overlap in range(7)) == independent
    assert pair_cost_convexity_excess(independent) == (
        0,
        0,
        655_788,
        1_963_542,
        4_251_912,
        8_337_532,
        15_706_432,
    )
    assert EXPECTED_MIN_EXTRA_S2 == 466_200
    assert EXPECTED_HEAVY_PAIR_EXCESS == 655_788


def test_all_343_triple_profile_maxima_match_an_independent_venn_enumerator() -> None:
    independent = _independent_triple_table()
    assert len(independent) == 343
    assert exact_triple_profile_table() == independent
    digest = hashlib.sha256(json.dumps(independent, separators=(",", ":")).encode()).hexdigest()
    assert digest == "fabbd522204dee9c8dd3790f733ef11dc717c5efb632220e2861abd755635cd8"
    assert dict(((a, b, c), value) for a, b, c, value in independent)[(2, 0, 0)] == 2_240
    assert dict(((a, b, c), value) for a, b, c, value in independent)[(2, 1, 0)] == 14_420
    assert dict(((a, b, c), value) for a, b, c, value in independent)[(2, 1, 1)] == 56_126


def test_exact_family_floors_and_preliminary_hunter_bounds() -> None:
    assert exact_family_s2_floors() == {
        "OUTSIDE_MIN_S2_BASELINE": 63_838_600,
        "A_AT_LEAST_ONE_OVERLAP_3": 65_802_142,
        "B_AT_LEAST_TWO_OVERLAP_2": 65_150_176,
        "C_EXACTLY_ONE_OVERLAP_2": 64_494_388,
    }
    bounds = preliminary_family_bounds()
    assert bounds["A_PRELIMINARY_BOUND"] == 357_841_345
    assert bounds["B_PRELIMINARY_BOUND"] == 357_906_542
    assert bounds["C_S2_FLOOR"] == 64_494_388


def test_family_c_wedge_certificate_closes_c_below_the_incumbent() -> None:
    certificate = c_wedge_certificate()
    assert certificate.upper_bound == 311_499_152
    assert certificate.s2_at_maximum == 64_494_388
    assert certificate.s3_upper_bound == 11_571_980
    assert certificate.ordinary_edge_count == 91
    assert certificate.heavy_endpoint_spokes == 36
    assert certificate.common_neighbors == 18
    assert certificate.wedge_count_upper == 1_581
    assert certificate.regular_wedge_count_upper == 1_563
    assert certificate.special_triple_recovery_upper == 1_010_268


def test_certified_bound_uses_the_maximization_bound_and_not_incumbent_objective() -> None:
    assert certified_integer_upper_bound(12_880_125.2) == 12_880_126
    assert certified_integer_upper_bound(-7.2) == -7


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
        ticket_sets = tuple(map(set, (first, second, third)))
        overlaps = (
            len(ticket_sets[0] & ticket_sets[1]),
            len(ticket_sets[0] & ticket_sets[2]),
            len(ticket_sets[1] & ticket_sets[2]),
        )
        common = len(ticket_sets[0] & ticket_sets[1] & ticket_sets[2])
        brute = sum(
            _wins(first, draw, special, outright)
            and _wins(second, draw, special, outright)
            and _wins(third, draw, special, outright)
            for draw in draws
            for special in set(range(1, pool_size + 1)) - set(draw)
        )
        assert triple_intersection_count(
            overlaps,
            common,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright,
        ) == brute
