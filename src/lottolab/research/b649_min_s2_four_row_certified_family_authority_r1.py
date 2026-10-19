"""Compose the T257 three-row authority and the sibling T264 S4 certificate.

This is exact certificate integration, not a new proof. Both source/result pairs
and their tests are read from pinned Git objects. Their prior Judgments are reused.
The original T257 Fresh Judge report is archived verbatim, including its caveats;
Certificate B keeps its original status and Worker-sourced caveat provenance.

Replay the frozen 4,647 rows, preserve A/B/C in full and change only D's bound
and source. D's S4 floor applies at T264 only. Its cap, realization and global S4
base stay unchanged; the lower-T Route-B terms remain in the full envelope.
All maxima, tied owners and gaps are derived, including the unresolved cursor.
No donor proof suite, solver, portfolio search or STS reconstruction is run.
Reproduction requires the pinned local Git objects and frozen archives.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from dataclasses import asdict, replace
from fractions import Fraction

from . import b649_min_s2_core_zero_t257_three_row_cert_r1 as three

TASK_ID = "B649_MIN_S2_FOUR_ROW_CERTIFIED_FAMILY_AUTHORITY_R1"
BASE_HEAD = "038eb9f040a34d2e6a8220caf28f164f94bf1edc"
BASE_TREE = "8c1f35844d727ffe0df8fe4c5ebc220cf327e8b7"
DONOR_HEAD = "9c9d309f89b6050e7b4cb49155fc72ff168f7ef8"
DONOR_TREE = "3972a602f45062c36d0bac8716a739ca47e95478"
COMMON_PARENT = "cc493492701d19ad433bba967f14c2f27f844c3e"
BASE_RESULT_SHA256 = "a62bef4f276e0515adada305665cf392caf81a0c1808d7141d7664e5f8871cfa"
DONOR_RESULT_SHA256 = "cd90847d495684305fb814f605f9f4a531d7401775ab2602a82c48ae85c93a4e"
C_MODULE = "b649_min_s2_core_zero_t257_three_row_cert_r1"
D_MODULE = "b649_min_s2_next_owner_t264_s4_cert_r1"
C_SOURCE_SHA256 = "0e3d4746ef59eece7de5291cf3fe40c364f5dc70380d00666095c0362f95d806"
D_SOURCE_SHA256 = "503e9f8181142272c5e1df1e3608a4543633014988e772c1a15b82e93db7413f"
C_TEST_SHA256 = "1ef6f0da09e737dbd71d081f965bb0003ce59dbbba6105131fd9616c2db2c020"
D_TEST_SHA256 = "9f25f5c22a24db098f7afd6287fc7d3e8c3868497a60476108df9eec90264945"
D_PROFILE = "66665555555421000000"
RESULT_STEM = "b649-min-s2-four-row-certified-family-authority-r1"
two, chase, r32 = three.two, three.chase, three.r32
ROOT = three.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
C_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{three.RESULT_STEM}-{BASE_RESULT_SHA256}.json"
D_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{D_MODULE.replace('_', '-')}-result.json"
JUDGE_ARCHIVE = f"{two.RESULT_DIRECTORY}/{RESULT_STEM}-sources/t257-fresh-judge.md"
JUDGE_ORIGIN = (
    "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.git/worktrees/"
    "B649_MIN_S2_CORE_ZERO_T257_CERT_R1/fable-finalization/"
    "B649_MIN_S2_T257_QUOTA_INTERRUPTED_FINALIZATION_R1/judge/final-report.md"
)
JUDGE_SHA256 = "b16f0a0253b240abcededa465835e3843d9b996cda58a40d1c938ade3d55698b"
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
Row = chase.Row
Term = tuple[int, int, int, int, int, int]


def certificate(
    head: str,
    tree: str,
    module: str,
    source_digest: str,
    result_path: str,
    result_digest: str,
    test_digest: str,
    verdict: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Bind the reused proof/result/tests to immutable objects, without executing proof."""
    require(three.git_tree(head) == tree, "certificate tree mismatch")
    require(chase.git("rev-parse", f"{head}^").decode().strip() == COMMON_PARENT, "not siblings")
    source_path = f"src/lottolab/research/{module}.py"
    test_path = f"tests/unit/test_{module}.py"
    source = two.blob(head, source_path, source_digest)
    raw = two.blob(head, result_path, result_digest)
    two.blob(head, test_path, test_digest)
    result = object_row(json.loads(raw))
    require(ast.get_docstring(ast.parse(source), clean=False) == result["PROOF"], "proof mismatch")
    require(
        result["BASE_HEAD"] == COMMON_PARENT and result["BASE_TREE"] == three.BASE_TREE,
        "certificate input base mismatch",
    )
    return result, {
        "IDENTITY": "PASS",
        "LOCAL_HEAD": head,
        "LOCAL_TREE": tree,
        "BLOB_SHA256": {
            source_path: source_digest,
            result_path: result_digest,
            test_path: test_digest,
        },
        "JUDGE_STATUS": verdict,
        "JUDGE_STATUS_SOURCE": "CURRENT_OWNER_PACKET",
        "DONOR_TESTS": "REUSED_BY_EXACT_SOURCE_AND_TEST_IDENTITY",
    }


def authorities() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    c, ci = certificate(
        BASE_HEAD,
        BASE_TREE,
        C_MODULE,
        C_SOURCE_SHA256,
        C_RESULT_PATH,
        BASE_RESULT_SHA256,
        C_TEST_SHA256,
        "VERIFIED_WITH_CAVEATS",
    )
    d, di = certificate(
        DONOR_HEAD,
        DONOR_TREE,
        D_MODULE,
        D_SOURCE_SHA256,
        D_RESULT_PATH,
        DONOR_RESULT_SHA256,
        D_TEST_SHA256,
        "VERIFIED",
    )
    require(
        c["CERTIFICATES_COMPOSED"] == 3
        and c["LEDGER_ROWS"] == two.LEDGER_ROWS
        and object_row(c["ROW_UPDATE"])["PROFILE_ID"] == three.C_PROFILE
        and d["TARGET_PROFILE"] == D_PROFILE
        and d["CERTIFICATE_SCOPE"] == "TARGET_PROFILE_T264_ONLY"
        and d["CERTIFIED_T_CAP"] == 264
        and d["QUARTET_IDENTITY"] == d["INCIDENCE_INEQUALITIES"] == "PASS"
        and d["R30_CAP264_IDENTITY"] == "PASS"
        and d["FAMILY_BOUND_AUTHORITY_PRODUCED"] is False,
        "certificate scope mismatch",
    )
    # Bind every reused scientific input. Never read a mutable donor worktree.
    for key in ("AUTHORITY_PROVENANCE", "EXISTING_CERTIFICATE_AUDIT"):
        for locator, digest in object_row(d[key]).items():
            ref, path = locator.split(":", 1) if ":" in locator else (COMMON_PARENT, locator)
            raw = two.blob(ref, path, text(digest))
            require(raw == chase.git("show", f"{BASE_HEAD}:{path}"), "shared input changed")
            if path.endswith(".py"):
                require((ROOT / path).read_bytes() == raw, "reused source changed")
    source = ROOT / f"src/lottolab/research/{C_MODULE}.py"
    require(
        source.read_bytes() == two.blob(BASE_HEAD, str(source.relative_to(ROOT)), C_SOURCE_SHA256),
        "T257 source changed",
    )
    reused = three.module_provenance()
    require(
        reused == {k: v for k, v in object_row(c["MODULE_PROVENANCE"]).items() if k in reused},
        "T257 helper provenance changed",
    )
    return c, d, {"CERTIFICATE_C_IDENTITY": ci, "CERTIFICATE_D_IDENTITY": di}


def prior_judge(c: Mapping[str, object]) -> dict[str, object]:
    raw = (ROOT / JUDGE_ARCHIVE).read_bytes()
    require(sha256(raw) == JUDGE_SHA256, "T257 Judge archive changed")
    report = raw.decode()
    require(
        report.startswith("# VERIFIED_WITH_CAVEATS\n") and BASE_TREE in report,
        "T257 Judge identity mismatch",
    )
    b = object_row(c["CERTIFICATE_B_IDENTITY"])
    require(
        b["JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
        and b["JUDGE_CAVEATS_TEXT"] == c["CERTIFICATE_B_CAVEATS"] == list(two.B_WORKER_CAVEATS)
        and b["JUDGE_CAVEATS_SOURCE"]
        == c["CERTIFICATE_B_CAVEATS_SOURCE"]
        == "OWNER_SUPPLIED_ORIGINAL_WORKER_REPORT"
        and all(caveat in report for caveat in two.B_WORKER_CAVEATS),
        "Certificate B caveats or provenance changed",
    )
    return {
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "JUDGED_TREE": BASE_TREE,
        "HEAD_AT_REVIEW": COMMON_PARENT,
        "COMMITTED_HEAD": BASE_HEAD,
        "SOURCE": "ORIGINAL_FRESH_JUDGE_REPORT_VERBATIM_ARCHIVE",
        "ORIGINAL_PATH": JUDGE_ORIGIN,
        "ARCHIVED_PATH": JUDGE_ARCHIVE,
        "REPORT_SHA256": JUDGE_SHA256,
        "CAVEATS_TEXT": report.split("\nLimitations:\n\n", 1)[1].split("\n\nCOVERED_ITEMS:", 1)[0],
        "PRIOR_JUDGE_REVIEWED_FOUR_ROW_TREE": False,
    }


def three_row_ledger(c: Mapping[str, object]) -> tuple[dict[str, Row], dict[str, Row]]:
    """Rebuild the accepted ledger, using stored certificates rather than their proof suites."""
    final, audit = three.pinned_two_row()
    original, second, provenance = three.two_row_ledger(final)
    require(c["ADDENDUM_AUDIT"] == audit, "prior addendum audit changed")
    update = object_row(c["ROW_UPDATE"])
    old, new = object_row(update["BEFORE"]), object_row(update["AFTER"])
    route = object_row(c["ROUTE_B"])
    terms, bound = three.route_b(integer(route["CAP_AFTER"]))
    require(
        json.loads(json.dumps(asdict(second[three.C_PROFILE]))) == old
        and [list(t) for t in terms] == rows(route["ALL_T_TERMS"])
        and bound == route["ALL_T_MAX_BOUND"] == c["PROFILE_BOUND_AFTER"] == new["bound"],
        "T257 row binding mismatch",
    )
    ledger = three.apply_third(second, bound, integer(new["cap"]), text(new["source"]))
    require(
        json.loads(json.dumps(asdict(ledger[three.C_PROFILE]))) == new
        and two.full_digest(ledger) == c["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(ledger) == c["BOUNDS_SHA256_AFTER"]
        and three.family(ledger)[:2]
        == (integer(c["FAMILY_BOUND_AFTER"]), rows(c["NEW_FAMILY_OWNER"]))
        and sorted(p for p in original if original[p] != ledger[p])
        == rows(c["ROWS_CHANGED_VS_ORIGINAL"])
        and all(object_row(c["MODULE_PROVENANCE"])[k] == v for k, v in provenance.items()),
        "three-row ledger does not reproduce T257 authority",
    )
    return original, ledger


def envelope(old: Row, d: Mapping[str, object]) -> tuple[list[Term], list[Term]]:
    """Retain all lower-T terms; reuse the certified T264 floor and round exactly."""
    require(
        old.cap == d["CERTIFIED_T_CAP"] and old.bound == d["PROFILE_BOUND_BEFORE"],
        "T264 row binding mismatch",
    )
    before = r32.route_b_envelope(chase.split.profile_values(D_PROFILE), old.cap, old.s4_base)
    require([t[0] for t in before] == list(range(22, old.cap + 1)), "envelope domain changed")
    require(list(before[-1]) == d["T264_TERM_BEFORE"], "T264 term binding mismatch")
    after = list(before)
    t, _, k, a, s4, s3 = before[-1]
    s4 = max(s4, integer(d["T264_S4_LOWER_BOUND"]))
    checked_s3, bound = r32.bound_from_cap(chase.split.profile_values(D_PROFILE), t, s4)
    require(checked_s3 == s3, "S3 changed")
    after[-1] = t, bound, k, a, s4, s3
    best = max(after, key=lambda term: (term[1], term[0]))
    lower_best = max(before[:-1], key=lambda term: (term[1], term[0]))
    require(
        d["LOWER_T_TERMS_UNCHANGED"] is True
        and after[:-1] == before[:-1]
        and d["LOWER_T_SCOPE"] == [22, old.cap - 1]
        and d["LOWER_T_TERM_COUNT"] == len(before) - 1
        and sha256(json.dumps(before[:-1], separators=(",", ":")).encode())
        == d["LOWER_T_TERMS_SHA256"]
        and list(lower_best) == d["LOWER_T_MAX_TERM"]
        and max(term[1] for term in before) == old.bound
        and list(after[-1]) == d["T264_TERM_AFTER"]
        and bound == d["T264_UPPER_BOUND"]
        and (best[0], best[1]) == (d["FULL_PROFILE_ARGMAX_T"], d["FULL_PROFILE_UPPER_BOUND"]),
        "full profile envelope mismatch",
    )
    for term in after:
        exact = r32.K20_S1 - r32.K20_S2 + term[5] - Fraction(4 * term[4], 7)
        require(0 <= term[1] - exact < 1, "Bonferroni rounding mismatch")
    return before, after


def apply_fourth(ledger: Mapping[str, Row], d: Mapping[str, object]) -> dict[str, Row]:
    _, terms = envelope(ledger[D_PROFILE], d)
    bound = max(term[1] for term in terms)
    require(bound < ledger[D_PROFILE].bound, "fourth update does not tighten")
    after = dict(ledger)
    after[D_PROFILE] = replace(
        ledger[D_PROFILE],
        bound=bound,
        source=f"{DONOR_HEAD}:{D_RESULT_PATH}:FULL_PROFILE_UPPER_BOUND",
    )
    require([p for p in ledger if ledger[p] != after[p]] == [D_PROFILE], "other row changed")
    return after


def compute_result() -> dict[str, object]:
    c, d, identities = authorities()
    judge = prior_judge(c)
    original, ledger = three_row_ledger(c)
    frozen = two.full_digest(ledger)
    before_terms, terms = envelope(ledger[D_PROFILE], d)
    after = apply_fourth(ledger, d)
    before, old_owners, _ = three.family(ledger)
    best, owners, next_level = three.family(after)
    require(two.full_digest(ledger) == frozen, "three-row ledger mutated")
    changed = sorted(p for p in ledger if after[p] != ledger[p])
    original_changed = sorted(p for p in original if after[p] != original[p])
    require(
        original_changed
        == sorted([*[text(p) for p in rows(c["ROWS_CHANGED_VS_ORIGINAL"])], D_PROFILE]),
        "prior updates not preserved",
    )
    actual: dict[str, object] = {
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_BOUND_AFTER": best,
        "EXACT_DELTA": before - best,
        "CURRENT_FAMILY_OWNER": owners,
        "GAP_TO_INCUMBENT": best - two.INCUMBENT,
    }
    expected: dict[str, object] = {
        "FAMILY_BOUND_BEFORE": 313_401_464,
        "FAMILY_BOUND_AFTER": 313_401_180,
        "EXACT_DELTA": 284,
        "CURRENT_FAMILY_OWNER": ["66665555554422000000"],
        "GAP_TO_INCUMBENT": 137_292,
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "FOUR_ROW_CERTIFIED_FAMILY_AUTHORITY",
        "PROOF_AUTHORITY": "REUSED_PINNED_CERTIFICATES_NO_NEW_PROOF",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "COMMON_PARENT": COMMON_PARENT,
        "T257_AUTHORITY": "PASS",
        "T264_S4_AUTHORITY": "PASS",
        **identities,
        "CERTIFICATE_A_IDENTITY": c["CERTIFICATE_A_IDENTITY"],
        "CERTIFICATE_B_IDENTITY": c["CERTIFICATE_B_IDENTITY"],
        "CERTIFICATE_B_JUDGE_STATUS": c["CERTIFICATE_B_JUDGE_STATUS"],
        "CERTIFICATE_B_CAVEATS": c["CERTIFICATE_B_CAVEATS"],
        "CERTIFICATE_B_CAVEATS_SOURCE": c["CERTIFICATE_B_CAVEATS_SOURCE"],
        "PRIOR_COMBINED_FRESH_JUDGE": c["PRIOR_COMBINED_FRESH_JUDGE"],
        "PRIOR_T257_FRESH_JUDGE": judge,
        "PRIOR_JUDGE_CAVEATS_PRESERVED": "YES",
        "ADDENDUM_AUDIT": c["ADDENDUM_AUDIT"],
        "SUPPORT_MODEL": c["SUPPORT_MODEL"],
        "PRESERVED_T257_SCIENCE": {
            k: c[k]
            for k in (
                "THEOREM_T257",
                "T257_REALIZATION",
                "RECORDED_ROW_REALIZATION",
                "ROUTE_B",
                "SUPPLEMENTAL_REDUCED_CONFIGURATIONS",
                "ROW_UPDATE",
            )
        },
        "LEDGER_DIGEST": c["LEDGER_DIGEST"],
        "LEDGER_ROWS": len(after),
        "CERTIFICATES_COMPOSED": 4,
        "ROWS_CHANGED_FROM_THREE_ROW": len(changed),
        "CHANGED_ROW_IDS": changed,
        "ROWS_CHANGED_VS_ORIGINAL": original_changed,
        "ROW_UPDATE": {
            "PROFILE_ID": D_PROFILE,
            "BEFORE": asdict(ledger[D_PROFILE]),
            "AFTER": asdict(after[D_PROFILE]),
        },
        "PROFILE_BOUND_BEFORE": max(term[1] for term in before_terms),
        "PROFILE_BOUND_AFTER": max(term[1] for term in terms),
        "T264_S4_FLOOR": d["T264_S4_LOWER_BOUND"],
        "T264_BOUND": d["T264_UPPER_BOUND"],
        "PROFILE_ENVELOPE": {
            "TERM_COLUMNS": d["TERM_COLUMNS"],
            "ALL_T_TERMS": [list(t) for t in terms],
            "LOWER_T_TERMS_SHA256": d["LOWER_T_TERMS_SHA256"],
            "LOWER_T_TERMS_UNCHANGED": True,
            "ARGMAX_T": max(terms, key=lambda t: (t[1], t[0]))[0],
        },
        **actual,
        "PREVIOUS_FAMILY_OWNER": old_owners,
        "NEXT_COMPETING_BOUND": next_level,
        "INCUMBENT": two.INCUMBENT,
        "EXPECTED_VALUES_MATCH": actual == expected,
        "EXPECTED_VALUE_DIFFERENCES": {
            k: {"EXPECTED": expected[k], "ACTUAL": actual[k]}
            for k in expected
            if actual[k] != expected[k]
        },
        "NEW_OWNER_ROWS": {p: asdict(after[p]) for p in owners if p in after},
        "CURSOR": {"ID": chase.prior.CURSOR_ID, "BOUND": chase.prior.CURSOR_BOUND},
        "BOUNDS_SHA256_BEFORE": two.bounds_digest(ledger),
        "FULL_ROWS_SHA256_BEFORE": frozen,
        "BOUNDS_SHA256_AFTER": two.bounds_digest(after),
        "FULL_ROWS_SHA256_AFTER": two.full_digest(after),
        "MODULE_PROVENANCE": c["MODULE_PROVENANCE"],
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
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
