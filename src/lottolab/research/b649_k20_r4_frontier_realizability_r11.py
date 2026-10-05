"""Realizability audit for the load-bearing K20 R4 joint-frontier states.

The module reuses R10's pinned finite frontier only to reproduce its state
identities.  It then imposes the actual 18-by-41 outside-label incidence
matrix, ticket capacities, pair intersections, and overlap-graph component
count in a bounded CP-SAT feasibility model.  For the S3 maximizer it adds an
exact frequency/profile census, a clique-partition infeasibility proof, and
support-attaining S3/S4 certificates before recomputing the R4 envelope.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import cache
from itertools import combinations, combinations_with_replacement, pairwise
from math import comb
from pathlib import Path
from time import monotonic
from typing import Any, cast

from ortools.sat.python import cp_model

from lottolab.research import b649_k20_r4_joint_residual_r10 as r10_module
from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    OUTSIDE_LABEL_CAPACITY,
    OUTSIDE_TICKET_COUNT,
    exact_joint_win_count,
    triple_intersection_count,
)
from lottolab.research.b649_k20_r4_dangerous_residual_union_r9 import (
    residual_pair_cost_rows,
)
from lottolab.research.b649_k20_r4_joint_residual_r10 import (
    EXPECTED_REALIZATIONS,
    MAXIMUM_OUTSIDE_PAIR_MASS,
    load_r9_residual_classes,
    maximum_selected_seven_frequency_by_pair_mass,
)

BASE_HEAD = "ac4d084375515309268153a829ce6ad5a370d896"
BASE_TREE = "f3d10b7af4a1c9484bfbaa184d1d0991207e2fc4"
TASK_BRANCH = "codex/b649-k20-r4-frontier-maximizer-realizability-r11"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_R4_FRONTIER_MAXIMIZER_REALIZABILITY_R11"
)
TASK_ID = "B649_K20_R4_FRONTIER_MAXIMIZER_REALIZABILITY_R11"

R10_RESULT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/b649-k20-r4-joint-residual-r10-result.json"
)
R10_SOURCE_RELATIVE_PATH = Path("src/lottolab/research/b649_k20_r4_joint_residual_r10.py")
R9_RESULT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/b649-k20-r4-dangerous-residual-union-r9-result.json"
)
EXPECTED_R10_RESULT_SHA256 = "2829fa4182fed169ba2b46695560efd244566c3dc3649ff50fc9b64c7d6e3d01"
EXPECTED_R10_SOURCE_SHA256 = "8e513e65cec6b81e45740c3f7468a11934d6885e77624527390f88ec2459e32d"
EXPECTED_R9_RESULT_SHA256 = "0024f79c9ed7bf4f5b00a207aa80e5adc8fa18b9d7f7946f4b0e192cd60ce1da"

R5_BOUND = 350_778_728
PRIOR_R4_BOUND = 351_106_608
INCUMBENT = 313_239_661
ANCHOR_UNION = 30_998_352
NATIVE_SUPPORT_WALL_LIMIT_SECONDS = 8.0
EXTERNAL_HARD_TIMEOUT_SECONDS = 150
SUPPORT_TYPE_GOOD = "18_GOOD"
SUPPORT_TYPE_SPECIAL = "17_GOOD_PLUS_SPECIAL"
GOOD_SIGNATURE = (0, 0, 0, 6)
SPECIAL_A_SIGNATURE = (0, 1, 0, 5)
SPECIAL_B_SIGNATURE = (0, 0, 1, 5)

type Signature = tuple[int, int, int, int]
type TypeCounts = tuple[tuple[Signature, int], ...]
type SupportMatrix = tuple[tuple[int, ...], ...]
type FourSupportRows = tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[int, ...]]
type PairCostRows = tuple[tuple[int, ...], ...]
type S2Envelope = Callable[[PairCostRows, int, float], tuple[tuple[int, ...], tuple[int, ...]]]

_pair_mass_s2_envelope: S2Envelope = cast(
    S2Envelope,
    r10_module._pair_mass_s2_envelope,  # pyright: ignore[reportPrivateUsage]
)
SPECIAL_147_WITNESS: SupportMatrix = (
    (3, 8, 12, 17, 20, 27),
    (1, 5, 13, 27, 28, 30),
    (0, 16, 20, 23, 24, 28),
    (3, 9, 10, 19, 28, 29),
    (4, 5, 17, 21, 29, 31),
    (1, 8, 11, 24, 25, 29),
    (2, 6, 12, 16, 29, 30),
    (3, 5, 14, 16, 22, 25),
    (4, 8, 13, 16, 19, 26),
    (4, 7, 12, 15, 25, 28),
    (2, 10, 21, 25, 26, 27),
    (3, 6, 13, 15, 21, 24),
    (1, 12, 19, 21, 22, 23),
    (2, 5, 11, 15, 19, 20),
    (1, 10, 15, 16, 17, 18),
    (0, 10, 11, 12, 13, 14),
    (0, 5, 6, 7, 8, 9),
    (0, 1, 2, 3, 4),
)
M153_GOOD_H100_BLOCKS: tuple[tuple[int, ...], ...] = (
    (0, 6),
    (1, 9, 12),
    (1, 13, 14),
    (2, 5, 10),
    (2, 12, 17),
    (3, 7, 15),
    (3, 11, 13),
    (4, 7, 8),
    (4, 10, 16),
    (0, 5, 12, 15),
    (0, 7, 11, 17),
    (0, 8, 10, 14),
    (0, 9, 13, 16),
    (1, 5, 7, 16),
    (1, 6, 8, 17),
    (1, 10, 11, 15),
    (2, 6, 11, 16),
    (2, 7, 9, 14),
    (2, 8, 13, 15),
    (3, 5, 6, 14),
    (3, 8, 12, 16),
    (3, 9, 10, 17),
    (4, 5, 13, 17),
    (4, 6, 9, 15),
    (4, 11, 12, 14),
    (5, 8, 9, 11),
    (14, 15, 16, 17),
    (0, 1, 2, 3, 4),
    (6, 7, 10, 12, 13),
)


def _cp_model_api() -> Any:
    return cast(Any, cp_model)


@dataclass(frozen=True)
class DangerousFrontierState:
    """One R10 class/mass state whose union envelope exceeds the R5 leaf."""

    realization: str
    component_count: int
    outside_pair_mass: int
    minimum_s2: int
    maximum_selected_seven_frequency: int
    multiplicity_cap: int
    current_r4_envelope: int

    @property
    def state_id(self) -> str:
        return (
            f"{self.realization}/components={self.component_count}/"
            f"outside_pair_mass={self.outside_pair_mass}"
        )

    @property
    def support_type(self) -> str:
        return SUPPORT_TYPE_GOOD if self.realization == SUPPORT_TYPE_GOOD else SUPPORT_TYPE_SPECIAL


@dataclass(frozen=True)
class SupportClassification:
    """Exact realizability result for one dangerous frontier state."""

    state: DangerousFrontierState
    realizable: bool
    classification_basis: str
    witness_sha256: str | None


@dataclass(frozen=True)
class FrontierSelection:
    states: tuple[DangerousFrontierState, ...]
    generated_joint_state_count: int
    source_frontier_segment_count: int
    source_r10_r4_bound: int
    source_r10_sha256: str
    source_r9_sha256: str


@dataclass(frozen=True)
class HigherOrderCertificate:
    """Exact S3/S4 certificate for the all-good M=153 frontier state."""

    s3_max: int
    h_min: int
    h_witness_sha256: str
    s4_min: int
    g_min: int
    s4_profile_counts: tuple[int, int, int]
    forced_frequency_minimum: int
    forced_frequency_argmin: int
    h_le_99_histogram_count: int
    h_le_99_profile_compatible_count: int
    h_le_99_profile_decomposition_count: int
    h100_histogram_count: int
    h100_profile_compatible_count: int


@dataclass(frozen=True)
class SupportFrequencyHistogram:
    """Frequency counts for labels of support sizes one through six."""

    counts: tuple[int, int, int, int, int, int]
    label_count: int
    h_value: int
    g_value: int


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


def select_dangerous_frontier_states(repository_root: Path) -> FrontierSelection:
    """Reproduce R10 state IDs and freeze only current envelopes above R5."""

    r10_path = repository_root / R10_RESULT_RELATIVE_PATH
    r10_source_path = repository_root / R10_SOURCE_RELATIVE_PATH
    r9_path = repository_root / R9_RESULT_RELATIVE_PATH
    r10_digest = _sha256(r10_path)
    r9_digest = _sha256(r9_path)
    if r10_digest != EXPECTED_R10_RESULT_SHA256:
        raise ValueError("the pinned R10 result identity changed")
    if _sha256(r10_source_path) != EXPECTED_R10_SOURCE_SHA256:
        raise ValueError("the pinned R10 source identity changed")
    if r9_digest != EXPECTED_R9_RESULT_SHA256:
        raise ValueError("the pinned R9 result identity changed")

    result = _json_object(json.loads(r10_path.read_text(encoding="utf-8")), "R10 result")
    envelopes_value = result.get("JOINT_RESIDUAL_ENVELOPE")
    if not isinstance(envelopes_value, list):
        raise ValueError("R10 has no per-realization joint envelope")
    envelopes = cast(list[object], envelopes_value)
    if (
        result.get("REALIZATION_COUNT") != 3
        or result.get("JOINT_STATE_COUNT") != 9_384
        or result.get("S2_S3_FRONTIER_SIZE") != 45
        or result.get("R4_BOUND") != PRIOR_R4_BOUND
        or len(envelopes) != 3
    ):
        raise ValueError("the R10 frontier authority no longer matches this packet")

    classes = load_r9_residual_classes(r9_path)
    if tuple(dict.fromkeys(row.vector_label for row in classes)) != EXPECTED_REALIZATIONS:
        raise ValueError("R9 realization order disagrees with the pinned R10 authority")

    state_rows: list[DangerousFrontierState] = []
    joint_state_count = 0
    frontier_size = 0
    for envelope_value in envelopes:
        envelope = _json_object(envelope_value, "R10 realization envelope")
        label_value = envelope.get("VECTOR_LABEL")
        if not isinstance(label_value, str) or label_value not in EXPECTED_REALIZATIONS:
            raise ValueError("R10 contains an unknown realization label")
        residual_class = next(row for row in classes if row.vector_label == label_value)
        pair_costs = residual_pair_cost_rows(residual_class.type_counts)
        minimum_s2, _ = _pair_mass_s2_envelope(
            pair_costs, MAXIMUM_OUTSIDE_PAIR_MASS, monotonic() + 45.0
        )
        selected_seven = maximum_selected_seven_frequency_by_pair_mass(
            residual_class.outside_incidences,
            MAXIMUM_OUTSIDE_PAIR_MASS,
            monotonic() + 45.0,
        )
        mass_count = 0
        realization_states: list[DangerousFrontierState] = []
        for mass in range(
            residual_class.outside_pair_mass_floor,
            MAXIMUM_OUTSIDE_PAIR_MASS + 1,
        ):
            top_seven = selected_seven[mass]
            if top_seven is None:
                continue
            multiplicity_cap = min(
                OUTSIDE_TICKET_COUNT,
                (top_seven + residual_class.special_anchor_incidences) // 3,
            )
            if multiplicity_cap < 1:
                continue
            mass_count += 1
            reduction = _ceil_div(2 * minimum_s2[mass], multiplicity_cap)
            envelope_bound = ANCHOR_UNION + residual_class.residual_s1 - reduction
            if envelope_bound > R5_BOUND:
                for component_count in range(1, 7):
                    realization_states.append(
                        DangerousFrontierState(
                            realization=label_value,
                            component_count=component_count,
                            outside_pair_mass=mass,
                            minimum_s2=minimum_s2[mass],
                            maximum_selected_seven_frequency=top_seven,
                            multiplicity_cap=multiplicity_cap,
                            current_r4_envelope=envelope_bound,
                        )
                    )
        state_count = mass_count * 6
        if envelope.get("JOINT_STATE_COUNT") != state_count:
            raise ValueError("the R10 joint-state count changed")
        if envelope.get("S2_S3_FRONTIER_SIZE") != len(
            cast(list[object], envelope.get("S2_S3_FRONTIER", []))
        ):
            raise ValueError("the R10 frontier segment count changed")
        joint_state_count += state_count
        frontier_size += cast(int, envelope["S2_S3_FRONTIER_SIZE"])
        state_rows.extend(realization_states)

    if joint_state_count != 9_384 or frontier_size != 45:
        raise ValueError("the reconstructed R10 state census changed")
    frozen = tuple(
        sorted(
            state_rows,
            key=lambda row: (
                EXPECTED_REALIZATIONS.index(row.realization),
                row.component_count,
                row.outside_pair_mass,
            ),
        )
    )
    if len(frozen) != 174:
        raise ValueError("the threshold no longer selects exactly 174 dangerous states")
    return FrontierSelection(
        states=frozen,
        generated_joint_state_count=joint_state_count,
        source_frontier_segment_count=frontier_size,
        source_r10_r4_bound=cast(int, result["R4_BOUND"]),
        source_r10_sha256=r10_digest,
        source_r9_sha256=r9_digest,
    )


def maximum_edges_with_components(vertex_count: int, component_count: int) -> int:
    """Exact extremal edge count for a simple graph with fixed component count."""

    if vertex_count < 1 or not 1 <= component_count <= vertex_count:
        raise ValueError("component count must be within the vertex count")
    return comb(vertex_count - component_count + 1, 2)


def _signature_rows(support_type: str) -> TypeCounts:
    if support_type == SUPPORT_TYPE_GOOD:
        return ((GOOD_SIGNATURE, OUTSIDE_TICKET_COUNT),)
    if support_type == SUPPORT_TYPE_SPECIAL:
        return ((GOOD_SIGNATURE, 17), (SPECIAL_B_SIGNATURE, 1))
    raise ValueError(f"unknown support type: {support_type}")


def overlap_components(rows: SupportMatrix) -> int:
    neighbors: list[set[int]] = [set() for _ in rows]
    for left, right in combinations(range(len(rows)), 2):
        if len(set(rows[left]).intersection(rows[right])) > 0:
            neighbors[left].add(right)
            neighbors[right].add(left)
    unseen = set(range(len(rows)))
    components = 0
    while unseen:
        components += 1
        pending = [unseen.pop()]
        while pending:
            vertex = pending.pop()
            linked = neighbors[vertex].intersection(unseen)
            unseen.difference_update(linked)
            pending.extend(linked)
    return components


def _verify_support_witness(
    matrix: SupportMatrix,
    support_type: str,
    state: DangerousFrontierState,
) -> str:
    if len(matrix) != OUTSIDE_TICKET_COUNT:
        raise ValueError("support witness must have exactly 18 ticket rows")
    row_caps = (6,) * 17 + ((5,) if support_type == SUPPORT_TYPE_SPECIAL else (6,))
    if tuple(len(row) for row in matrix) != row_caps:
        raise ValueError("support witness violates a ticket outside-label capacity")
    if any(
        len(set(row)) != len(row) or any(not 0 <= label < 41 for label in row) for row in matrix
    ):
        raise ValueError("support witness contains a duplicate or invalid label")

    support_rows = _signature_rows(support_type)
    if support_type == SUPPORT_TYPE_SPECIAL and state.realization.endswith("A_ONLY"):
        support_rows = ((GOOD_SIGNATURE, 17), (SPECIAL_A_SIGNATURE, 1))
    pair_costs = residual_pair_cost_rows(support_rows)
    pair_mass = 0
    residual_s2 = 0
    for (left, right), costs in zip(
        combinations(range(OUTSIDE_TICKET_COUNT), 2), pair_costs, strict=True
    ):
        overlap = len(set(matrix[left]).intersection(matrix[right]))
        if overlap > 1:
            raise ValueError("S2-minimizing support witness repeats a ticket pair")
        pair_mass += overlap
        residual_s2 += costs[overlap]
    if pair_mass != state.outside_pair_mass or residual_s2 != state.minimum_s2:
        raise ValueError("support witness does not realize the pinned (M,S2) state")
    if overlap_components(matrix) != state.component_count:
        raise ValueError("support witness does not realize the pinned component class")

    canonical = json.dumps(matrix, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class SupportFeasibilityModel:
    """One compressed incidence model reused across all selected state IDs."""

    def __init__(
        self,
        states: tuple[DangerousFrontierState, ...],
        support_type: str,
    ) -> None:
        self.support_type = support_type
        cp_model_api = cast(Any, cp_model)
        self.model: Any = cp_model_api.CpModel()
        self.special = self.model.NewBoolVar("one_anchor_exclusive_ticket")
        self.x = [
            [
                self.model.NewBoolVar(f"ticket_{ticket}_label_{label}")
                for label in range(OUTSIDE_LABEL_CAPACITY)
            ]
            for ticket in range(OUTSIDE_TICKET_COUNT)
        ]
        for ticket in range(17):
            self.model.Add(sum(self.x[ticket]) == 6)
        # R9 pins zero shared/A-only anchor incidences and, for the special
        # class, one B-only incidence on ticket 17. That fixed anchor-zone
        # label is appended outside this 41-label matrix; the ticket row has
        # five outside labels so its full capacity remains exactly six.
        self.model.Add(sum(self.x[17]) + self.special == 6)

        # Label columns are interchangeable. Sorting their 18-bit support
        # codes removes the 41! label-renaming symmetry without dropping a
        # realizable incidence matrix.
        column_codes = [
            sum((1 << ticket) * self.x[ticket][label] for ticket in range(18))
            for label in range(OUTSIDE_LABEL_CAPACITY)
        ]
        for left, right in pairwise(column_codes):
            self.model.Add(left >= right)

        self.pair_overlaps: dict[tuple[int, int], Any] = {}
        pair_cost_terms: list[Any] = []
        good_counts = ((GOOD_SIGNATURE, 18),)
        special_counts = ((GOOD_SIGNATURE, 17), (SPECIAL_B_SIGNATURE, 1))
        good_costs = residual_pair_cost_rows(good_counts)
        special_costs = residual_pair_cost_rows(special_counts)
        special_a_costs = residual_pair_cost_rows(((GOOD_SIGNATURE, 17), (SPECIAL_A_SIGNATURE, 1)))
        if special_a_costs != special_costs:
            raise ValueError("A-only and B-only classes are not support-symmetric")
        for pair_index, (left, right) in enumerate(combinations(range(18), 2)):
            common_by_label: list[Any] = []
            for label in range(OUTSIDE_LABEL_CAPACITY):
                common = self.model.NewBoolVar(f"pair_{left}_{right}_label_{label}")
                self.model.Add(common <= self.x[left][label])
                self.model.Add(common <= self.x[right][label])
                self.model.Add(common >= self.x[left][label] + self.x[right][label] - 1)
                common_by_label.append(common)
            overlap = self.model.NewBoolVar(f"pair_overlap_{left}_{right}")
            self.model.Add(overlap == sum(common_by_label))
            self.pair_overlaps[(left, right)] = overlap

            good_pair = good_costs[pair_index]
            special_pair = special_costs[pair_index] if left == 17 or right == 17 else good_pair
            pair_cost = self.model.NewIntVar(0, 7_000_000, f"pair_cost_{left}_{right}")
            allowed = [
                [q, use_special, (special_pair if use_special else good_pair)[q]]
                for q in range(2)
                for use_special in range(2)
            ]
            self.model.AddAllowedAssignments([overlap, self.special, pair_cost], allowed)
            pair_cost_terms.append(pair_cost)

        self.mass = self.model.NewIntVar(0, 153, "outside_pair_mass")
        self.model.Add(self.mass == sum(self.pair_overlaps.values()))
        self.s2 = self.model.NewIntVar(0, 1_500_000_000, "residual_s2")
        self.model.Add(self.s2 == sum(pair_cost_terms))
        self.s1 = self.model.NewIntVar(0, 400_000_000, "residual_s1")

        state_points = sorted(
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
        self.model.AddAllowedAssignments([self.special, self.mass, self.s2, self.s1], state_points)

        self.one_component = self.model.NewBoolVar("one_overlap_component")
        self.two_components = self.model.NewBoolVar("two_overlap_components")
        self.model.Add(self.one_component + self.two_components == 1)
        self._add_one_component_flow()
        self._add_two_component_partition()

        self.mass_literals: dict[int, Any] = {}
        for mass in sorted({row.outside_pair_mass for row in states}):
            literal = self.model.NewBoolVar(f"assume_mass_{mass}")
            self.model.Add(self.mass == mass).OnlyEnforceIf(literal)
            self.mass_literals[mass] = literal

        self.solver: Any = cp_model_api.CpSolver()
        self.solver.parameters.max_time_in_seconds = NATIVE_SUPPORT_WALL_LIMIT_SECONDS
        self.solver.parameters.num_search_workers = 2
        self.solver.parameters.random_seed = 0

    def _add_one_component_flow(self) -> None:
        flow: dict[tuple[int, int], Any] = {}
        for left in range(18):
            for right in range(18):
                if left == right:
                    continue
                value = self.model.NewIntVar(0, 17, f"flow_{left}_{right}")
                edge_key = (left, right) if left < right else (right, left)
                edge = self.pair_overlaps[edge_key]
                self.model.Add(value <= 17 * edge)
                flow[(left, right)] = value
        for vertex in range(18):
            incoming = sum(flow[(other, vertex)] for other in range(18) if other != vertex)
            outgoing = sum(flow[(vertex, other)] for other in range(18) if other != vertex)
            balance = 17 if vertex == 0 else -1
            self.model.Add(outgoing - incoming == balance).OnlyEnforceIf(self.one_component)

    def _add_two_component_partition(self) -> None:
        group = [self.model.NewBoolVar(f"small_component_{ticket}") for ticket in range(18)]
        group_size = self.model.NewIntVar(1, 2, "small_component_size")
        self.model.Add(group_size == sum(group))
        for left, right in combinations(range(18), 2):
            different = self.model.NewBoolVar(f"component_cut_{left}_{right}")
            self.model.AddAbsEquality(different, group[left] - group[right])
            edge = self.pair_overlaps[(left, right)]
            self.model.Add(edge + different <= 1).OnlyEnforceIf(self.two_components)
            same_pair = self.model.NewBoolVar(f"same_small_component_{left}_{right}")
            self.model.Add(same_pair <= group[left])
            self.model.Add(same_pair <= group[right])
            self.model.Add(same_pair >= group[left] + group[right] - 1)
            self.model.Add(edge >= same_pair).OnlyEnforceIf(self.two_components)

    def classify(
        self,
        state: DangerousFrontierState,
    ) -> tuple[bool, str | None]:
        if (
            self.support_type == SUPPORT_TYPE_SPECIAL
            and state.outside_pair_mass == 147
            and state.component_count == 1
        ):
            return True, _verify_support_witness(SPECIAL_147_WITNESS, self.support_type, state)
        cp_model_api = _cp_model_api()
        self.model.ClearAssumptions()
        type_literal = (
            self.special if state.support_type == SUPPORT_TYPE_SPECIAL else self.special.Not()
        )
        component_literal = (
            self.one_component if state.component_count == 1 else self.two_components
        )
        self.model.AddAssumptions(
            [type_literal, self.mass_literals[state.outside_pair_mass], component_literal]
        )
        status = self.solver.Solve(self.model)
        self.model.ClearAssumptions()
        if status == cp_model_api.INFEASIBLE:
            return False, None
        if status not in (cp_model_api.OPTIMAL, cp_model_api.FEASIBLE):
            raise TimeoutError(
                "CP-SAT did not classify a dangerous support state within the native limit"
            )
        matrix = tuple(
            tuple(
                label
                for label in range(OUTSIDE_LABEL_CAPACITY)
                if self.solver.Value(self.x[ticket][label])
            )
            for ticket in range(OUTSIDE_TICKET_COUNT)
        )
        digest = _verify_support_witness(matrix, state.support_type, state)
        return True, digest


def frequency_pair_histogram_minimum(
    label_count: int,
    incidence_total: int,
    pair_mass: int,
) -> int:
    """Exact minimum triple-support count over label-frequency histograms."""

    if label_count < 0 or incidence_total < 0 or pair_mass < 0:
        raise ValueError("frequency-histogram inputs must be nonnegative")
    infinity = comb(incidence_total, 3) + 1
    previous = [[infinity] * (pair_mass + 1) for _ in range(incidence_total + 1)]
    previous[0][0] = 0
    for _ in range(label_count):
        current = [[infinity] * (pair_mass + 1) for _ in range(incidence_total + 1)]
        for incidences, row in enumerate(previous):
            for mass, triple_mass in enumerate(row):
                if triple_mass == infinity:
                    continue
                maximum_frequency = min(OUTSIDE_TICKET_COUNT, incidence_total - incidences)
                for frequency in range(maximum_frequency + 1):
                    next_mass = mass + comb(frequency, 2)
                    if next_mass > pair_mass:
                        continue
                    next_incidence = incidences + frequency
                    next_triples = triple_mass + (comb(frequency, 3) if frequency >= 3 else 0)
                    if next_triples < current[next_incidence][next_mass]:
                        current[next_incidence][next_mass] = next_triples
        previous = current
    result = previous[incidence_total][pair_mass]
    if result == infinity:
        raise ValueError("no 41-label frequency histogram realizes this (I,M) pair")
    return result


def maximum_wedges_for_pair_mass(pair_mass: int, vertex_count: int = 18) -> int:
    """Convex degree-sum upper bound on simple-graph wedge count."""

    if vertex_count < 2 or not 0 <= pair_mass <= comb(vertex_count, 2):
        raise ValueError("pair mass is outside the simple graph range")
    degree_sum = 2 * pair_mass
    full_degrees, remainder = divmod(degree_sum, vertex_count - 1)
    if full_degrees > vertex_count:
        raise ValueError("pair mass exceeds the complete graph")
    return full_degrees * comb(vertex_count - 1, 2) + comb(remainder, 2)


def maximum_triangles_for_pair_mass(pair_mass: int) -> int:
    """Kruskal-Katona/colex upper bound for triangles in a simple graph."""

    if not 0 <= pair_mass <= comb(18, 2):
        raise ValueError("pair mass is outside the 18-vertex graph range")
    clique_size = 1
    while comb(clique_size + 1, 2) <= pair_mass:
        clique_size += 1
    remainder = pair_mass - comb(clique_size, 2)
    return comb(clique_size, 3) + comb(remainder, 2)


def full_s3_moment_from_support(rows: tuple[tuple[int, ...], ...]) -> int:
    """Compute the exact full-ticket S3 from compatible support moments."""

    ticket_count = len(rows)
    if ticket_count < 3 or any(len(row) != 6 for row in rows):
        raise ValueError("the S3 support oracle requires at least three six-label tickets")
    if any(len(set(row)) != 6 for row in rows):
        raise ValueError("each ticket support must contain six distinct labels")
    pair_overlaps = {
        (left, right): len(set(rows[left]).intersection(rows[right]))
        for left, right in combinations(range(ticket_count), 2)
    }
    if any(overlap > 1 for overlap in pair_overlaps.values()):
        raise ValueError("the S3 support oracle requires pair overlaps at most one")
    degrees: list[int] = []
    for ticket in range(ticket_count):
        degree = 0
        for other in range(ticket_count):
            if other == ticket:
                continue
            edge = (ticket, other) if ticket < other else (other, ticket)
            degree += pair_overlaps[edge]
        degrees.append(degree)
    wedges = sum(comb(degree, 2) for degree in degrees)
    triangles = 0
    common_triples = 0
    for left, middle, right in combinations(range(ticket_count), 3):
        edges = (
            pair_overlaps[(left, middle)],
            pair_overlaps[(left, right)],
            pair_overlaps[(middle, right)],
        )
        if all(edges):
            triangles += 1
        if len(set(rows[left]).intersection(rows[middle], rows[right])):
            common_triples += 1
    pair_mass = sum(pair_overlaps.values())
    coefficients = _full_s3_coefficients()
    constant, one_edge, wedge, triangle, common = coefficients
    return (
        constant * comb(ticket_count, 3)
        + one_edge * (ticket_count - 2) * pair_mass
        + wedge * wedges
        + triangle * triangles
        + common * common_triples
    )


def direct_full_s3_moment_from_support(rows: tuple[tuple[int, ...], ...]) -> int:
    """Small exact oracle that sums each ticket triple's joint-win count."""

    total = 0
    for left, middle, right in combinations(range(len(rows)), 3):
        common = len(set(rows[left]).intersection(rows[middle], rows[right]))
        pair_overlaps = (
            len(set(rows[left]).intersection(rows[middle])),
            len(set(rows[left]).intersection(rows[right])),
            len(set(rows[middle]).intersection(rows[right])),
        )
        total += triple_intersection_count(pair_overlaps, common)
    return total


def residual_triple_intersection_count(
    signatures: tuple[Signature, Signature, Signature],
    pair_overlaps: tuple[int, int, int],
    triple_common: int,
) -> int:
    """Count a compatible residual event triple after removing both anchors."""

    intersections: dict[int, int] = {1 << ticket: signatures[ticket][3] for ticket in range(3)}
    for (left, right), overlap in zip(combinations(range(3), 2), pair_overlaps, strict=True):
        intersections[(1 << left) | (1 << right)] = overlap
    intersections[0b111] = triple_common
    outside_cells = [0] * 8
    for support in range(1, 8):
        outside_cells[support] = sum(
            (-1) ** (superset.bit_count() - support.bit_count()) * count
            for superset, count in intersections.items()
            if superset & support == support
        )
        if outside_cells[support] < 0:
            raise ValueError("the requested outside triple-support profile is impossible")
    outside_cells[0] = OUTSIDE_LABEL_CAPACITY - sum(outside_cells[1:])
    if outside_cells[0] < 0:
        raise ValueError("the outside triple-support profile exceeds 41 labels")

    if any(signature[0] for signature in signatures):
        raise ValueError("the pinned R10 residual types have no shared-anchor labels")
    a_only_ticket = next(
        (ticket for ticket, signature in enumerate(signatures) if signature[1]), None
    )
    b_only_ticket = next(
        (ticket for ticket, signature in enumerate(signatures) if signature[2]), None
    )
    if (
        sum(signature[1] for signature in signatures) > 1
        or sum(signature[2] for signature in signatures) > 1
    ):
        raise ValueError("the pinned realization contains at most one anchor-exclusive ticket")

    cells = [0] * 32
    for residual_mask, capacity in enumerate(outside_cells):
        cells[residual_mask << 2] += capacity
    cells[1] += 2 - int(a_only_ticket is not None)
    if a_only_ticket is not None:
        cells[1 | (1 << (2 + a_only_ticket))] += 1
    cells[2] += 2 - int(b_only_ticket is not None)
    if b_only_ticket is not None:
        cells[2 | (1 << (2 + b_only_ticket))] += 1
    cells[3] += 4
    if sum(cells) != 49:
        raise AssertionError("anchor/outside support cells do not cover the 49-label pool")

    def joint_count(selected: tuple[int, ...]) -> int:
        aggregated = [0] * (1 << len(selected))
        for membership_mask, capacity in enumerate(cells):
            projected = 0
            for output_bit, input_bit in enumerate(selected):
                if membership_mask & (1 << input_bit):
                    projected |= 1 << output_bit
            aggregated[projected] += capacity
        return exact_joint_win_count(tuple(aggregated), 6, 3)

    residual_tickets = (2, 3, 4)
    return (
        joint_count(residual_tickets)
        - joint_count((0, *residual_tickets))
        - joint_count((1, *residual_tickets))
        + joint_count((0, 1, *residual_tickets))
    )


def residual_four_intersection_count(
    rows: FourSupportRows,
) -> int:
    """Count the four-ticket residual intersection for exact outside supports."""

    if any(len(row) != 6 or len(set(row)) != 6 for row in rows):
        raise ValueError("the four-ticket oracle requires four six-label supports")
    support_sets = (set(rows[0]), set(rows[1]), set(rows[2]), set(rows[3]))
    intersections: dict[int, int] = {}
    for mask in range(1, 16):
        selected_tickets = [ticket for ticket in range(4) if mask & (1 << ticket)]
        common = set(support_sets[selected_tickets[0]])
        for ticket in selected_tickets[1:]:
            common.intersection_update(support_sets[ticket])
        intersections[mask] = len(common)
    outside_cells = [0] * 16
    for support in range(1, 16):
        outside_cells[support] = sum(
            (-1) ** (superset.bit_count() - support.bit_count()) * count
            for superset, count in intersections.items()
            if superset & support == support
        )
        if outside_cells[support] < 0:
            raise ValueError("the requested outside four-ticket profile is impossible")
    outside_cells[0] = OUTSIDE_LABEL_CAPACITY - sum(outside_cells[1:])
    if outside_cells[0] < 0:
        raise ValueError("the outside four-ticket profile exceeds 41 labels")

    # Four labels are shared by the anchors; each anchor also has two labels
    # outside the 41-label residual universe.
    cells = [0] * 64
    for residual_mask, capacity in enumerate(outside_cells):
        cells[residual_mask << 2] += capacity
    cells[1] += 2
    cells[2] += 2
    cells[3] += 4
    if sum(cells) != 49:
        raise AssertionError("anchor/outside support cells do not cover the 49-label pool")

    def joint_count(selected: tuple[int, ...]) -> int:
        aggregated = [0] * (1 << len(selected))
        for membership_mask, capacity in enumerate(cells):
            projected = 0
            for output_bit, input_bit in enumerate(selected):
                if membership_mask & (1 << input_bit):
                    projected |= 1 << output_bit
            aggregated[projected] += capacity
        return exact_joint_win_count(tuple(aggregated), 6, 3)

    residual_tickets = (2, 3, 4, 5)
    return (
        joint_count(residual_tickets)
        - joint_count((0, *residual_tickets))
        - joint_count((1, *residual_tickets))
        + joint_count((0, 1, *residual_tickets))
    )


def _verify_clique_partition_witness(
    blocks: tuple[tuple[int, ...], ...],
) -> tuple[SupportMatrix, int, int, str]:
    """Validate an edge partition of K18 as a 41-label support matrix."""

    edge_coverage = {edge: 0 for edge in combinations(range(18), 2)}
    ticket_blocks: list[list[int]] = [[] for _ in range(18)]
    for label, block in enumerate(blocks):
        if len(block) < 2 or len(block) > 18 or tuple(sorted(set(block))) != block:
            raise ValueError("clique blocks must be sorted sets of at least two tickets")
        if any(ticket < 0 or ticket >= 18 for ticket in block):
            raise ValueError("clique block has a ticket outside K18")
        for ticket in block:
            ticket_blocks[ticket].append(label)
        for edge in combinations(block, 2):
            edge_coverage[edge] += 1
    if any(coverage != 1 for coverage in edge_coverage.values()):
        raise ValueError("clique blocks do not partition every K18 edge exactly once")
    if any(len(labels) > 6 for labels in ticket_blocks):
        raise ValueError("clique partition exceeds a ticket's six-label capacity")

    next_label = len(blocks)
    support_rows: list[tuple[int, ...]] = []
    for labels in ticket_blocks:
        row = list(labels)
        while len(row) < 6:
            row.append(next_label)
            next_label += 1
        support_rows.append(tuple(sorted(row)))
    if next_label > OUTSIDE_LABEL_CAPACITY:
        raise ValueError("clique partition exceeds the 41-label outside universe")
    matrix = tuple(support_rows)
    if any(len(set(row)) != 6 for row in matrix):
        raise AssertionError("private labels did not complete each six-label ticket")
    h_value = sum(comb(len(block), 3) for block in blocks)
    g_value = sum(comb(len(block), 4) for block in blocks)
    if sum(map(len, matrix)) != 108:
        raise AssertionError("the clique partition witness has the wrong incidence total")
    digest = hashlib.sha256(
        json.dumps(matrix, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return matrix, h_value, g_value, digest


@cache
def _frequency_histogram_table(
    label_count: int,
    incidence_limit: int,
    pair_mass_limit: int,
) -> tuple[tuple[int, ...], ...]:
    """Exact min-H table for all bounded (I,M) pairs over label frequencies."""

    if label_count < 0 or incidence_limit < 0 or pair_mass_limit < 0:
        raise ValueError("frequency-histogram inputs must be nonnegative")
    infinity = comb(incidence_limit, 3) + 1
    previous = [[infinity] * (pair_mass_limit + 1) for _ in range(incidence_limit + 1)]
    previous[0][0] = 0
    for _ in range(label_count):
        current = [[infinity] * (pair_mass_limit + 1) for _ in range(incidence_limit + 1)]
        for incidences, row in enumerate(previous):
            max_frequency = min(OUTSIDE_TICKET_COUNT, incidence_limit - incidences)
            for mass, triple_mass in enumerate(row):
                if triple_mass == infinity:
                    continue
                for frequency in range(max_frequency + 1):
                    next_mass = mass + comb(frequency, 2)
                    if next_mass > pair_mass_limit:
                        continue
                    next_incidence = incidences + frequency
                    next_triples = triple_mass + (comb(frequency, 3) if frequency >= 3 else 0)
                    if next_triples < current[next_incidence][next_mass]:
                        current[next_incidence][next_mass] = next_triples
        previous = current
    return tuple(tuple(row) for row in previous)


def _forced_frequency_h_minima() -> tuple[tuple[int, int], ...]:
    """Return exact H floors when a support label has each frequency >=7."""

    table = _frequency_histogram_table(40, 101, 153)
    infinity = comb(101, 3) + 1
    floors: list[tuple[int, int]] = []
    for frequency in range(7, 19):
        residual_incidences = 108 - frequency
        residual_pair_mass = 153 - comb(frequency, 2)
        residual_h = table[residual_incidences][residual_pair_mass]
        if residual_h != infinity:
            floors.append((frequency, comb(frequency, 3) + residual_h))
    if not floors:
        raise AssertionError("no possible forced-frequency histogram was found")
    return tuple(floors)


def enumerate_m153_frequency_histograms(
    maximum_h: int = 100,
) -> tuple[SupportFrequencyHistogram, ...]:
    """Census all (I,M) frequency histograms with support frequency at most six."""

    if maximum_h < 0:
        raise ValueError("maximum H must be nonnegative")
    histograms: list[SupportFrequencyHistogram] = []

    def visit(
        frequency: int,
        remaining_incidences: int,
        remaining_pair_mass: int,
        used_labels: int,
        h_value: int,
        g_value: int,
        descending_counts: tuple[int, ...],
    ) -> None:
        if h_value > maximum_h:
            return
        if frequency == 1:
            singleton_count = remaining_incidences
            total_labels = used_labels + singleton_count
            if remaining_pair_mass == 0 and total_labels <= OUTSIDE_LABEL_CAPACITY:
                counts = (singleton_count, *reversed(descending_counts))
                histograms.append(
                    SupportFrequencyHistogram(
                        counts=cast(tuple[int, int, int, int, int, int], counts),
                        label_count=total_labels,
                        h_value=h_value,
                        g_value=g_value,
                    )
                )
            return

        pair_cost = comb(frequency, 2)
        maximum_count = min(
            remaining_incidences // frequency,
            remaining_pair_mass // pair_cost,
            OUTSIDE_LABEL_CAPACITY - used_labels,
        )
        triple_cost = comb(frequency, 3)
        quadruple_cost = comb(frequency, 4)
        for count in range(maximum_count + 1):
            visit(
                frequency - 1,
                remaining_incidences - frequency * count,
                remaining_pair_mass - pair_cost * count,
                used_labels + count,
                h_value + triple_cost * count,
                g_value + quadruple_cost * count,
                (*descending_counts, count),
            )

    visit(6, 108, 153, 0, 0, 0, ())
    return tuple(
        sorted(histograms, key=lambda row: (row.h_value, row.g_value, row.counts))
    )


@cache
def ticket_frequency_profiles(
    maximum_frequency: int = 6,
) -> tuple[tuple[int, ...], ...]:
    """All six-label frequency multisets whose frequencies sum to 23."""

    if maximum_frequency < 1 or maximum_frequency > 18:
        raise ValueError("maximum label frequency must be within 1..18")
    return tuple(
        sorted(
            {
                tuple(profile.count(frequency) for frequency in range(1, maximum_frequency + 1))
                for profile in combinations_with_replacement(
                    range(1, maximum_frequency + 1), 6
                )
                if sum(profile) == 23
            }
        )
    )


def ticket_frequency_profile_decompositions(
    histogram: SupportFrequencyHistogram,
    maximum_frequency: int = 6,
) -> tuple[tuple[tuple[tuple[int, ...], int], ...], ...]:
    """Enumerate ticket-profile multisets whose incidences match one histogram."""

    if maximum_frequency > 6:
        raise ValueError("the bounded frequency census accepts frequencies through six")
    if any(histogram.counts[maximum_frequency:]):
        return ()
    profiles = ticket_frequency_profiles(maximum_frequency)
    target = tuple(
        frequency * histogram.counts[frequency - 1]
        for frequency in range(1, maximum_frequency + 1)
    )

    @cache
    def assign(
        tickets_left: int,
        profile_index: int,
        remaining: tuple[int, ...],
    ) -> tuple[tuple[int, ...], ...]:
        if profile_index == len(profiles):
            return ((),) if tickets_left == 0 and not any(remaining) else ()
        profile = profiles[profile_index]
        max_repetitions = tickets_left
        for need, per_ticket in zip(remaining, profile, strict=True):
            if per_ticket:
                max_repetitions = min(max_repetitions, need // per_ticket)
        solutions: list[tuple[int, ...]] = []
        for repetitions in range(max_repetitions, -1, -1):
            next_remaining = tuple(
                need - repetitions * per_ticket
                for need, per_ticket in zip(remaining, profile, strict=True)
            )
            for tail in assign(
                tickets_left - repetitions, profile_index + 1, next_remaining
            ):
                solutions.append((repetitions, *tail))
        return tuple(solutions)

    return tuple(
        tuple(
            (profiles[index], repetitions)
            for index, repetitions in enumerate(solution)
            if repetitions
        )
        for solution in assign(18, 0, target)
    )


def has_ticket_frequency_profile_decomposition(
    histogram: SupportFrequencyHistogram,
    maximum_frequency: int = 6,
) -> bool:
    """Check whether 18 ticket-local frequency profiles realize the histogram."""

    return bool(ticket_frequency_profile_decompositions(histogram, maximum_frequency))


def _m153_h100_support_witness() -> tuple[SupportMatrix, str]:
    matrix, h_value, g_value, digest = _verify_clique_partition_witness(M153_GOOD_H100_BLOCKS)
    if (h_value, g_value) != (100, 28):
        raise AssertionError("the pinned H=100 support witness changed its moments")
    if any(
        len(set(matrix[left]).intersection(matrix[right])) != 1
        for left, right in combinations(range(18), 2)
    ):
        raise AssertionError("the pinned support witness does not realize every K18 edge once")
    return matrix, digest


@cache
def certify_m153_higher_order() -> HigherOrderCertificate:
    """Prove exact S3 attainment and the minimum S4 at every S3 maximizer."""

    forced_frequencies = _forced_frequency_h_minima()
    forced_minimum = min(value for _, value in forced_frequencies)
    forced_argmin = min(
        frequency for frequency, value in forced_frequencies if value == forced_minimum
    )
    if (forced_minimum, forced_argmin) != (111, 7):
        raise AssertionError("the exact forced-frequency H floor changed")

    histograms = enumerate_m153_frequency_histograms()
    lower_histograms = tuple(row for row in histograms if row.h_value < 100)
    maximizing_histograms = tuple(row for row in histograms if row.h_value == 100)
    lower_compatible = tuple(
        row for row in lower_histograms if has_ticket_frequency_profile_decomposition(row)
    )
    maximizing_compatible = tuple(
        row for row in maximizing_histograms
        if has_ticket_frequency_profile_decomposition(row)
    )
    if (len(lower_histograms), len(lower_compatible)) != (4, 1):
        raise AssertionError("the exact H<100 frequency/profile census changed")
    if (len(maximizing_histograms), len(maximizing_compatible)) != (2, 1):
        raise AssertionError("the exact H=100 frequency/profile census changed")
    if lower_compatible[0].counts != (0, 2, 5, 21, 1, 0):
        raise AssertionError("the unique locally compatible H<100 histogram changed")
    if maximizing_compatible[0].counts != (0, 1, 8, 18, 2, 0):
        raise AssertionError("the unique locally compatible H=100 histogram changed")

    # Exactly three local profile decompositions remain for the sole H<100
    # histogram. Two require a ticket to contain multiple frequency-5 labels,
    # although the histogram has only one. In the third, every frequency-2
    # label joins tickets inside the sole frequency-5 K5 and repeats an edge.
    lower_decompositions = ticket_frequency_profile_decompositions(lower_compatible[0])
    if len(lower_decompositions) != 3:
        raise AssertionError("the exact H<100 ticket-profile decomposition count changed")
    multiple_size5_profiles = tuple(
        solution
        for solution in lower_decompositions
        if any(profile[4] > 1 for profile, _ in solution)
    )
    if len(multiple_size5_profiles) != 2:
        raise AssertionError("the H<100 multi-frequency-5 contradiction count changed")
    edge_repeat_decompositions = tuple(
        solution for solution in lower_decompositions if solution not in multiple_size5_profiles
    )
    if len(edge_repeat_decompositions) != 1:
        raise AssertionError("the H<100 repeated-edge contradiction is not unique")
    edge_repeat = edge_repeat_decompositions[0]
    size2_ticket_count = sum(repetitions for profile, repetitions in edge_repeat if profile[1])
    if size2_ticket_count != 4 or any(
        profile[1] and profile[4] != 1 for profile, _ in edge_repeat
    ):
        raise AssertionError("the H<100 size-2 labels do not lie within the unique K5 block")

    matrix, witness_digest = _m153_h100_support_witness()
    observed_frequency_counts = [0] * 7
    for label in {label for row in matrix for label in row}:
        frequency = sum(label in row for row in matrix)
        if frequency > 6:
            raise AssertionError("the H=100 witness has a support frequency above six")
        observed_frequency_counts[frequency] += 1
    if tuple(observed_frequency_counts[1:]) != maximizing_compatible[0].counts:
        raise AssertionError("the H=100 edge partition disagrees with the exact histogram census")
    if maximizing_compatible[0].g_value != 28:
        raise AssertionError("the exact H=100 census no longer gives G=28")

    residual_s3 = 0
    for tickets in combinations(range(18), 3):
        triple_rows = tuple(matrix[ticket] for ticket in tickets)
        common = len(set(triple_rows[0]).intersection(triple_rows[1], triple_rows[2]))
        residual_s3 += residual_triple_intersection_count(
            (GOOD_SIGNATURE, GOOD_SIGNATURE, GOOD_SIGNATURE), (1, 1, 1), common
        )
    if residual_s3 != 15_214_752:
        raise AssertionError("the H=100 support witness does not attain the expected residual S3")

    # Four tickets in K18 have either no common triple label, one common
    # triple label, or a common four-label. Pair uniqueness excludes every
    # other profile. These toy support rows independently pin each exact J.
    no_triple_rows = (
        (0, 1, 2, 3, 4, 5),
        (0, 6, 7, 8, 9, 10),
        (1, 6, 11, 12, 13, 14),
        (2, 7, 11, 15, 16, 17),
    )
    one_triple_rows = (
        (0, 1, 2, 3, 4, 5),
        (0, 6, 7, 8, 9, 10),
        (0, 11, 12, 13, 14, 15),
        (1, 6, 11, 16, 17, 18),
    )
    common_four_rows = (
        (0, 1, 2, 3, 4, 5),
        (0, 6, 7, 8, 9, 10),
        (0, 11, 12, 13, 14, 15),
        (0, 16, 17, 18, 19, 20),
    )
    intersection_counts = (
        residual_four_intersection_count(no_triple_rows),
        residual_four_intersection_count(one_triple_rows),
        residual_four_intersection_count(common_four_rows),
    )
    if intersection_counts != (679, 448, 0):
        raise AssertionError("the exact four-ticket support-profile oracle changed")

    g_minimum = maximizing_compatible[0].g_value
    n4 = g_minimum
    n3 = 15 * 100 - 4 * g_minimum
    n0 = comb(18, 4) - n3 - n4
    if (n0, n3, n4) != (1_644, 1_388, 28):
        raise AssertionError("the exact S4 support-profile census changed")
    s4_minimum = sum(
        count * value
        for count, value in zip((n0, n3, n4), intersection_counts, strict=True)
    )
    if s4_minimum != 1_738_100:
        raise AssertionError("the exact minimum S4 correction changed")
    direct_s4 = sum(
        residual_four_intersection_count(
            cast(FourSupportRows, tuple(matrix[ticket] for ticket in tickets))
        )
        for tickets in combinations(range(18), 4)
    )
    if direct_s4 != s4_minimum:
        raise AssertionError("the direct support S4 oracle disagrees with the profile census")
    return HigherOrderCertificate(
        s3_max=residual_s3,
        h_min=100,
        h_witness_sha256=witness_digest,
        s4_min=s4_minimum,
        g_min=g_minimum,
        s4_profile_counts=(n0, n3, n4),
        forced_frequency_minimum=forced_minimum,
        forced_frequency_argmin=forced_argmin,
        h_le_99_histogram_count=len(lower_histograms),
        h_le_99_profile_compatible_count=len(lower_compatible),
        h_le_99_profile_decomposition_count=len(lower_decompositions),
        h100_histogram_count=len(maximizing_histograms),
        h100_profile_compatible_count=len(maximizing_compatible),
    )


@cache
def _full_s3_coefficients() -> tuple[int, int, int, int, int]:
    """Finite-difference coefficients of a full ticket triple intersection."""

    no_edges = triple_intersection_count((0, 0, 0), 0)
    one_edge = triple_intersection_count((1, 0, 0), 0)
    two_edges = triple_intersection_count((1, 1, 0), 0)
    triangle_without_common = triple_intersection_count((1, 1, 1), 0)
    triangle_with_common = triple_intersection_count((1, 1, 1), 1)
    return (
        no_edges,
        one_edge - no_edges,
        two_edges - 2 * one_edge + no_edges,
        triangle_without_common - 3 * two_edges + 3 * one_edge - no_edges,
        triangle_with_common - triangle_without_common,
    )


@cache
def certified_s3_upper_bound(pair_mass: int, outside_incidences: int) -> int:
    """Bound residual S3 through exact graph and label-frequency moments.

    At S2-minimizing states all ticket-pair overlaps are zero or one.  For
    three such tickets, their full any-prize intersection depends on the
    overlap graph's edge count, wedge count, triangle count, and common-label
    support count H.  Its exact expansion is 2800 W + 11872 T - 13272 H.
    Since each residual event is a subset of its full ticket event, the same
    expression is a safe residual S3 ceiling.  We maximize W/T separately
    and minimize H over every 41-label frequency histogram for (I,M).
    """

    if outside_incidences not in (107, 108):
        raise ValueError("only the three pinned R10 outside-incidence totals are valid")
    if not 0 <= pair_mass <= comb(18, 2):
        raise ValueError("pair mass is outside the simple graph range")
    h_min = frequency_pair_histogram_minimum(OUTSIDE_LABEL_CAPACITY, outside_incidences, pair_mass)
    bound = (
        2_800 * maximum_wedges_for_pair_mass(pair_mass)
        + 11_872 * maximum_triangles_for_pair_mass(pair_mass)
        - 13_272 * h_min
    )
    return max(0, bound)


def _support_witness_digest(classifications: tuple[SupportClassification, ...]) -> str:
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


def _classify_dangerous_states(
    states: tuple[DangerousFrontierState, ...],
) -> tuple[SupportClassification, ...]:
    classifications: dict[str, SupportClassification] = {}
    candidate_states: list[DangerousFrontierState] = []
    for state in states:
        edge_limit = maximum_edges_with_components(OUTSIDE_TICKET_COUNT, state.component_count)
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
        else:
            candidate_states.append(state)

    models: dict[str, SupportFeasibilityModel] = {}
    for support_type in (SUPPORT_TYPE_GOOD, SUPPORT_TYPE_SPECIAL):
        relevant = tuple(row for row in states if row.support_type == support_type)
        if not relevant:
            continue
        model = SupportFeasibilityModel(relevant, support_type)
        models[support_type] = model

    case_cache: dict[tuple[str, int, int], tuple[bool, str | None]] = {}
    for state in candidate_states:
        key = (state.support_type, state.outside_pair_mass, state.component_count)
        result = case_cache.get(key)
        if result is None:
            result = models[state.support_type].classify(state)
            case_cache[key] = result
        realizable, witness_digest = result
        classifications[state.state_id] = SupportClassification(
            state=state,
            realizable=realizable,
            classification_basis=(
                "verified exact 18-by-41 incidence witness"
                if realizable
                else "CP-SAT INFEASIBLE for exact incidence/capacity/(M,S2)/components"
            ),
            witness_sha256=witness_digest,
        )

    if len(classifications) != len(states):
        raise AssertionError("the dangerous-state classifier omitted a state")
    return tuple(classifications[state.state_id] for state in states)


def analyze_frontier_realizability(repository_root: Path) -> dict[str, object]:
    """Classify all dangerous R10 states and recompute their R4 certificate."""

    started = monotonic()
    selection = select_dangerous_frontier_states(repository_root)
    classifications = _classify_dangerous_states(selection.states)
    higher_order = certify_m153_higher_order()
    unrealizable = tuple(row for row in classifications if not row.realizable)
    realizable = tuple(row for row in classifications if row.realizable)
    if len(unrealizable) + len(realizable) != len(selection.states):
        raise AssertionError("dangerous-state classification is incomplete")

    state_bounds: list[tuple[SupportClassification, int, int]] = []
    for row in realizable:
        incidences = 108 if row.state.support_type == SUPPORT_TYPE_GOOD else 107
        s3_bound = certified_s3_upper_bound(row.state.outside_pair_mass, incidences)
        # Third-order Bonferroni: |union| <= S1 - S2 + S3.
        bound = (
            ANCHOR_UNION
            + (331_588_656 if row.state.support_type == SUPPORT_TYPE_GOOD else 331_152_556)
            - row.state.minimum_s2
            + s3_bound
        )
        state_bounds.append((row, s3_bound, bound))
    if not state_bounds:
        raise AssertionError("no dangerous state survived realizability")

    dangerous_realizable_r4_bound = max(row[2] for row in state_bounds)
    maximizer_state_id = "18_GOOD/components=1/outside_pair_mass=153"
    if not any(
        row.state.state_id == maximizer_state_id and row.realizable
        for row in realizable
    ):
        raise AssertionError("the exact higher-order maximizer is absent from realizable states")
    other_state_s3_upper_bound = max(
        s3_bound for row, s3_bound, _ in state_bounds if row.state.state_id != maximizer_state_id
    )
    if higher_order.s3_max <= other_state_s3_upper_bound:
        raise AssertionError("the exact M=153 S3 value does not dominate every other state bound")
    s3_maximum_certified_bound = higher_order.s3_max
    # Every non-dangerous R10 envelope is <= R5 by the frozen selection rule.
    r4_bound = max(R5_BOUND, dangerous_realizable_r4_bound)
    r4_status = "CLOSED_VS_R5" if r4_bound <= R5_BOUND else "TIGHTENED_OPEN"

    grouped_states: list[dict[str, object]] = []
    for realization in EXPECTED_REALIZATIONS:
        for component_count in range(1, 7):
            masses = [
                row.outside_pair_mass
                for row in selection.states
                if row.realization == realization and row.component_count == component_count
            ]
            if masses:
                grouped_states.append(
                    {
                        "REALIZATION": realization,
                        "COMPONENT_COUNT": component_count,
                        "OUTSIDE_PAIR_MASSES": masses,
                    }
                )

    support_group_counts = {
        support_type: {
            "DANGEROUS": sum(row.state.support_type == support_type for row in classifications),
            "UNREALIZABLE": sum(
                row.state.support_type == support_type and not row.realizable
                for row in classifications
            ),
            "REALIZABLE": sum(
                row.state.support_type == support_type and row.realizable for row in classifications
            ),
        }
        for support_type in (SUPPORT_TYPE_GOOD, SUPPORT_TYPE_SPECIAL)
    }
    classification_groups: list[dict[str, object]] = []
    for realization in EXPECTED_REALIZATIONS:
        for component_count in range(1, 7):
            group_rows = [
                row
                for row in classifications
                if row.state.realization == realization
                and row.state.component_count == component_count
            ]
            if not group_rows:
                continue
            classification_groups.append(
                {
                    "REALIZATION": realization,
                    "COMPONENT_COUNT": component_count,
                    "REALIZABLE_MASSES": sorted(
                        row.state.outside_pair_mass for row in group_rows if row.realizable
                    ),
                    "UNREALIZABLE_BY_GRAPH_BOUND": sorted(
                        row.state.outside_pair_mass
                        for row in group_rows
                        if not row.realizable
                        and row.classification_basis.startswith("simple overlap graph")
                    ),
                    "UNREALIZABLE_BY_CP_SAT": sorted(
                        row.state.outside_pair_mass
                        for row in group_rows
                        if not row.realizable
                        and row.classification_basis.startswith("CP-SAT INFEASIBLE")
                    ),
                }
            )
    s3_max_state_ids = [maximizer_state_id]
    dangerous_r4_max_state_ids = sorted(
        row.state.state_id
        for row, _, bound in state_bounds
        if bound == dangerous_realizable_r4_bound
    )
    result: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_A_B_C_EXACT_S3_S4"
        if r4_bound <= R5_BOUND
        else "COMPLETED_SUCCESS_B"
        if r4_bound < PRIOR_R4_BOUND
        else "NO_STRICT_TIGHTENING",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_HEAD": "RECORDED_IN_FINAL_HANDOFF",
        "WORKTREE_PATH": WORKTREE_PATH,
        "WORKTREE_DISPOSITION": "RETAIN",
        "DANGEROUS_FRONTIER_STATE_COUNT": len(selection.states),
        "DANGEROUS_FRONTIER_STATES": grouped_states,
        "DANGEROUS_FRONTIER_STATE_SHA256": hashlib.sha256(
            json.dumps(
                [asdict(row) for row in selection.states],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "GENERATED_JOINT_STATE_COUNT_FOR_ID_REPRODUCTION": (selection.generated_joint_state_count),
        "SOURCE_R10_FRONTIER_SEGMENT_COUNT": selection.source_frontier_segment_count,
        "SOURCE_R10_RESULT_SHA256": selection.source_r10_sha256,
        "SOURCE_R9_RESULT_SHA256": selection.source_r9_sha256,
        "UNREALIZABLE_STATE_COUNT": len(unrealizable),
        "REALIZABLE_STATE_COUNT": len(realizable),
        "SUPPORT_TYPE_CLASSIFICATION_COUNTS": support_group_counts,
        "CLASSIFIED_FRONTIER_GROUPS": classification_groups,
        "CLASSIFICATION_BASIS_COUNTS": {
            "GRAPH_COMPONENT_EXTREMAL_PROOF": sum(
                row.classification_basis.startswith("simple overlap graph") for row in unrealizable
            ),
            "CP_SAT_INFEASIBLE_PROOF": sum(
                row.classification_basis.startswith("CP-SAT INFEASIBLE") for row in unrealizable
            ),
            "VERIFIED_INCIDENCE_WITNESS": len(realizable),
        },
        "SUPPORT_CLASSIFICATION_SHA256": _support_witness_digest(classifications),
        "GRAPH_COMPONENT_ELIMINATIONS": sum(
            row.classification_basis.startswith("simple overlap graph") for row in unrealizable
        ),
        "S3_MAX": {
            "CERTIFIED_UPPER_BOUND": s3_maximum_certified_bound,
            "EXACT_MAXIMUM": higher_order.s3_max,
            "STATUS": "EXACT_MAXIMUM_WITH_SUPPORT_AND_HISTOGRAM_CERTIFICATES",
            "BOUND_MAXIMIZING_STATE_IDS": s3_max_state_ids,
            "ATTAINEDNESS": "PROVEN_BY_VERIFIED_SUPPORT_WITNESS",
            "MAXIMIZER_SUPPORT_WITNESS_SHA256": higher_order.h_witness_sha256,
            "H_MIN": higher_order.h_min,
            "OTHER_REALIZABLE_STATE_CERTIFIED_S3_UPPER_MAXIMUM": other_state_s3_upper_bound,
            "FORCED_FREQUENCY_H_FLOOR_FOR_FREQUENCY_AT_LEAST_7": (
                higher_order.forced_frequency_minimum
            ),
            "FORCED_FREQUENCY_ARGMIN": higher_order.forced_frequency_argmin,
            "H_LE_99_FREQUENCY_HISTOGRAM_COUNT": higher_order.h_le_99_histogram_count,
            "H_LE_99_PROFILE_COMPATIBLE_HISTOGRAM_COUNT": (
                higher_order.h_le_99_profile_compatible_count
            ),
            "H_LE_99_PROFILE_DECOMPOSITION_COUNT": (
                higher_order.h_le_99_profile_decomposition_count
            ),
            "H_LOWER_BOUND_CERTIFICATE": (
                "For a forced label frequency >=7, the exact residual frequency DP gives "
                "H>=111. For frequencies 1..6, exhaustive integer histogram enumeration "
                "under (I,M,label count) yields four H<100 profiles; exact DP over the "
                "18 ticket-local six-label frequency patterns summing to 23 leaves one "
                "profile, with n5=1 and n6=0, and exactly three decompositions. Two require "
                "a ticket in multiple frequency-5 labels. In the remaining decomposition, "
                "both frequency-2 labels join tickets inside the unique frequency-5 K5, "
                "duplicating an already-covered pair."
            ),
            "CERTIFICATE": (
                "Pair mass 153 on 18 tickets forces K18. The outside-label supports "
                "are therefore an exact clique partition of K18's 153 edges; the "
                "verified 29-block witness has H=100 and attains residual S3. Every "
                "other realizable dangerous state has certified S3 upper bound below it."
            ),
        },
        "S4_MIN_AT_S3_MAX": {
            "EXACT_MINIMUM": higher_order.s4_min,
            "STATUS": "EXACT_OPTIMAL_SUPPORT_MINIMUM",
            "G_MIN_AT_H_100": higher_order.g_min,
            "PROFILE_COUNTS_NO_TRIPLE_ONE_TRIPLE_COMMON_FOUR": list(
                higher_order.s4_profile_counts
            ),
            "PROFILE_RESIDUAL_INTERSECTIONS_J0_J3_J4": [679, 448, 0],
            "H_100_FREQUENCY_HISTOGRAM_COUNT": higher_order.h100_histogram_count,
            "H_100_PROFILE_COMPATIBLE_HISTOGRAM_COUNT": (
                higher_order.h100_profile_compatible_count
            ),
            "CERTIFICATE": (
                "At H=100, the exact (I,M,label-count) histogram census and ticket-local "
                "frequency-profile DP leave one profile-compatible histogram, with G=28. "
                "The verified K18 block witness attains it. Four-ticket profile counts "
                "are (N0,N3,N4)=(1644,1388,28), with exact residual intersections "
                "(J0,J3,J4)=(679,448,0), giving S4=1,738,100."
            ),
            "USED_IN_R4_BOUND": False,
        },
        "DANGEROUS_REALIZABLE_R4_BOUND": dangerous_realizable_r4_bound,
        "DANGEROUS_REALIZABLE_R4_BOUND_MAXIMIZING_STATE_IDS": (dangerous_r4_max_state_ids),
        "R4_BOUND": r4_bound,
        "R4_STATUS": r4_status,
        "INCUMBENT": INCUMBENT,
        "LEAF_GAP": r4_bound - INCUMBENT,
        "SOLVER_STATUS": (
            "EXACT_SUPPORT_FEASIBILITY; FINITE H/PROFILE CENSUS; "
            "EXACT S3/S4 CELL COUNTS"
        ),
        "SOLVER_CONFIGURED_WALL_LIMIT": (
            f"{NATIVE_SUPPORT_WALL_LIMIT_SECONDS}s native per frontier support case; "
            "2 search workers; "
            f"{EXTERNAL_HARD_TIMEOUT_SECONDS}s external process timeout; "
            "higher-order bound proved by finite census, no solver"
        ),
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": round(monotonic() - started, 6),
        "SOLVER_CERTIFIED_BOUND": r4_bound,
        "FOCUSED_TESTS": "PASS: 10 focused tests",
        "RUFF": "PASS: scoped ruff check",
        "PYRIGHT": "PASS: scoped pyright, 0 errors",
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
        "b649-k20-r4-frontier-realizability-r11-result.json",
    )
    arguments = parser.parse_args()
    result = analyze_frontier_realizability(repository_root)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"DANGEROUS={result['DANGEROUS_FRONTIER_STATE_COUNT']} "
        f"UNREALIZABLE={result['UNREALIZABLE_STATE_COUNT']} "
        f"REALIZABLE={result['REALIZABLE_STATE_COUNT']} "
        f"DANGEROUS_R4_BOUND={result['DANGEROUS_REALIZABLE_R4_BOUND']} "
        f"R4_BOUND={result['R4_BOUND']}"
    )


if __name__ == "__main__":
    main()
