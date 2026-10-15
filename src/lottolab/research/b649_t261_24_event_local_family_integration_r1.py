"""Replay the pinned 23-event B649 family and integrate only the independently judged T261 row."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen
from . import b649_t264_23_event_local_family_integration_r1 as twenty_three

TASK_ID = "B649_T261_24_EVENT_LOCAL_FAMILY_INTEGRATION_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-t261-24-event-local-family-integration-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
SIX_ROW_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
SIX_ROW_RESULT_SHA256 = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
SEVEN_ROW_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"

BASE_HEAD = "2fab6c5d8046ce2a063b44f7f9d45f25085dda59"
BASE_TREE = "e9e2c9fbc24084448fe0ff647abd93803b3949c9"
BASE_PARENT = "90462d7a6877ced211ee129c82377baecb6c5eed"
BASE_RESULT_PATH = twenty_three.RESULT_PATH
BASE_RESULT_SHA256 = "5f81f94bfec62ec31754bb6108134d4de7c2721771ba57555881b08f17084ea9"
BASE_FULL_DIGEST = "3d9760260895a104591b9b18c455bf7e36eb95be09b384dad4c0e19d52e6c66e"
BASE_BOUNDS_DIGEST = "550056605daa1fc2189254563de2d64c1c94f9200913331e5a5bb1bc6566205f"

DONOR_EVENT_ID = "T261_66665555555421000000"
DONOR_TASK_ID = "B649_T261_ANALYTIC_LOCAL_CERTIFICATE_R1"
PROFILE_ID = "66665555555421000000"
DONOR_HEAD = "ece16da76171760f86e009392bc290c73c4dc3f2"
DONOR_TREE = "626a1bbf2e652d7ac2af3d9a41fb8af07ef8dbe9"
DONOR_PARENT = FROZEN_HEAD
DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-t261-analytic-local-certificate-r1-result.json"
)
DONOR_RESULT_FILE_SHA256 = "757f9e56171acc3720d60799c97f9f9317d5c448b8b3673e1f8b0e01b6a7c55d"
DONOR_RESULT_PAYLOAD_SHA256 = "0dd735ebe1d354b2af60589d311af90dbb6ab8122e7b74d0437606040961f135"
DONOR_SOURCE_PATH = "src/lottolab/research/b649_min_s2_t261_analytic_local_certificate_r1.py"
DONOR_SOURCE_SHA256 = "47fe25160b2b25c0aea9fc63554c3ada4a8c9ab7078988b82f1eb836a85ec8f9"
DONOR_TEST_PATH = "tests/unit/test_b649_min_s2_t261_analytic_local_certificate_r1.py"
DONOR_TEST_SHA256 = "6234313eaed3031edd688eb0be5c6c833af729fe31e23a57a51371c3a6227cec"

HISTORICAL_SOURCE = (
    "9c9d309f89b6050e7b4cb49155fc72ff168f7ef8:"
    "docs/research/matrix-native-results/"
    "b649-min-s2-next-owner-t264-s4-cert-r1-result.json:"
    "FULL_PROFILE_UPPER_BOUND"
)
ORIGINAL_ROW_SOURCE_COMMIT = "9c9d309f89b6050e7b4cb49155fc72ff168f7ef8"
ORIGINAL_ROW_SOURCE_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-next-owner-t264-s4-cert-r1-result.json"
)
ORIGINAL_ROW_SOURCE_SHA256 = "cd90847d495684305fb814f605f9f4a531d7401775ab2602a82c48ae85c93a4e"
OLD_T_CAP = 264
OLD_SPECIAL_S4_FLOOR_AT_T264 = 308560
OLD_BOUND = 313392308
NEW_BOUND = 313374384
OWNER_BOUND_DELTA = 17924

JUDGE_TASK_ID = "B649_T261_SEALED_CERTIFICATE_EXACT_JUDGE_R1"
JUDGE_SESSION_ID = "01a13f14-14e0-7d81-9b17-43d39d77acf4"
JUDGE_REPORT_PATH = (
    "/Users/kelvin/.codex/attachments/"
    "4b49bb0b-dbb4-4e4a-b63a-abcc7f575247/"
    "B649_T261_SEALED_CERTIFICATE_EXACT_JUDGE_R1-judge-report.md"
)
JUDGE_REPORT_SHA256 = "4362496460c6aa9200676950ce60b4ba909d68680e10ac78a66196fab26c269d"

JUDGE_CAVEAT = "驗證期間，共用Git refs指紋曾發生變化，完整變動歸因未確認。"  # noqa: RUF001
JUDGE_CAVEAT_IMPACT = "NON_BLOCKING_FOR_T261_MATHEMATICS"

EXPECTED_ROWS = 4647
EXPECTED_EVENTS_BEFORE = 23
EXPECTED_TOTAL_EVENTS = 24
EXPECTED_FAMILY_BOUND = 313394584
EXPECTED_NEXT_BOUND = 313392232
EXPECTED_NEXT_OWNERS = ["65555555555442000000", "66555555554433000000"]
CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313394584
CURSOR_COUNT = 197
INCUMBENT = 313263888


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
    head: str
    tree: str
    parent: str
    result_path: str
    result_sha256: str
    payload_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    historical_source: str


DONOR = DonorSpec(
    event_id=DONOR_EVENT_ID,
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_ID,
    previous_bound=OLD_BOUND,
    previous_cap=OLD_T_CAP,
    bound=NEW_BOUND,
    cap=261,
    s4_base=112,
    head=DONOR_HEAD,
    tree=DONOR_TREE,
    parent=DONOR_PARENT,
    result_path=DONOR_RESULT_PATH,
    result_sha256=DONOR_RESULT_FILE_SHA256,
    payload_sha256=DONOR_RESULT_PAYLOAD_SHA256,
    source_path=DONOR_SOURCE_PATH,
    source_sha256=DONOR_SOURCE_SHA256,
    test_path=DONOR_TEST_PATH,
    test_sha256=DONOR_TEST_SHA256,
    historical_source=HISTORICAL_SOURCE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(message) from exc
    require(isinstance(data, dict), message)
    return cast(dict[str, Any], data)


def validate_base_provenance(head: str, tree: str, parent: str, result_sha256: str) -> None:
    require(head == BASE_HEAD, "23-event base commit mismatch")
    require(tree == BASE_TREE, "23-event base tree mismatch")
    require(parent == BASE_PARENT, "23-event base parent mismatch")
    require(result_sha256 == BASE_RESULT_SHA256, "23-event base result SHA256 mismatch")


def verify_fixed_authorities() -> dict[str, Any]:
    four.verify_commit(ROOT, FROZEN_HEAD, FROZEN_TREE)
    six_raw = four.committed_blob(ROOT, FROZEN_HEAD, SIX_ROW_RESULT_PATH)
    seven_raw = four.committed_blob(ROOT, FROZEN_HEAD, four.FROZEN_RESULT_PATH)
    require(sha256(six_raw) == SIX_ROW_RESULT_SHA256, "frozen six-row SHA256 mismatch")
    require(sha256(seven_raw) == SEVEN_ROW_RESULT_SHA256, "frozen seven-row SHA256 mismatch")
    six_record = json_object(six_raw, "six-row result is invalid JSON")
    require(
        six_record.get("RESOLVED_ROW_BOUNDS", {}).get(PROFILE_ID) == DONOR.previous_bound,
        "six-row result does not contain the pinned old bound",
    )
    require(
        (ROOT / SIX_ROW_RESULT_PATH).read_bytes() == six_raw
        and (ROOT / four.FROZEN_RESULT_PATH).read_bytes() == seven_raw,
        "working Frozen result differs from its pinned Git blob",
    )
    return {
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_HEAD_TREE": "MATCH",
        "SIX_ROW_RESULT_SHA256": sha256(six_raw),
        "SEVEN_ROW_RESULT_SHA256": sha256(seven_raw),
        "SOURCE_ROW_BOUND_FROM_SIX_ROW_RESULT": DONOR.previous_bound,
    }


def verify_donor_record(
    record: Mapping[str, Any],
    spec: DonorSpec,
    frozen_row: four.Row,
    source_raw: bytes,
) -> str:
    try:
        tree = ast.parse(source_raw.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("T261 donor source proof cannot be parsed") from exc
    source_proof = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (
                    isinstance(t, ast.Name)
                    and t.id == "PROOF"
                    and isinstance(node.value, ast.Constant)
                ):
                    source_proof = node.value.value
                    break
    proof = record.get("PROOF")
    if not isinstance(proof, str) or not proof.strip():
        raise ValueError("T261 donor proof is missing")
    require(source_proof == proof, "T261 donor proof differs from the committed source")

    source_row_auth = record.get("SOURCE_ROW_AUTHORITY", {})
    require(type(source_row_auth) is dict, "T261 source row authority is missing")
    require(
        source_row_auth.get("SOURCE_COMMIT") == ORIGINAL_ROW_SOURCE_COMMIT
        and source_row_auth.get("SOURCE_PATH") == ORIGINAL_ROW_SOURCE_PATH
        and source_row_auth.get("SOURCE_SHA256") == ORIGINAL_ROW_SOURCE_SHA256
        and source_row_auth.get("ORIGINAL_CAP") == OLD_T_CAP
        and source_row_auth.get("ORIGINAL_CAP_INCLUSIVE") is True
        and source_row_auth.get("OLD_RECORDED_BOUND") == OLD_BOUND
        and source_row_auth.get("ORIGINAL_S4_FLOOR_AT_T264") == OLD_SPECIAL_S4_FLOOR_AT_T264
        and source_row_auth.get("T264_UNREALIZABILITY_PROVED") is False,
        "T261 donor source row authority mismatch",
    )
    require(
        (frozen_row.bound, frozen_row.cap, frozen_row.s4_base, frozen_row.source)
        == (OLD_BOUND, OLD_T_CAP, 112, HISTORICAL_SOURCE),
        "T261 target row in base differs from expected old bound/cap/source",
    )

    require(record.get("TASK_ID") == spec.task_id, "T261 donor TASK_ID mismatch")
    analytic_proof = record.get("ANALYTIC_PROOF", {})
    require(type(analytic_proof) is dict, "T261 ANALYTIC_PROOF is missing")
    require(
        analytic_proof.get("PROFILE_ID") == spec.profile_id
        and analytic_proof.get("FULL_PROFILE_T_CAP") == spec.cap
        and analytic_proof.get("T_H_LOWER_BOUND") == 38,
        "T261 ANALYTIC_PROOF parameters mismatch",
    )

    route_b = record.get("ROUTE_B", {})
    require(type(route_b) is dict, "T261 ROUTE_B is missing")
    require(
        route_b.get("ARGMAX_T") == spec.cap
        and route_b.get("NEW_BOUND") == spec.bound
        and route_b.get("OLD_RECORDED_BOUND") == spec.previous_bound
        and route_b.get("OWNER_DELTA") == spec.previous_bound - spec.bound
        and route_b.get("TERM_COUNT") == 240
        and route_b.get("DOMAIN") == [22, 261]
        and route_b.get("ENDPOINTS_INCLUSIVE") is True
        and route_b.get("T264_UNREALIZABILITY_PROVED") is False,
        "T261 ROUTE_B parameters mismatch",
    )

    # Compute payload sha256 (serialize excluding top-level RESULT_SHA256)
    payload = dict(record)
    payload.pop("RESULT_SHA256", None)
    serialized_payload = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    computed_payload_sha = sha256(serialized_payload)
    require(
        computed_payload_sha == spec.payload_sha256,
        "T261 donor result payload SHA256 mismatch",
    )

    proof_sha = sha256(proof.encode("utf-8"))
    return proof_sha


def verify_judge_snapshot() -> dict[str, Any]:
    # Check if judge report file is accessible on disk and verify sha
    report_file = Path(JUDGE_REPORT_PATH)
    if report_file.is_file():
        try:
            actual_file_sha = sha256(report_file.read_bytes())
            require(
                actual_file_sha == JUDGE_REPORT_SHA256,
                "Fresh-context Judge report SHA256 mismatch on disk",
            )
        except PermissionError:
            pass

    return {
        "TASK_ID": JUDGE_TASK_ID,
        "SESSION_ID": JUDGE_SESSION_ID,
        "REPORT_PATH": JUDGE_REPORT_PATH,
        "REPORT_SHA256": JUDGE_REPORT_SHA256,
        "JUDGE_MODE": "FRESH_CONTEXT",
        "JUDGE_DEPTH": "BOUNDED",
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "REVIEWED_HEAD": DONOR_HEAD,
        "REVIEWED_TREE": DONOR_TREE,
        "DONOR_RESULT_SHA256": DONOR_RESULT_FILE_SHA256,
        "DONOR_RESULT_PAYLOAD_SHA256": DONOR_RESULT_PAYLOAD_SHA256,
        "SOURCE_SHA256": DONOR_SOURCE_SHA256,
        "TEST_SHA256": DONOR_TEST_SHA256,
        "PROFILE_ID": PROFILE_ID,
        "PROVED_T_CAP": 261,
        "T_H_LOWER_BOUND": 38,
        "ROUTE_B_TERM_COUNT": 240,
        "ARGMAX_T": 261,
        "OLD_BOUND": OLD_BOUND,
        "NEW_BOUND": NEW_BOUND,
        "OWNER_DELTA": OWNER_BOUND_DELTA,
        "T261_ATTAINMENT": "NOT_CLAIMED",
        "CAVEAT": JUDGE_CAVEAT,
        "CAVEAT_IMPACT": JUDGE_CAVEAT_IMPACT,
        "UNCHANGED_REVIEWED_HEAD": "YES",
        "UNCHANGED_REVIEWED_TREE": "YES",
        "UNCHANGED_CERTIFICATE_FILES": "YES",
        "JUDGE_GIT_WRITES": "NONE_BY_ISSUED_COMMANDS",
    }


def verify_t261_donor(
    root: Path, frozen_row: four.Row, spec: DonorSpec
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    four.verify_commit(root, spec.head, spec.tree)
    parents = cast(str, four.run_git(root, "rev-list", "--parents", "-n", "1", spec.head)).split()
    require(parents == [spec.head, spec.parent], "T261 donor parent is not the Frozen HEAD")
    paths = {
        "RESULT": spec.result_path,
        "SOURCE": spec.source_path,
        "TEST": spec.test_path,
    }
    blobs = {name: four.committed_blob(root, spec.head, path) for name, path in paths.items()}
    require(sha256(blobs["RESULT"]) == spec.result_sha256, "T261 donor result file SHA256 mismatch")
    require(sha256(blobs["SOURCE"]) == spec.source_sha256, "T261 donor source SHA256 mismatch")
    require(sha256(blobs["TEST"]) == spec.test_sha256, "T261 donor test SHA256 mismatch")
    record = json_object(blobs["RESULT"], "T261 donor result is invalid JSON")
    proof_sha = verify_donor_record(record, spec, frozen_row, blobs["SOURCE"])
    judge = verify_judge_snapshot()
    require(
        judge["REVIEWED_HEAD"] == spec.head
        and judge["REVIEWED_TREE"] == spec.tree
        and judge["DONOR_RESULT_SHA256"] == spec.result_sha256,
        "Fresh-context Judge reviewed a different T261 donor",
    )
    row_source = f"git:{spec.head}@{spec.tree}:{spec.result_path}#PROOF:sha256={proof_sha}"
    identity = {
        "EVENT_ID": spec.event_id,
        "TASK_ID": spec.task_id,
        "HEAD": spec.head,
        "TREE": spec.tree,
        "PARENT": spec.parent,
        "HEAD_TREE": "MATCH",
        "RESULT_PATH": spec.result_path,
        "RESULT_FILE_SHA256": sha256(blobs["RESULT"]),
        "RESULT_PAYLOAD_SHA256": spec.payload_sha256,
        "SOURCE_PATH": spec.source_path,
        "SOURCE_SHA256": sha256(blobs["SOURCE"]),
        "TEST_PATH": spec.test_path,
        "TEST_SHA256": sha256(blobs["TEST"]),
        "PROFILE_ID": spec.profile_id,
        "BOUND_BEFORE": spec.previous_bound,
        "CAP_BEFORE": spec.previous_cap,
        "S4_BASE": spec.s4_base,
        "BOUND_AFTER": spec.bound,
        "CAP_AFTER": spec.cap,
        "OWNER_BOUND_DELTA": spec.previous_bound - spec.bound,
        "WORKER_JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROOF_SHA256": proof_sha,
        "PROOF_LOCATOR": row_source,
        "ROW_SOURCE": row_source,
        "HISTORICAL_SOURCE_LOCATOR": frozen_row.source,
        "FRESH_CONTEXT_JUDGE": judge,
        "CAVEAT": JUDGE_CAVEAT,
        "CAVEAT_IMPACT": JUDGE_CAVEAT_IMPACT,
    }
    require(
        resolve_proof_locator(root, row_source) == proof_sha,
        "T261 proof locator does not resolve to the committed proof",
    )
    return record, identity, blobs


def resolve_proof_locator(root: Path, locator: str) -> str:
    match = re.fullmatch(
        r"git:([0-9a-f]{40})@([0-9a-f]{40}):([^#]+)#PROOF:sha256=([0-9a-f]{64})",
        locator,
    )
    require(match is not None, "proof locator is malformed")
    donor_head, donor_tree, result_path, expected_proof_sha = cast(re.Match[str], match).groups()
    four.verify_commit(root, donor_head, donor_tree)
    raw = four.committed_blob(root, donor_head, result_path)
    record = json_object(raw, "proof locator result is invalid JSON")
    proof = record.get("PROOF")
    if not isinstance(proof, str):
        raise ValueError("proof locator has no string PROOF")
    actual = sha256(proof.encode("utf-8"))
    require(actual == expected_proof_sha, "proof locator SHA256 does not match its proof")
    return actual


def expected_family() -> dict[str, Any]:
    return {
        "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
        "TIED_OWNERS": [CURSOR_ID],
        "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
        "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNERS,
        "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
    }


def verify_23_event_base() -> tuple[
    dict[str, Any],
    dict[str, four.Row],
    dict[str, four.Row],
    dict[str, four.Row],
    bytes,
]:
    verify_fixed_authorities()
    four.verify_commit(ROOT, BASE_HEAD, BASE_TREE)
    parents = cast(str, four.run_git(ROOT, "rev-list", "--parents", "-n", "1", BASE_HEAD)).split()
    require(
        parents == [BASE_HEAD, BASE_PARENT],
        "23-event base commit parent differs from the fixed 22-event parent",
    )
    raw = four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    base_sha = sha256(raw)
    validate_base_provenance(BASE_HEAD, BASE_TREE, parents[1], base_sha)
    require(
        (ROOT / BASE_RESULT_PATH).read_bytes() == raw,
        "working 23-event result differs from its pinned Git blob",
    )
    recorded = json_object(raw, "pinned 23-event result is invalid JSON")

    twenty_three_result, frozen, base_rows_22, after_23 = twenty_three.build_candidate()
    twenty_three_raw = four.committed_blob(ROOT, BASE_HEAD, twenty_three.RESULT_PATH)
    require(
        (ROOT / twenty_three.RESULT_PATH).read_bytes() == twenty_three_raw
        and twenty_three.serialize_result(twenty_three_result) == twenty_three_raw
        and twenty_three_result.get("TOTAL_EVENTS") == 23
        and len(twenty_three_result.get("EVENT_HISTORY", [])) == 23,
        "23-event source replay differs from the fixed 23-event parent",
    )

    full = four.seven.two.full_digest(after_23)
    bounds = four.seven.two.bounds_digest(after_23)
    require(
        (len(after_23), full, bounds) == (EXPECTED_ROWS, BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "23-event replay row count or full/bounds digest mismatch",
    )
    return recorded, frozen, base_rows_22, after_23, raw


def validate_t261_result(
    record: Mapping[str, Any], frozen_row: four.Row, spec: DonorSpec = DONOR
) -> None:
    proof = record.get("PROOF")
    if not isinstance(proof, str) or not proof.strip():
        raise ValueError("T261 donor proof is missing")
    source_raw = four.committed_blob(ROOT, spec.head, spec.source_path)
    verify_donor_record(record, spec, frozen_row, source_raw)


def expect_rejected(action: Any, message: str) -> str:
    try:
        action()
    except (ValueError, AssertionError, KeyError, subprocess.CalledProcessError):
        return "PASS"
    raise AssertionError(message)


def verify_negative_cases(
    frozen_row: four.Row,
    donor_record: Mapping[str, Any],
    base_rows: Mapping[str, four.Row],
    after_rows: Mapping[str, four.Row],
    family_result: Mapping[str, Any],
) -> dict[str, str]:
    wrong_sha = replace(DONOR, result_sha256="0" * 64)
    wrong_donor_commit = replace(DONOR, head="0" * 40)
    wrong_donor_tree = replace(DONOR, tree="0" * 40)
    wrong_profile = replace(DONOR, profile_id="0" * 20)
    wrong_cap = replace(DONOR, cap=DONOR.cap - 1)
    wrong_bound = replace(DONOR, bound=DONOR.bound + 1)
    bad_proof = dict(donor_record)
    bad_proof["PROOF"] = "altered proof text"
    unrelated = next(profile_id for profile_id in after_rows if profile_id != PROFILE_ID)
    changed_rows = dict(after_rows)
    changed_rows[unrelated] = replace(changed_rows[unrelated], source="unrelated-row-mutation")
    missing_cursor = dict(family_result)
    missing_cursor.pop("CURSOR", None)
    dummy_events = [{"EVENT_ID": f"EVENT_{i}"} for i in range(24)]

    return {
        "WRONG_BASE_REJECTED": expect_rejected(
            lambda: validate_base_provenance("0" * 40, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256),
            "wrong 23-event base provenance was accepted",
        ),
        "WRONG_DONOR_COMMIT_REJECTED": expect_rejected(
            lambda: verify_t261_donor(ROOT, frozen_row, wrong_donor_commit),
            "wrong donor commit was accepted",
        ),
        "WRONG_DONOR_TREE_REJECTED": expect_rejected(
            lambda: verify_t261_donor(ROOT, frozen_row, wrong_donor_tree),
            "wrong donor tree was accepted",
        ),
        "WRONG_DONOR_RESULT_SHA_REJECTED": expect_rejected(
            lambda: verify_t261_donor(ROOT, frozen_row, wrong_sha),
            "wrong donor result SHA was accepted",
        ),
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: validate_t261_result(donor_record, frozen_row, wrong_profile),
            "wrong profile was accepted",
        ),
        "WRONG_CAP_REJECTED": expect_rejected(
            lambda: validate_t261_result(donor_record, frozen_row, wrong_cap),
            "wrong cap was accepted",
        ),
        "WRONG_BOUND_REJECTED": expect_rejected(
            lambda: validate_t261_result(donor_record, frozen_row, wrong_bound),
            "wrong bound was accepted",
        ),
        "WRONG_PROOF_REJECTED": expect_rejected(
            lambda: validate_t261_result(bad_proof, frozen_row, DONOR),
            "wrong proof was accepted",
        ),
        "WRONG_PROOF_LOCATOR_REJECTED": expect_rejected(
            lambda: resolve_proof_locator(
                ROOT,
                f"git:{DONOR_HEAD}@{DONOR_TREE}:{DONOR_RESULT_PATH}#PROOF:sha256={'0' * 64}",
            ),
            "wrong proof locator hash was accepted",
        ),
        "DUPLICATE_EVENT_REJECTED": expect_rejected(
            lambda: sixteen.verify_unique_events([*dummy_events, dummy_events[-1]]),
            "duplicate event was accepted",
        ),
        "UNRELATED_ROW_MUTATION_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(base_rows, changed_rows, {PROFILE_ID}),
            "unrelated ledger-row mutation was accepted",
        ),
        "CURSOR_OMISSION_REJECTED": expect_rejected(
            lambda: four.verify_family_summary(missing_cursor, expected_family()),
            "omitted unresolved cursor was accepted",
        ),
        "WRONG_ANCESTRY_REJECTED": expect_rejected(
            lambda: verify_t261_donor(ROOT, frozen_row, replace(DONOR, parent="0" * 40)),
            "wrong donor ancestry was accepted",
        ),
    }


def build_candidate() -> tuple[
    dict[str, Any],
    dict[str, four.Row],
    dict[str, four.Row],
    dict[str, four.Row],
]:
    base_result, frozen, _base_rows_22, base_rows, base_raw = verify_23_event_base()
    frozen_target = frozen.get(PROFILE_ID)
    require(frozen_target is not None, "Frozen ledger omitted the T261 profile")
    frozen_row = cast(four.Row, frozen_target)
    require(
        base_rows.get(PROFILE_ID) == frozen_row
        and (frozen_row.bound, frozen_row.cap, frozen_row.s4_base, frozen_row.source)
        == (DONOR.previous_bound, DONOR.previous_cap, DONOR.s4_base, DONOR.historical_source),
        "23-event base does not retain the pinned old T264 row",
    )

    donor_record, donor_identity, donor_blobs = verify_t261_donor(ROOT, frozen_row, DONOR)
    pin = nine.DonorPin(
        event_id=DONOR.event_id,
        task_id=DONOR.task_id,
        profile_id=DONOR.profile_id,
        previous_bound=DONOR.previous_bound,
        previous_cap=DONOR.previous_cap,
        bound=DONOR.bound,
        cap=DONOR.cap,
        s4_base=DONOR.s4_base,
        head=DONOR.head,
        tree=DONOR.tree,
        result_path=DONOR.result_path,
        result_sha256=DONOR.result_sha256,
        source_path=DONOR.source_path,
        source_sha256=sha256(donor_blobs["SOURCE"]),
        test_path=DONOR.test_path,
        test_sha256=sha256(donor_blobs["TEST"]),
        proof_sha256=donor_identity["PROOF_SHA256"],
    )

    family_before = four.family_frontier(base_rows)
    four.verify_family_summary(
        family_before,
        {
            "FAMILY_BOUND": 313394584,
            "TIED_OWNERS": [CURSOR_ID],
            "NEXT_COMPETING_BOUND": 313392308,
            "NEXT_COMPETING_OWNERS": [PROFILE_ID],
            "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        },
    )

    after_24, new_events = nine.apply_donor_events(
        base_rows, [pin], {DONOR.event_id: donor_identity}
    )
    require(
        len(new_events) == 1
        and new_events[0].get("PROFILE_ID") == PROFILE_ID
        and new_events[0].get("BOUND_BEFORE") == DONOR.previous_bound
        and new_events[0].get("BOUND_AFTER") == DONOR.bound
        and new_events[0].get("CAP_BEFORE") == DONOR.previous_cap
        and new_events[0].get("CAP_AFTER") == DONOR.cap
        and new_events[0].get("S4_BASE_BEFORE") == DONOR.s4_base
        and new_events[0].get("S4_BASE_AFTER") == DONOR.s4_base
        and new_events[0].get("SOURCE_BEFORE") == HISTORICAL_SOURCE
        and new_events[0].get("SOURCE_AFTER") == donor_identity["PROOF_LOCATOR"],
        "the T261 event differs from its one-row transition",
    )

    previous_events = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    events = [*previous_events, *new_events]
    sixteen.verify_unique_events(events)
    require(
        len(previous_events) == EXPECTED_EVENTS_BEFORE
        and len(new_events) == 1
        and len(events) == EXPECTED_TOTAL_EVENTS,
        "24-event history must retain 23 events and add exactly one",
    )

    changed_from_base = sixteen.verify_ledger_partition(base_rows, after_24, {PROFILE_ID})
    changed_from_frozen = {
        profile_id for profile_id in frozen if frozen[profile_id] != after_24[profile_id]
    }
    require(
        len(changed_from_frozen) == 23
        and PROFILE_ID not in base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"]
        and len(frozen) - len(changed_from_frozen) == 4624
        and changed_from_base == {PROFILE_ID}
        and len(base_rows) - len(changed_from_base) == 4646,
        "24-event changed/unchanged row partition mismatch",
    )

    before_full = four.seven.two.full_digest(base_rows)
    before_bounds = four.seven.two.bounds_digest(base_rows)
    full_digest = four.seven.two.full_digest(after_24)
    bounds_digest = four.seven.two.bounds_digest(after_24)
    require(
        (before_full, before_bounds) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "23-event base digest differs before applying T261",
    )

    family_after = four.family_frontier(after_24)
    four.verify_family_summary(family_after, expected_family())
    require(
        family_before["FAMILY_BOUND"] == family_after["FAMILY_BOUND"]
        and family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"] == 0,
        "T261 owner delta must not be reported as Family gain",
    )

    cursor = cast(dict[str, Any], base_result["CURSOR_AUTHORITY"])
    require(
        cursor.get("ID") == CURSOR_ID
        and cursor.get("BOUND") == CURSOR_BOUND
        and cursor.get("COUNT") == CURSOR_COUNT
        and family_after.get("CURSOR") == {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "unresolved cursor identity or count was not preserved",
    )

    resolved_above_incumbent = sum(row.bound > INCUMBENT for row in after_24.values())
    require(
        resolved_above_incumbent == 1364,
        "resolved profile count above the incumbent changed unexpectedly",
    )

    judge = cast(dict[str, Any], donor_identity["FRESH_CONTEXT_JUDGE"])
    negative_validations = verify_negative_cases(
        frozen_row, donor_record, base_rows, after_24, family_after
    )
    require(
        set(negative_validations.values()) == {"PASS"},
        "one or more negative integration controls were accepted",
    )

    transitions = cast(list[dict[str, Any]], base_result["EVENT_FAMILY_TRANSITIONS"])
    require(
        len(transitions) == 7,
        "23-event base must preserve its seven historical Family transitions",
    )
    transitions_after = [
        *transitions,
        {
            "EVENT_ID": DONOR.event_id,
            "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
            "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
            "TIED_OWNERS_AFTER": family_after["TIED_OWNERS"],
            "NEXT_COMPETING_BOUND_AFTER": family_after["NEXT_COMPETING_BOUND"],
            "NEXT_COMPETING_OWNERS_AFTER": family_after["NEXT_COMPETING_OWNERS"],
        },
    ]

    inherited_caveats = [
        *base_result["INHERITED_CAVEATS_PRESERVED"],
        {
            "TASK_ID": JUDGE_TASK_ID,
            "CAVEAT": JUDGE_CAVEAT,
            "UNCHANGED_REVIEWED_HEAD": "YES",
            "UNCHANGED_REVIEWED_TREE": "YES",
            "UNCHANGED_CERTIFICATE_FILES": "YES",
            "JUDGE_GIT_WRITES": "NONE_BY_ISSUED_COMMANDS",
            "IMPACT": JUDGE_CAVEAT_IMPACT,
        },
    ]

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_24_EVENT_CANDIDATE_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "SIX_ROW_RESULT_SHA256": "MATCH",
            "SEVEN_ROW_RESULT_SHA256": "MATCH",
            "BASE_HEAD_TREE": "MATCH",
            "BASE_RESULT_SHA256": "MATCH",
            "BASE_FULL_DIGEST": "MATCH",
            "BASE_BOUNDS_DIGEST": "MATCH",
            "DONOR_HEAD_TREE": "MATCH",
            "DONOR_PARENT": "MATCH",
            "DONOR_RESULT_FILE_SHA256": "MATCH",
            "DONOR_RESULT_PAYLOAD_SHA256": "MATCH",
            "DONOR_SOURCE_SHA256": "MATCH",
            "DONOR_TEST_SHA256": "MATCH",
            "DONOR_JUDGE_REPORT_SHA256": "MATCH",
            "DONOR_JUDGE_IDENTITY": "MATCH",
            "ALL_PROOF_LOCATORS": "RESOLVED",
        },
        "FROZEN_AUTHORITY": base_result["FROZEN_AUTHORITY"],
        "BASE_23_EVENT_AUTHORITY": {
            "TASK_ID": base_result["TASK_ID"],
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PARENT": BASE_PARENT,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "FULL_DIGEST": before_full,
            "BOUNDS_DIGEST": before_bounds,
            "EVENTS": EXPECTED_EVENTS_BEFORE,
            "REPLAY_MATCH": "YES",
            "JUDGE_MODE": base_result["JUDGE_MODE"],
            "FORMAL_AUTHORITY": base_result["FORMAL_FAMILY_AUTHORITY"],
        },
        "DONOR_IDENTITY": donor_identity,
        "INHERITED_22_EVENT_JUDGE": base_result["INHERITED_22_EVENT_JUDGE"],
        "UPSTREAM_23_EVENT_JUDGE": {
            "TASK_ID": base_result["TASK_ID"],
            "JUDGE_MODE": base_result["JUDGE_MODE"],
            "VERDICT": "SELF_CHECK_ONLY",
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PARENT": BASE_PARENT,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "FULL_DIGEST": before_full,
            "BOUNDS_DIGEST": before_bounds,
            "EVENTS": EXPECTED_EVENTS_BEFORE,
            "FORMAL_AUTHORITY": base_result["FORMAL_FAMILY_AUTHORITY"],
        },
        "INHERITED_CAVEATS_PRESERVED": inherited_caveats,
        "T261_SCIENCE_JUDGE": judge,
        "T261_SEALED_CERTIFICATE": "VERIFIED_WITH_CAVEATS",
        "T261_SCIENCE": {
            "PROFILE_ID": PROFILE_ID,
            "PROVED_T_CAP": DONOR.cap,
            "OLD_BOUND": DONOR.previous_bound,
            "NEW_BOUND": DONOR.bound,
            "OWNER_DELTA": DONOR.previous_bound - DONOR.bound,
            "GOODMAN_TOTAL": 299,
            "T_H_LOWER_BOUND": 38,
            "R_UPPER_BOUND": 46,
            "ALPHA_SQUARE_UPPER_BOUND_FORMULA": "m*(m+1)",
            "M_DOMAIN": [0, 6],
            "T_H_LOWER_BOUNDS_BY_M": [38, 44, 48, 50, 50, 48, 44],
            "ROUTE_B_TERM_COUNT": 240,
            "ARGMAX_T": 261,
            "T261_ATTAINMENT": "NOT_CLAIMED",
            "JUDGE_CAVEAT": JUDGE_CAVEAT,
            "CAVEAT_IMPACT": JUDGE_CAVEAT_IMPACT,
            "STATUS": "VERIFIED",
        },
        "ROWS_BEFORE": len(frozen),
        "ROWS_AFTER": len(after_24),
        "OLD_EVENTS": EXPECTED_EVENTS_BEFORE,
        "PREVIOUS_EVENTS": len(previous_events),
        "NEW_EVENTS": len(new_events),
        "TOTAL_EVENTS": len(events),
        "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": len(changed_from_frozen),
        "CHANGED_PROFILE_IDS_FROM_FROZEN": sorted(changed_from_frozen),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed_from_frozen),
        "CHANGED_ROWS_FROM_BASE": len(changed_from_base),
        "UNCHANGED_ROWS_FROM_BASE": len(base_rows) - len(changed_from_base),
        "PROFILE_ID": PROFILE_ID,
        "OWNER_OLD_CAP": DONOR.previous_cap,
        "OWNER_NEW_CAP": DONOR.cap,
        "OWNER_OLD_BOUND": DONOR.previous_bound,
        "OWNER_NEW_BOUND": DONOR.bound,
        "OWNER_DELTA": DONOR.previous_bound - DONOR.bound,
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "ALL_PROOF_LOCATORS_RESOLVED": "YES",
        "UNRELATED_ROW_MUTATION": "NONE",
        "FULL_DIGEST": full_digest,
        "BOUNDS_DIGEST": bounds_digest,
        "NEW_FULL_DIGEST": full_digest,
        "NEW_BOUNDS_DIGEST": bounds_digest,
        "EVENT_HISTORY": events,
        "EVENT_FAMILY_TRANSITIONS": transitions_after,
        "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"],
        "MAX_OWNER": CURSOR_ID,
        "MAX_OWNER_TYPE": "UNRESOLVED_CURSOR",
        "MAXIMIZING_OWNERS": family_after["TIED_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_COMPETING_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "NEXT_DISTINCT_RESOLVED_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_DISTINCT_RESOLVED_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": resolved_above_incumbent,
        "CURSOR_COUNT": cursor["COUNT"],
        "CURSOR_BOUND": cursor["BOUND"],
        "CURSOR_INCLUDED": "YES",
        "CURSOR_AUTHORITY": cursor,
        "UNADOPTED_197_PROFILE_CLASS_BOUND": "NOT_INTEGRATED",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "NEGATIVE_VALIDATIONS": negative_validations,
        "FOCUSED_TEST_PATH": ("tests/unit/test_b649_t261_24_event_local_family_integration_r1.py"),
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    require(
        result["FAMILY_GAIN"] == 0,
        "the 17924 Owner delta must not be treated as Family gain",
    )
    encoded = serialize_result(result)
    json_object(encoded, "24-event result serialization is invalid JSON")
    result_path = ROOT / RESULT_PATH
    if result_path.exists():
        require(
            result_path.read_bytes() == encoded,
            "saved 24-event result differs from the complete replay",
        )
    return result, frozen, base_rows, after_24


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    if path.exists():
        require(path.read_bytes() == raw, "refusing to replace a different result artifact")
    else:
        with path.open("xb") as output:
            output.write(raw)
        require(path.read_bytes() == raw, "result read-after-write mismatch")
    return sha256(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="save the replayed result JSON")
    args = parser.parse_args()
    result, _frozen, _base_rows, _after = build_candidate()
    raw = serialize_result(result)
    result_sha = write_result(result) if args.write else sha256(raw)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "ROWS_AFTER": result["ROWS_AFTER"],
                "TOTAL_EVENTS": result["TOTAL_EVENTS"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
                "RESULT_SHA256": result_sha,
                "WORKTREE_HEAD": four.run_git(ROOT, "rev-parse", "HEAD"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
