"""Exact, lottery-agnostic identities for the Phase-6 higher-order (j>=3) residual mechanism.

This module contains only pure combinatorial helpers.  It does not load a
lottery result artifact, construct a native B649/T539/P638 portfolio, read
historical draws, or write a Matrix result.  It generalizes the sealed
Phase-5 pairwise (``j=2``) geometry-to-multiplicity identity in
``lottolab.research.low_overlap_geometry_mechanism`` to ticket *triples*
(``j=3``): given a portfolio's raw ticket-triple intersection pattern, it
derives ``S_3`` independently of the winner-multiplicity route, exactly as
Phase 5 already does for ``S_2``.  It is used at toy scale so the formulas
can be tested before a separate Owner-authorized lock-and-execute task
exists.  See ``docs/research/strategy-matrix-phase6-higher-order-residual-
mechanism-design-r1.md`` for the derivation this module implements.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from collections.abc import Mapping, Sequence

Ticket = tuple[int, ...]

# Canonical (order-independent) ticket-triple shape: sorted pairwise
# intersection sizes followed by the triple intersection size.
TripleShape = tuple[int, int, int, int]

# The eight membership-pattern regions for a ticket triple {t1, t2, t3},
# keyed by an (in_t1, in_t2, in_t3) flag tuple.
_TRIPLE_REGION_KEYS: tuple[tuple[int, int, int], ...] = (
    (1, 1, 1),
    (1, 1, 0),
    (1, 0, 1),
    (0, 1, 1),
    (1, 0, 0),
    (0, 1, 0),
    (0, 0, 1),
    (0, 0, 0),
)


def _validate_shape(pool_size: int, draw_size: int, minimum_matches: int) -> None:
    if not 1 <= draw_size <= pool_size:
        raise ValueError("draw_size must lie in [1, pool_size]")
    if not 1 <= minimum_matches <= draw_size:
        raise ValueError("minimum_matches must lie in [1, draw_size]")


def canonical_triple_shape(
    pairwise_12: int, pairwise_13: int, pairwise_23: int, triple: int
) -> TripleShape:
    """Sort the three pairwise sizes so relabeling ``t1/t2/t3`` gives the same key.

    ``ticket_triple_hit_event_intersection_size`` is invariant under
    permuting which ticket is labeled 1/2/3 (see
    ``test_triple_hit_event_size_is_symmetric_under_ticket_relabeling``), so
    two triples that share a canonical shape always contribute the same
    amount to ``S_3``.
    """

    r_min, r_mid, r_max = sorted((pairwise_12, pairwise_13, pairwise_23))
    return (r_min, r_mid, r_max, triple)


def ticket_triple_intersection_histogram(
    portfolio: Sequence[Ticket],
) -> tuple[tuple[TripleShape, int], ...]:
    """Canonical-shape histogram over every unordered ticket triple in ``portfolio``.

    The triple-order analog of ``portfolio_geometry``'s
    ``ticket_pair_intersection_histogram`` in the sealed Phase-5 module.
    """

    tickets = tuple(portfolio)
    counter: Counter[TripleShape] = Counter()
    for first, second, third in itertools.combinations(tickets, 3):
        set_first, set_second, set_third = set(first), set(second), set(third)
        pairwise_12 = len(set_first & set_second)
        pairwise_13 = len(set_first & set_third)
        pairwise_23 = len(set_second & set_third)
        triple = len(set_first & set_second & set_third)
        shape = canonical_triple_shape(pairwise_12, pairwise_13, pairwise_23, triple)
        counter[shape] += 1
    return tuple(sorted(counter.items()))


def _triple_region_sizes(
    pool_size: int,
    draw_size: int,
    pairwise_12: int,
    pairwise_13: int,
    pairwise_23: int,
    triple: int,
) -> dict[tuple[int, int, int], int]:
    """Exact sizes of the eight ticket-triple membership regions.

    Region ``(1,1,0)`` means "in t1 and t2, not t3", etc.  See the Phase-6
    design doc S5 for the derivation; every size must be non-negative for
    the shape to be geometrically realizable at this ``pool_size``.
    """

    pairwise_values = (pairwise_12, pairwise_13, pairwise_23)
    if not all(0 <= pairwise <= draw_size for pairwise in pairwise_values):
        raise ValueError("pairwise intersections must lie in [0, draw_size]")
    if not 0 <= triple <= min(pairwise_12, pairwise_13, pairwise_23):
        raise ValueError("triple intersection must be <= every pairwise intersection")

    sizes: dict[tuple[int, int, int], int] = {
        (1, 1, 1): triple,
        (1, 1, 0): pairwise_12 - triple,
        (1, 0, 1): pairwise_13 - triple,
        (0, 1, 1): pairwise_23 - triple,
        (1, 0, 0): draw_size - pairwise_12 - pairwise_13 + triple,
        (0, 1, 0): draw_size - pairwise_12 - pairwise_23 + triple,
        (0, 0, 1): draw_size - pairwise_13 - pairwise_23 + triple,
    }
    sizes[(0, 0, 0)] = pool_size - 3 * draw_size + pairwise_12 + pairwise_13 + pairwise_23 - triple

    for region, size in sizes.items():
        if size < 0:
            raise ValueError(
                f"ticket-triple shape is not geometrically realizable: "
                f"region {region} has size {size}"
            )
    return sizes


def ticket_triple_hit_event_intersection_size(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    pairwise_12: int,
    pairwise_13: int,
    pairwise_23: int,
    triple: int,
) -> int:
    """Exact count of winning draws hitting all three tickets at ``minimum_matches``.

    Generalizes ``ticket_pair_hit_event_intersection_size`` (Phase-5,
    two tickets) to three.  The pool splits into eight regions by membership
    in ``{t1, t2, t3}``; this sums, over every way to place the ``draw_size``
    drawn numbers across those regions, the region-size-weighted count of
    placements where every ticket independently reaches ``minimum_matches``.
    ``pairwise_12/13/23`` are the raw pairwise ticket-number intersection
    sizes and ``triple`` is ``|t1 & t2 & t3|``.
    """

    _validate_shape(pool_size, draw_size, minimum_matches)
    region_sizes = _triple_region_sizes(
        pool_size, draw_size, pairwise_12, pairwise_13, pairwise_23, triple
    )
    ordered_keys = _TRIPLE_REGION_KEYS
    sizes = tuple(region_sizes[key] for key in ordered_keys)

    total = 0
    counts = [0] * len(ordered_keys)

    def recurse(index: int, remaining: int, matches: tuple[int, int, int]) -> None:
        nonlocal total
        if index == len(ordered_keys):
            if remaining == 0 and all(match >= minimum_matches for match in matches):
                weight = 1
                for size, count in zip(sizes, counts, strict=True):
                    weight *= math.comb(size, count)
                total += weight
            return
        key = ordered_keys[index]
        for count in range(min(sizes[index], remaining) + 1):
            counts[index] = count
            recurse(
                index + 1,
                remaining - count,
                (
                    matches[0] + (count if key[0] else 0),
                    matches[1] + (count if key[1] else 0),
                    matches[2] + (count if key[2] else 0),
                ),
            )
        counts[index] = 0

    recurse(0, draw_size, (0, 0, 0))
    return total


def s3_from_ticket_triple_intersection_histogram(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    histogram: Mapping[TripleShape, int],
) -> int:
    """Derive ``S_3`` from the exact ticket-triple intersection histogram.

    The triple-order analog of ``s2_from_ticket_pair_intersection_histogram``
    in the sealed Phase-5 module.
    """

    total = 0
    for shape, triple_count in histogram.items():
        if triple_count < 0:
            raise ValueError("triple counts must be non-negative")
        pairwise_12, pairwise_13, pairwise_23, triple = shape
        total += triple_count * ticket_triple_hit_event_intersection_size(
            pool_size, draw_size, minimum_matches, pairwise_12, pairwise_13, pairwise_23, triple
        )
    return total


def triple_collision_mass_bound(
    pairwise_12: int, pairwise_13: int, pairwise_23: int, triple: int
) -> int:
    """``r_12 + r_13 + r_23 - s``: the largest 'excess sharing mass' this triple can offer.

    See the Necessary Mass Bound Lemma, Phase-6 design doc S5.  A winning
    draw can hit all three tickets at threshold ``m`` only if this quantity
    is at least ``3*m - d``; ``triple_collision_is_impossible`` applies that
    test.
    """

    return pairwise_12 + pairwise_13 + pairwise_23 - triple


def triple_collision_is_impossible(
    draw_size: int,
    minimum_matches: int,
    pairwise_12: int,
    pairwise_13: int,
    pairwise_23: int,
    triple: int,
) -> bool:
    """``True`` iff the Necessary Mass Bound Lemma proves ``H_m^(3) == 0`` for every pool size.

    A cheap, ``pool_size``-independent, purely arithmetic sufficient test.
    ``False`` means a triple collision is not ruled out -- it is not a claim
    that one exists; that still requires evaluating
    ``ticket_triple_hit_event_intersection_size``.
    """

    mass = triple_collision_mass_bound(pairwise_12, pairwise_13, pairwise_23, triple)
    return mass < 3 * minimum_matches - draw_size


def max_pairwise_overlap_forces_zero_triple_collisions(
    draw_size: int, minimum_matches: int, max_pairwise_overlap: int
) -> bool:
    """``True`` iff every triple with overlaps <= ``max_pairwise_overlap`` has zero ``H_m^(3)``.

    Portfolio-level corollary of the Necessary Mass Bound Lemma: under a
    uniform per-pair overlap cap, the largest achievable mass bound is
    ``3 * max_pairwise_overlap`` (three distinct pairwise-only shared
    numbers, triple intersection 0).  If that is still short of
    ``3*minimum_matches - draw_size``, no triple anywhere in the portfolio
    can contribute to ``S_3``, regardless of ``k`` or pool size -- this is
    the exact mechanism behind ``PAIRWISE_COLLISION_EXACTLY_SUFFICIENT``
    whenever it is observed.
    """

    required_mass = 3 * minimum_matches - draw_size
    return 3 * max_pairwise_overlap < required_mass
