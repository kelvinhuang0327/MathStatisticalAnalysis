"""Resolve every still-active profile tied at the K20 minimum-S2 top bound.

The ranked prefix is inherited from R8.  This module reconstructs only the
remaining fixed-W=836 suffix, screens it with the established pair and residual
degree conditions, then certifies support realizability and profile-specific
motif bounds with bounded single-worker CP-SAT runs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from itertools import combinations
from math import ceil, comb, floor
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_REUSED_S4_LOWER_BOUND,
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
    validate_k20_support_realization,
)
from .b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    ACTIVE_PROFILE as PREVIOUSLY_ELIMINATED_PROFILE,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    ACTIVE_PROFILE_COARSE_FAMILY_BOUND,
    ErdosGallaiViolation,
    coarse_profile_envelope,
    profile_shadow_obstruction,
    triple_shadow_degree_sequence,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    EXPECTED_NEXT_PROFILE as FIRST_UNPROCESSED_PROFILE,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_INCUMBENT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    linear_triple_degree_sequence_passes_pair_capacity,
    minimum_internal_pair_uses,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]
Pair = tuple[int, int]
Triple = tuple[int, int, int]

PLATEAU_BOUND = ACTIVE_PROFILE_COARSE_FAMILY_BOUND
PLATEAU_WEDGE_COUNT = 836
PROMOTION_CAP = 12
PROOF_WALL_BUDGET_SECONDS = 3_600.0
NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS = 12.0
NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS = 12.0
NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS = 10.0
EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS = 90.0
MAX_NEXT_PROFILE_PREFIX_LEAVES = 1_024
SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND = 1_680


@dataclass(frozen=True, slots=True)
class PlateauEnumeration:
    """Deterministic suffix of dangerous profiles tied at the active bound."""

    profiles: tuple[DegreeProfile, ...]
    complete_profiles_examined: int
    pair_capacity_profiles_checked: int


@dataclass(frozen=True, slots=True)
class NextDistinctProfile:
    """First dangerous profile at the next distinct coarse family bound."""

    degree_profile: DegreeProfile
    wedge_count: int
    family_upper_bound: int
    square_sum: int
    complete_profiles_examined: int
    square_sum_classes_examined: int


def _minimum_square_sum(total: int, slots: int) -> int | None:
    if slots == 0:
        return 0 if total == 0 else None
    if total < 0 or total > slots * K20_TICKET_CAPACITY:
        return None
    quotient, remainder = divmod(total, slots)
    return (slots - remainder) * quotient**2 + remainder * (quotient + 1) ** 2


def _maximum_square_sum(total: int, slots: int, degree_cap: int) -> int | None:
    if slots == 0:
        return 0 if total == 0 else None
    if total < 0 or total > slots * degree_cap:
        return None
    if degree_cap == 0:
        return 0 if total == 0 else None
    full, remainder = divmod(total, degree_cap)
    return full * degree_cap**2 + remainder**2


def enumerate_current_top_plateau() -> PlateauEnumeration:
    """Enumerate only the R8-pinned suffix in the fixed W=836 tie class.

    The preceding R8 profile is already eliminated.  Its committed successor
    is the first unresolved rank, so the search prunes every lexicographically
    earlier profile and fixes the degree-square sum that defines W=836.
    """

    reference = FIRST_UNPROCESSED_PROFILE
    reference_envelope = coarse_profile_envelope(reference)
    if reference_envelope.wedge_count != PLATEAU_WEDGE_COUNT:
        raise AssertionError("the R8-pinned next profile left the W=836 class")
    if reference_envelope.family_upper_bound != PLATEAU_BOUND:
        raise AssertionError("the R8-pinned next profile changed its coarse bound")

    target_square_sum = sum(degree**2 for degree in reference)
    prefix: list[int] = []
    found: list[DegreeProfile] = []
    complete_profiles_examined = 0
    pair_capacity_profiles_checked = 0

    def visit(
        index: int,
        previous_degree: int,
        remaining_sum: int,
        remaining_square_sum: int,
        prefix_sum: int,
        already_after_reference: bool,
    ) -> None:
        nonlocal complete_profiles_examined
        nonlocal pair_capacity_profiles_checked

        remaining_slots = K20_TICKET_COUNT - index
        if remaining_slots == 0:
            if remaining_sum != 0 or remaining_square_sum != 0:
                return
            complete_profiles_examined += 1
            candidate = tuple(prefix)
            if candidate > reference:
                return
            if not linear_triple_degree_sequence_passes_pair_capacity(
                candidate, K20_TRIPLE_SUPPORT_COUNT
            ):
                return
            residual = residual_double_ticket_degrees(candidate)
            if not simple_graph_degree_sequence_is_graphical(residual):
                return
            pair_capacity_profiles_checked += 1
            envelope = coarse_profile_envelope(candidate)
            if envelope.family_upper_bound == PLATEAU_BOUND:
                found.append(candidate)
            return

        maximum_degree = min(previous_degree, K20_TICKET_CAPACITY, remaining_sum)
        if maximum_degree * remaining_slots < remaining_sum:
            return
        for degree in range(maximum_degree, -1, -1):
            if not already_after_reference and degree > reference[index]:
                continue
            after_reference = already_after_reference or degree < reference[index]
            suffix_sum = remaining_sum - degree
            suffix_square_sum = remaining_square_sum - degree**2
            suffix_slots = remaining_slots - 1
            if suffix_sum < 0 or suffix_square_sum < 0:
                continue
            if suffix_sum > suffix_slots * degree:
                continue
            minimum_squares = _minimum_square_sum(suffix_sum, suffix_slots)
            maximum_squares = _maximum_square_sum(suffix_sum, suffix_slots, degree)
            if (
                minimum_squares is None
                or maximum_squares is None
                or not minimum_squares <= suffix_square_sum <= maximum_squares
            ):
                continue
            next_prefix_sum = prefix_sum + degree
            if minimum_internal_pair_uses(next_prefix_sum, K20_TRIPLE_SUPPORT_COUNT) > comb(
                index + 1, 2
            ):
                continue
            prefix.append(degree)
            visit(
                index + 1,
                degree,
                suffix_sum,
                suffix_square_sum,
                next_prefix_sum,
                after_reference,
            )
            prefix.pop()

    visit(
        0,
        K20_TICKET_CAPACITY,
        sum(reference),
        target_square_sum,
        0,
        False,
    )
    profiles = tuple(found)
    if not profiles or profiles[0] != reference:
        raise AssertionError("the fixed-wedge suffix did not start at the R8 successor")
    if any(
        coarse_profile_envelope(profile).family_upper_bound != PLATEAU_BOUND for profile in profiles
    ):
        raise AssertionError("the reconstructed plateau contains a different bound")
    return PlateauEnumeration(
        profiles=profiles,
        complete_profiles_examined=complete_profiles_examined,
        pair_capacity_profiles_checked=pair_capacity_profiles_checked,
    )


def _cp_model_api() -> Any:
    from ortools.sat.python import cp_model

    return cast(Any, cp_model)


def _support_model(
    profile: DegreeProfile,
) -> tuple[Any, dict[Triple, Any], dict[Pair, Any], dict[Pair, list[Any]]]:
    cp_model = _cp_model_api()
    model: Any = cp_model.CpModel()
    active_vertices = tuple(index for index, degree in enumerate(profile) if degree > 0)
    candidate_triples = tuple(combinations(active_vertices, 3))
    candidate_pairs = tuple(combinations(range(K20_TICKET_COUNT), 2))
    triple_vars = {
        triple: model.NewBoolVar(f"triple_{triple[0]}_{triple[1]}_{triple[2]}")
        for triple in candidate_triples
    }
    double_vars = {
        pair: model.NewBoolVar(f"double_{pair[0]}_{pair[1]}") for pair in candidate_pairs
    }
    triples_by_vertex = {
        vertex: [variable for triple, variable in triple_vars.items() if vertex in triple]
        for vertex in range(K20_TICKET_COUNT)
    }
    triples_by_pair: dict[Pair, list[Any]] = {pair: [] for pair in candidate_pairs}
    for triple, variable in triple_vars.items():
        for pair in combinations(triple, 2):
            triples_by_pair[pair].append(variable)

    for vertex, degree in enumerate(profile):
        model.Add(sum(triples_by_vertex[vertex]) == degree)
        incident_doubles = [variable for pair, variable in double_vars.items() if vertex in pair]
        model.Add(sum(incident_doubles) == K20_TICKET_CAPACITY - degree)
    for pair, variable in double_vars.items():
        model.Add(sum(triples_by_pair[pair]) + variable <= 1)
    model.Add(sum(triple_vars.values()) == K20_TRIPLE_SUPPORT_COUNT)
    model.Add(sum(double_vars.values()) == K20_DOUBLE_SUPPORT_COUNT)
    return model, triple_vars, double_vars, triples_by_pair


def _support_witness(
    solver: Any,
    triple_vars: dict[Triple, Any],
    double_vars: dict[Pair, Any],
) -> tuple[tuple[Triple, ...], tuple[Pair, ...]]:
    triples = tuple(triple for triple, variable in triple_vars.items() if solver.Value(variable))
    doubles = tuple(pair for pair, variable in double_vars.items() if solver.Value(variable))
    return triples, doubles


def _overlap_edges(triples: Sequence[Triple], doubles: Sequence[Pair]) -> frozenset[Pair]:
    return frozenset(
        (min(first, second), max(first, second))
        for support in (*triples, *doubles)
        for first, second in combinations(support, 2)
    )


def _graph_triangle_count(edges: frozenset[Pair]) -> int:
    return sum(
        all(tuple(sorted(pair)) in edges for pair in combinations(triangle, 2))
        for triangle in combinations(range(K20_TICKET_COUNT), 3)
    )


def _degree_class_triangle_bound(
    profile: DegreeProfile,
    *,
    wall_limit_seconds: float,
) -> dict[str, object]:
    """Lower bound open wedges from the relaxed complement degree classes."""

    cp_model = _cp_model_api()
    complement_degrees = tuple(K20_TICKET_CAPACITY * 2 + 1 - degree for degree in profile)
    degree_classes = tuple(sorted(Counter(complement_degrees).items()))
    model: Any = cp_model.CpModel()
    edge_vars: dict[tuple[int, int], Any] = {}
    edge_costs: dict[tuple[int, int], int] = {}
    for first_class, (first_degree, first_size) in enumerate(degree_classes):
        for second_class in range(first_class, len(degree_classes)):
            second_degree, second_size = degree_classes[second_class]
            capacity = (
                comb(first_size, 2) if first_class == second_class else first_size * second_size
            )
            key = (first_class, second_class)
            edge_vars[key] = model.NewIntVar(0, capacity, f"class_edges_{key}")
            edge_costs[key] = max(0, K20_TICKET_COUNT - first_degree - second_degree)

    for class_index, (degree, class_size) in enumerate(degree_classes):
        incident_terms: list[Any] = []
        for other_class in range(len(degree_classes)):
            key = (
                (class_index, other_class)
                if class_index <= other_class
                else (other_class, class_index)
            )
            multiplier = 2 if class_index == other_class else 1
            incident_terms.append(multiplier * edge_vars[key])
        model.Add(sum(incident_terms) == degree * class_size)

    weighted_open_wedges = sum(edge_costs[key] * variable for key, variable in edge_vars.items())
    model.Minimize(weighted_open_wedges)
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = wall_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    solver.parameters.log_search_progress = False
    solver_status = solver.Solve(model)
    status_name = str(solver.StatusName(solver_status))
    if solver_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "SOLVER_STATUS": status_name,
            "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
            "GRAPH_TRIANGLE_UPPER_BOUND": None,
        }
    weighted_lower_bound = (
        int(solver.Value(weighted_open_wedges))
        if solver_status == cp_model.OPTIMAL
        else floor(solver.BestObjectiveBound())
    )
    wedge_count = overlap_wedge_count(profile)
    residue = wedge_count % 3
    open_wedge_lower_bound = residue + 3 * max(0, ceil((weighted_lower_bound - residue) / 3))
    triangle_bound = (wedge_count - open_wedge_lower_bound) // 3
    return {
        "SOLVER_STATUS": status_name,
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
        "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": weighted_lower_bound,
        "OPEN_WEDGE_LOWER_BOUND": open_wedge_lower_bound,
        "GRAPH_TRIANGLE_UPPER_BOUND": triangle_bound,
    }


def _motif_triangle_bound(
    profile: DegreeProfile,
    witness_triples: tuple[Triple, ...],
    witness_doubles: tuple[Pair, ...],
    *,
    wall_limit_seconds: float,
) -> dict[str, object]:
    cp_model = _cp_model_api()
    model, triple_vars, double_vars, triples_by_pair = _support_model(profile)
    witness_triple_set = set(witness_triples)
    witness_double_set = set(witness_doubles)
    for triple, variable in triple_vars.items():
        model.AddHint(variable, int(triple in witness_triple_set))
    for pair, variable in double_vars.items():
        model.AddHint(variable, int(pair in witness_double_set))

    overlap_vars = {pair: model.NewBoolVar(f"overlap_{pair[0]}_{pair[1]}") for pair in double_vars}
    for pair, variable in overlap_vars.items():
        model.Add(variable == sum(triples_by_pair[pair]) + double_vars[pair])

    witness_graph_edges = _overlap_edges(witness_triples, witness_doubles)
    for pair, variable in overlap_vars.items():
        model.AddHint(variable, int(pair in witness_graph_edges))

    triangle_vars: dict[Triple, Any] = {}
    for triangle in combinations(range(K20_TICKET_COUNT), 3):
        triangle_var = model.NewBoolVar(f"triangle_{triangle[0]}_{triangle[1]}_{triangle[2]}")
        triangle_edges = tuple(
            overlap_vars[(min(pair), max(pair))] for pair in combinations(triangle, 2)
        )
        for edge_var in triangle_edges:
            model.Add(triangle_var <= edge_var)
        model.Add(triangle_var >= sum(triangle_edges) - 2)
        triangle_vars[triangle] = triangle_var
        is_witness_triangle = all(
            tuple(sorted(pair)) in witness_graph_edges for pair in combinations(triangle, 2)
        )
        model.AddHint(
            triangle_var,
            int(is_witness_triangle),
        )

    model.Maximize(sum(triangle_vars.values()))
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = wall_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    solver.parameters.symmetry_level = 2
    solver.parameters.log_search_progress = False
    solver_status = solver.Solve(model)
    status_name = str(solver.StatusName(solver_status))
    if solver_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "SOLVER_STATUS": status_name,
            "BOUND_KIND": "UNAVAILABLE",
            "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
            "SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND": None,
            "WITNESS_GRAPH_TRIANGLE_COUNT": None,
        }
    witness_triangle_count = int(sum(solver.Value(variable) for variable in triangle_vars.values()))
    motif_triples, motif_doubles = _support_witness(solver, triple_vars, double_vars)
    motif_graph_edges = _overlap_edges(motif_triples, motif_doubles)
    if _graph_triangle_count(motif_graph_edges) != witness_triangle_count:
        raise AssertionError("CP-SAT triangle count disagrees with its optimized supports")
    motif_signature = validate_k20_support_realization(motif_triples, motif_doubles, profile)
    certified_bound = (
        witness_triangle_count
        if solver_status == cp_model.OPTIMAL
        else min(PLATEAU_WEDGE_COUNT // 3, ceil(solver.BestObjectiveBound()))
    )
    return {
        "SOLVER_STATUS": status_name,
        "BOUND_KIND": (
            "OPTIMAL_OBJECTIVE"
            if solver_status == cp_model.OPTIMAL
            else "BEST_OBJECTIVE_UPPER_BOUND"
        ),
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
        "SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND": certified_bound,
        "WITNESS_GRAPH_TRIANGLE_COUNT": witness_triangle_count,
        "MOTIF_WITNESS_TRIPLES": [list(triple) for triple in motif_triples],
        "MOTIF_WITNESS_DOUBLE_SUPPORTS": [list(pair) for pair in motif_doubles],
        "MOTIF_WITNESS_MOTIFS": asdict(motif_signature),
    }


def _solve_profile_child(
    profile: DegreeProfile,
    *,
    support_wall_limit_seconds: float,
    motif_wall_limit_seconds: float,
    degree_class_wall_limit_seconds: float,
) -> dict[str, object]:
    cp_model = _cp_model_api()
    support_model, triple_vars, double_vars, _ = _support_model(profile)
    support_solver: Any = cp_model.CpSolver()
    support_solver.parameters.max_time_in_seconds = support_wall_limit_seconds
    support_solver.parameters.num_search_workers = 1
    support_solver.parameters.random_seed = 649
    support_solver.parameters.log_search_progress = False
    support_status_code = support_solver.Solve(support_model)
    support_status = str(support_solver.StatusName(support_status_code))
    payload: dict[str, object] = {
        "PROFILE": list(profile),
        "SUPPORT_SOLVER_STATUS": support_status,
        "SUPPORT_SOLVER_WALL_TIME_SECONDS": float(support_solver.WallTime()),
    }
    if support_status_code == cp_model.INFEASIBLE:
        payload["REALIZABILITY"] = "UNREALIZABLE"
        return payload
    if support_status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        payload["REALIZABILITY"] = "UNRESOLVED"
        return payload

    triples, doubles = _support_witness(support_solver, triple_vars, double_vars)
    signature = validate_k20_support_realization(triples, doubles, profile)
    payload["REALIZABILITY"] = "REALIZABLE"
    payload["WITNESS_TRIPLES"] = [list(triple) for triple in triples]
    payload["WITNESS_DOUBLE_SUPPORTS"] = [list(pair) for pair in doubles]
    payload["WITNESS_MOTIFS"] = asdict(signature)
    motif = _motif_triangle_bound(
        profile,
        triples,
        doubles,
        wall_limit_seconds=motif_wall_limit_seconds,
    )
    class_bound = _degree_class_triangle_bound(
        profile,
        wall_limit_seconds=degree_class_wall_limit_seconds,
    )
    payload["MOTIF_SOLVER"] = motif
    payload["DEGREE_CLASS_RELAXATION"] = class_bound
    return payload


def _run_profile_solver(
    profile: DegreeProfile,
    *,
    external_timeout_seconds: float = EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
    support_wall_limit_seconds: float = NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
    motif_wall_limit_seconds: float = NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
    degree_class_wall_limit_seconds: float = NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
) -> dict[str, object]:
    """Run the native solver chain in a child with an enforced hard timeout."""

    module_name = "lottolab.research.b649_k20_min_s2_top_plateau_closure_r9"
    request = {
        "profile": list(profile),
        "support_wall_limit_seconds": support_wall_limit_seconds,
        "motif_wall_limit_seconds": motif_wall_limit_seconds,
        "degree_class_wall_limit_seconds": degree_class_wall_limit_seconds,
    }
    command = [
        sys.executable,
        "-m",
        module_name,
        "--solver-profile",
        json.dumps(request, separators=(",", ":")),
    ]
    project_root = Path(__file__).resolve().parents[3]
    started = monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=external_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"profile solver exceeded its {external_timeout_seconds:g}s hard timeout"
        ) from exc
    elapsed = monotonic() - started
    if completed.returncode != 0:
        raise RuntimeError(
            "profile solver child failed: " + completed.stderr[-2_000:] + completed.stdout[-2_000:]
        )
    try:
        decoded: object = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("profile solver child returned invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("profile solver child returned a non-object result")
    decoded_mapping = cast(dict[object, object], decoded)
    if any(not isinstance(key, str) for key in decoded_mapping):
        raise RuntimeError("profile solver child returned a non-string result key")
    payload = cast(dict[str, object], decoded_mapping)
    payload["EXTERNAL_SOLVER_WALL_TIME_SECONDS"] = elapsed
    return payload


def _parse_support_rows(raw: object, support_size: int) -> tuple[tuple[int, ...], ...]:
    if not isinstance(raw, list):
        raise AssertionError("support witness must be a list")
    parsed_rows: list[tuple[int, ...]] = []
    raw_rows = cast(list[object], raw)
    for raw_row in raw_rows:
        if not isinstance(raw_row, list):
            raise AssertionError("support witness row must be a list")
        row = cast(list[object], raw_row)
        if len(row) != support_size or any(type(value) is not int for value in row):
            raise AssertionError("support witness row has the wrong size or value type")
        parsed_rows.append(tuple(cast(int, value) for value in row))
    return tuple(parsed_rows)


def _profile_envelope_from_solver(
    profile: DegreeProfile,
    solver_payload: dict[str, object],
    *,
    shadow_obstruction: ErdosGallaiViolation | None,
) -> dict[str, object]:
    resolution = dict(solver_payload)
    resolution["PROFILE"] = list(profile)
    resolution["SHADOW_DEGREES"] = list(triple_shadow_degree_sequence(profile))
    resolution["SHADOW_OBSTRUCTION"] = (
        None if shadow_obstruction is None else asdict(shadow_obstruction)
    )
    realizability = str(solver_payload.get("REALIZABILITY", "UNRESOLVED"))
    resolution["REALIZABILITY"] = realizability
    resolution["COARSE_FAMILY_UPPER_BOUND"] = coarse_profile_envelope(profile).family_upper_bound
    if realizability != "REALIZABLE":
        resolution["FAMILY_UPPER_BOUND"] = None
        return resolution

    triples_raw = solver_payload.get("WITNESS_TRIPLES")
    doubles_raw = solver_payload.get("WITNESS_DOUBLE_SUPPORTS")
    triples = cast(tuple[Triple, ...], _parse_support_rows(triples_raw, 3))
    doubles = cast(tuple[Pair, ...], _parse_support_rows(doubles_raw, 2))
    signature = validate_k20_support_realization(triples, doubles, profile)
    if asdict(signature) != solver_payload.get("WITNESS_MOTIFS"):
        raise AssertionError("the child support witness motif signature changed")

    motif_raw = solver_payload.get("MOTIF_SOLVER")
    class_raw = solver_payload.get("DEGREE_CLASS_RELAXATION")
    if not isinstance(motif_raw, dict) or not isinstance(class_raw, dict):
        raise AssertionError("a realizable profile lacks its motif certificates")
    motif_certificate = cast(dict[str, object], motif_raw)
    class_certificate = cast(dict[str, object], class_raw)
    coarse_triangle_bound = PLATEAU_WEDGE_COUNT // 3
    candidate_triangle_bounds = [coarse_triangle_bound]
    for source in (motif_certificate, class_certificate):
        bound = source.get(
            "SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND",
            source.get("GRAPH_TRIANGLE_UPPER_BOUND"),
        )
        if isinstance(bound, int):
            candidate_triangle_bounds.append(bound)
    triangle_bound = min(candidate_triangle_bounds)
    if triangle_bound < K20_TRIPLE_SUPPORT_COUNT:
        raise AssertionError("a triangle certificate is below the 22 core triangles")
    wedge_count = overlap_wedge_count(profile)
    noncore_triangle_bound = triangle_bound - K20_TRIPLE_SUPPORT_COUNT
    s3_bound = s3_sum_from_wedges_and_triangles(wedge_count, noncore_triangle_bound)

    # R7's already-certified seven-inactive-ticket census applies unchanged to
    # profiles with exactly seven zero triple degrees.  All other plateau
    # profiles retain the established global R2 S4 floor.
    s4_bound = max(
        K20_REUSED_S4_LOWER_BOUND,
        SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND
        if profile.count(0) == 7
        else K20_REUSED_S4_LOWER_BOUND,
    )
    fourth_order_credit = (4 * s4_bound) // 7
    family_bound = K20_S1 - K20_S2 + s3_bound - fourth_order_credit
    resolution.update(
        {
            "WITNESS_MOTIFS": asdict(signature),
            "WITNESS_GRAPH_TRIANGLE_COUNT": _graph_triangle_count(_overlap_edges(triples, doubles)),
            "GRAPH_TRIANGLE_UPPER_BOUND": triangle_bound,
            "NONCORE_TRIANGLE_UPPER_BOUND": noncore_triangle_bound,
            "LOOSE_THREE_CYCLE_UPPER_BOUND": noncore_triangle_bound,
            "PASCH_LIKE_FOUR_SUPPORT_UPPER_BOUND": noncore_triangle_bound // 4,
            "S3_UPPER_BOUND": s3_bound,
            "S4_LOWER_BOUND": s4_bound,
            "FOURTH_ORDER_CREDIT": fourth_order_credit,
            "FAMILY_UPPER_BOUND": family_bound,
        }
    )
    if family_bound > int(resolution["COARSE_FAMILY_UPPER_BOUND"]):
        raise AssertionError("the motif envelope exceeded its coarse profile bound")
    return resolution


def _first_eligible_profile_for_square_sum(
    square_sum: int,
) -> tuple[DegreeProfile | None, int]:
    prefix: list[int] = []
    examined = 0
    selected: DegreeProfile | None = None

    def visit(
        index: int,
        previous_degree: int,
        remaining_sum: int,
        remaining_square_sum: int,
        prefix_sum: int,
    ) -> bool:
        nonlocal examined
        nonlocal selected
        remaining_slots = K20_TICKET_COUNT - index
        if remaining_slots == 0:
            if remaining_sum != 0 or remaining_square_sum != 0:
                return False
            examined += 1
            candidate = tuple(prefix)
            if not linear_triple_degree_sequence_passes_pair_capacity(
                candidate, K20_TRIPLE_SUPPORT_COUNT
            ):
                return False
            if not simple_graph_degree_sequence_is_graphical(
                residual_double_ticket_degrees(candidate)
            ):
                return False
            if coarse_profile_envelope(candidate).family_upper_bound <= K20_INCUMBENT:
                return False
            selected = candidate
            return True

        maximum_degree = min(previous_degree, K20_TICKET_CAPACITY, remaining_sum)
        if maximum_degree * remaining_slots < remaining_sum:
            return False
        for degree in range(maximum_degree, -1, -1):
            suffix_sum = remaining_sum - degree
            suffix_square_sum = remaining_square_sum - degree**2
            suffix_slots = remaining_slots - 1
            if suffix_sum < 0 or suffix_square_sum < 0:
                continue
            if suffix_sum > suffix_slots * degree:
                continue
            minimum_squares = _minimum_square_sum(suffix_sum, suffix_slots)
            maximum_squares = _maximum_square_sum(suffix_sum, suffix_slots, degree)
            if (
                minimum_squares is None
                or maximum_squares is None
                or not minimum_squares <= suffix_square_sum <= maximum_squares
            ):
                continue
            next_prefix_sum = prefix_sum + degree
            if minimum_internal_pair_uses(next_prefix_sum, K20_TRIPLE_SUPPORT_COUNT) > comb(
                index + 1, 2
            ):
                continue
            prefix.append(degree)
            if visit(
                index + 1,
                degree,
                suffix_sum,
                suffix_square_sum,
                next_prefix_sum,
            ):
                return True
            prefix.pop()
        return False

    visit(
        0,
        K20_TICKET_CAPACITY,
        K20_TRIPLE_SUPPORT_COUNT * 3,
        square_sum,
        0,
    )
    return selected, examined


def find_next_distinct_profile() -> NextDistinctProfile:
    """Find the next coarse rank after the plateau without rebuilding R5."""

    starting_square_sum = sum(degree**2 for degree in FIRST_UNPROCESSED_PROFILE)
    minimum_square_sum = _minimum_square_sum(K20_TRIPLE_SUPPORT_COUNT * 3, K20_TICKET_COUNT)
    if minimum_square_sum is None:
        raise AssertionError("the minimum triple-degree square sum is unavailable")
    examined_total = 0
    classes_examined = 0
    for square_sum in range(starting_square_sum - 2, minimum_square_sum - 1, -2):
        classes_examined += 1
        profile, examined = _first_eligible_profile_for_square_sum(square_sum)
        examined_total += examined
        if examined_total > MAX_NEXT_PROFILE_PREFIX_LEAVES:
            raise RuntimeError("next-distinct search exceeded its bounded profile prefix")
        if profile is None:
            continue
        envelope = coarse_profile_envelope(profile)
        if envelope.family_upper_bound == PLATEAU_BOUND:
            continue
        if envelope.family_upper_bound > PLATEAU_BOUND:
            raise AssertionError("a lower-wedge profile outranked the exhausted plateau")
        return NextDistinctProfile(
            degree_profile=profile,
            wedge_count=envelope.wedge_count,
            family_upper_bound=envelope.family_upper_bound,
            square_sum=square_sum,
            complete_profiles_examined=examined_total,
            square_sum_classes_examined=classes_examined,
        )
    raise RuntimeError("no next dangerous profile found within the bounded search")


def compute_top_plateau_result(
    *,
    promotion_cap: int = PROMOTION_CAP,
    proof_wall_budget_seconds: float = PROOF_WALL_BUDGET_SECONDS,
) -> dict[str, object]:
    """Promote the entire current top plateau up to the declared task limits."""

    if not 1 <= promotion_cap <= PROMOTION_CAP:
        raise ValueError("promotion_cap must be between one and twelve")
    if proof_wall_budget_seconds <= 0:
        raise ValueError("proof_wall_budget_seconds must be positive")
    started = monotonic()
    plateau = enumerate_current_top_plateau()
    profile_results: list[dict[str, object]] = []
    promotions = 0
    processed = 0
    stop_reason: str | None = None
    unresolved_index: int | None = None

    for index, profile in enumerate(plateau.profiles):
        if promotions >= promotion_cap:
            stop_reason = "PROMOTION_CAP_REACHED"
            unresolved_index = index
            break
        elapsed = monotonic() - started
        if elapsed >= proof_wall_budget_seconds:
            stop_reason = "PROOF_WALL_BUDGET_REACHED"
            unresolved_index = index
            break
        promotions += 1
        obstruction = profile_shadow_obstruction(profile)
        try:
            solver_payload = _run_profile_solver(
                profile,
                external_timeout_seconds=min(
                    EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
                    proof_wall_budget_seconds - elapsed,
                ),
            )
        except TimeoutError:
            stop_reason = "EXTERNAL_SOLVER_HARD_TIMEOUT"
            unresolved_index = index
            profile_results.append(
                {
                    "PROFILE": list(profile),
                    "REALIZABILITY": "UNRESOLVED",
                    "SHADOW_OBSTRUCTION": (None if obstruction is None else asdict(obstruction)),
                    "COARSE_FAMILY_UPPER_BOUND": PLATEAU_BOUND,
                    "FAMILY_UPPER_BOUND": None,
                }
            )
            break
        resolution = _profile_envelope_from_solver(
            profile,
            solver_payload,
            shadow_obstruction=obstruction,
        )
        profile_results.append(resolution)
        if resolution["REALIZABILITY"] == "UNRESOLVED":
            stop_reason = "SOLVER_UNRESOLVED"
            unresolved_index = index
            break
        processed += 1
    else:
        unresolved_index = len(plateau.profiles)

    remaining_profiles = plateau.profiles[unresolved_index:]
    all_profiles_resolved = processed == len(plateau.profiles)
    next_distinct: NextDistinctProfile | None = None
    if all_profiles_resolved:
        surviving_bounds: list[int] = []
        for item in profile_results:
            bound = item.get("FAMILY_UPPER_BOUND")
            if item.get("REALIZABILITY") == "REALIZABLE" and isinstance(bound, int):
                surviving_bounds.append(bound)
        plateau_survivor_bound = max(surviving_bounds, default=0)
        if plateau_survivor_bound < PLATEAU_BOUND:
            next_distinct = find_next_distinct_profile()
            family_upper_bound = max(plateau_survivor_bound, next_distinct.family_upper_bound)
            stop_reason = "PLATEAU_EXHAUSTED"
        else:
            family_upper_bound = PLATEAU_BOUND
            stop_reason = "PLATEAU_BOUND_UNCHANGED"
    else:
        family_upper_bound = PLATEAU_BOUND
        stop_reason = stop_reason or "PLATEAU_INCOMPLETE"

    family_status = (
        "CLOSED"
        if family_upper_bound <= K20_INCUMBENT
        else "OPEN_STRICTLY_TIGHTENED"
        if family_upper_bound < PLATEAU_BOUND
        else "OPEN_UNCHANGED"
    )
    if family_status == "CLOSED":
        task_status = "SUCCESS_A_FAMILY_CLOSED"
    elif family_upper_bound < PLATEAU_BOUND:
        task_status = "SUCCESS_B_BOUND_STRICTLY_DROPPED"
    elif all_profiles_resolved and next_distinct is not None:
        task_status = "SUCCESS_C_PLATEAU_EXHAUSTED"
    elif stop_reason in ("PROMOTION_CAP_REACHED", "PROOF_WALL_BUDGET_REACHED"):
        task_status = stop_reason
    else:
        task_status = stop_reason

    solver_status_values: set[str] = set()
    for item in profile_results:
        solver_status_values.add(str(item.get("SUPPORT_SOLVER_STATUS", "NOT_RUN")))
        for field in ("MOTIF_SOLVER", "DEGREE_CLASS_RELAXATION"):
            nested = item.get(field)
            if isinstance(nested, dict):
                nested_mapping = cast(dict[str, object], nested)
                solver_status_values.add(str(nested_mapping.get("SOLVER_STATUS", "NOT_RUN")))
    solver_statuses = sorted(solver_status_values)
    actual_wall = monotonic() - started
    return {
        "TASK_ID": "B649_K20_MIN_S2_TOP_PLATEAU_CLOSURE_R9",
        "TASK_STATUS": task_status,
        "BASE_HEAD": "5ac18ded3f2bc61449baa4d5e00ac0c1c8b247d1",
        "BASE_TREE": "88152c144d1c4b1ad8adcb04b4c686aaca8a147e",
        "TASK_BRANCH": "codex/b649-k20-min-s2-top-plateau-closure-r9",
        "WORKTREE_PATH": (
            "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
            "B649_K20_MIN_S2_TOP_PLATEAU_CLOSURE_R9"
        ),
        "WORKTREE_DISPOSITION": "RETAIN",
        "PLATEAU_BOUND": PLATEAU_BOUND,
        "PLATEAU_WEDGE_COUNT": PLATEAU_WEDGE_COUNT,
        "PLATEAU_PROFILE_COUNT": len(plateau.profiles),
        "PLATEAU_PROCESSED_COUNT": processed,
        "PLATEAU_REMAINING_COUNT": len(remaining_profiles),
        "PLATEAU_PROFILES": [list(profile) for profile in plateau.profiles],
        "PLATEAU_ENUMERATION": {
            "METHOD": "fixed W=836 / fixed degree-square sum / R8 successor suffix",
            "COMPLETE_PROFILES_EXAMINED": plateau.complete_profiles_examined,
            "PAIR_CAPACITY_PROFILES_CHECKED": plateau.pair_capacity_profiles_checked,
            "FULL_4850_PROFILE_RANKING_RERUN": False,
        },
        "UNREALIZABLE_PROFILE_COUNT": sum(
            item["REALIZABILITY"] == "UNREALIZABLE" for item in profile_results
        ),
        "REALIZABLE_PROFILE_COUNT": sum(
            item["REALIZABILITY"] == "REALIZABLE" for item in profile_results
        ),
        "PROFILE_BOUNDS": profile_results,
        "REMAINING_PLATEAU_PROFILES": [list(profile) for profile in remaining_profiles],
        "NEXT_DISTINCT_BOUND": (
            None if next_distinct is None else next_distinct.family_upper_bound
        ),
        "NEXT_ACTIVE_PROFILE": (
            None if next_distinct is None else list(next_distinct.degree_profile)
        ),
        "NEXT_PROFILE_SEARCH": (
            None
            if next_distinct is None
            else {
                "WEDGE_COUNT": next_distinct.wedge_count,
                "DEGREE_SQUARE_SUM": next_distinct.square_sum,
                "COMPLETE_PROFILES_EXAMINED": next_distinct.complete_profiles_examined,
                "SQUARE_SUM_CLASSES_EXAMINED": next_distinct.square_sum_classes_examined,
                "MAX_COMPLETE_PROFILE_PREFIX": MAX_NEXT_PROFILE_PREFIX_LEAVES,
            }
        ),
        "FAMILY_UPPER_BOUND": family_upper_bound,
        "INCUMBENT": K20_INCUMBENT,
        "REMAINING_FAMILY_GAP": max(0, family_upper_bound - K20_INCUMBENT),
        "FAMILY_STATUS": family_status,
        "PROMOTION_CAP": promotion_cap,
        "ACTUAL_PROMOTIONS": promotions,
        "SOLVER_STATUS": ", ".join(solver_statuses) or "NOT_RUN",
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "NATIVE_SUPPORT_SOLVER_SECONDS_PER_PROFILE": NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_MOTIF_SOLVER_SECONDS_PER_PROFILE": NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_DEGREE_CLASS_SECONDS_PER_PROFILE": NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
            "EXTERNAL_HARD_TIMEOUT_SECONDS_PER_PROFILE": EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
            "OVERALL_PROOF_WALL_BUDGET_SECONDS": proof_wall_budget_seconds,
            "WORKERS": 1,
        },
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": actual_wall,
        "SOLVER_CERTIFIED_BOUND": family_upper_bound,
        "STOP_REASON": stop_reason,
        "PREVIOUSLY_ELIMINATED_PROFILE": list(PREVIOUSLY_ELIMINATED_PROFILE),
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def _parse_solver_request(raw: str) -> dict[str, object]:
    parsed: object = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("solver request must be a JSON object")
    return cast(dict[str, object], parsed)


def _request_float(request: dict[str, object], field: str) -> float:
    value = request.get(field)
    if not isinstance(value, (int, float)):
        raise ValueError(f"solver request field {field} must be numeric")
    return float(value)


def _request_profile(request: dict[str, object]) -> DegreeProfile:
    raw_profile = request.get("profile")
    if not isinstance(raw_profile, list):
        raise ValueError("solver request profile must be a list")
    values = cast(list[object], raw_profile)
    if len(values) != K20_TICKET_COUNT or any(type(value) is not int for value in values):
        raise ValueError("solver request profile must contain twenty integers")
    return tuple(cast(int, value) for value in values)


def _encode_support_rows(raw: object) -> str:
    if not isinstance(raw, list):
        raise TypeError("support witness must be a list")
    rows = cast(list[object], raw)
    encoded_rows: list[str] = []
    for raw_row in rows:
        if not isinstance(raw_row, list):
            raise TypeError("support witness row must be a list")
        row = cast(list[object], raw_row)
        if any(type(value) is not int for value in row):
            raise TypeError("support witness vertices must be integers")
        encoded_rows.append(",".join(str(cast(int, value)) for value in row))
    return ";".join(encoded_rows)


def _compact_result(result: dict[str, object]) -> dict[str, object]:
    compact = dict(result)
    raw_resolutions = result.get("PROFILE_BOUNDS")
    if not isinstance(raw_resolutions, list):
        raise TypeError("profile result list is missing")
    resolutions: list[dict[str, object]] = []
    for raw_resolution in cast(list[object], raw_resolutions):
        if not isinstance(raw_resolution, dict):
            raise TypeError("profile result must be an object")
        resolution = cast(dict[str, object], raw_resolution).copy()
        resolution["WITNESS_TRIPLES"] = _encode_support_rows(resolution.get("WITNESS_TRIPLES"))
        resolution["WITNESS_DOUBLE_SUPPORTS"] = _encode_support_rows(
            resolution.get("WITNESS_DOUBLE_SUPPORTS")
        )
        motif_raw = resolution.get("MOTIF_SOLVER")
        if not isinstance(motif_raw, dict):
            raise TypeError("motif solver result is missing")
        motif = cast(dict[str, object], motif_raw).copy()
        motif["MOTIF_WITNESS_TRIPLES"] = _encode_support_rows(motif.get("MOTIF_WITNESS_TRIPLES"))
        motif["MOTIF_WITNESS_DOUBLE_SUPPORTS"] = _encode_support_rows(
            motif.get("MOTIF_WITNESS_DOUBLE_SUPPORTS")
        )
        resolution["MOTIF_SOLVER"] = motif
        resolutions.append(resolution)
    compact["PROFILE_BOUNDS"] = resolutions
    return compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver-profile")
    parser.add_argument("--write-result")
    args = parser.parse_args()
    if args.solver_profile is not None:
        request = _parse_solver_request(args.solver_profile)
        profile = _request_profile(request)
        result = _solve_profile_child(
            profile,
            support_wall_limit_seconds=_request_float(request, "support_wall_limit_seconds"),
            motif_wall_limit_seconds=_request_float(request, "motif_wall_limit_seconds"),
            degree_class_wall_limit_seconds=_request_float(
                request, "degree_class_wall_limit_seconds"
            ),
        )
        print(json.dumps(result, separators=(",", ":")))
        return
    if args.write_result is None:
        parser.error("--write-result is required for a full plateau proof")
    result = _compact_result(compute_top_plateau_result())
    output_path = Path(args.write_result)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()


__all__ = [
    "EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS",
    "FIRST_UNPROCESSED_PROFILE",
    "MAX_NEXT_PROFILE_PREFIX_LEAVES",
    "NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS",
    "NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS",
    "NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS",
    "PLATEAU_BOUND",
    "PLATEAU_WEDGE_COUNT",
    "PROMOTION_CAP",
    "PROOF_WALL_BUDGET_SECONDS",
    "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND",
    "NextDistinctProfile",
    "PlateauEnumeration",
    "compute_top_plateau_result",
    "enumerate_current_top_plateau",
    "find_next_distinct_profile",
]
