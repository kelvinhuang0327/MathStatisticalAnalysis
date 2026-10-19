"""Adopt f2ad83b4's existing T264 S4 certificate in the sealed five-row family.

This is exact certificate integration: no donor module, 96-case proof checker,
243-T arithmetic verifier or solver is executed. All shared scientific bytes
are identical; donor-only proof dependencies are bound through immutable Git
objects. Only T264 receives S4 >= 309183. The sealed lower-T terms, including
the T263 maximum 313391920, remain intact. Replay the existing 4647-row ledger
and change one bound/source in a copy, retaining cap, S4 base and realization.
The unresolved 197-profile cursor participates in the complete family maximum.
The five-row VERIFIED_WITH_CAVEATS and donor SELF_CHECK_ONLY dispositions are
preserved, not upgraded. Reproduction needs pinned local Git objects/archives;
this integration does not establish the global K20 optimum.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from dataclasses import asdict, replace

from . import b649_min_s2_five_row_cap238_family_authority_r1 as five

TASK_ID = "B649_MIN_S2_SIX_ROW_EXISTING_S4_CERTIFIED_AUTHORITY_R1"
BASE_HEAD = "827a29132ba77bc01bc18307ba822ed75a29751a"
BASE_TREE = "1b5c577e34ef31f73a071e466ccc56968ea64585"
DONOR_HEAD = "f2ad83b4e07571a6842ac301d336360cec805a6a"
DONOR_TREE = "0b089eb90884f14283679528be40295098a5d3ef"
COMMON_ANCESTOR = "2f70925698cb28758fdf29a62bc5e91028c03a81"
BASE_RESULT_SHA256 = "374181acc60e6d202b9beccc9442fd34e74073e734d7c6068621e99e4b42622b"
DONOR_RESULT_SHA256 = "e376c3c15a767bdc75fe937f8ad36adf2ae94cc705628caccfab7f655c55852c"
DONOR_SOURCE_SHA256 = "1621262ae38fefcad112c30788c791e258be1eb5f8f2eea3dc328e3e7d6e8f09"
DONOR_TEST_SHA256 = "8e7d1dbede49bf3b47f816b40912d7f2b017ca6a1865bf87b7f16b6889028a70"
FIVE_JUDGE_SHA256 = "ebbbfe22326ea8d49ab27f77c44bb7245c44b90fdbc87afbd9dde7ae1e88407b"
TARGET_PROFILE = "66666555554411100000"
DONOR_MODULE = "b649_k20_min_s2_current_owner_motif_exact_refinement_r1"
DONOR_ONLY = {
    f"src/lottolab/research/b649_k20_min_s2_{name}_r1.py"
    for name in (
        "next_owners_and_loader_correction",
        "owner_66655555555440000000_motif",
        "three_motif_complete_family_integration",
    )
}
RESULT_STEM = "b649-min-s2-six-row-existing-s4-family-authority-r1"
two, chase, ROOT = five.two, five.chase, five.ROOT
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
Row = five.Row
BASE_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{five.RESULT_STEM}-result.json"
DONOR_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{DONOR_MODULE.replace('_', '-')}-result.json"
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
ARCHIVE = f"{two.RESULT_DIRECTORY}/{RESULT_STEM}-sources"


def digest(value: object) -> str:
    """Match the donor's canonical stored-term digest without executing its code."""
    return sha256(json.dumps(value, sort_keys=True).encode())


def prior_judge() -> dict[str, object]:
    raw = (ROOT / ARCHIVE / "five-row-fresh-judge.md").read_bytes()
    require(sha256(raw) == FIVE_JUDGE_SHA256, "five-row Judge digest mismatch")
    report = raw.decode()
    require(
        report.startswith("# VERIFIED_WITH_CAVEATS\n") and f"JUDGED_TREE: `{BASE_TREE}`" in report,
        "five-row Judge identity mismatch",
    )
    return {
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "COMMITTED_HEAD": BASE_HEAD,
        "JUDGED_TREE": BASE_TREE,
        "REPORT_SHA256": FIVE_JUDGE_SHA256,
        "ARCHIVED_PATH": f"{ARCHIVE}/five-row-fresh-judge.md",
        "STATUS_SOURCE": "ORIGINAL_FRESH_JUDGE_VERBATIM_ARCHIVE",
        "PRIOR_JUDGE_REVIEWED_SIX_ROW_TREE": False,
    }


def authorities() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Bind source, stored proof, terms, dependencies and actual Judge disposition."""
    for head, tree in ((BASE_HEAD, BASE_TREE), (DONOR_HEAD, DONOR_TREE)):
        require(five.four.three.git_tree(head) == tree, "authority tree mismatch")
    require(
        chase.git("merge-base", BASE_HEAD, DONOR_HEAD).decode().strip() == COMMON_ANCESTOR,
        "authority ancestry mismatch",
    )
    raw = two.blob(BASE_HEAD, BASE_RESULT_PATH, BASE_RESULT_SHA256)
    require((ROOT / BASE_RESULT_PATH).read_bytes() == raw, "five-row result changed")
    for path in (
        "src/lottolab/research/b649_min_s2_five_row_cap238_family_authority_r1.py",
        "tests/unit/test_b649_min_s2_five_row_cap238_family_authority_r1.py",
    ):
        require(
            (ROOT / path).read_bytes() == chase.git("show", f"{BASE_HEAD}:{path}"),
            "five-row source or tests changed",
        )
    prior = object_row(json.loads(raw))
    prior_judge()
    blobs: dict[str, bytes] = {}
    manifest: dict[str, str] = {}
    for path, pin, name in (
        (DONOR_RESULT_PATH, DONOR_RESULT_SHA256, "s4-result.json"),
        (f"src/lottolab/research/{DONOR_MODULE}.py", DONOR_SOURCE_SHA256, "s4-source.py.txt"),
        (f"tests/unit/test_{DONOR_MODULE}.py", DONOR_TEST_SHA256, "s4-tests.py.txt"),
    ):
        blob = two.blob(DONOR_HEAD, path, pin)
        require((ROOT / ARCHIVE / name).read_bytes() == blob, "donor archive changed")
        blobs[name], manifest[path] = blob, pin
    donor = object_row(json.loads(blobs["s4-result.json"]))
    require(
        ast.get_docstring(ast.parse(blobs["s4-source.py.txt"]), clean=False) == donor["PROOF"]
        and donor["SOURCE_SHA256"] == DONOR_SOURCE_SHA256,
        "donor proof/source mismatch",
    )
    dependencies = object_row(donor["MODULE_PROVENANCE"])
    require(
        len(dependencies) == 30 and set(dependencies) >= DONOR_ONLY, "provenance scope mismatch"
    )
    for path, pin in dependencies.items():
        blob = two.blob(DONOR_HEAD, path, text(pin))
        if path not in DONOR_ONLY:
            require(
                blob == chase.git("show", f"{BASE_HEAD}:{path}") == (ROOT / path).read_bytes(),
                "shared scientific dependency changed",
            )
    primitive, equivalent = (
        object_row(donor["INCIDENCE_IDENTITY"]),
        object_row(donor["EQUIVALENT_INCIDENCE_IDENTITY"]),
    )
    require(
        primitive["STATUS"] == equivalent["STATUS"] == "PASS"
        and primitive["LOCAL_CASES"] == equivalent["LOCAL_CASES"] == 96
        and len(rows(primitive["TABLE"])) == 96
        and digest(primitive["TABLE"])
        == primitive["TABLE_SHA256"]
        == "d23f333c47ca1d8a01d318cb669504206e924fd6e52b816bfe51fb7b69b40165"
        and equivalent["TABLE_SHA256"]
        == "24a070df675bd9cd9e8abd95580625c2057654f120a326c42a872a4ddc6c0eae",
        "sealed proof verification mismatch",
    )
    require(
        prior["ROWS_TOTAL"] == 4647
        and prior["CERTIFICATES_COMPOSED"] == 5
        and prior["FAMILY_BOUND_AFTER"] == 313401076
        and prior["NEW_FAMILY_OWNER_IDS"] == [TARGET_PROFILE]
        and prior["AUTHORITY_JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
        and donor["TASK_STATUS"] == "COMPLETE_SELF_CHECK_ONLY"
        and donor["JUDGE_MODE"] == "SELF_CHECK_ONLY"
        and donor["PROFILE_COVERAGE_STATUS"] == "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH"
        and donor["WITNESS_SOUNDNESS_STATUS"] == "PASS"
        and object_row(donor["OWNER_SUPPORT_REALIZATION"])["PROFILE_ID"] == TARGET_PROFILE,
        "authority disposition/scope mismatch",
    )
    cert = object_row(donor["OWNER_CERTIFICATE"])
    verify_scope(cert)
    return (
        prior,
        cert,
        {
            "IDENTITY": "PASS",
            "LOCAL_HEAD": DONOR_HEAD,
            "LOCAL_TREE": DONOR_TREE,
            "BLOB_SHA256": manifest,
            "MODULE_PROVENANCE": dependencies,
            "SHARED_SCIENTIFIC_DEPENDENCIES": 27,
            "DONOR_ONLY_DEPENDENCIES": sorted(DONOR_ONLY),
            "JUDGE_STATUS": "SELF_CHECK_ONLY",
            "TASK_STATUS": donor["TASK_STATUS"],
            "JUDGE_STATUS_SOURCE": "PINNED_DONOR_RESULT_JUDGE_MODE",
            "PROOF_VERIFICATION": "REUSED_BY_EXACT_IDENTITY_NOT_EXECUTED",
            "PROOF_SHA256": sha256(text(donor["PROOF"]).encode()),
            "INCIDENCE_IDENTITY": primitive,
            "EQUIVALENT_INCIDENCE_IDENTITY": equivalent,
        },
    )


def verify_scope(cert: Mapping[str, object]) -> None:
    """Read the sealed complete envelope; recheck just the adopted T264 arithmetic."""
    require(
        cert["PROFILE_ID"] == TARGET_PROFILE
        and cert["D"] == [int(v) for v in TARGET_PROFILE]
        and cert["G"] == [6 + int(v) for v in TARGET_PROFILE]
        and cert["MINIMUM_S2_PREMISES"]
        == {
            "TRIPLE_LABELS": 22,
            "PAIR_LABELS": 27,
            "TICKET_CAPACITY": 6,
            "PAIR_LINEARITY": True,
            "AUTHORITY": "PINNED_COMPLETE_LEDGER_AND_VALIDATED_OWNER_SUPPORT_REALIZATION",
        }
        and cert["STATUS"] == "PASS"
        and cert["TRIANGLE_CAP"] == cert["LOAD_BEARING_T"] == 264
        and cert["S4_BASE"] == 112
        and cert["OLD_PROFILE_BOUND"] == 313401076
        and cert["NEW_S4_FLOOR"] == 309183
        and cert["CAP_NEW_BOUND"] == 313387988
        and cert["CERTIFIED_PROFILE_BOUND"] == cert["RETAINED_LOWER_T_MAX"] == 313391920
        and cert["S4_RULE"] == "MAX(EXISTING, DEGREE, INCIDENCE); NEVER ADD OVERLAPPING FLOORS",
        "certificate target/premises/bound/S4 mismatch",
    )
    terms = [tuple(integer(v) for v in rows(t)) for t in rows(cert["ALL_T_TERMS"])]
    require(
        all(len(t) == 6 for t in terms)
        and [t[0] for t in terms] == list(range(22, 265))
        and terms[-1] == (264, 313387988, 490, 201, 309183, 5174624)
        and len(terms[:-1]) == cert["RETAINED_LOWER_T_COUNT"] == 242
        and digest(terms[:-1]) == cert["RETAINED_TERMS_SHA256"]
        and max(terms, key=lambda t: t[1]) == (263, 313391920, 483, 201, 281526, 5162752),
        "sealed retained lower-T envelope mismatch",
    )
    p = chase.split.profile_values(TARGET_PROFILE)
    require(
        chase.r20.bound_from_cap(p, 264, integer(cert["NEW_S4_FLOOR"]))
        == (terms[-1][5], integer(cert["CAP_NEW_BOUND"])),
        "adopted T264 arithmetic mismatch",
    )


def five_row_ledger(prior: Mapping[str, object]) -> dict[str, Row]:
    accepted, donor, _identity = five.authorities()
    ledger = five.apply_fifth(five.four_row_ledger(accepted), donor)
    require(
        len(ledger) == prior["ROWS_TOTAL"] == 4647
        and two.full_digest(ledger) == prior["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(ledger) == prior["BOUNDS_SHA256_AFTER"]
        and {p: row.bound for p, row in ledger.items()} == prior["RESOLVED_ROW_BOUNDS"]
        and five.four.three.family(ledger)[:2]
        == (integer(prior["FAMILY_BOUND_AFTER"]), rows(prior["NEW_FAMILY_OWNER_IDS"]))
        and prior["CURSOR"] == {"ID": chase.prior.CURSOR_ID, "BOUND": chase.prior.CURSOR_BOUND},
        "five-row sealed ledger mismatch",
    )
    return ledger


def apply_sixth(ledger: Mapping[str, Row], cert: Mapping[str, object]) -> dict[str, Row]:
    verify_scope(cert)
    old = ledger[TARGET_PROFILE]
    require(
        (old.bound, old.cap, old.s4_base, old.source)
        == (313401076, 264, 112, cert["EXISTING_LEDGER_SOURCE"]),
        "target already tightened or prior authority mismatch",
    )
    proof = object_row(cert["CAP_SOURCE_IDENTITY"])
    r30 = object_row(
        json.loads(
            two.blob(
                BASE_HEAD,
                f"{two.RESULT_DIRECTORY}/{five.four.r32.CAP_SOURCE_RESULT}",
                five.four.r32.R30_SHA256,
            )
        )
    )
    require(
        proof == object_row(rows(r30["GROUP_ATTEMPTS"])[2779]),
        "cap-source identity mismatch",
    )
    before = two.full_digest(ledger)
    after = dict(ledger)
    after[TARGET_PROFILE] = replace(
        old,
        bound=integer(cert["CERTIFIED_PROFILE_BOUND"]),
        source=f"{DONOR_HEAD}:{DONOR_RESULT_PATH}:OWNER_CERTIFICATE",
    )
    require(
        set(after) == set(ledger)
        and [p for p in ledger if ledger[p] != after[p]] == [TARGET_PROFILE]
        and two.full_digest(ledger) == before,
        "other row or frozen ledger changed",
    )
    return after


def compute_result() -> dict[str, object]:
    prior, cert, identity = authorities()
    ledger = five_row_ledger(prior)
    after = apply_sixth(ledger, cert)
    best, owners, next_level = five.four.three.family(after)
    ids = [text(p) for p in rows(prior["CERTIFICATE_PROFILE_IDS"])]
    require(
        len(set([*ids, TARGET_PROFILE])) == 6 and all(after[p] == ledger[p] for p in ids),
        "duplicate/prior certificate changed",
    )
    above = sorted(p for p, row in after.items() if row.bound > two.INCUMBENT)
    partition = prior["CURSOR_PARTITION_AUTHORITY"]
    require(
        partition == chase.pinned_authority()["INHERITED_PARTITION"], "cursor partition changed"
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SIX_ROW_CERTIFIED_FAMILY_AUTHORITY",
        "AUTHORITY_JUDGE_STATUS": "VERIFIED_WITH_CAVEATS",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "COMMON_ANCESTOR": COMMON_ANCESTOR,
        "FIVE_ROW_RESULT_SHA256": BASE_RESULT_SHA256,
        "DONOR_RESULT_SHA256": DONOR_RESULT_SHA256,
        "DONOR_JUDGE_STATUS": identity["JUDGE_STATUS"],
        "DONOR_APPLICABILITY": "PASS",
        "PRESERVED_FIVE_ROW_AUTHORITY": prior,
        "PRIOR_FIVE_ROW_JUDGE": prior_judge(),
        "PRIOR_JUDGE_CAVEATS": "PRESERVED",
        "CERTIFICATE_F_IDENTITY": identity,
        "CERTIFICATE_F": cert,
        "CERTIFICATE_PROFILE_IDS": [*ids, TARGET_PROFILE],
        "CERTIFICATES_COMPOSED": 6,
        "LEDGER_ROWS": len(after),
        "ROWS_CHANGED_FROM_FIVE_ROW": 1,
        "CHANGED_ROW_IDS": [TARGET_PROFILE],
        "ROW_UPDATE": {
            "PROFILE_ID": TARGET_PROFILE,
            "BEFORE": asdict(ledger[TARGET_PROFILE]),
            "AFTER": asdict(after[TARGET_PROFILE]),
        },
        "PROFILE_BOUND_BEFORE": ledger[TARGET_PROFILE].bound,
        "PROFILE_BOUND_AFTER": after[TARGET_PROFILE].bound,
        "FAMILY_BOUND_BEFORE": prior["FAMILY_BOUND_AFTER"],
        "FAMILY_BOUND_AFTER": best,
        "FAMILY_BOUND_DELTA": integer(prior["FAMILY_BOUND_AFTER"]) - best,
        "FAMILY_OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": best - two.INCUMBENT,
        "INCUMBENT": two.INCUMBENT,
        "NEXT_COMPETING_BOUND": next_level,
        "RESOLVED_ROWS_ABOVE_INCUMBENT": len(above),
        "RESOLVED_ROW_IDS_ABOVE_INCUMBENT": above,
        "RESOLVED_ROW_BOUNDS": {p: row.bound for p, row in sorted(after.items())},
        "STILL_OPEN_PROFILE_COUNT": len(above) + 197,
        "CURSOR": prior["CURSOR"],
        "CURSOR_STATUS": "UNRESOLVED_AUTHORITY_UNCHANGED",
        "CURSOR_PROFILE_COUNT": 197,
        "CURSOR_PARTITION_AUTHORITY": partition,
        "FULL_ROWS_SHA256_BEFORE": two.full_digest(ledger),
        "FULL_ROWS_SHA256_AFTER": two.full_digest(after),
        "BOUNDS_SHA256_BEFORE": two.bounds_digest(ledger),
        "BOUNDS_SHA256_AFTER": two.bounds_digest(after),
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
        "DONOR_LOCAL_CASES_REVERIFIED": 0,
        "DONOR_FULL_T_ARITHMETIC_REVERIFIED": 0,
        "ADOPTED_T_TERMS_RECHECKED": 1,
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
