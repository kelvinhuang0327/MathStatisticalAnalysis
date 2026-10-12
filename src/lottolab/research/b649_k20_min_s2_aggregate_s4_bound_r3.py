"""Aggregate weighted fourth-order bound for the K20 minimum-S2 family.

Let t_i be the number of triple-label supports containing ticket i. The 66
triple incidences give sum(t_i)=66, so convexity gives sum(t_i**2)>=222.
For a triple support S and an outside ticket v, let n(S,v) count the three
core tickets adjacent to v in the overlap graph. Summing these incidences
over all 22 supports gives

    sum(S,v) n(S,v) = 4*66 + sum_i(t_i**2) >= 486.

There are 22*17=374 support/outside-ticket cells. Since
binom(n,2)>=n-1 for n in {0,1,2,3}, the sum of outside common-neighbor
incidences over the 66 core edges is at least 486-374=112.

Write c_e for the number of outside common neighbors of core edge e. The
collision witnesses are pairs of such neighbors, so their total is
sum_e binom(c_e,2). Convexity over 66 edges makes this at least 46.
The balanced relaxation has 20 edges with one outside common neighbor and 46
with two; this is only the minimizer of the lower-bound relaxation, not a
claim about the actual edge distribution.

Each witness is a four-ticket intersection with an exact local profile:
five overlap edges and no contained triple contribute 112 outcomes and can
carry at most five witnesses; six edges without a contained triple contribute
679 and can carry at most six; six edges with a contained triple contribute
448 and can carry at most three. Thus a quartet with m witnesses contributes
at least 112*ceil(m/5), and aggregate S4 is at least
112*ceil(46/5)=1120. The exact local weights are supplied by the compressed
four-ticket profile dynamic program in the existing K20 closure module.

For a witness quartet, every witnessing core edge is one of its overlapping
ticket pairs, and a fixed edge determines at most one witness for that
quartet. If the quartet contains a triple-label support, its three core edges
cannot witness because the third ticket of each such edge is inside the
quartet; therefore only the other three pairs can witness. If it has no
contained triple, the five-edge and six-edge profiles have at most five and
six witnessing pairs respectively.

The existing multiplicity-seven Bonferroni argument then credits at least
ceil(4*S4/7) outcomes to fourth order. This module is specific to the
minimum-S2 K20 structure; it does not add general inclusion-exclusion code.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import (
    K20_INCUMBENT,
    K20_S1,
    K20_S2,
    K20_S3_BOUND,
    K20_TICKET_COUNT,
    K20_TRIPLE_LABEL_COUNT,
    k20_min_s2_s4_lower_bound_certificate,
)

K20_TRIPLE_INCIDENCE_COUNT = 3 * K20_TRIPLE_LABEL_COUNT
K20_CORE_EDGE_COUNT = K20_TRIPLE_INCIDENCE_COUNT
K20_SUPPORT_OUTSIDE_PAIR_COUNT = K20_TRIPLE_LABEL_COUNT * (K20_TICKET_COUNT - 3)
K20_LOCAL_PROFILE_WITNESS_CAPACITIES_AND_WEIGHTS = (
    (5, 112),
    (6, 679),
    (3, 448),
)


@dataclass(frozen=True, slots=True)
class AggregateWeightedS4Certificate:
    """Integer steps in the aggregate collision and weighted S4 proof."""

    minimum_triple_degree_square_sum: int
    cross_incidence_lower_bound: int
    support_outside_pair_count: int
    aggregate_common_neighbor_incidence_lower_bound: int
    core_edge_count: int
    aggregate_collision_witness_lower_bound: int
    previous_s4_lower_bound: int
    aggregate_weighted_s4_lower_bound: int
    bonferroni_fourth_order_credit: int
    previous_family_upper_bound: int
    family_upper_bound: int
    incumbent: int
    remaining_family_gap: int
    family_status: str


def minimum_degree_square_sum(
    total: int, slots: int, *, maximum_per_slot: int | None = None
) -> int:
    """Return the minimum sum of squares for bounded nonnegative integers."""

    if type(total) is not int or type(slots) is not int:
        raise TypeError("total and slots must be integers")
    if total < 0 or slots <= 0:
        raise ValueError("total must be non-negative and slots must be positive")
    quotient, remainder = divmod(total, slots)
    if maximum_per_slot is not None:
        if type(maximum_per_slot) is not int or maximum_per_slot < 0:
            raise ValueError("maximum_per_slot must be a non-negative integer")
        if quotient > maximum_per_slot or (quotient == maximum_per_slot and remainder):
            raise ValueError("total cannot fit within the per-slot maximum")
    return (slots - remainder) * quotient**2 + remainder * (quotient + 1) ** 2


def minimum_collision_count(total_incidence: int, slots: int, *, maximum_per_slot: int) -> int:
    """Minimize sum(binomial(n, 2)) over bounded integer incidence loads."""

    if type(total_incidence) is not int or type(slots) is not int:
        raise TypeError("total_incidence and slots must be integers")
    if total_incidence < 0 or slots <= 0:
        raise ValueError("total_incidence must be non-negative and slots must be positive")
    if type(maximum_per_slot) is not int or maximum_per_slot < 0:
        raise ValueError("maximum_per_slot must be a non-negative integer")
    quotient, remainder = divmod(total_incidence, slots)
    if quotient > maximum_per_slot or (quotient == maximum_per_slot and remainder):
        raise ValueError("total incidence cannot fit within the per-slot maximum")
    return (slots - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)


def minimum_pair_collision_count(total: int, slots: int) -> int:
    """Minimize pair collisions when distributing counts over core edges."""

    if type(total) is not int or type(slots) is not int:
        raise TypeError("total and slots must be integers")
    if total < 0 or slots <= 0:
        raise ValueError("total must be non-negative and slots must be positive")
    quotient, remainder = divmod(total, slots)
    return (slots - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)


def weighted_s4_lower_bound_from_witnesses(witness_count: int) -> int:
    """Map aggregate collision witnesses to exact weighted quartet profiles.

    The 112-outcome profile carries at most five witnesses. The 679-outcome
    profile carries at most six, and the 448-outcome profile with a contained
    triple carries at most three. For each profile its exact weight is at
    least 112*ceil(profile witness count/5); summing over quartets proves this
    bound for the aggregate witness count.
    """

    if type(witness_count) is not int:
        raise TypeError("witness_count must be an integer")
    if witness_count < 0:
        raise ValueError("witness_count must be non-negative")
    return 112 * ((witness_count + 4) // 5)


def bonferroni_fourth_order_credit(s4_lower_bound: int) -> int:
    """Return the integer credit implied by the multiplicity-seven bound."""

    if type(s4_lower_bound) is not int:
        raise TypeError("s4_lower_bound must be an integer")
    if s4_lower_bound < 0:
        raise ValueError("s4_lower_bound must be non-negative")
    return (4 * s4_lower_bound + 6) // 7


def family_upper_bound_from_s4(s4_lower_bound: int) -> int:
    """Combine an S4 floor with the certified K20 S1/S2/S3 values."""

    return K20_S1 - K20_S2 + K20_S3_BOUND - bonferroni_fourth_order_credit(s4_lower_bound)


def k20_min_s2_aggregate_weighted_s4_certificate() -> AggregateWeightedS4Certificate:
    """Return the aggregate weighted fourth-order certificate for K20."""

    minimum_square_sum = minimum_degree_square_sum(
        K20_TRIPLE_INCIDENCE_COUNT, K20_TICKET_COUNT, maximum_per_slot=6
    )
    cross_incidence_lower_bound = 4 * K20_TRIPLE_INCIDENCE_COUNT + minimum_square_sum
    common_neighbor_lower_bound = cross_incidence_lower_bound - K20_SUPPORT_OUTSIDE_PAIR_COUNT
    if common_neighbor_lower_bound <= 0:
        raise AssertionError("the K20 common-neighbor incidence floor changed")

    witness_lower_bound = minimum_pair_collision_count(
        common_neighbor_lower_bound, K20_CORE_EDGE_COUNT
    )
    weighted_s4_lower_bound = weighted_s4_lower_bound_from_witnesses(witness_lower_bound)
    previous_s4_lower_bound = k20_min_s2_s4_lower_bound_certificate().s4_lower_bound
    previous_family_upper_bound = family_upper_bound_from_s4(previous_s4_lower_bound)
    family_upper_bound = family_upper_bound_from_s4(weighted_s4_lower_bound)
    remaining_gap = family_upper_bound - K20_INCUMBENT
    if remaining_gap <= 0:
        family_status = "CLOSED"
    elif family_upper_bound < previous_family_upper_bound:
        family_status = "OPEN_STRICTLY_TIGHTENED"
    else:
        family_status = "OPEN"

    return AggregateWeightedS4Certificate(
        minimum_triple_degree_square_sum=minimum_square_sum,
        cross_incidence_lower_bound=cross_incidence_lower_bound,
        support_outside_pair_count=K20_SUPPORT_OUTSIDE_PAIR_COUNT,
        aggregate_common_neighbor_incidence_lower_bound=common_neighbor_lower_bound,
        core_edge_count=K20_CORE_EDGE_COUNT,
        aggregate_collision_witness_lower_bound=witness_lower_bound,
        previous_s4_lower_bound=previous_s4_lower_bound,
        aggregate_weighted_s4_lower_bound=weighted_s4_lower_bound,
        bonferroni_fourth_order_credit=bonferroni_fourth_order_credit(weighted_s4_lower_bound),
        previous_family_upper_bound=previous_family_upper_bound,
        family_upper_bound=family_upper_bound,
        incumbent=K20_INCUMBENT,
        remaining_family_gap=remaining_gap,
        family_status=family_status,
    )


__all__ = [
    "K20_CORE_EDGE_COUNT",
    "K20_LOCAL_PROFILE_WITNESS_CAPACITIES_AND_WEIGHTS",
    "K20_SUPPORT_OUTSIDE_PAIR_COUNT",
    "AggregateWeightedS4Certificate",
    "bonferroni_fourth_order_credit",
    "family_upper_bound_from_s4",
    "k20_min_s2_aggregate_weighted_s4_certificate",
    "minimum_collision_count",
    "minimum_degree_square_sum",
    "minimum_pair_collision_count",
    "weighted_s4_lower_bound_from_witnesses",
]
