"""Route B, the contained-triple K4 split, on R31's owners and next plateau (R32).

Authority is the R31 result committed at 74c0ff8a, pinned by SHA-256. R31's own
zero-solve replay rebuilds R30's 1,795-row ledger, re-derives every R31 Route-4
certificate and asserts the sealed R31 ledger digest. Its family maximum
313,567,400 is owned by seven profiles whose triangle caps come from R30
exact-support refutations. The next ledger level holds 104 profiles at
313,567,288, and the unresolved cursor sits at 313,556,760.

Route B. In the min-S2 family pair overlaps are at most one and every label has
multiplicity two or three, so a ticket with triple degree d has graph degree
g = 6 + d. A K4 quartet then has one of two exact local profiles: six pair
labels (679 common outcomes) or one contained triple plus three pair labels
(448). Two triples inside one quartet would share two tickets, so a K4 holds at
most one contained triple. A contained-triple K4 is a triple support T plus a
common neighbour outside T. A vertex v of T has g_v - 2 neighbours outside T,
so T lies in at most min_v (g_v - 2) <= sum_{v in T} (g_v - 2) / 3 of them.
Each ticket lies in d_v triple supports, hence at most
A_max = floor(sum_v d_v (g_v - 2) / 3) K4 quartets contain a triple. With at
least K4 quartets (R30's open-wedge K4 floor at exactly t triangles) and every
S4 term non-negative,

    S4 >= 448 a + 679 (K4 - a) = 679 K4 - 231 min(K4, A_max),

because the right side increases in the true K4 count and is least when as many
quartets as allowed carry the cheaper profile. Route 4 (448 K4) is the special
case A_max >= K4.

Certificates. A cap is read from the profile's catalog certificate and accepted
only after the cited R30 GROUP_ATTEMPTS row is re-checked as the CP-SAT
INFEASIBLE refutation of exactly that profile at cap + 1. FEASIBLE, UNKNOWN and
every other row are rejected; no cap is inferred from a bound. The profile bound
is the maximum over every t in 22..cap of
S1 - S2 + S3(t) - floor(4 * max(global, S4_B(t)) / 7), with exact integer floors
and ceilings asserted at every t. As in R31 a certificate is adopted only when
that maximum sits at the cap, and the catalog keeps the global S4 floor.

Phase 1 certifies the seven owners. Phase 2 certifies each member of the exact
104-profile ledger level they expose. Each member cites its own refutation and
the members differ in sum C(g,3) and g_max, so no common class certificate
applies. Phase 3 recomputes the complete family maximum and stops at the first
level outside the 7 + 104 slice. No solver, census or outcome enumeration is
run: the STS(13) witness check recounts graph structure only and reads its
exact union and S4 from the pinned R31 result.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, pairwise
from math import comb
from time import monotonic

from . import b649_k20_min_s2_closed_form_owner_plateau_r31 as r31
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_S1,
    K20_S2,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
)

r28 = r31.r28
r29 = r31.r29
r30 = r31.r30
DegreeProfile = r31.DegreeProfile
Chase = r31.Chase
Proofs = Sequence[Mapping[str, object]]
Term = tuple[int, int, int, int, int, int]

TASK_ID = "B649_K20_MIN_S2_R32_ROUTE_B_CURRENT_OWNER_REFINEMENT_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-r32-route-b-current-owner-refinement-r1"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "74c0ff8a07572f196ad7826b237df9329662f9fa"
BASE_TREE = "2fe8a23896b8bcae6c76d5742e4c44a26b52e936"
R31_RESULT = r31.RESULT_FILENAME
R31_SHA256 = "eb11a410d2d4a67c6151b7044b4f37f3dde8dd7c40cf7c5740c3bf4d6f9b7770"
R31_LEDGER_SHA256 = "ffa83c30a06565b63a5fc1963cefd86d465091a9152cbd254bedd1eaefb5dec3"
R30_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
LEDGER_COUNT = 1_795
START_BOUND = 313_567_400
START_OWNERS = tuple(
    decode_profile(p)
    for p in (
        "66666665444322000000",
        "66666664444431000000",
        "66666655544411100000",
        "66666655544331000000",
        "66666555555311100000",
        "66666555555222000000",
        "66666555554421000000",
    )
)
PLATEAU_BOUND = 313_567_288
PLATEAU_COUNT = 104
CURSOR = r31.CURSOR
CURSOR_BOUND = 313_556_760
INCUMBENT = r31.INCUMBENT
REFERENCE_OWNER = r31.START_OWNER
REFERENCE_START_BOUND = r31.START_BOUND
REFERENCE_ROUTE_B_BOUND = 313_401_180
WITNESS_PROFILE = r31.WITNESS_PROFILE
WITNESS_UNION = r31.WITNESS_UNION
WITNESS_TRIANGLES = r31.WITNESS_TRIANGLES
WITNESS_ROUTE_B_S4_FLOOR = 325_486
WITH_TRIPLE = "SIX_EDGES_WITH_CONTAINED_TRIPLE"
WITHOUT_TRIPLE = "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE"
K4_WEIGHTS = {WITH_TRIPLE: 448, WITHOUT_TRIPLE: 679}
CAP_SOURCE_RESULT = r30.RESULT_FILENAME
CAP_SOURCE_ROUTE = r28.ROUTE_A
ROUTE_B = "D4_K4_CONTAINED_TRIPLE_SPLIT_S4_CORRECTION"
REPLAY_SECONDS = 600.0
RESULT_DIRECTORY = r31.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-route-b-current-owner-refinement-r32-result.json"
CERTIFIED = r31.CERTIFIED
REJECTED = r31.REJECTED
NOT_AT_CAP = r31.NOT_AT_CAP
NO_DROP = r31.NO_DROP
SUCCESS_A = "SUCCESS_A_CERTIFIED_FAMILY_UPPER_BOUND_REDUCTION"
SUCCESS_B = "SUCCESS_B_ROUTE_B_OBSTRUCTION_INSIDE_THE_SLICE"
BOUND_RULE = (
    "MAX_OVER_T_IN_22..CAP_OF_S1-S2+S3(T)-FLOOR(4*MAX(GLOBAL,679*K4(T)-231*MIN(K4(T),A_MAX))/7)"
)

object_row = r28.object_row
rows = r28.rows
integer = r28.integer


def r31_authority() -> tuple[dict[str, object], str]:
    """The R31 result at the base: exact tree, pinned digest, sealed facts."""

    if r31.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("the base tree changed")
    blob = r31.git("show", f"{BASE_HEAD}:{RESULT_DIRECTORY}/{R31_RESULT}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != R31_SHA256:
        raise AssertionError("sealed R31 fingerprint changed")
    result = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": r31.TASK_ID,
        "TASK_STATUS": r31.SUCCESS_A,
        "FAMILY_UPPER_BOUND": START_BOUND,
        "FINAL_BOUND_OWNER_IDS": list(map(profile_id, START_OWNERS)),
        "NEXT_COMPETING_BOUND": PLATEAU_BOUND,
        "NEXT_ACTIVE_PROFILE": profile_id(CURSOR),
        "NEXT_ACTIVE_BOUND": CURSOR_BOUND,
        "RESOLVED_LEDGER_COUNT": LEDGER_COUNT,
        "FINAL_COMPLETE_LEDGER_SHA256": R31_LEDGER_SHA256,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": START_BOUND - INCUMBENT,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"R31 authority mismatch: {key}")
    if object_row(result["AUTHORITY_FINGERPRINT"]).get("R30_RESULT_SHA256") != R30_SHA256:
        raise AssertionError("R31 authority mismatch: R30_RESULT_SHA256")
    return result, digest


def sealed_level(result: Mapping[str, object], bound: int) -> tuple[DegreeProfile, ...]:
    """Profiles of one bound in the committed R31 ledger."""

    ledger = map(object_row, rows(result["FINAL_RESOLVED_LEDGER"]))
    return tuple(
        sorted(
            (decode_profile(r["PROFILE_ID"]) for r in ledger if r["CURRENT_BOUND"] == bound),
            reverse=True,
        )
    )


def start_chase(deadline: float) -> tuple[Chase, str, dict[str, object]]:
    """R31's zero-solve replay of its sealed result; assert owners, plateau and ledger."""

    result, digest = r31_authority()
    chase = r31.replay_result(result, deadline)
    family, owners = r28.family_state(chase)
    level = tuple(sorted((p for p, b in chase.bounds.items() if b == PLATEAU_BOUND), reverse=True))
    if (
        (family, owners) != (START_BOUND, START_OWNERS)
        or sealed_level(result, START_BOUND) != START_OWNERS
        or level != sealed_level(result, PLATEAU_BOUND)
        or len(level) != PLATEAU_COUNT
        or (chase.cursor, chase.cursor_bound) != (CURSOR, CURSOR_BOUND)
        or len(chase.bounds) != LEDGER_COUNT
        or r29.ledger_digest(chase) != R31_LEDGER_SHA256
        or r28.competing_bound(chase, owners) != PLATEAU_BOUND
    ):
        raise AssertionError("R31 owner, plateau or complete-ledger reconstruction failed")
    for log in (chase.attempts, chase.steps, chase.plateaus, chase.sequence, chase.nonvacuity):
        log.clear()
    chase.dispatched.clear()
    chase.failed.clear()
    chase.checked.clear()
    r30.record_owner(chase)
    return chase, digest, result


def r30_proofs() -> list[dict[str, object]]:
    """Every sealed R30 solver attempt, from the pinned and ancestry-checked R30 result."""

    result, _ = r31.r30_authority()
    return list(map(object_row, rows(result["GROUP_ATTEMPTS"])))


def structural_failures(profile: DegreeProfile) -> list[str]:
    """Min-S2 shape: 20 tickets of capacity 6, 22 triple supports, degrees sorted."""

    if (
        len(profile) != K20_TICKET_COUNT
        or any(type(d) is not int or not 0 <= d <= K20_TICKET_CAPACITY for d in profile)
        or list(profile) != sorted(profile, reverse=True)
    ):
        return ["PROFILE_NOT_A_K20_TRIPLE_DEGREE_SEQUENCE"]
    if sum(profile) != K20_TRIPLE_INCIDENCE_COUNT:
        return ["TRIPLE_INCIDENCES_ARE_NOT_THREE_PER_TRIPLE_SUPPORT"]
    return []


def k4_premises(profile: DegreeProfile) -> tuple[int, int, int]:
    """W, sum_v C(g_v,3) and g_max of the overlap graph of every realization."""

    degrees = [K20_TICKET_CAPACITY + d for d in profile]
    return overlap_wedge_count(profile), sum(comb(g, 3) for g in degrees), max(degrees)


def outside_degree_sum(profile: DegreeProfile) -> int:
    """sum_v d_v (g_v - 2): triple memberships times neighbours outside the triple."""

    return sum(d * (K20_TICKET_CAPACITY + d - 2) for d in profile)


def contained_triple_k4_cap(profile: DegreeProfile) -> int:
    """A_max: at most this many K4 quartets contain a triple support."""

    total = outside_degree_sum(profile)
    cap = total // 3
    if total < 0 or Fraction(cap) > Fraction(total, 3) or Fraction(cap + 1) <= Fraction(total, 3):
        raise AssertionError("A_max is not the exact floor")
    return cap


def route_b_s4_floor(k4: int, a_max: int) -> tuple[int, int]:
    """Contained-triple quartets and the S4 floor 679*K4 - 231*min(K4, A_max)."""

    if k4 < 0 or a_max < 0:
        raise AssertionError("K4 floor and A_max must be non-negative")
    light, heavy = K4_WEIGHTS[WITH_TRIPLE], K4_WEIGHTS[WITHOUT_TRIPLE]
    contained = min(k4, a_max)
    s4 = heavy * k4 - (heavy - light) * contained
    if s4 != light * contained + heavy * (k4 - contained) or s4 < light * k4:
        raise AssertionError("Route-B S4 split is not exact")
    return contained, s4


def envelope_term(profile: DegreeProfile, triangles: int, base: int, a_max: int) -> Term:
    """Bound, K4 floor, contained quartets, S4 and S3 at exactly ``triangles``."""

    wedges, choose3, top = k4_premises(profile)
    open_wedges = wedges - 3 * triangles
    if open_wedges < 0:
        raise AssertionError("triangle count exceeds the wedge identity")
    excess = choose3 - (top - 2) * open_wedges
    k4 = r30.k4_lower_bound([K20_TICKET_CAPACITY + d for d in profile], open_wedges)
    if k4 < 0 or 4 * k4 < excess or (k4 > 0 and 4 * (k4 - 1) >= excess):
        raise AssertionError("Route-B integer rounding is not exact: K4 ceiling")
    contained, floor = route_b_s4_floor(k4, a_max)
    s4 = max(base, floor)
    s3, bound = bound_from_cap(profile, triangles, s4)
    exact = K20_S1 - K20_S2 + s3 - Fraction(4 * s4, 7)
    if not 0 <= bound - exact < 1:
        raise AssertionError("Route-B integer rounding is not exact: S4 credit")
    return triangles, bound, k4, contained, s4, s3


def route_b_envelope(profile: DegreeProfile, cap: int, base: int) -> list[Term]:
    """One exact term for every permitted triangle count 22..cap."""

    a_max = contained_triple_k4_cap(profile)
    return [
        envelope_term(profile, t, base, a_max) for t in range(K20_TRIPLE_SUPPORT_COUNT, cap + 1)
    ]


def source_proof(cert: Certificate, proofs: Proofs) -> Mapping[str, object] | None:
    """The sealed R30 attempt a certificate cites, or None for any other source."""

    prefix = "GROUP_ATTEMPTS["
    row = cert.source_row
    if cert.source_result != CAP_SOURCE_RESULT or not (
        row.startswith(prefix) and row.endswith("]") and row[len(prefix) : -1].isdecimal()
    ):
        return None
    index = int(row[len(prefix) : -1])
    if index >= len(proofs) or proofs[index].get("ATTEMPT_INDEX") != index:
        return None
    return proofs[index]


def identity_failures(profile: DegreeProfile, cert: Certificate, proofs: Proofs) -> list[str]:
    """The cited proof must be the INFEASIBLE refutation of this profile at cap + 1."""

    proof = source_proof(cert, proofs)
    if proof is None:
        return ["CERTIFICATE_SOURCE_NOT_A_SEALED_R30_ATTEMPT"]
    if cert.relaxation != CAP_SOURCE_ROUTE or proof.get("ROUTE") != cert.relaxation:
        return ["NOT_A_VERIFIED_TRIANGLE_CAP_CERTIFICATE"]
    if cert.triangle_cap is None:
        return ["TRIANGLE_CAP_MISSING"]
    try:
        accepted = r28.r26.accepted_cap(proof, (profile,), cert.triangle_cap)
    except AssertionError:
        return ["SOURCE_PROOF_IDENTITY_MISMATCH"]
    if accepted is None:
        return ["SOURCE_PROOF_NOT_INFEASIBLE"]
    failures: list[str] = []
    if proof.get("TARGET_TRIANGLE_CAP") != cert.triangle_cap:
        failures.append("SOURCE_PROOF_TARGET_CAP_MISMATCH")
    if proof.get("TARGET_BOUND") != cert.bound:
        failures.append("SOURCE_PROOF_BOUND_MISMATCH")
    return failures


def premise_failures(profile: DegreeProfile, cert: Certificate, proofs: Proofs) -> list[str]:
    """Every Route-B premise this certificate does not satisfy."""

    if cert.profile != profile:
        return ["CERTIFICATE_PROFILE_MISMATCH"]
    failures = structural_failures(profile)
    if failures:
        return failures
    failures = identity_failures(profile, cert, proofs)
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


def route_b_certificate(
    profile: DegreeProfile, cert: Certificate, proofs: Proofs
) -> dict[str, object]:
    """All-t closed-form Route B for one certificate; never calls a solver."""

    structure = structural_failures(profile)
    if structure:
        return {
            "PROFILE_ID": profile_id(profile),
            "STATUS": REJECTED,
            "PREMISE_FAILURES": structure,
            "NEW_BOUND": cert.bound,
        }
    proof = source_proof(cert, proofs)
    wedges, choose3, top = k4_premises(profile)
    row: dict[str, object] = {
        "PROFILE_ID": profile_id(profile),
        "CERTIFICATE_SOURCE": {
            "SOURCE_RESULT": cert.source_result,
            "SOURCE_ROW": cert.source_row,
            "SOURCE_RELAXATION": cert.relaxation,
            "SOURCE_STATUS": None if proof is None else proof.get("STATUS"),
            "SOURCE_CERTIFICATE_KIND": None if proof is None else proof.get("CERTIFICATE_KIND"),
            "REFUTED_GRAPH_TRIANGLE_COUNT": None
            if proof is None
            else proof.get("REFUTED_GRAPH_TRIANGLE_COUNT"),
        },
        "CERTIFIED_TRIANGLE_CAP": cert.triangle_cap,
        "GLOBAL_S4_FLOOR": cert.s4,
        "WEDGE_COUNT": wedges,
        "SUM_GRAPH_DEGREE_CHOOSE_3": choose3,
        "MAX_GRAPH_DEGREE": top,
        "SUM_TRIPLE_DEGREE_TIMES_OUTSIDE_DEGREE": outside_degree_sum(profile),
        "A_MAX": contained_triple_k4_cap(profile),
        "PREVIOUS_BOUND": cert.bound,
    }
    failures = premise_failures(profile, cert, proofs)
    if failures:
        return {**row, "STATUS": REJECTED, "PREMISE_FAILURES": failures, "NEW_BOUND": cert.bound}
    cap, base = integer(cert.triangle_cap), integer(cert.s4)
    terms = route_b_envelope(profile, cap, base)
    bound = max(term[1] for term in terms)
    argmax = max(t for t, b, *_ in terms if b == bound)
    _, at_cap, k4, contained, s4, s3 = terms[-1]
    status = NO_DROP if bound >= cert.bound else CERTIFIED if argmax == cap else NOT_AT_CAP
    return {
        **row,
        "STATUS": status,
        "PREMISE_FAILURES": [],
        "ROUTE": ROUTE_B,
        "MIN_TRIANGLES": K20_TRIPLE_SUPPORT_COUNT,
        "TRIANGLE_COUNTS_CHECKED": len(terms),
        "OPEN_WEDGES_AT_CAP": wedges - 3 * cap,
        "K4_FLOOR": k4,
        "CONTAINED_TRIPLE_K4_AT_CAP": contained,
        "K4_QUARTET_WEIGHTS": dict(K4_WEIGHTS),
        "S4_FLOOR": s4,
        "ROUTE4_S4_FLOOR_AT_CAP": K4_WEIGHTS[WITH_TRIPLE] * k4,
        "S3_AT_CAP": s3,
        "BOUND_AT_CAP": at_cap,
        "MAX_BOUND_BELOW_CAP": max((term[1] for term in terms[:-1]), default=None),
        "ENVELOPE_MAXIMIZED_AT_TRIANGLES": argmax,
        "ENVELOPE_STRICTLY_INCREASING_IN_T": all(a[1] < b[1] for a, b in pairwise(terms)),
        "ALL_T_MAX_BOUND": bound,
        "ROUNDING": "FLOOR_4_S4_OVER_7_ROUNDS_THE_EXACT_BOUND_UP_BY_LESS_THAN_ONE",
        "BOUND_RULE": BOUND_RULE,
        "NEW_BOUND": bound if status == CERTIFIED else cert.bound,
    }


def certify(chase: Chase, profile: DegreeProfile, index: int, proofs: Proofs) -> dict[str, object]:
    """Route B on one current resolved family-max owner, adopted only when certified."""

    r28.assert_owner_scope(chase, (profile,))
    cert = chase.catalog[profile]
    before, _ = r28.family_state(chase)
    row = route_b_certificate(profile, cert, proofs)
    if row["STATUS"] == CERTIFIED:
        bound = integer(row["NEW_BOUND"])
        if profile == WITNESS_PROFILE and bound < WITNESS_UNION:
            raise AssertionError("Route B fell below the realized witness portfolio")
        chase.bounds[profile] = bound
        chase.catalog[profile] = replace(
            cert,
            bound=bound,
            s3=integer(row["S3_AT_CAP"]),
            source_result=RESULT_FILENAME,
            source_row=f"ROUTE_B_CERTIFICATES[{index}]",
            relaxation=ROUTE_B,
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


def plateau_members(chase: Chase, sealed: Sequence[DegreeProfile]) -> tuple[DegreeProfile, ...]:
    """The exact 104-profile R31 ledger level that owns the family after the owners drop."""

    family, owners = r28.family_state(chase)
    if (
        family != PLATEAU_BOUND
        or owners != tuple(sealed)
        or chase.cursor_bound is None
        or chase.cursor_bound >= family
        or len(owners) != PLATEAU_COUNT
    ):
        raise AssertionError("the exposed plateau is not the exact 104-profile ledger level")
    return owners


def certificate_mode(chase: Chase, members: Sequence[DegreeProfile]) -> dict[str, object]:
    """A shared certificate needs one source and one premise tuple; else per member."""

    def premises(p: DegreeProfile) -> tuple[object, ...]:
        cert = chase.catalog[p]
        return (cert.triangle_cap, cert.s4, *k4_premises(p), contained_triple_k4_cap(p))

    tuples = {premises(p) for p in members}
    sources = {(chase.catalog[p].source_result, chase.catalog[p].source_row) for p in members}
    shared = len(tuples) == 1 and len(sources) == 1
    choose3 = [k4_premises(p)[1] for p in members]
    return {
        "MODE": "SHARED_CLASS_CERTIFICATE" if shared else "PER_MEMBER_CLOSED_FORM",
        "REASON": "ONE_SOURCE_AND_ONE_PREMISE_TUPLE"
        if shared
        else "EACH_MEMBER_CITES_ITS_OWN_REFUTATION_OR_PREMISES_DIFFER",
        "DISTINCT_SOURCE_CERTIFICATES": len(sources),
        "DISTINCT_PREMISE_TUPLES": len(tuples),
        "TRIANGLE_CAPS": sorted({integer(chase.catalog[p].triangle_cap) for p in members}),
        "GLOBAL_S4_FLOORS": sorted({integer(chase.catalog[p].s4) for p in members}),
        "WEDGE_COUNTS": sorted({k4_premises(p)[0] for p in members}),
        "A_MAX_VALUES": sorted({contained_triple_k4_cap(p) for p in members}),
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


def next_obstruction(chase: Chase, scope: Collection[DegreeProfile]) -> dict[str, object]:
    """The current family owners and why this task stops at them."""

    family, owners = r28.family_state(chase)
    inside = [p for p in owners if p in scope]
    kinds = Counter(
        ("UNRESOLVED_CURSOR", None, None)
        if p == chase.cursor
        else (
            chase.catalog[p].source_result,
            chase.catalog[p].relaxation,
            chase.catalog[p].triangle_cap,
        )
        for p in owners
    )
    return {
        "KIND": "SLICE_OWNER_NOT_CERTIFIED_BY_ROUTE_B"
        if inside
        else "FIRST_LEVEL_OUTSIDE_THE_7_PLUS_104_SLICE",
        "FAMILY_UPPER_BOUND": family,
        "OWNER_COUNT": len(owners),
        "OWNER_IDS": list(map(profile_id, owners)),
        "SLICE_OWNERS_REMAINING": len(inside),
        "CURSOR_IS_OWNER": chase.cursor in owners,
        "CERTIFICATE_KINDS": [
            {"SOURCE_RESULT": s, "RELAXATION": r, "TRIANGLE_CAP": c, "PROFILE_COUNT": n}
            for (s, r, c), n in sorted(kinds.items(), key=lambda kv: str(kv[0]))
        ],
        "ROUTE_B_APPLIED": "NO_ROUTE_B_DID_NOT_CERTIFY"
        if inside
        else "NO_OUTSIDE_THE_AUTHORIZED_SLICE",
        "NEXT_COMPETING_BOUND": r28.competing_bound(chase, owners),
    }


def r31_route4_revalidation(chase: Chase, sealed: Mapping[str, object]) -> dict[str, object]:
    """Every R31 Route-4 certificate is re-derived by the replay and left intact."""

    certs = list(map(object_row, rows(sealed["ROUTE4_CERTIFICATES"])))
    for index, row in enumerate(certs):
        p = decode_profile(row["PROFILE_ID"])
        cert = chase.catalog[p]
        if (
            row["STATUS"] != CERTIFIED
            or (cert.source_result, cert.source_row)
            != (R31_RESULT, f"ROUTE4_CERTIFICATES[{index}]")
            or cert.relaxation != r30.ROUTE_MOTIF
            or chase.bounds[p] != row["NEW_BOUND"]
        ):
            raise AssertionError("an R31 Route-4 certificate changed")
    return {
        "STATUS": "PASS",
        "CERTIFICATES_REVALIDATED": len(certs),
        "METHOD": "R31_ZERO_SOLVE_REPLAY_REDERIVES_EACH_CERTIFICATE_AND_R32_LEAVES_IT_UNCHANGED",
        "MAX_R31_ROUTE4_BOUND": max(integer(row["NEW_BOUND"]) for row in certs),
    }


def witness_route_b(witness: Mapping[str, object]) -> dict[str, object]:
    """Route B on the realized STS(13) witness, from its graph structure alone.

    The exact union and S4 are R30's sealed values, carried in the pinned R31
    result; no outcome is enumerated here.
    """

    tickets = r30.sts13_witness()
    sets = [set(t) for t in tickets]
    multiplicity = Counter(n for t in tickets for n in t)
    triples = [
        frozenset(i for i, s in enumerate(sets) if n in s)
        for n, m in multiplicity.items()
        if m == 3
    ]
    profile = tuple(
        sorted((sum(n in s for n, m in multiplicity.items() if m == 3) for s in sets), reverse=True)
    )
    edges = {
        (a, b) for a, b in combinations(range(K20_TICKET_COUNT), 2) if len(sets[a] & sets[b]) == 1
    }

    def clique(q: Sequence[int]) -> bool:
        return all(e in edges for e in combinations(q, 2))

    quartets = [q for q in combinations(range(K20_TICKET_COUNT), 4) if clique(q)]
    contained = [sum(t <= set(q) for t in triples) for q in quartets]
    triangles = sum(clique(q) for q in combinations(range(K20_TICKET_COUNT), 3))
    exact_contained = sum(contained)
    a_max = contained_triple_k4_cap(profile)
    terms = route_b_envelope(profile, triangles, r28.profile_s4_floor(profile))
    _, bound, k4_floor, _, s4_floor, _ = terms[-1]
    exact_s4, union = integer(witness["EXACT_S4"]), integer(witness["EXACT_ANY_PRIZE_UNION"])
    motif = K4_WEIGHTS[WITH_TRIPLE] * exact_contained + K4_WEIGHTS[WITHOUT_TRIPLE] * (
        len(quartets) - exact_contained
    )
    if (
        witness.get("STATUS") != "PASS"
        or profile != WITNESS_PROFILE
        or set(multiplicity.values()) != {2, 3}
        or len(multiplicity) != r30.r2.BIG_LOTTO_POOL_SIZE
        or any(len(sets[a] & sets[b]) > 1 for a, b in combinations(range(K20_TICKET_COUNT), 2))
        or (triangles, len(quartets)) != (WITNESS_TRIANGLES, witness["EXACT_K4"])
        or triangles != witness["GRAPH_TRIANGLES"]
        or union != WITNESS_UNION
    ):
        raise AssertionError("STS(13) witness structure differs from the sealed witness")
    if (
        max(contained) > 1
        or exact_contained > a_max
        or k4_floor > len(quartets)
        or not s4_floor <= motif <= exact_s4
        or max(term[1] for term in terms) != bound
        or not union <= bound_from_cap(profile, triangles, exact_s4)[1] <= bound
    ):
        raise AssertionError("Route B over-tightens the realizable STS(13) witness")
    if s4_floor != WITNESS_ROUTE_B_S4_FLOOR:
        raise AssertionError("witness Route-B S4 floor differs from the independent proof")
    return {
        "STATUS": "PASS",
        "PROFILE_ID": profile_id(profile),
        "REALIZED_TRIANGLES": triangles,
        "EXACT_K4": len(quartets),
        "EXACT_CONTAINED_TRIPLE_K4": exact_contained,
        "MAX_CONTAINED_TRIPLES_PER_K4": max(contained),
        "A_MAX": a_max,
        "K4_FLOOR_AT_REALIZED_TRIANGLES": k4_floor,
        "ROUTE_B_S4_FLOOR": s4_floor,
        "EXACT_K4_MOTIF_S4": motif,
        "EXACT_S4": exact_s4,
        "EXACT_ANY_PRIZE_UNION": union,
        "ROUTE_B_BOUND_AT_REALIZED_CAP": bound,
        "SLACK_UNDER_ROUTE_B_BOUND": bound - union,
        "EXACT_VALUES_SOURCE": "R31_SEALED_SOUNDNESS_WITNESS_NO_NEW_OUTCOME_ENUMERATION",
    }


def reference_regression(proofs: Proofs, deadline: float) -> dict[str, object]:
    """Route B on R30's original owner certificate; a regression, not a family result."""

    chase, _ = r31.start_chase(deadline)
    cert = chase.catalog[REFERENCE_OWNER]
    row = route_b_certificate(REFERENCE_OWNER, cert, proofs)
    if (
        row["STATUS"] != CERTIFIED
        or row["PREVIOUS_BOUND"] != REFERENCE_START_BOUND
        or row["NEW_BOUND"] != REFERENCE_ROUTE_B_BOUND
    ):
        raise AssertionError("Route-B reference regression on the R30 owner failed")
    keys = ("PROFILE_ID", "CERTIFIED_TRIANGLE_CAP", "A_MAX", "K4_FLOOR", "S4_FLOOR")
    return {
        "STATUS": "PASS",
        "SCOPE": "REFERENCE_REGRESSION_NOT_THE_FAMILY_RESULT",
        **{k: row[k] for k in keys},
        "CERTIFICATE_SOURCE": row["CERTIFICATE_SOURCE"],
        "R30_BOUND": row["PREVIOUS_BOUND"],
        "ROUTE_B_BOUND": row["NEW_BOUND"],
    }


def compute_result() -> dict[str, object]:
    primitives = r28.canonical_primitive_preflight()
    if primitives["STATUS"] != "PASS" or r30.k4_quartet_weights() != K4_WEIGHTS:
        raise AssertionError("canonical primitive gate failed")
    proofs = r30_proofs()
    reference = reference_regression(proofs, monotonic() + REPLAY_SECONDS)
    chase, digest, sealed = start_chase(monotonic() + REPLAY_SECONDS)
    witness = object_row(sealed["SOUNDNESS_WITNESS"])
    witness_check = witness_route_b(witness)
    start_ledger = r29.ledger_digest(chase)
    plateau = sealed_level(sealed, PLATEAU_BOUND)
    owner_mode = certificate_mode(chase, START_OWNERS)
    certificates = [certify(chase, p, i, proofs) for i, p in enumerate(START_OWNERS)]
    members: tuple[DegreeProfile, ...] = ()
    plateau_mode: dict[str, object] | None = None
    if all(row["STATUS"] == CERTIFIED for row in certificates):
        members = plateau_members(chase, plateau)
        plateau_mode = certificate_mode(chase, members)
        for p in members:
            certificates.append(certify(chase, p, len(certificates), proofs))
    owner_rows = certificates[: len(START_OWNERS)]
    plateau_rows = certificates[len(START_OWNERS) :]
    recompute = full_recompute(chase)
    obstruction = next_obstruction(chase, (*START_OWNERS, *plateau))
    revalidation = r31_route4_revalidation(chase, sealed)
    family, owners = r28.family_state(chase)

    def certified(group: Sequence[Mapping[str, object]]) -> int:
        return sum(row["STATUS"] == CERTIFIED for row in group)

    def top(group: Sequence[Mapping[str, object]]) -> int | None:
        return max((integer(row["NEW_BOUND"]) for row in group), default=None)

    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": SUCCESS_A if family < START_BOUND else SUCCESS_B,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "INPUT_AUTHORITY": "R31_SEALED_RESULT_ZERO_SOLVE_REPLAY",
        "AUTHORITY_FINGERPRINT": {
            "R31_HEAD": BASE_HEAD,
            "R31_RESULT_SHA256": digest,
            "R31_FINAL_LEDGER_SHA256": R31_LEDGER_SHA256,
            "R30_RESULT_SHA256": R30_SHA256,
            "SEALED_REPLAY": "PASS",
        },
        "START_FAMILY_BOUND": START_BOUND,
        "START_COMPLETE_LEDGER_SHA256": start_ledger,
        "CURRENT_OWNER_COUNT": len(START_OWNERS),
        "CURRENT_OWNER_IDS": list(map(profile_id, START_OWNERS)),
        "CURRENT_OWNERS_CERTIFIED": certified(owner_rows),
        "CURRENT_OWNER_CERTIFICATE_MODE": owner_mode,
        "CURRENT_OWNER_MAX_NEW_BOUND": top(owner_rows),
        "NEXT_PLATEAU_BOUND": PLATEAU_BOUND,
        "NEXT_PLATEAU_COUNT": len(plateau),
        "NEXT_PLATEAU_PROFILE_IDS": list(map(profile_id, plateau)),
        "NEXT_PLATEAU_MEMBERSHIP_SHA256": r30.membership_digest(plateau),
        "NEXT_PLATEAU_PROCESSED": len(members),
        "NEXT_PLATEAU_CERTIFIED": certified(plateau_rows),
        "NEXT_PLATEAU_CERTIFICATE_MODE": plateau_mode,
        "NEXT_PLATEAU_MAX_NEW_BOUND": top(plateau_rows),
        "ROUTE_B_APPLICABILITY": "ALL_SLICE_CERTIFICATES_SATISFY_EVERY_PREMISE"
        if all(row["PREMISE_FAILURES"] == [] for row in certificates)
        else "PREMISE_FAILURES_PRESENT",
        "ALL_T_CERTIFICATE_STATUS": "PASS"
        if len(certificates) == len(START_OWNERS) + PLATEAU_COUNT
        and all(
            row["STATUS"] == CERTIFIED
            and row["TRIANGLE_COUNTS_CHECKED"]
            == integer(row["CERTIFIED_TRIANGLE_CAP"]) - K20_TRIPLE_SUPPORT_COUNT + 1
            for row in certificates
        )
        else "PARTIAL",
        "ROUTE_B_CERTIFICATES": certificates,
        "OWNER_CLASS_SEQUENCE": chase.sequence,
        "FULL_LEDGER_RECOMPUTATION": recompute,
        "NEXT_OBSTRUCTION": obstruction,
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
        "REFERENCE_REGRESSION": reference,
        "R31_ROUTE4_REVALIDATION": revalidation,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "WITNESS_SOUNDNESS_STATUS": witness_check["STATUS"],
        "ROUTE_B_ON_WITNESS": witness_check,
        "METHOD_CAPABILITY": r30.method_capability(witness),
        "FINAL_RESOLVED_LEDGER": r29.ledger(chase),
        "FINAL_COMPLETE_LEDGER_SHA256": r29.ledger_digest(chase),
        "RESOLVED_LEDGER_COUNT": len(chase.bounds),
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "FULL_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "JUDGE_DISPATCH": "SUPPRESSED",
    }


def replay_result(result: Mapping[str, object], deadline: float) -> Chase:
    """Re-derive every sealed R32 certificate on the R31 replay; assert the ledger."""

    chase, _, _ = start_chase(deadline)
    proofs = r30_proofs()
    for index, raw in enumerate(rows(result["ROUTE_B_CERTIFICATES"])):
        sealed = object_row(raw)
        if certify(chase, decode_profile(sealed["PROFILE_ID"]), index, proofs) != sealed:
            raise AssertionError("Route-B certificate replay diverged")
    if (
        r29.ledger(chase) != result["FINAL_RESOLVED_LEDGER"]
        or r29.ledger_digest(chase) != result["FINAL_COMPLETE_LEDGER_SHA256"]
        or r28.family_state(chase)[0] != result["FAMILY_UPPER_BOUND"]
        or chase.sequence != result["OWNER_CLASS_SEQUENCE"]
    ):
        raise AssertionError("complete R32 ledger replay diverged")
    return chase


SUMMARY_KEYS = (
    "TASK_STATUS",
    "CURRENT_OWNERS_CERTIFIED",
    "NEXT_PLATEAU_CERTIFIED",
    "FAMILY_UPPER_BOUND",
    "FINAL_BOUND_OWNER_IDS",
    "REMAINING_GAP",
)


def main() -> None:
    target = r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME
    if target.exists():
        raise AssertionError("only a new exact R32 result output is authorized")
    result = compute_result()
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    print(json.dumps({k: result[k] for k in SUMMARY_KEYS}), flush=True)


if __name__ == "__main__":
    main()
