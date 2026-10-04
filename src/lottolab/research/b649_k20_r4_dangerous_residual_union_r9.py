"""Joint residual-event union bounds for the three pinned K20 r=4 vectors.

The calculation reloads R7's exact danger vectors and R8's 18 compressed
assignment strata. It never runs the count-vector census or searches full
portfolios. A finite overlap-mass DP jointly bounds residual S1/S2/S3 and the
union after conditioning on the exact r=4 anchor pair.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    ANCHOR_OVERLAP,
    DRAW_SIZE,
    EXPECTED_SINGLE_TICKET_OUTCOMES,
    OUTSIDE_LABEL_CAPACITY,
    OUTSIDE_TICKET_COUNT,
    anchor_incidence_profiles,
    exact_residual_pair_intersection,
    pair_intersection_table,
)
from lottolab.research.b649_k20_r4_dangerous_assignment_exact_r8 import (
    CURRENT_R3_BOUND,
    CURRENT_R5_BOUND,
    CURRENT_R6_BOUND,
    DANGEROUS_VECTOR_TYPES,
    INCUMBENT,
    MAXIMUM_PAIR_OVERLAP,
    PRIOR_R4_BOUND,
    balanced_frequency_histogram,
    build_assignment_witness,
    load_prior_dangerous_vectors,
    pair_mass_from_frequency_histogram,
)

BASE_HEAD = "726ca446f7ab521740ef9e8b41b29fe561af89cc"
BASE_TREE = "a180363a33f51bc3b1f62a5665c4878825f2d652"
TASK_BRANCH = "codex/b649-k20-r4-dangerous-realization-residual-union-r9"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_R4_DANGEROUS_REALIZATION_RESIDUAL_UNION_R9"
)

NATIVE_WALL_LIMIT_SECONDS = 45
EXTERNAL_HARD_TIMEOUT_SECONDS = 60
COMPONENT_COUNTS = tuple(range(1, 7))
EXPECTED_DANGEROUS_VECTOR_COUNT = 3
EXPECTED_RESIDUAL_CLASS_COUNT = 18
EXPECTED_OUTSIDE_PAIR_MASS_FLOORS = (93, 91, 91)
EXPECTED_R8_VECTOR_BOUNDS = (354_332_314, 353_896_214, 353_896_214)
COMPRESSED_ASSIGNMENT_CLASS_COLUMNS = (
    "VECTOR_LABEL",
    "COMPONENT_COUNT",
    "OUTSIDE_INCIDENCES",
    "OUTSIDE_PAIR_MASS_FLOOR",
    "COMPONENT_POSITIVE_EDGE_FLOOR",
    "MASS_POSITIVE_EDGE_FLOOR",
    "RESIDUAL_S1",
    "RESIDUAL_S2_BOUND",
    "RESIDUAL_S3_BOUND",
    "MAXIMUM_RESIDUAL_EVENT_MULTIPLICITY_AT_FLOOR",
    "JOINT_UNION_REDUCTION",
    "JOINT_UNION_REDUCTION_AT_OUTSIDE_PAIR_MASS",
    "RESIDUAL_UNION_BOUND",
    "ANCHOR_UNION",
    "R4_BOUND",
)
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
type PairCostRows = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class ResidualMassEnvelope:
    """Exact finite-DP envelope indexed by outside label-pair mass."""

    minimum_s2_by_mass: tuple[int, ...]
    maximum_s2_by_mass: tuple[int, ...]
    union_reduction: int
    union_reduction_mass: int
    maximum_s3: int
    maximum_s3_mass: int
    maximum_multiplicity_at_floor: int
    maximum_mass: int


@dataclass(frozen=True)
class ResidualClassBound:
    """Joint residual-event certificate for one vector/component stratum."""

    vector_label: str
    type_counts: TypeCounts
    component_count: int
    outside_incidences: int
    outside_pair_mass_floor: int
    residual_s1: int
    residual_s2_bound: int
    residual_s3_bound: int
    residual_event_multiplicity_cap_at_floor: int
    joint_union_reduction: int
    joint_union_reduction_mass: int
    residual_union_bound: int
    anchor_union: int
    r4_bound: int
    component_positive_edge_floor: int
    mass_positive_edge_floor: int


def _check_deadline(deadline: float) -> None:
    if monotonic() > deadline:
        raise TimeoutError("the residual-union DP exceeded its native wall limit")


def _parse_type_counts(value: object) -> TypeCounts:
    if not isinstance(value, list):
        raise ValueError("a dangerous-vector type-count field is not a list")
    parsed: list[tuple[Signature, int]] = []
    for raw_entry_value in cast(list[object], value):
        if not isinstance(raw_entry_value, dict):
            raise ValueError("a dangerous-vector type-count entry is not an object")
        raw_entry = cast(dict[str, object], raw_entry_value)
        raw_signature_value = raw_entry.get("SIGNATURE")
        count = raw_entry.get("COUNT")
        if (
            not isinstance(raw_signature_value, list)
            or type(count) is not int
            or count < 1
        ):
            raise ValueError("a dangerous-vector type-count entry is invalid")
        signature_values = cast(list[object], raw_signature_value)
        if len(signature_values) != 4 or any(type(cell) is not int for cell in signature_values):
            raise ValueError("a dangerous-vector signature must have four integer cells")
        signature = cast(
            Signature,
            tuple(cast(int, cell) for cell in signature_values),
        )
        parsed.append((signature, count))
    return tuple(sorted(parsed))


def _vector_label(type_counts: TypeCounts) -> str:
    special = tuple(
        signature
        for signature, count in type_counts
        if count and signature != (0, 0, 0, 6)
    )
    if not special:
        return "18_GOOD"
    if special == ((0, 0, 1, 5),):
        return "17_GOOD_PLUS_B_ONLY"
    if special == ((0, 1, 0, 5),):
        return "17_GOOD_PLUS_A_ONLY"
    raise ValueError("the pinned dangerous-vector type is not recognized")


def load_compressed_assignment_classes(
    r7_result_path: Path,
    r8_result_path: Path,
) -> tuple[tuple[TypeCounts, int], ...]:
    """Reload only R7's danger vectors and R8's certified component strata."""

    vectors = load_prior_dangerous_vectors(r7_result_path)
    if vectors != DANGEROUS_VECTOR_TYPES:
        raise ValueError("the pinned R7 danger-vector identities changed")

    loaded_document = json.loads(r8_result_path.read_text(encoding="utf-8"))
    if not isinstance(loaded_document, dict):
        raise ValueError("the pinned R8 result must be a JSON object")
    document = cast(dict[str, object], loaded_document)
    if (
        document.get("TASK_ID") != "B649_K20_R4_DANGEROUS_VECTOR_EXACT_ASSIGNMENT_R8"
        or document.get("TASK_STATUS") != "COMPLETED_SUCCESS_B"
        or document.get("COUNT_VECTOR_CENSUS")
        != "REUSED_PINNED_R7_RESULT; 52,360-VECTOR CENSUS NOT RERUN"
        or document.get("DANGEROUS_VECTOR_COUNT")
        != EXPECTED_DANGEROUS_VECTOR_COUNT
        or document.get("REALIZABLE_VECTOR_COUNT") != EXPECTED_DANGEROUS_VECTOR_COUNT
        or document.get("ASSIGNMENT_CLASS_COUNT") != EXPECTED_RESIDUAL_CLASS_COUNT
    ):
        raise ValueError("the pinned R8 danger layer or compressed class count changed")

    raw_results = document.get("DANGEROUS_VECTOR_RESULTS")
    if not isinstance(raw_results, list):
        raise ValueError("the pinned R8 result has no dangerous-vector rows")
    results = cast(list[object], raw_results)
    if len(results) != EXPECTED_DANGEROUS_VECTOR_COUNT:
        raise ValueError("the pinned R8 result does not have exactly three vectors")
    loaded_types: list[TypeCounts] = []
    for raw_result_value in results:
        if not isinstance(raw_result_value, dict):
            raise ValueError("a pinned R8 dangerous-vector row is not an object")
        raw_result = cast(dict[str, object], raw_result_value)
        type_counts = _parse_type_counts(raw_result.get("TYPE_COUNTS"))
        witness_value = raw_result.get("WITNESS")
        if not isinstance(witness_value, dict):
            raise ValueError("a pinned R8 vector has no assignment witness")
        witness = cast(dict[str, object], witness_value)
        maximum_overlap = witness.get("MAXIMUM_FULL_PORTFOLIO_PAIR_OVERLAP")
        if (
            raw_result.get("REALIZABLE") is not True
            or raw_result.get("LABEL") != _vector_label(type_counts)
            or type_counts not in vectors
            or type(maximum_overlap) is not int
            or maximum_overlap > MAXIMUM_PAIR_OVERLAP
        ):
            raise ValueError("a pinned R8 vector row no longer certifies realizability")
        loaded_types.append(type_counts)
    if tuple(loaded_types) != vectors:
        raise ValueError("R7 and R8 dangerous-vector identities are out of order")

    raw_component_cases = document.get("COMPONENT_CASES")
    if not isinstance(raw_component_cases, list):
        raise ValueError("the pinned R8 result has no component strata")
    component_cases = cast(list[object], raw_component_cases)
    component_counts: list[int] = []
    for raw_case_value in component_cases:
        if not isinstance(raw_case_value, dict):
            raise ValueError("a pinned R8 component case is not an object")
        raw_case = cast(dict[str, object], raw_case_value)
        component_count = raw_case.get("COMPONENT_COUNT")
        if type(component_count) is not int:
            raise ValueError("a pinned R8 component count is not an integer")
        component_counts.append(component_count)
    if tuple(component_counts) != COMPONENT_COUNTS:
        raise ValueError("the pinned R8 component strata are not exactly 1..6")

    raw_bounds = tuple(
        cast(dict[str, object], row).get("R4_BOUND") for row in results
    )
    if any(type(bound) is not int for bound in raw_bounds):
        raise ValueError("a pinned R8 vector bound is not an integer")
    r8_bounds = tuple(cast(int, bound) for bound in raw_bounds)
    if r8_bounds != EXPECTED_R8_VECTOR_BOUNDS:
        raise ValueError("the pinned R8 per-vector bounds changed")

    classes = tuple(
        (type_counts, component_count)
        for type_counts in vectors
        for component_count in component_counts
    )
    if len(classes) != EXPECTED_RESIDUAL_CLASS_COUNT:
        raise AssertionError("the exact compressed R8 strata did not expand to 18 classes")
    return classes


def minimum_pair_mass_for_incidences(incidences: int, label_count: int) -> int:
    """Convexity floor for ``sum_l C(f_l, 2)`` at fixed incidence total."""

    if incidences < 0 or label_count < 1:
        raise ValueError("incidences must be nonnegative and labels positive")
    quotient, remainder = divmod(incidences, label_count)
    return (label_count - remainder) * comb(quotient, 2) + remainder * comb(
        quotient + 1, 2
    )


def minimum_pair_mass_for_residual_multiplicity(
    winning_ticket_count: int,
) -> int:
    """Lower-bound outside label-pair mass for a draw with ``k`` residual wins.

    ``r`` tickets may use the special-number rescue and need only two main hits;
    the other tickets need at least three. Six main-draw labels distribute the
    resulting incidences, while the special label contributes ``C(r, 2)``.
    """

    if not 1 <= winning_ticket_count <= OUTSIDE_TICKET_COUNT:
        raise ValueError("winning ticket count must be within the outside-ticket range")
    return min(
        minimum_pair_mass_for_incidences(3 * winning_ticket_count - rescued, DRAW_SIZE)
        + comb(rescued, 2)
        for rescued in range(winning_ticket_count + 1)
    )


def maximum_residual_multiplicity(outside_pair_mass: int) -> int:
    """Maximum simultaneous residual wins allowed by the pair-mass budget."""

    if outside_pair_mass < 0:
        raise ValueError("outside pair mass must be nonnegative")
    feasible = tuple(
        winning_count
        for winning_count in range(1, OUTSIDE_TICKET_COUNT + 1)
        if minimum_pair_mass_for_residual_multiplicity(winning_count)
        <= outside_pair_mass
    )
    return max(feasible, default=0)


def _ticket_types(type_counts: TypeCounts) -> tuple[Signature, ...]:
    tickets = tuple(
        signature for signature, count in type_counts for _ in range(count)
    )
    if len(tickets) != OUTSIDE_TICKET_COUNT:
        raise ValueError("a dangerous vector must contain 18 outside tickets")
    return tickets


def residual_pair_cost_rows(type_counts: TypeCounts) -> PairCostRows:
    """Return exact ``|R_C intersect R_D|`` costs for outside overlap 0..4."""

    rows = tuple(
        tuple(
            exact_residual_pair_intersection(
                left,
                right,
                (0, 0, 0, outside_overlap),
            )
            for outside_overlap in range(MAXIMUM_PAIR_OVERLAP + 1)
        )
        for left, right in combinations(_ticket_types(type_counts), 2)
    )
    if len(rows) != comb(OUTSIDE_TICKET_COUNT, 2):
        raise AssertionError("the residual-pair table is missing ticket pairs")
    if any(
        costs[overlap] < costs[overlap - 1]
        for costs in rows
        for overlap in range(1, len(costs))
    ):
        raise AssertionError("residual pair intersections must increase with overlap")
    return rows


def _residual_pair_mass_dp(
    pair_cost_rows: PairCostRows,
    maximum_mass: int,
    deadline: float,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Exhaust exact pair-overlap masses and return min/max residual S2."""

    minimum: list[int | None] = [None] * (maximum_mass + 1)
    maximum: list[int | None] = [None] * (maximum_mass + 1)
    minimum[0] = 0
    maximum[0] = 0
    reachable_mass = 0

    for pair_costs in pair_cost_rows:
        _check_deadline(deadline)
        next_minimum: list[int | None] = [None] * (maximum_mass + 1)
        next_maximum: list[int | None] = [None] * (maximum_mass + 1)
        for mass in range(min(reachable_mass, maximum_mass) + 1):
            minimum_cost = minimum[mass]
            maximum_cost = maximum[mass]
            for overlap, pair_cost in enumerate(pair_costs):
                next_mass = mass + overlap
                if next_mass > maximum_mass:
                    continue
                if minimum_cost is not None:
                    candidate_minimum = minimum_cost + pair_cost
                    prior_minimum = next_minimum[next_mass]
                    if prior_minimum is None or candidate_minimum < prior_minimum:
                        next_minimum[next_mass] = candidate_minimum
                if maximum_cost is not None:
                    candidate_maximum = maximum_cost + pair_cost
                    prior_maximum = next_maximum[next_mass]
                    if prior_maximum is None or candidate_maximum > prior_maximum:
                        next_maximum[next_mass] = candidate_maximum
        minimum, maximum = next_minimum, next_maximum
        reachable_mass = min(maximum_mass, reachable_mass + MAXIMUM_PAIR_OVERLAP)

    if any(value is None for value in minimum) or any(value is None for value in maximum):
        raise AssertionError("the finite overlap-mass DP did not cover its full range")
    return (
        tuple(cast(int, value) for value in minimum),
        tuple(cast(int, value) for value in maximum),
    )


def _ceil_div(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator < 1:
        raise ValueError("ceil division requires a nonnegative numerator and positive divisor")
    return (numerator + denominator - 1) // denominator


def joint_residual_union_upper_bound(
    residual_s1: int,
    residual_s2_lower_bound: int,
    multiplicity_cap: int,
) -> int:
    """Use a pointwise multiplicity inequality to bound a residual union."""

    if residual_s1 < 0 or residual_s2_lower_bound < 0 or multiplicity_cap < 1:
        raise ValueError("residual moments and multiplicity cap must be nonnegative")
    return residual_s1 - _ceil_div(2 * residual_s2_lower_bound, multiplicity_cap)


def residual_s3_upper_bound(
    residual_s2_upper_bound: int,
    multiplicity_cap: int,
) -> int:
    """Bound residual S3 jointly from S2 and the maximum outcome multiplicity."""

    if residual_s2_upper_bound < 0 or multiplicity_cap < 1:
        raise ValueError("residual pair bound and multiplicity cap must be valid")
    if multiplicity_cap < 3:
        return 0
    return (multiplicity_cap - 2) * residual_s2_upper_bound // 3


def _residual_s1(
    type_counts: TypeCounts,
    pair_counts: tuple[int, ...],
) -> int:
    """Compute exact residual S1 from anchor-pair inclusion-exclusion."""

    profiles = {profile.signature: profile for profile in anchor_incidence_profiles()}
    total = 0
    for signature, count in type_counts:
        profile = profiles[signature]
        residual_ticket_events = (
            EXPECTED_SINGLE_TICKET_OUTCOMES
            - pair_counts[profile.overlap_with_a]
            - pair_counts[profile.overlap_with_b]
            + profile.triple_recovery
        )
        total += count * residual_ticket_events
    return total


def _mass_envelope(
    type_counts: TypeCounts,
    outside_pair_mass_floor: int,
    deadline: float,
) -> ResidualMassEnvelope:
    maximum_mass = MAXIMUM_PAIR_OVERLAP * comb(OUTSIDE_TICKET_COUNT, 2)
    rows = residual_pair_cost_rows(type_counts)
    minimum_s2, maximum_s2 = _residual_pair_mass_dp(rows, maximum_mass, deadline)
    best_reduction: int | None = None
    best_mass: int | None = None
    maximum_s3 = 0
    maximum_s3_mass: int | None = None

    for outside_pair_mass in range(outside_pair_mass_floor, maximum_mass + 1):
        _check_deadline(deadline)
        simultaneous_wins = maximum_residual_multiplicity(outside_pair_mass)
        if simultaneous_wins < 1:
            raise AssertionError("a nonempty dangerous assignment has no feasible residual win")
        minimum_s2_at_mass = minimum_s2[outside_pair_mass]
        maximum_s2_at_mass = maximum_s2[outside_pair_mass]
        reduction = _ceil_div(2 * minimum_s2_at_mass, simultaneous_wins)
        if best_reduction is None or reduction < best_reduction:
            best_reduction = reduction
            best_mass = outside_pair_mass

        s3_at_mass = residual_s3_upper_bound(
            maximum_s2_at_mass,
            simultaneous_wins,
        )
        if s3_at_mass > maximum_s3:
            maximum_s3 = s3_at_mass
            maximum_s3_mass = outside_pair_mass

    if best_reduction is None or best_mass is None or maximum_s3_mass is None:
        raise AssertionError("the residual mass scan did not visit a feasible state")
    return ResidualMassEnvelope(
        minimum_s2_by_mass=minimum_s2,
        maximum_s2_by_mass=maximum_s2,
        union_reduction=best_reduction,
        union_reduction_mass=best_mass,
        maximum_s3=maximum_s3,
        maximum_s3_mass=maximum_s3_mass,
        maximum_multiplicity_at_floor=maximum_residual_multiplicity(
            outside_pair_mass_floor
        ),
        maximum_mass=maximum_mass,
    )


def _serialize_type_counts(type_counts: TypeCounts) -> list[dict[str, object]]:
    return [
        {"SIGNATURE": list(signature), "COUNT": count}
        for signature, count in type_counts
    ]


def analyze_dangerous_residual_union(
    r7_result_path: Path,
    r8_result_path: Path,
) -> dict[str, object]:
    """Build the exact compressed residual-union certificate."""

    started = monotonic()
    deadline = started + NATIVE_WALL_LIMIT_SECONDS
    classes = load_compressed_assignment_classes(r7_result_path, r8_result_path)
    if pair_intersection_table() != EXPECTED_PAIR_COUNTS:
        raise AssertionError("the pinned exact ticket pair table changed")

    pair_counts = pair_intersection_table()
    anchor_union = (
        2 * EXPECTED_SINGLE_TICKET_OUTCOMES - pair_counts[ANCHOR_OVERLAP]
    )
    vector_types = tuple(dict.fromkeys(type_counts for type_counts, _ in classes))
    if vector_types != DANGEROUS_VECTOR_TYPES:
        raise AssertionError("the 18 strata do not contain exactly the three R7 vectors")

    vector_metrics: dict[TypeCounts, dict[str, object]] = {}
    class_rows: list[ResidualClassBound] = []
    vector_labels: dict[TypeCounts, str] = {}
    for vector_index, type_counts in enumerate(vector_types):
        _check_deadline(deadline)
        label = _vector_label(type_counts)
        vector_labels[type_counts] = label
        witness = build_assignment_witness(type_counts)
        incidences = sum(signature[3] * count for signature, count in type_counts)
        frequency_histogram = balanced_frequency_histogram(
            incidences, OUTSIDE_LABEL_CAPACITY
        )
        outside_pair_mass_floor = pair_mass_from_frequency_histogram(
            frequency_histogram
        )
        if outside_pair_mass_floor != EXPECTED_OUTSIDE_PAIR_MASS_FLOORS[vector_index]:
            raise AssertionError("the exact outside-label pair-mass floor changed")
        if (
            witness.outside_pair_mass != outside_pair_mass_floor
            or witness.maximum_full_portfolio_pair_overlap > MAXIMUM_PAIR_OVERLAP
        ):
            raise AssertionError("the pinned realizability witness no longer checks")

        residual_s1 = _residual_s1(type_counts, pair_counts)
        envelope = _mass_envelope(type_counts, outside_pair_mass_floor, deadline)
        minimum_positive_edges = _ceil_div(
            outside_pair_mass_floor, MAXIMUM_PAIR_OVERLAP
        )
        vector_classes: list[ResidualClassBound] = []
        for _, component_count in (
            row for row in classes if row[0] == type_counts
        ):
            component_positive_edge_floor = OUTSIDE_TICKET_COUNT - component_count
            if minimum_positive_edges < component_positive_edge_floor:
                raise AssertionError(
                    "the pair-mass floor no longer covers the component edge floor"
                )
            residual_union_bound = joint_residual_union_upper_bound(
                residual_s1,
                envelope.minimum_s2_by_mass[envelope.union_reduction_mass],
                maximum_residual_multiplicity(envelope.union_reduction_mass),
            )
            if residual_s1 - residual_union_bound != envelope.union_reduction:
                raise AssertionError("the mass-scan minimum is not the class envelope")
            r4_bound = anchor_union + residual_union_bound
            vector_class = ResidualClassBound(
                vector_label=label,
                type_counts=type_counts,
                component_count=component_count,
                outside_incidences=incidences,
                outside_pair_mass_floor=outside_pair_mass_floor,
                residual_s1=residual_s1,
                residual_s2_bound=envelope.minimum_s2_by_mass[
                    outside_pair_mass_floor
                ],
                residual_s3_bound=envelope.maximum_s3,
                residual_event_multiplicity_cap_at_floor=(
                    envelope.maximum_multiplicity_at_floor
                ),
                joint_union_reduction=envelope.union_reduction,
                joint_union_reduction_mass=envelope.union_reduction_mass,
                residual_union_bound=residual_union_bound,
                anchor_union=anchor_union,
                r4_bound=r4_bound,
                component_positive_edge_floor=component_positive_edge_floor,
                mass_positive_edge_floor=minimum_positive_edges,
            )
            vector_classes.append(vector_class)
            class_rows.append(vector_class)

        vector_metrics[type_counts] = {
            "LABEL": label,
            "TYPE_COUNTS": _serialize_type_counts(type_counts),
            "REALIZABLE": True,
            "OUTSIDE_INCIDENCES": incidences,
            "OUTSIDE_PAIR_MASS_FLOOR": outside_pair_mass_floor,
            "OUTSIDE_PAIR_FREQUENCIES": [
                {"FREQUENCY": frequency, "LABEL_COUNT": count}
                for frequency, count in frequency_histogram
            ],
            "RESIDUAL_S1": residual_s1,
            "RESIDUAL_S2_BOUND": envelope.minimum_s2_by_mass[
                outside_pair_mass_floor
            ],
            "RESIDUAL_S3_BOUND": envelope.maximum_s3,
            "RESIDUAL_S3_BOUND_AT_MASS": envelope.maximum_s3_mass,
            "RESIDUAL_S3_RELATION": (
                "For each exact outside pair mass M, S3 <= "
                "floor((K(M)-2)*S2_max(M)/3), from "
                "C(m,3) <= (K(M)-2)*C(m,2)/3."
            ),
            "MAXIMUM_RESIDUAL_EVENT_MULTIPLICITY_AT_FLOOR": (
                envelope.maximum_multiplicity_at_floor
            ),
            "MINIMUM_JOINT_UNION_REDUCTION": envelope.union_reduction,
            "JOINT_UNION_REDUCTION_AT_OUTSIDE_PAIR_MASS": (
                envelope.union_reduction_mass
            ),
            "RESIDUAL_UNION_BOUND": vector_classes[0].residual_union_bound,
            "ANCHOR_UNION": anchor_union,
            "R4_BOUND": max(row.r4_bound for row in vector_classes),
            "OUTSIDE_PAIR_MASS_SCAN": {
                "FIRST": outside_pair_mass_floor,
                "LAST": envelope.maximum_mass,
                "MASS_COUNT": envelope.maximum_mass - outside_pair_mass_floor + 1,
                "JOINT_REDUCTION_MINIMUM_AT": envelope.union_reduction_mass,
                "JOINT_REDUCTION_MINIMUM": envelope.union_reduction,
                "MAXIMUM_S3_BOUND_AT": envelope.maximum_s3_mass,
                "MAXIMUM_S3_BOUND": envelope.maximum_s3,
            },
        }

    if len(class_rows) != EXPECTED_RESIDUAL_CLASS_COUNT:
        raise AssertionError("the exact residual analysis did not return 18 classes")

    vector_result_rows = [vector_metrics[type_counts] for type_counts in vector_types]
    r4_bound = max(cast(int, row["R4_BOUND"]) for row in vector_result_rows)
    base_bound = anchor_union + cast(
        int, vector_metrics[DANGEROUS_VECTOR_TYPES[0]]["RESIDUAL_S1"]
    )
    family_a_bounds = (
        CURRENT_R3_BOUND,
        r4_bound,
        CURRENT_R5_BOUND,
        CURRENT_R6_BOUND,
    )
    family_a_bound = max(family_a_bounds)
    bottleneck_r = family_a_bounds.index(family_a_bound) + 3
    elapsed = monotonic() - started
    minimum_certified_reduction = min(
        cast(int, row["MINIMUM_JOINT_UNION_REDUCTION"])
        for row in vector_result_rows
    )

    serialized_classes: list[list[str | int]] = [
        [
            row.vector_label,
            row.component_count,
            row.outside_incidences,
            row.outside_pair_mass_floor,
            row.component_positive_edge_floor,
            row.mass_positive_edge_floor,
            row.residual_s1,
            row.residual_s2_bound,
            row.residual_s3_bound,
            row.residual_event_multiplicity_cap_at_floor,
            row.joint_union_reduction,
            row.joint_union_reduction_mass,
            row.residual_union_bound,
            row.anchor_union,
            row.r4_bound,
        ]
        for row in class_rows
    ]

    return {
        "TASK_ID": "B649_K20_R4_DANGEROUS_REALIZATION_RESIDUAL_UNION_R9",
        "TASK_STATUS": "COMPLETED_SUCCESS_B" if r4_bound < PRIOR_R4_BOUND else "NO_IMPROVEMENT",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_HEAD": "RECORDED_IN_FINAL_HANDOFF",
        "WORKTREE_PATH": WORKTREE_PATH,
        "WORKTREE_DISPOSITION": "RETAIN",
        "DANGEROUS_VECTOR_COUNT": len(vector_types),
        "REALIZABLE_VECTOR_COUNT": len(vector_types),
        "DANGEROUS_REALIZATION_COUNT": len(vector_types),
        "RESIDUAL_CLASS_COUNT": len(class_rows),
        "ASSIGNMENT_CLASS_COUNT": len(class_rows),
        "COUNT_VECTOR_CENSUS": "REUSED_PINNED_R7_RESULT; 52,360-VECTOR CENSUS NOT RERUN",
        "GENERIC_DANGEROUS_VECTOR_SEARCH": "NOT RUN",
        "RESIDUAL_CLASS_DEFINITION": (
            "Eighteen strata: the three exact R7/R8 danger vectors crossed with "
            "R8's component counts 1..6. Pair-mass scans are finite relaxations "
            "over outside-ticket overlaps, not raw incidence matrices."
        ),
        "ANCHOR_PAIR_UNION": anchor_union,
        "RESIDUAL_UNION_POINTWISE_CERTIFICATE": (
            "For every outcome with m residual wins and exact outside pair mass M, "
            "1[m>0] <= m - 2*C(m,2)/K(M), where m<=K(M). Summing gives "
            "union <= S1 - 2*S2/K(M); the exact pair-mass DP jointly scans "
            "S2 and K(M) over every M."
        ),
        "RESIDUAL_S3_RELATION": (
            "For every exact outside pair mass M, S3 <= "
            "floor((K(M)-2)*S2/3); S2 and S3 are bounded jointly through "
            "the same residual-win multiplicity K(M)."
        ),
        "DANGEROUS_VECTOR_RESULTS": vector_result_rows,
        "COMPRESSED_ASSIGNMENT_CLASS_COLUMNS": list(
            COMPRESSED_ASSIGNMENT_CLASS_COLUMNS
        ),
        "COMPRESSED_ASSIGNMENT_CLASSES": serialized_classes,
        "OUTSIDE_PAIR_MASS_RANGE": {
            "MAXIMUM_PAIR_OVERLAP": MAXIMUM_PAIR_OVERLAP,
            "MAXIMUM_TICKET_PAIR_MASS": MAXIMUM_PAIR_OVERLAP
            * comb(OUTSIDE_TICKET_COUNT, 2),
            "LABEL_CAPACITY": OUTSIDE_LABEL_CAPACITY,
        },
        "R4_BASE_BOUND": base_bound,
        "PRIOR_R4_BOUND": PRIOR_R4_BOUND,
        "R4_BOUND": r4_bound,
        "R4_STATUS": "CLOSED" if r4_bound <= INCUMBENT else "TIGHTENED_OPEN_SUCCESS_B",
        "SUCCESS_A": r4_bound <= INCUMBENT,
        "SUCCESS_B": r4_bound < PRIOR_R4_BOUND,
        "R4_BOUND_IMPROVEMENT": PRIOR_R4_BOUND - r4_bound,
        "FROZEN_OTHER_SUBFAMILY_BOUNDS": {
            "R3": CURRENT_R3_BOUND,
            "R5": CURRENT_R5_BOUND,
            "R6": CURRENT_R6_BOUND,
        },
        "FAMILY_A_RECOMPUTED_BOUND": family_a_bound,
        "FAMILY_A_BOTTLENECK_R": bottleneck_r,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_a_bound - INCUMBENT,
        "SOLVER_STATUS": "EXACT_DYNAMIC_PROGRAM_OPTIMAL",
        "SOLVER_CONFIGURED_WALL_LIMIT": (
            f"{NATIVE_WALL_LIMIT_SECONDS}s native; "
            f"{EXTERNAL_HARD_TIMEOUT_SECONDS}s external hard timeout"
        ),
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": round(elapsed, 6),
        "SOLVER_CERTIFIED_BOUND": minimum_certified_reduction,
        "SOLVER_NOTE": (
            "Exact finite min/max dynamic program over every pair-overlap mass "
            "M=minimum..4*C(18,2), combined with the exact label-mass bound "
            "K(M). The union envelope is pointwise and does not combine "
            "independently maximized anchor recovery and pair penalties."
        ),
        "FOCUSED_TESTS": "PENDING",
        "RUFF": "PENDING",
        "PYRIGHT": "PENDING",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--r7-result",
        type=Path,
        default=repository_root
        / "docs/research/matrix-native-results/"
        "b649-k20-r4-exact-anchor-realizability-r7-result.json",
    )
    parser.add_argument(
        "--r8-result",
        type=Path,
        default=repository_root
        / "docs/research/matrix-native-results/"
        "b649-k20-r4-dangerous-assignment-exact-r8-result.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root
        / "docs/research/matrix-native-results/"
        "b649-k20-r4-dangerous-residual-union-r9-result.json",
    )
    arguments = parser.parse_args()
    result = analyze_dangerous_residual_union(arguments.r7_result, arguments.r8_result)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"R4_BOUND={result['R4_BOUND']} "
        f"RESIDUAL_CLASS_COUNT={result['RESIDUAL_CLASS_COUNT']} "
        f"SOLVER_STATUS={result['SOLVER_STATUS']}"
    )


if __name__ == "__main__":
    main()
