"""Replay the pinned 24-event B649 family and integrate one judged T255 row."""

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
from . import b649_t261_24_event_local_family_integration_r1 as base

TASK_ID = "B649_T255_25_EVENT_FROM_T261_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = "docs/research/matrix-native-results/b649-t255-25-event-from-t261-r1-result.json"

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"

BASE_HEAD = "ee4bb2f22ff101522e73952a3f11c66c55d95098"
BASE_TREE = "876d80cb5fb524af925bd35e0d6042093248710e"
BASE_PARENT = "2fab6c5d8046ce2a063b44f7f9d45f25085dda59"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-t261-24-event-local-family-integration-r1-result.json"
)
BASE_RESULT_SHA256 = "a1a40b170ff8e0eb7b9fcf10d33ecf56b1ceaa0a92652facea2f3e8bcfcbca7e"
BASE_FULL_DIGEST = "3d5d699f1186f0792329d1b4b85ae0e2f9ea9fdb8b3ca00826de6ce13eb4b67b"
BASE_BOUNDS_DIGEST = "b3f24bc6032485f0cd52eff45e2d26eef0da34eedfd6b81701f6c47a8ad0a2e9"

DONOR_EVENT_ID = "T255_66666555554411100000"
DONOR_TASK_ID = "B649_NEXT_RESOLVED_OWNER_66666555554411100000_R1"
PROFILE_ID = "66666555554411100000"
DONOR_HEAD = "f078addd6551f8eb0c183709ae7d1afc288899ec"
DONOR_TREE = "d326b210ba3976923ef61e66d733e77ed7c836b7"
DONOR_PARENT = FROZEN_HEAD
DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-next-resolved-owner-66666555554411100000-r1-result.json"
)
DONOR_RESULT_SHA256 = "31650a5b232af97de718fda2fdb37b173ad54603295283c897887885205f6cc0"
DONOR_SOURCE_PATH = "src/lottolab/research/b649_next_resolved_owner_66666555554411100000_r1.py"
DONOR_SOURCE_SHA256 = "6047e429c45124a848a58a0ae02b6d28e97e3aecac415317759b2a698b3999be"
DONOR_TEST_PATH = "tests/unit/test_b649_next_resolved_owner_66666555554411100000_r1.py"
DONOR_TEST_SHA256 = "9c2aafdad79d1870d2f418f9fc1a0f97068ef118b16870ab31343f7f953ef7a6"
DONOR_PROOF_SHA256 = "e82aecb6a12b73f5b7ffed3443e9252d83ad85ee604303ab53c4b118e9df8f98"

JUDGE_TASK_ID = "B649_NEXT_OWNER_T255_FRESH_CONTEXT_JUDGE_R1"
JUDGE_SESSION_ID = "01a13e50-3032-7f60-976b-c79c07465fdc"
JUDGE_REPORT_PATH = (
    "/Users/kelvin/.codex/attachments/"
    "ef74e011-5e0e-4d7f-9dc2-831bf9e91314/"
    "B649_NEXT_OWNER_T255_FRESH_CONTEXT_JUDGE_R1/verdict-report.txt"
)
JUDGE_REPORT_SHA256 = "139db27cfe0b89982fe1f00cdde006e13756f5ebba45aa1e9147287919f5caa9"

OLD_CAP = 264
NEW_CAP = 255
OLD_BOUND = 313_391_920
NEW_BOUND = 313_320_224
OWNER_DELTA = 71_696
TARGET_T_CAP = 262
TERM_COUNT = 234
ARGMAX_T = 255
CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
CURSOR_COUNT = 197
EXPECTED_FAMILY_BOUND = 313_394_584
EXPECTED_NEXT_BOUND = 313_392_232
EXPECTED_NEXT_OWNERS = ["65555555555442000000", "66555555554433000000"]

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
    head: str
    tree: str
    parent: str
    result_path: str
    result_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    proof_sha256: str


DONOR = DonorSpec(
    event_id=DONOR_EVENT_ID,
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_ID,
    previous_bound=OLD_BOUND,
    previous_cap=OLD_CAP,
    bound=NEW_BOUND,
    cap=NEW_CAP,
    s4_base=112,
    head=DONOR_HEAD,
    tree=DONOR_TREE,
    parent=DONOR_PARENT,
    result_path=DONOR_RESULT_PATH,
    result_sha256=DONOR_RESULT_SHA256,
    source_path=DONOR_SOURCE_PATH,
    source_sha256=DONOR_SOURCE_SHA256,
    test_path=DONOR_TEST_PATH,
    test_sha256=DONOR_TEST_SHA256,
    proof_sha256=DONOR_PROOF_SHA256,
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


def validate_base_provenance(head: str, tree: str, parent: str, result_sha256: str) -> None:
    require(head == BASE_HEAD, "24-event base commit mismatch")
    require(tree == BASE_TREE, "24-event base tree mismatch")
    require(parent == BASE_PARENT, "24-event base parent mismatch")
    require(result_sha256 == BASE_RESULT_SHA256, "24-event base result SHA256 mismatch")


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
    require(parents == [BASE_HEAD, BASE_PARENT], "24-event base ancestry mismatch")
    raw = four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    validate_base_provenance(BASE_HEAD, BASE_TREE, parents[1], sha256(raw))
    require((ROOT / BASE_RESULT_PATH).read_bytes() == raw, "24-event base result bytes mismatch")

    result, frozen_rows, _rows_23, after_24 = base.build_candidate()
    require(
        base.serialize_result(result) == raw
        and result.get("TASK_ID") == "B649_T261_24_EVENT_LOCAL_FAMILY_INTEGRATION_R1"
        and len(result.get("EVENT_HISTORY", [])) == 24
        and result.get("TOTAL_EVENTS") == 24
        and result.get("ROWS_AFTER") == 4_647,
        "complete 24-event Base replay mismatch",
    )
    full = four.seven.two.full_digest(after_24)
    bounds = four.seven.two.bounds_digest(after_24)
    require(
        (len(frozen_rows), len(after_24), full, bounds)
        == (4_647, 4_647, BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        and (result.get("FULL_DIGEST"), result.get("BOUNDS_DIGEST")) == (full, bounds),
        "24-event Base row count or digest replay mismatch",
    )
    return result, frozen_rows, after_24, raw


def validate_donor_record(record: Mapping[str, Any], source_raw: bytes, spec: DonorSpec) -> str:
    try:
        module = compile(source_raw.decode("utf-8"), spec.source_path, "exec")
        source_doc = module.co_consts[0]
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("T255 donor source proof cannot be parsed") from exc
    proof = record.get("PROOF")
    if not isinstance(proof, str) or not proof.strip():
        raise ValueError("T255 donor proof is missing")
    if not isinstance(source_doc, str):
        raise ValueError("T255 donor source has no module proof docstring")
    require(source_doc == proof, "T255 donor result PROOF differs from source docstring")
    proof_sha = sha256(proof.encode("utf-8"))
    require(proof_sha == spec.proof_sha256, "T255 donor proof SHA256 mismatch")
    require(
        record.get("TASK_ID") == spec.task_id and record.get("PROFILE_ID") == spec.profile_id,
        "T255 donor task/profile mismatch",
    )
    require(
        record.get("SOURCE_T_CAP") == spec.previous_cap
        and record.get("SOURCE_ROW_BOUND") == spec.previous_bound
        and record.get("PROVED_T_CAP") == spec.cap
        and record.get("NEW_ADMISSIBLE_BOUND") == spec.bound
        and record.get("OWNER_BOUND_DELTA") == spec.previous_bound - spec.bound,
        "T255 donor cap/bound transition mismatch",
    )
    require(
        record.get("TARGET_T_CAP") == TARGET_T_CAP
        and record.get("ATTAINMENT") == "NOT_ASSERTED"
        and record.get("PROOF_SCOPE") == "FULL_PROFILE",
        "T255 donor caveat or proof scope changed",
    )
    route_value = record.get("ROUTE_B")
    if not isinstance(route_value, dict):
        raise ValueError("T255 Route-B result is missing")
    route = cast(dict[str, Any], route_value)
    terms_value = route.get("ALL_T_TERMS")
    argmax_value = route.get("ARGMAX_TERM")
    if not isinstance(terms_value, list) or not terms_value:
        raise ValueError("T255 Route-B term list is missing")
    if not isinstance(argmax_value, list):
        raise ValueError("T255 Route-B argmax is missing")
    terms = cast(list[list[Any]], terms_value)
    argmax = cast(list[Any], argmax_value)
    require(
        len(terms) == TERM_COUNT
        and terms[0][0] == 22
        and terms[-1][0] == ARGMAX_T
        and argmax[:2] == [ARGMAX_T, spec.bound],
        "T255 Route-B domain or argmax mismatch",
    )
    return proof_sha


def verify_judge_report() -> dict[str, Any]:
    report_path = Path(JUDGE_REPORT_PATH)
    raw = report_path.read_bytes()
    require(sha256(raw) == JUDGE_REPORT_SHA256, "fresh-context Judge report SHA256 mismatch")
    report = raw.decode("utf-8")
    required_lines = (
        f"TASK_ID: {JUDGE_TASK_ID}",
        "FRESH_CONTEXT_VERDICT: VERIFIED_WITH_CAVEATS",
        f"REVIEWED_HEAD: {DONOR_HEAD}",
        f"REVIEWED_TREE: {DONOR_TREE}",
        f"REVIEWED_RESULT_SHA256: {DONOR_RESULT_SHA256}",
        PROFILE_ID,
        "PROVED_T_CAP: 255",
        "NEW_BOUND: 313320224",
        "OWNER_DELTA: 71696",
        "T255_ATTAINMENT: NOT_CLAIMED",
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
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "REVIEWED_HEAD": DONOR_HEAD,
        "REVIEWED_TREE": DONOR_TREE,
        "DONOR_RESULT_SHA256": DONOR_RESULT_SHA256,
        "PROFILE_ID": PROFILE_ID,
        "PROVED_T_CAP": NEW_CAP,
        "NEW_BOUND": NEW_BOUND,
        "OWNER_DELTA": OWNER_DELTA,
        "T255_ATTAINMENT": "NOT_CLAIMED",
        "METADATA_CAVEAT": "TARGET_T_CAP=262; PROVED_T_CAP=255; SOURCE_T_CAP=264",
    }


def resolve_proof_locator(root: Path, locator: str) -> str:
    match = re.fullmatch(
        r"git:([0-9a-f]{40})@([0-9a-f]{40}):([^#]+)#PROOF:sha256=([0-9a-f]{64})",
        locator,
    )
    if match is None:
        raise ValueError("proof locator is malformed")
    head, tree, result_path, expected_sha = match.groups()
    four.verify_commit(root, head, tree)
    raw = four.committed_blob(root, head, result_path)
    proof_value = json_object(raw, "proof locator result is invalid JSON").get("PROOF")
    if not isinstance(proof_value, str):
        raise ValueError("proof locator does not resolve a string PROOF")
    proof = proof_value
    actual = sha256(proof.encode("utf-8"))
    require(actual == expected_sha, "proof locator SHA256 does not match /PROOF")
    return actual


def verify_donor(
    base_rows: Mapping[str, Row], spec: DonorSpec = DONOR
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    four.verify_commit(ROOT, spec.head, spec.tree)
    parents = git_text("rev-list", "--parents", "-n", "1", spec.head).split()
    require(parents == [spec.head, spec.parent], "T255 donor parent is not the Frozen HEAD")
    paths = {
        "RESULT": spec.result_path,
        "SOURCE": spec.source_path,
        "TEST": spec.test_path,
    }
    blobs = {key: four.committed_blob(ROOT, spec.head, path) for key, path in paths.items()}
    require(sha256(blobs["RESULT"]) == spec.result_sha256, "T255 donor result SHA256 mismatch")
    require(sha256(blobs["SOURCE"]) == spec.source_sha256, "T255 donor source SHA256 mismatch")
    require(sha256(blobs["TEST"]) == spec.test_sha256, "T255 donor test SHA256 mismatch")
    record = json_object(blobs["RESULT"], "T255 donor result is invalid JSON")
    proof_sha = validate_donor_record(record, blobs["SOURCE"], spec)
    row = base_rows.get(spec.profile_id)
    if row is None:
        raise ValueError("24-event Base omitted the T255 profile")
    require(
        (row.bound, row.cap, row.s4_base) == (spec.previous_bound, spec.previous_cap, spec.s4_base),
        "T255 Base row does not match the pinned old cap/bound",
    )

    judge = verify_judge_report()
    proof_locator = f"git:{spec.head}@{spec.tree}:{spec.result_path}#PROOF:sha256={proof_sha}"
    require(resolve_proof_locator(ROOT, proof_locator) == proof_sha, "T255 proof locator mismatch")
    row_source = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f";RESULT_SHA256={spec.result_sha256}"
        f";SOURCE_SHA256={spec.source_sha256}"
        f";JUDGE_REPORT_SHA256={judge['REPORT_SHA256']}"
        f";JUDGE_TASK_ID={judge['TASK_ID']}"
        f";JUDGE_SESSION_ID={judge['SESSION_ID']}"
        f";JUDGE_VERDICT={judge['VERDICT']}"
        f"#PROOF:sha256={proof_sha}"
    )
    identity: dict[str, Any] = {
        "EVENT_ID": spec.event_id,
        "TASK_ID": spec.task_id,
        "HEAD": spec.head,
        "TREE": spec.tree,
        "PARENT": spec.parent,
        "HEAD_TREE": "MATCH",
        "RESULT_PATH": spec.result_path,
        "RESULT_SHA256": sha256(blobs["RESULT"]),
        "SOURCE_PATH": spec.source_path,
        "SOURCE_SHA256": sha256(blobs["SOURCE"]),
        "TEST_PATH": spec.test_path,
        "TEST_SHA256": sha256(blobs["TEST"]),
        "PROFILE_ID": spec.profile_id,
        "CAP_BEFORE": spec.previous_cap,
        "BOUND_BEFORE": spec.previous_bound,
        "CAP_AFTER": spec.cap,
        "BOUND_AFTER": spec.bound,
        "S4_BASE": spec.s4_base,
        "OWNER_DELTA": spec.previous_bound - spec.bound,
        "WORKER_JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROOF_SHA256": proof_sha,
        "PROOF_LOCATOR": proof_locator,
        "JUDGE_REPORT_SHA256": judge["REPORT_SHA256"],
        "ROW_SOURCE": row_source,
        "FRESH_CONTEXT_JUDGE": judge,
        "METADATA_CAVEAT": "TARGET_T_CAP=262; PROVED_T_CAP=255; SOURCE_T_CAP=264",
    }
    require(
        f"RESULT_SHA256={spec.result_sha256}" in row_source
        and f"SOURCE_SHA256={spec.source_sha256}" in row_source
        and f"JUDGE_REPORT_SHA256={judge['REPORT_SHA256']}" in row_source,
        "T255 Row.source is not bound to result/source/Judge evidence",
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
    frozen_row: Row,
    donor_record: Mapping[str, Any],
    donor_source: bytes,
    base_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    family_result: Mapping[str, Any],
) -> dict[str, str]:
    unrelated = next(profile_id for profile_id in after_rows if profile_id != PROFILE_ID)
    changed_rows = dict(after_rows)
    changed_rows[unrelated] = replace(changed_rows[unrelated], source="unrelated-row-mutation")
    missing_cursor = dict(family_result)
    missing_cursor.pop("CURSOR", None)
    bad_proof = dict(donor_record)
    bad_proof["PROOF"] = "altered proof text"
    events = [{"EVENT_ID": f"EVENT_{index}"} for index in range(25)]
    wrong_sha = replace(DONOR, result_sha256="0" * 64)
    wrong_head = replace(DONOR, head="0" * 40)
    wrong_tree = replace(DONOR, tree="0" * 40)
    wrong_parent = replace(DONOR, parent="0" * 40)

    return {
        "WRONG_BASE_REJECTED": expect_rejected(
            lambda: validate_base_provenance("0" * 40, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256),
            "wrong base was accepted",
        ),
        "WRONG_DONOR_REJECTED": expect_rejected(
            lambda: verify_donor(base_rows, wrong_head),
            "wrong donor head was accepted",
        ),
        "WRONG_DONOR_TREE_REJECTED": expect_rejected(
            lambda: verify_donor(base_rows, wrong_tree),
            "wrong donor tree was accepted",
        ),
        "WRONG_DONOR_RESULT_SHA_REJECTED": expect_rejected(
            lambda: verify_donor(base_rows, wrong_sha),
            "wrong donor result SHA was accepted",
        ),
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: validate_donor_record(
                donor_record, donor_source, replace(DONOR, profile_id="0" * 20)
            ),
            "wrong donor profile was accepted",
        ),
        "WRONG_CAP_REJECTED": expect_rejected(
            lambda: validate_donor_record(
                donor_record, donor_source, replace(DONOR, cap=NEW_CAP + 1)
            ),
            "wrong donor cap was accepted",
        ),
        "WRONG_BOUND_REJECTED": expect_rejected(
            lambda: validate_donor_record(
                donor_record, donor_source, replace(DONOR, bound=NEW_BOUND + 1)
            ),
            "wrong donor bound was accepted",
        ),
        "WRONG_PROOF_REJECTED": expect_rejected(
            lambda: validate_donor_record(bad_proof, donor_source, DONOR),
            "wrong donor proof was accepted",
        ),
        "WRONG_PROOF_LOCATOR_REJECTED": expect_rejected(
            lambda: resolve_proof_locator(
                ROOT,
                f"git:{DONOR_HEAD}@{DONOR_TREE}:{DONOR_RESULT_PATH}#PROOF:sha256={'0' * 64}",
            ),
            "wrong proof locator was accepted",
        ),
        "DUPLICATE_EVENT_REJECTED": expect_rejected(
            lambda: sixteen.verify_unique_events([*events, events[-1]]),
            "duplicate event was accepted",
        ),
        "UNRELATED_ROW_CHANGE_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(base_rows, changed_rows, {PROFILE_ID}),
            "unrelated row mutation was accepted",
        ),
        "CURSOR_OMISSION_REJECTED": expect_rejected(
            lambda: four.verify_family_summary(missing_cursor, expected_family()),
            "omitted unresolved cursor was accepted",
        ),
        "WRONG_ANCESTRY_REJECTED": expect_rejected(
            lambda: verify_donor(base_rows, wrong_parent),
            "wrong donor ancestry was accepted",
        ),
        "WRONG_BASE_RESULT_SHA_REJECTED": expect_rejected(
            lambda: validate_base_provenance(BASE_HEAD, BASE_TREE, BASE_PARENT, "0" * 64),
            "wrong base result SHA was accepted",
        ),
        "UNRELATED_BASE_ROW_CHANGE_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(
                base_rows,
                {
                    **after_rows,
                    unrelated: replace(after_rows[unrelated], source="unrelated-row-mutation"),
                },
                {PROFILE_ID},
            ),
            "unrelated base row mutation was accepted",
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
    frozen_row = frozen_rows.get(PROFILE_ID)
    require(frozen_row is not None, "Frozen ledger omitted the T255 profile")
    frozen_row = cast(Row, frozen_row)
    require(
        base_rows.get(PROFILE_ID) == frozen_row
        and (frozen_row.bound, frozen_row.cap, frozen_row.s4_base) == (OLD_BOUND, OLD_CAP, 112),
        "24-event Base does not retain the T255 row before update",
    )

    donor_record, donor_identity, donor_blobs = verify_donor(base_rows)
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
        source_sha256=DONOR.source_sha256,
        test_path=DONOR.test_path,
        test_sha256=DONOR.test_sha256,
        proof_sha256=DONOR.proof_sha256,
    )
    family_before = four.family_frontier(base_rows)
    four.verify_family_summary(family_before, expected_family())
    after_25, new_events = nine.apply_donor_events(
        base_rows, [pin], {DONOR.event_id: donor_identity}
    )
    require(
        len(new_events) == 1
        and new_events[0].get("EVENT_ID") == DONOR.event_id
        and new_events[0].get("PROFILE_ID") == PROFILE_ID
        and (new_events[0].get("CAP_BEFORE"), new_events[0].get("CAP_AFTER")) == (OLD_CAP, NEW_CAP)
        and (new_events[0].get("BOUND_BEFORE"), new_events[0].get("BOUND_AFTER"))
        == (OLD_BOUND, NEW_BOUND)
        and new_events[0].get("SOURCE_AFTER") == donor_identity["ROW_SOURCE"],
        "T255 event is not the pinned one-row transition",
    )

    prior_events = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    events = [*prior_events, *new_events]
    sixteen.verify_unique_events(events)
    require(
        len(prior_events) == 24 and len(new_events) == 1 and len(events) == 25,
        "25-event history must replay 24 events and add exactly one",
    )
    changed_from_base = sixteen.verify_ledger_partition(base_rows, after_25, {PROFILE_ID})
    changed_from_frozen = {
        profile_id for profile_id in frozen_rows if frozen_rows[profile_id] != after_25[profile_id]
    }
    require(
        len(frozen_rows) == len(after_25) == 4_647
        and changed_from_base == {PROFILE_ID}
        and len(base_rows) - len(changed_from_base) == 4_646
        and len(changed_from_frozen) == 24
        and len(frozen_rows) - len(changed_from_frozen) == 4_623
        and PROFILE_ID not in base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"],
        "25-event changed/unchanged row partition mismatch",
    )

    full_before = four.seven.two.full_digest(base_rows)
    bounds_before = four.seven.two.bounds_digest(base_rows)
    full_after = four.seven.two.full_digest(after_25)
    bounds_after = four.seven.two.bounds_digest(after_25)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "24-event Base digest changed before the T255 event",
    )
    family_after = four.family_frontier(after_25)
    four.verify_family_summary(family_after, expected_family())
    require(
        family_before["FAMILY_BOUND"] == family_after["FAMILY_BOUND"]
        and family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"] == 0,
        "Owner delta must not be reported as Family gain",
    )
    cursor = cast(dict[str, Any], base_result["CURSOR_AUTHORITY"])
    require(
        cursor.get("ID") == CURSOR_ID
        and cursor.get("BOUND") == CURSOR_BOUND
        and cursor.get("COUNT") == CURSOR_COUNT
        and family_after.get("CURSOR") == {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "197-profile unresolved cursor was not preserved",
    )
    resolved_above_incumbent = sum(row.bound > base.INCUMBENT for row in after_25.values())
    require(resolved_above_incumbent == 1_364, "resolved profile count changed unexpectedly")

    negative = verify_negative_cases(
        frozen_row,
        donor_record,
        donor_blobs["SOURCE"],
        base_rows,
        after_25,
        family_after,
    )
    require(set(negative.values()) == {"PASS"}, "a negative integration control was accepted")
    transitions = cast(list[dict[str, Any]], base_result["EVENT_FAMILY_TRANSITIONS"])
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
            "REPORT_SHA256": JUDGE_REPORT_SHA256,
            "PROFILE_ID": PROFILE_ID,
            "PROVED_T_CAP": NEW_CAP,
            "CAVEAT": "TARGET_T_CAP=262 while PROVED_T_CAP=255 and SOURCE_T_CAP=264",
            "IMPACT": "NON_BLOCKING_METADATA_CAVEAT",
        },
    ]
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_25_EVENT_CANDIDATE_REPLAYED",
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
            "DONOR_SOURCE_SHA256": "MATCH",
            "DONOR_TEST_SHA256": "MATCH",
            "DONOR_PROOF_LOCATOR": "RESOLVED",
            "DONOR_JUDGE_REPORT_SHA256": "MATCH",
            "DONOR_JUDGE_BINDING": "MATCH",
        },
        "FROZEN_AUTHORITY": base_result["FROZEN_AUTHORITY"],
        "BASE_24_EVENT_AUTHORITY": {
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
        "DONOR_IDENTITY": donor_identity,
        "UPSTREAM_24_EVENT_JUDGE_MODE": base_result["JUDGE_MODE"],
        "UPSTREAM_24_EVENT_FORMAL_AUTHORITY": base_result["FORMAL_FAMILY_AUTHORITY"],
        "INHERITED_T261_SCIENCE_JUDGE": base_result["T261_SCIENCE_JUDGE"],
        "INHERITED_CAVEATS_PRESERVED": inherited_caveats,
        "PROFILE_ID": PROFILE_ID,
        "OLD_CAP": OLD_CAP,
        "NEW_CAP": NEW_CAP,
        "OLD_BOUND": OLD_BOUND,
        "NEW_BOUND": NEW_BOUND,
        "OWNER_DELTA": OWNER_DELTA,
        "T255_ATTAINMENT": "NOT_CLAIMED",
        "METADATA_CAVEAT": "TARGET_T_CAP=262; PROVED_T_CAP=255; SOURCE_T_CAP=264",
        "ROWS_BEFORE": len(frozen_rows),
        "ROWS_AFTER": len(after_25),
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
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"],
        "MAX_OWNER": CURSOR_ID,
        "MAX_OWNER_TYPE": "UNRESOLVED_CURSOR",
        "MAXIMIZING_OWNERS": family_after["TIED_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_DISTINCT_RESOLVED_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_DISTINCT_RESOLVED_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "NEXT_RESOLVED_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_RESOLVED_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": resolved_above_incumbent,
        "CURSOR_AUTHORITY": cursor,
        "CURSOR_BOUND": cursor["BOUND"],
        "CURSOR_COUNT": cursor["COUNT"],
        "CURSOR_INCLUDED": "YES",
        "UNADOPTED_197_PROFILE_CLASS_BOUND": base_result["UNADOPTED_197_PROFILE_CLASS_BOUND"],
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "NEGATIVE_VALIDATIONS": negative,
        "FOCUSED_TEST_PATH": ("tests/unit/test_b649_t255_25_event_from_t261_r1.py"),
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    require(
        result["OWNER_DELTA"] == 71_696
        and result["FAMILY_GAIN"] == 0
        and result["NEW_BOUND"] == 313_320_224,
        "Owner delta and Family gain were conflated",
    )
    encoded = serialize_result(result)
    json_object(encoded, "25-event result serialization is invalid JSON")
    result_path = ROOT / RESULT_PATH
    if result_path.exists():
        require(result_path.read_bytes() == encoded, "saved result differs from replay")
    return result, frozen_rows, base_rows, after_25


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
                "ROWS_BEFORE": result["ROWS_BEFORE"],
                "ROWS_AFTER": result["ROWS_AFTER"],
                "EVENTS_BEFORE": result["OLD_EVENTS"],
                "EVENTS_AFTER": result["TOTAL_EVENTS"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
                "FAMILY_BOUND": result["FAMILY_BOUND_AFTER"],
                "FAMILY_GAIN": result["FAMILY_GAIN"],
                "NEXT_RESOLVED_BOUND": result["NEXT_RESOLVED_BOUND"],
                "NEXT_RESOLVED_OWNERS": result["NEXT_RESOLVED_OWNERS"],
                "RESULT_SHA256": result_sha,
                "WORKTREE_HEAD": git_text("rev-parse", "HEAD"),
                "WORKTREE_BRANCH": git_text("branch", "--show-current"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
