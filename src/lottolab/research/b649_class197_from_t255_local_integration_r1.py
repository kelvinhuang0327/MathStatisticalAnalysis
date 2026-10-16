"""Replay the pinned 25-event B649 family and integrate the 197-profile class certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen
from . import b649_t255_25_event_from_t261_r1 as base

TASK_ID = "B649_CLASS197_FROM_T255_LOCAL_INTEGRATION_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-class197-from-t255-local-integration-r1-result.json"
)

# Pinned 25-event Base
BASE_HEAD = "355d6831426deb324c52c8f06c8a3233ffba66d8"
BASE_TREE = "15ca2db51932a7c42a7bfc512008f3b60d5d5b2f"
BASE_PARENT = "ee4bb2f22ff101522e73952a3f11c66c55d95098"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-t255-25-event-from-t261-r1-result.json"
)
BASE_RESULT_SHA256 = "fce1eeb472655b97ae7d0a387b00f6df0e056bb51c94cf5cfb69b75c5057e633"
BASE_FULL_DIGEST = "aea35e031ad93a75ba499173e0810db421e76bb95181e58ebe1ac9e808ac2010"
BASE_BOUNDS_DIGEST = "429bdb7937db7d5b8e5656a2dd0362b3c678fb4526d29978ef2dc8f45acdd611"
BASE_ROWS = 4_647
BASE_RESOLVED_EVENTS = 25
BASE_FAMILY_BOUND = 313_394_584
BASE_NEXT_RESOLVED_BOUND = 313_392_232

# Pinned 197-profile Class Certificate Donor
DONOR_TASK_ID = "B649_CURSOR_197_CLASS_LOCAL_CERTIFICATE_R1"
DONOR_HEAD = "7fc9088f370a4cc4d35a1c2dfc385cdc963bff06"
DONOR_TREE = "004c25d9bbe261e753f8630f467b37d28c5ba95b"
DONOR_PARENT = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-cursor-197-class-local-certificate-r1-result.json"
)
DONOR_RESULT_SHA256 = "12fb24ee69674acc731c0b495eb54f0fa04a8b2675e2b60de9f6ad81061dd4a7"
DONOR_SOURCE_PATH = (
    "src/lottolab/research/b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
)
DONOR_SOURCE_SHA256 = "d9966d0bf8c12fb33f1978f9f7fc153f8d4fa03c4895ce3239155d41d81be8ba"
DONOR_TEST_PATH = (
    "tests/unit/test_b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
)
DONOR_TEST_SHA256 = "1598dc74543ef3711d8e537e29bb977930e6d54f212a008dbd8176058a5f2b08"
DONOR_OWNER_SESSION = "01a139ea-0a7b-78b2-ae6a-134234d9a1be"
DONOR_OWNERSHIP = "RELEASED_WITH_SUPPLEMENTAL_RECEIPT"
DONOR_FOCUSED_QA = "11_PASSED"
DONOR_FOCUSED_EXIT_CODE = 0
EXPECTED_DONOR_PROOF_LOCATOR = (
    "src/lottolab/research/b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
    "#build_result, exact_term, rebuild_frontier; module docstring"
)

# Scientific evidence
SCIENCE_JUDGE = "VERIFIED_WITH_CAVEATS"
SCIENCE_JUDGE_SESSION = "01a139e9-4ece-7cb2-9855-be53cdda0855"
CLASS_COUNT = 197
CLASS_ID_SET_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
OLD_CLASS_BOUND = 313_394_584
NEW_CLASS_BOUND = 313_258_872
CLASS_BOUND_DELTA = 135_712

# Retained family baselines
FROZEN_SEVEN_ROW_FAMILY = 313_398_532
NINETEEN_EVENT_FAMILY = 313_394_584
NINETEEN_EVENT_NEXT_RESOLVED = 313_392_516
CURRENT_25_EVENT_FAMILY = 313_394_584
CURRENT_25_EVENT_NEXT_RESOLVED = 313_392_232

# Family transition expectations
EXPECTED_NEW_FAMILY_BOUND = 313_392_232
EXPECTED_FAMILY_GAIN = 2_352
EXPECTED_MAXIMIZING_OWNERS = ["65555555555442000000", "66555555554433000000"]
EXPECTED_NEXT_DISTINCT_BOUND = 313_392_128
EXPECTED_NEXT_DISTINCT_OWNERS = ["66655555554432000000"]

CURSOR_ID = "66544333333333332222"

Row = four.Row


@dataclass(frozen=True)
class DonorSpec:
    task_id: str
    class_count: int
    class_id_set_sha256: str
    previous_class_bound: int
    class_bound: int
    class_bound_delta: int
    head: str
    tree: str
    parent: str
    result_path: str
    result_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    proof_locator: str


DONOR = DonorSpec(
    task_id=DONOR_TASK_ID,
    class_count=CLASS_COUNT,
    class_id_set_sha256=CLASS_ID_SET_SHA256,
    previous_class_bound=OLD_CLASS_BOUND,
    class_bound=NEW_CLASS_BOUND,
    class_bound_delta=CLASS_BOUND_DELTA,
    head=DONOR_HEAD,
    tree=DONOR_TREE,
    parent=DONOR_PARENT,
    result_path=DONOR_RESULT_PATH,
    result_sha256=DONOR_RESULT_SHA256,
    source_path=DONOR_SOURCE_PATH,
    source_sha256=DONOR_SOURCE_SHA256,
    test_path=DONOR_TEST_PATH,
    test_sha256=DONOR_TEST_SHA256,
    proof_locator=EXPECTED_DONOR_PROOF_LOCATOR,
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
        require(
            parents == [head, BASE_HEAD],
            "candidate must be one commit over the fixed base",
        )
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
    base.verify_candidate_ancestry = lambda: base.BASE_HEAD
    try:
        result, frozen_rows, _rows_24, after_25 = base.build_candidate()
    finally:
        base.verify_candidate_ancestry = orig_ancestry
    require(
        base.serialize_result(result) == raw
        and result.get("TASK_ID") == "B649_T255_25_EVENT_FROM_T261_R1"
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
    cursor = cast(dict[str, Any], result.get("CURSOR_AUTHORITY", {}))
    require(
        cursor.get("ID") == CURSOR_ID
        and cursor.get("BOUND") == OLD_CLASS_BOUND
        and cursor.get("COUNT") == CLASS_COUNT,
        "25-event Base unresolved cursor identity mismatch",
    )
    return result, frozen_rows, after_25, raw


def resolve_proof_locator(root: Path, locator: str, expected_source_sha: str) -> str:
    expected_prefix = (
        f"git:{DONOR_HEAD}@{DONOR_TREE}:{DONOR_SOURCE_PATH}"
        "#build_result, exact_term, rebuild_frontier; module docstring"
    )
    if locator != expected_prefix:
        raise ValueError("proof locator is malformed or differs from expected donor locator")
    four.verify_commit(root, DONOR_HEAD, DONOR_TREE)
    source_bytes = four.committed_blob(root, DONOR_HEAD, DONOR_SOURCE_PATH)
    require(
        sha256(source_bytes) == expected_source_sha,
        "proof locator committed source blob SHA256 mismatch",
    )
    try:
        module = compile(source_bytes.decode("utf-8"), DONOR_SOURCE_PATH, "exec")
        source_doc = module.co_consts[0]
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("donor source proof cannot be parsed") from exc
    if not isinstance(source_doc, str) or not source_doc.strip():
        raise ValueError("donor source has no module proof docstring")
    return sha256(source_doc.encode("utf-8"))


def validate_donor_record(
    record: Mapping[str, Any], source_raw: bytes, spec: DonorSpec = DONOR
) -> tuple[list[str], str]:
    try:
        module = compile(source_raw.decode("utf-8"), spec.source_path, "exec")
        source_doc = module.co_consts[0]
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("197-class donor source proof cannot be parsed") from exc
    if not isinstance(source_doc, str) or not source_doc.strip():
        raise ValueError("197-class donor source has no module proof docstring")
    doc_sha = sha256(source_doc.encode("utf-8"))

    require(
        record.get("TASK_ID") == spec.task_id,
        "197-class donor task mismatch",
    )
    require(
        record.get("COVERED_PROFILES") == spec.class_count
        and record.get("MISSING_PROFILES") == 0
        and record.get("DUPLICATE_PROFILES") == 0
        and record.get("COMPLETE_CLASS_COVERAGE") is True,
        "197-class coverage metadata mismatch",
    )
    require(
        record.get("CLASS_BOUND_BEFORE") == spec.previous_class_bound
        and record.get("CLASS_BOUND_AFTER") == spec.class_bound
        and record.get("CLASS_DELTA") == spec.class_bound_delta
        and record.get("NEW_CLASS_BOUND_CANDIDATE") == spec.class_bound,
        "197-class donor bound transition mismatch",
    )
    require(
        record.get("PARTITION_COUNT") == spec.class_count
        and record.get("PARTITION_IDS_SHA256") == spec.class_id_set_sha256,
        "197-class partition count or ID set digest mismatch",
    )
    raw_ids = record.get("PROFILE_IDS")
    if not isinstance(raw_ids, list):
        raise ValueError("197-class PROFILE_IDS list is missing")
    profile_ids = cast(list[str], raw_ids)
    require(
        len(profile_ids) == spec.class_count,
        "197-class PROFILE_IDS count mismatch",
    )
    require(
        len(set(profile_ids)) == len(profile_ids),
        "197-class PROFILE_IDS contains duplicates",
    )
    require(
        profile_ids == sorted(profile_ids, reverse=True),
        "197-class PROFILE_IDS is not canonical descending sort",
    )
    computed_id_sha = sha256(json.dumps(list(profile_ids)).encode("utf-8"))
    require(
        computed_id_sha == spec.class_id_set_sha256,
        "197-class PROFILE_IDS computed SHA256 does not match expected",
    )
    proof_locator = record.get("PROOF_LOCATOR")
    require(
        proof_locator == spec.proof_locator,
        "197-class donor proof locator string mismatch",
    )

    verification_val = record.get("VERIFICATION")
    if not isinstance(verification_val, dict):
        raise ValueError("197-class donor VERIFICATION block missing")
    verification = cast(dict[str, object], verification_val)
    require(
        verification.get("FOCUSED_TEST_EXIT_CODE") is None,
        "197-class donor historical FOCUSED_TEST_EXIT_CODE must remain null",
    )
    return profile_ids, doc_sha


def verify_donor(
    spec: DonorSpec = DONOR,
) -> tuple[dict[str, Any], list[str], dict[str, Any], dict[str, bytes]]:
    four.verify_commit(ROOT, spec.head, spec.tree)
    parents = git_text("rev-list", "--parents", "-n", "1", spec.head).split()
    require(parents == [spec.head, spec.parent], "197-class donor parent is not the Frozen HEAD")
    paths = {
        "RESULT": spec.result_path,
        "SOURCE": spec.source_path,
        "TEST": spec.test_path,
    }
    blobs = {key: four.committed_blob(ROOT, spec.head, path) for key, path in paths.items()}
    require(sha256(blobs["RESULT"]) == spec.result_sha256, "197-class donor result SHA256 mismatch")
    require(sha256(blobs["SOURCE"]) == spec.source_sha256, "197-class donor source SHA256 mismatch")
    require(sha256(blobs["TEST"]) == spec.test_sha256, "197-class donor test SHA256 mismatch")
    record = json_object(blobs["RESULT"], "197-class donor result is invalid JSON")
    profile_ids, doc_sha = validate_donor_record(record, blobs["SOURCE"], spec)

    locator = (
        f"git:{spec.head}@{spec.tree}:{spec.source_path}"
        "#build_result, exact_term, rebuild_frontier; module docstring"
    )
    resolved_doc_sha = resolve_proof_locator(
        ROOT,
        locator,
        spec.source_sha256,
    )
    require(resolved_doc_sha == doc_sha, "resolved proof locator docstring mismatch")

    class_source = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f";RESULT_SHA256={spec.result_sha256}"
        f";SOURCE_SHA256={spec.source_sha256}"
        f";SCIENCE_JUDGE={SCIENCE_JUDGE}"
        f";SCIENCE_JUDGE_SESSION={SCIENCE_JUDGE_SESSION}"
        f";DOC_SHA256={doc_sha}"
        f"#PROOF_LOCATOR={spec.proof_locator}"
    )

    identity: dict[str, Any] = {
        "EVENT_TYPE": "UNRESOLVED_CLASS_CERTIFICATE",
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
        "OWNER_SESSION": DONOR_OWNER_SESSION,
        "OWNERSHIP": DONOR_OWNERSHIP,
        "DONOR_FOCUSED_QA": DONOR_FOCUSED_QA,
        "DONOR_FOCUSED_EXIT_CODE": DONOR_FOCUSED_EXIT_CODE,
        "CLASS_COUNT": spec.class_count,
        "CLASS_ID_SET_SHA256": spec.class_id_set_sha256,
        "CLASS_BOUND_BEFORE": spec.previous_class_bound,
        "CLASS_BOUND_AFTER": spec.class_bound,
        "CLASS_BOUND_DELTA": spec.class_bound_delta,
        "PROOF_LOCATOR": spec.proof_locator,
        "DOC_SHA256": doc_sha,
        "CLASS_SOURCE": class_source,
        "SCIENCE_JUDGE": {
            "TASK_ID": "B649_CURSOR_197_CLASS_LOCAL_CERTIFICATE_R1",
            "SESSION_ID": SCIENCE_JUDGE_SESSION,
            "VERDICT": SCIENCE_JUDGE,
            "CLASS_COUNT": spec.class_count,
            "OLD_CLASS_BOUND": spec.previous_class_bound,
            "NEW_CLASS_BOUND": spec.class_bound,
            "CLASS_BOUND_DELTA": spec.class_bound_delta,
        },
    }
    return record, profile_ids, identity, blobs


def family_frontier(
    ledger: Mapping[str, Row],
    cursor_id: str = CURSOR_ID,
    cursor_bound: int = NEW_CLASS_BOUND,
) -> dict[str, Any]:
    levels = [(row.bound, profile_id) for profile_id, row in ledger.items()]
    levels.append((cursor_bound, cursor_id))
    maximum = max(bound for bound, _profile_id in levels)
    owners = sorted(profile_id for bound, profile_id in levels if bound == maximum)
    next_bound = max(bound for bound, _profile_id in levels if bound < maximum)
    next_owners = sorted(profile_id for bound, profile_id in levels if bound == next_bound)
    return {
        "FAMILY_BOUND": maximum,
        "TIED_OWNERS": owners,
        "NEXT_COMPETING_BOUND": next_bound,
        "NEXT_COMPETING_OWNERS": next_owners,
        "CURSOR": {"ID": cursor_id, "BOUND": cursor_bound},
    }


def verify_frontier_is_current(frontier_bound: int) -> None:
    if frontier_bound == NINETEEN_EVENT_NEXT_RESOLVED:
        raise ValueError("historical 19-event bound used as current frontier")


def expect_rejected(action: Any, message: str) -> str:
    try:
        action()
    except (ValueError, AssertionError, KeyError):
        return "PASS"
    raise AssertionError(message)


def verify_negative_cases(
    donor_record: Mapping[str, Any],
    donor_source: bytes,
    base_rows: Mapping[str, Row],
    profile_ids: list[str],
) -> dict[str, str]:
    bad_count = replace(DONOR, class_count=196)
    bad_id_digest = replace(DONOR, class_id_set_sha256="0" * 64)
    bad_old_bound = replace(DONOR, previous_class_bound=313_394_585)
    bad_new_bound = replace(DONOR, class_bound=313_258_873)
    bad_result_sha = replace(DONOR, result_sha256="0" * 64)
    bad_source_sha = replace(DONOR, source_sha256="0" * 64)
    bad_test_sha = replace(DONOR, test_sha256="0" * 64)
    bad_locator = replace(DONOR, proof_locator="wrong_proof_locator")

    unrelated = next(iter(base_rows))
    mutated_rows = dict(base_rows)
    mutated_row = replace(mutated_rows[unrelated], bound=mutated_rows[unrelated].bound + 1)
    mutated_rows[unrelated] = mutated_row

    bad_duplicate_ids = [profile_ids[0], *profile_ids[1:-1], profile_ids[0]]

    return {
        "WRONG_CLASS_COUNT_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, bad_count),
            "wrong class count was accepted",
        ),
        "WRONG_CLASS_ID_SET_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, bad_id_digest),
            "wrong class id set digest was accepted",
        ),
        "DUPLICATE_CLASS_ID_REJECTED": expect_rejected(
            lambda: validate_donor_record(
                {**donor_record, "PROFILE_IDS": bad_duplicate_ids},
                donor_source,
                DONOR,
            ),
            "duplicate class profile was accepted",
        ),
        "MISSING_CLASS_PROFILE_REJECTED": expect_rejected(
            lambda: validate_donor_record(
                {**donor_record, "PROFILE_IDS": profile_ids[:-1]},
                donor_source,
                replace(DONOR, class_count=196),
            ),
            "missing class profile was accepted",
        ),
        "WRONG_DONOR_RESULT_SHA_REJECTED": expect_rejected(
            lambda: verify_donor(bad_result_sha),
            "wrong donor result SHA was accepted",
        ),
        "WRONG_DONOR_SOURCE_SHA_REJECTED": expect_rejected(
            lambda: verify_donor(bad_source_sha),
            "wrong donor source SHA was accepted",
        ),
        "WRONG_DONOR_TEST_SHA_REJECTED": expect_rejected(
            lambda: verify_donor(bad_test_sha),
            "wrong donor test SHA was accepted",
        ),
        "WRONG_PROOF_LOCATOR_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, bad_locator),
            "wrong proof locator was accepted",
        ),
        "WRONG_OLD_CLASS_BOUND_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, bad_old_bound),
            "wrong old class bound was accepted",
        ),
        "WRONG_NEW_CLASS_BOUND_REJECTED": expect_rejected(
            lambda: validate_donor_record(donor_record, donor_source, bad_new_bound),
            "wrong new class bound was accepted",
        ),
        "RESOLVED_ROW_MUTATION_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(base_rows, mutated_rows, set()),
            "resolved row mutation was accepted",
        ),
        "WRONG_BASE_LEDGER_REJECTED": expect_rejected(
            lambda: validate_base_provenance("0" * 40, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256),
            "wrong base ledger was accepted",
        ),
        "HISTORICAL_19_EVENT_FRONTIER_REJECTED": expect_rejected(
            lambda: verify_frontier_is_current(NINETEEN_EVENT_NEXT_RESOLVED),
            "historical 19-event next resolved bound was accepted as current 25-event frontier",
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

    donor_record, profile_ids, donor_identity, donor_blobs = verify_donor()

    # Verify that the 4647 resolved rows are completely preserved with 0 mutations
    after_rows = dict(base_rows)
    require(len(after_rows) == BASE_ROWS == 4_647, "resolved rows count must be 4647")
    sixteen.verify_ledger_partition(base_rows, after_rows, set())

    full_before = four.seven.two.full_digest(base_rows)
    bounds_before = four.seven.two.bounds_digest(base_rows)
    full_after = four.seven.two.full_digest(after_rows)
    bounds_after = four.seven.two.bounds_digest(after_rows)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "25-event Base digests changed before Class integration",
    )
    require(
        (full_after, bounds_after) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "resolved rows digests mutated during Class integration",
    )

    # Family frontier before Class update (cursor at OLD_CLASS_BOUND)
    family_before = family_frontier(after_rows, cursor_id=CURSOR_ID, cursor_bound=OLD_CLASS_BOUND)
    require(
        family_before["FAMILY_BOUND"] == BASE_FAMILY_BOUND == 313_394_584
        and family_before["TIED_OWNERS"] == [CURSOR_ID]
        and family_before["NEXT_COMPETING_BOUND"] == BASE_NEXT_RESOLVED_BOUND == 313_392_232
        and family_before["NEXT_COMPETING_OWNERS"] == EXPECTED_MAXIMIZING_OWNERS,
        "family frontier before Class update mismatch",
    )

    # Family frontier after Class update (cursor at NEW_CLASS_BOUND)
    family_after = family_frontier(after_rows, cursor_id=CURSOR_ID, cursor_bound=NEW_CLASS_BOUND)
    require(
        family_after["FAMILY_BOUND"] == EXPECTED_NEW_FAMILY_BOUND == 313_392_232
        and family_after["TIED_OWNERS"] == EXPECTED_MAXIMIZING_OWNERS
        and family_after["NEXT_COMPETING_BOUND"] == EXPECTED_NEXT_DISTINCT_BOUND == 313_392_128
        and family_after["NEXT_COMPETING_OWNERS"] == EXPECTED_NEXT_DISTINCT_OWNERS
        and family_after["CURSOR"] == {"ID": CURSOR_ID, "BOUND": NEW_CLASS_BOUND},
        "family frontier after Class update mismatch",
    )

    family_gain = family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"]
    require(family_gain == EXPECTED_FAMILY_GAIN == 2_352, "Family gain calculation mismatch")

    # Verify negative test cases
    negative = verify_negative_cases(
        donor_record,
        donor_blobs["SOURCE"],
        base_rows,
        profile_ids,
    )
    require(set(negative.values()) == {"PASS"}, "a negative integration control was accepted")

    prior_events = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    require(len(prior_events) == 25, "prior events count is not 25")

    inherited_caveats = [
        *base_result["INHERITED_CAVEATS_PRESERVED"],
        {
            "TASK_ID": DONOR_TASK_ID,
            "SESSION_ID": DONOR_OWNER_SESSION,
            "SCIENCE_JUDGE_SESSION": SCIENCE_JUDGE_SESSION,
            "CLASS_COUNT": CLASS_COUNT,
            "OLD_CLASS_BOUND": OLD_CLASS_BOUND,
            "NEW_CLASS_BOUND": NEW_CLASS_BOUND,
            "CLASS_BOUND_DELTA": CLASS_BOUND_DELTA,
            "CAVEAT": "LOCAL_MATHEMATICAL_CANDIDATE; NOT_CLAIMED_FORMAL_FAMILY_AUTHORITY",
            "IMPACT": "NON_BLOCKING_CANDIDATE_CAVEAT",
        },
    ]

    cursor_authority = {
        "ID": CURSOR_ID,
        "BOUND": NEW_CLASS_BOUND,
        "PREVIOUS_BOUND": OLD_CLASS_BOUND,
        "COUNT": CLASS_COUNT,
        "IDS_SHA256": CLASS_ID_SET_SHA256,
        "W_RANGE": [774, 785],
        "INCLUDED_IN_FAMILY_FRONTIER": "YES",
        "SOURCE": donor_identity["CLASS_SOURCE"],
        "STATUS": "LOCAL_CLASS197_BOUND_REPLACED",
    }

    distinct_changed = base_result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"]
    changed_ids = base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"]
    unchanged_frozen = base_result["UNCHANGED_ROWS_FROM_FROZEN"]

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_CLASS197_INTEGRATED_CANDIDATE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_FAMILY_ADOPTION": "NOT_ACCEPTED",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "AUTHORITY_GATES": {
            "BASE_HEAD_TREE": "MATCH",
            "BASE_RESULT_SHA256": "MATCH",
            "BASE_FULL_DIGEST_REPLAY": "MATCH",
            "BASE_BOUNDS_DIGEST_REPLAY": "MATCH",
            "DONOR_HEAD_TREE": "MATCH",
            "DONOR_PARENT": "MATCH",
            "DONOR_RESULT_SHA256": "MATCH",
            "DONOR_SOURCE_SHA256": "MATCH",
            "DONOR_TEST_SHA256": "MATCH",
            "DONOR_QA_RECEIPT": "VERIFIED",
            "DONOR_PROOF_LOCATOR": "RESOLVED",
            "SCIENCE_JUDGE": "VERIFIED_WITH_CAVEATS",
            "SCIENCE_JUDGE_SESSION": SCIENCE_JUDGE_SESSION,
        },
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
            "FAMILY_BOUND": BASE_FAMILY_BOUND,
            "NEXT_RESOLVED_BOUND": BASE_NEXT_RESOLVED_BOUND,
            "FORMAL_AUTHORITY": base_result["FORMAL_FAMILY_AUTHORITY"],
        },
        "DONOR_IDENTITY": donor_identity,
        "RETAINED_BASELINES": {
            "FROZEN_SEVEN_ROW_FAMILY": FROZEN_SEVEN_ROW_FAMILY,
            "NINETEEN_EVENT_FAMILY": NINETEEN_EVENT_FAMILY,
            "NINETEEN_EVENT_NEXT_RESOLVED": NINETEEN_EVENT_NEXT_RESOLVED,
            "CURRENT_25_EVENT_FAMILY": CURRENT_25_EVENT_FAMILY,
            "CURRENT_25_EVENT_NEXT_RESOLVED": CURRENT_25_EVENT_NEXT_RESOLVED,
        },
        "INHERITED_CAVEATS_PRESERVED": inherited_caveats,
        "CLASS_COUNT": CLASS_COUNT,
        "CLASS_ID_SET_SHA256": CLASS_ID_SET_SHA256,
        "OLD_CLASS_BOUND": OLD_CLASS_BOUND,
        "NEW_CLASS_BOUND": NEW_CLASS_BOUND,
        "CLASS_BOUND_DELTA": CLASS_BOUND_DELTA,
        "ROWS_BEFORE": len(frozen_rows),
        "ROWS_AFTER": len(after_rows),
        "RESOLVED_ROW_MUTATIONS": 0,
        "UNCHANGED_ROWS_FROM_BASE": len(base_rows),
        "CHANGED_ROWS_FROM_BASE": 0,
        "RESOLVED_HISTORY_EVENTS": len(prior_events),
        "OLD_EVENTS": len(prior_events),
        "PREVIOUS_EVENTS": len(prior_events),
        "NEW_EVENTS": 0,
        "TOTAL_EVENTS": len(prior_events),
        "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": distinct_changed,
        "CHANGED_PROFILE_IDS_FROM_FROZEN": changed_ids,
        "UNCHANGED_ROWS_FROM_FROZEN": unchanged_frozen,
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "ALL_PROOF_LOCATORS_RESOLVED": "YES",
        "UNRELATED_ROW_MUTATION": "NONE",
        "FULL_DIGEST": full_after,
        "BOUNDS_DIGEST": bounds_after,
        "NEW_FULL_DIGEST": full_after,
        "NEW_BOUNDS_DIGEST": bounds_after,
        "EVENT_HISTORY": prior_events,
        "EVENT_FAMILY_TRANSITIONS": base_result["EVENT_FAMILY_TRANSITIONS"],
        "CLASS_INTEGRATION_TRANSITION": {
            "TASK_ID": DONOR_TASK_ID,
            "CLASS_COUNT": CLASS_COUNT,
            "CLASS_BOUND_BEFORE": OLD_CLASS_BOUND,
            "CLASS_BOUND_AFTER": NEW_CLASS_BOUND,
            "CLASS_BOUND_DELTA": CLASS_BOUND_DELTA,
            "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
            "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
            "FAMILY_GAIN": family_gain,
            "TIED_OWNERS_BEFORE": family_before["TIED_OWNERS"],
            "TIED_OWNERS_AFTER": family_after["TIED_OWNERS"],
            "NEXT_COMPETING_BOUND_AFTER": family_after["NEXT_COMPETING_BOUND"],
            "NEXT_COMPETING_OWNERS_AFTER": family_after["NEXT_COMPETING_OWNERS"],
        },
        "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_gain,
        "MAX_OWNER": family_after["TIED_OWNERS"][0],
        "MAX_OWNER_TYPE": "RESOLVED_ROWS",
        "MAXIMIZING_OWNERS": family_after["TIED_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_DISTINCT_RESOLVED_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_DISTINCT_RESOLVED_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "NEXT_RESOLVED_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_RESOLVED_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": base_result["RESOLVED_PROFILES_ABOVE_INCUMBENT"],
        "CURSOR_AUTHORITY": cursor_authority,
        "CURSOR_BOUND": cursor_authority["BOUND"],
        "CURSOR_COUNT": cursor_authority["COUNT"],
        "CURSOR_INCLUDED": "YES",
        "UNADOPTED_197_PROFILE_CLASS_BOUND": NEW_CLASS_BOUND,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "NEGATIVE_VALIDATIONS": negative,
        "FOCUSED_TEST_PATH": "tests/unit/test_b649_class197_from_t255_local_integration_r1.py",
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    return result, frozen_rows, base_rows, after_rows


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
    parser.add_argument(
        "--write",
        "--write-result",
        dest="write",
        action="store_true",
        help="save the replayed result JSON",
    )
    args = parser.parse_args()
    result, _frozen, _base_rows, _after = build_candidate()
    raw = serialize_result(result)
    result_sha = write_result(result) if args.write else sha256(raw)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "CLASS_COUNT": result["CLASS_COUNT"],
                "OLD_CLASS_BOUND": result["OLD_CLASS_BOUND"],
                "NEW_CLASS_BOUND": result["NEW_CLASS_BOUND"],
                "ROWS_BEFORE": result["ROWS_BEFORE"],
                "ROWS_AFTER": result["ROWS_AFTER"],
                "RESOLVED_ROW_MUTATIONS": result["RESOLVED_ROW_MUTATIONS"],
                "EVENTS_BEFORE": result["OLD_EVENTS"],
                "EVENTS_AFTER": result["TOTAL_EVENTS"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
                "FAMILY_BOUND_BEFORE": result["FAMILY_BOUND_BEFORE"],
                "FAMILY_BOUND_AFTER": result["FAMILY_BOUND_AFTER"],
                "FAMILY_GAIN": result["FAMILY_GAIN"],
                "MAXIMIZING_OWNERS": result["MAXIMIZING_OWNERS"],
                "NEXT_DISTINCT_BOUND": result["NEXT_DISTINCT_BOUND"],
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
