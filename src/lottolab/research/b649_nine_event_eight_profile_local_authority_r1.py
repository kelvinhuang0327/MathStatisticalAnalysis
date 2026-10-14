"""Rebuild the prospective nine-event, eight-profile B649 family authority."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_existing_four_owner_local_authority_r1 as four

TASK_ID = "B649_NINE_EVENT_EIGHT_PROFILE_LOCAL_AUTHORITY_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
FOUR_OWNER_HEAD = "7ee6b57d084ac75d68b18f45ba44cdb49352f0d8"
FOUR_OWNER_TREE = "f45927de4d2b2372831357d83c307b1183fac237"
FOUR_OWNER_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-existing-four-owner-local-authority-r1-result.json"
)
FOUR_OWNER_RESULT_SHA256 = "3df0f24990811303fc111d866fb37022a3d60521951955e5921b15d068b8405e"
EXPECTED_BASE_FULL_DIGEST = "dd2c452d64a9c4afd49be4e375c72370c5ed336479f094dc5ec7b134670ae5cf"
EXPECTED_BASE_BOUNDS_DIGEST = "38e7dedafd2e01af2625d672dadb15c74ba059df859b77552453fea4b143fa0b"
EXPECTED_NEW_FULL_DIGEST = "a1f056cb9330c22505e0dd320b6c1e331e1569782927fb4c8b87c41fe97e146b"
EXPECTED_NEW_BOUNDS_DIGEST = "dff29de4b8732ad88a7906453a244406bc147343ff48a980f50dcd2d26d1b4d0"
EXPECTED_ROW_COUNT = 4_647
EXPECTED_UPDATE_EVENTS = 9
EXPECTED_DISTINCT_CHANGED_PROFILES = 8
EXPECTED_UNCHANGED_ROWS = 4_639
FROZEN_FAMILY_BOUND = 313_398_532
EXPECTED_FAMILY_BOUND = 313_395_448
EXPECTED_FAMILY_OWNERS = ["66555555555441000000", "66555555555522000000"]
EXPECTED_NEXT_BOUND = 313_395_344
EXPECTED_NEXT_OWNERS = ["66655555555511100000", "66665555554431000000"]
CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
INCUMBENT = 313_263_888
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-nine-event-eight-profile-local-authority-r1-result.json"
)
ROOT = Path(__file__).resolve().parents[3]
Row = four.Row


@dataclass(frozen=True)
class DonorPin:
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
    result_path: str
    result_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    proof_sha256: str


DONOR_PINS: tuple[DonorPin, ...] = (
    DonorPin(
        "FRONTIER_A",
        "B649_FRONTIER_OWNER_A_EXACT_BOUND_R1",
        "66665555555331000000",
        313_398_144,
        264,
        313_371_452,
        261,
        112,
        "a161aec2ebfbc338b4411fd7d9c2f14851d13dfb",
        "efc0ae9ca86eaa2f65091a33432142aeb22fe32e",
        "docs/research/matrix-native-results/b649-frontier-owner-a-exact-bound-r1-result.json",
        "3135c1a73c9c6dedbfcdb49bc08565d9a8f0b40d854be8cd18532103193636d5",
        "src/lottolab/research/b649_frontier_owner_a_exact_bound_r1.py",
        "82291ae7eb58311c7fabca730ed5be6180fb1cb8c9163ffc81e9b470f99215fc",
        "tests/unit/test_b649_frontier_owner_a_exact_bound_r1.py",
        "0cdd2f73b7521ea0d11202d406a3883b620ac34012c9ba8a73491228fea57101",
        "98fb91aa44a1c17fe62f77d1f0112d604e45720d6699168215042824bb37d10e",
    ),
    DonorPin(
        "FRONTIER_B",
        "B649_FRONTIER_OWNER_B_EXACT_BOUND_R1",
        "66665555555411100000",
        313_398_144,
        264,
        313_380_220,
        262,
        112,
        "04683df66a80b7cb4e1f39588ebfa5099b4739e9",
        "d1b11ead94b271d2b8c54aafe1b0df7b56e5929f",
        "docs/research/matrix-native-results/b649-frontier-owner-b-exact-bound-r1-result.json",
        "1fade343cebd99011997dad34eb64c99c1db8fdadc4e9940e03015a771b19310",
        "src/lottolab/research/b649_frontier_owner_b_exact_bound_r1.py",
        "cdfba6a21dc3e3d9f61a30bbf4170f93302aac63e450acab8547869497009dd9",
        "tests/unit/test_b649_frontier_owner_b_exact_bound_r1.py",
        "6464014c10439515c8e22e1f158ad3cb314a2d003b6c6a63bf97a8f1053d3561",
        "526fa1d0e3553a17daec979ac1479cfe279ff1bbca56b15a25cfa681b2c8db3e",
    ),
    DonorPin(
        "FRONTIER_C",
        "B649_NEXT_FAMILY_OWNER_66665555554421100000_R1",
        "66665555554421100000",
        313_397_860,
        265,
        313_362_012,
        261,
        112,
        "fc303de0b95af10bf5ead2e6e51fed199be380e2",
        "9d6b39fc2d0075d5be334100847c5ac4bdd2f6cb",
        "docs/research/matrix-native-results/"
        "b649-next-family-owner-66665555554421100000-r1-result.json",
        "eeeaea8e4f07b00c01ea6f6f3de428f310a49389f76c392835386e76b734cb07",
        "src/lottolab/research/b649_next_family_owner_66665555554421100000_r1.py",
        "9608974171d685db3b8de21763c517ed6f17223511c4031dcd4b0fe9ac17ed4b",
        "tests/unit/test_b649_next_family_owner_66665555554421100000_r1.py",
        "cde617f90bf02fcc702d3289d9ceeff09d1e8108f266527a3132f6fa046275c1",
        "f965a07d08d94b00dca6c375683d6d446106bfae2830a0adf147572b0f682663",
    ),
    DonorPin(
        "T258",
        "B649_CURRENT_MAX_OWNER_BOUND_REFINEMENT_R1",
        "66655555555521000000",
        313_397_476,
        264,
        313_343_704,
        258,
        112,
        "b838f9a20bf51d2937f7b63ae56682f70c4d067f",
        "b5c7db68b4ee4619f37b39a11bb3a51fe1d9692e",
        "docs/research/matrix-native-results/"
        "b649-current-max-owner-bound-refinement-r1-result.json",
        "af3f096631cbf8fb38fa268ab733d0b1b7b6189dc76d0c3a03e701dea056b4c9",
        "src/lottolab/research/b649_current_max_owner_bound_refinement_r1.py",
        "3787e270be62da5104867e562bb33a06060c4077149464d2a08c5699da7e8cb8",
        "tests/unit/test_b649_current_max_owner_bound_refinement_r1.py",
        "bfded0f8fef0b7488d0000336bc6c45d6703ce3652dc321dfca88b1b996669f6",
        "36b004ef2ab0820dbfa2edad6fd4ae2b8017dc02e5f0ba5338d4a88e779d5525",
    ),
    DonorPin(
        "T255",
        "B649_NEXT_OWNER_T255_COMPLETION_R1",
        "65555555555550000000",
        313_396_120,
        264,
        313_315_656,
        255,
        1_680,
        "40a516aaa5a766c2312ef1402d70bdafdc22177e",
        "819f8edc7828539e37e663dee284adbc93c1047e",
        "docs/research/matrix-native-results/b649-next-owner-t255-completion-r1-result.json",
        "976cc1d5ace7c2597b356fe1ecde0ad4da11d9c3d592ac1e0f6ce2b58f84e856",
        "src/lottolab/research/b649_next_owner_t255_completion_r1.py",
        "a6d51804a0c2d52aa5dc1009e6326cb97a3cbe1183dc7f602b0a356f960195ed",
        "tests/unit/test_b649_next_owner_t255_completion_r1.py",
        "107a4d1d976eb70bdec6973ddfd9e8c05f5a3e2a38f1f9ccd318c1df78476b3b",
        "943064723daf40dfbf97f0016d2ca5be8ae247f014207c06cbf7370fb36a7796",
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


def nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            raise ValueError(f"missing proof field: {key}")
        current = cast(Mapping[str, Any], current)[key]
    return current


def verify_commit(root: Path, head: str, tree: str) -> None:
    require(four.run_git(root, "rev-parse", head) == head, f"donor HEAD mismatch: {head}")
    require(
        four.run_git(root, "rev-parse", f"{head}^{{tree}}") == tree,
        f"donor tree mismatch: {head}",
    )


def proof_sha256(proof: Any) -> str:
    require(type(proof) is str and bool(proof.strip()), "donor proof is missing")
    return sha256(cast(str, proof).encode())


def proof_source(pin: DonorPin) -> str:
    return f"git:{pin.head}@{pin.tree}:{pin.result_path}#PROOF:sha256={pin.proof_sha256}"


def verify_certificate(
    certificate: Mapping[str, Any],
    *,
    profile_id: str,
    cap: int,
    bound: int,
    source: str,
) -> None:
    require(certificate.get("PROFILE_ID") == profile_id, "certificate profile mismatch")
    require(
        type(certificate.get("T_CAP")) is int and certificate.get("T_CAP") == cap,
        "certificate T cap mismatch",
    )
    require(
        type(certificate.get("OWNER_BOUND")) is int and certificate.get("OWNER_BOUND") == bound,
        "certificate owner bound mismatch",
    )
    require(
        certificate.get("PROOF_SCOPE") == "FULL_PROFILE"
        and certificate.get("ROW_SOURCE") == source,
        "certificate proof scope or source identity mismatch",
    )
    require(
        certificate.get("PROOF_SHA256") == source.rsplit("=", 1)[-1],
        "certificate proof is missing or mismatched",
    )


def verify_donor(root: Path, pin: DonorPin) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_commit(root, pin.head, pin.tree)
    raw_result = four.committed_blob(root, pin.head, pin.result_path)
    raw_source = four.committed_blob(root, pin.head, pin.source_path)
    raw_test = four.committed_blob(root, pin.head, pin.test_path)
    require(
        sha256(raw_result) == pin.result_sha256,
        f"donor result SHA256 mismatch: {pin.event_id}",
    )
    require(
        sha256(raw_source) == pin.source_sha256,
        f"donor source SHA256 mismatch: {pin.event_id}",
    )
    require(sha256(raw_test) == pin.test_sha256, f"donor test SHA256 mismatch: {pin.event_id}")
    result = json_object(raw_result, f"donor result is invalid JSON: {pin.event_id}")
    proof = result.get("PROOF")
    require(proof_sha256(proof) == pin.proof_sha256, f"donor proof SHA256 mismatch: {pin.event_id}")
    try:
        source_doc = ast.get_docstring(ast.parse(raw_source.decode()), clean=False)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError(f"donor proof source cannot be parsed: {pin.event_id}") from exc
    require(source_doc == proof, f"donor proof differs from committed source: {pin.event_id}")
    require(result.get("TASK_ID") == pin.task_id, f"donor task identity mismatch: {pin.event_id}")
    require(
        result.get("PROOF_SCOPE", "FULL_PROFILE") == "FULL_PROFILE",
        f"donor proof scope mismatch: {pin.event_id}",
    )

    if pin.event_id == "FRONTIER_A":
        profile = nested(result, "SOURCE", "PROFILE_ID")
        before_bound = nested(result, "SOURCE", "ORIGINAL_ROW_BOUND")
        before_cap = nested(result, "SOURCE", "ORIGINAL_T_CAP")
        s4_base = nested(result, "SOURCE", "ORIGINAL_S4_BASE")
        cap = nested(result, "MATHEMATICS", "ANALYTIC_CAP")
        bound = nested(result, "OPTIMIZATION", "NEW_ADMISSIBLE_BOUND")
    elif pin.event_id == "FRONTIER_B":
        profile = result.get("PROFILE_ID")
        before_bound = nested(result, "SOURCE", "SOURCE_ROW_BOUND")
        before_cap = nested(result, "SOURCE", "SOURCE_T_CAP")
        s4_base = nested(result, "SOURCE", "SOURCE_S4_BASE")
        cap = result.get("EXACT_UPPER_BOUND")
        bound = result.get("NEW_ADMISSIBLE_BOUND")
    elif pin.event_id == "FRONTIER_C":
        profile = result.get("PROFILE_ID")
        before_bound = nested(result, "SOURCE_ROW", "BOUND")
        before_cap = result.get("SOURCE_T_CAP")
        s4_base = result.get("SOURCE_S4_BASE")
        cap = result.get("PROVED_T_CAP")
        bound = result.get("NEW_ADMISSIBLE_BOUND")
    elif pin.event_id == "T258":
        profile = result.get("PROFILE")
        before_bound = result.get("OLD_BOUND")
        before_cap = result.get("SOURCE_T_CAP")
        s4_base = pin.s4_base
        cap = result.get("NEW_T_CAP")
        bound = result.get("NEW_ADMISSIBLE_BOUND")
    else:
        profile = nested(result, "THEOREM_T255", "PROFILE_ID")
        before_bound = nested(result, "SOURCE_ROW", "SOURCE_ROW_BOUND")
        before_cap = nested(result, "SOURCE_ROW", "SOURCE_T_CAP")
        s4_base = nested(result, "SOURCE_ROW", "SOURCE_S4_BASE")
        cap = result.get("NEW_CAP")
        bound = result.get("NEW_BOUND")

    require(
        (profile, before_bound, before_cap, s4_base, cap, bound)
        == (
            pin.profile_id,
            pin.previous_bound,
            pin.previous_cap,
            pin.s4_base,
            pin.cap,
            pin.bound,
        ),
        f"donor profile, row, cap, or bound mismatch: {pin.event_id}",
    )
    source = proof_source(pin)
    certificate = {
        "PROFILE_ID": pin.profile_id,
        "T_CAP": pin.cap,
        "OWNER_BOUND": pin.bound,
        "PROOF_SCOPE": "FULL_PROFILE",
        "ROW_SOURCE": source,
        "PROOF_SHA256": pin.proof_sha256,
    }
    verify_certificate(
        certificate,
        profile_id=pin.profile_id,
        cap=pin.cap,
        bound=pin.bound,
        source=source,
    )
    identity = {
        "EVENT_ID": pin.event_id,
        "TASK_ID": pin.task_id,
        "HEAD": pin.head,
        "TREE": pin.tree,
        "RESULT_PATH": pin.result_path,
        "RESULT_SHA256": sha256(raw_result),
        "SOURCE_PATH": pin.source_path,
        "SOURCE_SHA256": sha256(raw_source),
        "TEST_PATH": pin.test_path,
        "TEST_SHA256": sha256(raw_test),
        "PROOF_FIELD": "PROOF",
        "PROOF_SHA256": proof_sha256(proof),
        "PROFILE_ID": pin.profile_id,
        "PROOF_SCOPE": "FULL_PROFILE",
        "CAP_BEFORE": pin.previous_cap,
        "CAP_AFTER": pin.cap,
        "BOUND_BEFORE": pin.previous_bound,
        "BOUND_AFTER": pin.bound,
        "S4_BASE": pin.s4_base,
        "ROW_SOURCE": source,
    }
    return result, identity


def verify_four_owner_baseline(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Row], dict[str, Row], dict[str, Any]]:
    verify_commit(root, FROZEN_HEAD, FROZEN_TREE)
    verify_commit(root, FOUR_OWNER_HEAD, FOUR_OWNER_TREE)
    raw = four.committed_blob(root, FOUR_OWNER_HEAD, FOUR_OWNER_RESULT_PATH)
    require(sha256(raw) == FOUR_OWNER_RESULT_SHA256, "four-owner result SHA256 mismatch")
    require((root / FOUR_OWNER_RESULT_PATH).read_bytes() == raw, "four-owner result bytes mismatch")
    recorded = json_object(raw, "four-owner result is invalid JSON")
    require(
        recorded.get("TASK_STATUS") == "PROSPECTIVE_LOCAL_INTEGRATION_COMPLETE"
        and recorded.get("TASK_ID") == four.TASK_ID,
        "four-owner result identity mismatch",
    )
    replay, frozen, after, certificates = four.build_candidate()
    require(
        len(frozen) == EXPECTED_ROW_COUNT and len(after) == EXPECTED_ROW_COUNT,
        "four-owner row count mismatch",
    )
    overlay = replay["LEDGER_OVERLAY"]
    recorded_overlay = recorded.get("LEDGER_OVERLAY")
    require(type(recorded_overlay) is dict, "four-owner ledger overlay is missing")
    require(
        overlay == recorded_overlay
        and overlay.get("FULL_DIGEST_BEFORE") == four.SEVEN_ROW_FULL_DIGEST
        and overlay.get("BOUNDS_DIGEST_BEFORE") == four.SEVEN_ROW_BOUNDS_DIGEST
        and overlay.get("FULL_DIGEST_AFTER") == EXPECTED_BASE_FULL_DIGEST
        and overlay.get("BOUNDS_DIGEST_AFTER") == EXPECTED_BASE_BOUNDS_DIGEST
        and overlay.get("UNCHANGED_ROWS") == EXPECTED_ROW_COUNT - 4,
        "four-owner ledger digest or row replay mismatch",
    )
    require(
        recorded.get("ROW_UPDATES") == replay.get("ROW_UPDATES")
        and recorded.get("OWNER_CERTIFICATES") == replay.get("OWNER_CERTIFICATES"),
        "four-owner source pointers or updates mismatch",
    )
    require(
        len(certificates) == 4
        and all(
            after[cast(str, cert["PROFILE_ID"])].source == cert["ROW_SOURCE"]
            for cert in certificates
        ),
        "four-owner source metadata does not match reconstructed rows",
    )
    return (
        replay,
        frozen,
        after,
        {
            "HEAD": FOUR_OWNER_HEAD,
            "TREE": FOUR_OWNER_TREE,
            "RESULT_PATH": FOUR_OWNER_RESULT_PATH,
            "RESULT_SHA256": sha256(raw),
            "ROWS_BEFORE": len(frozen),
            "ROWS_AFTER": len(after),
            "FULL_DIGEST_BEFORE": overlay["FULL_DIGEST_BEFORE"],
            "BOUNDS_DIGEST_BEFORE": overlay["BOUNDS_DIGEST_BEFORE"],
            "FULL_DIGEST_AFTER": overlay["FULL_DIGEST_AFTER"],
            "BOUNDS_DIGEST_AFTER": overlay["BOUNDS_DIGEST_AFTER"],
            "ROW_SOURCE_METADATA_VERIFIED": "YES",
            "ALL_ROWS_RECONSTRUCTED": "YES",
        },
    )


def event_from_update(
    event_id: str,
    profile_id: str,
    before: Row,
    after: Row,
) -> dict[str, Any]:
    return {
        "EVENT_ID": event_id,
        "PROFILE_ID": profile_id,
        "BOUND_BEFORE": before.bound,
        "BOUND_AFTER": after.bound,
        "CAP_BEFORE": before.cap,
        "CAP_AFTER": after.cap,
        "S4_BASE_BEFORE": before.s4_base,
        "S4_BASE_AFTER": after.s4_base,
        "SOURCE_BEFORE": before.source,
        "SOURCE_AFTER": after.source,
    }


def historical_events(
    recorded: Mapping[str, Any], before: Mapping[str, Row], after: Mapping[str, Row]
) -> list[dict[str, Any]]:
    updates = recorded.get("ROW_UPDATES")
    require(type(updates) is list and len(updates) == 4, "four historical owner events are missing")
    events: list[dict[str, Any]] = []
    for index, raw_update in enumerate(cast(list[Any], updates)):
        require(type(raw_update) is dict, "historical owner event schema mismatch")
        update = cast(dict[str, Any], raw_update)
        profile_id = cast(str, update.get("PROFILE_ID"))
        old = before[profile_id]
        new = after[profile_id]
        require(
            (
                update.get("BEFORE_BOUND"),
                update.get("AFTER_BOUND"),
                update.get("CAP_BEFORE"),
                update.get("CAP_AFTER"),
                update.get("SOURCE_AFTER"),
            )
            == (old.bound, new.bound, old.cap, new.cap, new.source),
            f"historical owner event does not match row replay: {profile_id}",
        )
        events.append(event_from_update(f"FOUR_OWNER_{index + 1}", profile_id, old, new))
    return events


def apply_donor_events(
    ledger: Mapping[str, Row],
    pins: Sequence[DonorPin],
    identities: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Row], list[dict[str, Any]]]:
    seen_events: set[str] = set()
    after = dict(ledger)
    events: list[dict[str, Any]] = []
    for pin in pins:
        require(pin.event_id not in seen_events, "duplicate update event")
        seen_events.add(pin.event_id)
        identity = identities.get(pin.event_id)
        if identity is None:
            raise ValueError(f"missing verified donor proof: {pin.event_id}")
        source = cast(str, identity.get("ROW_SOURCE"))
        certificate = {
            "PROFILE_ID": identity.get("PROFILE_ID"),
            "T_CAP": identity.get("CAP_AFTER"),
            "OWNER_BOUND": identity.get("BOUND_AFTER"),
            "PROOF_SCOPE": identity.get("PROOF_SCOPE"),
            "ROW_SOURCE": source,
            "PROOF_SHA256": identity.get("PROOF_SHA256"),
        }
        verify_certificate(
            certificate,
            profile_id=pin.profile_id,
            cap=pin.cap,
            bound=pin.bound,
            source=source,
        )
        old = after[pin.profile_id]
        require(
            (old.bound, old.cap, old.s4_base)
            == (pin.previous_bound, pin.previous_cap, pin.s4_base),
            f"row event before-state mismatch: {pin.event_id}",
        )
        new = replace(old, bound=pin.bound, cap=pin.cap, s4_base=pin.s4_base, source=source)
        require(
            new.bound < old.bound and new.cap <= old.cap,
            f"row event is not a tightening: {pin.event_id}",
        )
        after[pin.profile_id] = new
        event = event_from_update(pin.event_id, pin.profile_id, old, new)
        event["DONOR"] = dict(identity)
        event["PROOF_SCOPE"] = certificate["PROOF_SCOPE"]
        event["PROOF_SHA256"] = certificate["PROOF_SHA256"]
        events.append(event)
    return after, events


def verify_overlay(
    frozen: Mapping[str, Row],
    after: Mapping[str, Row],
    expected_changed_profiles: set[str],
) -> dict[str, Any]:
    require(set(frozen) == set(after), "ledger profile set changed")
    changed = {profile_id for profile_id in frozen if frozen[profile_id] != after[profile_id]}
    require(changed == expected_changed_profiles, "unrelated row mutation or missing row event")
    unchanged = sum(frozen[profile_id] == after[profile_id] for profile_id in frozen)
    require(unchanged == EXPECTED_UNCHANGED_ROWS, "unchanged row count mismatch")
    before_full = four.seven.two.full_digest(frozen)
    before_bounds = four.seven.two.bounds_digest(frozen)
    after_full = four.seven.two.full_digest(after)
    after_bounds = four.seven.two.bounds_digest(after)
    require(before_full == four.SEVEN_ROW_FULL_DIGEST, "frozen full digest changed")
    require(before_bounds == four.SEVEN_ROW_BOUNDS_DIGEST, "frozen bounds digest changed")
    require(after_full == EXPECTED_NEW_FULL_DIGEST, "new full digest mismatch")
    require(after_bounds == EXPECTED_NEW_BOUNDS_DIGEST, "new bounds digest mismatch")
    return {
        "ROWS_BEFORE": len(frozen),
        "ROWS_AFTER": len(after),
        "UPDATE_EVENTS": EXPECTED_UPDATE_EVENTS,
        "DISTINCT_CHANGED_PROFILE_COUNT": len(changed),
        "DISTINCT_CHANGED_PROFILES": sorted(changed),
        "UNCHANGED_ROWS": unchanged,
        "FULL_DIGEST_BEFORE": before_full,
        "BOUNDS_DIGEST_BEFORE": before_bounds,
        "FULL_DIGEST_AFTER": after_full,
        "BOUNDS_DIGEST_AFTER": after_bounds,
        "FULL_DIGEST_IS_ROW_SOURCE_AWARE": "YES",
        "FROZEN_LEDGER_UNCHANGED": "YES",
    }


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    four_result, frozen, four_after, four_identity = verify_four_owner_baseline(ROOT)
    require(
        four.seven.two.full_digest(four_after) == EXPECTED_BASE_FULL_DIGEST
        and four.seven.two.bounds_digest(four_after) == EXPECTED_BASE_BOUNDS_DIGEST,
        "four-owner digests fail immediately before additional events",
    )
    donor_data: dict[str, dict[str, Any]] = {}
    donor_identities: dict[str, dict[str, Any]] = {}
    for pin in DONOR_PINS:
        donor_data[pin.event_id], donor_identities[pin.event_id] = verify_donor(ROOT, pin)

    after, donor_events = apply_donor_events(four_after, DONOR_PINS, donor_identities)
    events = historical_events(four_result, frozen, four_after) + donor_events
    require(len(events) == EXPECTED_UPDATE_EVENTS, "update event count mismatch")
    require(
        len({event["EVENT_ID"] for event in events}) == EXPECTED_UPDATE_EVENTS,
        "duplicate update event",
    )
    expected_changed = {
        *four.TARGET_PROFILE_IDS,
        *(pin.profile_id for pin in DONOR_PINS),
    }
    require(
        len(expected_changed) == EXPECTED_DISTINCT_CHANGED_PROFILES,
        "distinct profile count mismatch",
    )
    overlay = verify_overlay(frozen, after, expected_changed)
    family_before = four.family_frontier(frozen)
    family_after = four.family_frontier(after)
    require(family_before["FAMILY_BOUND"] == FROZEN_FAMILY_BOUND, "frozen family bound mismatch")
    require(
        family_after
        == {
            "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
            "TIED_OWNERS": EXPECTED_FAMILY_OWNERS,
            "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
            "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNERS,
            "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        },
        "new family frontier mismatch",
    )
    resolved_above_incumbent = sum(row.bound > INCUMBENT for row in after.values())
    require(resolved_above_incumbent == 1_375, "resolved profiles above incumbent mismatch")
    require(four.seven.two.full_digest(frozen) == four.SEVEN_ROW_FULL_DIGEST, "frozen rows mutated")

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PROSPECTIVE_LOCAL_INTEGRATION_COMPLETE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "SOURCE_PUBLICATION": "NOT_RUN",
        "FROZEN_AUTHORITY": {
            "HEAD": FROZEN_HEAD,
            "TREE": FROZEN_TREE,
            "RESULT_SHA256": FROZEN_RESULT_SHA256,
            "RESULT_PATH": four.FROZEN_RESULT_PATH,
            "ROWS": EXPECTED_ROW_COUNT,
            "FULL_DIGEST": four.SEVEN_ROW_FULL_DIGEST,
            "BOUNDS_DIGEST": four.SEVEN_ROW_BOUNDS_DIGEST,
            "FAMILY_BOUND": FROZEN_FAMILY_BOUND,
        },
        "FOUR_OWNER_AUTHORITY": four_identity,
        "DONOR_IDENTITIES": donor_identities,
        "T255_SOLE_DONOR": next(pin.head for pin in DONOR_PINS if pin.event_id == "T255"),
        "SECOND_T255_DONOR_ADOPTED": "NO",
        "UPDATE_EVENTS": len(events),
        "EVENT_HISTORY": events,
        "DISTINCT_CHANGED_PROFILES": len(expected_changed),
        "LEDGER_OVERLAY": overlay,
        "ROW_SOURCE_METADATA_VERIFIED": "YES",
        "OLD_LEDGER_UNCHANGED": "YES",
        "FOUR_OWNER_DIGESTS_MATCH": "YES",
        "NEW_FULL_DIGEST": overlay["FULL_DIGEST_AFTER"],
        "NEW_BOUNDS_DIGEST": overlay["BOUNDS_DIGEST_AFTER"],
        "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST": EXPECTED_NEW_BOUNDS_DIGEST,
        "FAMILY_BEFORE": family_before,
        "FAMILY_AFTER": family_after,
        "FAMILY_DELTA_FROM_FROZEN": FROZEN_FAMILY_BOUND - family_after["FAMILY_BOUND"],
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": resolved_above_incumbent,
        "UNRESOLVED_CURSOR": {
            "PROFILE_COUNT": 197,
            "STATUS": "UNRESOLVED_AUTHORITY_UNCHANGED",
            "ID": CURSOR_ID,
            "BOUND": CURSOR_BOUND,
        },
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CAVEATS": {
            "EIGHT_ROW_HISTORICAL": "BLOCKED_UNVERIFIABLE",
            "FOUR_OWNER": "VERIFIED_WITH_CAVEATS",
            "T255": "VERIFIED_WITH_CAVEATS",
        },
        "HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
    }
    return result, frozen, after


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    if path.exists():
        require(path.read_bytes() == raw, "refusing to overwrite a different result artifact")
    else:
        path.write_bytes(raw)
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
                "FAMILY_AFTER": result["FAMILY_AFTER"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
