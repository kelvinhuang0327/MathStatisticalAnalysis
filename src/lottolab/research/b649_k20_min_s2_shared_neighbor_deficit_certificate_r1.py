"""Universal neighbor-deficit certificate on the 78 sealed active profiles.

For a vertex v of degree g, an actual neighbor u has at most g_u-1
neighbors inside N(v), hence at least max(g-g_u,0) missing incidences.
Their sum is at most 2*ow_v and each is at most ow_v. The descending
highest g degrees outside v dominate the actual descending neighbor
degrees coordinatewise. Thus ow_v >= q_v, where q_v is the maximum of
the ceiling of half the sum of these deficits and their maximum.
This proof uses only degree data and applies to every legal graph.

W=sum C(g_v,2), OW=sum ow_v=W-3t, G=max g_v, and
L=sum (g_v-2)*ow_v = (G-2)*OW-sum (G-g_v)*ow_v
 <= (G-2)*(W-3t)-delta = L_hat, delta=sum (G-g_v)*q_v.
Consequently t<=floor((W-sum q_v)/3); intersect with the sealed cap.
Only t above this universal cap are excluded, never a retained witness.

The pinned 96-case quartet table proves U=4K+2D+P+C,
L=2D+2P+3C and B=3A+2D1+P1. Pair linearity allows at most one
contained triple per quartet. With weights 679,448,112,0 it gives
S4=231K-63A+56*(2U-L-B)+56*(P1+C).
Here U=sum C(g_v,3), B=sum d_v*(g_v-2), A<=floor(B/3),
and 4K=U-L+P+2C>=U-L. Substituting L<=L_hat, K>=0 and
K>=ceil((U-L_hat)/4), then dropping nonnegative P1+C proves
F=max(0,231*max(0,ceil((U-L_hat)/4))-63*floor(B/3)
      +56*(2U-L_hat-B)). No Pasch assumption or credit is used.

Replay the immutable predecessor, retaining all 4569 other resolved rows,
197 frontier profiles, sealed cap authorities, special floors at their
original certified t, and S5 caps. On every retained active t use
MAX(existing S4,F) and MIN(existing bound,fourth bound,fifth bound),
then MAX over all retained t. The S5 identity stays
7*(sum_tau C(m_tau,2)+2*N_2T), with double-triple K5 weight 28.
Recompute the complete 4844-profile maximum and sorted integer bounds.
Every one of the 77 sealed support records is checked against the new
cap, S4 floor, per-t envelope and profile bound. No solver or census runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_all_resolved_cursor_refinement_r1 as previous
from .b649_k20_min_s2_split_cap_current_owner_chase_r1 import Row

integer, object_row, rows, digest = (
    previous.integer,
    previous.object_row,
    previous.rows,
    previous.digest,
)
integration, chase, nb = previous.integration, previous.chase, previous.nb
TASK_ID = "B649_K20_MIN_S2_SHARED_NEIGHBOR_DEFICIT_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-shared-neighbor-deficit-certificate-r1"
BASE_HEAD = "a1e5dd3cc32a07f6f5c6e70482578aeb6c950aaf"
BASE_TREE = "a7624329868107f3d77e5bcb91ab9da8cdd5ecc4"
BASE_RESULT_SHA256 = "6a41df1dd018706894d3ea6dba0d22c55d5f5f62239504f93cdc820c2359c622"
RESULT_FILENAME = "b649-k20-min-s2-shared-neighbor-deficit-certificate-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME
INCUMBENT = 313263888
START_BOUND = 313283936
type Profile = tuple[int, ...]
type Term = tuple[int, int, int, int | None, int, int, int, int, int, int, int, int, int]
TERM_COLUMNS = [
    "T",
    "OLD_BOUND",
    "OLD_K4_FLOOR",
    "OLD_CONTAINED_K4_CAP",
    "OLD_S4",
    "S3",
    "L_HAT",
    "K4_FLOOR",
    "SHARED_S4_FLOOR",
    "S4_USED",
    "FOURTH_ORDER_BOUND",
    "FIFTH_ORDER_BOUND",
    "BOUND",
]


@dataclass(frozen=True)
class Authority:
    inherited: previous.Authority
    sealed: dict[str, object]
    ledger: dict[str, Row]
    active: tuple[str, ...]
    provenance: dict[str, str]


@dataclass(frozen=True)
class Deficit:
    d: Profile
    g: Profile
    neighbors: tuple[Profile, ...]
    deficits: tuple[Profile, ...]
    q: Profile
    w: int
    u: int
    b: int
    delta: int
    sealed_cap: int
    cap: int

    def certificate(self) -> dict[str, object]:
        return {
            "D": list(self.d),
            "G_V": list(self.g),
            "G": max(self.g),
            "HIGHEST_OTHER_DEGREES": [list(h) for h in self.neighbors],
            "NEIGHBOR_DEFICITS": [list(h) for h in self.deficits],
            "Q_V": list(self.q),
            "SUM_Q": sum(self.q),
            "W": self.w,
            "U": self.u,
            "B": self.b,
            "DELTA": self.delta,
            "SEALED_TRIANGLE_CAP": self.sealed_cap,
            "UNIVERSAL_TRIANGLE_CAP": (self.w - sum(self.q)) // 3,
            "NEW_TRIANGLE_CAP": self.cap,
            "Q_PROOF": "SUM_MISSING_INCIDENCES=2*OW_V; EACH_MISSING_INCIDENCE<=OW_V",
            "L_HAT_PROOF": "L=(G-2)*(W-3T)-SUM((G-G_V)*OW_V)<=L_HAT",
        }


def profile_values(profile: str | Sequence[int]) -> Profile:
    if isinstance(profile, str):
        if len(profile) != 20 or any(c not in "0123456" for c in profile):
            raise ValueError("invalid canonical degree profile")
        d = tuple(map(int, profile))
    else:
        d = tuple(profile)
    if (
        len(d) != 20
        or any(type(v) is not int or not 0 <= v <= 6 for v in d)
        or sum(d) != 66
        or d != tuple(sorted(d, reverse=True))
    ):
        raise ValueError("expected descending twenty integer degrees in 0..6 with sum 66")
    return d


def neighbor_deficit(profile: str | Sequence[int], sealed_cap: int) -> Deficit:
    d = profile_values(profile)
    g = tuple(6 + v for v in d)
    w = sum(comb(v, 2) for v in g)
    if type(sealed_cap) is not int or not 22 <= sealed_cap <= w // 3:
        raise ValueError("invalid sealed triangle cap")
    highest = tuple(
        tuple(sorted(g[:i] + g[i + 1 :], reverse=True)[:own]) for i, own in enumerate(g)
    )
    deficits = tuple(tuple(max(own - h, 0) for h in hs) for own, hs in zip(g, highest, strict=True))
    q = tuple(max((sum(ds) + 1) // 2, max(ds, default=0)) for ds in deficits)
    delta = sum((max(g) - v) * qv for v, qv in zip(g, q, strict=True))
    cap = min(sealed_cap, (w - sum(q)) // 3)
    if cap < 22:
        raise AssertionError("universal cap excludes the required 22 triple supports")
    return Deficit(
        d,
        g,
        highest,
        deficits,
        q,
        w,
        sum(comb(v, 3) for v in g),
        sum(v * (gv - 2) for v, gv in zip(d, g, strict=True)),
        delta,
        sealed_cap,
        cap,
    )


def s4_floor(proof: Deficit, t: int) -> tuple[int, int, int]:
    if type(t) is not int or not 22 <= t <= proof.cap:
        raise ValueError("t outside the universally retained legal range")
    l_hat = (max(proof.g) - 2) * (proof.w - 3 * t) - proof.delta
    k4 = max(0, -(-(proof.u - l_hat) // 4))
    floor = max(0, 231 * k4 - 63 * (proof.b // 3) + 56 * (2 * proof.u - l_hat - proof.b))
    return l_hat, k4, floor


def pinned_file(relative: str) -> bytes:
    blob = chase.git("show", f"{BASE_HEAD}:{relative}")
    if (chase.ROOT / relative).read_bytes() != blob:
        raise AssertionError(f"immutable source/result bytes differ: {relative}")
    return blob


def active_profiles(ledger: Mapping[str, Row], sealed: Mapping[str, object]) -> tuple[str, ...]:
    active = tuple(sorted(pid for pid, row in ledger.items() if row.bound > INCUMBENT))
    if len(active) != 78 or list(active) != sealed["ABOVE_INCUMBENT_PROFILE_IDS"]:
        raise AssertionError("sealed active profile coverage differs")
    return active


@cache
def load_authority() -> Authority:
    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("immutable base tree mismatch")
    sealed = integration.pinned(BASE_HEAD, previous.RESULT_FILENAME, BASE_RESULT_SHA256)
    relative = Path(previous.__file__ or "").resolve().relative_to(chase.ROOT).as_posix()
    source = pinned_file(relative)
    if hashlib.sha256(source).hexdigest() != sealed["SOURCE_SHA256"]:
        raise AssertionError("immutable predecessor source identity mismatch")
    inherited = previous.load_authority()
    if digest(previous.compute_result(inherited)) != digest(sealed):
        raise AssertionError("immutable complete predecessor replay mismatch")
    ledger = dict(inherited.ledger)
    certs = object_row(sealed["RESOLVED_CERTIFICATES"])
    if set(certs) != set(ledger):
        raise AssertionError("sealed resolved profile coverage differs")
    for pid, raw in certs.items():
        cert = object_row(raw)
        bound = integer(cert["CERTIFIED_PROFILE_BOUND"])
        row = ledger[pid]
        if cert["PROFILE_ID"] != pid or not 0 <= bound <= row.bound:
            raise AssertionError("invalid inherited profile refinement")
        if bound != row.bound:
            ledger[pid] = replace(
                row, bound=bound, source=f"{previous.RESULT_FILENAME}:RESOLVED_CERTIFICATES[{pid}]"
            )
    frontier = object_row(sealed["FRONTIER_CERTIFICATES"])
    if previous.family(ledger, frontier, inherited) != sealed["FINAL_FAMILY"]:
        raise AssertionError("complete sealed Family ledger differs")
    if sealed["FINAL_COMPLETE_FAMILY_UB"] != START_BOUND:
        raise AssertionError("starting Family maximum differs")
    provenance = {**inherited.provenance, relative: hashlib.sha256(source).hexdigest()}
    for path, expected in {**provenance, **inherited.result_provenance}.items():
        if hashlib.sha256(pinned_file(path)).hexdigest() != expected:
            raise AssertionError("inherited source authority differs")
    return Authority(inherited, sealed, ledger, active_profiles(ledger, sealed), provenance)


def assert_authority(auth: Authority) -> None:
    previous.partition_check(auth.ledger, auth.inherited.frontier, auth.inherited.family_authority)
    if active_profiles(auth.ledger, auth.sealed) != auth.active:
        raise AssertionError("active profile selection differs")
    sealed_rows = object_row(auth.sealed["RESOLVED_CERTIFICATES"])
    if set(auth.ledger) != set(sealed_rows):
        raise AssertionError("missing sealed profile")
    for pid, row in auth.ledger.items():
        original = previous.assert_row(auth.inherited, pid)
        bound = integer(object_row(sealed_rows[pid])["CERTIFIED_PROFILE_BOUND"])
        expected = (
            original
            if bound == original.bound
            else replace(
                original,
                bound=bound,
                source=f"{previous.RESULT_FILENAME}:RESOLVED_CERTIFICATES[{pid}]",
            )
        )
        if row != expected:
            raise AssertionError("sealed row/cap/floor/witness identity mismatch")


def authoritative_terms(auth: Authority, pid: str) -> list[previous.Term]:
    cert = object_row(object_row(auth.sealed["RESOLVED_CERTIFICATES"])[pid])
    original = previous.authoritative_terms(auth.inherited, pid)
    s5 = integer(object_row(cert["DEGREE_S5_PROOF"])["S5_CAP"])
    terms, fifths = previous.refine_terms(original, s5)
    if (
        digest(original) != cert["AUTHORITATIVE_TERMS_SHA256"]
        or digest(terms) != cert["ALL_T_TERMS_SHA256"]
        or digest(fifths) != cert["BONFERRONI5_TERMS_SHA256"]
        or max(term[1] for term in terms) != auth.ledger[pid].bound
        or previous.degree_s5_cap(pid) != cert["DEGREE_S5_PROOF"]
    ):
        raise AssertionError("sealed per-t envelope or S5 authority differs")
    return terms


def refine_terms(old: Sequence[previous.Term], proof: Deficit, s5: int) -> list[Term]:
    if [term[0] for term in old] != list(range(22, proof.sealed_cap + 1)):
        raise AssertionError("incomplete sealed t range")
    new: list[Term] = []
    for t, bound, k, a, s4, s3 in old:
        if t > proof.cap:
            continue
        l_hat, k4, shared = s4_floor(proof, t)
        used = max(s4, shared)
        fourth, fifth = previous.moment_bounds(s3, used, s5)
        new.append(
            (
                t,
                bound,
                k,
                a,
                s4,
                s3,
                l_hat,
                k4,
                shared,
                used,
                fourth,
                fifth,
                min(bound, fourth, fifth),
            )
        )
    return new


def active_certificate(auth: Authority, pid: str) -> dict[str, object]:
    if pid not in auth.active:
        raise AssertionError("shared certificate adoption outside the active profiles")
    row = auth.ledger[pid]
    sealed = object_row(object_row(auth.sealed["RESOLVED_CERTIFICATES"])[pid])
    old = authoritative_terms(auth, pid)
    proof = neighbor_deficit(pid, row.cap)
    s5_proof = object_row(sealed["DEGREE_S5_PROOF"])
    new = refine_terms(old, proof, integer(s5_proof["S5_CAP"]))
    maximum = max(term[-1] for term in new)
    return {
        "PROFILE_ID": pid,
        "OLD_PROFILE_BOUND": row.bound,
        "SEALED_ROW_SHA256": digest(previous.row_identity(pid, row)),
        "CAP_AUTHORITY": sealed["CAP_AUTHORITY"],
        "NEIGHBOR_DEFICIT_PROOF": proof.certificate(),
        "SPECIAL_CERTIFICATE_SHA256": sealed["SPECIAL_CERTIFICATE_SHA256"],
        "S4_SCOPE": "MAX(SEALED_PER_T_FLOOR,UNIVERSAL_F); SPECIAL_MOTIF_AT_ORIGINAL_T_ONLY",
        "DEGREE_S5_PROOF": s5_proof,
        "S5_SCOPE": sealed["S5_SCOPE"],
        "SEALED_T_RANGE": [22, row.cap],
        "T_RANGE": [22, proof.cap],
        "OLD_T_TERM_COUNT": len(old),
        "LEGAL_T_COUNT": len(new),
        "EXCLUDED_T_VALUES": list(range(proof.cap + 1, row.cap + 1)),
        "EXCLUSION_PROOF": "3*T>W-SUM_Q; SUM_OW_V=W-3*T>=SUM_Q",
        "AUTHORITATIVE_TERMS_SHA256": digest(old),
        "ALL_T_TERMS": new,
        "ALL_T_TERMS_SHA256": digest(new),
        "CERTIFIED_PROFILE_BOUND": maximum,
        "ARGMAX_T": [term[0] for term in new if term[-1] == maximum],
        "BOUND_RULE": "MAX_S4; MIN_EXISTING_FOURTH_FIFTH; MAX_ALL_RETAINED_T",
    }


def witness_soundness(
    auth: Authority, ledger: Mapping[str, Row], certs: Mapping[str, object]
) -> dict[str, object]:
    # load_authority freshly replayed all support records and exact local moments.
    sound = object_row(auth.sealed["WITNESS_SOUNDNESS"])
    witnesses = object_row(sound["WITNESSES"])
    checks: dict[str, object] = {}
    if len(witnesses) != 77:
        raise AssertionError("sealed witness coverage differs")
    for name, raw in witnesses.items():
        witness = object_row(raw)
        pid = integration.text(witness["PROFILE_ID"])
        t = integer(witness["TRIANGLES"])
        old = authoritative_terms(auth, pid)
        if pid in certs:
            cert = object_row(certs[pid])
            proof = neighbor_deficit(pid, auth.ledger[pid].cap)
            s5 = integer(object_row(cert["DEGREE_S5_PROOF"])["S5_CAP"])
            terms = refine_terms(old, proof, s5)
            if t > proof.cap:
                raise AssertionError(f"universal cap excludes a legal support: {name}")
            term = terms[t - 22]
            floor, bound = term[9], term[-1]
        else:
            term_old = old[t - 22]
            floor, bound = term_old[4], term_old[1]
            sealed_cert = object_row(object_row(auth.sealed["RESOLVED_CERTIFICATES"])[pid])
            s5 = integer(object_row(sealed_cert["DEGREE_S5_PROOF"])["S5_CAP"])
        if (
            not 22 <= t <= auth.ledger[pid].cap
            or integer(witness["EXACT_S5"]) > s5
            or integer(witness["EXACT_S4_FROM_PINNED_LOCAL_TABLE"]) < floor
            or integer(witness["EXACT_MOMENT_UPPER_BOUND"]) > bound
            or integer(witness["EXACT_MOMENT_UPPER_BOUND"]) > ledger[pid].bound
        ):
            raise AssertionError(f"refined envelope excludes a legal support witness: {name}")
        checks[name] = {
            "PROFILE_ID": pid,
            "T": t,
            "S4_USED": floor,
            "S5_CAP": s5,
            "T_BOUND": bound,
            "PROFILE_BOUND": ledger[pid].bound,
        }
    if (
        ledger[integration.STS13_PROFILE].bound < INCUMBENT
        or object_row(sound["TRADED_STS13_EXACT_UNION"])["EXACT_ANY_PRIZE_UNION"] != INCUMBENT
    ):
        raise AssertionError("incumbent support soundness differs")
    return {
        "STATUS": "PASS",
        "WITNESS_COUNT": len(checks),
        "PRESERVED_WITNESS_RECORDS_SHA256": digest(witnesses),
        "CHECKS": checks,
    }


def complete_bounds(
    ledger: Mapping[str, Row], frontier: Mapping[str, object], auth: Authority
) -> list[list[object]]:
    previous.partition_check(ledger, tuple(frontier), auth.inherited.family_authority)
    bounds = {pid: row.bound for pid, row in ledger.items()}
    for pid, raw in frontier.items():
        cert = object_row(raw)
        if cert["PROFILE_ID"] != pid:
            raise AssertionError("frontier certificate identity differs")
        bounds[pid] = integer(cert["CERTIFIED_PROFILE_BOUND"])
    return [[pid, bound] for pid, bound in sorted(bounds.items())]


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    assert_authority(auth)
    certs: dict[str, object] = {}
    final = dict(auth.ledger)
    for pid in auth.active:
        cert = active_certificate(auth, pid)
        certs[pid] = cert
        bound = integer(cert["CERTIFIED_PROFILE_BOUND"])
        if not 0 <= bound <= final[pid].bound:
            raise AssertionError("invalid shared refinement")
        if bound != final[pid].bound:
            final[pid] = replace(
                final[pid], bound=bound, source=f"{RESULT_FILENAME}:ACTIVE_CERTIFICATES[{pid}]"
            )
    frontier = object_row(auth.sealed["FRONTIER_CERTIFICATES"])
    final_family = previous.family(final, frontier, auth.inherited)
    bounds = complete_bounds(final, frontier, auth)
    maximum = max(integer(pair[1]) for pair in bounds)
    if maximum != final_family["FAMILY_UB"] or not INCUMBENT <= maximum <= START_BOUND:
        raise AssertionError("complete Family maximum differs")
    unchanged = [
        previous.row_identity(pid, row)
        for pid, row in sorted(final.items())
        if pid not in auth.active
    ]
    if len(unchanged) != 4569 or any(
        final[p] != r for p, r in auth.ledger.items() if p not in auth.active
    ):
        raise AssertionError("non-active resolved row changed")
    sound = witness_soundness(auth, final, certs)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "MODULE_PROVENANCE": auth.provenance,
        "RESULT_PROVENANCE": auth.inherited.result_provenance,
        "SOURCE_AUTHORITY_STATUS": "PASS_EXACT_TREE_BYTES_SHA_AND_EXECUTABLE_REPLAY",
        "PROOF": __doc__,
        "LOCAL_QUARTET_IDENTITY": previous.motif.local_identity_check(),
        "ACTIVE_PROFILE_COUNT": len(certs),
        "ACTIVE_PROFILE_IDS": list(auth.active),
        "ACTIVE_CERTIFICATES": certs,
        "TERM_COLUMNS": TERM_COLUMNS,
        "NEW_CAP_PROOF_STATUS": "PASS_UNIVERSAL_NEIGHBOR_DEFICITS",
        "NEW_S4_FLOOR_PROOF_STATUS": "PASS_WEIGHTED_DEFICIENCY_AND_LOCAL_IDENTITY",
        "OLD_ACTIVE_T_TERM_COUNT": sum(
            integer(object_row(c)["OLD_T_TERM_COUNT"]) for c in certs.values()
        ),
        "CAP_REDUCTION_PROFILE_IDS": [
            p for p, c in certs.items() if rows(object_row(c)["EXCLUDED_T_VALUES"])
        ],
        "EXCLUDED_T_TERM_COUNT": sum(
            len(rows(object_row(c)["EXCLUDED_T_VALUES"])) for c in certs.values()
        ),
        "RETAINED_T_TERM_COUNT": sum(
            integer(object_row(c)["LEGAL_T_COUNT"]) for c in certs.values()
        ),
        "PROFILES_BELOW_INCUMBENT": sum(final[p].bound < INCUMBENT for p in auth.active),
        "NEW_TOP_OWNER_BOUND": final["66555555555540000000"].bound,
        "STS13_BOUND": final[integration.STS13_PROFILE].bound,
        "S5_IDENTITY": auth.sealed["S5_IDENTITY"],
        "SPECIAL_PER_T_CERTIFICATES_SHA256": digest(auth.sealed["SPECIAL_PER_T_CERTIFICATES"]),
        "SPECIAL_S4_SCOPE_STATUS": "PASS_ORIGINAL_CERTIFIED_T_ONLY",
        "UNCHANGED_RESOLVED_ROW_COUNT": len(unchanged),
        "UNCHANGED_RESOLVED_ROWS_SHA256": digest(unchanged),
        "FRONTIER_CERTIFICATES": frontier,
        "FRONTIER_CERTIFICATES_SHA256": digest(frontier),
        "FRONTIER_PROFILE_COUNT": len(frontier),
        "FINAL_FAMILY": final_family,
        "START_COMPLETE_FAMILY_UB": START_BOUND,
        "FINAL_COMPLETE_FAMILY_UB": maximum,
        "FINAL_OWNER_IDS": final_family["OWNER_IDS"],
        "REMAINING_GAP": maximum - INCUMBENT,
        "COMPLETE_PROFILE_BOUNDS": bounds,
        "COMPLETE_BOUNDS_SHA256": digest(bounds),
        "COMPLETE_BOUNDS_ENCODING": "SHA256_CANONICAL_JSON_SORTED_PROFILE_ID_INTEGER_BOUND_PAIRS",
        "COMPLETE_4844_COVERAGE_STATUS": "PASS_DISJOINT_EXHAUSTIVE_DIGEST_MATCHED",
        "DOUBLE_COUNT_STATUS": "PASS_MAX_FLOORS_MIN_BOUNDS_NO_ADDITIVE_CREDIT",
        "WITNESS_SOUNDNESS": sound,
        "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_77_RECORDS",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PROFILE_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def verify_result(result: Mapping[str, object], authority: Authority | None = None) -> None:
    if digest(result) != digest(compute_result(authority)):
        raise AssertionError("tampered universal neighbor-deficit executable certificate")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", action="store_true", help="recompute and verify exact JSON bytes"
    )
    args = parser.parse_args()
    result = compute_result()
    rendered = integration.render(result).encode("utf-8")
    if args.verify:
        if RESULT_PATH.read_bytes() != rendered:
            raise AssertionError("universal certificate byte replay differs")
    else:
        with RESULT_PATH.open("xb") as out:
            out.write(rendered)
    print(
        json.dumps(
            {
                "RESULT_REPLAY_STATUS": "PASS" if args.verify else "CREATED",
                **{
                    k: result[k]
                    for k in (
                        "ACTIVE_PROFILE_COUNT",
                        "EXCLUDED_T_TERM_COUNT",
                        "RETAINED_T_TERM_COUNT",
                        "FINAL_COMPLETE_FAMILY_UB",
                        "REMAINING_GAP",
                        "COMPLETE_BOUNDS_SHA256",
                    )
                },
            }
        )
    )


if __name__ == "__main__":
    main()
