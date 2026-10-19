"""Certify successive K20 minimum-S2 degree-square classes (R14).

The R13 handoff leaves square-sum class 332 at the ranked frontier. This
module applies the existing degree-class open-wedge relaxation to complete
successive classes, then uses a bounded exact-profile fallback only if the
class certificates stop tightening the family bound.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    CLASS_RELAXATION_WALL_LIMIT_SECONDS,
    FrontierLookupLimit,
    assert_no_prior_profile_rerun,
    degree_class_open_wedge_relaxation,
    graph_triangle_upper_bound_from_open_wedges,
    profile_family_envelope_from_triangle_bound,
    validate_prior_resolved_state,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
    MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
    solver_runtime_preflight,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    FrontierLookupLimit as R12FrontierLookupLimit,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    _iter_square_sum_profiles as iter_square_sum_profiles,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    _LookupCounters as R12LookupCounters,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    _resolve_profile as resolve_profile,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    compact_descent_result as compact_profile_result,
)
from .b649_k20_min_s2_dangerous_core_realizability_r5 import K20_REUSED_S4_LOWER_BOUND
from .b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    CoarseProfileEnvelope,
    coarse_profile_envelope,
    profile_shadow_obstruction,
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

TASK_ID = "B649_K20_MIN_S2_SUCCESSIVE_CLASS_DOMINANCE_R14"
TASK_BRANCH = "codex/b649-k20-min-s2-successive-class-dominance-r14"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_MIN_S2_SUCCESSIVE_CLASS_DOMINANCE_R14"
)
BASE_HEAD = "b48cc8bfe197b80201e1c57c55a8dcce4d17dae2"
BASE_TREE = "3e2271f1bbffb992555434ea97de0ac9af4f5cef"
START_BOUND = 313_695_864
INCUMBENT = K20_INCUMBENT
START_PROFILE: DegreeProfile = (
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
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    0,
    0,
)
PRIOR_RESOLVED_PROFILE_COUNT = 76
STAGE_A_WALL_BUDGET_SECONDS = 1_500.0
TOTAL_WALL_BUDGET_SECONDS = 3_600.0
STAGE_A_DROP_TARGET = 25_000
FALLBACK_DROP_TARGET = 50_000
FALLBACK_PROFILE_CAP = 72
MINIMUM_SQUARE_SUM = 222
PROFILE_IDENTITY_ENCODING = "20 digits; position i is the 0..6 degree for ranked ticket i"
HISTOGRAM_ROW_ENCODING = (
    "counts0to6(comma)|status|solver_seconds|open_wedge_lb|bound_source|triangle_ub|"
    "s3_ub|s4_lb|fourth_credit|family_ub|coarse_ub; '-' means not applicable"
)
RESULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-successive-class-dominance-r14-result.json"
)
R13_RESULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-class-dominance-or-descent-r13-result.json"
)


@dataclass(frozen=True, slots=True)
class PriorFrontierState:
    """The validated R13 frontier and exact no-rerun identity set."""

    profiles: frozenset[DegreeProfile]
    higher_rank_bound: int
    class_bounds: tuple[int, ...]
    active_bound: int
    active_profile: DegreeProfile


@dataclass(frozen=True, slots=True)
class RankedFrontier:
    """A bounded exact prefix beginning at the first unresolved profile."""

    profiles: tuple[DegreeProfile, ...]
    envelopes: tuple[CoarseProfileEnvelope, ...]
    complete_profiles_examined: int
    square_sum_classes_examined: int
    lookup_complete: bool


def _require_int(value: object, name: str) -> int:
    if type(value) is not int:
        raise AssertionError(f"{name} must be an integer")
    return value


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


def canonical_primitive_preflight() -> dict[str, int | str]:
    """Assert the canonical one-ticket and twenty-ticket S1 counts."""

    single_ticket_any_prize = K20_S1 // K20_TICKET_COUNT
    if K20_S1 != 372_228_640 or single_ticket_any_prize != 18_611_432:
        raise AssertionError("canonical S1 primitives changed")
    if single_ticket_any_prize * K20_TICKET_COUNT != K20_S1:
        raise AssertionError("single-ticket and K20 S1 counts do not reconcile")
    return {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": single_ticket_any_prize,
        "K20_S1": K20_S1,
    }


def _read_json(path: Path) -> dict[str, object]:
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise TypeError(f"result at {path} must be a JSON object")
    return cast(dict[str, object], decoded)


def validate_prior_frontier_state() -> PriorFrontierState:
    """Validate R13's exact 76-profile handoff without rerunning profile solves."""

    prior_exact = validate_prior_resolved_state()
    result = _read_json(R13_RESULT_PATH)
    certificate_raw = result.get("CLASS_DOMINANCE_CERTIFICATE")
    if not isinstance(certificate_raw, dict):
        raise AssertionError("the R13 handoff lacks its class certificate")
    certificate = cast(dict[str, object], certificate_raw)
    if result.get("TASK_STATUS") != "SUCCESS_C_CLASS_DOMINANCE":
        raise AssertionError("R13 did not complete its class-dominance handoff")
    if result.get("PRIOR_RESOLVED_PROFILE_COUNT") != 72:
        raise AssertionError("R13 did not preserve its 72-profile prior ledger")
    if result.get("PRIOR_PROFILE_RERUN_COUNT") != 0:
        raise AssertionError("R13 reported a prior profile rerun")
    if result.get("TOTAL_RESOLVED_PROFILE_COUNT") != PRIOR_RESOLVED_PROFILE_COUNT:
        raise AssertionError("R13 does not report the packet-pinned 76 resolved profiles")
    if result.get("FAMILY_UPPER_BOUND") != START_BOUND:
        raise AssertionError("R13's family bound does not match the packet")
    if result.get("NEXT_ACTIVE_BOUND") != START_BOUND:
        raise AssertionError("R13's next active bound does not match the packet")
    if result.get("INCUMBENT") != INCUMBENT:
        raise AssertionError("R13's incumbent does not match the packet")
    active_profile = _profile_from_raw(result.get("NEXT_ACTIVE_PROFILE"), name="R13 cursor")
    if active_profile != START_PROFILE:
        raise AssertionError("R13's next active profile does not match the packet")
    if certificate.get("SQUARE_SUM") != 334:
        raise AssertionError("R13's completed class is not square-sum 334")
    if certificate.get("COMPLETE_SUFFIX_ENUMERATION") is not True:
        raise AssertionError("R13 did not certify the complete class suffix")

    raw_identities = certificate.get("PROFILE_IDENTITIES")
    if not isinstance(raw_identities, list):
        raise AssertionError("R13's class certificate lacks profile identities")
    class_profiles = frozenset(
        _profile_from_raw(profile, name="R13 class-eliminated profile")
        for profile in cast(list[object], raw_identities)
    )
    if len(class_profiles) != 4:
        raise AssertionError("R13's class certificate does not account for four profiles")
    assert_no_prior_profile_rerun(prior_exact.profiles, class_profiles)
    all_profiles = prior_exact.profiles | class_profiles
    if len(all_profiles) != PRIOR_RESOLVED_PROFILE_COUNT:
        raise AssertionError("the R13 no-rerun identity set is not exactly 76 profiles")
    assert_no_prior_profile_rerun(all_profiles, (active_profile,))

    higher_rank_bound = _require_int(
        certificate.get("HIGHER_RANK_PROFILE_BOUND"), "R13 higher-rank bound"
    )
    if higher_rank_bound != prior_exact.maximum_profile_bound:
        raise AssertionError("R13 higher-rank bound disagrees with its validated prior ledger")
    prior_class_bound = _require_int(certificate.get("CLASS_FAMILY_UPPER_BOUND"), "R13 class bound")
    if prior_class_bound >= START_BOUND:
        raise AssertionError("R13's eliminated class is not below the active frontier")
    if max(higher_rank_bound, prior_class_bound, START_BOUND) != START_BOUND:
        raise AssertionError("R13's decomposition does not reconcile to the family bound")
    return PriorFrontierState(
        profiles=all_profiles,
        higher_rank_bound=higher_rank_bound,
        class_bounds=(prior_class_bound,),
        active_bound=START_BOUND,
        active_profile=active_profile,
    )


def _wedge_total_for_square_sum(square_sum: int) -> int:
    """Use the degree-square identity for the overlap graph's wedge total."""

    numerator = square_sum + 11 * K20_TRIPLE_INCIDENCE_COUNT + 30 * K20_TICKET_COUNT
    if numerator % 2:
        raise AssertionError("degree-square identity produced a noninteger wedge total")
    return numerator // 2


def coarse_family_bound_for_square_sum(square_sum: int) -> int:
    """Return the generic triangle and S4 envelope for one complete class."""

    wedges = _wedge_total_for_square_sum(square_sum)
    graph_triangle_bound = wedges // 3
    noncore_triangle_bound = graph_triangle_bound - K20_TRIPLE_SUPPORT_COUNT
    if noncore_triangle_bound < 0:
        return 0
    s3_bound = s3_sum_from_wedges_and_triangles(wedges, noncore_triangle_bound)
    fourth_order_credit = (4 * K20_REUSED_S4_LOWER_BOUND) // 7
    return K20_S1 - K20_S2 + s3_bound - fourth_order_credit


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


def _structurally_empty_class(
    square_sum: int,
    *,
    complete_profiles_examined: int,
    reason: str,
) -> dict[str, object]:
    return {
        "SQUARE_SUM": square_sum,
        "WEDGE_COUNT": _wedge_total_for_square_sum(square_sum),
        "CLASS_STATUS": "CERTIFIED_EMPTY_BY_STRUCTURAL_FILTERS",
        "EMPTY_CLASS_REASON": reason,
        "COMPLETE_PROFILES_EXAMINED": complete_profiles_examined,
        "PAIR_CAPACITY_FILTER": "APPLIED",
        "RESIDUAL_DOUBLE_SUPPORT_GRAPHICALITY_FILTER": "APPLIED",
        "SHADOW_GRAPHICALITY_FILTER": "APPLIED",
        "REMAINING_ELIGIBLE_PROFILE_COUNT": 0,
        "PROFILE_IDENTITIES": [],
        "CLASS_FAMILY_UPPER_BOUND": 0,
        "RANKED_COARSE_CLASS_BOUND": coarse_family_bound_for_square_sum(square_sum),
        "COMPLETE_SUFFIX_ENUMERATION": True,
    }


def certify_square_sum_class(
    *,
    square_sum: int,
    upper_profile: DegreeProfile | None,
    prior_profiles: Collection[DegreeProfile],
    deadline: float,
) -> dict[str, object]:
    """Certify one complete ranked square-sum class suffix generically.

    The profile iterator applies pair-capacity and residual-double-support
    graphicality filters. Shadow-degree graphicality then removes impossible
    triple systems. Remaining degree histograms share their degree-square and
    wedge totals, so each histogram needs one relaxed complement-graph solve.
    """

    if upper_profile is not None and sum(degree**2 for degree in upper_profile) != square_sum:
        raise ValueError("upper profile does not belong to the requested square-sum class")
    counters = R12LookupCounters()
    raw_profiles = tuple(
        iter_square_sum_profiles(
            square_sum,
            upper_profile=upper_profile,
            counters=counters,
            deadline=deadline,
        )
    )
    if upper_profile is not None and (not raw_profiles or raw_profiles[0] != upper_profile):
        raise AssertionError("the active profile is not the first eligible suffix member")
    assert_no_prior_profile_rerun(prior_profiles, raw_profiles)
    profiles = tuple(
        profile for profile in raw_profiles if profile_shadow_obstruction(profile) is None
    )
    if upper_profile is not None and (not profiles or profiles[0] != upper_profile):
        raise AssertionError("shadow-graph filtering removed the active profile")
    if any(sum(profile) != K20_TRIPLE_INCIDENCE_COUNT for profile in profiles):
        raise AssertionError("a class profile has the wrong triple-incidence sum")
    if any(sum(degree**2 for degree in profile) != square_sum for profile in profiles):
        raise AssertionError("a class profile has the wrong square sum")

    wedge_count = _wedge_total_for_square_sum(square_sum)
    if profiles and {overlap_wedge_count(profile) for profile in profiles} != {wedge_count}:
        raise AssertionError("a square-sum class does not have its degree-square wedge total")
    if not profiles:
        if upper_profile is not None:
            raise AssertionError("the packet-pinned active class unexpectedly has no profiles")
        reason = "PAIR_CAPACITY_RESIDUAL_DOUBLE_SUPPORT_OR_SHADOW_DEGREE"
        return _structurally_empty_class(
            square_sum,
            complete_profiles_examined=counters.complete_profiles_examined,
            reason=reason,
        )

    histograms = tuple(sorted({_profile_histogram(profile) for profile in profiles}))
    histogram_bounds: list[dict[str, object]] = []
    class_upper_bound: int | None = None
    class_triangle_upper_bound: int | None = None
    total_solver_wall = 0.0
    for histogram in histograms:
        if monotonic() >= deadline:
            raise R12FrontierLookupLimit("Stage A wall budget expired during class relaxation")
        profile = _degree_sequence_from_histogram(histogram)
        if sum(profile) != K20_TRIPLE_INCIDENCE_COUNT or sum(d**2 for d in profile) != square_sum:
            raise AssertionError("a degree histogram left the certified square-sum class")
        graph_degrees = tuple(K20_TICKET_CAPACITY + degree for degree in profile)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise R12FrontierLookupLimit("Stage A wall budget expired before class solve")
        relaxation = degree_class_open_wedge_relaxation(
            graph_degrees,
            wall_limit_seconds=min(CLASS_RELAXATION_WALL_LIMIT_SECONDS, remaining),
        )
        solver_wall = relaxation.get("SOLVER_WALL_TIME_SECONDS")
        if not isinstance(solver_wall, (int, float)):
            raise AssertionError("degree-class relaxation omitted its wall time")
        total_solver_wall += float(solver_wall)
        status = relaxation.get("SOLVER_STATUS")
        if status == "INFEASIBLE":
            histogram_bounds.append(
                {
                    "DEGREE_COUNTS_0_TO_6": list(histogram),
                    "PROFILE": list(profile),
                    "RELAXATION_STATUS": "INFEASIBLE_GRAPH_DEGREE_CLASS",
                    "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": None,
                    "FAMILY_UPPER_BOUND": None,
                }
            )
            continue
        if status == "MODEL_INVALID":
            raise RuntimeError("the degree-class CP-SAT relaxation model is invalid")
        lower_bound_raw = relaxation.get("WEIGHTED_OPEN_WEDGE_LOWER_BOUND")
        if type(lower_bound_raw) is not int or lower_bound_raw < 0:
            raise AssertionError("relaxation omitted its certified open-wedge lower bound")
        lower_bound = lower_bound_raw
        if status == "FEASIBLE":
            bound_source = "BEST_OBJECTIVE_BOUND_FLOOR"
        elif status == "OPTIMAL":
            bound_source = "OPTIMAL_OBJECTIVE_VALUE"
        else:
            bound_source = "SAFE_NONNEGATIVE_BOUND"
        triangle_envelope = graph_triangle_upper_bound_from_open_wedges(graph_degrees, lower_bound)
        triangle_bound = _require_int(
            triangle_envelope.get("GRAPH_TRIANGLE_UPPER_BOUND"), "triangle upper bound"
        )
        if triangle_bound < K20_TRIPLE_SUPPORT_COUNT:
            histogram_bounds.append(
                {
                    "DEGREE_COUNTS_0_TO_6": list(histogram),
                    "PROFILE": list(profile),
                    "RELAXATION_STATUS": str(status),
                    "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": lower_bound,
                    "LOWER_BOUND_SOURCE": bound_source,
                    "TRIANGLE_ENVELOPE": triangle_envelope,
                    "FAMILY_UPPER_BOUND": None,
                }
            )
            continue
        profile_envelope = profile_family_envelope_from_triangle_bound(profile, triangle_bound)
        family_bound = _require_int(
            profile_envelope.get("FAMILY_UPPER_BOUND"), "profile motif bound"
        )
        class_upper_bound = (
            family_bound if class_upper_bound is None else max(class_upper_bound, family_bound)
        )
        class_triangle_upper_bound = (
            triangle_bound
            if class_triangle_upper_bound is None
            else max(class_triangle_upper_bound, triangle_bound)
        )
        histogram_bounds.append(
            {
                "DEGREE_COUNTS_0_TO_6": list(histogram),
                "PROFILE": list(profile),
                "RELAXATION_STATUS": str(status),
                "SOLVER_WALL_TIME_SECONDS": float(solver_wall),
                "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": lower_bound,
                "LOWER_BOUND_SOURCE": bound_source,
                "TRIANGLE_ENVELOPE": triangle_envelope,
                "PROFILE_ENVELOPE": profile_envelope,
                "FAMILY_UPPER_BOUND": family_bound,
            }
        )

    if class_upper_bound is None:
        class_upper_bound = 0
    if upper_profile is not None:
        ranked_coarse_bound = coarse_profile_envelope(upper_profile).family_upper_bound
    else:
        ranked_coarse_bound = coarse_family_bound_for_square_sum(square_sum)
    if class_upper_bound > ranked_coarse_bound:
        raise AssertionError("the class envelope exceeds the ranked coarse class bound")
    return {
        "SQUARE_SUM": square_sum,
        "UPPER_PROFILE": list(profiles[0]),
        "REMAINING_ELIGIBLE_PROFILE_COUNT": len(profiles),
        "STRUCTURAL_CANDIDATE_PROFILE_COUNT": len(raw_profiles),
        "SHADOW_INFEASIBLE_PROFILE_COUNT": len(raw_profiles) - len(profiles),
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
        "RANKED_COARSE_CLASS_BOUND": ranked_coarse_bound,
        "CLASS_LOCAL_DROP": ranked_coarse_bound - class_upper_bound,
        "RELAXATION_SOLVER_WALL_TIME_SECONDS": total_solver_wall,
        "COMPLETE_SUFFIX_ENUMERATION": True,
    }


def assert_ranked_frontier_invariant(
    profiles: Sequence[DegreeProfile], envelopes: Sequence[CoarseProfileEnvelope]
) -> None:
    """Require a unique, square-sum-descending, envelope-ranked frontier."""

    if len(profiles) != len(envelopes):
        raise AssertionError("ranked frontier profiles and envelopes have different lengths")
    if len(set(profiles)) != len(profiles):
        raise AssertionError("ranked frontier contains duplicate profiles")
    keys = tuple(_rank_key(envelope) for envelope in envelopes)
    if keys != tuple(sorted(keys, reverse=True)):
        raise AssertionError("ranked frontier envelope order is not descending")
    square_sums = tuple(sum(degree**2 for degree in profile) for profile in profiles)
    if any(first < second for first, second in pairwise(square_sums)):
        raise AssertionError("ranked frontier square-sum classes are not descending")
    for square_sum in set(square_sums):
        class_profiles = tuple(
            profile for profile in profiles if sum(degree**2 for degree in profile) == square_sum
        )
        if class_profiles != tuple(sorted(class_profiles, reverse=True)):
            raise AssertionError("ranked frontier class is not in descending profile order")


def lookup_ranked_frontier(
    *,
    start_profile: DegreeProfile | None,
    start_square_sum: int,
    profile_limit: int,
    deadline: float,
    prior_profiles: Collection[DegreeProfile],
) -> RankedFrontier:
    """Build only a bounded eligible prefix from a supplied frontier cursor."""

    if profile_limit < 1:
        raise ValueError("profile_limit must be positive")
    if start_profile is not None and sum(degree**2 for degree in start_profile) != start_square_sum:
        raise ValueError("start profile does not belong to the requested square-sum class")
    if start_profile is not None:
        assert_no_prior_profile_rerun(prior_profiles, (start_profile,))
    profiles: list[DegreeProfile] = []
    envelopes: list[CoarseProfileEnvelope] = []
    complete_profiles_examined = 0
    square_sum_classes_examined = 0
    square_sum = start_square_sum
    upper_profile = start_profile
    while square_sum >= MINIMUM_SQUARE_SUM:
        if monotonic() >= deadline:
            raise R12FrontierLookupLimit("proof wall budget expired during ranked frontier lookup")
        square_sum_classes_examined += 1
        counters = R12LookupCounters()
        for profile in iter_square_sum_profiles(
            square_sum,
            upper_profile=upper_profile,
            counters=counters,
            deadline=deadline,
        ):
            assert_no_prior_profile_rerun(prior_profiles, (profile,))
            if profile_shadow_obstruction(profile) is not None:
                continue
            envelope = coarse_profile_envelope(profile)
            profiles.append(profile)
            envelopes.append(envelope)
            assert_ranked_frontier_invariant(profiles, envelopes)
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
            raise R12FrontierLookupLimit(
                "ranked lookup exceeded its bounded complete-profile prefix"
            )
        upper_profile = None
        square_sum -= 2
    assert_ranked_frontier_invariant(profiles, envelopes)
    return RankedFrontier(
        tuple(profiles),
        tuple(envelopes),
        complete_profiles_examined,
        square_sum_classes_examined,
        True,
    )


def _first_eligible_profile(
    *,
    start_square_sum: int,
    deadline: float,
    prior_profiles: Collection[DegreeProfile],
) -> tuple[DegreeProfile | None, int | None, list[dict[str, object]], int]:
    """Find the next active profile, recording intervening empty classes."""

    empty_classes: list[dict[str, object]] = []
    complete_profiles_examined = 0
    square_sum = start_square_sum
    while square_sum >= MINIMUM_SQUARE_SUM:
        if monotonic() >= deadline:
            raise R12FrontierLookupLimit(
                "proof wall budget expired while finding next active profile"
            )
        counters = R12LookupCounters()
        found: DegreeProfile | None = None
        for profile in iter_square_sum_profiles(
            square_sum,
            upper_profile=None,
            counters=counters,
            deadline=deadline,
        ):
            assert_no_prior_profile_rerun(prior_profiles, (profile,))
            if profile_shadow_obstruction(profile) is None:
                found = profile
                break
        complete_profiles_examined += counters.complete_profiles_examined
        if found is not None:
            return found, square_sum, empty_classes, complete_profiles_examined
        empty_classes.append(
            _structurally_empty_class(
                square_sum,
                complete_profiles_examined=counters.complete_profiles_examined,
                reason="PAIR_CAPACITY_RESIDUAL_DOUBLE_SUPPORT_OR_SHADOW_DEGREE",
            )
        )
        square_sum -= 2
    return None, None, empty_classes, complete_profiles_examined


def _rank_key(envelope: CoarseProfileEnvelope) -> tuple[object, ...]:
    return (
        envelope.family_upper_bound,
        envelope.s3_upper_bound,
        envelope.wedge_count,
        envelope.degree_profile,
    )


def _family_bound(
    *,
    prior: PriorFrontierState,
    class_bounds: Sequence[int],
    profile_bounds: Sequence[int] = (),
    next_active_bound: int | None,
) -> int:
    bounds = [prior.higher_rank_bound, *prior.class_bounds, *class_bounds, *profile_bounds]
    if next_active_bound is not None:
        bounds.append(next_active_bound)
    return max(bounds, default=0)


def _ranked_fallback(
    *,
    prior: PriorFrontierState,
    class_profiles: Collection[DegreeProfile],
    class_bounds: Sequence[int],
    start_profile: DegreeProfile | None,
    start_square_sum: int,
    started: float,
    deadline: float,
    profile_cap: int,
) -> dict[str, object]:
    excluded_profiles = prior.profiles | frozenset(class_profiles)
    frontier = lookup_ranked_frontier(
        start_profile=start_profile,
        start_square_sum=start_square_sum,
        profile_limit=profile_cap + 1,
        deadline=deadline,
        prior_profiles=excluded_profiles,
    )
    if start_profile is not None and (
        not frontier.profiles or frontier.profiles[0] != start_profile
    ):
        raise AssertionError("fallback no longer starts at the unresolved ranked cursor")
    profile_rows: list[dict[str, object]] = []
    resolved_bounds: list[int] = []
    resolved_count = 0
    unresolved = False
    stop_reason = "PROFILE_CAP_REACHED"
    family_bound = _family_bound(
        prior=prior,
        class_bounds=class_bounds,
        next_active_bound=(
            frontier.envelopes[0].family_upper_bound if frontier.envelopes else None
        ),
    )
    for rank_index, profile in enumerate(frontier.profiles[:profile_cap]):
        if monotonic() >= deadline:
            stop_reason = "PROOF_WALL_BUDGET_REACHED"
            break
        assert_no_prior_profile_rerun(excluded_profiles, (profile,))
        resolution: dict[str, object]
        try:
            resolution = resolve_profile(profile, remaining_wall=deadline - monotonic())
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
        profile_rows.append(resolution)
        state = resolution.get("REALIZABILITY")
        if state == "UNRESOLVED":
            unresolved = True
            stop_reason = "SOLVER_UNRESOLVED"
            break
        if state == "REALIZABLE":
            bound = resolution.get("FAMILY_UPPER_BOUND")
            if type(bound) is not int:
                raise AssertionError("a realizable fallback profile lacks its family bound")
            resolved_bounds.append(bound)
        elif state != "UNREALIZABLE":
            raise AssertionError("fallback returned an unknown realizability state")
        resolved_count += 1

        next_index = rank_index + 1
        next_profile_bound = (
            frontier.envelopes[next_index].family_upper_bound
            if next_index < len(frontier.envelopes)
            else None
        )
        family_bound = _family_bound(
            prior=prior,
            class_bounds=class_bounds,
            profile_bounds=resolved_bounds,
            next_active_bound=next_profile_bound,
        )
        if family_bound <= INCUMBENT:
            stop_reason = "FAMILY_CLOSED"
            break
        if START_BOUND - family_bound >= FALLBACK_DROP_TARGET:
            stop_reason = "CERTIFIED_DROP_TARGET_REACHED"
            break
        if len(profile_rows) >= profile_cap:
            stop_reason = "PROFILE_CAP_REACHED"
            break

    next_index = len(profile_rows) - 1 if unresolved else len(profile_rows)
    next_profile = frontier.profiles[next_index] if next_index < len(frontier.profiles) else None
    next_bound = (
        frontier.envelopes[next_index].family_upper_bound
        if next_index < len(frontier.envelopes)
        else None
    )
    family_bound = _family_bound(
        prior=prior,
        class_bounds=class_bounds,
        profile_bounds=resolved_bounds,
        next_active_bound=next_bound,
    )
    if family_bound <= INCUMBENT:
        task_status = "SUCCESS_A_FAMILY_CLOSED"
        family_status = "CLOSED"
    elif START_BOUND - family_bound >= FALLBACK_DROP_TARGET:
        task_status = "SUCCESS_B_CERTIFIED_DROP"
        family_status = "OPEN_STRICTLY_TIGHTENED"
    elif len(profile_rows) >= profile_cap and not unresolved:
        task_status = "SUCCESS_D_PROFILE_CAP"
        family_status = "OPEN_STRICTLY_TIGHTENED" if family_bound < START_BOUND else "OPEN"
    elif monotonic() >= deadline:
        task_status = "SUCCESS_E_WALL_BUDGET"
        family_status = "OPEN_STRICTLY_TIGHTENED" if family_bound < START_BOUND else "OPEN"
        stop_reason = "PROOF_WALL_BUDGET_REACHED"
    else:
        task_status = "BLOCKED_SOLVER_UNRESOLVED"
        family_status = "OPEN_STRICTLY_TIGHTENED" if family_bound < START_BOUND else "OPEN"
    compact_rows_raw: object = (
        compact_profile_result({"PROFILE_BOUNDS": profile_rows}).get("PROFILE_BOUNDS", [])
        if profile_rows
        else []
    )
    if not isinstance(compact_rows_raw, list):
        raise AssertionError("compact fallback rows are malformed")
    compact_rows = cast(list[dict[str, object]], compact_rows_raw)
    return {
        "TASK_STATUS": task_status,
        "FALLBACK_PROFILE_COUNT": len(profile_rows),
        "FALLBACK_PROFILE_RESOLVED_COUNT": resolved_count,
        "TOTAL_RESOLVED_PROFILE_COUNT": (
            PRIOR_RESOLVED_PROFILE_COUNT + len(class_profiles) + resolved_count
        ),
        "NEXT_ACTIVE_BOUND": next_bound,
        "NEXT_ACTIVE_PROFILE": None if next_profile is None else list(next_profile),
        "FAMILY_UPPER_BOUND": family_bound,
        "REMAINING_GAP": max(0, family_bound - INCUMBENT),
        "FAMILY_STATUS": family_status,
        "STOP_REASON": stop_reason,
        "PROFILE_BOUNDS": compact_rows,
        "RANK_LOOKUP": {
            "COMPLETE_PROFILES_EXAMINED": frontier.complete_profiles_examined,
            "SQUARE_SUM_CLASSES_EXAMINED": frontier.square_sum_classes_examined,
            "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
            "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        },
        "LOOKUP_COMPLETE": frontier.lookup_complete,
        "ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
    }


def compute_r14_result(
    *,
    proof_wall_budget_seconds: float = TOTAL_WALL_BUDGET_SECONDS,
    stage_a_wall_budget_seconds: float = STAGE_A_WALL_BUDGET_SECONDS,
    profile_cap: int = FALLBACK_PROFILE_CAP,
) -> dict[str, object]:
    """Certify successive classes and run only the bounded fallback if needed."""

    if not 0 < proof_wall_budget_seconds <= TOTAL_WALL_BUDGET_SECONDS:
        raise ValueError("proof wall budget must be in (0, 3600] seconds")
    if not 0 < stage_a_wall_budget_seconds <= STAGE_A_WALL_BUDGET_SECONDS:
        raise ValueError("Stage A wall budget must be in (0, 1500] seconds")
    if not 1 <= profile_cap <= FALLBACK_PROFILE_CAP:
        raise ValueError("fallback profile cap must be between one and seventy-two")
    started = monotonic()
    deadline = started + proof_wall_budget_seconds
    primitives = canonical_primitive_preflight()
    runtime_preflight = solver_runtime_preflight()
    prior = validate_prior_frontier_state()

    stage_a_started = monotonic()
    stage_a_deadline = min(deadline, stage_a_started + stage_a_wall_budget_seconds)
    class_certificates: list[dict[str, object]] = []
    certified_class_profiles: set[DegreeProfile] = set()
    certified_class_bounds: list[int] = []
    eliminated_profile_count = 0
    current_profile: DegreeProfile = prior.active_profile
    has_current_profile: bool = bool(prior.profiles)
    current_square_sum = sum(degree**2 for degree in prior.active_profile)
    fallback_start_square_sum = current_square_sum
    current_active_bound = prior.active_bound
    stage_a_stop_reason = "NO_MATERIAL_CLASS_DOMINANCE"
    stage_a_success = False

    while has_current_profile and current_square_sum >= MINIMUM_SQUARE_SUM:
        if monotonic() >= stage_a_deadline:
            stage_a_stop_reason = "STAGE_A_WALL_BUDGET_REACHED"
            break
        try:
            certificate = certify_square_sum_class(
                square_sum=current_square_sum,
                upper_profile=current_profile,
                prior_profiles=prior.profiles | certified_class_profiles,
                deadline=stage_a_deadline,
            )
        except R12FrontierLookupLimit as exc:
            stage_a_stop_reason = f"STAGE_A_WALL_OR_LOOKUP_LIMIT: {exc}"
            break
        if certificate.get("COMPLETE_SUFFIX_ENUMERATION") is not True:
            raise AssertionError("Stage A did not enumerate the complete active class suffix")
        class_bound = _require_int(
            certificate.get("CLASS_FAMILY_UPPER_BOUND"), "class family upper bound"
        )
        certificate["CURRENT_ACTIVE_BOUND"] = current_active_bound
        certificate["CERTIFICATION_STATUS"] = (
            "CERTIFIED_BELOW_ACTIVE_BOUND"
            if class_bound < current_active_bound
            else "NOT_BELOW_ACTIVE_BOUND"
        )
        class_certificates.append(certificate)
        if class_bound >= current_active_bound:
            stage_a_stop_reason = "CLASS_BOUND_NOT_BELOW_CURRENT_ACTIVE_BOUND"
            break

        identities_raw = certificate.get("PROFILE_IDENTITIES")
        if not isinstance(identities_raw, list):
            raise AssertionError("a certified class lacks its profile identities")
        identities = frozenset(
            _profile_from_raw(profile, name="R14 class-eliminated profile")
            for profile in cast(list[object], identities_raw)
        )
        if len(identities) != _require_int(
            certificate.get("REMAINING_ELIGIBLE_PROFILE_COUNT"), "class profile count"
        ):
            raise AssertionError("class identity count disagrees with its certificate")
        assert_no_prior_profile_rerun(prior.profiles | certified_class_profiles, identities)
        certified_class_profiles.update(identities)
        eliminated_profile_count += len(identities)
        certified_class_bounds.append(class_bound)

        fallback_start_square_sum = current_square_sum - 2
        try:
            next_profile, next_square_sum, empty_classes, _ = _first_eligible_profile(
                start_square_sum=fallback_start_square_sum,
                deadline=stage_a_deadline,
                prior_profiles=prior.profiles | certified_class_profiles,
            )
        except R12FrontierLookupLimit as exc:
            stage_a_stop_reason = f"STAGE_A_NEXT_CURSOR_LIMIT: {exc}"
            has_current_profile = False
            current_active_bound = _family_bound(
                prior=prior,
                class_bounds=certified_class_bounds,
                next_active_bound=coarse_family_bound_for_square_sum(fallback_start_square_sum),
            )
            break
        for empty_class in empty_classes:
            empty_class["CERTIFICATION_STATUS"] = "CERTIFIED_EMPTY_BY_STRUCTURAL_FILTERS"
            class_certificates.append(empty_class)
            certified_class_bounds.append(0)
        if next_profile is None or next_square_sum is None:
            has_current_profile = False
            current_active_bound = _family_bound(
                prior=prior,
                class_bounds=certified_class_bounds,
                next_active_bound=None,
            )
        else:
            current_profile = next_profile
            if next_square_sum >= current_square_sum or (current_square_sum - next_square_sum) % 2:
                raise AssertionError("successive class cursor did not descend by even square sums")
            current_square_sum = next_square_sum
            fallback_start_square_sum = next_square_sum
            next_envelope = coarse_profile_envelope(next_profile)
            current_active_bound = _family_bound(
                prior=prior,
                class_bounds=certified_class_bounds,
                next_active_bound=next_envelope.family_upper_bound,
            )

        if current_active_bound <= INCUMBENT:
            stage_a_success = True
            stage_a_stop_reason = "FAMILY_CLOSED_BY_CLASS_ENVELOPES"
            break
        if START_BOUND - current_active_bound >= STAGE_A_DROP_TARGET:
            stage_a_success = True
            stage_a_stop_reason = "STAGE_A_DROP_TARGET_REACHED"
            break
        certified_count = sum(
            row.get("CERTIFICATION_STATUS")
            in {"CERTIFIED_BELOW_ACTIVE_BOUND", "CERTIFIED_EMPTY_BY_STRUCTURAL_FILTERS"}
            for row in class_certificates
        )
        if certified_count >= 3:
            stage_a_success = True
            stage_a_stop_reason = "THREE_COMPLETE_CLASSES_CERTIFIED"
            break
        if not has_current_profile:
            stage_a_success = True
            stage_a_stop_reason = "NO_REMAINING_ELIGIBLE_CLASS"
            break

    stage_a_wall = monotonic() - stage_a_started
    if stage_a_wall > stage_a_wall_budget_seconds + 0.25:
        raise AssertionError("Stage A exceeded its 25-minute proof wall budget")

    certified_count = sum(
        row.get("CERTIFICATION_STATUS")
        in {"CERTIFIED_BELOW_ACTIVE_BOUND", "CERTIFIED_EMPTY_BY_STRUCTURAL_FILTERS"}
        for row in class_certificates
    )
    next_active_bound = (
        coarse_profile_envelope(current_profile).family_upper_bound if has_current_profile else None
    )
    family_bound = _family_bound(
        prior=prior,
        class_bounds=certified_class_bounds,
        next_active_bound=next_active_bound,
    )
    fallback_result: dict[str, object] | None = None
    if stage_a_success:
        if family_bound <= INCUMBENT:
            task_status = "SUCCESS_A_FAMILY_CLOSED"
            family_status = "CLOSED"
        elif START_BOUND - family_bound >= STAGE_A_DROP_TARGET:
            task_status = "SUCCESS_B_STAGE_A_DROP"
            family_status = "OPEN_STRICTLY_TIGHTENED"
        elif certified_count >= 3:
            task_status = "SUCCESS_C_CLASS_DOMINANCE"
            family_status = "OPEN_STRICTLY_TIGHTENED"
        else:
            task_status = "SUCCESS_C_CLASS_DOMINANCE"
            family_status = "OPEN_STRICTLY_TIGHTENED" if family_bound < START_BOUND else "OPEN"
        stop_reason = stage_a_stop_reason
        fallback_count = 0
        fallback_resolved_count = 0
        total_resolved = PRIOR_RESOLVED_PROFILE_COUNT + eliminated_profile_count
        profile_bounds: list[dict[str, object]] = []
        active_profile_raw: list[int] | None = (
            list(current_profile) if has_current_profile else None
        )
        active_bound = next_active_bound
        rank_lookup: dict[str, object] = {
            "COMPLETE_PROFILES_EXAMINED": sum(
                _require_int(row.get("COMPLETE_PROFILES_EXAMINED", 0), "class profile count")
                for row in class_certificates
            ),
            "SQUARE_SUM_CLASSES_EXAMINED": len(class_certificates),
            "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
            "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        }
    else:
        fallback_started = monotonic()
        fallback_start_profile = current_profile if has_current_profile else None
        if has_current_profile:
            fallback_start_square_sum = current_square_sum
        try:
            fallback_result = _ranked_fallback(
                prior=prior,
                class_profiles=certified_class_profiles,
                class_bounds=certified_class_bounds,
                start_profile=fallback_start_profile,
                start_square_sum=fallback_start_square_sum,
                started=fallback_started,
                deadline=deadline,
                profile_cap=profile_cap,
            )
        except (FrontierLookupLimit, R12FrontierLookupLimit) as exc:
            fallback_result = {
                "TASK_STATUS": "BLOCKED_RANK_LOOKUP_LIMIT",
                "FALLBACK_PROFILE_COUNT": 0,
                "FALLBACK_PROFILE_RESOLVED_COUNT": 0,
                "TOTAL_RESOLVED_PROFILE_COUNT": PRIOR_RESOLVED_PROFILE_COUNT
                + eliminated_profile_count,
                "NEXT_ACTIVE_BOUND": next_active_bound,
                "NEXT_ACTIVE_PROFILE": None
                if fallback_start_profile is None
                else list(fallback_start_profile),
                "FAMILY_UPPER_BOUND": family_bound,
                "REMAINING_GAP": max(0, family_bound - INCUMBENT),
                "FAMILY_STATUS": "OPEN_STRICTLY_TIGHTENED"
                if family_bound < START_BOUND
                else "OPEN",
                "STOP_REASON": f"RANK_LOOKUP_LIMIT: {exc}",
                "PROFILE_BOUNDS": [],
                "RANK_LOOKUP": {
                    "COMPLETE_PROFILES_EXAMINED": 0,
                    "SQUARE_SUM_CLASSES_EXAMINED": 0,
                    "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
                    "FULL_4850_PROFILE_CENSUS_REBUILT": False,
                },
                "LOOKUP_COMPLETE": False,
                "ACTUAL_WALL_TIME_SECONDS": monotonic() - fallback_started,
            }
        task_status = str(fallback_result["TASK_STATUS"])
        family_bound = _require_int(fallback_result.get("FAMILY_UPPER_BOUND"), "family bound")
        family_status = str(fallback_result["FAMILY_STATUS"])
        stop_reason = str(fallback_result["STOP_REASON"])
        fallback_count = _require_int(
            fallback_result.get("FALLBACK_PROFILE_COUNT"), "fallback profile count"
        )
        fallback_resolved_count = _require_int(
            fallback_result.get("FALLBACK_PROFILE_RESOLVED_COUNT"),
            "fallback resolved profile count",
        )
        total_resolved = _require_int(
            fallback_result.get("TOTAL_RESOLVED_PROFILE_COUNT"), "resolved profile count"
        )
        active_bound_raw = fallback_result.get("NEXT_ACTIVE_BOUND")
        active_bound = int(active_bound_raw) if type(active_bound_raw) is int else None
        fallback_next_profile_raw = fallback_result.get("NEXT_ACTIVE_PROFILE")
        active_profile_raw = (
            cast(list[int], fallback_next_profile_raw)
            if isinstance(fallback_next_profile_raw, list)
            else None
        )
        profile_bounds_raw = fallback_result.get("PROFILE_BOUNDS")
        profile_bounds = cast(list[dict[str, object]], profile_bounds_raw)
        rank_lookup_raw = fallback_result.get("RANK_LOOKUP")
        rank_lookup = cast(dict[str, object], rank_lookup_raw)

    cumulative_drop = START_BOUND - family_bound
    if family_bound <= INCUMBENT:
        family_status = "CLOSED"
    elif family_bound < START_BOUND:
        family_status = "OPEN_STRICTLY_TIGHTENED"
    else:
        family_status = "OPEN"
    actual_wall = monotonic() - started
    if actual_wall > proof_wall_budget_seconds:
        raise AssertionError("the 60-minute total proof wall budget was exceeded")
    if fallback_count > FALLBACK_PROFILE_CAP:
        raise AssertionError("fallback exceeded the 72-profile cap")
    if (
        PRIOR_RESOLVED_PROFILE_COUNT + eliminated_profile_count + fallback_resolved_count
        > total_resolved
    ):
        raise AssertionError("resolved profile accounting is inconsistent")
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
        "CLASSES_ANALYZED": len(class_certificates),
        "CLASSES_CERTIFIED": certified_count,
        "CLASS_CERTIFICATES": class_certificates,
        "PROFILES_ELIMINATED_BY_CLASS_BOUND": eliminated_profile_count,
        "FALLBACK_PROFILE_COUNT": fallback_count,
        "FALLBACK_PROFILE_RESOLVED_COUNT": fallback_resolved_count,
        "TOTAL_RESOLVED_PROFILE_COUNT": total_resolved,
        "NEXT_ACTIVE_BOUND": active_bound,
        "NEXT_ACTIVE_PROFILE": active_profile_raw,
        "FAMILY_UPPER_BOUND": family_bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": max(0, family_bound - INCUMBENT),
        "FAMILY_STATUS": family_status,
        "STOP_REASON": stop_reason,
        "STAGE_A_STATUS": stage_a_stop_reason,
        "STAGE_A_WALL_TIME_SECONDS": stage_a_wall,
        "STAGE_A_WALL_BUDGET_SECONDS": stage_a_wall_budget_seconds,
        "FALLBACK_PROFILE_CAP": profile_cap,
        "PRIOR_RESOLVED_PROFILE_COUNT": PRIOR_RESOLVED_PROFILE_COUNT,
        "PRIOR_PROFILE_RERUN_COUNT": 0,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "NO_RERUN_GUARD_STATUS": "PASS",
        "CLASS_ENVELOPE_ORACLE_STATUS": "NOT_RUN",
        "RANKED_FRONTIER_INVARIANT_STATUS": "PASS",
        "FOCUSED_TESTS": "NOT_RUN",
        "RUFF": "NOT_RUN",
        "PYRIGHT": "NOT_RUN",
        "SOLVER_RUNTIME_PREFLIGHT": runtime_preflight,
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "STAGE_A_PROOF_WALL_BUDGET_SECONDS": stage_a_wall_budget_seconds,
            "PROOF_WALL_BUDGET_SECONDS": proof_wall_budget_seconds,
            "CLASS_RELAXATION_SECONDS_PER_HISTOGRAM": CLASS_RELAXATION_WALL_LIMIT_SECONDS,
            "EXTERNAL_HARD_TIMEOUT_SECONDS_PER_PROFILE": EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
            "FALLBACK_PROFILE_CAP": profile_cap,
            "WORKERS": 1,
        },
        "RANK_LOOKUP": rank_lookup,
        "PROFILE_BOUNDS": profile_bounds,
        "FALLBACK_RESULT": fallback_result,
        "ACTUAL_WALL_TIME_SECONDS": actual_wall,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
    }
    return result


def _encode_profile_identity(raw: object, *, name: str) -> str:
    profile = _profile_from_raw(raw, name=name)
    return "".join(str(degree) for degree in profile)


def compact_r14_result(result: dict[str, object]) -> dict[str, object]:
    """Compact profile vectors and redundant histogram fields in the result."""

    compact = result.copy()
    certificates_raw = compact.get("CLASS_CERTIFICATES")
    if not isinstance(certificates_raw, list):
        raise AssertionError("R14 result lacks its class-certificate list")
    certificates: list[dict[str, object]] = []
    for certificate_raw in cast(list[object], certificates_raw):
        if not isinstance(certificate_raw, dict):
            raise AssertionError("R14 class certificate is malformed")
        certificate = cast(dict[str, object], certificate_raw).copy()
        identities_raw = certificate.get("PROFILE_IDENTITIES")
        if isinstance(identities_raw, list):
            certificate["PROFILE_IDENTITIES"] = [
                _encode_profile_identity(profile, name="class profile identity")
                for profile in cast(list[object], identities_raw)
            ]
            certificate["PROFILE_IDENTITY_ENCODING"] = PROFILE_IDENTITY_ENCODING
        upper_raw = certificate.get("UPPER_PROFILE")
        if isinstance(upper_raw, list):
            certificate["UPPER_PROFILE"] = _encode_profile_identity(
                cast(list[object], upper_raw), name="class upper profile"
            )
        histograms_raw = certificate.get("HISTOGRAM_ENVELOPES")
        if isinstance(histograms_raw, list):
            histograms: list[str] = []
            for histogram_raw in cast(list[object], histograms_raw):
                if not isinstance(histogram_raw, dict):
                    raise AssertionError("R14 histogram envelope is malformed")
                histogram = cast(dict[str, object], histogram_raw).copy()
                counts_raw = histogram.get("DEGREE_COUNTS_0_TO_6")
                if not isinstance(counts_raw, list):
                    raise AssertionError("R14 histogram degree counts are malformed")
                counts = cast(list[object], counts_raw)
                if any(type(count) is not int for count in counts):
                    raise AssertionError("R14 histogram degree counts are malformed")
                triangle_raw = histogram.get("TRIANGLE_ENVELOPE")
                triangle = (
                    cast(dict[str, object], triangle_raw) if isinstance(triangle_raw, dict) else {}
                )
                motif_raw = histogram.get("PROFILE_ENVELOPE")
                motif = cast(dict[str, object], motif_raw) if isinstance(motif_raw, dict) else {}
                fields = (
                    ",".join(str(count) for count in cast(list[int], counts)),
                    histogram.get("RELAXATION_STATUS", "-"),
                    histogram.get("SOLVER_WALL_TIME_SECONDS", "-"),
                    histogram.get("WEIGHTED_OPEN_WEDGE_LOWER_BOUND", "-"),
                    histogram.get("LOWER_BOUND_SOURCE", "-"),
                    triangle.get("GRAPH_TRIANGLE_UPPER_BOUND", "-"),
                    motif.get("S3_UPPER_BOUND", "-"),
                    motif.get("S4_LOWER_BOUND", "-"),
                    motif.get("FOURTH_ORDER_CREDIT", "-"),
                    histogram.get("FAMILY_UPPER_BOUND", "-"),
                    motif.get("COARSE_FAMILY_UPPER_BOUND", "-"),
                )
                histograms.append("|".join(str(value) for value in fields))
            certificate["HISTOGRAM_ENVELOPES"] = histograms
            certificate["HISTOGRAM_ROW_ENCODING"] = HISTOGRAM_ROW_ENCODING
        certificates.append(certificate)
    compact["CLASS_CERTIFICATES"] = certificates
    compact["PROFILE_IDENTITY_ENCODING"] = PROFILE_IDENTITY_ENCODING
    compact["HISTOGRAM_ROW_ENCODING"] = HISTOGRAM_ROW_ENCODING
    for field in ("PROFILE_BOUNDS",):
        rows_raw = compact.get(field)
        if isinstance(rows_raw, list):
            rows: list[dict[str, object]] = []
            for row_raw in cast(list[object], rows_raw):
                if not isinstance(row_raw, dict):
                    raise AssertionError("R14 fallback profile row is malformed")
                row = cast(dict[str, object], row_raw).copy()
                profile_raw = row.get("PROFILE")
                if isinstance(profile_raw, list):
                    row["PROFILE"] = _encode_profile_identity(
                        cast(list[object], profile_raw), name="fallback profile identity"
                    )
                    row["PROFILE_IDENTITY_ENCODING"] = PROFILE_IDENTITY_ENCODING
                rows.append(row)
            compact[field] = rows
    fallback_raw = compact.get("FALLBACK_RESULT")
    if isinstance(fallback_raw, dict):
        fallback = cast(dict[str, object], fallback_raw).copy()
        nested_rows = fallback.get("PROFILE_BOUNDS")
        if isinstance(nested_rows, list):
            rows: list[dict[str, object]] = []
            for row_raw in cast(list[object], nested_rows):
                if not isinstance(row_raw, dict):
                    raise AssertionError("nested R14 fallback row is malformed")
                row = cast(dict[str, object], row_raw).copy()
                profile_raw = row.get("PROFILE")
                if isinstance(profile_raw, list):
                    row["PROFILE"] = _encode_profile_identity(
                        cast(list[object], profile_raw), name="nested fallback profile identity"
                    )
                    row["PROFILE_IDENTITY_ENCODING"] = PROFILE_IDENTITY_ENCODING
                rows.append(row)
            fallback["PROFILE_BOUNDS"] = rows
        compact["FALLBACK_RESULT"] = fallback
    return compact


def main() -> None:
    result = compact_r14_result(compute_r14_result())
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


__all__ = [
    "BASE_HEAD",
    "BASE_TREE",
    "FALLBACK_PROFILE_CAP",
    "HISTOGRAM_ROW_ENCODING",
    "INCUMBENT",
    "MINIMUM_SQUARE_SUM",
    "PRIOR_RESOLVED_PROFILE_COUNT",
    "PROFILE_IDENTITY_ENCODING",
    "RESULT_PATH",
    "START_BOUND",
    "START_PROFILE",
    "TASK_BRANCH",
    "TASK_ID",
    "WORKTREE_PATH",
    "assert_ranked_frontier_invariant",
    "canonical_primitive_preflight",
    "certify_square_sum_class",
    "coarse_family_bound_for_square_sum",
    "compact_r14_result",
    "compute_r14_result",
    "lookup_ranked_frontier",
    "validate_prior_frontier_state",
]


if __name__ == "__main__":
    main()
