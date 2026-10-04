"""Tighten the K20 minimum-S2 envelope using only the four feasible top profiles.

The support system has 22 linear triple supports and 27 residual double
supports.  This module reuses the four committed full-support witnesses from
R6 without rerunning its 4,850-profile ranking.  A compact CP-SAT model can
maximize overlap-graph triangles for each fixed degree profile.  Independently,
the inactive-ticket double graph gives a certified S4 floor by an exhaustive
seven-vertex missing-edge census.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from math import ceil, comb, floor
from time import perf_counter
from typing import Any, cast

from . import b649_k20_min_s2_top_envelope_realizability_r6 as r6
from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20SupportMotifSignature,
    validate_k20_support_realization,
)
from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_S1,
    K20_S2,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)
from .b649_k20_min_s2_top_envelope_realizability_r6 import K20TopProfileResolution

type DegreeProfile = tuple[int, ...]
type Pair = tuple[int, int]
type Triple = tuple[int, int, int]

TOP_PROFILES: tuple[DegreeProfile, ...] = (
    r6.TOP_PROFILE_1,
    r6.TOP_PROFILE_2,
    r6.TOP_PROFILE_4,
    r6.TOP_PROFILE_5,
)
TOP_PROFILE_COUNT = 5
EXACTLY_ANALYZED_PROFILE_COUNT = 4
TOP_ENVELOPE_WEDGE_COUNT = 837
ANALYTIC_GRAPH_TRIANGLE_UPPER_BOUND = 278
SOLVER_PROFILE_WALL_LIMIT_SECONDS = 12.0
DEGREE_CLASS_RELAXATION_WALL_LIMIT_SECONDS = 10.0
SOLVER_EXTERNAL_WALL_LIMIT_SECONDS = 90.0

NEXT_UNPROCESSED_PROFILE: DegreeProfile = (
    6,
    6,
    6,
    6,
    6,
    6,
    6,
    5,
    4,
    4,
    4,
    4,
    2,
    1,
    0,
    0,
    0,
    0,
    0,
    0,
)
NEXT_UNPROCESSED_FAMILY_UPPER_BOUND = 313_739_208
PROFILE_GRAPH_TRIANGLE_UPPER_BOUNDS: tuple[tuple[DegreeProfile, int], ...] = (
    (TOP_PROFILES[0], 275),
    (TOP_PROFILES[1], 261),
    (TOP_PROFILES[2], 275),
    (TOP_PROFILES[3], 276),
)


@dataclass(frozen=True, slots=True)
class InactiveS4Census:
    """Exact minimum S4 contribution from the seven zero-triple tickets."""

    labeled_missing_graphs_examined: int
    minimum_s4: int
    minimizing_missing_edge_count: int
    minimizing_missing_degree_sequence: tuple[int, ...]
    labeled_minimizer_count: int
    representative_missing_edges: tuple[Pair, ...]


@dataclass(frozen=True, slots=True)
class ProfileEnvelope:
    """Certified S3-S4 envelope for one fixed realizable degree profile."""

    degree_profile: DegreeProfile
    wedge_count: int
    open_wedge_lower_bound: int
    graph_triangle_upper_bound: int
    noncore_graph_triangle_upper_bound: int
    loose_three_cycle_upper_bound: int
    shared_vertex_support_pair_count: int
    pasch_like_four_support_upper_bound: int
    s3_upper_bound: int
    inactive_s4_lower_bound: int
    fourth_order_credit: int
    family_upper_bound: int


@dataclass(frozen=True, slots=True)
class DegreeClassWedgeCertificate:
    """Certified open-wedge lower bound from a relaxed complement degree model."""

    degree_profile: DegreeProfile
    complement_degree_classes: tuple[tuple[int, int], ...]
    solver_status: str
    solver_wall_limit_seconds: float
    solver_wall_time_seconds: float
    weighted_open_wedge_lower_bound: int
    open_wedge_lower_bound: int
    graph_triangle_upper_bound: int
    class_edge_counts: tuple[tuple[Pair, int], ...]


@dataclass(frozen=True, slots=True)
class ProfileSolveResult:
    """One CP-SAT maximum and its independently bounded graph-triangle count."""

    degree_profile: DegreeProfile
    solver_status: str
    solver_wall_limit_seconds: float
    solver_wall_time_seconds: float
    incumbent_graph_triangle_count: int
    solver_certified_triangle_bound: int
    s3_upper_bound: int
    witness_motif_signature: K20SupportMotifSignature


def _top_witnesses() -> tuple[K20TopProfileResolution, ...]:
    """Select only the four previously proven feasible R6 witnesses."""

    raw_resolutions = getattr(r6, "_RESOLUTIONS", None)
    if not isinstance(raw_resolutions, tuple):
        raise AssertionError("the committed R6 profile witnesses are unavailable")
    resolutions = cast(tuple[K20TopProfileResolution, ...], raw_resolutions)
    by_profile = {
        item.degree_sequence: item
        for item in resolutions
        if item.degree_sequence in TOP_PROFILES and item.realizable
    }
    if set(by_profile) != set(TOP_PROFILES):
        raise AssertionError("the four proven-feasible top profile identities changed")
    return tuple(by_profile[profile] for profile in TOP_PROFILES)


def _cp_model_api() -> Any:
    from ortools.sat.python import cp_model

    return cast(Any, cp_model)


def _overlap_edges(
    triple_supports: Sequence[Triple], double_supports: Sequence[Pair]
) -> frozenset[Pair]:
    edges: set[Pair] = set()
    for triple in triple_supports:
        for first, second in combinations(triple, 2):
            edges.add((min(first, second), max(first, second)))
    for first, second in double_supports:
        edges.add((min(first, second), max(first, second)))
    return frozenset(edges)


def overlap_graph_triangle_count(edges: frozenset[Pair]) -> int:
    """Count triangles in the full 20-ticket overlap graph."""

    return sum(
        all(tuple(sorted(pair)) in edges for pair in combinations(triangle, 2))
        for triangle in combinations(range(K20_TICKET_COUNT), 3)
    )


def profile_witness_motifs(
    profile: DegreeProfile,
) -> tuple[int, K20SupportMotifSignature]:
    """Return one R6 witness's full-graph triangles and exact core motifs."""

    try:
        witness = next(item for item in _top_witnesses() if item.degree_sequence == profile)
    except StopIteration as exc:
        raise ValueError("profile is outside the four authorized top profiles") from exc
    if not witness.realizable:
        raise AssertionError("a selected top witness must be realizable")
    signature = validate_k20_support_realization(
        witness.triple_supports,
        witness.double_supports,
        profile,
    )
    return (
        overlap_graph_triangle_count(
            _overlap_edges(witness.triple_supports, witness.double_supports)
        ),
        signature,
    )


def _inactive_s4_for_missing_edges(missing_edges: frozenset[Pair]) -> int:
    inactive_count = 7
    total = 0
    for quartet in combinations(range(inactive_count), 4):
        vertices = frozenset(quartet)
        missing = sum(
            first in vertices and second in vertices
            for first, second in missing_edges
        )
        overlap_edges = 6 - missing
        if overlap_edges == 6:
            total += 679
        elif overlap_edges == 5:
            total += 112
    return total


@cache
def inactive_ticket_s4_census() -> InactiveS4Census:
    """Exhaust all seven-ticket missing graphs with at most six edges.

    The seven tickets with triple degree zero have six double-support
    incidences each.  The active tickets have only twelve residual double
    incidences in total, so at most twelve double supports cross between the
    two groups.  Thus the inactive induced double graph has at least 15 of
    its 21 possible edges, leaving at most six missing edges.  The local
    four-ticket intersection table assigns 679 outcomes when all six pairs
    overlap and 112 when five pairs overlap.
    """

    possible_edges = tuple(combinations(range(7), 2))
    labeled_graph_count = sum(comb(len(possible_edges), size) for size in range(7))
    best_score: int | None = None
    best_graphs = 0
    best_missing_edges: tuple[Pair, ...] = ()
    best_degree_sequence: tuple[int, ...] = ()
    best_edge_count = 0

    for missing_count in range(7):
        for missing_tuple in combinations(possible_edges, missing_count):
            missing = frozenset(missing_tuple)
            score = _inactive_s4_for_missing_edges(missing)
            degrees = tuple(
                sorted(
                    (sum(vertex in edge for edge in missing) for vertex in range(7)),
                    reverse=True,
                )
            )
            if best_score is None or score < best_score:
                best_score = score
                best_graphs = 1
                best_missing_edges = missing_tuple
                best_degree_sequence = degrees
                best_edge_count = missing_count
            elif score == best_score:
                best_graphs += 1

    if best_score is None:
        raise AssertionError("the finite inactive-ticket census is empty")
    return InactiveS4Census(
        labeled_missing_graphs_examined=labeled_graph_count,
        minimum_s4=best_score,
        minimizing_missing_edge_count=best_edge_count,
        minimizing_missing_degree_sequence=best_degree_sequence,
        labeled_minimizer_count=best_graphs,
        representative_missing_edges=best_missing_edges,
    )


def degree_class_open_wedge_certificate(
    profile: DegreeProfile,
    *,
    wall_limit_seconds: float = DEGREE_CLASS_RELAXATION_WALL_LIMIT_SECONDS,
) -> DegreeClassWedgeCertificate:
    """Certify a profile-specific triangle cap from complement degree classes.

    If ``q_i = 13 - d_i`` is the degree of ticket ``i`` in the complement of
    the overlap graph, each complement edge ``ij`` forces at least
    ``max(0, 20 - q_i - q_j)`` open wedges.  The integer model minimizes this
    weight over class-to-class edge counts subject only to necessary
    degree-sum and simple-graph capacity constraints.  Relaxing vertex-level
    structure can only lower the forced open-wedge count, so its optimum is a
    valid lower bound for every realizable overlap graph.
    """

    if profile not in TOP_PROFILES:
        raise ValueError("profile is outside the four authorized top profiles")
    if wall_limit_seconds <= 0:
        raise ValueError("wall_limit_seconds must be positive")

    complement_degrees = tuple(13 - degree for degree in profile)
    degree_classes = tuple(sorted(Counter(complement_degrees).items()))
    cp_model_api = _cp_model_api()
    model: Any = cp_model_api.CpModel()
    edge_count_vars: dict[tuple[int, int], Any] = {}
    edge_costs: dict[tuple[int, int], int] = {}
    for first_class, (first_degree, first_size) in enumerate(degree_classes):
        for second_class in range(first_class, len(degree_classes)):
            second_degree, second_size = degree_classes[second_class]
            capacity = (
                comb(first_size, 2)
                if first_class == second_class
                else first_size * second_size
            )
            key = (first_class, second_class)
            edge_count_vars[key] = model.NewIntVar(0, capacity, f"class_edges_{key}")
            edge_costs[key] = max(0, 20 - first_degree - second_degree)

    for class_index, (degree, class_size) in enumerate(degree_classes):
        incident_terms: list[Any] = []
        for other_class in range(len(degree_classes)):
            key = (
                (class_index, other_class)
                if class_index <= other_class
                else (other_class, class_index)
            )
            multiplier = 2 if class_index == other_class else 1
            incident_terms.append(multiplier * edge_count_vars[key])
        model.Add(sum(incident_terms) == degree * class_size)

    weighted_cost = sum(
        edge_costs[key] * variable for key, variable in edge_count_vars.items()
    )
    model.Minimize(weighted_cost)
    solver: Any = cp_model_api.CpSolver()
    solver.parameters.max_time_in_seconds = wall_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    solver.parameters.log_search_progress = False
    started = perf_counter()
    status_code = solver.Solve(model)
    elapsed = perf_counter() - started
    status = str(solver.StatusName(status_code))
    if status not in ("OPTIMAL", "FEASIBLE"):
        raise RuntimeError(f"degree-class CP-SAT failed: {status}")
    weighted_lower = (
        int(solver.Value(weighted_cost))
        if status == "OPTIMAL"
        else floor(solver.BestObjectiveBound())
    )
    open_wedge_lower = 3 * ceil(weighted_lower / 3)
    wedge_count = overlap_wedge_count(profile)
    triangle_upper = min(
        ANALYTIC_GRAPH_TRIANGLE_UPPER_BOUND,
        (wedge_count - open_wedge_lower) // 3,
    )
    class_edge_counts = tuple(
        (
            (degree_classes[first][0], degree_classes[second][0]),
            int(solver.Value(variable)),
        )
        for (first, second), variable in edge_count_vars.items()
    )
    return DegreeClassWedgeCertificate(
        degree_profile=profile,
        complement_degree_classes=degree_classes,
        solver_status=status,
        solver_wall_limit_seconds=wall_limit_seconds,
        solver_wall_time_seconds=elapsed,
        weighted_open_wedge_lower_bound=weighted_lower,
        open_wedge_lower_bound=open_wedge_lower,
        graph_triangle_upper_bound=triangle_upper,
        class_edge_counts=class_edge_counts,
    )


def profile_envelope(
    profile: DegreeProfile,
    *,
    graph_triangle_upper_bound: int | None = None,
) -> ProfileEnvelope:
    """Compute the certified third/fourth-order family bound for a profile."""

    if profile not in TOP_PROFILES:
        raise ValueError("profile is outside the four authorized top profiles")
    triangle_bound = (
        dict(PROFILE_GRAPH_TRIANGLE_UPPER_BOUNDS)[profile]
        if graph_triangle_upper_bound is None
        else graph_triangle_upper_bound
    )
    if not 22 <= triangle_bound <= ANALYTIC_GRAPH_TRIANGLE_UPPER_BOUND:
        raise ValueError("graph triangle bound must lie between the 22 core and 278")
    wedges = overlap_wedge_count(profile)
    open_wedge_lower = wedges - 3 * triangle_bound
    noncore_triangles = triangle_bound - K20_TRIPLE_SUPPORT_COUNT
    shared_support_pairs = sum(comb(degree, 2) for degree in profile)
    loose_cycle_bound = noncore_triangles
    pasch_bound = loose_cycle_bound // 4
    s3_bound = s3_sum_from_wedges_and_triangles(wedges, noncore_triangles)
    inactive_s4_bound = inactive_ticket_s4_census().minimum_s4
    fourth_order_credit = (4 * inactive_s4_bound) // 7
    family_bound = K20_S1 - K20_S2 + s3_bound - fourth_order_credit
    return ProfileEnvelope(
        degree_profile=profile,
        wedge_count=wedges,
        open_wedge_lower_bound=open_wedge_lower,
        graph_triangle_upper_bound=triangle_bound,
        noncore_graph_triangle_upper_bound=noncore_triangles,
        loose_three_cycle_upper_bound=loose_cycle_bound,
        shared_vertex_support_pair_count=shared_support_pairs,
        pasch_like_four_support_upper_bound=pasch_bound,
        s3_upper_bound=s3_bound,
        inactive_s4_lower_bound=inactive_s4_bound,
        fourth_order_credit=fourth_order_credit,
        family_upper_bound=family_bound,
    )


def _solve_profile_model(
    profile: DegreeProfile,
    *,
    wall_limit_seconds: float,
) -> tuple[
    Any,
    list[Any],
    int,
    float,
    dict[Triple, Any],
    dict[Pair, Any],
]:
    """Build and solve the compressed support-to-overlap triangle model."""

    if profile not in TOP_PROFILES:
        raise ValueError("profile is outside the four authorized top profiles")
    if wall_limit_seconds <= 0:
        raise ValueError("wall_limit_seconds must be positive")

    started = perf_counter()
    witness = next(item for item in _top_witnesses() if item.degree_sequence == profile)
    cp_model_api = _cp_model_api()
    model: Any = cp_model_api.CpModel()
    active_vertices = tuple(index for index, degree in enumerate(profile) if degree > 0)
    candidate_triples = tuple(combinations(active_vertices, 3))
    triple_vars = {
        triple: model.NewBoolVar(f"triple_{triple[0]}_{triple[1]}_{triple[2]}")
        for triple in candidate_triples
    }
    double_vars = {
        pair: model.NewBoolVar(f"double_{pair[0]}_{pair[1]}")
        for pair in combinations(range(K20_TICKET_COUNT), 2)
    }
    overlap_vars = {
        pair: model.NewBoolVar(f"overlap_{pair[0]}_{pair[1]}")
        for pair in combinations(range(K20_TICKET_COUNT), 2)
    }

    triples_by_vertex = {
        vertex: [variable for triple, variable in triple_vars.items() if vertex in triple]
        for vertex in range(K20_TICKET_COUNT)
    }
    triples_by_pair = {
        pair: [variable for triple, variable in triple_vars.items() if set(pair) <= set(triple)]
        for pair in double_vars
    }
    for vertex, degree in enumerate(profile):
        model.Add(sum(triples_by_vertex[vertex]) == degree)
        incident_double_vars = [
            variable
            for (first, second), variable in double_vars.items()
            if vertex in (first, second)
        ]
        model.Add(sum(incident_double_vars) == K20_TICKET_CAPACITY - degree)

    for pair, double_var in double_vars.items():
        pair_triples = triples_by_pair[pair]
        model.Add(sum(pair_triples) + double_var <= 1)
        model.Add(overlap_vars[pair] == sum(pair_triples) + double_var)

    triangle_vars: list[Any] = []
    for first, second, third in combinations(range(K20_TICKET_COUNT), 3):
        triangle = model.NewBoolVar(f"triangle_{first}_{second}_{third}")
        triangle_edges = (
            overlap_vars[(first, second)],
            overlap_vars[(first, third)],
            overlap_vars[(second, third)],
        )
        for edge_var in triangle_edges:
            model.Add(triangle <= edge_var)
        model.Add(triangle >= sum(triangle_edges) - 2)
        triangle_vars.append(triangle)

    model.Maximize(sum(triangle_vars))

    witness_triples = {tuple(sorted(triple)) for triple in witness.triple_supports}
    witness_doubles = {tuple(sorted(pair)) for pair in witness.double_supports}
    witness_graph_edges = _overlap_edges(witness.triple_supports, witness.double_supports)
    for triple, variable in triple_vars.items():
        model.AddHint(variable, int(triple in witness_triples))
    for pair, variable in double_vars.items():
        model.AddHint(variable, int(pair in witness_doubles))
    for pair, variable in overlap_vars.items():
        model.AddHint(variable, int(pair in witness_graph_edges))
    for triangle_index, triple in enumerate(combinations(range(K20_TICKET_COUNT), 3)):
        complete = all(
            tuple(sorted(pair)) in witness_graph_edges
            for pair in combinations(triple, 2)
        )
        model.AddHint(triangle_vars[triangle_index], int(complete))

    solver: Any = cp_model_api.CpSolver()
    solver.parameters.max_time_in_seconds = wall_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    solver.parameters.symmetry_level = 2
    solver.parameters.log_search_progress = False
    status = solver.Solve(model)
    elapsed = perf_counter() - started
    if status not in (cp_model_api.OPTIMAL, cp_model_api.FEASIBLE):
        raise RuntimeError(
            f"CP-SAT did not find a support realization: {solver.StatusName(status)}"
        )
    return solver, triangle_vars, status, elapsed, triple_vars, double_vars


def solve_profile_s3_maximum(
    profile: DegreeProfile,
    *,
    wall_limit_seconds: float = SOLVER_PROFILE_WALL_LIMIT_SECONDS,
) -> ProfileSolveResult:
    """Maximize S3's graph-triangle term with a bounded one-worker CP-SAT run."""

    solver, triangle_vars, status_code, elapsed, triple_vars, double_vars = _solve_profile_model(
        profile,
        wall_limit_seconds=wall_limit_seconds,
    )
    witness_triangles = sum(solver.Value(variable) for variable in triangle_vars)
    status = str(solver.StatusName(status_code))
    raw_bound = solver.BestObjectiveBound()
    solver_bound = min(ANALYTIC_GRAPH_TRIANGLE_UPPER_BOUND, ceil(raw_bound))
    if status == "OPTIMAL":
        solver_bound = witness_triangles
    s3_bound = s3_sum_from_wedges_and_triangles(
        overlap_wedge_count(profile),
        solver_bound - K20_TRIPLE_SUPPORT_COUNT,
    )
    support_triples = tuple(
        triple for triple, variable in triple_vars.items() if solver.Value(variable)
    )
    support_doubles = tuple(
        pair for pair, variable in double_vars.items() if solver.Value(variable)
    )
    witness_signature = validate_k20_support_realization(
        support_triples,
        support_doubles,
        profile,
    )
    graph_edges = _overlap_edges(support_triples, support_doubles)
    if overlap_graph_triangle_count(graph_edges) != witness_triangles:
        raise AssertionError(
            "the CP-SAT graph-triangle objective disagrees with its support witness"
        )
    return ProfileSolveResult(
        degree_profile=profile,
        solver_status=status,
        solver_wall_limit_seconds=wall_limit_seconds,
        solver_wall_time_seconds=elapsed,
        incumbent_graph_triangle_count=witness_triangles,
        solver_certified_triangle_bound=solver_bound,
        s3_upper_bound=s3_bound,
        witness_motif_signature=witness_signature,
    )


__all__ = [
    "ANALYTIC_GRAPH_TRIANGLE_UPPER_BOUND",
    "DEGREE_CLASS_RELAXATION_WALL_LIMIT_SECONDS",
    "EXACTLY_ANALYZED_PROFILE_COUNT",
    "NEXT_UNPROCESSED_FAMILY_UPPER_BOUND",
    "NEXT_UNPROCESSED_PROFILE",
    "PROFILE_GRAPH_TRIANGLE_UPPER_BOUNDS",
    "SOLVER_EXTERNAL_WALL_LIMIT_SECONDS",
    "SOLVER_PROFILE_WALL_LIMIT_SECONDS",
    "TOP_ENVELOPE_WEDGE_COUNT",
    "TOP_PROFILES",
    "TOP_PROFILE_COUNT",
    "DegreeClassWedgeCertificate",
    "InactiveS4Census",
    "ProfileEnvelope",
    "ProfileSolveResult",
    "degree_class_open_wedge_certificate",
    "inactive_ticket_s4_census",
    "overlap_graph_triangle_count",
    "profile_envelope",
    "profile_witness_motifs",
    "solve_profile_s3_maximum",
]
