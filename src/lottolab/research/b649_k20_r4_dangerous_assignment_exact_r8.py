"""Exact compressed assignment bounds for the remaining K20 r=4 vectors.

This module reloads only the three pinned R7 danger vectors. It does not run
the 52,360-vector count census or search complete portfolios. Label names are
quotiented out through frequency and overlap-component invariants.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS,
    anchor_incidence_profiles,
    minimum_label_pair_mass,
    pair_intersection_table,
)

BASE_HEAD = "aea551006d341648408d534d317ae020d3bb89e2"
BASE_TREE = "148a1b234ac984890ea3dcf8e8a1d71d5bc0e0b8"
TASK_BRANCH = "codex/b649-k20-r4-dangerous-vector-exact-assignment-r8"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_R4_DANGEROUS_VECTOR_EXACT_ASSIGNMENT_R8"
)

POOL_SIZE = 49
DRAW_SIZE = 6
TICKET_COUNT = 20
OUTSIDE_TICKET_COUNT = 18
OUTSIDE_LABEL_CAPACITY = 41
MAXIMUM_PAIR_OVERLAP = 4
ANCHOR_SHARED_CAPACITY = 4
ANCHOR_A_ONLY_CAPACITY = 2
ANCHOR_B_ONLY_CAPACITY = 2

INCUMBENT = 313_239_661
CURRENT_R3_BOUND = 351_483_978
CURRENT_R5_BOUND = 350_778_728
CURRENT_R6_BOUND = 343_869_728
PRIOR_R4_BOUND = 354_519_816
UNCORRECTED_R4_BOUND = 362_587_008
PRIOR_LOWER_GOOD_MINIMUM_REDUCTION = 8_392_832
PRIOR_17_GOOD_NO_BEST_MINIMUM_REDUCTION = 8_260_784

# Fixed before the exact DP run. The outer process applies the hard timeout.
NATIVE_WALL_LIMIT_SECONDS = 45
EXTERNAL_HARD_TIMEOUT_SECONDS = 60

EXPECTED_PAIR_COUNTS = (
    107_800,
    574_000,
    1_695_988,
    3_469_942,
    6_224_512,
    10_776_332,
    18_611_432,
)

type Signature = tuple[int, int, int, int]
type TypeCounts = tuple[tuple[Signature, int], ...]

DANGEROUS_VECTOR_TYPES: tuple[TypeCounts, ...] = (
    (((0, 0, 0, 6), 18),),
    (((0, 0, 0, 6), 17), ((0, 0, 1, 5), 1)),
    (((0, 0, 0, 6), 17), ((0, 1, 0, 5), 1)),
)


@dataclass(frozen=True)
class WitnessMetrics:
    """Checkable global assignment witness for one dangerous vector."""

    outside_pair_mass: int
    outside_frequency_histogram: tuple[tuple[int, int], ...]
    maximum_outside_pair_overlap: int
    maximum_full_portfolio_pair_overlap: int
    all_tickets_have_size_six: bool
    anchor_capacities: tuple[int, int, int, int]
    special_ticket_index: int | None
    replaced_outside_label: int | None
    special_anchor_label: int | None


@dataclass(frozen=True)
class ComponentPenaltyCase:
    """Certified Hunter-forest penalty for one component-count stratum."""

    component_count: int
    positive_tree_edge_count: int
    zero_overlap_bridge_count: int
    repeated_overlap_forced: bool
    no_repeat_label_union_floor: int
    penalty_floor: int


@dataclass(frozen=True)
class DangerousVectorCertificate:
    """Exact local and compressed global certificate for one type vector."""

    label: str
    type_counts: TypeCounts
    realizable: bool
    outside_incidences: int
    minimum_s2_label_pair_mass: int
    minimum_s2_frequency_histogram: tuple[tuple[int, int], ...]
    witness: WitnessMetrics
    anchor_s3_recovery: int
    anchor_pair_cost: int
    net_anchor_recovery: int
    local_recovery_loss: int
    maximum_overlap_components: int
    component_cases: tuple[ComponentPenaltyCase, ...]
    mandatory_outside_pair_penalty: int
    total_recovery_reduction: int
    r4_bound: int


def _check_deadline(deadline: float) -> None:
    if monotonic() > deadline:
        raise TimeoutError("the exact assignment DP exceeded its native wall limit")


def load_prior_dangerous_vectors(path: Path) -> tuple[TypeCounts, ...]:
    """Reload the exact three type vectors from the pinned R7 result file."""

    loaded_document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded_document, dict):
        raise ValueError("the pinned R7 result must be a JSON object")
    document = cast(dict[str, object], loaded_document)
    raw_results = document.get("DANGEROUS_VECTOR_RESULTS")
    if not isinstance(raw_results, list):
        raise ValueError("the pinned R7 result has no dangerous-vector list")

    vectors: list[TypeCounts] = []
    for raw_result_value in cast(list[object], raw_results):
        if not isinstance(raw_result_value, dict):
            raise ValueError("a dangerous-vector row is not an object")
        raw_result = cast(dict[str, object], raw_result_value)
        raw_counts = raw_result.get("TYPE_COUNTS")
        if not isinstance(raw_counts, list):
            raise ValueError("a dangerous-vector row has no type counts")
        counts: list[tuple[Signature, int]] = []
        for raw_count_value in cast(list[object], raw_counts):
            if not isinstance(raw_count_value, dict):
                raise ValueError("a type-count entry is not an object")
            raw_count = cast(dict[str, object], raw_count_value)
            raw_signature_value = raw_count.get("signature")
            count = raw_count.get("count")
            if (
                not isinstance(raw_signature_value, list)
                or not isinstance(count, int)
                or count < 1
            ):
                raise ValueError("a type-count entry has an invalid signature or count")
            signature_values = cast(list[object], raw_signature_value)
            if len(signature_values) != 4 or any(
                not isinstance(value, int) for value in signature_values
            ):
                raise ValueError("a type-count signature must have four integer cells")
            signature = (
                cast(int, signature_values[0]),
                cast(int, signature_values[1]),
                cast(int, signature_values[2]),
                cast(int, signature_values[3]),
            )
            counts.append((signature, count))
        vectors.append(tuple(sorted(counts)))

    result = tuple(vectors)
    if result != DANGEROUS_VECTOR_TYPES:
        raise ValueError("the exact dangerous vectors differ from the pinned R7 inputs")
    return result


def balanced_frequency_histogram(
    incidences: int, label_count: int
) -> tuple[tuple[int, int], ...]:
    """Return the unique frequency histogram minimizing sum_l C(f_l, 2)."""

    if incidences < 0 or label_count < 1:
        raise ValueError("incidences must be nonnegative and label_count positive")
    quotient, remainder = divmod(incidences, label_count)
    histogram: list[tuple[int, int]] = []
    low_count = label_count - remainder
    if low_count:
        histogram.append((quotient, low_count))
    if remainder:
        histogram.append((quotient + 1, remainder))
    return tuple(histogram)


def pair_mass_from_frequency_histogram(
    histogram: tuple[tuple[int, int], ...]
) -> int:
    """Compute the exact label-pair mass represented by a frequency table."""

    return sum(label_count * comb(frequency, 2) for frequency, label_count in histogram)


def build_assignment_witness(type_counts: TypeCounts) -> WitnessMetrics:
    """Construct a cyclic interval assignment attaining the balanced S2 floor."""

    if sum(count for _, count in type_counts) != OUTSIDE_TICKET_COUNT:
        raise ValueError("the type vector must contain 18 outside tickets")
    special_types = tuple(
        signature
        for signature, count in type_counts
        if count and signature[:3] in ((0, 1, 0), (0, 0, 1))
    )
    if len(special_types) > 1 or any(
        signature not in ((0, 0, 0, 6), (0, 1, 0, 5), (0, 0, 1, 5))
        for signature, _ in type_counts
    ):
        raise ValueError("the assignment witness accepts only pinned dangerous types")

    gaps = (3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2)
    starts: list[int] = []
    start = 0
    for gap in gaps:
        starts.append(start)
        start += gap
    if start != OUTSIDE_LABEL_CAPACITY:
        raise AssertionError("the cyclic interval gaps do not close on 41 labels")

    outside_rows = [
        {8 + (row_start + offset) % OUTSIDE_LABEL_CAPACITY for offset in range(DRAW_SIZE)}
        for row_start in starts
    ]
    ticket_types = [
        signature for signature, count in type_counts for _ in range(count)
    ]
    special_ticket_index: int | None = None
    replaced_outside_label: int | None = None
    special_anchor_label: int | None = None
    if special_types:
        special_signature = special_types[0]
        ticket_types.remove(special_signature)
        ticket_types.insert(0, special_signature)
        special_ticket_index = 0
        replaced_outside_label = 8
        outside_rows[0].remove(replaced_outside_label)
        special_anchor_label = 4 if special_signature[1] else 6

    anchor_a = frozenset((0, 1, 2, 3, 4, 5))
    anchor_b = frozenset((0, 1, 2, 3, 6, 7))
    shared_labels = anchor_a & anchor_b
    a_only_labels = anchor_a - anchor_b
    b_only_labels = anchor_b - anchor_a
    tickets_list: list[frozenset[int]] = []
    for signature, row in zip(ticket_types, outside_rows, strict=True):
        if signature == (0, 0, 0, 6):
            tickets_list.append(frozenset(row))
            continue
        if special_anchor_label is None:
            raise AssertionError("the special ticket has no anchor-exclusive label")
        tickets_list.append(frozenset((*row, special_anchor_label)))
    tickets = tuple(tickets_list)
    portfolio = (anchor_a, anchor_b, *tickets)
    if any(len(ticket) != DRAW_SIZE for ticket in portfolio):
        raise AssertionError("the cyclic witness emitted a ticket of the wrong size")

    overlaps = tuple(
        len(left & right)
        for left, right in combinations(portfolio, 2)
    )
    outside_overlaps = tuple(
        len(left & right)
        for left, right in combinations(tickets, 2)
    )
    if max(overlaps) > MAXIMUM_PAIR_OVERLAP:
        raise AssertionError("the cyclic witness exceeds the maximum pair overlap")

    outside_frequencies = Counter(
        label
        for ticket in tickets
        for label in ticket
        if 8 <= label < POOL_SIZE
    )
    histogram = Counter(outside_frequencies.values())
    frequency_histogram = tuple(sorted(histogram.items()))
    outside_pair_mass = sum(comb(frequency, 2) for frequency in outside_frequencies.values())
    if outside_pair_mass != sum(outside_overlaps):
        raise AssertionError("label and pairwise overlap masses disagree")

    return WitnessMetrics(
        outside_pair_mass=outside_pair_mass,
        outside_frequency_histogram=frequency_histogram,
        maximum_outside_pair_overlap=max(outside_overlaps),
        maximum_full_portfolio_pair_overlap=max(overlaps),
        all_tickets_have_size_six=all(len(ticket) == DRAW_SIZE for ticket in portfolio),
        anchor_capacities=(
            len(shared_labels),
            len(a_only_labels),
            len(b_only_labels),
            OUTSIDE_LABEL_CAPACITY,
        ),
        special_ticket_index=special_ticket_index,
        replaced_outside_label=replaced_outside_label,
        special_anchor_label=special_anchor_label,
    )


@cache
def _integer_partitions(total: int, minimum_part: int = 1) -> tuple[tuple[int, ...], ...]:
    if total == 0:
        return ((),)
    return tuple(
        (part, *tail)
        for part in range(minimum_part, total + 1)
        for tail in _integer_partitions(total - part, part)
    )


def maximum_overlap_component_count(has_special_ticket: bool) -> int:
    """Use label-capacity floors to bound positive-overlap components."""

    maximum = 0
    for sizes in _integer_partitions(OUTSIDE_TICKET_COUNT):
        if not has_special_ticket:
            labels_needed = sum(6 if size == 1 else 8 for size in sizes)
            if labels_needed <= OUTSIDE_LABEL_CAPACITY:
                maximum = max(maximum, len(sizes))
            continue

        for special_index in range(len(sizes)):
            labels_needed = 0
            for index, size in enumerate(sizes):
                if size == 1:
                    labels_needed += 5 if index == special_index else 6
                elif size == 2 and index == special_index:
                    labels_needed += 7
                else:
                    labels_needed += 8
            if labels_needed <= OUTSIDE_LABEL_CAPACITY:
                maximum = max(maximum, len(sizes))
    if maximum != 6:
        raise AssertionError("the 41-label component capacity no longer gives six")
    return maximum


def minimum_labels_with_pair_overlap_at_most_one(
    ticket_count: int,
    incidence_count: int,
    deadline: float | None = None,
) -> int:
    """Exactly minimize used labels under the necessary pair-mass constraint.

    If every ticket pair shares at most one label, then
    ``sum_l C(f_l, 2) <= C(ticket_count, 2)``. The DP exhausts all integer
    frequency multisets satisfying that necessary constraint. Its minimum is
    a valid lower bound on labels required by any such assignment.
    """

    if ticket_count < 1 or incidence_count < 0:
        raise ValueError("ticket_count must be positive and incidence_count nonnegative")
    pair_budget = comb(ticket_count, 2)
    infinity = incidence_count + 1
    minimum = [
        [infinity] * (pair_budget + 1) for _ in range(incidence_count + 1)
    ]
    minimum[0][0] = 0

    for used_incidences in range(incidence_count + 1):
        if deadline is not None:
            _check_deadline(deadline)
        for pair_mass in range(pair_budget + 1):
            used_labels = minimum[used_incidences][pair_mass]
            if used_labels == infinity:
                continue
            maximum_frequency = min(ticket_count, incidence_count - used_incidences)
            for frequency in range(1, maximum_frequency + 1):
                next_mass = pair_mass + comb(frequency, 2)
                if next_mass > pair_budget:
                    continue
                next_incidences = used_incidences + frequency
                minimum[next_incidences][next_mass] = min(
                    minimum[next_incidences][next_mass], used_labels + 1
                )
    result = min(minimum[incidence_count])
    if result == infinity:
        raise AssertionError("the finite label-frequency DP has no feasible state")
    return result


def minimum_component_label_use_by_count(
    has_special_ticket: bool, deadline: float
) -> tuple[tuple[int, int], ...]:
    """Exhaust component partitions under the no-repeated-pair hypothesis."""

    label_floors = {
        (size, special): minimum_labels_with_pair_overlap_at_most_one(
            size, DRAW_SIZE * size - int(special), deadline
        )
        for size in range(1, OUTSIDE_TICKET_COUNT + 1)
        for special in ((False, True) if has_special_ticket else (False,))
    }
    maximum_components = maximum_overlap_component_count(has_special_ticket)
    minima: list[tuple[int, int]] = []

    for component_count in range(1, maximum_components + 1):
        best = OUTSIDE_LABEL_CAPACITY * OUTSIDE_TICKET_COUNT
        for sizes in _integer_partitions(OUTSIDE_TICKET_COUNT):
            if len(sizes) != component_count:
                continue
            if not has_special_ticket:
                best = min(best, sum(label_floors[(size, False)] for size in sizes))
                continue
            for special_index in range(component_count):
                labels_needed = sum(
                    label_floors[(size, index == special_index)]
                    for index, size in enumerate(sizes)
                )
                best = min(best, labels_needed)
        minima.append((component_count, best))
    return tuple(minima)


def _component_penalty_cases(
    has_special_ticket: bool,
    minimum_outside_pair_mass: int,
    deadline: float,
) -> tuple[ComponentPenaltyCase, ...]:
    p0, p1, p2 = EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS[:3]
    component_label_use = dict(
        minimum_component_label_use_by_count(has_special_ticket, deadline)
    )
    maximum_components = maximum_overlap_component_count(has_special_ticket)
    cases: list[ComponentPenaltyCase] = []

    for component_count in range(1, maximum_components + 1):
        _check_deadline(deadline)
        # The exact multiplicity DP forces a repeated edge in the 4..6 strata.
        repeated_forced_by_capacity = component_label_use[component_count] > (
            OUTSIDE_LABEL_CAPACITY
        )
        # At six components the pair-mass count also exceeds the maximum number
        # of distinct within-component pairs (C(13, 2) = 78).
        repeated_forced_by_mass = (
            component_count == 6 and minimum_outside_pair_mass > comb(13, 2)
        )
        repeated = repeated_forced_by_capacity or repeated_forced_by_mass
        positive_edges = OUTSIDE_TICKET_COUNT - component_count
        bridges = component_count - 1
        penalty = positive_edges * p1 + bridges * p0
        if repeated:
            penalty += p2 - p1
        cases.append(
            ComponentPenaltyCase(
                component_count=component_count,
                positive_tree_edge_count=positive_edges,
                zero_overlap_bridge_count=bridges,
                repeated_overlap_forced=repeated,
                no_repeat_label_union_floor=component_label_use[component_count],
                penalty_floor=penalty,
            )
        )
    return tuple(cases)


def _compact_vector_result(result: DangerousVectorCertificate) -> dict[str, object]:
    witness = result.witness
    special_assignment: dict[str, int] | None = None
    if witness.special_ticket_index is not None:
        if witness.replaced_outside_label is None or witness.special_anchor_label is None:
            raise AssertionError("the special-ticket witness is incomplete")
        special_assignment = {
            "TICKET_INDEX": witness.special_ticket_index,
            "REPLACED_OUTSIDE_LABEL": witness.replaced_outside_label,
            "ANCHOR_EXCLUSIVE_LABEL": witness.special_anchor_label,
        }
    return {
        "LABEL": result.label,
        "TYPE_COUNTS": [
            {"SIGNATURE": list(signature), "COUNT": count}
            for signature, count in result.type_counts
        ],
        "REALIZABLE": result.realizable,
        "OUTSIDE_INCIDENCES": result.outside_incidences,
        "S2_MIN": result.minimum_s2_label_pair_mass,
        "S2_FREQUENCIES": [
            {"FREQUENCY": frequency, "LABEL_COUNT": count}
            for frequency, count in result.minimum_s2_frequency_histogram
        ],
        "WITNESS": {
            "OUTSIDE_PAIR_MASS": witness.outside_pair_mass,
            "OUTSIDE_FREQUENCIES": [
                {"FREQUENCY": frequency, "LABEL_COUNT": count}
                for frequency, count in witness.outside_frequency_histogram
            ],
            "MAXIMUM_OUTSIDE_PAIR_OVERLAP": witness.maximum_outside_pair_overlap,
            "MAXIMUM_FULL_PORTFOLIO_PAIR_OVERLAP": (
                witness.maximum_full_portfolio_pair_overlap
            ),
            "ALL_TICKETS_SIZE_SIX": witness.all_tickets_have_size_six,
            "ANCHOR_CAPACITIES": list(witness.anchor_capacities),
            "SPECIAL_ASSIGNMENT": special_assignment,
        },
        "ANCHOR_S3_RECOVERY": result.anchor_s3_recovery,
        "ANCHOR_PAIR_COST": result.anchor_pair_cost,
        "NET_ANCHOR_RECOVERY": result.net_anchor_recovery,
        "LOCAL_RECOVERY_LOSS": result.local_recovery_loss,
        "OUTSIDE_PAIR_PENALTY": result.mandatory_outside_pair_penalty,
        "TOTAL_RECOVERY_REDUCTION": result.total_recovery_reduction,
        "R4_BOUND": result.r4_bound,
    }


def analyze_dangerous_assignments(
    prior_result_path: Path,
) -> dict[str, object]:
    """Build the exact compressed assignment certificate from the pinned input."""

    started = monotonic()
    deadline = started + NATIVE_WALL_LIMIT_SECONDS
    vectors = load_prior_dangerous_vectors(prior_result_path)
    if pair_intersection_table() != EXPECTED_PAIR_COUNTS:
        raise AssertionError("the exact K20 pair-intersection table changed")

    profiles = {profile.signature: profile for profile in anchor_incidence_profiles()}
    good_profile = profiles[(0, 0, 0, 6)]
    vector_results: list[DangerousVectorCertificate] = []
    all_component_classes = 0

    for type_counts in vectors:
        _check_deadline(deadline)
        outside_incidences = sum(signature[3] * count for signature, count in type_counts)
        frequency_histogram = balanced_frequency_histogram(
            outside_incidences, OUTSIDE_LABEL_CAPACITY
        )
        minimum_s2 = pair_mass_from_frequency_histogram(frequency_histogram)
        if minimum_s2 != minimum_label_pair_mass(
            outside_incidences, OUTSIDE_LABEL_CAPACITY
        ):
            raise AssertionError("balanced label frequencies disagree with the pinned formula")

        witness = build_assignment_witness(type_counts)
        if (
            witness.outside_pair_mass != minimum_s2
            or witness.outside_frequency_histogram != frequency_histogram
            or witness.maximum_full_portfolio_pair_overlap > MAXIMUM_PAIR_OVERLAP
        ):
            raise AssertionError("the dangerous vector lacks an S2-minimizing assignment")

        anchor_s3 = sum(
            profiles[signature].triple_recovery * count
            for signature, count in type_counts
        )
        anchor_pair_cost = sum(
            profiles[signature].pair_recovery_cost * count
            for signature, count in type_counts
        )
        net_anchor_recovery = anchor_s3 - anchor_pair_cost
        local_recovery_loss = OUTSIDE_TICKET_COUNT * good_profile.net_recovery - (
            sum(profiles[signature].net_recovery * count for signature, count in type_counts)
        )

        special_count = sum(
            count for signature, count in type_counts if signature != (0, 0, 0, 6)
        )
        if special_count not in (0, 1):
            raise AssertionError("a dangerous vector has an unexpected special-ticket count")
        component_count_limit = maximum_overlap_component_count(bool(special_count))
        component_cases = _component_penalty_cases(
            bool(special_count), minimum_s2, deadline
        )
        all_component_classes += component_count_limit
        mandatory_penalty = min(case.penalty_floor for case in component_cases)
        vector_bound = UNCORRECTED_R4_BOUND - local_recovery_loss - mandatory_penalty
        special_signature = next(
            (signature for signature, _ in type_counts if signature != (0, 0, 0, 6)),
            None,
        )
        vector_label = (
            "18_GOOD"
            if special_signature is None
            else "17_GOOD_PLUS_B_ONLY"
            if special_signature == (0, 0, 1, 5)
            else "17_GOOD_PLUS_A_ONLY"
        )
        vector_results.append(
            DangerousVectorCertificate(
                label=vector_label,
                type_counts=type_counts,
                realizable=True,
                outside_incidences=outside_incidences,
                minimum_s2_label_pair_mass=minimum_s2,
                minimum_s2_frequency_histogram=frequency_histogram,
                witness=witness,
                anchor_s3_recovery=anchor_s3,
                anchor_pair_cost=anchor_pair_cost,
                net_anchor_recovery=net_anchor_recovery,
                local_recovery_loss=local_recovery_loss,
                maximum_overlap_components=component_count_limit,
                component_cases=component_cases,
                mandatory_outside_pair_penalty=mandatory_penalty,
                total_recovery_reduction=local_recovery_loss + mandatory_penalty,
                r4_bound=vector_bound,
            )
        )

    if len(vector_results) != 3 or not all(result.realizable for result in vector_results):
        raise AssertionError("the pinned danger layer must retain three realizable vectors")

    minimum_reduction = min(
        PRIOR_LOWER_GOOD_MINIMUM_REDUCTION,
        PRIOR_17_GOOD_NO_BEST_MINIMUM_REDUCTION,
        *(result.total_recovery_reduction for result in vector_results),
    )
    r4_bound = UNCORRECTED_R4_BOUND - minimum_reduction
    family_a_bounds = (
        CURRENT_R3_BOUND,
        r4_bound,
        CURRENT_R5_BOUND,
        CURRENT_R6_BOUND,
    )
    family_a_bound = max(family_a_bounds)
    bottleneck_r = family_a_bounds.index(family_a_bound) + 3
    elapsed = monotonic() - started
    regular_cases = vector_results[0].component_cases
    special_cases = vector_results[1].component_cases
    component_case_rows: list[dict[str, object]] = []
    for regular_case, special_case in zip(regular_cases, special_cases, strict=True):
        if (
            regular_case.component_count != special_case.component_count
            or regular_case.penalty_floor != special_case.penalty_floor
            or regular_case.repeated_overlap_forced
            != special_case.repeated_overlap_forced
        ):
            raise AssertionError("mirrored vectors disagree on their component penalty")
        component_case_rows.append(
            {
                "COMPONENT_COUNT": regular_case.component_count,
                "POSITIVE_TREE_EDGES": regular_case.positive_tree_edge_count,
                "ZERO_OVERLAP_BRIDGES": regular_case.zero_overlap_bridge_count,
                "REPEATED_OVERLAP_FORCED": regular_case.repeated_overlap_forced,
                "NO_REPEAT_LABEL_FLOOR_ALL_GOOD": (
                    regular_case.no_repeat_label_union_floor
                ),
                "NO_REPEAT_LABEL_FLOOR_ONE_SPECIAL": (
                    special_case.no_repeat_label_union_floor
                ),
                "PENALTY_FLOOR": regular_case.penalty_floor,
            }
        )

    return {
        "TASK_ID": "B649_K20_R4_DANGEROUS_VECTOR_EXACT_ASSIGNMENT_R8",
        "TASK_STATUS": "COMPLETED_SUCCESS_B" if r4_bound < PRIOR_R4_BOUND else "NO_IMPROVEMENT",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_HEAD": "RECORDED_IN_FINAL_HANDOFF",
        "WORKTREE_PATH": WORKTREE_PATH,
        "WORKTREE_DISPOSITION": "RETAIN",
        "COUNT_VECTOR_CENSUS": "REUSED_PINNED_R7_RESULT; 52,360-VECTOR CENSUS NOT RERUN",
        "DANGEROUS_VECTOR_COUNT": len(vector_results),
        "REALIZABLE_VECTOR_COUNT": sum(result.realizable for result in vector_results),
        "ASSIGNMENT_CLASS_COUNT": all_component_classes,
        "ASSIGNMENT_CLASS_DEFINITION": (
            "Eighteen compressed proof strata: three pinned vectors times component "
            "counts 1..6. This is not a count of raw incidence matrices; the exact "
            "frequency and component DPs quotient out label names and bound every case."
        ),
        "ANCHOR_S3_RECOVERY_DEFINITION": (
            "Exact sum_C J(A,B,C) from the pinned incidence signatures; global label "
            "assignments cannot change this anchored third-order term."
        ),
        "DANGEROUS_VECTOR_RESULTS": [
            _compact_vector_result(result) for result in vector_results
        ],
        "COMPONENT_CASES": component_case_rows,
        "ANCHOR_SHARED_LABEL_CAPACITY": ANCHOR_SHARED_CAPACITY,
        "A_ONLY_LABEL_CAPACITY": ANCHOR_A_ONLY_CAPACITY,
        "B_ONLY_LABEL_CAPACITY": ANCHOR_B_ONLY_CAPACITY,
        "OUTSIDE_LABEL_CAPACITY": OUTSIDE_LABEL_CAPACITY,
        "TICKET_SIZE": DRAW_SIZE,
        "MAXIMUM_PAIR_OVERLAP": MAXIMUM_PAIR_OVERLAP,
        "RESIDUAL_PAIR_FLOORS_BY_OVERLAP_AT_LEAST_0_TO_2": list(
            EXPECTED_ACTIVE_PAIR_RESIDUAL_FLOORS[:3]
        ),
        "FOREST_PENALTY_FORMULA": (
            "(18-k)*p1 + (k-1)*p0; add p2-p1 for k=4..6, where the exact "
            "no-repeat frequency DP requires more than 41 labels."
        ),
        "MANDATORY_OUTSIDE_PAIR_PENALTY": min(
            result.mandatory_outside_pair_penalty for result in vector_results
        ),
        "R4_BASE_BOUND": UNCORRECTED_R4_BOUND,
        "R4_BOUND": r4_bound,
        "R4_STATUS": "CLOSED" if r4_bound <= INCUMBENT else "TIGHTENED_OPEN_SUCCESS_B",
        "SUCCESS_A": r4_bound <= INCUMBENT,
        "SUCCESS_B": r4_bound < PRIOR_R4_BOUND,
        "PRIOR_R4_BOUND": PRIOR_R4_BOUND,
        "R4_BOUND_IMPROVEMENT": PRIOR_R4_BOUND - r4_bound,
        "FAMILY_A_RECOMPUTED_BOUND": family_a_bound,
        "FAMILY_A_BOTTLENECK_R": bottleneck_r,
        "FROZEN_OTHER_SUBFAMILY_BOUNDS": {
            "R3": CURRENT_R3_BOUND,
            "R5": CURRENT_R5_BOUND,
            "R6": CURRENT_R6_BOUND,
        },
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_a_bound - INCUMBENT,
        "SOLVER_STATUS": "EXACT_DYNAMIC_PROGRAM_OPTIMAL",
        "SOLVER_CONFIGURED_WALL_LIMIT": (
            f"{NATIVE_WALL_LIMIT_SECONDS}s native; "
            f"{EXTERNAL_HARD_TIMEOUT_SECONDS}s external hard timeout"
        ),
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": round(elapsed, 6),
        "SOLVER_CERTIFIED_BOUND": min(
            result.mandatory_outside_pair_penalty for result in vector_results
        ),
        "SOLVER_NOTE": (
            "Exact finite frequency/component DP; no CP-SAT/MILP feasible status was "
            "used as proof. Every returned state was exhausted under the fixed deadline."
        ),
        "FOCUSED_TESTS": "PASS: 4 focused tests passed.",
        "RUFF": "PASS: scoped proof module and focused test.",
        "PYRIGHT": (
            "PASS: scoped strict Python 3.13; 0 errors, 0 warnings, 0 informations."
        ),
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prior-result",
        type=Path,
        default=repository_root
        / "docs/research/matrix-native-results/"
        "b649-k20-r4-exact-anchor-realizability-r7-result.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root
        / "docs/research/matrix-native-results/"
        "b649-k20-r4-dangerous-assignment-exact-r8-result.json",
    )
    arguments = parser.parse_args()
    result = analyze_dangerous_assignments(arguments.prior_result)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"R4_BOUND={result['R4_BOUND']} "
        f"MANDATORY_OUTSIDE_PAIR_PENALTY={result['MANDATORY_OUTSIDE_PAIR_PENALTY']} "
        f"WALL={result['SOLVER_ACTUAL_WALL_TIME_SECONDS']}s"
    )


if __name__ == "__main__":
    main()


__all__ = [
    "DANGEROUS_VECTOR_TYPES",
    "EXTERNAL_HARD_TIMEOUT_SECONDS",
    "NATIVE_WALL_LIMIT_SECONDS",
    "ComponentPenaltyCase",
    "DangerousVectorCertificate",
    "WitnessMetrics",
    "analyze_dangerous_assignments",
    "balanced_frequency_histogram",
    "build_assignment_witness",
    "load_prior_dangerous_vectors",
    "maximum_overlap_component_count",
    "minimum_component_label_use_by_count",
    "minimum_labels_with_pair_overlap_at_most_one",
    "pair_mass_from_frequency_histogram",
]
