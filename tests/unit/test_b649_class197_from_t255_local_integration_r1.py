"""Focused unit tests for B649_CLASS197_FROM_T255_LOCAL_INTEGRATION_R1."""

from __future__ import annotations

from typing import Any

import pytest

from lottolab.research import b649_class197_from_t255_local_integration_r1 as integration


@pytest.fixture(scope="module")
def candidate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return integration.build_candidate()


def test_pinned_base_donor_and_judge_identities_match(
    candidate: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = candidate
    base_auth = result["BASE_25_EVENT_AUTHORITY"]
    assert (base_auth["HEAD"], base_auth["TREE"], base_auth["PARENT"]) == (
        integration.BASE_HEAD,
        integration.BASE_TREE,
        integration.BASE_PARENT,
    )
    assert base_auth["RESULT_SHA256"] == integration.BASE_RESULT_SHA256
    assert base_auth["EVENTS"] == 25
    assert base_auth["REPLAY_MATCH"] == "YES"
    assert base_auth["FULL_DIGEST"] == integration.BASE_FULL_DIGEST
    assert base_auth["BOUNDS_DIGEST"] == integration.BASE_BOUNDS_DIGEST
    assert base_auth["FAMILY_BOUND"] == integration.BASE_FAMILY_BOUND
    assert base_auth["NEXT_RESOLVED_BOUND"] == integration.BASE_NEXT_RESOLVED_BOUND

    donor = result["DONOR_IDENTITY"]
    assert (donor["HEAD"], donor["TREE"], donor["PARENT"]) == (
        integration.DONOR_HEAD,
        integration.DONOR_TREE,
        integration.DONOR_PARENT,
    )
    assert donor["RESULT_SHA256"] == integration.DONOR_RESULT_SHA256
    assert donor["SOURCE_SHA256"] == integration.DONOR_SOURCE_SHA256
    assert donor["TEST_SHA256"] == integration.DONOR_TEST_SHA256
    assert donor["CLASS_COUNT"] == integration.CLASS_COUNT == 197
    assert donor["CLASS_ID_SET_SHA256"] == integration.CLASS_ID_SET_SHA256
    assert donor["PROOF_LOCATOR"] == integration.EXPECTED_DONOR_PROOF_LOCATOR
    assert donor["DONOR_FOCUSED_QA"] == "11_PASSED"
    assert donor["DONOR_FOCUSED_EXIT_CODE"] == 0
    assert donor["SCIENCE_JUDGE"]["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert donor["SCIENCE_JUDGE"]["SESSION_ID"] == integration.SCIENCE_JUDGE_SESSION

    assert result["AUTHORITY_GATES"]["BASE_HEAD_TREE"] == "MATCH"
    assert result["AUTHORITY_GATES"]["DONOR_HEAD_TREE"] == "MATCH"
    assert result["AUTHORITY_GATES"]["DONOR_QA_RECEIPT"] == "VERIFIED"
    assert result["AUTHORITY_GATES"]["DONOR_PROOF_LOCATOR"] == "RESOLVED"
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["FORMAL_FAMILY_ADOPTION"] == "NOT_ACCEPTED"


def test_class_integration_leaves_all_resolved_rows_and_history_unmutated(
    candidate: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, frozen, base_rows, after_rows = candidate
    assert (result["ROWS_BEFORE"], result["ROWS_AFTER"]) == (4_647, 4_647)
    assert result["RESOLVED_ROW_MUTATIONS"] == 0
    assert result["CHANGED_ROWS_FROM_BASE"] == 0
    assert result["UNCHANGED_ROWS_FROM_BASE"] == 4_647
    assert result["RESOLVED_HISTORY_EVENTS"] == 25
    assert (result["OLD_EVENTS"], result["PREVIOUS_EVENTS"], result["NEW_EVENTS"]) == (25, 25, 0)
    assert result["TOTAL_EVENTS"] == 25
    assert set(base_rows) == set(after_rows) == set(frozen)
    assert base_rows == after_rows

    assert result["FULL_DIGEST"] == integration.BASE_FULL_DIGEST
    assert result["BOUNDS_DIGEST"] == integration.BASE_BOUNDS_DIGEST
    assert result["NEW_FULL_DIGEST"] == integration.BASE_FULL_DIGEST
    assert result["NEW_BOUNDS_DIGEST"] == integration.BASE_BOUNDS_DIGEST
    assert result["FULL_DIGEST"] == integration.four.seven.two.full_digest(after_rows)
    assert result["BOUNDS_DIGEST"] == integration.four.seven.two.bounds_digest(after_rows)
    assert len(result["EVENT_HISTORY"]) == 25


def test_class_bound_replacement_and_recomputed_family_frontier(
    candidate: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = candidate
    assert result["CLASS_COUNT"] == 197
    assert result["OLD_CLASS_BOUND"] == 313_394_584
    assert result["NEW_CLASS_BOUND"] == 313_258_872
    assert result["CLASS_BOUND_DELTA"] == 135_712

    assert result["FAMILY_BOUND_BEFORE"] == 313_394_584
    assert result["FAMILY_BOUND_AFTER"] == 313_392_232
    assert result["FAMILY_GAIN"] == 2_352

    assert result["MAXIMIZING_OWNERS"] == ["65555555555442000000", "66555555554433000000"]
    assert result["MAX_OWNER"] == "65555555555442000000"
    assert result["MAX_OWNER_TYPE"] == "RESOLVED_ROWS"

    assert result["NEXT_DISTINCT_BOUND"] == 313_392_128
    assert result["NEXT_DISTINCT_RESOLVED_BOUND"] == 313_392_128
    assert result["NEXT_DISTINCT_RESOLVED_OWNERS"] == ["66655555554432000000"]
    assert result["NEXT_RESOLVED_BOUND"] == 313_392_128
    assert result["NEXT_RESOLVED_OWNERS"] == ["66655555554432000000"]

    cursor = result["CURSOR_AUTHORITY"]
    assert cursor["ID"] == integration.CURSOR_ID
    assert cursor["BOUND"] == 313_258_872
    assert cursor["PREVIOUS_BOUND"] == 313_394_584
    assert cursor["COUNT"] == 197
    assert cursor["STATUS"] == "LOCAL_CLASS197_BOUND_REPLACED"
    assert result["CURSOR_BOUND"] == 313_258_872
    assert result["CURSOR_COUNT"] == 197
    assert result["CURSOR_INCLUDED"] == "YES"
    assert result["UNADOPTED_197_PROFILE_CLASS_BOUND"] == 313_258_872

    transition = result["CLASS_INTEGRATION_TRANSITION"]
    assert transition["CLASS_COUNT"] == 197
    assert transition["CLASS_BOUND_BEFORE"] == 313_394_584
    assert transition["CLASS_BOUND_AFTER"] == 313_258_872
    assert transition["FAMILY_BOUND_BEFORE"] == 313_394_584
    assert transition["FAMILY_BOUND_AFTER"] == 313_392_232
    assert transition["FAMILY_GAIN"] == 2_352
    assert transition["TIED_OWNERS_BEFORE"] == [integration.CURSOR_ID]
    assert transition["TIED_OWNERS_AFTER"] == ["65555555555442000000", "66555555554433000000"]


def test_retained_baselines_remain_distinct_and_preserved(
    candidate: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = candidate
    baselines = result["RETAINED_BASELINES"]
    assert baselines["FROZEN_SEVEN_ROW_FAMILY"] == 313_398_532
    assert baselines["NINETEEN_EVENT_FAMILY"] == 313_394_584
    assert baselines["NINETEEN_EVENT_NEXT_RESOLVED"] == 313_392_516
    assert baselines["CURRENT_25_EVENT_FAMILY"] == 313_394_584
    assert baselines["CURRENT_25_EVENT_NEXT_RESOLVED"] == 313_392_232

    # Verify that the 19-event next resolved bound is NOT conflated with the 25-event frontier
    assert baselines["NINETEEN_EVENT_NEXT_RESOLVED"] != baselines["CURRENT_25_EVENT_NEXT_RESOLVED"]
    assert baselines["CURRENT_25_EVENT_NEXT_RESOLVED"] == 313_392_232
    assert baselines["NINETEEN_EVENT_NEXT_RESOLVED"] == 313_392_516


def test_all_mandatory_negative_controls_reject_mutation(
    candidate: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = candidate
    expected_keys = {
        "WRONG_CLASS_COUNT_REJECTED",
        "WRONG_CLASS_ID_SET_REJECTED",
        "DUPLICATE_CLASS_ID_REJECTED",
        "MISSING_CLASS_PROFILE_REJECTED",
        "WRONG_DONOR_RESULT_SHA_REJECTED",
        "WRONG_DONOR_SOURCE_SHA_REJECTED",
        "WRONG_DONOR_TEST_SHA_REJECTED",
        "WRONG_PROOF_LOCATOR_REJECTED",
        "WRONG_OLD_CLASS_BOUND_REJECTED",
        "WRONG_NEW_CLASS_BOUND_REJECTED",
        "RESOLVED_ROW_MUTATION_REJECTED",
        "WRONG_BASE_LEDGER_REJECTED",
        "HISTORICAL_19_EVENT_FRONTIER_REJECTED",
    }
    assert set(result["NEGATIVE_VALIDATIONS"]) == expected_keys
    assert set(result["NEGATIVE_VALIDATIONS"].values()) == {"PASS"}


def test_result_artifact_and_operational_constraints(
    candidate: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = candidate
    path = integration.ROOT / integration.RESULT_PATH
    assert path.read_bytes() == integration.serialize_result(result)
    assert result["TASK_STATUS"] == "LOCAL_CLASS197_INTEGRATED_CANDIDATE"
    assert result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["FULL_SUITE"] == "NOT_RUN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PUSH"] == result["PR"] == result["MERGE"] == "NOT_RUN"
    assert result["PRODUCTION_MUTATION"] == "NONE"
