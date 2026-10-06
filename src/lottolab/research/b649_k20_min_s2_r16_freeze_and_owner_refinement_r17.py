"""Freeze R16 and refine only the K20 minimum-S2 family-bound owner (R17).

R16 left the resolved profile 66666555555311100000 as the unique family-bound
owner at 313,674,248, above the ranked cursor bound 313,672,792.  Its committed
row is R11.PROFILE_BOUNDS[4].  That row takes its graph-triangle cap 273 from
the R10 degree-class open-wedge relaxation (W = 834 wedges, at least 15 open),
which is tighter than both the coarse cap and the 12-second motif cap 278.

Route (a) reruns the R15 complement-triangle model unchanged.  Route (b) refutes
the cap on the exact R10 support model: every realization of the profile is a
linear system of 22 triple and 27 double supports, and its overlap graph has
W - 3*T open wedges when it has T graph triangles.  Adding the constraint
``open wedges <= W - 3*273`` to that exact model and obtaining INFEASIBLE
certifies T <= 272, i.e. at most 250 noncore triangles.  Why it holds: the five
degree-six tickets carry no double supports and the five degree-zero tickets no
triple supports, so those 25 pairs never overlap; every ticket overlapping one
side on its double supports and the other on its triple supports centers an
open wedge, and the three degree-one tickets cannot absorb all of them.

The S4 floor and its fourth-order credit are reused unchanged.  The ranked
cursor profile is only read through its committed coarse envelope; it is never
sent to a solver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Sequence
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    NATIVE_S3_WALL_LIMIT_SECONDS,
    ProfileCertificate,
    canonical_primitive_preflight,
    reconstruct_family_max_ledger,
)
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    _owner_source_row as owner_source_row,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    _owner_support_witness as owner_support_witness,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    _s3_upper_bound as complement_triangle_bound,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    _s4_lower_bound_for_s3_maximizers as s4_floor_at_s3_maximizers,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import (
    RESULT_FILENAME as R16_RESULT_FILENAME,
)
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import (
    _current_state as r16_current_state,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import profile_identity
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _graph_triangle_count as graph_triangle_count,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _overlap_edges as overlap_edges,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _support_model as support_model,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_INCUMBENT,
    K20_TICKET_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]
Triple = tuple[int, int, int]
Pair = tuple[int, int]

TASK_ID = "B649_K20_MIN_S2_R16_FREEZE_AND_OWNER_REFINEMENT_R17"
TASK_BRANCH = "codex/b649-k20-min-s2-r16-freeze-and-owner-refinement-r17"
WORKTREE_PATH = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_MIN_S2_R16_FREEZE_AND_OWNER_REFINEMENT_R17"
)
BASE_HEAD = "b7ad9b4e85c09ae8a1816696c035b80deb884072"
R16_FREEZE_HEAD = "48c27139ca57b71eaa6b0a4b719a634c3a82afa9"
R16_FREEZE_TREE = "5a2157bc4aad96785c6cbf2576dc75f208247de8"
R16_SOURCE_HASHES: dict[str, str] = {
    "src/lottolab/research/b649_k20_min_s2_load_bearing_plateau_descent_r16.py": (
        "84c12e5172099fe532f7512804b96ce35e71e69ff8abd47f6f696d1ec2e05303"
    ),
    "tests/unit/test_b649_k20_min_s2_load_bearing_plateau_descent_r16.py": (
        "6cac2ab7187965af979a3b9540125eae48cddfcc35f8b1224deafab892ea1b6a"
    ),
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-load-bearing-plateau-descent-r16-result.json": (
        "777b7ee0bf85a0daf351f4c41120f29343d91266df8d59432a8b943602f80083"
    ),
}

INCUMBENT = K20_INCUMBENT
START_OWNER_BOUND = 313_674_248
NEXT_CURSOR_BOUND = 313_672_792
OWNER_TO_CURSOR_GAP = START_OWNER_BOUND - NEXT_CURSOR_BOUND
EXPECTED_OWNER_PROFILE: DegreeProfile = (
    6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 3, 1, 1, 1, 0, 0, 0, 0, 0,
)  # fmt: skip
EXPECTED_NEXT_CURSOR_PROFILE: DegreeProfile = (
    6, 6, 6, 6, 6, 6, 6, 5, 4, 4, 2, 2, 1, 1, 1, 1, 1, 1, 1, 0,
)  # fmt: skip
EXPECTED_OWNER_SOURCE = "R11.PROFILE_BOUNDS[4]"
EXPECTED_OWNER_TRIANGLE_CAP = 273
EXPECTED_OWNER_WEDGE_COUNT = 834
EXPECTED_RESOLVED_PROFILE_COUNT = 227
LOAD_BEARING_RELAXATION = "R10_DEGREE_CLASS_OPEN_WEDGE_RELAXATION"
NATIVE_SUPPORT_REFUTATION_WALL_LIMIT_SECONDS = 60.0
NATIVE_WITNESS_CHECK_WALL_LIMIT_SECONDS = 30.0
EXTERNAL_TASK_HARD_TIMEOUT_SECONDS = 900
RESULT_FILENAME = "b649-k20-min-s2-r16-freeze-and-owner-refinement-r17-result.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_result(name: str) -> dict[str, object]:
    path = _repo_root() / "docs" / "research" / "matrix-native-results" / name
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"committed result {name} must be a JSON object")
    return cast(dict[str, object], value)


def _require_int(value: object, name: str) -> int:
    if type(value) is not int:
        raise AssertionError(f"{name} must be an integer")
    return value


def _decode_profile(raw: object, name: str) -> DegreeProfile:
    if isinstance(raw, str) and len(raw) == K20_TICKET_COUNT and raw.isdecimal():
        return tuple(int(value) for value in raw)
    if isinstance(raw, list):
        values = cast(list[object], raw)
        if len(values) == K20_TICKET_COUNT and all(type(value) is int for value in values):
            return tuple(cast(int, value) for value in values)
    raise AssertionError(f"{name} is not a twenty-degree profile")


def r16_freeze_regression() -> dict[str, str]:
    """Fail closed unless the frozen R16 deliverables are byte-identical."""

    observed: dict[str, str] = {}
    for relative_path, expected in R16_SOURCE_HASHES.items():
        digest = hashlib.sha256((_repo_root() / relative_path).read_bytes()).hexdigest()
        if digest != expected:
            raise AssertionError(f"frozen R16 deliverable drifted: {relative_path}")
        observed[relative_path] = digest
    return observed


def post_r16_bound_ledger() -> tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]]:
    """Rebuild every resolved profile bound after R16 without solver work."""

    state = r16_current_state()
    ledger = reconstruct_family_max_ledger()
    r15 = _read_result("b649-k20-min-s2-current-bound-owner-refinement-r15-result.json")
    r16 = _read_result(R16_RESULT_FILENAME)

    overrides: dict[DegreeProfile, int] = {}
    for raw in cast(list[object], r15["OWNER_PROFILE_BOUNDS"]):
        row = cast(dict[str, object], raw)
        profile = _decode_profile(row.get("PROFILE"), "R15 refined owner")
        overrides[profile] = _require_int(row.get("FAMILY_UPPER_BOUND"), "R15 owner bound")
    bounds = {
        record.profile: overrides.get(record.profile, record.family_upper_bound)
        for record in ledger.records
    }
    sources = {
        record.profile: (
            "R15.OWNER_PROFILE_BOUNDS" if record.profile in overrides else record.certificate_source
        )
        for record in ledger.records
    }
    if frozenset(bounds) != state.prior_profiles:
        raise AssertionError("R16 prior profile identities disagree with the R11-R15 ledger")

    certificates = cast(list[object], r16["CLASS_CERTIFICATES"])
    if len(certificates) != 1:
        raise AssertionError("R16 must contribute exactly one class certificate")
    certificate = cast(dict[str, object], certificates[0])
    if certificate.get("CERTIFICATION_STATUS") != "CERTIFIED_BELOW_ACTIVE_BOUND":
        raise AssertionError("the R16 class certificate is not certified")
    class_bound = _require_int(certificate.get("CLASS_FAMILY_UPPER_BOUND"), "R16 class bound")
    for raw in cast(list[object], certificate["PROFILE_IDENTITIES"]):
        profile = _decode_profile(raw, "R16 class profile")
        if profile in bounds:
            raise AssertionError("R16 class certificate re-resolved a prior profile")
        bounds[profile] = class_bound
        sources[profile] = "R16.CLASS_CERTIFICATES[0].SQUARE_SUM=326"
    if len(bounds) != EXPECTED_RESOLVED_PROFILE_COUNT:
        raise AssertionError("post-R16 resolved ledger has an unexpected size")
    if max(bounds.values()) != _require_int(r16.get("FAMILY_UPPER_BOUND"), "R16 family bound"):
        raise AssertionError("post-R16 ledger maximum disagrees with the frozen R16 result")
    return bounds, sources


def assert_owner_only_solver_scope(
    requested_profiles: Iterable[DegreeProfile],
    *,
    owner: DegreeProfile,
    cursor: DegreeProfile,
) -> None:
    """Reject every solver request except the single current owner."""

    requested = tuple(requested_profiles)
    if requested != (owner,):
        raise AssertionError("only the current family-bound owner may be sent to a solver")
    if owner == cursor or cursor in requested:
        raise AssertionError("the ranked cursor profile must never be sent to a solver")


def owner_lineage(owner: ProfileCertificate) -> dict[str, object]:
    """Recover the owner's committed row and the relaxation that sets its bound."""

    row = owner_source_row(owner)
    triples, doubles = owner_support_witness(row, owner.profile)
    motif = cast(dict[str, object], row["MOTIF_SOLVER"])
    degree_class = cast(dict[str, object], row["DEGREE_CLASS_RELAXATION"])
    caps = {
        "R8_COARSE_PROFILE_ENVELOPE": coarse_profile_envelope(
            owner.profile
        ).graph_triangle_upper_bound,
        "R10_MOTIF_CP_SAT_BEST_BOUND": _require_int(
            motif.get("SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"), "motif triangle cap"
        ),
        LOAD_BEARING_RELAXATION: _require_int(
            degree_class.get("GRAPH_TRIANGLE_UPPER_BOUND"), "degree-class triangle cap"
        ),
    }
    cap = min(caps.values())
    responsible = [name for name, value in caps.items() if value == cap]
    if cap != owner.graph_triangle_upper_bound or responsible != [LOAD_BEARING_RELAXATION]:
        raise AssertionError("the owner cap is not set uniquely by the degree-class relaxation")
    wedge_count = overlap_wedge_count(owner.profile)
    s3_bound = s3_sum_from_wedges_and_triangles(wedge_count, cap - K20_TRIPLE_SUPPORT_COUNT)
    s4_floor = _require_int(row.get("S4_LOWER_BOUND"), "owner S4 floor")
    credit = (4 * s4_floor) // 7
    if (
        s3_bound != owner.s3_upper_bound
        or credit != _require_int(row.get("FOURTH_ORDER_CREDIT"), "owner credit")
        or K20_S1 - K20_S2 + s3_bound - credit != owner.family_upper_bound
    ):
        raise AssertionError("the owner row no longer reproduces its family bound")
    return {
        "row": row,
        "triples": triples,
        "doubles": doubles,
        "caps": caps,
        "wedge_count": wedge_count,
        "open_wedge_lower_bound": _require_int(
            degree_class.get("OPEN_WEDGE_LOWER_BOUND"), "degree-class open-wedge bound"
        ),
        "s4_floor": s4_floor,
        "fourth_order_credit": credit,
    }


def _configured_solver(wall_limit_seconds: float) -> Any:
    from ortools.sat.python import cp_model

    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = wall_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    solver.parameters.log_search_progress = False
    return solver


def _open_wedge_support_model(
    profile: DegreeProfile, open_wedge_ceiling: int
) -> tuple[Any, dict[Triple, Any], dict[Pair, Any], int]:
    """Exact R10 support model plus a ceiling on overlap-graph open wedges."""

    model, triple_vars, double_vars, triples_by_pair = support_model(profile)
    adjacency: dict[Pair, Any] = {}
    for pair, double_var in double_vars.items():
        variable = model.NewBoolVar(f"overlap_{pair[0]}_{pair[1]}")
        model.Add(variable == sum(triples_by_pair[pair]) + double_var)
        adjacency[pair] = variable

    def adjacent(first: int, second: int) -> Any:
        return adjacency[(min(first, second), max(first, second))]

    indicators: list[Any] = []
    for center in range(K20_TICKET_COUNT):
        others = (ticket for ticket in range(K20_TICKET_COUNT) if ticket != center)
        for first, second in combinations(others, 2):
            indicator = model.NewBoolVar(f"open_{center}_{first}_{second}")
            # A wedge first-center-second is open exactly when its ends do not overlap.
            model.Add(
                indicator
                >= adjacent(center, first)
                + adjacent(center, second)
                - adjacent(first, second)
                - 1
            )
            indicators.append(indicator)
    model.Add(sum(indicators) <= open_wedge_ceiling)
    return model, triple_vars, double_vars, len(indicators)


def exact_support_triangle_refutation(
    profile: DegreeProfile,
    *,
    refuted_triangle_count: int,
    wall_limit_seconds: float = NATIVE_SUPPORT_REFUTATION_WALL_LIMIT_SECONDS,
) -> dict[str, object]:
    """Refute every realization with at least refuted_triangle_count graph triangles."""

    wedge_count = overlap_wedge_count(profile)
    ceiling = wedge_count - 3 * refuted_triangle_count
    if ceiling < 0:
        raise ValueError("the refuted triangle count exceeds the wedge identity")
    model, _, _, indicator_count = _open_wedge_support_model(profile, ceiling)
    solver = _configured_solver(wall_limit_seconds)
    status = str(solver.StatusName(solver.Solve(model)))
    certified = status == "INFEASIBLE"
    return {
        "ROUTE": "B_EXACT_SUPPORT_MODEL_OPEN_WEDGE_REFUTATION",
        "STATUS": status,
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE" if certified else "NOT_CERTIFIED",
        "WEDGE_COUNT": wedge_count,
        "REFUTED_GRAPH_TRIANGLE_COUNT": refuted_triangle_count,
        "OPEN_WEDGE_CEILING_REFUTED": ceiling,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": ceiling + 1 if certified else None,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": refuted_triangle_count - 1 if certified else None,
        "OPEN_WEDGE_INDICATOR_COUNT": indicator_count,
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
    }


def witness_open_wedge_check(
    profile: DegreeProfile,
    triples: Sequence[Triple],
    doubles: Sequence[Pair],
    *,
    wall_limit_seconds: float = NATIVE_WITNESS_CHECK_WALL_LIMIT_SECONDS,
) -> dict[str, object]:
    """Show the refutation model accepts a real witness at exactly its open-wedge count."""

    witness_triangles = graph_triangle_count(overlap_edges(triples, doubles))
    witness_open_wedges = overlap_wedge_count(profile) - 3 * witness_triangles
    statuses: dict[str, str] = {}
    for label, ceiling in (
        ("AT_WITNESS_COUNT", witness_open_wedges),
        ("ONE_BELOW_WITNESS_COUNT", witness_open_wedges - 1),
    ):
        model, triple_vars, double_vars, _ = _open_wedge_support_model(profile, ceiling)
        triple_set = {tuple(sorted(triple)) for triple in triples}
        double_set = {tuple(sorted(pair)) for pair in doubles}
        for triple, variable in triple_vars.items():
            model.Add(variable == int(triple in triple_set))
        for pair, variable in double_vars.items():
            model.Add(variable == int(pair in double_set))
        solver = _configured_solver(wall_limit_seconds)
        statuses[label] = str(solver.StatusName(solver.Solve(model)))
    if statuses != {"AT_WITNESS_COUNT": "OPTIMAL", "ONE_BELOW_WITNESS_COUNT": "INFEASIBLE"}:
        raise AssertionError(f"open-wedge model miscounts the committed witness: {statuses}")
    return {
        "WITNESS_SOURCE": EXPECTED_OWNER_SOURCE,
        "WITNESS_GRAPH_TRIANGLES": witness_triangles,
        "WITNESS_OPEN_WEDGES": witness_open_wedges,
        "FIXED_WITNESS_STATUS_BY_CEILING": statuses,
        "STATUS": "PASS",
    }


def complement_route_attempt(
    profile: DegreeProfile,
    triples: Sequence[Triple],
    doubles: Sequence[Pair],
) -> dict[str, object]:
    """Rerun the unchanged R15 complement-triangle model for the owner (route a)."""

    complement_degrees = tuple(K20_TICKET_COUNT - 1 - (6 + degree) for degree in profile)
    identity_constant = (
        comb(K20_TICKET_COUNT, 3)
        - (sum(complement_degrees) // 2) * (K20_TICKET_COUNT - 2)
        + sum(comb(degree, 2) for degree in complement_degrees)
    )
    started = monotonic()
    try:
        # Graph triangles never exceed the identity constant, so passing it keeps
        # R15's monotonicity guard non-binding; the owner cap is compared below.
        certificate = complement_triangle_bound(profile, triples, doubles, identity_constant)
    except RuntimeError as exc:
        return {
            "ROUTE": "A_R15_COMPLEMENT_TRIANGLE_MODEL",
            "STATUS": "NO_SOLUTION",
            "ERROR": str(exc),
            "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": None,
            "SOLVER_ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
        }
    return {
        "ROUTE": "A_R15_COMPLEMENT_TRIANGLE_MODEL",
        **certificate,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": certificate["GRAPH_TRIANGLE_UPPER_BOUND"],
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
    }


def _owner_bound(wedge_count: int, triangle_cap: int, credit: int) -> tuple[int, int]:
    s3_bound = s3_sum_from_wedges_and_triangles(
        wedge_count, triangle_cap - K20_TRIPLE_SUPPORT_COUNT
    )
    return s3_bound, K20_S1 - K20_S2 + s3_bound - credit


def recompute_family_bound(
    bounds: dict[DegreeProfile, int],
    *,
    owner: DegreeProfile,
    refined_owner_bound: int,
    cursor: DegreeProfile,
    cursor_bound: int,
) -> tuple[int, str, str, list[str]]:
    """Return max(refined owner, cursor ceiling, other resolved bounds) and its stop state."""

    if owner not in bounds or cursor in bounds:
        raise AssertionError("the owner must be resolved and the cursor unresolved")
    if refined_owner_bound > bounds[owner]:
        raise AssertionError("a refined owner bound may not exceed its committed bound")
    effective = {**bounds, owner: refined_owner_bound}
    family_bound = max(cursor_bound, *effective.values())
    if family_bound <= INCUMBENT:
        task_status, family_status = "SUCCESS_A_FAMILY_CLOSED", "CLOSED"
    elif refined_owner_bound <= cursor_bound:
        task_status = "SUCCESS_B_OWNER_ELIMINATED_CURSOR_LOAD_BEARING"
        family_status = "CURRENT_OWNER_ELIMINATED_CURSOR_LOAD_BEARING"
    elif refined_owner_bound < bounds[owner]:
        task_status = "SUCCESS_C_OWNER_STRICTLY_TIGHTENED"
        family_status = "OPEN_STRICTLY_TIGHTENED"
    else:
        task_status, family_status = "BLOCKED_NO_CERTIFIED_OWNER_TIGHTENING", "OPEN"
    bound_owners = sorted(
        (profile_identity(p) for p, bound in effective.items() if bound == family_bound),
        reverse=True,
    )
    if cursor_bound == family_bound:
        bound_owners.insert(0, profile_identity(cursor))
    return family_bound, task_status, family_status, bound_owners


def compute_owner_refinement_result(*, run_complement_route: bool = True) -> dict[str, object]:
    """Certify a tighter owner cap and recompute the family maximum."""

    started = monotonic()
    primitives = canonical_primitive_preflight()
    r16_hashes = r16_freeze_regression()
    runtime = solver_runtime_preflight()
    r16 = _read_result(R16_RESULT_FILENAME)
    bounds, sources = post_r16_bound_ledger()

    owner_profiles = [profile for profile, bound in bounds.items() if bound == START_OWNER_BOUND]
    if owner_profiles != [EXPECTED_OWNER_PROFILE] or max(bounds.values()) != START_OWNER_BOUND:
        raise AssertionError("the post-R16 owner is not the unique packet owner")
    if sources[EXPECTED_OWNER_PROFILE] != EXPECTED_OWNER_SOURCE:
        raise AssertionError("the owner certificate source changed")
    owner_ids = cast(list[object], r16["PRIOR_RESOLVED_FAMILY_BOUND_OWNER_PROFILES"])
    if [_decode_profile(raw, "R16 owner") for raw in owner_ids] != [EXPECTED_OWNER_PROFILE]:
        raise AssertionError("R16 names a different family-bound owner")
    cursor = _decode_profile(r16.get("NEXT_ACTIVE_PROFILE"), "R16 next cursor")
    cursor_bound = _require_int(r16.get("NEXT_ACTIVE_BOUND"), "R16 next cursor bound")
    if cursor != EXPECTED_NEXT_CURSOR_PROFILE or cursor_bound != NEXT_CURSOR_BOUND:
        raise AssertionError("R16 cursor differs from the packet cursor")
    if cursor in bounds or coarse_profile_envelope(cursor).family_upper_bound != cursor_bound:
        raise AssertionError("the cursor is resolved or its coarse envelope moved")

    ledger = reconstruct_family_max_ledger()
    owner_record = next(r for r in ledger.records if r.profile == EXPECTED_OWNER_PROFILE)
    lineage = owner_lineage(owner_record)
    triples = cast(tuple[Triple, ...], lineage["triples"])
    doubles = cast(tuple[Pair, ...], lineage["doubles"])
    wedge_count = cast(int, lineage["wedge_count"])
    credit = cast(int, lineage["fourth_order_credit"])
    start_cap = owner_record.graph_triangle_upper_bound
    if start_cap != EXPECTED_OWNER_TRIANGLE_CAP or wedge_count != EXPECTED_OWNER_WEDGE_COUNT:
        raise AssertionError("owner wedge or triangle envelope changed")

    solver_profiles = (owner_record.profile,)
    assert_owner_only_solver_scope(solver_profiles, owner=owner_record.profile, cursor=cursor)
    routes: list[dict[str, object]] = []
    if run_complement_route:
        routes.append(complement_route_attempt(owner_record.profile, triples, doubles))
    witness_check = witness_open_wedge_check(owner_record.profile, triples, doubles)
    routes.append(
        exact_support_triangle_refutation(
            owner_record.profile, refuted_triangle_count=start_cap
        )
    )

    caps = [start_cap]
    caps.extend(
        cap
        for route in routes
        if type(cap := route.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND")) is int
    )
    refined_cap = min(caps)
    s4 = s4_floor_at_s3_maximizers()
    if s4["CERTIFIED_LOWER_BOUND"] != lineage["s4_floor"]:
        raise AssertionError("the reused S4 floor changed")
    refined_s3, refined_owner_bound = _owner_bound(wedge_count, refined_cap, credit)
    if refined_owner_bound > START_OWNER_BOUND:
        raise AssertionError("owner refinement weakened the committed owner bound")

    family_bound, task_status, family_status, bound_owners = recompute_family_bound(
        bounds,
        owner=owner_record.profile,
        refined_owner_bound=refined_owner_bound,
        cursor=cursor,
        cursor_bound=cursor_bound,
    )

    by_route = {cast(str, route["ROUTE"]): route for route in routes}
    route_b = by_route["B_EXACT_SUPPORT_MODEL_OPEN_WEDGE_REFUTATION"]
    route_a = by_route.get("A_R15_COMPLEMENT_TRIANGLE_MODEL")
    solver_status = (
        "INFEASIBLE_CERTIFIED"
        if route_b["STATUS"] == "INFEASIBLE"
        else "NOT_CERTIFIED_" + str(route_b["STATUS"])
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": task_status,
        "BASE_HEAD": BASE_HEAD,
        "R16_FREEZE_HEAD": R16_FREEZE_HEAD,
        "R16_FREEZE_TREE": R16_FREEZE_TREE,
        "R16_SOURCE_HASHES": r16_hashes,
        "R16_FREEZE_REGRESSION": "PASS",
        "CURRENT_OWNER_PROFILE": profile_identity(owner_record.profile),
        "CURRENT_OWNER_CERTIFICATE_SOURCE": owner_record.certificate_source,
        "START_OWNER_BOUND": START_OWNER_BOUND,
        "OWNER_TO_CURSOR_GAP": OWNER_TO_CURSOR_GAP,
        "OWNER_LINEAGE": {
            "REALIZABILITY": owner_record.realizability,
            "SUPPORT_SOLVER_STATUS": owner_record.support_solver_status,
            "SUPPORT_WITNESS_VALIDATED": True,
            "WEDGE_COUNT": wedge_count,
            "TRIANGLE_CAPS_BY_RELAXATION": lineage["caps"],
            "LOAD_BEARING_RELAXATION": LOAD_BEARING_RELAXATION,
            "LOAD_BEARING_OPEN_WEDGE_LOWER_BOUND": lineage["open_wedge_lower_bound"],
            "START_GRAPH_TRIANGLE_UPPER_BOUND": start_cap,
            "START_NONCORE_TRIANGLE_UPPER_BOUND": start_cap - K20_TRIPLE_SUPPORT_COUNT,
            "START_S3_UPPER_BOUND": owner_record.s3_upper_bound,
            "S4_LOWER_BOUND": lineage["s4_floor"],
            "FOURTH_ORDER_CREDIT": credit,
        },
        "TIGHTENING_PREFERENCE_ORDER_APPLIED": [
            "A_EXACT_COMPLEMENT_TRIANGLE_COUNT",
            "B_EXACT_NONCORE_TRIANGLE_CEILING",
        ],
        "ROUTE_A_COMPLEMENT_ATTEMPT": route_a if route_a is not None else "NOT_RUN",
        "ROUTE_B_EXACT_SUPPORT_REFUTATION": route_b,
        "ROUTE_B_WITNESS_NON_VACUITY": witness_check,
        "REFINED_GRAPH_TRIANGLE_UPPER_BOUND": refined_cap,
        "REFINED_NONCORE_TRIANGLE_UPPER_BOUND": refined_cap - K20_TRIPLE_SUPPORT_COUNT,
        "REFINED_S3_UPPER_BOUND": refined_s3,
        "S4_LOWER_BOUND_AT_S3_MAXIMIZERS": s4["CERTIFIED_LOWER_BOUND"],
        "EXACT_PROFILE_SPECIFIC_S4_MINIMUM": "NOT_COMPUTED",
        "OWNER_REFINED_BOUND": refined_owner_bound,
        "OWNER_ELIMINATED_BELOW_CURSOR": refined_owner_bound <= cursor_bound,
        "NEXT_CURSOR_PROFILE": profile_identity(cursor),
        "NEXT_CURSOR_BOUND": cursor_bound,
        "MAX_OTHER_RESOLVED_BOUND": max(
            bound for profile, bound in bounds.items() if profile != owner_record.profile
        ),
        "RESOLVED_PROFILE_LEDGER_COUNT": len(bounds),
        "FAMILY_UPPER_BOUND": family_bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": max(0, family_bound - INCUMBENT),
        "FAMILY_STATUS": family_status,
        "CURRENT_BOUND_OWNER": bound_owners[0],
        "CURRENT_BOUND_OWNERS": bound_owners,
        "CURRENT_BOUND_OWNER_KIND": (
            "UNRESOLVED_RANKED_CURSOR" if cursor_bound == family_bound else "RESOLVED_PROFILE"
        ),
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": solver_status,
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "ROUTE_A_NATIVE_WALL_SECONDS": NATIVE_S3_WALL_LIMIT_SECONDS,
            "ROUTE_B_NATIVE_WALL_SECONDS": NATIVE_SUPPORT_REFUTATION_WALL_LIMIT_SECONDS,
            "WITNESS_CHECK_NATIVE_WALL_SECONDS": NATIVE_WITNESS_CHECK_WALL_LIMIT_SECONDS,
            "EXTERNAL_TASK_HARD_TIMEOUT_SECONDS": EXTERNAL_TASK_HARD_TIMEOUT_SECONDS,
            "CP_SAT_SEARCH_WORKERS": 1,
        },
        "SOLVER_CERTIFIED_BOUND": refined_owner_bound,
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": monotonic() - started,
        "SOLVER_PROFILES_SENT": [profile_identity(p) for p in solver_profiles],
        "CURSOR_PROFILE_SOLVES": 0,
        "NO_CURSOR_WORK_STATUS": "PASS",
        "CURSOR_DESCENT_STARTED": False,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", required=True)
    parser.add_argument("--skip-complement-route", action="store_true")
    args = parser.parse_args()
    result = compute_owner_refinement_result(run_complement_route=not args.skip_complement_route)
    Path(args.write_result).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "OWNER_REFINED_BOUND",
                    "NEXT_CURSOR_BOUND",
                    "FAMILY_UPPER_BOUND",
                    "REMAINING_GAP",
                    "SOLVER_STATUS",
                    "SOLVER_ACTUAL_WALL_TIME_SECONDS",
                )
            },
            separators=(",", ":"),
        )
    )


__all__ = [
    "BASE_HEAD",
    "EXPECTED_NEXT_CURSOR_PROFILE",
    "EXPECTED_OWNER_PROFILE",
    "NEXT_CURSOR_BOUND",
    "R16_FREEZE_HEAD",
    "R16_SOURCE_HASHES",
    "RESULT_FILENAME",
    "START_OWNER_BOUND",
    "TASK_ID",
    "assert_owner_only_solver_scope",
    "compute_owner_refinement_result",
    "exact_support_triangle_refutation",
    "owner_lineage",
    "post_r16_bound_ledger",
    "r16_freeze_regression",
    "recompute_family_bound",
    "witness_open_wedge_check",
]


if __name__ == "__main__":
    main()
