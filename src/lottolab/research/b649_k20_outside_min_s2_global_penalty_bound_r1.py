"""Structural bounds for K=20 portfolios outside the minimum-S2 family.

The module counts intersections of ticket-win events from ticket-pair overlap
types and three-ticket Venn cells. It does not construct or search portfolios.
"""

from __future__ import annotations

from functools import cache
from itertools import combinations_with_replacement
from math import comb

POOL_SIZE = 49
DRAW_SIZE = 6
OUTRIGHT_MATCHES = 3
TICKET_COUNT = 20
PAIR_COUNT = comb(TICKET_COUNT, 2)
TRIPLE_COUNT = comb(TICKET_COUNT, 3)
INCUMBENT = 313_239_661
SINGLE_TICKET_OUTCOMES = 18_221_078
PORTFOLIO_S1 = TICKET_COUNT * SINGLE_TICKET_OUTCOMES
TWO_EDGE_TRIPLE_CAP = 2_800
THREE_EDGE_TRIPLE_CAP = 20_272


def pair_intersection_count(
    overlap: int,
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Count joint official-win outcomes for two tickets with this overlap."""

    _validate_parameters(pool_size, draw_size, outright_matches)
    if not 0 <= overlap <= draw_size:
        raise ValueError("ticket overlap must be within 0..draw_size")
    outside_size = pool_size - (2 * draw_size - overlap)
    if outside_size < 0:
        raise ValueError("the requested ticket overlap cannot fit in the pool")

    rescue_hits = outright_matches - 1
    special_count = pool_size - draw_size
    total = 0
    for common_hits in range(min(overlap, draw_size) + 1):
        for left_hits in range(draw_size - overlap + 1):
            for right_hits in range(draw_size - overlap + 1):
                outside_hits = draw_size - common_hits - left_hits - right_hits
                if not 0 <= outside_hits <= outside_size:
                    continue
                ways = (
                    comb(overlap, common_hits)
                    * comb(draw_size - overlap, left_hits)
                    * comb(draw_size - overlap, right_hits)
                    * comb(outside_size, outside_hits)
                )
                left_total = common_hits + left_hits
                right_total = common_hits + right_hits
                if left_total >= outright_matches and right_total >= outright_matches:
                    specials = special_count
                elif (
                    left_total >= outright_matches and right_total == rescue_hits
                ) or (left_total == rescue_hits and right_total >= outright_matches):
                    specials = draw_size - rescue_hits
                elif left_total == rescue_hits and right_total == rescue_hits:
                    specials = overlap - common_hits
                else:
                    specials = 0
                total += ways * specials
    return total


def pair_intersection_table(
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> tuple[int, ...]:
    """Return exact pair-event intersections for overlaps ``0..draw_size``."""

    return tuple(
        pair_intersection_count(
            overlap,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
        )
        for overlap in range(draw_size + 1)
    )


def triple_intersection_count(
    pair_overlaps: tuple[int, int, int],
    triple_common: int,
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Count joint wins for a fixed three-ticket Venn profile.

    ``pair_overlaps`` is ordered as ``(AB, AC, BC)``. The seven nonempty
    Venn cells and the outside cell determine every draw allocation exactly.
    """

    _validate_parameters(pool_size, draw_size, outright_matches)
    if len(pair_overlaps) != 3:
        raise ValueError("three pair overlaps are required")
    ab, ac, bc = pair_overlaps
    if any(not 0 <= overlap <= draw_size for overlap in pair_overlaps):
        raise ValueError("ticket overlaps must be within 0..draw_size")
    if not 0 <= triple_common <= min(pair_overlaps):
        raise ValueError("triple common count must fit every pair overlap")

    # Membership masks: 1=A, 2=B, 4=C. Pair cells are 3, 5, and 6.
    cells = {
        7: triple_common,
        3: ab - triple_common,
        5: ac - triple_common,
        6: bc - triple_common,
        1: draw_size - ab - ac + triple_common,
        2: draw_size - ab - bc + triple_common,
        4: draw_size - ac - bc + triple_common,
    }
    if min(cells.values()) < 0:
        raise ValueError("the requested Venn profile is impossible")
    union_size = sum(cells.values())
    outside_size = pool_size - union_size
    if outside_size < 0:
        raise ValueError("the requested Venn profile cannot fit in the pool")
    cells[0] = outside_size

    rescue_hits = outright_matches - 1
    total = 0
    for allocation in _draw_allocations(draw_size):
        if any(allocation[mask] > cells[mask] for mask in range(8)):
            continue
        hits = tuple(
            sum(allocation[mask] for mask in range(1, 8) if mask & (1 << ticket))
            for ticket in range(3)
        )
        if min(hits) < rescue_hits:
            continue

        rescued = tuple(ticket for ticket, count in enumerate(hits) if count == rescue_hits)
        if rescued:
            required_mask = sum(1 << ticket for ticket in rescued)
            specials = sum(
                cells[mask] - allocation[mask]
                for mask in range(1, 8)
                if mask & required_mask == required_mask
            )
        else:
            specials = pool_size - draw_size

        main_draws = 1
        for mask in range(8):
            main_draws *= comb(cells[mask], allocation[mask])
        total += main_draws * specials
    return total


def maximum_triple_intersection(
    pair_overlaps: tuple[int, int, int],
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Maximize a triple-event intersection over feasible common-cell sizes."""

    if len(pair_overlaps) != 3:
        raise ValueError("three pair overlaps are required")
    maximum = 0
    for triple_common in range(min(pair_overlaps) + 1):
        try:
            count = triple_intersection_count(
                pair_overlaps,
                triple_common,
                pool_size=pool_size,
                draw_size=draw_size,
                outright_matches=outright_matches,
            )
        except ValueError as error:
            if "Venn profile" not in str(error) and "cannot fit" not in str(error):
                raise
            continue
        maximum = max(maximum, count)
    return maximum


def minimum_pair_overlap_mass(
    *, pool_size: int = POOL_SIZE, draw_size: int = DRAW_SIZE, ticket_count: int = TICKET_COUNT
) -> tuple[int, tuple[int, ...]]:
    """Return the balanced frequency lower bound and its frequency histogram.

    Convexity of ``C(f, 2)`` makes frequencies differ by at most one at the
    minimum. The returned tuple is ``(sum C(f,2), sorted positive frequencies)``.
    """

    if pool_size < 1 or draw_size < 1 or ticket_count < 1:
        raise ValueError("pool, draw, and ticket counts must be positive")
    incidences = draw_size * ticket_count
    low, high = divmod(incidences, pool_size)
    frequencies = (low,) * (pool_size - high) + (low + 1,) * high
    mass = sum(comb(frequency, 2) for frequency in frequencies)
    return mass, tuple(frequency for frequency in frequencies if frequency)


def outside_min_s2_bounds() -> dict[str, int | str]:
    """Compute the two-family outside-S2 bound and its unresolved gap."""

    pair_counts = pair_intersection_table()
    c0, c1, c2 = pair_counts[:3]
    minimum_mass, frequency_profile = minimum_pair_overlap_mass()
    if minimum_mass != 93 or frequency_profile != (2,) * 27 + (3,) * 22:
        raise AssertionError("K20 balanced frequency lower bound changed")

    s2_minimum = 97 * c0 + 93 * c1
    if s2_minimum != 63_838_600:
        raise AssertionError("K20 minimum-S2 input does not match the exact pair table")
    if PORTFOLIO_S1 != 364_421_560:
        raise AssertionError("K20 single-ticket total changed")

    min_s2_penalty = c1 - c0
    high_overlap_penalty = c2 - c0 - 2 * (c1 - c0)
    two_edge_triple_cap = maximum_triple_intersection((1, 1, 0))
    triangle_triple_cap = maximum_triple_intersection((1, 1, 1))
    if (two_edge_triple_cap, triangle_triple_cap) != (
        TWO_EDGE_TRIPLE_CAP,
        THREE_EDGE_TRIPLE_CAP,
    ):
        raise AssertionError("pairwise-overlap-at-most-one triple cap changed")

    # For overlaps 0/1, a triple with fewer than two overlap edges has zero
    # intersection. A two-edge wedge contributes at most 2,800; a triangle
    # contributes at most 20,272. Since triangles use three wedges,
    # S3 <= 20,272/3 * W, where W=sum_v C(degree(v), 2).
    # For L overlap edges, degree sum is 2L and each degree is <=19. Convexity
    # gives the exact relaxed maximum W by filling degrees up to 19 first.
    low_family_rows = tuple(
        (edge_count, _higher_order_bound_for_overlap_graph(edge_count))
        for edge_count in range(minimum_mass + 1, PAIR_COUNT + 1)
    )
    max_recovery = max(recovery for _, recovery in low_family_rows)
    max_net_recovery, max_net_edge_count = max(
        (recovery - min_s2_penalty * (edge_count - minimum_mass), edge_count)
        for edge_count, recovery in low_family_rows
    )
    low_overlap_ub = PORTFOLIO_S1 - s2_minimum + max_net_recovery

    high_overlap_s2 = s2_minimum + high_overlap_penalty
    hunter_star_lower_bound = (2 * high_overlap_s2 + TICKET_COUNT - 1) // TICKET_COUNT
    high_overlap_ub = PORTFOLIO_S1 - hunter_star_lower_bound
    overall_ub = max(low_overlap_ub, high_overlap_ub)
    return {
        "DEVIATION_FAMILY_COUNT": 2,
        "CLOSED_FAMILY_COUNT": 1,
        "MIN_EXTRA_S2": min_s2_penalty,
        "MAX_HIGHER_ORDER_RECOVERY": max_recovery,
        "MAX_NET_HIGHER_ORDER_RECOVERY_AFTER_S2_PENALTY": max_net_recovery,
        "OVERLAP_EDGE_COUNT_AT_MAX_NET_RECOVERY": max_net_edge_count,
        "LOW_OVERLAP_MAX_PAIRWISE_OVERLAP": 1,
        "LOW_OVERLAP_FAMILY_UPPER_BOUND": low_overlap_ub,
        "HIGH_OVERLAP_FAMILY_UPPER_BOUND": high_overlap_ub,
        "OUTSIDE_FAMILY_UPPER_BOUND": overall_ub,
        "UNRESOLVED_FAMILY": "at least one ticket pair has intersection size >= 2",
        "REMAINING_GAP": overall_ub - INCUMBENT,
    }


def _higher_order_bound_for_overlap_graph(edge_count: int) -> int:
    """Bonferroni S3 bound from degree and triangle caps for a simple graph."""

    if not 0 <= edge_count <= PAIR_COUNT:
        raise ValueError("overlap graph edge count must be within 0..C(20,2)")
    degree_sum = 2 * edge_count
    full_degrees, remainder = divmod(degree_sum, TICKET_COUNT - 1)
    wedge_bound = full_degrees * comb(TICKET_COUNT - 1, 2) + comb(remainder, 2)
    return (THREE_EDGE_TRIPLE_CAP * wedge_bound) // 3


@cache
def _draw_allocations(draw_size: int) -> tuple[tuple[int, ...], ...]:
    allocations: list[tuple[int, ...]] = []
    for selected in combinations_with_replacement(range(8), draw_size):
        counts = [0] * 8
        for mask in selected:
            counts[mask] += 1
        allocations.append(tuple(counts))
    return tuple(allocations)


def _validate_parameters(pool_size: int, draw_size: int, outright_matches: int) -> None:
    if not 1 <= outright_matches <= draw_size <= pool_size:
        raise ValueError("parameters must satisfy 1 <= outright_matches <= draw_size <= pool_size")


__all__ = [
    "DRAW_SIZE",
    "INCUMBENT",
    "OUTRIGHT_MATCHES",
    "PAIR_COUNT",
    "POOL_SIZE",
    "PORTFOLIO_S1",
    "SINGLE_TICKET_OUTCOMES",
    "TICKET_COUNT",
    "TRIPLE_COUNT",
    "maximum_triple_intersection",
    "minimum_pair_overlap_mass",
    "outside_min_s2_bounds",
    "pair_intersection_count",
    "pair_intersection_table",
    "triple_intersection_count",
]
