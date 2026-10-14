"""Rebuild the 20-event B649 local Family Authority candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_nineteen_event_local_family_authority_r1 as nineteen
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen

TASK_ID = "B649_T238_TWENTY_EVENT_LOCAL_AUTHORITY_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-t238-twenty-event-local-authority-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
)
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
SIX_ROW_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
SIX_ROW_RESULT_SHA256 = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"

BASE_HEAD = "2f208ec87f7be5e536153b2b1f56f9f3ec5b7ae5"
BASE_TREE = "24256dda5764c9b3f3f88d62728384c1a70ea2ba"
BASE_RESULT_PATH = nineteen.RESULT_PATH
BASE_RESULT_SHA256 = "561768b28ab5115a98637f8148d159545e79a37bff985af410be6a9cb16c391d"
BASE_FULL_DIGEST = "d10732eb35fca5dbd7155efa1f70005f5f0a29a0ce124a214204f8fadb39e700"
BASE_BOUNDS_DIGEST = "fc086130c7505f0a8106ec25e234a87e4277df0f32436e3434227fe1afa770e1"

T238_HEAD = "fdf242b272d28f51ecab7967d2087c934804eac1"
T238_TREE = "b970687832598c95cd28c3131436713b043743e8"
T238_TASK_ID = "B649_NEXT_RESOLVED_OWNER_65555555555541000000_R1"
T238_PROFILE_ID = "65555555555541000000"
T238_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-next-resolved-owner-65555555555541000000-r1-result.json"
)
T238_RESULT_SHA256 = "1458041ea76b0f132e68d2281ad2fbc25fc6281ed6f21c13632d8588b1864f51"
T238_SOURCE_PATH = (
    "src/lottolab/research/b649_next_resolved_owner_65555555555541000000_r1.py"
)
T238_TEST_PATH = "tests/unit/test_b649_next_resolved_owner_65555555555541000000_r1.py"
T238_JUDGE_SESSION_ID = "01a13a54-c2c2-7510-a300-0527929429b0"

T238_HISTORICAL_ROW_SOURCE = (
    "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1614]"
)
R30_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
R30_RESULT_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
R30_ATTEMPT_INDEX = 3397
R30_PROOF_OBJECT_SHA256 = "b6f826609608b17265d1164afd79a559f68168bdfa3cdc2502fcea53d9440b2d"

CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
CURSOR_COUNT = 197
INCUMBENT = 313_263_888
EXPECTED_ROW_COUNT = 4_647
EXPECTED_FAMILY_BOUND = 313_394_584
EXPECTED_NEXT_BOUND = 313_392_412
EXPECTED_NEXT_OWNERS = ["66655555555431000000", "66665555544441000000"]


@dataclass(frozen=True)
class T238Spec:
    event_id: str
    task_id: str
    profile_id: str
    before_bound: int
    before_cap: int
    s4_base: int
    after_bound: int
    after_cap: int
    head: str
    tree: str
    result_path: str
    result_sha256: str
    source_path: str
    test_path: str
    proof_fragment: str
    historical_row_source: str


T238 = T238Spec(
    event_id="T238_65555555555541000000",
    task_id=T238_TASK_ID,
    profile_id=T238_PROFILE_ID,
    before_bound=313_392_516,
    before_cap=265,
    s4_base=112,
    after_bound=313_150_736,
    after_cap=238,
    head=T238_HEAD,
    tree=T238_TREE,
    result_path=T238_RESULT_PATH,
    result_sha256=T238_RESULT_SHA256,
    source_path=T238_SOURCE_PATH,
    test_path=T238_TEST_PATH,
    proof_fragment="THEOREM_T238",
    historical_row_source=T238_HISTORICAL_ROW_SOURCE,
)


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


def validate_t238_claim(record: Mapping[str, Any], spec: T238Spec) -> None:
    source_row_raw = record.get("SOURCE_ROW")
    require(type(source_row_raw) is dict, "T238 historical source row is missing")
    source_row = cast(dict[str, Any], source_row_raw)
    actual = (
        record.get("TASK_ID"),
        record.get("PROFILE_ID"),
        record.get("SOURCE_OLD_BOUND"),
        record.get("SOURCE_T_CAP"),
        record.get("SOURCE_S4_BASE"),
        source_row.get("BOUND"),
        source_row.get("CAP"),
        source_row.get("S4_BASE"),
        source_row.get("SOURCE"),
        record.get("PROVED_T_CAP"),
        record.get("NEW_ADMISSIBLE_BOUND"),
    )
    expected = (
        spec.task_id,
        spec.profile_id,
        spec.before_bound,
        spec.before_cap,
        spec.s4_base,
        spec.before_bound,
        spec.before_cap,
        spec.s4_base,
        spec.historical_row_source,
        spec.after_cap,
        spec.after_bound,
    )
    require(actual == expected, "T238 profile, historical row, cap, or bound mismatch")
    require(record.get("PROOF_SCOPE") == "FULL_PROFILE", "T238 proof is not full-profile")
    require(record.get("FAMILY_GAIN_CLAIMED") == 0, "T238 donor claims a Family gain")


def proof_source(spec: T238Spec, proof_sha256: str) -> str:
    return (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f"#{spec.proof_fragment}:sha256={proof_sha256}"
    )


def verify_proof_locator(
    record: Mapping[str, Any], spec: T238Spec, locator: str
) -> tuple[str, dict[str, Any]]:
    proof_raw = record.get(spec.proof_fragment)
    require(type(proof_raw) is dict, "T238 theorem proof fragment is missing")
    proof = cast(dict[str, Any], proof_raw)
    require(
        proof.get("PROFILE_ID") == spec.profile_id
        and proof.get("PROOF_SCOPE") == "FULL_PROFILE"
        and proof.get("STATUS") == "PROVEN"
        and proof.get("TRIANGLE_CAP") == spec.after_cap
        and proof.get("PHI_GOODMAN") == 293
        and record.get("GOODMAN_CONSTANT") == 293,
        "T238 theorem fragment identity mismatch",
    )
    relaxation_raw = proof.get("BALANCED_RELAXATION")
    require(
        type(relaxation_raw) is dict
        and cast(dict[str, Any], relaxation_raw).get("MAXIMUM") == spec.after_cap,
        "T238 theorem relaxation cap mismatch",
    )
    proof_sha = nineteen.canonical_json_sha256(proof)
    require(locator == proof_source(spec, proof_sha), "T238 proof locator mismatch")
    return proof_sha, proof


def verify_r30_cap_source(
    root: Path, record: Mapping[str, Any], spec: T238Spec
) -> dict[str, Any]:
    locator = f"{R30_RESULT_PATH}:GROUP_ATTEMPTS[{R30_ATTEMPT_INDEX}]"
    require(record.get("SOURCE_PROOF_LOCATOR") == locator, "R30 cap source locator mismatch")
    cap_source_raw = record.get("SOURCE_CAP_AUTHORITY")
    require(type(cap_source_raw) is dict, "R30 cap source authority is missing")
    cap_source = cast(dict[str, Any], cap_source_raw)
    r30_raw = four.committed_blob(root, FROZEN_HEAD, R30_RESULT_PATH)
    nineteen.require_hash(r30_raw, R30_RESULT_SHA256, "R30 result")
    require((root / R30_RESULT_PATH).read_bytes() == r30_raw, "working R30 result differs")
    r30 = json_object(r30_raw, "R30 result is invalid JSON")
    attempts_raw = r30.get("GROUP_ATTEMPTS")
    require(type(attempts_raw) is list, "R30 GROUP_ATTEMPTS is missing")
    attempts = cast(list[Any], attempts_raw)
    require(len(attempts) > R30_ATTEMPT_INDEX, "R30 attempt index is out of range")
    attempt_raw = attempts[R30_ATTEMPT_INDEX]
    require(type(attempt_raw) is dict, "R30 indexed attempt is invalid")
    attempt = cast(dict[str, Any], attempt_raw)
    attempt_sha = sha256(json.dumps(attempt, sort_keys=True).encode())
    expected_attempt = (
        attempt.get("ATTEMPT_INDEX"),
        attempt.get("PROFILE_IDS"),
        attempt.get("STATUS"),
        attempt.get("CERTIFICATE_KIND"),
        attempt.get("CURRENT_TRIANGLE_CAP"),
        attempt.get("TARGET_TRIANGLE_CAP"),
        attempt.get("REFUTED_GRAPH_TRIANGLE_COUNT"),
        attempt.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"),
        attempt_sha,
    )
    require(
        expected_attempt
        == (
            R30_ATTEMPT_INDEX,
            [spec.profile_id],
            "INFEASIBLE",
            "CP_SAT_INFEASIBLE",
            spec.before_cap + 1,
            spec.before_cap,
            spec.before_cap + 1,
            spec.before_cap,
            R30_PROOF_OBJECT_SHA256,
        ),
        "R30 attempt does not resolve to the historical profile cap",
    )
    expected_cap_source = (
        cap_source.get("SOURCE_LABEL"),
        cap_source.get("SOURCE_LABEL_KIND"),
        cap_source.get("R30_RESULT"),
        cap_source.get("R30_RESULT_SHA256"),
        cap_source.get("ATTEMPT"),
        cap_source.get("PROOF_OBJECT_SHA256"),
        cap_source.get("STATUS"),
        cap_source.get("CAP"),
        cap_source.get("REPLAYED_HISTORICAL_SOLVER"),
    )
    require(
        expected_cap_source
        == (
            spec.historical_row_source,
            "HISTORICAL_CATALOG_LABEL_NOT_A_RESULT_POINTER",
            R30_RESULT_PATH,
            R30_RESULT_SHA256,
            f"GROUP_ATTEMPTS[{R30_ATTEMPT_INDEX}]",
            R30_PROOF_OBJECT_SHA256,
            "INFEASIBLE",
            spec.before_cap,
            False,
        ),
        "T238 cap source metadata differs from the pinned R30 attempt",
    )
    return {
        "RESULT_PATH": R30_RESULT_PATH,
        "RESULT_SHA256": sha256(r30_raw),
        "LOCATOR": locator,
        "PROOF_OBJECT_SHA256": attempt_sha,
        "PROFILE_IDS": attempt["PROFILE_IDS"],
        "STATUS": attempt["STATUS"],
        "CAP": attempt["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"],
        "SOLVER_REPLAYED": False,
    }


def verify_donor_artifact(
    root: Path, frozen_row: four.Row, spec: T238Spec
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    four.verify_commit(root, FROZEN_HEAD, FROZEN_TREE)
    four.verify_commit(root, spec.head, spec.tree)
    parent_line = cast(
        str,
        four.run_git(root, "rev-list", "--parents", "-n", "1", spec.head),
    ).split()
    require(parent_line == [spec.head, FROZEN_HEAD], "T238 donor parent is not Frozen HEAD")
    require(
        nineteen.row_details(frozen_row)
        == {
            "bound": spec.before_bound,
            "cap": spec.before_cap,
            "s4_base": spec.s4_base,
            "source": spec.historical_row_source,
        },
        "Frozen target row or historical Row.source mismatch",
    )
    paths = {
        "RESULT": spec.result_path,
        "SOURCE": spec.source_path,
        "TEST": spec.test_path,
    }
    blobs = {name: four.committed_blob(root, spec.head, path) for name, path in paths.items()}
    result_raw = blobs["RESULT"]
    nineteen.require_hash(result_raw, spec.result_sha256, "T238 donor result")
    record = json_object(result_raw, "T238 donor result is invalid JSON")
    validate_t238_claim(record, spec)
    require(
        record.get("FROZEN_HEAD") == FROZEN_HEAD
        and record.get("FROZEN_TREE") == FROZEN_TREE
        and record.get("FROZEN_HEAD_TREE") == "MATCH"
        and record.get("FROZEN_RESULT_SHA256") == FROZEN_RESULT_SHA256,
        "T238 donor Frozen identity mismatch",
    )
    cap_locator = f"{R30_RESULT_PATH}:GROUP_ATTEMPTS[{R30_ATTEMPT_INDEX}]"
    cap_source = verify_r30_cap_source(root, record, spec)
    proof_sha = nineteen.canonical_json_sha256(cast(dict[str, Any], record[spec.proof_fragment]))
    row_source = proof_source(spec, proof_sha)
    checked_proof_sha, _proof = verify_proof_locator(record, spec, row_source)
    require(checked_proof_sha == proof_sha, "T238 proof digest replay mismatch")
    identity = {
        "EVENT_ID": spec.event_id,
        "TASK_ID": spec.task_id,
        "HEAD": spec.head,
        "TREE": spec.tree,
        "PARENT": FROZEN_HEAD,
        "RESULT_PATH": spec.result_path,
        "RESULT_SHA256": sha256(result_raw),
        "SOURCE_PATH": spec.source_path,
        "SOURCE_SHA256": sha256(blobs["SOURCE"]),
        "TEST_PATH": spec.test_path,
        "TEST_SHA256": sha256(blobs["TEST"]),
        "PROFILE_ID": spec.profile_id,
        "BOUND_BEFORE": spec.before_bound,
        "CAP_BEFORE": spec.before_cap,
        "S4_BASE": spec.s4_base,
        "BOUND_AFTER": spec.after_bound,
        "CAP_AFTER": spec.after_cap,
        "OWNER_BOUND_DELTA": spec.after_bound - spec.before_bound,
        "PROOF_FRAGMENT": spec.proof_fragment,
        "PROOF_SHA256": checked_proof_sha,
        "PROOF_SCOPE": "FULL_PROFILE",
        "CAP_SOURCE_LOCATOR": cap_locator,
        "CAP_SOURCE": cap_source,
        "ROW_SOURCE_BEFORE": frozen_row.source,
        "ROW_SOURCE": row_source,
        "FRESH_CONTEXT_JUDGE": "VERIFIED",
        "JUDGE_SESSION_ID": T238_JUDGE_SESSION_ID,
    }
    return record, identity, blobs


def verify_final_family(frontier: Mapping[str, Any]) -> None:
    expected = {
        "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
        "TIED_OWNERS": [CURSOR_ID],
        "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
        "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNERS,
        "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
    }
    four.verify_family_summary(frontier, expected)


def expect_rejected(action: Any, message: str) -> str:
    try:
        action()
    except ValueError:
        return "PASS"
    raise ValueError(message)


def verify_negative_cases(
    donor_raw: bytes,
    donor_record: Mapping[str, Any],
    donor_identity: Mapping[str, Any],
    frozen: Mapping[str, four.Row],
    after: Mapping[str, four.Row],
    changed_from_frozen: set[str],
    family_after: Mapping[str, Any],
) -> dict[str, str]:
    wrong_profile = replace(T238, profile_id="0" * 20)
    wrong_cap = replace(T238, after_cap=T238.after_cap - 1)
    wrong_bound = replace(T238, after_bound=T238.after_bound + 1)
    unrelated = next(
        profile_id
        for profile_id in after
        if profile_id not in changed_from_frozen
    )
    changed_copy = dict(after)
    changed_copy[unrelated] = replace(changed_copy[unrelated], source="unrelated-mutation")
    missing_cursor = dict(family_after)
    missing_cursor.pop("CURSOR", None)
    incorrect_family_max = dict(family_after)
    incorrect_family_max["FAMILY_BOUND"] = EXPECTED_FAMILY_BOUND + 1
    locator = cast(str, donor_identity["ROW_SOURCE"])
    return {
        "WRONG_DONOR_SHA_REJECTED": expect_rejected(
            lambda: nineteen.require_hash(donor_raw, "0" * 64, "T238 donor result"),
            "wrong donor SHA was accepted",
        ),
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: validate_t238_claim(donor_record, wrong_profile),
            "wrong profile was accepted",
        ),
        "WRONG_CAP_REJECTED": expect_rejected(
            lambda: validate_t238_claim(donor_record, wrong_cap),
            "wrong cap was accepted",
        ),
        "WRONG_BOUND_REJECTED": expect_rejected(
            lambda: validate_t238_claim(donor_record, wrong_bound),
            "wrong bound was accepted",
        ),
        "WRONG_PROOF_LOCATOR_REJECTED": expect_rejected(
            lambda: verify_proof_locator(donor_record, T238, locator + "/wrong"),
            "wrong proof locator was accepted",
        ),
        "UNRELATED_ROW_MUTATION_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(frozen, changed_copy, changed_from_frozen),
            "unrelated row mutation was accepted",
        ),
        "CURSOR_OMISSION_REJECTED": expect_rejected(
            lambda: verify_final_family(missing_cursor),
            "cursor omission was accepted",
        ),
        "INCORRECT_FAMILY_MAX_REJECTED": expect_rejected(
            lambda: verify_final_family(incorrect_family_max),
            "incorrect family maximum was accepted",
        ),
    }


def verify_base_artifact() -> tuple[
    dict[str, Any], dict[str, four.Row], dict[str, four.Row], bytes
]:
    four.verify_commit(ROOT, FROZEN_HEAD, FROZEN_TREE)
    frozen_result_raw = four.committed_blob(ROOT, FROZEN_HEAD, FROZEN_RESULT_PATH)
    nineteen.require_hash(frozen_result_raw, FROZEN_RESULT_SHA256, "Frozen seven-row result")
    six_row_result_raw = four.committed_blob(ROOT, FROZEN_HEAD, SIX_ROW_RESULT_PATH)
    nineteen.require_hash(six_row_result_raw, SIX_ROW_RESULT_SHA256, "Frozen six-row result")
    require(
        (ROOT / FROZEN_RESULT_PATH).read_bytes() == frozen_result_raw
        and (ROOT / SIX_ROW_RESULT_PATH).read_bytes() == six_row_result_raw,
        "working Frozen result differs from pinned commit",
    )
    four.verify_commit(ROOT, BASE_HEAD, BASE_TREE)
    base_raw = four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    nineteen.require_hash(base_raw, BASE_RESULT_SHA256, "19-event base result")
    require((ROOT / BASE_RESULT_PATH).read_bytes() == base_raw, "working 19-event result differs")
    stored_base = json_object(base_raw, "19-event base result is invalid JSON")
    replay, frozen, after_nineteen = nineteen.build_candidate()
    require(
        replay == stored_base and nineteen.serialize_result(replay) == base_raw,
        "19-event result differs from complete replay",
    )
    require(
        replay["NEW_FULL_DIGEST"] == BASE_FULL_DIGEST
        and replay["NEW_BOUNDS_DIGEST"] == BASE_BOUNDS_DIGEST,
        "19-event full or bounds digest mismatch",
    )
    require(
        len(frozen) == EXPECTED_ROW_COUNT
        and len(after_nineteen) == EXPECTED_ROW_COUNT
        and replay["UPDATE_EVENTS"] == 19
        and replay["FAMILY_AFTER"]["FAMILY_BOUND"] == EXPECTED_FAMILY_BOUND,
        "19-event row count, history, or family bound mismatch",
    )
    return replay, frozen, after_nineteen, base_raw


def build_candidate() -> tuple[dict[str, Any], dict[str, four.Row], dict[str, four.Row]]:
    base, frozen, after_nineteen, base_raw = verify_base_artifact()
    frozen_row = frozen.get(T238.profile_id)
    require(frozen_row is not None, "Frozen ledger omitted T238 target row")
    target_frozen_row = cast(four.Row, frozen_row)
    require(
        after_nineteen.get(T238.profile_id) == target_frozen_row,
        "T238 target row changed in the 19-event base",
    )
    donor_record, donor_identity, donor_blobs = verify_donor_artifact(
        ROOT, target_frozen_row, T238
    )
    pin = nine.DonorPin(
        event_id=T238.event_id,
        task_id=T238.task_id,
        profile_id=T238.profile_id,
        previous_bound=T238.before_bound,
        previous_cap=T238.before_cap,
        bound=T238.after_bound,
        cap=T238.after_cap,
        s4_base=T238.s4_base,
        head=T238.head,
        tree=T238.tree,
        result_path=T238.result_path,
        result_sha256=T238.result_sha256,
        source_path=T238.source_path,
        source_sha256=donor_identity["SOURCE_SHA256"],
        test_path=T238.test_path,
        test_sha256=donor_identity["TEST_SHA256"],
        proof_sha256=donor_identity["PROOF_SHA256"],
    )
    before_family = four.family_frontier(after_nineteen)
    after_twenty, new_events = nine.apply_donor_events(
        after_nineteen, [pin], {T238.event_id: donor_identity}
    )
    require(len(new_events) == 1, "exactly one new T238 proof event is required")
    new_event = new_events[0]
    require(
        new_event.get("EVENT_ID") == T238.event_id
        and new_event.get("PROFILE_ID") == T238.profile_id
        and new_event.get("BOUND_BEFORE") == T238.before_bound
        and new_event.get("BOUND_AFTER") == T238.after_bound
        and new_event.get("CAP_BEFORE") == T238.before_cap
        and new_event.get("CAP_AFTER") == T238.after_cap
        and new_event.get("S4_BASE_BEFORE") == T238.s4_base
        and new_event.get("S4_BASE_AFTER") == T238.s4_base
        and new_event.get("SOURCE_AFTER") == donor_identity["ROW_SOURCE"],
        "T238 event transition or Row.source mismatch",
    )
    previous_events = cast(list[dict[str, Any]], base["EVENT_HISTORY"])
    events = previous_events + new_events
    sixteen.verify_unique_events(events)
    require(
        len(previous_events) == 19 and len(new_events) == 1 and len(events) == 20,
        "20-event history count mismatch",
    )
    changed_from_base = sixteen.verify_ledger_partition(
        after_nineteen, after_twenty, {T238.profile_id}
    )
    old_changed = {
        profile_id
        for profile_id in frozen
        if frozen[profile_id] != after_nineteen[profile_id]
    }
    require(
        len(old_changed) == base["DISTINCT_CHANGED_PROFILES"] == 18,
        "19-event changed-profile replay mismatch",
    )
    changed_from_frozen = sixteen.verify_ledger_partition(
        frozen, after_twenty, old_changed | {T238.profile_id}
    )
    require(
        len(changed_from_frozen) == 19
        and len(frozen) - len(changed_from_frozen) == 4_628
        and len(changed_from_base) == 1
        and len(after_nineteen) - len(changed_from_base) == 4_646,
        "20-event changed or unchanged row counts mismatch",
    )
    require(
        after_twenty[T238.profile_id].source == donor_identity["ROW_SOURCE"],
        "T238 Row.source metadata replay mismatch",
    )

    before_full = four.seven.two.full_digest(after_nineteen)
    before_bounds = four.seven.two.bounds_digest(after_nineteen)
    after_full = four.seven.two.full_digest(after_twenty)
    after_bounds = four.seven.two.bounds_digest(after_twenty)
    require(
        before_full == BASE_FULL_DIGEST and before_bounds == BASE_BOUNDS_DIGEST,
        "19-event digest changed before event 20",
    )
    bounds_projection = {
        profile_id: replace(row, source=frozen[profile_id].source)
        for profile_id, row in after_twenty.items()
    }
    require(
        four.seven.two.bounds_digest(bounds_projection) == after_bounds,
        "20-event bounds-only digest projection mismatch",
    )

    family_after = four.family_frontier(after_twenty)
    verify_final_family(family_after)
    require(
        before_family == base["FAMILY_AFTER"]
        and before_family["FAMILY_BOUND"] == EXPECTED_FAMILY_BOUND
        and before_family["FAMILY_BOUND"] - family_after["FAMILY_BOUND"] == 0,
        "Family maximum changed during T238 row integration",
    )
    resolved_above_incumbent = sum(row.bound > INCUMBENT for row in after_twenty.values())
    require(resolved_above_incumbent == 1_366, "resolved rows above incumbent mismatch")
    cursor = cast(dict[str, Any], base["CURSOR_AUTHORITY"])
    require(
        cursor.get("ID") == CURSOR_ID
        and cursor.get("BOUND") == CURSOR_BOUND
        and cursor.get("COUNT") == CURSOR_COUNT
        and family_after.get("CURSOR") == {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "unresolved cursor or its partition was not preserved",
    )
    require(
        base["NEW_WINNING_OUTCOMES"] == 0
        and base["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
        and donor_record["NEW_WINNING_OUTCOMES"] == 0,
        "winning outcome or global optimum status changed",
    )

    negative_validations = verify_negative_cases(
        donor_blobs["RESULT"],
        donor_record,
        donor_identity,
        frozen,
        after_twenty,
        changed_from_frozen,
        family_after,
    )
    require(
        set(negative_validations.values()) == {"PASS"},
        "a negative authority validation accepted a mutation",
    )
    transitions = cast(list[dict[str, Any]], base["EVENT_FAMILY_TRANSITIONS"])
    event_transitions = [
        *transitions,
        {
            "EVENT_ID": T238.event_id,
            "FAMILY_BOUND_BEFORE": before_family["FAMILY_BOUND"],
            "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
            "TIED_OWNERS_AFTER": family_after["TIED_OWNERS"],
            "NEXT_COMPETING_BOUND_AFTER": family_after["NEXT_COMPETING_BOUND"],
            "NEXT_COMPETING_OWNERS_AFTER": family_after["NEXT_COMPETING_OWNERS"],
        },
    ]
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_20_EVENT_CANDIDATE_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "BASE_19_HEAD_TREE": "MATCH",
            "BASE_19_RESULT_SHA256": "MATCH",
            "T238_DONOR_HEAD_TREE": "MATCH",
            "T238_RESULT_SHA256": "MATCH",
            "T238_JUDGE_IDENTITY": "MATCH",
            "ALL_PROOF_LOCATORS_RESOLVE": "YES",
        },
        "FROZEN_AUTHORITY": base["FROZEN_AUTHORITY"],
        "BASE_19_AUTHORITY": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "FULL_DIGEST": before_full,
            "BOUNDS_DIGEST": before_bounds,
            "EVENTS": len(previous_events),
            "REPLAY_MATCH": "YES",
        },
        "T238_DONOR_IDENTITY": donor_identity,
        "T238_HISTORICAL_ROW": nineteen.row_details(target_frozen_row),
        "T238_SOURCE_CAP_AUTHORITY": donor_identity["CAP_SOURCE"],
        "ROWS_BEFORE": len(frozen),
        "ROWS_AFTER": len(after_twenty),
        "OLD_EVENTS": len(previous_events),
        "NEW_EVENTS": len(new_events),
        "TOTAL_EVENTS": len(events),
        "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": len(changed_from_frozen),
        "CHANGED_PROFILE_IDS_FROM_FROZEN": sorted(changed_from_frozen),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed_from_frozen),
        "CHANGED_ROWS_FROM_19_EVENT": len(changed_from_base),
        "UNCHANGED_ROWS_FROM_19_EVENT": len(after_nineteen) - len(changed_from_base),
        "T238_NEW_CAP": T238.after_cap,
        "T238_NEW_BOUND": T238.after_bound,
        "OWNER_BOUND_DELTA": T238.after_bound - T238.before_bound,
        "SOURCE_METADATA_REPLAY": "MATCH",
        "FULL_DIGEST": after_full,
        "BOUNDS_DIGEST": after_bounds,
        "NEW_FULL_DIGEST": after_full,
        "NEW_BOUNDS_DIGEST": after_bounds,
        "LEDGER_OVERLAY": {
            "ROWS_BEFORE": len(frozen),
            "ROWS_AFTER": len(after_twenty),
            "FULL_DIGEST_BEFORE": before_full,
            "BOUNDS_DIGEST_BEFORE": before_bounds,
            "FULL_DIGEST_AFTER": after_full,
            "BOUNDS_DIGEST_AFTER": after_bounds,
            "FULL_DIGEST_IS_ROW_SOURCE_AWARE": "YES",
            "SOURCE_METADATA_BINDINGS": "VERIFIED",
            "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed_from_frozen),
            "UNCHANGED_ROWS_FROM_19_EVENT": len(after_nineteen) - len(changed_from_base),
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
        "NEXT_OWNER_IDS": family_after["NEXT_COMPETING_OWNERS"],
        "RESOLVED_ROWS_ABOVE_INCUMBENT": resolved_above_incumbent,
        "CURSOR_COUNT": cursor["COUNT"],
        "CURSOR_BOUND": cursor["BOUND"],
        "CURSOR_INCLUDED": "YES",
        "CURSOR_AUTHORITY": base["CURSOR_AUTHORITY"],
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "OLD_LEDGER_UNCHANGED": "YES",
        "FROZEN_LEDGER_MUTATED": "NO",
        "DONOR_WORKTREES_MUTATED": "NO",
        "NEGATIVE_VALIDATIONS": negative_validations,
        "FOCUSED_TEST_PATH": "tests/unit/test_b649_t238_twenty_event_local_authority_r1.py",
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    serialized = serialize_result(result)
    require(
        json_object(serialized, "20-event result serialization is invalid") == result,
        "20-event result JSON round trip mismatch",
    )
    return result, frozen, after_twenty


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    if path.exists():
        previous = json_object(path.read_bytes(), "existing result artifact is invalid JSON")
        require(previous.get("TASK_ID") == TASK_ID, "refusing to overwrite another result artifact")
    path.write_bytes(raw)
    require(path.read_bytes() == raw, "result read-after-write mismatch")
    return sha256(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result, _frozen, _after = build_candidate()
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
                "OLD_EVENTS": result["OLD_EVENTS"],
                "NEW_EVENTS": result["NEW_EVENTS"],
                "TOTAL_EVENTS": result["TOTAL_EVENTS"],
                "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": result[
                    "DISTINCT_CHANGED_PROFILES_FROM_FROZEN"
                ],
                "UNCHANGED_ROWS_FROM_FROZEN": result["UNCHANGED_ROWS_FROM_FROZEN"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
                "FAMILY_BOUND_BEFORE": result["FAMILY_BOUND_BEFORE"],
                "FAMILY_BOUND_AFTER": result["FAMILY_BOUND_AFTER"],
                "FAMILY_GAIN": result["FAMILY_GAIN"],
                "MAX_OWNER": result["MAX_OWNER"],
                "NEXT_DISTINCT_BOUND": result["NEXT_DISTINCT_BOUND"],
                "NEXT_OWNER_IDS": result["NEXT_OWNER_IDS"],
                "NEGATIVE_VALIDATIONS": result["NEGATIVE_VALIDATIONS"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
