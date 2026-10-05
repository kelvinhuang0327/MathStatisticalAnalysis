"""Bounded ranked-frontier descent for the K20 minimum-S2 family.

The R10 result pins the first unresolved profile at coarse bound 313733608.
This module follows only that fixed-square-sum suffix and later lower-ranked
square-sum classes, grouping equal coarse bounds and resolving profiles in
the established order. It never reconstructs the 4,850-profile inventory.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_REUSED_S4_LOWER_BOUND,
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
    validate_k20_support_realization,
)
from .b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    CoarseProfileEnvelope,
    ErdosGallaiViolation,
    coarse_profile_envelope,
    profile_shadow_obstruction,
    triple_shadow_degree_sequence,
)
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
    MAX_NEXT_PROFILE_PREFIX_LEAVES,
    NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
    NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
    NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
    SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND,
    _encode_support_rows,  # pyright: ignore[reportPrivateUsage]
    _graph_triangle_count,  # pyright: ignore[reportPrivateUsage]
    _overlap_edges,  # pyright: ignore[reportPrivateUsage]
    _parse_support_rows,  # pyright: ignore[reportPrivateUsage]
    _run_profile_solver,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
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

START_BOUND = 313_733_608
INCUMBENT = 313_239_661
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
    3,
    2,
    2,
    0,
    0,
    0,
    0,
    0,
    0,
)
PROFILE_CAP = 24
CERTIFIED_DROP_TARGET = 50_000
PROOF_WALL_BUDGET_SECONDS = 3_600.0
MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES = MAX_NEXT_PROFILE_PREFIX_LEAVES


class FrontierLookupLimit(RuntimeError):
    """The bounded ranked-frontier lookup could not certify a successor."""


@dataclass(slots=True)
class _LookupCounters:
    complete_profiles_examined: int = 0
    square_sum_classes_examined: int = 0


@dataclass(frozen=True, slots=True)
class RankedFrontier:
    """A bounded, ordered prefix plus exact per-profile coarse keys."""

    profiles: tuple[DegreeProfile, ...]
    envelopes: tuple[CoarseProfileEnvelope, ...]
    complete_profiles_examined: int
    square_sum_classes_examined: int
    lookup_complete: bool


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


def _iter_square_sum_profiles(
    square_sum: int,
    *,
    upper_profile: DegreeProfile | None,
    counters: _LookupCounters,
    deadline: float,
) -> Iterator[DegreeProfile]:
    """Yield eligible profiles in descending lexicographic order for one class."""

    prefix: list[int] = []

    def visit(
        index: int,
        previous_degree: int,
        remaining_sum: int,
        remaining_square_sum: int,
        prefix_sum: int,
        already_below_upper: bool,
    ) -> Iterator[DegreeProfile]:
        if monotonic() >= deadline:
            raise FrontierLookupLimit("proof wall budget expired during rank lookup")
        remaining_slots = K20_TICKET_COUNT - index
        if remaining_slots == 0:
            if remaining_sum != 0 or remaining_square_sum != 0:
                return
            counters.complete_profiles_examined += 1
            if counters.complete_profiles_examined > MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES:
                raise FrontierLookupLimit("rank lookup exceeded its bounded leaf prefix")
            candidate = tuple(prefix)
            if upper_profile is not None and candidate > upper_profile:
                return
            if not linear_triple_degree_sequence_passes_pair_capacity(
                candidate, K20_TRIPLE_SUPPORT_COUNT
            ):
                return
            if not simple_graph_degree_sequence_is_graphical(
                residual_double_ticket_degrees(candidate)
            ):
                return
            yield candidate
            return

        maximum_degree = min(previous_degree, K20_TICKET_CAPACITY, remaining_sum)
        if maximum_degree * remaining_slots < remaining_sum:
            return
        for degree in range(maximum_degree, -1, -1):
            if (
                upper_profile is not None
                and not already_below_upper
                and degree > upper_profile[index]
            ):
                continue
            below_upper = already_below_upper or (
                upper_profile is not None and degree < upper_profile[index]
            )
            suffix_sum = remaining_sum - degree
            suffix_squares = remaining_square_sum - degree**2
            suffix_slots = remaining_slots - 1
            if suffix_sum < 0 or suffix_squares < 0:
                continue
            if suffix_sum > suffix_slots * degree:
                continue
            minimum_squares = _minimum_square_sum(suffix_sum, suffix_slots)
            maximum_squares = _maximum_square_sum(suffix_sum, suffix_slots, degree)
            if (
                minimum_squares is None
                or maximum_squares is None
                or not minimum_squares <= suffix_squares <= maximum_squares
            ):
                continue
            next_prefix_sum = prefix_sum + degree
            if minimum_internal_pair_uses(
                next_prefix_sum, K20_TRIPLE_SUPPORT_COUNT
            ) > comb(index + 1, 2):
                continue
            prefix.append(degree)
            yield from visit(
                index + 1,
                degree,
                suffix_sum,
                suffix_squares,
                next_prefix_sum,
                below_upper,
            )
            prefix.pop()

    yield from visit(
        0,
        K20_TICKET_CAPACITY,
        K20_TRIPLE_SUPPORT_COUNT * 3,
        square_sum,
        0,
        False,
    )


def _rank_key(envelope: CoarseProfileEnvelope) -> tuple[object, ...]:
    """Match R5 ordering: coarse bound, S3, wedge count, then profile."""

    return (
        envelope.family_upper_bound,
        envelope.s3_upper_bound,
        envelope.wedge_count,
        envelope.degree_profile,
    )


def lookup_ranked_frontier(
    *,
    profile_limit: int = PROFILE_CAP + 1,
    deadline: float | None = None,
) -> RankedFrontier:
    """Look up only the ranked suffix required for descent and its next profile."""

    if not 1 <= profile_limit <= PROFILE_CAP + 1:
        raise ValueError("profile_limit must be between one and the cap plus one")
    started = monotonic()
    effective_deadline = deadline if deadline is not None else started + PROOF_WALL_BUDGET_SECONDS
    start_envelope = coarse_profile_envelope(START_PROFILE)
    if start_envelope.family_upper_bound != START_BOUND:
        raise AssertionError("the packet-pinned start bound changed")
    if start_envelope.wedge_count != 834 or sum(value**2 for value in START_PROFILE) != 342:
        raise AssertionError("the packet-pinned active profile left its ranked class")

    counters = _LookupCounters()
    profiles: list[DegreeProfile] = []
    envelopes: list[CoarseProfileEnvelope] = []
    square_sum = 342
    minimum_square_sum = _minimum_square_sum(
        K20_TRIPLE_SUPPORT_COUNT * 3, K20_TICKET_COUNT
    )
    if minimum_square_sum is None:
        raise AssertionError("the minimum profile square sum is unavailable")
    previous_key: tuple[object, ...] | None = None
    first_candidate = True

    while square_sum >= minimum_square_sum:
        counters.square_sum_classes_examined += 1
        upper = START_PROFILE if square_sum == 342 else None
        for profile in _iter_square_sum_profiles(
            square_sum,
            upper_profile=upper,
            counters=counters,
            deadline=effective_deadline,
        ):
            envelope = coarse_profile_envelope(profile)
            key = _rank_key(envelope)
            if previous_key is not None and previous_key < key:
                raise AssertionError("ranked coarse frontier is not monotone")
            if first_candidate:
                if profile != START_PROFILE:
                    raise AssertionError("the packet profile is not the first active rank")
                first_candidate = False
            previous_key = key
            profiles.append(profile)
            envelopes.append(envelope)
            if len(profiles) >= profile_limit:
                return RankedFrontier(
                    tuple(profiles),
                    tuple(envelopes),
                    counters.complete_profiles_examined,
                    counters.square_sum_classes_examined,
                    True,
                )
            if envelope.family_upper_bound <= INCUMBENT:
                return RankedFrontier(
                    tuple(profiles),
                    tuple(envelopes),
                    counters.complete_profiles_examined,
                    counters.square_sum_classes_examined,
                    True,
                )
        square_sum -= 2

    if first_candidate:
        raise FrontierLookupLimit("no eligible profile was found at the packet frontier")
    return RankedFrontier(
        tuple(profiles),
        tuple(envelopes),
        counters.complete_profiles_examined,
        counters.square_sum_classes_examined,
        True,
    )


def group_ranked_plateaus(
    profiles: Sequence[DegreeProfile],
) -> tuple[tuple[int, tuple[DegreeProfile, ...]], ...]:
    """Group a ranked prefix by equal coarse bound while preserving its order."""

    grouped: list[tuple[int, list[DegreeProfile]]] = []
    for profile in profiles:
        bound = coarse_profile_envelope(profile).family_upper_bound
        if not grouped or grouped[-1][0] != bound:
            if any(existing_bound == bound for existing_bound, _ in grouped):
                raise AssertionError("an equal-bound plateau is not contiguous")
            grouped.append((bound, []))
        grouped[-1][1].append(profile)
    return tuple((bound, tuple(items)) for bound, items in grouped)


def _resolution_from_solver(
    profile: DegreeProfile,
    solver_payload: dict[str, object],
    *,
    shadow_obstruction: ErdosGallaiViolation | None,
) -> dict[str, object]:
    """Validate solver witnesses and combine only certified motif relaxations."""

    coarse = coarse_profile_envelope(profile)
    resolution: dict[str, object] = {
        **solver_payload,
        "PROFILE": list(profile),
        "SHADOW_DEGREES": list(triple_shadow_degree_sequence(profile)),
        "SHADOW_OBSTRUCTION": None
        if shadow_obstruction is None
        else asdict(shadow_obstruction),
        "COARSE_FAMILY_UPPER_BOUND": coarse.family_upper_bound,
    }
    realizability = str(solver_payload.get("REALIZABILITY", "UNRESOLVED"))
    resolution["REALIZABILITY"] = realizability
    if realizability == "UNREALIZABLE":
        resolution["FAMILY_UPPER_BOUND"] = None
        return resolution
    if realizability != "REALIZABLE":
        resolution["FAMILY_UPPER_BOUND"] = None
        return resolution

    support_raw = solver_payload.get("WITNESS_TRIPLES")
    double_raw = solver_payload.get("WITNESS_DOUBLE_SUPPORTS")
    if support_raw is None or double_raw is None:
        raise AssertionError("a realizable profile lacks its support witness")
    triples = cast(tuple[Triple, ...], _parse_support_rows(support_raw, 3))
    doubles = cast(tuple[Pair, ...], _parse_support_rows(double_raw, 2))
    signature = validate_k20_support_realization(triples, doubles, profile)
    if asdict(signature) != solver_payload.get("WITNESS_MOTIFS"):
        raise AssertionError("the support solver witness motif signature changed")
    if len(doubles) != K20_DOUBLE_SUPPORT_COUNT:
        raise AssertionError("the residual 27-double-support capacity changed")

    motif_raw = solver_payload.get("MOTIF_SOLVER")
    class_raw = solver_payload.get("DEGREE_CLASS_RELAXATION")
    if not isinstance(motif_raw, dict) or not isinstance(class_raw, dict):
        raise AssertionError("a realizable profile lacks its motif relaxations")
    motif = cast(dict[str, object], motif_raw)
    degree_class = cast(dict[str, object], class_raw)

    triangle_bounds = [coarse.graph_triangle_upper_bound]
    motif_bound = motif.get("SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND")
    if isinstance(motif_bound, int):
        triangle_bounds.append(motif_bound)
    class_bound = degree_class.get("GRAPH_TRIANGLE_UPPER_BOUND")
    if isinstance(class_bound, int):
        triangle_bounds.append(class_bound)
    triangle_bound = min(triangle_bounds)
    if triangle_bound < K20_TRIPLE_SUPPORT_COUNT:
        raise AssertionError("a triangle certificate is below the 22 core triangles")

    motif_triples_raw = motif.get("MOTIF_WITNESS_TRIPLES")
    motif_doubles_raw = motif.get("MOTIF_WITNESS_DOUBLE_SUPPORTS")
    if motif_triples_raw is not None and motif_doubles_raw is not None:
        motif_triples = cast(tuple[Triple, ...], _parse_support_rows(motif_triples_raw, 3))
        motif_doubles = cast(tuple[Pair, ...], _parse_support_rows(motif_doubles_raw, 2))
        motif_signature = validate_k20_support_realization(
            motif_triples, motif_doubles, profile
        )
        witness_triangles = _graph_triangle_count(
            _overlap_edges(motif_triples, motif_doubles)
        )
        if motif.get("WITNESS_GRAPH_TRIANGLE_COUNT") != witness_triangles:
            raise AssertionError("the optimized motif witness triangle count changed")
        if isinstance(motif_bound, int) and motif_bound < witness_triangles:
            raise AssertionError("a certified motif upper bound excludes its witness")
        resolution["MOTIF_WITNESS_SIGNATURE"] = asdict(motif_signature)

    wedge_count = overlap_wedge_count(profile)
    noncore_triangle_bound = triangle_bound - K20_TRIPLE_SUPPORT_COUNT
    s3_bound = s3_sum_from_wedges_and_triangles(wedge_count, noncore_triangle_bound)
    s4_bound = max(
        K20_REUSED_S4_LOWER_BOUND,
        SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND if profile.count(0) == 7 else 0,
    )
    fourth_order_credit = (4 * s4_bound) // 7
    family_bound = K20_S1 - K20_S2 + s3_bound - fourth_order_credit
    if family_bound > coarse.family_upper_bound:
        raise AssertionError("the certified motif envelope exceeds its coarse bound")
    resolution.update(
        {
            "WEDGE_COUNT": wedge_count,
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
    return resolution


def _resolve_profile(profile: DegreeProfile, *, remaining_wall: float) -> dict[str, object]:
    obstruction = profile_shadow_obstruction(profile)
    if obstruction is not None:
        return {
            "PROFILE": list(profile),
            "SHADOW_DEGREES": list(triple_shadow_degree_sequence(profile)),
            "SHADOW_OBSTRUCTION": asdict(obstruction),
            "SUPPORT_SOLVER_STATUS": "NOT_RUN_SHADOW_OBSTRUCTION",
            "REALIZABILITY": "UNREALIZABLE",
            "COARSE_FAMILY_UPPER_BOUND": coarse_profile_envelope(profile).family_upper_bound,
            "FAMILY_UPPER_BOUND": None,
        }
    if remaining_wall <= 0:
        return {
            "PROFILE": list(profile),
            "REALIZABILITY": "UNRESOLVED",
            "SUPPORT_SOLVER_STATUS": "NOT_RUN_WALL_BUDGET",
            "COARSE_FAMILY_UPPER_BOUND": coarse_profile_envelope(profile).family_upper_bound,
            "FAMILY_UPPER_BOUND": None,
        }
    payload = _run_profile_solver(
        profile,
        external_timeout_seconds=min(
            EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS, remaining_wall
        ),
        support_wall_limit_seconds=NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
        motif_wall_limit_seconds=NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
        degree_class_wall_limit_seconds=NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
    )
    return _resolution_from_solver(
        profile, payload, shadow_obstruction=obstruction
    )


def _solver_statuses(profile_bounds: Sequence[dict[str, object]]) -> str:
    statuses: set[str] = set()
    for item in profile_bounds:
        statuses.add(str(item.get("SUPPORT_SOLVER_STATUS", "NOT_RUN")))
        for name in ("MOTIF_SOLVER", "DEGREE_CLASS_RELAXATION"):
            nested = item.get(name)
            if isinstance(nested, dict):
                mapping = cast(dict[str, object], nested)
                statuses.add(str(mapping.get("SOLVER_STATUS", "NOT_RUN")))
    return ", ".join(sorted(statuses)) if statuses else "NOT_RUN"


def compute_budgeted_descent_result(
    *,
    profile_cap: int = PROFILE_CAP,
    proof_wall_budget_seconds: float = PROOF_WALL_BUDGET_SECONDS,
) -> dict[str, object]:
    """Resolve successive complete plateaus up to the packet stop conditions."""

    if not 1 <= profile_cap <= PROFILE_CAP:
        raise ValueError("profile_cap must be between one and twenty-four")
    if proof_wall_budget_seconds <= 0:
        raise ValueError("proof_wall_budget_seconds must be positive")
    started = monotonic()
    deadline = started + proof_wall_budget_seconds
    try:
        frontier = lookup_ranked_frontier(
            profile_limit=profile_cap + 1, deadline=deadline
        )
    except FrontierLookupLimit as exc:
        return {
            "TASK_ID": "B649_K20_MIN_S2_BUDGETED_MULTI_PLATEAU_DESCENT_R11",
            "TASK_STATUS": "BLOCKED_RANK_LOOKUP_LIMIT",
            "START_BOUND": START_BOUND,
            "END_BOUND": START_BOUND,
            "CUMULATIVE_DROP": 0,
            "PROFILE_CAP": profile_cap,
            "ACTUAL_PROFILE_COUNT": 0,
            "PROOF_WALL_BUDGET_SECONDS": proof_wall_budget_seconds,
            "ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
            "RANK_LOOKUP_STATUS": str(exc),
            "NEXT_ACTIVE_BOUND": START_BOUND,
            "NEXT_ACTIVE_PROFILE": list(START_PROFILE),
            "PROFILE_BOUNDS": [],
        }

    profile_bounds: list[dict[str, object]] = []
    realized_bounds: list[int] = []
    unrealizable_count = 0
    realizable_count = 0
    processed_plateau_bounds: list[int] = []
    exhausted_plateau_bounds: list[int] = []
    stop_reason = "PROFILE_CAP_REACHED"
    unresolved = False

    for rank_index, profile in enumerate(frontier.profiles[:profile_cap]):
        elapsed = monotonic() - started
        if elapsed >= proof_wall_budget_seconds:
            stop_reason = "PROOF_WALL_BUDGET_REACHED"
            break
        resolution: dict[str, object]
        try:
            resolution = _resolve_profile(
                profile, remaining_wall=proof_wall_budget_seconds - elapsed
            )
        except TimeoutError:
            resolution = {
                "PROFILE": list(profile),
                "REALIZABILITY": "UNRESOLVED",
                "SUPPORT_SOLVER_STATUS": "EXTERNAL_HARD_TIMEOUT",
                "COARSE_FAMILY_UPPER_BOUND": frontier.envelopes[rank_index].family_upper_bound,
                "FAMILY_UPPER_BOUND": None,
            }
        resolution["RANK_INDEX"] = rank_index
        resolution["RANKED_COARSE_BOUND"] = frontier.envelopes[
            rank_index
        ].family_upper_bound
        profile_bounds.append(resolution)
        if resolution["REALIZABILITY"] == "UNRESOLVED":
            unresolved = True
            stop_reason = (
                "PROOF_WALL_BUDGET_REACHED"
                if monotonic() >= deadline
                else "SOLVER_UNRESOLVED"
            )
            break
        if resolution["REALIZABILITY"] == "UNREALIZABLE":
            unrealizable_count += 1
        elif resolution["REALIZABILITY"] == "REALIZABLE":
            realizable_count += 1
            bound = resolution.get("FAMILY_UPPER_BOUND")
            if not isinstance(bound, int):
                raise AssertionError("a realizable profile lacks its certified family bound")
            realized_bounds.append(bound)
        else:
            raise AssertionError("profile solver returned an unknown realizability state")

        plateau_bound = frontier.envelopes[rank_index].family_upper_bound
        if not processed_plateau_bounds or processed_plateau_bounds[-1] != plateau_bound:
            processed_plateau_bounds.append(plateau_bound)

        next_index = rank_index + 1
        next_profile = (
            frontier.profiles[next_index]
            if next_index < len(frontier.profiles)
            else None
        )
        next_bound = (
            frontier.envelopes[next_index].family_upper_bound
            if next_index < len(frontier.envelopes)
            else 0
        )
        if next_profile is None or next_bound < plateau_bound:
            exhausted_plateau_bounds.append(plateau_bound)

        family_bound = max([*realized_bounds, next_bound])
        cumulative_drop = START_BOUND - family_bound
        if family_bound <= INCUMBENT:
            stop_reason = "FAMILY_CLOSED"
            break
        if cumulative_drop >= CERTIFIED_DROP_TARGET:
            stop_reason = "CERTIFIED_DROP_TARGET_REACHED"
            break
        if len(profile_bounds) >= profile_cap:
            stop_reason = "PROFILE_CAP_REACHED"
            break
    else:
        family_bound = max(
            [
                *realized_bounds,
                frontier.envelopes[len(profile_bounds)].family_upper_bound
                if len(profile_bounds) < len(frontier.envelopes)
                else 0,
            ]
        )

    next_index = len(profile_bounds) - 1 if unresolved else len(profile_bounds)
    next_profile = (
        frontier.profiles[next_index]
        if next_index < len(frontier.profiles)
        else None
    )
    next_envelope = (
        frontier.envelopes[next_index]
        if next_index < len(frontier.envelopes)
        else None
    )
    if next_envelope is None:
        family_bound = max(realized_bounds, default=0)
    else:
        family_bound = max(max(realized_bounds, default=0), next_envelope.family_upper_bound)
    cumulative_drop = START_BOUND - family_bound
    if family_bound <= INCUMBENT:
        family_status = "CLOSED"
        task_status = "SUCCESS_A_FAMILY_CLOSED"
    elif cumulative_drop >= CERTIFIED_DROP_TARGET:
        family_status = "OPEN_STRICTLY_TIGHTENED"
        task_status = "SUCCESS_B_CERTIFIED_DROP"
    elif stop_reason == "PROFILE_CAP_REACHED" and not unresolved:
        family_status = "OPEN_STRICTLY_TIGHTENED" if cumulative_drop > 0 else "OPEN"
        task_status = "SUCCESS_C_PROFILE_CAP"
    elif stop_reason == "PROOF_WALL_BUDGET_REACHED" and not unresolved:
        family_status = "OPEN_STRICTLY_TIGHTENED" if cumulative_drop > 0 else "OPEN"
        task_status = "SUCCESS_C_PROOF_WALL_BUDGET"
    else:
        family_status = "OPEN_STRICTLY_TIGHTENED" if cumulative_drop > 0 else "OPEN"
        task_status = "BLOCKED_SOLVER_UNRESOLVED"

    actual_wall = monotonic() - started
    return {
        "TASK_ID": "B649_K20_MIN_S2_BUDGETED_MULTI_PLATEAU_DESCENT_R11",
        "TASK_STATUS": task_status,
        "BASE_HEAD": "906deaa00504601068bdae06583042f28c230f19",
        "BASE_TREE": "68e4bba672918c6810aa08da5ee9939acb29b55a",
        "TASK_BRANCH": "codex/b649-k20-min-s2-budgeted-multi-plateau-descent-r11",
        "WORKTREE_PATH": (
            "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
            "B649_K20_MIN_S2_BUDGETED_MULTI_PLATEAU_DESCENT_R11"
        ),
        "WORKTREE_DISPOSITION": "RETAIN",
        "START_BOUND": START_BOUND,
        "END_BOUND": family_bound,
        "CUMULATIVE_DROP": cumulative_drop,
        "PLATEAU_COUNT_PROCESSED": len(processed_plateau_bounds),
        "PLATEAU_COUNT_EXHAUSTED": len(exhausted_plateau_bounds),
        "PROCESSED_PLATEAU_BOUNDS": processed_plateau_bounds,
        "PROFILE_COUNT_PROCESSED": unrealizable_count + realizable_count,
        "UNREALIZABLE_PROFILE_COUNT": unrealizable_count,
        "REALIZABLE_PROFILE_COUNT": realizable_count,
        "PROFILE_CAP": profile_cap,
        "ACTUAL_PROFILE_COUNT": unrealizable_count + realizable_count,
        "PROOF_WALL_BUDGET_SECONDS": proof_wall_budget_seconds,
        "ACTUAL_WALL_TIME_SECONDS": actual_wall,
        "RANK_LOOKUP": {
            "COMPLETE_PROFILES_EXAMINED": frontier.complete_profiles_examined,
            "SQUARE_SUM_CLASSES_EXAMINED": frontier.square_sum_classes_examined,
            "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
            "FULL_4850_PROFILE_RANKING_RERUN": False,
        },
        "NEXT_ACTIVE_BOUND": None if next_envelope is None else next_envelope.family_upper_bound,
        "NEXT_ACTIVE_PROFILE": None if next_profile is None else list(next_profile),
        "NEXT_ACTIVE_WEDGE_COUNT": None if next_envelope is None else next_envelope.wedge_count,
        "FAMILY_UPPER_BOUND": family_bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_FAMILY_GAP": max(0, family_bound - INCUMBENT),
        "FAMILY_STATUS": family_status,
        "STOP_REASON": stop_reason,
        "SOLVER_STATUS": _solver_statuses(profile_bounds),
        "SOLVER_CERTIFIED_BOUND": family_bound,
        "SOLVER_LIMITS": {
            "NATIVE_SUPPORT_SECONDS_PER_PROFILE": NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_MOTIF_SECONDS_PER_PROFILE": NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_DEGREE_CLASS_SECONDS_PER_PROFILE": NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
            "EXTERNAL_HARD_TIMEOUT_SECONDS_PER_PROFILE": EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
            "WORKERS": 1,
        },
        "PROFILE_BOUNDS": profile_bounds,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def compact_descent_result(result: dict[str, object]) -> dict[str, object]:
    """Serialize support witnesses with R10's regression-tested row encoding."""

    compact = dict(result)
    raw_profiles = result.get("PROFILE_BOUNDS")
    if not isinstance(raw_profiles, list):
        raise TypeError("profile result list is missing")
    compact_profiles: list[dict[str, object]] = []
    for raw_profile in cast(list[object], raw_profiles):
        if not isinstance(raw_profile, dict):
            raise TypeError("profile result must be an object")
        item = cast(dict[str, object], raw_profile).copy()
        for field in ("WITNESS_TRIPLES", "WITNESS_DOUBLE_SUPPORTS"):
            if field in item:
                item[field] = _encode_support_rows(item[field])
        motif_raw = item.get("MOTIF_SOLVER")
        if motif_raw is not None:
            if not isinstance(motif_raw, dict):
                raise TypeError("motif solver result must be an object")
            motif = cast(dict[str, object], motif_raw).copy()
            for field in ("MOTIF_WITNESS_TRIPLES", "MOTIF_WITNESS_DOUBLE_SUPPORTS"):
                if field in motif:
                    motif[field] = _encode_support_rows(motif[field])
            item["MOTIF_SOLVER"] = motif
        compact_profiles.append(item)
    compact["PROFILE_BOUNDS"] = compact_profiles
    return compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-result", required=True)
    parser.add_argument(
        "--proof-wall-budget-seconds",
        type=float,
        default=PROOF_WALL_BUDGET_SECONDS,
    )
    parser.add_argument("--profile-cap", type=int, default=PROFILE_CAP)
    args = parser.parse_args()
    result = compact_descent_result(
        compute_budgeted_descent_result(
            profile_cap=args.profile_cap,
            proof_wall_budget_seconds=args.proof_wall_budget_seconds,
        )
    )
    output_path = Path(args.write_result)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary = {
        key: result[key]
        for key in (
            "TASK_STATUS",
            "START_BOUND",
            "END_BOUND",
            "CUMULATIVE_DROP",
            "PLATEAU_COUNT_PROCESSED",
            "PROFILE_COUNT_PROCESSED",
            "NEXT_ACTIVE_BOUND",
            "NEXT_ACTIVE_PROFILE",
            "ACTUAL_WALL_TIME_SECONDS",
        )
        if key in result
    }
    print(json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
