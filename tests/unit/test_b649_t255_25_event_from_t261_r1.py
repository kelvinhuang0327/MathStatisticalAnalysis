"""Focused tests for the 25-event local B649 family integration."""

from __future__ import annotations

from typing import Any

import pytest

from lottolab.research import b649_t255_25_event_from_t261_r1 as integration


@pytest.fixture(scope="module")
def replay() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return integration.build_candidate()


def test_pinned_base_donor_and_judge_identities_match(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    base = result["BASE_24_EVENT_AUTHORITY"]
    assert (base["HEAD"], base["TREE"], base["PARENT"]) == (
        integration.BASE_HEAD,
        integration.BASE_TREE,
        integration.BASE_PARENT,
    )
    assert base["RESULT_SHA256"] == integration.BASE_RESULT_SHA256
    assert base["EVENTS"] == 24
    assert base["REPLAY_MATCH"] == "YES"
    assert base["FULL_DIGEST"] == integration.BASE_FULL_DIGEST
    assert base["BOUNDS_DIGEST"] == integration.BASE_BOUNDS_DIGEST
    donor = result["DONOR_IDENTITY"]
    assert (donor["HEAD"], donor["TREE"], donor["PARENT"]) == (
        integration.DONOR_HEAD,
        integration.DONOR_TREE,
        integration.DONOR_PARENT,
    )
    assert donor["RESULT_SHA256"] == integration.DONOR_RESULT_SHA256
    assert donor["SOURCE_SHA256"] == integration.DONOR_SOURCE_SHA256
    assert donor["PROOF_SHA256"] == integration.DONOR_PROOF_SHA256
    assert donor["FRESH_CONTEXT_JUDGE"]["REPORT_SHA256"] == integration.JUDGE_REPORT_SHA256
    assert donor["FRESH_CONTEXT_JUDGE"]["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert result["AUTHORITY_GATES"]["DONOR_JUDGE_BINDING"] == "MATCH"
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"


def test_one_t255_event_changes_only_its_profile(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, frozen, base_rows, after_rows = replay
    assert (result["ROWS_BEFORE"], result["ROWS_AFTER"]) == (4_647, 4_647)
    assert (result["OLD_EVENTS"], result["PREVIOUS_EVENTS"], result["NEW_EVENTS"]) == (24, 24, 1)
    assert result["TOTAL_EVENTS"] == 25
    assert (
        result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"],
        result["UNCHANGED_ROWS_FROM_FROZEN"],
        result["CHANGED_ROWS_FROM_BASE"],
        result["UNCHANGED_ROWS_FROM_BASE"],
    ) == (24, 4_623, 1, 4_646)
    changed_from_frozen = {
        profile_id for profile_id in frozen if frozen[profile_id] != after_rows[profile_id]
    }
    assert set(result["CHANGED_PROFILE_IDS_FROM_FROZEN"]) == changed_from_frozen
    assert integration.PROFILE_ID in changed_from_frozen
    assert set(base_rows) == set(after_rows) == set(frozen)

    before = base_rows[integration.PROFILE_ID]
    after = after_rows[integration.PROFILE_ID]
    event = result["EVENT_HISTORY"][-1]
    donor = result["DONOR_IDENTITY"]
    assert (event["EVENT_ID"], event["PROFILE_ID"]) == (
        integration.DONOR_EVENT_ID,
        integration.PROFILE_ID,
    )
    assert (before.cap, after.cap, before.bound, after.bound) == (
        264,
        255,
        313_391_920,
        313_320_224,
    )
    assert (after.cap, after.bound, after.s4_base) == (255, 313_320_224, 112)
    assert event["SOURCE_AFTER"] == donor["ROW_SOURCE"] == after.source
    assert f"RESULT_SHA256={integration.DONOR_RESULT_SHA256}" in after.source
    assert f"JUDGE_REPORT_SHA256={integration.JUDGE_REPORT_SHA256}" in after.source
    assert after.source.endswith(f"#PROOF:sha256={integration.DONOR_PROOF_SHA256}")
    assert result["OWNER_DELTA"] == 71_696
    assert result["T255_ATTAINMENT"] == "NOT_CLAIMED"
    assert result["METADATA_CAVEAT"] == "TARGET_T_CAP=262; PROVED_T_CAP=255; SOURCE_T_CAP=264"


def test_recomputed_digests_and_family_frontier_preserve_cursor(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, base_rows, after_rows = replay
    assert result["FULL_DIGEST"] == integration.four.seven.two.full_digest(after_rows)
    assert result["BOUNDS_DIGEST"] == integration.four.seven.two.bounds_digest(after_rows)
    assert result["FULL_DIGEST"] == (
        "aea35e031ad93a75ba499173e0810db421e76bb95181e58ebe1ac9e808ac2010"
    )
    assert result["BOUNDS_DIGEST"] == (
        "429bdb7937db7d5b8e5656a2dd0362b3c678fb4526d29978ef2dc8f45acdd611"
    )
    assert result["FAMILY_BOUND_BEFORE"] == result["FAMILY_BOUND_AFTER"] == 313_394_584
    assert result["FAMILY_GAIN"] == 0
    assert result["MAXIMIZING_OWNERS"] == ["66544333333333332222"]
    assert result["MAX_OWNER_TYPE"] == "UNRESOLVED_CURSOR"
    assert result["CURSOR_AUTHORITY"]["BOUND"] == 313_394_584
    assert result["CURSOR_AUTHORITY"]["COUNT"] == 197
    assert result["CURSOR_INCLUDED"] == "YES"
    assert result["UNADOPTED_197_PROFILE_CLASS_BOUND"] == "NOT_INTEGRATED"
    assert result["NEXT_DISTINCT_RESOLVED_BOUND"] == 313_392_232
    assert result["NEXT_DISTINCT_RESOLVED_OWNERS"] == [
        "65555555555442000000",
        "66555555554433000000",
    ]
    assert result["RESOLVED_PROFILES_ABOVE_INCUMBENT"] == 1_364
    assert integration.four.seven.two.full_digest(base_rows) == integration.BASE_FULL_DIGEST


def test_all_required_negative_controls_reject_the_mutation(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    expected = {
        "WRONG_BASE_REJECTED",
        "WRONG_DONOR_REJECTED",
        "WRONG_DONOR_TREE_REJECTED",
        "WRONG_DONOR_RESULT_SHA_REJECTED",
        "WRONG_PROFILE_REJECTED",
        "WRONG_CAP_REJECTED",
        "WRONG_BOUND_REJECTED",
        "WRONG_PROOF_REJECTED",
        "WRONG_PROOF_LOCATOR_REJECTED",
        "DUPLICATE_EVENT_REJECTED",
        "UNRELATED_ROW_CHANGE_REJECTED",
        "CURSOR_OMISSION_REJECTED",
        "WRONG_ANCESTRY_REJECTED",
        "WRONG_BASE_RESULT_SHA_REJECTED",
        "UNRELATED_BASE_ROW_CHANGE_REJECTED",
    }
    assert set(result["NEGATIVE_VALIDATIONS"]) == expected
    assert set(result["NEGATIVE_VALIDATIONS"].values()) == {"PASS"}


def test_result_artifact_and_forbidden_actions_are_recorded_truthfully(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    path = integration.ROOT / integration.RESULT_PATH
    assert path.read_bytes() == integration.serialize_result(result)
    assert result["TASK_STATUS"] == "LOCAL_25_EVENT_CANDIDATE_REPLAYED"
    assert result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["FULL_SUITE"] == "NOT_RUN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PUSH"] == result["PR"] == result["MERGE"] == "NOT_RUN"
    assert result["PRODUCTION_MUTATION"] == "NONE"
