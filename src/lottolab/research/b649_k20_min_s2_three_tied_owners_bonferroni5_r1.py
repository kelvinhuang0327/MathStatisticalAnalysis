"""Three t=265 Bonferroni-5 certificates on the immutable complete Minimum-S2 ledger.

Reuse the independently proved S5=7*(sum_tau C(m_tau,2)+2*N_2T) identity
and its weight 28 for a double-triple K5. No new identity search is performed.
For d and g=6+d, m_tau<=4+min(d_v). The inherited threshold relaxation
bounds H_k by high incidences/3, the complement of a low vertex's triples,
and zero when fewer than three high vertices exist. The three sequences
give common-pair caps 736,788,788 and intersecting-triple-pair cap 133,
hence S5 caps 7014,7378,7378.

R30 GROUP_ATTEMPTS[2771,2770,2772] independently cap the three profiles
at 265. Only their t=265 terms change, using MIN(existing fourth-order,
S1-S2+S3-S4_floor+S5_cap). Credits are never summed. All t<=264 terms,
triangle caps, witnesses, the cursor and other rows retain their authority.
The complete 4844-profile partition and maximum are recomputed without
a solver, R30 census, or official-outcome enumeration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_two_owner_bonferroni5_certificate_r1 as previous
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
degree_s5_cap, moment_bounds = previous.degree_s5_cap, previous.moment_bounds
TASK_ID = "B649_K20_MIN_S2_THREE_TIED_OWNERS_BONFERRONI5_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-three-tied-owners-bonferroni5-r1"
BASE_HEAD = "d02d1ab940c51e14655bce2f5d1491f0b8d5ef79"
BASE_TREE = "699462b16688176762ad732477c245b558db1ca5"
BASE_RESULT_SHA256 = "69cd0dcd2efa45cec2e0fd4195cbdd92de67de46d0700c67a427518451a635d2"
OWNER_SOURCES = {
    "66555555555531000000": (1443, 2771),
    "66655555554441000000": (1215, 2770),
    "66655555555422000000": (1202, 2772),
}
CAP = 265
RESULT_FILENAME = "b649-k20-min-s2-three-tied-owners-bonferroni5-r1-result.json"
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
    family = integration.family(ledger, inherited.inherited.inherited.inherited.inherited)
    if family != sealed["FINAL_FAMILY"] or family["OWNER_IDS"] != sorted(OWNER_SOURCES):
        raise AssertionError("sealed complete family or tied owners differs")
    return Authority(
        inherited,
        ledger,
        sealed,
        inherited.r30,
        {**inherited.provenance, relative: hashlib.sha256(blob).hexdigest()},
    )


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
    previous.previous.previous.exact_terms(d, old, row.cap)
    *lower, last = old
    t, old_bound, _k, _a, s4, s3 = last
    if t != CAP or old_bound != row.bound or max(term[1] for term in old) != row.bound:
        raise AssertionError("load-bearing envelope differs from sealed ledger")
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
        common, n2 = previous.s5_counts(tuple(range(20)), edges, triples)
        s5 = previous.s5_identity_value(common, n2)
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
    sts = previous.previous.higher_order_sums(*split.witness_supports("STS13"))
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
        raise AssertionError("all three and only the targeted rows must change")
    family_auth = auth.inherited.inherited.inherited.inherited.inherited
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
        "BONFERRONI5": previous.bonferroni_check(),
        "OWNER_CERTIFICATES": certs,
        "START_FAMILY": start,
        "FINAL_FAMILY": family,
        "START_COMPLETE_FAMILY_UB": start["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": family["FAMILY_UB"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "REMAINING_GAP": family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - len(OWNER_SOURCES),
        "OTHER_ROWS_SHA256": digest(
            {pid: row.bound for pid, row in final.items() if pid not in OWNER_SOURCES}
        ),
        "INHERITED_CERTIFICATES": auth.sealed["INHERITED_CERTIFICATES"],
        "PREDECESSOR_OWNER_CERTIFICATES": auth.sealed["OWNER_CERTIFICATES"],
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
    if RESULT_PATH.exists():
        raise AssertionError("immutable Bonferroni5 result already exists")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as out:
        out.write(integration.render(result))
    print(json.dumps({k: result[k] for k in ("FINAL_COMPLETE_FAMILY_UB", "REMAINING_GAP")}))


if __name__ == "__main__":
    main()
