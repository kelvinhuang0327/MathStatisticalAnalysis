"""Complete minimum-S2 family maximum after adopting three local S4 certificates.

Authority. The ledger is the 2f709256 split-cap chase ledger: the e44a635f zero-solve
replay plus that chase's tightened rows, checked against its sealed row digest. All three
certificates start from that ledger, and each changes one profile at its cap term only.
Every other row, every lower-t term, every triangle cap and all 4,844-profile coverage
stay as they are.

Certificate 1 (t=264 owner 66666555555311100000, new here). Let U=sum C(g_v,3),
L=sum (g_v-2)*ow_v and R=sum d_v(g_v-2). K counts K4 quartets, A those containing a triple
support, P1 the paws containing one and C the claws. Each of U, L and R counts quartet
incidences, so the 96 local graph/support cases add up to the exact identity
    S4 = 231K - 63A + 56(2U-L-R) + 56(P1+C).
Also 4K = U-L+P+2C >= U-L, R = 3A+2D1+P1 >= 3A, and L <= (max g-2)(W-3t). The bound is
decreasing in L, so S4 >= 231*ceil((U-L_max)/4) - 63*floor(R/3) + 56(2U-L_max-R). At the
owner's cap t=264 (R30 GROUP_ATTEMPTS[2504], t=265 INFEASIBLE) this gives U=2379, R=606,
L<=420, K>=490 and A<=202, so S4>=309,456. That replaces the Route-B floor 286,048, and the
two credits are never added. The t=264 term falls from 313,404,008 to 313,390,632. The
t<=263 terms keep their maximum 313,394,852.

Certificate 2 (STS13 profile 55555555555511111100 at t=270, donor d67f8233). The donor
result bytes are adopted as they stand. The graph isolation K12+(K8-e) is not derived
again. Only its applicability is checked: degree arithmetic, K4=550, A=190, D=15,
S4=331,240, its retained Route-B terms against this ledger row, and its t=270 term. The
profile bound falls from 313,402,304 to 313,399,016.

Certificate 3 (owner 66655555555440000000, BASE_HEAD 914de80a). Its sealed result bytes are
kept as they stand. Its owner certificate is re-verified against this ledger row and its
cap proof by the committed verifier, so the profile bound is 313,393,084.

The complete family maximum is recomputed over all 4,647 resolved rows and the W<=785
cursor. Each install moves the family owner by one step. No solver, census, portfolio
search or outcome enumeration is run.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_owner_66655555555440000000_motif_r1 as motif
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase

split = chase.split
prior = chase.prior
r32 = motif.r32
TASK_ID = "B649_K20_MIN_S2_THREE_MOTIF_COMPLETE_FAMILY_INTEGRATION_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-three-motif-complete-family-integration-r1"
BASE_HEAD = "914de80a4c95162d87f062746651619dabe1f072"
BASE_TREE = "ce5854b4cef6baa4d4067b45cf64040665405633"
BASE_RESULT_SHA256 = "2c29cd66b76042402b2e68886d50c3ed5360fb9f3b695d0d5a8fe4dc095f5c6b"
CHASE_HEAD = motif.BASE_HEAD
CHASE_RESULT_SHA256 = motif.BASE_RESULT_SHA256
STS13_DONOR_HEAD = "d67f8233628117026b0a87bbd0bcc5a54c58c200"
STS13_DONOR_RESULT_SHA256 = "085434aa3708b0e3032093fd0a98b3a039c448c183f3ec633ebfef61a29b4d92"
STS13_TASK_ID = "B649_K20_MIN_S2_STS13_ISOLATION_S4_CERTIFICATE_R1"
STS13_RESULT_FILENAME = "b649-k20-min-s2-sts13-isolation-s4-certificate-r1-result.json"
START_FAMILY_UB = 313_404_008
START_OWNER_IDS = ["66666555555311100000"]
INCUMBENT = chase.INCUMBENT
T264_PROFILE = "66666555555311100000"
T264_CAP = 264
T264_CAP_INDEX = 2504
T264_LEDGER_INDEX = 4
STS13_PROFILE = "55555555555511111100"
STS13_T = 270
OWNER_PROFILE = motif.PROFILE_ID
RESULT_FILENAME = "b649-k20-min-s2-three-motif-complete-family-integration-r1-result.json"
ROOT = chase.ROOT
RESULT_PATH = ROOT / prior.RESULT_DIRECTORY / RESULT_FILENAME
T264_LOCATOR = f"{RESULT_FILENAME}:T264_OWNER_CERTIFICATE"
STS13_LOCATOR = f"{STS13_RESULT_FILENAME}:STS13_T270_CERTIFICATE"
OWNER_LOCATOR = f"{motif.RESULT_FILENAME}:OWNER_CERTIFICATE"
Row = chase.Row
Ledger = dict[str, Row]
digest = motif.digest
integer, object_row, rows, text = chase.integer, chase.object_row, chase.rows, chase.text


def pinned(head: str, filename: str, expected: str) -> dict[str, object]:
    """A committed result blob at an exact commit, and its in-tree copy, by SHA-256."""

    blob = chase.git("show", f"{head}:{prior.RESULT_DIRECTORY}/{filename}")
    if hashlib.sha256(blob).hexdigest() != expected:
        raise AssertionError(f"pinned result digest mismatch: {filename}")
    if (ROOT / prior.RESULT_DIRECTORY / filename).read_bytes() != blob:
        raise AssertionError(f"in-tree result differs from its committed bytes: {filename}")
    return object_row(json.loads(blob))


def provenance() -> dict[str, str]:
    """Commit identities, and every reused module equal to its BASE_HEAD blob."""

    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    if chase.git("rev-parse", f"{STS13_DONOR_HEAD}^").decode().strip() != CHASE_HEAD:
        raise AssertionError("STS13 donor does not start from the chase ledger commit")
    if chase.git("rev-parse", f"{BASE_HEAD}^").decode().strip() != CHASE_HEAD:
        raise AssertionError("owner motif base does not start from the chase ledger commit")
    out: dict[str, str] = {}
    for module in (
        motif,
        chase,
        split,
        prior,
        chase.r20,
        r32,
        motif.event,
        *prior.PROVENANCE_MODULES,
    ):
        if module.__file__ is None:
            raise AssertionError("reused module has no source")
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(ROOT):
            raise AssertionError(f"reused module loaded outside this tree: {path}")
        relative = path.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        if path.read_bytes() != committed:
            raise AssertionError(f"reused source changed: {relative}")
        out[relative] = hashlib.sha256(committed).hexdigest()
    return out


def rows_digest(ledger: Mapping[str, Row]) -> str:
    serialized = [{"PROFILE_ID": pid, "CURRENT_BOUND": ledger[pid].bound} for pid in sorted(ledger)]
    return hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()


def chase_ledger(auth: chase.Authority, sealed: Mapping[str, object]) -> Ledger:
    """The e44a635f replay with the 2f709256 tightened rows, checked by the sealed digest."""

    ledger = dict(auth.ledger)
    for index, raw in enumerate(rows(sealed["CERTIFICATES"])):
        cert = object_row(raw)
        if cert["STATUS"] != chase.TIGHTENED:
            continue
        pid = text(cert["PROFILE_ID"])
        old = ledger[pid]
        if (cert["EXISTING_BOUND"], cert["EXISTING_TRIANGLE_CAP"], cert["S4_BASE"]) != (
            old.bound,
            old.cap,
            old.s4_base,
        ):
            raise AssertionError(f"chase certificate does not start from the replay: {pid}")
        cap, bound = integer(cert["TRIANGLE_CAP"]), integer(cert["ALL_T_MAX_BOUND"])
        terms = split.route_b_terms(split.profile_values(pid), cap, old.s4_base)
        if [list(t) for t in terms] != rows(cert["ALL_T_TERMS"]) or max(
            t[1] for t in terms
        ) != bound:
            raise AssertionError(f"chase certificate envelope changed: {pid}")
        ledger[pid] = replace(
            old, bound=bound, cap=cap, source=f"{chase.RESULT_FILENAME}:CERTIFICATES[{index}]"
        )
    if rows_digest(ledger) != sealed["FINAL_RESOLVED_ROWS_SHA256"]:
        raise AssertionError("rebuilt ledger differs from the sealed 2f709256 row digest")
    if chase.family_state(ledger) != (START_FAMILY_UB, START_OWNER_IDS):
        raise AssertionError("rebuilt family state differs from 2f709256")
    return ledger


@cache
def incidence_identity_check() -> dict[str, object]:
    """All 96 local graph/support cases satisfy the four-point incidence identity."""

    pairs = tuple(combinations(range(4), 2))
    table: list[list[int]] = []
    for mask in range(64):
        edges = {e for i, e in enumerate(pairs) if mask >> i & 1}
        supports: list[motif.Support | None] = [
            None,
            *(t for t in combinations(range(4), 3) if set(combinations(t, 2)) <= edges),
        ]
        for triple in supports:
            m = motif.classify(edges, triple)
            u, ell, r = motif.incidences(4, edges, () if triple is None else (triple,))
            s4 = motif.local_weight(edges, triple)
            slack = 56 * (m.p1 + m.c)
            if s4 != 231 * m.k - 63 * m.a + 56 * (2 * u - ell - r) + slack:
                raise AssertionError("four-point incidence identity failed")
            if 4 * m.k < u - ell or 3 * m.a > r or slack < 0:
                raise AssertionError("K4, contained-triple or slack incidence bound failed")
            mark = 0 if triple is None else sum(1 << v for v in triple)
            table.append([mask, mark, u, ell, r, s4, slack])
    if len(table) != 96 or len({(row[0], row[1]) for row in table}) != 96:
        raise AssertionError("local graph/support coverage changed")
    return {
        "STATUS": "PASS",
        "IDENTITY": "S4 = 231K - 63A + 56(2U-L-R) + 56(P1+C)",
        "LOCAL_CASES": len(table),
        "TABLE_COLUMNS": ["EDGES_MASK", "TRIPLE_MASK", "U", "L", "R", "S4", "SLACK"],
        "TABLE_SHA256": digest(table),
    }


def incidence_floor(profile: Sequence[int], triangles: int) -> dict[str, int]:
    """Lower S4 bound from the identity with K>=ceil((U-L_max)/4), A<=R//3, L<=L_max."""

    g = [6 + d for d in profile]
    w = sum(comb(v, 2) for v in g)
    u = sum(comb(v, 3) for v in g)
    r = sum(d * (v - 2) for d, v in zip(profile, g, strict=True))
    ow = w - 3 * triangles
    if ow < 0:
        raise ValueError("negative open-wedge count")
    l_max = (max(g) - 2) * ow
    k4 = max(0, -(-(u - l_max) // 4))
    a_max = r // 3
    s4 = max(0, 231 * k4 - 63 * a_max + 56 * (2 * u - l_max - r))
    return {
        "W": w,
        "U": u,
        "R": r,
        "OW": ow,
        "L_MAX": l_max,
        "K4_FLOOR": k4,
        "A_MAX": a_max,
        "S4_FLOOR": s4,
    }


def check_t264_cap(row: Row, proof: Mapping[str, object], source: Mapping[str, object]) -> None:
    """The owner's cap 264 is R30's t=265 refutation, recorded by its R32 ledger row."""

    expected: dict[str, object] = {
        "ATTEMPT_INDEX": T264_CAP_INDEX,
        "PROFILE_IDS": [T264_PROFILE],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "ROUTE": r32.CAP_SOURCE_ROUTE,
        "WEDGE_COUNT": 834,
        "TARGET_TRIANGLE_CAP": T264_CAP,
        "REFUTED_GRAPH_TRIANGLE_COUNT": T264_CAP + 1,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": T264_CAP,
        "OPEN_WEDGE_CEILING_REFUTED": 39,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": 40,
    }
    if any(digest(proof.get(k)) != digest(v) for k, v in expected.items()):
        raise AssertionError("t264 cap-source identity mismatch")
    profile = split.profile_values(T264_PROFILE)
    if r32.r28.r26.accepted_cap(proof, (profile,), T264_CAP) != T264_CAP:
        raise AssertionError("t264 cap-source refutation not accepted")
    origin = object_row(source["CERTIFICATE_SOURCE"])
    recorded: dict[str, object] = {
        "CERTIFICATE_INDEX": T264_LEDGER_INDEX,
        "PROFILE_ID": T264_PROFILE,
        "STATUS": "CERTIFIED",
        "CERTIFIED_TRIANGLE_CAP": T264_CAP,
        "GLOBAL_S4_FLOOR": row.s4_base,
        "ALL_T_MAX_BOUND": row.bound,
    }
    if (
        any(digest(source.get(k)) != digest(v) for k, v in recorded.items())
        or origin.get("SOURCE_RESULT") != r32.CAP_SOURCE_RESULT
        or origin.get("SOURCE_ROW") != f"GROUP_ATTEMPTS[{T264_CAP_INDEX}]"
        or row.source != f"{r32.RESULT_FILENAME}:ROUTE_B_CERTIFICATES[{T264_LEDGER_INDEX}]"
        or type(row.cap) is not int
        or row.cap != T264_CAP
    ):
        raise AssertionError("t264 cap-source identity mismatch")


def t264_certificate(
    row: Row, proof: Mapping[str, object], source: Mapping[str, object]
) -> dict[str, object]:
    """Replace only the cap-term S4 floor of the t=264 owner; never add the two credits."""

    check_t264_cap(row, proof, source)
    p = split.profile_values(T264_PROFILE)
    old = split.route_b_terms(p, row.cap, row.s4_base)
    *lower, last = old
    t, old_bound, old_k4, old_a, old_s4, s3 = last
    if t != T264_CAP or max(term[1] for term in old) != row.bound:
        raise AssertionError("existing t264 owner envelope does not reproduce the ledger")
    floor = incidence_floor(p, t)
    sealed = {
        k: source[k]
        for k in ("SUM_GRAPH_DEGREE_CHOOSE_3", "SUM_TRIPLE_DEGREE_TIMES_OUTSIDE_DEGREE")
    }
    if sealed != {
        "SUM_GRAPH_DEGREE_CHOOSE_3": floor["U"],
        "SUM_TRIPLE_DEGREE_TIMES_OUTSIDE_DEGREE": floor["R"],
    }:
        raise AssertionError("t264 degree constants differ from the sealed ledger row")
    reference = motif.degree_floor(p, t)
    if floor["S4_FLOOR"] - reference["S4_CERTIFIED_FLOOR"] != 21 * (floor["R"] % 3):
        raise AssertionError("incidence floor differs from the committed degree floor")
    s4 = max(old_s4, floor["S4_FLOOR"])
    s3_check, bound = chase.r20.bound_from_cap(p, t, s4)
    exact = motif.event.K20_S1 - motif.event.K20_S2 + s3 - Fraction(4 * s4, 7)
    if s3_check != s3 or not 0 <= bound - exact < 1:
        raise AssertionError("t264 S4 credit rounding is not exact")
    terms = [*lower, (t, bound, floor["K4_FLOOR"], floor["A_MAX"], s4, s3)]
    return {
        "PROFILE_ID": T264_PROFILE,
        "TRIANGLE_CAP": t,
        "CAP_SOURCE": f"{r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS[{T264_CAP_INDEX}]",
        "CAP_SOURCE_IDENTITY": dict(proof),
        "EXISTING_LEDGER_SOURCE": row.source,
        "S4_BASE": row.s4_base,
        "INCIDENCE_FLOOR": floor,
        "COMMITTED_DEGREE_FLOOR_S4": reference["S4_CERTIFIED_FLOOR"],
        "OLD_K4_FLOOR": old_k4,
        "OLD_CONTAINED_K4_CAP": old_a,
        "OLD_ROUTE_B_S4_FLOOR": old_s4,
        "NEW_S4_FLOOR": s4,
        "S4_RULE": "MAX(OLD_ROUTE_B_S4_FLOOR, INCIDENCE_S4_FLOOR); CREDITS NEVER ADDED",
        "CREDIT_GAIN": 4 * s4 // 7 - 4 * old_s4 // 7,
        "T264_OLD_BOUND": old_bound,
        "T264_NEW_BOUND": bound,
        "RETAINED_LOWER_T_COUNT": len(lower),
        "RETAINED_LOWER_T_MAX": max(term[1] for term in lower),
        "RETAINED_TERMS_SHA256": digest(lower),
        "ALL_T_TERMS": [list(term) for term in terms],
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "CERTIFIED_PROFILE_BOUND": max(term[1] for term in terms),
        "STATUS": "PASS",
    }


def sts13_certificate(row: Row, donor: Mapping[str, object]) -> dict[str, object]:
    """Adopt the donor t=270 certificate bytes; check only that they apply to this row."""

    if (
        donor.get("TASK_ID") != STS13_TASK_ID
        or donor.get("BASE_HEAD") != CHASE_HEAD
        or donor.get("BASE_RESULT_SHA256") != CHASE_RESULT_SHA256
        or donor.get("BASE_FAMILY_UB") != START_FAMILY_UB
    ):
        raise AssertionError("STS13 donor authority mismatch")
    cert = object_row(donor["STS13_T270_CERTIFICATE"])
    iso, lab = object_row(cert["GRAPH_ISOLATION"]), object_row(cert["LABEL_SUPPORTS"])
    seen, adopt = object_row(cert["WITNESS"]), object_row(cert["ADOPTION"])
    p = split.profile_values(STS13_PROFILE)
    g = [6 + d for d in p]
    w = sum(comb(v, 2) for v in g)
    k4, a, d, s4 = (
        integer(lab[k])
        for k in ("K4_COUNT", "TRIPLE_CONTAINING_K4_COUNT", "DIAMOND_COUNT", "EXACT_S4")
    )
    if (
        cert.get("PROFILE_ID") != STS13_PROFILE
        or cert.get("LOAD_BEARING_T") != STS13_T
        or cert.get("STATUS") != "PASS"
        or iso.get("STATUS") != "PROVED_UNIQUE"
        or (iso.get("T"), iso.get("STRUCTURE_TRIANGLES"), iso.get("W")) != (STS13_T, STS13_T, w)
        or iso.get("OPEN_WEDGES") != w - 3 * STS13_T
        or iso.get("STRUCTURE") != "K12 + (K8-e)"
    ):
        raise AssertionError("STS13 certificate identity mismatch")
    if (
        s4 != 679 * (k4 - a) + 448 * a + 112 * d
        or lab.get("STAR_COUNT") != sum(comb(v, 3) for v in g)
        or lab.get("STAR_COUNT") != 4 * k4 + 2 * d
        or (seen.get("S4_DECOMPOSITION"), seen.get("S4_CLASS_DP")) != (s4, s4)
        or seen.get("DECOMPOSITION") != [k4 - a, a, d]
        or (seen.get("STATUS"), seen.get("TRIANGLES")) != ("PASS", STS13_T)
    ):
        raise AssertionError("STS13 certificate counts are inconsistent")
    if (
        type(row.cap) is not int
        or row.cap != STS13_T
        or adopt.get("TRIANGLE_CAP") != row.cap
        or adopt.get("CAP_AUTHORITY") != row.source
        or adopt.get("S4_BASE") != row.s4_base
        or adopt.get("OLD_PROFILE_BOUND") != row.bound
        or adopt.get("EXACT_S4") != s4
    ):
        raise AssertionError("STS13 certificate does not apply to this ledger row")
    old = split.route_b_terms(p, row.cap, row.s4_base)
    *lower, last = old
    t, old_bound, old_k4, old_a, old_s4, s3 = last
    a_max = sum(x * (v - 2) for x, v in zip(p, g, strict=True)) // 3
    if k4 < old_k4 or a > a_max or old_a != min(old_k4, a_max) or s4 < old_s4:
        raise AssertionError("exact STS13 counts violate the Route-B floor premises")
    bound = motif.event.K20_S1 - motif.event.K20_S2 + s3 - (4 * s4) // 7
    exact = motif.event.K20_S1 - motif.event.K20_S2 + s3 - Fraction(4 * s4, 7)
    terms = [[*term] for term in lower] + [[t, bound, k4, a, s4, s3]]
    full = max(bound, max(term[1] for term in lower))
    if (
        not 0 <= bound - exact < 1
        or rows(adopt["ALL_T_TERMS"]) != terms
        or adopt.get("T270_OLD_BOUND") != old_bound
        or adopt.get("T270_NEW_BOUND") != bound
        or adopt.get("LOWER_T_MAX_BOUND") != max(term[1] for term in lower)
        or adopt.get("FULL_PROFILE_BOUND") != full
    ):
        raise AssertionError("STS13 adoption terms differ from this ledger row")
    return {
        "PROFILE_ID": STS13_PROFILE,
        "TRIANGLE_CAP": row.cap,
        "CAP_SOURCE": row.source,
        "DONOR_HEAD": STS13_DONOR_HEAD,
        "DONOR_RESULT_SHA256": STS13_DONOR_RESULT_SHA256,
        "CERTIFICATE_LOCATOR": STS13_LOCATOR,
        "CERTIFICATE_SHA256": digest(cert),
        "GRAPH_STRUCTURE": iso["STRUCTURE"],
        "GRAPH_ISOLATION_REDERIVED": False,
        "K4": k4,
        "A": a,
        "DIAMONDS": d,
        "EXACT_S4": s4,
        "OLD_ROUTE_B_S4_FLOOR": old_s4,
        "S4_RULE": "EXACT_S4 REPLACES THE ROUTE-B FLOOR; CREDITS NEVER ADDED",
        "T270_OLD_BOUND": old_bound,
        "T270_NEW_BOUND": bound,
        "RETAINED_LOWER_T_COUNT": len(lower),
        "RETAINED_LOWER_T_MAX": max(term[1] for term in lower),
        "CERTIFIED_PROFILE_BOUND": full,
        "STATUS": "ADOPTED_DONOR_BYTES",
    }


def owner_motif_certificate(
    row: Row, proof: Mapping[str, object], sealed: Mapping[str, object], base: Mapping[str, Row]
) -> dict[str, object]:
    """Keep the BASE_HEAD owner certificate bytes and re-verify them on this ledger row."""

    if (
        sealed.get("TASK_ID") != motif.TASK_ID
        or sealed.get("BASE_HEAD") != CHASE_HEAD
        or sealed.get("BASE_RESULT_SHA256") != CHASE_RESULT_SHA256
        or sealed.get("COMPLETE_FAMILY_BOUND_FROM_BASE") != START_FAMILY_UB
        or sealed.get("OTHER_ROWS_SHA256")
        != digest({pid: r.bound for pid, r in base.items() if pid != OWNER_PROFILE})
    ):
        raise AssertionError("owner motif authority mismatch")
    cert = object_row(sealed["OWNER_CERTIFICATE"])
    motif.verify_certificate(cert, row, proof)
    return {
        "PROFILE_ID": OWNER_PROFILE,
        "TRIANGLE_CAP": cert["TRIANGLE_CAP"],
        "CAP_SOURCE": cert["CAP_SOURCE"],
        "EXISTING_LEDGER_SOURCE": row.source,
        "CERTIFICATE_LOCATOR": OWNER_LOCATOR,
        "CERTIFICATE_SHA256": digest(cert),
        "T264_OLD_BOUND": cert["T264_OLD_BOUND"],
        "T264_NEW_BOUND": cert["T264_NEW_BOUND"],
        "CERTIFIED_PROFILE_BOUND": integer(cert["CERTIFIED_OWNER_BOUND"]),
        "STATUS": "PRESERVED_SEALED_BYTES_REVERIFIED",
    }


def install(ledger: Mapping[str, Row], pid: str, bound: int, locator: str) -> Ledger:
    """One strictly lower profile bound; cap and S4 base keep their authority."""

    old = ledger[pid]
    if not INCUMBENT <= bound < old.bound:
        raise AssertionError(f"certificate does not strictly improve a sound bound: {pid}")
    return {**ledger, pid: replace(old, bound=bound, source=locator)}


def family(ledger: Mapping[str, Row], auth: chase.Authority) -> dict[str, object]:
    """Complete maximum over every resolved row and the cursor, by an independent sort."""

    covered = chase.coverage(ledger, auth.members, auth.base)
    ranked = sorted(((r.bound, pid) for pid, r in ledger.items()), reverse=True)
    terms = [*ranked, (prior.CURSOR_BOUND, prior.CURSOR_ID)]
    if len({pid for _b, pid in terms}) != len(terms) or len(ledger) != chase.RESOLVED_COUNT:
        raise AssertionError("family terms are not unique resolved rows plus the cursor")
    top = max(b for b, _pid in terms)
    owners = sorted(pid for b, pid in terms if b == top)
    runner_up = max(b for b, pid in terms if pid not in owners)
    reused, reused_owners = chase.family_state(ledger)
    if (top, owners) != (reused, sorted(reused_owners)):
        raise AssertionError("complete family recomputation disagrees")
    if not INCUMBENT <= top <= START_FAMILY_UB:
        raise AssertionError("family bound left the [incumbent, start] interval")
    competing = [
        {
            "PROFILE_ID": pid,
            "BOUND": b,
            "TRIANGLE_CAP": ledger[pid].cap,
            "SOURCE": ledger[pid].source,
        }
        for b, pid in ranked
        if b > prior.CURSOR_BOUND
    ]
    return {
        "FAMILY_UB": top,
        "OWNER_IDS": owners,
        "NEXT_COMPETING_BOUND": runner_up,
        "NEXT_COMPETING_IDS": sorted(pid for b, pid in terms if b == runner_up),
        "CURSOR_ID": prior.CURSOR_ID,
        "CURSOR_BOUND": prior.CURSOR_BOUND,
        "ROWS_ABOVE_CURSOR": competing,
        "RESOLVED_ROW_COUNT": len(ledger),
        "RESOLVED_ROWS_SHA256": rows_digest(ledger),
        "COVERAGE": covered,
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": top - INCUMBENT,
    }


def transitions(
    start: Ledger, installs: Sequence[tuple[str, int, str]]
) -> tuple[Ledger, list[dict[str, object]]]:
    ledger, out = start, list[dict[str, object]]()
    for pid, bound, locator in installs:
        before, owners = chase.family_state(ledger)
        ledger = install(ledger, pid, bound, locator)
        after, after_owners = chase.family_state(ledger)
        out.append(
            {
                "PROFILE_ID": pid,
                "PROFILE_WAS_OWNER": pid in owners,
                "FAMILY_BEFORE": before,
                "OWNER_IDS_BEFORE": owners,
                "PROFILE_BOUND_AFTER": bound,
                "FAMILY_AFTER": after,
                "OWNER_IDS_AFTER": after_owners,
            }
        )
    return ledger, out


def soundness(
    ledger: Mapping[str, Row], r30: Mapping[str, object], sts: Mapping[str, object]
) -> dict[str, object]:
    """Legal realizations obey the new floor; the canonical STS(13) witness stays admissible."""

    base = chase.witness_soundness(dict(ledger))
    named = {
        "T264_OWNER": T264_PROFILE,
        "STS13_PROFILE": STS13_PROFILE,
        "OWNER_MOTIF": OWNER_PROFILE,
        **{f"FINAL_OWNER_{pid}": pid for pid in chase.family_state(ledger)[1] if pid in ledger},
    }
    witnesses = {
        **{name: ledger[pid].realization for name, pid in named.items()},
        "P2": split.witness_supports("P2"),
        "STS13": split.witness_supports("STS13"),
    }
    checks: dict[str, object] = {}
    for name, w in witnesses.items():
        if w is None:
            continue
        seen = motif.realization_check(*w)
        pid, t = text(seen["PROFILE_ID"]), integer(seen["TRIANGLES"])
        k, _d, _p, _c, a, _d1, _p1 = map(integer, rows(seen["MOTIFS_K_D_P_C_A_D1_P1"]))
        floor = incidence_floor(split.profile_values(pid), t)
        exact = integer(seen["EXACT_S4_FROM_PINNED_LOCAL_TABLE"])
        if (
            exact < floor["S4_FLOOR"]
            or k < floor["K4_FLOOR"]
            or a > floor["A_MAX"]
            or integer(seen["R"]) > floor["L_MAX"]
            or (pid in ledger and t > ledger[pid].cap)
        ):
            raise AssertionError(f"incidence floor or cap excludes a legal realization: {name}")
        checks[name] = {
            "PROFILE_ID": pid,
            "TRIANGLES": t,
            "EXACT_S4": exact,
            "INCIDENCE_S4_FLOOR": floor["S4_FLOOR"],
        }
    if "T264_OWNER" not in checks:
        raise AssertionError("t264 owner's committed legal realization missing")
    witness, capability = object_row(r30["SOUNDNESS_WITNESS"]), object_row(r30["METHOD_CAPABILITY"])
    sts_seen = object_row(checks["STS13"])
    sts_bound = ledger[STS13_PROFILE].bound
    if (
        witness.get("PROFILE_ID") != STS13_PROFILE
        or capability.get("INCUMBENT_PROFILE_ID") != STS13_PROFILE
        or capability.get("INCUMBENT") != INCUMBENT
        or witness.get("GRAPH_TRIANGLES") != STS13_T
        or witness.get("EXACT_S4") != sts["EXACT_S4"]
        or sts_seen["EXACT_S4"] != sts["EXACT_S4"]
        or sts_bound < integer(capability["ROUTES_1_TO_4_FLOOR_FOR_INCUMBENT_PROFILE"])
        or sts_bound < integer(witness["EXACT_ANY_PRIZE_UNION"])
    ):
        raise AssertionError("canonical STS(13) incumbent witness tripwire")
    return {
        "STATUS": "PASS",
        "SPLIT_CAP_WITNESSES": base,
        "INCIDENCE_FLOOR_REALIZATIONS": checks,
        "CANONICAL_WITNESS": {
            "PROFILE_ID": STS13_PROFILE,
            "INCUMBENT": INCUMBENT,
            "EXACT_ANY_PRIZE_UNION": witness["EXACT_ANY_PRIZE_UNION"],
            "EXACT_S4": witness["EXACT_S4"],
            "ROUTES_1_TO_4_FLOOR": capability["ROUTES_1_TO_4_FLOOR_FOR_INCUMBENT_PROFILE"],
            "STS13_PROFILE_BOUND": sts_bound,
        },
    }


def compute_result(authority: chase.Authority | None = None) -> dict[str, object]:
    modules = provenance()
    sealed_chase = motif.pinned_result(chase.RESULT_FILENAME, CHASE_RESULT_SHA256)
    sealed_motif = pinned(BASE_HEAD, motif.RESULT_FILENAME, BASE_RESULT_SHA256)
    donor = pinned(STS13_DONOR_HEAD, STS13_RESULT_FILENAME, STS13_DONOR_RESULT_SHA256)
    r30 = motif.pinned_result(r32.CAP_SOURCE_RESULT, r32.R30_SHA256)
    r32_result = motif.pinned_result(r32.RESULT_FILENAME)
    auth = chase.load_authority() if authority is None else authority
    ledger = chase_ledger(auth, sealed_chase)
    attempts = rows(r30["GROUP_ATTEMPTS"])
    owner = owner_motif_certificate(
        ledger[OWNER_PROFILE], object_row(attempts[motif.CAP_INDEX]), sealed_motif, ledger
    )
    start = install(ledger, OWNER_PROFILE, integer(owner["CERTIFIED_PROFILE_BOUND"]), OWNER_LOCATOR)
    start_family = family(start, auth)
    if (start_family["FAMILY_UB"], start_family["OWNER_IDS"]) != (START_FAMILY_UB, START_OWNER_IDS):
        raise AssertionError("BASE_HEAD family state differs from the start authority")
    if (
        start_family["RESOLVED_ROWS_SHA256"]
        != object_row(sealed_motif["FAMILY_RECOMPUTATION"])["FINAL_RESOLVED_ROWS_SHA256"]
    ):
        raise AssertionError("BASE_HEAD ledger digest differs from the sealed owner motif result")
    identity = incidence_identity_check()
    t264 = t264_certificate(
        start[T264_PROFILE],
        object_row(attempts[T264_CAP_INDEX]),
        object_row(rows(r32_result["ROUTE_B_CERTIFICATES"])[T264_LEDGER_INDEX]),
    )
    sts = sts13_certificate(start[STS13_PROFILE], donor)
    final, steps = transitions(
        start,
        [
            (T264_PROFILE, integer(t264["CERTIFIED_PROFILE_BOUND"]), T264_LOCATOR),
            (STS13_PROFILE, integer(sts["CERTIFIED_PROFILE_BOUND"]), STS13_LOCATOR),
        ],
    )
    changed = sorted(pid for pid in final if final[pid] != ledger[pid])
    if changed != sorted((T264_PROFILE, STS13_PROFILE, OWNER_PROFILE)):
        raise AssertionError("only the three certified profiles may change")
    final_family = family(final, auth)
    checks = soundness(final, r30, sts)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "CHASE_LEDGER_HEAD": CHASE_HEAD,
        "CHASE_LEDGER_RESULT_SHA256": CHASE_RESULT_SHA256,
        "CHASE_LEDGER_ROWS_SHA256": sealed_chase["FINAL_RESOLVED_ROWS_SHA256"],
        "STS13_DONOR_HEAD": STS13_DONOR_HEAD,
        "STS13_DONOR_RESULT_SHA256": STS13_DONOR_RESULT_SHA256,
        "SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "MODULE_PROVENANCE": modules,
        "PROOF": __doc__,
        "INCIDENCE_IDENTITY": identity,
        "T264_OWNER_CERTIFICATE": t264,
        "STS13_CERTIFICATE": sts,
        "OWNER_MOTIF_CERTIFICATE": owner,
        "CERTIFIED_PROFILE_IDS": sorted((T264_PROFILE, STS13_PROFILE, OWNER_PROFILE)),
        "DOUBLE_COUNT_STATUS": "PASS_DISTINCT_PROFILES_ONE_CAP_TERM_EACH_S4_REPLACED_NOT_ADDED",
        "START_FAMILY": start_family,
        "OWNER_TRANSITIONS": steps,
        "FINAL_FAMILY": final_family,
        "START_COMPLETE_FAMILY_UB": start_family["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": final_family["FAMILY_UB"],
        "FINAL_OWNER_IDS": final_family["OWNER_IDS"],
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": final_family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - len(changed),
        "OTHER_ROWS_SHA256": digest(
            {pid: r.bound for pid, r in final.items() if pid not in changed}
        ),
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "WITNESS_SOUNDNESS": checks,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
    }


def verify_result(result: Mapping[str, object], authority: chase.Authority | None = None) -> None:
    if digest(result) != digest(compute_result(authority)):
        raise AssertionError("tampered immutable result")


def render(result: Mapping[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("immutable result already exists")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as out:
        out.write(render(result))
    keys = (
        "START_COMPLETE_FAMILY_UB",
        "FINAL_COMPLETE_FAMILY_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}))


if __name__ == "__main__":
    main()
