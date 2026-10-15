"""Focused replay checks for the pinned T264 family-ledger integration."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from lottolab.research import b649_t264_23_event_local_family_integration_r1 as integration


@pytest.fixture(scope="module")
def replay() -> Iterator[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]]:
    result, frozen, base_rows, after_rows = integration.build_candidate()
    yield result, frozen, base_rows, after_rows


def test_exact_authorities_and_inherited_judge_state_are_preserved(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    assert result["AUTHORITY_GATES"] == {
        "FROZEN_HEAD_TREE": "MATCH",
        "SIX_ROW_RESULT_SHA256": "MATCH",
        "SEVEN_ROW_RESULT_SHA256": "MATCH",
        "BASE_HEAD_TREE": "MATCH",
        "BASE_RESULT_SHA256": "MATCH",
        "DONOR_HEAD_TREE": "MATCH",
        "DONOR_RESULT_SHA256": "MATCH",
        "DONOR_SOURCE_SHA256": "MATCH",
        "DONOR_TEST_SHA256": "MATCH",
        "DONOR_JUDGE_IDENTITY": "MATCH",
        "ALL_PROOF_LOCATORS": "RESOLVED",
    }
    base = result["BASE_22_EVENT_AUTHORITY"]
    assert (base["HEAD"], base["TREE"], base["PARENT"]) == (
        integration.BASE_HEAD,
        integration.BASE_TREE,
        integration.BASE_PARENT,
    )
    assert base["RESULT_SHA256"] == integration.BASE_RESULT_SHA256
    assert base["EVENTS"] == 22
    assert base["REPLAY_MATCH"] == "YES"
    assert result["INHERITED_22_EVENT_JUDGE"] == {
        "VERDICT": "REFUTED",
        "REASON": "POSTCOMMIT_HEAD_GUARD",
        "PRESERVED": "YES",
        "BASE_RESULT_SHA256": integration.BASE_RESULT_SHA256,
    }


def test_one_t264_event_changes_only_the_pinned_profile(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, frozen, base_rows, after_rows = replay
    assert (result["ROWS_BEFORE"], result["ROWS_AFTER"]) == (4_647, 4_647)
    assert result["OLD_EVENTS"] == 22
    assert (result["PREVIOUS_EVENTS"], result["NEW_EVENTS"], result["TOTAL_EVENTS"]) == (
        22,
        1,
        23,
    )
    assert (
        result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"],
        result["UNCHANGED_ROWS_FROM_FROZEN"],
        result["CHANGED_ROWS_FROM_BASE"],
        result["UNCHANGED_ROWS_FROM_BASE"],
    ) == (22, 4_625, 1, 4_646)
    assert set(frozen) == set(base_rows) == set(after_rows)
    expected_changed = {
        profile_id for profile_id, row in frozen.items() if row != after_rows[profile_id]
    }
    assert set(result["CHANGED_PROFILE_IDS_FROM_FROZEN"]) == expected_changed
    assert integration.PROFILE_ID in expected_changed

    event = result["EVENT_HISTORY"][-1]
    donor = result["DONOR_IDENTITY"]
    assert (event["EVENT_ID"], event["PROFILE_ID"]) == (
        integration.DONOR_EVENT_ID,
        integration.PROFILE_ID,
    )
    assert (event["BOUND_BEFORE"], event["BOUND_AFTER"]) == (313_392_128, 313_382_972)
    assert (event["CAP_BEFORE"], event["CAP_AFTER"]) == (265, 264)
    assert (event["S4_BASE_BEFORE"], event["S4_BASE_AFTER"]) == (112, 112)
    assert event["SOURCE_AFTER"] == donor["PROOF_LOCATOR"]
    assert after_rows[integration.PROFILE_ID].source == donor["PROOF_LOCATOR"]
    assert after_rows[integration.PROFILE_ID].bound == 313_382_972
    assert result["ALL_PROOF_LOCATORS_RESOLVED"] == "YES"
    assert result["SOURCE_METADATA_BINDINGS"] == "VERIFIED"
    assert result["UNRELATED_ROW_MUTATION"] == "NONE"


def test_donor_and_fresh_judge_snapshots_bind_the_same_proof(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    donor = result["DONOR_IDENTITY"]
    judge = donor["FRESH_CONTEXT_JUDGE"]
    assert (donor["HEAD"], donor["TREE"], donor["PARENT"]) == (
        integration.DONOR_HEAD,
        integration.DONOR_TREE,
        integration.FROZEN_HEAD,
    )
    assert donor["RESULT_SHA256"] == integration.DONOR_RESULT_SHA256
    assert donor["SOURCE_SHA256"] == integration.DONOR_SOURCE_SHA256
    assert donor["TEST_SHA256"] == integration.DONOR_TEST_SHA256
    assert donor["PROOF_SCOPE"] == "FULL_PROFILE"
    assert donor["WORKER_JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert donor["PROOF_LOCATOR"].startswith(
        f"git:{integration.DONOR_HEAD}@{integration.DONOR_TREE}:"
    )
    assert donor["PROOF_LOCATOR"].endswith(f"#PROOF:sha256={donor['PROOF_SHA256']}")
    assert judge["THREAD_ID"] == integration.JUDGE_THREAD_ID
    assert judge["SESSION_ID"] == integration.JUDGE_SESSION_ID
    assert judge["JUDGE_MODE"] == "FRESH_CONTEXT"
    assert judge["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert judge["REVIEWED_HEAD"] == integration.DONOR_HEAD
    assert judge["REVIEWED_TREE"] == integration.DONOR_TREE
    assert judge["DONOR_RESULT_SHA256"] == integration.DONOR_RESULT_SHA256
    assert judge["FINAL_MESSAGE_SHA256"] == integration.JUDGE_FINAL_MESSAGE_SHA256


def test_science_accounting_keeps_scalar_and_configuration_units_distinct(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    science = result["T264_SCIENCE"]
    assert science["PROFILE_ID"] == integration.PROFILE_ID
    assert science["PROVED_T_CAP"] == 264
    assert science["OWNER_DELTA"] == 9_156
    assert science["SCALAR_ACCOUNTING"] == integration.SCALAR_ACCOUNTING
    assert science["CONFIGURATION_ACCOUNTING"] == integration.CONFIGURATION_ACCOUNTING
    assert science["SCALAR_ACCOUNTING"]["REMAINING_SCALAR_STATES"] == 74
    assert science["CONFIGURATION_ACCOUNTING"]["EXPANDED_CRITICAL_CONFIGURATIONS"] == 20
    assert science["COUNT_UNITS_NOT_MIXED"] == "YES"
    assert science["JUDGE_CAVEAT"] == integration.JUDGE_CAVEAT
    assert science["CAVEAT_IMPACT"] == "NON_BLOCKING_FOR_T264_MATHEMATICS"
    assert result["UNADOPTED_197_PROFILE_CLASS_BOUND"] == "NOT_INTEGRATED"
    assert result["FORMAL_AUTHORITY_ACCEPTANCE"] == "NOT_CLAIMED"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["NEW_WINNING_OUTCOMES"] == 0


def test_family_frontier_and_cursor_are_unchanged(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, base_rows, after_rows = replay
    assert result["FAMILY_BOUND_BEFORE"] == result["FAMILY_BOUND_AFTER"] == 313_394_584
    assert result["FAMILY_GAIN"] == 0
    assert result["OWNER_DELTA"] == 9_156
    assert result["MAX_OWNER"] == integration.CURSOR_ID
    assert result["MAX_OWNER_TYPE"] == "UNRESOLVED_CURSOR"
    assert result["CURSOR_AUTHORITY"]["BOUND"] == 313_394_584
    assert result["CURSOR_AUTHORITY"]["COUNT"] == 197
    assert result["CURSOR_INCLUDED"] == "YES"
    assert result["NEXT_DISTINCT_BOUND"] == 313_392_308
    assert result["NEXT_COMPETING_OWNERS"] == ["66665555555421000000"]
    assert result["RESOLVED_PROFILES_ABOVE_INCUMBENT"] == 1_364
    assert integration.four.seven.two.full_digest(base_rows) == integration.BASE_FULL_DIGEST
    assert result["FULL_DIGEST"] == integration.four.seven.two.full_digest(after_rows)
    assert result["BOUNDS_DIGEST"] == integration.four.seven.two.bounds_digest(after_rows)


def test_all_negative_integration_controls_reject_mutated_inputs(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    expected = {
        "WRONG_DONOR_SHA_REJECTED",
        "WRONG_PROFILE_REJECTED",
        "WRONG_CAP_REJECTED",
        "WRONG_BOUND_REJECTED",
        "WRONG_PROOF_REJECTED",
        "UNRELATED_ROW_CHANGE_REJECTED",
        "CURSOR_OMISSION_REJECTED",
        "INCORRECT_SCALAR_ACCOUNTING_REJECTED",
        "WRONG_BASE_PROVENANCE_REJECTED",
    }
    assert set(result["NEGATIVE_VALIDATIONS"]) == expected
    assert set(result["NEGATIVE_VALIDATIONS"].values()) == {"PASS"}


def test_result_json_is_the_exact_replay_and_external_actions_remain_unrun(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    path = integration.ROOT / integration.RESULT_PATH
    assert path.read_bytes() == integration.serialize_result(result)
    assert result["PUSH"] == "NOT_RUN"
    assert result["PR"] == "NOT_RUN"
    assert result["MERGE"] == "NOT_RUN"
    assert result["PRODUCTION_MUTATION"] == "NONE"
