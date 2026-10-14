"""Rebuild the 19-event B649 local Family Authority candidate."""

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
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen

TASK_ID = "B649_NINETEEN_EVENT_LOCAL_FAMILY_AUTHORITY_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-nineteen-event-local-family-authority-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
FROZEN_ROWS_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
FROZEN_ROWS_RESULT_SHA256 = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"

SIXTEEN_HEAD = "c0fb13d41d58c91cab578aae8afd0b62829a1069"
SIXTEEN_TREE = "0c3d5c794e5cd16446e51dedcb00662a1e922c16"
SIXTEEN_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-sixteen-event-frozen-lineage-local-authority-r1-result.json"
)
SIXTEEN_RESULT_SHA256 = "033e57180f50cc3f42d9122f3dcb3ef20a45b8cdd53616e09168ff2599b4fa3f"

CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
INCUMBENT = 313_263_888
EXPECTED_ROW_COUNT = 4_647
EXPECTED_BASE_FAMILY_BOUND = 313_395_060
EXPECTED_FAMILY_BOUND = 313_394_584
EXPECTED_NEXT_DISTINCT_BOUND = 313_392_516
EXPECTED_NEXT_OWNER = "65555555555541000000"

Row = four.Row


@dataclass(frozen=True)
class DonorSpec:
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
    source_sha256: str
    test_path: str
    test_sha256: str
    proof_fragment: str
    proof_sha256: str


DONORS: tuple[DonorSpec, ...] = (
    DonorSpec(
        event_id="T228_A187",
        task_id="B649_NEXT_MAX_OWNER_66655555555332000000_R1",
        profile_id="66655555555332000000",
        before_bound=313_395_060,
        before_cap=265,
        s4_base=112,
        after_bound=313_062_208,
        after_cap=228,
        head="03afee8eed0a35bb8977351bc90ab180b8fe7ec6",
        tree="6ff5e78d4794f3634cddf30c636ba4909c8a69e4",
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-next-max-owner-66655555555332000000-r1-result.json"
        ),
        result_sha256="3192f9fcd43e7e3b7abbb1fb2ba4f626448d9d8a4887a3dd4cabc1197194ec5d",
        source_path=("src/lottolab/research/b649_next_max_owner_66655555555332000000_r1.py"),
        source_sha256="6380b6613c43b21765c18ce1cf2f8c875543914312a03b0468c0792bb7794854",
        test_path=("tests/unit/test_b649_next_max_owner_66655555555332000000_r1.py"),
        test_sha256="583f7b7fe6bcfcb5cac9230acf8630c556a73f91e0301de0a1d72b9aa3e9e37d",
        proof_fragment="PROOF",
        proof_sha256="0cfcb47f527417ff32ffe291b4544926ad5dd66813fb2850b492d7c0d1fc5caf",
    ),
    DonorSpec(
        event_id="T248",
        task_id="B649_MIN_S2_OWNER_666555555554211_T248_FORMAL_CERT_R1",
        profile_id="66655555555421100000",
        before_bound=313_395_060,
        before_cap=265,
        s4_base=112,
        after_bound=313_242_512,
        after_cap=248,
        head="88eb7bccd1269a4b420fef18d2d06bd3eacbf90e",
        tree="c9a91a46d4c784058e3c94aee3b863705a4c6f97",
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-min-s2-owner-666555555554211-t248-formal-cert-r1-result.json"
        ),
        result_sha256="a59cd61711f54f15c02d265fffcbeeee4c81bcd957ab3e7aa27b146b55345a0d",
        source_path=(
            "src/lottolab/research/b649_min_s2_owner_666555555554211_t248_formal_cert_r1.py"
        ),
        source_sha256="6424358c00452231065da13765308e2cc1637dc274adf0c22eee277263dbb462",
        test_path=("tests/unit/test_b649_min_s2_owner_666555555554211_t248_formal_cert_r1.py"),
        test_sha256="fc64229c8553fa825f4b6b5b025ef7ec76103db79011f7265ed1a4afd681d251",
        proof_fragment="PROOF",
        proof_sha256="2770fcfd2a3ad4cef9a9eba8ca64adb6e3ae17e859eb54d9629d0198674cb4ca",
    ),
    DonorSpec(
        event_id="T255_NEW_OWNER",
        task_id="B649_NEXT_FRONTIER_66555555555431100000_R1",
        profile_id="66555555555431100000",
        before_bound=313_394_776,
        before_cap=266,
        s4_base=112,
        after_bound=313_296_388,
        after_cap=255,
        head="625f22e31abc6d8c150f806480cbda66d78aafb1",
        tree="727214fde35f21b4d696bfe0570a6c03d2905c91",
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-next-frontier-66555555555431100000-r1-result.json"
        ),
        result_sha256="08d7d0f990578243f88e21a39f960a5fbac553ac87d56734c4fb84d12b5686a7",
        source_path=("src/lottolab/research/b649_next_frontier_66555555555431100000_r1.py"),
        source_sha256="832cb64d7e1cde0c18783f1d2d7f282797ce136fdba1f5bfab1c8ca004f568c7",
        test_path=("tests/unit/test_b649_next_frontier_66555555555431100000_r1.py"),
        test_sha256="146433c21aed83196519f4211edf607016cea993b6e56f9d7152446b92c15e0b",
        proof_fragment="ANALYTIC_CERTIFICATE",
        proof_sha256="c009ff736a876766940485bf2aa2aafd140b0b250d3910b792501e70c08b782f",
    ),
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


def require_hash(raw: bytes, expected: str, label: str) -> None:
    require(sha256(raw) == expected, f"{label} SHA256 mismatch")


def canonical_json_sha256(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode())


def evidence_sha256(record: Mapping[str, Any], fragment: str) -> str:
    value = record.get(fragment)
    if fragment == "ANALYTIC_CERTIFICATE":
        require(type(value) is dict, "analytic certificate fragment is missing")
        return canonical_json_sha256(cast(dict[str, Any], value))
    if type(value) is not str:
        raise ValueError("proof fragment is missing")
    require(bool(value.strip()), "proof fragment is empty")
    return sha256(value.encode())


def proof_source(spec: DonorSpec) -> str:
    return (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}"
        f"#{spec.proof_fragment}:sha256={spec.proof_sha256}"
    )


def verify_proof_locator(record: Mapping[str, Any], spec: DonorSpec, locator: str) -> None:
    require(
        evidence_sha256(record, spec.proof_fragment) == spec.proof_sha256,
        f"proof fragment SHA256 mismatch: {spec.event_id}",
    )
    require(locator == proof_source(spec), f"proof locator mismatch: {spec.event_id}")


def validate_donor_claim(record: Mapping[str, Any], spec: DonorSpec) -> None:
    if spec.event_id == "T228_A187":
        actual = (
            record.get("PROFILE_ID"),
            record.get("SOURCE_OLD_BOUND"),
            record.get("SOURCE_T_CAP"),
            record.get("SOURCE_S4_BASE"),
            record.get("PROVED_T_CAP"),
            record.get("NEW_ADMISSIBLE_BOUND"),
        )
    elif spec.event_id == "T248":
        before_rows = record.get("RESOLVED_ROW_BOUNDS_BEFORE")
        before_bound = (
            cast(Mapping[str, Any], before_rows).get(spec.profile_id)
            if type(before_rows) is dict
            else None
        )
        actual = (
            record.get("TARGET_PROFILE"),
            before_bound,
            record.get("CURRENT_T_CAP"),
            record.get("CURRENT_S4_FLOOR"),
            record.get("NEW_PROVEN_T_CAP"),
            record.get("FULL_PROFILE_BOUND"),
        )
    else:
        actual = (
            record.get("PROFILE_ID"),
            record.get("SOURCE_OLD_BOUND"),
            record.get("SOURCE_T_CAP"),
            record.get("SOURCE_S4_BASE"),
            record.get("PROVED_T_CAP"),
            record.get("NEW_ADMISSIBLE_BOUND"),
        )
    expected = (
        spec.profile_id,
        spec.before_bound,
        spec.before_cap,
        spec.s4_base,
        spec.after_cap,
        spec.after_bound,
    )
    require(actual == expected, f"donor profile, cap, or bound mismatch: {spec.event_id}")


def verify_frozen_rows_source(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    four.verify_commit(root, FROZEN_HEAD, FROZEN_TREE)
    raw = four.committed_blob(root, FROZEN_HEAD, FROZEN_ROWS_RESULT_PATH)
    require_hash(raw, FROZEN_ROWS_RESULT_SHA256, "Frozen full-row source")
    require(
        (root / FROZEN_ROWS_RESULT_PATH).read_bytes() == raw,
        "working Frozen full-row source differs from the pinned tree",
    )
    source = json_object(raw, "Frozen full-row source is invalid JSON")
    bounds = source.get("RESOLVED_ROW_BOUNDS")
    require(
        type(bounds) is dict and len(cast(dict[str, Any], bounds)) == EXPECTED_ROW_COUNT,
        "Frozen full-row source does not contain 4,647 row bounds",
    )
    bound_map = cast(dict[str, Any], bounds)
    for spec in DONORS:
        require(
            bound_map.get(spec.profile_id) == spec.before_bound,
            f"Frozen full-row bound mismatch: {spec.profile_id}",
        )
    partition = source.get("CURSOR_PARTITION_AUTHORITY")
    require(type(partition) is dict, "Frozen cursor partition metadata is missing")
    cursor_partition_raw = cast(dict[str, Any], partition).get(
        "UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"
    )
    if type(cursor_partition_raw) is not dict:
        raise ValueError("Frozen cursor partition is missing")
    cursor_partition = cast(dict[str, Any], cursor_partition_raw)
    require(
        cursor_partition.get("COUNT") == 197 and cursor_partition.get("W_RANGE") == [774, 785],
        "Frozen cursor partition count or W range mismatch",
    )
    cursor = source.get("CURSOR")
    require(
        type(cursor) is dict
        and cursor.get("ID") == CURSOR_ID
        and cursor.get("BOUND") == CURSOR_BOUND,
        "Frozen cursor identity mismatch",
    )
    return source, {
        "RESULT_PATH": FROZEN_ROWS_RESULT_PATH,
        "RESULT_SHA256": sha256(raw),
        "ROWS": len(bound_map),
        "CURSOR_ID": CURSOR_ID,
        "CURSOR_BOUND": CURSOR_BOUND,
        "CURSOR_COUNT": cursor_partition["COUNT"],
        "CURSOR_W_RANGE": cursor_partition["W_RANGE"],
    }


def row_details(row: Row) -> dict[str, Any]:
    return {
        "bound": row.bound,
        "cap": row.cap,
        "s4_base": row.s4_base,
        "source": row.source,
    }


def verify_donor_artifact(
    root: Path, spec: DonorSpec, frozen_row: Row
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    require(
        row_details(frozen_row)
        == {
            "bound": spec.before_bound,
            "cap": spec.before_cap,
            "s4_base": spec.s4_base,
            "source": frozen_row.source,
        }
        and type(frozen_row.source) is str
        and bool(frozen_row.source),
        f"Frozen cap, S4 base, or Row.source mismatch: {spec.profile_id}",
    )
    spec_paths = {
        "RESULT": (spec.result_path, spec.result_sha256),
        "SOURCE": (spec.source_path, spec.source_sha256),
        "TEST": (spec.test_path, spec.test_sha256),
    }
    blobs: dict[str, bytes] = {}
    for key, (path, expected_sha) in spec_paths.items():
        raw = four.committed_blob(root, spec.head, path)
        require_hash(raw, expected_sha, f"{spec.event_id} {key.lower()}")
        blobs[key] = raw
    record = json_object(blobs["RESULT"], f"{spec.event_id} result is invalid JSON")
    require(record.get("TASK_ID") == spec.task_id, f"donor task ID mismatch: {spec.event_id}")
    validate_donor_claim(record, spec)

    if spec.event_id == "T228_A187":
        require(
            record.get("FROZEN_HEAD") == FROZEN_HEAD
            and record.get("FROZEN_TREE") == FROZEN_TREE
            and record.get("FROZEN_RESULT_SHA256") == FROZEN_RESULT_SHA256
            and record.get("FROZEN_RESULT_SHA256_STATUS") == "MATCH",
            "T228 Frozen identity mismatch",
        )
        require(
            "at most 187 contained-triple K4s" in cast(str, record.get("PROOF")),
            "T228 contained-triple K4 cap is missing",
        )
        route = record.get("ROUTE_B")
        require(type(route) is dict, "T228 Route-B proof is missing")
        route_map = cast(dict[str, Any], route)
        terms = route_map.get("ALL_ADMISSIBLE_T_TERMS")
        require(
            route_map.get("ADMISSIBLE_T_RANGE") == [22, 228]
            and type(terms) is list
            and len(cast(list[Any], terms)) == 207
            and cast(list[Any], terms)[-1][1] == spec.after_bound
            and record.get("ROUTE_B_INTEGER_RECOUNT") == "PASS_ALL_T",
            "T228 admissible-bound recount mismatch",
        )
        source_row = record.get("SOURCE_ROW")
        require(type(source_row) is dict, "T228 Frozen row evidence is missing")
        source_row_map = cast(dict[str, Any], source_row)
        replay_row = source_row_map.get("FROZEN_LINEAGE_TARGET_REPLAY")
        replay_row_details = (
            {
                key: cast(dict[str, Any], replay_row).get(key)
                for key in ("bound", "cap", "s4_base", "source")
            }
            if type(replay_row) is dict
            else None
        )
        require(
            replay_row_details == row_details(frozen_row),
            "T228 source row differs from the Frozen loader",
        )
        require(
            source_row_map.get("BOUND") == frozen_row.bound
            and source_row_map.get("TRIANGLE_CAP") == frozen_row.cap
            and source_row_map.get("S4_BASE") == frozen_row.s4_base,
            "T228 source row summary differs from the Frozen loader",
        )
    elif spec.event_id == "T248":
        require(
            cast(dict[str, Any], record["RESOLVED_ROW_BOUNDS_AFTER"]).get(spec.profile_id)
            == spec.after_bound,
            "T248 after-bound row map mismatch",
        )
        proof = record.get("PROOF")
        if type(proof) is not str:
            raise ValueError("T248 full-profile proof is missing")
        require(
            proof.startswith(f"Universal T<=248 certificate for exactly {spec.profile_id}."),
            "T248 full-profile proof identity mismatch",
        )
        require(
            record.get("R14_HISTORICAL_DISPOSITION")
            == "R14_NOT_VERIFIED_SHARED_REFS_CHANGED_DURING_PARALLEL_ACTIVITY",
            "T248 R14 shared-reference caveat changed",
        )
        require(
            record.get("SOURCE_SHA256") == spec.source_sha256
            and record.get("TEST_SHA256") == spec.test_sha256,
            "T248 source or test identity mismatch",
        )
    else:
        certificate = record.get("ANALYTIC_CERTIFICATE")
        require(type(certificate) is dict, "T255 analytic certificate is missing")
        certificate_map = cast(dict[str, Any], certificate)
        require(
            certificate_map.get("PROFILE_ID") == spec.profile_id
            and certificate_map.get("CAP") == spec.after_cap
            and certificate_map.get("PROOF_SCOPE") == "FULL_PROFILE"
            and certificate_map.get("ATTAINMENT") == "NOT_ASSERTED",
            "T255 analytic certificate identity mismatch",
        )
        require(
            record.get("FROZEN_HEAD_TREE") == "MATCH"
            and record.get("FROZEN_RESULT_SHA256") == "MATCH"
            and record.get("JUDGE_MODE") == "SELF_CHECK_ONLY"
            and record.get("RESEARCH_SOURCE_SHA256") == spec.source_sha256
            and record.get("FOCUSED_TEST_SOURCE_SHA256") == spec.test_sha256,
            "T255 source or review status mismatch",
        )
        authority = record.get("AUTHORITY")
        require(type(authority) is dict, "T255 Frozen authority is missing")
        authority_map = cast(dict[str, Any], authority)
        require(
            authority_map.get("FROZEN_HEAD") == FROZEN_HEAD
            and authority_map.get("FROZEN_TREE") == FROZEN_TREE
            and authority_map.get("FROZEN_RESULT_SHA256") == FROZEN_RESULT_SHA256
            and authority_map.get("FROZEN_ROW")
            == {
                "BOUND": frozen_row.bound,
                "CAP": frozen_row.cap,
                "S4_BASE": frozen_row.s4_base,
                "SOURCE": frozen_row.source,
            },
            "T255 source row differs from the Frozen loader",
        )
        falsifiability = record.get("FALSIFIABILITY_CHECK")
        require(
            type(falsifiability) is dict
            and cast(dict[str, Any], falsifiability).get("STATUS") == "CONFIRMED",
            "T255 certificate falsifiability record is missing",
        )

    locator = proof_source(spec)
    verify_proof_locator(record, spec, locator)
    identity = {
        "EVENT_ID": spec.event_id,
        "TASK_ID": spec.task_id,
        "HEAD": spec.head,
        "TREE": spec.tree,
        "RESULT_PATH": spec.result_path,
        "RESULT_SHA256": sha256(blobs["RESULT"]),
        "SOURCE_PATH": spec.source_path,
        "SOURCE_SHA256": sha256(blobs["SOURCE"]),
        "TEST_PATH": spec.test_path,
        "TEST_SHA256": sha256(blobs["TEST"]),
        "PROOF_FRAGMENT": spec.proof_fragment,
        "PROOF_SHA256": evidence_sha256(record, spec.proof_fragment),
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROFILE_ID": spec.profile_id,
        "BOUND_BEFORE": frozen_row.bound,
        "CAP_BEFORE": frozen_row.cap,
        "S4_BASE": frozen_row.s4_base,
        "BOUND_AFTER": spec.after_bound,
        "CAP_AFTER": spec.after_cap,
        "ROW_SOURCE_BEFORE": frozen_row.source,
        "ROW_SOURCE": locator,
    }
    if spec.event_id == "T248":
        identity["R14_HISTORICAL_DISPOSITION"] = record["R14_HISTORICAL_DISPOSITION"]
        identity["R2_HEAD"] = record["R2_HEAD"]
        identity["R2_TREE"] = record["R2_TREE"]
        identity["R2_RESULT_SHA256"] = record["R2_RESULT_SHA256"]
        identity["R2_SOURCE_STATUS_VERBATIM"] = record["R2_SOURCE_STATUS_VERBATIM"]
    if spec.event_id == "T255_NEW_OWNER":
        identity["DONOR_JUDGE_MODE"] = record["JUDGE_MODE"]
        identity["AUTHORITY_STATUS_UPGRADED"] = cast(dict[str, Any], record["AUTHORITY"])[
            "AUTHORITY_STATUS_UPGRADED"
        ]
    return record, identity, blobs


def verify_final_family(frontier: Mapping[str, Any]) -> None:
    expected = {
        "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
        "TIED_OWNERS": [CURSOR_ID],
        "NEXT_COMPETING_BOUND": EXPECTED_NEXT_DISTINCT_BOUND,
        "NEXT_COMPETING_OWNERS": [EXPECTED_NEXT_OWNER],
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
    records: Mapping[str, Mapping[str, Any]],
    blobs: Mapping[str, Mapping[str, bytes]],
    identities: Mapping[str, Mapping[str, Any]],
    frozen: Mapping[str, Row],
    after_sixteen: Mapping[str, Row],
    after: Mapping[str, Row],
    changed_from_frozen: set[str],
    final_family: Mapping[str, Any],
) -> dict[str, str]:
    first = DONORS[0]
    first_record = records[first.event_id]
    first_blobs = blobs[first.event_id]
    wrong_profile = replace(first, profile_id="0" * 20)
    wrong_cap = replace(first, after_cap=first.after_cap - 1)
    wrong_bound = replace(first, after_bound=first.after_bound + 1)
    unrelated = next(profile_id for profile_id in after if profile_id not in changed_from_frozen)
    changed_copy = dict(after)
    changed_copy[unrelated] = replace(changed_copy[unrelated], source="unrelated-mutation")
    missing_cursor = dict(final_family)
    missing_cursor.pop("CURSOR", None)
    return {
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: validate_donor_claim(first_record, wrong_profile),
            "wrong profile was accepted",
        ),
        "WRONG_SOURCE_SHA_REJECTED": expect_rejected(
            lambda: require_hash(first_blobs["SOURCE"], "0" * 64, "donor source"),
            "wrong source SHA was accepted",
        ),
        "WRONG_CAP_REJECTED": expect_rejected(
            lambda: validate_donor_claim(first_record, wrong_cap),
            "wrong cap was accepted",
        ),
        "WRONG_BOUND_REJECTED": expect_rejected(
            lambda: validate_donor_claim(first_record, wrong_bound),
            "wrong bound was accepted",
        ),
        "WRONG_PROOF_LOCATOR_REJECTED": expect_rejected(
            lambda: verify_proof_locator(
                first_record,
                first,
                cast(str, identities[first.event_id]["ROW_SOURCE"]).replace(
                    "#PROOF:", "#WRONG_PROOF:"
                ),
            ),
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
    }


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    frozen_source, cursor_identity = verify_frozen_rows_source(ROOT)
    previous, frozen, after_sixteen = sixteen.build_candidate()
    base_blob = four.committed_blob(ROOT, SIXTEEN_HEAD, SIXTEEN_RESULT_PATH)
    require_hash(base_blob, SIXTEEN_RESULT_SHA256, "16-event base result")
    stored_base = json_object(base_blob, "16-event base result is invalid JSON")
    require(
        (ROOT / SIXTEEN_RESULT_PATH).read_bytes() == base_blob
        and sixteen.serialize_result(previous) == base_blob
        and previous == stored_base,
        "16-event base result differs from exact replay",
    )
    require(
        previous.get("FROZEN_AUTHORITY", {}).get("HEAD") == FROZEN_HEAD
        and previous.get("FROZEN_AUTHORITY", {}).get("TREE") == FROZEN_TREE
        and previous.get("FROZEN_AUTHORITY", {}).get("RESULT_SHA256") == FROZEN_RESULT_SHA256,
        "16-event Frozen authority identity mismatch",
    )
    require(
        previous.get("UPDATE_EVENTS") == 16
        and previous.get("DISTINCT_CHANGED_PROFILES") == 15
        and previous.get("FAMILY_AFTER", {}).get("FAMILY_BOUND") == EXPECTED_BASE_FAMILY_BOUND,
        "16-event base count or Family maximum mismatch",
    )
    require(
        len(frozen) == EXPECTED_ROW_COUNT
        and len(after_sixteen) == EXPECTED_ROW_COUNT
        and four.seven.two.full_digest(after_sixteen) == previous["NEW_FULL_DIGEST"]
        and four.seven.two.bounds_digest(after_sixteen) == previous["NEW_BOUNDS_DIGEST"],
        "16-event full-row replay digest mismatch",
    )
    frozen_bounds = cast(dict[str, Any], frozen_source["RESOLVED_ROW_BOUNDS"])
    frozen_rows: dict[str, Row] = {}
    for spec in DONORS:
        row = frozen.get(spec.profile_id)
        require(row is not None, f"Frozen loader omitted target row: {spec.profile_id}")
        actual = cast(Row, row)
        require(
            frozen_bounds.get(spec.profile_id) == spec.before_bound
            and row_details(actual)
            == {
                "bound": spec.before_bound,
                "cap": spec.before_cap,
                "s4_base": spec.s4_base,
                "source": actual.source,
            }
            and type(actual.source) is str
            and bool(actual.source),
            f"Frozen target row identity mismatch: {spec.profile_id}",
        )
        require(
            after_sixteen[spec.profile_id] == actual,
            f"target row changed in the 16-event base: {spec.profile_id}",
        )
        frozen_rows[spec.profile_id] = actual

    records: dict[str, dict[str, Any]] = {}
    identities: dict[str, dict[str, Any]] = {}
    blobs: dict[str, dict[str, bytes]] = {}
    pins: list[nine.DonorPin] = []
    for spec in DONORS:
        record, identity, donor_blobs = verify_donor_artifact(
            ROOT, spec, frozen_rows[spec.profile_id]
        )
        records[spec.event_id] = record
        identities[spec.event_id] = identity
        blobs[spec.event_id] = donor_blobs
        pins.append(
            nine.DonorPin(
                event_id=spec.event_id,
                task_id=spec.task_id,
                profile_id=spec.profile_id,
                previous_bound=spec.before_bound,
                previous_cap=spec.before_cap,
                bound=spec.after_bound,
                cap=spec.after_cap,
                s4_base=spec.s4_base,
                head=spec.head,
                tree=spec.tree,
                result_path=spec.result_path,
                result_sha256=spec.result_sha256,
                source_path=spec.source_path,
                source_sha256=spec.source_sha256,
                test_path=spec.test_path,
                test_sha256=spec.test_sha256,
                proof_sha256=spec.proof_sha256,
            )
        )

    state = dict(after_sixteen)
    new_events: list[dict[str, Any]] = []
    event_family_transitions: list[dict[str, Any]] = []
    for spec, pin in zip(DONORS, pins, strict=True):
        before_family = four.family_frontier(state)
        state, events = nine.apply_donor_events(
            state, [pin], {spec.event_id: identities[spec.event_id]}
        )
        require(len(events) == 1, f"one row event expected: {spec.event_id}")
        event = events[0]
        require(
            event.get("EVENT_ID") == spec.event_id
            and event.get("PROFILE_ID") == spec.profile_id
            and event.get("BOUND_BEFORE") == spec.before_bound
            and event.get("BOUND_AFTER") == spec.after_bound
            and event.get("CAP_BEFORE") == spec.before_cap
            and event.get("CAP_AFTER") == spec.after_cap
            and event.get("S4_BASE_BEFORE") == spec.s4_base
            and event.get("S4_BASE_AFTER") == spec.s4_base
            and event.get("SOURCE_AFTER") == identities[spec.event_id]["ROW_SOURCE"],
            f"row event transition mismatch: {spec.event_id}",
        )
        new_events.append(event)
        after_family = four.family_frontier(state)
        event_family_transitions.append(
            {
                "EVENT_ID": spec.event_id,
                "FAMILY_BOUND_BEFORE": before_family["FAMILY_BOUND"],
                "FAMILY_BOUND_AFTER": after_family["FAMILY_BOUND"],
                "TIED_OWNERS_AFTER": after_family["TIED_OWNERS"],
                "NEXT_COMPETING_BOUND_AFTER": after_family["NEXT_COMPETING_BOUND"],
            }
        )

    previous_events = cast(list[dict[str, Any]], previous["EVENT_HISTORY"])
    events = previous_events + new_events
    sixteen.verify_unique_events(events)
    require(
        len(previous_events) == 16 and len(new_events) == 3 and len(events) == 19,
        "19-event history count mismatch",
    )
    old_changed = set(previous["LEDGER_OVERLAY"]["DISTINCT_CHANGED_PROFILES"])
    new_profiles = {spec.profile_id for spec in DONORS}
    require(not old_changed.intersection(new_profiles), "new donor profile already changed")
    expected_changed = old_changed | new_profiles
    changed = sixteen.verify_ledger_partition(frozen, state, expected_changed)
    changed_from_sixteen = sixteen.verify_ledger_partition(after_sixteen, state, new_profiles)
    require(
        len(changed) == 18
        and len(changed_from_sixteen) == 3
        and len(frozen) - len(changed) == 4_629
        and len(after_sixteen) - len(changed_from_sixteen) == 4_644,
        "changed or unchanged row counts mismatch",
    )
    require(
        all(
            state[spec.profile_id].source == identities[spec.event_id]["ROW_SOURCE"]
            for spec in DONORS
        ),
        "new Row.source metadata binding mismatch",
    )

    before_full = four.seven.two.full_digest(after_sixteen)
    before_bounds = four.seven.two.bounds_digest(after_sixteen)
    after_full = four.seven.two.full_digest(state)
    after_bounds = four.seven.two.bounds_digest(state)
    require(
        before_full == previous["NEW_FULL_DIGEST"]
        and before_bounds == previous["NEW_BOUNDS_DIGEST"],
        "16-event digest changed before event 17",
    )
    bounds_projection = {
        profile_id: replace(row, source=frozen[profile_id].source)
        for profile_id, row in state.items()
    }
    projected_bounds = four.seven.two.bounds_digest(bounds_projection)
    require(projected_bounds == after_bounds, "bounds-only digest projection mismatch")

    family_before = four.family_frontier(frozen)
    family_sixteen = four.family_frontier(after_sixteen)
    family_after = four.family_frontier(state)
    require(
        family_sixteen == previous["FAMILY_AFTER"]
        and family_sixteen["FAMILY_BOUND"] == EXPECTED_BASE_FAMILY_BOUND,
        "16-event family replay differs from its stored result",
    )
    verify_final_family(family_after)
    require(
        event_family_transitions[0]["FAMILY_BOUND_AFTER"] == 313_395_060
        and event_family_transitions[1]["FAMILY_BOUND_AFTER"] == 313_394_776
        and event_family_transitions[2]["FAMILY_BOUND_AFTER"] == EXPECTED_FAMILY_BOUND,
        "event family transitions mismatch",
    )
    resolved_above_incumbent = sum(row.bound > INCUMBENT for row in state.values())
    require(resolved_above_incumbent == 1_367, "resolved rows above incumbent mismatch")
    base_cursor = previous.get("UNRESOLVED_CURSOR")
    require(
        type(base_cursor) is dict
        and base_cursor.get("ID") == CURSOR_ID
        and base_cursor.get("BOUND") == CURSOR_BOUND
        and base_cursor.get("PROFILE_COUNT") == cursor_identity["CURSOR_COUNT"]
        and cursor_identity["CURSOR_W_RANGE"] == [774, 785]
        and family_after.get("CURSOR") == {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "unresolved cursor or partition was not preserved",
    )

    negative_validations = verify_negative_cases(
        records,
        blobs,
        identities,
        frozen,
        after_sixteen,
        state,
        changed,
        family_after,
    )
    require(
        set(negative_validations.values()) == {"PASS"},
        "a negative authority validation did not reject its mutation",
    )

    caveats = dict(previous["CAVEATS"])
    historical_caveats = previous["HISTORICAL_AUTHORITY_CAVEATS"]
    t248_record = records["T248"]
    t255_record = records["T255_NEW_OWNER"]
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_19_EVENT_CANDIDATE_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "SIXTEEN_EVENT_HEAD_TREE": "MATCH",
            "SIXTEEN_EVENT_RESULT_SHA256": "MATCH",
            "T228_DONOR_IDENTITY": "MATCH",
            "T248_SEALED_DONOR_IDENTITY": "MATCH",
            "T255_DONOR_IDENTITY": "MATCH",
            "T248_FROZEN_ROW_EXISTS": "YES",
            "T248_FROZEN_ROW_BOUND": frozen_rows[DONORS[1].profile_id].bound,
            "T248_FROZEN_CAP_AND_SOURCE": "VERIFIED",
            "ALL_NEW_PROOF_LOCATORS_RESOLVE": "YES",
        },
        "FROZEN_AUTHORITY": previous["FROZEN_AUTHORITY"],
        "FROZEN_FULL_ROWS_SOURCE": cursor_identity,
        "FROZEN_TARGET_ROWS": {
            spec.profile_id: row_details(frozen_rows[spec.profile_id]) for spec in DONORS
        },
        "SIXTEEN_EVENT_AUTHORITY": {
            "HEAD": SIXTEEN_HEAD,
            "TREE": SIXTEEN_TREE,
            "RESULT_PATH": SIXTEEN_RESULT_PATH,
            "RESULT_SHA256": sha256(base_blob),
            "RESULT_REPLAY_MATCH": "YES",
            "UPDATE_EVENTS": previous["UPDATE_EVENTS"],
            "DISTINCT_CHANGED_PROFILES": previous["DISTINCT_CHANGED_PROFILES"],
            "NEW_FULL_DIGEST": previous["NEW_FULL_DIGEST"],
            "NEW_BOUNDS_DIGEST": previous["NEW_BOUNDS_DIGEST"],
            "FAMILY_BOUND": family_sixteen["FAMILY_BOUND"],
        },
        "NEW_DONOR_IDENTITIES": identities,
        "NEW_DONOR_REVIEW_CAVEATS": {
            "T228_A187_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
            "T228_A187_RESULT_JUDGE_MODE": records["T228_A187"].get("JUDGE_MODE"),
            "T248_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
            "T248_R14_HISTORICAL_DISPOSITION": t248_record["R14_HISTORICAL_DISPOSITION"],
            "T248_R14_SHARED_REFERENCES": "NOT_VERIFIED",
            "T248_SOURCE_STATUS_VERBATIM": t248_record["R2_SOURCE_STATUS_VERBATIM"],
            "T255_NEW_OWNER_SCIENTIFIC_REVIEW": t255_record["JUDGE_MODE"],
            "T255_NEW_OWNER_AUTHORITY_STATUS_UPGRADED": cast(
                dict[str, Any], t255_record["AUTHORITY"]
            )["AUTHORITY_STATUS_UPGRADED"],
        },
        "UPDATE_EVENTS": len(events),
        "PREVIOUS_EVENTS": len(previous_events),
        "NEW_EVENTS": len(new_events),
        "DISTINCT_CHANGED_PROFILES": len(changed),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed),
        "UNCHANGED_ROWS_FROM_SIXTEEN_EVENT": len(after_sixteen) - len(changed_from_sixteen),
        "EVENT_HISTORY": events,
        "EVENT_FAMILY_TRANSITIONS": event_family_transitions,
        "LEDGER_OVERLAY": {
            "ROWS_BEFORE": len(frozen),
            "ROWS_AFTER": len(state),
            "FULL_DIGEST_BEFORE": before_full,
            "BOUNDS_DIGEST_BEFORE": before_bounds,
            "FULL_DIGEST_AFTER": after_full,
            "BOUNDS_DIGEST_AFTER": after_bounds,
            "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST": projected_bounds,
            "FULL_DIGEST_IS_ROW_SOURCE_AWARE": "YES",
            "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed),
            "UNCHANGED_ROWS_FROM_SIXTEEN_EVENT": len(after_sixteen) - len(changed_from_sixteen),
            "UNRELATED_ROW_MUTATION": "NONE",
            "SOURCE_METADATA_BINDINGS": "VERIFIED",
        },
        "ROW_SOURCE_METADATA_VERIFIED": "YES",
        "INDEPENDENT_RESULT_REPLAY_MATCH": "YES",
        "OLD_LEDGER_UNCHANGED": "YES",
        "FROZEN_LEDGER_MUTATED": "NO",
        "DONOR_WORKTREES_MUTATED": "NO",
        "CURSOR_PRESERVED": "YES",
        "CURSOR_AUTHORITY": {
            "ID": CURSOR_ID,
            "BOUND": CURSOR_BOUND,
            "COUNT": cursor_identity["CURSOR_COUNT"],
            "W_RANGE": cursor_identity["CURSOR_W_RANGE"],
            "INCLUDED_IN_FAMILY_FRONTIER": "YES",
        },
        "NEW_FULL_DIGEST": after_full,
        "NEW_BOUNDS_DIGEST": after_bounds,
        "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST": projected_bounds,
        "FAMILY_BEFORE": family_before,
        "FAMILY_AFTER_SIXTEEN_EVENT": family_sixteen,
        "FAMILY_AFTER": family_after,
        "MAX_OWNER_TYPE": "UNRESOLVED_CURSOR",
        "NEXT_DISTINCT_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_RESOLVED_OWNER": family_after["NEXT_COMPETING_OWNERS"],
        "FAMILY_DELTA_FROM_SIXTEEN_EVENT": (
            family_sixteen["FAMILY_BOUND"] - family_after["FAMILY_BOUND"]
        ),
        "FAMILY_DELTA_FROM_FROZEN": (family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"]),
        "RESOLVED_ROWS_ABOVE_INCUMBENT": resolved_above_incumbent,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CAVEATS": caveats,
        "HISTORICAL_AUTHORITY_CAVEATS": historical_caveats,
        "PR378_CI": previous["PR378_CI"],
        "NEGATIVE_VALIDATIONS": negative_validations,
        "FOCUSED_TEST_PATH": ("tests/unit/test_b649_nineteen_event_local_family_authority_r1.py"),
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER": "NOT_RUN",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    serialized = serialize_result(result)
    require(
        json_object(serialized, "19-event result serialization is invalid") == result,
        "19-event result JSON round trip mismatch",
    )
    return result, frozen, state


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    if path.exists():
        previous = json_object(path.read_bytes(), "existing result artifact is invalid JSON")
        require(
            previous.get("TASK_ID") == TASK_ID,
            "refusing to overwrite another result artifact",
        )
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
                "UPDATE_EVENTS": result["UPDATE_EVENTS"],
                "DISTINCT_CHANGED_PROFILES": result["DISTINCT_CHANGED_PROFILES"],
                "NEW_FULL_DIGEST": result["NEW_FULL_DIGEST"],
                "NEW_BOUNDS_DIGEST": result["NEW_BOUNDS_DIGEST"],
                "FAMILY_BOUND": result["FAMILY_AFTER"]["FAMILY_BOUND"],
                "NEXT_DISTINCT_BOUND": result["NEXT_DISTINCT_BOUND"],
                "NEGATIVE_VALIDATIONS": result["NEGATIVE_VALIDATIONS"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
