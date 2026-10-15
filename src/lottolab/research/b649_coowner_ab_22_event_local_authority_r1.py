"""Replay the existing 20-event ledger and add only the judged A/B profiles."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen
from . import b649_t238_twenty_event_local_authority_r1 as twenty

TASK_ID = "B649_COOWNER_AB_22_EVENT_LOCAL_AUTHORITY_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-coowner-ab-22-event-local-authority-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
BASE_HEAD = "52da2de3974fbbc85c3dc10b40a8a7ba96ef80f0"
BASE_TREE = "9a50f7203922c5d8cdf3a422dd8f7e276040a51e"
TWENTY_TWO_HEAD = "90462d7a6877ced211ee129c82377baecb6c5eed"
TWENTY_TWO_TREE = "54260af5c0d96304f8ec09108afff9f8b55c7b82"
BASE_RESULT_PATH = twenty.RESULT_PATH
BASE_RESULT_SHA256 = "ccdaf9f9928fb26b3888550e0487f156243fe9d23e850f4eef5c4994042bc0f4"
BASE_FULL_DIGEST = "3fa64615e6615eb6e3d3fdf8e50739057194f8e781ce970d8eafac0212888089"
BASE_BOUNDS_DIGEST = "bd6162eebadb7740801c138bd5956c361922f075f381fe1674a7af1c45329dbb"

CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
CURSOR_COUNT = 197
EXPECTED_FAMILY_BOUND = 313_394_584
EXPECTED_BASE_NEXT_BOUND = 313_392_412
EXPECTED_BASE_NEXT_OWNERS = ["66655555555431000000", "66665555544441000000"]
EXPECTED_NEXT_BOUND = 313_392_308
EXPECTED_NEXT_OWNERS = ["66665555555421000000"]
EXPECTED_ROW_COUNT = 4_647
INCUMBENT = 313_263_888

JUDGE_A_REPORT_PATH = (
    "/Users/kelvin/.codex/attachments/9e2fdfa3-3e02-480b-bef4-5b8b4b4db251/"
    "B649_NEXT_COOWNER_A_T248_FRESH_JUDGE_R1-verdict.md"
)
JUDGE_B_REPORT_PATH = (
    "/Users/kelvin/.codex/attachments/f891653a-9de9-4d4f-854b-ef2d90b48383/"
    "judge-B649-T246-R1/judge-report.txt"
)


@dataclass(frozen=True)
class DonorSpec:
    event_id: str
    task_id: str
    worker_status: str
    profile_id: str
    previous_bound: int
    previous_cap: int
    s4_base: int
    cap: int
    bound: int
    head: str
    tree: str
    result_path: str
    result_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    historical_source: str
    judge_task_id: str
    judge_session_id: str
    judge_report_path: str
    judge_report_sha256: str
    judge_claim: str
    caveat: str
    caveat_markers: tuple[str, ...]


DONOR_A = DonorSpec(
    event_id="COOWNER_A_66655555555431000000",
    task_id="B649_NEXT_COOWNER_A_66655555555431000000_R1",
    worker_status="FULL_PROFILE_CERTIFICATE_SELF_CHECKED",
    profile_id="66655555555431000000",
    previous_bound=313_392_412,
    previous_cap=264,
    s4_base=112,
    cap=248,
    bound=313_249_020,
    head="317735e5d59691461f452c0b21760929c1fba6e3",
    tree="906bae1a9132f1c42402a7d44fcc28cc3eaf75fd",
    result_path=(
        "docs/research/matrix-native-results/"
        "b649-next-coowner-a-66655555555431000000-r1-result.json"
    ),
    result_sha256="52bbd4227d2605f6a2500447ecc62218d2a52090304bd318565bc134cf85d241",
    source_path="src/lottolab/research/b649_next_coowner_a_66655555555431000000_r1.py",
    source_sha256="b8d6834629dc9e82ffa737d16326604e5c6406732ebae0dc1d09b5298ac6c9c7",
    test_path="tests/unit/test_b649_next_coowner_a_66655555555431000000_r1.py",
    test_sha256="173536e4e81adf5328f30640516caf53b133d45c48408255a9802bc40485200e",
    historical_source=(
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1201]"
    ),
    judge_task_id="B649_NEXT_COOWNER_A_T248_FRESH_JUDGE_R1",
    judge_session_id="01a13ad3-f723-7313-b9d8-e90b868c042d",
    judge_report_path=JUDGE_A_REPORT_PATH,
    judge_report_sha256="a3f8c0af82ef39c1a18098f6af97b3e5da201e1c172f7f63e2c2c4c76c2f120f",
    judge_claim="T≤248",
    caveat=(
        "The original focused tests did not retain direct K4-floor-error or source-SHA-error "
        "cases. The Fresh-context Judge ran temporary checks and observed both rejected; "
        "this remains a non-blocking test-coverage caveat."
    ),
    caveat_markers=("K4 floor", "來源 SHA", "暫態檢查", "非阻擋"),
)

DONOR_B = DonorSpec(
    event_id="COOWNER_B_66665555544441000000",
    task_id="B649_NEXT_COOWNER_B_66665555544441000000_R1",
    worker_status="COMPLETE_SELF_CHECK_ONLY",
    profile_id="66665555544441000000",
    previous_bound=313_392_412,
    previous_cap=264,
    s4_base=112,
    cap=246,
    bound=313_231_096,
    head="d1c3c8ed613c844bc868cdd11415619fe5a1a6b2",
    tree="312f12f2a37f485410407e1b68d4d678709fbbc5",
    result_path=(
        "docs/research/matrix-native-results/"
        "b649-next-coowner-b-66665555544441000000-r1-result.json"
    ),
    result_sha256="6780c5e1aba9666aac82e0903a77228e6d72ad19ee0b49ccc94eca4a7bf19358",
    source_path="src/lottolab/research/b649_next_coowner_b_66665555544441000000_r1.py",
    source_sha256="34018e14b5886792d9d208533ab2803ad66a86d009e9f4dc61770e958c8c501b",
    test_path="tests/unit/test_b649_next_coowner_b_66665555544441000000_r1.py",
    test_sha256="ba287f2e14650a08b9f4d174cc074be2773309a613d8748179bbb35e4ea602eb",
    historical_source=(
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[912]"
    ),
    judge_task_id="B649_NEXT_COOWNER_B_T246_FRESH_JUDGE_R1",
    judge_session_id="01a13ad4-1b69-75a1-be73-0a85dd918350",
    judge_report_path=JUDGE_B_REPORT_PATH,
    judge_report_sha256="4f1c2192ba5f55f83972928ba2b9cc66dcb1763459baf545352ea3dd2d03b8e5",
    judge_claim="T≤246",
    caveat=(
        "NB_CERTIFICATES[912] is a replay-generated historical logical index, not a "
        "serialized JSON array pointer. The integration uses a donor commit/result/proof "
        "locator instead."
    ),
    caveat_markers=("NB_CERTIFICATES[912]", "replay", "不能直接當作", "VERIFIED_WITH_CAVEATS"),
)

DONORS = (DONOR_A, DONOR_B)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(message) from exc
    require(type(value) is dict, message)
    return cast(dict[str, Any], value)


def _capture(pattern: str, text: str, message: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    require(match is not None, message)
    return cast(re.Match[str], match).group(1)


def verify_judge_report(spec: DonorSpec) -> dict[str, Any]:
    """Bind actual report bytes, reviewed Git identity, verdict and caveat to a donor."""
    raw = Path(spec.judge_report_path).read_bytes()
    require(sha256(raw) == spec.judge_report_sha256, "Judge report SHA256 mismatch")
    text = raw.decode("utf-8")
    verdict = _capture(
        r"^FRESH_CONTEXT_VERDICT:\s*(\S+)\s*$", text, "Judge verdict missing"
    )
    task_id = _capture(r"^TASK_ID:\s*(\S+)\s*$", text, "Judge task ID missing")
    session_id = _capture(
        r"^JUDGE_SESSION_ID:\s*(\S+)\s*$", text, "Judge session ID missing"
    )
    judge_mode = _capture(r"^JUDGE_MODE:\s*(\S+)\s*$", text, "Judge mode missing")
    identity_match = re.search(
        r"(?m)^REVIEWED_HEAD_TREE:\s*\n\s*HEAD:\s*([0-9a-f]{40})\s*\n"
        r"\s*TREE:\s*([0-9a-f]{40})\s*$",
        text,
    )
    require(identity_match is not None, "Judge reviewed HEAD/tree missing")
    reviewed_head, reviewed_tree = cast(re.Match[str], identity_match).groups()
    result_hashes = re.findall(
        r"(?m)^\s*DONOR_RESULT_SHA256:\s*([0-9a-f]{64})\s*$", text
    )
    require(
        verdict == "VERIFIED_WITH_CAVEATS"
        and task_id == spec.judge_task_id
        and session_id == spec.judge_session_id
        and judge_mode == "FRESH_CONTEXT"
        and reviewed_head == spec.head
        and reviewed_tree == spec.tree
        and bool(result_hashes)
        and set(result_hashes) == {spec.result_sha256}
        and spec.profile_id in text
        and spec.judge_claim in text
        and all(marker in text for marker in spec.caveat_markers),
        "Judge report does not identify the pinned donor, verdict or caveat",
    )
    return {
        "PATH": spec.judge_report_path,
        "SHA256": sha256(raw),
        "TASK_ID": task_id,
        "SESSION_ID": session_id,
        "JUDGE_MODE": judge_mode,
        "VERDICT": verdict,
        "REVIEWED_HEAD": reviewed_head,
        "REVIEWED_TREE": reviewed_tree,
        "DONOR_RESULT_SHA256": result_hashes[0],
        "PROFILE_ID": spec.profile_id,
        "PROFILE_IDENTITY_BINDING": "REPORT_RESULT_SHA256_RESOLVES_TO_PINNED_PROFILE",
        "CAVEAT": spec.caveat,
        "CAVEAT_PRESERVED": True,
    }


def validate_donor_result(
    record: Mapping[str, Any], spec: DonorSpec, frozen_row: four.Row
) -> str:
    proof = record.get("PROOF")
    require(type(proof) is str and bool(proof.strip()), "donor proof is missing")
    try:
        source_doc = ast.get_docstring(
            ast.parse(four.committed_blob(ROOT, spec.head, spec.source_path).decode("utf-8")),
            clean=False,
        )
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("donor source proof cannot be parsed") from exc
    require(source_doc == proof, "donor proof differs from committed source docstring")
    source_row = record.get("SOURCE_ROW")
    require(type(source_row) is dict, "donor source row is missing")
    source_values = cast(dict[str, Any], source_row)
    actual_row = (
        source_values.get("bound"),
        source_values.get("cap"),
        source_values.get("s4_base"),
        source_values.get("source"),
    )
    frozen_values = (frozen_row.bound, frozen_row.cap, frozen_row.s4_base, frozen_row.source)
    actual_claim = (
        record.get("TASK_ID"),
        record.get("TASK_STATUS"),
        record.get("JUDGE_MODE"),
        record.get("PROFILE_ID"),
        record.get("SOURCE_T_CAP"),
        record.get("SOURCE_ROW_BOUND"),
        record.get("SOURCE_S4_BASE"),
        record.get("OLD_BOUND"),
        record.get("PROVED_T_CAP"),
        record.get("NEW_ADMISSIBLE_BOUND"),
        record.get("PROOF_SCOPE"),
        record.get("FAMILY_GAIN_CLAIMED"),
    )
    expected_claim = (
        spec.task_id,
        spec.worker_status,
        "SELF_CHECK_ONLY",
        spec.profile_id,
        spec.previous_cap,
        spec.previous_bound,
        spec.s4_base,
        spec.previous_bound,
        spec.cap,
        spec.bound,
        "FULL_PROFILE",
        0,
    )
    require(actual_row == frozen_values, "donor source row differs from replayed Frozen row")
    require(actual_claim == expected_claim, "donor profile, cap, bound or Worker status mismatch")
    delta = record.get("OWNER_DELTA", record.get("OWNER_BOUND_DELTA"))
    require(delta == spec.previous_bound - spec.bound, "donor Owner delta mismatch")
    require(
        record.get("NEW_WINNING_OUTCOMES") == 0
        and record.get("GLOBAL_K20_OPTIMUM") == "UNKNOWN"
        and record.get("UNPROVED_ASSUMPTIONS") == [],
        "donor makes an out-of-scope claim or leaves assumptions unproved",
    )
    require(
        record.get("FROZEN_HEAD") == FROZEN_HEAD
        and record.get("FROZEN_TREE") == FROZEN_TREE
        and record.get("FROZEN_HEAD_TREE") == "MATCH"
        and record.get("FROZEN_RESULT_SHA256")
        in {FROZEN_RESULT_SHA256, "MATCH"},
        "donor Frozen identity mismatch",
    )
    return sha256(cast(str, proof).encode())


def donor_pin(spec: DonorSpec, identity: Mapping[str, Any]) -> nine.DonorPin:
    return nine.DonorPin(
        event_id=spec.event_id,
        task_id=spec.task_id,
        profile_id=spec.profile_id,
        previous_bound=spec.previous_bound,
        previous_cap=spec.previous_cap,
        bound=spec.bound,
        cap=spec.cap,
        s4_base=spec.s4_base,
        head=spec.head,
        tree=spec.tree,
        result_path=spec.result_path,
        result_sha256=spec.result_sha256,
        source_path=spec.source_path,
        source_sha256=cast(str, identity["SOURCE_SHA256"]),
        test_path=spec.test_path,
        test_sha256=cast(str, identity["TEST_SHA256"]),
        proof_sha256=cast(str, identity["PROOF_SHA256"]),
    )


def verify_donor_artifact(
    root: Path, frozen_row: four.Row, spec: DonorSpec
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    four.verify_commit(root, FROZEN_HEAD, FROZEN_TREE)
    four.verify_commit(root, spec.head, spec.tree)
    parents = cast(
        str, four.run_git(root, "rev-list", "--parents", "-n", "1", spec.head)
    ).split()
    require(parents == [spec.head, FROZEN_HEAD], "donor parent is not the Frozen HEAD")
    paths = {"RESULT": spec.result_path, "SOURCE": spec.source_path, "TEST": spec.test_path}
    blobs = {name: four.committed_blob(root, spec.head, path) for name, path in paths.items()}
    require(sha256(blobs["RESULT"]) == spec.result_sha256, "donor result SHA256 mismatch")
    require(sha256(blobs["SOURCE"]) == spec.source_sha256, "donor source SHA256 mismatch")
    require(sha256(blobs["TEST"]) == spec.test_sha256, "donor test SHA256 mismatch")
    record = json_object(blobs["RESULT"], "donor result is invalid JSON")
    proof_sha = validate_donor_result(record, spec, frozen_row)
    report = verify_judge_report(spec)
    row_source = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}#PROOF:sha256={proof_sha}"
    )
    identity = {
        "EVENT_ID": spec.event_id,
        "TASK_ID": spec.task_id,
        "HEAD": spec.head,
        "TREE": spec.tree,
        "PARENT": FROZEN_HEAD,
        "HEAD_TREE": "MATCH",
        "RESULT_PATH": spec.result_path,
        "RESULT_SHA256": sha256(blobs["RESULT"]),
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
        "WORKER_STATUS": spec.worker_status,
        "WORKER_JUDGE_MODE": record["JUDGE_MODE"],
        "PROOF_SCOPE": record["PROOF_SCOPE"],
        "PROOF_SHA256": proof_sha,
        "PROOF_LOCATOR": row_source,
        "ROW_SOURCE": row_source,
        "HISTORICAL_SOURCE_LOCATOR": frozen_row.source,
        "FRESH_CONTEXT_JUDGE": report,
        "FAMILY_GAIN_CLAIMED_BY_DONOR": record["FAMILY_GAIN_CLAIMED"],
    }
    return record, identity, blobs


def verify_source_identity(root: Path, current_head: str) -> None:
    four.verify_commit(root, FROZEN_HEAD, FROZEN_TREE)
    four.verify_commit(root, BASE_HEAD, BASE_TREE)
    four.verify_commit(root, TWENTY_TWO_HEAD, TWENTY_TWO_TREE)
    candidate_parents = cast(
        str, four.run_git(root, "rev-list", "--parents", "-n", "1", TWENTY_TWO_HEAD)
    ).split()
    require(
        candidate_parents == [TWENTY_TWO_HEAD, BASE_HEAD],
        "pinned 22-event commit is not based on the pinned 20-event base",
    )
    if current_head == TWENTY_TWO_HEAD:
        return
    current_parents = cast(
        str, four.run_git(root, "rev-list", "--parents", "-n", "1", current_head)
    ).split()
    require(
        current_parents == [current_head, TWENTY_TWO_HEAD],
        "integration HEAD is not the pinned 22-event commit or its direct successor",
    )


def verify_base() -> tuple[
    dict[str, Any], dict[str, four.Row], dict[str, four.Row], bytes
]:
    verify_source_identity(ROOT, cast(str, four.run_git(ROOT, "rev-parse", "HEAD")))
    base_raw = four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    require(sha256(base_raw) == BASE_RESULT_SHA256, "20-event result SHA256 mismatch")
    require((ROOT / BASE_RESULT_PATH).read_bytes() == base_raw, "working 20-event result differs")
    recorded = json_object(base_raw, "20-event base result is invalid JSON")
    replay, frozen, after_twenty = twenty.build_candidate()
    require(
        replay == recorded and twenty.serialize_result(replay) == base_raw,
        "20-event result differs from complete replay",
    )
    require(
        len(frozen) == len(after_twenty) == EXPECTED_ROW_COUNT
        and replay["TOTAL_EVENTS"] == len(replay["EVENT_HISTORY"]) == 20
        and replay["FAMILY_BOUND_AFTER"] == EXPECTED_FAMILY_BOUND
        and replay["FULL_DIGEST"] == BASE_FULL_DIGEST
        and replay["BOUNDS_DIGEST"] == BASE_BOUNDS_DIGEST,
        "20-event replay count, Family frontier or digest mismatch",
    )
    old_changed = {
        profile_id
        for profile_id in frozen
        if frozen[profile_id] != after_twenty[profile_id]
    }
    require(
        len(old_changed) == 19
        and replay["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"] == 19
        and replay["UNCHANGED_ROWS_FROM_FROZEN"] == 4_628,
        "20-event changed-profile partition mismatch",
    )
    return replay, frozen, after_twenty, base_raw


def expected_family(
    next_bound: int = EXPECTED_NEXT_BOUND,
    next_owners: list[str] = EXPECTED_NEXT_OWNERS,
) -> dict[str, Any]:
    return {
        "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
        "TIED_OWNERS": [CURSOR_ID],
        "NEXT_COMPETING_BOUND": next_bound,
        "NEXT_COMPETING_OWNERS": next_owners,
        "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
    }


def expect_rejected(action: Any, message: str) -> str:
    try:
        action()
    except ValueError:
        return "PASS"
    raise ValueError(message)


def verify_negative_cases(
    base_rows: Mapping[str, four.Row],
    frozen: Mapping[str, four.Row],
    after: Mapping[str, four.Row],
    donor_records: Mapping[str, Mapping[str, Any]],
    donor_identities: Mapping[str, Mapping[str, Any]],
    pins: tuple[nine.DonorPin, ...],
    family_after: Mapping[str, Any],
) -> dict[str, str]:
    spec_a, spec_b = DONORS
    wrong_sha = replace(spec_a, result_sha256="0" * 64)
    record_a = donor_records[spec_a.event_id]
    source_row_a = frozen[spec_a.profile_id]
    wrong_profile = replace(spec_a, profile_id="0" * 20)
    wrong_cap = replace(spec_a, cap=spec_a.cap - 1)
    wrong_bound = replace(spec_a, bound=spec_a.bound + 1)
    missing_proof = dict(record_a)
    missing_proof.pop("PROOF", None)
    duplicated_pin = pins[0]
    duplicate_events = [duplicated_pin, duplicated_pin]
    identities = {spec_a.event_id: donor_identities[spec_a.event_id]}
    unrelated_profile = next(
        profile_id for profile_id in after if profile_id not in {s.profile_id for s in DONORS}
    )
    unrelated_change = dict(after)
    unrelated_change[unrelated_profile] = replace(
        unrelated_change[unrelated_profile], source="unrelated-row-mutation"
    )
    missing_cursor = dict(family_after)
    missing_cursor.pop("CURSOR", None)
    return {
        "WRONG_DONOR_SHA_REJECTED": expect_rejected(
            lambda: verify_donor_artifact(ROOT, source_row_a, wrong_sha),
            "wrong donor SHA was accepted",
        ),
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: validate_donor_result(record_a, wrong_profile, source_row_a),
            "wrong donor profile was accepted",
        ),
        "WRONG_CAP_REJECTED": expect_rejected(
            lambda: validate_donor_result(record_a, wrong_cap, source_row_a),
            "wrong donor cap was accepted",
        ),
        "WRONG_BOUND_REJECTED": expect_rejected(
            lambda: validate_donor_result(record_a, wrong_bound, source_row_a),
            "wrong donor bound was accepted",
        ),
        "MISSING_PROOF_REJECTED": expect_rejected(
            lambda: validate_donor_result(missing_proof, spec_a, source_row_a),
            "missing donor proof was accepted",
        ),
        "DUPLICATE_EVENT_REJECTED": expect_rejected(
            lambda: nine.apply_donor_events(base_rows, duplicate_events, identities),
            "duplicate donor event was accepted",
        ),
        "UNRELATED_ROW_CHANGE_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(
                base_rows,
                unrelated_change,
                {spec_a.profile_id, spec_b.profile_id},
            ),
            "unrelated row mutation was accepted",
        ),
        "CURSOR_OMISSION_REJECTED": expect_rejected(
            lambda: four.verify_family_summary(missing_cursor, expected_family()),
            "cursor omission was accepted",
        ),
    }


def build_candidate() -> tuple[
    dict[str, Any], dict[str, four.Row], dict[str, four.Row], dict[str, four.Row]
]:
    base, frozen, after_twenty, base_raw = verify_base()
    donor_records: dict[str, dict[str, Any]] = {}
    donor_identities: dict[str, dict[str, Any]] = {}
    donor_blobs: dict[str, dict[str, bytes]] = {}
    pins: list[nine.DonorPin] = []
    for spec in DONORS:
        row = frozen.get(spec.profile_id)
        require(row is not None, f"Frozen ledger omitted profile {spec.profile_id}")
        target = cast(four.Row, row)
        require(
            after_twenty.get(spec.profile_id) == target,
            f"20-event base already changed target {spec.profile_id}",
        )
        require(
            (target.bound, target.cap, target.s4_base, target.source)
            == (spec.previous_bound, spec.previous_cap, spec.s4_base, spec.historical_source),
            f"Frozen target row mismatch: {spec.profile_id}",
        )
        record, identity, blobs = verify_donor_artifact(ROOT, target, spec)
        donor_records[spec.event_id] = record
        donor_identities[spec.event_id] = identity
        donor_blobs[spec.event_id] = blobs
        pins.append(donor_pin(spec, identity))

    pin_tuple = tuple(pins)
    before_family = four.family_frontier(after_twenty)
    four.verify_family_summary(
        before_family,
        expected_family(EXPECTED_BASE_NEXT_BOUND, EXPECTED_BASE_NEXT_OWNERS),
    )
    after_twenty_two, new_events = nine.apply_donor_events(
        after_twenty, pin_tuple, donor_identities
    )
    require(
        len(new_events) == 2
        and [event["PROFILE_ID"] for event in new_events]
        == [DONOR_A.profile_id, DONOR_B.profile_id],
        "the integration must add exactly the two pinned donor events",
    )
    for event, spec in zip(new_events, DONORS, strict=True):
        identity = donor_identities[spec.event_id]
        require(
            event.get("EVENT_ID") == spec.event_id
            and event.get("BOUND_BEFORE") == spec.previous_bound
            and event.get("BOUND_AFTER") == spec.bound
            and event.get("CAP_BEFORE") == spec.previous_cap
            and event.get("CAP_AFTER") == spec.cap
            and event.get("S4_BASE_BEFORE") == spec.s4_base
            and event.get("S4_BASE_AFTER") == spec.s4_base
            and event.get("SOURCE_AFTER") == identity["PROOF_LOCATOR"],
            f"event transition or proof source mismatch: {spec.event_id}",
        )

    previous_events = cast(list[dict[str, Any]], base["EVENT_HISTORY"])
    events = previous_events + new_events
    sixteen.verify_unique_events(events)
    require(
        len(previous_events) == 20 and len(new_events) == 2 and len(events) == 22,
        "event history must preserve 20 events and add exactly two",
    )
    base_changed = {spec.profile_id for spec in DONORS}
    changed_from_base = sixteen.verify_ledger_partition(
        after_twenty, after_twenty_two, base_changed
    )
    changed_from_frozen_before = {
        profile_id
        for profile_id in frozen
        if frozen[profile_id] != after_twenty[profile_id]
    }
    require(len(changed_from_frozen_before) == 19, "20-event changed profile count mismatch")
    changed_from_frozen = sixteen.verify_ledger_partition(
        frozen, after_twenty_two, changed_from_frozen_before | base_changed
    )
    require(
        len(changed_from_frozen) == 21
        and len(frozen) - len(changed_from_frozen) == 4_626
        and len(changed_from_base) == 2
        and len(after_twenty) - len(changed_from_base) == 4_645,
        "22-event changed/unchanged row partition mismatch",
    )
    for spec in DONORS:
        require(
            after_twenty_two[spec.profile_id].source
            == donor_identities[spec.event_id]["PROOF_LOCATOR"],
            f"new Row.source is not bound to donor commit/result/proof: {spec.profile_id}",
        )

    before_full = four.seven.two.full_digest(after_twenty)
    before_bounds = four.seven.two.bounds_digest(after_twenty)
    full_digest = four.seven.two.full_digest(after_twenty_two)
    bounds_digest = four.seven.two.bounds_digest(after_twenty_two)
    require(
        before_full == BASE_FULL_DIGEST and before_bounds == BASE_BOUNDS_DIGEST,
        "20-event full or bounds digest mismatch before new events",
    )
    family_after = four.family_frontier(after_twenty_two)
    four.verify_family_summary(family_after, expected_family())
    require(
        before_family["FAMILY_BOUND"] == family_after["FAMILY_BOUND"]
        and before_family["FAMILY_BOUND"] - family_after["FAMILY_BOUND"] == 0,
        "Family maximum changed during co-owner row integration",
    )
    cursor_authority = cast(dict[str, Any], base["CURSOR_AUTHORITY"])
    require(
        cursor_authority.get("ID") == CURSOR_ID
        and cursor_authority.get("BOUND") == CURSOR_BOUND
        and cursor_authority.get("COUNT") == CURSOR_COUNT
        and family_after["CURSOR"] == {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "unresolved cursor identity or count was not preserved",
    )
    resolved_above_incumbent = sum(
        row.bound > INCUMBENT for row in after_twenty_two.values()
    )
    require(resolved_above_incumbent == 1_364, "resolved profiles above incumbent mismatch")
    require(
        base["NEW_WINNING_OUTCOMES"] == 0
        and base["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
        and all(record["NEW_WINNING_OUTCOMES"] == 0 for record in donor_records.values()),
        "integration must not claim new winners or a global K20 optimum",
    )

    negative_validations = verify_negative_cases(
        after_twenty,
        frozen,
        after_twenty_two,
        donor_records,
        donor_identities,
        pin_tuple,
        family_after,
    )
    require(
        set(negative_validations.values()) == {"PASS"},
        "a negative integration mutation was accepted",
    )
    transitions = cast(list[dict[str, Any]], base["EVENT_FAMILY_TRANSITIONS"])
    require(len(transitions) == 4, "20-event Family transition checkpoints mismatch")
    event_transitions = [
        *transitions,
        *[
            {
                "EVENT_ID": spec.event_id,
                "FAMILY_BOUND_BEFORE": before_family["FAMILY_BOUND"],
                "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
                "TIED_OWNERS_AFTER": family_after["TIED_OWNERS"],
                "NEXT_COMPETING_BOUND_AFTER": family_after["NEXT_COMPETING_BOUND"],
                "NEXT_COMPETING_OWNERS_AFTER": family_after["NEXT_COMPETING_OWNERS"],
            }
            for spec in DONORS
        ],
    ]
    family_deltas = {
        spec.profile_id: spec.previous_bound - spec.bound for spec in DONORS
    }
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_22_EVENT_CANDIDATE_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "FROZEN_RESULT_SHA256": "MATCH",
            "BASE_HEAD_TREE": "MATCH",
            "BASE_RESULT_SHA256": "MATCH",
            "DONOR_A_HEAD_TREE": "MATCH",
            "DONOR_A_RESULT_SHA256": "MATCH",
            "DONOR_A_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
            "DONOR_B_HEAD_TREE": "MATCH",
            "DONOR_B_RESULT_SHA256": "MATCH",
            "DONOR_B_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
            "ALL_NEW_PROOF_LOCATORS_RESOLVE": "YES",
        },
        "FROZEN_AUTHORITY": base["FROZEN_AUTHORITY"],
        "BASE_20_EVENT_AUTHORITY": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "FULL_DIGEST": before_full,
            "BOUNDS_DIGEST": before_bounds,
            "EVENTS": len(previous_events),
            "REPLAY_MATCH": "YES",
        },
        "DONOR_IDENTITIES": donor_identities,
        "INHERITED_CAVEATS_PRESERVED": {
            spec.event_id: {
                "WORKER_JUDGE_MODE": donor_identities[spec.event_id]["WORKER_JUDGE_MODE"],
                "JUDGE_VERDICT": "VERIFIED_WITH_CAVEATS",
                "JUDGE_SESSION_ID": donor_identities[spec.event_id]["FRESH_CONTEXT_JUDGE"][
                    "SESSION_ID"
                ],
                "JUDGE_REPORT_SHA256": donor_identities[spec.event_id]["FRESH_CONTEXT_JUDGE"][
                    "SHA256"
                ],
                "CAVEAT": spec.caveat,
            }
            for spec in DONORS
        },
        "ROWS_BEFORE": len(frozen),
        "ROWS_AFTER": len(after_twenty_two),
        "PREVIOUS_EVENTS": len(previous_events),
        "NEW_EVENTS": len(new_events),
        "UPDATE_EVENTS": len(events),
        "TOTAL_EVENTS": len(events),
        "DISTINCT_CHANGED_PROFILES": len(changed_from_frozen),
        "CHANGED_PROFILE_IDS_FROM_FROZEN": sorted(changed_from_frozen),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed_from_frozen),
        "CHANGED_ROWS_FROM_BASE": len(changed_from_base),
        "UNCHANGED_ROWS_FROM_BASE": len(after_twenty) - len(changed_from_base),
        "OWNER_A_OLD_CAP": DONOR_A.previous_cap,
        "OWNER_A_NEW_CAP": DONOR_A.cap,
        "OWNER_A_OLD_BOUND": DONOR_A.previous_bound,
        "OWNER_A_NEW_BOUND": DONOR_A.bound,
        "OWNER_A_BOUND_DELTA": family_deltas[DONOR_A.profile_id],
        "OWNER_B_OLD_CAP": DONOR_B.previous_cap,
        "OWNER_B_NEW_CAP": DONOR_B.cap,
        "OWNER_B_OLD_BOUND": DONOR_B.previous_bound,
        "OWNER_B_NEW_BOUND": DONOR_B.bound,
        "OWNER_B_BOUND_DELTA": family_deltas[DONOR_B.profile_id],
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "ALL_NEW_PROOF_LOCATORS_RESOLVE": "YES",
        "UNRELATED_ROW_MUTATION": "NONE",
        "FULL_DIGEST": full_digest,
        "BOUNDS_DIGEST": bounds_digest,
        "NEW_FULL_DIGEST": full_digest,
        "NEW_BOUNDS_DIGEST": bounds_digest,
        "LEDGER_OVERLAY": {
            "ROWS_BEFORE": len(frozen),
            "ROWS_AFTER": len(after_twenty_two),
            "FULL_DIGEST_BEFORE": before_full,
            "BOUNDS_DIGEST_BEFORE": before_bounds,
            "FULL_DIGEST_AFTER": full_digest,
            "BOUNDS_DIGEST_AFTER": bounds_digest,
            "FULL_DIGEST_IS_ROW_SOURCE_AWARE": "YES",
            "SOURCE_METADATA_BINDINGS": "VERIFIED",
            "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed_from_frozen),
            "UNCHANGED_ROWS_FROM_BASE": len(after_twenty) - len(changed_from_base),
            "UNRELATED_ROW_MUTATION": "NONE",
        },
        "EVENT_HISTORY": events,
        "EVENT_FAMILY_TRANSITIONS": event_transitions,
        "FAMILY_BOUND_BEFORE": before_family["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": before_family["FAMILY_BOUND"] - family_after["FAMILY_BOUND"],
        "MAX_OWNER": CURSOR_ID,
        "MAX_OWNER_TYPE": "UNRESOLVED_CURSOR",
        "NEXT_DISTINCT_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_COMPETING_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": resolved_above_incumbent,
        "CURSOR_COUNT": cursor_authority["COUNT"],
        "CURSOR_BOUND": cursor_authority["BOUND"],
        "CURSOR_INCLUDED": "YES",
        "CURSOR_AUTHORITY": cursor_authority,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "OLD_LEDGER_UNCHANGED": "YES",
        "FROZEN_LEDGER_MUTATED": "NO",
        "DONOR_WORKTREES_MUTATED": "NO",
        "NEGATIVE_VALIDATIONS": negative_validations,
        "FOCUSED_TEST_PATH": (
            "tests/unit/test_b649_coowner_ab_22_event_local_authority_r1.py"
        ),
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    require(result["FAMILY_GAIN"] == 0, "Owner deltas must not be called Family gain")
    require(
        json_object(serialize_result(result), "22-event result serialization is invalid") == result,
        "22-event result JSON round trip mismatch",
    )
    return result, frozen, after_twenty, after_twenty_two


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    require(not path.exists(), "refusing to overwrite an existing integration result")
    with path.open("xb") as output:
        output.write(raw)
    require(path.read_bytes() == raw, "result read-after-write mismatch")
    return sha256(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result, _frozen, _base_rows, _after = build_candidate()
    raw = serialize_result(result)
    digest = sha256(raw)
    if args.write_result:
        digest = write_result(result)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "RESULT_PATH": RESULT_PATH if args.write_result else "NOT_WRITTEN",
                "RESULT_SHA256": digest,
                "ROWS_BEFORE": result["ROWS_BEFORE"],
                "ROWS_AFTER": result["ROWS_AFTER"],
                "PREVIOUS_EVENTS": result["PREVIOUS_EVENTS"],
                "NEW_EVENTS": result["NEW_EVENTS"],
                "TOTAL_EVENTS": result["TOTAL_EVENTS"],
                "DISTINCT_CHANGED_PROFILES": result["DISTINCT_CHANGED_PROFILES"],
                "UNCHANGED_ROWS_FROM_FROZEN": result["UNCHANGED_ROWS_FROM_FROZEN"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
                "FAMILY_BOUND_BEFORE": result["FAMILY_BOUND_BEFORE"],
                "FAMILY_BOUND_AFTER": result["FAMILY_BOUND_AFTER"],
                "FAMILY_GAIN": result["FAMILY_GAIN"],
                "MAX_OWNER": result["MAX_OWNER"],
                "NEXT_DISTINCT_BOUND": result["NEXT_DISTINCT_BOUND"],
                "NEXT_COMPETING_OWNERS": result["NEXT_COMPETING_OWNERS"],
                "NEGATIVE_VALIDATIONS": result["NEGATIVE_VALIDATIONS"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
