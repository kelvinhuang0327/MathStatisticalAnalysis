"""Compose the accepted four-row authority with the exact D6 Cap238 certificate.

Reuse immutable proof/result/test bytes; never execute the donor proof, its 620
degree configurations or its 217-term arithmetic verification. Recover the
digest-sealed four-row ledger with its existing zero-solve replay, then replace
only profile 66665555554422000000. Its S4 base and realization are retained.
The full 4,647-row maximum includes the unchanged unresolved cursor authority.
All prior certificate identities, science and Judge caveats remain verbatim in
the preserved four-row result. VERIFIED_WITH_CAVEATS is never upgraded.
Reproduction requires the pinned local Git objects and frozen archives.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from dataclasses import asdict, replace

from . import b649_min_s2_four_row_certified_family_authority_r1 as four

TASK_ID = "B649_MIN_S2_FIVE_ROW_CAP238_CERTIFIED_AUTHORITY_R1"
BASE_HEAD = "5cb67b536c225e53cbf29d3fe5334cfa82a1c652"
BASE_TREE = "38b5ad8cace1f0d28323f0dcea3b866dda71286d"
DONOR_HEAD = "eb2e23902c72720722cd7f12343b5f2b476dd6cc"
DONOR_TREE = "ffac7fbe81470cd0a85ffa01d052ca7779278953"
COMMON_ANCESTOR = "2f70925698cb28758fdf29a62bc5e91028c03a81"
THEOREM_HEAD = "e44a635f1932166734aaa3f64f9469c0e63c7520"
THEOREM_BLOB = "ade988f4198b11c9591ca4e49e0bd976082bf26a"
TARGET_PROFILE = "66665555554422000000"
BASE_RESULT_SHA256 = "f17cb7e1d8710f089c57e6739e9d4963ecd963d58d69e0c37e85a8552c307bd1"
DONOR_RESULT_SHA256 = "65a854c3b766dd3cf220c9ad1e48ff0bdc03b46d3648a5a477d8b52ceff0515a"
DONOR_SOURCE_SHA256 = "07b1caa8c25d01ab3c974c4555785fc3fc61db1d5d26deac1b64d1476521c98a"
DONOR_TEST_SHA256 = "8312354324fe79a85243567753c9e4a1b8456d07bd6d03ce69776127da2c3fe9"
FOUR_JUDGE_SHA256 = "e59196d903cabdacbe7d5359a4739d7d6a4cb51a68993784a2b936241cb9f597"
DONOR_MODULE = "b649_k20_min_s2_d6_generic_cap238_certificate_r1"
RESULT_STEM = "b649-min-s2-five-row-cap238-family-authority-r1"
two, chase = four.two, four.chase
ROOT = four.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
ARCHIVE = f"{two.RESULT_DIRECTORY}/{RESULT_STEM}-sources"
BASE_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{four.RESULT_STEM}-result.json"
DONOR_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{DONOR_MODULE.replace('_', '-')}-result.json"
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
Row = four.Row


def prior_judge() -> dict[str, object]:
    """Keep the four-row Fresh Judge report and its limitations verbatim."""
    name = f"{ARCHIVE}/four-row-fresh-judge.md"
    raw = (ROOT / name).read_bytes()
    require(sha256(raw) == FOUR_JUDGE_SHA256, "four-row Judge archive digest mismatch")
    report = raw.decode()
    require(
        report.startswith("# VERIFIED_WITH_CAVEATS\n") and f"JUDGED_TREE: `{BASE_TREE}`" in report,
        "four-row Judge identity mismatch",
    )
    return {
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "JUDGED_TREE": BASE_TREE,
        "COMMITTED_HEAD": BASE_HEAD,
        "STATUS_SOURCE": "ORIGINAL_FRESH_JUDGE_VERBATIM_ARCHIVE",
        "ORIGINAL_PATH": (
            "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
            "B649_MIN_S2_FOUR_ROW_CERTIFIED_AUTHORITY_R1/"
            ".task-data/b649-four-row/judge/final-report.md"
        ),
        "ARCHIVED_PATH": name,
        "REPORT_SHA256": FOUR_JUDGE_SHA256,
        "CAVEATS_TEXT": report.split("\nLimitations: ", 1)[1].split("\n\nWrite accounting:", 1)[0],
        "PRIOR_JUDGE_REVIEWED_FIVE_ROW_TREE": False,
    }


def authorities() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Validate the exact accepted authorities and their common scientific inputs."""
    for head, tree in ((BASE_HEAD, BASE_TREE), (DONOR_HEAD, DONOR_TREE)):
        require(four.three.git_tree(head) == tree, "authority tree mismatch")
    require(
        chase.git("merge-base", BASE_HEAD, DONOR_HEAD).decode().strip() == COMMON_ANCESTOR
        and chase.git("merge-base", THEOREM_HEAD, BASE_HEAD).decode().strip() == THEOREM_HEAD
        and chase.git("merge-base", THEOREM_HEAD, DONOR_HEAD).decode().strip() == THEOREM_HEAD,
        "authority ancestry mismatch",
    )
    prior_raw = two.blob(BASE_HEAD, BASE_RESULT_PATH, BASE_RESULT_SHA256)
    require((ROOT / BASE_RESULT_PATH).read_bytes() == prior_raw, "four-row result changed")
    for path in (
        "src/lottolab/research/b649_min_s2_four_row_certified_family_authority_r1.py",
        "tests/unit/test_b649_min_s2_four_row_certified_family_authority_r1.py",
    ):
        require(
            (ROOT / path).read_bytes() == chase.git("show", f"{BASE_HEAD}:{path}"),
            "four-row source or tests changed",
        )
    prior = object_row(json.loads(prior_raw))
    prior_judge()
    manifest: dict[str, str] = {}
    blobs: dict[str, bytes] = {}
    for path, digest, name in (
        (DONOR_RESULT_PATH, DONOR_RESULT_SHA256, "d6-cap238-result.json"),
        (
            f"src/lottolab/research/{DONOR_MODULE}.py",
            DONOR_SOURCE_SHA256,
            "d6-cap238-source.py.txt",
        ),
        (f"tests/unit/test_{DONOR_MODULE}.py", DONOR_TEST_SHA256, "d6-cap238-tests.py.txt"),
    ):
        raw = two.blob(DONOR_HEAD, path, digest)
        require((ROOT / ARCHIVE / name).read_bytes() == raw, "donor archive changed")
        manifest[path] = digest
        blobs[name] = raw
    donor = object_row(json.loads(blobs["d6-cap238-result.json"]))
    proof = next(
        ast.literal_eval(n.value)
        for n in ast.parse(blobs["d6-cap238-source.py.txt"]).body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PROOF" for t in n.targets)
    )
    require(
        proof == donor["PROOF"] and sha256(text(proof).encode()) == donor["PROOF_SHA256"],
        "donor proof/result mismatch",
    )
    generic = object_row(donor["GENERIC_THEOREM_IDENTITY"])
    theorem_path = text(generic["THEOREM_PATH"])
    require(
        generic["THEOREM_HEAD"] == THEOREM_HEAD
        and four.three.git_tree(THEOREM_HEAD) == generic["THEOREM_TREE"]
        and generic["THEOREM_BLOB"]
        == chase.git("rev-parse", f"{THEOREM_HEAD}:{theorem_path}").decode().strip()
        == THEOREM_BLOB
        and generic["GENERAL_BRANCH"] == "A_NONNEGATIVE_P"
        and generic["CONDITIONAL_P12_USED"] is False,
        "generic theorem authority mismatch",
    )
    for path, digest in object_row(generic["DEPENDENCY_SHA256"]).items():
        raw = two.blob(text(donor["BASE_HEAD"]), path, text(digest))
        require(
            raw == chase.git("show", f"{BASE_HEAD}:{path}") == (ROOT / path).read_bytes(),
            "shared scientific dependency changed",
        )
    original = object_row(
        json.loads(
            two.blob(
                THEOREM_HEAD,
                f"{two.RESULT_DIRECTORY}/b649-k20-min-s2-topw12-split-cap-certificate-r1-result.json",
                text(generic["ORIGINAL_RESULT_SHA256"]),
            )
        )
    )
    theorem_source = two.blob(THEOREM_HEAD, theorem_path, text(generic["THEOREM_SHA256"]))
    original_proof = ast.get_docstring(ast.parse(theorem_source), clean=False)
    require(
        original_proof == original["PROOF"]
        and sha256(text(original_proof).encode()) == generic["ORIGINAL_PROOF_SHA256"],
        "generic theorem proof mismatch",
    )
    cert = object_row(donor["DEGREE_CERTIFICATE"])
    require(
        prior["LEDGER_ROWS"] == 4647
        and prior["CERTIFICATES_COMPOSED"] == 4
        and prior["FAMILY_BOUND_AFTER"] == 313401180
        and prior["CURRENT_FAMILY_OWNER"] == [TARGET_PROFILE]
        and donor["TARGET_PROFILE"] == cert["PROFILE_ID"] == TARGET_PROFILE
        and donor["PROVEN_NEW_CAP"] == cert["TRIANGLE_CAP"] == 238
        and donor["THEOREM_APPLICABILITY"] == donor["MODEL_SEMANTICS"] == "PASS"
        and donor["TRIANGLE_DOMAIN"] == [22, 238]
        and donor["TERM_COUNT"] == 217
        and donor["ALL_T_STATUS"] == "PASS_INTEGER_RATIONAL_AND_R32_AGREEMENT"
        and donor["R32_BOUND_RULE"] == four.r32.BOUND_RULE
        and donor["S4_BASE"] == 112
        and donor["A_MAX"] == 199
        and donor["NEW_PROFILE_BOUND"] == 313159012
        and cert["DEGREE_CONFIGURATION_COUNT"] == 620
        and cert["BRANCH_COUNTS"] == {"A_NONNEGATIVE_P": 620}
        and cert["CONDITIONAL_CONFIGURATIONS"] == [],
        "certificate scope mismatch",
    )
    # Read the sealed all-T coverage and maximum; do not re-evaluate its arithmetic.
    terms = [tuple(integer(v) for v in rows(t)) for t in rows(donor["ALL_T_TERMS"])]
    require(
        all(len(t) == 6 for t in terms)
        and [t[0] for t in terms] == list(range(22, 239))
        and list(max(terms, key=lambda t: (t[1], t[0]))) == donor["ARGMAX_TERM"]
        and max(t[1] for t in terms) == donor["NEW_PROFILE_BOUND"],
        "sealed full T domain mismatch",
    )
    return (
        prior,
        donor,
        {
            "IDENTITY": "PASS",
            "LOCAL_HEAD": DONOR_HEAD,
            "LOCAL_TREE": DONOR_TREE,
            "BLOB_SHA256": manifest,
            "JUDGE_STATUS": "VERIFIED",
            "JUDGE_STATUS_SOURCE": "CURRENT_OWNER_PACKET",
            "PROOF_AND_DONOR_TESTS": "REUSED_BY_EXACT_IDENTITY_NOT_EXECUTED",
            "GENERIC_THEOREM_IDENTITY": generic,
        },
    )


def four_row_ledger(prior: Mapping[str, object]) -> dict[str, Row]:
    """Recover the sealed rows without calling any proof/search entrypoint."""
    c, d, identities = four.authorities()
    require(four.prior_judge(c) == prior["PRIOR_T257_FRESH_JUDGE"], "prior caveats changed")
    _, third = four.three_row_ledger(c)
    ledger = four.apply_fourth(third, d)
    require(
        len(ledger) == prior["LEDGER_ROWS"]
        and two.full_digest(ledger) == prior["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(ledger) == prior["BOUNDS_SHA256_AFTER"]
        and four.three.family(ledger)[:2]
        == (integer(prior["FAMILY_BOUND_AFTER"]), rows(prior["CURRENT_FAMILY_OWNER"]))
        and all(prior[k] == v for k, v in identities.items())
        and prior["CURSOR"] == {"ID": chase.prior.CURSOR_ID, "BOUND": chase.prior.CURSOR_BOUND},
        "four-row sealed ledger mismatch",
    )
    return ledger


def apply_fifth(ledger: Mapping[str, Row], donor: Mapping[str, object]) -> dict[str, Row]:
    """Apply this target-specific certificate exactly once, in a copy."""
    require(donor["TARGET_PROFILE"] == TARGET_PROFILE, "certificate target mismatch")
    old = ledger[TARGET_PROFILE]
    require(
        (old.bound, old.cap, old.s4_base) == (313401180, 265, 112),
        "target already tightened or prior authority mismatch",
    )
    cap, bound = integer(donor["PROVEN_NEW_CAP"]), integer(donor["NEW_PROFILE_BOUND"])
    require(
        (cap, bound, donor["S4_BASE"]) == (238, 313159012, old.s4_base),
        "fifth certificate bound/cap/S4 mismatch",
    )
    before = two.full_digest(ledger)
    after = dict(ledger)
    after[TARGET_PROFILE] = replace(
        old,
        bound=bound,
        cap=cap,
        source=f"{DONOR_HEAD}:{DONOR_RESULT_PATH}:NEW_PROFILE_BOUND",
    )
    require(
        set(after) == set(ledger)
        and [p for p in ledger if ledger[p] != after[p]] == [TARGET_PROFILE]
        and two.full_digest(ledger) == before,
        "other row or frozen ledger changed",
    )
    return after


def compute_result() -> dict[str, object]:
    prior, donor, identity = authorities()
    ledger = four_row_ledger(prior)
    before_digest = two.full_digest(ledger)
    after = apply_fifth(ledger, donor)
    best, owners, next_level = four.three.family(after)
    require(two.full_digest(ledger) == before_digest, "frozen four-row ledger mutated")
    previous_ids = [two.A_PROFILE, two.B_PROFILE, four.three.C_PROFILE, four.D_PROFILE]
    require(
        len(set([*previous_ids, TARGET_PROFILE])) == 5
        and all(after[p] == ledger[p] for p in previous_ids),
        "duplicate/prior certificate changed",
    )
    above = sorted(p for p, row in after.items() if row.bound > two.INCUMBENT)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "FIVE_ROW_CERTIFIED_FAMILY_AUTHORITY",
        "AUTHORITY_JUDGE_STATUS": "VERIFIED_WITH_CAVEATS",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "COMMON_ANCESTOR": COMMON_ANCESTOR,
        "FOUR_ROW_AUTHORITY": "PASS",
        "D6_CAP238_AUTHORITY": "PASS",
        "FOUR_ROW_RESULT_SHA256": BASE_RESULT_SHA256,
        "D6_CAP238_RESULT_SHA256": DONOR_RESULT_SHA256,
        "PRESERVED_FOUR_ROW_AUTHORITY": prior,
        "PRIOR_FOUR_ROW_JUDGE": prior_judge(),
        "PRIOR_JUDGE_CAVEATS": "PRESERVED",
        "CERTIFICATE_E_IDENTITY": identity,
        "CERTIFICATE_PROFILE_IDS": [*previous_ids, TARGET_PROFILE],
        "CERTIFICATES_COMPOSED": 5,
        "ROWS_TOTAL": len(after),
        "ROWS_CHANGED_FROM_FOUR_ROW": 1,
        "CHANGED_ROW_IDS": [TARGET_PROFILE],
        "ROW_UPDATE": {
            "PROFILE_ID": TARGET_PROFILE,
            "BEFORE": asdict(ledger[TARGET_PROFILE]),
            "AFTER": asdict(after[TARGET_PROFILE]),
        },
        "PROFILE_BOUND_BEFORE": ledger[TARGET_PROFILE].bound,
        "PROFILE_BOUND_AFTER": after[TARGET_PROFILE].bound,
        "EXACT_PROFILE_DELTA": ledger[TARGET_PROFILE].bound - after[TARGET_PROFILE].bound,
        "DONOR_PRIOR_CAP260_ADOPTED_IN_FOUR_ROW": False,
        "D6_CERTIFICATE_SCOPE": {
            "TRIANGLE_DOMAIN": donor["TRIANGLE_DOMAIN"],
            "S4_BASE": donor["S4_BASE"],
            "A_MAX": donor["A_MAX"],
            "R32_BOUND_RULE": donor["R32_BOUND_RULE"],
        },
        "FAMILY_BOUND_BEFORE": prior["FAMILY_BOUND_AFTER"],
        "FAMILY_BOUND_AFTER": best,
        "EXACT_FAMILY_DELTA": integer(prior["FAMILY_BOUND_AFTER"]) - best,
        "OLD_OWNER": prior["CURRENT_FAMILY_OWNER"],
        "NEW_FAMILY_OWNER_IDS": owners,
        "NEW_GAP_TO_INCUMBENT": best - two.INCUMBENT,
        "INCUMBENT": two.INCUMBENT,
        "NEXT_COMPETING_BOUND": next_level,
        "RESOLVED_ROWS_ABOVE_INCUMBENT": len(above),
        "RESOLVED_ROW_IDS_ABOVE_INCUMBENT": above,
        "RESOLVED_ROW_BOUNDS": {p: row.bound for p, row in sorted(after.items())},
        "CURSOR": prior["CURSOR"],
        "CURSOR_STATUS": "UNRESOLVED_AUTHORITY_UNCHANGED",
        "CURSOR_PARTITION_AUTHORITY": chase.pinned_authority()["INHERITED_PARTITION"],
        "NEW_OWNER_ROWS": {p: asdict(after[p]) for p in owners if p in after},
        "FULL_ROWS_SHA256_BEFORE": before_digest,
        "FULL_ROWS_SHA256_AFTER": two.full_digest(after),
        "BOUNDS_SHA256_BEFORE": two.bounds_digest(ledger),
        "BOUNDS_SHA256_AFTER": two.bounds_digest(after),
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SEARCH_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
        "DEGREE_CONFIGURATIONS_REENUMERATED": 0,
        "D6_ROUTE_B_TERMS_REVERIFIED": 0,
    }


def main() -> None:
    payload = two.render(compute_result())
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing exact result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    print(json.dumps({"RESULT": str(RESULT_PATH), "SHA256": sha256(payload)}))


if __name__ == "__main__":
    main()
