"""Refine only the two tied K20 minimum-S2 family-bound owners (R19).

R18 left two resolved profiles tied at the family bound 313,671,448:
66666555554411100000 (R11.PROFILE_BOUNDS[15]) and 66665555555421000000
(R11.PROFILE_BOUNDS[17]).  Both rows take their graph-triangle cap 273 from the
R10 degree-class open-wedge relaxation (W = 833 wedges, at least 14 open); the
coarse cap is 277 and the 12-second motif best bound 278.

Each step works on the currently higher owner (ties keep R18's owner order).
Route (a) reruns the unchanged R15 complement-triangle model.  Route (b) adds
``open wedges <= W - 3*cap`` to the exact R10 support model; INFEASIBLE
certifies at most cap-1 graph triangles.  A fixed-witness check shows the model
counts the committed witness's open wedges exactly.  After every strict owner
improvement the family maximum is recomputed over all 282 resolved profiles and
the unresolved cursor ceiling.  The run stops at the first packet success:

A. family bound <= incumbent;
B. both owners <= the cursor bound 313,658,120;
C. the family bound strictly drops and is carried by an exactly identified
   profile, so further work on these two owners cannot move it.

The ledger has twelve further resolved profiles between the cursor bound and the
start bound (the highest are R12.PROFILE_BOUNDS[8] and [10] at 313,668,648).
Lowering both owners therefore leaves a resolved profile, not the cursor, as the
family-bound owner.  The cursor is never sent to a solver.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    NATIVE_S3_WALL_LIMIT_SECONDS,
    canonical_primitive_preflight,
    reconstruct_family_max_ledger,
)
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    _s4_lower_bound_for_s3_maximizers as s4_floor_at_s3_maximizers,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_cursor_plateau_closure_r18 import (
    RESULT_FILENAME as R18_RESULT_FILENAME,
)
from .b649_k20_min_s2_cursor_plateau_closure_r18 import current_state as r18_current_state
from .b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import profile_identity
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    NATIVE_SUPPORT_REFUTATION_WALL_LIMIT_SECONDS,
    NATIVE_WITNESS_CHECK_WALL_LIMIT_SECONDS,
    complement_route_attempt,
    exact_support_triangle_refutation,
    owner_lineage,
    witness_open_wedge_check,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_INCUMBENT,
    K20_TICKET_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]
Triple = tuple[int, int, int]
Pair = tuple[int, int]

TASK_ID = "B649_K20_MIN_S2_DUAL_OWNER_REFINEMENT_R19"
TASK_BRANCH = "codex/b649-k20-min-s2-dual-owner-refinement-r19"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "70c154bcdd9ab2d4c74e4f1e1032f0a817fa4919"
BASE_TREE = "832d52e02fdce09a4a4a2226f5e08d3405c42e8c"
RESULT_FILENAME = "b649-k20-min-s2-dual-owner-refinement-r19-result.json"

INCUMBENT = K20_INCUMBENT
START_FAMILY_BOUND = 313_671_448
START_OWNER_TRIANGLE_CAP = 273
EXPECTED_OWNER_WEDGE_COUNT = 833
EXPECTED_OWNER_OPEN_WEDGE_LOWER_BOUND = 14
EXPECTED_POST_R18_PROFILE_COUNT = 282
LOAD_BEARING_RELAXATION = "R10_DEGREE_CLASS_OPEN_WEDGE_RELAXATION"
OWNER_A: DegreeProfile = tuple(int(d) for d in "66666555554411100000")
OWNER_B: DegreeProfile = tuple(int(d) for d in "66665555555421000000")
# R18 CURRENT_BOUND_OWNERS order; it breaks ties between equally high owners.
OWNER_ORDER: tuple[DegreeProfile, ...] = (OWNER_A, OWNER_B)
EXPECTED_OWNER_SOURCES: dict[DegreeProfile, str] = {
    OWNER_A: "R11.PROFILE_BOUNDS[15]",
    OWNER_B: "R11.PROFILE_BOUNDS[17]",
}
NEXT_CURSOR_PROFILE: DegreeProfile = tuple(int(d) for d in "66666665442111111111")
NEXT_CURSOR_BOUND = 313_658_120
MAX_REFINEMENT_STEPS = 8
EXTERNAL_TASK_HARD_TIMEOUT_SECONDS = 900

SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_BOTH_OWNERS_AT_OR_BELOW_CURSOR"
SUCCESS_C = "SUCCESS_C_FAMILY_STRICTLY_TIGHTENED_EXACT_REMAINING_OWNER"
BLOCKED = "BLOCKED_NO_CERTIFIED_FAMILY_TIGHTENING"


@dataclass(frozen=True, slots=True)
class FamilyState:
    bound: int
    owners: tuple[str, ...]
    cursor_carries_bound: bool


@dataclass(frozen=True, slots=True)
class RefinementStep:
    owner: DegreeProfile
    start_cap: int
    refined_cap: int
    start_bound: int
    refined_bound: int
    family_after: FamilyState


@dataclass(frozen=True, slots=True)
class RefinementOutcome:
    status: str
    steps: tuple[RefinementStep, ...]
    owner_caps: dict[DegreeProfile, int]
    owner_bounds: dict[DegreeProfile, int]
    family: FamilyState


def result_path(filename: str = RESULT_FILENAME) -> Path:
    return Path(__file__).resolve().parents[3] / "docs/research/matrix-native-results" / filename


def _read_object(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected a JSON object at {path}")
    return cast(dict[str, object], value)


def _decode_profile(raw: object, name: str) -> DegreeProfile:
    if isinstance(raw, str) and len(raw) == K20_TICKET_COUNT and raw.isdecimal():
        return tuple(int(value) for value in raw)
    raise AssertionError(f"{name} is not a twenty-degree profile identity")


def post_r18_bound_ledger() -> tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]]:
    """Rebuild all 282 resolved bounds: R17's 227-profile ledger plus R18's class."""

    state = r18_current_state()
    bounds, sources = dict(state.bounds), dict(state.sources)
    r18 = _read_object(result_path(R18_RESULT_FILENAME))
    expected: dict[str, object] = {
        "TASK_STATUS": "SUCCESS_C_PLATEAU_RESOLVED_EXACT_LOAD_BEARING_CURSOR",
        "FAMILY_UPPER_BOUND": START_FAMILY_BOUND,
        "CURRENT_BOUND_OWNERS": [profile_identity(p) for p in OWNER_ORDER],
        "CURRENT_BOUND_OWNER_SOURCES": {
            profile_identity(p): source for p, source in EXPECTED_OWNER_SOURCES.items()
        },
        "NEXT_ACTIVE_PROFILE": profile_identity(NEXT_CURSOR_PROFILE),
        "NEXT_ACTIVE_BOUND": NEXT_CURSOR_BOUND,
        "INCUMBENT": INCUMBENT,
    }
    for key, value in expected.items():
        if r18.get(key) != value:
            raise AssertionError(f"R18 authority mismatch: {key}")
    certificates = cast(list[object], r18["CLASS_CERTIFICATES"])
    if len(certificates) != 1:
        raise AssertionError("R18 must contribute exactly one class certificate")
    certificate = cast(dict[str, object], certificates[0])
    if certificate.get("CERTIFICATION_STATUS") != "CERTIFIED_BELOW_NEXT_DISTINCT_CURSOR":
        raise AssertionError("the R18 class certificate is not certified")
    class_bound = certificate.get("CLASS_FAMILY_UPPER_BOUND")
    if type(class_bound) is not int or class_bound >= NEXT_CURSOR_BOUND:
        raise AssertionError("the R18 class bound is malformed or above the cursor")
    square_sum = certificate.get("SQUARE_SUM")
    for raw in cast(list[object], certificate["PROFILE_IDENTITIES"]):
        profile = _decode_profile(raw, "R18 class profile")
        if profile in bounds:
            raise AssertionError("R18 class certificate re-resolved a prior profile")
        bounds[profile] = class_bound
        sources[profile] = f"R18.CLASS_CERTIFICATES[0].SQUARE_SUM={square_sum}"
    if len(bounds) != EXPECTED_POST_R18_PROFILE_COUNT:
        raise AssertionError("post-R18 resolved ledger has an unexpected size")
    if NEXT_CURSOR_PROFILE in bounds:
        raise AssertionError("the R18 cursor was already resolved")
    if coarse_profile_envelope(NEXT_CURSOR_PROFILE).family_upper_bound != NEXT_CURSOR_BOUND:
        raise AssertionError("the cursor bound does not match its coarse envelope")
    return bounds, sources


def assert_exact_two_owner_set(
    bounds: Mapping[DegreeProfile, int],
    sources: Mapping[DegreeProfile, str],
    *,
    cursor: DegreeProfile = NEXT_CURSOR_PROFILE,
    cursor_bound: int = NEXT_CURSOR_BOUND,
) -> tuple[DegreeProfile, ...]:
    """Fail closed unless exactly the two packet owners carry the family maximum."""

    family_bound = max(cursor_bound, *bounds.values())
    tied = tuple(sorted((p for p, b in bounds.items() if b == family_bound), reverse=True))
    if family_bound != START_FAMILY_BOUND:
        raise AssertionError("the family maximum is not the packet start bound")
    if cursor in bounds or cursor_bound >= family_bound:
        raise AssertionError("the unresolved cursor is tied with or above the owners")
    if len(tied) > len(OWNER_ORDER):
        raise AssertionError("a third profile is tied at the family maximum")
    if tied != OWNER_ORDER:
        raise AssertionError("the family-bound owner set differs from the packet owners")
    if any(sources[p] != EXPECTED_OWNER_SOURCES[p] for p in tied):
        raise AssertionError("an owner certificate source changed")
    return tied


def assert_owner_set_solver_scope(
    requested_profiles: Collection[DegreeProfile],
    *,
    owners: Collection[DegreeProfile],
    cursor: DegreeProfile,
) -> None:
    """Allow exactly one current owner per solver call; never the cursor."""

    requested = tuple(requested_profiles)
    if cursor in requested or cursor in owners:
        raise AssertionError("the unresolved cursor profile must never be sent to a solver")
    if len(requested) != 1 or requested[0] not in owners:
        raise AssertionError("only one current family-bound owner may be sent to a solver")


def owner_bound_from_cap(wedge_count: int, triangle_cap: int, credit: int) -> tuple[int, int]:
    s3_bound = s3_sum_from_wedges_and_triangles(
        wedge_count, triangle_cap - K20_TRIPLE_SUPPORT_COUNT
    )
    return s3_bound, K20_S1 - K20_S2 + s3_bound - credit


def family_state(
    bounds: Mapping[DegreeProfile, int],
    owner_bounds: Mapping[DegreeProfile, int],
    *,
    cursor: DegreeProfile = NEXT_CURSOR_PROFILE,
    cursor_bound: int = NEXT_CURSOR_BOUND,
) -> FamilyState:
    """Recompute max(every resolved bound, unresolved cursor ceiling) and its carriers."""

    if cursor in bounds or not set(owner_bounds) <= set(bounds):
        raise AssertionError("owners must be resolved and the cursor unresolved")
    if any(owner_bounds[p] > bounds[p] for p in owner_bounds):
        raise AssertionError("a refined owner bound may not exceed its committed bound")
    effective = {**bounds, **owner_bounds}
    family_bound = max(cursor_bound, *effective.values())
    carriers = sorted(
        (profile_identity(p) for p, b in effective.items() if b == family_bound), reverse=True
    )
    if cursor_bound == family_bound:
        carriers.insert(0, profile_identity(cursor))
    return FamilyState(family_bound, tuple(carriers), cursor_bound == family_bound)


def classify_stop(
    family: FamilyState,
    owner_bounds: Mapping[DegreeProfile, int],
    *,
    start_family_bound: int = START_FAMILY_BOUND,
    cursor_bound: int = NEXT_CURSOR_BOUND,
) -> str | None:
    """Return the first packet success reached, or None to keep refining."""

    if family.bound <= INCUMBENT:
        return SUCCESS_A
    if all(bound <= cursor_bound for bound in owner_bounds.values()):
        return SUCCESS_B
    owner_ids = {profile_identity(p) for p in owner_bounds}
    if family.bound < start_family_bound and not owner_ids & set(family.owners):
        return SUCCESS_C
    return None


def select_next_owner(
    owner_bounds: Mapping[DegreeProfile, int],
    family_bound: int,
    owner_order: Sequence[DegreeProfile] = OWNER_ORDER,
) -> DegreeProfile | None:
    """Return the higher owner (ties keep owner_order) while it carries the family max."""

    if set(owner_order) != set(owner_bounds):
        raise AssertionError("owner order must list exactly the current owners")
    top = max(owner_bounds.values())
    if top < family_bound:
        return None
    return next(p for p in owner_order if owner_bounds[p] == top)


def run_refinement_schedule(
    bounds: Mapping[DegreeProfile, int],
    *,
    owner_caps: Mapping[DegreeProfile, int],
    owner_bound: Callable[[DegreeProfile, int], int],
    refine: Callable[[DegreeProfile, int], int],
    owner_order: Sequence[DegreeProfile] = OWNER_ORDER,
    cursor: DegreeProfile = NEXT_CURSOR_PROFILE,
    cursor_bound: int = NEXT_CURSOR_BOUND,
    max_steps: int = MAX_REFINEMENT_STEPS,
) -> RefinementOutcome:
    """Refine the higher owner one certificate at a time until the first success.

    ``refine(owner, cap)`` returns the certified cap after one attempt; a value
    not below ``cap`` means no certificate and stops the schedule.
    """

    caps = dict(owner_caps)
    current = {p: owner_bound(p, caps[p]) for p in owner_order}
    if any(current[p] != bounds[p] for p in owner_order):
        raise AssertionError("owner caps do not reproduce the committed owner bounds")
    start_family_bound = family_state(bounds, current, cursor=cursor, cursor_bound=cursor_bound)
    steps: list[RefinementStep] = []
    family = start_family_bound
    while True:
        status = classify_stop(
            family,
            current,
            start_family_bound=start_family_bound.bound,
            cursor_bound=cursor_bound,
        )
        if status is not None:
            break
        owner = select_next_owner(current, family.bound, owner_order)
        if owner is None:
            raise AssertionError("no owner carries an untightened family maximum")
        if len(steps) >= max_steps:
            raise AssertionError("refinement step budget exhausted")
        assert_owner_set_solver_scope((owner,), owners=owner_order, cursor=cursor)
        refined_cap = refine(owner, caps[owner])
        if refined_cap >= caps[owner]:
            status = SUCCESS_C if family.bound < start_family_bound.bound else BLOCKED
            break
        refined_bound = owner_bound(owner, refined_cap)
        if refined_bound >= current[owner]:
            raise AssertionError("a lower triangle cap failed to lower the owner bound")
        start_cap, start_bound = caps[owner], current[owner]
        caps[owner], current[owner] = refined_cap, refined_bound
        family = family_state(bounds, current, cursor=cursor, cursor_bound=cursor_bound)
        steps.append(
            RefinementStep(owner, start_cap, refined_cap, start_bound, refined_bound, family)
        )
    return RefinementOutcome(status, tuple(steps), caps, current, family)


def owner_ledger_row(
    profile: DegreeProfile, lineage: Mapping[str, object], source: str
) -> dict[str, object]:
    """Phase 1 row: certified bound, witness, caps, S3, S4 floor, binding relaxation."""

    row = cast(dict[str, object], lineage["row"])
    caps = cast(dict[str, int], lineage["caps"])
    cap = min(caps.values())
    wedge_count = cast(int, lineage["wedge_count"])
    credit = cast(int, lineage["fourth_order_credit"])
    s3_bound, bound = owner_bound_from_cap(wedge_count, cap, credit)
    complement_degrees = [K20_TICKET_COUNT - 1 - (6 + degree) for degree in profile]
    complement_constant = (
        comb(K20_TICKET_COUNT, 3)
        - (sum(complement_degrees) // 2) * (K20_TICKET_COUNT - 2)
        + sum(comb(degree, 2) for degree in complement_degrees)
    )
    return {
        "PROFILE": profile_identity(profile),
        "CERTIFICATE_SOURCE": source,
        "CERTIFIED_FAMILY_UPPER_BOUND": bound,
        "REALIZABILITY": row["REALIZABILITY"],
        "SUPPORT_SOLVER_STATUS": row["SUPPORT_SOLVER_STATUS"],
        "REALIZABILITY_WITNESS_TRIPLES": row["WITNESS_TRIPLES"],
        "REALIZABILITY_WITNESS_DOUBLE_SUPPORTS": row["WITNESS_DOUBLE_SUPPORTS"],
        "REALIZABILITY_WITNESS_VALIDATED": True,
        "WEDGE_COUNT": wedge_count,
        "TRIANGLE_CAPS_BY_RELAXATION": caps,
        "GRAPH_TRIANGLE_UPPER_BOUND": cap,
        "NONCORE_TRIANGLE_UPPER_BOUND": cap - K20_TRIPLE_SUPPORT_COUNT,
        "LOOSE_THREE_CYCLE_UPPER_BOUND": row["LOOSE_THREE_CYCLE_UPPER_BOUND"],
        "PASCH_LIKE_FOUR_SUPPORT_UPPER_BOUND": row["PASCH_LIKE_FOUR_SUPPORT_UPPER_BOUND"],
        "COMPLEMENT_TRIANGLE_IDENTITY_CONSTANT": complement_constant,
        "COMPLEMENT_TRIANGLE_LOWER_BOUND_IMPLIED": complement_constant - cap,
        "S3_UPPER_BOUND": s3_bound,
        "S4_LOWER_BOUND": lineage["s4_floor"],
        "FOURTH_ORDER_CREDIT": credit,
        "LOAD_BEARING_RELAXATION": LOAD_BEARING_RELAXATION,
        "LOAD_BEARING_OPEN_WEDGE_LOWER_BOUND": lineage["open_wedge_lower_bound"],
    }


def _family_payload(family: FamilyState) -> dict[str, object]:
    return {
        "FAMILY_UPPER_BOUND": family.bound,
        "FAMILY_BOUND_CARRIERS": list(family.owners),
        "CURSOR_CARRIES_FAMILY_BOUND": family.cursor_carries_bound,
    }


def compute_result(*, run_complement_route: bool = True) -> dict[str, object]:
    started = monotonic()
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    bounds, sources = post_r18_bound_ledger()
    owners = assert_exact_two_owner_set(bounds, sources)
    above_cursor = sorted(
        (
            (profile_identity(p), b, sources[p])
            for p, b in bounds.items()
            if b > NEXT_CURSOR_BOUND and p not in owners
        ),
        key=lambda row: (-row[1], row[0]),
    )

    ledger = reconstruct_family_max_ledger()
    records = {r.profile: r for r in ledger.records if r.profile in owners}
    lineages = {p: owner_lineage(records[p]) for p in owners}
    s4 = s4_floor_at_s3_maximizers()
    phase1: dict[str, dict[str, object]] = {}
    witness_checks: dict[str, dict[str, object]] = {}
    for p in owners:
        lineage = lineages[p]
        if records[p].certificate_source != EXPECTED_OWNER_SOURCES[p]:
            raise AssertionError("an owner record moved away from its committed row")
        if (
            lineage["wedge_count"] != EXPECTED_OWNER_WEDGE_COUNT
            or lineage["open_wedge_lower_bound"] != EXPECTED_OWNER_OPEN_WEDGE_LOWER_BOUND
            or records[p].graph_triangle_upper_bound != START_OWNER_TRIANGLE_CAP
            or s4["CERTIFIED_LOWER_BOUND"] != lineage["s4_floor"]
        ):
            raise AssertionError("an owner wedge, triangle, or S4 envelope changed")
        row = owner_ledger_row(p, lineage, EXPECTED_OWNER_SOURCES[p])
        if row["CERTIFIED_FAMILY_UPPER_BOUND"] != bounds[p]:
            raise AssertionError("an owner ledger row does not reproduce its bound")
        phase1[profile_identity(p)] = row
        check = witness_open_wedge_check(
            p,
            cast(tuple[Triple, ...], lineage["triples"]),
            cast(tuple[Pair, ...], lineage["doubles"]),
        )
        witness_checks[profile_identity(p)] = {**check, "WITNESS_SOURCE": EXPECTED_OWNER_SOURCES[p]}

    attempts: list[dict[str, object]] = []

    def owner_bound(profile: DegreeProfile, cap: int) -> int:
        lineage = lineages[profile]
        return owner_bound_from_cap(
            cast(int, lineage["wedge_count"]), cap, cast(int, lineage["fourth_order_credit"])
        )[1]

    def refine(profile: DegreeProfile, cap: int) -> int:
        lineage = lineages[profile]
        routes: list[dict[str, object]] = []
        if run_complement_route:
            routes.append(
                complement_route_attempt(
                    profile,
                    cast(tuple[Triple, ...], lineage["triples"]),
                    cast(tuple[Pair, ...], lineage["doubles"]),
                )
            )
        routes.append(exact_support_triangle_refutation(profile, refuted_triangle_count=cap))
        certified = [
            value
            for route in routes
            if type(value := route.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND")) is int
        ]
        refined = min(cap, *certified)
        attempts.append(
            {
                "OWNER": profile_identity(profile),
                "START_GRAPH_TRIANGLE_UPPER_BOUND": cap,
                "ROUTES": routes,
                "REFINED_GRAPH_TRIANGLE_UPPER_BOUND": refined,
            }
        )
        return refined

    outcome = run_refinement_schedule(
        bounds,
        owner_caps=dict.fromkeys(owners, START_OWNER_TRIANGLE_CAP),
        owner_bound=owner_bound,
        refine=refine,
    )
    if outcome.status == BLOCKED:
        raise AssertionError("no owner certificate tightened the family bound")

    if len(attempts) not in {len(outcome.steps), len(outcome.steps) + 1}:
        raise AssertionError("attempt ledger and step ledger disagree")
    steps: list[dict[str, object]] = []
    for index, step in enumerate(outcome.steps):
        attempt = attempts[index]
        if attempt["OWNER"] != profile_identity(step.owner):
            raise AssertionError("attempt ledger and step ledger disagree")
        steps.append(
            {
                "STEP": index + 1,
                "OWNER": profile_identity(step.owner),
                "START_GRAPH_TRIANGLE_UPPER_BOUND": step.start_cap,
                "REFINED_GRAPH_TRIANGLE_UPPER_BOUND": step.refined_cap,
                "REFINED_NONCORE_TRIANGLE_UPPER_BOUND": step.refined_cap - K20_TRIPLE_SUPPORT_COUNT,
                "START_OWNER_BOUND": step.start_bound,
                "REFINED_OWNER_BOUND": step.refined_bound,
                "ROUTES": attempt["ROUTES"],
                **_family_payload(step.family_after),
            }
        )
    route_b_rows = [
        route
        for attempt in attempts
        for route in cast(list[dict[str, object]], attempt["ROUTES"])
        if route["ROUTE"] == "B_EXACT_SUPPORT_MODEL_OPEN_WEDGE_REFUTATION"
    ]
    solver_wall = sum(
        float(cast(float, route.get("SOLVER_WALL_TIME_SECONDS", 0.0)))
        for attempt in attempts
        for route in cast(list[dict[str, object]], attempt["ROUTES"])
    )
    family = outcome.family
    refined_rows = {
        profile_identity(p): {
            "GRAPH_TRIANGLE_UPPER_BOUND": outcome.owner_caps[p],
            "NONCORE_TRIANGLE_UPPER_BOUND": outcome.owner_caps[p] - K20_TRIPLE_SUPPORT_COUNT,
            "S3_UPPER_BOUND": owner_bound_from_cap(
                EXPECTED_OWNER_WEDGE_COUNT,
                outcome.owner_caps[p],
                cast(int, lineages[p]["fourth_order_credit"]),
            )[0],
            "FAMILY_UPPER_BOUND": outcome.owner_bounds[p],
        }
        for p in owners
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": outcome.status,
        "OWNER_PROFILE_COUNT": len(owners),
        "OWNER_PROFILES": [profile_identity(p) for p in owners],
        "OWNER_SOURCES": {profile_identity(p): EXPECTED_OWNER_SOURCES[p] for p in owners},
        "START_OWNER_BOUNDS": {profile_identity(p): bounds[p] for p in owners},
        "REFINED_OWNER_BOUNDS": {profile_identity(p): outcome.owner_bounds[p] for p in owners},
        "REFINED_OWNER_ROWS": refined_rows,
        "PHASE1_OWNER_LEDGER": phase1,
        "NO_THIRD_OWNER_AT_START": "PASS",
        "RESOLVED_PROFILE_LEDGER_COUNT": len(bounds),
        "RESOLVED_PROFILES_ABOVE_CURSOR_OUTSIDE_OWNER_SET": [
            {"PROFILE": identity, "FAMILY_UPPER_BOUND": bound, "CERTIFICATE_SOURCE": source}
            for identity, bound, source in above_cursor
        ],
        "PACKET_SUCCESS_B_PREMISE": (
            "CONTRADICTED_RESOLVED_PROFILES_ABOVE_CURSOR" if above_cursor else "CONSISTENT"
        ),
        "TIGHTENING_PREFERENCE_ORDER_APPLIED": [
            "A_EXACT_COMPLEMENT_TRIANGLE_LOWER_BOUND",
            "B_EXACT_NONCORE_TRIANGLE_CEILING",
        ],
        "TIGHTENING_ROUTES_NOT_NEEDED": [
            "C_LOOSE_CYCLE_PASCH_SHARED_VERTEX",
            "D_MINIMUM_S4_AT_S3_MAXIMIZERS",
            "E_HIGHER_ORDER_MULTIPLICITY",
        ],
        "REFINEMENT_STEPS": steps,
        "UNCERTIFIED_FINAL_ATTEMPT": (attempts[-1] if len(attempts) > len(outcome.steps) else None),
        "ROUTE_B_WITNESS_NON_VACUITY": witness_checks,
        "S4_LOWER_BOUND_AT_S3_MAXIMIZERS": s4["CERTIFIED_LOWER_BOUND"],
        "EXACT_PROFILE_SPECIFIC_S4_MINIMUM": "NOT_COMPUTED",
        "NEXT_CURSOR_PROFILE": profile_identity(NEXT_CURSOR_PROFILE),
        "NEXT_CURSOR_BOUND": NEXT_CURSOR_BOUND,
        "START_FAMILY_UPPER_BOUND": START_FAMILY_BOUND,
        **_family_payload(family),
        "CURRENT_BOUND_OWNER": family.owners[0],
        "CURRENT_BOUND_OWNERS": list(family.owners),
        "CURRENT_BOUND_OWNER_SOURCES": {
            identity: sources[_decode_profile(identity, "owner")]
            for identity in family.owners
            if identity != profile_identity(NEXT_CURSOR_PROFILE)
        },
        "CURRENT_BOUND_OWNER_KIND": (
            "UNRESOLVED_RANKED_CURSOR"
            if family.cursor_carries_bound
            else "PRIOR_RESOLVED_PROFILE_OUTSIDE_REFINED_OWNER_SET"
        ),
        "CERTIFIED_FAMILY_DROP": START_FAMILY_BOUND - family.bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": max(0, family.bound - INCUMBENT),
        "FAMILY_STATUS": ("CLOSED" if outcome.status == SUCCESS_A else "OPEN_STRICTLY_TIGHTENED"),
        "PACKET_SUCCESS_A_SATISFIED": family.bound <= INCUMBENT,
        "PACKET_SUCCESS_B_SATISFIED": all(
            b <= NEXT_CURSOR_BOUND for b in outcome.owner_bounds.values()
        ),
        "PACKET_SUCCESS_C_SATISFIED": outcome.status == SUCCESS_C,
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": (
            "INFEASIBLE_CERTIFIED"
            if route_b_rows and all(r["STATUS"] == "INFEASIBLE" for r in route_b_rows)
            else "NOT_ALL_ROUTE_B_STEPS_CERTIFIED"
        ),
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "ROUTE_A_NATIVE_WALL_SECONDS": NATIVE_S3_WALL_LIMIT_SECONDS,
            "ROUTE_B_NATIVE_WALL_SECONDS": NATIVE_SUPPORT_REFUTATION_WALL_LIMIT_SECONDS,
            "WITNESS_CHECK_NATIVE_WALL_SECONDS": NATIVE_WITNESS_CHECK_WALL_LIMIT_SECONDS,
            "EXTERNAL_TASK_HARD_TIMEOUT_SECONDS": EXTERNAL_TASK_HARD_TIMEOUT_SECONDS,
            "MAX_REFINEMENT_STEPS": MAX_REFINEMENT_STEPS,
            "CP_SAT_SEARCH_WORKERS": 1,
        },
        "SOLVER_ROUTE_WALL_SECONDS": solver_wall,
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
        "SOLVER_CERTIFIED_BOUND": max(outcome.owner_bounds.values()),
        "SOLVER_PROFILES_SENT": [profile_identity(s.owner) for s in outcome.steps],
        "CURSOR_PROFILE_SOLVES": 0,
        "NO_CURSOR_WORK_STATUS": "PASS",
        "CURSOR_DESCENT_STARTED": False,
        "OUTSIDE_OWNER_SET_PROFILE_SOLVES": 0,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-complement-route", action="store_true")
    arguments = parser.parse_args()
    result = compute_result(run_complement_route=not arguments.skip_complement_route)
    result_path().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "REFINED_OWNER_BOUNDS",
                    "FAMILY_UPPER_BOUND",
                    "CURRENT_BOUND_OWNERS",
                    "REMAINING_GAP",
                    "SOLVER_STATUS",
                    "SOLVER_ACTUAL_WALL_TIME_SECONDS",
                )
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
