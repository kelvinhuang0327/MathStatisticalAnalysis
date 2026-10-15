"""Focused tests for the 24-event local B649 family integration."""

from __future__ import annotations

from typing import Any

import pytest

from lottolab.research import b649_t261_24_event_local_family_integration_r1 as integration


@pytest.fixture(scope="module")
def replay() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return integration.build_candidate()


def test_authorities_and_gates_match_pinned_identities(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    assert result["AUTHORITY_GATES"] == {
        "FROZEN_HEAD_TREE": "MATCH",
        "SIX_ROW_RESULT_SHA256": "MATCH",
        "SEVEN_ROW_RESULT_SHA256": "MATCH",
        "BASE_HEAD_TREE": "MATCH",
        "BASE_RESULT_SHA256": "MATCH",
        "BASE_FULL_DIGEST": "MATCH",
        "BASE_BOUNDS_DIGEST": "MATCH",
        "DONOR_HEAD_TREE": "MATCH",
        "DONOR_PARENT": "MATCH",
        "DONOR_RESULT_FILE_SHA256": "MATCH",
        "DONOR_RESULT_PAYLOAD_SHA256": "MATCH",
        "DONOR_SOURCE_SHA256": "MATCH",
        "DONOR_TEST_SHA256": "MATCH",
        "DONOR_JUDGE_REPORT_SHA256": "MATCH",
        "DONOR_JUDGE_IDENTITY": "MATCH",
        "ALL_PROOF_LOCATORS": "RESOLVED",
    }
    base = result["BASE_23_EVENT_AUTHORITY"]
    assert (base["HEAD"], base["TREE"], base["PARENT"]) == (
        integration.BASE_HEAD,
        integration.BASE_TREE,
        integration.BASE_PARENT,
    )
    assert base["RESULT_SHA256"] == integration.BASE_RESULT_SHA256
    assert base["EVENTS"] == 23
    assert base["REPLAY_MATCH"] == "YES"
    assert result["INHERITED_22_EVENT_JUDGE"] == {
        "VERDICT": "REFUTED",
        "REASON": "POSTCOMMIT_HEAD_GUARD",
        "PRESERVED": "YES",
        "BASE_RESULT_SHA256": integration.twenty_three.BASE_RESULT_SHA256,
    }
    assert result["UPSTREAM_23_EVENT_JUDGE"]["VERDICT"] == "SELF_CHECK_ONLY"
    assert result["UPSTREAM_23_EVENT_JUDGE"]["HEAD"] == integration.BASE_HEAD
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"


def test_one_t261_event_changes_only_the_pinned_profile(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, frozen, base_rows, after_rows = replay
    assert (result["ROWS_BEFORE"], result["ROWS_AFTER"]) == (4_647, 4_647)
    assert result["OLD_EVENTS"] == 23
    assert (result["PREVIOUS_EVENTS"], result["NEW_EVENTS"], result["TOTAL_EVENTS"]) == (
        23,
        1,
        24,
    )
    assert (
        result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"],
        result["UNCHANGED_ROWS_FROM_FROZEN"],
        result["CHANGED_ROWS_FROM_BASE"],
        result["UNCHANGED_ROWS_FROM_BASE"],
    ) == (23, 4_624, 1, 4_646)
    assert set(frozen) == set(base_rows) == set(after_rows)
    expected_changed = {
        profile_id for profile_id in frozen if frozen[profile_id] != after_rows[profile_id]
    }
    assert set(result["CHANGED_PROFILE_IDS_FROM_FROZEN"]) == expected_changed
    assert integration.PROFILE_ID in expected_changed

    event = result["EVENT_HISTORY"][-1]
    donor = result["DONOR_IDENTITY"]
    assert (event["EVENT_ID"], event["PROFILE_ID"]) == (
        integration.DONOR_EVENT_ID,
        integration.PROFILE_ID,
    )
    assert (event["BOUND_BEFORE"], event["BOUND_AFTER"]) == (313_392_308, 313_374_384)
    assert (event["CAP_BEFORE"], event["CAP_AFTER"]) == (264, 261)
    assert (event["S4_BASE_BEFORE"], event["S4_BASE_AFTER"]) == (112, 112)
    assert event["SOURCE_AFTER"] == donor["PROOF_LOCATOR"]
    assert after_rows[integration.PROFILE_ID].source == donor["PROOF_LOCATOR"]
    assert after_rows[integration.PROFILE_ID].bound == 313_374_384
    assert after_rows[integration.PROFILE_ID].cap == 261
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
    assert donor["RESULT_FILE_SHA256"] == integration.DONOR_RESULT_FILE_SHA256
    assert donor["RESULT_PAYLOAD_SHA256"] == integration.DONOR_RESULT_PAYLOAD_SHA256
    assert donor["SOURCE_SHA256"] == integration.DONOR_SOURCE_SHA256
    assert donor["TEST_SHA256"] == integration.DONOR_TEST_SHA256
    assert donor["PROOF_SCOPE"] == "FULL_PROFILE"
    assert donor["WORKER_JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert donor["PROOF_LOCATOR"].startswith(
        f"git:{integration.DONOR_HEAD}@{integration.DONOR_TREE}:"
    )
    assert donor["PROOF_LOCATOR"].endswith(f"#PROOF:sha256={donor['PROOF_SHA256']}")
    assert judge["TASK_ID"] == integration.JUDGE_TASK_ID
    assert judge["SESSION_ID"] == integration.JUDGE_SESSION_ID
    assert judge["JUDGE_MODE"] == "FRESH_CONTEXT"
    assert judge["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert judge["REVIEWED_HEAD"] == integration.DONOR_HEAD
    assert judge["REVIEWED_TREE"] == integration.DONOR_TREE
    assert judge["DONOR_RESULT_SHA256"] == integration.DONOR_RESULT_FILE_SHA256
    assert judge["DONOR_RESULT_PAYLOAD_SHA256"] == integration.DONOR_RESULT_PAYLOAD_SHA256
    assert judge["REPORT_SHA256"] == integration.JUDGE_REPORT_SHA256


def test_science_accounting_and_provenance_preserved(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    science = result["T261_SCIENCE"]
    assert science["PROFILE_ID"] == integration.PROFILE_ID
    assert science["PROVED_T_CAP"] == 261
    assert science["OWNER_DELTA"] == 17_924
    assert science["T_H_LOWER_BOUND"] == 38
    assert science["R_UPPER_BOUND"] == 46
    assert science["ROUTE_B_TERM_COUNT"] == 240
    assert science["ARGMAX_T"] == 261
    assert science["T261_ATTAINMENT"] == "NOT_CLAIMED"
    assert science["JUDGE_CAVEAT"] == integration.JUDGE_CAVEAT
    assert science["CAVEAT_IMPACT"] == "NON_BLOCKING_FOR_T261_MATHEMATICS"
    assert result["T261_SEALED_CERTIFICATE"] == "VERIFIED_WITH_CAVEATS"
    assert result["UNADOPTED_197_PROFILE_CLASS_BOUND"] == "NOT_INTEGRATED"
    assert result["FORMAL_AUTHORITY_ACCEPTANCE"] == "NOT_CLAIMED"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["NEW_WINNING_OUTCOMES"] == 0


def test_family_frontier_and_cursor_are_preserved(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, base_rows, after_rows = replay
    assert result["FAMILY_BOUND_BEFORE"] == result["FAMILY_BOUND_AFTER"] == 313_394_584
    assert result["FAMILY_GAIN"] == 0
    assert result["OWNER_DELTA"] == 17_924
    assert result["MAX_OWNER"] == integration.CURSOR_ID
    assert result["MAX_OWNER_TYPE"] == "UNRESOLVED_CURSOR"
    assert result["CURSOR_AUTHORITY"]["BOUND"] == 313_394_584
    assert result["CURSOR_AUTHORITY"]["COUNT"] == 197
    assert result["CURSOR_INCLUDED"] == "YES"
    assert result["NEXT_DISTINCT_BOUND"] == 313_392_232
    assert result["NEXT_COMPETING_OWNERS"] == [
        "65555555555442000000",
        "66555555554433000000",
    ]
    assert result["NEXT_DISTINCT_RESOLVED_BOUND"] == 313_392_232
    assert result["NEXT_DISTINCT_RESOLVED_OWNERS"] == [
        "65555555555442000000",
        "66555555554433000000",
    ]
    assert result["RESOLVED_PROFILES_ABOVE_INCUMBENT"] == 1_364
    assert integration.four.seven.two.full_digest(base_rows) == integration.BASE_FULL_DIGEST
    assert result["FULL_DIGEST"] == integration.four.seven.two.full_digest(after_rows)
    assert result["BOUNDS_DIGEST"] == integration.four.seven.two.bounds_digest(after_rows)
    assert (
        result["FULL_DIGEST"] == "3d5d699f1186f0792329d1b4b85ae0e2f9ea9fdb8b3ca00826de6ce13eb4b67b"
    )
    assert (
        result["BOUNDS_DIGEST"]
        == "b3f24bc6032485f0cd52eff45e2d26eef0da34eedfd6b81701f6c47a8ad0a2e9"
    )


def test_all_negative_integration_controls_reject_mutated_inputs(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    expected = {
        "WRONG_BASE_REJECTED",
        "WRONG_DONOR_COMMIT_REJECTED",
        "WRONG_DONOR_TREE_REJECTED",
        "WRONG_DONOR_RESULT_SHA_REJECTED",
        "WRONG_PROFILE_REJECTED",
        "WRONG_CAP_REJECTED",
        "WRONG_BOUND_REJECTED",
        "WRONG_PROOF_REJECTED",
        "WRONG_PROOF_LOCATOR_REJECTED",
        "DUPLICATE_EVENT_REJECTED",
        "UNRELATED_ROW_MUTATION_REJECTED",
        "CURSOR_OMISSION_REJECTED",
        "WRONG_ANCESTRY_REJECTED",
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
