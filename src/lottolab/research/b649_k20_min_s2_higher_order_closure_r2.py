"""Fourth-order OFFICIAL_ANY_PRIZE intersections for the K20 minimum-S2 family.

The official lowest prize is equivalent to a ticket meeting at least three of
the seven labels in ``main_draw | special``.  This module counts only
four-ticket intersections; it does not implement a general inclusion-exclusion
engine.

For a four-ticket set ``Q``, let ``e(Q)`` be the number of ticket pairs that
share a label and let ``b(Q)`` indicate whether a multiplicity-three label is
supported by all three of its tickets inside ``Q``.  Since every ticket pair
overlaps at most once, ``b(Q)`` is zero or one.  The fourth-order intersection
is determined by this compressed profile:

* ``e=5, b=0``: 112 outcomes;
* ``e=6, b=0``: 679 outcomes;
* ``e=6, b=1``: 448 outcomes;
* every other profile: zero outcomes.

The counts follow by selecting the seven labels ``main_draw | special``.
Four winning tickets require at least twelve ticket-label incidences.  A
relative label has support size at most three in ``Q``; the three profiles
above are the only ones with enough incidence.  The independent dynamic
program below checks those local counts directly from the repeated-label
profile and is also parameterized for small exhaustive toy oracles.

The K20 profile also forces ``S4 >= 112``.  Suppose instead that no quartet
has a common winning outcome.  A triple-label support ``S`` then has at most
two overlap-graph neighbors from any outside ticket, or ``S`` plus that
ticket is a contributing six-edge quartet.  Across all 22 triple supports,
the number of cross incidences is at least
``4 * 66 + min(sum(t_i**2)) = 486``, where ``t_i`` is the number of triple
labels on ticket ``i`` and ``sum(t_i)=66``.  There are only ``22 * 17 = 374``
support/outside-ticket pairs, so at least 112 of them have exactly two
incidences.  Each such pair identifies one core edge with an outside common
neighbor.  A core edge cannot have two such outside common neighbors: those
two neighbors and the core edge form a contributing five- or six-edge
quartet.  There are only 66 core edges, a contradiction.  Every contributing
quartet has at least 112 common outcomes by the exact local table.

Finally, at most seven tickets can win on one outcome: choose three hit
labels from each winner; the resulting triples on seven labels are pairwise
linear, so they use distinct pairs and number at most ``C(7,2)/C(3,2)=7``.
For multiplicity ``r`` from 4 through 7, the third-order Bonferroni excess
over the union indicator is at least ``(4/7) * C(r,4)``.  Therefore the
fourth-order floor sharpens the family union upper bound by at least 64.

The earlier terms in that upper bound are checked from the same compressed
structure.  Each ticket covers 18,611,432 outcomes, so ``S1=372,228,640``.
There are 93 overlap-one pairs (27 double labels and 3 pairs from each of 22
triple labels) and 97 disjoint pairs; their intersection counts are 574,000
and 107,800, giving ``S2=63,838,600``.  If ``W`` is the overlap-graph wedge
count and ``T`` is the number of graph triangles other than the 22 core
triangles, the exact three-ticket local counts give
``S3 = 2,800 W + 11,872 T - 30,800``.  With ticket triple-label degrees
``t_i`` summing to 66 and bounded by 6, ``W=sum(C(6+t_i,2)) <= 861``; also
``3(T+22) <= W``, so ``T <= 265``.  Substitution verifies
``S3 <= 5,526,080`` and the third-order union bound ``313,916,120``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from math import comb

type Ticket = Sequence[int]
type ProfileCounts = Sequence[int]
type DynamicState = tuple[int, int, int, int, int]

BIG_LOTTO_POOL_SIZE = 49
BIG_LOTTO_DRAW_SIZE = 6
BIG_LOTTO_OUTRIGHT_MATCHES = 3
K20_TICKET_COUNT = 20
K20_TRIPLE_LABEL_COUNT = 22
K20_DOUBLE_LABEL_COUNT = 27
K20_S1 = 372_228_640
K20_S2 = 63_838_600
K20_MAX_WEDGES = 861
K20_MAX_NONCORE_TRIANGLES = 265
K20_S3_BOUND = (
    2_800 * K20_MAX_WEDGES + 11_872 * K20_MAX_NONCORE_TRIANGLES - 30_800
)
K20_INCUMBENT = 313_239_661


@dataclass(frozen=True, slots=True)
class S4LowerBoundCertificate:
    """Integer counts in the K20 triple-core contradiction proof."""

    minimum_triple_incidence_square_sum: int
    cross_incidence_lower_bound: int
    core_outside_pair_count: int
    double_incidence_lower_bound_if_no_contribution: int
    core_edge_count: int
    s4_lower_bound: int


@dataclass(frozen=True, slots=True)
class S4Decomposition:
    """Exact S4 contributions by four-ticket overlap type."""

    five_edges_without_contained_triple: int
    six_edges_without_contained_triple: int
    six_edges_with_contained_triple: int

    @property
    def s4(self) -> int:
        """Return the total fourth-order intersection count."""

        return (
            112 * self.five_edges_without_contained_triple
            + 679 * self.six_edges_without_contained_triple
            + 448 * self.six_edges_with_contained_triple
        )


def k20_min_s2_s4_lower_bound_certificate() -> S4LowerBoundCertificate:
    """Return the exact counting certificate proving ``S4 >= 112``.

    ``t_i`` is the number of triple-multiplicity labels on ticket ``i``.
    Each ticket has overlap-graph degree ``6 + t_i``.  Summing its external
    degree once for each incident triple support gives
    ``sum(t_i * (4 + t_i))``.  The balanced integer allocation minimizes
    ``sum(t_i**2)`` subject to 20 tickets and 66 triple incidences.

    If S4 were zero, no core support/outside-ticket pair could have three
    incidences, leaving at most one incidence on each of 374 pairs plus one
    extra for every pair with exactly two.  That forces at least 112 such
    pairs.  Two outside common neighbors on one core edge create a contributing
    quartet, so these pairs inject into the 66 distinct core edges, which is
    impossible.  Thus a contributing quartet exists, and the local table's
    smallest positive coefficient is 112.
    """

    ticket_count = K20_TICKET_COUNT
    triple_incidence_count = 3 * K20_TRIPLE_LABEL_COUNT
    balanced, remainder = divmod(triple_incidence_count, ticket_count)
    square_sum = (ticket_count - remainder) * balanced**2 + remainder * (balanced + 1) ** 2
    core_outside_pairs = K20_TRIPLE_LABEL_COUNT * (K20_TICKET_COUNT - 3)
    cross_incidence_lower_bound = 4 * triple_incidence_count + square_sum
    double_incidence_lower_bound = cross_incidence_lower_bound - core_outside_pairs
    core_edge_count = 3 * K20_TRIPLE_LABEL_COUNT
    if double_incidence_lower_bound <= core_edge_count:
        raise AssertionError("the K20 triple-core contradiction no longer closes")

    return S4LowerBoundCertificate(
        minimum_triple_incidence_square_sum=square_sum,
        cross_incidence_lower_bound=cross_incidence_lower_bound,
        core_outside_pair_count=core_outside_pairs,
        double_incidence_lower_bound_if_no_contribution=double_incidence_lower_bound,
        core_edge_count=core_edge_count,
        s4_lower_bound=112,
    )


def k20_min_s2_family_official_any_prize_upper_bound() -> int:
    """Return the certified union bound using the S3 and S4 floors."""

    s4_lower_bound = k20_min_s2_s4_lower_bound_certificate().s4_lower_bound
    # For r <= 7, the order-three Bonferroni excess is at least 4/7*C(r, 4).
    fourth_order_credit = (4 * s4_lower_bound) // 7
    return K20_S1 - K20_S2 + K20_S3_BOUND - fourth_order_credit


def compressed_four_ticket_intersection_count(
    profile_counts: ProfileCounts,
    *,
    pool_size: int,
    draw_size: int,
    outright_matches: int,
) -> int:
    """Count outcomes common to four tickets from their 4-bit incidence profile.

    ``profile_counts[mask]`` is the number of labels whose incidence mask among
    the four tickets is ``mask`` (mask zero covers labels outside all four).
    Outcomes are ordered pairs ``(main draw, special)`` with the special
    outside the main draw, matching the official BIG_LOTTO outcome space.
    """

    if len(profile_counts) != 16:
        raise ValueError("a four-ticket profile must have 16 incidence counts")
    if any(type(count) is not int or count < 0 for count in profile_counts):
        raise ValueError("profile counts must be non-negative integers")
    if sum(profile_counts) != pool_size:
        raise ValueError("profile counts must sum to pool_size")
    if not 1 <= draw_size < pool_size:
        raise ValueError("draw_size must be within 1..pool_size-1")
    if not 1 <= outright_matches <= draw_size:
        raise ValueError("outright_matches must be within 1..draw_size")

    total = 0
    for special_mask, special_multiplicity in enumerate(profile_counts):
        if special_multiplicity == 0:
            continue

        thresholds: tuple[int, int, int, int] = (
            outright_matches - int(bool(special_mask & 1)),
            outright_matches - int(bool(special_mask & 2)),
            outright_matches - int(bool(special_mask & 4)),
            outright_matches - int(bool(special_mask & 8)),
        )
        available = list(profile_counts)
        available[special_mask] -= 1
        states: dict[DynamicState, int] = {(0, 0, 0, 0, 0): 1}

        for incidence_mask, label_count in enumerate(available):
            if label_count == 0:
                continue
            following: dict[DynamicState, int] = {}
            for state, ways in states.items():
                used = state[0]
                hits = (state[1], state[2], state[3], state[4])
                max_take = min(label_count, draw_size - used)
                for take in range(max_take + 1):
                    new_hits: tuple[int, int, int, int] = (
                        min(thresholds[0], hits[0] + (take if incidence_mask & 1 else 0)),
                        min(thresholds[1], hits[1] + (take if incidence_mask & 2 else 0)),
                        min(thresholds[2], hits[2] + (take if incidence_mask & 4 else 0)),
                        min(thresholds[3], hits[3] + (take if incidence_mask & 8 else 0)),
                    )
                    new_state: DynamicState = (
                        used + take,
                        new_hits[0],
                        new_hits[1],
                        new_hits[2],
                        new_hits[3],
                    )
                    following[new_state] = following.get(new_state, 0) + ways * comb(
                        label_count, take
                    )
            states = following

        target: DynamicState = (
            draw_size,
            thresholds[0],
            thresholds[1],
            thresholds[2],
            thresholds[3],
        )
        total += special_multiplicity * states.get(target, 0)

    return total


def fourth_order_intersection_sum(family: Sequence[Ticket]) -> int:
    """Return exact S4 for a 6/49 family with pair overlap at most one.

    This compressed formula accepts a subset of a larger family, so labels
    that also occur outside ``family`` may appear only once in its incidence
    profile.  It requires each label to occur at most three times and each
    ticket pair to share at most one label.
    """

    if len(family) < 4:
        raise ValueError("fourth-order intersections require at least four tickets")

    normalized: list[frozenset[int]] = []
    label_supports: dict[int, set[int]] = {}
    for ticket_index, ticket in enumerate(family):
        if (
            len(ticket) != BIG_LOTTO_DRAW_SIZE
            or len(set(ticket)) != BIG_LOTTO_DRAW_SIZE
            or any(
                type(label) is not int or not 1 <= label <= BIG_LOTTO_POOL_SIZE
                for label in ticket
            )
        ):
            raise ValueError(f"illegal ticket at index {ticket_index}: {tuple(ticket)}")
        normalized_ticket = frozenset(ticket)
        normalized.append(normalized_ticket)
        for label in normalized_ticket:
            label_supports.setdefault(label, set()).add(ticket_index)

    if any(len(support) > 3 for support in label_supports.values()):
        raise ValueError("a label may occur in at most three tickets")
    for left, right in combinations(range(len(normalized)), 2):
        if len(normalized[left] & normalized[right]) > 1:
            raise ValueError("every ticket pair must overlap in at most one label")

    overlap_edges: set[frozenset[int]] = set()
    triple_supports: set[frozenset[int]] = set()
    for support_set in label_supports.values():
        support = frozenset(support_set)
        if len(support) == 2:
            overlap_edges.add(support)
        elif len(support) == 3:
            triple_supports.add(support)
            overlap_edges.update(frozenset(pair) for pair in combinations(support, 2))

    five_no_triple = 0
    six_no_triple = 0
    six_with_triple = 0
    for quartet in combinations(range(len(normalized)), 4):
        quartet_set = frozenset(quartet)
        edge_count = sum(edge <= quartet_set for edge in overlap_edges)
        contained_triples = sum(triple <= quartet_set for triple in triple_supports)
        if contained_triples > 1:
            raise ValueError("pair-overlap constraints permit at most one contained triple")
        if edge_count == 5 and contained_triples == 0:
            five_no_triple += 1
        elif edge_count == 6 and contained_triples == 0:
            six_no_triple += 1
        elif edge_count == 6 and contained_triples == 1:
            six_with_triple += 1

    return S4Decomposition(
        five_edges_without_contained_triple=five_no_triple,
        six_edges_without_contained_triple=six_no_triple,
        six_edges_with_contained_triple=six_with_triple,
    ).s4


def k20_min_s2_s4_decomposition(family: Sequence[Ticket]) -> S4Decomposition:
    """Return the exact compressed S4 decomposition for the specified K20 family."""

    if len(family) != K20_TICKET_COUNT:
        raise ValueError(f"K20 family must contain exactly {K20_TICKET_COUNT} tickets")
    normalized = [frozenset(ticket) for ticket in family]
    if any(len(ticket) != BIG_LOTTO_DRAW_SIZE for ticket in normalized):
        raise ValueError("every K20 ticket must contain six distinct labels")
    if any(
        type(label) is not int or not 1 <= label <= BIG_LOTTO_POOL_SIZE
        for ticket in normalized
        for label in ticket
    ):
        raise ValueError("K20 labels must be integers in 1..49")

    multiplicities = Counter(label for ticket in normalized for label in ticket)
    if Counter(multiplicities.values()) != Counter(
        {2: K20_DOUBLE_LABEL_COUNT, 3: K20_TRIPLE_LABEL_COUNT}
    ):
        raise ValueError("K20 labels must have the 27-double / 22-triple profile")

    five_no_triple = 0
    six_no_triple = 0
    six_with_triple = 0
    label_supports: dict[int, frozenset[int]] = {}
    for label in multiplicities:
        label_supports[label] = frozenset(
            ticket_index
            for ticket_index, ticket in enumerate(normalized)
            if label in ticket
        )
    for left, right in combinations(range(K20_TICKET_COUNT), 2):
        if len(normalized[left] & normalized[right]) > 1:
            raise ValueError("every ticket pair must overlap in at most one label")

    overlap_edges: set[frozenset[int]] = set()
    triple_supports: set[frozenset[int]] = set()
    for support in label_supports.values():
        if len(support) == 2:
            overlap_edges.add(support)
        else:
            triple_supports.add(support)
            overlap_edges.update(frozenset(pair) for pair in combinations(support, 2))

    for quartet in combinations(range(K20_TICKET_COUNT), 4):
        quartet_set = frozenset(quartet)
        edge_count = sum(edge <= quartet_set for edge in overlap_edges)
        contained_triples = sum(triple <= quartet_set for triple in triple_supports)
        if contained_triples > 1:
            raise ValueError("pair-overlap constraints permit at most one contained triple")
        if edge_count == 5 and contained_triples == 0:
            five_no_triple += 1
        elif edge_count == 6 and contained_triples == 0:
            six_no_triple += 1
        elif edge_count == 6 and contained_triples == 1:
            six_with_triple += 1

    return S4Decomposition(
        five_edges_without_contained_triple=five_no_triple,
        six_edges_without_contained_triple=six_no_triple,
        six_edges_with_contained_triple=six_with_triple,
    )


__all__ = [
    "BIG_LOTTO_DRAW_SIZE",
    "BIG_LOTTO_OUTRIGHT_MATCHES",
    "BIG_LOTTO_POOL_SIZE",
    "K20_DOUBLE_LABEL_COUNT",
    "K20_INCUMBENT",
    "K20_S1",
    "K20_S2",
    "K20_S3_BOUND",
    "K20_TICKET_COUNT",
    "K20_TRIPLE_LABEL_COUNT",
    "S4Decomposition",
    "S4LowerBoundCertificate",
    "Ticket",
    "compressed_four_ticket_intersection_count",
    "fourth_order_intersection_sum",
    "k20_min_s2_family_official_any_prize_upper_bound",
    "k20_min_s2_s4_decomposition",
    "k20_min_s2_s4_lower_bound_certificate",
]
