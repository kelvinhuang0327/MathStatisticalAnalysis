"""Two cap-term quartet-incidence certificates on the sealed a5eb5081 family.

Reuse S4 = 231K - 63A + 56(2U-L-R) + 56(P1+C), with nonnegative slack,
K>=ceil((U-L_max)/4), A<=floor(R/3), L_max=(max g-2)(W-3t).
The pinned R30 cap refutations select t=264 and t=265 respectively. At each
cap replace the Route-B S4 floor by its maximum with this incidence floor.
Keep every lower-t term and every other profile unchanged; recompute the
complete resolved ledger plus cursor, with its inherited 4,844-profile partition.

Historical result bytes remain immutable. Only the owner loader's explicit
27-source boundary and the integration's pin for that corrected source change.
Their new source identities are checked separately from the historical bytes.
No solver, outcome enumeration, portfolio search or special floor branch runs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path

from . import b649_k20_min_s2_owner_66655555555440000000_motif_r1 as motif
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase
from . import b649_k20_min_s2_three_motif_complete_family_integration_r1 as previous
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split

integer, object_row, rows, digest = (
    previous.integer,
    previous.object_row,
    previous.rows,
    previous.digest,
)
TASK_ID = "B649_K20_MIN_S2_NEXT_OWNERS_AND_LOADER_CORRECTION_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-next-owners-and-loader-correction-r1"
BASE_HEAD = "a5eb5081180dd9cbe1745b0f2577cd18eb76a90b"
BASE_TREE = "4f327f76d24ed4b292b1a02bd08cf40c9a4ec7fe"
BASE_RESULT_SHA256 = "b1997251940fea63ca10c8e26e08a66dfdb76c18164d39c13d4a475e4e74a917"
CORRECTED_SOURCE_SHA256 = {
    "b649_k20_min_s2_owner_66655555555440000000_motif_r1": (
        "33ba11cddd498f55019d708901e1a387316e23eecd4a9c3613dfd72268e56234"
    ),
    "b649_k20_min_s2_three_motif_complete_family_integration_r1": (
        "7aacb00b3c9ff247c9cdb2d00faacd5ea2a84f3535b3e595b3bccfd5dbb91178"
    ),
}
# Only profile/cap/source identities are inputs; all floors and bounds are derived.
OWNER_SOURCES = {
    "66665555555421000000": (264, 2781, "NB_CERTIFICATES[870]"),
    "66665555554422000000": (265, 2497, "NB_CERTIFICATES[882]"),
}
RESULT_FILENAME = "b649-k20-min-s2-next-owners-and-loader-correction-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME


def corrected_provenance() -> dict[str, str]:
    """The corrected sources have explicit new pins; historical sources keep old pins."""
    out = motif.historical_provenance()
    for module in (motif, previous):
        name = module.__name__.rsplit(".", 1)[-1]
        relative = f"src/lottolab/research/{name}.py"
        if module.__file__ is None:
            raise AssertionError("corrected module has no source")
        path = Path(module.__file__).resolve()
        if path != (chase.ROOT / relative).resolve():
            raise AssertionError("corrected source identity mismatch")
        expected = CORRECTED_SOURCE_SHA256[name]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise AssertionError(f"corrected source digest mismatch: {name}")
        out[relative] = expected
    return out


def check_base_result(sealed: Mapping[str, object], replay: Mapping[str, object]) -> None:
    """Only the two changed source identities may differ from the sealed base result."""
    old_sources = object_row(sealed["MODULE_PROVENANCE"])
    new_sources = object_row(replay["MODULE_PROVENANCE"])
    owner_path = f"src/lottolab/research/{motif.__name__.rsplit('.', 1)[-1]}.py"
    integration_path = f"src/lottolab/research/{previous.__name__.rsplit('.', 1)[-1]}.py"
    if (
        old_sources[owner_path]
        != hashlib.sha256(chase.git("show", f"{BASE_HEAD}:{owner_path}")).hexdigest()
        or sealed["SOURCE_SHA256"]
        != hashlib.sha256(chase.git("show", f"{BASE_HEAD}:{integration_path}")).hexdigest()
        or new_sources != {**old_sources, owner_path: previous.MOTIF_SOURCE_SHA256}
        or replay["SOURCE_SHA256"]
        != CORRECTED_SOURCE_SHA256[integration_path.rsplit("/", 1)[-1][:-3]]
        or digest(
            {**sealed, "MODULE_PROVENANCE": new_sources, "SOURCE_SHA256": replay["SOURCE_SHA256"]}
        )
        != digest(replay)
    ):
        raise AssertionError("sealed base result replay or source identities differ")


@dataclass(frozen=True)
class Authority:
    inherited: chase.Authority
    ledger: previous.Ledger
    sealed: dict[str, object]
    r30: dict[str, object]
    provenance: dict[str, str]


@cache
def load_authority() -> Authority:
    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    provenance = corrected_provenance()
    sealed = previous.pinned(BASE_HEAD, previous.RESULT_FILENAME, BASE_RESULT_SHA256)
    inherited = chase.load_authority()
    replay = previous.compute_result(inherited)
    check_base_result(sealed, replay)
    ledger = previous.chase_ledger(
        inherited, motif.pinned_result(chase.RESULT_FILENAME, previous.CHASE_RESULT_SHA256)
    )
    for pid, key, locator in (
        (previous.T264_PROFILE, "T264_OWNER_CERTIFICATE", previous.T264_LOCATOR),
        (previous.STS13_PROFILE, "STS13_CERTIFICATE", previous.STS13_LOCATOR),
        (previous.OWNER_PROFILE, "OWNER_MOTIF_CERTIFICATE", previous.OWNER_LOCATOR),
    ):
        cert = object_row(replay[key])
        ledger = previous.install(ledger, pid, integer(cert["CERTIFIED_PROFILE_BOUND"]), locator)
    if previous.family(ledger, inherited) != sealed["FINAL_FAMILY"]:
        raise AssertionError("complete base ledger does not match sealed family")
    r30 = motif.pinned_result(previous.r32.CAP_SOURCE_RESULT, previous.r32.R30_SHA256)
    return Authority(inherited, ledger, sealed, r30, provenance)


def check_cap(pid: str, row: chase.Row, proof: Mapping[str, object]) -> None:
    cap, index, source_row = OWNER_SOURCES[pid]
    profile = split.profile_values(pid)
    w = previous.incidence_floor(profile, cap)["W"]
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": index,
        "PROFILE_IDS": [pid],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "ROUTE": previous.r32.CAP_SOURCE_ROUTE,
        "WEDGE_COUNT": w,
        "TARGET_TRIANGLE_CAP": cap,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap,
        "OPEN_WEDGE_CEILING_REFUTED": w - 3 * (cap + 1),
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": w - 3 * (cap + 1) + 1,
    }
    if (
        type(row.cap) is not int
        or row.cap != cap
        or row.source != f"{chase.prior.nb.RESULT_FILENAME}:{source_row}"
        or any(digest(proof.get(k)) != digest(v) for k, v in expected.items())
    ):
        raise AssertionError("owner cap-source identity mismatch")
    if previous.r32.r28.r26.accepted_cap(proof, (profile,), cap) != cap:
        raise AssertionError("owner cap-source refutation not accepted")


def owner_certificate(pid: str, row: chase.Row, proof: Mapping[str, object]) -> dict[str, object]:
    check_cap(pid, row, proof)
    profile = split.profile_values(pid)
    old = split.route_b_terms(profile, row.cap, row.s4_base)
    *lower, last = old
    t, old_bound, _old_k, _old_a, old_s4, s3 = last
    if t != row.cap or max(term[1] for term in old) != row.bound:
        raise AssertionError("owner envelope does not reproduce sealed ledger")
    floor = previous.incidence_floor(profile, t)
    s4 = max(old_s4, floor["S4_FLOOR"])
    checked_s3, bound = chase.r20.bound_from_cap(profile, t, s4)
    exact = motif.event.K20_S1 - motif.event.K20_S2 + s3 - Fraction(4 * s4, 7)
    if checked_s3 != s3 or not 0 <= bound - exact < 1:
        raise AssertionError("cap-term exact integer envelope mismatch")
    terms = [*lower, (t, bound, floor["K4_FLOOR"], floor["A_MAX"], s4, s3)]
    return {
        "PROFILE_ID": pid,
        "TRIANGLE_CAP": t,
        "CAP_SOURCE": f"{previous.r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS[{OWNER_SOURCES[pid][1]}]",
        "CAP_SOURCE_IDENTITY": dict(proof),
        "EXISTING_LEDGER_SOURCE": row.source,
        "S4_BASE": row.s4_base,
        "INCIDENCE_FLOOR": floor,
        "OLD_PROFILE_BOUND": row.bound,
        "OLD_ROUTE_B_S4_FLOOR": old_s4,
        "NEW_S4_FLOOR": s4,
        "S4_RULE": "MAX(OLD_ROUTE_B_S4_FLOOR, INCIDENCE_S4_FLOOR); CREDITS NEVER ADDED",
        "CREDIT_GAIN": 4 * s4 // 7 - 4 * old_s4 // 7,
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
    if digest(cert) != digest(owner_certificate(previous.text(cert["PROFILE_ID"]), row, proof)):
        raise AssertionError("tampered owner certificate")


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    certificates = {
        pid: owner_certificate(
            pid, auth.ledger[pid], object_row(rows(auth.r30["GROUP_ATTEMPTS"])[index])
        )
        for pid, (_cap, index, _source) in OWNER_SOURCES.items()
    }
    final, transitions = previous.transitions(
        auth.ledger,
        [
            (
                pid,
                integer(cert["CERTIFIED_PROFILE_BOUND"]),
                f"{RESULT_FILENAME}:OWNER_CERTIFICATES[{pid}]",
            )
            for pid, cert in certificates.items()
        ],
    )
    if {pid for pid in final if final[pid] != auth.ledger[pid]} != set(OWNER_SOURCES):
        raise AssertionError("only the two specified owner rows may change")
    for pid, cert in certificates.items():
        proof = object_row(cert["CAP_SOURCE_IDENTITY"])
        verify_certificate(cert, auth.ledger[pid], proof)
    start_family, final_family = (
        previous.family(auth.ledger, auth.inherited),
        previous.family(final, auth.inherited),
    )
    checks = previous.soundness(final, auth.r30, object_row(auth.sealed["STS13_CERTIFICATE"]))
    owner_checks: dict[str, object] = {}
    for pid in OWNER_SOURCES:
        witness = final[pid].realization
        if witness is None:
            owner_checks[pid] = {"STATUS": "NO_RECORDED_REALIZATION_IN_INHERITED_LEDGER"}
            continue
        seen = motif.realization_check(*witness)
        t = integer(seen["TRIANGLES"])
        floor = previous.incidence_floor(split.profile_values(pid), t)
        if (
            t > final[pid].cap
            or integer(seen["EXACT_S4_FROM_PINNED_LOCAL_TABLE"]) < floor["S4_FLOOR"]
        ):
            raise AssertionError("owner incidence floor excludes a legal realization")
        owner_checks[pid] = seen
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
        "HISTORICAL_RESULT_BYTES_PRESERVED": True,
        "PROOF": __doc__,
        "INCIDENCE_IDENTITY": previous.incidence_identity_check(),
        "INHERITED_CERTIFICATES": {
            key: auth.sealed[key]
            for key in ("T264_OWNER_CERTIFICATE", "STS13_CERTIFICATE", "OWNER_MOTIF_CERTIFICATE")
        },
        "OWNER_CERTIFICATES": certificates,
        "DOUBLE_COUNT_STATUS": "PASS_DISTINCT_PROFILES_ONE_CAP_TERM_EACH_S4_REPLACED_NOT_ADDED",
        "START_FAMILY": start_family,
        "OWNER_TRANSITIONS": transitions,
        "FINAL_FAMILY": final_family,
        "START_COMPLETE_FAMILY_UB": start_family["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": final_family["FAMILY_UB"],
        "FINAL_OWNER_IDS": final_family["OWNER_IDS"],
        "CURRENT_INCUMBENT": chase.INCUMBENT,
        "REMAINING_GAP": final_family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - len(certificates),
        "OTHER_ROWS_SHA256": digest(
            {pid: r.bound for pid, r in final.items() if pid not in certificates}
        ),
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "WITNESS_SOUNDNESS": checks,
        "CURRENT_OWNER_REALIZATIONS": owner_checks,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
    }


def verify_result(result: Mapping[str, object], authority: Authority | None = None) -> None:
    if digest(result) != digest(compute_result(authority)):
        raise AssertionError("tampered immutable successor result")


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("immutable successor result already exists")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as out:
        out.write(previous.render(result))
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "START_COMPLETE_FAMILY_UB",
                    "FINAL_COMPLETE_FAMILY_UB",
                    "FINAL_OWNER_IDS",
                    "REMAINING_GAP",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
