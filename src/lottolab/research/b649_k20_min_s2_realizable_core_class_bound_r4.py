"""Degree-sequence bound for the K20 minimum-S2 family.

The 22 triple supports form a linear 3-uniform hypergraph H: no ticket pair
appears in two supports. Let d_i be the degree of ticket i in H. All 49
labels have support size two or three, and every ticket has six labels, so
the 27 residual double supports give ticket i exactly 6-d_i further overlap
edges. The overlap graph therefore has degree 6+d_i at ticket i.

For a ten-ticket set A and a triple support S, put k=|S intersect A|. For
k=0,1,2,3, binom(k,2) >= 2k-3. Linearity bounds the number of H-pairs inside
A by binom(10,2), hence
  2 * sum_{i in A} d_i - 3*22 <= binom(10,2),
so the sum of the ten largest d_i is at most 55.

The exact integer case table by q=d_10 then bounds sum(d_i**2) by 356.
Since sum(d_i)=66,
  W = sum binom(6+d_i,2) = 663 + sum(d_i**2)/2 <= 841.

For the overlap graph, let T count triangles other than the 22 support
triangles. Each graph triangle uses three distinct wedges, so
T <= floor(W/3)-22. Exact three-ticket local counts are 2,800 for a two-edge
wedge, 20,272 for a triangle made from three double supports, and 7,000 for a
triangle containing one triple support. Thus
S3 = 2800*(W-3*(22+T)) + 20272*T + 7000*22
   = 2800*W + 11872*T - 30800.
We use no positive S4 correction; the ordinary third-order Bonferroni bound
already gives a strict improvement.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from math import comb

K20_TICKET_COUNT = 20
K20_TICKET_CAPACITY = 6
K20_LABEL_COUNT = 49
K20_TRIPLE_SUPPORT_COUNT = 22
K20_DOUBLE_SUPPORT_COUNT = 27
K20_TRIPLE_INCIDENCE_COUNT = 3 * K20_TRIPLE_SUPPORT_COUNT

K20_S1 = 372_228_640
K20_S2 = 63_838_600
K20_INCUMBENT = 313_239_661
K20_PREVIOUS_FAMILY_UPPER_BOUND = 313_915_480

K20_S3_WEDGE_COEFFICIENT = 2_800
K20_S3_TRIANGLE_COEFFICIENT = 11_872
K20_S3_CONSTANT = 30_800

K20_PROFILE_DEGREE_SQUARE_CASE_TABLE: tuple[tuple[int, int | None], ...] = (
    (0, None),
    (1, None),
    (2, 338),
    (3, 344),
    (4, 350),
    (5, 356),
    (6, None),
)


@dataclass(frozen=True, slots=True)
class K20RealizableCoreClassCertificate:
    """Exact bounded-profile enumeration and its union-bound envelope."""

    degree_sequence_count: int
    pair_capacity_compatible_degree_sequence_count: int
    maximum_wedge_count: int
    maximizing_degree_sequences: tuple[tuple[int, ...], ...]
    maximum_noncore_triangle_count: int
    s3_upper_bound: int
    s4_lower_bound_used: int
    fourth_order_correction_used: int
    family_upper_bound: int
    incumbent: int
    remaining_family_gap: int
    family_status: str


def _validate_nonnegative_int(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def bounded_nonincreasing_degree_sequences(
    total: int, slots: int, maximum_value: int
) -> tuple[tuple[int, ...], ...]:
    """Enumerate each bounded integer degree multiset once, in descending order."""

    _validate_nonnegative_int(total, "total")
    _validate_nonnegative_int(slots, "slots")
    _validate_nonnegative_int(maximum_value, "maximum_value")
    if slots == 0:
        if total == 0:
            return ((),)
        raise ValueError("a positive total cannot fit into zero slots")
    if total > slots * maximum_value:
        raise ValueError("total cannot fit within the per-slot maximum")

    def visit(remaining: int, remaining_slots: int, previous_max: int) -> Iterator[tuple[int, ...]]:
        if remaining_slots == 0:
            if remaining == 0:
                yield ()
            return
        upper = min(previous_max, remaining)
        for value in range(upper, -1, -1):
            tail_total = remaining - value
            if tail_total > (remaining_slots - 1) * value:
                continue
            for tail in visit(tail_total, remaining_slots - 1, value):
                yield (value, *tail)

    return tuple(visit(total, slots, maximum_value))


def minimum_internal_pair_uses(incidence_count: int, support_count: int) -> int:
    """Minimize internal pair uses over support intersections of sizes 0..3."""

    _validate_nonnegative_int(incidence_count, "incidence_count")
    _validate_nonnegative_int(support_count, "support_count")
    if support_count == 0:
        if incidence_count == 0:
            return 0
        raise ValueError("positive incidences require at least one support")
    if incidence_count > 3 * support_count:
        raise ValueError("incidence_count exceeds the 3-uniform support capacity")

    quotient, remainder = divmod(incidence_count, support_count)
    return (support_count - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)


def linear_triple_degree_sequence_passes_pair_capacity(
    degrees: Sequence[int], support_count: int
) -> bool:
    """Check necessary pair-capacity inequalities for a linear triple system.

    The check is intentionally necessary, not sufficient: profiles passing it
    are candidate degree sequences, not asserted realizations.
    """

    _validate_nonnegative_int(support_count, "support_count")
    values = tuple(degrees)
    if any(type(value) is not int for value in values):
        raise TypeError("degrees must contain only integers")
    if any(value < 0 for value in values):
        raise ValueError("degrees must be non-negative")
    if sum(values) != 3 * support_count:
        return False
    if any(value > support_count for value in values):
        return False

    descending = tuple(sorted(values, reverse=True))
    for slot_count in range(1, len(descending) + 1):
        incidence_count = sum(descending[:slot_count])
        minimum_pairs = minimum_internal_pair_uses(incidence_count, support_count)
        if minimum_pairs > comb(slot_count, 2):
            return False
    return True


def overlap_wedge_count(triple_degrees: Sequence[int]) -> int:
    """Return W=sum binom(6+d_i, 2) for a K20 triple-degree profile."""

    values = tuple(triple_degrees)
    if len(values) != K20_TICKET_COUNT:
        raise ValueError(f"K20 profiles must contain {K20_TICKET_COUNT} degrees")
    if any(type(value) is not int for value in values):
        raise TypeError("triple_degrees must contain only integers")
    if any(not 0 <= value <= K20_TICKET_CAPACITY for value in values):
        raise ValueError("triple degrees must lie between zero and ticket capacity")
    if sum(values) != K20_TRIPLE_INCIDENCE_COUNT:
        raise ValueError("triple degrees must sum to 66")
    return sum(comb(K20_TICKET_CAPACITY + value, 2) for value in values)


def s3_sum_from_wedges_and_triangles(wedge_count: int, noncore_triangle_count: int) -> int:
    """Return the exact local-profile identity for the third intersection sum."""

    if type(wedge_count) is not int or type(noncore_triangle_count) is not int:
        raise TypeError("wedge_count and noncore_triangle_count must be integers")
    if noncore_triangle_count < 0:
        raise ValueError("noncore_triangle_count must be non-negative")
    triangle_count = K20_TRIPLE_SUPPORT_COUNT + noncore_triangle_count
    two_edge_wedge_count = wedge_count - 3 * triangle_count
    if two_edge_wedge_count < 0:
        raise ValueError("triangle count exceeds the available wedge count")
    return (
        K20_S3_WEDGE_COEFFICIENT * two_edge_wedge_count
        + 20_272 * noncore_triangle_count
        + 7_000 * K20_TRIPLE_SUPPORT_COUNT
    )


def s3_upper_bound_from_wedges(wedge_count: int) -> tuple[int, int]:
    """Return the triangle and S3 ceilings implied by a wedge count."""

    if type(wedge_count) is not int:
        raise TypeError("wedge_count must be an integer")
    if wedge_count < 3 * K20_TRIPLE_SUPPORT_COUNT:
        raise ValueError("the 22 core triangles already require 66 wedges")
    noncore_triangle_count = wedge_count // 3 - K20_TRIPLE_SUPPORT_COUNT
    return (
        noncore_triangle_count,
        s3_sum_from_wedges_and_triangles(wedge_count, noncore_triangle_count),
    )


def _maximum_square_sum_with_bounds(total: int, slots: int, lower: int, upper: int) -> int | None:
    """Maximize an integer square sum in a box by saturating its endpoints."""

    if not slots * lower <= total <= slots * upper:
        return None
    if lower == upper:
        return slots * lower**2

    excess = total - slots * lower
    capacity = upper - lower
    full, remainder = divmod(excess, capacity)
    square_sum = full * upper**2
    if full < slots:
        square_sum += (lower + remainder) ** 2
        full += 1
    return square_sum + (slots - full) * lower**2


def _degree_square_case_table() -> tuple[tuple[int, int | None], ...]:
    """Compute the exact convex allocation bound for each d_10 value."""

    table: list[tuple[int, int | None]] = []
    for tenth_degree in range(K20_TICKET_CAPACITY + 1):
        best: int | None = None
        first_ten_minimum = 10 * tenth_degree
        first_ten_maximum = min(55, 9 * K20_TICKET_CAPACITY + tenth_degree)
        for first_ten_sum in range(first_ten_minimum, first_ten_maximum + 1):
            tail_sum = K20_TRIPLE_INCIDENCE_COUNT - first_ten_sum
            top_nine_squares = _maximum_square_sum_with_bounds(
                first_ten_sum - tenth_degree,
                9,
                tenth_degree,
                K20_TICKET_CAPACITY,
            )
            tail_squares = _maximum_square_sum_with_bounds(
                tail_sum,
                10,
                0,
                tenth_degree,
            )
            if top_nine_squares is None or tail_squares is None:
                continue
            candidate = top_nine_squares + tenth_degree**2 + tail_squares
            best = candidate if best is None else max(best, candidate)
        table.append((tenth_degree, best))
    return tuple(table)


def k20_min_s2_realizable_core_class_certificate() -> K20RealizableCoreClassCertificate:
    """Return the profile enumeration and direct third-order union certificate."""

    if K20_TRIPLE_SUPPORT_COUNT + K20_DOUBLE_SUPPORT_COUNT != K20_LABEL_COUNT:
        raise AssertionError("the 49-label support partition changed")
    if (
        3 * K20_TRIPLE_SUPPORT_COUNT + 2 * K20_DOUBLE_SUPPORT_COUNT
        != K20_TICKET_COUNT * K20_TICKET_CAPACITY
    ):
        raise AssertionError("the ticket support-capacity identity changed")

    profiles = bounded_nonincreasing_degree_sequences(
        K20_TRIPLE_INCIDENCE_COUNT,
        K20_TICKET_COUNT,
        K20_TICKET_CAPACITY,
    )
    candidates = tuple(
        profile
        for profile in profiles
        if linear_triple_degree_sequence_passes_pair_capacity(profile, K20_TRIPLE_SUPPORT_COUNT)
    )
    if not candidates:
        raise AssertionError("the K20 linear triple-support profile set is empty")

    table = _degree_square_case_table()
    if table != K20_PROFILE_DEGREE_SQUARE_CASE_TABLE:
        raise AssertionError("the exact degree-square case table changed")

    maximizing_wedge_count = max(overlap_wedge_count(profile) for profile in candidates)
    maximizing_profiles = tuple(
        profile for profile in candidates if overlap_wedge_count(profile) == maximizing_wedge_count
    )
    maximum_square_sum = max(value for _, value in table if value is not None)
    case_table_wedge_bound = 663 + maximum_square_sum // 2
    if maximizing_wedge_count != case_table_wedge_bound:
        raise AssertionError("profile enumeration and the integer case table disagree")
    if maximizing_wedge_count != 841:
        raise AssertionError("the K20 pair-capacity wedge bound changed")

    maximum_triangles, s3_upper_bound = s3_upper_bound_from_wedges(maximizing_wedge_count)
    family_upper_bound = K20_S1 - K20_S2 + s3_upper_bound
    remaining_gap = family_upper_bound - K20_INCUMBENT
    if family_upper_bound <= K20_INCUMBENT:
        family_status = "CLOSED"
    elif family_upper_bound < K20_PREVIOUS_FAMILY_UPPER_BOUND:
        family_status = "OPEN_STRICTLY_TIGHTENED"
    else:
        family_status = "OPEN"

    return K20RealizableCoreClassCertificate(
        degree_sequence_count=len(profiles),
        pair_capacity_compatible_degree_sequence_count=len(candidates),
        maximum_wedge_count=maximizing_wedge_count,
        maximizing_degree_sequences=maximizing_profiles,
        maximum_noncore_triangle_count=maximum_triangles,
        s3_upper_bound=s3_upper_bound,
        s4_lower_bound_used=0,
        fourth_order_correction_used=0,
        family_upper_bound=family_upper_bound,
        incumbent=K20_INCUMBENT,
        remaining_family_gap=remaining_gap,
        family_status=family_status,
    )


__all__ = [
    "K20_DOUBLE_SUPPORT_COUNT",
    "K20_INCUMBENT",
    "K20_LABEL_COUNT",
    "K20_PREVIOUS_FAMILY_UPPER_BOUND",
    "K20_PROFILE_DEGREE_SQUARE_CASE_TABLE",
    "K20_S1",
    "K20_S2",
    "K20_TICKET_CAPACITY",
    "K20_TICKET_COUNT",
    "K20_TRIPLE_INCIDENCE_COUNT",
    "K20_TRIPLE_SUPPORT_COUNT",
    "K20RealizableCoreClassCertificate",
    "bounded_nonincreasing_degree_sequences",
    "k20_min_s2_realizable_core_class_certificate",
    "linear_triple_degree_sequence_passes_pair_capacity",
    "minimum_internal_pair_uses",
    "overlap_wedge_count",
    "s3_sum_from_wedges_and_triangles",
    "s3_upper_bound_from_wedges",
]
