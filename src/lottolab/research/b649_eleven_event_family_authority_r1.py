"""Integrate the two reviewed certificates into the existing B649 family authority."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_nine_event_eight_profile_local_authority_r1 as nine

TASK_ID = "B649_ELEVEN_EVENT_FAMILY_AUTHORITY_INTEGRATION_R1"
BASE_HEAD = "8b6921006005ac256d6c44b81ab0cb3d2049584c"
BASE_TREE = "3317545b5ed348cb8ad2372671cb036479a6d1ba"
NINE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-nine-event-eight-profile-local-authority-r1-result.json"
)
NINE_RESULT_SHA256 = "49ad781cdc5cbcf972d3726cf8367255efa995afac0b7265b016bcb1792a91fa"
NINE_SOURCE_PATH = "src/lottolab/research/b649_nine_event_eight_profile_local_authority_r1.py"
NINE_SOURCE_SHA256 = "56e8f337878914c04d2ff1ef402d547af38665eadf4869791545e9ee11b09d28"
NINE_TEST_PATH = "tests/unit/test_b649_nine_event_eight_profile_local_authority_r1.py"
NINE_TEST_SHA256 = "4c5e6f4a33029ccb0d2a9afa92dc2f52e36b47685d19585f30c9a9add6eb6d22"
EXPECTED_ROW_COUNT = 4_647
EXPECTED_UPDATE_EVENTS = 11
EXPECTED_DISTINCT_CHANGED_PROFILES = 10
EXPECTED_UNCHANGED_ROWS = 4_637
EXPECTED_ADDITIONAL_EVENTS_FROM_NINE = 2
EXPECTED_ADDITIONAL_CHANGED_PROFILES = 2
EXPECTED_UNCHANGED_ROWS_FROM_NINE = 4_645
FROZEN_FAMILY_BOUND = 313_398_532
NINE_EVENT_FAMILY_BOUND = 313_395_448
EXPECTED_FAMILY_BOUND = 313_395_344
EXPECTED_FAMILY_OWNERS = ["66655555555511100000", "66665555554431000000"]
EXPECTED_NEXT_BOUND = 313_395_164
EXPECTED_NEXT_OWNERS = [
    "65555555555532000000",
    "66555555554442000000",
    "66555555555333000000",
]
CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
INCUMBENT = 313_263_888
EXPECTED_NEW_FULL_DIGEST = "55ed4aae5f090ec7ea451ee9c477525b0b5e9ee362b8e3d79282fb04428f151d"
EXPECTED_NEW_BOUNDS_DIGEST = "bf27d37e5ee5443e68e5c27a21f8490239cda18573cfcd6b90c011a4b8b22d4e"
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-eleven-event-family-authority-r1-result.json"
)
ROOT = Path(__file__).resolve().parents[3]
Row = four.Row
DonorPin = nine.DonorPin


DONOR_PINS: tuple[DonorPin, ...] = (
    DonorPin(
        "OWNER_A_T238",
        "B649_NEXT_TIED_OWNER_A_EXACT_BOUND_R1",
        "66555555555441000000",
        313_395_448,
        265,
        313_153_668,
        238,
        112,
        "2fd8e783cbcf66c677f58b69dae8735779315698",
        "d222abc33554720b7276a03513a2127a05663bd0",
        "docs/research/matrix-native-results/"
        "b649-min-s2-tied-owner-a-hub-t238-exact-bound-r1-result.json",
        "6d46633e83f83cc6f1242d421e015bcbf9fb2da62fe90f9e5d0c8e707bd13bff",
        "src/lottolab/research/b649_min_s2_tied_owner_a_hub_t238_exact_bound_r1.py",
        "513c03b510f8c49485fa0c9b92ef09d40566de51215a9aacf83828787c8295b1",
        "tests/unit/test_b649_min_s2_tied_owner_a_hub_t238_exact_bound_r1.py",
        "8e1f976f11805765c9b048728318a0c23d42be598a49f290ca4394e0d3dc6cf6",
        "c5c93ce62bceb4acd352cc4cfb2db79e4957c61490a5cdd561fbf83ad5c6a58b",
    ),
    DonorPin(
        "OWNER_B_T236",
        "B649_NEW_FRONTIER_OWNER_B_BOUNDED_RESEARCH_R1",
        "66555555555522000000",
        313_395_448,
        265,
        313_135_356,
        236,
        112,
        "6b9565274527f7132eff36f95c87d1c8cbe7c009",
        "f5a871b15109482d9a1ac7911a5f8c38da24b022",
        "docs/research/matrix-native-results/b649-new-frontier-owner-b-bounded-r1-result.json",
        "3db430900df1194d072582d6c15a7101d9687009cccd71c8c9fb054180b3b6b4",
        "src/lottolab/research/b649_new_frontier_owner_b_bounded_r1.py",
        "b3648db195564a99831be75453a6dfa7ac3511f9ca47c6eb481a11cf27382dcf",
        "tests/unit/test_b649_new_frontier_owner_b_bounded_r1.py",
        "0836a18d67f56e479acde7bccfe0a316238c942fe66c181b5df419c85a69863b",
        "0da6eec66858fa6e9b1aa030f28036f47f320e25e7416771af98f60254ec0d24",
    ),
)

FRESH_JUDGE_STATUS = {
    "OWNER_A_T238": "VERIFIED_WITH_CAVEATS",
    "OWNER_B_T236": "VERIFIED_WITH_CAVEATS",
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    nine.require(condition, message)


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    return nine.json_object(raw, message)


def verify_nine_event_authority(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Row], dict[str, Row], dict[str, Any]]:
    nine.verify_commit(root, BASE_HEAD, BASE_TREE)
    raw_result = four.committed_blob(root, BASE_HEAD, NINE_RESULT_PATH)
    raw_source = four.committed_blob(root, BASE_HEAD, NINE_SOURCE_PATH)
    raw_test = four.committed_blob(root, BASE_HEAD, NINE_TEST_PATH)
    require(sha256(raw_result) == NINE_RESULT_SHA256, "nine-event result SHA256 mismatch")
    require(sha256(raw_source) == NINE_SOURCE_SHA256, "nine-event source SHA256 mismatch")
    require(sha256(raw_test) == NINE_TEST_SHA256, "nine-event test SHA256 mismatch")

    recorded = json_object(raw_result, "nine-event result is invalid JSON")
    rebuilt, frozen, after = nine.build_candidate()
    require(
        recorded == rebuilt and raw_result == nine.serialize_result(rebuilt),
        "nine-event result differs from its verified source replay",
    )
    require(
        rebuilt.get("TASK_ID") == "B649_NINE_EVENT_EIGHT_PROFILE_LOCAL_AUTHORITY_R1"
        and rebuilt.get("UPDATE_EVENTS") == 9
        and rebuilt.get("DISTINCT_CHANGED_PROFILES") == 8,
        "nine-event source identity or event counts mismatch",
    )
    require(
        rebuilt.get("NEW_BOUNDS_DIGEST") == nine.EXPECTED_NEW_BOUNDS_DIGEST
        and rebuilt.get("NEW_FULL_DIGEST") == nine.EXPECTED_NEW_FULL_DIGEST,
        "nine-event source digest mismatch",
    )
    return (
        rebuilt,
        frozen,
        after,
        {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": NINE_RESULT_PATH,
            "RESULT_SHA256": sha256(raw_result),
            "SOURCE_PATH": NINE_SOURCE_PATH,
            "SOURCE_SHA256": sha256(raw_source),
            "TEST_PATH": NINE_TEST_PATH,
            "TEST_SHA256": sha256(raw_test),
            "UPDATE_EVENTS": rebuilt["UPDATE_EVENTS"],
            "DISTINCT_CHANGED_PROFILES": rebuilt["DISTINCT_CHANGED_PROFILES"],
            "NEW_FULL_DIGEST": rebuilt["NEW_FULL_DIGEST"],
            "NEW_BOUNDS_DIGEST": rebuilt["NEW_BOUNDS_DIGEST"],
            "SOURCE_REPLAY_MATCH": "YES",
        },
    )


def verify_new_donor(root: Path, pin: DonorPin) -> tuple[dict[str, Any], dict[str, Any]]:
    nine.verify_commit(root, pin.head, pin.tree)
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
    proof_digest = nine.proof_sha256(proof)
    require(proof_digest == pin.proof_sha256, f"donor proof SHA256 mismatch: {pin.event_id}")
    try:
        source_doc = ast.get_docstring(ast.parse(raw_source.decode()), clean=False)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError(f"donor proof source cannot be parsed: {pin.event_id}") from exc
    require(source_doc == proof, f"donor proof differs from committed source: {pin.event_id}")
    require(result.get("TASK_ID") == pin.task_id, f"donor task identity mismatch: {pin.event_id}")
    require(
        result.get("PROOF_SCOPE") == "FULL_PROFILE",
        f"donor proof scope mismatch: {pin.event_id}",
    )

    if pin.event_id == "OWNER_A_T238":
        profile = nine.nested(result, "THEOREM_T238", "ATTAINED_BY_WITNESS", "PROFILE_ID")
        before_bound = result.get("OLD_BOUND")
        before_cap = result.get("SOURCE_T_CAP")
        s4_base = result.get("SOURCE_S4_BASE")
        cap = result.get("NEW_T_CAP")
        bound = result.get("NEW_ADMISSIBLE_BOUND")
    elif pin.event_id == "OWNER_B_T236":
        profile = result.get("PROFILE_ID")
        before_bound = result.get("OLD_BOUND")
        before_cap = nine.nested(result, "SOURCE", "SOURCE_T_CAP")
        s4_base = nine.nested(result, "SOURCE", "SOURCE_S4_BASE")
        cap = result.get("PROVED_T_CAP")
        bound = result.get("NEW_ADMISSIBLE_BOUND")
    else:
        raise ValueError(f"unsupported new donor event: {pin.event_id}")

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

    source = nine.proof_source(pin)
    certificate = {
        "PROFILE_ID": pin.profile_id,
        "T_CAP": pin.cap,
        "OWNER_BOUND": pin.bound,
        "PROOF_SCOPE": "FULL_PROFILE",
        "ROW_SOURCE": source,
        "PROOF_SHA256": proof_digest,
    }
    nine.verify_certificate(
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
        "PROOF_SHA256": proof_digest,
        "PROFILE_ID": pin.profile_id,
        "PROOF_SCOPE": "FULL_PROFILE",
        "CAP_BEFORE": pin.previous_cap,
        "CAP_AFTER": pin.cap,
        "BOUND_BEFORE": pin.previous_bound,
        "BOUND_AFTER": pin.bound,
        "S4_BASE": pin.s4_base,
        "ROW_SOURCE": source,
        "FRESH_JUDGE_STATUS": FRESH_JUDGE_STATUS[pin.event_id],
    }
    return result, identity


def verify_overlay(
    frozen: Mapping[str, Row],
    after: Mapping[str, Row],
    expected_changed_profiles: set[str],
) -> dict[str, Any]:
    require(set(frozen) == set(after), "ledger profile set changed")
    require(
        len(frozen) == EXPECTED_ROW_COUNT and len(after) == EXPECTED_ROW_COUNT,
        "ledger row count mismatch",
    )
    changed = {profile_id for profile_id in frozen if frozen[profile_id] != after[profile_id]}
    require(changed == expected_changed_profiles, "unrelated row mutation or missing row event")
    unchanged = sum(frozen[profile_id] == after[profile_id] for profile_id in frozen)
    require(unchanged == EXPECTED_UNCHANGED_ROWS, "unchanged row count mismatch")

    before_full = four.seven.two.full_digest(frozen)
    before_bounds = four.seven.two.bounds_digest(frozen)
    after_full = four.seven.two.full_digest(after)
    after_bounds = four.seven.two.bounds_digest(after)
    bounds_projection = {
        profile_id: replace(row, source=frozen[profile_id].source)
        for profile_id, row in after.items()
    }
    projected_bounds = four.seven.two.bounds_digest(bounds_projection)
    require(before_full == four.SEVEN_ROW_FULL_DIGEST, "frozen full digest changed")
    require(before_bounds == four.SEVEN_ROW_BOUNDS_DIGEST, "frozen bounds digest changed")
    require(projected_bounds == after_bounds, "bounds-only projection digest mismatch")
    if EXPECTED_NEW_FULL_DIGEST:
        require(after_full == EXPECTED_NEW_FULL_DIGEST, "new full digest mismatch")
    if EXPECTED_NEW_BOUNDS_DIGEST:
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
        "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST": projected_bounds,
        "FULL_DIGEST_IS_ROW_SOURCE_AWARE": "YES",
        "FROZEN_LEDGER_UNCHANGED": "YES",
    }


EXPECTED_FAMILY_AFTER = {
    "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
    "TIED_OWNERS": EXPECTED_FAMILY_OWNERS,
    "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
    "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNERS,
    "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
}


def verify_family_frontier(frontier: Mapping[str, Any]) -> None:
    require(dict(frontier) == EXPECTED_FAMILY_AFTER, "new family frontier mismatch")


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    nine_result, frozen, nine_after, nine_identity = verify_nine_event_authority(ROOT)
    require(
        nine_result["FAMILY_AFTER"]["FAMILY_BOUND"] == NINE_EVENT_FAMILY_BOUND,
        "nine-event family bound mismatch",
    )

    donor_identities: dict[str, dict[str, Any]] = {}
    for pin in DONOR_PINS:
        donor_identities[pin.event_id] = verify_new_donor(ROOT, pin)[1]

    after, new_events = nine.apply_donor_events(nine_after, DONOR_PINS, donor_identities)
    events = list(nine_result["EVENT_HISTORY"]) + new_events
    additional_changed = {
        profile_id
        for profile_id in nine_after
        if nine_after[profile_id] != after[profile_id]
    }
    unchanged_from_nine = sum(
        nine_after[profile_id] == after[profile_id] for profile_id in nine_after
    )
    require(
        len(new_events) == EXPECTED_ADDITIONAL_EVENTS_FROM_NINE
        and additional_changed
        == {pin.profile_id for pin in DONOR_PINS}
        and len(additional_changed) == EXPECTED_ADDITIONAL_CHANGED_PROFILES,
        "additional updates from the nine-event source mismatch",
    )
    require(
        unchanged_from_nine == EXPECTED_UNCHANGED_ROWS_FROM_NINE,
        "unchanged rows from the nine-event source mismatch",
    )
    require(len(events) == EXPECTED_UPDATE_EVENTS, "update event count mismatch")
    require(
        len({event["EVENT_ID"] for event in events}) == EXPECTED_UPDATE_EVENTS,
        "duplicate update event",
    )

    expected_changed = set(nine_result["LEDGER_OVERLAY"]["DISTINCT_CHANGED_PROFILES"])
    expected_changed.update(pin.profile_id for pin in DONOR_PINS)
    require(
        len(expected_changed) == EXPECTED_DISTINCT_CHANGED_PROFILES,
        "distinct profile count mismatch",
    )
    overlay = verify_overlay(frozen, after, expected_changed)
    family_before = four.family_frontier(frozen)
    family_after = four.family_frontier(after)
    require(family_before["FAMILY_BOUND"] == FROZEN_FAMILY_BOUND, "frozen family bound mismatch")
    verify_family_frontier(family_after)

    resolved_above_incumbent = sum(row.bound > INCUMBENT for row in after.values())
    require(resolved_above_incumbent == 1_373, "resolved profiles above incumbent mismatch")
    require(
        four.seven.two.full_digest(frozen) == four.SEVEN_ROW_FULL_DIGEST,
        "frozen rows mutated",
    )

    donor_identities_all = dict(nine_result["DONOR_IDENTITIES"])
    donor_identities_all.update(donor_identities)
    caveats = dict(nine_result["CAVEATS"])
    caveats.update(
        {
            "HISTORICAL_NB_CERTIFICATES_1444": "UNRESOLVED_LOCATOR_PRESERVED",
            "HISTORICAL_MUTATION_RAW_LOGS": "NOT_OBTAINED",
            "T238": "VERIFIED_WITH_CAVEATS",
            "T236": "VERIFIED_WITH_CAVEATS",
        }
    )
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PROSPECTIVE_LOCAL_INTEGRATION_COMPLETE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "SOURCE_PUBLICATION": "NOT_RUN",
        "FROZEN_AUTHORITY": nine_result["FROZEN_AUTHORITY"],
        "FOUR_OWNER_AUTHORITY": nine_result["FOUR_OWNER_AUTHORITY"],
        "NINE_EVENT_AUTHORITY": nine_identity,
        "DONOR_IDENTITIES": donor_identities_all,
        "T255_SOLE_DONOR": nine_result["T255_SOLE_DONOR"],
        "SECOND_T255_DONOR_ADOPTED": "NO",
        "UPDATE_EVENTS": len(events),
        "ADDITIONAL_EVENTS_FROM_NINE": len(new_events),
        "ADDITIONAL_CHANGED_PROFILES": len(additional_changed),
        "UNCHANGED_ROWS_FROM_NINE": unchanged_from_nine,
        "EVENT_HISTORY": events,
        "DISTINCT_CHANGED_PROFILES": len(expected_changed),
        "LEDGER_OVERLAY": overlay,
        "ROW_SOURCE_METADATA_VERIFIED": "YES",
        "OLD_LEDGER_UNCHANGED": "YES",
        "FROZEN_LEDGER_MUTATED": "NO",
        "DONOR_WORKTREES_MUTATED": "NO",
        "CURSOR_PRESERVED": "YES",
        "FOUR_OWNER_DIGESTS_MATCH": "YES",
        "NEW_FULL_DIGEST": overlay["FULL_DIGEST_AFTER"],
        "NEW_BOUNDS_DIGEST": overlay["BOUNDS_DIGEST_AFTER"],
        "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST": overlay[
            "EXPECTED_BOUND_ONLY_BOUNDS_DIGEST"
        ],
        "FAMILY_BEFORE": family_before,
        "FAMILY_AFTER": family_after,
        "FAMILY_DELTA_FROM_NINE": NINE_EVENT_FAMILY_BOUND
        - family_after["FAMILY_BOUND"],
        "FAMILY_DELTA_FROM_FROZEN": FROZEN_FAMILY_BOUND - family_after["FAMILY_BOUND"],
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": resolved_above_incumbent,
        "UNRESOLVED_CURSOR": {
            "PROFILE_COUNT": nine_result["UNRESOLVED_CURSOR"]["PROFILE_COUNT"],
            "STATUS": nine_result["UNRESOLVED_CURSOR"]["STATUS"],
            "ID": CURSOR_ID,
            "BOUND": CURSOR_BOUND,
        },
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CAVEATS": caveats,
        "HISTORICAL_AUTHORITY_CAVEATS": {
            "NB_CERTIFICATES_1444": {
                "STATUS": "UNRESOLVED_LOCATOR_PRESERVED",
                "SOURCE_LOCATOR": (
                    "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:"
                    "NB_CERTIFICATES[1444]"
                ),
                "FROZEN_HISTORY_REWRITTEN": "NO",
            },
            "MUTATION_RAW_LOGS": {"STATUS": "NOT_OBTAINED"},
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
        previous = json_object(path.read_bytes(), "existing result artifact is invalid JSON")
        require(
            previous.get("TASK_ID") == TASK_ID,
            "refusing to overwrite a different result artifact",
        )
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
