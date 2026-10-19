"""One exact quartet-incidence refinement of the sealed d7082c9d family.

Minimum-S2 has 22 triple and 27 pair labels, six labels per ticket, and pair
linearity. For triple degrees d, graph degrees g=6+d. K/D/P/C count induced
K4/diamond/paw/claw quartets; A/D1/P1 count those containing a triple support.
The pinned primitive proves J=4K+2D+P+C, R=2D+2P+3C, B=3A+2D1+P1 and
S4=231K+112J-56R-77B+42D1+77P1+56C. J=sum C(g,3), B=sum d(g-2).
OW=W-3t, R<=Rmax=(max(g)-2)OW and K>=ceil((J-Rmax)/4).
Dropping nonnegative terms gives the committed degree floor. Substituting
B=3A+2D1+P1 gives the committed equivalent incidence identity
S4=231K-63A+56(2J-R-B)+56(P1+C), with A<=floor(B/3).
Its floor is stronger by 21*(B mod 3); take the maximum, never add floors.

Only owner 66666555554411100000 at t=264 changes. Its R30 refutation is
GROUP_ATTEMPTS[2779]. S4 rises from 286279 to 309183, giving integer credit
13088. The cap term becomes 313387988; retained t=263 gives 313391920.
The next competitor's sealed STS13 floor 331240 exceeds incidence 328510,
so it survives verbatim. Replay all 4647 resolved rows plus the cursor under
the inherited 4844-profile coverage. No solver or outcome enumeration runs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path

from . import b649_k20_min_s2_next_owners_and_loader_correction_r1 as previous
from . import b649_k20_min_s2_owner_66655555555440000000_motif_r1 as motif
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase
from . import b649_k20_min_s2_three_motif_complete_family_integration_r1 as integration
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split

integer, object_row, rows, digest = (
    previous.integer,
    previous.object_row,
    previous.rows,
    previous.digest,
)
TASK_ID = "B649_K20_MIN_S2_CURRENT_OWNER_MOTIF_EXACT_REFINEMENT_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-current-owner-motif-exact-refinement-r1"
BASE_HEAD = "d7082c9dee1b0dfe6136b5b9067ae1ca3d55986a"
BASE_TREE = "e8616d7d5f0ee3280176e85d03de14c43a38685b"
BASE_RESULT_SHA256 = "bcd000ee934e218b96093d6fedb41168518f625ec9838397e53e92615dc0f806"
OWNER_PROFILE = "66666555554411100000"
COMPETITOR_PROFILE = integration.STS13_PROFILE
CAP, CAP_INDEX, LEDGER_INDEX = 264, 2779, 497
RESULT_FILENAME = "b649-k20-min-s2-current-owner-motif-exact-refinement-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME


@dataclass(frozen=True)
class Authority:
    inherited: previous.Authority
    ledger: integration.Ledger
    sealed: dict[str, object]
    provenance: dict[str, str]


@cache
def load_authority() -> Authority:
    """Replay the pinned predecessor and adopt its two already sealed refinements."""
    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    sealed = integration.pinned(BASE_HEAD, previous.RESULT_FILENAME, BASE_RESULT_SHA256)
    provenance = previous.corrected_provenance()
    path = Path(previous.__file__ or "").resolve()
    relative = f"src/lottolab/research/{previous.__name__.rsplit('.', 1)[-1]}.py"
    blob = chase.git("show", f"{BASE_HEAD}:{relative}")
    if (
        path != (chase.ROOT / relative).resolve()
        or path.read_bytes() != blob
        or hashlib.sha256(blob).hexdigest() != sealed["SOURCE_SHA256"]
        or provenance != sealed["MODULE_PROVENANCE"]
    ):
        raise AssertionError("predecessor source identity mismatch")
    provenance = {**provenance, relative: hashlib.sha256(blob).hexdigest()}
    inherited = previous.load_authority()
    replay = previous.compute_result(inherited)
    if digest(replay) != digest(sealed):
        raise AssertionError("sealed predecessor replay differs")
    ledger = dict(inherited.ledger)
    for pid, raw in object_row(sealed["OWNER_CERTIFICATES"]).items():
        cert = object_row(raw)
        ledger = integration.install(
            ledger,
            pid,
            integer(cert["CERTIFIED_PROFILE_BOUND"]),
            f"{previous.RESULT_FILENAME}:OWNER_CERTIFICATES[{pid}]",
        )
    family = integration.family(ledger, inherited.inherited)
    if family != sealed["FINAL_FAMILY"] or family["OWNER_IDS"] != [OWNER_PROFILE]:
        raise AssertionError("sealed complete-family owner mismatch")
    return Authority(inherited, ledger, sealed, provenance)


def check_cap(row: chase.Row, proof: Mapping[str, object]) -> None:
    profile = split.profile_values(OWNER_PROFILE)
    w = motif.degree_floor(profile, CAP)["W"]
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": CAP_INDEX,
        "PROFILE_IDS": [OWNER_PROFILE],
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
        or row.source != f"{chase.prior.nb.RESULT_FILENAME}:NB_CERTIFICATES[{LEDGER_INDEX}]"
        or any(digest(proof.get(k)) != digest(v) for k, v in expected.items())
        or integration.r32.r28.r26.accepted_cap(proof, (profile,), CAP) != CAP
    ):
        raise AssertionError("current owner cap-source identity mismatch")


def exact_terms(profile: split.Profile, terms: Sequence[Sequence[object]], cap: int) -> None:
    """Check every retained and changed t using rational and integer expressions."""
    if [integer(term[0]) for term in terms] != list(range(22, cap + 1)):
        raise AssertionError("all-t coverage changed")
    for term in terms:
        t, bound, _k, _a, s4, s3 = term
        checked_s3, rounded = chase.r20.bound_from_cap(profile, integer(t), integer(s4))
        exact = motif.event.K20_S1 - motif.event.K20_S2 + integer(s3) - Fraction(4 * integer(s4), 7)
        if s3 != checked_s3 or bound != rounded or not 0 <= rounded - exact < 1:
            raise AssertionError("all-t rational/integer equivalence failed")


def owner_certificate(row: chase.Row, proof: Mapping[str, object]) -> dict[str, object]:
    check_cap(row, proof)
    p = split.profile_values(OWNER_PROFILE)
    old = split.route_b_terms(p, row.cap, row.s4_base)
    *lower, last = old
    t, old_bound, _old_k, _old_a, old_s4, s3 = last
    if t != CAP or old_bound != row.bound or max(term[1] for term in old) != row.bound:
        raise AssertionError("load-bearing owner envelope differs from sealed ledger")
    degree, incidence = motif.degree_floor(p, t), integration.incidence_floor(p, t)
    if incidence["S4_FLOOR"] != degree["S4_CERTIFIED_FLOOR"] + 21 * (degree["B"] % 3):
        raise AssertionError("committed incidence/degree floor equivalence failed")
    s4 = max(old_s4, degree["S4_CERTIFIED_FLOOR"], incidence["S4_FLOOR"])
    _s3, bound = chase.r20.bound_from_cap(p, t, s4)
    terms = [*lower, (t, bound, incidence["K4_FLOOR"], incidence["A_MAX"], s4, s3)]
    exact_terms(p, terms, row.cap)
    return {
        "PROFILE_ID": OWNER_PROFILE,
        "MINIMUM_S2_PREMISES": {
            "TRIPLE_LABELS": 22,
            "PAIR_LABELS": 27,
            "TICKET_CAPACITY": 6,
            "PAIR_LINEARITY": True,
            "AUTHORITY": "PINNED_COMPLETE_LEDGER_AND_VALIDATED_OWNER_SUPPORT_REALIZATION",
        },
        "D": list(p),
        "G": [6 + d for d in p],
        "TRIANGLE_CAP": CAP,
        "LOAD_BEARING_T": t,
        "CAP_SOURCE": f"{integration.r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS[{CAP_INDEX}]",
        "CAP_SOURCE_IDENTITY": dict(proof),
        "EXISTING_LEDGER_SOURCE": row.source,
        "DEGREE_FLOOR": degree,
        "INCIDENCE_FLOOR": incidence,
        "S4_BASE": row.s4_base,
        "OLD_PROFILE_BOUND": row.bound,
        "OLD_ROUTE_B_S4_FLOOR": old_s4,
        "NEW_S4_FLOOR": s4,
        "S4_RULE": "MAX(EXISTING, DEGREE, INCIDENCE); NEVER ADD OVERLAPPING FLOORS",
        "OLD_INTEGER_CREDIT": 4 * old_s4 // 7,
        "NEW_INTEGER_CREDIT": 4 * s4 // 7,
        "EXACT_ADDITIONAL_CREDIT": 4 * s4 // 7 - 4 * old_s4 // 7,
        "CAP_OLD_BOUND": old_bound,
        "CAP_NEW_BOUND": bound,
        "RETAINED_LOWER_T_COUNT": len(lower),
        "RETAINED_LOWER_T_MAX": max(term[1] for term in lower),
        "RETAINED_TERMS_SHA256": digest(lower),
        "ALL_T_TERMS": [list(term) for term in terms],
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "CERTIFIED_PROFILE_BOUND": max(term[1] for term in terms),
        "STATUS": "PASS",
    }


def verify_certificate(
    cert: Mapping[str, object], row: chase.Row, proof: Mapping[str, object]
) -> None:
    if digest(cert) != digest(owner_certificate(row, proof)):
        raise AssertionError("tampered current owner certificate")


def competitor_check(auth: Authority) -> dict[str, object]:
    """Retain the stronger STS13 certificate, including every one of its t terms."""
    row = auth.ledger[COMPETITOR_PROFILE]
    donor = integration.pinned(
        integration.STS13_DONOR_HEAD,
        integration.STS13_RESULT_FILENAME,
        integration.STS13_DONOR_RESULT_SHA256,
    )
    cert = object_row(donor["STS13_T270_CERTIFICATE"])
    adopt = object_row(cert["ADOPTION"])
    terms = [rows(term) for term in rows(adopt["ALL_T_TERMS"])]
    p = split.profile_values(COMPETITOR_PROFILE)
    exact_terms(p, terms, row.cap)
    existing, t = integer(adopt["EXACT_S4"]), integer(cert["LOAD_BEARING_T"])
    degree, incidence = motif.degree_floor(p, t), integration.incidence_floor(p, t)
    if (
        row.source != integration.STS13_LOCATOR
        or row.cap != t
        or row.bound != adopt["FULL_PROFILE_BOUND"]
        or row.bound != max(integer(term[1]) for term in terms)
        or terms[-1][4] != existing
        or max(existing, degree["S4_CERTIFIED_FLOOR"], incidence["S4_FLOOR"]) != existing
    ):
        raise AssertionError("stronger existing competitor certificate was not preserved")
    return {
        "PROFILE_ID": COMPETITOR_PROFILE,
        "CAP_SOURCE": row.source,
        "TRIANGLE_CAP": t,
        "EXISTING_S4_FLOOR": existing,
        "DEGREE_FLOOR": degree,
        "INCIDENCE_FLOOR": incidence,
        "ADOPTED_S4_FLOOR": existing,
        "CERTIFIED_PROFILE_BOUND": row.bound,
        "EXACT_ADDITIONAL_CREDIT": 0,
        "SEALED_ALL_T_TERMS_SHA256": digest(terms),
        "DONOR_CERTIFICATE_SHA256": digest(cert),
        "STATUS": "PRESERVED_STRONGER_SEALED_CERTIFICATE",
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    proof = object_row(rows(auth.inherited.r30["GROUP_ATTEMPTS"])[CAP_INDEX])
    cert = owner_certificate(auth.ledger[OWNER_PROFILE], proof)
    verify_certificate(cert, auth.ledger[OWNER_PROFILE], proof)
    competitor = competitor_check(auth)
    final = integration.install(
        auth.ledger,
        OWNER_PROFILE,
        integer(cert["CERTIFIED_PROFILE_BOUND"]),
        f"{RESULT_FILENAME}:OWNER_CERTIFICATE",
    )
    if {pid for pid in final if final[pid] != auth.ledger[pid]} != {OWNER_PROFILE}:
        raise AssertionError("only the current owner row may change")
    start, family = (
        integration.family(auth.ledger, auth.inherited.inherited),
        integration.family(final, auth.inherited.inherited),
    )
    witness = auth.ledger[OWNER_PROFILE].realization
    if witness is None:
        raise AssertionError("current owner label-support realization missing")
    seen = motif.realization_check(*witness)
    if seen["PROFILE_ID"] != OWNER_PROFILE or integer(seen["TRIANGLES"]) > CAP:
        raise AssertionError("owner support applicability mismatch")
    inherited_certs = object_row(auth.sealed["INHERITED_CERTIFICATES"])
    soundness = integration.soundness(
        final, auth.inherited.r30, object_row(inherited_certs["STS13_CERTIFICATE"])
    )
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
        "HISTORICAL_RESULT_BYTES_PRESERVED": True,
        "INCIDENCE_IDENTITY": motif.local_identity_check(),
        "EQUIVALENT_INCIDENCE_IDENTITY": integration.incidence_identity_check(),
        "OWNER_CERTIFICATE": cert,
        "IMMEDIATE_COMPETITOR": competitor,
        "OWNER_SUPPORT_REALIZATION": seen,
        "INHERITED_CERTIFICATES": inherited_certs,
        "START_FAMILY": start,
        "FINAL_FAMILY": family,
        "START_COMPLETE_FAMILY_UB": start["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": family["FAMILY_UB"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "CURRENT_INCUMBENT": chase.INCUMBENT,
        "REMAINING_GAP": family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - 1,
        "OTHER_ROWS_SHA256": digest(
            {pid: r.bound for pid, r in final.items() if pid != OWNER_PROFILE}
        ),
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "WITNESS_SOUNDNESS": soundness,
        "WITNESS_SOUNDNESS_STATUS": soundness["STATUS"],
        "DOUBLE_COUNT_STATUS": "PASS_ONE_PROFILE_ONE_CAP_TERM_MAX_NOT_SUM",
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
        raise AssertionError("tampered immutable current-owner result")


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("immutable current-owner result already exists")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as out:
        out.write(integration.render(result))
    print(json.dumps({k: result[k] for k in ("FINAL_COMPLETE_FAMILY_UB", "REMAINING_GAP")}))


if __name__ == "__main__":
    main()
