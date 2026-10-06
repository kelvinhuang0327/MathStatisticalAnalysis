"""Class-wide dominance attempt and bounded ranked fallback for K20 S2 R13.

The R12 handoff leaves a four-profile suffix in the degree-square class 334.
This module bounds that suffix by a degree-class relaxation before it falls
back to exact ranked per-profile support and motif proofs.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from importlib import import_module
from math import ceil, comb, floor
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
    MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
    solver_runtime_preflight,
    validate_resume_cursor,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    PREVIOUS_RESULT_PATH as R11_RESULT_PATH,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    _iter_square_sum_profiles as iter_r12_square_sum_profiles,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    _LookupCounters as R12LookupCounters,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    _resolve_profile as resolve_r12_profile,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    compact_descent_result as _compact_profile_result,
)
from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_REUSED_S4_LOWER_BOUND,
)
from .b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    CoarseProfileEnvelope,
    coarse_profile_envelope,
    profile_shadow_obstruction,
)
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
    NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
    NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
    SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_INCUMBENT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]

TASK_ID = "B649_K20_MIN_S2_CLASS_DOMINANCE_OR_DESCENT_R13"
TASK_BRANCH = "codex/b649-k20-min-s2-class-dominance-or-descent-r13"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_MIN_S2_CLASS_DOMINANCE_OR_DESCENT_R13"
)
BASE_HEAD = "0cc283e8bf3fb60c5de0a205a6389b8afeb77e5e"
BASE_TREE = "8f366460b3cc773b0f1bf7f2b6de7bcc1da091cb"
START_BOUND = 313_698_664
INCUMBENT = K20_INCUMBENT
START_PROFILE: DegreeProfile = (
    6,
    6,
    6,
    6,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    3,
    2,
    1,
    1,
    0,
    0,
    0,
    0,
    0,
)
PROFILE_CAP = 96
CERTIFIED_DROP_TARGET = 50_000
STAGE_A_WALL_BUDGET_SECONDS = 1_200.0
TOTAL_WALL_BUDGET_SECONDS = 3_600.0
CLASS_RELAXATION_WALL_LIMIT_SECONDS = 10.0
RESULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-class-dominance-or-descent-r13-result.json"
)
R12_RESULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json"
)


class FrontierLookupLimit(RuntimeError):
    """The bounded ranked-frontier lookup could not certify a successor."""


@dataclass(frozen=True, slots=True)
class PriorResolvedState:
    """Validated R11/R12 profile identities and their best certified bound."""

    profiles: frozenset[DegreeProfile]
    profile_count: int
    maximum_profile_bound: int


@dataclass(frozen=True, slots=True)
class RankedFrontier:
    """A bounded exact prefix beginning at the packet-pinned R13 cursor."""

    profiles: tuple[DegreeProfile, ...]
    envelopes: tuple[CoarseProfileEnvelope, ...]
    complete_profiles_examined: int
    square_sum_classes_examined: int
    lookup_complete: bool


def _profile_from_raw(raw: object, *, name: str) -> DegreeProfile:
    if not isinstance(raw, list):
        raise AssertionError(f"{name} must be an array")
    values = cast(list[object], raw)
    if len(values) != K20_TICKET_COUNT or any(type(value) is not int for value in values):
        raise AssertionError(f"{name} must contain twenty integer degrees")
    profile = tuple(cast(list[int], values))
    if tuple(sorted(profile, reverse=True)) != profile:
        raise AssertionError(f"{name} must be nonincreasing")
    if any(not 0 <= degree <= K20_TICKET_CAPACITY for degree in profile):
        raise AssertionError(f"{name} contains a degree outside 0..6")
    if sum(profile) != K20_TRIPLE_INCIDENCE_COUNT:
        raise AssertionError(f"{name} must sum to 66")
    return profile


def _read_json(path: Path) -> dict[str, object]:
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise TypeError(f"result at {path} must be a JSON object")
    return cast(dict[str, object], decoded)


def _require_int(value: object, name: str) -> int:
    if type(value) is not int:
        raise AssertionError(f"{name} must be an integer")
    return value


def _require_float(value: object, name: str) -> float:
    if not isinstance(value, (int, float)):
        raise AssertionError(f"{name} must be numeric")
    return float(value)


def _profile_rows(
    result: dict[str, object], *, expected_count: int
) -> tuple[tuple[DegreeProfile, ...], tuple[int, ...]]:
    raw_rows = result.get("PROFILE_BOUNDS")
    if not isinstance(raw_rows, list):
        raise AssertionError("a prior result lacks its profile ledger")
    rows = cast(list[object], raw_rows)
    if len(rows) != expected_count:
        raise AssertionError("a prior profile ledger has an unexpected length")
    profiles: list[DegreeProfile] = []
    bounds: list[int] = []
    for row_raw in rows:
        if not isinstance(row_raw, dict):
            raise AssertionError("a prior profile ledger row is malformed")
        row = cast(dict[str, object], row_raw)
        profiles.append(_profile_from_raw(row.get("PROFILE"), name="prior profile"))
        bound = row.get("FAMILY_UPPER_BOUND")
        if type(bound) is int:
            bounds.append(bound)
    if len(set(profiles)) != expected_count:
        raise AssertionError("a prior profile ledger contains duplicate identities")
    return tuple(profiles), tuple(bounds)


def validate_prior_resolved_state(
    r11_result: dict[str, object] | None = None,
    r12_result: dict[str, object] | None = None,
) -> PriorResolvedState:
    """Validate the 72-profile R11/R12 handoff before any candidate is ranked."""

    r11 = r11_result if r11_result is not None else _read_json(R11_RESULT_PATH)
    r12 = r12_result if r12_result is not None else _read_json(R12_RESULT_PATH)
    r11_profiles = validate_resume_cursor(r11)
    if r12.get("TASK_ID") != "B649_K20_MIN_S2_CONTINUED_MULTI_PLATEAU_DESCENT_R12":
        raise AssertionError("the prior result is not the required R12 task")
    if r12.get("TASK_STATUS") != "SUCCESS_C_PROFILE_CAP":
        raise AssertionError("R12 did not stop at its declared profile cap")
    if r12.get("PROFILE_COUNT_PROCESSED") != 48 or r12.get("ACTUAL_PROFILE_COUNT") != 48:
        raise AssertionError("R12 did not resolve exactly 48 additional profiles")
    if r12.get("PRIOR_RESOLVED_PROFILE_COUNT") != 24:
        raise AssertionError("R12 did not continue from the 24-profile R11 ledger")
    if r12.get("TOTAL_RESOLVED_PROFILE_COUNT") != 72:
        raise AssertionError("R12 did not record exactly 72 resolved profiles")
    if r12.get("PRIOR_PROFILE_RERUN_COUNT") != 0:
        raise AssertionError("R12 recorded a prior profile rerun")
    if r12.get("STOP_REASON") != "PROFILE_CAP_REACHED":
        raise AssertionError("R12 did not stop at the requested profile cursor")
    if r12.get("END_BOUND") != START_BOUND or r12.get("FAMILY_UPPER_BOUND") != START_BOUND:
        raise AssertionError("R12 end bound does not match the R13 start bound")
    if r12.get("NEXT_ACTIVE_BOUND") != START_BOUND:
        raise AssertionError("R12 next bound does not match the R13 cursor")
    next_profile = _profile_from_raw(r12.get("NEXT_ACTIVE_PROFILE"), name="R12 next profile")
    if next_profile != START_PROFILE:
        raise AssertionError("R12 next profile does not match the packet-pinned R13 cursor")
    if sum(degree**2 for degree in START_PROFILE) != 334:
        raise AssertionError("the packet-pinned cursor left square-sum class 334")
    if coarse_profile_envelope(START_PROFILE).family_upper_bound != START_BOUND:
        raise AssertionError("the packet-pinned cursor no longer has its recorded bound")

    r12_profiles, r12_bounds = _profile_rows(r12, expected_count=48)
    if set(r11_profiles).intersection(r12_profiles):
        raise AssertionError("R12 reran one or more R11 profiles")
    all_profiles = frozenset((*r11_profiles, *r12_profiles))
    if len(all_profiles) != 72:
        raise AssertionError("the R11/R12 resolved profile identities are not unique")
    if START_PROFILE in all_profiles:
        raise AssertionError("the R13 cursor was already resolved")
    _, r11_bounds = _profile_rows(r11, expected_count=24)
    all_bounds = (*r11_bounds, *r12_bounds)
    if not all_bounds:
        raise AssertionError("the prior profile ledgers lack certified numeric bounds")
    maximum_bound = max(all_bounds)
    if maximum_bound != 313_689_592:
        raise AssertionError("the prior ranked frontier's maximum certified bound changed")
    return PriorResolvedState(all_profiles, len(all_profiles), maximum_bound)


def assert_no_prior_profile_rerun(
    prior_profiles: Collection[DegreeProfile], candidate_profiles: Collection[DegreeProfile]
) -> None:
    """Reject any attempted support/motif work on an R11 or R12 profile."""

    overlap = set(prior_profiles).intersection(candidate_profiles)
    if overlap:
        raise AssertionError(f"R13 attempted to resolve a prior profile again: {min(overlap)}")


def _minimum_square_sum(total: int, slots: int) -> int | None:
    if slots == 0:
        return 0 if total == 0 else None
    quotient, remainder = divmod(total, slots)
    return (slots - remainder) * quotient**2 + remainder * (quotient + 1) ** 2


def _rank_key(envelope: CoarseProfileEnvelope) -> tuple[object, ...]:
    """Match the established coarse-bound, S3, wedge, and profile order."""

    return (
        envelope.family_upper_bound,
        envelope.s3_upper_bound,
        envelope.wedge_count,
        envelope.degree_profile,
    )


def lookup_ranked_frontier(
    *,
    profile_limit: int,
    deadline: float,
    prior_profiles: Collection[DegreeProfile],
) -> RankedFrontier:
    """Build only the requested eligible prefix from the exact R13 cursor."""

    if profile_limit < 1:
        raise ValueError("profile_limit must be positive")
    if START_PROFILE in prior_profiles:
        raise AssertionError("the packet cursor is in the prior resolved profile set")
    profiles: list[DegreeProfile] = []
    envelopes: list[CoarseProfileEnvelope] = []
    complete_profiles_examined = 0
    square_sum_classes_examined = 0
    previous_key: tuple[object, ...] | None = None
    square_sum = sum(degree**2 for degree in START_PROFILE)
    upper_profile: DegreeProfile | None = START_PROFILE
    minimum_square_sum = _minimum_square_sum(K20_TRIPLE_INCIDENCE_COUNT, K20_TICKET_COUNT)
    if minimum_square_sum is None:
        raise AssertionError("the minimum degree square sum could not be calculated")

    while square_sum >= minimum_square_sum:
        if monotonic() >= deadline:
            raise FrontierLookupLimit("proof wall budget expired during ranked lookup")
        square_sum_classes_examined += 1
        counters = R12LookupCounters()
        for profile in iter_r12_square_sum_profiles(
            square_sum,
            upper_profile=upper_profile,
            counters=counters,
            deadline=deadline,
        ):
            assert_no_prior_profile_rerun(prior_profiles, (profile,))
            envelope = coarse_profile_envelope(profile)
            key = _rank_key(envelope)
            if previous_key is not None and previous_key < key:
                raise AssertionError("the ranked frontier is not monotonically descending")
            previous_key = key
            profiles.append(profile)
            envelopes.append(envelope)
            if len(profiles) >= profile_limit:
                complete_profiles_examined += counters.complete_profiles_examined
                return RankedFrontier(
                    tuple(profiles),
                    tuple(envelopes),
                    complete_profiles_examined,
                    square_sum_classes_examined,
                    False,
                )
        complete_profiles_examined += counters.complete_profiles_examined
        if complete_profiles_examined > MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES:
            raise FrontierLookupLimit("rank lookup exceeded its bounded complete-profile prefix")
        upper_profile = None
        square_sum -= 2

    return RankedFrontier(
        tuple(profiles),
        tuple(envelopes),
        complete_profiles_examined,
        square_sum_classes_examined,
        True,
    )


def degree_class_open_wedge_relaxation(
    graph_degrees: Sequence[int], *, wall_limit_seconds: float
) -> dict[str, object]:
    """Lower-bound open wedges using only complement degree-class capacities.

    For a complement edge ij, its endpoints have at least
    max(0, n-c_i-c_j) common neighbors in the graph. Summing those costs over
    complement edges lower-bounds all open wedges. Aggregating edge variables
    by degree class relaxes simple-graph structure, so its minimum remains a
    certified lower bound for every graph with these degrees.
    """

    cp_model: Any = import_module("ortools.sat.python.cp_model")

    degrees = tuple(graph_degrees)
    vertex_count = len(degrees)
    if vertex_count < 1 or any(type(degree) is not int for degree in degrees):
        raise ValueError("graph degrees must be a nonempty integer sequence")
    if any(not 0 <= degree < vertex_count for degree in degrees):
        raise ValueError("graph degrees must be valid simple-graph degrees")
    if sum(degrees) % 2:
        raise ValueError("graph degree sum must be even")
    if wall_limit_seconds <= 0:
        return {
            "SOLVER_STATUS": "NOT_RUN_WALL_BUDGET",
            "SOLVER_WALL_TIME_SECONDS": 0.0,
            "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": 0,
        }

    complement_degrees = tuple(vertex_count - 1 - degree for degree in degrees)
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
            edge_vars[key] = model.NewIntVar(0, capacity, f"complement_edges_{key}")
            edge_costs[key] = max(0, vertex_count - first_degree - second_degree)

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
    status = solver.Solve(model)
    status_name = str(solver.StatusName(status))
    if status == cp_model.INFEASIBLE:
        lower_bound = None
    elif status == cp_model.OPTIMAL:
        lower_bound = int(solver.Value(weighted_open_wedges))
    elif status == cp_model.FEASIBLE:
        lower_bound = max(0, floor(solver.BestObjectiveBound()))
    else:
        lower_bound = 0
    return {
        "SOLVER_STATUS": status_name,
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
        "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": lower_bound,
        "DEGREE_CLASSES": [
            {"COMPLEMENT_DEGREE": degree, "VERTEX_COUNT": size} for degree, size in degree_classes
        ],
    }


def graph_triangle_upper_bound_from_open_wedges(
    graph_degrees: Sequence[int], weighted_open_wedge_lower_bound: int
) -> dict[str, int]:
    """Turn a certified open-wedge floor into an integer triangle ceiling."""

    degrees = tuple(graph_degrees)
    wedge_count = sum(comb(degree, 2) for degree in degrees)
    if type(weighted_open_wedge_lower_bound) is not int or weighted_open_wedge_lower_bound < 0:
        raise ValueError("the weighted open-wedge lower bound must be nonnegative")
    residue = wedge_count % 3
    open_wedge_lower_bound = residue + 3 * max(
        0, ceil((weighted_open_wedge_lower_bound - residue) / 3)
    )
    return {
        "WEDGE_COUNT": wedge_count,
        "OPEN_WEDGE_LOWER_BOUND": open_wedge_lower_bound,
        "GRAPH_TRIANGLE_UPPER_BOUND": (wedge_count - open_wedge_lower_bound) // 3,
    }


def profile_family_envelope_from_triangle_bound(
    profile: DegreeProfile, graph_triangle_upper_bound: int
) -> dict[str, int]:
    """Apply the shared S3 identity and certified S4 floor to one profile."""

    if graph_triangle_upper_bound < K20_TRIPLE_SUPPORT_COUNT:
        raise ValueError("the graph triangle ceiling is below the 22 core triangles")
    wedge_count = overlap_wedge_count(profile)
    noncore_triangle_bound = graph_triangle_upper_bound - K20_TRIPLE_SUPPORT_COUNT
    s3_upper_bound = s3_sum_from_wedges_and_triangles(wedge_count, noncore_triangle_bound)
    s4_lower_bound = max(
        K20_REUSED_S4_LOWER_BOUND,
        SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND if profile.count(0) == 7 else 0,
    )
    fourth_order_credit = (4 * s4_lower_bound) // 7
    family_upper_bound = K20_S1 - K20_S2 + s3_upper_bound - fourth_order_credit
    coarse_bound = coarse_profile_envelope(profile).family_upper_bound
    if family_upper_bound > coarse_bound:
        raise AssertionError("the class motif envelope exceeds the coarse profile envelope")
    return {
        "WEDGE_COUNT": wedge_count,
        "GRAPH_TRIANGLE_UPPER_BOUND": graph_triangle_upper_bound,
        "NONCORE_TRIANGLE_UPPER_BOUND": noncore_triangle_bound,
        "S3_UPPER_BOUND": s3_upper_bound,
        "S4_LOWER_BOUND": s4_lower_bound,
        "FOURTH_ORDER_CREDIT": fourth_order_credit,
        "FAMILY_UPPER_BOUND": family_upper_bound,
        "COARSE_FAMILY_UPPER_BOUND": coarse_bound,
    }


def _profile_histogram(profile: DegreeProfile) -> tuple[int, ...]:
    counts = Counter(profile)
    return tuple(counts[degree] for degree in range(K20_TICKET_CAPACITY + 1))


def _degree_sequence_from_histogram(histogram: Sequence[int]) -> DegreeProfile:
    if len(histogram) != K20_TICKET_CAPACITY + 1:
        raise ValueError("a K20 degree histogram must have seven bins")
    if any(type(count) is not int or count < 0 for count in histogram):
        raise ValueError("degree histogram counts must be nonnegative integers")
    degrees = tuple(
        degree for degree, count in reversed(tuple(enumerate(histogram))) for _ in range(count)
    )
    if len(degrees) != K20_TICKET_COUNT:
        raise ValueError("degree histogram must contain twenty tickets")
    return degrees


def certify_square_sum_class_suffix(
    *,
    square_sum: int,
    upper_profile: DegreeProfile,
    prior_profiles: Collection[DegreeProfile],
    deadline: float,
) -> dict[str, object]:
    """Certify every eligible profile in one complete ranked class suffix."""

    if sum(degree**2 for degree in upper_profile) != square_sum:
        raise ValueError("upper profile does not belong to the requested square-sum class")
    counters = R12LookupCounters()
    profiles = tuple(
        iter_r12_square_sum_profiles(
            square_sum,
            upper_profile=upper_profile,
            counters=counters,
            deadline=deadline,
        )
    )
    if not profiles or profiles[0] != upper_profile:
        raise AssertionError("the active profile is not the first eligible suffix member")
    assert_no_prior_profile_rerun(prior_profiles, profiles)
    profiles = tuple(profile for profile in profiles if profile_shadow_obstruction(profile) is None)
    if not profiles or profiles[0] != upper_profile:
        raise AssertionError("shadow-graph filtering removed the packet-pinned active profile")
    if any(sum(profile) != K20_TRIPLE_INCIDENCE_COUNT for profile in profiles):
        raise AssertionError("a class profile has the wrong triple-incidence sum")
    if any(sum(degree**2 for degree in profile) != square_sum for profile in profiles):
        raise AssertionError("a class profile has the wrong square sum")
    wedge_counts = {overlap_wedge_count(profile) for profile in profiles}
    if len(wedge_counts) != 1:
        raise AssertionError("a square-sum class does not have a fixed wedge total")
    wedge_count = next(iter(wedge_counts))
    histograms = tuple(sorted({_profile_histogram(profile) for profile in profiles}))
    histogram_bounds: list[dict[str, object]] = []
    class_upper_bound: int | None = None
    class_triangle_upper_bound: int | None = None
    total_solver_wall = 0.0
    for histogram in histograms:
        if monotonic() >= deadline:
            raise FrontierLookupLimit("proof wall budget expired during class relaxation")
        profile = _degree_sequence_from_histogram(histogram)
        if sum(profile) != K20_TRIPLE_INCIDENCE_COUNT or sum(d**2 for d in profile) != square_sum:
            raise AssertionError("a degree histogram left the certified square-sum class")
        graph_degrees = tuple(K20_TICKET_CAPACITY + degree for degree in profile)
        remaining = deadline - monotonic()
        wall_limit = min(CLASS_RELAXATION_WALL_LIMIT_SECONDS, max(0.001, remaining))
        relaxation = degree_class_open_wedge_relaxation(
            graph_degrees, wall_limit_seconds=wall_limit
        )
        total_solver_wall += _require_float(
            relaxation["SOLVER_WALL_TIME_SECONDS"], "solver wall time"
        )
        if relaxation["SOLVER_STATUS"] == "INFEASIBLE":
            histogram_row: dict[str, object] = {
                "DEGREE_COUNTS_0_TO_6": list(histogram),
                "PROFILE": list(profile),
                "RELAXATION_STATUS": "INFEASIBLE_GRAPH_DEGREE_CLASS",
                "FAMILY_UPPER_BOUND": None,
                "SOLVER": relaxation,
            }
            histogram_bounds.append(histogram_row)
            continue
        lower_bound = relaxation["WEIGHTED_OPEN_WEDGE_LOWER_BOUND"]
        if type(lower_bound) is not int:
            raise AssertionError("the degree-class relaxation omitted its certified lower bound")
        triangle_envelope = graph_triangle_upper_bound_from_open_wedges(graph_degrees, lower_bound)
        triangle_bound = triangle_envelope["GRAPH_TRIANGLE_UPPER_BOUND"]
        if triangle_bound < K20_TRIPLE_SUPPORT_COUNT:
            histogram_row = {
                "DEGREE_COUNTS_0_TO_6": list(histogram),
                "PROFILE": list(profile),
                "RELAXATION_STATUS": "BELOW_REQUIRED_CORE_TRIANGLE_COUNT",
                "FAMILY_UPPER_BOUND": None,
                "SOLVER": relaxation,
                "TRIANGLE_ENVELOPE": triangle_envelope,
            }
            histogram_bounds.append(histogram_row)
            continue
        profile_envelope = profile_family_envelope_from_triangle_bound(profile, triangle_bound)
        family_bound = profile_envelope["FAMILY_UPPER_BOUND"]
        class_upper_bound = (
            family_bound if class_upper_bound is None else max(class_upper_bound, family_bound)
        )
        class_triangle_upper_bound = (
            triangle_bound
            if class_triangle_upper_bound is None
            else max(class_triangle_upper_bound, triangle_bound)
        )
        histogram_row = {
            "DEGREE_COUNTS_0_TO_6": list(histogram),
            "PROFILE": list(profile),
            "RELAXATION_STATUS": relaxation["SOLVER_STATUS"],
            "FAMILY_UPPER_BOUND": family_bound,
            "SOLVER": relaxation,
            "TRIANGLE_ENVELOPE": triangle_envelope,
            "PROFILE_ENVELOPE": profile_envelope,
        }
        histogram_bounds.append(histogram_row)
    if class_upper_bound is None:
        class_upper_bound = 0
    coarse_bound = coarse_profile_envelope(upper_profile).family_upper_bound
    if class_upper_bound > coarse_bound:
        raise AssertionError("the class envelope exceeds the ranked coarse class bound")
    return {
        "SQUARE_SUM": square_sum,
        "UPPER_PROFILE": list(upper_profile),
        "REMAINING_ELIGIBLE_PROFILE_COUNT": len(profiles),
        "PROFILE_IDENTITIES": [list(profile) for profile in profiles],
        "COMPLETE_PROFILES_EXAMINED": counters.complete_profiles_examined,
        "PAIR_CAPACITY_FILTER": "APPLIED",
        "RESIDUAL_DOUBLE_SUPPORT_GRAPHICALITY_FILTER": "APPLIED",
        "SHADOW_GRAPHICALITY_FILTER": "APPLIED",
        "WEDGE_COUNT": wedge_count,
        "DEGREE_HISTOGRAM_COUNT": len(histograms),
        "HISTOGRAM_ENVELOPES": histogram_bounds,
        "GRAPH_TRIANGLE_UPPER_BOUND": class_triangle_upper_bound,
        "CLASS_FAMILY_UPPER_BOUND": class_upper_bound,
        "RANKED_COARSE_CLASS_BOUND": coarse_bound,
        "CLASS_LOCAL_DROP": coarse_bound - class_upper_bound,
        "RELAXATION_SOLVER_WALL_TIME_SECONDS": total_solver_wall,
        "COMPLETE_SUFFIX_ENUMERATION": True,
    }


def _first_eligible_profile_in_class(
    square_sum: int,
    *,
    prior_profiles: Collection[DegreeProfile],
    deadline: float,
) -> tuple[DegreeProfile | None, CoarseProfileEnvelope | None, int]:
    counters = R12LookupCounters()
    iterator = iter_r12_square_sum_profiles(
        square_sum,
        upper_profile=None,
        counters=counters,
        deadline=deadline,
    )
    profile = next(iterator, None)
    if profile is None:
        return None, None, counters.complete_profiles_examined
    assert_no_prior_profile_rerun(prior_profiles, (profile,))
    return profile, coarse_profile_envelope(profile), counters.complete_profiles_examined


def _ranked_fallback(
    *,
    prior_state: PriorResolvedState,
    started: float,
    deadline: float,
    profile_cap: int,
) -> dict[str, object]:
    frontier = lookup_ranked_frontier(
        profile_limit=profile_cap + 1,
        deadline=deadline,
        prior_profiles=prior_state.profiles,
    )
    if not frontier.profiles or frontier.profiles[0] != START_PROFILE:
        raise AssertionError("fallback no longer starts at the exact R12 next profile")
    profile_bounds: list[dict[str, object]] = []
    resolved_bounds: list[int] = []
    previous_profile_bound = prior_state.maximum_profile_bound
    stop_reason = "PROFILE_CAP_REACHED"
    unresolved = False
    for rank_index, profile in enumerate(frontier.profiles[:profile_cap]):
        if monotonic() >= deadline:
            stop_reason = "PROOF_WALL_BUDGET_REACHED"
            break
        assert_no_prior_profile_rerun(prior_state.profiles, (profile,))
        resolution: dict[str, object]
        try:
            resolution = resolve_r12_profile(profile, remaining_wall=deadline - monotonic())
        except TimeoutError:
            resolution = {
                "PROFILE": list(profile),
                "REALIZABILITY": "UNRESOLVED",
                "SUPPORT_SOLVER_STATUS": "EXTERNAL_HARD_TIMEOUT",
                "COARSE_FAMILY_UPPER_BOUND": frontier.envelopes[rank_index].family_upper_bound,
                "FAMILY_UPPER_BOUND": None,
            }
        resolution["RANK_INDEX"] = rank_index
        resolution["RANKED_COARSE_BOUND"] = frontier.envelopes[rank_index].family_upper_bound
        profile_bounds.append(resolution)
        if resolution.get("REALIZABILITY") == "UNRESOLVED":
            unresolved = True
            stop_reason = "SOLVER_UNRESOLVED"
            break
        if resolution.get("REALIZABILITY") == "REALIZABLE":
            bound = resolution.get("FAMILY_UPPER_BOUND")
            if type(bound) is not int:
                raise AssertionError("a realizable fallback profile lacks its family bound")
            resolved_bounds.append(bound)
        elif resolution.get("REALIZABILITY") != "UNREALIZABLE":
            raise AssertionError("fallback returned an unknown realizability state")

        next_index = rank_index + 1
        next_bound = (
            frontier.envelopes[next_index].family_upper_bound
            if next_index < len(frontier.envelopes)
            else 0
        )
        family_bound = max(previous_profile_bound, max(resolved_bounds, default=0), next_bound)
        if family_bound <= INCUMBENT:
            stop_reason = "FAMILY_CLOSED"
            break
        if START_BOUND - family_bound >= CERTIFIED_DROP_TARGET:
            stop_reason = "CERTIFIED_DROP_TARGET_REACHED"
            break
        if len(profile_bounds) >= profile_cap:
            stop_reason = "PROFILE_CAP_REACHED"
            break
    else:
        family_bound = max(
            previous_profile_bound,
            max(resolved_bounds, default=0),
            frontier.envelopes[len(profile_bounds)].family_upper_bound
            if len(profile_bounds) < len(frontier.envelopes)
            else 0,
        )

    next_index = len(profile_bounds) - 1 if unresolved else len(profile_bounds)
    next_profile = frontier.profiles[next_index] if next_index < len(frontier.profiles) else None
    next_envelope = frontier.envelopes[next_index] if next_index < len(frontier.envelopes) else None
    if next_envelope is None:
        family_bound = max(previous_profile_bound, max(resolved_bounds, default=0))
    else:
        family_bound = max(
            previous_profile_bound,
            max(resolved_bounds, default=0),
            next_envelope.family_upper_bound,
        )
    cumulative_drop = START_BOUND - family_bound
    if family_bound <= INCUMBENT:
        task_status = "SUCCESS_A_FAMILY_CLOSED"
        family_status = "CLOSED"
    elif cumulative_drop >= CERTIFIED_DROP_TARGET:
        task_status = "SUCCESS_B_CERTIFIED_DROP"
        family_status = "OPEN_STRICTLY_TIGHTENED"
    elif stop_reason == "PROFILE_CAP_REACHED" and not unresolved:
        task_status = "SUCCESS_D_PROFILE_CAP"
        family_status = "OPEN_STRICTLY_TIGHTENED" if cumulative_drop > 0 else "OPEN"
    elif stop_reason == "PROOF_WALL_BUDGET_REACHED" and not unresolved:
        task_status = "SUCCESS_E_WALL_BUDGET"
        family_status = "OPEN_STRICTLY_TIGHTENED" if cumulative_drop > 0 else "OPEN"
    else:
        task_status = "BLOCKED_SOLVER_UNRESOLVED"
        family_status = "OPEN_STRICTLY_TIGHTENED" if cumulative_drop > 0 else "OPEN"
    attempted = tuple(
        _profile_from_raw(item["PROFILE"], name="fallback profile") for item in profile_bounds
    )
    assert_no_prior_profile_rerun(prior_state.profiles, attempted)
    return {
        "TASK_STATUS": task_status,
        "START_BOUND": START_BOUND,
        "END_BOUND": family_bound,
        "CUMULATIVE_DROP": cumulative_drop,
        "FALLBACK_PROFILE_COUNT": len(profile_bounds),
        "TOTAL_RESOLVED_PROFILE_COUNT": prior_state.profile_count + len(profile_bounds),
        "NEXT_ACTIVE_BOUND": None if next_envelope is None else next_envelope.family_upper_bound,
        "NEXT_ACTIVE_PROFILE": None if next_profile is None else list(next_profile),
        "FAMILY_UPPER_BOUND": family_bound,
        "REMAINING_FAMILY_GAP": max(0, family_bound - INCUMBENT),
        "FAMILY_STATUS": family_status,
        "STOP_REASON": stop_reason,
        "PROFILE_BOUNDS": profile_bounds,
        "RANK_LOOKUP": {
            "COMPLETE_PROFILES_EXAMINED": frontier.complete_profiles_examined,
            "SQUARE_SUM_CLASSES_EXAMINED": frontier.square_sum_classes_examined,
            "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
            "FULL_4850_PROFILE_RANKING_RERUN": False,
        },
        "LOOKUP_COMPLETE": frontier.lookup_complete,
        "ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
    }


def compute_r13_result(
    *,
    proof_wall_budget_seconds: float = TOTAL_WALL_BUDGET_SECONDS,
    stage_a_wall_budget_seconds: float = STAGE_A_WALL_BUDGET_SECONDS,
    profile_cap: int = PROFILE_CAP,
) -> dict[str, object]:
    """Run the class-dominance stage, then bounded ranked descent if needed."""

    if not 0 < proof_wall_budget_seconds <= TOTAL_WALL_BUDGET_SECONDS:
        raise ValueError("proof wall budget must be in (0, 3600] seconds")
    if not 0 < stage_a_wall_budget_seconds <= STAGE_A_WALL_BUDGET_SECONDS:
        raise ValueError("Stage A wall budget must be in (0, 1200] seconds")
    if not 1 <= profile_cap <= PROFILE_CAP:
        raise ValueError("fallback profile cap must be between one and ninety-six")
    started = monotonic()
    deadline = started + proof_wall_budget_seconds
    preflight = solver_runtime_preflight()
    prior_state = validate_prior_resolved_state()
    if prior_state.profile_count != 72:
        raise AssertionError("the R13 task requires exactly 72 already-resolved profiles")

    stage_a_started = monotonic()
    stage_a_deadline = min(deadline, stage_a_started + stage_a_wall_budget_seconds)
    class_certificate: dict[str, object] | None = None
    stage_a_status = "NO_MATERIAL_CLASS_DOMINANCE"
    next_profile: DegreeProfile | None = None
    next_envelope: CoarseProfileEnvelope | None = None
    lookup_profiles_examined = 0
    lookup_classes_examined = 0
    try:
        certificate = certify_square_sum_class_suffix(
            square_sum=sum(degree**2 for degree in START_PROFILE),
            upper_profile=START_PROFILE,
            prior_profiles=prior_state.profiles,
            deadline=stage_a_deadline,
        )
        class_certificate = certificate
        lookup_profiles_examined += _require_int(
            certificate.get("COMPLETE_PROFILES_EXAMINED"), "class profile count"
        )
        lookup_classes_examined += 1
        next_profile, next_envelope, next_examined = _first_eligible_profile_in_class(
            sum(degree**2 for degree in START_PROFILE) - 2,
            prior_profiles=prior_state.profiles,
            deadline=stage_a_deadline,
        )
        lookup_profiles_examined += next_examined
        lookup_classes_examined += 1
        if next_profile is None or next_envelope is None:
            raise FrontierLookupLimit("no eligible profile was found in the next square-sum class")
        class_bound = _require_int(
            certificate.get("CLASS_FAMILY_UPPER_BOUND"), "class family bound"
        )
        dominated_by_higher_class = class_bound < prior_state.maximum_profile_bound
        dominated_by_next_class = class_bound <= next_envelope.family_upper_bound
        class_certificate["HIGHER_RANK_PROFILE_BOUND"] = prior_state.maximum_profile_bound
        class_certificate["NEXT_LOWER_CLASS_BOUND"] = next_envelope.family_upper_bound
        class_certificate["DOMINATED_BY_HIGHER_RANK_BOUND"] = dominated_by_higher_class
        class_certificate["DOMINATED_BY_NEXT_CLASS_BOUND"] = dominated_by_next_class
        if dominated_by_higher_class or dominated_by_next_class:
            stage_a_status = "CERTIFIED_CLASS_DOMINANCE"
    except FrontierLookupLimit as exc:
        stage_a_status = f"CLASS_ATTEMPT_BUDGET_LIMIT: {exc}"

    stage_a_wall = monotonic() - stage_a_started
    if stage_a_wall > stage_a_wall_budget_seconds:
        raise AssertionError("Stage A exceeded its 20-minute proof wall budget")
    class_dominance_pass = (
        class_certificate is not None
        and stage_a_status == "CERTIFIED_CLASS_DOMINANCE"
        and next_profile is not None
        and next_envelope is not None
    )

    fallback_result: dict[str, object] | None = None
    if class_dominance_pass:
        if class_certificate is None or next_envelope is None or next_profile is None:
            raise AssertionError("a class-dominance result lacks its certified frontier")
        class_bound = _require_int(
            class_certificate.get("CLASS_FAMILY_UPPER_BOUND"), "class family bound"
        )
        if class_bound > max(prior_state.maximum_profile_bound, next_envelope.family_upper_bound):
            raise AssertionError(
                "class certificate does not lie below its competing frontier bound"
            )
        # W and the coarse S3 ceiling increase with square sum, so this first
        # lower-class profile bounds every class after it in the ranked suffix.
        family_bound = max(
            prior_state.maximum_profile_bound,
            class_bound,
            next_envelope.family_upper_bound,
        )
        stop_reason = "CLASS_DOMINANCE_CERTIFICATE"
        task_status = "SUCCESS_C_CLASS_DOMINANCE"
        family_status = "CLOSED" if family_bound <= INCUMBENT else "OPEN_STRICTLY_TIGHTENED"
        fallback_count = 0
        total_resolved = prior_state.profile_count + _require_int(
            class_certificate.get("REMAINING_ELIGIBLE_PROFILE_COUNT"),
            "class-resolved profile count",
        )
        next_active_bound: int | None = next_envelope.family_upper_bound
        next_active_profile: list[int] | None = list(next_profile)
        profile_bounds: list[dict[str, object]] = []
        fallback_wall = 0.0
        rank_lookup = {
            "COMPLETE_PROFILES_EXAMINED": lookup_profiles_examined,
            "SQUARE_SUM_CLASSES_EXAMINED": lookup_classes_examined,
            "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
            "FULL_4850_PROFILE_RANKING_RERUN": False,
        }
    else:
        fallback_started = monotonic()
        fallback_deadline = min(deadline, started + proof_wall_budget_seconds)
        try:
            fallback_result = _ranked_fallback(
                prior_state=prior_state,
                started=fallback_started,
                deadline=fallback_deadline,
                profile_cap=profile_cap,
            )
        except FrontierLookupLimit as exc:
            fallback_result = {
                "TASK_STATUS": "BLOCKED_RANK_LOOKUP_LIMIT",
                "START_BOUND": START_BOUND,
                "END_BOUND": START_BOUND,
                "CUMULATIVE_DROP": 0,
                "FALLBACK_PROFILE_COUNT": 0,
                "TOTAL_RESOLVED_PROFILE_COUNT": prior_state.profile_count,
                "NEXT_ACTIVE_BOUND": START_BOUND,
                "NEXT_ACTIVE_PROFILE": list(START_PROFILE),
                "FAMILY_UPPER_BOUND": START_BOUND,
                "REMAINING_FAMILY_GAP": START_BOUND - INCUMBENT,
                "FAMILY_STATUS": "OPEN",
                "STOP_REASON": f"RANK_LOOKUP_LIMIT: {exc}",
                "PROFILE_BOUNDS": [],
                "RANK_LOOKUP": {
                    "COMPLETE_PROFILES_EXAMINED": 0,
                    "SQUARE_SUM_CLASSES_EXAMINED": 0,
                    "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
                    "FULL_4850_PROFILE_RANKING_RERUN": False,
                },
                "LOOKUP_COMPLETE": False,
                "ACTUAL_WALL_TIME_SECONDS": monotonic() - fallback_started,
            }
        task_status = str(fallback_result["TASK_STATUS"])
        family_bound = _require_int(
            fallback_result.get("FAMILY_UPPER_BOUND"), "fallback family bound"
        )
        family_status = str(fallback_result["FAMILY_STATUS"])
        stop_reason = str(fallback_result["STOP_REASON"])
        fallback_count = _require_int(
            fallback_result.get("FALLBACK_PROFILE_COUNT"), "fallback profile count"
        )
        total_resolved = _require_int(
            fallback_result.get("TOTAL_RESOLVED_PROFILE_COUNT"), "resolved profile count"
        )
        next_active_bound_raw = fallback_result.get("NEXT_ACTIVE_BOUND")
        next_active_bound = (
            int(next_active_bound_raw) if type(next_active_bound_raw) is int else None
        )
        next_active_profile_raw = fallback_result.get("NEXT_ACTIVE_PROFILE")
        next_active_profile = (
            cast(list[int], next_active_profile_raw)
            if isinstance(next_active_profile_raw, list)
            else None
        )
        profile_bounds = cast(list[dict[str, object]], fallback_result["PROFILE_BOUNDS"])
        rank_lookup = cast(dict[str, object], fallback_result["RANK_LOOKUP"])
        fallback_wall = _require_float(
            fallback_result.get("ACTUAL_WALL_TIME_SECONDS"), "fallback wall time"
        )

    actual_wall = monotonic() - started
    if actual_wall > proof_wall_budget_seconds:
        raise AssertionError("the 60-minute total proof wall budget was exceeded")
    cumulative_drop = START_BOUND - family_bound
    stage_a_class_count = (
        _require_int(
            class_certificate.get("REMAINING_ELIGIBLE_PROFILE_COUNT"),
            "class-resolved profile count",
        )
        if class_certificate is not None
        else 0
    )
    class_bound_raw = (
        class_certificate.get("CLASS_FAMILY_UPPER_BOUND") if class_certificate is not None else None
    )
    class_bound = int(class_bound_raw) if type(class_bound_raw) is int else None
    classes_certified = (
        [
            {
                "SQUARE_SUM": class_certificate["SQUARE_SUM"],
                "REMAINING_PROFILE_COUNT": stage_a_class_count,
                "CLASS_FAMILY_UPPER_BOUND": class_bound,
                "RANKED_COARSE_CLASS_BOUND": class_certificate["RANKED_COARSE_CLASS_BOUND"],
                "HIGHER_RANK_PROFILE_BOUND": prior_state.maximum_profile_bound,
                "NEXT_LOWER_CLASS_BOUND": next_envelope.family_upper_bound
                if next_envelope is not None
                else None,
            }
        ]
        if class_dominance_pass and class_certificate is not None
        else []
    )
    result: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": task_status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "WORKTREE_DISPOSITION": "RETAIN",
        "START_BOUND": START_BOUND,
        "END_BOUND": family_bound,
        "CUMULATIVE_DROP": cumulative_drop,
        "CLASS_LOCAL_DROP": (
            class_certificate.get("CLASS_LOCAL_DROP") if class_certificate is not None else None
        ),
        "PRIOR_RESOLVED_PROFILE_COUNT": prior_state.profile_count,
        "PRIOR_PROFILE_RERUN_COUNT": 0,
        "CLASS_DOMINANCE_STATUS": ("CERTIFIED" if class_dominance_pass else stage_a_status),
        "CLASSES_CERTIFIED": classes_certified,
        "PROFILES_ELIMINATED_BY_CLASS_BOUND": stage_a_class_count if class_dominance_pass else 0,
        "CLASS_DOMINANCE_CERTIFICATE": class_certificate,
        "STAGE_A_WALL_TIME_SECONDS": stage_a_wall,
        "STAGE_A_WALL_BUDGET_SECONDS": stage_a_wall_budget_seconds,
        "FALLBACK_PROFILE_COUNT": fallback_count,
        "FALLBACK_PROFILE_CAP": profile_cap,
        "FALLBACK_WALL_TIME_SECONDS": fallback_wall,
        "TOTAL_RESOLVED_PROFILE_COUNT": total_resolved,
        "NEXT_ACTIVE_BOUND": next_active_bound,
        "NEXT_ACTIVE_PROFILE": next_active_profile,
        "FAMILY_UPPER_BOUND": family_bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": max(0, family_bound - INCUMBENT),
        "REMAINING_FAMILY_GAP": max(0, family_bound - INCUMBENT),
        "FAMILY_STATUS": family_status,
        "STOP_REASON": stop_reason,
        "RANK_LOOKUP": rank_lookup,
        "PROFILE_BOUNDS": profile_bounds,
        "SOLVER_RUNTIME_PREFLIGHT": preflight,
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "STAGE_A_PROOF_WALL_BUDGET_SECONDS": stage_a_wall_budget_seconds,
            "PROOF_WALL_BUDGET_SECONDS": proof_wall_budget_seconds,
            "EXTERNAL_HARD_TIMEOUT_SECONDS_PER_PROFILE": EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
            "NATIVE_SUPPORT_SECONDS_PER_PROFILE": NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_MOTIF_SECONDS_PER_PROFILE": NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_DEGREE_CLASS_SECONDS_PER_PROFILE": NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
            "WORKERS": 1,
        },
        "ACTUAL_WALL_TIME_SECONDS": actual_wall,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }
    if fallback_result is not None:
        result["FALLBACK_RESULT"] = fallback_result
    return result


def compact_r13_result(result: dict[str, object]) -> dict[str, object]:
    """Keep the result compact while retaining the full class certificate."""

    compact = result.copy()
    profile_rows = compact.get("PROFILE_BOUNDS")
    if isinstance(profile_rows, list) and profile_rows:
        profile_result = _compact_profile_result({"PROFILE_BOUNDS": profile_rows})
        compact["PROFILE_BOUNDS"] = profile_result["PROFILE_BOUNDS"]
    fallback = compact.get("FALLBACK_RESULT")
    if isinstance(fallback, dict):
        fallback_result = cast(dict[str, object], fallback).copy()
        nested_rows = fallback_result.get("PROFILE_BOUNDS")
        if isinstance(nested_rows, list) and nested_rows:
            profile_result = _compact_profile_result({"PROFILE_BOUNDS": nested_rows})
            fallback_result["PROFILE_BOUNDS"] = profile_result["PROFILE_BOUNDS"]
        compact["FALLBACK_RESULT"] = fallback_result
    return compact


def main() -> None:
    result = compact_r13_result(compute_r13_result())
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
