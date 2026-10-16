"""Replay the pinned 25-event B649 family and integrate two tied resolved owners."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen
from . import b649_t255_25_event_from_t261_r1 as base

TASK_ID = "B649_TIED_TWO_ROW_27_EVENT_FROM_T255_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-tied-two-row-27-event-from-t255-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"

BASE_TASK_ID = "B649_T255_25_EVENT_FROM_T261_R1"
BASE_HEAD = "355d6831426deb324c52c8f06c8a3233ffba66d8"
BASE_TREE = "15ca2db51932a7c42a7bfc512008f3b60d5d5b2f"
BASE_PARENT = "ee4bb2f22ff101522e73952a3f11c66c55d95098"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-t255-25-event-from-t261-r1-result.json"
)
BASE_RESULT_SHA256 = "fce1eeb472655b97ae7d0a387b00f6df0e056bb51c94cf5cfb69b75c5057e633"
BASE_FULL_DIGEST = "aea35e031ad93a75ba499173e0810db421e76bb95181e58ebe1ac9e808ac2010"
BASE_BOUNDS_DIGEST = "429bdb7937db7d5b8e5656a2dd0362b3c678fb4526d29978ef2dc8f45acdd611"

DONOR_TASK_ID = "B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1"
DONOR_HEAD = "ba4bb2b678d62364e4383962763d8ac38c5b303b"
DONOR_TREE = "a661bade7aa610d70f920850c87aec72009c5781"
DONOR_PARENT = "ee4bb2f22ff101522e73952a3f11c66c55d95098"
DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-next-tied-resolved-frontier-math-r1-result.json"
)
DONOR_RESULT_SHA256 = "5b5834e003dc52daabdf72acf872f8fce83184030b7ed40f139b686d6836c1b2"
DONOR_RESULT_FILE_SHA256 = "89c9fda3d3526285677e81867161f0fdeefa6f00a84779e1ccdd5f7cb96c1180"
DONOR_SOURCE_PATH = "src/lottolab/research/b649_next_tied_resolved_frontier_math_r1.py"
DONOR_SOURCE_SHA256 = "735a64b67d6a375322c00152662573b1d6ba0785d855c7d5db2668565259b53d"
DONOR_TEST_PATH = "tests/unit/test_b649_next_tied_resolved_frontier_math_r1.py"
DONOR_TEST_SHA256 = "c8a3d16bf01924b5a11ef9d0572389677d0f5c5e7af2187c52f6411e2396ab79"
DONOR_PROOF_REPORT = "docs/research/B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1.md"
DONOR_PROOF_SHA256 = "3e20d8083ee2f26e93f569dcabe0ff1df41f10e2d76db2b1d5b9c2c2714c32b2"
DONOR_WORKER_REPORT = (
    "docs/research/B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1_WORKER_REPORT.md"
)
DONOR_WORKER_REPORT_SHA256 = (
    "f14811e6a18962bf4e336bc57e8d4b30ada3b8f2738d95cec5cbad8febd1964b"
)

JUDGE_TASK_ID = "B649_NEXT_TIED_FRONTIER_FRESH_MATH_JUDGE_R1"
JUDGE_SESSION_ID = "223bbd67-1a36-4f14-86e0-8a4c320b5a43"
JUDGE_REPORT_PATH = (
    "/var/folders/tm/ft7d03r14b35h16hbjkjppbs_jv8xm/T/"
    "b649-fresh-judge-momp21p1/B649_FRESH_CONTEXT_MATHEMATICAL_JUDGE_R1.md"
)
JUDGE_REPORT_SHA256 = "5b94b3f3de5dded9256004ea253e410fa8c5b9644bfded2d5f68774af25ce8ea"
JUDGE_VERDICT = "VERIFIED_WITH_CAVEATS"

PROFILE_A_ID = "65555555555442000000"
A_OLD_CAP = 266
A_SEPARATE_NB_CAP = 269
A_NEW_CAP = 224
A_OLD_BOUND = 313_392_232
A_NEW_BOUND = 313_015_432
A_OWNER_DELTA = 376_800
A_TERM_COUNT = 203
A_DOMAIN = "T=22..224"
A_ARGMAX_T = 224

PROFILE_B_ID = "66555555554433000000"
B_OLD_CAP = 266
B_NEW_CAP = 222
B_OLD_BOUND = 313_392_232
B_NEW_BOUND = 312_995_528
B_OWNER_DELTA = 396_704
B_TERM_COUNT = 201
B_DOMAIN = "T=22..222"
B_ARGMAX_T = 222

CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
CURSOR_COUNT = 197

EXPECTED_FAMILY_BOUND = 313_394_584
EXPECTED_FAMILY_GAIN = 0
EXPECTED_NEXT_BOUND = 313_392_128
EXPECTED_NEXT_OWNERS = ["66655555554432000000"]
NEW_MAX_RESOLVED_BOUND = 313_392_128
NEW_MAX_RESOLVED_OWNERS = ["66655555554432000000"]
NEXT_DISTINCT_RESOLVED_BOUND = 313_391_844
NEXT_DISTINCT_RESOLVED_OWNERS = [
    "65555555555531100000",
    "66555555554441100000",
    "66555555555422100000",
]

NEW_FULL_DIGEST = "869a3ccfb20535694b6e6c842337bd69290a6a45f77e326f9264ab9b273ef767"
NEW_BOUNDS_DIGEST = "e897ee98b83d166a40471a6449cd9f6b38652f376e669bc221b8f0010b05d472"

UNADOPTED_197_PROFILE_CLASS_BOUND = 313_258_872
PROSPECTIVE_FAMILY_WITH_NEW_CLASS = 313_392_128
PROSPECTIVE_STATUS = "PROSPECTIVE_ONLY_NOT_ADOPTED"

four = base.four
Row = four.Row


@dataclass(frozen=True)
class DonorSpec:
    event_id: str
    task_id: str
    profile_id: str
    previous_bound: int
    previous_cap: int
    bound: int
    cap: int
    s4_base: int
    term_count: int
    argmax_t: int
    cert_index: int
    caveat: str
    head: str = DONOR_HEAD
    tree: str = DONOR_TREE
    parent: str = DONOR_PARENT
    result_path: str = DONOR_RESULT_PATH
    result_sha256: str = DONOR_RESULT_SHA256
    source_path: str = DONOR_SOURCE_PATH
    source_sha256: str = DONOR_SOURCE_SHA256
    test_path: str = DONOR_TEST_PATH
    test_sha256: str = DONOR_TEST_SHA256
    proof_sha256: str = DONOR_PROOF_SHA256


DONOR_A = DonorSpec(
    event_id="T224_65555555555442000000",
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_A_ID,
    previous_bound=A_OLD_BOUND,
    previous_cap=A_OLD_CAP,
    bound=A_NEW_BOUND,
    cap=A_NEW_CAP,
    s4_base=112,
    term_count=A_TERM_COUNT,
    argmax_t=A_ARGMAX_T,
    cert_index=0,
    caveat="NJ-01_PROFILE_A_SOURCE_CAP_CATALOG_266_NOT_RAW_NB_LEMMA_269",
)

DONOR_B = DonorSpec(
    event_id="T222_66555555554433000000",
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_B_ID,
    previous_bound=B_OLD_BOUND,
    previous_cap=B_OLD_CAP,
    bound=B_NEW_BOUND,
    cap=B_NEW_CAP,
    s4_base=112,
    term_count=B_TERM_COUNT,
    argmax_t=B_ARGMAX_T,
    cert_index=1,
    caveat="NONE",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_text(*args: str) -> str:
    output = four.run_git(ROOT, *args)
    if not isinstance(output, str):
        raise ValueError("expected text output from git")
    return output


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(message) from exc
    require(isinstance(value, dict), message)
    return cast(dict[str, Any], value)


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def validate_base_provenance(head: str, tree: str, parent: str, result_sha256: str) -> None:
    require(head == BASE_HEAD, "25-event base commit mismatch")
    require(tree == BASE_TREE, "25-event base tree mismatch")
    require(parent == BASE_PARENT, "25-event base parent mismatch")
    require(result_sha256 == BASE_RESULT_SHA256, "25-event base result SHA256 mismatch")


def verify_candidate_ancestry() -> str:
    head = git_text("rev-parse", "HEAD")
    if head == BASE_HEAD:
        require(
            git_text("rev-parse", "HEAD^{tree}") == BASE_TREE,
            "candidate base tree mismatch",
        )
    else:
        parents = git_text("rev-list", "--parents", "-n", "1", head).split()
        require(parents == [head, BASE_HEAD], "candidate must be one commit over the fixed base")
    return head


def verify_base_replay() -> tuple[
    dict[str, Any],
    dict[str, Row],
    dict[str, Row],
    bytes,
]:
    four.verify_commit(ROOT, BASE_HEAD, BASE_TREE)
    parents = git_text("rev-list", "--parents", "-n", "1", BASE_HEAD).split()
    require(parents == [BASE_HEAD, BASE_PARENT], "25-event base ancestry mismatch")
    raw = four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    validate_base_provenance(BASE_HEAD, BASE_TREE, parents[1], sha256(raw))
    require((ROOT / BASE_RESULT_PATH).read_bytes() == raw, "25-event base result bytes mismatch")

    orig_ancestry = base.verify_candidate_ancestry
    base.verify_candidate_ancestry = lambda: BASE_HEAD
    try:
        result, frozen_rows, _base_rows_24, after_25 = base.build_candidate()
    finally:
        base.verify_candidate_ancestry = orig_ancestry
    require(
        base.serialize_result(result) == raw
        and result.get("TASK_ID") == BASE_TASK_ID
        and len(result.get("EVENT_HISTORY", [])) == 25
        and result.get("TOTAL_EVENTS") == 25
        and result.get("ROWS_AFTER") == 4_647,
        "complete 25-event Base replay mismatch",
    )
    full = four.seven.two.full_digest(after_25)
    bounds = four.seven.two.bounds_digest(after_25)
    require(
        (len(frozen_rows), len(after_25), full, bounds)
        == (4_647, 4_647, BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        and (result.get("FULL_DIGEST"), result.get("BOUNDS_DIGEST")) == (full, bounds),
        "25-event Base row count or digest replay mismatch",
    )
    return result, frozen_rows, after_25, raw


def resolve_proof_locator(
    root: Path, locator: str, expected_profile_id: str | None = None
) -> str:
    match = re.fullmatch(
        r"git:([0-9a-f]{40})@([0-9a-f]{40}):([^#]+)#([^:]+):sha256=([0-9a-f]{64})",
        locator,
    )
    if match is None:
        raise ValueError("proof locator is malformed")
    head, tree, path, fragment, expected_sha = match.groups()
    four.verify_commit(root, head, tree)
    raw = four.committed_blob(root, head, path)
    if path.endswith(".json"):
        record = json_object(raw, "proof locator result is invalid JSON")
        require(
            record.get("PROOF_SHA256") == expected_sha,
            "proof locator SHA256 does not match PROOF_SHA256",
        )
        if fragment.startswith("CERTIFICATES[") and fragment.endswith("]"):
            idx = int(fragment[len("CERTIFICATES[") : -1])
            cert_val = record["CERTIFICATES"][idx]
            cert = cast(dict[str, Any], cert_val)
            source_id = cast(dict[str, Any], cert["SOURCE_IDENTITY"])
            if expected_profile_id is not None:
                require(
                    source_id["PROFILE_ID"] == expected_profile_id,
                    "proof locator profile mismatch",
                )
        proof_report = four.committed_blob(root, head, DONOR_PROOF_REPORT)
        require(sha256(proof_report) == expected_sha, "committed proof report SHA256 mismatch")
    elif path.endswith(".md"):
        require(sha256(raw) == expected_sha, "committed markdown proof SHA256 mismatch")
    else:
        raise ValueError(f"unsupported proof path: {path}")
    return expected_sha


def verify_judge_report() -> dict[str, Any]:
    report_path = Path(JUDGE_REPORT_PATH)
    raw = report_path.read_bytes()
    require(sha256(raw) == JUDGE_REPORT_SHA256, "fresh-context Judge report SHA256 mismatch")
    report = raw.decode("utf-8")
    required_lines = (
        f"TASK_ID: {JUDGE_TASK_ID}",
        "OVERALL_FRESH_CONTEXT_VERDICT: VERIFIED_WITH_CAVEATS",
        f"REVIEWED_HEAD: {DONOR_HEAD}",
        f"REVIEWED_TREE: {DONOR_TREE}",
        f"RESULT_SHA256: {DONOR_RESULT_SHA256}",
        f"RESULT_FILE_SHA256: {DONOR_RESULT_FILE_SHA256}",
        f"PROFILE_A: {PROFILE_A_ID}",
        f"PROVED_T_CAP_A: {A_NEW_CAP}",
        f"NEW_BOUND_A: {A_NEW_BOUND}",
        f"OWNER_DELTA_A: {A_OWNER_DELTA}",
        f"PROFILE_B: {PROFILE_B_ID}",
        f"PROVED_T_CAP_B: {B_NEW_CAP}",
        f"NEW_BOUND_B: {B_NEW_BOUND}",
        f"OWNER_DELTA_B: {B_OWNER_DELTA}",
    )
    require(
        all(line in report for line in required_lines),
        "Judge report reviewed identity mismatch",
    )
    return {
        "TASK_ID": JUDGE_TASK_ID,
        "SESSION_ID": JUDGE_SESSION_ID,
        "REPORT_PATH": JUDGE_REPORT_PATH,
        "REPORT_SHA256": JUDGE_REPORT_SHA256,
        "JUDGE_MODE": "FRESH_CONTEXT",
        "VERDICT": JUDGE_VERDICT,
        "REVIEWED_HEAD": DONOR_HEAD,
        "REVIEWED_TREE": DONOR_TREE,
        "DONOR_RESULT_SHA256": DONOR_RESULT_SHA256,
        "DONOR_RESULT_FILE_SHA256": DONOR_RESULT_FILE_SHA256,
        "PROFILE_A": {
            "PROFILE_ID": PROFILE_A_ID,
            "PROVED_T_CAP": A_NEW_CAP,
            "NEW_BOUND": A_NEW_BOUND,
            "OWNER_DELTA": A_OWNER_DELTA,
            "VERDICT": "VERIFIED_WITH_CAVEATS",
            "CAVEAT": "NJ-01_PROFILE_A_SOURCE_CAP_CATALOG_266_NOT_RAW_NB_LEMMA_269",
        },
        "PROFILE_B": {
            "PROFILE_ID": PROFILE_B_ID,
            "PROVED_T_CAP": B_NEW_CAP,
            "NEW_BOUND": B_NEW_BOUND,
            "OWNER_DELTA": B_OWNER_DELTA,
            "VERDICT": "VERIFIED",
            "CAVEAT": "NONE",
        },
        "NON_BLOCKING_CAVEAT": (
            "NJ-01: Profile A source cap 266 from catalog, separate NB lemma gives 269"
        ),
    }


def validate_donor_record(
    record: Mapping[str, Any], source_raw: bytes, spec: DonorSpec
) -> tuple[dict[str, Any], str]:
    require(
        record.get("TASK_ID") == spec.task_id,
        "donor task mismatch",
    )
    require(
        record.get("PROOF_SHA256") == spec.proof_sha256,
        "donor proof SHA256 mismatch",
    )
    raw_certificates_obj = record.get("CERTIFICATES")
    if not isinstance(raw_certificates_obj, list):
        raise ValueError(f"donor certificate list missing: {type(raw_certificates_obj)}")
    raw_certificates = cast(list[object], raw_certificates_obj)
    if len(raw_certificates) <= spec.cert_index:
        raise ValueError(f"donor certificate missing at index {spec.cert_index}")
    raw_cert: object = raw_certificates[spec.cert_index]
    if not isinstance(raw_cert, dict):
        raise ValueError("donor certificate is not a dict")
    cert = cast(dict[str, Any], raw_cert)
    raw_source_identity = cert.get("SOURCE_IDENTITY")
    if not isinstance(raw_source_identity, dict):
        raise ValueError("donor source identity is not a dict")
    source_identity = cast(dict[str, Any], raw_source_identity)

    require(
        source_identity.get("PROFILE_ID") == spec.profile_id,
        "donor certificate profile mismatch",
    )
    require(
        source_identity.get("ORIGINAL_CAP") == spec.previous_cap,
        "donor original cap mismatch",
    )
    require(
        source_identity.get("OLD_BOUND") == spec.previous_bound,
        "donor original bound mismatch",
    )
    require(
        cert.get("PROVED_T_CAP") == spec.cap,
        "donor proved cap mismatch",
    )
    require(
        cert.get("NEW_BOUND") == spec.bound,
        "donor new bound mismatch",
    )
    require(
        cert.get("OWNER_DELTA") == spec.previous_bound - spec.bound,
        "donor owner delta mismatch",
    )
    require(
        cert.get("ROUTE_B_TERM_COUNT") == spec.term_count,
        "donor Route-B term count mismatch",
    )
    require(
        cert.get("PROOF_SCOPE") == "FULL_PROFILE",
        "donor proof scope changed",
    )
    terms_value = cert.get("ROUTE_B_TERMS")
    argmax_value = cert.get("ARGMAX_TERM")
    if not isinstance(terms_value, list) or not terms_value:
        raise ValueError("Route-B term list is missing")
    if not isinstance(argmax_value, list):
        raise ValueError("Route-B argmax is missing")
    terms = cast(list[list[Any]], terms_value)
    argmax = cast(list[Any], argmax_value)
    require(
        len(terms) == spec.term_count
        and terms[0][0] == 22
        and terms[-1][0] == spec.argmax_t
        and argmax[:2] == [spec.argmax_t, spec.bound],
        "Route-B domain or argmax mismatch",
    )
    proof_locator = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f"#CERTIFICATES[{spec.cert_index}]:sha256={spec.proof_sha256}"
    )
    return cert, proof_locator


def verify_donor(
    base_rows: Mapping[str, Row], spec: DonorSpec
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    four.verify_commit(ROOT, spec.head, spec.tree)
    parents = git_text("rev-list", "--parents", "-n", "1", spec.head).split()
    require(parents == [spec.head, spec.parent], "donor parent mismatch")
    paths = {
        "RESULT": spec.result_path,
        "SOURCE": spec.source_path,
        "TEST": spec.test_path,
        "PROOF_REPORT": DONOR_PROOF_REPORT,
    }
    blobs = {key: four.committed_blob(ROOT, spec.head, path) for key, path in paths.items()}
    require(
        sha256(blobs["RESULT"]) == DONOR_RESULT_FILE_SHA256,
        "donor result file SHA256 mismatch",
    )
    require(sha256(blobs["SOURCE"]) == spec.source_sha256, "donor source SHA256 mismatch")
    require(sha256(blobs["TEST"]) == spec.test_sha256, "donor test SHA256 mismatch")
    require(
        sha256(blobs["PROOF_REPORT"]) == spec.proof_sha256,
        "donor proof report SHA256 mismatch",
    )

    record = json_object(blobs["RESULT"], "donor result is invalid JSON")
    require(
        record.get("RESULT_SHA256") == spec.result_sha256,
        "donor canonical RESULT_SHA256 mismatch",
    )
    _cert, proof_locator = validate_donor_record(record, blobs["SOURCE"], spec)
    row = base_rows.get(spec.profile_id)
    if row is None:
        raise ValueError(f"Base omitted profile {spec.profile_id}")
    require(
        (row.bound, row.cap, row.s4_base) == (spec.previous_bound, spec.previous_cap, spec.s4_base),
        f"Base row does not match pinned before state: {spec.profile_id}",
    )
    if spec.profile_id == PROFILE_A_ID:
        require(
            row.cap == 266 and A_SEPARATE_NB_CAP == 269,
            "Profile A before-cap must match Base catalog cap 266, not separate NB lemma 269",
        )

    judge = verify_judge_report()
    resolved_sha = resolve_proof_locator(ROOT, proof_locator, spec.profile_id)
    require(resolved_sha == spec.proof_sha256, "donor proof locator resolution mismatch")

    caveat_entry = f";CAVEAT={spec.caveat}" if spec.caveat != "NONE" else ""
    row_source = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f";RESULT_SHA256={spec.result_sha256}"
        f";SOURCE_SHA256={spec.source_sha256}"
        f";JUDGE_REPORT_SHA256={judge['REPORT_SHA256']}"
        f";JUDGE_TASK_ID={judge['TASK_ID']}"
        f";JUDGE_SESSION_ID={judge['SESSION_ID']}"
        f";JUDGE_VERDICT={judge['VERDICT']}"
        f"{caveat_entry}"
        f"#CERTIFICATES[{spec.cert_index}]:sha256={spec.proof_sha256}"
    )

    identity: dict[str, Any] = {
        "EVENT_ID": spec.event_id,
        "TASK_ID": spec.task_id,
        "HEAD": spec.head,
        "TREE": spec.tree,
        "PARENT": spec.parent,
        "HEAD_TREE": "MATCH",
        "RESULT_PATH": spec.result_path,
        "RESULT_SHA256": spec.result_sha256,
        "RESULT_FILE_SHA256": sha256(blobs["RESULT"]),
        "SOURCE_PATH": spec.source_path,
        "SOURCE_SHA256": sha256(blobs["SOURCE"]),
        "TEST_PATH": spec.test_path,
        "TEST_SHA256": sha256(blobs["TEST"]),
        "PROOF_REPORT_PATH": DONOR_PROOF_REPORT,
        "PROOF_SHA256": spec.proof_sha256,
        "PROFILE_ID": spec.profile_id,
        "CAP_BEFORE": spec.previous_cap,
        "BOUND_BEFORE": spec.previous_bound,
        "CAP_AFTER": spec.cap,
        "BOUND_AFTER": spec.bound,
        "S4_BASE": spec.s4_base,
        "OWNER_DELTA": spec.previous_bound - spec.bound,
        "WORKER_JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROOF_LOCATOR": proof_locator,
        "JUDGE_REPORT_SHA256": judge["REPORT_SHA256"],
        "ROW_SOURCE": row_source,
        "FRESH_CONTEXT_JUDGE": judge,
        "CAVEAT": spec.caveat,
    }
    require(
        f"RESULT_SHA256={spec.result_sha256}" in row_source
        and f"SOURCE_SHA256={spec.source_sha256}" in row_source
        and f"JUDGE_REPORT_SHA256={judge['REPORT_SHA256']}" in row_source
        and f"#CERTIFICATES[{spec.cert_index}]:sha256={spec.proof_sha256}" in row_source,
        "Row.source is not bound to result/source/Judge evidence",
    )
    return record, identity, blobs


def expected_family() -> dict[str, Any]:
    return {
        "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
        "TIED_OWNERS": [CURSOR_ID],
        "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
        "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNERS,
        "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
    }


def expect_rejected(action: Any, message: str) -> str:
    try:
        action()
    except (ValueError, AssertionError, KeyError, subprocess.CalledProcessError):
        return "PASS"
    raise AssertionError(message)


def verify_negative_cases(
    frozen_rows: Mapping[str, Row],
    donor_record: Mapping[str, Any],
    donor_source: bytes,
    base_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    family_result: Mapping[str, Any],
) -> dict[str, str]:
    unrelated = next(
        profile_id
        for profile_id in after_rows
        if profile_id not in (PROFILE_A_ID, PROFILE_B_ID)
    )
    changed_rows = dict(after_rows)
    changed_rows[unrelated] = replace(changed_rows[unrelated], source="unrelated-row-mutation")
    missing_cursor = dict(family_result)
    missing_cursor.pop("CURSOR", None)

    wrong_donor_head = replace(DONOR_A, head="0" * 40)
    wrong_donor_tree = replace(DONOR_A, tree="0" * 40)
    wrong_donor_sha = replace(DONOR_A, result_sha256="0" * 64)
    wrong_donor_parent = replace(DONOR_A, parent="0" * 40)
    wrong_profile = replace(DONOR_A, profile_id="0" * 20)
    wrong_bound_before = replace(DONOR_A, previous_bound=A_OLD_BOUND + 1)
    wrong_cap_before_269 = replace(DONOR_A, previous_cap=269)
    wrong_new_cap = replace(DONOR_A, cap=A_NEW_CAP + 1)
    wrong_new_bound = replace(DONOR_A, bound=A_NEW_BOUND + 1)

    bad_locator = (
        f"git:{DONOR_HEAD}@{DONOR_TREE}:{DONOR_RESULT_PATH}"
        f"#CERTIFICATES[0]:sha256={'0' * 64}"
    )

    events = [{"EVENT_ID": f"EVENT_{index}"} for index in range(27)]

    def check_wrong_donor_head_tree() -> None:
        verify_donor(base_rows, wrong_donor_head)
        verify_donor(base_rows, wrong_donor_tree)

    return {
        "WRONG_BASE_REJECTED": expect_rejected(
            lambda: validate_base_provenance(
                "0" * 40, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256
            ),
            "wrong base was accepted",
        ),
        "WRONG_DONOR_HEAD_TREE_REJECTED": expect_rejected(
            check_wrong_donor_head_tree,
            "wrong donor head/tree was accepted",
        ),
        "WRONG_DONOR_RESULT_SHA_REJECTED": expect_rejected(
            lambda: verify_donor(base_rows, wrong_donor_sha),
            "wrong donor result SHA was accepted",
        ),
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, wrong_profile),
            "wrong profile was accepted",
        ),
        "WRONG_ORIGINAL_ROW_BOUND_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, wrong_bound_before),
            "wrong original row bound was accepted",
        ),
        "PROFILE_A_WRONG_CATALOG_CAP_269_REJECTED": expect_rejected(
            lambda: verify_donor(base_rows, wrong_cap_before_269),
            "A catalog cap wrongly set to 269 was accepted",
        ),
        "WRONG_NEW_CAP_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, wrong_new_cap),
            "wrong new cap was accepted",
        ),
        "WRONG_NEW_BOUND_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, wrong_new_bound),
            "wrong new bound was accepted",
        ),
        "WRONG_PROOF_LOCATOR_REJECTED": expect_rejected(
            lambda: resolve_proof_locator(ROOT, bad_locator),
            "wrong proof locator was accepted",
        ),
        "DUPLICATE_EVENT_REJECTED": expect_rejected(
            lambda: sixteen.verify_unique_events([*events, events[-1]]),
            "duplicate event was accepted",
        ),
        "UNRELATED_ROW_MUTATION_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(
                base_rows, changed_rows, {PROFILE_A_ID, PROFILE_B_ID}
            ),
            "unrelated row mutation was accepted",
        ),
        "CURSOR_OMISSION_REJECTED": expect_rejected(
            lambda: four.verify_family_summary(missing_cursor, expected_family()),
            "omitted unresolved cursor was accepted",
        ),
        "WRONG_EVENT_ANCESTRY_REJECTED": expect_rejected(
            lambda: verify_donor(base_rows, wrong_donor_parent),
            "wrong event ancestry was accepted",
        ),
    }


def build_candidate() -> tuple[
    dict[str, Any],
    dict[str, Row],
    dict[str, Row],
    dict[str, Row],
]:
    verify_candidate_ancestry()
    base_result, frozen_rows, base_rows, base_raw = verify_base_replay()

    record_a, identity_a, blobs_a = verify_donor(base_rows, DONOR_A)
    _record_b, identity_b, _blobs_b = verify_donor(base_rows, DONOR_B)

    pin_a = nine.DonorPin(
        event_id=DONOR_A.event_id,
        task_id=DONOR_A.task_id,
        profile_id=DONOR_A.profile_id,
        previous_bound=DONOR_A.previous_bound,
        previous_cap=DONOR_A.previous_cap,
        bound=DONOR_A.bound,
        cap=DONOR_A.cap,
        s4_base=DONOR_A.s4_base,
        head=DONOR_A.head,
        tree=DONOR_A.tree,
        result_path=DONOR_A.result_path,
        result_sha256=DONOR_A.result_sha256,
        source_path=DONOR_A.source_path,
        source_sha256=DONOR_A.source_sha256,
        test_path=DONOR_A.test_path,
        test_sha256=DONOR_A.test_sha256,
        proof_sha256=DONOR_A.proof_sha256,
    )
    pin_b = nine.DonorPin(
        event_id=DONOR_B.event_id,
        task_id=DONOR_B.task_id,
        profile_id=DONOR_B.profile_id,
        previous_bound=DONOR_B.previous_bound,
        previous_cap=DONOR_B.previous_cap,
        bound=DONOR_B.bound,
        cap=DONOR_B.cap,
        s4_base=DONOR_B.s4_base,
        head=DONOR_B.head,
        tree=DONOR_B.tree,
        result_path=DONOR_B.result_path,
        result_sha256=DONOR_B.result_sha256,
        source_path=DONOR_B.source_path,
        source_sha256=DONOR_B.source_sha256,
        test_path=DONOR_B.test_path,
        test_sha256=DONOR_B.test_sha256,
        proof_sha256=DONOR_B.proof_sha256,
    )

    family_before = four.family_frontier(base_rows)
    four.verify_family_summary(
        family_before,
        {
            "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
            "TIED_OWNERS": [CURSOR_ID],
            "NEXT_COMPETING_BOUND": 313_392_232,
            "NEXT_COMPETING_OWNERS": [PROFILE_A_ID, PROFILE_B_ID],
            "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        },
    )

    after_26, new_event_a_list = nine.apply_donor_events(
        base_rows, [pin_a], {DONOR_A.event_id: identity_a}
    )
    frontier_26 = four.family_frontier(after_26)
    four.verify_family_summary(
        frontier_26,
        {
            "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
            "TIED_OWNERS": [CURSOR_ID],
            "NEXT_COMPETING_BOUND": 313_392_232,
            "NEXT_COMPETING_OWNERS": [PROFILE_B_ID],
            "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        },
    )

    after_27, new_event_b_list = nine.apply_donor_events(
        after_26, [pin_b], {DONOR_B.event_id: identity_b}
    )
    frontier_27 = four.family_frontier(after_27)
    four.verify_family_summary(frontier_27, expected_family())

    new_events = [*new_event_a_list, *new_event_b_list]
    prior_events = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    events = [*prior_events, *new_events]
    sixteen.verify_unique_events(events)
    require(
        len(prior_events) == 25 and len(new_events) == 2 and len(events) == 27,
        "27-event history must replay 25 events and add exactly two",
    )

    changed_from_base = sixteen.verify_ledger_partition(
        base_rows, after_27, {PROFILE_A_ID, PROFILE_B_ID}
    )
    changed_from_frozen = {
        profile_id for profile_id in frozen_rows if frozen_rows[profile_id] != after_27[profile_id]
    }
    require(
        len(frozen_rows) == len(after_27) == 4_647
        and changed_from_base == {PROFILE_A_ID, PROFILE_B_ID}
        and len(base_rows) - len(changed_from_base) == 4_645
        and len(changed_from_frozen) == 26
        and len(frozen_rows) - len(changed_from_frozen) == 4_621
        and PROFILE_A_ID not in base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"]
        and PROFILE_B_ID not in base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"],
        "27-event changed/unchanged row partition mismatch",
    )

    full_before = four.seven.two.full_digest(base_rows)
    bounds_before = four.seven.two.bounds_digest(base_rows)
    full_after = four.seven.two.full_digest(after_27)
    bounds_after = four.seven.two.bounds_digest(after_27)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "25-event Base digest changed before the two row events",
    )
    require(
        (full_after, bounds_after) == (NEW_FULL_DIGEST, NEW_BOUNDS_DIGEST),
        "recomputed 27-event digests mismatch expected values",
    )

    require(
        family_before["FAMILY_BOUND"] == frontier_27["FAMILY_BOUND"]
        and family_before["FAMILY_BOUND"] - frontier_27["FAMILY_BOUND"] == 0,
        "Owner delta must not be reported as Family gain",
    )

    cursor = cast(dict[str, Any], base_result["CURSOR_AUTHORITY"])
    require(
        cursor.get("ID") == CURSOR_ID
        and cursor.get("BOUND") == CURSOR_BOUND
        and cursor.get("COUNT") == CURSOR_COUNT
        and frontier_27.get("CURSOR") == {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "197-profile unresolved cursor was not preserved",
    )

    resolved_above_incumbent = sum(
        row.bound > base.base.INCUMBENT for row in after_27.values()
    )
    require(resolved_above_incumbent == 1_362, "resolved profile count changed unexpectedly")

    negative = verify_negative_cases(
        frozen_rows,
        record_a,
        blobs_a["SOURCE"],
        base_rows,
        after_27,
        frontier_27,
    )
    require(set(negative.values()) == {"PASS"}, "a negative integration control was accepted")

    transitions = cast(list[dict[str, Any]], base_result["EVENT_FAMILY_TRANSITIONS"])
    transitions_after = [
        *transitions,
        {
            "EVENT_ID": DONOR_A.event_id,
            "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
            "FAMILY_BOUND_AFTER": frontier_26["FAMILY_BOUND"],
            "TIED_OWNERS_AFTER": frontier_26["TIED_OWNERS"],
            "NEXT_COMPETING_BOUND_AFTER": frontier_26["NEXT_COMPETING_BOUND"],
            "NEXT_COMPETING_OWNERS_AFTER": frontier_26["NEXT_COMPETING_OWNERS"],
        },
        {
            "EVENT_ID": DONOR_B.event_id,
            "FAMILY_BOUND_BEFORE": frontier_26["FAMILY_BOUND"],
            "FAMILY_BOUND_AFTER": frontier_27["FAMILY_BOUND"],
            "TIED_OWNERS_AFTER": frontier_27["TIED_OWNERS"],
            "NEXT_COMPETING_BOUND_AFTER": frontier_27["NEXT_COMPETING_BOUND"],
            "NEXT_COMPETING_OWNERS_AFTER": frontier_27["NEXT_COMPETING_OWNERS"],
        },
    ]

    inherited_caveats = [
        *base_result["INHERITED_CAVEATS_PRESERVED"],
        {
            "TASK_ID": JUDGE_TASK_ID,
            "REPORT_SHA256": JUDGE_REPORT_SHA256,
            "PROFILE_ID": PROFILE_A_ID,
            "PROVED_T_CAP": A_NEW_CAP,
            "CAVEAT": "NJ-01: Profile A source cap 266 from catalog, separate NB lemma gives 269",
            "IMPACT": "NON_BLOCKING_SOURCE_PROVENANCE_CAVEAT",
        },
    ]

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_27_EVENT_CANDIDATE_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_FAMILY_ADOPTION": "NOT_ACCEPTED",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
            "BASE_HEAD_TREE": "MATCH",
            "BASE_RESULT_SHA256": "MATCH",
            "BASE_FULL_DIGEST_REPLAY": "MATCH",
            "BASE_BOUNDS_DIGEST_REPLAY": "MATCH",
            "DONOR_HEAD_TREE": "MATCH",
            "DONOR_PARENT": "MATCH",
            "DONOR_RESULT_SHA256": "MATCH",
            "DONOR_RESULT_FILE_SHA256": "MATCH",
            "DONOR_SOURCE_SHA256": "MATCH",
            "DONOR_TEST_SHA256": "MATCH",
            "DONOR_PROOF_LOCATORS": "RESOLVED",
            "DONOR_JUDGE_REPORT_SHA256": "MATCH",
            "DONOR_JUDGE_BINDING": "MATCH",
        },
        "FROZEN_AUTHORITY": base_result["FROZEN_AUTHORITY"],
        "BASE_25_EVENT_AUTHORITY": {
            "TASK_ID": base_result["TASK_ID"],
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PARENT": BASE_PARENT,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "FULL_DIGEST": full_before,
            "BOUNDS_DIGEST": bounds_before,
            "EVENTS": len(prior_events),
            "REPLAY_MATCH": "YES",
            "FORMAL_AUTHORITY": base_result["FORMAL_FAMILY_AUTHORITY"],
        },
        "DONOR_A_IDENTITY": identity_a,
        "DONOR_B_IDENTITY": identity_b,
        "UPSTREAM_25_EVENT_JUDGE_MODE": base_result["JUDGE_MODE"],
        "UPSTREAM_25_EVENT_FORMAL_AUTHORITY": base_result["FORMAL_FAMILY_AUTHORITY"],
        "SCIENCE_JUDGE": identity_a["FRESH_CONTEXT_JUDGE"],
        "INHERITED_CAVEATS_PRESERVED": inherited_caveats,
        "PROFILE_A": {
            "PROFILE_ID": PROFILE_A_ID,
            "OLD_CAP": A_OLD_CAP,
            "SEPARATE_NB_CAP": A_SEPARATE_NB_CAP,
            "NEW_CAP": A_NEW_CAP,
            "OLD_BOUND": A_OLD_BOUND,
            "NEW_BOUND": A_NEW_BOUND,
            "OWNER_DELTA": A_OWNER_DELTA,
            "TERM_COUNT": A_TERM_COUNT,
            "DOMAIN": A_DOMAIN,
            "CAP_PROVENANCE_VERIFIED": "YES",
            "CAVEAT": "NJ-01_PROFILE_A_SOURCE_CAP_CATALOG_266_NOT_RAW_NB_LEMMA_269",
        },
        "PROFILE_B": {
            "PROFILE_ID": PROFILE_B_ID,
            "OLD_CAP": B_OLD_CAP,
            "NEW_CAP": B_NEW_CAP,
            "OLD_BOUND": B_OLD_BOUND,
            "NEW_BOUND": B_NEW_BOUND,
            "OWNER_DELTA": B_OWNER_DELTA,
            "TERM_COUNT": B_TERM_COUNT,
            "DOMAIN": B_DOMAIN,
            "CAP_PROVENANCE_VERIFIED": "YES",
            "CAVEAT": "NONE",
        },
        "OWNER_DELTA_SUM": A_OWNER_DELTA + B_OWNER_DELTA,
        "ROWS_BEFORE": len(frozen_rows),
        "ROWS_AFTER": len(after_27),
        "OLD_EVENTS": len(prior_events),
        "PREVIOUS_EVENTS": len(prior_events),
        "NEW_EVENTS": len(new_events),
        "TOTAL_EVENTS": len(events),
        "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": len(changed_from_frozen),
        "CHANGED_PROFILE_IDS_FROM_FROZEN": sorted(changed_from_frozen),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen_rows) - len(changed_from_frozen),
        "CHANGED_ROWS_FROM_BASE": len(changed_from_base),
        "UNCHANGED_ROWS_FROM_BASE": len(base_rows) - len(changed_from_base),
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "ALL_PROOF_LOCATORS_RESOLVED": "YES",
        "UNRELATED_ROW_MUTATION": "NONE",
        "FULL_DIGEST": full_after,
        "BOUNDS_DIGEST": bounds_after,
        "NEW_FULL_DIGEST": full_after,
        "NEW_BOUNDS_DIGEST": bounds_after,
        "EVENT_HISTORY": events,
        "EVENT_FAMILY_TRANSITIONS": transitions_after,
        "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": frontier_27["FAMILY_BOUND"],
        "FAMILY_GAIN": family_before["FAMILY_BOUND"] - frontier_27["FAMILY_BOUND"],
        "MAX_OWNER": CURSOR_ID,
        "MAX_OWNER_TYPE": "UNRESOLVED_CURSOR",
        "MAXIMIZING_OWNERS": frontier_27["TIED_OWNERS"],
        "NEXT_DISTINCT_BOUND": frontier_27["NEXT_COMPETING_BOUND"],
        "NEXT_DISTINCT_RESOLVED_BOUND": NEXT_DISTINCT_RESOLVED_BOUND,
        "NEXT_DISTINCT_RESOLVED_OWNERS": NEXT_DISTINCT_RESOLVED_OWNERS,
        "MAX_RESOLVED_BOUND": NEW_MAX_RESOLVED_BOUND,
        "MAX_RESOLVED_OWNERS": NEW_MAX_RESOLVED_OWNERS,
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": resolved_above_incumbent,
        "CURSOR_AUTHORITY": cursor,
        "CURSOR_BOUND": cursor["BOUND"],
        "CURSOR_COUNT": cursor["COUNT"],
        "CURSOR_INCLUDED": "YES",
        "UNADOPTED_197_PROFILE_CLASS_BOUND": UNADOPTED_197_PROFILE_CLASS_BOUND,
        "PROSPECTIVE_FAMILY_WITH_NEW_CLASS": PROSPECTIVE_FAMILY_WITH_NEW_CLASS,
        "PROSPECTIVE_FAMILY_WITH_NEW_CLASS_STATUS": PROSPECTIVE_STATUS,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "NEGATIVE_VALIDATIONS": negative,
        "FOCUSED_TEST_PATH": "tests/unit/test_b649_tied_two_row_27_event_from_t255_r1.py",
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    require(
        result["OWNER_DELTA_SUM"] == 773_504
        and result["FAMILY_GAIN"] == 0
        and result["MAX_RESOLVED_BOUND"] == 313_392_128
        and result["PROSPECTIVE_FAMILY_WITH_NEW_CLASS"] == 313_392_128,
        "Owner delta and Family gain were conflated or maximum incorrect",
    )
    encoded = serialize_result(result)
    json_object(encoded, "27-event result serialization is invalid JSON")
    result_path = ROOT / RESULT_PATH
    if result_path.exists():
        require(result_path.read_bytes() == encoded, "persisted result payload drift")
    else:
        result_path.write_bytes(encoded)
    return result, frozen_rows, base_rows, after_27


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="persist result JSON artifact",
    )
    args = parser.parse_args()
    result, _frozen, _base_rows, _after = build_candidate()
    encoded = serialize_result(result)
    if args.write:
        (ROOT / RESULT_PATH).write_bytes(encoded)
        print(f"Wrote {RESULT_PATH}")
    else:
        print(
            f"Candidate built: FAMILY_BOUND={result['FAMILY_BOUND_AFTER']} "
            f"MAX_RESOLVED={result['MAX_RESOLVED_BOUND']} "
            f"DIGESTS={result['FULL_DIGEST'][:12]}/{result['BOUNDS_DIGEST'][:12]}"
        )


if __name__ == "__main__":
    main()
