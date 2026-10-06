"""Exact K20 R4 threshold descent below the current R3 portfolio bound.

The module reconstructs stable R10 state identities, freezes exactly the
prior-envelope interval above R3 and at or below the old R4 ceiling, and
classifies those states without revisiting the already-classified R11 frontier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from itertools import combinations, pairwise
from pathlib import Path
from time import monotonic
from typing import Any, cast

from ortools.sat.python import cp_model

from lottolab.research import b649_k20_r4_frontier_realizability_r11 as r11_module
from lottolab.research import b649_k20_r4_joint_residual_r10 as r10_module
from lottolab.research.b649_k20_r4_dangerous_residual_union_r9 import (
    residual_pair_cost_rows,
)
from lottolab.research.b649_k20_r4_frontier_realizability_r11 import (
    ANCHOR_UNION,
    EXPECTED_REALIZATIONS,
    GOOD_SIGNATURE,
    MAXIMUM_OUTSIDE_PAIR_MASS,
    NATIVE_SUPPORT_WALL_LIMIT_SECONDS,
    SPECIAL_A_SIGNATURE,
    SPECIAL_B_SIGNATURE,
    SUPPORT_TYPE_GOOD,
    SUPPORT_TYPE_SPECIAL,
    DangerousFrontierState,
    SupportClassification,
    SupportMatrix,
    certified_s3_upper_bound,
    load_r9_residual_classes,
    maximum_edges_with_components,
    select_dangerous_frontier_states,
)

BASE_HEAD = "813392e28f08a54f58962663987a9ae75bc9d38f"
BASE_TREE = "f037dd9a97760580d21fa88ff4f92be8d20929c5"
TASK_BRANCH = "codex/b649-k20-r4-threshold-descent-below-r3-r13"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_R4_THRESHOLD_DESCENT_BELOW_R3_R13"
)
TASK_ID = "B649_K20_R4_THRESHOLD_DESCENT_BELOW_R3_R13"

R10_RESULT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/b649-k20-r4-joint-residual-r10-result.json"
)
R10_SOURCE_RELATIVE_PATH = Path("src/lottolab/research/b649_k20_r4_joint_residual_r10.py")
R9_RESULT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/b649-k20-r4-dangerous-residual-union-r9-result.json"
)
R11_SOURCE_RELATIVE_PATH = Path("src/lottolab/research/b649_k20_r4_frontier_realizability_r11.py")
R11_RESULT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/b649-k20-r4-frontier-realizability-r11-result.json"
)
EXPECTED_R10_RESULT_SHA256 = "2829fa4182fed169ba2b46695560efd244566c3dc3649ff50fc9b64c7d6e3d01"
EXPECTED_R10_SOURCE_SHA256 = "8e513e65cec6b81e45740c3f7468a11934d6885e77624527390f88ec2459e32d"
EXPECTED_R9_RESULT_SHA256 = "0024f79c9ed7bf4f5b00a207aa80e5adc8fa18b9d7f7946f4b0e192cd60ce1da"
EXPECTED_R11_SOURCE_SHA256 = "536131e831bbf431784d4297f3c8a21fa438c6e6982b34dcb9705337e50e6ff5"
EXPECTED_R11_RESULT_SHA256 = "b3cb322122619b1786b74114ead4533791c61f55bf371c99247f1904b4fbc043"

NEW_R3_BOUND = 350_545_749
OLD_R4_THRESHOLD = 350_778_728
CURRENT_R5_BOUND = 349_009_248
CURRENT_R6_BOUND = 343_869_728
PRIOR_R11_REALIZABLE_BOUND = 300_547_996
INCUMBENT = 313_239_661
EXTERNAL_HARD_TIMEOUT_SECONDS = 300
R13_LEGACY_SUPPORT_WALL_LIMIT_SECONDS = 30
EXPECTED_JOINT_STATE_COUNT = 9_384
EXPECTED_R10_FRONTIER_SEGMENT_COUNT = 45
EXPECTED_R11_HIGH_STATE_COUNT = 174
EXPECTED_NEW_STATE_COUNT = 228
EXPECTED_NEW_CLASS_MASS_COUNT = 38
EXPECTED_S3_MAX_IN_NEW_INTERVAL = 14_737_408
EXPECTED_R11_OTHER_STATE_S3_MAX = 14_991_088
EXPECTED_GLOBAL_S3_MAX = 15_214_752
EXPECTED_GLOBAL_S4_MIN = 1_738_100

type PairEdgeMap = Mapping[tuple[int, int], Any]
type SupportResult = tuple[bool, str | None]


@dataclass(frozen=True)
class ThresholdFrontierSelection:
    """Deterministically frozen R10 state interval for this threshold descent."""

    states: tuple[DangerousFrontierState, ...]
    generated_joint_state_count: int
    source_frontier_segment_count: int
    above_old_threshold_state_count: int
    at_or_below_new_threshold_state_count: int
    source_r10_sha256: str
    source_r9_sha256: str
    source_r11_sha256: str
    state_sha256: str

    @property
    def class_mass_count(self) -> int:
        return len({(row.realization, row.outside_pair_mass) for row in self.states})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return cast(dict[str, object], value)


def _ceil_div(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator < 1:
        raise ValueError("ceil division requires a nonnegative numerator and divisor")
    return (numerator + denominator - 1) // denominator


def _state_digest(states: tuple[DangerousFrontierState, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            [asdict(row) for row in states],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _verify_source_authorities(
    repository_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    r10_result_path = repository_root / R10_RESULT_RELATIVE_PATH
    r10_source_path = repository_root / R10_SOURCE_RELATIVE_PATH
    r9_result_path = repository_root / R9_RESULT_RELATIVE_PATH
    r11_source_path = repository_root / R11_SOURCE_RELATIVE_PATH
    r11_result_path = repository_root / R11_RESULT_RELATIVE_PATH

    r10_digest = _sha256(r10_result_path)
    r9_digest = _sha256(r9_result_path)
    r11_digest = _sha256(r11_result_path)
    if r10_digest != EXPECTED_R10_RESULT_SHA256:
        raise ValueError("the pinned R10 result identity changed")
    if _sha256(r10_source_path) != EXPECTED_R10_SOURCE_SHA256:
        raise ValueError("the pinned R10 source identity changed")
    if r9_digest != EXPECTED_R9_RESULT_SHA256:
        raise ValueError("the pinned R9 result identity changed")
    if _sha256(r11_source_path) != EXPECTED_R11_SOURCE_SHA256:
        raise ValueError("the pinned R11 source identity changed")
    if r11_digest != EXPECTED_R11_RESULT_SHA256:
        raise ValueError("the pinned R11 result identity changed")

    r10_result = _json_object(
        json.loads(r10_result_path.read_text(encoding="utf-8")),
        "R10 result",
    )
    r11_result = _json_object(
        json.loads(r11_result_path.read_text(encoding="utf-8")),
        "R11 result",
    )
    if (
        r10_result.get("TASK_ID") != "B649_K20_R4_THREE_REALIZATION_JOINT_RESIDUAL_R10"
        or r10_result.get("JOINT_STATE_COUNT") != EXPECTED_JOINT_STATE_COUNT
        or r10_result.get("S2_S3_FRONTIER_SIZE") != EXPECTED_R10_FRONTIER_SEGMENT_COUNT
        or r10_result.get("R4_BOUND") != 351_106_608
    ):
        raise ValueError("the pinned R10 frontier authority changed")
    if (
        r11_result.get("TASK_ID") != "B649_K20_R4_FRONTIER_MAXIMIZER_REALIZABILITY_R11"
        or r11_result.get("DANGEROUS_FRONTIER_STATE_COUNT") != EXPECTED_R11_HIGH_STATE_COUNT
        or r11_result.get("UNREALIZABLE_STATE_COUNT") != 141
        or r11_result.get("REALIZABLE_STATE_COUNT") != 33
        or r11_result.get("DANGEROUS_REALIZABLE_R4_BOUND") != PRIOR_R11_REALIZABLE_BOUND
        or r11_result.get("R4_BOUND") != OLD_R4_THRESHOLD
    ):
        raise ValueError("the pinned R11 classification authority changed")
    return r10_result, r11_result


def select_threshold_frontier_states(repository_root: Path) -> ThresholdFrontierSelection:
    """Reconstruct all R10 states and select exactly NEW_R3 < bound <= OLD_R4."""

    r10_result, _r11_result = _verify_source_authorities(repository_root)
    envelopes_value = r10_result.get("JOINT_RESIDUAL_ENVELOPE")
    if not isinstance(envelopes_value, list):
        raise ValueError("R10 must contain all three pinned realization envelopes")
    envelopes = cast(list[object], envelopes_value)
    if len(envelopes) != len(EXPECTED_REALIZATIONS):
        raise ValueError("R10 must contain all three pinned realization envelopes")

    classes = load_r9_residual_classes(repository_root / R9_RESULT_RELATIVE_PATH)
    if tuple(dict.fromkeys(row.vector_label for row in classes)) != EXPECTED_REALIZATIONS:
        raise ValueError("R9 realization order disagrees with R10")

    old_selection = select_dangerous_frontier_states(repository_root)
    old_state_ids = {row.state_id for row in old_selection.states}
    if len(old_state_ids) != EXPECTED_R11_HIGH_STATE_COUNT:
        raise ValueError("R11's prior high-threshold selection changed")
    if old_selection.source_r10_sha256 != EXPECTED_R10_RESULT_SHA256:
        raise ValueError("R11 did not consume the pinned R10 result")

    state_rows: list[DangerousFrontierState] = []
    above_old_state_ids: set[str] = set()
    generated_joint_state_count = 0
    frontier_segment_count = 0
    below_or_at_new_state_count = 0

    for envelope_value in envelopes:
        envelope = _json_object(envelope_value, "R10 realization envelope")
        label_value = envelope.get("VECTOR_LABEL")
        if not isinstance(label_value, str) or label_value not in EXPECTED_REALIZATIONS:
            raise ValueError("R10 contains an unknown realization label")
        residual_class = next(row for row in classes if row.vector_label == label_value)
        pair_costs = residual_pair_cost_rows(residual_class.type_counts)
        minimum_s2, _ = r10_module._pair_mass_s2_envelope(  # pyright: ignore[reportPrivateUsage]
            pair_costs,
            MAXIMUM_OUTSIDE_PAIR_MASS,
            monotonic() + r10_module.NATIVE_WALL_LIMIT_SECONDS,
        )
        selected_seven = r10_module.maximum_selected_seven_frequency_by_pair_mass(
            residual_class.outside_incidences,
            MAXIMUM_OUTSIDE_PAIR_MASS,
            monotonic() + r10_module.NATIVE_WALL_LIMIT_SECONDS,
        )

        mass_count = 0
        for mass in range(
            residual_class.outside_pair_mass_floor,
            MAXIMUM_OUTSIDE_PAIR_MASS + 1,
        ):
            top_seven = selected_seven[mass]
            if top_seven is None:
                continue
            multiplicity_cap = min(
                r10_module.OUTSIDE_TICKET_COUNT,
                (top_seven + residual_class.special_anchor_incidences) // 3,
            )
            if multiplicity_cap < 1:
                continue
            mass_count += 1
            envelope_bound = (
                ANCHOR_UNION
                + residual_class.residual_s1
                - _ceil_div(2 * minimum_s2[mass], multiplicity_cap)
            )
            for component_count in range(1, 7):
                state = DangerousFrontierState(
                    realization=label_value,
                    component_count=component_count,
                    outside_pair_mass=mass,
                    minimum_s2=minimum_s2[mass],
                    maximum_selected_seven_frequency=top_seven,
                    multiplicity_cap=multiplicity_cap,
                    current_r4_envelope=envelope_bound,
                )
                if envelope_bound > OLD_R4_THRESHOLD:
                    above_old_state_ids.add(state.state_id)
                elif envelope_bound <= NEW_R3_BOUND:
                    below_or_at_new_state_count += 1
                else:
                    state_rows.append(state)
        state_count = mass_count * 6
        if envelope.get("JOINT_STATE_COUNT") != state_count:
            raise ValueError("an R10 per-realization joint-state count changed")
        if envelope.get("S2_S3_FRONTIER_SIZE") != len(
            cast(list[object], envelope.get("S2_S3_FRONTIER", []))
        ):
            raise ValueError("an R10 per-realization frontier segment count changed")
        generated_joint_state_count += state_count
        frontier_segment_count += cast(int, envelope["S2_S3_FRONTIER_SIZE"])

    if generated_joint_state_count != EXPECTED_JOINT_STATE_COUNT:
        raise ValueError("the R10 joint-state census changed")
    if frontier_segment_count != EXPECTED_R10_FRONTIER_SEGMENT_COUNT:
        raise ValueError("the R10 frontier segment census changed")
    if above_old_state_ids != old_state_ids:
        raise ValueError("the prior R11 states are not exactly the states above OLD_R4")
    if len(state_rows) != EXPECTED_NEW_STATE_COUNT:
        raise ValueError("the new R3-to-R4 interval no longer contains 228 states")
    if len({(row.realization, row.outside_pair_mass) for row in state_rows}) != (
        EXPECTED_NEW_CLASS_MASS_COUNT
    ):
        raise ValueError("the new threshold interval's class/mass count changed")

    states = tuple(
        sorted(
            state_rows,
            key=lambda row: (
                EXPECTED_REALIZATIONS.index(row.realization),
                row.component_count,
                row.outside_pair_mass,
            ),
        )
    )
    if old_state_ids.intersection(row.state_id for row in states):
        raise AssertionError("an already-classified R11 state entered the new interval")
    return ThresholdFrontierSelection(
        states=states,
        generated_joint_state_count=generated_joint_state_count,
        source_frontier_segment_count=frontier_segment_count,
        above_old_threshold_state_count=len(above_old_state_ids),
        at_or_below_new_threshold_state_count=below_or_at_new_state_count,
        source_r10_sha256=EXPECTED_R10_RESULT_SHA256,
        source_r9_sha256=EXPECTED_R9_RESULT_SHA256,
        source_r11_sha256=EXPECTED_R11_RESULT_SHA256,
        state_sha256=_state_digest(states),
    )


def _add_dense_three_component_constraints(
    model: Any,
    pair_edges: PairEdgeMap,
    vertex_count: int,
    minimum_pair_mass: int,
) -> None:
    """Encode exactly three components above the four-component edge ceiling.

    A simple graph on 18 vertices with at least 112 edges cannot have four
    components because the extremal four-component graph has 105 edges.
    Requiring two isolated vertices therefore forces exactly three.
    """

    maximum_four_component_edges = maximum_edges_with_components(vertex_count, 4)
    if vertex_count != 18 or minimum_pair_mass <= maximum_four_component_edges:
        raise ValueError("the dense three-component reduction requires 18 tickets and M > 105")

    isolates = [
        model.NewBoolVar(f"three_component_isolate_{ticket}") for ticket in range(vertex_count)
    ]
    model.Add(sum(isolates) == 2)
    model.Add(sum(pair_edges.values()) >= minimum_pair_mass)
    for ticket in range(vertex_count):
        for other in range(vertex_count):
            if ticket == other:
                continue
            edge_key = (ticket, other) if ticket < other else (other, ticket)
            model.Add(pair_edges[edge_key] == 0).OnlyEnforceIf(isolates[ticket])


def _uniform_pair_cost(cost_rows: tuple[tuple[int, ...], ...], overlap: int, label: str) -> int:
    values = {row[overlap] for row in cost_rows}
    if len(values) != 1:
        raise ValueError(f"{label} residual pair costs are not uniform")
    return next(iter(values))


def _special_ticket_degree_required(state: DangerousFrontierState) -> int | None:
    """Recover the special-ticket graph degree forced by exact minimum S2."""

    if state.support_type != SUPPORT_TYPE_SPECIAL:
        raise ValueError("special-ticket degree applies only to special support states")
    good_costs = residual_pair_cost_rows(((GOOD_SIGNATURE, 18),))
    special_costs = residual_pair_cost_rows(((GOOD_SIGNATURE, 17), (SPECIAL_B_SIGNATURE, 1)))
    special_a_costs = residual_pair_cost_rows(((GOOD_SIGNATURE, 17), (SPECIAL_A_SIGNATURE, 1)))
    if special_a_costs != special_costs:
        raise ValueError("A-only and B-only residual pair costs are not symmetric")

    zero_cost = _uniform_pair_cost(good_costs, 0, "good q=0")
    good_one_cost = _uniform_pair_cost(good_costs, 1, "good q=1")
    if _uniform_pair_cost(special_costs, 0, "special q=0") != zero_cost:
        raise ValueError("special and good q=0 costs differ")

    special_ticket_one_costs = {
        costs[1]
        for (left, right), costs in zip(
            combinations(range(18), 2), special_costs, strict=True
        )
        if left == 17 or right == 17
    }
    ordinary_ticket_one_costs = {
        costs[1]
        for (left, right), costs in zip(
            combinations(range(18), 2), special_costs, strict=True
        )
        if left != 17 and right != 17
    }
    if ordinary_ticket_one_costs != {good_one_cost} or len(special_ticket_one_costs) != 1:
        raise ValueError("special pair-cost profile does not reduce to one degree correction")
    special_one_cost = next(iter(special_ticket_one_costs))
    degree_rebate = good_one_cost - special_one_cost
    if degree_rebate <= 0:
        raise ValueError("special-ticket degree correction must be positive")

    baseline = 153 * zero_cost + (good_one_cost - zero_cost) * state.outside_pair_mass
    required_rebate = baseline - state.minimum_s2
    if required_rebate < 0 or required_rebate % degree_rebate:
        return None
    return required_rebate // degree_rebate


def _dense_good_three_component_witness(state: DangerousFrontierState) -> str | None:
    """Construct a checked witness from the affine plane of order five."""

    if (
        state.support_type != SUPPORT_TYPE_GOOD
        or state.component_count != 3
        or state.outside_pair_mass not in (117, 118, 119)
    ):
        return None

    missing_extra = {117: (2, 1), 118: (1, 1), 119: (2, 1)}[state.outside_pair_mass]
    points = tuple(
        (x, y)
        for x in range(1, 5)
        for y in range(5)
        if (x, y) not in {(2, 0), (3, 0), (4, 0), missing_extra}
    )
    if len(points) != 16 or (1, 0) not in points:
        raise AssertionError("the affine-plane ticket set changed")

    def line_labels(point: tuple[int, int]) -> set[int]:
        x, y = point
        nonvertical = {slope * 5 + ((y - slope * x) % 5) for slope in range(5)}
        return {*nonvertical, 25 + x}

    target_line = 9 if state.outside_pair_mass == 119 else 26

    def lies_on_target(point: tuple[int, int]) -> bool:
        x, y = point
        if target_line < 25:
            slope, intercept = divmod(target_line, 5)
            return y == (slope * x + intercept) % 5
        return x == target_line - 25

    target_members = tuple(point for point in points if lies_on_target(point))
    ticket_to_rewire = next((point for point in target_members if point != (1, 0)), None)
    if ticket_to_rewire is None or (1, 0) not in target_members:
        raise AssertionError("the affine-plane edge-rewire line changed")

    rows_by_point = {point: line_labels(point) for point in points}
    ticket_support = rows_by_point[ticket_to_rewire]
    if target_line not in ticket_support or 0 in ticket_support:
        raise AssertionError("the affine-plane support rewire is not a valid line exchange")
    ticket_support.remove(target_line)
    ticket_support.add(0)
    if len(ticket_support) != 6:
        raise AssertionError("the affine-plane line exchange changed a ticket capacity")

    active_used_labels = {
        label for ticket_labels in rows_by_point.values() for label in ticket_labels
    }
    isolate_labels = sorted(set(range(41)) - active_used_labels)
    if len(isolate_labels) < 12:
        raise AssertionError("the affine-plane witness leaves too few labels for two isolates")
    matrix_rows = [tuple(sorted(rows_by_point[point])) for point in points]
    matrix_rows.extend((tuple(isolate_labels[:6]), tuple(isolate_labels[6:12])))
    matrix: SupportMatrix = tuple(matrix_rows)
    return r11_module._verify_support_witness(  # pyright: ignore[reportPrivateUsage]
        matrix,
        state.support_type,
        state,
    )


class ThreeComponentSupportFeasibilityModel:
    """Exact 18-by-41 incidence feasibility model with three graph components."""

    def __init__(self, states: tuple[DangerousFrontierState, ...], support_type: str) -> None:
        if not states or any(row.component_count != 3 for row in states):
            raise ValueError("the three-component model requires only component-count-three states")
        if any(row.support_type != support_type for row in states):
            raise ValueError("the three-component model cannot mix support types")
        self.support_type = support_type
        cp_model_api = cast(Any, cp_model)
        self.model: Any = cp_model_api.CpModel()
        self.special = self.model.NewBoolVar("one_anchor_exclusive_ticket")
        self.x = [
            [self.model.NewBoolVar(f"ticket_{ticket}_label_{label}") for label in range(41)]
            for ticket in range(18)
        ]
        for ticket in range(17):
            self.model.Add(sum(self.x[ticket]) == 6)
        self.model.Add(sum(self.x[17]) + self.special == 6)

        column_codes = [
            sum((1 << ticket) * self.x[ticket][label] for ticket in range(18))
            for label in range(41)
        ]
        for left, right in pairwise(column_codes):
            self.model.Add(left >= right)

        pair_overlaps: dict[tuple[int, int], Any] = {}
        good_costs = residual_pair_cost_rows(((GOOD_SIGNATURE, 18),))
        special_costs = residual_pair_cost_rows(((GOOD_SIGNATURE, 17), (SPECIAL_B_SIGNATURE, 1)))
        special_a_costs = residual_pair_cost_rows(((GOOD_SIGNATURE, 17), (SPECIAL_A_SIGNATURE, 1)))
        if special_a_costs != special_costs:
            raise ValueError("A-only and B-only residual pair costs are not symmetric")
        good_zero_cost = _uniform_pair_cost(good_costs, 0, "good q=0")
        good_one_cost = _uniform_pair_cost(good_costs, 1, "good q=1")
        special_zero_cost = _uniform_pair_cost(special_costs, 0, "special q=0")
        special_one_costs = {
            costs[1]
            for (left, right), costs in zip(
                combinations(range(18), 2), special_costs, strict=True
            )
            if left == 17 or right == 17
        }
        ordinary_special_one_costs = {
            costs[1]
            for (left, right), costs in zip(
                combinations(range(18), 2), special_costs, strict=True
            )
            if left != 17 and right != 17
        }
        if (
            good_zero_cost != special_zero_cost
            or ordinary_special_one_costs != {good_one_cost}
            or len(special_one_costs) != 1
        ):
            raise ValueError("residual pair costs do not admit the exact degree formula")
        special_one_cost = next(iter(special_one_costs))
        degree_rebate = good_one_cost - special_one_cost
        if degree_rebate <= 0:
            raise ValueError("special-ticket degree correction must be positive")
        for left, right in combinations(range(18), 2):
            common_by_label: list[Any] = []
            for label in range(41):
                common = self.model.NewBoolVar(f"pair_{left}_{right}_label_{label}")
                self.model.Add(common <= self.x[left][label])
                self.model.Add(common <= self.x[right][label])
                self.model.Add(common >= self.x[left][label] + self.x[right][label] - 1)
                common_by_label.append(common)
            overlap = self.model.NewBoolVar(f"pair_overlap_{left}_{right}")
            self.model.Add(overlap == sum(common_by_label))
            self.model.Add(overlap <= 1)
            pair_overlaps[(left, right)] = overlap

        self.mass = self.model.NewIntVar(0, 153, "outside_pair_mass")
        self.model.Add(self.mass == sum(pair_overlaps.values()))
        self.s2 = self.model.NewIntVar(0, 1_500_000_000, "residual_s2")
        degree = sum(pair_overlaps[(ticket, 17)] for ticket in range(17))
        good_s2 = 153 * good_zero_cost + (good_one_cost - good_zero_cost) * self.mass
        self.model.Add(self.s2 == good_s2).OnlyEnforceIf(self.special.Not())
        self.model.Add(
            self.s2 == good_s2 - degree_rebate * degree
        ).OnlyEnforceIf(self.special)
        self.s1 = self.model.NewIntVar(0, 400_000_000, "residual_s1")
        points = sorted(
            {
                (
                    0 if row.support_type == SUPPORT_TYPE_GOOD else 1,
                    row.outside_pair_mass,
                    row.minimum_s2,
                    331_588_656 if row.support_type == SUPPORT_TYPE_GOOD else 331_152_556,
                )
                for row in states
            }
        )
        self.model.AddAllowedAssignments([self.special, self.mass, self.s2, self.s1], points)
        self.pair_overlaps = pair_overlaps
        _add_dense_three_component_constraints(
            self.model,
            pair_overlaps,
            vertex_count=18,
            minimum_pair_mass=min(row.outside_pair_mass for row in states),
        )

        self.mass_literals: dict[int, Any] = {}
        for mass in sorted({row.outside_pair_mass for row in states}):
            literal = self.model.NewBoolVar(f"assume_mass_{mass}")
            self.model.Add(self.mass == mass).OnlyEnforceIf(literal)
            self.mass_literals[mass] = literal

        self.solver: Any = cp_model_api.CpSolver()
        self.solver.parameters.max_time_in_seconds = NATIVE_SUPPORT_WALL_LIMIT_SECONDS
        self.solver.parameters.num_search_workers = 2
        self.solver.parameters.random_seed = 0

    def classify(self, state: DangerousFrontierState) -> SupportResult:
        if state.component_count != 3 or state.support_type != self.support_type:
            raise ValueError("state does not belong to this three-component model")
        self.model.ClearAssumptions()
        type_literal = (
            self.special if state.support_type == SUPPORT_TYPE_SPECIAL else self.special.Not()
        )
        self.model.AddAssumptions([type_literal, self.mass_literals[state.outside_pair_mass]])
        status = self.solver.Solve(self.model)
        self.model.ClearAssumptions()
        if status == cp_model.INFEASIBLE:
            return False, None
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise TimeoutError(
                "CP-SAT did not classify a three-component state within the native time limit"
            )
        matrix: SupportMatrix = tuple(
            tuple(label for label in range(41) if self.solver.Value(self.x[ticket][label]))
            for ticket in range(18)
        )
        digest = r11_module._verify_support_witness(  # pyright: ignore[reportPrivateUsage]
            matrix,
            state.support_type,
            state,
        )
        return True, digest


def _classify_legacy_support_states(
    states: tuple[DangerousFrontierState, ...],
) -> tuple[SupportClassification, ...]:
    """Reuse R11's exact one/two-component model with a R13 native cap."""

    if not states:
        return ()
    models: dict[str, Any] = {}
    for support_type in (SUPPORT_TYPE_GOOD, SUPPORT_TYPE_SPECIAL):
        relevant = tuple(row for row in states if row.support_type == support_type)
        if relevant:
            model = r11_module.SupportFeasibilityModel(relevant, support_type)
            model.solver.parameters.max_time_in_seconds = R13_LEGACY_SUPPORT_WALL_LIMIT_SECONDS
            models[support_type] = model

    classifications: list[SupportClassification] = []
    case_cache: dict[tuple[str, int, int], SupportResult] = {}
    for state in states:
        key = (state.support_type, state.outside_pair_mass, state.component_count)
        result = case_cache.get(key)
        if result is None:
            result = models[state.support_type].classify(state)
            case_cache[key] = result
        realizable, witness_digest = result
        classifications.append(
            SupportClassification(
                state=state,
                realizable=realizable,
                classification_basis=(
                    "verified exact 18-by-41 incidence witness"
                    if realizable
                    else "CP-SAT INFEASIBLE for exact incidence/capacity/(M,S2)/components"
                ),
                witness_sha256=witness_digest,
            )
        )
    return tuple(classifications)


def classify_threshold_frontier_states(
    states: tuple[DangerousFrontierState, ...],
) -> tuple[SupportClassification, ...]:
    """Classify every selected exact state, including the three-component cases."""

    if not states:
        raise ValueError("the threshold interval must contain at least one state")
    classifications: dict[str, SupportClassification] = {}
    legacy_candidates: list[DangerousFrontierState] = []
    three_component_states: list[DangerousFrontierState] = []

    for state in states:
        edge_limit = maximum_edges_with_components(18, state.component_count)
        if state.outside_pair_mass > edge_limit:
            classifications[state.state_id] = SupportClassification(
                state=state,
                realizable=False,
                classification_basis=(
                    f"simple overlap graph has at most {edge_limit} edges with "
                    f"{state.component_count} components"
                ),
                witness_sha256=None,
            )
        elif state.component_count <= 2:
            legacy_candidates.append(state)
        elif state.component_count == 3:
            if state.support_type == SUPPORT_TYPE_SPECIAL:
                required_degree = _special_ticket_degree_required(state)
                maximum_special_degree = 18 - 3
                if required_degree is None:
                    classifications[state.state_id] = SupportClassification(
                        state=state,
                        realizable=False,
                        classification_basis=(
                            "minimum-S2 class dominance requires a nonintegral "
                            "special-ticket degree"
                        ),
                        witness_sha256=None,
                    )
                    continue
                if required_degree < 0 or required_degree > maximum_special_degree:
                    classifications[state.state_id] = SupportClassification(
                        state=state,
                        realizable=False,
                        classification_basis=(
                            "minimum-S2 class dominance requires special-ticket degree "
                            f"{required_degree}, above the dense three-component maximum "
                            f"of {maximum_special_degree}"
                        ),
                        witness_sha256=None,
                    )
                    continue
            affine_witness = _dense_good_three_component_witness(state)
            if affine_witness is not None:
                classifications[state.state_id] = SupportClassification(
                    state=state,
                    realizable=True,
                    classification_basis=(
                        "verified exact affine-plane order-five incidence witness "
                        "with three overlap components"
                    ),
                    witness_sha256=affine_witness,
                )
                continue
            three_component_states.append(state)
        else:
            raise AssertionError("a component-four-or-higher state escaped the graph bound")

    if legacy_candidates:
        for row in _classify_legacy_support_states(tuple(legacy_candidates)):
            classifications[row.state.state_id] = row

    models: dict[str, ThreeComponentSupportFeasibilityModel] = {}
    for support_type in (SUPPORT_TYPE_GOOD, SUPPORT_TYPE_SPECIAL):
        relevant = tuple(row for row in three_component_states if row.support_type == support_type)
        if relevant:
            models[support_type] = ThreeComponentSupportFeasibilityModel(relevant, support_type)

    case_cache: dict[tuple[str, int], SupportResult] = {}
    for state in three_component_states:
        key = (state.support_type, state.outside_pair_mass)
        result = case_cache.get(key)
        if result is None:
            result = models[state.support_type].classify(state)
            case_cache[key] = result
        realizable, witness_digest = result
        classifications[state.state_id] = SupportClassification(
            state=state,
            realizable=realizable,
            classification_basis=(
                "verified exact 18-by-41 incidence witness with three overlap components"
                if realizable
                else "CP-SAT INFEASIBLE for exact incidence/capacity/(M,S2)/three components"
            ),
            witness_sha256=witness_digest,
        )

    if len(classifications) != len(states):
        missing = sorted({row.state_id for row in states} - classifications.keys())
        raise AssertionError(f"the threshold classifier omitted states: {missing[:3]}")
    return tuple(classifications[row.state_id] for row in states)


def _classification_digest(classifications: tuple[SupportClassification, ...]) -> str:
    rows = [
        {
            "STATE_ID": row.state.state_id,
            "REALIZABLE": row.realizable,
            "BASIS": row.classification_basis,
            "WITNESS_SHA256": row.witness_sha256,
        }
        for row in classifications
    ]
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _states_by_component(
    classifications: tuple[SupportClassification, ...],
) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for realization in EXPECTED_REALIZATIONS:
        for component_count in range(1, 7):
            rows = [
                row
                for row in classifications
                if row.state.realization == realization
                and row.state.component_count == component_count
            ]
            if rows:
                groups.append(
                    {
                        "REALIZATION": realization,
                        "COMPONENT_COUNT": component_count,
                        "OUTSIDE_PAIR_MASSES": sorted(row.state.outside_pair_mass for row in rows),
                        "REALIZABLE_MASSES": sorted(
                            row.state.outside_pair_mass for row in rows if row.realizable
                        ),
                    }
                )
    return groups


def analyze_threshold_descent(repository_root: Path) -> dict[str, object]:
    """Classify the newly load-bearing interval and recompute the global R4 cap."""

    started = monotonic()
    selection = select_threshold_frontier_states(repository_root)
    classifications = classify_threshold_frontier_states(selection.states)
    r11_result = _verify_source_authorities(repository_root)[1]
    realizable = tuple(row for row in classifications if row.realizable)
    unrealizable = tuple(row for row in classifications if not row.realizable)
    if len(realizable) + len(unrealizable) != EXPECTED_NEW_STATE_COUNT:
        raise AssertionError("new load-bearing state classification is incomplete")

    r11_s3 = _json_object(r11_result.get("S3_MAX"), "R11 S3 maximum")
    r11_s4 = _json_object(r11_result.get("S4_MIN_AT_S3_MAX"), "R11 S4 minimum")
    if (
        r11_s3.get("EXACT_MAXIMUM") != EXPECTED_GLOBAL_S3_MAX
        or r11_s3.get("OTHER_REALIZABLE_STATE_CERTIFIED_S3_UPPER_MAXIMUM")
        != EXPECTED_R11_OTHER_STATE_S3_MAX
        or r11_s4.get("EXACT_MINIMUM") != EXPECTED_GLOBAL_S4_MIN
    ):
        raise ValueError("R11's exact S3/S4 authority changed")

    state_bounds: list[tuple[SupportClassification, int, int]] = []
    for row in realizable:
        incidences = 108 if row.state.support_type == SUPPORT_TYPE_GOOD else 107
        s3_upper = certified_s3_upper_bound(row.state.outside_pair_mass, incidences)
        bound = (
            ANCHOR_UNION
            + (331_588_656 if row.state.support_type == SUPPORT_TYPE_GOOD else 331_152_556)
            - row.state.minimum_s2
            + s3_upper
        )
        state_bounds.append((row, s3_upper, bound))
    if not state_bounds:
        raise AssertionError("no new load-bearing state survived exact classification")

    graph_possible_states = tuple(
        row.state
        for row in classifications
        if row.state.outside_pair_mass
        <= maximum_edges_with_components(18, row.state.component_count)
    )
    new_interval_s3_max = max(
        certified_s3_upper_bound(
            row.outside_pair_mass,
            108 if row.support_type == SUPPORT_TYPE_GOOD else 107,
        )
        for row in graph_possible_states
    )
    if new_interval_s3_max != EXPECTED_S3_MAX_IN_NEW_INTERVAL:
        raise AssertionError("the new interval's certified S3 upper maximum changed")
    if new_interval_s3_max >= EXPECTED_R11_OTHER_STATE_S3_MAX:
        raise AssertionError(
            "new states challenge R11's S3 ordering; an expanded exact S4 census is required"
        )
    new_interval_r4_bound = max(row[2] for row in state_bounds)

    lower_safe_bound = max(NEW_R3_BOUND, CURRENT_R5_BOUND, CURRENT_R6_BOUND)
    if lower_safe_bound != NEW_R3_BOUND:
        raise AssertionError("the R3 target is not the maximum lower-safe bound")
    prior_classified_bound = cast(int, r11_result["DANGEROUS_REALIZABLE_R4_BOUND"])
    if prior_classified_bound != PRIOR_R11_REALIZABLE_BOUND:
        raise ValueError("R11's previously classified realizable bound changed")
    r4_bound = max(lower_safe_bound, prior_classified_bound, new_interval_r4_bound)
    r4_status = "CLOSED_AT_OR_BELOW_R3" if r4_bound <= NEW_R3_BOUND else "OPEN_ABOVE_R3"

    success_a = r4_bound <= NEW_R3_BOUND
    success_b = r4_bound < OLD_R4_THRESHOLD
    success_c = len(classifications) == len(selection.states)
    task_status = (
        "SUCCESS_A_B_C"
        if success_a and success_b and success_c
        else "SUCCESS_B_C"
        if success_b and success_c
        else "INCOMPLETE_OR_OPEN"
    )
    if not success_b or not success_c:
        raise AssertionError("the R4 threshold descent acceptance criteria did not close")

    maximizing_state_ids = sorted(
        row.state.state_id for row, _, bound in state_bounds if bound == new_interval_r4_bound
    )
    result: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": task_status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_HEAD": "RECORDED_IN_FINAL_HANDOFF",
        "WORKTREE_PATH": WORKTREE_PATH,
        "WORKTREE_DISPOSITION": "RETAIN",
        "OLD_THRESHOLD": OLD_R4_THRESHOLD,
        "NEW_THRESHOLD": NEW_R3_BOUND,
        "CURRENT_BOUNDS": {
            "R3": NEW_R3_BOUND,
            "R5": CURRENT_R5_BOUND,
            "R6": CURRENT_R6_BOUND,
        },
        "NEW_LOAD_BEARING_STATE_COUNT": len(selection.states),
        "NEW_CLASS_MASS_COUNT": selection.class_mass_count,
        "UNREALIZABLE_STATE_COUNT": len(unrealizable),
        "REALIZABLE_STATE_COUNT": len(realizable),
        "NEW_LOAD_BEARING_STATES": _states_by_component(classifications),
        "NEW_LOAD_BEARING_STATE_SHA256": selection.state_sha256,
        "CLASSIFICATION_SHA256": _classification_digest(classifications),
        "GENERATED_JOINT_STATE_COUNT_FOR_ID_RECONSTRUCTION": (
            selection.generated_joint_state_count
        ),
        "SOURCE_R10_FRONTIER_SEGMENT_COUNT": selection.source_frontier_segment_count,
        "SOURCE_R10_RESULT_SHA256": selection.source_r10_sha256,
        "SOURCE_R9_RESULT_SHA256": selection.source_r9_sha256,
        "SOURCE_R11_RESULT_SHA256": selection.source_r11_sha256,
        "ABOVE_OLD_THRESHOLD_STATES_REUSED_WITHOUT_REOPTIMIZATION": (
            selection.above_old_threshold_state_count
        ),
        "AT_OR_BELOW_NEW_THRESHOLD_STATES_LEFT_UNOPTIMIZED": (
            selection.at_or_below_new_threshold_state_count
        ),
        "NEW_INTERVAL_CERTIFIED_S3_UPPER_MAXIMUM": new_interval_s3_max,
        "NEW_INTERVAL_R4_BOUND_MAXIMUM": new_interval_r4_bound,
        "NEW_INTERVAL_R4_BOUND_MAXIMIZING_STATE_IDS": maximizing_state_ids,
        "PRIOR_CLASSIFIED_R11_R4_BOUND": prior_classified_bound,
        "LOWER_SAFE_STATE_BOUND": lower_safe_bound,
        "S3_MAX": {
            "EXACT_MAXIMUM": EXPECTED_GLOBAL_S3_MAX,
            "MAXIMIZING_STATE_IDS": r11_s3.get("BOUND_MAXIMIZING_STATE_IDS"),
            "STATUS": r11_s3.get("STATUS"),
            "OTHER_PREVIOUS_STATE_CERTIFIED_UPPER_MAXIMUM": (EXPECTED_R11_OTHER_STATE_S3_MAX),
            "NEW_INTERVAL_CERTIFIED_UPPER_MAXIMUM": new_interval_s3_max,
            "GLOBAL_MAXIMUM_REMAINS_R11_STATE": True,
        },
        "S4_MIN_AT_GLOBAL_S3_MAX": {
            "EXACT_MINIMUM": EXPECTED_GLOBAL_S4_MIN,
            "STATUS": r11_s4.get("STATUS"),
            "SOURCE_R11_RESULT_SHA256": EXPECTED_R11_RESULT_SHA256,
            "USED_AS_CORRECTION_IN_NEW_INTERVAL": False,
        },
        "R4_BOUND": r4_bound,
        "R4_STATUS": r4_status,
        "SUCCESS_A_R4_AT_OR_BELOW_R3": success_a,
        "SUCCESS_B_STRICTLY_BELOW_OLD_R4": success_b,
        "SUCCESS_C_ALL_NEW_INTERVAL_STATES_CLASSIFIED": success_c,
        "INCUMBENT": INCUMBENT,
        "LEAF_GAP": r4_bound - INCUMBENT,
        "SOLVER_STATUS": (
            "EXACT_SUPPORT_FEASIBILITY; OPTIMAL/FEASIBLE IS ACCEPTED ONLY WITH A "
            "VERIFIED WITNESS; INFEASIBLE IS A CP-SAT PROOF; UNKNOWN FAILS CLOSED"
        ),
        "SOLVER_CONFIGURED_LIMITS": {
            "NATIVE_PER_SUPPORT_CASE_SECONDS": R13_LEGACY_SUPPORT_WALL_LIMIT_SECONDS,
            "NATIVE_ONE_TWO_COMPONENT_SUPPORT_CASE_SECONDS": (
                R13_LEGACY_SUPPORT_WALL_LIMIT_SECONDS
            ),
            "NATIVE_THREE_COMPONENT_SUPPORT_CASE_SECONDS": NATIVE_SUPPORT_WALL_LIMIT_SECONDS,
            "EXTERNAL_HARD_TIMEOUT_SECONDS": EXTERNAL_HARD_TIMEOUT_SECONDS,
            "CP_SAT_SEARCH_WORKERS": 2,
            "CP_SAT_RANDOM_SEED": 0,
        },
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": round(monotonic() - started, 6),
        "FOCUSED_TESTS": "REPORTED_IN_FINAL_HANDOFF",
        "RUFF": "REPORTED_IN_FINAL_HANDOFF",
        "PYRIGHT": "REPORTED_IN_FINAL_HANDOFF",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }
    return result


def main() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root / "docs/research/matrix-native-results/"
        "b649-k20-r4-threshold-descent-below-r3-r13-result.json",
    )
    arguments = parser.parse_args()
    result = analyze_threshold_descent(repository_root)
    output_path = arguments.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"NEW_LOAD_BEARING={result['NEW_LOAD_BEARING_STATE_COUNT']} "
        f"UNREALIZABLE={result['UNREALIZABLE_STATE_COUNT']} "
        f"REALIZABLE={result['REALIZABLE_STATE_COUNT']} "
        f"NEW_R4_MAX={result['NEW_INTERVAL_R4_BOUND_MAXIMUM']} "
        f"R4_BOUND={result['R4_BOUND']} "
        f"STATUS={result['TASK_STATUS']}"
    )


if __name__ == "__main__":
    main()
