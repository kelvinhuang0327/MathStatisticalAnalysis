"""Descend the load-bearing K20 minimum-S2 cursor plateau (R16).

The R15 result is the active-family authority at the pinned base. Its exact
cursor is used below; the packet's square-sum-332 profile is already covered
by R14's complete class certificate. R15's two refined owner profiles remain
in the resolved ledger and are rejected by every new profile-solve path.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    assert_no_prior_profile_rerun,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
    MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
    NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
    NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
    NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
    FrontierLookupLimit,
    compact_descent_result,
    solver_runtime_preflight,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    _resolve_profile as resolve_profile,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    canonical_primitive_preflight,
    reconstruct_family_max_ledger,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_INCUMBENT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
)
from .b649_k20_min_s2_successive_class_dominance_r14 import (
    RankedFrontier,
    certify_square_sum_class,
    lookup_ranked_frontier,
)
from .b649_k20_min_s2_successive_class_dominance_r14 import (
    _first_eligible_profile as first_eligible_profile,  # pyright: ignore[reportPrivateUsage]
)

DegreeProfile = tuple[int, ...]

TASK_ID = "B649_K20_MIN_S2_LOAD_BEARING_PLATEAU_DESCENT_R16"
TASK_BRANCH = "codex/b649-k20-min-s2-load-bearing-plateau-descent-r16"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_MIN_S2_LOAD_BEARING_PLATEAU_DESCENT_R16"
)
BASE_HEAD = "b7ad9b4e85c09ae8a1816696c035b80deb884072"
BASE_TREE = "34f903fa220ec4bd6ff582882e897a04da050556"
START_BOUND = 313_675_592
INCUMBENT = K20_INCUMBENT
EXPECTED_GAP = 435_931
CERTIFIED_DROP_TARGET = 50_000
MAX_PROFILE_RESOLVES = 48
MAX_GENERIC_CLASS_ELIMINATIONS = 3
MAX_PROOF_WALL_SECONDS = 3_580.0
MAX_PLATEAU_LOOKUP_PROFILES = 256
INITIAL_PLATEAU_LOOKUP_PROFILES = 8
EXPECTED_RESOLVED_PROFILE_COUNT = 179
EXPECTED_R15_CURSOR: DegreeProfile = (
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
    3,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    0,
)
PACKET_PROFILE: DegreeProfile = (
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
R15_RESULT_NAME = "b649-k20-min-s2-current-bound-owner-refinement-r15-result.json"
R14_RESULT_NAME = "b649-k20-min-s2-successive-class-dominance-r14-result.json"
RESULT_FILENAME = "b649-k20-min-s2-load-bearing-plateau-descent-r16-result.json"


@dataclass(frozen=True, slots=True)
class CurrentState:
    """R15's resolved ledger, refined owners, and active unresolved cursor."""

    prior_profiles: frozenset[DegreeProfile]
    prior_family_bound: int
    prior_family_bound_owner_profiles: tuple[DegreeProfile, ...]
    cursor_profile: DegreeProfile
    cursor_bound: int
    owner_profiles: tuple[DegreeProfile, ...]
    packet_profile_class_certificate: dict[str, object]


@dataclass(frozen=True, slots=True)
class PlateauFrontier:
    """A complete ranked prefix through one entire coarse-bound plateau."""

    bound: int
    profiles: tuple[DegreeProfile, ...]
    next_profile: DegreeProfile | None
    next_bound: int | None
    lookup_profile_count: int
    complete_profiles_examined: int
    square_sum_classes_examined: int
    lookup_complete: bool
    frontier: RankedFrontier


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _result_path(name: str) -> Path:
    return _repo_root() / "docs" / "research" / "matrix-native-results" / name


def _read_json(name: str) -> dict[str, object]:
    value: object = json.loads(_result_path(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"committed result {name} must be a JSON object")
    return cast(dict[str, object], value)


def _profile(raw: object, *, name: str) -> DegreeProfile:
    if isinstance(raw, str):
        if len(raw) != K20_TICKET_COUNT or not raw.isdecimal():
            raise AssertionError(f"{name} must be a twenty-digit degree profile")
        values = tuple(int(value) for value in raw)
    elif isinstance(raw, list):
        values_raw = cast(list[object], raw)
        if len(values_raw) != K20_TICKET_COUNT or any(
            type(value) is not int for value in values_raw
        ):
            raise AssertionError(f"{name} must contain twenty integer degrees")
        values = tuple(cast(int, value) for value in values_raw)
    else:
        raise AssertionError(f"{name} must be a profile array or compact identity")
    if tuple(sorted(values, reverse=True)) != values:
        raise AssertionError(f"{name} must be nonincreasing")
    if any(not 0 <= degree <= K20_TICKET_CAPACITY for degree in values):
        raise AssertionError(f"{name} contains a degree outside 0..6")
    if sum(values) != K20_TRIPLE_INCIDENCE_COUNT:
        raise AssertionError(f"{name} must sum to {K20_TRIPLE_INCIDENCE_COUNT}")
    return values


def profile_identity(profile: DegreeProfile) -> str:
    return "".join(str(degree) for degree in profile)


def _require_int(value: object, *, name: str) -> int:
    if type(value) is not int:
        raise AssertionError(f"{name} must be an integer")
    return value


def _current_state() -> CurrentState:
    """Validate the exact R15 cursor without invoking any profile solver."""

    r15 = _read_json(R15_RESULT_NAME)
    r14 = _read_json(R14_RESULT_NAME)
    ledger = reconstruct_family_max_ledger()
    if r15.get("TASK_STATUS") != "SUCCESS_B_CURSOR_LOAD_BEARING":
        raise AssertionError("R15 did not complete the cursor-load-bearing handoff")
    if _require_int(r15.get("FAMILY_UPPER_BOUND"), name="R15 family bound") != START_BOUND:
        raise AssertionError("R15 family bound does not match the R16 start bound")
    if _require_int(r15.get("INCUMBENT"), name="R15 incumbent") != INCUMBENT:
        raise AssertionError("R15 incumbent does not match the R16 incumbent")
    if _require_int(r15.get("REMAINING_GAP"), name="R15 remaining gap") != EXPECTED_GAP:
        raise AssertionError("R15 remaining gap does not match the R16 packet")

    cursor = _profile(r15.get("NEXT_CURSOR_PROFILE"), name="R15 next cursor")
    cursor_bound = _require_int(r15.get("NEXT_CURSOR_BOUND"), name="R15 cursor bound")
    if cursor != EXPECTED_R15_CURSOR or cursor != ledger.next_cursor_profile:
        raise AssertionError("R15 result, reconstructed ledger, and expected cursor disagree")
    if cursor_bound != START_BOUND or cursor_bound != ledger.next_cursor_bound:
        raise AssertionError("R15 cursor bound does not match the R16 start bound")
    if coarse_profile_envelope(cursor).family_upper_bound != cursor_bound:
        raise AssertionError("R15 cursor envelope does not reproduce the active bound")

    raw_owner_profiles = r15.get("REFINED_LOAD_BEARING_PROFILES")
    raw_owner_rows = r15.get("OWNER_PROFILE_BOUNDS")
    if not isinstance(raw_owner_profiles, list) or not isinstance(raw_owner_rows, list):
        raise AssertionError("R15 lacks its resolved owner profile ledger")
    owner_profiles = tuple(
        _profile(raw, name="R15 refined owner") for raw in cast(list[object], raw_owner_profiles)
    )
    if len(owner_profiles) != 2 or len(set(owner_profiles)) != 2:
        raise AssertionError("R15 must contribute exactly two distinct refined owner profiles")

    prior_records = {record.profile: record for record in ledger.records}
    prior_profiles = frozenset(prior_records)
    if len(prior_profiles) != EXPECTED_RESOLVED_PROFILE_COUNT:
        raise AssertionError("R15 resolved-profile identity ledger has the wrong size")
    for owner in owner_profiles:
        if owner not in prior_profiles:
            raise AssertionError("an R15 refined owner is absent from the prior profile ledger")

    owner_bound_overrides: dict[DegreeProfile, int] = {}
    owner_row_profiles: list[DegreeProfile] = []
    for index, raw_row in enumerate(cast(list[object], raw_owner_rows)):
        if not isinstance(raw_row, dict):
            raise AssertionError(f"R15 owner row {index} is malformed")
        row = cast(dict[str, object], raw_row)
        owner = _profile(row.get("PROFILE"), name=f"R15 owner row {index} profile")
        owner_row_profiles.append(owner)
        owner_bound_overrides[owner] = _require_int(
            row.get("FAMILY_UPPER_BOUND"), name=f"R15 owner row {index} family bound"
        )
    if set(owner_row_profiles) != set(owner_profiles):
        raise AssertionError("R15 refined owner names and bound rows disagree")

    prior_bounds = {
        profile: owner_bound_overrides.get(profile, record.family_upper_bound)
        for profile, record in prior_records.items()
    }
    prior_family_bound = max(prior_bounds.values())
    prior_family_bound_owner_profiles = tuple(
        sorted(
            (profile for profile, bound in prior_bounds.items() if bound == prior_family_bound),
            reverse=True,
        )
    )
    if prior_family_bound >= START_BOUND:
        raise AssertionError("a resolved R15 profile still owns the R16 active family bound")

    raw_certificates = r14.get("CLASS_CERTIFICATES")
    if not isinstance(raw_certificates, list):
        raise AssertionError("R14 class certificates are missing")
    packet_square_sum = sum(degree**2 for degree in PACKET_PROFILE)
    matching_certificates: list[dict[str, object]] = []
    for raw_certificate in cast(list[object], raw_certificates):
        if not isinstance(raw_certificate, dict):
            continue
        certificate = cast(dict[str, object], raw_certificate)
        if certificate.get("SQUARE_SUM") == packet_square_sum:
            matching_certificates.append(certificate)
    if len(matching_certificates) != 1:
        raise AssertionError("R14 does not have one complete certificate for packet square-sum 332")
    packet_class = matching_certificates[0]
    raw_packet_ids = packet_class.get("PROFILE_IDENTITIES")
    if not isinstance(raw_packet_ids, list):
        raise AssertionError("R14 square-sum-332 certificate lacks profile identities")
    packet_class_profiles = {
        _profile(raw, name="R14 square-sum-332 profile")
        for raw in cast(list[object], raw_packet_ids)
    }
    packet_class_bound = _require_int(
        packet_class.get("CLASS_FAMILY_UPPER_BOUND"), name="R14 square-sum-332 class bound"
    )
    if PACKET_PROFILE not in packet_class_profiles or PACKET_PROFILE not in prior_profiles:
        raise AssertionError("packet profile is not covered by the committed R14 class certificate")
    if packet_class.get("COMPLETE_SUFFIX_ENUMERATION") is not True:
        raise AssertionError("R14 packet-profile class certificate is incomplete")
    if packet_class_bound >= START_BOUND:
        raise AssertionError("R14 packet-profile class certificate does not fall below the cursor")

    return CurrentState(
        prior_profiles=prior_profiles,
        prior_family_bound=prior_family_bound,
        prior_family_bound_owner_profiles=prior_family_bound_owner_profiles,
        cursor_profile=cursor,
        cursor_bound=cursor_bound,
        owner_profiles=owner_profiles,
        packet_profile_class_certificate={
            "PROFILE": profile_identity(PACKET_PROFILE),
            "SQUARE_SUM": packet_square_sum,
            "PROFILE_COUNT": len(packet_class_profiles),
            "CLASS_FAMILY_UPPER_BOUND": packet_class_bound,
            "CERTIFICATION_STATUS": packet_class.get("CERTIFICATION_STATUS"),
            "REUSED_FROM": "R14.CLASS_CERTIFICATES[SQUARE_SUM=332]",
        },
    )


def freeze_current_plateau(
    *,
    cursor: DegreeProfile,
    active_bound: int,
    prior_profiles: Collection[DegreeProfile],
    deadline: float,
) -> PlateauFrontier:
    """Find every ranked profile at active_bound and the first lower cursor."""

    if coarse_profile_envelope(cursor).family_upper_bound != active_bound:
        raise AssertionError("plateau cursor does not own the active coarse bound")
    square_sum = sum(degree**2 for degree in cursor)
    profile_limit = INITIAL_PLATEAU_LOOKUP_PROFILES
    while True:
        frontier = lookup_ranked_frontier(
            start_profile=cursor,
            start_square_sum=square_sum,
            profile_limit=profile_limit,
            deadline=deadline,
            prior_profiles=prior_profiles,
        )
        if not frontier.profiles or frontier.profiles[0] != cursor:
            raise AssertionError("ranked frontier does not begin at the active cursor")
        bounds = tuple(envelope.family_upper_bound for envelope in frontier.envelopes)
        if any(bound > active_bound for bound in bounds):
            raise AssertionError("an unresolved ranked profile exceeds the active family bound")
        first_lower = next(
            (index for index, bound in enumerate(bounds) if bound < active_bound), None
        )
        if first_lower is not None:
            if first_lower == 0:
                raise AssertionError("active cursor is not part of its own coarse-bound plateau")
            plateau = frontier.profiles[:first_lower]
            return PlateauFrontier(
                bound=active_bound,
                profiles=plateau,
                next_profile=frontier.profiles[first_lower],
                next_bound=bounds[first_lower],
                lookup_profile_count=len(frontier.profiles),
                complete_profiles_examined=frontier.complete_profiles_examined,
                square_sum_classes_examined=frontier.square_sum_classes_examined,
                lookup_complete=frontier.lookup_complete,
                frontier=frontier,
            )
        if frontier.lookup_complete:
            return PlateauFrontier(
                bound=active_bound,
                profiles=frontier.profiles,
                next_profile=None,
                next_bound=None,
                lookup_profile_count=len(frontier.profiles),
                complete_profiles_examined=frontier.complete_profiles_examined,
                square_sum_classes_examined=frontier.square_sum_classes_examined,
                lookup_complete=True,
                frontier=frontier,
            )
        if profile_limit >= MAX_PLATEAU_LOOKUP_PROFILES:
            raise FrontierLookupLimit(
                "the active coarse-bound plateau did not end within the bounded lookup prefix"
            )
        profile_limit = min(MAX_PLATEAU_LOOKUP_PROFILES, profile_limit * 2)


def _profile_family_bound(row: dict[str, object]) -> int | None:
    raw = row.get("FAMILY_UPPER_BOUND")
    return raw if type(raw) is int else None


def _family_bound(
    *,
    prior_bound: int,
    profile_rows: Sequence[dict[str, object]],
    next_profile: DegreeProfile | None,
) -> int:
    bounds = [prior_bound]
    bounds.extend(
        bound
        for row in profile_rows
        if (bound := _profile_family_bound(row)) is not None
    )
    if next_profile is not None:
        bounds.append(coarse_profile_envelope(next_profile).family_upper_bound)
    return max(bounds, default=0)


def _terminal_reason(
    *,
    family_bound: int,
    start_bound: int,
    incumbent: int,
    certified_classes: int,
    resolved_profiles: int,
    deadline: float,
) -> str | None:
    if family_bound <= incumbent:
        return "FAMILY_CLOSED"
    if start_bound - family_bound >= CERTIFIED_DROP_TARGET:
        return "CERTIFIED_DROP_TARGET_REACHED"
    if certified_classes >= MAX_GENERIC_CLASS_ELIMINATIONS:
        return "THREE_COMPLETE_CLASSES_ELIMINATED_GENERALLY"
    if resolved_profiles >= MAX_PROFILE_RESOLVES:
        return "PROFILE_CAP_REACHED"
    if monotonic() >= deadline:
        return "PROOF_WALL_BUDGET_REACHED"
    return None


def _task_status(stop_reason: str) -> str:
    return {
        "FAMILY_CLOSED": "SUCCESS_A_FAMILY_CLOSED",
        "CERTIFIED_DROP_TARGET_REACHED": "SUCCESS_B_CERTIFIED_DROP",
        "THREE_COMPLETE_CLASSES_ELIMINATED_GENERALLY": "SUCCESS_C_THREE_CLASSES",
        "PROFILE_CAP_REACHED": "SUCCESS_D_PROFILE_CAP",
        "PROOF_WALL_BUDGET_REACHED": "SUCCESS_E_WALL_BUDGET",
        "CURRENT_PLATEAU_RESOLVED_EXACT_CURSOR": "SUCCESS_C_EXACT_CURSOR",
        "CURRENT_CURSOR_NOT_FAMILY_BOUND": "SUCCESS_C_EXACT_CURSOR",
        "SOLVER_UNRESOLVED": "BLOCKED_SOLVER_UNRESOLVED",
        "RANK_LOOKUP_LIMIT": "BLOCKED_RANK_LOOKUP_LIMIT",
        "NO_ACTIVE_CURSOR": "SUCCESS_C_EXACT_CURSOR",
    }.get(stop_reason, "BLOCKED_INCOMPLETE")


def _empty_class_records(
    empty_classes: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for raw in empty_classes:
        record = raw.copy()
        record["CERTIFICATION_STATUS"] = "CERTIFIED_EMPTY_BY_STRUCTURAL_FILTERS"
        record["CLASS_CERTIFICATE_KIND"] = "COMPLETE_SQUARE_SUM_STRUCTURAL_FILTER"
        records.append(record)
    return records


def compute_load_bearing_plateau_result(
    *,
    proof_wall_budget_seconds: float = MAX_PROOF_WALL_SECONDS,
    profile_cap: int = MAX_PROFILE_RESOLVES,
) -> dict[str, object]:
    """Certify successive R15 cursor plateaus within the R16 task limits."""

    if not 0 < proof_wall_budget_seconds <= MAX_PROOF_WALL_SECONDS:
        raise ValueError("proof wall budget must be in (0, 3580] seconds")
    if not 1 <= profile_cap <= MAX_PROFILE_RESOLVES:
        raise ValueError("profile cap must be between one and forty-eight")
    started = monotonic()
    deadline = started + proof_wall_budget_seconds
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    state = _current_state()

    profile_rows: list[dict[str, object]] = []
    class_certificates: list[dict[str, object]] = []
    class_attempt_squares: set[int] = set()
    certified_class_squares: set[int] = set()
    eliminated_profile_identities: set[DegreeProfile] = set()
    plateau_rows: list[dict[str, object]] = []
    current_plateau: tuple[DegreeProfile, ...] = ()
    profile_resolution_count = 0
    frontier_complete_profiles_examined = 0
    frontier_square_sum_classes_examined = 0
    class_certificate_solver_wall = 0.0
    next_profile: DegreeProfile | None = state.cursor_profile
    next_bound: int | None = state.cursor_bound
    family_bound = max(state.prior_family_bound, state.cursor_bound)
    stop_reason = "NO_STOP_CONDITION_REACHED"
    unresolved_solver_profile: DegreeProfile | None = None
    class_certified_profile_count = 0

    while True:
        if monotonic() >= deadline:
            stop_reason = "PROOF_WALL_BUDGET_REACHED"
            break
        cursor = next_profile
        cursor_bound = next_bound
        if cursor_bound != family_bound:
            stop_reason = "CURRENT_CURSOR_NOT_FAMILY_BOUND"
            break
        resolved_before_plateau = state.prior_profiles | eliminated_profile_identities | {
            _profile(row.get("PROFILE"), name="resolved R16 profile row")
            for row in profile_rows
            if row.get("REALIZABILITY") in {"REALIZABLE", "UNREALIZABLE"}
        }
        try:
            plateau = freeze_current_plateau(
                cursor=cursor,
                active_bound=cursor_bound,
                prior_profiles=resolved_before_plateau,
                deadline=deadline,
            )
        except FrontierLookupLimit:
            stop_reason = "RANK_LOOKUP_LIMIT"
            break
        frontier_complete_profiles_examined += plateau.complete_profiles_examined
        frontier_square_sum_classes_examined += plateau.square_sum_classes_examined
        if not current_plateau:
            current_plateau = plateau.profiles
        plateau_square_sums = {sum(degree**2 for degree in p) for p in plateau.profiles}
        if len(plateau_square_sums) != 1:
            raise AssertionError("one coarse-bound plateau crosses square-sum classes")
        square_sum = next(iter(plateau_square_sums))
        plateau_rows.append(
            {
                "BOUND": cursor_bound,
                "SQUARE_SUM": square_sum,
                "PROFILE_COUNT": len(plateau.profiles),
                "PROFILE_IDENTITIES": [profile_identity(p) for p in plateau.profiles],
                "NEXT_PROFILE": (
                    None if plateau.next_profile is None else profile_identity(plateau.next_profile)
                ),
                "NEXT_BOUND": plateau.next_bound,
                "LOOKUP_PROFILE_COUNT": plateau.lookup_profile_count,
                "LOOKUP_COMPLETE_PROFILES_EXAMINED": plateau.complete_profiles_examined,
                "LOOKUP_SQUARE_SUM_CLASSES_EXAMINED": plateau.square_sum_classes_examined,
                "FULL_4850_PROFILE_CENSUS_REBUILT": False,
            }
        )
        assert_no_prior_profile_rerun(resolved_before_plateau, plateau.profiles)

        try:
            class_certificate = certify_square_sum_class(
                square_sum=square_sum,
                upper_profile=cursor,
                prior_profiles=resolved_before_plateau,
                deadline=deadline,
            )
        except FrontierLookupLimit:
            class_certificate = None
        class_bound: int | None = None
        class_attempt_squares.add(square_sum)
        if class_certificate is not None:
            class_bound = _require_int(
                class_certificate.get("CLASS_FAMILY_UPPER_BOUND"),
                name="R16 class family bound",
            )
            if class_certificate.get("COMPLETE_SUFFIX_ENUMERATION") is not True:
                raise AssertionError("R16 class certificate did not enumerate the full suffix")
            raw_class_ids = class_certificate.get("PROFILE_IDENTITIES")
            if not isinstance(raw_class_ids, list):
                raise AssertionError("R16 class certificate lacks profile identities")
            class_profiles = {
                _profile(raw, name="R16 class-certified profile")
                for raw in cast(list[object], raw_class_ids)
            }
            if not set(plateau.profiles) <= class_profiles:
                raise AssertionError("class certificate does not cover the complete active plateau")
            assert_no_prior_profile_rerun(resolved_before_plateau, class_profiles)
            certified = class_bound < cursor_bound
            class_certificate["CURRENT_ACTIVE_BOUND"] = cursor_bound
            class_certificate["CERTIFICATION_STATUS"] = (
                "CERTIFIED_BELOW_ACTIVE_BOUND" if certified else "NOT_BELOW_ACTIVE_BOUND"
            )
            class_certificate["CLASS_CERTIFICATE_KIND"] = (
                "COMPLETE_DEGREE_SQUARE_SUM_SUFFIX_OPEN_WEDGE_RELAXATION"
            )
            class_certificates.append(class_certificate)
            wall = class_certificate.get("RELAXATION_SOLVER_WALL_TIME_SECONDS")
            if isinstance(wall, (int, float)):
                class_certificate_solver_wall += float(wall)
            if certified:
                certified_class_squares.add(square_sum)
                eliminated_profile_identities.update(class_profiles)
                class_certified_profile_count += len(class_profiles)

        if class_certificate is not None and class_bound is not None and class_bound < cursor_bound:
            resolved_for_cursor = (
                state.prior_profiles
                | eliminated_profile_identities
                | {
                    _profile(row.get("PROFILE"), name="resolved R16 profile row")
                    for row in profile_rows
                    if row.get("REALIZABILITY") in {"REALIZABLE", "UNREALIZABLE"}
                }
            )
            try:
                next_profile, _next_square_sum, empty_classes, _ = first_eligible_profile(
                    start_square_sum=square_sum - 2,
                    deadline=deadline,
                    prior_profiles=resolved_for_cursor,
                )
            except FrontierLookupLimit:
                stop_reason = "RANK_LOOKUP_LIMIT"
                next_profile = None
                next_bound = None
                break
            empty_records = _empty_class_records(empty_classes)
            for empty_record in empty_records:
                empty_square_sum = _require_int(
                    empty_record.get("SQUARE_SUM"), name="empty class square sum"
                )
                class_attempt_squares.add(empty_square_sum)
                certified_class_squares.add(empty_square_sum)
                class_certificates.append(empty_record)
            next_bound = (
                None
                if next_profile is None
                else coarse_profile_envelope(next_profile).family_upper_bound
            )
            family_bound = _family_bound(
                prior_bound=state.prior_family_bound,
                profile_rows=profile_rows,
                next_profile=next_profile,
            )
            stop = _terminal_reason(
                family_bound=family_bound,
                start_bound=START_BOUND,
                incumbent=INCUMBENT,
                certified_classes=len(certified_class_squares),
                resolved_profiles=profile_resolution_count,
                deadline=deadline,
            )
            if stop is not None:
                stop_reason = stop
                break
            if next_profile is None or next_bound is None:
                stop_reason = "NO_ACTIVE_CURSOR"
                break
            if family_bound != next_bound:
                stop_reason = "CURRENT_CURSOR_NOT_FAMILY_BOUND"
                break
            continue

        if class_certificate is None:
            class_certificates.append(
                {
                    "SQUARE_SUM": square_sum,
                    "UPPER_PROFILE": profile_identity(cursor),
                    "CLASS_FAMILY_UPPER_BOUND": None,
                    "CERTIFICATION_STATUS": "NOT_RUN_FRONTIER_OR_WALL_LIMIT",
                    "COMPLETE_SUFFIX_ENUMERATION": False,
                    "CLASS_CERTIFICATE_KIND": (
                        "COMPLETE_DEGREE_SQUARE_SUM_SUFFIX_OPEN_WEDGE_RELAXATION"
                    ),
                }
            )

        unresolved = False
        for index, profile in enumerate(plateau.profiles):
            if profile_resolution_count >= profile_cap:
                stop_reason = "PROFILE_CAP_REACHED"
                next_profile = profile
                next_bound = coarse_profile_envelope(profile).family_upper_bound
                unresolved = True
                break
            if monotonic() >= deadline:
                stop_reason = "PROOF_WALL_BUDGET_REACHED"
                next_profile = profile
                next_bound = coarse_profile_envelope(profile).family_upper_bound
                unresolved = True
                break
            assert_no_prior_profile_rerun(
                resolved_before_plateau | {
                    _profile(row.get("PROFILE"), name="prior R16 profile row")
                    for row in profile_rows
                    if row.get("REALIZABILITY") in {"REALIZABLE", "UNREALIZABLE"}
                },
                (profile,),
            )
            resolution: dict[str, object]
            try:
                resolution = resolve_profile(
                    profile,
                    remaining_wall=deadline - monotonic(),
                )
            except TimeoutError:
                resolution = {
                    "PROFILE": list(profile),
                    "REALIZABILITY": "UNRESOLVED",
                    "SUPPORT_SOLVER_STATUS": "EXTERNAL_HARD_TIMEOUT",
                    "COARSE_FAMILY_UPPER_BOUND": coarse_profile_envelope(
                        profile
                    ).family_upper_bound,
                    "FAMILY_UPPER_BOUND": None,
                }
            resolution["RANK_INDEX"] = index
            resolution["RANKED_COARSE_BOUND"] = cursor_bound
            profile_rows.append(resolution)
            state_name = resolution.get("REALIZABILITY")
            if state_name == "UNRESOLVED":
                unresolved = True
                unresolved_solver_profile = profile
                next_profile = profile
                next_bound = coarse_profile_envelope(profile).family_upper_bound
                stop_reason = (
                    "PROOF_WALL_BUDGET_REACHED"
                    if monotonic() >= deadline
                    else "SOLVER_UNRESOLVED"
                )
                break
            if state_name not in {"REALIZABLE", "UNREALIZABLE"}:
                raise AssertionError("profile solver returned an unknown realizability state")
            profile_resolution_count += 1

            next_unprocessed = (
                plateau.profiles[index + 1]
                if index + 1 < len(plateau.profiles)
                else plateau.next_profile
            )
            family_bound = _family_bound(
                prior_bound=state.prior_family_bound,
                profile_rows=profile_rows,
                next_profile=next_unprocessed,
            )
            next_bound = (
                None
                if next_unprocessed is None
                else coarse_profile_envelope(next_unprocessed).family_upper_bound
            )
            stop = _terminal_reason(
                family_bound=family_bound,
                start_bound=START_BOUND,
                incumbent=INCUMBENT,
                certified_classes=len(certified_class_squares),
                resolved_profiles=profile_resolution_count,
                deadline=deadline,
            )
            if stop is not None:
                stop_reason = stop
                next_profile = next_unprocessed
                unresolved = next_unprocessed is not None
                break

        if unresolved:
            break
        next_profile = plateau.next_profile
        next_bound = plateau.next_bound
        family_bound = _family_bound(
            prior_bound=state.prior_family_bound,
            profile_rows=profile_rows,
            next_profile=next_profile,
        )
        stop = _terminal_reason(
            family_bound=family_bound,
            start_bound=START_BOUND,
            incumbent=INCUMBENT,
            certified_classes=len(certified_class_squares),
            resolved_profiles=profile_resolution_count,
            deadline=deadline,
        )
        if stop is not None:
            stop_reason = stop
            break
        if next_profile is None or next_bound is None:
            stop_reason = "NO_ACTIVE_CURSOR"
            break
        if family_bound != next_bound:
            stop_reason = "CURRENT_CURSOR_NOT_FAMILY_BOUND"
            break

    if stop_reason == "NO_STOP_CONDITION_REACHED":
        stop_reason = "PROOF_WALL_BUDGET_REACHED" if monotonic() >= deadline else "NO_ACTIVE_CURSOR"
    family_status = (
        "CLOSED"
        if family_bound <= INCUMBENT
        else "OPEN_STRICTLY_TIGHTENED"
        if family_bound < START_BOUND
        else "OPEN"
    )
    compact_rows_raw: object = (
        compact_descent_result({"PROFILE_BOUNDS": profile_rows}).get("PROFILE_BOUNDS", [])
        if profile_rows
        else []
    )
    if not isinstance(compact_rows_raw, list):
        raise AssertionError("compact R16 profile rows are malformed")
    compact_rows = cast(list[dict[str, object]], compact_rows_raw)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": _task_status(stop_reason),
        "STOP_REASON": stop_reason,
        "BASE_HEAD": BASE_HEAD,
        "TASK_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "START_BOUND": START_BOUND,
        "END_BOUND": family_bound,
        "CUMULATIVE_DROP": max(0, START_BOUND - family_bound),
        "CURRENT_PLATEAU_PROFILE_COUNT": len(current_plateau),
        "CURRENT_LOAD_BEARING_PLATEAU": [profile_identity(p) for p in current_plateau],
        "PROFILES_PROCESSED": profile_resolution_count,
        "CLASSES_ANALYZED": len(class_attempt_squares),
        "CLASS_CERTIFICATE_ATTEMPTS": len(class_certificates),
        "CLASSES_CERTIFIED": len(certified_class_squares),
        "CERTIFIED_CLASS_SQUARE_SUMS": sorted(certified_class_squares, reverse=True),
        "PROFILES_ELIMINATED_BY_CLASS_BOUND": len(eliminated_profile_identities),
        "CLASS_CERTIFIED_PROFILE_COUNT": class_certified_profile_count,
        "CLASS_CERTIFICATES": class_certificates,
        "PLATEAUS_PROCESSED": plateau_rows,
        "PROFILE_BOUNDS": compact_rows,
        "NEXT_ACTIVE_BOUND": next_bound,
        "NEXT_ACTIVE_PROFILE": (
            None if next_profile is None else profile_identity(next_profile)
        ),
        "FAMILY_UPPER_BOUND": family_bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": max(0, family_bound - INCUMBENT),
        "FAMILY_STATUS": family_status,
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "PROOF_WALL_BUDGET_SECONDS": proof_wall_budget_seconds,
            "EXTERNAL_TASK_HARD_TIMEOUT_SECONDS": 3_600,
            "EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS": EXTERNAL_PROFILE_HARD_TIMEOUT_SECONDS,
            "NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS": NATIVE_SUPPORT_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS": NATIVE_MOTIF_SOLVER_WALL_LIMIT_SECONDS,
            "NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS": NATIVE_DEGREE_CLASS_WALL_LIMIT_SECONDS,
            "PROFILE_RESOLVE_CAP": profile_cap,
            "GENERIC_CLASS_ELIMINATION_STOP": MAX_GENERIC_CLASS_ELIMINATIONS,
            "CP_SAT_SEARCH_WORKERS": 1,
            "CPU_MATH_THREADS": 1,
        },
        "SOLVER_CLASS_RELAXATION_WALL_TIME_SECONDS": class_certificate_solver_wall,
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
        "RANK_LOOKUP": {
            "COMPLETE_PROFILES_EXAMINED": frontier_complete_profiles_examined,
            "SQUARE_SUM_CLASSES_EXAMINED": frontier_square_sum_classes_examined,
            "MAX_PLATEAU_LOOKUP_PROFILES": MAX_PLATEAU_LOOKUP_PROFILES,
            "MAX_COMPLETE_PROFILE_PREFIX": MAX_FRONTIER_LOOKUP_COMPLETE_LEAVES,
            "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        },
        "PRIOR_RESOLVED_PROFILE_COUNT": len(state.prior_profiles),
        "PRIOR_RESOLVED_FAMILY_UPPER_BOUND": state.prior_family_bound,
        "PRIOR_RESOLVED_FAMILY_BOUND_OWNER_PROFILES": [
            profile_identity(profile) for profile in state.prior_family_bound_owner_profiles
        ],
        "PRIOR_PROFILE_RERUN_COUNT": 0,
        "R15_REFINED_OWNER_PROFILES": [profile_identity(p) for p in state.owner_profiles],
        "R15_OWNER_PROFILES_RERUN": [],
        "PACKET_PROFILE_RECONCILIATION": state.packet_profile_class_certificate,
        "UNRESOLVED_SOLVER_PROFILE": (
            None
            if unresolved_solver_profile is None
            else profile_identity(unresolved_solver_profile)
        ),
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "NEW_PORTFOLIO_SEARCH_STARTED": False,
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proof-wall-budget-seconds",
        type=float,
        default=MAX_PROOF_WALL_SECONDS,
    )
    parser.add_argument("--profile-cap", type=int, default=MAX_PROFILE_RESOLVES)
    args = parser.parse_args()
    result = compute_load_bearing_plateau_result(
        proof_wall_budget_seconds=args.proof_wall_budget_seconds,
        profile_cap=args.profile_cap,
    )
    path = _result_path(RESULT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


__all__ = [
    "BASE_HEAD",
    "BASE_TREE",
    "INCUMBENT",
    "MAX_GENERIC_CLASS_ELIMINATIONS",
    "MAX_PROFILE_RESOLVES",
    "PACKET_PROFILE",
    "RESULT_FILENAME",
    "START_BOUND",
    "TASK_BRANCH",
    "TASK_ID",
    "WORKTREE_PATH",
    "_current_state",
    "_terminal_reason",
    "compute_load_bearing_plateau_result",
    "freeze_current_plateau",
    "profile_identity",
]


if __name__ == "__main__":
    main()
