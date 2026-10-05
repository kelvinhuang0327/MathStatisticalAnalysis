"""Certified joint residual S2/S3 envelope for the K20 r_max=5 subfamily.

The module counts anchor-incidence type vectors, then bounds each type orbit
without constructing portfolios. The all-outside type receives an exact
outside-pair-mass DP and a joint S2/S3 multiplicity frontier. Other type
orbits use canonical pair/triple event counts and within-orbit pair floors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import pairwise, product
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    EXPECTED_PAIR_COUNTS as CANONICAL_EXPECTED_PAIR_COUNTS,
)
from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    EXPECTED_SINGLE_TICKET_OUTCOMES,
    anchor_incidence_profiles,
    legal_anchor_incidence_signatures,
    pair_intersection_table,
    triple_intersection_count,
)

TASK_ID = "B649_K20_R5_JOINT_RESIDUAL_ENVELOPE_R1"
BASE_HEAD = "ac4d084375515309268153a829ce6ad5a370d896"
BASE_TREE = "f3d10b7af4a1c9484bfbaa184d1d0991207e2fc4"
TASK_BRANCH = "codex/b649-k20-r5-joint-residual-envelope-r1"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_R5_JOINT_RESIDUAL_ENVELOPE_R1"
)
WORKTREE_DISPOSITION = "RETAIN"

POOL_SIZE = 49
DRAW_SIZE = 6
OUTRIGHT_MATCHES = 3
ANCHOR_OVERLAP = 5
TICKET_COUNT = 20
OUTSIDE_TICKET_COUNT = TICKET_COUNT - 2
OUTSIDE_LABEL_CAPACITY = POOL_SIZE - (2 * DRAW_SIZE - ANCHOR_OVERLAP)
INCUMBENT = 313_239_661
CURRENT_R5_BOUND = 350_778_728
GOOD_SIGNATURE = (0, 0, 0, DRAW_SIZE)
NATIVE_WALL_LIMIT_SECONDS = 45
EXTERNAL_HARD_TIMEOUT_SECONDS = 60
EXPECTED_ANCHOR_INCIDENCE_TYPE_COUNT = 21

type Signature = tuple[int, int, int, int]
type ClassKey = tuple[int, int, int]
type PairFloors = dict[tuple[Signature, Signature], int]

DEFAULT_RESULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/research/matrix-native-results/"
    "b649-k20-r5-joint-residual-envelope-r1-result.json"
)


@dataclass(frozen=True)
class AnchorType:
    """One legal outside-ticket incidence type and its exact local data."""

    signature: Signature
    residual_single: int
    distinct_ticket_capacity: int
    self_residual_pair_floor: int


@dataclass(frozen=True)
class TypeClassOptions:
    """Compressed count-vector options for one A/B-symmetric type orbit."""

    key: ClassKey
    members: tuple[AnchorType, ...]
    is_good_class: bool
    type_vector_ways: tuple[int, ...]
    maximum_union_bound: tuple[int | None, ...]
    maximizing_member_counts: tuple[tuple[int, ...] | None, ...]


@dataclass(frozen=True)
class TypeVectorState:
    """Exact number of count vectors and the largest relaxed union sum."""

    vector_count: int
    maximum_non_good_union_bound: int
    witness: tuple[tuple[ClassKey, int, tuple[int, ...]], ...]


@dataclass(frozen=True)
class JointMassState:
    """One shared outside-pair-mass state for S2, S3, and union bounds."""

    outside_pair_mass: int
    minimum_s2: int
    maximum_s2: int
    maximum_selected_seven_frequency: int
    residual_multiplicity_cap: int
    maximum_s3_at_minimum_s2: int
    maximum_s3_at_maximum_s2: int
    union_reduction: int


@dataclass(frozen=True)
class FrontierSegment:
    """A certified S3 upper-envelope segment indexed by residual S2."""

    s2_start: int
    s2_end: int
    residual_multiplicity_cap: int
    maximum_s3_at_start: int
    maximum_s3_at_end: int


def _check_deadline(deadline: float) -> None:
    if monotonic() > deadline:
        raise TimeoutError("the R5 finite-state proof exceeded its native wall limit")


def _ceil_div(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator < 1:
        raise ValueError("ceil division requires a nonnegative numerator and positive divisor")
    return (numerator + denominator - 1) // denominator


def _type_capacity(
    signature: Signature,
    pool_size: int,
    draw_size: int,
    anchor_overlap: int,
) -> int:
    shared, a_only, b_only, outside = signature
    outside_capacity = pool_size - (2 * draw_size - anchor_overlap)
    if (
        min(signature) < 0
        or shared > anchor_overlap
        or a_only > draw_size - anchor_overlap
        or b_only > draw_size - anchor_overlap
        or outside > outside_capacity
        or sum(signature) != draw_size
    ):
        raise ValueError("the anchor-incidence signature is not legal")
    return (
        comb(anchor_overlap, shared)
        * comb(draw_size - anchor_overlap, a_only)
        * comb(draw_size - anchor_overlap, b_only)
        * comb(outside_capacity, outside)
    )


def residual_pair_floor(
    first: Signature,
    second: Signature,
    anchor_overlap: int = ANCHOR_OVERLAP,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Lower-bound a residual pair intersection using only canonical S2/S3.

    Inclusion-exclusion gives
    |R_C intersect R_D| = I(C,D)-I(A,C,D)-I(B,C,D)+I(A,B,C,D).
    The omitted four-event term is nonnegative, so minimizing the first three
    exact terms over feasible anchor-cell overlaps is a certified floor.
    """

    shared_a, a_a, b_a, outside_a = first
    shared_b, a_b, b_b, outside_b = second
    outside_capacity = pool_size - (2 * draw_size - anchor_overlap)
    if outside_capacity < 0:
        raise ValueError("the requested anchor pair cannot fit in the pool")
    pair_counts = pair_intersection_table(pool_size, draw_size, outright_matches)
    costs: list[int] = []

    shared_min = max(0, shared_a + shared_b - anchor_overlap)
    shared_max = min(shared_a, shared_b)
    a_min = max(0, a_a + a_b - (draw_size - anchor_overlap))
    a_max = min(a_a, a_b)
    b_min = max(0, b_a + b_b - (draw_size - anchor_overlap))
    b_max = min(b_a, b_b)
    outside_min = max(0, outside_a + outside_b - outside_capacity)
    outside_max = min(outside_a, outside_b)

    for shared_common in range(shared_min, shared_max + 1):
        for a_common in range(a_min, a_max + 1):
            for b_common in range(b_min, b_max + 1):
                for outside_common in range(outside_min, outside_max + 1):
                    pair_overlap = (
                        shared_common + a_common + b_common + outside_common
                    )
                    if pair_overlap > anchor_overlap:
                        continue
                    try:
                        triple_a = triple_intersection_count(
                            (
                                shared_a + a_a,
                                shared_b + a_b,
                                pair_overlap,
                            ),
                            shared_common + a_common,
                            pool_size,
                            draw_size,
                            outright_matches,
                        )
                        triple_b = triple_intersection_count(
                            (
                                shared_a + b_a,
                                shared_b + b_b,
                                pair_overlap,
                            ),
                            shared_common + b_common,
                            pool_size,
                            draw_size,
                            outright_matches,
                        )
                    except ValueError:
                        continue
                    costs.append(max(0, pair_counts[pair_overlap] - triple_a - triple_b))

    if not costs:
        raise ValueError("the incidence types have no legal distinct-ticket pair")
    return min(costs)


def r5_anchor_types(
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> tuple[AnchorType, ...]:
    """Enumerate every legal overlap-five outside-ticket incidence type."""

    signatures = legal_anchor_incidence_signatures(
        ANCHOR_OVERLAP, draw_size, pool_size
    )
    pair_counts = pair_intersection_table(pool_size, draw_size, outright_matches)
    single_count = pair_counts[draw_size]
    profiles = {
        profile.signature: profile
        for profile in anchor_incidence_profiles(
            ANCHOR_OVERLAP, pool_size, draw_size, outright_matches
        )
    }
    if set(profiles) != set(signatures):
        raise AssertionError("canonical anchor profiles disagree with legal r5 types")

    result: list[AnchorType] = []
    for signature in signatures:
        profile = profiles[signature]
        residual_single = (
            single_count
            - pair_counts[profile.overlap_with_a]
            - pair_counts[profile.overlap_with_b]
            + profile.triple_recovery
        )
        if residual_single < 0:
            raise AssertionError("anchor-conditioned single residual became negative")
        result.append(
            AnchorType(
                signature=signature,
                residual_single=residual_single,
                distinct_ticket_capacity=_type_capacity(
                    signature, pool_size, draw_size, ANCHOR_OVERLAP
                ),
                self_residual_pair_floor=0,
            )
        )
    if pool_size == POOL_SIZE and draw_size == DRAW_SIZE:
        if len(result) != EXPECTED_ANCHOR_INCIDENCE_TYPE_COUNT:
            raise AssertionError("the exact r5 anchor type census changed")
        if any(row.signature in ((5, 1, 0, 0), (5, 0, 1, 0)) for row in result):
            raise AssertionError("an outside type duplicates one of the anchors")
    return tuple(result)


def _pair_floor_table(
    types: tuple[AnchorType, ...],
    deadline: float,
) -> PairFloors:
    floors: PairFloors = {}
    for left_index, left in enumerate(types):
        for right in types[left_index:]:
            _check_deadline(deadline)
            floor = residual_pair_floor(left.signature, right.signature)
            floors[(left.signature, right.signature)] = floor
            floors[(right.signature, left.signature)] = floor
    return floors


def _class_key(signature: Signature) -> ClassKey:
    shared, a_only, b_only, outside = signature
    return (shared, a_only + b_only, outside)


def _class_options(
    key: ClassKey,
    members: tuple[AnchorType, ...],
    pair_floors: PairFloors,
    deadline: float,
) -> TypeClassOptions:
    if not members:
        raise ValueError("an incidence class cannot be empty")
    if len({member.residual_single for member in members}) != 1:
        raise AssertionError("A/B-mirror types must have equal residual singles")
    is_good_class = any(member.signature == GOOD_SIGNATURE for member in members)
    if is_good_class and len(members) != 1:
        raise AssertionError("the all-outside good type must be a singleton class")

    ways = [0] * (OUTSIDE_TICKET_COUNT + 1)
    maximum_union: list[int | None] = [None] * (OUTSIDE_TICKET_COUNT + 1)
    maximizing_counts: list[tuple[int, ...] | None] = [
        None
    ] * (OUTSIDE_TICKET_COUNT + 1)
    count_ranges = tuple(
        range(min(OUTSIDE_TICKET_COUNT, member.distinct_ticket_capacity) + 1)
        for member in members
    )
    single = members[0].residual_single

    for member_counts in product(*count_ranges):
        _check_deadline(deadline)
        ticket_count = sum(member_counts)
        if ticket_count > OUTSIDE_TICKET_COUNT:
            continue
        ways[ticket_count] += 1
        if ticket_count == 0:
            candidate = 0
        else:
            residual_s2_floor = 0
            for left_index, left in enumerate(members):
                for right_index in range(left_index, len(members)):
                    right = members[right_index]
                    pair_count = (
                        comb(member_counts[left_index], 2)
                        if left_index == right_index
                        else member_counts[left_index] * member_counts[right_index]
                    )
                    if pair_count:
                        residual_s2_floor += pair_count * pair_floors[
                            (left.signature, right.signature)
                        ]
            candidate = ticket_count * single - _ceil_div(
                2 * residual_s2_floor, ticket_count
            )
        prior = maximum_union[ticket_count]
        if prior is None or candidate > prior:
            maximum_union[ticket_count] = candidate
            maximizing_counts[ticket_count] = tuple(member_counts)

    return TypeClassOptions(
        key=key,
        members=members,
        is_good_class=is_good_class,
        type_vector_ways=tuple(ways),
        maximum_union_bound=tuple(maximum_union),
        maximizing_member_counts=tuple(maximizing_counts),
    )


def _compress_type_classes(
    types: tuple[AnchorType, ...],
    pair_floors: PairFloors,
    deadline: float,
) -> tuple[TypeClassOptions, ...]:
    by_key: dict[ClassKey, list[AnchorType]] = defaultdict(list)
    for row in types:
        by_key[_class_key(row.signature)].append(row)
    return tuple(
        _class_options(
            key,
            tuple(sorted(members, key=lambda row: row.signature)),
            pair_floors,
            deadline,
        )
        for key, members in sorted(by_key.items())
    )


def _type_vector_census(
    classes: tuple[TypeClassOptions, ...],
    deadline: float,
) -> dict[int, TypeVectorState]:
    states: dict[tuple[int, int], TypeVectorState] = {
        (0, 0): TypeVectorState(1, 0, ())
    }
    for type_class in classes:
        _check_deadline(deadline)
        next_states: dict[tuple[int, int], TypeVectorState] = {}
        for (prior_count, prior_good), prior in states.items():
            for count, ways in enumerate(type_class.type_vector_ways):
                total = prior_count + count
                if not ways or total > OUTSIDE_TICKET_COUNT:
                    continue
                good_count = prior_good + (
                    count if type_class.is_good_class else 0
                )
                key = (total, good_count)
                group_bound = (
                    0
                    if type_class.is_good_class
                    else type_class.maximum_union_bound[count]
                )
                if group_bound is None:
                    raise AssertionError("a feasible type count lacks its union bound")
                candidate = prior.maximum_non_good_union_bound + group_bound
                witness_counts = type_class.maximizing_member_counts[count]
                if witness_counts is None:
                    raise AssertionError("a feasible class count lacks a witness")
                witness = (
                    *prior.witness,
                    (type_class.key, count, witness_counts),
                )
                existing = next_states.get(key)
                if existing is None:
                    next_states[key] = TypeVectorState(
                        prior.vector_count * ways, candidate, witness
                    )
                else:
                    next_states[key] = TypeVectorState(
                        existing.vector_count + prior.vector_count * ways,
                        candidate
                        if candidate > existing.maximum_non_good_union_bound
                        else existing.maximum_non_good_union_bound,
                        witness
                        if candidate > existing.maximum_non_good_union_bound
                        else existing.witness,
                    )
        states = next_states
    result = {
        good_count: state
        for (ticket_count, good_count), state in states.items()
        if ticket_count == OUTSIDE_TICKET_COUNT
    }
    if set(result) != set(range(OUTSIDE_TICKET_COUNT + 1)):
        raise AssertionError("the compressed type-vector census missed a good-count class")
    return result


def residual_s3_upper_bound(residual_s2: int, multiplicity_cap: int) -> int:
    """Use C(m,3) <= (K-2) C(m,2)/3 for every residual multiplicity m<=K."""

    if residual_s2 < 0 or multiplicity_cap < 0:
        raise ValueError("S2 and multiplicity cap must be nonnegative")
    if multiplicity_cap < 3:
        return 0
    return (multiplicity_cap - 2) * residual_s2 // 3


def residual_union_reduction(residual_s2: int, multiplicity_cap: int) -> int:
    """Return the certified S1 reduction from S2 when every multiplicity is <=K."""

    if residual_s2 < 0 or multiplicity_cap < 0:
        raise ValueError("S2 and multiplicity cap must be nonnegative")
    if multiplicity_cap == 0:
        return 0
    return _ceil_div(2 * residual_s2, multiplicity_cap)


def _pair_s2_envelopes(
    deadline: float,
) -> tuple[
    tuple[tuple[int | None, ...], ...],
    tuple[tuple[int | None, ...], ...],
]:
    """Relax ticket-pair overlaps independently, retaining their common mass."""

    maximum_pairs = comb(OUTSIDE_TICKET_COUNT, 2)
    maximum_mass = ANCHOR_OVERLAP * maximum_pairs
    pair_counts = pair_intersection_table()
    lower_costs = tuple(
        max(
            0,
            pair_counts[overlap]
            - 2 * triple_intersection_count((0, 0, overlap), 0),
        )
        for overlap in range(ANCHOR_OVERLAP + 1)
    )
    upper_costs = pair_counts[: ANCHOR_OVERLAP + 1]
    minimum: list[list[int | None]] = [
        [None] * (maximum_mass + 1) for _ in range(maximum_pairs + 1)
    ]
    maximum: list[list[int | None]] = [
        [None] * (maximum_mass + 1) for _ in range(maximum_pairs + 1)
    ]
    minimum[0][0] = maximum[0][0] = 0
    reachable_mass = 0

    for pair_count in range(1, maximum_pairs + 1):
        _check_deadline(deadline)
        for mass in range(min(reachable_mass, maximum_mass) + 1):
            low = minimum[pair_count - 1][mass]
            high = maximum[pair_count - 1][mass]
            if low is None or high is None:
                continue
            for overlap in range(ANCHOR_OVERLAP + 1):
                next_mass = mass + overlap
                if next_mass > maximum_mass:
                    continue
                candidate_low = low + lower_costs[overlap]
                candidate_high = high + upper_costs[overlap]
                prior_low = minimum[pair_count][next_mass]
                prior_high = maximum[pair_count][next_mass]
                if prior_low is None or candidate_low < prior_low:
                    minimum[pair_count][next_mass] = candidate_low
                if prior_high is None or candidate_high > prior_high:
                    maximum[pair_count][next_mass] = candidate_high
        reachable_mass = min(maximum_mass, reachable_mass + ANCHOR_OVERLAP)

    return (
        tuple(tuple(row) for row in minimum),
        tuple(tuple(row) for row in maximum),
    )


def _frequency_mass_bitsets(
    label_count: int,
    total_incidences: int,
    maximum_frequency: int,
    maximum_pair_mass: int,
    deadline: float,
) -> tuple[int, ...]:
    """Census all frequency multisets by incidence total and C(f,2) mass."""

    if min(label_count, total_incidences, maximum_frequency, maximum_pair_mass) < 0:
        raise ValueError("frequency DP dimensions must be nonnegative")
    mass_mask = (1 << (maximum_pair_mass + 1)) - 1
    reachable = [0] * (total_incidences + 1)
    reachable[0] = 1
    for _ in range(label_count):
        _check_deadline(deadline)
        next_reachable = [0] * (total_incidences + 1)
        for incidences, masses in enumerate(reachable):
            if not masses:
                continue
            for frequency in range(
                min(maximum_frequency, total_incidences - incidences) + 1
            ):
                next_reachable[incidences + frequency] |= (
                    masses << comb(frequency, 2)
                ) & mass_mask
        reachable = next_reachable
    return tuple(reachable)


def _maximum_selected_seven_by_mass(
    ticket_count: int,
    maximum_pair_mass: int,
    deadline: float,
) -> tuple[int | None, ...]:
    total_incidences = DRAW_SIZE * ticket_count
    selected = _frequency_mass_bitsets(
        7, total_incidences, ticket_count, maximum_pair_mass, deadline
    )
    remaining = _frequency_mass_bitsets(
        OUTSIDE_LABEL_CAPACITY - 7,
        total_incidences,
        ticket_count,
        maximum_pair_mass,
        deadline,
    )
    mass_mask = (1 << (maximum_pair_mass + 1)) - 1
    maximum_selected: list[int | None] = [None] * (maximum_pair_mass + 1)
    for selected_incidences, selected_masses in enumerate(selected):
        _check_deadline(deadline)
        remaining_incidences = total_incidences - selected_incidences
        if (
            not selected_masses
            or not 0 <= remaining_incidences < len(remaining)
        ):
            continue
        remaining_masses = remaining[remaining_incidences]
        if not remaining_masses:
            continue
        combined_masses = 0
        pending = selected_masses
        while pending:
            least_bit = pending & -pending
            combined_masses |= remaining_masses << (least_bit.bit_length() - 1)
            pending ^= least_bit
        combined_masses &= mass_mask
        while combined_masses:
            least_bit = combined_masses & -combined_masses
            mass = least_bit.bit_length() - 1
            maximum_selected[mass] = selected_incidences
            combined_masses ^= least_bit
    return tuple(maximum_selected)


def _incidence_pair_mass_floor(incidences: int, labels: int) -> int:
    quotient, remainder = divmod(incidences, labels)
    return (labels - remainder) * comb(quotient, 2) + remainder * comb(
        quotient + 1, 2
    )


def _joint_mass_states(
    ticket_count: int,
    minimum_s2_by_pair_count: tuple[tuple[int | None, ...], ...],
    maximum_s2_by_pair_count: tuple[tuple[int | None, ...], ...],
    deadline: float,
) -> tuple[JointMassState, ...]:
    pair_count = comb(ticket_count, 2)
    maximum_pair_mass = ANCHOR_OVERLAP * pair_count
    minimum_s2_by_mass = minimum_s2_by_pair_count[pair_count]
    maximum_s2_by_mass = maximum_s2_by_pair_count[pair_count]
    selected_seven = _maximum_selected_seven_by_mass(
        ticket_count, maximum_pair_mass, deadline
    )
    incidence_floor = _incidence_pair_mass_floor(
        DRAW_SIZE * ticket_count, OUTSIDE_LABEL_CAPACITY
    )
    states: list[JointMassState] = []
    for mass in range(incidence_floor, maximum_pair_mass + 1):
        _check_deadline(deadline)
        top_seven = selected_seven[mass]
        minimum_s2 = minimum_s2_by_mass[mass]
        maximum_s2 = maximum_s2_by_mass[mass]
        if top_seven is None or minimum_s2 is None or maximum_s2 is None:
            continue
        multiplicity_cap = min(ticket_count, top_seven // 3)
        states.append(
            JointMassState(
                outside_pair_mass=mass,
                minimum_s2=minimum_s2,
                maximum_s2=maximum_s2,
                maximum_selected_seven_frequency=top_seven,
                residual_multiplicity_cap=multiplicity_cap,
                maximum_s3_at_minimum_s2=residual_s3_upper_bound(
                    minimum_s2, multiplicity_cap
                ),
                maximum_s3_at_maximum_s2=residual_s3_upper_bound(
                    maximum_s2, multiplicity_cap
                ),
                union_reduction=residual_union_reduction(
                    minimum_s2, multiplicity_cap
                ),
            )
        )
    if not states:
        raise AssertionError("the good-ticket joint mass census is empty")
    return tuple(states)


def joint_s2_s3_frontier_segments(
    states: tuple[JointMassState, ...],
) -> tuple[FrontierSegment, ...]:
    """Build the maximum S3 upper envelope over shared S2 interval states."""

    breakpoints = sorted(
        {
            endpoint
            for state in states
            for endpoint in (state.minimum_s2, state.maximum_s2 + 1)
        }
    )
    segments: list[FrontierSegment] = []
    for start, next_start in pairwise(breakpoints):
        end = next_start - 1
        active = tuple(
            state
            for state in states
            if state.minimum_s2 <= start and state.maximum_s2 >= end
        )
        if not active:
            continue
        multiplicity_cap = max(
            state.residual_multiplicity_cap for state in active
        )
        segment = FrontierSegment(
            s2_start=start,
            s2_end=end,
            residual_multiplicity_cap=multiplicity_cap,
            maximum_s3_at_start=residual_s3_upper_bound(
                start, multiplicity_cap
            ),
            maximum_s3_at_end=residual_s3_upper_bound(end, multiplicity_cap),
        )
        if (
            segments
            and segments[-1].s2_end + 1 == segment.s2_start
            and segments[-1].residual_multiplicity_cap
            == segment.residual_multiplicity_cap
        ):
            prior = segments.pop()
            segments.append(
                FrontierSegment(
                    s2_start=prior.s2_start,
                    s2_end=segment.s2_end,
                    residual_multiplicity_cap=multiplicity_cap,
                    maximum_s3_at_start=prior.maximum_s3_at_start,
                    maximum_s3_at_end=segment.maximum_s3_at_end,
                )
            )
        else:
            segments.append(segment)
    if not segments:
        raise AssertionError("the S2/S3 upper frontier is empty")
    return tuple(segments)


def _frontier_digest(
    states: tuple[JointMassState, ...],
    segments: tuple[FrontierSegment, ...],
) -> str:
    payload = {
        "STATES": [asdict(state) for state in states],
        "SEGMENTS": [asdict(segment) for segment in segments],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _good_group_results(
    minimum_s2_by_pair_count: tuple[tuple[int | None, ...], ...],
    maximum_s2_by_pair_count: tuple[tuple[int | None, ...], ...],
    good_single: int,
    deadline: float,
) -> tuple[dict[str, object], ...]:
    results: list[dict[str, object]] = []
    for ticket_count in range(OUTSIDE_TICKET_COUNT + 1):
        states = _joint_mass_states(
            ticket_count,
            minimum_s2_by_pair_count,
            maximum_s2_by_pair_count,
            deadline,
        )
        frontier = joint_s2_s3_frontier_segments(states)
        best_state = min(
            states,
            key=lambda state: (
                state.union_reduction,
                state.outside_pair_mass,
            ),
        )
        reduction = best_state.union_reduction
        residual_union_bound = ticket_count * good_single - reduction
        results.append(
            {
                "GOOD_TICKET_COUNT": ticket_count,
                "RESIDUAL_STATE_COUNT": len(states),
                "S2_S3_FRONTIER_SIZE": len(frontier),
                "S2_S3_FRONTIER_SHA256": _frontier_digest(states, frontier),
                "S2_S3_FRONTIER": [asdict(segment) for segment in frontier],
                "MAXIMUM_FRONTIER_S3_UPPER_BOUND": max(
                    segment.maximum_s3_at_end for segment in frontier
                ),
                "MAXIMUM_FRONTIER_S2_ENDPOINT": max(
                    segment.s2_end for segment in frontier
                ),
                "UNION_OBJECTIVE": (
                    "max_M [S1 - ceil(2*minimum_S2(M)/K(M))] over "
                    "the same outside-pair-mass states"
                ),
                "MINIMUM_UNION_REDUCTION": reduction,
                "REDUCTION_OUTSIDE_PAIR_MASS": best_state.outside_pair_mass,
                "REDUCTION_S2_LOWER_BOUND": best_state.minimum_s2,
                "REDUCTION_MULTIPLICITY_CAP": (
                    best_state.residual_multiplicity_cap
                ),
                "REDUCTION_TOP_SEVEN_FREQUENCY": (
                    best_state.maximum_selected_seven_frequency
                ),
                "RESIDUAL_S1": ticket_count * good_single,
                "RESIDUAL_UNION_BOUND": residual_union_bound,
            }
        )
    return tuple(results)


def analyze_r5_joint_residual_envelope(
    focused_tests: str = "NOT RUN",
    ruff: str = "NOT RUN",
    pyright: str = "NOT RUN",
) -> dict[str, object]:
    """Run the exact finite type census and certified joint residual DP."""

    started = monotonic()
    deadline = started + NATIVE_WALL_LIMIT_SECONDS
    pair_counts = pair_intersection_table()
    if pair_counts != CANONICAL_EXPECTED_PAIR_COUNTS:
        raise AssertionError("the canonical official pair outcome table changed")
    types = r5_anchor_types()
    pair_floors = _pair_floor_table(types, deadline)
    enriched_types = tuple(
        AnchorType(
            signature=row.signature,
            residual_single=row.residual_single,
            distinct_ticket_capacity=row.distinct_ticket_capacity,
            self_residual_pair_floor=pair_floors[
                (row.signature, row.signature)
            ],
        )
        for row in types
    )
    classes = _compress_type_classes(enriched_types, pair_floors, deadline)
    if len(classes) != 16:
        raise AssertionError("the A/B-symmetric r5 type compression changed")
    type_vectors = _type_vector_census(classes, deadline)
    vector_count = sum(row.vector_count for row in type_vectors.values())

    minimum_s2, maximum_s2 = _pair_s2_envelopes(deadline)
    good_single = next(
        row.residual_single
        for row in enriched_types
        if row.signature == GOOD_SIGNATURE
    )
    good_results = _good_group_results(
        minimum_s2, maximum_s2, good_single, deadline
    )
    anchor_union = (
        2 * EXPECTED_SINGLE_TICKET_OUTCOMES - pair_counts[ANCHOR_OVERLAP]
    )
    bound_rows: list[dict[str, object]] = []
    for good_count in range(OUTSIDE_TICKET_COUNT + 1):
        _check_deadline(deadline)
        census = type_vectors[good_count]
        good_result = good_results[good_count]
        good_union_bound = cast(int, good_result["RESIDUAL_UNION_BOUND"])
        total_bound = (
            anchor_union
            + census.maximum_non_good_union_bound
            + good_union_bound
        )
        bound_rows.append(
            {
                "GOOD_TICKET_COUNT": good_count,
                "FEASIBLE_TYPE_COUNT_VECTOR_COUNT": census.vector_count,
                "MAXIMUM_NON_GOOD_ORBIT_UNION_BOUND": (
                    census.maximum_non_good_union_bound
                ),
                "GOOD_GROUP_RESIDUAL_UNION_BOUND": good_union_bound,
                "GOOD_GROUP_MINIMUM_UNION_REDUCTION": (
                    good_result["MINIMUM_UNION_REDUCTION"]
                ),
                "R5_UPPER_BOUND": total_bound,
            }
        )
    worst = max(
        bound_rows, key=lambda row: cast(int, row["R5_UPPER_BOUND"])
    )
    worst_good_count = cast(int, worst["GOOD_TICKET_COUNT"])
    worst_witness = type_vectors[worst_good_count].witness
    frontier_count = sum(
        cast(int, row["S2_S3_FRONTIER_SIZE"]) for row in good_results
    )
    residual_state_count = sum(
        cast(int, row["RESIDUAL_STATE_COUNT"]) for row in good_results
    )
    state_manifest = {
        "TYPE_ROWS": [asdict(row) for row in enriched_types],
        "PAIR_FLOORS": [
            {
                "FIRST": list(left),
                "SECOND": list(right),
                "FLOOR": floor,
            }
            for (left, right), floor in sorted(pair_floors.items())
            if left <= right
        ],
        "TYPE_VECTOR_COUNTS": [
            {
                "GOOD_TICKET_COUNT": good_count,
                "VECTOR_COUNT": type_vectors[good_count].vector_count,
                "MAXIMUM_NON_GOOD_UNION_BOUND": (
                    type_vectors[good_count].maximum_non_good_union_bound
                ),
                "WITNESS": [
                    {
                        "CLASS_KEY": list(class_key),
                        "TICKET_COUNT": count,
                        "MEMBER_COUNTS": list(member_counts),
                    }
                    for class_key, count, member_counts in type_vectors[
                        good_count
                    ].witness
                ],
            }
            for good_count in range(OUTSIDE_TICKET_COUNT + 1)
        ],
        "GOOD_GROUP_FRONTIERS": good_results,
        "BOUND_ROWS": bound_rows,
    }
    state_sha256 = hashlib.sha256(
        json.dumps(
            state_manifest, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    elapsed = monotonic() - started
    _check_deadline(deadline)
    certified_bound = cast(int, worst["R5_UPPER_BOUND"])
    success_a = certified_bound <= INCUMBENT
    success_b = certified_bound < CURRENT_R5_BOUND
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": (
            "COMPLETED_SUCCESS_A"
            if success_a
            else "COMPLETED_SUCCESS_B"
            if success_b
            else "NO_STRICT_IMPROVEMENT"
        ),
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_HEAD": "RECORDED_IN_FINAL_HANDOFF",
        "WORKTREE_PATH": WORKTREE_PATH,
        "WORKTREE_DISPOSITION": WORKTREE_DISPOSITION,
        "ANCHOR_INCIDENCE_TYPE_COUNT": len(enriched_types),
        "COMPRESSED_ANCHOR_TYPE_CLASS_COUNT": len(classes),
        "FEASIBLE_TYPE_COUNT_VECTOR_COUNT": vector_count,
        "TYPE_COUNT_VECTOR_COMPRESSION": (
            "Exact bounded generating-function census, compressed by "
            "A/B-symmetric anchor type class and good-ticket count."
        ),
        "RESIDUAL_STATE_COUNT": residual_state_count,
        "S2_S3_FRONTIER_SIZE": frontier_count,
        "S2_S3_FRONTIER_BY_GOOD_COUNT": list(good_results),
        "JOINT_STATE_SHA256": state_sha256,
        "ANCHOR_UNION": anchor_union,
        "R5_BOUND": certified_bound,
        "R5_STATUS": "CLOSED" if success_a else "TIGHTENED_OPEN" if success_b else "OPEN",
        "CURRENT_CERTIFIED_R5_BOUND": CURRENT_R5_BOUND,
        "R5_BOUND_IMPROVEMENT": CURRENT_R5_BOUND - certified_bound,
        "MILESTONE_BOUND": 350_545_750,
        "MILESTONE_MET": certified_bound < 350_545_750,
        "INCUMBENT": INCUMBENT,
        "LEAF_GAP": certified_bound - INCUMBENT,
        "WORST_GOOD_TICKET_COUNT": worst_good_count,
        "WORST_CASE_COMPRESSED_TYPE_VECTOR": [
            {
                "CLASS_KEY": list(class_key),
                "TICKET_COUNT": count,
                "MEMBER_COUNTS": list(member_counts),
            }
            for class_key, count, member_counts in worst_witness
        ],
        "BOUND_BY_GOOD_TICKET_COUNT": bound_rows,
        "PAIR_OUTCOME_TABLE": list(pair_counts),
        "PAIR_TRIPLE_TABLE_SOURCE": (
            "Canonical pair_intersection_table and triple_intersection_count "
            "from b649_k20_r4_anchor_incidence_bound_r6.py."
        ),
        "RESIDUAL_PAIR_FLOOR_CERTIFICATE": (
            "For every outside pair, residual S2 is at least I(C,D)-I(A,C,D)"
            "-I(B,C,D); the omitted four-event term is nonnegative. "
            "The finite type-pair census minimizes this floor over all legal "
            "shared/A-only/B-only/outside cell intersections."
        ),
        "RESIDUAL_S3_POINTWISE_CERTIFICATE": (
            "For each same-mass state, residual multiplicity m<=K gives "
            "C(m,3)<=(K-2)*C(m,2)/3 when K>=3; otherwise S3=0. "
            "The frontier carries K on each S2 interval."
        ),
        "RESIDUAL_UNION_POINTWISE_CERTIFICATE": (
            "For 1<=m<=K, 1<=m-2*C(m,2)/K. The good-type union objective "
            "uses the minimum residual S2 and maximum multiplicity from the "
            "same outside-pair-mass state. Other anchor type classes use "
            "their own within-class pair floors and are combined by "
            "subadditivity."
        ),
        "SOLVER_STATUS": "EXACT_FINITE_STATE_DP_WITH_CERTIFIED_RELAXATIONS",
        "SOLVER_CONFIGURED_WALL_LIMIT": (
            f"{NATIVE_WALL_LIMIT_SECONDS}s native; "
            f"{EXTERNAL_HARD_TIMEOUT_SECONDS}s external hard timeout"
        ),
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": round(elapsed, 6),
        "SOLVER_CERTIFIED_BOUND": certified_bound,
        "SOLVER_CERTIFICATE_SHA256": state_sha256,
        "FOCUSED_TESTS": focused_tests,
        "RUFF": ruff,
        "PYRIGHT": pyright,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-path", type=Path, default=DEFAULT_RESULT_PATH)
    parser.add_argument(
        "--focused-tests",
        choices=("NOT RUN", "PASS", "FAIL"),
        default="NOT RUN",
    )
    parser.add_argument("--ruff", choices=("NOT RUN", "PASS", "FAIL"), default="NOT RUN")
    parser.add_argument(
        "--pyright",
        choices=("NOT RUN", "PASS", "FAIL"),
        default="NOT RUN",
    )
    arguments = parser.parse_args()
    result = analyze_r5_joint_residual_envelope(
        focused_tests=arguments.focused_tests,
        ruff=arguments.ruff,
        pyright=arguments.pyright,
    )
    arguments.result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"TASK_STATUS={result['TASK_STATUS']}")
    print(f"ANCHOR_INCIDENCE_TYPE_COUNT={result['ANCHOR_INCIDENCE_TYPE_COUNT']}")
    print(f"RESIDUAL_STATE_COUNT={result['RESIDUAL_STATE_COUNT']}")
    print(f"S2_S3_FRONTIER_SIZE={result['S2_S3_FRONTIER_SIZE']}")
    print(f"R5_BOUND={result['R5_BOUND']}")
    print(f"R5_STATUS={result['R5_STATUS']}")
    print(f"SOLVER_ACTUAL_WALL_TIME_SECONDS={result['SOLVER_ACTUAL_WALL_TIME_SECONDS']}")


if __name__ == "__main__":
    main()
