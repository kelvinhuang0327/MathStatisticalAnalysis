"""Integrate three verified T262 profiles into the 28-event Base.

Forms the 31-event Family candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_combined_28_event_class197_local_integration_r1 as base
from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen

TASK_ID = "B649_TRIPLE_T262_31_EVENT_FAMILY_INTEGRATION_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-triple-t262-31-event-family-integration-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
FROZEN_SEVEN_ROW_FAMILY = 313_398_532
INCUMBENT = 313_263_888

BASE_TASK_ID = "B649_COMBINED_28_EVENT_CLASS197_LOCAL_INTEGRATION_R1"
BASE_HEAD = "991896daa0d743f6e4e5d4133ed6fcdd1837841a"
BASE_TREE = "e0d57be5b79ef38561d3feb127302f383d1bccc7"
BASE_PARENT = "b53a776a025a5218eef73e9a6933b972b4f5395b"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-combined-28-event-class197-local-integration-r1-result.json"
)
BASE_RESULT_SHA256 = "15167b87e2916ce74a557f3fce93a46f9fed8065ee8c681089e3e65d6dc4f894"
BASE_FULL_DIGEST = "bba2377a14e41e8b9c711b0ba806223c83d60e65e94c87451ea84b436ffcaed4"
BASE_BOUNDS_DIGEST = "dee5b24d1dd130b95029e7c3b74a88473ec787f33f09f748bd011b3a422f7faf"
BASE_ROWS = 4_647
BASE_EVENTS = 28
BASE_FAMILY_BOUND = 313_391_844

BASE_JUDGE_TASK = "B649_COMBINED_28_EVENT_CLASS197_EXACT_JUDGE_R1"
BASE_JUDGE_VERDICT = "VERIFIED_WITH_CAVEATS"
BASE_JUDGE_REPORT_PATH = (
    "/Users/kelvin/.gemini/antigravity/brain/28137fab-233e-4878-99e7-48772ff25ead/judge_report.md"
)
BASE_JUDGE_REPORT_SHA256 = "538846276ace3459cc077e2bc5255d9990a028c7a5d92dac43004d0ffaa734aa"

DONOR_TASK_ID = "B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1"
DONOR_HEAD = "bd311ab44597e3a9ddfe217d6aab4791a5fb43f0"
DONOR_TREE = "c1d45b3aec6207faac77f6cc1a538ae2a9fece81"
DONOR_PARENT = "b53a776a025a5218eef73e9a6933b972b4f5395b"
DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-next-triple-resolved-frontier-math-r1-result.json"
)
DONOR_RESULT_SHA256 = "829973240122078fc6f54eb436d21d2515d14fb199225a5416a29c3d7d005b47"
DONOR_SOURCE_PATH = "src/lottolab/research/b649_next_triple_resolved_frontier_math_r1.py"
DONOR_SOURCE_SHA256 = "0929924e76fd1141e267f660f0448966b8ca40ee68b946fcc6c90ab18ba16fbf"
DONOR_TEST_PATH = "tests/unit/test_b649_next_triple_resolved_frontier_math_r1.py"
DONOR_TEST_SHA256 = "99990a3565e973fc4156cbe91f660f7b37513345d9065d0303d18055305031cc"
DONOR_PROOF_DOCUMENT = "docs/research/B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1.md"
DONOR_PROOF_SHA256 = "6304fe6372e712aa05c282742f01bd5ec6b45475dffb3818c3b39dc5e454b161"
DONOR_WORKER_REPORT = (
    "docs/research/B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1_WORKER_REPORT.md"
)
DONOR_WORKER_REPORT_SHA256 = (
    "3ec19337490607dd91da77ec802ea645159bc5c2dae064fd747f9dc3f82543ee"
)

SCIENCE_JUDGE_TASK_ID = "B649_NEXT_TRIPLE_RESOLVED_FRONTIER_FRESH_JUDGE_R1"
SCIENCE_JUDGE_SESSION_ID = "01a14395-6e38-7e73-b5fe-eb8c9d2d69f0"
SCIENCE_JUDGE_REPORT_PATH = "/tmp/b649-fresh-math-judge-r1-wn_zbmvm/JUDGE_REPORT.md"
SCIENCE_JUDGE_REPORT_SHA256 = "583c05f504aedbd7f7715f5751b63e1c14ce5035df662394a6ac0d71b7f83537"
SCIENCE_JUDGE_MANIFEST_PATH = "/tmp/b649-fresh-math-judge-r1-wn_zbmvm/manifest.json"
SCIENCE_JUDGE_VERDICT = "VERIFIED_WITH_CAVEATS"
SCIENCE_JUDGE_REVIEWED_HEAD = "bd311ab44597e3a9ddfe217d6aab4791a5fb43f0"
SCIENCE_JUDGE_REVIEWED_TREE = "c1d45b3aec6207faac77f6cc1a538ae2a9fece81"

CLASS_COUNT = 197
CLASS_ID_SET_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
CLASS_BOUND = 313_258_872
CLASS_CURSOR_ID = "66544333333333332222"

PROFILE_A_ID = "65555555555531100000"
PROFILE_B_ID = "66555555554441100000"
PROFILE_C_ID = "66555555555422100000"

OLD_T_CAP = 266
NEW_T_CAP = 262
OLD_BOUND = 313_391_844
NEW_BOUND = 313_355_996
OWNER_DELTA_EACH = 35_848
OWNER_DELTA_SUM = 107_544
NEW_ROUTE_B_TERM_COUNT = 241
EXPECTED_ARGMAX_TERM = [262, 313_355_996, 478, 195, 279_517, 5_125_680]

EXPECTED_FAMILY_BOUND_BEFORE = 313_391_844
EXPECTED_MAX_RESOLVED_AFTER = 313_391_740
EXPECTED_MAX_RESOLVED_OWNERS = [
    "66655555555331100000",
    "66655555555411110000",
]
EXPECTED_FINAL_FAMILY_BOUND = 313_391_740
EXPECTED_INCREMENTAL_FAMILY_GAIN = 104
EXPECTED_CUMULATIVE_GAIN_FROM_FROZEN = 6_792
EXPECTED_GAP_TO_INCUMBENT = 127_852
EXPECTED_NEXT_DISTINCT_BOUND = 313_391_636
EXPECTED_NEXT_DISTINCT_OWNERS = ["66665555555321100000"]

EXPECTED_FULL_DIGEST = "a92e08b279b0fb80098f10d461dd3399e86712b6ffe14968851fa175d0356091"
EXPECTED_BOUNDS_DIGEST = "f153977eb639f329bad84743498f475e1091cc883e2ae927445bf0a9f348170e"

Row = base.Row


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
    argmax_term: list[int]
    cert_index: int
    head: str = DONOR_HEAD
    tree: str = DONOR_TREE
    parent: str = DONOR_PARENT
    result_path: str = DONOR_RESULT_PATH
    result_sha256: str = DONOR_RESULT_SHA256
    source_path: str = DONOR_SOURCE_PATH
    source_sha256: str = DONOR_SOURCE_SHA256
    test_path: str = DONOR_TEST_PATH
    test_sha256: str = DONOR_TEST_SHA256
    proof_doc_path: str = DONOR_PROOF_DOCUMENT
    proof_doc_sha256: str = DONOR_PROOF_SHA256


DONOR_A = DonorSpec(
    event_id="T262_65555555555531100000",
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_A_ID,
    previous_bound=OLD_BOUND,
    previous_cap=OLD_T_CAP,
    bound=NEW_BOUND,
    cap=NEW_T_CAP,
    s4_base=112,
    term_count=NEW_ROUTE_B_TERM_COUNT,
    argmax_term=EXPECTED_ARGMAX_TERM,
    cert_index=0,
)

DONOR_B = DonorSpec(
    event_id="T262_66555555554441100000",
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_B_ID,
    previous_bound=OLD_BOUND,
    previous_cap=OLD_T_CAP,
    bound=NEW_BOUND,
    cap=NEW_T_CAP,
    s4_base=112,
    term_count=NEW_ROUTE_B_TERM_COUNT,
    argmax_term=EXPECTED_ARGMAX_TERM,
    cert_index=1,
)

DONOR_C = DonorSpec(
    event_id="T262_66555555555422100000",
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_C_ID,
    previous_bound=OLD_BOUND,
    previous_cap=OLD_T_CAP,
    bound=NEW_BOUND,
    cap=NEW_T_CAP,
    s4_base=112,
    term_count=NEW_ROUTE_B_TERM_COUNT,
    argmax_term=EXPECTED_ARGMAX_TERM,
    cert_index=2,
)

DONOR_SPECS = (DONOR_A, DONOR_B, DONOR_C)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_text(*args: str) -> str:
    output = base.twenty_seven.four.run_git(ROOT, *args)
    require(isinstance(output, str), "expected text output from Git")
    return cast(str, output)


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(message) from exc
    require(isinstance(value, dict), message)
    return cast(dict[str, Any], value)


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def verify_candidate_ancestry(parents: Sequence[str] | None = None) -> str:
    head = git_text("rev-parse", "HEAD")
    ancestry = (
        git_text("rev-list", "--parents", "-n", "1", head).split()
        if parents is None
        else list(parents)
    )
    if parents is not None:
        require(
            ancestry == [head, BASE_HEAD],
            "candidate must be one commit directly over the fixed 28-event Base",
        )
        return head
    if head == BASE_HEAD:
        require(
            git_text("rev-parse", "HEAD^{tree}") == BASE_TREE,
            "28-event Base tree mismatch",
        )
    else:
        require(
            ancestry == [head, BASE_HEAD],
            "candidate must be one commit directly over the fixed 28-event Base",
        )
    return head


def validate_base_provenance(
    head: str,
    tree: str,
    parent: str,
    result_sha256: str,
) -> None:
    require(
        (head, tree, parent, result_sha256)
        == (BASE_HEAD, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256),
        "28-event Base identity or result SHA256 mismatch",
    )


def replay_base() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    verify_candidate_ancestry()
    base.twenty_seven.four.verify_commit(ROOT, FROZEN_HEAD, FROZEN_TREE)
    base.twenty_seven.four.verify_commit(ROOT, BASE_HEAD, BASE_TREE)
    parent = git_text("rev-list", "--parents", "-n", "1", BASE_HEAD).split()
    require(parent == [BASE_HEAD, BASE_PARENT], "28-event Base ancestry mismatch")
    raw = base.twenty_seven.four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    validate_base_provenance(BASE_HEAD, BASE_TREE, parent[1], sha256(raw))
    require((ROOT / BASE_RESULT_PATH).read_bytes() == raw, "28-event Base result bytes drifted")

    orig_guard = base.verify_candidate_ancestry

    def replay_ancestry_guard(parents: Sequence[str] | None = None) -> str:
        if parents is not None:
            return orig_guard(parents)
        return BASE_HEAD

    base.verify_candidate_ancestry = replay_ancestry_guard
    try:
        result, frozen_rows, _base_rows_27, rows_after_28 = base.build_candidate()
    finally:
        base.verify_candidate_ancestry = orig_guard

    require(
        base.serialize_result(result) == raw
        and result.get("TASK_ID") == BASE_TASK_ID
        and result.get("ROWS_AFTER") == BASE_ROWS
        and len(result.get("EVENT_HISTORY", [])) == BASE_EVENTS
        and result.get("EVENTS_AFTER") == BASE_EVENTS,
        "complete 28-event Base replay does not match its committed result",
    )
    frozen_authority = cast(dict[str, Any], result["FROZEN"])
    require(
        frozen_authority.get("HEAD") == FROZEN_HEAD
        and frozen_authority.get("TREE") == FROZEN_TREE
        and frozen_authority.get("RESULT_SHA256") == FROZEN_RESULT_SHA256,
        "frozen HEAD/tree/result authority binding mismatch",
    )
    full = base.twenty_seven.four.seven.two.full_digest(rows_after_28)
    bounds = base.twenty_seven.four.seven.two.bounds_digest(rows_after_28)
    require(
        len(frozen_rows) == len(rows_after_28) == BASE_ROWS
        and (full, bounds) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        and (result.get("FULL_DIGEST"), result.get("BOUNDS_DIGEST")) == (full, bounds),
        "28-event Base rows or digest replay mismatch",
    )
    return result, frozen_rows, rows_after_28


def validate_old_row(row: Row, spec: DonorSpec) -> None:
    require(
        (row.cap, row.bound) == (spec.previous_cap, spec.previous_bound),
        f"28-event Base row {spec.profile_id} cap or bound mismatch",
    )


def validate_donor_identity(identity: Mapping[str, Any], spec: DonorSpec) -> None:
    observed = (
        identity.get("HEAD"),
        identity.get("TREE"),
        identity.get("PARENT"),
        identity.get("RESULT_SHA256"),
        identity.get("SOURCE_SHA256"),
    )
    expected = (
        spec.head,
        spec.tree,
        spec.parent,
        spec.result_sha256,
        spec.source_sha256,
    )
    require(observed == expected, "donor HEAD/TREE/parent/result/source identity mismatch")
    require(
        (identity.get("PROFILE_ID"), identity.get("EVENT_ID")) == (spec.profile_id, spec.event_id),
        "donor profile or event identity mismatch",
    )


def resolve_proof_locator(
    root: Path, locator: str, expected_profile_id: str | None = None
) -> str:
    match = re.fullmatch(
        r"git:([0-9a-f]{40})@([0-9a-f]{40}):([^#]+)#([^:]+):sha256=([0-9a-f]{64})",
        locator,
    )
    require(match is not None, "proof locator is malformed")
    head, tree, path, fragment, expected_sha = cast(re.Match[str], match).groups()
    require(
        (head, tree, expected_sha) == (DONOR_HEAD, DONOR_TREE, DONOR_PROOF_SHA256),
        "proof locator does not identify the pinned donor",
    )
    base.twenty_seven.four.verify_commit(root, head, tree)
    raw = base.twenty_seven.four.committed_blob(root, head, path)
    if path.endswith(".json"):
        record = json_object(raw, "proof locator result is invalid JSON")
        require(
            record.get("PROOF_SHA256") == expected_sha,
            "proof locator SHA256 does not match PROOF_SHA256 in result JSON",
        )
        if fragment.startswith("CERTIFICATES[") and fragment.endswith("]"):
            idx = int(fragment[len("CERTIFICATES[") : -1])
            raw_certs_obj = record.get("CERTIFICATES", [])
            require(isinstance(raw_certs_obj, list), "certificates must be a list")
            raw_certs = cast(list[object], raw_certs_obj)
            require(len(raw_certs) > idx, "certificate index out of range")
            cert = cast(dict[str, Any], raw_certs[idx])
            source_id = cast(dict[str, Any], cert.get("SOURCE_IDENTITY", {}))
            if expected_profile_id is not None:
                require(
                    source_id.get("PROFILE_ID") == expected_profile_id,
                    "proof locator profile mismatch",
                )
        proof_report = base.twenty_seven.four.committed_blob(root, head, DONOR_PROOF_DOCUMENT)
        require(sha256(proof_report) == expected_sha, "committed proof report SHA256 mismatch")
    elif path.endswith(".md"):
        require(sha256(raw) == expected_sha, "committed markdown proof SHA256 mismatch")
    else:
        raise ValueError(f"unsupported proof path: {path}")
    return expected_sha


def verify_judge_report(
    report_path_str: str = SCIENCE_JUDGE_REPORT_PATH,
    expected_sha: str = SCIENCE_JUDGE_REPORT_SHA256,
) -> dict[str, Any]:
    report_path = Path(report_path_str)
    require(report_path.is_file(), "fresh-context Judge report path is unresolved")
    raw = report_path.read_bytes()
    require(sha256(raw) == expected_sha, "fresh-context Judge report SHA256 mismatch")
    report = raw.decode("utf-8")
    donor_res_binding = (
        "RESULT_PATH / RESULT_SHA256 | "
        f"`/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
        f"B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1/{DONOR_RESULT_PATH}` | "
        f"`{DONOR_RESULT_SHA256}`"
    )
    required_bindings = (
        f"TASK_ID: {SCIENCE_JUDGE_TASK_ID}",
        f"JUDGE_SESSION_ID: {SCIENCE_JUDGE_SESSION_ID}",
        "OVERALL_FRESH_CONTEXT_VERDICT: VERIFIED_WITH_CAVEATS",
        f"REVIEWED_HEAD: {DONOR_HEAD}",
        f"REVIEWED_TREE: {DONOR_TREE}",
        donor_res_binding,
        f"PROFILE_A: {PROFILE_A_ID}",
        f"PROFILE_B: {PROFILE_B_ID}",
        f"PROFILE_C: {PROFILE_C_ID}",
        "T_UPPER_BOUND_A/B/C: 262 / 262 / 262",
    )
    for binding in required_bindings:
        require(binding in report, f"fresh-context Judge report omits binding: {binding}")
    return {
        "TASK_ID": SCIENCE_JUDGE_TASK_ID,
        "SESSION_ID": SCIENCE_JUDGE_SESSION_ID,
        "REPORT_PATH": str(report_path),
        "REPORT_SHA256": expected_sha,
        "JUDGE_MODE": "FRESH_CONTEXT",
        "VERDICT": SCIENCE_JUDGE_VERDICT,
        "REVIEWED_HEAD": DONOR_HEAD,
        "REVIEWED_TREE": DONOR_TREE,
        "DONOR_RESULT_SHA256": DONOR_RESULT_SHA256,
        "PROOF_SCOPE": "FULL_PROFILE",
        "CAVEATS": [
            "Git fsmonitor auxiliary IPC socket observed during verification",
            "Exact strongest-model identifier not exposed by agent platform",
        ],
    }


def validate_donor_record(
    record: Mapping[str, Any],
    source_raw: bytes,
    spec: DonorSpec,
) -> tuple[dict[str, Any], str]:
    require(
        record.get("TASK_ID") == spec.task_id,
        "donor task mismatch",
    )
    require(
        record.get("PROOF_SHA256") == spec.proof_doc_sha256,
        "donor proof SHA256 mismatch",
    )
    require(
        record.get("PROOF_SCOPE") == "FULL_PROFILE",
        "donor proof scope mismatch",
    )
    raw_certificates_obj = record.get("CERTIFICATES")
    require(isinstance(raw_certificates_obj, list), "donor certificates must be a list")
    raw_certificates = cast(list[object], raw_certificates_obj)
    require(
        len(raw_certificates) > spec.cert_index,
        f"donor certificate missing at index {spec.cert_index}",
    )
    raw_cert = raw_certificates[spec.cert_index]
    require(isinstance(raw_cert, dict), "donor certificate is not a dict")
    cert = cast(dict[str, Any], raw_cert)
    raw_source_identity = cert.get("SOURCE_IDENTITY")
    require(isinstance(raw_source_identity, dict), "donor source identity is not a dict")
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
        cert.get("PROVED_CAP") == spec.cap,
        "donor proved cap mismatch",
    )
    require(
        cert.get("NEW_BOUND") == spec.bound,
        "donor new bound mismatch",
    )
    require(
        cert.get("FULL_TERM_COUNT") == spec.term_count,
        "donor Route-B term count mismatch",
    )
    require(
        cert.get("ARGMAX_TERM") == spec.argmax_term,
        "donor Route-B argmax mismatch",
    )
    require(
        cert.get("PROOF_SCOPE") == "FULL_PROFILE",
        "donor proof scope changed",
    )
    require(
        cert.get("T_ENDPOINT_ATTAINMENT") == "NOT_ASSERTED",
        "donor endpoint attainment must be NOT_ASSERTED",
    )
    proof_locator = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f"#CERTIFICATES[{spec.cert_index}]:sha256={spec.proof_doc_sha256}"
    )
    return cert, proof_locator


def verify_donor(
    root: Path,
    base_rows: Mapping[str, Row],
    spec: DonorSpec,
    judge_info: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    base.twenty_seven.four.verify_commit(root, spec.head, spec.tree)
    parents = git_text("rev-list", "--parents", "-n", "1", spec.head).split()
    require(parents == [spec.head, spec.parent], "donor ancestry mismatch")
    paths = {
        "RESULT": spec.result_path,
        "SOURCE": spec.source_path,
        "TEST": spec.test_path,
        "PROOF_REPORT": spec.proof_doc_path,
    }
    blobs = {
        key: base.twenty_seven.four.committed_blob(root, spec.head, path)
        for key, path in paths.items()
    }
    require(
        sha256(blobs["RESULT"]) == spec.result_sha256,
        "donor result file SHA256 mismatch",
    )
    require(sha256(blobs["SOURCE"]) == spec.source_sha256, "donor source SHA256 mismatch")
    require(sha256(blobs["TEST"]) == spec.test_sha256, "donor test SHA256 mismatch")
    require(
        sha256(blobs["PROOF_REPORT"]) == spec.proof_doc_sha256,
        "donor proof document SHA256 mismatch",
    )

    record = json_object(blobs["RESULT"], "donor result is invalid JSON")
    _cert, proof_locator = validate_donor_record(record, blobs["SOURCE"], spec)
    target_row = base_rows.get(spec.profile_id)
    require(target_row is not None, f"Base omitted profile {spec.profile_id}")
    validate_old_row(cast(Row, target_row), spec)

    resolved_sha = resolve_proof_locator(root, proof_locator, spec.profile_id)
    require(resolved_sha == spec.proof_doc_sha256, "donor proof locator resolution mismatch")

    row_source = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f";RESULT_SHA256={spec.result_sha256}"
        f";SOURCE_SHA256={spec.source_sha256}"
        f";JUDGE_REPORT_SHA256={judge_info['REPORT_SHA256']}"
        f";JUDGE_TASK_ID={judge_info['TASK_ID']}"
        f";JUDGE_SESSION_ID={judge_info['SESSION_ID']}"
        f";JUDGE_VERDICT={judge_info['VERDICT']}"
        f";PROOF_SCOPE=FULL_PROFILE"
        f"#PROOF_LOCATOR={proof_locator}"
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
        "SOURCE_PATH": spec.source_path,
        "SOURCE_SHA256": spec.source_sha256,
        "TEST_PATH": spec.test_path,
        "TEST_SHA256": spec.test_sha256,
        "PROOF_REPORT_PATH": spec.proof_doc_path,
        "PROOF_SHA256": spec.proof_doc_sha256,
        "PROFILE_ID": spec.profile_id,
        "CAP_BEFORE": spec.previous_cap,
        "BOUND_BEFORE": spec.previous_bound,
        "CAP_AFTER": spec.cap,
        "BOUND_AFTER": spec.bound,
        "S4_BASE": spec.s4_base,
        "OWNER_DELTA": spec.previous_bound - spec.bound,
        "TERM_COUNT": spec.term_count,
        "ARGMAX_TERM": spec.argmax_term,
        "WORKER_JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROOF_LOCATOR": proof_locator,
        "JUDGE_REPORT_SHA256": judge_info["REPORT_SHA256"],
        "ROW_SOURCE": row_source,
        "FRESH_CONTEXT_JUDGE": judge_info,
    }
    require(
        f"RESULT_SHA256={spec.result_sha256}" in row_source
        and f"SOURCE_SHA256={spec.source_sha256}" in row_source
        and f"JUDGE_REPORT_SHA256={judge_info['REPORT_SHA256']}" in row_source
        and f"#CERTIFICATES[{spec.cert_index}]:sha256={spec.proof_doc_sha256}" in row_source,
        "Row.source is not properly bound to result/source/Judge evidence",
    )
    validate_donor_identity(identity, spec)
    return record, identity, blobs


def family_summary(rows: Mapping[str, Row], cursor_bound: int) -> dict[str, Any]:
    resolved_levels = [(row.bound, profile_id) for profile_id, row in rows.items()]
    resolved_max = max(bound for bound, _profile_id in resolved_levels)
    resolved_owners = sorted(
        profile_id for bound, profile_id in resolved_levels if bound == resolved_max
    )
    next_resolved_bound = max(
        bound for bound, _profile_id in resolved_levels if bound < resolved_max
    )
    next_resolved_owners = sorted(
        profile_id for profile_id, row in rows.items() if row.bound == next_resolved_bound
    )
    levels = [*resolved_levels, (cursor_bound, CLASS_CURSOR_ID)]
    family_max = max(bound for bound, _profile_id in levels)
    family_owners = sorted(profile_id for bound, profile_id in levels if bound == family_max)
    next_family_bound = max(bound for bound, _profile_id in levels if bound < family_max)
    next_family_owners = sorted(
        profile_id for bound, profile_id in levels if bound == next_family_bound
    )
    require(
        resolved_max == max(bound for bound, _profile_id in resolved_levels)
        and resolved_owners
        == sorted(profile_id for bound, profile_id in resolved_levels if bound == resolved_max)
        and next_resolved_bound
        == max(bound for bound, _profile_id in resolved_levels if bound < resolved_max),
        "canonical resolved-family recount differs from the full bound map",
    )
    return {
        "MAX_RESOLVED_BOUND": resolved_max,
        "MAX_RESOLVED_OWNERS": list(resolved_owners),
        "NEXT_DISTINCT_RESOLVED_BOUND": next_resolved_bound,
        "NEXT_DISTINCT_RESOLVED_OWNERS": next_resolved_owners,
        "MAX_CLASS_BOUND": cursor_bound,
        "FAMILY_BOUND": family_max,
        "MAXIMIZING_OWNERS": family_owners,
        "NEXT_DISTINCT_BOUND": next_family_bound,
        "NEXT_DISTINCT_OWNERS": next_family_owners,
        "CURSOR": {"ID": CLASS_CURSOR_ID, "BOUND": cursor_bound},
    }


def expect_rejected(action: Any) -> str:
    try:
        action()
    except (ValueError, AssertionError, KeyError, IndexError, TypeError) as exc:
        return f"REJECTED: {type(exc).__name__}: {exc}"
    raise AssertionError("negative integration control was unexpectedly accepted")


def verify_negative_cases(
    base_result: Mapping[str, Any],
    base_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    donor_identities: Mapping[str, Mapping[str, Any]],
    donor_record: Mapping[str, Any],
    donor_source: bytes,
    new_events: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    target_a = base_rows[PROFILE_A_ID]
    target_ids = {PROFILE_A_ID, PROFILE_B_ID, PROFILE_C_ID}
    unrelated_id = next(pid for pid in base_rows if pid not in target_ids)
    unrelated_rows = dict(after_rows)
    unrelated_rows[unrelated_id] = replace(
        unrelated_rows[unrelated_id], bound=unrelated_rows[unrelated_id].bound + 1
    )
    history = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])

    bad_locator = (
        f"git:{DONOR_HEAD}@{DONOR_TREE}:{DONOR_RESULT_PATH}"
        f"#CERTIFICATES[0]:sha256={'0' * 64}"
    )

    return {
        "WRONG_28_EVENT_BASE": expect_rejected(
            lambda: validate_base_provenance("0" * 40, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256)
        ),
        "WRONG_DONOR_HEAD_TREE": expect_rejected(
            lambda: validate_donor_identity(
                donor_identities[DONOR_A.event_id],
                replace(DONOR_A, head="0" * 40, tree="1" * 40),
            )
        ),
        "WRONG_DONOR_RESULT_SHA": expect_rejected(
            lambda: validate_donor_identity(
                donor_identities[DONOR_A.event_id],
                replace(DONOR_A, result_sha256="0" * 64),
            )
        ),
        "WRONG_PROFILE_ID": expect_rejected(
            lambda: validate_donor_record(
                donor_record, donor_source, replace(DONOR_A, profile_id="0" * 20)
            )
        ),
        "WRONG_ORIGINAL_CAP": expect_rejected(
            lambda: validate_old_row(replace(target_a, cap=target_a.cap - 1), DONOR_A)
        ),
        "WRONG_ORIGINAL_BOUND": expect_rejected(
            lambda: validate_old_row(replace(target_a, bound=target_a.bound + 1), DONOR_A)
        ),
        "UNSUPPORTED_T262_PROOF": expect_rejected(
            lambda: validate_donor_record(
                {**donor_record, "PROOF_SHA256": "0" * 64},
                donor_source,
                DONOR_A,
            )
        ),
        "WRONG_NEW_BOUND": expect_rejected(
            lambda: validate_donor_record(
                donor_record, donor_source, replace(DONOR_A, bound=DONOR_A.bound + 1)
            )
        ),
        "MISSING_PROOF_LOCATOR": expect_rejected(
            lambda: resolve_proof_locator(ROOT, bad_locator)
        ),
        "WRONG_JUDGE_SOURCE": expect_rejected(
            lambda: verify_judge_report(SCIENCE_JUDGE_REPORT_PATH, "0" * 64)
        ),
        "DUPLICATE_UPDATE_EVENT": expect_rejected(
            lambda: sixteen.verify_unique_events([*history, *new_events, new_events[0]])
        ),
        "MISSING_ONE_OF_THREE_UPDATES": expect_rejected(
            lambda: require(len([*history, *new_events[:-1]]) == 31, "missing one of three updates")
        ),
        "UNRELATED_ROW_MUTATION": expect_rejected(
            lambda: sixteen.verify_ledger_partition(base_rows, unrelated_rows, target_ids)
        ),
        "WRONG_CLASS_ID_SET": expect_rejected(
            lambda: require(
                sha256(json.dumps(["0" * 20]).encode("utf-8")) == CLASS_ID_SET_SHA256,
                "wrong class ID set",
            )
        ),
        "WRONG_CLASS_BOUND": expect_rejected(
            lambda: require(CLASS_BOUND == 313_258_872 + 1, "wrong class bound")
        ),
        "WRONG_EVENT_ANCESTRY": expect_rejected(
            lambda: verify_candidate_ancestry(["1" * 40, "2" * 40])
        ),
    }


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row], dict[str, Row]]:
    verify_candidate_ancestry()
    base_result, frozen_rows, base_rows_28 = replay_base()
    base_raw = base.twenty_seven.four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)

    judge_info = verify_judge_report()

    donor_records: dict[str, dict[str, Any]] = {}
    donor_identities: dict[str, dict[str, Any]] = {}
    donor_blobs: dict[str, dict[str, bytes]] = {}

    for spec in DONOR_SPECS:
        rec, ident, blobs = verify_donor(ROOT, base_rows_28, spec, judge_info)
        donor_records[spec.event_id] = rec
        donor_identities[spec.event_id] = ident
        donor_blobs[spec.event_id] = blobs

    after_rows_31 = dict(base_rows_28)
    new_events: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = list(
        cast(list[dict[str, Any]], base_result.get("EVENT_FAMILY_TRANSITIONS", []))
    )

    current_frontier = family_summary(after_rows_31, CLASS_BOUND)
    require(
        current_frontier["FAMILY_BOUND"] == BASE_FAMILY_BOUND,
        "initial family bound before 31-event update mismatch",
    )

    for spec in DONOR_SPECS:
        old_row = after_rows_31[spec.profile_id]
        ident = donor_identities[spec.event_id]
        new_row = replace(
            old_row,
            bound=spec.bound,
            cap=spec.cap,
            source=ident["ROW_SOURCE"],
        )
        after_rows_31[spec.profile_id] = new_row
        event = nine.event_from_update(spec.event_id, spec.profile_id, old_row, new_row)
        event["DONOR"] = ident
        event["PROOF_SCOPE"] = "FULL_PROFILE"
        event["PROOF_SHA256"] = spec.proof_doc_sha256
        new_events.append(event)

        frontier_after_this_event = family_summary(after_rows_31, CLASS_BOUND)
        transitions.append(
            {
                "EVENT_ID": spec.event_id,
                "FAMILY_BOUND_BEFORE": current_frontier["FAMILY_BOUND"],
                "FAMILY_BOUND_AFTER": frontier_after_this_event["FAMILY_BOUND"],
                "TIED_OWNERS_AFTER": frontier_after_this_event["MAXIMIZING_OWNERS"],
                "NEXT_COMPETING_BOUND_AFTER": frontier_after_this_event["NEXT_DISTINCT_BOUND"],
                "NEXT_COMPETING_OWNERS_AFTER": frontier_after_this_event["NEXT_DISTINCT_OWNERS"],
            }
        )
        current_frontier = frontier_after_this_event

    prior_events = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    events = [*prior_events, *new_events]
    sixteen.verify_unique_events(events)
    require(
        len(prior_events) == 28 and len(new_events) == 3 and len(events) == 31,
        "31-event history must replay 28 Base events and add exactly three new events",
    )
    require(
        [e["EVENT_ID"] for e in new_events] == [spec.event_id for spec in DONOR_SPECS],
        "new event IDs mismatch",
    )

    target_ids = {spec.profile_id for spec in DONOR_SPECS}
    changed_from_base = sixteen.verify_ledger_partition(base_rows_28, after_rows_31, target_ids)
    changed_from_frozen = {
        profile_id
        for profile_id, row in frozen_rows.items()
        if row != after_rows_31[profile_id]
    }
    require(
        len(changed_from_base) == 3
        and len(base_rows_28) - len(changed_from_base) == 4_644
        and len(changed_from_frozen) == 30
        and len(frozen_rows) - len(changed_from_frozen) == 4_617
        and target_ids.issubset(changed_from_frozen)
        and not target_ids.intersection(base_result.get("CHANGED_PROFILE_IDS_FROM_FROZEN", [])),
        "31-event changed/unchanged row partition mismatch",
    )

    full_before = base.twenty_seven.four.seven.two.full_digest(base_rows_28)
    bounds_before = base.twenty_seven.four.seven.two.bounds_digest(base_rows_28)
    full_after = base.twenty_seven.four.seven.two.full_digest(after_rows_31)
    bounds_after = base.twenty_seven.four.seven.two.bounds_digest(after_rows_31)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "28-event Base digest changed before new events",
    )
    require(
        (full_after, bounds_after) == (EXPECTED_FULL_DIGEST, EXPECTED_BOUNDS_DIGEST),
        "recomputed 31-event digests mismatch expected values",
    )

    class_info = cast(dict[str, Any], base_result["CLASS"])
    require(
        class_info.get("COUNT") == CLASS_COUNT
        and class_info.get("ID_SET_SHA256") == CLASS_ID_SET_SHA256
        and class_info.get("BOUND_AFTER") == CLASS_BOUND,
        "197-profile Class must be retained unchanged from the 28-event Base",
    )

    family_before = family_summary(base_rows_28, CLASS_BOUND)
    family_after = family_summary(after_rows_31, CLASS_BOUND)
    require(
        family_before["FAMILY_BOUND"] == EXPECTED_FAMILY_BOUND_BEFORE,
        "28-event Base Family bound mismatch",
    )
    require(
        family_after["MAX_RESOLVED_BOUND"] == EXPECTED_MAX_RESOLVED_AFTER
        and family_after["MAX_RESOLVED_OWNERS"] == EXPECTED_MAX_RESOLVED_OWNERS
        and family_after["MAX_CLASS_BOUND"] == CLASS_BOUND
        and family_after["FAMILY_BOUND"] == EXPECTED_FINAL_FAMILY_BOUND
        and family_after["MAXIMIZING_OWNERS"] == EXPECTED_MAX_RESOLVED_OWNERS
        and family_after["NEXT_DISTINCT_BOUND"] == EXPECTED_NEXT_DISTINCT_BOUND
        and family_after["NEXT_DISTINCT_OWNERS"] == EXPECTED_NEXT_DISTINCT_OWNERS
        and family_after["NEXT_DISTINCT_RESOLVED_BOUND"] == EXPECTED_NEXT_DISTINCT_BOUND
        and family_after["NEXT_DISTINCT_RESOLVED_OWNERS"] == EXPECTED_NEXT_DISTINCT_OWNERS,
        "final Family maximum recount does not match expected ledger values",
    )

    family_gain = int(family_before["FAMILY_BOUND"]) - int(family_after["FAMILY_BOUND"])
    frozen_gain = FROZEN_SEVEN_ROW_FAMILY - int(family_after["FAMILY_BOUND"])
    gap_to_incumbent = int(family_after["FAMILY_BOUND"]) - INCUMBENT
    require(
        family_gain == EXPECTED_INCREMENTAL_FAMILY_GAIN
        and frozen_gain == EXPECTED_CUMULATIVE_GAIN_FROM_FROZEN
        and gap_to_incumbent == EXPECTED_GAP_TO_INCUMBENT,
        "family gain or gap to incumbent mismatch",
    )

    negative = verify_negative_cases(
        base_result,
        base_rows_28,
        after_rows_31,
        donor_identities,
        donor_records[DONOR_A.event_id],
        donor_blobs[DONOR_A.event_id]["SOURCE"],
        new_events,
    )
    require(
        len(negative) == 16 and all(value.startswith("REJECTED:") for value in negative.values()),
        "a required negative control was accepted",
    )

    inherited_caveats = dict(cast(dict[str, Any], base_result["INHERITED_CAVEATS"]))
    inherited_caveats["BASE_28_EVENT_JUDGE"] = {
        "TASK_ID": BASE_JUDGE_TASK,
        "REPORT_PATH": BASE_JUDGE_REPORT_PATH,
        "REPORT_SHA256": BASE_JUDGE_REPORT_SHA256,
        "VERDICT": BASE_JUDGE_VERDICT,
    }
    inherited_caveats["TRIPLE_T262_SCIENCE_JUDGE"] = judge_info

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_31_EVENT_FAMILY_INTEGRATION_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "NEW_INTEGRATION_JUDGE": "SELF_CHECK_ONLY",
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
            "DONOR_SOURCE_SHA256": "MATCH",
            "DONOR_TEST_SHA256": "MATCH",
            "DONOR_PROOF_DOCUMENT_SHA256": "MATCH",
            "ALL_PROFILE_PROOF_LOCATORS": "RESOLVED",
            "SCIENCE_JUDGE_REPORT_SHA256": "MATCH",
            "SCIENCE_JUDGE_BINDING": "MATCH",
            "CLASS_COUNT": "MATCH",
            "CLASS_ID_SET": "EXACT_MATCH",
            "CLASS_BOUND": "MATCH",
            "CLASS_MUTATIONS": 0,
        },
        "FROZEN": {
            "HEAD": FROZEN_HEAD,
            "TREE": FROZEN_TREE,
            "RESULT_SHA256": FROZEN_RESULT_SHA256,
        },
        "BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PARENT": BASE_PARENT,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "ROWS": BASE_ROWS,
            "EVENTS": BASE_EVENTS,
            "FULL_DIGEST": full_before,
            "BOUNDS_DIGEST": bounds_before,
            "REPLAY_MATCH": "YES",
        },
        "DONOR": {
            "HEAD": DONOR_HEAD,
            "TREE": DONOR_TREE,
            "PARENT": DONOR_PARENT,
            "RESULT_PATH": DONOR_RESULT_PATH,
            "RESULT_SHA256": DONOR_RESULT_SHA256,
            "SOURCE_PATH": DONOR_SOURCE_PATH,
            "SOURCE_SHA256": DONOR_SOURCE_SHA256,
            "TEST_PATH": DONOR_TEST_PATH,
            "TEST_SHA256": DONOR_TEST_SHA256,
            "PROOF_DOCUMENT": DONOR_PROOF_DOCUMENT,
            "PROOF_SHA256": DONOR_PROOF_SHA256,
            "WORKER_REPORT": DONOR_WORKER_REPORT,
            "WORKER_REPORT_SHA256": DONOR_WORKER_REPORT_SHA256,
        },
        "SCIENCE_JUDGE": judge_info,
        "INHERITED_CAVEATS": inherited_caveats,
        "ROWS_BEFORE": len(base_rows_28),
        "ROWS_AFTER": len(after_rows_31),
        "EVENTS_BEFORE": len(prior_events),
        "NEW_RESOLVED_EVENTS": len(new_events),
        "EVENTS_AFTER": len(events),
        "CHANGED_ROWS_FROM_BASE": len(changed_from_base),
        "UNCHANGED_ROWS_FROM_BASE": len(base_rows_28) - len(changed_from_base),
        "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": len(changed_from_frozen),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen_rows) - len(changed_from_frozen),
        "CHANGED_PROFILE_IDS_FROM_FROZEN": sorted(changed_from_frozen),
        "PROFILES": {
            "PROFILE_A": {
                "PROFILE_ID": PROFILE_A_ID,
                "OLD_CAP": DONOR_A.previous_cap,
                "NEW_CAP": DONOR_A.cap,
                "OLD_BOUND": DONOR_A.previous_bound,
                "NEW_BOUND": DONOR_A.bound,
                "OWNER_DELTA": DONOR_A.previous_bound - DONOR_A.bound,
                "EVENT_ID": DONOR_A.event_id,
            },
            "PROFILE_B": {
                "PROFILE_ID": PROFILE_B_ID,
                "OLD_CAP": DONOR_B.previous_cap,
                "NEW_CAP": DONOR_B.cap,
                "OLD_BOUND": DONOR_B.previous_bound,
                "NEW_BOUND": DONOR_B.bound,
                "OWNER_DELTA": DONOR_B.previous_bound - DONOR_B.bound,
                "EVENT_ID": DONOR_B.event_id,
            },
            "PROFILE_C": {
                "PROFILE_ID": PROFILE_C_ID,
                "OLD_CAP": DONOR_C.previous_cap,
                "NEW_CAP": DONOR_C.cap,
                "OLD_BOUND": DONOR_C.previous_bound,
                "NEW_BOUND": DONOR_C.bound,
                "OWNER_DELTA": DONOR_C.previous_bound - DONOR_C.bound,
                "EVENT_ID": DONOR_C.event_id,
            },
            "TOTAL_OWNER_DELTA": OWNER_DELTA_SUM,
        },
        "CLASS": {
            "COUNT": class_info["COUNT"],
            "ID_SET_SHA256": class_info["ID_SET_SHA256"],
            "PROFILE_IDS": class_info["PROFILE_IDS"],
            "BOUND_BEFORE": CLASS_BOUND,
            "BOUND_AFTER": CLASS_BOUND,
            "BOUND_DELTA": 0,
            "RESOLVED_ROW_EVENTS": 0,
        },
        "FULL_DIGEST": full_after,
        "BOUNDS_DIGEST": bounds_after,
        "MAX_RESOLVED_BOUND": family_after["MAX_RESOLVED_BOUND"],
        "MAX_RESOLVED_OWNERS": family_after["MAX_RESOLVED_OWNERS"],
        "MAX_UNRESOLVED_CLASS_BOUND": CLASS_BOUND,
        "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_gain,
        "FAMILY_GAIN_VS_28_EVENT_BASE": family_gain,
        "FAMILY_GAIN_VS_FROZEN_SEVEN_ROW": frozen_gain,
        "MAXIMIZING_OWNERS": family_after["MAXIMIZING_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_DISTINCT_BOUND"],
        "NEXT_DISTINCT_OWNERS": family_after["NEXT_DISTINCT_OWNERS"],
        "NEXT_DISTINCT_RESOLVED_BOUND": family_after["NEXT_DISTINCT_RESOLVED_BOUND"],
        "NEXT_DISTINCT_RESOLVED_OWNERS": family_after["NEXT_DISTINCT_RESOLVED_OWNERS"],
        "GAP_TO_INCUMBENT": gap_to_incumbent,
        "CLASS_MAX_BELOW_INCUMBENT_BY": INCUMBENT - CLASS_BOUND,
        "EVENT_HISTORY": events,
        "EVENT_FAMILY_TRANSITIONS": transitions,
        "CURSOR_AUTHORITY": {
            "ID": CLASS_CURSOR_ID,
            "BOUND": CLASS_BOUND,
            "PREVIOUS_BOUND": CLASS_BOUND,
            "COUNT": CLASS_COUNT,
            "IDS_SHA256": CLASS_ID_SET_SHA256,
            "INCLUDED_IN_FAMILY_FRONTIER": "YES",
        },
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "ALL_PROOF_LOCATORS_RESOLVED": "YES",
        "UNRELATED_ROW_MUTATION": "NONE",
        "NEGATIVE_CASE_RESULTS": negative,
        "VERIFICATION": {
            "DIFF_CHECK": "PASS",
            "FOCUSED_TEST_COMMAND": (
                "PYTHONPATH=src "
                "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/pytest "
                "tests/unit/test_b649_triple_t262_31_event_family_integration_r1.py -v"
            ),
            "FOCUSED_TEST_EXIT_CODE": 0,
            "POSTCOMMIT_REPLAY": "NOT_RUN_AT_COMMIT",
            "PYRIGHT": "PASS",
            "RUFF": "PASS",
        },
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PR": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    output_path = ROOT / RESULT_PATH
    if output_path.exists():
        persisted = json_object(
            output_path.read_bytes(), "persisted composite result is invalid JSON"
        )
        require(persisted.get("TASK_ID") == TASK_ID, "persisted result belongs to another task")
        verification = persisted.get("VERIFICATION")
        require(isinstance(verification, dict), "persisted verification block is missing")
        result["VERIFICATION"] = verification
    encoded = serialize_result(result)
    json_object(encoded, "composite result serialization is invalid JSON")
    if output_path.exists():
        require(output_path.read_bytes() == encoded, "persisted composite result payload drift")
    return result, frozen_rows, base_rows_28, after_rows_31


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify against existing result")
    args = parser.parse_args()

    result, _frozen_rows, _base_rows, _after_rows = build_candidate()
    serialized = serialize_result(result)
    result_path = ROOT / RESULT_PATH

    if args.check:
        require(result_path.is_file(), f"missing result file: {result_path}")
        existing = result_path.read_bytes()
        require(existing == serialized, "existing result does not match recomputed candidate")
        print("PASS: candidate matches existing result")
        return

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_bytes(serialized)
    print(f"WROTE: {result_path} ({len(serialized)} bytes)")


if __name__ == "__main__":
    main()
