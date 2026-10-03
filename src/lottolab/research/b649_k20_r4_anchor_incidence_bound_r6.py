"""Exact r=4 anchor-incidence and outside-overlap bound for K20.

This module is self-contained. It counts official 6/49 any-prize outcomes,
enumerates all r=4 anchor-incidence types, and applies an exact finite
weighted-forest relaxation to the good and best non-good outside-ticket types.
It does not construct portfolios or call a solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from itertools import pairwise, product
from math import comb

type Signature = tuple[int, int, int, int]

BASE_HEAD = "92f88afb2f98073bdb9612f1e002e2c1a20cc350"
BASE_TREE = "a9e3108ff1f32c8718db22c4115a81b661249e33"
TASK_BRANCH = "codex/b649-k20-r4-anchor-incidence-bound-r6"
POOL_SIZE = 49
DRAW_SIZE = 6
OUTRIGHT_MATCHES = 3
TICKET_COUNT = 20
OUTSIDE_TICKET_COUNT = TICKET_COUNT - 2
ANCHOR_OVERLAP = 4
OUTSIDE_LABEL_CAPACITY = POOL_SIZE - (2 * DRAW_SIZE - ANCHOR_OVERLAP)

INCUMBENT = 313_239_661
CURRENT_R3_BOUND = 351_926_868
CURRENT_R4_BOUND = 354_779_928
CURRENT_R5_BOUND = 350_778_728
CURRENT_R6_BOUND = 343_869_728

EXPECTED_PAIR_COUNTS = (
    107_800,
    574_000,
    1_695_988,
    3_469_942,
    6_224_512,
    10_776_332,
    18_611_432,
)
EXPECTED_SINGLE_TICKET_OUTCOMES = 18_611_432
EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS = (
    105_000,
    553_728,
    1_638_686,
    3_354_015,
    6_004_446,
)


@dataclass(frozen=True)
class AnchorIncidenceProfile:
    """Exact local event contribution and slot use for one ticket type."""

    shared: int
    a_only: int
    b_only: int
    outside: int
    overlap_with_a: int
    overlap_with_b: int
    triple_recovery: int
    pair_recovery_cost: int
    net_recovery: int

    @property
    def signature(self) -> Signature:
        return (self.shared, self.a_only, self.b_only, self.outside)


@dataclass(frozen=True)
class WeightedForestCensus:
    """Minimum forest-weight relaxation for fixed vertex and overlap counts."""

    active_ticket_count: int
    minimum_pair_mass: int
    threshold_pair_counts: tuple[int, ...]
    threshold_rank_floors: tuple[int, ...]
    lower_bound_penalty: int


@dataclass(frozen=True)
class TradeoffCase:
    """Local type loss plus the certified active-ticket forest correction."""

    good_ticket_count: int
    best_non_good_count: int
    worse_type_count: int
    active_ticket_count: int
    outside_label_pair_mass: int
    anchor_exclusive_pair_mass: int
    minimum_pair_mass: int
    threshold_pair_counts: tuple[int, ...]
    threshold_rank_floors: tuple[int, ...]
    mandatory_outside_pair_penalty: int
    local_recovery_loss: int
    total_recovery_reduction: int


@dataclass(frozen=True)
class R4Tradeoff:
    """Exact 0..18 good-ticket and best-non-good tradeoff certificate."""

    single_ticket_outcomes: int
    pair_counts: tuple[int, ...]
    good_local_net_recovery: int
    maximum_non_good_net_recovery: int
    second_best_non_good_net_recovery: int
    active_pair_residual_floors: tuple[int, ...]
    cases: tuple[TradeoffCase, ...]
    best_by_good_count: tuple[TradeoffCase, ...]
    minimizing_case: TradeoffCase
    uncorrected_all_good_bound: int
    guaranteed_recovery_reduction: int
    r4_bound: int
    family_a_bound: int
    family_a_bottleneck_r: int
    remaining_gap: int


def _validate_game(pool_size: int, draw_size: int, outright_matches: int) -> None:
    if pool_size < 1 or not 0 <= draw_size <= pool_size:
        raise ValueError("draw size must be within the pool")
    if not 1 <= outright_matches <= draw_size:
        raise ValueError("outright matches must be within 1..draw_size")


@cache
def _draw_allocations(
    capacities: tuple[int, ...], draw_size: int
) -> tuple[tuple[int, ...], ...]:
    """Enumerate bounded draw-count vectors over membership cells."""

    allocation = [0] * len(capacities)
    result: list[tuple[int, ...]] = []

    def visit(index: int, remaining: int) -> None:
        if index == len(capacities) - 1:
            if 0 <= remaining <= capacities[index]:
                allocation[index] = remaining
                result.append(tuple(allocation))
            return
        for count in range(min(capacities[index], remaining) + 1):
            allocation[index] = count
            visit(index + 1, remaining - count)

    visit(0, draw_size)
    return tuple(result)


@cache
def exact_joint_win_count(
    capacities: tuple[int, ...],
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Count outcomes where every ticket in a membership-cell profile wins.

    Capacities are indexed by ticket-membership mask. An outcome is a
    draw_size-label main draw plus one special label outside that draw. A
    ticket wins with at least outright_matches main-draw hits, or with one
    fewer hit when the special label belongs to it.
    """

    if len(capacities) < 2 or len(capacities) & (len(capacities) - 1):
        raise ValueError("membership cells must have power-of-two length")
    if any(capacity < 0 for capacity in capacities):
        raise ValueError("membership-cell capacities must be nonnegative")
    pool_size = sum(capacities)
    _validate_game(pool_size, draw_size, outright_matches)
    ticket_count = len(capacities).bit_length() - 1
    total = 0

    for allocation in _draw_allocations(capacities, draw_size):
        draw_ways = 1
        for capacity, chosen in zip(capacities, allocation, strict=True):
            draw_ways *= comb(capacity, chosen)

        hits = tuple(
            sum(
                allocation[mask]
                for mask in range(1, len(capacities))
                if mask & (1 << ticket)
            )
            for ticket in range(ticket_count)
        )
        rescue_threshold = outright_matches - 1
        if min(hits) < rescue_threshold:
            continue

        rescued = tuple(
            ticket for ticket, count in enumerate(hits) if count == rescue_threshold
        )
        if rescued:
            required_mask = sum(1 << ticket for ticket in rescued)
            special_ways = sum(
                capacities[mask] - allocation[mask]
                for mask in range(len(capacities))
                if mask & required_mask == required_mask
            )
        else:
            special_ways = pool_size - draw_size
        total += draw_ways * special_ways

    return total


@cache
def pair_intersection_count(
    overlap: int,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Return the exact joint any-prize count for two tickets."""

    _validate_game(pool_size, draw_size, outright_matches)
    if not 0 <= overlap <= draw_size:
        raise ValueError("overlap must be within 0..draw_size")
    outside = pool_size - (2 * draw_size - overlap)
    if outside < 0:
        raise ValueError("the requested pair overlap cannot fit in the pool")
    capacities = (outside, draw_size - overlap, draw_size - overlap, overlap)
    return exact_joint_win_count(capacities, draw_size, outright_matches)


@cache
def pair_intersection_table(
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> tuple[int, ...]:
    """Return exact pair-event intersections for overlaps 0..draw_size."""

    return tuple(
        pair_intersection_count(overlap, pool_size, draw_size, outright_matches)
        for overlap in range(draw_size + 1)
    )


@cache
def triple_intersection_count(
    pair_overlaps: tuple[int, int, int],
    triple_common: int,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Count joint wins for a feasible three-ticket Venn profile.

    Pair overlaps are ordered as AB, AC, BC.
    """

    _validate_game(pool_size, draw_size, outright_matches)
    if len(pair_overlaps) != 3:
        raise ValueError("three pair overlaps are required")
    ab, ac, bc = pair_overlaps
    if any(not 0 <= overlap <= draw_size for overlap in pair_overlaps):
        raise ValueError("pair overlaps must be within 0..draw_size")
    if not 0 <= triple_common <= min(pair_overlaps):
        raise ValueError("triple common count must fit every pair overlap")

    capacities = [0] * 8
    capacities[7] = triple_common
    capacities[3] = ab - triple_common
    capacities[5] = ac - triple_common
    capacities[6] = bc - triple_common
    capacities[1] = draw_size - ab - ac + triple_common
    capacities[2] = draw_size - ab - bc + triple_common
    capacities[4] = draw_size - ac - bc + triple_common
    if min(capacities[1:]) < 0:
        raise ValueError("the requested three-ticket Venn profile is impossible")
    capacities[0] = pool_size - sum(capacities[1:])
    if capacities[0] < 0:
        raise ValueError("the requested three-ticket Venn profile cannot fit")
    return exact_joint_win_count(tuple(capacities), draw_size, outright_matches)


def good_pair_anchor_four_way_count(
    anchor_overlap: int,
    good_ticket_overlap: int,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Count joint wins of A,B,C,D for disjoint-anchor C,D with C∩D=d."""

    _validate_game(pool_size, draw_size, outright_matches)
    if not 0 <= anchor_overlap <= draw_size:
        raise ValueError("anchor overlap must be within 0..draw_size")
    if not 0 <= good_ticket_overlap <= draw_size:
        raise ValueError("good-ticket overlap must be within 0..draw_size")

    capacities = [0] * 16
    capacities[3] = anchor_overlap
    capacities[1] = draw_size - anchor_overlap
    capacities[2] = draw_size - anchor_overlap
    capacities[12] = good_ticket_overlap
    capacities[4] = draw_size - good_ticket_overlap
    capacities[8] = draw_size - good_ticket_overlap
    capacities[0] = pool_size - sum(capacities[1:])
    if capacities[0] < 0:
        raise ValueError("the requested four-ticket profile cannot fit")
    return exact_joint_win_count(tuple(capacities), draw_size, outright_matches)


def legal_anchor_incidence_signatures(
    anchor_overlap: int,
    draw_size: int,
    pool_size: int,
) -> tuple[Signature, ...]:
    """Enumerate legal shared/A-only/B-only/outside ticket slot counts."""

    if pool_size < 1 or not 0 <= draw_size <= pool_size:
        raise ValueError("draw size must be within the pool")
    if not 0 <= anchor_overlap <= draw_size:
        raise ValueError("anchor overlap must be within 0..draw_size")
    outside_capacity = pool_size - (2 * draw_size - anchor_overlap)
    if outside_capacity < 0:
        raise ValueError("the anchor pair cannot fit in the pool")
    exclusive_capacity = draw_size - anchor_overlap

    signatures: list[Signature] = []
    for shared in range(anchor_overlap + 1):
        for a_only in range(exclusive_capacity + 1):
            if shared + a_only > anchor_overlap:
                continue
            for b_only in range(exclusive_capacity + 1):
                if shared + b_only > anchor_overlap:
                    continue
                outside = draw_size - shared - a_only - b_only
                if 0 <= outside <= outside_capacity:
                    signatures.append((shared, a_only, b_only, outside))
    return tuple(signatures)


@cache
def anchor_incidence_profiles(
    anchor_overlap: int = ANCHOR_OVERLAP,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> tuple[AnchorIncidenceProfile, ...]:
    """Compute exact local pair/triple contributions for every legal type."""

    pair_counts = pair_intersection_table(pool_size, draw_size, outright_matches)
    profiles: list[AnchorIncidenceProfile] = []
    for shared, a_only, b_only, outside in legal_anchor_incidence_signatures(
        anchor_overlap, draw_size, pool_size
    ):
        overlap_a = shared + a_only
        overlap_b = shared + b_only
        triple = triple_intersection_count(
            (anchor_overlap, overlap_a, overlap_b),
            shared,
            pool_size,
            draw_size,
            outright_matches,
        )
        pair_cost = pair_counts[overlap_a] + pair_counts[overlap_b]
        profiles.append(
            AnchorIncidenceProfile(
                shared=shared,
                a_only=a_only,
                b_only=b_only,
                outside=outside,
                overlap_with_a=overlap_a,
                overlap_with_b=overlap_b,
                triple_recovery=triple,
                pair_recovery_cost=pair_cost,
                net_recovery=triple - pair_cost,
            )
        )
    return tuple(profiles)


def _four_ticket_capacities_for_types(
    first: Signature,
    second: Signature,
    shared_by_cell: tuple[int, int, int, int],
    anchor_overlap: int,
    pool_size: int,
    draw_size: int,
) -> tuple[int, ...]:
    """Build A,B,C,D membership cells for two outside ticket types."""

    shared_capacity = anchor_overlap
    exclusive_capacity = draw_size - anchor_overlap
    outside_capacity = pool_size - (2 * draw_size - anchor_overlap)
    cell_capacities = (
        shared_capacity,
        exclusive_capacity,
        exclusive_capacity,
        outside_capacity,
    )
    anchor_masks = (3, 1, 2, 0)
    capacities = [0] * 16

    for anchor_mask, cell_size, left, right, common in zip(
        anchor_masks, cell_capacities, first, second, shared_by_cell, strict=True
    ):
        if not 0 <= left <= cell_size or not 0 <= right <= cell_size:
            raise ValueError("ticket type exceeds an anchor-incidence cell")
        if not max(0, left + right - cell_size) <= common <= min(left, right):
            raise ValueError("cell intersection is infeasible")
        capacities[anchor_mask | 12] += common
        capacities[anchor_mask | 4] += left - common
        capacities[anchor_mask | 8] += right - common
        capacities[anchor_mask] += cell_size - left - right + common

    return tuple(capacities)


def exact_residual_pair_intersection(
    first: Signature,
    second: Signature,
    shared_by_cell: tuple[int, int, int, int],
    anchor_overlap: int = ANCHOR_OVERLAP,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Count R_C∩R_D exactly for one specified cell-overlap profile."""

    capacities = _four_ticket_capacities_for_types(
        first, second, shared_by_cell, anchor_overlap, pool_size, draw_size
    )
    total_overlap = sum(shared_by_cell)
    if total_overlap > anchor_overlap:
        raise ValueError("outside tickets exceed the r_max overlap")
    common_shared, common_a, common_b, _ = shared_by_cell

    pair_cd = pair_intersection_count(
        total_overlap, pool_size, draw_size, outright_matches
    )
    triple_acd = triple_intersection_count(
        (
            first[0] + first[1],
            second[0] + second[1],
            total_overlap,
        ),
        common_shared + common_a,
        pool_size,
        draw_size,
        outright_matches,
    )
    triple_bcd = triple_intersection_count(
        (
            first[0] + first[2],
            second[0] + second[2],
            total_overlap,
        ),
        common_shared + common_b,
        pool_size,
        draw_size,
        outright_matches,
    )
    four_way = exact_joint_win_count(capacities, draw_size, outright_matches)
    result = pair_cd - triple_acd - triple_bcd + four_way
    if result < 0:
        raise AssertionError("exact residual-pair inclusion-exclusion became negative")
    return result


def minimum_residual_pair_counts_by_overlap(
    first: Signature,
    second: Signature,
    anchor_overlap: int = ANCHOR_OVERLAP,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> tuple[int | None, ...]:
    """Minimize exact residual-pair intersections over cell placements."""

    outside_capacity = pool_size - (2 * draw_size - anchor_overlap)
    cell_capacities = (
        anchor_overlap,
        draw_size - anchor_overlap,
        draw_size - anchor_overlap,
        outside_capacity,
    )
    ranges = tuple(
        range(max(0, left + right - size), min(left, right) + 1)
        for left, right, size in zip(
            first, second, cell_capacities, strict=True
        )
    )
    minimums: list[int | None] = [None] * (anchor_overlap + 1)

    for shared in product(*ranges):
        overlap = sum(shared)
        if overlap > anchor_overlap:
            continue
        shared_by_cell = (shared[0], shared[1], shared[2], shared[3])
        value = exact_residual_pair_intersection(
            first,
            second,
            shared_by_cell,
            anchor_overlap,
            pool_size,
            draw_size,
            outright_matches,
        )
        prior = minimums[overlap]
        if prior is None or value < prior:
            minimums[overlap] = value

    return tuple(minimums)


@cache
def active_pair_residual_floors() -> tuple[int, ...]:
    """Return monotone exact floors for pairs of locally top-recovery types."""

    profiles = anchor_incidence_profiles()
    good_types = tuple(
        profile.signature
        for profile in profiles
        if profile.shared == profile.a_only == profile.b_only == 0
    )
    non_good_net = max(
        profile.net_recovery
        for profile in profiles
        if profile.signature not in good_types
    )
    top_non_good_types = tuple(
        profile.signature for profile in profiles if profile.net_recovery == non_good_net
    )
    if len(good_types) != 1 or len(top_non_good_types) != 2:
        raise AssertionError("the top local recovery types changed")

    minima: list[int | None] = [None] * (ANCHOR_OVERLAP + 1)
    active_types = (*good_types, *top_non_good_types)
    for first in active_types:
        for second in active_types:
            pair_minima = minimum_residual_pair_counts_by_overlap(first, second)
            for overlap, value in enumerate(pair_minima):
                if value is None:
                    continue
                prior = minima[overlap]
                if prior is None or value < prior:
                    minima[overlap] = value

    if any(value is None for value in minima):
        raise AssertionError("an active overlap class has no feasible incidence")
    exact_floors = tuple(value for value in minima if value is not None)
    monotone_floors = tuple(
        min(exact_floors[overlap:]) for overlap in range(len(exact_floors))
    )
    if monotone_floors != EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS:
        raise AssertionError("the active residual-pair floor table changed")
    return monotone_floors


def minimum_label_pair_mass(incidences: int, label_count: int) -> int:
    """Return min sum_l binom(f_l,2) for fixed incidences across labels."""

    if incidences < 0 or label_count < 1:
        raise ValueError("incidences must be nonnegative and labels positive")
    quotient, remainder = divmod(incidences, label_count)
    return remainder * comb(quotient + 1, 2) + (
        label_count - remainder
    ) * comb(quotient, 2)


@cache
def _rank_floor(edge_count: int) -> int:
    """Minimum forest rank capable of containing edge_count edges."""

    if edge_count < 0:
        raise ValueError("edge count must be nonnegative")
    rank = 0
    while comb(rank + 1, 2) < edge_count:
        rank += 1
    return rank


@cache
def _minimum_weighted_forest_census(
    active_ticket_count: int,
    minimum_pair_mass: int,
    pair_weights: tuple[int, ...],
) -> WeightedForestCensus:
    """Exhaust nested threshold-edge counts in a finite relaxation."""

    if active_ticket_count < 0 or minimum_pair_mass < 0:
        raise ValueError("ticket count and pair mass must be nonnegative")
    if len(pair_weights) < 2 or any(
        left > right for left, right in pairwise(pair_weights)
    ):
        raise ValueError("pair weights must be a nondecreasing overlap table")

    threshold_count = len(pair_weights) - 1
    edge_capacity = comb(active_ticket_count, 2)
    zero_counts = (0,) * threshold_count
    if active_ticket_count < 2:
        if minimum_pair_mass:
            raise ValueError("fewer than two tickets cannot have positive pair mass")
        return WeightedForestCensus(
            active_ticket_count,
            minimum_pair_mass,
            zero_counts,
            zero_counts,
            0,
        )

    rank_floors = tuple(_rank_floor(count) for count in range(edge_capacity + 1))
    best: tuple[int, tuple[int, ...], tuple[int, ...]] | None = None

    def visit(prefix: tuple[int, ...], upper: int) -> None:
        nonlocal best
        if len(prefix) == threshold_count - 1:
            final_count = max(0, minimum_pair_mass - sum(prefix))
            if final_count > upper:
                return
            counts = (*prefix, final_count)
            ranks = tuple(rank_floors[count] for count in counts)
            penalty = (active_ticket_count - 1) * pair_weights[0] + sum(
                (pair_weights[index + 1] - pair_weights[index]) * ranks[index]
                for index in range(threshold_count)
            )
            candidate = (penalty, counts, ranks)
            if best is None or candidate < best:
                best = candidate
            return
        for count in range(upper + 1):
            visit((*prefix, count), count)

    visit((), edge_capacity)
    if best is None:
        raise AssertionError("the finite weighted-forest census is infeasible")
    return WeightedForestCensus(
        active_ticket_count,
        minimum_pair_mass,
        best[1],
        best[2],
        best[0],
    )


def minimum_weighted_forest_census(
    active_ticket_count: int,
    minimum_pair_mass: int,
    pair_weights: tuple[int, ...],
) -> WeightedForestCensus:
    """Public checked entry to the exact finite forest-count relaxation."""

    if active_ticket_count < 0 or minimum_pair_mass < 0:
        raise ValueError("ticket count and pair mass must be nonnegative")
    if len(pair_weights) < 2 or any(
        left > right for left, right in pairwise(pair_weights)
    ):
        raise ValueError("pair weights must be a nondecreasing overlap table")
    return _minimum_weighted_forest_census(
        active_ticket_count, minimum_pair_mass, pair_weights
    )


@cache
def r4_tradeoff() -> R4Tradeoff:
    """Optimize all 190 good/best-non-good count cases exactly."""

    pair_counts = pair_intersection_table()
    if pair_counts != EXPECTED_PAIR_COUNTS:
        raise AssertionError("the exact K20 pair table changed")
    single_count = pair_counts[DRAW_SIZE]
    if single_count != EXPECTED_SINGLE_TICKET_OUTCOMES:
        raise AssertionError("the single-ticket official outcome count changed")

    profiles = anchor_incidence_profiles()
    good = tuple(
        profile for profile in profiles if profile.shared == profile.a_only == profile.b_only == 0
    )
    non_good = tuple(profile for profile in profiles if profile not in good)
    if len(good) != 1:
        raise AssertionError("the fully outside incidence type is not unique")
    good_net = good[0].net_recovery
    maximum_non_good = max(profile.net_recovery for profile in non_good)
    second_best_non_good = max(
        profile.net_recovery for profile in non_good if profile.net_recovery < maximum_non_good
    )
    if sum(profile.net_recovery == maximum_non_good for profile in non_good) != 2:
        raise AssertionError("the best non-good incidence types changed")

    pair_floors = active_pair_residual_floors()
    cases: list[TradeoffCase] = []
    for good_count in range(OUTSIDE_TICKET_COUNT + 1):
        for best_non_good_count in range(OUTSIDE_TICKET_COUNT - good_count + 1):
            worse_count = OUTSIDE_TICKET_COUNT - good_count - best_non_good_count
            active_count = good_count + best_non_good_count
            outside_mass = minimum_label_pair_mass(
                DRAW_SIZE * good_count + (DRAW_SIZE - 1) * best_non_good_count,
                OUTSIDE_LABEL_CAPACITY,
            )
            anchor_mass = minimum_label_pair_mass(best_non_good_count, 4)
            total_mass = outside_mass + anchor_mass
            census = _minimum_weighted_forest_census(
                active_count, total_mass, pair_floors
            )
            local_loss = (
                best_non_good_count * (good_net - maximum_non_good)
                + worse_count * (good_net - second_best_non_good)
            )
            cases.append(
                TradeoffCase(
                    good_ticket_count=good_count,
                    best_non_good_count=best_non_good_count,
                    worse_type_count=worse_count,
                    active_ticket_count=active_count,
                    outside_label_pair_mass=outside_mass,
                    anchor_exclusive_pair_mass=anchor_mass,
                    minimum_pair_mass=total_mass,
                    threshold_pair_counts=census.threshold_pair_counts,
                    threshold_rank_floors=census.threshold_rank_floors,
                    mandatory_outside_pair_penalty=census.lower_bound_penalty,
                    local_recovery_loss=local_loss,
                    total_recovery_reduction=local_loss + census.lower_bound_penalty,
                )
            )

    best_by_good = tuple(
        min(
            (case for case in cases if case.good_ticket_count == good_count),
            key=lambda case: (case.total_recovery_reduction, case.best_non_good_count),
        )
        for good_count in range(OUTSIDE_TICKET_COUNT + 1)
    )
    minimizing = min(
        cases,
        key=lambda case: (
            case.total_recovery_reduction,
            case.good_ticket_count,
            case.best_non_good_count,
        ),
    )
    uncorrected = (
        TICKET_COUNT * single_count
        - pair_counts[ANCHOR_OVERLAP]
        + OUTSIDE_TICKET_COUNT * good_net
    )
    guaranteed_reduction = minimizing.total_recovery_reduction
    r4_bound = uncorrected - guaranteed_reduction
    frozen_subfamily_bounds = (
        CURRENT_R3_BOUND,
        r4_bound,
        CURRENT_R5_BOUND,
        CURRENT_R6_BOUND,
    )
    family_a_bound = max(frozen_subfamily_bounds)
    family_a_bottleneck = frozen_subfamily_bounds.index(family_a_bound) + 3
    remaining_gap = family_a_bound - INCUMBENT

    if (
        len(profiles) != 32
        or good_net != -189_840
        or maximum_non_good != -625_940
        or second_best_non_good != -937_160
        or pair_floors != EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS
        or minimizing.good_ticket_count != 17
        or minimizing.best_non_good_count != 1
        or minimizing.local_recovery_loss != 436_100
        or minimizing.mandatory_outside_pair_penalty != 7_618_464
        or guaranteed_reduction != 8_054_564
        or uncorrected != 362_587_008
        or r4_bound != 354_532_444
        or r4_bound >= CURRENT_R4_BOUND
        or family_a_bound != 354_532_444
        or family_a_bottleneck != 4
    ):
        raise AssertionError("the exact r=4 incidence/forest certificate changed")

    return R4Tradeoff(
        single_ticket_outcomes=single_count,
        pair_counts=pair_counts,
        good_local_net_recovery=good_net,
        maximum_non_good_net_recovery=maximum_non_good,
        second_best_non_good_net_recovery=second_best_non_good,
        active_pair_residual_floors=pair_floors,
        cases=tuple(cases),
        best_by_good_count=best_by_good,
        minimizing_case=minimizing,
        uncorrected_all_good_bound=uncorrected,
        guaranteed_recovery_reduction=guaranteed_reduction,
        r4_bound=r4_bound,
        family_a_bound=family_a_bound,
        family_a_bottleneck_r=family_a_bottleneck,
        remaining_gap=remaining_gap,
    )


def r4_result_record() -> dict[str, object]:
    """Build the compact exact r=4 proof and handoff record."""

    pair_counts = pair_intersection_table()
    profiles = anchor_incidence_profiles()
    tradeoff = r4_tradeoff()
    winner = tradeoff.minimizing_case
    return {
        "TASK_ID": "B649_K20_R4_ANCHOR_INCIDENCE_BOUND_R6",
        "TASK_STATUS": "CERTIFIED_R4_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "INCUMBENT": INCUMBENT,
        "OFFICIAL_SINGLE_TICKET_OUTCOMES": tradeoff.single_ticket_outcomes,
        "PORTFOLIO_S1": TICKET_COUNT * tradeoff.single_ticket_outcomes,
        "PAIR_INTERSECTION_COUNTS_BY_OVERLAP": list(pair_counts),
        "ANCHOR_INCIDENCE_TYPE_COUNT": len(profiles),
        "ANCHOR_INCIDENCE_TYPES": [
            ",".join(
                str(value)
                for value in (
                    profile.shared,
                    profile.a_only,
                    profile.b_only,
                    profile.outside,
                    profile.overlap_with_a,
                    profile.overlap_with_b,
                    profile.pair_recovery_cost,
                    profile.triple_recovery,
                    profile.net_recovery,
                )
            )
            for profile in profiles
        ],
        "ANCHOR_INCIDENCE_TYPES_ENCODING": (
            "Comma-separated integer rows in TYPE_ROW_COLUMNS order."
        ),
        "TYPE_ROW_COLUMNS": [
            "shared",
            "a_only",
            "b_only",
            "outside",
            "overlap_with_a",
            "overlap_with_b",
            "local_pair_cost",
            "exact_anchor_triple",
            "net_recovery",
        ],
        "TYPE_COUNT_CONSTRAINTS": {
            "TICKET_COUNTS": (
                "Integer n_(s,a,b,o)>=0 for each of the 32 legal types; "
                "sum n_(s,a,b,o)=18."
            ),
            "TYPE_RULES": (
                "0<=s<=4; 0<=a,b<=2; s+a<=4; s+b<=4; "
                "o=6-s-a-b>=0."
            ),
            "SLOT_SUM": "s+a+b+o=6 for every outside ticket.",
            "LABEL_FREQUENCIES": (
                "Each physical label has an integer frequency 0..18; "
                "frequency sums equal type-coordinate totals in the 4 shared, "
                "2 A-only, 2 B-only, and 41 outside-label cells."
            ),
            "AGGREGATE_SLOT_CAPACITIES": {
                "SHARED": 4 * OUTSIDE_TICKET_COUNT,
                "A_ONLY": 2 * OUTSIDE_TICKET_COUNT,
                "B_ONLY": 2 * OUTSIDE_TICKET_COUNT,
                "OUTSIDE": OUTSIDE_LABEL_CAPACITY * OUTSIDE_TICKET_COUNT,
            },
            "PAIRWISE_MAXIMUM_OVERLAP": 4,
        },
        "LOCAL_TYPE_EXTREMA": {
            "GOOD_TYPE": [0, 0, 0, DRAW_SIZE],
            "GOOD_LOCAL_NET_RECOVERY": tradeoff.good_local_net_recovery,
            "BEST_NON_GOOD_TYPES": [[0, 1, 0, 5], [0, 0, 1, 5]],
            "MAXIMUM_NON_GOOD_NET_RECOVERY": (
                tradeoff.maximum_non_good_net_recovery
            ),
            "SECOND_BEST_NON_GOOD_NET_RECOVERY": (
                tradeoff.second_best_non_good_net_recovery
            ),
        },
        "OUTSIDE_PAIR_PENALTY": {
            "ACTIVE_TYPE_FAMILY": (
                "The good type and both maximum-net non-good types."
            ),
            "RESIDUAL_PAIR_FLOORS_BY_OVERLAP_0_TO_4": list(
                tradeoff.active_pair_residual_floors
            ),
            "OPTIMIZING_GOOD_COUNT": winner.good_ticket_count,
            "OPTIMIZING_BEST_NON_GOOD_COUNT": winner.best_non_good_count,
            "OPTIMIZING_WORSE_TYPE_COUNT": winner.worse_type_count,
            "MINIMUM_OUTSIDE_LABEL_PAIR_MASS": winner.outside_label_pair_mass,
            "MINIMUM_ANCHOR_EXCLUSIVE_PAIR_MASS": (
                winner.anchor_exclusive_pair_mass
            ),
            "MINIMUM_TOTAL_PAIR_MASS": winner.minimum_pair_mass,
            "THRESHOLD_PAIR_COUNTS": list(winner.threshold_pair_counts),
            "THRESHOLD_RANK_FLOORS": list(winner.threshold_rank_floors),
            "MANDATORY_OUTSIDE_PAIR_PENALTY": (
                winner.mandatory_outside_pair_penalty
            ),
            "LOCAL_RECOVERY_LOSS": winner.local_recovery_loss,
            "TOTAL_RECOVERY_REDUCTION": winner.total_recovery_reduction,
            "TRADEOFF_BY_GOOD_COUNT_BEST_ROW_COLUMNS": [
                "good_count",
                "best_non_good_count",
                "worse_type_count",
                "active_count",
                "outside_pair_mass_min",
                "anchor_pair_mass_min",
                "total_pair_mass_min",
                "e1",
                "e2",
                "e3",
                "e4",
                "rank1_floor",
                "rank2_floor",
                "rank3_floor",
                "rank4_floor",
                "forest_penalty",
                "local_loss",
                "total_reduction",
            ],
            "TRADEOFF_BY_GOOD_COUNT_BEST_ROWS": [
                ",".join(
                    str(value)
                    for value in (
                        case.good_ticket_count,
                        case.best_non_good_count,
                        case.worse_type_count,
                        case.active_ticket_count,
                        case.outside_label_pair_mass,
                        case.anchor_exclusive_pair_mass,
                        case.minimum_pair_mass,
                        *case.threshold_pair_counts,
                        *case.threshold_rank_floors,
                        case.mandatory_outside_pair_penalty,
                        case.local_recovery_loss,
                        case.total_recovery_reduction,
                    )
                )
                for case in tradeoff.best_by_good_count
            ],
            "TRADEOFF_ROWS_ENCODING": (
                "Comma-separated integer rows in TRADEOFF_BY_GOOD_COUNT_BEST_ROW_COLUMNS order."
            ),
        },
        "R4_PROOF": {
            "OUTCOME_RULE": (
                "A ticket wins with at least 3 of the 6 main-draw labels, or "
                "with exactly 2 main-draw labels when the special label is in "
                "the ticket and outside the main draw."
            ),
            "SINGLE_COUNT": (
                "sum_{h=3..6} C(6,h) C(43,6-h)*43 "
                "+ C(6,2) C(43,4)*4 = 18,611,432."
            ),
            "ANCHOR_COVER_IDENTITY": (
                "|union E_i| <= 20*N - I(4) + sum_C "
                "[J(A,B,C)-I(|A∩C|)-I(|B∩C|)]."
            ),
            "LOCAL_RESIDUAL_IDENTITY": (
                "|E_C \\ (E_A union E_B)| = "
                "N-I(|A∩C|)-I(|B∩C|)+J(A,B,C)."
            ),
            "OUTSIDE_RESIDUAL_PAIR_IDENTITY": (
                "|R_C∩R_D| = I(C,D)-J(A,C,D)-J(B,C,D)+K(A,B,C,D), "
                "counted exactly from the four-ticket membership cells."
            ),
            "LABEL_PAIR_MASS": (
                "For each active type family, sum_l C(f_l,2) equals the total "
                "outside-ticket pair overlap. Convex balancing gives lower "
                "bounds over 41 outside labels and four anchor-exclusive labels."
            ),
            "WEIGHTED_FOREST": (
                "Pair residual floors are monotone by overlap d=0..4. For "
                "e_t=#active pairs sharing at least t labels, a maximum "
                "spanning forest has weight p0*(q-1)+sum_t "
                "(p_t-p_(t-1))*rank(G_t). If a graph has e edges and forest "
                "rank r, e<=C(r+1,2), so rank>=rho(e)."
            ),
            "FINITE_CENSUS": (
                "Exhaust all nonincreasing integer e1>=e2>=e3>=e4>=0 with "
                "sum(e_t)>=the balanced pair-mass floor and e_t<=C(q,2). "
                "For fixed good count m and best non-good count n, all other "
                "types lose at least the second-best local amount. The 190 "
                "integer (m,n) cases are minimized exactly."
            ),
            "SINGLE_COUNT_DISCREPANCY": (
                "The official event count gives 18,611,432 per ticket and "
                "S1=372,228,640. This r4 proof derives S1 directly and does "
                "not import the conflicting legacy portfolio total."
            ),
        },
        "UNCORRECTED_ALL_GOOD_R4_BOUND": tradeoff.uncorrected_all_good_bound,
        "GUARANTEED_RECOVERY_REDUCTION": tradeoff.guaranteed_recovery_reduction,
        "R4_BOUND": tradeoff.r4_bound,
        "R4_STATUS": "TIGHTENED_OPEN_SUCCESS_B",
        "SUCCESS_A": tradeoff.r4_bound <= INCUMBENT,
        "SUCCESS_B": tradeoff.r4_bound < CURRENT_R4_BOUND,
        "FROZEN_OTHER_SUBFAMILY_BOUNDS": {
            "R3": CURRENT_R3_BOUND,
            "R5": CURRENT_R5_BOUND,
            "R6": CURRENT_R6_BOUND,
        },
        "FAMILY_A_RECOMPUTED_BOUND": tradeoff.family_a_bound,
        "FAMILY_A_BOTTLENECK_R": tradeoff.family_a_bottleneck_r,
        "FAMILY_A_SCOPE_NOTE": (
            "Maximum of this corrected independent r4 bound and the packet's "
            "frozen r3/r5/r6 values; those subfamilies were out of scope."
        ),
        "REMAINING_GAP": tradeoff.remaining_gap,
        "SOLVER_STATUS": "NOT_NEEDED_ANALYTIC_EXACT_FINITE_CENSUS",
        "SOLVER_CONFIGURED_WALL_LIMIT": "NOT_APPLICABLE",
        "SOLVER_ACTUAL_WALL_TIME": "NOT_APPLICABLE",
        "SOLVER_CERTIFIED_BOUND": None,
        "VERIFICATION": {
            "EXACT_PAIR_TRIPLE_CHECKS": "NOT RUN",
            "SMALL_ANCHOR_INCIDENCE_TOYS": "NOT RUN",
            "FOCUSED_TESTS": "NOT RUN",
            "RUFF": "NOT RUN",
            "PYRIGHT": "NOT RUN",
        },
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "TASK_HEAD": "RECORDED_IN_FINAL_HANDOFF",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
