"""All-t Bonferroni-5 envelopes for the latest seven above-cursor Minimum-S2 rows.

The immutable predecessor is replayed before recovering the active rows. Its
two latest owner certificates are installed first; a stale nine-row selection
is rejected. Every legal t=22..cap uses its own committed/reconstructed S4
floor. In particular, the motif floor of 66666555555311100000 belongs only
to t=264. Its lower terms come directly from the sealed motif certificate;
neither monotonicity nor the cap term determines its envelope maximum.

For 22 pair-linear triple supports with degrees d and graph degrees 6+d,
m_tau <= 4+min(d_v). If H_k counts triples whose three degrees are >=k,
3H_k <= sum_{d>=k}d, H_k <= 22-d_v for each positive low-degree vertex,
and H_k=0 with fewer than three high vertices. Threshold telescoping bounds
sum_tau C(m_tau,2). Pair-linearity gives N_2T <= sum_v C(d_v,2).
The inherited independently proved identity is
S5=7*(sum_tau C(m_tau,2)+2*N_2T), with double-triple K5 weight 28.
These degree caps do not depend on t. Odd-order Bonferroni therefore gives
B5(t)=S1-S2+S3(t)-S4_used(t)+S5_cap for every legal t. Adopt only
min(existing_term(t), B5(t)), then take the maximum over the entire list.

All other resolved rows, prior certificates, legal witnesses, triangle-cap
authorities and the sealed cursor partition are preserved. The complete
4844-profile family maximum is recomputed from its ledger and cursor.
No solver, new census, portfolio search or official-outcome enumeration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from pathlib import Path

from . import b649_k20_min_s2_next_two_313395344_bonferroni5_r1 as previous
from .b649_k20_min_s2_split_cap_current_owner_chase_r1 import Authority as FamilyAuthority
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
identity, motif, nb = previous.identity, previous.motif, previous.nb
degree_s5_cap, moment_bounds = previous.degree_s5_cap, previous.moment_bounds
TASK_ID = "B649_K20_MIN_S2_ACTIVE_SEVEN_ALL_T_BONFERRONI5_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-active-seven-all-t-bonferroni5-r1"
BASE_HEAD = "8fa9c0e67f48aee7b8a51eb940eac565eeefecfe"
BASE_TREE = "28d983fdef72533e409b330b6481258046c8f3cd"
BASE_RESULT_SHA256 = "c653f07a0538b3f56601aaf9716a8e4b604b2212cc7257bb40e491180a90b34c"
ACTIVE_IDS = (
    "66555555555333000000",
    "66555555554442000000",
    "65555555555532000000",
    "66655555555421100000",
    "66655555555332000000",
    "66666555555311100000",
    "66555555555431100000",
)
NB_SOURCES = {
    "66555555555333000000": 1453,
    "66555555554442000000": 1465,
    "65555555555532000000": 1615,
    "66655555555421100000": 1203,
    "66655555555332000000": 1205,
    "66555555555431100000": 1449,
}
MIXED_PROFILE = integration.T264_PROFILE
RESULT_FILENAME = "b649-k20-min-s2-active-seven-all-t-bonferroni5-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME
type Term = tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class Authority:
    inherited: previous.Authority
    ledger: Ledger
    sealed: dict[str, object]
    family_authority: FamilyAuthority
    provenance: dict[str, str]


def active_profiles(ledger: Mapping[str, Row]) -> list[str]:
    recovered = sorted(pid for pid, row in ledger.items() if row.bound > chase.prior.CURSOR_BOUND)
    if recovered != sorted(ACTIVE_IDS):
        raise AssertionError("latest seven above-cursor profiles differ; stale selection rejected")
    return recovered


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
    if digest(previous.compute_result(inherited)) != digest(sealed):
        raise AssertionError("sealed predecessor replay differs")
    ledger = dict(inherited.ledger)
    for pid in previous.PROFILE_SOURCES:
        cert = object_row(object_row(sealed["PROFILE_CERTIFICATES"])[pid])
        ledger = integration.install(
            ledger,
            pid,
            integer(cert["CERTIFIED_PROFILE_BOUND"]),
            f"{previous.RESULT_FILENAME}:PROFILE_CERTIFICATES[{pid}]",
        )
    chain = inherited.inherited.inherited.inherited
    family_authority = chain.inherited.inherited.inherited.inherited.inherited.inherited
    family = integration.family(ledger, family_authority)
    if family != sealed["FINAL_FAMILY"] or family["FAMILY_UB"] != 313395164:
        raise AssertionError("sealed complete family differs")
    active_profiles(ledger)
    return Authority(
        inherited,
        ledger,
        sealed,
        family_authority,
        {**inherited.provenance, relative: hashlib.sha256(blob).hexdigest()},
    )


def authoritative_terms(auth: Authority, pid: str) -> list[Term]:
    """Use replayed NB terms or the actual sealed mixed-floor motif terms."""
    if pid not in ACTIVE_IDS:
        raise AssertionError("profile outside active seven")
    row = auth.ledger[pid]
    baseline = split.route_b_terms(split.profile_values(pid), row.cap, row.s4_base)
    if pid == MIXED_PROFILE:
        cert = object_row(
            object_row(auth.sealed["INHERITED_CERTIFICATES"])["T264_OWNER_CERTIFICATE"]
        )
        old = [tuple(map(integer, rows(raw))) for raw in rows(cert["ALL_T_TERMS"])]
        # Preserve all lower-t fields; the motif certificate changes only its cap term.
        if (
            row.source != integration.T264_LOCATOR
            or cert["PROFILE_ID"] != pid
            or cert["TRIANGLE_CAP"] != row.cap
            or cert["S4_BASE"] != row.s4_base
            or old[:-1] != baseline[:-1]
            or old[-1][4] != cert["NEW_S4_FLOOR"]
        ):
            raise AssertionError("mixed motif S4 floor scope differs")
    else:
        if (
            row.source != f"{nb.RESULT_FILENAME}:NB_CERTIFICATES[{NB_SOURCES[pid]}]"
            or row.s4_base != nb.r28.profile_s4_floor(split.profile_values(pid))
        ):
            raise AssertionError("immutable NB cap-source identity differs")
        old = baseline
    identity.previous.previous.exact_terms(split.profile_values(pid), old, row.cap)
    if any(len(term) != 6 for term in old) or max(term[1] for term in old) != row.bound:
        raise AssertionError("authoritative per-t envelope differs from latest ledger")
    return [(t, b, k, a, s4, s3) for t, b, k, a, s4, s3 in old]


def profile_certificate(auth: Authority, pid: str) -> dict[str, object]:
    row = auth.ledger[pid]
    old = authoritative_terms(auth, pid)
    cap = degree_s5_cap(pid)
    s5 = integer(cap["S5_CAP"])
    terms: list[Term] = []
    fifth_terms: list[list[int]] = []
    changed: list[list[object]] = []
    for t, old_bound, k, a, s4, s3 in old:
        fourth, fifth = moment_bounds(s3, s4, s5)
        if fourth != old_bound:
            raise AssertionError("existing authoritative fourth-order term differs")
        bound = min(old_bound, fifth)
        terms.append((t, bound, k, a, s4, s3))
        fifth_terms.append([t, fifth])
        if bound != old_bound:
            changed.append([t, "BOUND"])
    maximum = max(term[1] for term in terms)
    return {
        "STATUS": "PASS",
        "PROFILE_ID": pid,
        "TRIANGLE_CAP": row.cap,
        "CAP_SOURCE": row.source,
        "S4_BASE": row.s4_base,
        "AUTHORITATIVE_TERMS_SHA256": digest(old),
        "AUTHORITATIVE_TERMS": [list(term) for term in old],
        "DEGREE_S5_PROOF": cap,
        "S5_SCOPE": "EVERY_LEGAL_T_DEGREE_ONLY",
        "S4_SCOPE": "AUTHORITATIVE_PER_TERM; MOTIF_FLOOR_ONLY_AT_T264",
        "BOUND_RULE": "MIN(EXISTING_TERM, BONFERRONI5); NEVER ADD CREDITS",
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "ALL_T_TERMS": [list(term) for term in terms],
        "BONFERRONI5_TERMS": fifth_terms,
        "LEGAL_T_COUNT": len(terms),
        "CHANGED_TERM_FIELDS": changed,
        "CHANGED_T_TERM_COUNT": len(changed),
        "OLD_PROFILE_BOUND": row.bound,
        "CERTIFIED_PROFILE_BOUND": maximum,
        "ARGMAX_T": [term[0] for term in terms if term[1] == maximum],
        "CAP_T_NEW_BOUND": terms[-1][1],
        "ALL_T_RECOMPUTATION_STATUS": "PASS_EXACT_INTEGER_AND_RATIONAL",
    }


def verify_certificate(cert: Mapping[str, object], auth: Authority, pid: str) -> None:
    if digest(cert) != digest(profile_certificate(auth, pid)):
        raise AssertionError("tampered all-t Bonferroni5 certificate")


def witness_soundness(ledger: Mapping[str, Row], certs: Mapping[str, object]) -> dict[str, object]:
    named = {pid: row.realization for pid, row in ledger.items() if row.realization is not None}
    named.update({kind: split.witness_supports(kind) for kind in ("P2", "STS13")})
    checks: dict[str, object] = {}
    for name, supports in named.items():
        triples, pairs = supports
        seen = motif.realization_check(triples, pairs)
        pid = integration.text(seen["PROFILE_ID"])
        if name in ledger and pid != name:
            raise AssertionError("recorded witness profile differs")
        d = tuple(sum(v in tau for tau in triples) for v in range(20))
        edges = {e for tau in triples for e in combinations(tau, 2)} | set(pairs)
        common, n2 = identity.s5_counts(tuple(range(20)), edges, triples)
        s5 = identity.s5_identity_value(common, n2)
        cap = degree_s5_cap(d)
        t = integer(seen["TRIANGLES"])
        s4 = integer(seen["EXACT_S4_FROM_PINNED_LOCAL_TABLE"])
        if s5 > integer(cap["S5_CAP"]) or (pid in ledger and t > ledger[pid].cap):
            raise AssertionError("degree cap or triangle cap excludes legal witness")
        s3, _ = chase.r20.bound_from_cap(split.profile_values(d), t, s4)
        witness_bound = min(moment_bounds(s3, s4, s5))
        if pid in certs:
            cert = object_row(certs[pid])
            terms = {integer(rows(raw)[0]): rows(raw) for raw in rows(cert["ALL_T_TERMS"])}
            if (
                t not in terms
                or s4 < integer(terms[t][4])
                or witness_bound > integer(terms[t][1])
                or witness_bound > integer(cert["CERTIFIED_PROFILE_BOUND"])
            ):
                raise AssertionError("all-t bound excludes legal witness")
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
            for pid in ACTIVE_IDS
        },
        "STS13_EXACT_UNION": sts,
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    recovered = active_profiles(auth.ledger)
    certs: dict[str, object] = {}
    final = dict(auth.ledger)
    for pid in recovered:
        cert = profile_certificate(auth, pid)
        verify_certificate(cert, auth, pid)
        certs[pid] = cert
        final = integration.install(
            final,
            pid,
            integer(cert["CERTIFIED_PROFILE_BOUND"]),
            f"{RESULT_FILENAME}:PROFILE_CERTIFICATES[{pid}]",
        )
    if {pid for pid in final if final[pid] != auth.ledger[pid]} != set(recovered):
        raise AssertionError("only active seven rows must change")
    start = integration.family(auth.ledger, auth.family_authority)
    family = integration.family(final, auth.family_authority)
    if any(start[key] != family[key] for key in ("CURSOR_ID", "CURSOR_BOUND", "COVERAGE")):
        raise AssertionError("cursor authority or coverage changed")
    soundness = witness_soundness(final, certs)
    preserved_keys = (
        "INHERITED_CERTIFICATES",
        "PRESERVED_COMPETING_PROFILE_CERTIFICATES",
        "PRESERVED_OWNER_CERTIFICATE",
        "PREDECESSOR_OWNER_CERTIFICATES",
        "EARLIER_OWNER_CERTIFICATES",
        "OLDER_OWNER_CERTIFICATES",
        "STS13_CERTIFICATE_SHA256",
    )
    mixed = object_row(certs[MIXED_PROFILE])
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
        "BONFERRONI5": identity.bonferroni_check(),
        "S5_ALL_T_PROOF_STATUS": "PASS_DEGREE_CAP_INDEPENDENT_OF_T",
        "MIXED_S4_MOTIF_STATUS": "PASS_AUTHORITATIVE_FLOOR_PER_T_NO_MONOTONICITY_SHORTCUT",
        "MIXED_PROFILE_ARGMAX_T": mixed["ARGMAX_T"],
        "MIXED_PROFILE_CAP_T_BOUND": mixed["CAP_T_NEW_BOUND"],
        "ACTIVE_SEVEN_PROFILE_IDS": recovered,
        "ACTIVE_PROFILE_COVERAGE": "PASS_EXACT_LATEST_SEVEN",
        "PROFILE_CERTIFICATES": certs,
        "CHANGED_T_TERM_COUNT": sum(
            integer(object_row(cert)["CHANGED_T_TERM_COUNT"]) for cert in certs.values()
        ),
        "SEVEN_NEW_PROFILE_BOUNDS": {
            pid: object_row(cert)["CERTIFIED_PROFILE_BOUND"] for pid, cert in certs.items()
        },
        "ALL_LEGAL_T_TERM_COUNT": sum(
            integer(object_row(cert)["LEGAL_T_COUNT"]) for cert in certs.values()
        ),
        "START_FAMILY": start,
        "FINAL_FAMILY": family,
        "START_COMPLETE_FAMILY_UB": start["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": family["FAMILY_UB"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "REMAINING_GAP": family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - len(recovered),
        "OTHER_ROWS_FULL_SHA256": digest(
            [
                [pid, row.bound, row.cap, row.s4_base, row.source, row.realization]
                for pid, row in sorted(final.items())
                if pid not in recovered
            ]
        ),
        **{key: auth.sealed[key] for key in preserved_keys},
        "PRIOR_OWNER_CERTIFICATES": auth.sealed["PROFILE_CERTIFICATES"],
        "PRIOR_OWNER_CERTIFICATES_STATUS": "PASS_PRESERVED_COMMITTED_LOWER_BOUNDS",
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
        raise AssertionError("tampered immutable all-t Bonferroni5 result")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify sealed JSON and exact bytes")
    args = parser.parse_args()
    result = compute_result()
    if args.verify:
        raw = RESULT_PATH.read_bytes()
        verify_result(object_row(json.loads(raw)))
        if raw != integration.render(result).encode("utf-8"):
            raise AssertionError("immutable result byte replay differs")
    else:
        if RESULT_PATH.exists():
            raise AssertionError("immutable all-t Bonferroni5 result already exists")
        with RESULT_PATH.open("x", encoding="utf-8") as out:
            out.write(integration.render(result))
    print(
        json.dumps(
            {
                "RESULT_REPLAY_STATUS": "PASS" if args.verify else "CREATED",
                **{
                    key: result[key]
                    for key in ("FINAL_COMPLETE_FAMILY_UB", "REMAINING_GAP", "CHANGED_T_TERM_COUNT")
                },
            }
        )
    )


if __name__ == "__main__":
    main()
