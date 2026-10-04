"""Realizability-tightened K20 r=4 anchor bound.

The r6 certificate supplies the exact 32 anchor-incidence profiles and a
certified envelope for the non-dangerous type-count classes. This module
enumerates the full high-good-count tail as 32-coordinate count vectors, adds
cellwise label-multiplicity floors, and tightens the three vectors that can
still attain the old envelope. It never searches over complete portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from itertools import combinations_with_replacement
from math import comb
from time import monotonic

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS,
    AnchorIncidenceProfile,
    anchor_incidence_profiles,
    minimum_label_pair_mass,
    minimum_residual_pair_counts_by_overlap,
    minimum_weighted_forest_census,
    pair_intersection_table,
)

BASE_HEAD = "3735fdcc2273e5e36c6a7a8a64352235aa7324a9"
BASE_TREE = "10ae61d7d1ea3cdc71a95299a181fc03cb4460f3"
TASK_BRANCH = "codex/b649-k20-r4-exact-anchor-realizability-r7"

POOL_SIZE = 49
DRAW_SIZE = 6
TICKET_COUNT = 20
OUTSIDE_TICKET_COUNT = 18
ANCHOR_OVERLAP = 4
ANCHOR_SHARED_CAPACITY = 4
ANCHOR_A_ONLY_CAPACITY = 2
ANCHOR_B_ONLY_CAPACITY = 2
OUTSIDE_LABEL_CAPACITY = 41

INCUMBENT = 313_239_661
CURRENT_R3_BOUND = 351_483_978
CURRENT_R5_BOUND = 350_778_728
CURRENT_R6_BOUND = 343_869_728
PREVIOUS_R4_BOUND = 354_532_444

EXPECTED_PAIR_COUNTS = (
    107_800,
    574_000,
    1_695_988,
    3_469_942,
    6_224_512,
    10_776_332,
    18_611_432,
)
EXPECTED_GLOBAL_PAIR_RESIDUAL_FLOORS = (11_242, 41_496, 41_496, 223_314, 804_258)

# Certified minima from the prior r6 result's 19 rows, indexed by good-ticket
# count. These rows already cover all best-non-good counts and use the prior
# second-best local recovery for every remaining type.
PRIOR_MINIMUM_REDUCTION_BY_GOOD_COUNT = (
    12_521_880,
    11_879_560,
    11_237_240,
    10_594_920,
    10_158_820,
    9_722_720,
    9_286_620,
    9_299_248,
    10_003_112,
    9_809_520,
    9_615_928,
    9_422_336,
    9_022_524,
    8_828_932,
    8_392_832,
    8_647_968,
    8_454_376,
    8_054_564,
    8_067_192,
)


@dataclass(frozen=True)
class TypeCountMetrics:
    """Exact local recovery and conservative pair-mass data for one vector."""

    counts: tuple[int, ...]
    good_count: int
    best_non_good_count: int
    worse_type_count: int
    local_recovery: int
    local_recovery_loss: int
    cell_incidences: tuple[int, int, int, int]
    cellwise_pair_mass_floor: int
    full_system_pair_mass_floor: int
    outside_pair_mass_floor: int
    generic_pair_penalty_floor: int
    pair_mass_feasible: bool


@dataclass(frozen=True)
class ComponentPenaltyCase:
    """A connected-component case in the bounded label-assignment layer."""

    component_count: int
    threshold_one_rank: int
    distinct_pair_capacity: int
    repeated_overlap_forced: bool
    pair_penalty_floor: int


@dataclass(frozen=True)
class DangerousVectorResult:
    """Tightened result for one vector left open by the prior envelope."""

    label: str
    type_counts: tuple[tuple[tuple[int, int, int, int], int], ...]
    local_recovery_loss: int
    outside_pair_mass_floor: int
    component_cases: tuple[ComponentPenaltyCase, ...]
    mandatory_outside_pair_penalty: int
    total_recovery_reduction: int
    r4_bound: int
    realizable: bool


@dataclass(frozen=True)
class R4RealizabilityCertificate:
    """Compact outcome of the exact count-vector and assignment bounds."""

    total_type_count_vector_space: int
    type_count_vector_count: int
    pruned_lower_good_vector_count: int
    dangerous_vector_count: int
    realizable_dangerous_vector_count: int
    dangerous_vectors: tuple[DangerousVectorResult, ...]
    mandatory_outside_pair_penalty: int
    r4_bound: int
    r4_status: str
    family_a_recomputed_bound: int
    family_a_bottleneck_r: int
    remaining_gap: int
    analytic_precompute_wall_seconds: float


def _rank_floor(edge_count: int) -> int:
    """Minimum graphic-matroid rank that can contain ``edge_count`` edges."""

    if edge_count < 0:
        raise ValueError("edge count must be nonnegative")
    rank = 0
    while comb(rank + 1, 2) < edge_count:
        rank += 1
    return rank


def count_vector_space_size(type_count: int, ticket_count: int) -> int:
    """Count nonnegative type-count vectors with a fixed ticket total."""

    if type_count < 1 or ticket_count < 0:
        raise ValueError("type_count must be positive and ticket_count nonnegative")
    return comb(type_count + ticket_count - 1, ticket_count)


def enumerate_count_vectors_with_good_floor(
    type_count: int,
    ticket_count: int,
    good_type_index: int,
    minimum_good_count: int,
) -> tuple[tuple[int, ...], ...]:
    """Enumerate every vector with at least ``minimum_good_count`` good types.

    The other coordinates are generated as multisets, so this is a direct
    count-vector enumeration rather than an ordered ticket-sequence search.
    """

    if not 0 <= good_type_index < type_count:
        raise ValueError("good type index is outside the type table")
    if not 0 <= minimum_good_count <= ticket_count:
        raise ValueError("minimum_good_count must be within the ticket total")

    other_types = tuple(index for index in range(type_count) if index != good_type_index)
    vectors: list[tuple[int, ...]] = []
    for good_count in range(minimum_good_count, ticket_count + 1):
        remaining = ticket_count - good_count
        for selected in combinations_with_replacement(other_types, remaining):
            counts = [0] * type_count
            counts[good_type_index] = good_count
            for index in selected:
                counts[index] += 1
            vectors.append(tuple(counts))
    return tuple(vectors)


@cache
def exact_global_pair_residual_floors() -> tuple[int, ...]:
    """Exhaust all 32-by-32 profile pairs and return overlap-monotone floors."""

    profiles = anchor_incidence_profiles()
    exact_minima: list[int | None] = [None] * (ANCHOR_OVERLAP + 1)
    for left in profiles:
        for right in profiles:
            values = minimum_residual_pair_counts_by_overlap(left.signature, right.signature)
            for overlap, value in enumerate(values):
                prior = exact_minima[overlap]
                if value is not None and (prior is None or value < prior):
                    exact_minima[overlap] = value

    exact = tuple(value for value in exact_minima if value is not None)
    if len(exact) != len(exact_minima):
        raise AssertionError("a feasible overlap class has no profile-pair floor")
    floors = tuple(min(exact[overlap:]) for overlap in range(len(exact)))
    if floors != EXPECTED_GLOBAL_PAIR_RESIDUAL_FLOORS:
        raise AssertionError("the all-profile residual-pair floor table changed")
    return floors


def _generic_pair_penalty_floor(
    outside_pair_mass_floor: int,
    pair_floors: tuple[int, ...],
    outside_ticket_count: int = OUTSIDE_TICKET_COUNT,
) -> tuple[int, bool]:
    """Use mass, overlap cap four, and a one-threshold forest rank bound."""

    maximum_mass = 4 * comb(outside_ticket_count, 2)
    if outside_pair_mass_floor > maximum_mass:
        return 0, False
    if outside_ticket_count < 2:
        return 0, True

    overlap_edge_floor = (outside_pair_mass_floor + 3) // 4
    rank = min(outside_ticket_count - 1, _rank_floor(overlap_edge_floor))
    pair_zero = pair_floors[0]
    pair_positive_overlap = pair_floors[1]
    penalty = (outside_ticket_count - 1) * pair_zero + (
        pair_positive_overlap - pair_zero
    ) * rank
    return penalty, True


def type_count_metrics(
    counts: tuple[int, ...],
    profiles: tuple[AnchorIncidenceProfile, ...] | None = None,
    global_pair_floors: tuple[int, ...] | None = None,
) -> TypeCountMetrics:
    """Compute exact local recovery and cellwise/full-system overlap floors."""

    selected_profiles = anchor_incidence_profiles() if profiles is None else profiles
    if len(counts) != len(selected_profiles) or any(count < 0 for count in counts):
        raise ValueError("count vector must match the profile table and be nonnegative")
    if sum(counts) != OUTSIDE_TICKET_COUNT:
        raise ValueError("count vector must total 18 outside tickets")

    good_profiles = tuple(
        profile
        for profile in selected_profiles
        if profile.shared == profile.a_only == profile.b_only == 0
    )
    if len(good_profiles) != 1:
        raise AssertionError("the all-outside profile is not unique")
    good_profile = good_profiles[0]
    good_index = selected_profiles.index(good_profile)
    best_non_good_net = max(
        profile.net_recovery for profile in selected_profiles if profile != good_profile
    )
    best_indices = tuple(
        index
        for index, profile in enumerate(selected_profiles)
        if profile.net_recovery == best_non_good_net
    )
    good_count = counts[good_index]
    best_count = sum(counts[index] for index in best_indices)
    local_recovery = sum(
        count * profile.net_recovery
        for count, profile in zip(counts, selected_profiles, strict=True)
    )
    local_loss = OUTSIDE_TICKET_COUNT * good_profile.net_recovery - local_recovery

    cell_totals = [0, 0, 0, 0]
    for count, profile in zip(counts, selected_profiles, strict=True):
        for cell, incidence in enumerate(profile.signature):
            cell_totals[cell] += count * incidence
    cell_incidences = (cell_totals[0], cell_totals[1], cell_totals[2], cell_totals[3])
    capacities = (
        ANCHOR_SHARED_CAPACITY,
        ANCHOR_A_ONLY_CAPACITY,
        ANCHOR_B_ONLY_CAPACITY,
        OUTSIDE_LABEL_CAPACITY,
    )
    cellwise_mass = sum(
        minimum_label_pair_mass(incidences, capacity)
        for incidences, capacity in zip(cell_incidences, capacities, strict=True)
    )

    total_positions = TICKET_COUNT * DRAW_SIZE
    full_pair_mass = minimum_label_pair_mass(total_positions, POOL_SIZE)
    shared, a_only, b_only, _ = cell_incidences
    fixed_anchor_cross_pairs = 2 * shared + a_only + b_only
    full_system_remainder = max(
        0, full_pair_mass - ANCHOR_OVERLAP - fixed_anchor_cross_pairs
    )
    outside_pair_mass = max(cellwise_mass, full_system_remainder)

    pair_floors = (
        exact_global_pair_residual_floors()
        if global_pair_floors is None
        else global_pair_floors
    )
    penalty, pair_mass_feasible = _generic_pair_penalty_floor(
        outside_pair_mass, pair_floors
    )
    return TypeCountMetrics(
        counts=counts,
        good_count=good_count,
        best_non_good_count=best_count,
        worse_type_count=OUTSIDE_TICKET_COUNT - good_count - best_count,
        local_recovery=local_recovery,
        local_recovery_loss=local_loss,
        cell_incidences=cell_incidences,
        cellwise_pair_mass_floor=cellwise_mass,
        full_system_pair_mass_floor=full_system_remainder,
        outside_pair_mass_floor=outside_pair_mass,
        generic_pair_penalty_floor=penalty,
        pair_mass_feasible=pair_mass_feasible,
    )


@cache
def _integer_partitions(total: int, minimum_part: int = 1) -> tuple[tuple[int, ...], ...]:
    """Return nondecreasing integer partitions of ``total``."""

    if total == 0:
        return ((),)
    return tuple(
        (part, *tail)
        for part in range(minimum_part, total + 1)
        for tail in _integer_partitions(total - part, part)
    )


def _component_label_floor(component_size: int, has_special_ticket: bool) -> int:
    """Minimum outside labels in a component under ticket intersections <=4."""

    if not has_special_ticket:
        return DRAW_SIZE if component_size == 1 else 2 * DRAW_SIZE - 4
    if component_size == 1:
        return DRAW_SIZE - 1
    if component_size == 2:
        return DRAW_SIZE + (DRAW_SIZE - 1) - 4
    return 2 * DRAW_SIZE - 4


def maximum_overlap_components(
    outside_ticket_count: int,
    outside_label_capacity: int = OUTSIDE_LABEL_CAPACITY,
    special_outside_degree: int | None = None,
) -> int:
    """Bound connected components using disjoint label sets per component."""

    if outside_ticket_count < 1:
        raise ValueError("outside_ticket_count must be positive")
    maximum = 0
    has_special = special_outside_degree is not None
    if has_special and special_outside_degree != DRAW_SIZE - 1:
        raise ValueError("the supported best non-good type has five outside labels")

    for sizes in _integer_partitions(outside_ticket_count):
        if not has_special:
            if sum(_component_label_floor(size, False) for size in sizes) <= outside_label_capacity:
                maximum = max(maximum, len(sizes))
            continue

        for index, size in enumerate(sizes):
            if index > 0 and size == sizes[index - 1]:
                continue
            required = sum(
                _component_label_floor(part, part_index == index)
                for part_index, part in enumerate(sizes)
            )
            if required <= outside_label_capacity:
                maximum = max(maximum, len(sizes))
    return maximum


def _extremal_component_pair_mass(
    outside_ticket_count: int,
    component_count: int,
    has_special_ticket: bool,
    label_capacity: int = OUTSIDE_LABEL_CAPACITY,
) -> int:
    """Minimum mass in the unique largest-component partition for a tie."""

    largest = outside_ticket_count - component_count + 1
    special_placements = (True,) if not has_special_ticket else (True, False)
    masses: list[int] = []
    for special_in_largest in special_placements:
        if not has_special_ticket and not special_in_largest:
            continue
        if has_special_ticket and not special_in_largest and component_count == 1:
            continue
        singleton_count = component_count - 1
        singleton_labels = 6 * singleton_count
        largest_incidences = 6 * largest
        if has_special_ticket:
            if special_in_largest:
                largest_incidences -= 1
            else:
                singleton_labels -= 1
        remaining_labels = label_capacity - singleton_labels
        if remaining_labels < 1:
            continue
        masses.append(minimum_label_pair_mass(largest_incidences, remaining_labels))
    if not masses:
        return 0
    return min(masses)


def component_assignment_penalty_cases(
    outside_ticket_count: int,
    outside_incidences: int,
    has_special_ticket: bool,
    pair_floors: tuple[int, ...] = EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS,
) -> tuple[ComponentPenaltyCase, ...]:
    """Bound the forest penalty using actual label-component realizability.

    A connected component of the ticket-overlap graph contributes exactly
    ``size - 1`` to the rank at threshold one. For threshold two, one forced
    repeated-overlap pair contributes at least rank one. Component label sets
    are disjoint, and the outside-label incidence mass is balanced over the
    actual 41-label capacity.
    """

    if outside_ticket_count < 2 or outside_incidences < 0:
        raise ValueError("at least two tickets and nonnegative incidences are required")
    if len(pair_floors) != ANCHOR_OVERLAP + 1:
        raise ValueError("pair floor table must cover overlap thresholds zero through four")

    component_limit = maximum_overlap_components(
        outside_ticket_count,
        OUTSIDE_LABEL_CAPACITY,
        DRAW_SIZE - 1 if has_special_ticket else None,
    )
    if component_limit == 0:
        raise AssertionError("no component assignment fits the outside-label capacity")

    total_pair_mass = minimum_label_pair_mass(outside_incidences, OUTSIDE_LABEL_CAPACITY)
    cases: list[ComponentPenaltyCase] = []
    pair_zero = pair_floors[0]
    delta_one = pair_floors[1] - pair_floors[0]
    delta_two = pair_floors[2] - pair_floors[1]

    for component_count in range(1, component_limit + 1):
        distinct_pair_capacity = comb(outside_ticket_count - component_count + 1, 2)
        repeated_overlap_forced = total_pair_mass > distinct_pair_capacity
        if total_pair_mass == distinct_pair_capacity:
            repeated_overlap_forced = (
                _extremal_component_pair_mass(
                    outside_ticket_count,
                    component_count,
                    has_special_ticket,
                )
                > distinct_pair_capacity
            )

        threshold_one_rank = outside_ticket_count - component_count
        penalty = (outside_ticket_count - 1) * pair_zero + delta_one * threshold_one_rank
        if repeated_overlap_forced:
            penalty += delta_two
        cases.append(
            ComponentPenaltyCase(
                component_count=component_count,
                threshold_one_rank=threshold_one_rank,
                distinct_pair_capacity=distinct_pair_capacity,
                repeated_overlap_forced=repeated_overlap_forced,
                pair_penalty_floor=penalty,
            )
        )
    return tuple(cases)


def component_assignment_penalty_floor(
    outside_ticket_count: int,
    outside_incidences: int,
    has_special_ticket: bool,
) -> tuple[int, tuple[ComponentPenaltyCase, ...]]:
    """Return the minimum component-case penalty over all allowed counts."""

    cases = component_assignment_penalty_cases(
        outside_ticket_count,
        outside_incidences,
        has_special_ticket,
    )
    return min(case.pair_penalty_floor for case in cases), cases


def _cyclic_assignment_witness(
    counts: tuple[int, ...], profiles: tuple[AnchorIncidenceProfile, ...]
) -> bool:
    """Constructively realize a dangerous type vector on abstract labels."""

    if sum(counts) != OUTSIDE_TICKET_COUNT or len(counts) != len(profiles):
        return False
    anchor_a = frozenset((0, 1, 2, 3, 4, 5))
    anchor_b = frozenset((0, 1, 2, 3, 6, 7))
    shared = anchor_a & anchor_b
    a_only = anchor_a - anchor_b
    b_only = anchor_b - anchor_a
    outside_labels = tuple(range(8, POOL_SIZE))
    good_index = next(
        index
        for index, profile in enumerate(profiles)
        if profile.shared == profile.a_only == profile.b_only == 0
    )
    best_non_good_net = max(
        profile.net_recovery
        for index, profile in enumerate(profiles)
        if index != good_index
    )
    best_indices = tuple(
        index
        for index, profile in enumerate(profiles)
        if index != good_index and profile.net_recovery == best_non_good_net
    )
    expected_types = [
        index
        for index, count in enumerate(counts)
        for _ in range(count)
    ]
    if any(index not in (good_index, *best_indices) for index in expected_types):
        return False

    tickets: list[frozenset[int]] = []
    for ticket_index, profile_index in enumerate(expected_types):
        row = tuple(
            outside_labels[(2 * ticket_index + offset) % OUTSIDE_LABEL_CAPACITY]
            for offset in range(DRAW_SIZE)
        )
        profile = profiles[profile_index]
        if profile_index == good_index:
            ticket = frozenset(row)
        else:
            exclusive_label = next(iter(a_only if profile.a_only else b_only))
            ticket = frozenset((*row[: DRAW_SIZE - 1], exclusive_label))
        tickets.append(ticket)

    portfolio = (anchor_a, anchor_b, *tickets)
    if any(len(ticket) != DRAW_SIZE for ticket in portfolio):
        return False
    if any(
        len(left & right) > ANCHOR_OVERLAP
        for left_index, left in enumerate(portfolio)
        for right in portfolio[left_index + 1 :]
    ):
        return False

    observed = [0] * len(profiles)
    for ticket in tickets:
        signature = (
            len(ticket & shared),
            len(ticket & a_only),
            len(ticket & b_only),
            len(ticket & frozenset(outside_labels)),
        )
        try:
            observed[tuple(profile.signature for profile in profiles).index(signature)] += 1
        except ValueError:
            return False
    return tuple(observed) == counts


def analyze_r4_realizability() -> R4RealizabilityCertificate:
    """Run the exact high-good vector census and bounded assignment layer."""

    started = monotonic()
    profiles = anchor_incidence_profiles()
    if len(profiles) != 32 or pair_intersection_table() != EXPECTED_PAIR_COUNTS:
        raise AssertionError("the pinned r4 profile or official pair table changed")
    good_indices = tuple(
        index
        for index, profile in enumerate(profiles)
        if profile.shared == profile.a_only == profile.b_only == 0
    )
    if len(good_indices) != 1:
        raise AssertionError("the fully outside ticket type is not unique")
    good_index = good_indices[0]
    good_net = profiles[good_index].net_recovery
    non_good_net = tuple(
        profile.net_recovery for index, profile in enumerate(profiles) if index != good_index
    )
    best_non_good_net = max(non_good_net)
    best_non_good_indices = tuple(
        index
        for index, profile in enumerate(profiles)
        if index != good_index and profile.net_recovery == best_non_good_net
    )
    second_best_net = max(value for value in non_good_net if value < best_non_good_net)
    if len(best_non_good_indices) != 2 or good_net - second_best_net != 747_320:
        raise AssertionError("the certified top-profile recovery gaps changed")

    pair_floors = exact_global_pair_residual_floors()
    if pair_floors != EXPECTED_GLOBAL_PAIR_RESIDUAL_FLOORS:
        raise AssertionError("the all-profile pair floor was not reproduced")

    vectors = enumerate_count_vectors_with_good_floor(
        len(profiles), OUTSIDE_TICKET_COUNT, good_index, 14
    )
    expected_vector_count = sum(
        comb(len(profiles) - 1 + OUTSIDE_TICKET_COUNT - good_count - 1,
             OUTSIDE_TICKET_COUNT - good_count)
        for good_count in range(14, OUTSIDE_TICKET_COUNT + 1)
    )
    if len(vectors) != expected_vector_count or expected_vector_count != 52_360:
        raise AssertionError("the finite high-good count-vector census changed")

    metrics_by_vector: list[TypeCountMetrics] = []
    for vector in vectors:
        metrics = type_count_metrics(vector, profiles, pair_floors)
        if sum(vector) != OUTSIDE_TICKET_COUNT:
            raise AssertionError("the type-count generator emitted a bad ticket total")
        metrics_by_vector.append(metrics)

    all_good_recovery = OUTSIDE_TICKET_COUNT * good_net
    uncorrected_bound = (
        TICKET_COUNT * EXPECTED_PAIR_COUNTS[DRAW_SIZE]
        - EXPECTED_PAIR_COUNTS[ANCHOR_OVERLAP]
        + all_good_recovery
    )
    if uncorrected_bound != 362_587_008:
        raise AssertionError("the exact all-good r4 baseline changed")

    dangerous_results: list[DangerousVectorResult] = []
    target_reduction = PRIOR_MINIMUM_REDUCTION_BY_GOOD_COUNT[18]
    for metrics in metrics_by_vector:
        if metrics.good_count <= 16:
            if PRIOR_MINIMUM_REDUCTION_BY_GOOD_COUNT[metrics.good_count] <= target_reduction:
                raise AssertionError("a lower-good class unexpectedly reaches the danger cutoff")
            continue

        if metrics.good_count == 17:
            if metrics.best_non_good_count == 0:
                # The 17 good tickets alone have 102 outside incidences. Their
                # exact balanced mass is 81; the old active-type floor is 7,513,464.
                active_mass = minimum_label_pair_mass(17 * DRAW_SIZE, OUTSIDE_LABEL_CAPACITY)
                active_penalty = minimum_weighted_forest_census(
                    17, active_mass, EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS
                ).lower_bound_penalty
                prior_bound = active_penalty + good_net - second_best_net
                if prior_bound != 8_260_784 or prior_bound <= target_reduction:
                    raise AssertionError("the remaining 17-good vector class is not safely pruned")
                continue
            if metrics.best_non_good_count != 1 or metrics.worse_type_count != 0:
                raise AssertionError("an unclassified 17-good vector entered the dangerous layer")
            label = "17_GOOD_PLUS_ONE_BEST_NON_GOOD"
        elif metrics.good_count == 18:
            if metrics.best_non_good_count or metrics.worse_type_count:
                raise AssertionError("the 18-good vector contains a non-good profile")
            label = "18_GOOD"
        else:
            raise AssertionError("the high-good census emitted an unexpected category")

        special = metrics.best_non_good_count == 1
        outside_incidences = metrics.cell_incidences[3]
        pair_penalty, component_cases = component_assignment_penalty_floor(
            OUTSIDE_TICKET_COUNT,
            outside_incidences,
            special,
        )
        realizable = _cyclic_assignment_witness(metrics.counts, profiles)
        if not realizable:
            raise AssertionError("a dangerous count vector failed its bounded label witness")
        reduction = metrics.local_recovery_loss + pair_penalty
        dangerous_results.append(
            DangerousVectorResult(
                label=label,
                type_counts=tuple(
                    (profile.signature, count)
                    for profile, count in zip(profiles, metrics.counts, strict=True)
                    if count
                ),
                local_recovery_loss=metrics.local_recovery_loss,
                outside_pair_mass_floor=metrics.outside_pair_mass_floor,
                component_cases=component_cases,
                mandatory_outside_pair_penalty=pair_penalty,
                total_recovery_reduction=reduction,
                r4_bound=uncorrected_bound - reduction,
                realizable=realizable,
            )
        )

    if len(dangerous_results) != 3:
        raise AssertionError("the danger filter must leave exactly three count vectors")
    if sum(result.realizable for result in dangerous_results) != 3:
        raise AssertionError("not every dangerous type vector has an assignment witness")

    mandatory_penalty = min(
        result.mandatory_outside_pair_penalty for result in dangerous_results
    )
    minimum_reduction = min(
        min(PRIOR_MINIMUM_REDUCTION_BY_GOOD_COUNT[:17]),
        8_260_784,
        *(result.total_recovery_reduction for result in dangerous_results),
    )
    if minimum_reduction != 8_067_192:
        raise AssertionError("the tightened r4 reduction changed")
    r4_bound = uncorrected_bound - minimum_reduction
    family_a_candidates = (
        CURRENT_R3_BOUND,
        r4_bound,
        CURRENT_R5_BOUND,
        CURRENT_R6_BOUND,
    )
    family_a_bound = max(family_a_candidates)
    family_a_bottleneck = family_a_candidates.index(family_a_bound) + 3
    previous_tightening = PREVIOUS_R4_BOUND - r4_bound
    if r4_bound >= PREVIOUS_R4_BOUND or previous_tightening != 12_628:
        raise AssertionError("the certified r4 bound did not strictly improve")

    total_vector_space = count_vector_space_size(len(profiles), OUTSIDE_TICKET_COUNT)
    return R4RealizabilityCertificate(
        total_type_count_vector_space=total_vector_space,
        type_count_vector_count=len(vectors),
        pruned_lower_good_vector_count=total_vector_space - len(vectors),
        dangerous_vector_count=len(dangerous_results),
        realizable_dangerous_vector_count=sum(
            result.realizable for result in dangerous_results
        ),
        dangerous_vectors=tuple(dangerous_results),
        mandatory_outside_pair_penalty=mandatory_penalty,
        r4_bound=r4_bound,
        r4_status="TIGHTENED_OPEN_SUCCESS_B",
        family_a_recomputed_bound=family_a_bound,
        family_a_bottleneck_r=family_a_bottleneck,
        remaining_gap=family_a_bound - INCUMBENT,
        analytic_precompute_wall_seconds=monotonic() - started,
    )


__all__ = [
    "EXPECTED_GLOBAL_PAIR_RESIDUAL_FLOORS",
    "PRIOR_MINIMUM_REDUCTION_BY_GOOD_COUNT",
    "ComponentPenaltyCase",
    "DangerousVectorResult",
    "R4RealizabilityCertificate",
    "TypeCountMetrics",
    "analyze_r4_realizability",
    "component_assignment_penalty_cases",
    "component_assignment_penalty_floor",
    "count_vector_space_size",
    "enumerate_count_vectors_with_good_floor",
    "exact_global_pair_residual_floors",
    "maximum_overlap_components",
    "type_count_metrics",
]
