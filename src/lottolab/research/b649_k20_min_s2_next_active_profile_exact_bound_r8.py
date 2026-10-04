"""Resolve the packet-pinned next K20 minimum-S2 profile and its successor.

The active degree profile is impossible: a linear triple system would induce
a simple shadow graph with a degree sequence that violates Erdos-Gallai.
After removing it, this module searches only the equal-wedge tie class for its
immediate ranked successor. It never rebuilds the 4,850-profile ranking.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import comb

from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_INCUMBENT,
    K20_S1,
    K20_S2,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    linear_triple_degree_sequence_passes_pair_capacity,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]

ACTIVE_PROFILE: DegreeProfile = (
    6,
    6,
    6,
    6,
    6,
    6,
    6,
    5,
    4,
    4,
    4,
    4,
    2,
    1,
    0,
    0,
    0,
    0,
    0,
    0,
)
EXPECTED_NEXT_PROFILE: DegreeProfile = (
    6,
    6,
    6,
    6,
    6,
    6,
    5,
    5,
    4,
    4,
    4,
    4,
    4,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
)

INHERITED_S4_LOWER_BOUND = 112
INHERITED_FOURTH_ORDER_CREDIT = (4 * INHERITED_S4_LOWER_BOUND) // 7
ACTIVE_PROFILE_WEDGE_COUNT = 836
ACTIVE_PROFILE_COARSE_TRIANGLE_BOUND = 278
ACTIVE_PROFILE_COARSE_S3_BOUND = 5_349_232
ACTIVE_PROFILE_COARSE_FAMILY_BOUND = 313_739_208


@dataclass(frozen=True, slots=True)
class ErdosGallaiViolation:
    """One failed prefix inequality for a proposed simple-graph degree list."""

    prefix_size: int
    left_hand_side: int
    right_hand_side: int


@dataclass(frozen=True, slots=True)
class CoarseProfileEnvelope:
    """The existing wedge-only envelope used to rank dangerous profiles."""

    degree_profile: DegreeProfile
    degree_sum: int
    triple_support_count: int
    residual_double_incidence_count: int
    wedge_count: int
    graph_triangle_upper_bound: int
    noncore_triangle_upper_bound: int
    s3_upper_bound: int
    fourth_order_credit: int
    family_upper_bound: int


@dataclass(frozen=True, slots=True)
class RankedProfileSuccessor:
    """The immediate eligible profile after the removed same-wedge profile."""

    degree_profile: DegreeProfile
    wedge_count: int
    s3_upper_bound: int
    family_upper_bound: int
    explored_prefix_states: int
    complete_profiles_examined: int
    eligible_candidates_checked: int


def _validate_profile(degrees: Sequence[int]) -> DegreeProfile:
    profile = tuple(degrees)
    if len(profile) != K20_TICKET_COUNT:
        raise ValueError(f"a K20 profile must have {K20_TICKET_COUNT} ticket degrees")
    if any(type(value) is not int for value in profile):
        raise TypeError("ticket degrees must be integers")
    if any(not 0 <= value <= K20_TICKET_CAPACITY for value in profile):
        raise ValueError("ticket degrees must lie between zero and six")
    if sum(profile) != K20_TRIPLE_INCIDENCE_COUNT:
        raise ValueError("triple degrees must sum to 66")
    if tuple(sorted(profile, reverse=True)) != profile:
        raise ValueError("degree profiles must be sorted in nonincreasing order")
    return profile


def triple_shadow_degree_sequence(degrees: Sequence[int]) -> DegreeProfile:
    """Return the simple shadow degrees forced by a linear triple system."""

    profile = tuple(degrees)
    if any(type(value) is not int or value < 0 for value in profile):
        raise ValueError("triple degrees must be nonnegative integers")
    return tuple(sorted((2 * value for value in profile), reverse=True))


def erdos_gallai_first_violation(degrees: Sequence[int]) -> ErdosGallaiViolation | None:
    """Return the first failed Erdos-Gallai inequality, if there is one."""

    values = tuple(degrees)
    if any(type(value) is not int for value in values):
        raise TypeError("graph degrees must be integers")
    if any(value < 0 for value in values):
        raise ValueError("graph degrees must be nonnegative")
    if sum(values) % 2:
        raise ValueError("the Erdos-Gallai test requires an even degree sum")

    ordered = tuple(sorted(values, reverse=True))
    prefix_sum = 0
    for prefix_size, degree in enumerate(ordered, start=1):
        prefix_sum += degree
        right_hand_side = prefix_size * (prefix_size - 1) + sum(
            min(tail_degree, prefix_size) for tail_degree in ordered[prefix_size:]
        )
        if prefix_sum > right_hand_side:
            return ErdosGallaiViolation(prefix_size, prefix_sum, right_hand_side)
    return None


def profile_shadow_obstruction(
    degrees: Sequence[int],
) -> ErdosGallaiViolation | None:
    """Certify nonrealizability when the forced shadow degrees are nongraphical.

    A missing violation is only inconclusive; graphical shadow degrees do not
    prove that a linear triple system exists.
    """

    profile = _validate_profile(degrees)
    return erdos_gallai_first_violation(triple_shadow_degree_sequence(profile))


def coarse_profile_envelope(degrees: Sequence[int]) -> CoarseProfileEnvelope:
    """Reproduce the existing coarse S3 and S4-corrected family envelope."""

    profile = _validate_profile(degrees)
    wedge_count = overlap_wedge_count(profile)
    graph_triangle_bound = wedge_count // 3
    noncore_triangle_bound = graph_triangle_bound - K20_TRIPLE_SUPPORT_COUNT
    if noncore_triangle_bound < 0:
        raise ValueError("the wedge count cannot contain the core support triangles")
    s3_bound = s3_sum_from_wedges_and_triangles(wedge_count, noncore_triangle_bound)
    residual_incidences = K20_TICKET_COUNT * K20_TICKET_CAPACITY - sum(profile)
    if residual_incidences != 2 * K20_DOUBLE_SUPPORT_COUNT:
        raise AssertionError("the residual double-support incidence total changed")
    family_bound = K20_S1 - K20_S2 + s3_bound - INHERITED_FOURTH_ORDER_CREDIT
    return CoarseProfileEnvelope(
        degree_profile=profile,
        degree_sum=sum(profile),
        triple_support_count=sum(profile) // 3,
        residual_double_incidence_count=residual_incidences,
        wedge_count=wedge_count,
        graph_triangle_upper_bound=graph_triangle_bound,
        noncore_triangle_upper_bound=noncore_triangle_bound,
        s3_upper_bound=s3_bound,
        fourth_order_credit=INHERITED_FOURTH_ORDER_CREDIT,
        family_upper_bound=family_bound,
    )


def _minimum_internal_pairs(incidence_count: int) -> int:
    quotient, remainder = divmod(incidence_count, K20_TRIPLE_SUPPORT_COUNT)
    return (K20_TRIPLE_SUPPORT_COUNT - remainder) * comb(quotient, 2) + remainder * comb(
        quotient + 1, 2
    )


def _simple_graph_degree_sequence_is_graphical(degrees: Sequence[int]) -> bool:
    values = tuple(degrees)
    return (
        sum(values) % 2 == 0
        and erdos_gallai_first_violation(values) is None
    )


def _minimum_square_sum(total: int, slots: int) -> int | None:
    if slots == 0:
        return 0 if total == 0 else None
    if total < 0:
        return None
    quotient, remainder = divmod(total, slots)
    return (slots - remainder) * quotient**2 + remainder * (quotient + 1) ** 2


def _maximum_square_sum(total: int, slots: int, degree_cap: int) -> int | None:
    if slots == 0:
        return 0 if total == 0 else None
    if total < 0 or total > slots * degree_cap:
        return None
    if degree_cap == 0:
        return 0 if total == 0 else None
    full, remainder = divmod(total, degree_cap)
    return full * degree_cap**2 + remainder**2


def next_ranked_same_wedge_profile() -> RankedProfileSuccessor:
    """Find only the next profile in the active profile's equal-bound tie.

    The pinned R6 result establishes that ``ACTIVE_PROFILE`` is first among
    unresolved profiles at W=836. Rank keys before the profile tuple are equal
    throughout this wedge class, so the immediate successor is the first
    lexicographically smaller profile that passes the existing necessary
    triple-pair and residual-simple-graph filters. The search is confined to
    sum(d_i)=66 and sum(d_i**2)=346; it does not rebuild the full profile list.
    """

    target = _validate_profile(ACTIVE_PROFILE)
    target_envelope = coarse_profile_envelope(target)
    if target_envelope.wedge_count != ACTIVE_PROFILE_WEDGE_COUNT:
        raise AssertionError("the packet-pinned active wedge count changed")
    target_square_sum = sum(degree**2 for degree in target)
    prefix: list[int] = []
    explored_prefix_states = 0
    complete_profiles_examined = 0
    eligible_candidates_checked = 0

    def visit(
        index: int,
        previous_degree: int,
        remaining_sum: int,
        remaining_square_sum: int,
        prefix_sum: int,
        already_smaller: bool,
    ) -> DegreeProfile | None:
        nonlocal explored_prefix_states
        nonlocal complete_profiles_examined
        nonlocal eligible_candidates_checked
        explored_prefix_states += 1
        remaining_slots = K20_TICKET_COUNT - index
        if remaining_slots == 0:
            if remaining_sum != 0 or remaining_square_sum != 0:
                return None
            complete_profiles_examined += 1
            candidate = tuple(prefix)
            if candidate >= target:
                return None
            eligible_candidates_checked += 1
            if not linear_triple_degree_sequence_passes_pair_capacity(
                candidate, K20_TRIPLE_SUPPORT_COUNT
            ):
                return None
            residual_degrees = tuple(K20_TICKET_CAPACITY - degree for degree in candidate)
            if not _simple_graph_degree_sequence_is_graphical(residual_degrees):
                return None
            envelope = coarse_profile_envelope(candidate)
            if envelope.wedge_count != ACTIVE_PROFILE_WEDGE_COUNT:
                raise AssertionError("the successor search left its fixed-wedge class")
            if envelope.family_upper_bound <= K20_INCUMBENT:
                return None
            return candidate

        maximum_degree = min(previous_degree, K20_TICKET_CAPACITY, remaining_sum)
        if maximum_degree * remaining_slots < remaining_sum:
            return None
        for degree in range(maximum_degree, -1, -1):
            if not already_smaller and degree > target[index]:
                continue
            now_smaller = already_smaller or degree < target[index]
            suffix_sum = remaining_sum - degree
            suffix_square_sum = remaining_square_sum - degree**2
            suffix_slots = remaining_slots - 1
            if suffix_sum < 0 or suffix_square_sum < 0:
                continue
            if suffix_sum > suffix_slots * degree:
                continue
            minimum_squares = _minimum_square_sum(suffix_sum, suffix_slots)
            maximum_squares = _maximum_square_sum(suffix_sum, suffix_slots, degree)
            if (
                minimum_squares is None
                or maximum_squares is None
                or not minimum_squares <= suffix_square_sum <= maximum_squares
            ):
                continue

            next_prefix_sum = prefix_sum + degree
            next_prefix_size = index + 1
            if _minimum_internal_pairs(next_prefix_sum) > comb(next_prefix_size, 2):
                continue
            prefix.append(degree)
            successor = visit(
                index + 1,
                degree,
                suffix_sum,
                suffix_square_sum,
                next_prefix_sum,
                now_smaller,
            )
            if successor is not None:
                return successor
            prefix.pop()
        return None

    successor_profile = visit(
        0,
        K20_TICKET_CAPACITY,
        K20_TRIPLE_INCIDENCE_COUNT,
        target_square_sum,
        0,
        False,
    )
    if successor_profile is None:
        raise AssertionError("the ranked successor in the fixed-wedge class was not found")
    envelope = coarse_profile_envelope(successor_profile)
    return RankedProfileSuccessor(
        degree_profile=successor_profile,
        wedge_count=envelope.wedge_count,
        s3_upper_bound=envelope.s3_upper_bound,
        family_upper_bound=envelope.family_upper_bound,
        explored_prefix_states=explored_prefix_states,
        complete_profiles_examined=complete_profiles_examined,
        eligible_candidates_checked=eligible_candidates_checked,
    )


def active_profile_realizability_certificate() -> tuple[
    DegreeProfile, ErdosGallaiViolation | None
]:
    """Return the exact packet profile and its shadow-graph obstruction."""

    return ACTIVE_PROFILE, profile_shadow_obstruction(ACTIVE_PROFILE)


__all__ = [
    "ACTIVE_PROFILE",
    "ACTIVE_PROFILE_COARSE_FAMILY_BOUND",
    "ACTIVE_PROFILE_COARSE_S3_BOUND",
    "ACTIVE_PROFILE_COARSE_TRIANGLE_BOUND",
    "ACTIVE_PROFILE_WEDGE_COUNT",
    "EXPECTED_NEXT_PROFILE",
    "CoarseProfileEnvelope",
    "ErdosGallaiViolation",
    "RankedProfileSuccessor",
    "active_profile_realizability_certificate",
    "coarse_profile_envelope",
    "erdos_gallai_first_violation",
    "next_ranked_same_wedge_profile",
    "profile_shadow_obstruction",
    "triple_shadow_degree_sequence",
]
