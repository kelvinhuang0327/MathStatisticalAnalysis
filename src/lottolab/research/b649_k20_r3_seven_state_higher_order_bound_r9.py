"""Exact higher-order outcome certificates for the pinned seven R3 witnesses.

The native counter partitions official outcomes by their seven-number set:
each such set has seven possible special-number choices, and a ticket wins
exactly when it contains at least three labels from that set.  State-wide
upper bounds use a jointly optimized multiplicity-histogram relaxation whose
constraints hold for every support in the corresponding frozen state.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from lottolab.research import b649_k20_r3_frontier_realizability_bound_r8 as r8
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    DRAW_SIZE,
    INCUMBENT,
    OUTRIGHT_MATCHES,
    POOL_SIZE,
    TICKET_COUNT,
    pair_intersection_count,
)
from lottolab.research.b649_k20_r3_anchor_incidence_bound_r5 import (
    anchor_incidence_profiles,
)
from lottolab.research.b649_k20_r3_joint_residual_envelope_r7 import (
    JOINT_EXPRESSION_CONSTANT as LEGACY_JOINT_EXPRESSION_CONSTANT,
)

TASK_ID = "B649_K20_R3_SEVEN_STATE_HIGHER_ORDER_BOUND_R9"
MODULE_NAME = "lottolab.research.b649_k20_r3_seven_state_higher_order_bound_r9"
BASE_HEAD = "8bcdc9a06d04bc42484e3f991b7ec9c5be9feee6"
BASE_TREE = "964747abc6689c2e57e60648abbe7fb71d564669"
TASK_BRANCH = "codex/b649-k20-r3-seven-state-higher-order-bound-r9"
CURRENT_R3_BOUND = 350_545_749
CURRENT_R5_BOUND = 349_009_248
STATE_COUNT = 7
OUTCOME_SET_SIZE = DRAW_SIZE + 1
OUTCOME_MULTIPLICITY = OUTCOME_SET_SIZE
OFFICIAL_OUTCOME_COUNT = OUTCOME_MULTIPLICITY * math.comb(POOL_SIZE, OUTCOME_SET_SIZE)
LEGACY_SINGLE_TICKET_OUTCOMES = 18_221_078
SINGLE_TICKET_OUTCOMES = OUTCOME_MULTIPLICITY * sum(
    math.comb(DRAW_SIZE, hits) * math.comb(POOL_SIZE - DRAW_SIZE, OUTCOME_SET_SIZE - hits)
    for hits in range(OUTRIGHT_MATCHES, DRAW_SIZE + 1)
)
if pair_intersection_count(DRAW_SIZE) != SINGLE_TICKET_OUTCOMES:
    raise AssertionError("the exact single-ticket count disagrees with the diagonal pair count")
SINGLE_EVENT_COUNT_CORRECTION = SINGLE_TICKET_OUTCOMES - LEGACY_SINGLE_TICKET_OUTCOMES
ANCHOR_PAIR_INTERSECTION = pair_intersection_count(3)
ANCHOR_PAIR_UNION_OUTCOMES = 2 * SINGLE_TICKET_OUTCOMES - ANCHOR_PAIR_INTERSECTION
JOINT_EXPRESSION_CONSTANT = ANCHOR_PAIR_UNION_OUTCOMES + (TICKET_COUNT - 2) * SINGLE_TICKET_OUTCOMES
ANCHOR_EXCLUSIVE_OUTCOME_COUNT = OFFICIAL_OUTCOME_COUNT - ANCHOR_PAIR_UNION_OUTCOMES
LEGACY_BASELINE_CORRECTION = TICKET_COUNT * SINGLE_EVENT_COUNT_CORRECTION
R7_TAIL_BOUND = r8.R7_TAIL_BOUND + LEGACY_BASELINE_CORRECTION
R7_FRONTIER_NONLOAD_BOUND = r8.R7_FRONTIER_NONLOAD_BOUND + LEGACY_BASELINE_CORRECTION
SOLVER_WORKERS = 2
MULTIPLICITY_NATIVE_LIMIT_SECONDS = 15.0
MULTIPLICITY_EXTERNAL_TIMEOUT_SECONDS = 25.0
HISTOGRAM_NATIVE_LIMIT_SECONDS = 60.0
HISTOGRAM_EXTERNAL_TIMEOUT_SECONDS = 75.0
S4_NATIVE_LIMIT_SECONDS = 120.0
S4_EXTERNAL_TIMEOUT_SECONDS = 130.0
COMPILER_TIMEOUT_SECONDS = 30.0
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
NATIVE_SOURCE = Path(__file__).with_suffix(".cpp")
R8_RESULT_PATH = (
    REPO_ROOT / "docs/research/matrix-native-results/"
    "b649-k20-r3-frontier-realizability-bound-r8-result.json"
)
RESULT_PATH = (
    REPO_ROOT / "docs/research/matrix-native-results/"
    "b649-k20-r3-seven-state-higher-order-bound-r9-result.json"
)
ANCHOR_A_MASK = sum(1 << label for label in range(6))
ANCHOR_B_MASK = sum(1 << label for label in (*range(3), *range(6, 9)))


@dataclass(frozen=True)
class CertifiedStateInput:
    """One exact R8 state identity and its pinned support witness."""

    identifier: str
    witness_counts: tuple[int, ...]
    support_bitmasks: tuple[int, ...]
    current_upper_bound: int
    prior_s4_lower_bound: int
    prior_s4_witness: int
    prior_s4_proven: bool


def load_certified_states(
    path: Path = R8_RESULT_PATH,
) -> tuple[CertifiedStateInput, ...]:
    """Load only the seven state IDs and support witnesses pinned by R8."""

    prior = json.loads(path.read_text(encoding="utf-8"))
    rows = prior["R3_LOAD_BEARING_FRONTIER_STATES"]
    states_by_id = {state.identifier: state for state in r8.load_bearing_frontier_states()}
    if len(rows) != STATE_COUNT or len(states_by_id) != STATE_COUNT:
        raise AssertionError("the pinned R8 certificate must contain exactly seven states")

    loaded: list[CertifiedStateInput] = []
    for row in rows:
        identifier = str(row["state_id"])
        state = states_by_id.get(identifier)
        if state is None:
            raise AssertionError("R8 result contains a state outside the frozen frontier")
        bitmasks = tuple(int(mask) for mask in row["support_witness_bitmasks"])
        if bitmasks != r8.SUPPORT_WITNESS_BITMASKS[identifier]:
            raise AssertionError("R8 support witness differs from its frozen module copy")
        loaded.append(
            CertifiedStateInput(
                identifier=identifier,
                witness_counts=state.witness_counts,
                support_bitmasks=bitmasks,
                current_upper_bound=int(row["current_upper_bound"]),
                prior_s4_lower_bound=int(row["s4_minimum_certified_lower_bound"]),
                prior_s4_witness=int(row["s4_feasible_witness_at_s3_max"]),
                prior_s4_proven=bool(row["s4_minimum_proven"]),
            )
        )
    if tuple(item.identifier for item in loaded) != tuple(states_by_id):
        raise AssertionError("R8 state ordering or identity changed")
    return tuple(loaded)


def runtime_preflight() -> dict[str, str]:
    """Require the project Python/OR-Tools runtime and a native C++ compiler."""

    runtime = r8.solver_runtime_preflight()
    compiler = shutil.which("c++")
    if compiler is None:
        raise RuntimeError("the required C++ compiler is unavailable")
    completed = subprocess.run(
        [compiler, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    if completed.returncode != 0:
        raise RuntimeError("the C++ compiler version probe failed")
    runtime["compiler"] = compiler
    runtime["compiler_version"] = completed.stdout.splitlines()[0]
    return runtime


def compile_native_counter(output_dir: Path) -> Path:
    """Compile the exact counter into a disposable caller-selected directory."""

    compiler = shutil.which("c++")
    if compiler is None:
        raise RuntimeError("the required C++ compiler is unavailable")
    executable = output_dir / "b649-r3-r9-multiplicity-counter"
    completed = subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-O3",
            "-DNDEBUG",
            str(NATIVE_SOURCE),
            "-o",
            str(executable),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=COMPILER_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise RuntimeError("native counter compilation failed: " + completed.stderr[-2_000:])
    return executable


def native_counter_input(
    ticket_masks: tuple[int, ...],
    *,
    pool_size: int,
    set_size: int,
    threshold: int,
    anchor_count: int,
    outcome_multiplier: int,
    native_limit_seconds: float,
) -> str:
    """Serialize one outcome-cell histogram request for the C++ counter."""

    header = (
        f"{pool_size} {set_size} {threshold} {len(ticket_masks)} "
        f"{anchor_count} {outcome_multiplier} {native_limit_seconds}\n"
    )
    return header + "".join(f"{mask}\n" for mask in ticket_masks)


def run_native_counter(
    executable: Path,
    ticket_masks: tuple[int, ...],
    *,
    pool_size: int = POOL_SIZE,
    set_size: int = OUTCOME_SET_SIZE,
    threshold: int = 3,
    anchor_count: int = 2,
    outcome_multiplier: int = OUTCOME_MULTIPLICITY,
    native_limit_seconds: float = HISTOGRAM_NATIVE_LIMIT_SECONDS,
    external_timeout_seconds: float = HISTOGRAM_EXTERNAL_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run one bounded native multiplicity census and parse its JSON result."""

    completed = subprocess.run(
        [str(executable)],
        input=native_counter_input(
            ticket_masks,
            pool_size=pool_size,
            set_size=set_size,
            threshold=threshold,
            anchor_count=anchor_count,
            outcome_multiplier=outcome_multiplier,
            native_limit_seconds=native_limit_seconds,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=external_timeout_seconds,
    )
    if completed.returncode != 0:
        try:
            detail = json.loads(completed.stdout)
        except json.JSONDecodeError:
            detail = {"stderr": completed.stderr[-2_000:]}
        if detail.get("status") == "NATIVE_TIMEOUT":
            return {
                **detail,
                "external_status": "NATIVE_TIMEOUT",
                "external_timeout_seconds": external_timeout_seconds,
            }
        raise RuntimeError(f"native counter failed: {detail}")
    result = json.loads(completed.stdout)
    result["external_timeout_seconds"] = external_timeout_seconds
    return result


def brute_force_official_histogram(
    ticket_masks: tuple[int, ...],
    *,
    pool_size: int,
    set_size: int,
    threshold: int,
    anchor_count: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Small, deliberately direct official-outcome oracle for focused tests."""

    full = [0] * (len(ticket_masks) + 1)
    exclusive = [0] * (len(ticket_masks) - anchor_count + 1)
    for selected in combinations(range(pool_size), set_size):
        selected_mask = sum(1 << label for label in selected)
        for special in selected:
            main_mask = selected_mask ^ (1 << special)
            winners = tuple(
                (main_mask & ticket).bit_count() >= threshold
                or (
                    (main_mask & ticket).bit_count() == threshold - 1
                    and bool(ticket & (1 << special))
                )
                for ticket in ticket_masks
            )
            full[sum(winners)] += 1
            if not any(winners[:anchor_count]):
                exclusive[sum(winners[anchor_count:])] += 1
    return tuple(full), tuple(exclusive)


def multiplicity_moments(histogram: tuple[int, ...] | list[int]) -> dict[int, int]:
    """Return all binomial moments represented by one exact multiplicity histogram."""

    moments: dict[int, int] = {}
    for order in range(1, len(histogram)):
        moments[order] = sum(
            math.comb(multiplicity, order) * count
            for multiplicity, count in enumerate(histogram)
            if multiplicity >= order
        )
    return moments


def solve_multiplicity_cap(
    state_id: str,
    *,
    native_limit_seconds: float = MULTIPLICITY_NATIVE_LIMIT_SECONDS,
) -> dict[str, Any]:
    """Maximize residual winners in one anchor-excluded outcome over a state."""

    runtime = r8.solver_runtime_preflight()
    state = next(
        (item for item in r8.load_bearing_frontier_states() if item.identifier == state_id),
        None,
    )
    if state is None:
        raise ValueError("unknown load-bearing state")
    profiles = anchor_incidence_profiles()
    row_types = tuple(
        type_index for type_index, count in enumerate(state.witness_counts) for _ in range(count)
    )
    row_demands = tuple(
        tuple(
            getattr(profiles[type_index], attribute)
            for attribute in ("shared", "a_only", "b_only", "outside")
        )
        for type_index in row_types
    )
    incidence = r8.build_incidence_model(
        r8.ANCHOR_CELL_CAPACITIES,
        row_demands,
        maximum_pair_overlap=3,
    )
    cp_model: Any = importlib.import_module("ortools.sat.python.cp_model")
    selected = [incidence.model.NewBoolVar(f"outcome_label_{label}") for label in range(POOL_SIZE)]
    incidence.model.Add(sum(selected) == OUTCOME_SET_SIZE)
    incidence.model.Add(sum(selected[label] for label in range(6)) <= 2)
    incidence.model.Add(
        sum(selected[label] for label in range(3)) + sum(selected[label] for label in range(6, 9))
        <= 2
    )

    winning: list[Any] = []
    for ticket_index, ticket in enumerate(incidence.ticket_labels):
        overlaps: list[Any] = []
        for label, ticket_has_label in enumerate(ticket):
            included = incidence.model.NewBoolVar(f"outcome_ticket_label_{ticket_index}_{label}")
            incidence.model.Add(included <= ticket_has_label)
            incidence.model.Add(included <= selected[label])
            incidence.model.Add(included >= ticket_has_label + selected[label] - 1)
            overlaps.append(included)
        wins = incidence.model.NewBoolVar(f"ticket_wins_{ticket_index}")
        incidence.model.Add(sum(overlaps) >= 3 * wins)
        winning.append(wins)
    incidence.model.Maximize(sum(winning))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = native_limit_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = 0
    started = time.monotonic()
    status = solver.Solve(incidence.model)
    status_name = solver.StatusName(status)
    incumbent = (
        int(solver.Value(sum(winning))) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    )
    objective_bound = (
        float(solver.BestObjectiveBound())
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        else float(r8.OUTSIDE_TICKET_COUNT)
    )
    certified_upper = min(
        r8.OUTSIDE_TICKET_COUNT,
        max(0, math.ceil(objective_bound - 1e-9)),
    )
    exact_maximum = (
        incumbent
        if status == cp_model.OPTIMAL
        else r8.OUTSIDE_TICKET_COUNT
        if incumbent == r8.OUTSIDE_TICKET_COUNT
        else None
    )
    return {
        "state_id": state_id,
        "status": status_name,
        "incumbent": incumbent,
        "objective_bound": objective_bound,
        "certified_upper_bound": certified_upper,
        "exact_maximum": exact_maximum,
        "exactness_source": (
            "OPTIMAL"
            if status == cp_model.OPTIMAL
            else "FEASIBLE_AT_TRIVIAL_18_CAP"
            if exact_maximum is not None
            else "CONSERVATIVE_SOLVER_BOUND"
        ),
        "native_wall_limit_seconds": native_limit_seconds,
        "native_wall_time_seconds": time.monotonic() - started,
        "runtime": runtime,
        "workers": SOLVER_WORKERS,
    }


def solve_histogram_relaxation(
    outcome_count: int,
    exact_s1: int,
    s2_lower_bound: int,
    maximum_multiplicity: int,
    *,
    native_limit_seconds: float = MULTIPLICITY_NATIVE_LIMIT_SECONDS,
) -> dict[str, Any]:
    """Minimize union correction over one jointly constrained histogram."""

    if outcome_count < 0 or exact_s1 < 0 or s2_lower_bound < 0:
        raise ValueError("moment inputs must be nonnegative")
    if maximum_multiplicity < 1:
        raise ValueError("maximum multiplicity must be positive")
    runtime = r8.solver_runtime_preflight()
    cp_model: Any = importlib.import_module("ortools.sat.python.cp_model")
    model = cp_model.CpModel()
    bins = [
        model.NewIntVar(0, outcome_count, f"histogram_{multiplicity}")
        for multiplicity in range(maximum_multiplicity + 1)
    ]
    model.Add(sum(bins) == outcome_count)
    model.Add(
        sum(multiplicity * bins[multiplicity] for multiplicity in range(len(bins))) == exact_s1
    )
    model.Add(
        sum(math.comb(multiplicity, 2) * bins[multiplicity] for multiplicity in range(2, len(bins)))
        >= s2_lower_bound
    )
    correction = sum(
        (multiplicity - 1) * bins[multiplicity] for multiplicity in range(2, len(bins))
    )
    model.Minimize(correction)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = native_limit_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = 0
    started = time.monotonic()
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    has_solution = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    histogram = [int(solver.Value(value)) for value in bins] if has_solution else None
    incumbent = int(solver.Value(correction)) if has_solution else None
    objective_bound = (
        float(solver.BestObjectiveBound())
        if has_solution
        else 2.0 * s2_lower_bound / maximum_multiplicity
    )
    certified_correction = (
        incumbent if status == cp_model.OPTIMAL else max(0, math.ceil(objective_bound - 1e-9))
    )
    moments = multiplicity_moments(histogram) if histogram is not None else {}
    covered = sum(histogram[1:]) if histogram is not None else None
    return {
        "status": status_name,
        "outcome_count": outcome_count,
        "exact_s1": exact_s1,
        "s2_lower_bound": s2_lower_bound,
        "maximum_multiplicity": maximum_multiplicity,
        "histogram": histogram,
        "incumbent_correction": incumbent,
        "objective_bound": objective_bound,
        "certified_correction_lower_bound": certified_correction,
        "relaxed_union_upper_bound": (
            outcome_count - histogram[0] if histogram is not None else None
        ),
        "histogram_covered_outcomes": covered,
        "moments_of_joint_relaxation_histogram": moments,
        "native_wall_limit_seconds": native_limit_seconds,
        "native_wall_time_seconds": time.monotonic() - started,
        "runtime": runtime,
        "workers": SOLVER_WORKERS,
    }


def solve_s4_minimum(
    state_id: str,
    *,
    native_limit_seconds: float = S4_NATIVE_LIMIT_SECONDS,
) -> dict[str, Any]:
    """Attempt the final full-support S4 minimization with a native limit."""

    runtime = r8.solver_runtime_preflight()
    state = next(
        (item for item in r8.load_bearing_frontier_states() if item.identifier == state_id),
        None,
    )
    if state is None:
        raise ValueError("unknown load-bearing state")
    cp_model: Any = importlib.import_module("ortools.sat.python.cp_model")
    model_builder_name = "_build_state_optimization_model"
    state_model_builder = getattr(r8, model_builder_name)
    optimization = state_model_builder(state.witness_counts)
    objective = sum(optimization.s4_costs)
    optimization.incidence.model.Minimize(objective)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = native_limit_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = 0
    started = time.monotonic()
    status = solver.Solve(optimization.incidence.model)
    status_name = solver.StatusName(status)
    has_solution = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    incumbent = int(solver.Value(objective)) if has_solution else None
    lower_bound = max(
        optimization.moment_floor.s4_pairwise_minimum_floor,
        math.ceil(solver.BestObjectiveBound() - 1e-9)
        if has_solution
        else optimization.moment_floor.s4_pairwise_minimum_floor,
    )
    return {
        "state_id": state_id,
        "status": status_name,
        "incumbent_s4": incumbent,
        "certified_s4_lower_bound": lower_bound,
        "minimum_proven": status == cp_model.OPTIMAL and incumbent == lower_bound,
        "native_wall_limit_seconds": native_limit_seconds,
        "native_wall_time_seconds": time.monotonic() - started,
        "runtime": runtime,
        "workers": SOLVER_WORKERS,
    }


def _run_solver_child(
    *arguments: str,
    external_timeout_seconds: float,
) -> dict[str, Any]:
    """Run one native-limited solver in a parent process with a hard timeout."""

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    existing_pythonpath = environment.get("PYTHONPATH")
    pythonpath = [str(SRC_ROOT)]
    if existing_pythonpath:
        pythonpath.append(existing_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", MODULE_NAME, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=external_timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "EXTERNAL_TIMEOUT",
            "external_wall_time_seconds": time.monotonic() - started,
            "external_timeout_seconds": external_timeout_seconds,
        }
    wall_seconds = time.monotonic() - started
    if completed.returncode != 0:
        return {
            "status": "PROCESS_ERROR",
            "stderr": completed.stderr[-2_000:],
            "external_wall_time_seconds": wall_seconds,
            "external_timeout_seconds": external_timeout_seconds,
        }
    result = json.loads(completed.stdout)
    result["external_wall_time_seconds"] = wall_seconds
    result["external_timeout_seconds"] = external_timeout_seconds
    return result


def _state_inputs_for_bound(
    state: CertifiedStateInput,
) -> tuple[int, int, int]:
    profiles = anchor_incidence_profiles()
    anchor_s2 = sum(
        count * profile.pair_recovery_cost
        for count, profile in zip(state.witness_counts, profiles, strict=True)
    )
    anchor_s3 = sum(
        count * profile.triple_recovery
        for count, profile in zip(state.witness_counts, profiles, strict=True)
    )
    exact_s1 = (TICKET_COUNT - 2) * SINGLE_TICKET_OUTCOMES - anchor_s2 + anchor_s3
    if exact_s1 < 0:
        raise AssertionError("anchor subtraction produced a negative residual S1")
    return anchor_s2, anchor_s3, exact_s1


def _validate_histogram_result(
    result: dict[str, Any],
    state: CertifiedStateInput,
    exact_s1: int,
    s2_floor: int,
) -> None:
    if result.get("status") != "OK":
        raise RuntimeError(
            f"native outcome histogram incomplete for {state.identifier}: {result.get('status')}"
        )
    if result["subset_count"] != math.comb(POOL_SIZE, OUTCOME_SET_SIZE):
        raise AssertionError("native outcome-cell count failed conservation")
    full = tuple(int(value) for value in result["full_histogram"])
    exclusive = tuple(int(value) for value in result["anchor_exclusive_histogram"])
    if sum(full) != OFFICIAL_OUTCOME_COUNT:
        raise AssertionError("official outcome histogram failed conservation")
    if sum(exclusive) != ANCHOR_EXCLUSIVE_OUTCOME_COUNT:
        raise AssertionError("anchor-exclusive histogram failed conservation")
    moments = multiplicity_moments(exclusive)
    if moments.get(1) != exact_s1:
        raise AssertionError("support witness S1 disagrees with its exact state value")
    if moments.get(2, 0) < s2_floor:
        raise AssertionError("support witness S2 is below the certified state floor")
    if len(state.support_bitmasks) != TICKET_COUNT - 2:
        raise AssertionError("pinned state witness must contain 18 residual tickets")


def _state_result(
    state: CertifiedStateInput,
    witness_histogram: dict[str, Any],
    cap_result: dict[str, Any],
    envelope_result: dict[str, Any],
) -> dict[str, Any]:
    anchor_s2, anchor_s3, exact_s1 = _state_inputs_for_bound(state)
    s2_floor = r8.state_moment_floor(state.witness_counts).residual_s2_lower_bound
    _validate_histogram_result(witness_histogram, state, exact_s1, s2_floor)

    exact_cap = cap_result.get("exact_maximum")
    if exact_cap is None:
        cap_upper = cap_result.get("certified_upper_bound")
        if cap_upper is None:
            cap_upper = TICKET_COUNT - 2
        max_multiplicity = int(cap_upper)
    else:
        max_multiplicity = int(exact_cap)
    correction = int(envelope_result["certified_correction_lower_bound"])
    state_bound = JOINT_EXPRESSION_CONSTANT - anchor_s2 + anchor_s3 - correction
    prior_s2_penalty = (s2_floor + r8.PAIR_MULTIPLICITY_DIVISOR - 1) // r8.PAIR_MULTIPLICITY_DIVISOR
    corrected_pre_higher_order_bound = (
        JOINT_EXPRESSION_CONSTANT - anchor_s2 + anchor_s3 - prior_s2_penalty
    )
    exclusive_histogram = [int(value) for value in witness_histogram["anchor_exclusive_histogram"]]
    full_histogram = [int(value) for value in witness_histogram["full_histogram"]]
    witness_moments = multiplicity_moments(exclusive_histogram)
    relaxed_histogram = envelope_result.get("histogram")
    relaxed_moments = envelope_result.get("moments_of_joint_relaxation_histogram", {})
    exact_witness_union = sum(full_histogram[1:])
    witness_exclusive_union = sum(exclusive_histogram[1:])
    witness_correction = exact_s1 - witness_exclusive_union
    return {
        "state_id": state.identifier,
        "pinned_r8_upper_bound_using_legacy_single_event_count": state.current_upper_bound,
        "corrected_pre_higher_order_bound": corrected_pre_higher_order_bound,
        "witness_counts_sparse": [
            [index, count] for index, count in enumerate(state.witness_counts) if count
        ],
        "support_witness_bitmasks": list(state.support_bitmasks),
        "support_witness_sha256": r8.sha256(
            repr(r8.decode_support_witness_bitmasks(state.support_bitmasks)).encode("ascii")
        ).hexdigest(),
        "anchor_s2": anchor_s2,
        "anchor_s3": anchor_s3,
        "residual_s1_exact": exact_s1,
        "residual_s2_certified_lower_bound": s2_floor,
        "maximum_residual_winning_multiplicity": {
            **cap_result,
            "class_certified_upper_bound": max_multiplicity,
        },
        "witness_exact_histogram": {
            "outcome_set_count": witness_histogram["subset_count"],
            "official_outcome_count": sum(full_histogram),
            "full_portfolio_histogram": full_histogram,
            "anchor_exclusive_residual_histogram": exclusive_histogram,
            "full_portfolio_maximum_multiplicity": max(
                index for index, count in enumerate(full_histogram) if count
            ),
            "anchor_exclusive_maximum_multiplicity": max(
                index for index, count in enumerate(exclusive_histogram) if count
            ),
            "full_portfolio_union_outcomes": exact_witness_union,
            "anchor_exclusive_union_outcomes": witness_exclusive_union,
            "anchor_exclusive_union_correction": witness_correction,
            "moments_s1_through_s18": {
                str(order): value for order, value in witness_moments.items()
            },
            "higher_order_correction_by_multiplicity": {
                str(multiplicity): (multiplicity - 1) * count
                for multiplicity, count in enumerate(exclusive_histogram)
                if multiplicity >= 2 and count
            },
            "native_wall_time_seconds": witness_histogram["native_wall_time_seconds"],
        },
        "state_wide_joint_histogram_envelope": {
            "status": envelope_result["status"],
            "outcome_count": envelope_result["outcome_count"],
            "exact_s1": envelope_result["exact_s1"],
            "s2_lower_bound": envelope_result["s2_lower_bound"],
            "maximum_multiplicity": envelope_result["maximum_multiplicity"],
            "histogram": relaxed_histogram,
            "moments_s1_through_smax": {
                str(order): value for order, value in relaxed_moments.items()
            },
            "incumbent_correction": envelope_result.get("incumbent_correction"),
            "certified_correction_lower_bound": correction,
            "relaxed_union_upper_bound": (
                envelope_result["outcome_count"] - relaxed_histogram[0]
                if relaxed_histogram is not None
                else None
            ),
            "native_wall_limit_seconds": envelope_result["native_wall_limit_seconds"],
            "native_wall_time_seconds": envelope_result["native_wall_time_seconds"],
            "external_timeout_seconds": envelope_result.get("external_timeout_seconds"),
            "workers": envelope_result.get("workers", SOLVER_WORKERS),
            "scope": (
                "Exact optimum over the outcome-conserving histogram relaxation "
                "with exact S1, certified S2 floor, and the state-wide multiplicity "
                "cap; the stored histogram is jointly coherent but is not asserted "
                "to be the actual support-class histogram."
            ),
        },
        "certified_state_r3_bound": state_bound,
        "pruned_below_r5": state_bound <= CURRENT_R5_BOUND,
    }


def build_result(
    runtime: dict[str, str],
    state_results: tuple[dict[str, Any], ...],
    final_s4: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the compact state, S4, and higher-order handoff record."""

    state_bounds = tuple(int(row["certified_state_r3_bound"]) for row in state_results)
    r3_bound = max(
        R7_TAIL_BOUND,
        R7_FRONTIER_NONLOAD_BOUND,
        *state_bounds,
    )
    certified_states = load_certified_states()
    exact_s4_prefix = {state.identifier: state.prior_s4_witness for state in certified_states[:6]}
    last_state = certified_states[-1]
    solver_lower = final_s4.get("certified_s4_lower_bound")
    if solver_lower is None:
        solver_lower = last_state.prior_s4_lower_bound
    final_lower = max(last_state.prior_s4_lower_bound, int(solver_lower))
    solver_incumbent = final_s4.get("incumbent_s4")
    final_upper = last_state.prior_s4_witness if solver_incumbent is None else int(solver_incumbent)
    final_proven = bool(final_s4.get("minimum_proven")) or (
        last_state.prior_s4_proven and final_lower == final_upper
    )
    exact_s4_record = {
        "first_six_exact_minima": exact_s4_prefix,
        "last_state_id": last_state.identifier,
        "last_state_minimum_interval": [final_lower, final_upper],
        "last_state_minimum_proven": final_proven,
        "last_state_solver": final_s4,
    }
    all_histograms_complete = all(
        row["witness_exact_histogram"]["official_outcome_count"] == OFFICIAL_OUTCOME_COUNT
        and row["state_wide_joint_histogram_envelope"]["status"] == "OPTIMAL"
        for row in state_results
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": (
            "CERTIFIED_SEVEN_STATE_HIGHER_ORDER_ENVELOPES"
            if all_histograms_complete
            else "PARTIAL_CERTIFICATE"
        ),
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "STATE_COUNT": len(state_results),
        "EXACT_S4_STATUS": exact_s4_record,
        "MAX_WINNING_MULTIPLICITY": {
            "witness_maxima_by_state": {
                row["state_id"]: row["witness_exact_histogram"][
                    "full_portfolio_maximum_multiplicity"
                ]
                for row in state_results
            },
            "state_wide_residual_upper_bounds": {
                row["state_id"]: row["maximum_residual_winning_multiplicity"][
                    "class_certified_upper_bound"
                ]
                for row in state_results
            },
            "maximum_across_seven_witnesses": max(
                row["witness_exact_histogram"]["full_portfolio_maximum_multiplicity"]
                for row in state_results
            ),
            "maximum_state_wide_residual_upper_bound": max(
                row["maximum_residual_winning_multiplicity"]["class_certified_upper_bound"]
                for row in state_results
            ),
        },
        "HIGHER_ORDER_CORRECTION": {
            "witness_exact_by_state": {
                row["state_id"]: row["witness_exact_histogram"]["anchor_exclusive_union_correction"]
                for row in state_results
            },
            "state_wide_certified_lower_bound_by_state": {
                row["state_id"]: row["state_wide_joint_histogram_envelope"][
                    "certified_correction_lower_bound"
                ]
                for row in state_results
            },
            "joint_moment_representation": (
                "Each state-wide correction comes from one outcome-conserving "
                "integer multiplicity histogram optimized jointly over all bins. "
                "Its S3, S4, S5, and higher moments are read from that same "
                "histogram; no independently optimized moments are combined."
            ),
        },
        "R3_BOUND": r3_bound,
        "R3_STATUS": (
            "UPSTREAM_AUTHORITY_INVALIDATED_BY_SINGLE_EVENT_COUNT_MISMATCH"
            if r3_bound > CURRENT_R3_BOUND
            else "TIGHTENED_OPEN"
            if r3_bound < CURRENT_R3_BOUND
            else "UNCHANGED_TAIL_DOMINATED"
        ),
        "SUCCESS_A": r3_bound <= CURRENT_R5_BOUND,
        "SUCCESS_B": r3_bound < CURRENT_R3_BOUND,
        "SUCCESS_C": all_histograms_complete,
        "CERTIFICATE_SCOPE": (
            "The seven pinned support-witness histograms are exact over all "
            "601,304,088 official outcomes. State-wide upper bounds use an exact "
            "optimum of a conservative multiplicity-histogram relaxation, with "
            "state S1 exact, S2 floored, and multiplicity capped. This does not "
            "assert that a witness histogram is invariant over every support in "
            "its count-vector class."
        ),
        "UPSTREAM_ARITHMETIC_AUDIT": {
            "legacy_single_ticket_outcomes": LEGACY_SINGLE_TICKET_OUTCOMES,
            "exact_single_ticket_outcomes": SINGLE_TICKET_OUTCOMES,
            "exact_diagonal_pair_intersection": pair_intersection_count(DRAW_SIZE),
            "per_ticket_event_count_error": SINGLE_EVENT_COUNT_CORRECTION,
            "portfolio_s1_error_for_20_tickets": LEGACY_BASELINE_CORRECTION,
            "legacy_joint_expression_constant": LEGACY_JOINT_EXPRESSION_CONSTANT,
            "exact_joint_expression_constant": JOINT_EXPRESSION_CONSTANT,
            "conclusion": (
                "The pinned upstream single-event constant is inconsistent with "
                "its own exact diagonal pair-intersection table and the official "
                "outcome model. Bounds are recomputed locally with the exact count; "
                "no production source was changed."
            ),
        },
        "R3_LOAD_BEARING_STATES": list(state_results),
        "R7_TAIL_BOUND": R7_TAIL_BOUND,
        "R7_FRONTIER_NONLOAD_BOUND": R7_FRONTIER_NONLOAD_BOUND,
        "INCUMBENT": INCUMBENT,
        "LEAF_GAP": r3_bound - INCUMBENT,
        "OUTCOME_CONSERVATION": {
            "official_outcomes": OFFICIAL_OUTCOME_COUNT,
            "seven_number_outcome_cells": math.comb(POOL_SIZE, OUTCOME_SET_SIZE),
            "official_outcomes_per_cell": OUTCOME_MULTIPLICITY,
            "anchor_exclusive_outcomes": ANCHOR_EXCLUSIVE_OUTCOME_COUNT,
            "exact_single_ticket_winning_outcomes": SINGLE_TICKET_OUTCOMES,
            "anchor_pair_union_outcomes": ANCHOR_PAIR_UNION_OUTCOMES,
        },
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_WORKERS": SOLVER_WORKERS,
        "FOCUSED_TESTS": "NOT_RUN",
        "RUFF": "NOT_RUN",
        "PYRIGHT": "NOT_RUN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "ATTEMPT_LEDGER": [
            {
                "attempt": 1,
                "action": "Create exact worktree",
                "result": "FAILED_BEFORE_GIT",
                "reason": "zsh path special variable shadowed PATH",
                "state_change": "NONE",
            },
            {
                "attempt": 2,
                "action": "Bundled Python runtime preflight",
                "result": "UNAVAILABLE",
                "reason": "Python 3.12.14 and OR-Tools absent",
                "state_change": "NONE",
            },
            {
                "attempt": 3,
                "action": "Configured project runtime preflight",
                "result": "PASS",
                "reason": "Python 3.13.8 and OR-Tools 9.15.6755",
                "state_change": "NONE",
            },
        ],
    }


def write_result(result: dict[str, Any], path: Path = RESULT_PATH) -> None:
    """Write the compact result once, without replacing existing evidence."""

    if path.exists():
        raise FileExistsError(f"result already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stamp_verification(
    path: Path,
    *,
    focused_tests: str,
    ruff: str,
    pyright: str,
) -> None:
    """Record the observed required checks in the task result."""

    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("TASK_ID") != TASK_ID or result.get("BASE_HEAD") != BASE_HEAD:
        raise ValueError("result identity changed before verification stamping")
    result["FOCUSED_TESTS"] = focused_tests
    result["RUFF"] = ruff
    result["PYRIGHT"] = pyright
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_analysis(output_path: Path = RESULT_PATH) -> dict[str, Any]:
    """Run the bounded seven-state witness census and state-wide moment solves."""

    runtime = runtime_preflight()
    states = load_certified_states()
    state_results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="b649-k20-r3-r9-") as temporary:
        executable = compile_native_counter(Path(temporary))
        for state in states:
            ticket_masks = (
                ANCHOR_A_MASK,
                ANCHOR_B_MASK,
                *state.support_bitmasks,
            )
            witness_histogram = run_native_counter(
                executable,
                tuple(ticket_masks),
                native_limit_seconds=HISTOGRAM_NATIVE_LIMIT_SECONDS,
                external_timeout_seconds=HISTOGRAM_EXTERNAL_TIMEOUT_SECONDS,
            )
            anchor_s2, anchor_s3, exact_s1 = _state_inputs_for_bound(state)
            del anchor_s2, anchor_s3
            s2_floor = r8.state_moment_floor(state.witness_counts).residual_s2_lower_bound
            _validate_histogram_result(witness_histogram, state, exact_s1, s2_floor)

            cap_result = _run_solver_child(
                "--solve-multiplicity-cap",
                state.identifier,
                external_timeout_seconds=MULTIPLICITY_EXTERNAL_TIMEOUT_SECONDS,
            )
            cap_upper = int(cap_result.get("certified_upper_bound", TICKET_COUNT - 2))
            envelope_result = _run_solver_child(
                "--solve-histogram-envelope",
                state.identifier,
                str(cap_upper),
                external_timeout_seconds=MULTIPLICITY_EXTERNAL_TIMEOUT_SECONDS,
            )
            if envelope_result.get("status") == "PROCESS_ERROR":
                raise RuntimeError(
                    f"histogram envelope failed for {state.identifier}: "
                    f"{envelope_result.get('stderr')}"
                )
            state_results.append(
                _state_result(
                    state,
                    witness_histogram,
                    cap_result,
                    envelope_result,
                )
            )

    final_state = states[-1]
    final_s4 = _run_solver_child(
        "--solve-s4-minimum",
        final_state.identifier,
        external_timeout_seconds=S4_EXTERNAL_TIMEOUT_SECONDS,
    )
    if final_s4.get("status") == "PROCESS_ERROR":
        final_s4["certified_s4_lower_bound"] = final_state.prior_s4_lower_bound
    result = build_result(runtime, tuple(state_results), final_s4)
    write_result(result, output_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-analysis", action="store_true")
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    parser.add_argument("--solve-multiplicity-cap", metavar="STATE_ID")
    parser.add_argument("--solve-histogram-envelope", nargs=2, metavar=("STATE_ID", "MAX_M"))
    parser.add_argument("--solve-s4-minimum", metavar="STATE_ID")
    arguments = parser.parse_args(argv)

    if arguments.solve_multiplicity_cap:
        print(
            json.dumps(
                solve_multiplicity_cap(arguments.solve_multiplicity_cap),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    if arguments.solve_histogram_envelope:
        state_id, maximum_text = arguments.solve_histogram_envelope
        state = next(
            (item for item in r8.load_bearing_frontier_states() if item.identifier == state_id),
            None,
        )
        if state is None:
            raise ValueError("unknown load-bearing state")
        anchor_s2 = sum(
            count * profile.pair_recovery_cost
            for count, profile in zip(
                state.witness_counts, anchor_incidence_profiles(), strict=True
            )
        )
        anchor_s3 = sum(
            count * profile.triple_recovery
            for count, profile in zip(
                state.witness_counts, anchor_incidence_profiles(), strict=True
            )
        )
        exact_s1 = (TICKET_COUNT - 2) * SINGLE_TICKET_OUTCOMES - anchor_s2 + anchor_s3
        solved = solve_histogram_relaxation(
            ANCHOR_EXCLUSIVE_OUTCOME_COUNT,
            exact_s1,
            r8.state_moment_floor(state.witness_counts).residual_s2_lower_bound,
            int(maximum_text),
        )
        solved["state_id"] = state_id
        print(json.dumps(solved, sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.solve_s4_minimum:
        print(
            json.dumps(
                solve_s4_minimum(arguments.solve_s4_minimum),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    if not arguments.run_analysis:
        parser.error("select --run-analysis or a bounded solver action")

    result = run_analysis(arguments.output)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "STATE_COUNT": result["STATE_COUNT"],
                "EXACT_S4_STATUS": result["EXACT_S4_STATUS"],
                "R3_BOUND": result["R3_BOUND"],
                "R3_STATUS": result["R3_STATUS"],
                "SUCCESS_C": result["SUCCESS_C"],
                "RESULT_PATH": str(arguments.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
