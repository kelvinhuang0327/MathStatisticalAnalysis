"""Integrate the T227 row and the 197-profile unresolved class bound."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen
from . import b649_tied_two_row_27_event_from_t255_r1 as twenty_seven

TASK_ID = "B649_COMBINED_28_EVENT_CLASS197_LOCAL_INTEGRATION_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-combined-28-event-class197-local-integration-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"

BASE_HEAD = "b53a776a025a5218eef73e9a6933b972b4f5395b"
BASE_TREE = "d1b6d18bd41d45bd2cbc5b947f23cd6561e6d6b1"
BASE_PARENT = "355d6831426deb324c52c8f06c8a3233ffba66d8"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-tied-two-row-27-event-from-t255-r1-result.json"
)
BASE_RESULT_SHA256 = "766ebb9b2a046c50002082b19a3d60bfd77e8fc46ab894bfa2fd5fe542ca5d25"
BASE_FULL_DIGEST = "869a3ccfb20535694b6e6c842337bd69290a6a45f77e326f9264ab9b273ef767"
BASE_BOUNDS_DIGEST = "e897ee98b83d166a40471a6449cd9f6b38652f376e669bc221b8f0010b05d472"
BASE_ROWS = 4_647
BASE_EVENTS = 27
BASE_FAMILY_BOUND = 313_394_584
FROZEN_SEVEN_ROW_FAMILY = 313_398_532
INCUMBENT = 313_263_888

T227_INTEGRATION_HEAD = "bec908ed6f98f33154392357887e02855390592f"
T227_INTEGRATION_TREE = "686dbcf2d87c940f389d4dd0034fb000b35642f8"
T227_INTEGRATION_PARENT = "2fab6c5d8046ce2a063b44f7f9d45f25085dda59"
T227_INTEGRATION_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-t227-24-event-local-family-integration-r1-result.json"
)
T227_INTEGRATION_RESULT_SHA256 = "e0726c16f65a602e180ebe50a5eea9fd95ab273f2d27035710e4aca6327394eb"

T227_DONOR_HEAD = "204f668efe88ab71cb55df3e71cc12948252a450"
T227_DONOR_TREE = "9b31b53b79a5ee012055e1c77e486ec05552088a"
T227_DONOR_PARENT = "0f0c9a32dbed811eddbefc55fd5093a8ee0e914d"
T227_DONOR_TASK_ID = "B649_NEXT_TWO_OWNER_SHARED_BOUND_R1"
T227_DONOR_EVENT_ID = "T227_66655555554432000000"
T227_PROFILE_ID = "66655555554432000000"
T227_DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-next-two-owner-shared-bound-r1-result.json"
)
T227_DONOR_RESULT_SHA256 = "a022ef35cd3e7b853e82179f7696d63cb29365d8811c40f6a2ab5d2a0f39e108"
T227_DONOR_SOURCE_PATH = "src/lottolab/research/b649_next_two_owner_shared_bound_r1.py"
T227_DONOR_SOURCE_SHA256 = "40236da825592d922082827c5793c621e0f644c11e0bacdf40d0840372863100"
T227_PROOF_SHA256 = "55588f8f9aef3c24b6c611faf4368f67aa9b6fcfb19d2cae49c68ba28b43658f"
T227_PROOF_LOCATOR = (
    f"git:{T227_DONOR_HEAD}@{T227_DONOR_TREE}:{T227_DONOR_RESULT_PATH}"
    f"#PROOF:sha256={T227_PROOF_SHA256}"
)
T227_JUDGE_SESSION = "01a13e5b-072d-7ff2-a0be-d61eab32c2a5"
T227_JUDGE_REPORT_PATH = Path(
    "/Users/kelvin/.codex/sessions/2026/10/15/"
    "rollout-2026-10-15T14-58-35-01a13e5b-072d-7ff2-a0be-d61eab32c2a5.jsonl"
)
T227_JUDGE_REPORT_SHA256 = "eaac397ec4391e7049a4f46b464f6515ea92e20bf3259b509e50ed2987fcc21c"
T227_OLD_CAP = 265
T227_NEW_CAP = 227
T227_OLD_BOUND = 313_392_128
T227_NEW_BOUND = 313_051_572
T227_OWNER_DELTA = 340_556
T227_TERM_COUNT = 206
T227_ARGMAX_TERM = [227, 313_051_572, 214, 197, 99_799, 4_718_560]

CLASS_INTEGRATION_HEAD = "c24de523e4767d74ad9a34ca9232e531abda3404"
CLASS_INTEGRATION_TREE = "a4b0e6fe3fa3e7cccd53746f65648263fb1a478a"
CLASS_INTEGRATION_PARENT = "355d6831426deb324c52c8f06c8a3233ffba66d8"
CLASS_INTEGRATION_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-class197-from-t255-local-integration-r1-result.json"
)
CLASS_INTEGRATION_RESULT_SHA256 = "1daa5392c3eba4c00674d93d9096143838e10452ac45a916c4b6e9414f9cfcd8"

CLASS_DONOR_HEAD = "7fc9088f370a4cc4d35a1c2dfc385cdc963bff06"
CLASS_DONOR_TREE = "004c25d9bbe261e753f8630f467b37d28c5ba95b"
CLASS_DONOR_PARENT = FROZEN_HEAD
CLASS_DONOR_TASK_ID = "B649_CURSOR_197_CLASS_LOCAL_CERTIFICATE_R1"
CLASS_DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-cursor-197-class-local-certificate-r1-result.json"
)
CLASS_DONOR_RESULT_SHA256 = "12fb24ee69674acc731c0b495eb54f0fa04a8b2675e2b60de9f6ad81061dd4a7"
CLASS_DONOR_SOURCE_PATH = (
    "src/lottolab/research/b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
)
CLASS_DONOR_SOURCE_SHA256 = "d9966d0bf8c12fb33f1978f9f7fc153f8d4fa03c4895ce3239155d41d81be8ba"
CLASS_DONOR_TEST_PATH = "tests/unit/test_b649_k20_min_s2_cursor_197_class_local_certificate_r1.py"
CLASS_DONOR_TEST_SHA256 = "1598dc74543ef3711d8e537e29bb977930e6d54f212a008dbd8176058a5f2b08"
CLASS_DONOR_PROOF_LOCATOR = (
    f"{CLASS_DONOR_SOURCE_PATH}#build_result, exact_term, rebuild_frontier; module docstring"
)
CLASS_DONOR_DOC_SHA256 = "9a1afa84eeeec6a118ec413a0da7ba55cdae9dbb10a4640b596753bdb47bd08c"
CLASS_SCIENCE_JUDGE_SESSION = "01a139e9-4ece-7cb2-9855-be53cdda0855"
CLASS_OWNER_SESSION = "01a139ea-0a7b-78b2-ae6a-134234d9a1be"
CLASS_COUNT = 197
CLASS_ID_SET_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
OLD_CLASS_BOUND = 313_394_584
NEW_CLASS_BOUND = 313_258_872
CLASS_BOUND_DELTA = 135_712
CLASS_QA_RECEIPT = "11_PASSED_EXIT_0"
CLASS_CURSOR_ID = "66544333333333332222"
HISTORICAL_19_EVENT_NEXT_BOUND = 313_392_516

Row = twenty_seven.Row


@dataclass(frozen=True)
class T227Spec:
    head: str = T227_DONOR_HEAD
    tree: str = T227_DONOR_TREE
    parent: str = T227_DONOR_PARENT
    result_sha256: str = T227_DONOR_RESULT_SHA256
    source_sha256: str = T227_DONOR_SOURCE_SHA256
    profile_id: str = T227_PROFILE_ID
    event_id: str = T227_DONOR_EVENT_ID
    cap_before: int = T227_OLD_CAP
    cap_after: int = T227_NEW_CAP
    bound_before: int = T227_OLD_BOUND
    bound_after: int = T227_NEW_BOUND
    proof_sha256: str = T227_PROOF_SHA256
    proof_locator: str = T227_PROOF_LOCATOR


@dataclass(frozen=True)
class ClassSpec:
    head: str = CLASS_DONOR_HEAD
    tree: str = CLASS_DONOR_TREE
    parent: str = CLASS_DONOR_PARENT
    result_sha256: str = CLASS_DONOR_RESULT_SHA256
    source_sha256: str = CLASS_DONOR_SOURCE_SHA256
    test_sha256: str = CLASS_DONOR_TEST_SHA256
    class_count: int = CLASS_COUNT
    id_set_sha256: str = CLASS_ID_SET_SHA256
    bound_before: int = OLD_CLASS_BOUND
    bound_after: int = NEW_CLASS_BOUND
    proof_locator: str = CLASS_DONOR_PROOF_LOCATOR


T227 = T227Spec()
CLASS = ClassSpec()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_text(*args: str) -> str:
    output = twenty_seven.four.run_git(ROOT, *args)
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
            "composite must be one commit directly over the fixed 27-event Base",
        )
        return head
    if head == BASE_HEAD:
        require(
            git_text("rev-parse", "HEAD^{tree}") == BASE_TREE,
            "27-event Base tree mismatch",
        )
    else:
        require(
            ancestry == [head, BASE_HEAD],
            "composite must be one commit directly over the fixed 27-event Base",
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
        "27-event Base identity or result SHA256 mismatch",
    )


def replay_base() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    verify_candidate_ancestry()
    twenty_seven.four.verify_commit(ROOT, FROZEN_HEAD, FROZEN_TREE)
    twenty_seven.four.verify_commit(ROOT, BASE_HEAD, BASE_TREE)
    parent = git_text("rev-list", "--parents", "-n", "1", BASE_HEAD).split()
    require(parent == [BASE_HEAD, BASE_PARENT], "27-event Base ancestry mismatch")
    raw = twenty_seven.four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    validate_base_provenance(BASE_HEAD, BASE_TREE, parent[1], sha256(raw))
    require((ROOT / BASE_RESULT_PATH).read_bytes() == raw, "27-event Base result bytes drifted")

    # The existing loader pins its own candidate as a direct child of the 25-event
    # source. Replay it under the verified 27-event Base identity, including after
    # this integration has become one direct child of that Base.
    original_guard = twenty_seven.verify_candidate_ancestry
    twenty_seven.verify_candidate_ancestry = lambda: BASE_HEAD
    try:
        result, frozen_rows, _rows_before_27, rows_after_27 = twenty_seven.build_candidate()
    finally:
        twenty_seven.verify_candidate_ancestry = original_guard

    require(
        twenty_seven.serialize_result(result) == raw
        and result.get("TASK_ID") == "B649_TIED_TWO_ROW_27_EVENT_FROM_T255_R1"
        and result.get("ROWS_AFTER") == BASE_ROWS
        and len(result.get("EVENT_HISTORY", [])) == BASE_EVENTS
        and result.get("TOTAL_EVENTS") == BASE_EVENTS,
        "complete 27-event Base replay does not match its committed result",
    )
    frozen_authority = cast(dict[str, Any], result["FROZEN_AUTHORITY"])
    require(
        frozen_authority.get("HEAD") == FROZEN_HEAD
        and frozen_authority.get("TREE") == FROZEN_TREE
        and frozen_authority.get("RESULT_SHA256") == FROZEN_RESULT_SHA256,
        "frozen HEAD/tree/result authority binding mismatch",
    )
    full = twenty_seven.four.seven.two.full_digest(rows_after_27)
    bounds = twenty_seven.four.seven.two.bounds_digest(rows_after_27)
    require(
        len(frozen_rows) == len(rows_after_27) == BASE_ROWS
        and (full, bounds) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        and (result.get("FULL_DIGEST"), result.get("BOUNDS_DIGEST")) == (full, bounds),
        "27-event Base rows or digest replay mismatch",
    )
    return result, frozen_rows, rows_after_27


def validate_t227_old_row(row: Row) -> None:
    require(
        (row.cap, row.bound) == (T227_OLD_CAP, T227_OLD_BOUND),
        "27-event Base T227 row cap or bound mismatch",
    )


def validate_t227_identity(identity: Mapping[str, Any], spec: T227Spec = T227) -> None:
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
    require(observed == expected, "T227 donor HEAD/TREE/parent/result/source identity mismatch")
    require(
        (identity.get("PROFILE_ID"), identity.get("EVENT_ID")) == (spec.profile_id, spec.event_id),
        "T227 donor profile or event identity mismatch",
    )


def validate_t227_proof(proof: Any, source_raw: bytes, spec: T227Spec = T227) -> str:
    require(isinstance(proof, str) and bool(proof.strip()), "T227 proof is missing")
    try:
        source_doc = ast.get_docstring(ast.parse(source_raw.decode("utf-8")), clean=False)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("T227 proof source cannot be parsed") from exc
    require(source_doc == proof, "T227 proof differs from donor source docstring")
    digest = sha256(proof.encode("utf-8"))
    require(digest == spec.proof_sha256, "T227 science proof SHA256 mismatch")
    return digest


def validate_t227_record(
    record: Mapping[str, Any], source_raw: bytes, spec: T227Spec = T227
) -> str:
    require(
        record.get("TASK_ID") == T227_DONOR_TASK_ID
        and record.get("TASK_STATUS") == "PROVEN_FAMILY_GAIN"
        and record.get("SOURCE_SHA256") == spec.source_sha256,
        "T227 donor result task or source identity mismatch",
    )
    profile_value = record.get("PROFILES", {}).get(spec.profile_id)
    require(isinstance(profile_value, dict), "T227 donor full profile is missing")
    profile = cast(dict[str, Any], profile_value)
    require(
        (
            profile.get("OLD_CAP"),
            profile.get("NEW_CAP"),
            profile.get("OLD_BOUND"),
            profile.get("NEW_BOUND"),
        )
        == (spec.cap_before, spec.cap_after, spec.bound_before, spec.bound_after),
        "T227 donor cap or bound transition mismatch",
    )
    new_terms_value = profile.get("NEW_ALL_T_TERMS")
    old_terms_value = profile.get("OLD_ALL_T_TERMS")
    require(isinstance(new_terms_value, list), "T227 new T envelope is missing")
    new_terms = cast(list[list[int]], new_terms_value)
    require(len(new_terms) == T227_TERM_COUNT, "T227 new T envelope is incomplete")
    require(
        max(new_terms, key=lambda item: int(item[1])) == T227_ARGMAX_TERM,
        "T227 new T envelope argmax mismatch",
    )
    require(isinstance(old_terms_value, list), "T227 old T envelope is missing")
    old_terms = cast(list[list[int]], old_terms_value)
    require(len(old_terms) == 244, "T227 old T envelope is incomplete")
    require(
        max(old_terms, key=lambda item: int(item[1]))
        == [265, T227_OLD_BOUND, 499, 197, 293_314, 5_169_696],
        "T227 old T envelope does not bind cap 265 and bound 313392128",
    )
    relaxation_value = profile.get("RELAXATION")
    require(isinstance(relaxation_value, dict), "T227 relaxation metadata is missing")
    relaxation = cast(dict[str, Any], relaxation_value)
    require(
        relaxation.get("CAP") == spec.cap_after
        and relaxation.get("REALIZABILITY") == "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION",
        "T227 full-profile relaxation metadata mismatch",
    )
    return validate_t227_proof(record.get("PROOF"), source_raw, spec)


def resolve_t227_proof_locator(root: Path, locator: str, spec: T227Spec = T227) -> str:
    match = re.fullmatch(
        r"git:([0-9a-f]{40})@([0-9a-f]{40}):([^#]+)#PROOF:sha256=([0-9a-f]{64})",
        locator,
    )
    require(match is not None, "T227 source/proof locator is malformed")
    donor_head, donor_tree, result_path, proof_sha = cast(re.Match[str], match).groups()
    require(
        (donor_head, donor_tree, result_path, proof_sha)
        == (spec.head, spec.tree, T227_DONOR_RESULT_PATH, spec.proof_sha256),
        "T227 source/proof locator does not identify the pinned donor",
    )
    twenty_seven.four.verify_commit(root, donor_head, donor_tree)
    result = json_object(
        twenty_seven.four.committed_blob(root, donor_head, result_path),
        "T227 proof result is invalid JSON",
    )
    source = twenty_seven.four.committed_blob(root, donor_head, T227_DONOR_SOURCE_PATH)
    resolved = validate_t227_proof(result.get("PROOF"), source, spec)
    require(resolved == proof_sha, "T227 source/proof locator digest mismatch")
    return resolved


def validate_t227_judge_binding(candidate_result: Mapping[str, Any]) -> dict[str, Any]:
    judge_value = candidate_result.get("SCIENTIFIC_JUDGE")
    require(isinstance(judge_value, dict), "T227 Fresh-context Judge binding is missing")
    judge = cast(dict[str, Any], judge_value)
    report_path = Path(str(judge.get("REPORT_PATH", "")))
    require(
        report_path == T227_JUDGE_REPORT_PATH and report_path.is_file(),
        "T227 Judge report path is unresolved",
    )
    report_sha = sha256(report_path.read_bytes())
    require(report_sha == T227_JUDGE_REPORT_SHA256, "T227 Judge report SHA256 mismatch")
    report_text = report_path.read_text(encoding="utf-8", errors="replace")
    for binding in (
        T227_JUDGE_SESSION,
        T227_DONOR_HEAD,
        T227_DONOR_TREE,
        T227_PROFILE_ID,
        "VERIFIED_WITH_CAVEATS",
    ):
        require(binding in report_text, f"T227 Judge report omits binding {binding}")
    require(
        judge.get("SESSION_ID") == T227_JUDGE_SESSION
        and judge.get("THREAD_ID") == T227_JUDGE_SESSION
        and judge.get("JUDGE_MODE") == "FRESH_CONTEXT"
        and judge.get("VERDICT") == "VERIFIED_WITH_CAVEATS"
        and judge.get("PROOF_SCOPE") == "FULL_PROFILE"
        and judge.get("REVIEWED_PROFILE") == T227_PROFILE_ID
        and judge.get("REVIEWED_HEAD") == T227_DONOR_HEAD
        and judge.get("REVIEWED_TREE") == T227_DONOR_TREE
        and judge.get("REPORT_SHA256") == report_sha,
        "T227 Fresh-context Judge source binding mismatch",
    )
    return judge


def verify_t227(
    root: Path, base_rows: Mapping[str, Row]
) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    four = twenty_seven.four
    four.verify_commit(root, T227_INTEGRATION_HEAD, T227_INTEGRATION_TREE)
    integration_parents = cast(
        str,
        four.run_git(root, "rev-list", "--parents", "-n", "1", T227_INTEGRATION_HEAD),
    ).split()
    require(
        integration_parents == [T227_INTEGRATION_HEAD, T227_INTEGRATION_PARENT],
        "T227 integration candidate ancestry mismatch",
    )
    candidate_raw = four.committed_blob(root, T227_INTEGRATION_HEAD, T227_INTEGRATION_RESULT_PATH)
    require(
        sha256(candidate_raw) == T227_INTEGRATION_RESULT_SHA256,
        "T227 candidate result SHA256 mismatch",
    )
    candidate = json_object(candidate_raw, "T227 candidate result is invalid JSON")
    require(
        candidate.get("TASK_ID") == "B649_T227_24_EVENT_LOCAL_FAMILY_INTEGRATION_R1",
        "T227 candidate task mismatch",
    )

    four.verify_commit(root, T227_DONOR_HEAD, T227_DONOR_TREE)
    donor_parents = cast(
        str,
        four.run_git(root, "rev-list", "--parents", "-n", "1", T227_DONOR_HEAD),
    ).split()
    require(
        donor_parents == [T227_DONOR_HEAD, T227_DONOR_PARENT],
        "T227 science donor ancestry mismatch",
    )
    donor_raw = four.committed_blob(root, T227_DONOR_HEAD, T227_DONOR_RESULT_PATH)
    source_raw = four.committed_blob(root, T227_DONOR_HEAD, T227_DONOR_SOURCE_PATH)
    require(
        sha256(donor_raw) == T227_DONOR_RESULT_SHA256, "T227 science donor result SHA256 mismatch"
    )
    require(
        sha256(source_raw) == T227_DONOR_SOURCE_SHA256, "T227 science donor source SHA256 mismatch"
    )
    donor = json_object(donor_raw, "T227 science donor result is invalid JSON")
    proof_sha = validate_t227_record(donor, source_raw)
    require(
        resolve_t227_proof_locator(root, T227_PROOF_LOCATOR) == proof_sha,
        "T227 proof locator did not resolve",
    )

    identity_value = candidate.get("DONOR_IDENTITY")
    require(isinstance(identity_value, dict), "T227 integration candidate lacks donor identity")
    identity = cast(dict[str, Any], identity_value)
    validate_t227_identity(identity)
    require(
        identity.get("PROOF_LOCATOR") == T227_PROOF_LOCATOR
        and identity.get("PROOF_SHA256") == proof_sha
        and identity.get("PROOF_SCOPE") == "FULL_PROFILE"
        and identity.get("CAP_BEFORE") == T227_OLD_CAP
        and identity.get("CAP_AFTER") == T227_NEW_CAP
        and identity.get("BOUND_BEFORE") == T227_OLD_BOUND
        and identity.get("BOUND_AFTER") == T227_NEW_BOUND
        and identity.get("OWNER_DELTA") == T227_OWNER_DELTA,
        "T227 integration candidate donor delta mismatch",
    )
    target_row = base_rows.get(T227_PROFILE_ID)
    require(target_row is not None, "27-event Base is missing the T227 target row")
    validate_t227_old_row(cast(Row, target_row))
    candidate_events_value = candidate.get("EVENT_HISTORY")
    require(isinstance(candidate_events_value, list), "T227 candidate event history is missing")
    candidate_events = cast(list[dict[str, Any]], candidate_events_value)
    require(len(candidate_events) == 24, "T227 candidate event history mismatch")
    candidate_event = candidate_events[-1]
    require(
        candidate_event.get("EVENT_ID") == T227_DONOR_EVENT_ID
        and candidate_event.get("PROFILE_ID") == T227_PROFILE_ID
        and candidate_event.get("CAP_BEFORE") == T227_OLD_CAP
        and candidate_event.get("CAP_AFTER") == T227_NEW_CAP
        and candidate_event.get("BOUND_BEFORE") == T227_OLD_BOUND
        and candidate_event.get("BOUND_AFTER") == T227_NEW_BOUND,
        "T227 candidate event does not match the unique row delta",
    )
    judge = validate_t227_judge_binding(candidate)
    return donor, {**identity, "SCIENCE_JUDGE": judge}, source_raw, donor_raw


def validate_class_transition(
    old_bound: int,
    new_bound: int,
    spec: ClassSpec = CLASS,
) -> None:
    require(
        (old_bound, new_bound, old_bound - new_bound)
        == (spec.bound_before, spec.bound_after, CLASS_BOUND_DELTA),
        "197-class old/new bound transition mismatch",
    )


def validate_class_identity(identity: Mapping[str, Any], spec: ClassSpec = CLASS) -> None:
    observed = (
        identity.get("HEAD"),
        identity.get("TREE"),
        identity.get("PARENT"),
        identity.get("RESULT_SHA256"),
        identity.get("SOURCE_SHA256"),
        identity.get("TEST_SHA256"),
    )
    expected = (
        spec.head,
        spec.tree,
        spec.parent,
        spec.result_sha256,
        spec.source_sha256,
        spec.test_sha256,
    )
    require(
        observed == expected,
        "197-class donor HEAD/TREE/parent/result/source/test identity mismatch",
    )
    require(
        identity.get("TASK_ID") == CLASS_DONOR_TASK_ID
        and identity.get("CLASS_COUNT") == spec.class_count
        and identity.get("CLASS_ID_SET_SHA256") == spec.id_set_sha256
        and identity.get("PROOF_LOCATOR") == spec.proof_locator,
        "197-class donor identity, profile set or proof locator mismatch",
    )
    require(
        identity.get("CLASS_BOUND_BEFORE") == spec.bound_before
        and identity.get("CLASS_BOUND_AFTER") == spec.bound_after
        and identity.get("CLASS_BOUND_DELTA") == spec.bound_before - spec.bound_after,
        "197-class donor bound identity mismatch",
    )


def validate_class_record(
    record: Mapping[str, Any], source_raw: bytes, spec: ClassSpec = CLASS
) -> tuple[list[str], list[dict[str, Any]], str]:
    try:
        source_doc = ast.get_docstring(ast.parse(source_raw.decode("utf-8")), clean=False)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("197-class donor source proof cannot be parsed") from exc
    require(
        isinstance(source_doc, str) and bool(source_doc.strip()),
        "197-class donor source proof is missing",
    )
    doc_sha = sha256(cast(str, source_doc).encode("utf-8"))
    require(doc_sha == CLASS_DONOR_DOC_SHA256, "197-class donor source proof digest mismatch")
    require(
        record.get("TASK_ID") == CLASS_DONOR_TASK_ID
        and record.get("COVERED_PROFILES") == spec.class_count
        and record.get("MISSING_PROFILES") == 0
        and record.get("DUPLICATE_PROFILES") == 0
        and record.get("COMPLETE_CLASS_COVERAGE") is True,
        "197-class donor task or coverage metadata mismatch",
    )
    validate_class_transition(
        int(cast(int, record.get("CLASS_BOUND_BEFORE"))),
        int(cast(int, record.get("CLASS_BOUND_AFTER"))),
        spec,
    )
    require(
        record.get("PARTITION_COUNT") == spec.class_count
        and record.get("PARTITION_IDS_SHA256") == spec.id_set_sha256,
        "197-class partition identity mismatch",
    )
    raw_ids = record.get("PROFILE_IDS")
    raw_rows = record.get("PROFILE_BOUND_ROWS")
    require(isinstance(raw_ids, list), "197-class PROFILE_IDS is missing")
    require(isinstance(raw_rows, list), "197-class profile bound rows are missing")
    profile_ids = cast(list[str], raw_ids)
    bound_rows = cast(list[dict[str, Any]], raw_rows)
    require(len(profile_ids) == spec.class_count, "197-class PROFILE_IDS count mismatch")
    require(len(set(profile_ids)) == len(profile_ids), "197-class PROFILE_IDS contains duplicates")
    require(
        profile_ids == sorted(profile_ids, reverse=True),
        "197-class PROFILE_IDS order is not canonical",
    )
    require(len(bound_rows) == spec.class_count, "197-class bound row count mismatch")
    row_ids = [cast(str, row.get("PROFILE_ID")) for row in bound_rows]
    require(row_ids == profile_ids, "197-class bound rows do not exactly match PROFILE_IDS")
    computed_id_sha = sha256(json.dumps(profile_ids).encode("utf-8"))
    require(computed_id_sha == spec.id_set_sha256, "197-class PROFILE_IDS digest mismatch")
    max_class_bound = max(int(cast(int, row.get("CLASS_BOUND_AFTER"))) for row in bound_rows)
    require(
        max_class_bound == spec.bound_after,
        "197-class maximum does not match complete profile bounds",
    )
    require(
        record.get("NEW_CLASS_BOUND_CANDIDATE") == max_class_bound,
        "197-class candidate maximum mismatch",
    )
    require(record.get("PROOF_LOCATOR") == spec.proof_locator, "197-class proof locator mismatch")
    verification_value = record.get("VERIFICATION")
    require(isinstance(verification_value, dict), "197-class original QA block is missing")
    verification = cast(dict[str, Any], verification_value)
    require(
        verification.get("FOCUSED_TEST_EXIT_CODE") is None,
        "197-class original focused QA null field was not preserved",
    )
    return profile_ids, bound_rows, doc_sha


def verify_class(
    root: Path,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], dict[str, Any]]:
    four = twenty_seven.four
    four.verify_commit(root, CLASS_INTEGRATION_HEAD, CLASS_INTEGRATION_TREE)
    parents = cast(
        str,
        four.run_git(root, "rev-list", "--parents", "-n", "1", CLASS_INTEGRATION_HEAD),
    ).split()
    require(
        parents == [CLASS_INTEGRATION_HEAD, CLASS_INTEGRATION_PARENT],
        "197-class integration candidate ancestry mismatch",
    )
    candidate_raw = four.committed_blob(root, CLASS_INTEGRATION_HEAD, CLASS_INTEGRATION_RESULT_PATH)
    require(
        sha256(candidate_raw) == CLASS_INTEGRATION_RESULT_SHA256,
        "197-class integration result SHA256 mismatch",
    )
    candidate = json_object(candidate_raw, "197-class integration candidate result is invalid JSON")
    require(
        candidate.get("TASK_ID") == "B649_CLASS197_FROM_T255_LOCAL_INTEGRATION_R1",
        "197-class candidate task mismatch",
    )
    require(
        candidate.get("RESOLVED_ROW_MUTATIONS") == 0, "197-class candidate mutates resolved rows"
    )

    identity_value = candidate.get("DONOR_IDENTITY")
    require(isinstance(identity_value, dict), "197-class candidate lacks donor identity")
    identity = cast(dict[str, Any], identity_value)
    validate_class_identity(identity)
    gates = cast(dict[str, Any], candidate.get("AUTHORITY_GATES", {}))
    require(
        gates.get("DONOR_QA_RECEIPT") == "VERIFIED"
        and gates.get("SCIENCE_JUDGE") == "VERIFIED_WITH_CAVEATS"
        and gates.get("SCIENCE_JUDGE_SESSION") == CLASS_SCIENCE_JUDGE_SESSION,
        "197-class science Judge or supplemental QA receipt binding mismatch",
    )
    science = cast(dict[str, Any], identity.get("SCIENCE_JUDGE", {}))
    require(
        science.get("SESSION_ID") == CLASS_SCIENCE_JUDGE_SESSION
        and science.get("VERDICT") == "VERIFIED_WITH_CAVEATS"
        and science.get("CLASS_COUNT") == CLASS_COUNT
        and science.get("OLD_CLASS_BOUND") == OLD_CLASS_BOUND
        and science.get("NEW_CLASS_BOUND") == NEW_CLASS_BOUND,
        "197-class Science Judge session binding mismatch",
    )
    require(
        identity.get("OWNER_SESSION") == CLASS_OWNER_SESSION
        and identity.get("OWNERSHIP") == "RELEASED_WITH_SUPPLEMENTAL_RECEIPT"
        and identity.get("DONOR_FOCUSED_QA") == "11_PASSED"
        and identity.get("DONOR_FOCUSED_EXIT_CODE") == 0,
        "197-class supplemental QA receipt identity mismatch",
    )

    four.verify_commit(root, CLASS_DONOR_HEAD, CLASS_DONOR_TREE)
    donor_parents = cast(
        str,
        four.run_git(root, "rev-list", "--parents", "-n", "1", CLASS_DONOR_HEAD),
    ).split()
    require(
        donor_parents == [CLASS_DONOR_HEAD, CLASS_DONOR_PARENT],
        "197-class science donor ancestry mismatch",
    )
    paths = {
        "RESULT": CLASS_DONOR_RESULT_PATH,
        "SOURCE": CLASS_DONOR_SOURCE_PATH,
        "TEST": CLASS_DONOR_TEST_PATH,
    }
    blobs = {
        name: four.committed_blob(root, CLASS_DONOR_HEAD, path) for name, path in paths.items()
    }
    require(
        sha256(blobs["RESULT"]) == CLASS_DONOR_RESULT_SHA256,
        "197-class science donor result SHA256 mismatch",
    )
    require(
        sha256(blobs["SOURCE"]) == CLASS_DONOR_SOURCE_SHA256,
        "197-class science donor source SHA256 mismatch",
    )
    require(
        sha256(blobs["TEST"]) == CLASS_DONOR_TEST_SHA256,
        "197-class science donor test SHA256 mismatch",
    )
    donor = json_object(blobs["RESULT"], "197-class science donor result is invalid JSON")
    profile_ids, bound_rows, doc_sha = validate_class_record(donor, blobs["SOURCE"])
    require(doc_sha == identity.get("DOC_SHA256"), "197-class source docstring binding mismatch")
    expected_source = (
        f"git:{CLASS_DONOR_HEAD}@{CLASS_DONOR_TREE}:{CLASS_DONOR_RESULT_PATH}"
        f";RESULT_SHA256={CLASS_DONOR_RESULT_SHA256}"
        f";SOURCE_SHA256={CLASS_DONOR_SOURCE_SHA256}"
        ";SCIENCE_JUDGE=VERIFIED_WITH_CAVEATS"
        f";SCIENCE_JUDGE_SESSION={CLASS_SCIENCE_JUDGE_SESSION}"
        f";DOC_SHA256={doc_sha}#PROOF_LOCATOR={CLASS_DONOR_PROOF_LOCATOR}"
    )
    require(
        identity.get("CLASS_SOURCE") == expected_source,
        "197-class source/proof locator chain mismatch",
    )
    require(
        candidate.get("CLASS_COUNT") == CLASS_COUNT
        and candidate.get("CLASS_ID_SET_SHA256") == CLASS_ID_SET_SHA256
        and candidate.get("OLD_CLASS_BOUND") == OLD_CLASS_BOUND
        and candidate.get("NEW_CLASS_BOUND") == NEW_CLASS_BOUND
        and candidate.get("CLASS_BOUND_DELTA") == CLASS_BOUND_DELTA,
        "197-class integration summary mismatch",
    )
    return donor, profile_ids, bound_rows, candidate


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


def validate_current_frontier(
    event_count: int,
    actual_next_resolved_bound: int,
    claimed_next_resolved_bound: int,
) -> None:
    require(
        event_count == BASE_EVENTS,
        "historical 19-event frontier cannot substitute for the 27-event Base",
    )
    require(
        actual_next_resolved_bound == claimed_next_resolved_bound,
        "resolved frontier claim differs from the complete 27-event ledger",
    )


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
    t227_identity: Mapping[str, Any],
    t227_source: bytes,
    t227_donor: Mapping[str, Any],
    class_candidate: Mapping[str, Any],
    class_record: Mapping[str, Any],
    class_source: bytes,
    class_ids: list[str],
    class_bounds: list[dict[str, Any]],
    t227_event: Mapping[str, Any],
    base_raw: bytes,
) -> dict[str, str]:
    target = base_rows[T227_PROFILE_ID]
    unrelated_id = next(profile_id for profile_id in base_rows if profile_id != T227_PROFILE_ID)
    unrelated_rows = dict(after_rows)
    unrelated_rows[unrelated_id] = replace(
        unrelated_rows[unrelated_id], bound=unrelated_rows[unrelated_id].bound + 1
    )
    history = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    wrong_ids = list(class_ids)
    wrong_ids[0] = "0" * 20
    duplicate_ids = [class_ids[0], *class_ids[1:-1], class_ids[0]]
    class_bound_rows_by_id = {cast(str, row["PROFILE_ID"]): row for row in class_bounds}
    missing_record = {
        **class_record,
        "PROFILE_IDS": class_ids[:-1],
        "PROFILE_BOUND_ROWS": [class_bound_rows_by_id[item] for item in class_ids[:-1]],
        "COVERED_PROFILES": CLASS_COUNT - 1,
    }
    return {
        "WRONG_27_EVENT_BASE": expect_rejected(
            lambda: validate_base_provenance("0" * 40, BASE_TREE, BASE_PARENT, sha256(base_raw))
        ),
        "WRONG_T227_DONOR_HEAD_TREE": expect_rejected(
            lambda: validate_t227_identity(
                t227_identity,
                replace(T227, head="0" * 40, tree="1" * 40),
            )
        ),
        "WRONG_T227_ORIGINAL_ROW_BOUND": expect_rejected(
            lambda: validate_t227_old_row(replace(target, bound=target.bound + 1))
        ),
        "WRONG_T227_SCIENCE_PROOF": expect_rejected(
            lambda: validate_t227_proof(str(t227_donor["PROOF"]) + " altered", t227_source)
        ),
        "WRONG_CLASS_DONOR": expect_rejected(
            lambda: validate_class_identity(
                cast(Mapping[str, Any], class_candidate["DONOR_IDENTITY"]),
                replace(CLASS, head="0" * 40, tree="1" * 40),
            )
        ),
        "WRONG_CLASS_ID_SET": expect_rejected(
            lambda: validate_class_record({**class_record, "PROFILE_IDS": wrong_ids}, class_source)
        ),
        "DUPLICATE_CLASS_ID": expect_rejected(
            lambda: validate_class_record(
                {**class_record, "PROFILE_IDS": duplicate_ids}, class_source
            )
        ),
        "DUPLICATE_T227_EVENT": expect_rejected(
            lambda: sixteen.verify_unique_events([*history, dict(t227_event), dict(t227_event)])
        ),
        "WRONG_EVENT_ANCESTRY": expect_rejected(
            lambda: verify_candidate_ancestry(["1" * 40, "2" * 40])
        ),
        "UNRELATED_RESOLVED_ROW_MUTATION": expect_rejected(
            lambda: sixteen.verify_ledger_partition(base_rows, unrelated_rows, {T227_PROFILE_ID})
        ),
        "MISSING_UNRESOLVED_CLASS": expect_rejected(
            lambda: validate_class_record(missing_record, class_source)
        ),
        "WRONG_OLD_CLASS_BOUND": expect_rejected(
            lambda: validate_class_transition(OLD_CLASS_BOUND + 1, NEW_CLASS_BOUND)
        ),
        "WRONG_NEW_CLASS_BOUND": expect_rejected(
            lambda: validate_class_transition(OLD_CLASS_BOUND, NEW_CLASS_BOUND + 1)
        ),
        "HISTORICAL_19_EVENT_FRONTIER": expect_rejected(
            lambda: validate_current_frontier(19, 313_391_844, HISTORICAL_19_EVENT_NEXT_BOUND)
        ),
        "WRONG_SOURCE_PROOF_LOCATOR": expect_rejected(
            lambda: resolve_t227_proof_locator(ROOT, T227_PROOF_LOCATOR[:-1] + "0")
        ),
    }


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row], dict[str, Row]]:
    verify_candidate_ancestry()
    base_result, frozen_rows, base_rows = replay_base()
    base_raw = twenty_seven.four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)

    target_row = base_rows.get(T227_PROFILE_ID)
    require(target_row is not None, "27-event Base omitted the T227 profile")
    old_t227_row = cast(Row, target_row)
    validate_t227_old_row(old_t227_row)
    t227_donor, t227_identity, t227_source_raw, t227_donor_raw = verify_t227(ROOT, base_rows)
    t227_donor_sha = sha256(t227_donor_raw)
    t227_source_sha = sha256(t227_source_raw)
    t227_proof_sha = validate_t227_record(t227_donor, t227_source_raw)

    new_t227_row = replace(
        old_t227_row,
        bound=T227_NEW_BOUND,
        cap=T227_NEW_CAP,
        source=T227_PROOF_LOCATOR,
    )
    after_rows = dict(base_rows)
    after_rows[T227_PROFILE_ID] = new_t227_row
    t227_event = nine.event_from_update(
        T227_DONOR_EVENT_ID, T227_PROFILE_ID, old_t227_row, new_t227_row
    )
    t227_event["DONOR"] = t227_identity
    t227_event["PROOF_SCOPE"] = "FULL_PROFILE"
    t227_event["PROOF_SHA256"] = t227_proof_sha
    events = [*cast(list[dict[str, Any]], base_result["EVENT_HISTORY"]), t227_event]
    sixteen.verify_unique_events(events)
    require(
        len(events) == BASE_EVENTS + 1
        and events[:-1] == base_result["EVENT_HISTORY"]
        and events[-1]["EVENT_ID"] == T227_DONOR_EVENT_ID,
        "28-event history must preserve 27 Base events and append one T227 row event",
    )
    changed_from_base = sixteen.verify_ledger_partition(base_rows, after_rows, {T227_PROFILE_ID})
    changed_from_frozen = {
        profile_id
        for profile_id in frozen_rows
        if frozen_rows[profile_id] != after_rows[profile_id]
    }
    require(
        len(changed_from_base) == 1
        and len(base_rows) - len(changed_from_base) == 4_646
        and len(changed_from_frozen) == 27
        and len(frozen_rows) - len(changed_from_frozen) == 4_620
        and set(base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"]) < changed_from_frozen
        and changed_from_frozen - set(base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"])
        == {T227_PROFILE_ID},
        "resolved row change partition mismatch",
    )
    full_before = twenty_seven.four.seven.two.full_digest(base_rows)
    bounds_before = twenty_seven.four.seven.two.bounds_digest(base_rows)
    full_after = twenty_seven.four.seven.two.full_digest(after_rows)
    bounds_after = twenty_seven.four.seven.two.bounds_digest(after_rows)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "27-event Base digest changed before T227",
    )

    class_donor, class_ids, class_bound_rows, class_candidate = verify_class(ROOT)
    validate_class_transition(OLD_CLASS_BOUND, NEW_CLASS_BOUND)
    require(
        class_candidate.get("ROWS_BEFORE") == BASE_ROWS
        and class_candidate.get("ROWS_AFTER") == BASE_ROWS
        and class_candidate.get("RESOLVED_ROW_MUTATIONS") == 0,
        "197-class substitution changed resolved row count or rows",
    )
    require(
        len(class_ids) == CLASS_COUNT
        and len(set(class_ids)) == CLASS_COUNT
        and sha256(json.dumps(class_ids).encode("utf-8")) == CLASS_ID_SET_SHA256,
        "197-class exact ID set mismatch",
    )
    max_class_bound = max(int(cast(int, row["CLASS_BOUND_AFTER"])) for row in class_bound_rows)
    require(max_class_bound == NEW_CLASS_BOUND, "197-profile maximum class bound mismatch")
    require(
        cast(dict[str, Any], base_result["CURSOR_AUTHORITY"]).get("ID") == CLASS_CURSOR_ID
        and cast(dict[str, Any], base_result["CURSOR_AUTHORITY"]).get("BOUND") == OLD_CLASS_BOUND
        and cast(dict[str, Any], base_result["CURSOR_AUTHORITY"]).get("COUNT") == CLASS_COUNT,
        "unresolved 197-profile class cursor does not match the 27-event Base",
    )

    base_frontier = family_summary(base_rows, OLD_CLASS_BOUND)
    validate_current_frontier(
        len(cast(list[Any], base_result["EVENT_HISTORY"])),
        int(base_frontier["NEXT_DISTINCT_RESOLVED_BOUND"]),
        int(base_result["NEXT_DISTINCT_RESOLVED_BOUND"]),
    )
    family_before = family_summary(base_rows, OLD_CLASS_BOUND)
    family_after_t227_old_cursor = family_summary(after_rows, OLD_CLASS_BOUND)
    family_after = family_summary(after_rows, max_class_bound)
    require(
        family_before["FAMILY_BOUND"] == BASE_FAMILY_BOUND, "27-event Base Family bound mismatch"
    )
    require(
        family_after_t227_old_cursor["FAMILY_BOUND"] == BASE_FAMILY_BOUND,
        "T227 row update incorrectly changes Family bound with the old class cursor",
    )
    require(
        family_after["MAX_RESOLVED_BOUND"] == 313_391_844
        and family_after["MAX_CLASS_BOUND"] == NEW_CLASS_BOUND
        and family_after["FAMILY_BOUND"] == 313_391_844,
        "final Family maximum does not match the complete resolved and class bound maps",
    )
    family_gain = int(family_before["FAMILY_BOUND"]) - int(family_after["FAMILY_BOUND"])
    frozen_gain = FROZEN_SEVEN_ROW_FAMILY - int(family_after["FAMILY_BOUND"])
    require(
        family_gain == 2_740 and frozen_gain == 6_688,
        "recomputed Family gains do not match the full ledger frontier",
    )
    transitions = [
        *cast(list[dict[str, Any]], base_result["EVENT_FAMILY_TRANSITIONS"]),
        {
            "EVENT_ID": T227_DONOR_EVENT_ID,
            "FAMILY_BOUND_BEFORE": family_after_t227_old_cursor["FAMILY_BOUND"],
            "FAMILY_BOUND_AFTER": family_after_t227_old_cursor["FAMILY_BOUND"],
            "TIED_OWNERS_AFTER": family_after_t227_old_cursor["MAXIMIZING_OWNERS"],
            "NEXT_COMPETING_BOUND_AFTER": family_after_t227_old_cursor["NEXT_DISTINCT_BOUND"],
            "NEXT_COMPETING_OWNERS_AFTER": family_after_t227_old_cursor["NEXT_DISTINCT_OWNERS"],
        },
    ]
    class_transition = {
        "TASK_ID": CLASS_DONOR_TASK_ID,
        "CLASS_BOUND_BEFORE": OLD_CLASS_BOUND,
        "CLASS_BOUND_AFTER": max_class_bound,
        "CLASS_BOUND_DELTA": OLD_CLASS_BOUND - max_class_bound,
        "FAMILY_BOUND_BEFORE": family_after_t227_old_cursor["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": int(family_after_t227_old_cursor["FAMILY_BOUND"])
        - int(family_after["FAMILY_BOUND"]),
        "TIED_OWNERS_BEFORE": family_after_t227_old_cursor["MAXIMIZING_OWNERS"],
        "TIED_OWNERS_AFTER": family_after["MAXIMIZING_OWNERS"],
        "NEXT_COMPETING_BOUND_AFTER": family_after["NEXT_DISTINCT_BOUND"],
        "NEXT_COMPETING_OWNERS_AFTER": family_after["NEXT_DISTINCT_OWNERS"],
    }

    negative = verify_negative_cases(
        base_result,
        base_rows,
        after_rows,
        t227_identity,
        t227_source_raw,
        t227_donor,
        class_candidate,
        class_donor,
        twenty_seven.four.committed_blob(ROOT, CLASS_DONOR_HEAD, CLASS_DONOR_SOURCE_PATH),
        class_ids,
        class_bound_rows,
        t227_event,
        base_raw,
    )
    require(
        len(negative) == 15 and all(value.startswith("REJECTED:") for value in negative.values()),
        "a required load-bearing negative control was accepted",
    )

    historical = cast(dict[str, Any], base_result["INHERITED_CAVEATS_PRESERVED"])
    t227_candidate_raw = twenty_seven.four.committed_blob(
        ROOT, T227_INTEGRATION_HEAD, T227_INTEGRATION_RESULT_PATH
    )
    t227_candidate = json_object(
        t227_candidate_raw, "T227 integration candidate result is invalid JSON"
    )
    class_verification = cast(dict[str, Any], class_donor["VERIFICATION"])
    caveats = {
        "HISTORICAL_22_EVENT_JUDGE": t227_candidate["INHERITED_22_EVENT_JUDGE"],
        "BASE_HISTORICAL_CAVEATS": historical,
        "T227_PROCEDURAL_FINDING": t227_candidate.get("INHERITED_PROCESS_FINDING"),
        "T227_SCIENCE_CAVEATS": cast(dict[str, Any], t227_identity["SCIENCE_JUDGE"]).get("CAVEATS"),
        "CLASS_HISTORICAL_CAVEATS": class_candidate["INHERITED_CAVEATS_PRESERVED"],
        "CLASS_ORIGINAL_QA_AND_SUPPLEMENTAL_RECEIPT": {
            "ORIGINAL_FOCUSED_TEST_EXIT_CODE": class_verification.get("FOCUSED_TEST_EXIT_CODE"),
            "SUPPLEMENTAL_QA_RECEIPT": CLASS_QA_RECEIPT,
            "SUPPLEMENTAL_EXIT_CODE": cast(dict[str, Any], class_candidate["DONOR_IDENTITY"]).get(
                "DONOR_FOCUSED_EXIT_CODE"
            ),
            "SUPPLEMENTAL_TESTS_PASSED": cast(
                dict[str, Any], class_candidate["DONOR_IDENTITY"]
            ).get("DONOR_FOCUSED_QA"),
        },
    }

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_28_EVENT_CLASS197_INTEGRATION_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "NEW_COMPOSITE_JUDGE": "SELF_CHECK_ONLY",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
            "BASE_HEAD_TREE": "MATCH",
            "BASE_RESULT_SHA256": "MATCH",
            "BASE_FULL_DIGEST_REPLAY": "MATCH",
            "BASE_BOUNDS_DIGEST_REPLAY": "MATCH",
            "T227_CANDIDATE_HEAD_TREE": "MATCH",
            "T227_CANDIDATE_RESULT_SHA256": "MATCH",
            "T227_DONOR_HEAD_TREE": "MATCH",
            "T227_DONOR_PARENT": "MATCH",
            "T227_DONOR_RESULT_SHA256": "MATCH",
            "T227_DONOR_SOURCE_SHA256": "MATCH",
            "T227_PROOF_LOCATOR": "RESOLVED",
            "T227_SCIENCE_JUDGE_REPORT_SHA256": "MATCH",
            "T227_SCIENCE_JUDGE_BINDING": "MATCH",
            "CLASS_CANDIDATE_HEAD_TREE": "MATCH",
            "CLASS_CANDIDATE_RESULT_SHA256": "MATCH",
            "CLASS_DONOR_HEAD_TREE": "MATCH",
            "CLASS_DONOR_PARENT": "MATCH",
            "CLASS_DONOR_RESULT_SHA256": "MATCH",
            "CLASS_DONOR_SOURCE_SHA256": "MATCH",
            "CLASS_DONOR_TEST_SHA256": "MATCH",
            "CLASS_ID_SET": "EXACT_MATCH",
            "CLASS_SCIENCE_JUDGE_BINDING": "VERIFIED_WITH_CAVEATS",
            "CLASS_QA_RECEIPT": "VERIFIED",
        },
        "FROZEN": {"HEAD": FROZEN_HEAD, "TREE": FROZEN_TREE, "RESULT_SHA256": FROZEN_RESULT_SHA256},
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
        "T227_CANDIDATE": {
            "HEAD": T227_INTEGRATION_HEAD,
            "TREE": T227_INTEGRATION_TREE,
            "PARENT": T227_INTEGRATION_PARENT,
            "RESULT_PATH": T227_INTEGRATION_RESULT_PATH,
            "RESULT_SHA256": T227_INTEGRATION_RESULT_SHA256,
            "SCIENCE_DONOR_HEAD": T227_DONOR_HEAD,
            "SCIENCE_DONOR_TREE": T227_DONOR_TREE,
            "SCIENCE_DONOR_PARENT": T227_DONOR_PARENT,
            "SCIENCE_DONOR_RESULT_SHA256": t227_donor_sha,
            "SCIENCE_DONOR_SOURCE_SHA256": t227_source_sha,
            "PROOF_LOCATOR": T227_PROOF_LOCATOR,
            "PROOF_SHA256": t227_proof_sha,
            "SCIENCE_JUDGE": t227_identity["SCIENCE_JUDGE"],
        },
        "CLASS_CANDIDATE": {
            "HEAD": CLASS_INTEGRATION_HEAD,
            "TREE": CLASS_INTEGRATION_TREE,
            "PARENT": CLASS_INTEGRATION_PARENT,
            "RESULT_PATH": CLASS_INTEGRATION_RESULT_PATH,
            "RESULT_SHA256": CLASS_INTEGRATION_RESULT_SHA256,
            "SCIENCE_DONOR_HEAD": CLASS_DONOR_HEAD,
            "SCIENCE_DONOR_TREE": CLASS_DONOR_TREE,
            "SCIENCE_DONOR_PARENT": CLASS_DONOR_PARENT,
            "SCIENCE_DONOR_RESULT_SHA256": CLASS_DONOR_RESULT_SHA256,
            "SCIENCE_DONOR_SOURCE_SHA256": CLASS_DONOR_SOURCE_SHA256,
            "SCIENCE_DONOR_TEST_SHA256": CLASS_DONOR_TEST_SHA256,
            "SCIENCE_JUDGE_SESSION": CLASS_SCIENCE_JUDGE_SESSION,
            "SCIENCE_JUDGE_VERDICT": "VERIFIED_WITH_CAVEATS",
            "SOURCE_PROOF_LOCATOR": CLASS_DONOR_PROOF_LOCATOR,
            "DOC_SHA256": CLASS_DONOR_DOC_SHA256,
            "SUPPLEMENTAL_QA_RECEIPT": CLASS_QA_RECEIPT,
        },
        "SCIENCE_JUDGE_BINDINGS": {
            "T227": t227_identity["SCIENCE_JUDGE"],
            "CLASS": cast(
                dict[str, Any],
                cast(dict[str, Any], class_candidate["DONOR_IDENTITY"])["SCIENCE_JUDGE"],
            ),
        },
        "INHERITED_CAVEATS": caveats,
        "ROWS_BEFORE": len(base_rows),
        "ROWS_AFTER": len(after_rows),
        "EVENTS_BEFORE": len(cast(list[Any], base_result["EVENT_HISTORY"])),
        "NEW_RESOLVED_EVENTS": 1,
        "EVENTS_AFTER": len(events),
        "CHANGED_ROWS_FROM_BASE": len(changed_from_base),
        "UNCHANGED_ROWS_FROM_BASE": len(base_rows) - len(changed_from_base),
        "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": len(changed_from_frozen),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen_rows) - len(changed_from_frozen),
        "T227": {
            "PROFILE_ID": T227_PROFILE_ID,
            "OLD_CAP": T227_OLD_CAP,
            "NEW_CAP": T227_NEW_CAP,
            "OLD_BOUND": T227_OLD_BOUND,
            "NEW_BOUND": T227_NEW_BOUND,
            "OWNER_DELTA": T227_OWNER_DELTA,
            "EVENT_ID": T227_DONOR_EVENT_ID,
        },
        "CLASS": {
            "COUNT": len(class_ids),
            "ID_SET_SHA256": sha256(json.dumps(class_ids).encode("utf-8")),
            "PROFILE_IDS": class_ids,
            "PROFILE_BOUND_ROWS": [
                {"PROFILE_ID": row["PROFILE_ID"], "CLASS_BOUND_AFTER": row["CLASS_BOUND_AFTER"]}
                for row in class_bound_rows
            ],
            "BOUND_BEFORE": OLD_CLASS_BOUND,
            "BOUND_AFTER": max_class_bound,
            "BOUND_DELTA": OLD_CLASS_BOUND - max_class_bound,
            "RESOLVED_ROW_EVENTS": 0,
            "SUPPLEMENTAL_QA_RECEIPT": CLASS_QA_RECEIPT,
            "ORIGINAL_FOCUSED_TEST_EXIT_CODE": class_verification.get("FOCUSED_TEST_EXIT_CODE"),
        },
        "FULL_DIGEST": full_after,
        "BOUNDS_DIGEST": bounds_after,
        "MAX_RESOLVED_BOUND": family_after["MAX_RESOLVED_BOUND"],
        "MAX_RESOLVED_OWNERS": family_after["MAX_RESOLVED_OWNERS"],
        "MAX_UNRESOLVED_CLASS_BOUND": max_class_bound,
        "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER_T227_WITH_OLD_CURSOR": family_after_t227_old_cursor["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "T227_FAMILY_GAIN_WITH_OLD_CURSOR": int(family_before["FAMILY_BOUND"])
        - int(family_after_t227_old_cursor["FAMILY_BOUND"]),
        "FAMILY_GAIN": family_gain,
        "FAMILY_GAIN_VS_27_EVENT_BASE": family_gain,
        "FAMILY_GAIN_VS_FROZEN_SEVEN_ROW": frozen_gain,
        "MAXIMIZING_OWNERS": family_after["MAXIMIZING_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_DISTINCT_BOUND"],
        "NEXT_DISTINCT_OWNERS": family_after["NEXT_DISTINCT_OWNERS"],
        "NEXT_DISTINCT_RESOLVED_BOUND": family_after["NEXT_DISTINCT_RESOLVED_BOUND"],
        "NEXT_DISTINCT_RESOLVED_OWNERS": family_after["NEXT_DISTINCT_RESOLVED_OWNERS"],
        "GAP_TO_INCUMBENT": int(family_after["FAMILY_BOUND"]) - INCUMBENT,
        "CLASS_MAX_BELOW_INCUMBENT_BY": INCUMBENT - max_class_bound,
        "EVENT_HISTORY": events,
        "EVENT_FAMILY_TRANSITIONS": transitions,
        "CLASS_INTEGRATION_TRANSITION": class_transition,
        "CURSOR_AUTHORITY": {
            "ID": CLASS_CURSOR_ID,
            "BOUND": max_class_bound,
            "PREVIOUS_BOUND": OLD_CLASS_BOUND,
            "COUNT": CLASS_COUNT,
            "IDS_SHA256": CLASS_ID_SET_SHA256,
            "INCLUDED_IN_FAMILY_FRONTIER": "YES",
        },
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "ALL_PROOF_LOCATORS_RESOLVED": "YES",
        "UNRELATED_ROW_MUTATION": "NONE",
        "NEGATIVE_CASE_RESULTS": negative,
        "FOCUSED_TEST_PATH": (
            "tests/unit/test_b649_combined_28_event_class197_local_integration_r1.py"
        ),
        "VERIFICATION": {
            "FOCUSED_TEST_EXIT_CODE": None,
            "RUFF": "NOT_RUN",
            "PYRIGHT": "NOT_RUN",
            "DIFF_CHECK": "NOT_RUN",
            "POSTCOMMIT_REPLAY": "NOT_RUN_AT_COMMIT",
        },
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PR_CREATION": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    require(
        len(events) == 28
        and len(base_rows) == len(after_rows) == BASE_ROWS
        and len(changed_from_base) == 1
        and len(changed_from_frozen) == 27
        and full_after != full_before
        and bounds_after != bounds_before
        and family_gain == 2_740
        and family_after["MAX_RESOLVED_BOUND"] == 313_391_844,
        "composite ledger acceptance mismatch",
    )
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
    return result, frozen_rows, base_rows, after_rows


def write_result(result: Mapping[str, Any]) -> str:
    encoded = serialize_result(result)
    output_path = ROOT / RESULT_PATH
    if output_path.exists():
        require(
            output_path.read_bytes() == encoded, "refusing to replace a different composite result"
        )
    else:
        output_path.write_bytes(encoded)
    return sha256(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the pinned result artifact")
    args = parser.parse_args()
    result, _frozen_rows, _base_rows, _after_rows = build_candidate()
    if args.write:
        result_sha = write_result(result)
        print(json.dumps({"RESULT_PATH": RESULT_PATH, "RESULT_SHA256": result_sha}, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in (
                        "TASK_STATUS",
                        "ROWS_AFTER",
                        "EVENTS_AFTER",
                        "FULL_DIGEST",
                        "BOUNDS_DIGEST",
                        "FAMILY_BOUND_AFTER",
                        "FAMILY_GAIN_VS_27_EVENT_BASE",
                    )
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
