"""Focused acceptance and negative tests for the four-donor Family replay."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from lottolab.research import b649_certified_four_donor_family_replay_r1 as replay


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return replay.compute_result()


def rejected(candidate: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        replay.verify_result(candidate)


def test_four_donors_replay_to_expected_family_projection(result: dict[str, Any]) -> None:
    replay.verify_result(result)
    assert result["BASE"]["FAMILY_UB"] == 313391636
    assert result["FAMILY_AFTER"] == {
        "FAMILY_UB": 313389300,
        "ALL_OWNER_IDS": ["65555555555433000000"],
        "NEXT_DISTINCT_BOUND": 313388988,
        "NEXT_DISTINCT_OWNER_IDS": ["66666555544431000000"],
        "STILL_OPEN_PROFILES": 1513,
        "TOTAL_PROFILES": 4844,
        "RESOLVED_ROWS": 4647,
        "CURSOR_PROFILES": 197,
    }
    assert result["FAMILY_GAIN_FROM_BASE"] == 2336
    assert result["INDEPENDENT_REPLAY"]["MATCH"] is True


def test_only_four_resolved_rows_change_and_cursor_is_identical(result: dict[str, Any]) -> None:
    ledger = result["RESOLVED_LEDGER"]
    assert ledger["UPDATED_PROFILE_BOUNDS"] == {
        "66665555555321100000": 313329096,
        "65555555555432100000": 313122700,
        "65555555555511111000": 313364480,
        "55555555555443000000": 312835000,
    }
    assert ledger["UPDATED_ROWS"] == 4
    assert ledger["UNCHANGED_ROWS"] == 4643
    assert result["CURSOR"]["PROFILE_COUNT"] == 197
    assert result["CURSOR"]["UNCHANGED"] is True
    assert len(result["CURSOR"]["SOURCE_CURSOR"]["PROFILE_IDS"]) == 197


def test_all_four_donor_identities_and_judges_are_retained(result: dict[str, Any]) -> None:
    donors = result["DONORS"]
    assert [donor["DONOR"] for donor in donors] == ["T257", "T237", "W821_R2", "T208"]
    assert [donor["PROFILE"] for donor in donors] == [
        "66665555555321100000",
        "65555555555432100000",
        "65555555555511111000",
        "55555555555443000000",
    ]
    assert [donor["CERTIFIED_BOUND"] for donor in donors] == [
        313329096,
        313122700,
        313364480,
        312835000,
    ]
    assert all(donor["JUDGE"]["VERDICT"] == "VERIFIED_WITH_CAVEATS" for donor in donors)
    assert all(donor["JUDGE"]["JUDGE_MODE"] == "FRESH_CONTEXT" for donor in donors)
    assert (
        result["DONORS"][2]["INHERITED_CAVEATS_AND_DISPOSITIONS"]["INHERITED_EXCLUSION"][
            "RECERTIFIED_THIS_ROUND"
        ]
        is False
    )
    assert (
        result["DONORS"][3]["JUDGE"]["ORIGINAL_RESEARCH_CONVERSATION_ID"] == "UNKNOWN_NOT_VERIFIED"
    )


def test_wrong_base_sha_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["BASE"]["RESULT_SHA256"] = "0" * 64
    rejected(candidate)


def test_wrong_t237_committed_tree_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["DONORS"][1]["CERTIFIED_TREE"] = "0" * 40
    rejected(candidate)


def test_wrong_t237_result_sha_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["DONORS"][1]["RESULT_SHA256"] = "0" * 64
    rejected(candidate)


def test_wrong_t208_exact_identity_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["DONORS"][3]["PROFILE"] = "55555555555443000001"
    rejected(candidate)


def test_wrong_w821_judge_candidate_binding_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["DONORS"][2]["JUDGE"]["REVIEWED_TREE"] = "0" * 40
    rejected(candidate)


def test_duplicate_resolved_profile_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        replay.parse_json(b'{"RESOLVED_ROW_BOUNDS":{"profile":1,"profile":2}}', "duplicate test")


def test_missing_resolved_profile_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["RESOLVED_LEDGER"]["ROW_BOUNDS"].pop("44444444444433333300")
    rejected(candidate)


def test_missing_cursor_profile_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    cursor = candidate["CURSOR"]
    profile = cursor["SOURCE_CURSOR"]["PROFILE_IDS"].pop()
    cursor["PROFILE_BOUNDS"].pop(profile)
    rejected(candidate)


def test_cursor_bound_mutation_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    profile = next(iter(candidate["CURSOR"]["PROFILE_BOUNDS"]))
    candidate["CURSOR"]["PROFILE_BOUNDS"][profile] += 1
    rejected(candidate)


def test_wrong_donor_profile_assignment_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["DONORS"][0]["PROFILE"] = "65555555555432100000"
    rejected(candidate)


def test_donor_bound_increase_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["DONORS"][2]["CERTIFIED_BOUND"] += 1
    rejected(candidate)


def test_unauthorized_fifth_profile_update_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    ledger = candidate["RESOLVED_LEDGER"]
    profile = next(
        key for key in ledger["ROW_BOUNDS"] if key not in ledger["UPDATED_PROFILE_BOUNDS"]
    )
    ledger["ROW_BOUNDS"][profile] += 1
    ledger["UPDATED_PROFILE_BOUNDS"][profile] = ledger["ROW_BOUNDS"][profile]
    ledger["UPDATED_ROWS"] += 1
    ledger["UNCHANGED_ROWS"] -= 1
    rejected(candidate)


def test_family_summary_keeps_every_tied_owner_and_verifier_rejects_omission(
    result: dict[str, Any],
) -> None:
    synthetic = replay.family_summary({"owner-a": 10, "owner-b": 10, "next": 9}, {"cursor": 8}, 0)
    assert synthetic["ALL_OWNER_IDS"] == ["owner-a", "owner-b"]
    assert synthetic["NEXT_DISTINCT_BOUND"] == 9
    assert synthetic["NEXT_DISTINCT_OWNER_IDS"] == ["next"]
    candidate = deepcopy(result)
    candidate["FAMILY_AFTER"]["ALL_OWNER_IDS"] = []
    rejected(candidate)


def test_wrong_next_distinct_bound_is_rejected(result: dict[str, Any]) -> None:
    candidate = deepcopy(result)
    candidate["FAMILY_AFTER"]["NEXT_DISTINCT_BOUND"] += 1
    rejected(candidate)
