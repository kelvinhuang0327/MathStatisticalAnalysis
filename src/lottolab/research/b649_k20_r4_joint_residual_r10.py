"""Joint residual S2/S3 envelopes for the three pinned K20 r=4 realizations.

This proof reloads only R9's eighteen compressed classes. A label-frequency
DP bounds the number of simultaneous residual wins at each outside pair mass;
the exact pair-cost DP bounds residual S2 at the same mass. Those shared
states give a Pareto upper envelope for residual S3 and a sharper union bound
without constructing portfolios or rerunning the earlier vector census.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import pairwise
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    OUTSIDE_LABEL_CAPACITY,
    OUTSIDE_TICKET_COUNT,
)
from lottolab.research.b649_k20_r4_dangerous_residual_union_r9 import (
    MAXIMUM_PAIR_OVERLAP,
    residual_pair_cost_rows,
)

BASE_HEAD = "669566579ac7b06682acc624937843f1e714b1c8"
BASE_TREE = "6d08f9882b732778aff13fc3cadd2a31c9b1bc9c"
TASK_BRANCH = "codex/b649-k20-r4-three-realization-joint-residual-r10"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_R4_THREE_REALIZATION_JOINT_RESIDUAL_R10"
)
TASK_ID = "B649_K20_R4_THREE_REALIZATION_JOINT_RESIDUAL_R10"

NATIVE_WALL_LIMIT_SECONDS = 45
EXTERNAL_HARD_TIMEOUT_SECONDS = 60
DRAW_SIZE = 6
MAXIMUM_OUTSIDE_PAIR_MASS = MAXIMUM_PAIR_OVERLAP * comb(OUTSIDE_TICKET_COUNT, 2)
MAXIMUM_FREQUENCY = OUTSIDE_TICKET_COUNT
SELECTED_LABEL_COUNT = DRAW_SIZE + 1
EXPECTED_CLASS_COUNT = 18
EXPECTED_REALIZATIONS = (
    "18_GOOD",
    "17_GOOD_PLUS_B_ONLY",
    "17_GOOD_PLUS_A_ONLY",
)
EXPECTED_R9_BASE_HEAD = "726ca446f7ab521740ef9e8b41b29fe561af89cc"
EXPECTED_R9_BASE_TREE = "a180363a33f51bc3b1f62a5665c4878825f2d652"
EXPECTED_TYPE_COUNTS = {
    "18_GOOD": (((0, 0, 0, 6), 18),),
    "17_GOOD_PLUS_B_ONLY": (((0, 0, 0, 6), 17), ((0, 0, 1, 5), 1)),
    "17_GOOD_PLUS_A_ONLY": (((0, 0, 0, 6), 17), ((0, 1, 0, 5), 1)),
}
INCUMBENT = 313_239_661
CURRENT_BOUNDS = {"R3": 351_483_978, "R5": 350_778_728, "R6": 343_869_728}
PRIOR_R4_BOUND = 353_379_315
ANCHOR_UNION = 30_998_352
EXPECTED_CLASS_DATA = {
    "18_GOOD": (331_588_656, 108, 93, 59_850_000, 5_042_050_944),
    "17_GOOD_PLUS_B_ONLY": (331_152_556, 107, 91, 58_870_000, 5_039_413_269),
    "17_GOOD_PLUS_A_ONLY": (331_152_556, 107, 91, 58_870_000, 5_039_413_269),
}

type Signature = tuple[int, int, int, int]
type TypeCounts = tuple[tuple[Signature, int], ...]
type PairCostRows = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class ResidualClass:
    vector_label: str
    component_count: int
    outside_incidences: int
    outside_pair_mass_floor: int
    residual_s1: int
    residual_s2_floor: int
    prior_residual_s3_envelope: int
    special_anchor_incidences: int
    type_counts: TypeCounts


@dataclass(frozen=True)
class JointMassState:
    outside_pair_mass: int
    minimum_s2: int
    maximum_s2: int
    maximum_selected_seven_frequency: int
    residual_multiplicity_cap: int
    maximum_s3_at_minimum_s2: int
    maximum_s3_at_maximum_s2: int
    residual_union_reduction: int


@dataclass(frozen=True)
class FrontierSegment:
    s2_start: int
    s2_end: int
    residual_multiplicity_cap: int


def _check_deadline(deadline: float) -> None:
    if monotonic() > deadline:
        raise TimeoutError("the joint residual DP exceeded its native wall limit")


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return cast(dict[str, object], value)


def _integer(value: object, description: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{description} must be an integer >= {minimum}")
    return value


def _parse_type_counts(value: object) -> TypeCounts:
    if not isinstance(value, list):
        raise ValueError("R9 vector type counts must be a list")
    parsed: list[tuple[Signature, int]] = []
    for entry_value in cast(list[object], value):
        entry = _mapping(entry_value, "R9 type-count row")
        signature_value = entry.get("SIGNATURE")
        if not isinstance(signature_value, list):
            raise ValueError("R9 ticket signatures must contain four cells")
        cells = cast(list[object], signature_value)
        if len(cells) != 4:
            raise ValueError("R9 ticket signatures must contain four cells")
        if any(type(cell) is not int or cell < 0 for cell in cells):
            raise ValueError("R9 ticket signature cells must be nonnegative integers")
        count = _integer(entry.get("COUNT"), "R9 ticket count", 1)
        signature = cast(Signature, tuple(cast(int, cell) for cell in cells))
        parsed.append((signature, count))
    return tuple(sorted(parsed))


def load_r9_residual_classes(r9_result_path: Path) -> tuple[ResidualClass, ...]:
    """Load and identity-check precisely R9's eighteen compressed rows."""

    document = _mapping(
        json.loads(r9_result_path.read_text(encoding="utf-8")), "R9 result"
    )
    if (
        document.get("TASK_ID") != "B649_K20_R4_DANGEROUS_REALIZATION_RESIDUAL_UNION_R9"
        or document.get("BASE_HEAD") != EXPECTED_R9_BASE_HEAD
        or document.get("BASE_TREE") != EXPECTED_R9_BASE_TREE
        or document.get("RESIDUAL_CLASS_COUNT") != EXPECTED_CLASS_COUNT
        or document.get("DANGEROUS_VECTOR_COUNT") != len(EXPECTED_REALIZATIONS)
        or document.get("REALIZABLE_VECTOR_COUNT") != len(EXPECTED_REALIZATIONS)
    ):
        raise ValueError("the pinned R9 residual-class authority changed")
    raw_mass_range = _mapping(
        document.get("OUTSIDE_PAIR_MASS_RANGE"), "R9 outside pair-mass range"
    )
    if (
        raw_mass_range.get("MAXIMUM_PAIR_OVERLAP") != MAXIMUM_PAIR_OVERLAP
        or raw_mass_range.get("MAXIMUM_TICKET_PAIR_MASS")
        != MAXIMUM_OUTSIDE_PAIR_MASS
        or raw_mass_range.get("LABEL_CAPACITY") != OUTSIDE_LABEL_CAPACITY
    ):
        raise ValueError("R9 outside label or ticket capacities changed")

    raw_columns = document.get("COMPRESSED_ASSIGNMENT_CLASS_COLUMNS")
    raw_rows = document.get("COMPRESSED_ASSIGNMENT_CLASSES")
    raw_vectors = document.get("DANGEROUS_VECTOR_RESULTS")
    if not isinstance(raw_columns, list) or not isinstance(raw_rows, list):
        raise ValueError("R9 does not contain its compressed class table")
    if not isinstance(raw_vectors, list):
        raise ValueError("R9 does not contain exactly three realization rows")
    columns = cast(list[object], raw_columns)
    rows = cast(list[object], raw_rows)
    vectors = cast(list[object], raw_vectors)
    if len(vectors) != 3:
        raise ValueError("R9 does not contain exactly three realization rows")
    if len(rows) != EXPECTED_CLASS_COUNT:
        raise ValueError("R9 must supply exactly eighteen compressed classes")
    column_names = tuple(cast(str, name) for name in columns)
    index = {name: position for position, name in enumerate(column_names)}
    required = (
        "VECTOR_LABEL",
        "COMPONENT_COUNT",
        "OUTSIDE_INCIDENCES",
        "OUTSIDE_PAIR_MASS_FLOOR",
        "RESIDUAL_S1",
        "RESIDUAL_S2_BOUND",
        "RESIDUAL_S3_BOUND",
    )
    if any(name not in index for name in required):
        raise ValueError("R9's compressed class columns are incomplete")

    vectors_by_label: dict[str, TypeCounts] = {}
    for vector_value in vectors:
        vector = _mapping(vector_value, "R9 realization row")
        label_value = vector.get("LABEL")
        if not isinstance(label_value, str) or vector.get("REALIZABLE") is not True:
            raise ValueError("R9 contains an unverified realization row")
        if label_value in vectors_by_label:
            raise ValueError("R9 realization labels must be unique")
        vectors_by_label[label_value] = _parse_type_counts(vector.get("TYPE_COUNTS"))
    if tuple(vectors_by_label) != EXPECTED_REALIZATIONS:
        raise ValueError("R9 realization identities or order changed")
    if vectors_by_label != EXPECTED_TYPE_COUNTS:
        raise ValueError("R9 realization ticket signatures changed")

    classes: list[ResidualClass] = []
    for row_value in rows:
        if not isinstance(row_value, list):
            raise ValueError("an R9 compressed class row has the wrong shape")
        row = cast(list[object], row_value)
        if len(row) != len(column_names):
            raise ValueError("an R9 compressed class row has the wrong shape")
        label_value = row[index["VECTOR_LABEL"]]
        if not isinstance(label_value, str) or label_value not in vectors_by_label:
            raise ValueError("an R9 class names an unknown realization")
        expected_s1, expected_incidences, expected_mass, expected_s2, expected_s3 = (
            EXPECTED_CLASS_DATA[label_value]
        )
        s1 = _integer(row[index["RESIDUAL_S1"]], "R9 residual S1")
        s2 = _integer(row[index["RESIDUAL_S2_BOUND"]], "R9 residual S2")
        incidences = _integer(
            row[index["OUTSIDE_INCIDENCES"]], "R9 outside incidences"
        )
        mass_floor = _integer(
            row[index["OUTSIDE_PAIR_MASS_FLOOR"]], "R9 outside pair-mass floor"
        )
        s3 = _integer(row[index["RESIDUAL_S3_BOUND"]], "R9 residual S3 envelope")
        if (s1, incidences, mass_floor, s2, s3) != (
            expected_s1,
            expected_incidences,
            expected_mass,
            expected_s2,
            expected_s3,
        ):
            raise ValueError("an R9 realization envelope changed")
        classes.append(
            ResidualClass(
                vector_label=label_value,
                component_count=_integer(
                    row[index["COMPONENT_COUNT"]], "R9 component count", 1
                ),
                outside_incidences=incidences,
                outside_pair_mass_floor=expected_mass,
                residual_s1=expected_s1,
                residual_s2_floor=expected_s2,
                prior_residual_s3_envelope=s3,
                special_anchor_incidences=(
                    0 if label_value == "18_GOOD" else 1
                ),
                type_counts=vectors_by_label[label_value],
            )
        )

    for label in EXPECTED_REALIZATIONS:
        selected = tuple(row for row in classes if row.vector_label == label)
        if tuple(row.component_count for row in selected) != tuple(range(1, 7)):
            raise ValueError("R9 component classes must be exactly 1..6 per realization")
        if any(row.outside_incidences != selected[0].outside_incidences for row in selected):
            raise ValueError("R9 component classes disagree on label incidences")
    if len({row.type_counts for row in classes}) != 3:
        raise ValueError("the eighteen R9 classes must contain exactly three identities")
    return tuple(classes)


def frequency_mass_bitsets(
    label_count: int,
    total_incidences: int,
    maximum_pair_mass: int,
    deadline: float,
) -> tuple[int, ...]:
    """Exact reachable pair-mass bitsets, indexed by incidence total."""

    if label_count < 0 or total_incidences < 0 or maximum_pair_mass < 0:
        raise ValueError("frequency DP dimensions must be nonnegative")
    mass_mask = (1 << (maximum_pair_mass + 1)) - 1
    reachable = [0] * (total_incidences + 1)
    reachable[0] = 1
    for _ in range(label_count):
        _check_deadline(deadline)
        next_reachable = [0] * (total_incidences + 1)
        for incidences, mass_bits in enumerate(reachable):
            if not mass_bits:
                continue
            max_frequency = min(MAXIMUM_FREQUENCY, total_incidences - incidences)
            for frequency in range(max_frequency + 1):
                next_incidence = incidences + frequency
                next_mass_bits = (mass_bits << comb(frequency, 2)) & mass_mask
                next_reachable[next_incidence] |= next_mass_bits
        reachable = next_reachable
    return tuple(reachable)


def maximum_selected_seven_frequency_by_pair_mass(
    total_incidences: int,
    maximum_pair_mass: int,
    deadline: float,
) -> tuple[int | None, ...]:
    """Find the exact maximum top-seven label degree for every pair mass.

    Split the 41 outside labels into seven selected labels and 34 remaining
    labels. Reachable (incidence, pair-mass) bitsets on both sides enumerate
    frequency multisets only; no assignment of ticket portfolios is built.
    """

    selected = frequency_mass_bitsets(
        SELECTED_LABEL_COUNT, total_incidences, maximum_pair_mass, deadline
    )
    remaining = frequency_mass_bitsets(
        OUTSIDE_LABEL_CAPACITY - SELECTED_LABEL_COUNT,
        total_incidences,
        maximum_pair_mass,
        deadline,
    )
    mass_mask = (1 << (maximum_pair_mass + 1)) - 1
    maximum_selected: list[int | None] = [None] * (maximum_pair_mass + 1)
    for selected_incidences, selected_masses in enumerate(selected):
        _check_deadline(deadline)
        if not selected_masses:
            continue
        remaining_incidences = total_incidences - selected_incidences
        if not 0 <= remaining_incidences < len(remaining):
            continue
        remaining_masses = remaining[remaining_incidences]
        if not remaining_masses:
            continue
        combined_masses = 0
        pending = selected_masses
        while pending:
            least_bit = pending & -pending
            selected_mass = least_bit.bit_length() - 1
            combined_masses |= remaining_masses << selected_mass
            pending ^= least_bit
        combined_masses &= mass_mask
        while combined_masses:
            least_bit = combined_masses & -combined_masses
            mass = least_bit.bit_length() - 1
            maximum_selected[mass] = selected_incidences
            combined_masses ^= least_bit
    return tuple(maximum_selected)


def _pair_mass_s2_envelope(
    pair_cost_rows: PairCostRows,
    maximum_pair_mass: int,
    deadline: float,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Exact min/max residual S2 relaxations indexed by pair mass."""

    minimum: list[int | None] = [None] * (maximum_pair_mass + 1)
    maximum: list[int | None] = [None] * (maximum_pair_mass + 1)
    minimum[0] = maximum[0] = 0
    reachable_mass = 0
    for costs in pair_cost_rows:
        _check_deadline(deadline)
        next_minimum: list[int | None] = [None] * (maximum_pair_mass + 1)
        next_maximum: list[int | None] = [None] * (maximum_pair_mass + 1)
        for mass in range(min(reachable_mass, maximum_pair_mass) + 1):
            low = minimum[mass]
            high = maximum[mass]
            for overlap, cost in enumerate(costs):
                next_mass = mass + overlap
                if next_mass > maximum_pair_mass:
                    continue
                if low is not None:
                    candidate = low + cost
                    prior = next_minimum[next_mass]
                    if prior is None or candidate < prior:
                        next_minimum[next_mass] = candidate
                if high is not None:
                    candidate = high + cost
                    prior = next_maximum[next_mass]
                    if prior is None or candidate > prior:
                        next_maximum[next_mass] = candidate
        minimum, maximum = next_minimum, next_maximum
        reachable_mass = min(maximum_pair_mass, reachable_mass + MAXIMUM_PAIR_OVERLAP)
    if any(value is None for value in minimum) or any(value is None for value in maximum):
        raise AssertionError("pair-mass S2 DP did not cover its configured range")
    return (
        tuple(cast(int, value) for value in minimum),
        tuple(cast(int, value) for value in maximum),
    )


def _ceil_div(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator < 1:
        raise ValueError("ceil division requires a nonnegative numerator and positive divisor")
    return (numerator + denominator - 1) // denominator


def residual_s3_upper_bound(residual_s2: int, multiplicity_cap: int) -> int:
    if residual_s2 < 0 or multiplicity_cap < 1:
        raise ValueError("S2 and multiplicity cap must be nonnegative and positive")
    return max(0, (multiplicity_cap - 2) * residual_s2 // 3)


def _frontier_segments(states: tuple[JointMassState, ...]) -> tuple[FrontierSegment, ...]:
    """Return the piecewise maximum S3 slope over all joint S2 intervals."""

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
        multiplicity = max(state.residual_multiplicity_cap for state in active)
        if (
            segments
            and segments[-1].s2_end + 1 == start
            and segments[-1].residual_multiplicity_cap == multiplicity
        ):
            previous = segments.pop()
            segments.append(
                FrontierSegment(previous.s2_start, end, multiplicity)
            )
        else:
            segments.append(FrontierSegment(start, end, multiplicity))
    return tuple(segments)


def _frontier_summary(
    segments: tuple[FrontierSegment, ...],
) -> tuple[int, int, int, int]:
    if not segments:
        raise AssertionError("the S2/S3 frontier is empty")
    maximum_s3 = -1
    maximum_s3_at_s2 = -1
    maximum_cap = 0
    for segment in segments:
        maximum_cap = max(maximum_cap, segment.residual_multiplicity_cap)
        candidate = residual_s3_upper_bound(
            segment.s2_end, segment.residual_multiplicity_cap
        )
        if candidate > maximum_s3:
            maximum_s3 = candidate
            maximum_s3_at_s2 = segment.s2_end
    return len(segments), maximum_s3, maximum_s3_at_s2, maximum_cap


def _per_realization(
    residual_class: ResidualClass,
    deadline: float,
) -> dict[str, object]:
    pair_costs = residual_pair_cost_rows(residual_class.type_counts)
    minimum_s2, maximum_s2 = _pair_mass_s2_envelope(
        pair_costs, MAXIMUM_OUTSIDE_PAIR_MASS, deadline
    )
    selected_seven = maximum_selected_seven_frequency_by_pair_mass(
        residual_class.outside_incidences,
        MAXIMUM_OUTSIDE_PAIR_MASS,
        deadline,
    )
    states: list[JointMassState] = []
    for mass in range(
        residual_class.outside_pair_mass_floor,
        MAXIMUM_OUTSIDE_PAIR_MASS + 1,
    ):
        _check_deadline(deadline)
        top_seven = selected_seven[mass]
        if top_seven is None:
            continue
        # Seven labels are the six main-draw numbers plus the special number.
        # A mirrored realization has one additional A-only/B-only incidence.
        multiplicity_cap = min(
            OUTSIDE_TICKET_COUNT,
            (top_seven + residual_class.special_anchor_incidences) // 3,
        )
        if multiplicity_cap < 1:
            continue
        low = minimum_s2[mass]
        high = maximum_s2[mass]
        reduction = _ceil_div(2 * low, multiplicity_cap)
        states.append(
            JointMassState(
                outside_pair_mass=mass,
                minimum_s2=low,
                maximum_s2=high,
                maximum_selected_seven_frequency=top_seven,
                residual_multiplicity_cap=multiplicity_cap,
                maximum_s3_at_minimum_s2=residual_s3_upper_bound(low, multiplicity_cap),
                maximum_s3_at_maximum_s2=residual_s3_upper_bound(high, multiplicity_cap),
                residual_union_reduction=reduction,
            )
        )
    if not states:
        raise AssertionError("no joint mass state covers the R9 class floor")

    states_tuple = tuple(states)
    # Maximizing S1 - ceil(2*S2/K) means minimizing the reduction.
    minimum_reduction = min(state.residual_union_reduction for state in states_tuple)
    best_state = min(
        (state for state in states_tuple if state.residual_union_reduction == minimum_reduction),
        key=lambda state: state.outside_pair_mass,
    )
    frontier = _frontier_segments(states_tuple)
    frontier_size, maximum_s3, maximum_s3_at_s2, maximum_cap = _frontier_summary(frontier)
    floor_state = next(
        state
        for state in states_tuple
        if state.outside_pair_mass == residual_class.outside_pair_mass_floor
    )
    if floor_state.minimum_s2 != residual_class.residual_s2_floor:
        raise AssertionError("R10's exact pair DP disagrees with R9's S2 floor")
    if floor_state.maximum_s3_at_maximum_s2 <= floor_state.maximum_s3_at_minimum_s2:
        raise AssertionError("minimum S2 unexpectedly attains its same-mass S3 envelope")
    maximum_s3_state = max(
        states_tuple,
        key=lambda state: (state.maximum_s3_at_maximum_s2, state.outside_pair_mass),
    )
    if maximum_s3 <= floor_state.maximum_s3_at_minimum_s2:
        raise AssertionError("the minimum-S2 state attained the global S3 envelope")
    return {
        "VECTOR_LABEL": residual_class.vector_label,
        "COMPONENT_CLASS_COUNT": 6,
        "OUTSIDE_INCIDENCES": residual_class.outside_incidences,
        "OUTSIDE_PAIR_MASS_FLOOR": residual_class.outside_pair_mass_floor,
        "RESIDUAL_S1": residual_class.residual_s1,
        "RESIDUAL_S2_FLOOR": floor_state.minimum_s2,
        "MAXIMUM_SELECTED_SEVEN_FREQUENCY_AT_MASS_FLOOR": (
            floor_state.maximum_selected_seven_frequency
        ),
        "RESIDUAL_MULTIPLICITY_CAP_AT_MASS_FLOOR": (
            floor_state.residual_multiplicity_cap
        ),
        "RESIDUAL_S3_CAP_AT_MINIMUM_S2": floor_state.maximum_s3_at_minimum_s2,
        "RESIDUAL_S3_CAP_AT_SAME_MASS_MAXIMUM_S2": (
            floor_state.maximum_s3_at_maximum_s2
        ),
        "S3_SEPARATION_PROOF": {
            "OUTSIDE_PAIR_MASS": floor_state.outside_pair_mass,
            "MINIMUM_S2": floor_state.minimum_s2,
            "MINIMUM_S2_S3_CAP": floor_state.maximum_s3_at_minimum_s2,
            "SAME_MASS_MAXIMUM_S2": floor_state.maximum_s2,
            "SAME_MASS_MAXIMUM_S3_CAP": floor_state.maximum_s3_at_maximum_s2,
            "GLOBAL_MAXIMUM_S3_CAP": maximum_s3,
            "GLOBAL_MAXIMUM_S3_OUTSIDE_PAIR_MASS": maximum_s3_state.outside_pair_mass,
            "MINIMUM_S2_CANNOT_ATTAIN_GLOBAL_MAXIMUM": True,
        },
        "S2_S3_FRONTIER_SIZE": frontier_size,
        "S2_S3_FRONTIER_KIND": (
            "CERTIFIED_UPPER_FRONTIER; pair-S2 intervals are relaxed, and S3 "
            "values are upper bounds rather than exact triple totals"
        ),
        "S2_S3_FRONTIER_FORMULA": (
            "S3 <= max(0,floor((K-2)*S2/3)) on each segment with cap K"
        ),
        "S2_S3_FRONTIER_SHA256": hashlib.sha256(
            json.dumps(
                [asdict(segment) for segment in frontier],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "MAXIMUM_S3_ENVELOPE": {
            "S3_UPPER_BOUND": maximum_s3,
            "AT_S2": maximum_s3_at_s2,
            "MAXIMUM_RESIDUAL_MULTIPLICITY_CAP": maximum_cap,
            "OUTSIDE_PAIR_MASS": maximum_s3_state.outside_pair_mass,
            "S2_UPPER_BOUND_AT_MASS": maximum_s3_state.maximum_s2,
            "S3_UPPER_BOUND_AT_MASS": maximum_s3_state.maximum_s3_at_maximum_s2,
            "IS_EXACT_TRIPLE_TOTAL": False,
        },
        "R9_PRIOR_S3_ENVELOPE": residual_class.prior_residual_s3_envelope,
        "UNIQUE_VECTOR_MASS_STATE_COUNT": len(states_tuple),
        "JOINT_STATE_COUNT": len(states_tuple) * 6,
        "S2_S3_FRONTIER": [asdict(segment) for segment in frontier],
        "MINIMUM_JOINT_UNION_REDUCTION": minimum_reduction,
        "UNION_OBJECTIVE": (
            "max_M [S1 - ceil(2*minimum_S2(M)/K(M))] over the shared joint states"
        ),
        "JOINT_UNION_REDUCTION_AT_OUTSIDE_PAIR_MASS": best_state.outside_pair_mass,
        "RESIDUAL_UNION_BOUND": residual_class.residual_s1 - minimum_reduction,
        "R4_BOUND": ANCHOR_UNION + residual_class.residual_s1 - minimum_reduction,
    }


def analyze_joint_residual_envelope(
    r9_result_path: Path,
) -> dict[str, object]:
    """Build the certified joint S2/S3 residual envelope from R9 classes."""

    started = monotonic()
    deadline = started + NATIVE_WALL_LIMIT_SECONDS
    classes = load_r9_residual_classes(r9_result_path)
    by_label = {
        label: next(row for row in classes if row.vector_label == label)
        for label in EXPECTED_REALIZATIONS
    }
    realization_results = [
        _per_realization(by_label[label], deadline) for label in EXPECTED_REALIZATIONS
    ]
    r4_bound = max(cast(int, row["R4_BOUND"]) for row in realization_results)
    family_a_bounds = {**CURRENT_BOUNDS, "R4": r4_bound}
    family_a_bound = max(family_a_bounds.values())
    bottleneck_r = next(
        int(label[1:])
        for label, bound in family_a_bounds.items()
        if bound == family_a_bound
    )
    total_joint_states = sum(
        cast(int, row["JOINT_STATE_COUNT"]) for row in realization_results
    )
    frontier_size = sum(
        cast(int, row["S2_S3_FRONTIER_SIZE"]) for row in realization_results
    )
    joint_state_digest = hashlib.sha256(
        json.dumps(
            [
                {
                    key: row[key]
                    for key in (
                        "VECTOR_LABEL",
                        "OUTSIDE_PAIR_MASS_FLOOR",
                        "JOINT_STATE_COUNT",
                        "S2_S3_FRONTIER_SHA256",
                        "MINIMUM_JOINT_UNION_REDUCTION",
                        "JOINT_UNION_REDUCTION_AT_OUTSIDE_PAIR_MASS",
                    )
                }
                for row in realization_results
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    elapsed = monotonic() - started
    success_a = r4_bound <= INCUMBENT
    success_b = r4_bound < PRIOR_R4_BOUND
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETED_SUCCESS_A"
        if success_a
        else "COMPLETED_SUCCESS_B"
        if success_b
        else "NO_STRICT_IMPROVEMENT",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_HEAD": "RECORDED_IN_FINAL_HANDOFF",
        "WORKTREE_PATH": WORKTREE_PATH,
        "WORKTREE_DISPOSITION": "RETAIN",
        "R9_BASE_HEAD": EXPECTED_R9_BASE_HEAD,
        "R9_BASE_TREE": EXPECTED_R9_BASE_TREE,
        "REALIZATION_COUNT": len(realization_results),
        "RESIDUAL_CLASS_COUNT": len(classes),
        "JOINT_STATE_COUNT": total_joint_states,
        "JOINT_STATE_DEFINITION": (
            "One state per R9 compressed class (realization x component count) and "
            "exact outside label-pair mass M; "
            "each state joins the relaxed min/max residual S2 DP with the exact "
            "top-seven frequency maximum over 41-label incidence histograms."
        ),
        "FREQUENCY_MULTIPLICITY_CERTIFICATE": (
            "For an outcome with k residual wins, each needs at least three main "
            "hits except tickets containing the special label, which need two. "
            "Thus 3k is at most the incidence sum on its six main labels and "
            "one special label. At pair mass M, the seven outside-label "
            "incidences are bounded by the exact frequency-histogram DP; add at "
            "most one anchor-exclusive incidence for either mirrored realization. "
            "Therefore K(M)=min(18,floor((top7(M)+anchor_incidence)/3))."
        ),
        "RESIDUAL_S3_POINTWISE_CERTIFICATE": (
            "For every outcome with m residual wins, C(m,3)=(m-2)*C(m,2)/3 "
            "when m>=3; when K(M)<3, S3=0. Since m<=K(M), summing gives "
            "S3<=max(0,floor((K(M)-2)*S2/3)). The frontier records this upper "
            "bound on the same outside-pair-mass state as S2."
        ),
        "RESIDUAL_UNION_POINTWISE_CERTIFICATE": (
            "For 1<=m<=K, m-2*C(m,2)/K = 1+(m-1)*(K-m)/K >= 1; for m=0 "
            "both sides are zero. Summing gives U<=S1-2*S2/K. At each M, "
            "S2 is at least the pair-cost DP minimum and the actual multiplicity "
            "is at most K(M), so U<=S1-ceil(2*minimum_S2(M)/K(M))."
        ),
        "UNIQUE_VECTOR_MASS_STATE_COUNT": sum(
            cast(int, row["UNIQUE_VECTOR_MASS_STATE_COUNT"])
            for row in realization_results
        ),
        "JOINT_STATE_SHA256": joint_state_digest,
        "S2_S3_FRONTIER_SIZE": frontier_size,
        "JOINT_RESIDUAL_ENVELOPE": realization_results,
        "R4_BOUND": r4_bound,
        "R4_PRIOR_BOUND": PRIOR_R4_BOUND,
        "R4_BOUND_IMPROVEMENT": PRIOR_R4_BOUND - r4_bound,
        "R4_STATUS": "CLOSED" if success_a else "TIGHTENED_OPEN_SUCCESS_B" if success_b else "OPEN",
        "SUCCESS_A": success_a,
        "SUCCESS_B": success_b,
        "FAMILY_A_RECOMPUTED_BOUND": family_a_bound,
        "FAMILY_A_BOTTLENECK_R": bottleneck_r,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_a_bound - INCUMBENT,
        "FROZEN_OTHER_SUBFAMILY_BOUNDS": CURRENT_BOUNDS,
        "SOLVER_STATUS": "EXACT_JOINT_DYNAMIC_PROGRAM_OPTIMAL",
        "SOLVER_CONFIGURED_WALL_LIMIT": (
            f"{NATIVE_WALL_LIMIT_SECONDS}s native; "
            f"{EXTERNAL_HARD_TIMEOUT_SECONDS}s external hard timeout"
        ),
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": round(elapsed, 6),
        "SOLVER_CERTIFIED_BOUND": r4_bound,
        "SOLVER_NOTE": (
            "The finite DP exhausts 41-label frequency histograms and all "
            "outside pair-mass states under the fixed 18-ticket cap. Pair-cost "
            "S2 minima/maxima are a safe relaxation over ticket-pair overlaps; "
            "the S3 Pareto frontier uses the same M and K(M). The union "
            "objective is exhausted over every joint state."
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
        "--r9-result",
        type=Path,
        default=repository_root
        / "docs/research/matrix-native-results/"
        "b649-k20-r4-dangerous-residual-union-r9-result.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root
        / "docs/research/matrix-native-results/"
        "b649-k20-r4-joint-residual-r10-result.json",
    )
    arguments = parser.parse_args()
    result = analyze_joint_residual_envelope(arguments.r9_result)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"R4_BOUND={result['R4_BOUND']} "
        f"REALIZATION_COUNT={result['REALIZATION_COUNT']} "
        f"JOINT_STATE_COUNT={result['JOINT_STATE_COUNT']} "
        f"S2_S3_FRONTIER_SIZE={result['S2_S3_FRONTIER_SIZE']}"
    )


if __name__ == "__main__":
    main()
