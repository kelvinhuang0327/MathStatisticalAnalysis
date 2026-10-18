"""Realize and tighten only the load-bearing K20 R3 frontier states.

The R7 frontier is frozen below.  This module does not rediscover ticket
types or rebuild the 10,117-state census.  Exact reduced pair tables produce
state-specific S2 bounds with four-ticket corrections; a label-incidence
model classifies the seven frontier points above R5 and minimizes S4.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from hashlib import sha256
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from itertools import pairwise, product
from pathlib import Path
from typing import Any

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    DRAW_SIZE,
    INCUMBENT,
    OUTRIGHT_MATCHES,
    POOL_SIZE,
    TICKET_COUNT,
    pair_intersection_count,
    triple_intersection_count,
)
from lottolab.research.b649_k20_r3_anchor_incidence_bound_r5 import (
    AnchorIncidenceProfile,
    anchor_incidence_profiles,
)
from lottolab.research.b649_k20_r3_exact_anchor_neighborhood_envelope_r6 import (
    OUTSIDE_LABEL_CAPACITY,
    PAIR_MULTIPLICITY_DIVISOR,
    UNCORRECTED_R3_BOUND,
    balanced_pair_mass,
)
from lottolab.research.b649_k20_r3_joint_residual_envelope_r7 import (
    JOINT_EXPRESSION_CONSTANT,
)

TASK_ID = "B649_K20_R3_FRONTIER_REALIZABILITY_BOUND_R8"
BASE_HEAD = "588734b83266e4ea2f003b278edc9d067fcee9de"
BASE_TREE = "53afda81acce4ac72378a6575c44c778d702515f"
TASK_BRANCH = "codex/b649-k20-r3-frontier-realizability-bound-r8"
CURRENT_R3_BOUND = 350_545_750
CURRENT_R4_BOUND = 350_778_728
CURRENT_R5_BOUND = 349_009_248
CURRENT_R6_BOUND = 343_869_728
R7_FRONTIER_SHA256 = "271c3950b6d30d58d4baa5bb534894a60f17111b8458586fda0089447d1bc7d3"
R7_RESIDUAL_STATE_COUNT = 10_117
R7_FRONTIER_SIZE = 23
R7_TAIL_BOUND = UNCORRECTED_R3_BOUND - 6_695_798 - 1
R7_FRONTIER_NONLOAD_BOUND = 348_992_130
OUTSIDE_TICKET_COUNT = TICKET_COUNT - 2
ANCHOR_CELL_CAPACITIES = (3, 3, 3, OUTSIDE_LABEL_CAPACITY)
ANCHOR_CELL_MASKS = (0b0011, 0b0001, 0b0010, 0)
FULL_SUPPORT_S4_NATIVE_WALL_LIMIT_SECONDS = 120.0
FULL_SUPPORT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS = 130.0
COMPACT_S4_NATIVE_WALL_LIMIT_SECONDS = 15.0
COMPACT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS = 25.0
SOLVER_WORKERS = 16
RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "b649-k20-r3-frontier-realizability-bound-r8-result.json"
)
TypeCountVector = tuple[int, ...]
CellTuple = tuple[int, int, int, int]


@dataclass(frozen=True)
class FrontierCoordinate:
    """A frozen R7 (joint S2, joint S3) frontier coordinate."""

    joint_s2: int
    maximum_joint_s3: int
    upper_bound: int

    @property
    def identifier(self) -> str:
        return f"s2-{self.joint_s2}-s3-{self.maximum_joint_s3}"


# Frozen from the R7 result certificate.  The digest above binds the complete
# list, including the 16 points that the R5 threshold excludes.
R7_FRONTIER_POINTS = (
    FrontierCoordinate(10_833_008, 427_140, 350_545_750),
    FrontierCoordinate(11_295_555, 450_450, 350_106_513),
    FrontierCoordinate(11_298_977, 504_238, 350_156_879),
    FrontierCoordinate(11_761_525, 527_548, 349_717_641),
    FrontierCoordinate(11_764_636, 581_336, 349_768_318),
    FrontierCoordinate(12_227_184, 604_646, 349_329_080),
    FrontierCoordinate(12_229_984, 658_434, 349_380_068),
    FrontierCoordinate(12_692_531, 681_744, 348_940_831),
    FrontierCoordinate(12_695_020, 735_532, 348_992_130),
    FrontierCoordinate(13_169_800, 789_320, 348_571_138),
    FrontierCoordinate(13_548_976, 951_748, 348_354_390),
    FrontierCoordinate(14_122_976, 1_005_536, 347_834_178),
    FrontierCoordinate(14_696_976, 1_059_324, 347_313_966),
    FrontierCoordinate(15_270_976, 1_113_112, 346_793_754),
    FrontierCoordinate(15_754_130, 1_115_170, 346_312_658),
    FrontierCoordinate(15_844_976, 1_166_900, 346_273_542),
    FrontierCoordinate(16_328_130, 1_168_958, 345_792_446),
    FrontierCoordinate(16_608_564, 1_182_916, 345_525_970),
    FrontierCoordinate(16_794_330, 1_246_056, 345_403_344),
    FrontierCoordinate(16_798_152, 1_383_116, 345_536_582),
    FrontierCoordinate(17_372_152, 1_436_904, 345_016_370),
    FrontierCoordinate(17_743_684, 1_816_864, 345_024_798),
    FrontierCoordinate(18_317_684, 1_870_652, 344_504_586),
)


@dataclass(frozen=True)
class LoadBearingFrontierState:
    """One load-bearing frontier point and its anchor-swap orbit."""

    identifier: str
    joint_s2: int
    maximum_joint_s3: int
    current_upper_bound: int
    witness_counts: TypeCountVector
    mirrored_counts: TypeCountVector
    legacy_residual_pair_mass_floor: int


def _dense_counts(sparse: tuple[tuple[int, int], ...]) -> TypeCountVector:
    counts = [0] * len(anchor_incidence_profiles())
    for index, count in sparse:
        if not 0 <= index < len(counts) or count <= 0:
            raise ValueError("sparse type counts are invalid")
        counts[index] = count
    if sum(counts) != OUTSIDE_TICKET_COUNT:
        raise ValueError("type counts must total the 18 non-anchor tickets")
    return tuple(counts)


def swap_anchor_sides(counts: TypeCountVector) -> TypeCountVector:
    """Exchange A-only and B-only incidence types."""

    if len(counts) != len(anchor_incidence_profiles()):
        raise ValueError("type-count vector has the wrong dimension")
    swapped = list(counts)
    swapped[1], swapped[4] = swapped[4], swapped[1]
    return tuple(swapped)


_LOAD_BEARING_WITNESS_COUNTS = (
    ((0, 7), (4, 11)),
    ((0, 6), (4, 12)),
    ((0, 7), (4, 10), (5, 1)),
    ((0, 6), (4, 11), (5, 1)),
    ((0, 7), (4, 9), (5, 2)),
    ((0, 6), (4, 10), (5, 2)),
    ((0, 7), (4, 8), (5, 3)),
)
_LOAD_BEARING_LEGACY_PAIR_FLOORS = (
    16_416_064,
    16_383_192,
    16_413_992,
    16_381_120,
    16_409_120,
    16_376_248,
    16_401_448,
)

# Validated constructive supports for the seven frozen count-vector orbits.
# Each ticket is encoded as a 49-bit label mask; the result JSON stores the
# same masks so the support certificates can be checked without CP-SAT search.
SUPPORT_WITNESS_BITMASKS = {
    "s2-10833008-s3-427140": (
        32256, 1016320, 15762432,
        520159232, 16643129344, 532576206848,
        1666985754624, 549774821384, 7696585850888,
        11544914034704, 123179729158160, 4398719697440,
        2200365958176, 17609374369824, 70900551712,
        176063594373152, 71743133859872, 282033393762336,
    ),
    "s2-11295555-s3-450450": (
        32256, 1016320, 15762432,
        520095744, 1628508160, 15066013696,
        19394498568, 34495143944, 4565778440,
        34934620176, 71136968720, 142883160080,
        189246997536, 828928722976, 68862349344,
        8611446816, 1102198210592, 32986422575136,
    ),
    "s2-11298977-s3-504238": (
        32256, 2064384, 65044480,
        2080440320, 32214482944, 1065156083712,
        34119220199424, 1168298476040, 2201179194376,
        4535619815432, 8800656461832, 284022013960,
        4400730898960, 279273539600, 17601858113552,
        9363045548048, 1237222162448, 527765581332576,
    ),
    "s2-11761525-s3-527548": (
        32256, 1016320, 32506880,
        1040188416, 7550797824, 128850071552,
        413457711624, 1649401696264, 11007959048,
        2216240939016, 4437246476296, 6665789277200,
        8813281413136, 140123377680, 17592254472208,
        35571908624, 554336518160, 527765581332576,
    ),
    "s2-11764636-s3-581336": (
        32256, 1016320, 32538624,
        504430592, 16643129344, 258235170816,
        293167693824, 34431173640, 1649804838920,
        343739994120, 19595829256, 277092763664,
        38663626768, 138646962192, 575529877520,
        1168281567248, 32985348833376, 527765581332640,
    ),
    "s2-12227184-s3-604646": (
        32256, 1016320, 32506880,
        504397824, 16643063808, 532576075776,
        567506108936, 35500852232, 70869092360,
        1099650109448, 141735501832, 8866906120,
        138045034512, 1692217122832, 69797953552,
        21626093584, 32985348833376, 527765581332640,
    ),
    "s2-12229984-s3-658434": (
        32256, 1016320, 15762432,
        118556672, 421662720, 8069873664,
        60668772352, 78383219720, 675809288,
        2189692936, 17515454472, 38655901704,
        36776182800, 1283473424, 90232061968,
        2061584302160, 32985348833440, 527765581332768,
    ),
}


def select_load_bearing_frontier(
    points: tuple[FrontierCoordinate, ...] = R7_FRONTIER_POINTS,
    *,
    r5_bound: int = CURRENT_R5_BOUND,
) -> tuple[FrontierCoordinate, ...]:
    """Select exactly the frozen points whose current envelope exceeds R5."""

    return tuple(point for point in points if point.upper_bound > r5_bound)


def frozen_frontier_digest(
    points: tuple[FrontierCoordinate, ...] = R7_FRONTIER_POINTS,
) -> str:
    """Hash the frozen S2/S3 coordinates using the R7 serialization."""

    payload = "\n".join(
        f"{point.joint_s2},{point.maximum_joint_s3}" for point in points
    )
    return sha256(payload.encode("ascii")).hexdigest()


def load_bearing_frontier_states() -> tuple[LoadBearingFrontierState, ...]:
    """Return the seven frozen R7 frontier states, quotienting A/B symmetry."""

    selected = select_load_bearing_frontier()
    if (
        len(R7_FRONTIER_POINTS) != R7_FRONTIER_SIZE
        or frozen_frontier_digest() != R7_FRONTIER_SHA256
        or len(selected) != 7
    ):
        raise AssertionError("the frozen R7 frontier selection changed")
    profiles = anchor_incidence_profiles()
    states: list[LoadBearingFrontierState] = []
    for point, sparse, legacy_floor in zip(
        selected,
        _LOAD_BEARING_WITNESS_COUNTS,
        _LOAD_BEARING_LEGACY_PAIR_FLOORS,
        strict=True,
    ):
        counts = _dense_counts(sparse)
        mirrored = swap_anchor_sides(counts)
        anchor_s2 = sum(
            count * profile.pair_recovery_cost
            for count, profile in zip(counts, profiles, strict=True)
        )
        anchor_s3 = sum(
            count * profile.triple_recovery
            for count, profile in zip(counts, profiles, strict=True)
        )
        legacy_penalty = (legacy_floor + PAIR_MULTIPLICITY_DIVISOR - 1) // (
            PAIR_MULTIPLICITY_DIVISOR
        )
        if (
            anchor_s2 + legacy_penalty != point.joint_s2
            or anchor_s3 != point.maximum_joint_s3
            or JOINT_EXPRESSION_CONSTANT - point.joint_s2 + anchor_s3
            != point.upper_bound
        ):
            raise AssertionError("frozen frontier identifiers disagree with R7")
        if mirrored == counts:
            raise AssertionError("expected a two-member anchor-swap orbit")
        states.append(
            LoadBearingFrontierState(
                identifier=point.identifier,
                joint_s2=point.joint_s2,
                maximum_joint_s3=point.maximum_joint_s3,
                current_upper_bound=point.upper_bound,
                witness_counts=counts,
                mirrored_counts=mirrored,
                legacy_residual_pair_mass_floor=legacy_floor,
            )
        )
    return tuple(states)


def _cells(profile: AnchorIncidenceProfile) -> CellTuple:
    return (profile.shared, profile.a_only, profile.b_only, profile.outside)


@dataclass
class _IncidenceModel:
    """CP-SAT label-support model with exact pairwise overlap variables."""

    model: Any
    ticket_labels: list[list[Any]]
    pair_cell_overlaps: dict[tuple[int, int], tuple[Any, ...]]
    cell_label_ranges: tuple[range, ...]


def build_incidence_model(
    cell_capacities: tuple[int, ...],
    row_demands: tuple[tuple[int, ...], ...],
    *,
    maximum_pair_overlap: int,
) -> _IncidenceModel:
    """Build a label-incidence realization model for a small or full support."""

    cp_model: Any = import_module("ortools.sat.python.cp_model")

    if not cell_capacities or any(capacity <= 0 for capacity in cell_capacities):
        raise ValueError("cell capacities must be positive")
    if not row_demands or any(
        len(demands) != len(cell_capacities) for demands in row_demands
    ):
        raise ValueError("each ticket row must specify every label cell")
    if any(
        type(demand) is not int or demand < 0 or demand > capacity
        for demands in row_demands
        for demand, capacity in zip(demands, cell_capacities, strict=True)
    ):
        raise ValueError("ticket demands must fit their cell capacities")
    if maximum_pair_overlap < 0:
        raise ValueError("maximum_pair_overlap must be nonnegative")

    model = cp_model.CpModel()
    label_ranges: list[range] = []
    next_label = 0
    for capacity in cell_capacities:
        label_ranges.append(range(next_label, next_label + capacity))
        next_label += capacity
    ticket_labels: list[list[Any]] = [
        [model.NewBoolVar(f"x_{ticket}_{label}") for label in range(next_label)]
        for ticket in range(len(row_demands))
    ]

    for ticket, demands in enumerate(row_demands):
        for demand, labels in zip(demands, label_ranges, strict=True):
            model.Add(sum(ticket_labels[ticket][label] for label in labels) == demand)

    # Tickets with identical cell demands are interchangeable.  Order only
    # those rows, preserving every support orbit while reducing row symmetry.
    row_groups: dict[tuple[int, ...], list[int]] = {}
    for ticket, demands in enumerate(row_demands):
        row_groups.setdefault(demands, []).append(ticket)
    label_weights = tuple(
        1 << (next_label - 1 - label) for label in range(next_label)
    )
    for group in row_groups.values():
        for left_ticket, right_ticket in pairwise(group):
            left_code = sum(
                label_weights[label] * ticket_labels[left_ticket][label]
                for label in range(next_label)
            )
            right_code = sum(
                label_weights[label] * ticket_labels[right_ticket][label]
                for label in range(next_label)
            )
            model.Add(left_code >= right_code)

    # Relabel physical labels within each cell into canonical support-mask
    # order. Column permutations preserve every row demand and pair overlap.
    ticket_weights = tuple(
        1 << (len(row_demands) - 1 - ticket) for ticket in range(len(row_demands))
    )
    for labels in label_ranges:
        for left, right in pairwise(labels):
            left_code = sum(
                ticket_weights[ticket] * ticket_labels[ticket][left]
                for ticket in range(len(row_demands))
            )
            right_code = sum(
                ticket_weights[ticket] * ticket_labels[ticket][right]
                for ticket in range(len(row_demands))
            )
            model.Add(left_code >= right_code)

    pair_cell_overlaps: dict[tuple[int, int], tuple[Any, ...]] = {}
    for left_ticket in range(len(row_demands)):
        for right_ticket in range(left_ticket + 1, len(row_demands)):
            overlaps: list[Any] = []
            for cell_index, labels in enumerate(label_ranges):
                left_demand = row_demands[left_ticket][cell_index]
                right_demand = row_demands[right_ticket][cell_index]
                capacity = cell_capacities[cell_index]
                lower = max(0, left_demand + right_demand - capacity)
                upper = min(left_demand, right_demand)
                overlap = model.NewIntVar(
                    lower,
                    upper,
                    f"o_{left_ticket}_{right_ticket}_{cell_index}",
                )
                common: list[Any] = []
                for label in labels:
                    shared = model.NewBoolVar(
                        f"z_{left_ticket}_{right_ticket}_{label}"
                    )
                    left_has = ticket_labels[left_ticket][label]
                    right_has = ticket_labels[right_ticket][label]
                    model.Add(shared <= left_has)
                    model.Add(shared <= right_has)
                    model.Add(shared >= left_has + right_has - 1)
                    common.append(shared)
                model.Add(overlap == sum(common))
                overlaps.append(overlap)
            model.Add(sum(overlaps) <= maximum_pair_overlap)
            pair_cell_overlaps[(left_ticket, right_ticket)] = tuple(overlaps)

    return _IncidenceModel(
        model=model,
        ticket_labels=ticket_labels,
        pair_cell_overlaps=pair_cell_overlaps,
        cell_label_ranges=tuple(label_ranges),
    )


@cache
def _four_event_count_cached(
    profile_counts: tuple[int, ...],
    pool_size: int,
    draw_size: int,
    outright_matches: int,
) -> int:
    """Count exact four-ticket event intersections by a 16-cell DP."""

    if len(profile_counts) != 16 or sum(profile_counts) != pool_size:
        raise ValueError("four-ticket incidence profile must contain 16 pool cells")
    if any(type(count) is not int or count < 0 for count in profile_counts):
        raise ValueError("four-ticket profile counts must be nonnegative integers")
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
        states: dict[tuple[int, int, int, int, int], int] = {
            (0, 0, 0, 0, 0): 1
        }
        for incidence_mask, label_count in enumerate(available):
            if label_count == 0:
                continue
            following: dict[tuple[int, int, int, int, int], int] = {}
            for state, ways in states.items():
                used = state[0]
                hits: tuple[int, int, int, int] = (
                    state[1],
                    state[2],
                    state[3],
                    state[4],
                )
                for take in range(min(label_count, draw_size - used) + 1):
                    new_hits = (
                        min(thresholds[0], hits[0] + (take if incidence_mask & 1 else 0)),
                        min(thresholds[1], hits[1] + (take if incidence_mask & 2 else 0)),
                        min(thresholds[2], hits[2] + (take if incidence_mask & 4 else 0)),
                        min(thresholds[3], hits[3] + (take if incidence_mask & 8 else 0)),
                    )
                    new_state: tuple[int, int, int, int, int] = (
                        used + take,
                        new_hits[0],
                        new_hits[1],
                        new_hits[2],
                        new_hits[3],
                    )
                    following[new_state] = following.get(new_state, 0) + ways * math.comb(
                        label_count, take
                    )
            states = following
        target: tuple[int, int, int, int, int] = (
            draw_size,
            thresholds[0],
            thresholds[1],
            thresholds[2],
            thresholds[3],
        )
        total += special_multiplicity * states.get(target, 0)
    return total


def four_ticket_event_intersection_count(
    profile_counts: tuple[int, ...],
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Public exact four-event counter for a 16-mask incidence profile."""

    return _four_event_count_cached(
        profile_counts, pool_size, draw_size, outright_matches
    )


def _four_ticket_profile(
    left: AnchorIncidenceProfile,
    right: AnchorIncidenceProfile,
    overlap: CellTuple,
) -> tuple[int, ...]:
    counts = [0] * 16
    for capacity, anchor_mask, left_count, right_count, both in zip(
        ANCHOR_CELL_CAPACITIES,
        ANCHOR_CELL_MASKS,
        _cells(left),
        _cells(right),
        overlap,
        strict=True,
    ):
        if not (
            max(0, left_count + right_count - capacity)
            <= both
            <= min(left_count, right_count)
        ):
            raise ValueError("cell overlap cannot be realized by the two tickets")
        counts[anchor_mask | 0b1100] += both
        counts[anchor_mask | 0b0100] += left_count - both
        counts[anchor_mask | 0b1000] += right_count - both
        counts[anchor_mask] += capacity - left_count - right_count + both
    return tuple(counts)


@cache
def _pair_event_correction_table(
    left_index: int, right_index: int
) -> tuple[tuple[int, int, int, int, int, int], ...]:
    """Map every possible cell overlap to exact residual S2 and S4 costs."""

    profiles = anchor_incidence_profiles()
    left = profiles[left_index]
    right = profiles[right_index]
    left_cells, right_cells = _cells(left), _cells(right)
    ranges = tuple(
        range(
            max(0, left_count + right_count - capacity),
            min(left_count, right_count) + 1,
        )
        for capacity, left_count, right_count in zip(
            ANCHOR_CELL_CAPACITIES, left_cells, right_cells, strict=True
        )
    )
    rows: list[tuple[int, int, int, int, int, int]] = []
    for overlap_values in product(*ranges):
        overlap: CellTuple = (
            overlap_values[0],
            overlap_values[1],
            overlap_values[2],
            overlap_values[3],
        )
        total_overlap = sum(overlap)
        if total_overlap > 3:
            continue
        triple_a = triple_intersection_count(
            (
                left.overlap_with_a,
                right.overlap_with_a,
                total_overlap,
            ),
            overlap[0] + overlap[1],
        )
        triple_b = triple_intersection_count(
            (
                left.overlap_with_b,
                right.overlap_with_b,
                total_overlap,
            ),
            overlap[0] + overlap[2],
        )
        quadruple = four_ticket_event_intersection_count(
            _four_ticket_profile(left, right, overlap)
        )
        residual_pair_intersection = (
            pair_intersection_count(total_overlap) - triple_a - triple_b + quadruple
        )
        if residual_pair_intersection < 0:
            raise AssertionError("four-set inclusion-exclusion produced a negative count")
        rows.append(
            (
                overlap[0],
                overlap[1],
                overlap[2],
                overlap[3],
                residual_pair_intersection,
                quadruple,
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class StateMomentFloor:
    """Exact reduced-state S2 and S4 floors from pair tables and label counts."""

    residual_s2_lower_bound: int
    pair_minimum_sum: int
    minimum_outside_slope: Fraction
    outside_incidence_total: int
    outside_pair_mass_floor: int
    s4_pairwise_minimum_floor: int


def state_moment_floor(counts: TypeCountVector) -> StateMomentFloor:
    """Certify state-specific moments from the represented ticket types.

    For each type pair, every realizable cell-overlap row obeys a linear lower
    bound on residual S2 as a function of outside-cell overlap. Summing these
    inequalities and applying the exact convex 40-label frequency floor gives
    a support-independent lower bound. S4 uses the same exact four-ticket
    table and retains its pairwise minimum as a separate certificate.
    """

    profiles = anchor_incidence_profiles()
    if len(counts) != len(profiles) or sum(counts) != OUTSIDE_TICKET_COUNT:
        raise ValueError("frontier count vector is malformed")
    pair_minimum_sum = 0
    s4_pairwise_minimum_floor = 0
    pair_slopes: list[Fraction] = []
    for left_index, left_count in enumerate(counts):
        if left_count == 0:
            continue
        for right_index in range(left_index, len(counts)):
            right_count = counts[right_index]
            pair_count = (
                math.comb(left_count, 2)
                if left_index == right_index
                else left_count * right_count
            )
            if pair_count == 0:
                continue
            table = _pair_event_correction_table(left_index, right_index)
            pair_minimum = min(row[4] for row in table)
            outside_slopes = tuple(
                Fraction(row[4] - pair_minimum, row[3])
                for row in table
                if row[3] > 0
            )
            if not outside_slopes:
                raise AssertionError("reduced type pair has no outside overlap pattern")
            pair_slope = min(outside_slopes)
            if any(
                row[4] - pair_minimum < pair_slope * row[3]
                for row in table
            ):
                raise AssertionError("type-pair outside slope is not a valid dual")
            pair_minimum_sum += pair_count * pair_minimum
            s4_pairwise_minimum_floor += pair_count * min(row[5] for row in table)
            pair_slopes.append(pair_slope)

    if not pair_slopes:
        raise AssertionError("frontier state has no outside ticket pairs")
    outside_slope = min(pair_slopes)
    outside_total = sum(
        count * profile.outside
        for count, profile in zip(counts, profiles, strict=True)
    )
    outside_mass = balanced_pair_mass(outside_total, OUTSIDE_LABEL_CAPACITY)
    slope_credit = (
        outside_slope.numerator * outside_mass + outside_slope.denominator - 1
    ) // outside_slope.denominator
    return StateMomentFloor(
        residual_s2_lower_bound=pair_minimum_sum + slope_credit,
        pair_minimum_sum=pair_minimum_sum,
        minimum_outside_slope=outside_slope,
        outside_incidence_total=outside_total,
        outside_pair_mass_floor=outside_mass,
        s4_pairwise_minimum_floor=s4_pairwise_minimum_floor,
    )


@dataclass
class _StateOptimizationModel:
    """A support model annotated with exact residual pair and S4 costs."""

    incidence: _IncidenceModel
    residual_pair_costs: tuple[Any, ...]
    s4_costs: tuple[Any, ...]
    moment_floor: StateMomentFloor


def _build_state_optimization_model(
    counts: TypeCountVector,
) -> _StateOptimizationModel:
    profiles = anchor_incidence_profiles()
    if len(counts) != len(profiles) or sum(counts) != OUTSIDE_TICKET_COUNT:
        raise ValueError("frontier count vector is malformed")
    row_types = tuple(
        type_index
        for type_index, count in enumerate(counts)
        for _ in range(count)
    )
    row_demands = tuple(_cells(profiles[index]) for index in row_types)
    moment_floor = state_moment_floor(counts)
    incidence = build_incidence_model(
        ANCHOR_CELL_CAPACITIES,
        row_demands,
        maximum_pair_overlap=3,
    )
    residual_costs: list[Any] = []
    s4_costs: list[Any] = []
    for (left_ticket, right_ticket), overlaps in incidence.pair_cell_overlaps.items():
        left_type = row_types[left_ticket]
        right_type = row_types[right_ticket]
        allowed = _pair_event_correction_table(left_type, right_type)
        if not allowed:
            raise AssertionError("frontier state contains an impossible ticket-type pair")
        residual_values = tuple(row[4] for row in allowed)
        s4_values = tuple(row[5] for row in allowed)
        residual_cost = incidence.model.NewIntVar(
            min(residual_values),
            max(residual_values),
            f"residual_pair_{left_ticket}_{right_ticket}",
        )
        s4_cost = incidence.model.NewIntVar(
            min(s4_values),
            max(s4_values),
            f"s4_pair_{left_ticket}_{right_ticket}",
        )
        incidence.model.AddAllowedAssignments(
            [*overlaps, residual_cost, s4_cost],
            [list(row) for row in allowed],
        )
        residual_costs.append(residual_cost)
        s4_costs.append(s4_cost)
    incidence.model.Add(
        sum(residual_costs) >= moment_floor.residual_s2_lower_bound
    )
    incidence.model.Add(sum(s4_costs) >= moment_floor.s4_pairwise_minimum_floor)
    return _StateOptimizationModel(
        incidence=incidence,
        residual_pair_costs=tuple(residual_costs),
        s4_costs=tuple(s4_costs),
        moment_floor=moment_floor,
    )


def _build_compact_frequency_s4_model(
    counts: TypeCountVector,
) -> tuple[Any, Any]:
    """Build a relaxation coupling cell frequencies and pair-overlap histograms.

    Every actual support assignment maps into this model: per-label type
    frequencies determine the aggregate pair-overlap mass in each cell, while
    integer pair-pattern counts record the exact allowed overlap rows. The
    relaxation forgets ticket identities, so its minimum is a certified lower
    bound on the full support model's S4 minimum.
    """

    profiles = anchor_incidence_profiles()
    if len(counts) != len(profiles) or sum(counts) != OUTSIDE_TICKET_COUNT:
        raise ValueError("frontier count vector is malformed")
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model: Any = cp_model.CpModel()
    cell_attributes = ("shared", "a_only", "b_only", "outside")
    active_types = tuple(index for index, count in enumerate(counts) if count)
    pair_types = tuple(
        (left, right)
        for position, left in enumerate(active_types)
        for right in active_types[position:]
        if (counts[left] > 1 if left == right else True)
    )

    frequencies: dict[tuple[int, int], dict[int, Any]] = {}
    pair_products: dict[tuple[int, int, int, int], Any] = {}
    for cell_index, (attribute, capacity) in enumerate(
        zip(cell_attributes, ANCHOR_CELL_CAPACITIES, strict=True)
    ):
        for label in range(capacity):
            label_frequencies = {
                type_index: model.NewIntVar(
                    0,
                    counts[type_index],
                    f"frequency_{cell_index}_{label}_{type_index}",
                )
                for type_index in active_types
            }
            frequencies[cell_index, label] = label_frequencies
            for left_type, right_type in pair_types:
                maximum_product = (
                    math.comb(counts[left_type], 2)
                    if left_type == right_type
                    else counts[left_type] * counts[right_type]
                )
                product_variable = model.NewIntVar(
                    0,
                    maximum_product,
                    f"pair_mass_{cell_index}_{label}_{left_type}_{right_type}",
                )
                if left_type == right_type:
                    allowed_products = [
                        [frequency, math.comb(frequency, 2)]
                        for frequency in range(counts[left_type] + 1)
                    ]
                    model.AddAllowedAssignments(
                        [label_frequencies[left_type], product_variable],
                        allowed_products,
                    )
                else:
                    allowed_products = [
                        [left_frequency, right_frequency, left_frequency * right_frequency]
                        for left_frequency in range(counts[left_type] + 1)
                        for right_frequency in range(counts[right_type] + 1)
                    ]
                    model.AddAllowedAssignments(
                        [
                            label_frequencies[left_type],
                            label_frequencies[right_type],
                            product_variable,
                        ],
                        allowed_products,
                    )
                pair_products[cell_index, label, left_type, right_type] = (
                    product_variable
                )

        for type_index in active_types:
            total_incidence = counts[type_index] * getattr(
                profiles[type_index], attribute
            )
            model.Add(
                sum(
                    frequencies[cell_index, label][type_index]
                    for label in range(capacity)
                )
                == total_incidence
            )

        # Cell labels are interchangeable; sort their frequency vectors.
        place_value = 1
        type_weights: dict[int, int] = {}
        for type_index in reversed(active_types):
            type_weights[type_index] = place_value
            place_value *= counts[type_index] + 1
        label_codes = [
            sum(
                type_weights[type_index]
                * frequencies[cell_index, label][type_index]
                for type_index in active_types
            )
            for label in range(capacity)
        ]
        for left_code, right_code in pairwise(label_codes):
            model.Add(left_code >= right_code)

    objective_terms: list[Any] = []
    for left_type, right_type in pair_types:
        pair_count = (
            math.comb(counts[left_type], 2)
            if left_type == right_type
            else counts[left_type] * counts[right_type]
        )
        table = _pair_event_correction_table(left_type, right_type)
        pattern_counts = tuple(
            model.NewIntVar(
                0,
                pair_count,
                f"overlap_pattern_{left_type}_{right_type}_{row_index}",
            )
            for row_index in range(len(table))
        )
        model.Add(sum(pattern_counts) == pair_count)
        for cell_index, capacity in enumerate(ANCHOR_CELL_CAPACITIES):
            label_pair_mass = sum(
                pair_products[cell_index, label, left_type, right_type]
                for label in range(capacity)
            )
            pattern_pair_mass = sum(
                row[cell_index] * pattern_counts[row_index]
                for row_index, row in enumerate(table)
            )
            model.Add(label_pair_mass == pattern_pair_mass)
        objective_terms.extend(
            row[5] * pattern_counts[row_index]
            for row_index, row in enumerate(table)
        )
    objective = sum(objective_terms)
    model.Minimize(objective)
    return model, objective


def validate_support_assignment(
    counts: TypeCountVector,
    supports: tuple[tuple[int, ...], ...],
) -> bool:
    """Independently verify a concrete support witness for a frontier vector."""

    profiles = anchor_incidence_profiles()
    if len(counts) != len(profiles) or sum(counts) != OUTSIDE_TICKET_COUNT:
        return False
    row_types = tuple(
        type_index
        for type_index, count in enumerate(counts)
        for _ in range(count)
    )
    if len(supports) != OUTSIDE_TICKET_COUNT:
        return False
    if any(
        len(ticket) != DRAW_SIZE
        or len(set(ticket)) != DRAW_SIZE
        or any(not 0 <= label < POOL_SIZE for label in ticket)
        for ticket in supports
    ):
        return False
    cell_ranges = (
        range(0, 3),
        range(3, 6),
        range(6, 9),
        range(9, POOL_SIZE),
    )
    for ticket, type_index in zip(supports, row_types, strict=True):
        if tuple(
            sum(label in cell for label in ticket) for cell in cell_ranges
        ) != _cells(profiles[type_index]):
            return False
    for left_ticket in range(len(supports)):
        for right_ticket in range(left_ticket + 1, len(supports)):
            if len(set(supports[left_ticket]) & set(supports[right_ticket])) > 3:
                return False
    return True


def decode_support_witness_bitmasks(
    bitmasks: tuple[int, ...] | list[int],
) -> tuple[tuple[int, ...], ...]:
    """Expand compact label-membership bitmasks into ticket supports."""

    if any(type(mask) is not int or mask < 0 or mask >= 1 << POOL_SIZE for mask in bitmasks):
        raise ValueError("support witness contains an invalid label bitmask")
    return tuple(
        tuple(label for label in range(POOL_SIZE) if mask & (1 << label))
        for mask in bitmasks
    )


def support_model_status(
    cell_capacities: tuple[int, ...],
    row_demands: tuple[tuple[int, ...], ...],
    maximum_pair_overlap: int,
    *,
    wall_limit_seconds: float = 2.0,
) -> str:
    """Return a bounded CP-SAT status for the generic support model."""

    solver_runtime_preflight()
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    incidence = build_incidence_model(
        cell_capacities,
        row_demands,
        maximum_pair_overlap=maximum_pair_overlap,
    )
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = wall_limit_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    return str(solver.StatusName(solver.Solve(incidence.model)))


def witness_costs(
    counts: TypeCountVector,
    supports: tuple[tuple[int, ...], ...],
) -> tuple[int, int]:
    if not validate_support_assignment(counts, supports):
        raise AssertionError("CP-SAT support witness failed the independent check")
    row_types = tuple(
        type_index
        for type_index, count in enumerate(counts)
        for _ in range(count)
    )
    cell_ranges = (
        range(0, 3),
        range(3, 6),
        range(6, 9),
        range(9, POOL_SIZE),
    )
    residual_total = 0
    s4_total = 0
    for left_ticket in range(len(supports)):
        for right_ticket in range(left_ticket + 1, len(supports)):
            overlap: CellTuple = tuple(
                len(set(supports[left_ticket]) & set(supports[right_ticket]) & set(cell))
                for cell in cell_ranges
            )  # type: ignore[assignment]
            table = _pair_event_correction_table(
                row_types[left_ticket], row_types[right_ticket]
            )
            matched = next(
                row for row in table if row[:4] == overlap
            )
            residual_total += matched[4]
            s4_total += matched[5]
    return residual_total, s4_total


def solver_runtime_preflight() -> dict[str, str]:
    """Verify the exact active Python/OR-Tools runtime before any solver batch."""

    try:
        ortools_version = version("ortools")
    except PackageNotFoundError as error:
        raise RuntimeError(
            "OR-Tools is unavailable in the active execution environment"
        ) from error
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError("solver batch requires the project-configured Python 3.13 runtime")
    if not ortools_version.startswith("9.15."):
        raise RuntimeError("solver batch requires the locked OR-Tools 9.15 series")
    return {
        "python": sys.version.split()[0],
        "ortools": ortools_version,
    }


def solve_compact_frequency_s4_lower_bound(
    state_id: str,
    *,
    native_wall_limit_seconds: float = COMPACT_S4_NATIVE_WALL_LIMIT_SECONDS,
) -> dict[str, Any]:
    """Solve the label-frequency relaxation and return a certified S4 lower bound."""

    runtime = solver_runtime_preflight()
    state = next(
        (item for item in load_bearing_frontier_states() if item.identifier == state_id),
        None,
    )
    if state is None:
        raise ValueError("unknown load-bearing frontier state identifier")
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model, objective = _build_compact_frequency_s4_model(state.witness_counts)
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = native_wall_limit_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = 0
    started = time.monotonic()
    status: Any = solver.Solve(model)
    wall_seconds = time.monotonic() - started
    status_name = solver.StatusName(status)
    relaxation_objective: int | None = None
    certified_lower_bound = state_moment_floor(
        state.witness_counts
    ).s4_pairwise_minimum_floor
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        relaxation_objective = int(solver.Value(objective))
        solver_bound = (
            relaxation_objective
            if status == cp_model.OPTIMAL
            else math.ceil(solver.BestObjectiveBound() - 1e-7)
        )
        certified_lower_bound = max(certified_lower_bound, solver_bound)
    return {
        "state_id": state.identifier,
        "objective": "compact_s4_frequency_relaxation",
        "status": status_name,
        "native_wall_limit_seconds": native_wall_limit_seconds,
        "native_wall_time_seconds": wall_seconds,
        "solver_wall_time_seconds": solver.WallTime(),
        "runtime": runtime,
        "relaxation_objective": relaxation_objective,
        "relaxation_optimal": status == cp_model.OPTIMAL,
        "certified_minimum_lower_bound": certified_lower_bound,
    }


def solve_one_state(
    state_id: str,
    objective: str,
    *,
    native_wall_limit_seconds: float = FULL_SUPPORT_S4_NATIVE_WALL_LIMIT_SECONDS,
) -> dict[str, Any]:
    """Solve one reduced frontier state with a native CP-SAT wall limit."""

    cp_model: Any = import_module("ortools.sat.python.cp_model")

    runtime = solver_runtime_preflight()
    state = next(
        (item for item in load_bearing_frontier_states() if item.identifier == state_id),
        None,
    )
    if state is None:
        raise ValueError("unknown load-bearing frontier state identifier")
    if objective != "s4":
        raise ValueError("the reduced solver objective must be s4")
    optimization = _build_state_optimization_model(state.witness_counts)
    s4_expression = sum(optimization.s4_costs)
    optimization.incidence.model.Minimize(s4_expression)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = native_wall_limit_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = 0
    started = time.monotonic()
    status: Any = solver.Solve(optimization.incidence.model)
    wall_seconds = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "state_id": state.identifier,
        "objective": objective,
        "status": status_name,
        "native_wall_limit_seconds": native_wall_limit_seconds,
        "native_wall_time_seconds": wall_seconds,
        "solver_wall_time_seconds": solver.WallTime(),
        "runtime": runtime,
        "certified_minimum_lower_bound": None,
        "incumbent_objective": None,
        "support_witness_sha256": None,
        "witness_residual_pair_s2": None,
        "witness_s4": None,
        "support_witness": None,
        "minimum_proven": False,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        supports = tuple(
            tuple(
                label
                for label, variable in enumerate(row)
                if solver.BooleanValue(variable)
            )
            for row in optimization.incidence.ticket_labels
        )
        if not validate_support_assignment(state.witness_counts, supports):
            raise AssertionError("solver returned an invalid support assignment")
        witness_s2, witness_s4 = witness_costs(state.witness_counts, supports)
        if witness_s2 < optimization.moment_floor.residual_s2_lower_bound:
            raise AssertionError("support witness violates its certified S2 floor")
        if witness_s4 < optimization.moment_floor.s4_pairwise_minimum_floor:
            raise AssertionError("support witness violates its certified S4 floor")
        objective_value = witness_s4
        lower_bound = max(
            math.ceil(solver.BestObjectiveBound()),
            optimization.moment_floor.s4_pairwise_minimum_floor,
        )
        result.update(
            {
                "certified_minimum_lower_bound": lower_bound,
                "incumbent_objective": objective_value,
                "support_witness_sha256": sha256(
                    repr(supports).encode("ascii")
                ).hexdigest(),
                "witness_residual_pair_s2": witness_s2,
                "witness_s4": witness_s4,
                "support_witness": [list(ticket) for ticket in supports],
                "minimum_proven": lower_bound == objective_value,
            }
        )
        if status == cp_model.OPTIMAL and lower_bound != objective_value:
            raise AssertionError("optimal CP-SAT objective and bound disagree")
    return result


def run_one_with_external_timeout(
    state_id: str,
    objective: str,
) -> dict[str, Any]:
    """Run one native-limited solve under a parent-process hard timeout."""

    command = [
        sys.executable,
        "-m",
        "lottolab.research.b649_k20_r3_frontier_realizability_bound_r8",
        "--solve-one",
        state_id,
        objective,
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=FULL_SUPPORT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "state_id": state_id,
            "objective": objective,
            "status": "EXTERNAL_TIMEOUT",
            "external_wall_time_seconds": time.monotonic() - started,
            "external_hard_timeout_seconds": FULL_SUPPORT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS,
            "certified_minimum_lower_bound": None,
        }
    wall_seconds = time.monotonic() - started
    if completed.returncode != 0:
        return {
            "state_id": state_id,
            "objective": objective,
            "status": "PROCESS_ERROR",
            "external_wall_time_seconds": wall_seconds,
            "stderr": completed.stderr[-2_000:],
            "certified_minimum_lower_bound": None,
        }
    result = json.loads(completed.stdout)
    result["external_wall_time_seconds"] = wall_seconds
    result["external_hard_timeout_seconds"] = (
        FULL_SUPPORT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS
    )
    return result


def run_compact_with_external_timeout(state_id: str) -> dict[str, Any]:
    """Run the compact S4 lower-bound solve with a parent hard timeout."""

    state = next(
        (item for item in load_bearing_frontier_states() if item.identifier == state_id),
        None,
    )
    if state is None:
        raise ValueError("unknown load-bearing frontier state identifier")
    supports = decode_support_witness_bitmasks(SUPPORT_WITNESS_BITMASKS[state_id])
    if not validate_support_assignment(state.witness_counts, supports):
        raise AssertionError("frozen support witness failed independent realizability checks")
    witness_s2, witness_s4 = witness_costs(state.witness_counts, supports)
    fallback: dict[str, Any] = {
        "state_id": state_id,
        "objective": "compact_s4_frequency_relaxation",
        "status": "COMPACT_UNKNOWN",
        "certified_minimum_lower_bound": state_moment_floor(
            state.witness_counts
        ).s4_pairwise_minimum_floor,
    }
    command = [
        sys.executable,
        "-m",
        "lottolab.research.b649_k20_r3_frontier_realizability_bound_r8",
        "--solve-compact",
        state_id,
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=COMPACT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        result = fallback
        result.update(
            {
                "external_wall_time_seconds": time.monotonic() - started,
                "external_hard_timeout_seconds": (
                    COMPACT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS
                ),
            }
        )
    else:
        wall_seconds = time.monotonic() - started
        if completed.returncode == 0:
            result = json.loads(completed.stdout)
            result["external_wall_time_seconds"] = wall_seconds
            result["external_hard_timeout_seconds"] = (
                COMPACT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS
            )
        else:
            result = fallback
            result.update(
                {
                    "status": "PROCESS_ERROR",
                    "external_wall_time_seconds": wall_seconds,
                    "stderr": completed.stderr[-2_000:],
                }
            )
    lower_bound = int(result["certified_minimum_lower_bound"])
    if lower_bound > witness_s4:
        raise AssertionError("compact relaxation bound exceeds a realized S4 witness")
    result.update(
        {
            "incumbent_objective": witness_s4,
            "support_witness_sha256": sha256(repr(supports).encode("ascii")).hexdigest(),
            "witness_residual_pair_s2": witness_s2,
            "witness_s4": witness_s4,
            "support_witness": [list(ticket) for ticket in supports],
            "minimum_proven": lower_bound == witness_s4,
        }
    )
    return result


def run_solver_batch() -> dict[str, Any]:
    """Classify frozen support witnesses and certify compact S4 lower bounds."""

    runtime = solver_runtime_preflight()
    started = time.monotonic()
    states = load_bearing_frontier_states()
    runs = [
        run_compact_with_external_timeout(state.identifier)
        for state in states
    ]
    elapsed = time.monotonic() - started
    by_state: list[dict[str, Any]] = []
    tightened_state_bounds: list[int] = []

    for state, solver_run in zip(states, runs, strict=True):
        moment_floor = state_moment_floor(state.witness_counts)
        support_witness = solver_run.get("support_witness")
        if support_witness is not None and validate_support_assignment(
            state.witness_counts,
            tuple(tuple(ticket) for ticket in support_witness),
        ):
            classification = "REALIZABLE"
        elif solver_run["status"] == "INFEASIBLE":
            classification = "UNREALIZABLE"
        else:
            classification = "UNKNOWN"

        solver_lower = solver_run.get("certified_minimum_lower_bound")
        s4_lower = moment_floor.s4_pairwise_minimum_floor
        if solver_lower is not None:
            s4_lower = max(s4_lower, int(solver_lower))
        witness_s4 = solver_run.get("witness_s4")
        minimum_proven = (
            witness_s4 is not None and int(witness_s4) == s4_lower
        )
        support_witness_bitmasks = (
            [
                sum(1 << label for label in ticket)
                for ticket in support_witness
            ]
            if support_witness is not None
            else None
        )
        solver_run_summary = {
            key: value
            for key, value in solver_run.items()
            if key != "support_witness"
        }

        anchor_s2 = sum(
            count * profile.pair_recovery_cost
            for count, profile in zip(
                state.witness_counts,
                anchor_incidence_profiles(),
                strict=True,
            )
        )
        state_bound = (
            JOINT_EXPRESSION_CONSTANT
            - anchor_s2
            + state.maximum_joint_s3
            - (
                moment_floor.residual_s2_lower_bound
                + PAIR_MULTIPLICITY_DIVISOR
                - 1
            )
            // PAIR_MULTIPLICITY_DIVISOR
        )
        if classification == "UNREALIZABLE":
            reported_state_bound = None
        elif classification == "REALIZABLE":
            reported_state_bound = state_bound
            tightened_state_bounds.append(state_bound)
        else:
            reported_state_bound = state.current_upper_bound
            tightened_state_bounds.append(state.current_upper_bound)

        by_state.append(
            {
                "state_id": state.identifier,
                "joint_s2": state.joint_s2,
                "s3_max_at_state": state.maximum_joint_s3,
                "current_upper_bound": state.current_upper_bound,
                "classification": classification,
                "symmetric_count_vector_member_count": 2,
                "witness_counts_sparse": [
                    [index, count]
                    for index, count in enumerate(state.witness_counts)
                    if count
                ],
                "mirrored_counts_sparse": [
                    [index, count]
                    for index, count in enumerate(state.mirrored_counts)
                    if count
                ],
                "residual_s2_certified_lower_bound": (
                    moment_floor.residual_s2_lower_bound
                ),
                "residual_s2_certificate": {
                    "type_pair_minimum_sum": moment_floor.pair_minimum_sum,
                    "minimum_outside_slope": str(moment_floor.minimum_outside_slope),
                    "outside_incidence_total": moment_floor.outside_incidence_total,
                    "balanced_outside_pair_mass_floor": (
                        moment_floor.outside_pair_mass_floor
                    ),
                    "s4_pairwise_minimum_floor": (
                        moment_floor.s4_pairwise_minimum_floor
                    ),
                },
                "s4_min_at_s3_max": (
                    int(witness_s4)
                    if witness_s4 is not None and minimum_proven
                    else None
                ),
                "s4_minimum_certified_lower_bound": s4_lower,
                "s4_minimum_proven": minimum_proven,
                "s4_solver_status": solver_run["status"],
                "s4_lower_bound_source": "COMPACT_FREQUENCY_RELAXATION",
                "s4_relaxation_optimal": solver_run.get("relaxation_optimal", False),
                "s4_feasible_witness_at_s3_max": (
                    int(witness_s4) if witness_s4 is not None else None
                ),
                "s3_at_s4_feasible_witness": (
                    state.maximum_joint_s3
                    if witness_s4 is not None
                    else None
                ),
                "residual_s2_at_s4_feasible_witness": (
                    solver_run.get("witness_residual_pair_s2")
                ),
                "s4_support_witness_sha256": (
                    solver_run.get("support_witness_sha256")
                ),
                "support_witness_bitmasks": support_witness_bitmasks,
                "recomputed_r3_bound": reported_state_bound,
                "solver_run": solver_run_summary,
            }
        )

    unrealizable = sum(
        row["classification"] == "UNREALIZABLE" for row in by_state
    )
    realizable = sum(row["classification"] == "REALIZABLE" for row in by_state)
    unknown = sum(row["classification"] == "UNKNOWN" for row in by_state)
    r3_bound = max(
        R7_TAIL_BOUND,
        R7_FRONTIER_NONLOAD_BOUND,
        *tightened_state_bounds,
    )
    all_s4_certified = all(
        row["classification"] == "UNREALIZABLE" or row["s4_minimum_proven"]
        for row in by_state
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": (
            "CERTIFIED"
            if unknown == 0 and all_s4_certified
            else "PARTIAL_CERTIFICATE"
        ),
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "R7_FRONTIER_SHA256": R7_FRONTIER_SHA256,
        "R7_RESIDUAL_STATE_COUNT": R7_RESIDUAL_STATE_COUNT,
        "R7_FRONTIER_SIZE": R7_FRONTIER_SIZE,
        "CURRENT_AUTHORITY_BOUNDS": {
            "R3": CURRENT_R3_BOUND,
            "R4": CURRENT_R4_BOUND,
            "R5": CURRENT_R5_BOUND,
            "R6": CURRENT_R6_BOUND,
        },
        "LOAD_BEARING_FRONTIER_STATE_COUNT": len(by_state),
        "LOAD_BEARING_COUNT_VECTOR_MEMBER_COUNT": 2 * len(by_state),
        "UNREALIZABLE_STATE_COUNT": unrealizable,
        "REALIZABLE_STATE_COUNT": realizable,
        "UNKNOWN_STATE_COUNT": unknown,
        "R3_LOAD_BEARING_FRONTIER_STATES": by_state,
        "S3_MAX": max(row["s3_max_at_state"] for row in by_state),
        "S4_MIN_AT_S3_MAX": {
            row["state_id"]: row["s4_min_at_s3_max"] for row in by_state
        },
        "JOINT_S3_S4_WITNESS": {
            row["state_id"]: {
                "S3": row["s3_at_s4_feasible_witness"],
                "S4_MINIMUM": row["s4_min_at_s3_max"],
                "S4_FEASIBLE_WITNESS": row["s4_feasible_witness_at_s3_max"],
                "RESIDUAL_S2_AT_S4_FEASIBLE_WITNESS": (
                    row["residual_s2_at_s4_feasible_witness"]
                ),
            }
            for row in by_state
        },
        "HIGHER_ORDER_CORRECTION": (
            "NOT_COMPUTED; a full residual event-multiplicity census is outside "
            "the seven-state reduction."
        ),
        "R3_BOUND": r3_bound,
        "R3_STATUS": (
            "TIGHTENED_OPEN"
            if r3_bound < CURRENT_R3_BOUND
            else "UNCHANGED_OR_INCOMPLETE"
        ),
        "R3_BELOW_R5": r3_bound < CURRENT_R5_BOUND,
        "SUCCESS_A": r3_bound < CURRENT_R5_BOUND,
        "SUCCESS_B": r3_bound < CURRENT_R3_BOUND,
        "SUCCESS_C": unknown == 0,
        "INCUMBENT": INCUMBENT,
        "LEAF_GAP": r3_bound - INCUMBENT,
        "SOLVER_STATUS": {
            "counts": {
                name: sum(run["status"] == name for run in runs)
                for name in sorted({run["status"] for run in runs})
            },
            "runs": [
                {
                    "state_id": run["state_id"],
                    "objective": run["objective"],
                    "status": run["status"],
                }
                for run in runs
            ],
        },
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "native_seconds_per_run": COMPACT_S4_NATIVE_WALL_LIMIT_SECONDS,
            "external_hard_timeout_seconds_per_run": (
                COMPACT_S4_EXTERNAL_HARD_TIMEOUT_SECONDS
            ),
            "worker_count": SOLVER_WORKERS,
            "solver_model": "COMPACT_FREQUENCY_RELAXATION",
        },
        "SOLVER_ACTUAL_WALL_TIME": {
            "batch_external_seconds": elapsed,
            "native_solver_seconds_sum": sum(
                float(run.get("solver_wall_time_seconds", 0.0)) for run in runs
            ),
        },
        "SOLVER_CERTIFIED_BOUND": {
            row["state_id"]: {
                "RESIDUAL_S2": row["residual_s2_certified_lower_bound"],
                "S4_MINIMUM": row["s4_minimum_certified_lower_bound"],
            }
            for row in by_state
        },
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "FOCUSED_TESTS": "NOT_RUN",
        "RUFF": "NOT_RUN",
        "PYRIGHT": "NOT_RUN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def write_compact_result(result: dict[str, Any], path: Path = RESULT_PATH) -> None:
    """Write a new compact result without replacing pre-existing evidence."""

    if path.exists():
        raise FileExistsError(f"result already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solve-one", nargs=2, metavar=("STATE_ID", "OBJECTIVE"))
    parser.add_argument("--solve-compact", metavar="STATE_ID")
    parser.add_argument("--run-batch", action="store_true")
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    arguments = parser.parse_args(argv)
    if arguments.solve_one:
        state_id, objective = arguments.solve_one
        print(
            json.dumps(
                solve_one_state(state_id, objective),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    if arguments.solve_compact:
        print(
            json.dumps(
                solve_compact_frequency_s4_lower_bound(arguments.solve_compact),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    if not arguments.run_batch:
        parser.error("select --solve-one or --run-batch")
    result = run_solver_batch()
    write_compact_result(result, arguments.output)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "R3_BOUND": result["R3_BOUND"],
                "REALIZABLE_STATE_COUNT": result["REALIZABLE_STATE_COUNT"],
                "UNREALIZABLE_STATE_COUNT": result["UNREALIZABLE_STATE_COUNT"],
                "UNKNOWN_STATE_COUNT": result["UNKNOWN_STATE_COUNT"],
                "RESULT_PATH": str(arguments.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
