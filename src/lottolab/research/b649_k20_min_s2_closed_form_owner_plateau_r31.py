"""Apply R30's closed-form Route 4 to its owner and the plateau it exposes (R31).

Authority is the R30 result committed at 6ba48113 and carried unchanged to
13d2e0b4, pinned by SHA-256. R30's own zero-solve replay rebuilds its complete
1,795-row ledger, the unresolved cursor and every certificate's triangle cap and
S4 floor, and asserts the sealed ledger digest.

R30 runs Route 4, the K4-motif S4 correction, only after an exact-support
refutation fails, so its final owner 66665555554422000000 never received it.
Route 4 needs no solver. Its premises are:

* a certificate that caps every realization of the profile at ``cap`` graph
  triangles, whose bound is exactly that cap's R13/R20 envelope;
* the global profile S4 floor, valid for every realization;
* the min-S2 structure fixed by the family's S2: pair overlaps at most one and
  label multiplicities two or three (R2).

Every realization has a triangle count t in 22..cap: the 22 triple supports
are distinct triangles, and the certificate excludes t > cap. A realization
with exactly t triangles has W - 3t open wedges, at least
K4(t) = ceil((sum_v C(g_v,3) - (g_max-2)(W-3t))/4) K4 quartets, and
S4 >= max(global floor, 448*K4(t)). The profile bound is the maximum over every
such t of S1 - S2 + S3(t) - floor(4*S4(t)/7), which rounds the exact rational
bound up by less than one. As in R30, the certificate is accepted only when
that maximum sits at the cap, and the catalog keeps the global S4 floor,
because a motif floor is valid only at its own triangle count.

Phase 1 certifies the unique owner (cap 265). Phase 2 reconstructs the exact
ledger plateau that the drop exposes and certifies each member. The 126 R18
class members share the cap, W and S4 floor but differ in sum C(g,3) and g_max,
so each member gets its own certificate rather than one class certificate.
Phase 3 recomputes the complete family maximum over the ledger and the
unresolved cursor. No solver is started.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import pairwise
from math import comb
from time import monotonic

from . import b649_k20_min_s2_current_cursor_class_owner_chase_r28 as r28
from . import b649_k20_min_s2_current_cursor_dynamic_family_max_r30 as r30
from . import b649_k20_min_s2_ss332_owner_class_to_cursor_r29 as r29
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_S1,
    K20_S2,
    K20_TICKET_CAPACITY,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
)

DegreeProfile = r28.DegreeProfile
Chase = r28.Chase

TASK_ID = "B649_K20_MIN_S2_R31_CLOSED_FORM_OWNER_PLATEAU_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-r31-closed-form-owner-plateau-r1"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "13d2e0b4be9dba05426e4df8a3648b38f424c154"
BASE_TREE = "2511cb03323b0cba7a76e4bb1cf906a9a216dcd0"
R30_HEAD = "6ba4811304ec6528738a0c0b38969901b264d241"
R30_RESULT = r30.RESULT_FILENAME
R30_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
R30_LEDGER_SHA256 = "55d439314e0df2955236b2263e7df7bae1a512ec8a5568d58c5a525b0c839b0a"
LEDGER_COUNT = 1_795
START_BOUND = 313_568_072
START_OWNER = decode_profile("66665555554422000000")
START_OWNER_CAP = 265
CURSOR = decode_profile("66666653222222222211")
CURSOR_BOUND = 313_556_760
PLATEAU_BOUND = 313_567_960
PLATEAU_COUNT = 126
INCUMBENT = r30.INCUMBENT
WITNESS_PROFILE = r30.WITNESS_PROFILE
WITNESS_UNION = r30.WITNESS_UNION
WITNESS_TRIANGLES = r30.WITNESS_TRIANGLES
K4_WEIGHTS = {
    "SIX_EDGES_WITH_CONTAINED_TRIPLE": 448,
    "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE": 679,
}
CAP_ROUTES = (r28.ROUTE_A, r28.ROUTE_CLASS)
REPLAY_SECONDS = 600.0
RESULT_DIRECTORY = r30.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-closed-form-owner-plateau-r31-result.json"
CERTIFIED = "CERTIFIED"
REJECTED = "REJECTED_PREMISE_FAILED"
NOT_AT_CAP = "NOT_APPLIED_ENVELOPE_MAXIMUM_BELOW_CAP"
NO_DROP = "NOT_APPLIED_NO_STRICT_TIGHTENING"
SUCCESS_A = "SUCCESS_A_CERTIFIED_FAMILY_UPPER_BOUND_REDUCTION"
SUCCESS_B = "SUCCESS_B_ROUTE4_OBSTRUCTION_AT_CURRENT_OWNER"
BOUND_RULE = "MAX_OVER_T_IN_22..CAP_OF_S1-S2+S3(T)-FLOOR(4*MAX(GLOBAL,448*K4(T))/7)"

object_row = r28.object_row
rows = r28.rows
integer = r28.integer


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=r28.repo_root())


def r30_authority() -> tuple[dict[str, object], str]:
    """The R30 result at the base: pinned digest, unchanged since R30, sealed facts."""

    relative = f"{RESULT_DIRECTORY}/{R30_RESULT}"
    blob = git("show", f"{BASE_HEAD}:{relative}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != R30_SHA256:
        raise AssertionError("sealed R30 fingerprint changed")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", R30_HEAD, BASE_HEAD],
        cwd=r28.repo_root(),
        check=False,
    )
    if ancestry.returncode != 0 or git("rev-parse", f"{R30_HEAD}:{relative}") != git(
        "rev-parse", f"{BASE_HEAD}:{relative}"
    ):
        raise AssertionError("the base does not carry the R30 result unchanged from R30")
    result = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": r30.TASK_ID,
        "TASK_STATUS": r30.SUCCESS_C,
        "FAMILY_UPPER_BOUND": START_BOUND,
        "MAX_RESOLVED_BOUND": START_BOUND,
        "FINAL_BOUND_OWNER_IDS": [profile_id(START_OWNER)],
        "NEXT_COMPETING_BOUND": PLATEAU_BOUND,
        "NEXT_ACTIVE_PROFILE": profile_id(CURSOR),
        "NEXT_ACTIVE_BOUND": CURSOR_BOUND,
        "RESOLVED_LEDGER_COUNT": LEDGER_COUNT,
        "FINAL_COMPLETE_LEDGER_SHA256": R30_LEDGER_SHA256,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": START_BOUND - INCUMBENT,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"R30 authority mismatch: {key}")
    return result, digest


def start_chase(deadline: float) -> tuple[Chase, str]:
    """R30's zero-solve replay of its sealed result; assert owner, cursor and ledger."""

    result, digest = r30_authority()
    chase = r30.replay_result(result, deadline)
    family, owners = r28.family_state(chase)
    if (
        (family, owners) != (START_BOUND, (START_OWNER,))
        or chase.catalog[START_OWNER].triangle_cap != START_OWNER_CAP
        or (chase.cursor, chase.cursor_bound) != (CURSOR, CURSOR_BOUND)
        or len(chase.bounds) != LEDGER_COUNT
        or r29.ledger_digest(chase) != R30_LEDGER_SHA256
        or r28.competing_bound(chase, owners) != PLATEAU_BOUND
    ):
        raise AssertionError("R30 owner, cursor or complete-ledger reconstruction failed")
    for log in (chase.attempts, chase.steps, chase.plateaus, chase.sequence, chase.nonvacuity):
        log.clear()
    chase.dispatched.clear()
    chase.failed.clear()
    chase.checked.clear()
    r30.record_owner(chase)
    return chase, digest


def k4_premises(profile: DegreeProfile) -> tuple[int, int, int]:
    """W, sum_v C(g_v,3) and g_max of the overlap graph of every realization."""

    degrees = [K20_TICKET_CAPACITY + d for d in profile]
    return overlap_wedge_count(profile), sum(comb(g, 3) for g in degrees), max(degrees)


def premise_failures(profile: DegreeProfile, cert: Certificate) -> list[str]:
    """Every Route-4 premise this certificate does not satisfy."""

    if cert.profile != profile:
        return ["CERTIFICATE_PROFILE_MISMATCH"]
    failures: list[str] = []
    if cert.relaxation not in CAP_ROUTES:
        failures.append("NOT_A_TRIANGLE_CAP_CERTIFICATE")
    if r30.k4_quartet_weights() != K4_WEIGHTS:
        failures.append("K4_QUARTET_WEIGHTS_CHANGED")
    cap, s4 = cert.triangle_cap, cert.s4
    if s4 != r28.profile_s4_floor(profile):
        failures.append("S4_NOT_THE_GLOBAL_PROFILE_FLOOR")
    if cap is None or not K20_TRIPLE_SUPPORT_COUNT <= cap <= overlap_wedge_count(profile) // 3:
        failures.append("TRIANGLE_CAP_OUT_OF_RANGE")
    elif s4 is not None and s4 >= 0 and bound_from_cap(profile, cap, s4)[1] != cert.bound:
        failures.append("BOUND_IS_NOT_THE_CAP_ENVELOPE")
    return failures


def envelope_term(profile: DegreeProfile, triangles: int, base: int) -> tuple[int, int, int, int]:
    """Bound, K4 floor, S4 floor and S3 at exactly ``triangles``, rounding checked."""

    wedges, choose3, top = k4_premises(profile)
    open_wedges = wedges - 3 * triangles
    excess = choose3 - (top - 2) * open_wedges
    k4, motif = r30.motif_s4_floor(profile, triangles)
    s4 = max(base, motif)
    s3, bound = bound_from_cap(profile, triangles, s4)
    exact = K20_S1 - K20_S2 + s3 - Fraction(4 * s4, 7)
    if (
        open_wedges < 0
        or k4 < 0
        or 4 * k4 < excess
        or (k4 > 0 and 4 * (k4 - 1) >= excess)
        or motif != min(K4_WEIGHTS.values()) * k4
        or not 0 <= bound - exact < 1
    ):
        raise AssertionError("Route-4 integer rounding is not exact")
    return bound, k4, s4, s3


def route4_certificate(profile: DegreeProfile, cert: Certificate) -> dict[str, object]:
    """All-t closed-form Route 4 for one certificate; never calls a solver."""

    wedges, choose3, top = k4_premises(profile)
    row: dict[str, object] = {
        "PROFILE_ID": profile_id(profile),
        "SOURCE_RESULT": cert.source_result,
        "SOURCE_ROW": cert.source_row,
        "SOURCE_RELAXATION": cert.relaxation,
        "TRIANGLE_CAP": cert.triangle_cap,
        "GLOBAL_S4_FLOOR": cert.s4,
        "WEDGE_COUNT": wedges,
        "SUM_GRAPH_DEGREE_CHOOSE_3": choose3,
        "MAX_GRAPH_DEGREE": top,
        "PREVIOUS_BOUND": cert.bound,
    }
    failures = premise_failures(profile, cert)
    if failures:
        return {**row, "STATUS": REJECTED, "PREMISE_FAILURES": failures, "NEW_BOUND": cert.bound}
    cap, base = integer(cert.triangle_cap), integer(cert.s4)
    terms = [
        (t, *envelope_term(profile, t, base)) for t in range(K20_TRIPLE_SUPPORT_COUNT, cap + 1)
    ]
    bound = max(term[1] for term in terms)
    argmax = max(t for t, b, *_ in terms if b == bound)
    _, at_cap, k4, s4, s3 = terms[-1]
    status = NO_DROP if bound >= cert.bound else CERTIFIED if argmax == cap else NOT_AT_CAP
    return {
        **row,
        "STATUS": status,
        "PREMISE_FAILURES": [],
        "ROUTE": r30.ROUTE_MOTIF,
        "MIN_TRIANGLES": K20_TRIPLE_SUPPORT_COUNT,
        "TRIANGLE_COUNTS_CHECKED": len(terms),
        "OPEN_WEDGES_AT_CAP": wedges - 3 * cap,
        "K4_LOWER_BOUND_AT_CAP": k4,
        "K4_QUARTET_WEIGHTS": dict(K4_WEIGHTS),
        "S4_LOWER_BOUND_AT_CAP": s4,
        "S3_AT_CAP": s3,
        "BOUND_AT_CAP": at_cap,
        "MAX_BOUND_BELOW_CAP": max((term[1] for term in terms[:-1]), default=None),
        "ENVELOPE_MAXIMIZED_AT_TRIANGLES": argmax,
        "ENVELOPE_STRICTLY_INCREASING_IN_T": all(a[1] < b[1] for a, b in pairwise(terms)),
        "ROUNDING": "FLOOR_4_S4_OVER_7_ROUNDS_THE_EXACT_BOUND_UP_BY_LESS_THAN_ONE",
        "BOUND_RULE": BOUND_RULE,
        "NEW_BOUND": bound if status == CERTIFIED else cert.bound,
    }


def certify(chase: Chase, profile: DegreeProfile, index: int) -> dict[str, object]:
    """Route 4 on one current resolved family-max owner, adopted only when certified."""

    r28.assert_owner_scope(chase, (profile,))
    cert = chase.catalog[profile]
    before, _ = r28.family_state(chase)
    row = route4_certificate(profile, cert)
    if row["STATUS"] == CERTIFIED:
        bound = integer(row["NEW_BOUND"])
        if profile == WITNESS_PROFILE and bound < WITNESS_UNION:
            raise AssertionError("Route 4 fell below the realized witness portfolio")
        chase.bounds[profile] = bound
        chase.catalog[profile] = replace(
            cert,
            bound=bound,
            s3=integer(row["S3_AT_CAP"]),
            source_result=RESULT_FILENAME,
            source_row=f"ROUTE4_CERTIFICATES[{index}]",
            relaxation=r30.ROUTE_MOTIF,
        )
        r30.record_owner(chase)
    after, owners = r28.family_state(chase)
    return {
        "CERTIFICATE_INDEX": index,
        **row,
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_BOUND_AFTER": after,
        "OWNER_COUNT_AFTER": len(owners),
    }


def plateau_members(chase: Chase) -> tuple[DegreeProfile, ...]:
    """The exact resolved ledger level that owns the family after the owner's drop."""

    family, owners = r28.family_state(chase)
    members = tuple(sorted((p for p, b in chase.bounds.items() if b == family), reverse=True))
    if (
        family != PLATEAU_BOUND
        or members != owners
        or chase.cursor_bound is None
        or chase.cursor_bound >= family
        or len(members) != PLATEAU_COUNT
    ):
        raise AssertionError("the exposed plateau is not the exact 126-profile ledger level")
    return members


def shared_class_check(chase: Chase, members: Sequence[DegreeProfile]) -> dict[str, object]:
    """One class certificate needs one premise tuple; otherwise certify per member."""

    premises = {
        (chase.catalog[p].triangle_cap, chase.catalog[p].s4, *k4_premises(p)) for p in members
    }
    choose3 = [k4_premises(p)[1] for p in members]
    return {
        "MODE": "SHARED_CLASS_CERTIFICATE" if len(premises) == 1 else "PER_MEMBER_CLOSED_FORM",
        "REASON": "IDENTICAL_PREMISES"
        if len(premises) == 1
        else "MEMBERS_DIFFER_IN_SUM_GRAPH_DEGREE_CHOOSE_3_OR_MAX_GRAPH_DEGREE",
        "DISTINCT_PREMISE_TUPLES": len(premises),
        "TRIANGLE_CAPS": sorted({integer(chase.catalog[p].triangle_cap) for p in members}),
        "GLOBAL_S4_FLOORS": sorted({integer(chase.catalog[p].s4) for p in members}),
        "WEDGE_COUNTS": sorted({k4_premises(p)[0] for p in members}),
        "SUM_GRAPH_DEGREE_CHOOSE_3_RANGE": [min(choose3), max(choose3)],
        "MAX_GRAPH_DEGREES": sorted({k4_premises(p)[2] for p in members}),
        "SOURCE_RELAXATIONS": sorted({chase.catalog[p].relaxation for p in members}),
    }


def full_recompute(chase: Chase) -> dict[str, object]:
    """Family maximum from the serialized ledger rows plus the unresolved cursor."""

    ledger = r29.ledger(chase)
    terms = [integer(row["CURRENT_BOUND"]) for row in ledger]
    if chase.cursor is None or chase.cursor_bound is None:
        raise AssertionError("the unresolved frontier must keep its cursor term")
    family = max(*terms, chase.cursor_bound)
    owners = [str(row["PROFILE_ID"]) for row in ledger if row["CURRENT_BOUND"] == family]
    if chase.cursor_bound == family:
        owners.insert(0, profile_id(chase.cursor))
    state, live = r28.family_state(chase)
    levels = sorted(set(terms), reverse=True)[:3]
    if (
        (family, owners) != (state, list(map(profile_id, live)))
        or len(ledger) != LEDGER_COUNT
        or coarse_profile_envelope(chase.cursor).family_upper_bound != chase.cursor_bound
        or family < WITNESS_UNION
    ):
        raise AssertionError("independent family recomputation disagrees")
    return {
        "STATUS": "PASS",
        "LEDGER_ROWS_SCANNED": len(ledger),
        "UNRESOLVED_FRONTIER_PROFILE": profile_id(chase.cursor),
        "UNRESOLVED_FRONTIER_BOUND": chase.cursor_bound,
        "UNRESOLVED_FRONTIER_SOURCE": "R30_RANKED_LOOKUP_CURSOR_R8_COARSE_ENVELOPE",
        "FAMILY_UPPER_BOUND": family,
        "OWNER_IDS": owners,
        "TOP_LEDGER_LEVELS": [{"BOUND": b, "PROFILE_COUNT": terms.count(b)} for b in levels],
    }


def witness_route4() -> dict[str, object]:
    """This module's certificate on the realized witness profile at its 270 triangles."""

    s4 = r28.profile_s4_floor(WITNESS_PROFILE)
    s3, bound = bound_from_cap(WITNESS_PROFILE, WITNESS_TRIANGLES, s4)
    cert = Certificate(
        WITNESS_PROFILE,
        bound,
        "SYNTHETIC_REALIZED_CAP",
        "STS13_WITNESS",
        "REALIZED_WITNESS",
        s3,
        s4,
        WITNESS_TRIANGLES,
        r28.ROUTE_CLASS,
    )
    row = route4_certificate(WITNESS_PROFILE, cert)
    if row["STATUS"] != CERTIFIED:
        raise AssertionError("witness-profile Route-4 premises failed")
    if integer(row["NEW_BOUND"]) < WITNESS_UNION:
        raise AssertionError("Route 4 over-tightens the realizable STS(13) witness")
    return {
        "STATUS": "PASS",
        "PROFILE_ID": profile_id(WITNESS_PROFILE),
        "REALIZED_TRIANGLES": WITNESS_TRIANGLES,
        "EXACT_ANY_PRIZE_UNION": WITNESS_UNION,
        "ROUTE4_BOUND_AT_REALIZED_CAP": row["NEW_BOUND"],
        "SLACK_UNDER_ROUTE4_BOUND": integer(row["NEW_BOUND"]) - WITNESS_UNION,
    }


def compute_result() -> dict[str, object]:
    primitives = r28.canonical_primitive_preflight()
    if primitives["STATUS"] != "PASS":
        raise AssertionError("canonical primitive gate failed")
    witness = r30.witness_soundness()
    witness_check = witness_route4()
    chase, digest = start_chase(monotonic() + REPLAY_SECONDS)
    start_ledger = r29.ledger_digest(chase)
    certificates = [certify(chase, START_OWNER, 0)]
    owner = certificates[0]
    members: tuple[DegreeProfile, ...] = ()
    shared: dict[str, object] | None = None
    if owner["STATUS"] == CERTIFIED:
        members = plateau_members(chase)
        shared = shared_class_check(chase, members)
        for p in members:
            certificates.append(certify(chase, p, len(certificates)))
    plateau = certificates[1:]
    certified = sum(row["STATUS"] == CERTIFIED for row in plateau)
    recompute = full_recompute(chase)
    family, owners = r28.family_state(chase)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": SUCCESS_A if family < START_BOUND else SUCCESS_B,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "INPUT_AUTHORITY": "R30_SEALED_RESULT_ZERO_SOLVE_REPLAY",
        "AUTHORITY_FINGERPRINT": {
            "R30_HEAD": R30_HEAD,
            "R30_RESULT_SHA256": digest,
            "R30_FINAL_LEDGER_SHA256": R30_LEDGER_SHA256,
            "SEALED_REPLAY": "PASS",
        },
        "START_FAMILY_BOUND": START_BOUND,
        "START_OWNER_PROFILE": profile_id(START_OWNER),
        "START_OWNER_TRIANGLE_CAP": START_OWNER_CAP,
        "START_COMPLETE_LEDGER_SHA256": start_ledger,
        "ROUTE4_OWNER_STATUS": owner["STATUS"],
        "ROUTE4_OWNER_BOUND": owner["NEW_BOUND"],
        "OBSTRUCTION": None
        if owner["STATUS"] == CERTIFIED
        else {"PROFILE_ID": owner["PROFILE_ID"], "REASON": owner["STATUS"]},
        "PLATEAU_BOUND": PLATEAU_BOUND if members else None,
        "PLATEAU_OWNER_COUNT": len(members),
        "PLATEAU_PROFILE_IDS": list(map(profile_id, members)),
        "PLATEAU_MEMBERSHIP_SHA256": r30.membership_digest(members),
        "PLATEAU_CERTIFIED_COUNT": certified,
        "PLATEAU_REMAINING_OWNER_COUNT": len(members) - certified,
        "PLATEAU_MAX_NEW_BOUND": max((integer(row["NEW_BOUND"]) for row in plateau), default=None),
        "PLATEAU_CERTIFICATE_MODE": shared,
        "ALL_T_CERTIFICATE_STATUS": "PASS"
        if all(
            row["STATUS"] == CERTIFIED
            and row["TRIANGLE_COUNTS_CHECKED"]
            == integer(row["TRIANGLE_CAP"]) - K20_TRIPLE_SUPPORT_COUNT + 1
            for row in certificates
        )
        else "PARTIAL",
        "ROUTE4_CERTIFICATES": certificates,
        "OWNER_CLASS_SEQUENCE": chase.sequence,
        "FULL_LEDGER_RECOMPUTATION": recompute,
        "FAMILY_UPPER_BOUND": family,
        "FINAL_BOUND_OWNER_IDS": list(map(profile_id, owners)),
        "FINAL_BOUND_OWNERS": r28.owner_rows(chase, owners),
        "NEXT_COMPETING_BOUND": r28.competing_bound(chase, owners),
        "NEXT_ACTIVE_PROFILE": profile_id(CURSOR),
        "NEXT_ACTIVE_BOUND": chase.cursor_bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "CERTIFIED_FAMILY_DROP": START_BOUND - family,
        "FAMILY_STATUS": "CLOSED"
        if family <= INCUMBENT
        else "OPEN_STRICTLY_TIGHTENED"
        if family < START_BOUND
        else "OPEN_UNCHANGED",
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "SOUNDNESS_WITNESS_STATUS": witness["STATUS"],
        "SOUNDNESS_WITNESS": witness,
        "R31_ROUTE4_ON_WITNESS_PROFILE": witness_check,
        "METHOD_CAPABILITY": r30.method_capability(witness),
        "FINAL_RESOLVED_LEDGER": r29.ledger(chase),
        "FINAL_COMPLETE_LEDGER_SHA256": r29.ledger_digest(chase),
        "RESOLVED_LEDGER_COUNT": len(chase.bounds),
        "SOLVER_CALLS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "FULL_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "JUDGE_DISPATCH": "SUPPRESSED",
    }


def replay_result(result: Mapping[str, object], deadline: float) -> Chase:
    """Re-derive every sealed R31 certificate on the R30 replay; assert the ledger."""

    chase, _ = start_chase(deadline)
    for index, raw in enumerate(rows(result["ROUTE4_CERTIFICATES"])):
        sealed = object_row(raw)
        if certify(chase, decode_profile(sealed["PROFILE_ID"]), index) != sealed:
            raise AssertionError("Route-4 certificate replay diverged")
    if (
        r29.ledger(chase) != result["FINAL_RESOLVED_LEDGER"]
        or r29.ledger_digest(chase) != result["FINAL_COMPLETE_LEDGER_SHA256"]
        or r28.family_state(chase)[0] != result["FAMILY_UPPER_BOUND"]
        or chase.sequence != result["OWNER_CLASS_SEQUENCE"]
    ):
        raise AssertionError("complete R31 ledger replay diverged")
    return chase


SUMMARY_KEYS = (
    "TASK_STATUS",
    "ROUTE4_OWNER_BOUND",
    "PLATEAU_OWNER_COUNT",
    "PLATEAU_CERTIFIED_COUNT",
    "FAMILY_UPPER_BOUND",
    "FINAL_BOUND_OWNER_IDS",
    "REMAINING_GAP",
)


def main() -> None:
    target = r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME
    if target.exists():
        raise AssertionError("only a new exact R31 result output is authorized")
    result = compute_result()
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    print(json.dumps({k: result[k] for k in SUMMARY_KEYS}), flush=True)


if __name__ == "__main__":
    main()
