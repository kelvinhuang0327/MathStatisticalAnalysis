"""Exact toy-scale geometry identities for four-ticket hit intersections.

The Phase-6 S3 identity groups ticket triples by their eight membership
regions.  This module is the corresponding S4 design helper: a quadruple is
represented by all sixteen exact membership regions, canonicalized under the
24 relabelings of the four tickets.  It deliberately contains no native
constructor, result-artifact, historical-draw, or winning-space execution
path.  A future J4 executor may use these pure functions after an explicit
Owner authorization and portfolio-hash gate.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import cache

Ticket = tuple[int, ...]
QuadrupleShape = tuple[int, ...]

_TICKET_COUNT = 4
_REGION_COUNT = 1 << _TICKET_COUNT
_RELABELINGS: tuple[tuple[int, ...], ...] = tuple(itertools.permutations(range(_TICKET_COUNT)))


def _validate_shape(pool_size: int, draw_size: int, minimum_matches: int) -> None:
    if not 1 <= draw_size <= pool_size:
        raise ValueError("draw_size must lie in [1, pool_size]")
    if not 1 <= minimum_matches <= draw_size:
        raise ValueError("minimum_matches must lie in [1, draw_size]")


def _validated_quadruple(
    tickets: Sequence[Ticket], pool_size: int
) -> tuple[Ticket, Ticket, Ticket, Ticket]:
    if len(tickets) != _TICKET_COUNT:
        raise ValueError("exactly four tickets are required")
    normalized = tuple(tickets)
    for ticket in normalized:
        if not ticket or len(set(ticket)) != len(ticket):
            raise ValueError("each ticket must contain distinct numbers")
        if tuple(sorted(ticket)) != ticket:
            raise ValueError("tickets must be ascending-sorted")
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError("ticket number outside 1..pool_size")
    if len({len(ticket) for ticket in normalized}) != 1:
        raise ValueError("all four tickets must have the same draw size")
    return normalized  # type: ignore[return-value]


def _raw_region_shape(
    tickets: tuple[Ticket, Ticket, Ticket, Ticket], pool_size: int
) -> QuadrupleShape:
    region_counts = [0] * _REGION_COUNT
    memberships = [0] * pool_size
    for ticket_index, ticket in enumerate(tickets):
        for number in ticket:
            memberships[number - 1] |= 1 << ticket_index
    for mask in memberships:
        region_counts[mask] += 1
    return tuple(region_counts)


def _relabel_region_shape(shape: QuadrupleShape, permutation: tuple[int, ...]) -> QuadrupleShape:
    relabeled = [0] * _REGION_COUNT
    for new_mask in range(_REGION_COUNT):
        old_mask = 0
        for new_index, old_index in enumerate(permutation):
            if new_mask & (1 << new_index):
                old_mask |= 1 << old_index
        relabeled[new_mask] = shape[old_mask]
    return tuple(relabeled)


def canonical_quadruple_region_shape(
    pool_size: int,
    first: Ticket,
    second: Ticket,
    third: Ticket,
    fourth: Ticket,
) -> QuadrupleShape:
    """Return the exact 16-region shape, canonical under ticket relabeling.

    Region ``mask`` contains numbers belonging to exactly the tickets whose
    bits are set; region zero is outside the union of all four tickets.  The
    full region orbit retains the incidence pattern among the six pairwise,
    four triple, and one quadruple intersections.  Sorting those aggregate
    intersection values alone is not a sufficient S4 shape key.
    """

    tickets = _validated_quadruple((first, second, third, fourth), pool_size)
    raw_shape = _raw_region_shape(tickets, pool_size)
    return min(_relabel_region_shape(raw_shape, permutation) for permutation in _RELABELINGS)


def ticket_quadruple_intersection_histogram(
    portfolio: Sequence[Ticket], pool_size: int
) -> tuple[tuple[QuadrupleShape, int], ...]:
    """Count canonical full-region shapes over every unordered ticket quadruple."""

    counter: Counter[QuadrupleShape] = Counter()
    for quadruple in itertools.combinations(tuple(portfolio), _TICKET_COUNT):
        shape = canonical_quadruple_region_shape(pool_size, *quadruple)
        counter[shape] += 1
    return tuple(sorted(counter.items()))


def _validated_region_shape(pool_size: int, region_shape: QuadrupleShape) -> None:
    if len(region_shape) != _REGION_COUNT:
        raise ValueError("a quadruple shape must contain 16 region sizes")
    if any(size < 0 for size in region_shape):
        raise ValueError("quadruple region sizes must be non-negative")
    if sum(region_shape) != pool_size:
        raise ValueError("quadruple region sizes must sum to pool_size")


def ticket_quadruple_hit_event_intersection_size(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    region_shape: QuadrupleShape,
) -> int:
    """Count draws that hit all four tickets at ``minimum_matches``.

    The sum ranges over choosing ``x_mask`` numbers from each exact
    membership region.  It is a direct four-ticket generalization of the
    Phase-6 triple formula and does not enumerate winning combinations.
    """

    _validate_shape(pool_size, draw_size, minimum_matches)
    _validated_region_shape(pool_size, region_shape)

    suffix_capacity = [[0] * _TICKET_COUNT for _ in range(_REGION_COUNT + 1)]
    for index in range(_REGION_COUNT - 1, -1, -1):
        mask = index
        suffix_capacity[index] = suffix_capacity[index + 1].copy()
        for ticket_index in range(_TICKET_COUNT):
            if mask & (1 << ticket_index):
                suffix_capacity[index][ticket_index] += region_shape[index]

    @cache
    def count(index: int, remaining: int, matches: tuple[int, int, int, int]) -> int:
        if remaining < 0:
            return 0
        if index == _REGION_COUNT:
            return int(remaining == 0 and all(match >= minimum_matches for match in matches))
        if remaining > sum(region_shape[index:]):
            return 0
        if any(
            matches[ticket_index] + suffix_capacity[index][ticket_index] < minimum_matches
            for ticket_index in range(_TICKET_COUNT)
        ):
            return 0

        mask = index
        total = 0
        for selected in range(min(region_shape[index], remaining) + 1):
            next_matches = tuple(
                matches[ticket_index] + (selected if mask & (1 << ticket_index) else 0)
                for ticket_index in range(_TICKET_COUNT)
            )
            total += math.comb(region_shape[index], selected) * count(
                index + 1, remaining - selected, next_matches
            )
        return total

    return count(0, draw_size, (0, 0, 0, 0))


def s4_from_ticket_quadruple_region_histogram(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    histogram: Mapping[QuadrupleShape, int],
) -> int:
    """Derive ``S4`` by summing exact event intersections over shape counts."""

    total = 0
    for shape, quadruple_count in histogram.items():
        if quadruple_count < 0:
            raise ValueError("quadruple counts must be non-negative")
        total += quadruple_count * ticket_quadruple_hit_event_intersection_size(
            pool_size, draw_size, minimum_matches, shape
        )
    return total


def quadruple_region_mass(region_shape: QuadrupleShape) -> int:
    """Return ``sum_(|A|>=2) (|A|-1) q_A`` for a full-region shape."""

    _validated_region_shape(sum(region_shape), region_shape)
    return sum(
        (mask.bit_count() - 1) * region_shape[mask]
        for mask in range(_REGION_COUNT)
        if mask.bit_count() >= 2
    )


def quadruple_collision_mass(
    pairwise_intersections: Sequence[int],
    triple_intersections: Sequence[int],
    quadruple_intersection: int,
) -> int:
    """Return ``sum(pairwise) - sum(triple) + quadruple`` exactly.

    This equals ``4*d - |t1 union t2 union t3 union t4|`` and the full-region
    mass above.  It is a necessary-capacity quantity, not a sufficient
    condition for a nonzero quadruple hit event.
    """

    if len(pairwise_intersections) != 6:
        raise ValueError("four-ticket geometry requires six pairwise intersections")
    if len(triple_intersections) != 4:
        raise ValueError("four-ticket geometry requires four triple intersections")
    if any(value < 0 for value in (*pairwise_intersections, *triple_intersections)):
        raise ValueError("intersection sizes must be non-negative")
    if quadruple_intersection < 0:
        raise ValueError("quadruple intersection must be non-negative")
    return sum(pairwise_intersections) - sum(triple_intersections) + quadruple_intersection


def quadruple_collision_is_impossible(
    draw_size: int,
    minimum_matches: int,
    pairwise_intersections: Sequence[int],
    triple_intersections: Sequence[int],
    quadruple_intersection: int,
) -> bool:
    """Return the exact mass-bound predicate ``M4 < 4*m-d``."""

    return quadruple_collision_mass(
        pairwise_intersections, triple_intersections, quadruple_intersection
    ) < 4 * minimum_matches - draw_size


def quadruple_shape_is_saturated(
    draw_size: int, minimum_matches: int, region_shape: QuadrupleShape
) -> bool:
    """Return whether a shape reaches the necessary mass boundary exactly."""

    return quadruple_region_mass(region_shape) == 4 * minimum_matches - draw_size


def max_pairwise_overlap_forces_zero_quadruple_collisions(
    draw_size: int, minimum_matches: int, max_pairwise_overlap: int
) -> bool:
    """Return the uniform-cap corollary ``6*c < 4*m-d``."""

    if max_pairwise_overlap < 0:
        raise ValueError("max_pairwise_overlap must be non-negative")
    return 6 * max_pairwise_overlap < 4 * minimum_matches - draw_size
