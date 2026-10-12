"""Single-owner t=265 Bonferroni-5 certificate on the sealed Minimum-S2 ledger.

For every admissible pair-linear system, there are 22 triple supports and
sum d=66, with graph degrees g=6+d. A triple tau has at most
min(g_v-2)=4+min(d_v) common outside neighbours. Let H_k count supports
whose three degrees are at least k. Each uses three high incidences, so
3*H_k<=sum_{d>=k}d. Every low vertex belongs to d_v distinct supports
outside H_k, so H_k<=22-d_v; fewer than three high vertices forces H_k=0.
These integer inequalities give H1..H6 <= 22,21,20,20,18,8 for the owner.
The threshold telescoping sum bounds sum_tau C(m_tau,2) by 801.
Linearity gives one shared vertex per intersecting triple pair, hence
N_2T<=sum_v C(d_v,2)=133. The inherited exact identity is
S5=7*(sum_tau C(m_tau,2)+2*N_2T), so S5<=7*(801+266)=7469.
A double-triple K5 has weight 28; the +2 correction is essential.

R30 GROUP_ATTEMPTS[2767] refutes t=266, agreeing with NB_CERTIFICATES[883]
on cap 265. W=829, J=2336, B=596, A_MAX=198. Recompute all 244 original
terms with exact integer/rational checks. At t=265, S3=5175296 and
S4_floor=293083 give U5=S1-S2+S3-S4_floor+S5_cap=313279722.
Adopt MIN(existing bound,U5), never add overlapping credits. Only that
BOUND field changes. The 243 lower terms retain their digest and maximum
313388704. Recompute the complete family maximum over all 4647 resolved
rows plus the inherited cursor, preserving all 4844 admissible profiles,
existing certificates and witnesses. No solver or census is launched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_two_tied_owners_bonferroni5_r1 as previous
from .b649_k20_min_s2_split_cap_current_owner_chase_r1 import Row
from .b649_k20_min_s2_three_motif_complete_family_integration_r1 import Ledger

integration, chase, split, event = (
    previous.integration,
    previous.chase,
    previous.split,
    previous.event,
)
integer, object_row, rows, digest = (
    previous.integer,
    previous.object_row,
    previous.rows,
    previous.digest,
)
nb, motif = previous.nb, previous.motif
identity = previous.identity
moment_bounds = previous.moment_bounds
TASK_ID = "B649_K20_MIN_S2_OWNER_66665555554421100000_BONFERRONI5_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-owner-66665555554421100000-bonferroni5-r1"
BASE_HEAD = "f0ca4444faa4f57ea1dedcc293b029379e9f1494"
BASE_TREE = "ad9b4949204764d68e26caba93a3cb300aa1761c"
BASE_RESULT_SHA256 = "1998f36a92cea15ea4f7413a21a48dd1cad3a90aa7f5c840110ede30034a97ec"
OWNER_PROFILE = "66665555554421100000"
OWNER_SOURCES = {OWNER_PROFILE: (883, 2767)}
LOWER_T_SHA256 = "e919a34e55b2b0aa3ae597bc15636cbbfb0576a2e445da218da66f628a132d93"
CAP = 265
RESULT_FILENAME = "b649-k20-min-s2-owner-66665555554421100000-bonferroni5-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME


@dataclass(frozen=True)
class Authority:
    inherited: previous.Authority
    ledger: Ledger
    sealed: dict[str, object]
    r30: dict[str, object]
    provenance: dict[str, str]


@cache
def load_authority() -> Authority:
    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    sealed = integration.pinned(BASE_HEAD, previous.RESULT_FILENAME, BASE_RESULT_SHA256)
    path = Path(previous.__file__ or "").resolve()
    relative = path.relative_to(chase.ROOT).as_posix()
    blob = chase.git("show", f"{BASE_HEAD}:{relative}")
    if path.read_bytes() != blob or hashlib.sha256(blob).hexdigest() != sealed["SOURCE_SHA256"]:
        raise AssertionError("predecessor source identity mismatch")
    inherited = previous.load_authority()
    # Replay the committed verifier; its existing bounded local identity table is inherited.
    if digest(previous.compute_result(inherited)) != digest(sealed):
        raise AssertionError("sealed predecessor replay differs")
    ledger = dict(inherited.ledger)
    for pid in previous.OWNER_SOURCES:
        cert = object_row(object_row(sealed["OWNER_CERTIFICATES"])[pid])
        ledger = integration.install(
            ledger,
            pid,
            integer(cert["CERTIFIED_PROFILE_BOUND"]),
            f"{previous.RESULT_FILENAME}:OWNER_CERTIFICATES[{pid}]",
        )
    family = integration.family(
        ledger, inherited.inherited.inherited.inherited.inherited.inherited.inherited
    )
    if family != sealed["FINAL_FAMILY"] or family["OWNER_IDS"] != sorted(OWNER_SOURCES):
        raise AssertionError("sealed complete family or owner differs")
    return Authority(
        inherited,
        ledger,
        sealed,
        inherited.r30,
        {**inherited.provenance, relative: hashlib.sha256(blob).hexdigest()},
    )


def degree_s5_cap(profile: str | Sequence[int]) -> dict[str, object]:
    """Universal integer threshold proof; see the module proof for each inequality."""
    d = split.profile_values(profile)
    g = tuple(6 + v for v in d)
    thresholds: list[list[int]] = []
    weights = [comb(4 + k, 2) for k in range(1, 7)]
    for k in range(1, 7):
        high = [v for v in d if v >= k]
        low = [v for v in d if 0 < v < k]
        incidence = sum(high) // 3 if len(high) >= 3 else 0
        low_vertex = 22 - max(low, default=0)
        thresholds.append(
            [k, len(high), sum(high), incidence, low_vertex, min(incidence, low_vertex)]
        )
    common_cap = 22 * weights[0] + sum(
        thresholds[k - 1][5] * (weights[k - 1] - weights[k - 2]) for k in range(2, 7)
    )
    n2_cap = sum(comb(v, 2) for v in d)
    return {
        "STATUS": "PASS",
        "D": list(d),
        "G": list(g),
        "M_TAU_CAP": "4 + min(d_v for v in tau)",
        "H_K_DEFINITION": "number of triple supports all of whose vertex degrees are >= k",
        "THRESHOLD_COLUMNS": [
            "K",
            "HIGH_VERTEX_COUNT",
            "HIGH_INCIDENCES",
            "INCIDENCE_CAP",
            "LOW_VERTEX_CAP",
            "H_K_CAP",
        ],
        "THRESHOLD_CAPS": thresholds,
        "COMMON_PAIR_SUM_CAP": common_cap,
        "N_2T_CAP": n2_cap,
        "S5_CAP": 7 * (common_cap + 2 * n2_cap),
    }


def check_cap(pid: str, row: Row, proof: Mapping[str, object]) -> None:
    index, attempt = OWNER_SOURCES[pid]
    d = split.profile_values(pid)
    w = sum(comb(6 + v, 2) for v in d)
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": attempt,
        "PROFILE_IDS": [pid],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "ROUTE": integration.r32.CAP_SOURCE_ROUTE,
        "WEDGE_COUNT": w,
        "TARGET_TRIANGLE_CAP": CAP,
        "REFUTED_GRAPH_TRIANGLE_COUNT": CAP + 1,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": CAP,
        "OPEN_WEDGE_CEILING_REFUTED": w - 3 * (CAP + 1),
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": w - 3 * (CAP + 1) + 1,
    }
    if (
        type(row.cap) is not int
        or row.cap != CAP
        or row.source != f"{nb.RESULT_FILENAME}:NB_CERTIFICATES[{index}]"
        or row.s4_base != nb.r28.profile_s4_floor(d)
        or any(digest(proof.get(k)) != digest(v) for k, v in expected.items())
        or integration.r32.r28.r26.accepted_cap(proof, (d,), CAP) != CAP
        or nb.combined_triangle_cap(nb.profile_nb_cap(d)[2], nb.r18_cap(d), CAP) != CAP
    ):
        raise AssertionError("owner cap-source identity mismatch")


def owner_certificate(pid: str, row: Row, proof: Mapping[str, object]) -> dict[str, object]:
    check_cap(pid, row, proof)
    d = split.profile_values(pid)
    old = split.route_b_terms(d, row.cap, row.s4_base)
    identity.previous.previous.exact_terms(d, old, row.cap)
    *lower, last = old
    t, old_bound, _k, _a, s4, s3 = last
    if t != CAP or old_bound != row.bound or max(term[1] for term in old) != row.bound:
        raise AssertionError("load-bearing envelope differs from sealed ledger")
    if len(lower) != 243 or digest(lower) != LOWER_T_SHA256:
        raise AssertionError("lower-t preservation digest mismatch")
    cap = degree_s5_cap(d)
    fourth, fifth = moment_bounds(s3, s4, integer(cap["S5_CAP"]))
    if old_bound != fourth:
        raise AssertionError("fourth-order rounding changed")
    new_bound = min(old_bound, fifth)
    terms = [*lower, (t, new_bound, *last[2:])]
    return {
        "STATUS": "PASS",
        "PROFILE_ID": pid,
        "TRIANGLE_CAP": CAP,
        "LOAD_BEARING_T": t,
        "CAP_SOURCE": row.source,
        "ORIGINAL_CAP_SOURCE": f"{integration.r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS"
        f"[{OWNER_SOURCES[pid][1]}]",
        "CAP_SOURCE_IDENTITY": dict(proof),
        "DEGREE_S5_PROOF": cap,
        "W": sum(comb(6 + v, 2) for v in d),
        "J": sum(comb(6 + v, 3) for v in d),
        "B": sum(v * (4 + v) for v in d),
        "A_MAX": sum(v * (4 + v) for v in d) // 3,
        "S4_BASE": row.s4_base,
        "EXISTING_S4_FLOOR": s4,
        "OLD_T265_BOUND": old_bound,
        "BONFERRONI5_T265_BOUND": fifth,
        "NEW_T265_BOUND": new_bound,
        "EXACT_INTEGER_GAIN": old_bound - new_bound,
        "BOUND_RULE": "MIN(EXISTING_FOURTH_ORDER, BONFERRONI5); NEVER ADD CREDITS",
        "RETAINED_LOWER_T_COUNT": len(lower),
        "RETAINED_LOWER_T_MAX": max(term[1] for term in lower),
        "RETAINED_TERMS_SHA256": digest(lower),
        "LOWER_T_PRESERVATION": "PASS_BYTE_EQUIVALENT_CANONICAL_TERMS",
        "CHANGED_TERM_FIELDS": [[CAP, "BOUND"]],
        "ALL_T_RECOMPUTATION_STATUS": "PASS_EXACT_INTEGER_AND_RATIONAL",
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "ALL_T_TERMS": [list(term) for term in terms],
        "CERTIFIED_PROFILE_BOUND": max(term[1] for term in terms),
    }


def verify_certificate(
    cert: Mapping[str, object], pid: str, row: Row, proof: Mapping[str, object]
) -> None:
    if digest(cert) != digest(owner_certificate(pid, row, proof)):
        raise AssertionError("tampered Bonferroni5 certificate")


def witness_soundness(ledger: Mapping[str, Row], certs: Mapping[str, object]) -> dict[str, object]:
    named = {pid: ledger[pid].realization for pid in OWNER_SOURCES}
    named.update({kind: split.witness_supports(kind) for kind in ("P2", "STS13")})
    checks: dict[str, object] = {}
    for name, supports in named.items():
        if supports is None:
            continue
        triples, pairs = supports
        seen = motif.realization_check(triples, pairs)
        pid = integration.text(seen["PROFILE_ID"])
        if name in OWNER_SOURCES and pid != name:
            raise AssertionError("recorded owner witness profile differs")
        d = tuple(sum(v in tau for tau in triples) for v in range(20))
        edges = {e for tau in triples for e in combinations(tau, 2)} | {(a, b) for a, b in pairs}
        common, n2 = identity.s5_counts(tuple(range(20)), edges, triples)
        s5 = identity.s5_identity_value(common, n2)
        cap = degree_s5_cap(d)
        t, s4 = integer(seen["TRIANGLES"]), integer(seen["EXACT_S4_FROM_PINNED_LOCAL_TABLE"])
        if s5 > integer(cap["S5_CAP"]):
            raise AssertionError("degree cap excludes legal witness S5")
        s3, _ = chase.r20.bound_from_cap(split.profile_values(d), t, s4)
        fourth, fifth = moment_bounds(s3, s4, s5)
        witness_bound = min(fourth, fifth)
        if pid in certs:
            cert = object_row(certs[pid])
            terms = {
                integer(rows(raw)[0]): integer(rows(raw)[1]) for raw in rows(cert["ALL_T_TERMS"])
            }
            if (
                t > ledger[pid].cap
                or t not in terms
                or (t == CAP and s4 < integer(cert["EXISTING_S4_FLOOR"]))
                or witness_bound > terms[t]
                or witness_bound > integer(cert["CERTIFIED_PROFILE_BOUND"])
            ):
                raise AssertionError("new bound excludes legal owner witness")
        checks[name] = {
            **seen,
            "EXACT_S5": s5,
            "S5_CAP": cap["S5_CAP"],
            "M_TAU": list(common),
            "N_2T": n2,
            "EXACT_MOMENT_UPPER_BOUND": witness_bound,
            "SUPPORTS_SHA256": digest(supports),
        }
    sts = identity.previous.higher_order_sums(*split.witness_supports("STS13"))
    if object_row(checks["STS13"])["EXACT_S5"] != sts["S5"] or ledger[
        integration.STS13_PROFILE
    ].bound < integer(sts["EXACT_ANY_PRIZE_UNION"]):
        raise AssertionError("STS13 exact witness differs or is excluded")
    return {
        "STATUS": "PASS",
        "WITNESSES": checks,
        "OWNER_REALIZATION_STATUS": {
            pid: "NONE_RECORDED" if ledger[pid].realization is None else "PASS"
            for pid in OWNER_SOURCES
        },
        "STS13_EXACT_UNION": sts,
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    certs: dict[str, object] = {}
    final = dict(auth.ledger)
    for pid, (_index, attempt) in OWNER_SOURCES.items():
        proof = object_row(rows(auth.r30["GROUP_ATTEMPTS"])[attempt])
        cert = owner_certificate(pid, auth.ledger[pid], proof)
        verify_certificate(cert, pid, auth.ledger[pid], proof)
        certs[pid] = cert
        final = integration.install(
            final,
            pid,
            integer(cert["CERTIFIED_PROFILE_BOUND"]),
            f"{RESULT_FILENAME}:OWNER_CERTIFICATES[{pid}]",
        )
    if {pid for pid in final if final[pid] != auth.ledger[pid]} != set(OWNER_SOURCES):
        raise AssertionError("only the certified owner row must change")
    family_auth = auth.inherited.inherited.inherited.inherited.inherited.inherited.inherited
    start, family = (
        integration.family(auth.ledger, family_auth),
        integration.family(final, family_auth),
    )
    if (start["CURSOR_ID"], start["CURSOR_BOUND"], start["COVERAGE"]) != (
        family["CURSOR_ID"],
        family["CURSOR_BOUND"],
        family["COVERAGE"],
    ):
        raise AssertionError("cursor authority or coverage changed")
    soundness = witness_soundness(final, certs)
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
        "PROOF": __doc__,
        "S5_IDENTITY": auth.sealed["S5_IDENTITY"],
        "S5_IDENTITY_STATUS": "INHERITED_INDEPENDENT_PROOF_REPLAYED",
        "BONFERRONI5": identity.bonferroni_check(),
        "OWNER_CERTIFICATES": certs,
        "START_FAMILY": start,
        "FINAL_FAMILY": family,
        "START_COMPLETE_FAMILY_UB": start["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": family["FAMILY_UB"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "REMAINING_GAP": family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - len(OWNER_SOURCES),
        "OTHER_ROWS_FULL_SHA256": digest(
            [
                [pid, row.bound, row.cap, row.s4_base, row.source, row.realization]
                for pid, row in sorted(final.items())
                if pid not in OWNER_SOURCES
            ]
        ),
        "OTHER_ROWS_SHA256": digest(
            {pid: row.bound for pid, row in final.items() if pid not in OWNER_SOURCES}
        ),
        "INHERITED_CERTIFICATES": auth.sealed["INHERITED_CERTIFICATES"],
        "PREDECESSOR_OWNER_CERTIFICATES": auth.sealed["OWNER_CERTIFICATES"],
        "EARLIER_OWNER_CERTIFICATES": auth.sealed["PREDECESSOR_OWNER_CERTIFICATES"],
        "OLDER_OWNER_CERTIFICATES": auth.sealed["EARLIER_OWNER_CERTIFICATES"],
        "STS13_CERTIFICATE_SHA256": auth.sealed["STS13_CERTIFICATE_SHA256"],
        "STS13_ROW_UNCHANGED": final[integration.STS13_PROFILE]
        == auth.ledger[integration.STS13_PROFILE],
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "DOUBLE_COUNT_STATUS": "PASS_MIN_OF_BOUNDS_NO_ADDITIVE_CREDITS",
        "WITNESS_SOUNDNESS": soundness,
        "INHERITED_WITNESS_SOUNDNESS": auth.sealed["WITNESS_SOUNDNESS"],
        "WITNESS_SOUNDNESS_STATUS": "PASS",
        "CURSOR_AUTHORITY_STATUS": "UNCHANGED",
        "HISTORICAL_RESULT_BYTES_PRESERVED": True,
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PROFILE_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def verify_result(result: Mapping[str, object], authority: Authority | None = None) -> None:
    if digest(result) != digest(compute_result(authority)):
        raise AssertionError("tampered immutable Bonferroni5 result")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify sealed JSON and exact bytes")
    args = parser.parse_args()
    result = compute_result()
    if args.verify:
        raw = RESULT_PATH.read_bytes()
        loaded = object_row(json.loads(raw))
        verify_result(loaded)
        if raw != integration.render(result).encode("utf-8"):
            raise AssertionError("immutable result byte replay differs")
    else:
        if RESULT_PATH.exists():
            raise AssertionError("immutable Bonferroni5 result already exists")
        with RESULT_PATH.open("x", encoding="utf-8") as out:
            out.write(integration.render(result))
    print(
        json.dumps(
            {
                "RESULT_REPLAY_STATUS": "PASS" if args.verify else "CREATED",
                **{k: result[k] for k in ("FINAL_COMPLETE_FAMILY_UB", "REMAINING_GAP")},
            }
        )
    )


if __name__ == "__main__":
    main()
