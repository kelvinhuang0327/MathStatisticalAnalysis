"""Focused acceptance tests for the combined 28-event family integration."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from lottolab.research import b649_combined_28_event_class197_local_integration_r1 as integration


@pytest.fixture(scope="module")
def replay() -> Iterator[
    tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ]
]:
    yield integration.build_candidate()


def test_fixed_identities_and_complete_event_ledger(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen, base_rows, after_rows = replay
    gates = result["AUTHORITY_GATES"]
    assert gates["BASE_HEAD_TREE"] == "MATCH"
    assert gates["BASE_RESULT_SHA256"] == "MATCH"
    assert gates["T227_CANDIDATE_HEAD_TREE"] == "MATCH"
    assert gates["T227_PROOF_LOCATOR"] == "RESOLVED"
    assert gates["CLASS_CANDIDATE_HEAD_TREE"] == "MATCH"
    assert gates["CLASS_ID_SET"] == "EXACT_MATCH"
    assert gates["CLASS_SCIENCE_JUDGE_BINDING"] == "VERIFIED_WITH_CAVEATS"
    assert result["BASE"]["HEAD"] == integration.BASE_HEAD
    assert result["BASE"]["TREE"] == integration.BASE_TREE
    assert result["BASE"]["RESULT_SHA256"] == integration.BASE_RESULT_SHA256
    assert result["ROWS_BEFORE"] == result["ROWS_AFTER"] == integration.BASE_ROWS
    assert result["EVENTS_BEFORE"] == integration.BASE_EVENTS
    assert result["NEW_RESOLVED_EVENTS"] == 1
    assert result["EVENTS_AFTER"] == 28
    assert result["CHANGED_ROWS_FROM_BASE"] == 1
    assert result["UNCHANGED_ROWS_FROM_BASE"] == 4_646
    assert result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"] == 27
    assert result["UNCHANGED_ROWS_FROM_FROZEN"] == 4_620
    assert len(base_rows) == len(after_rows) == 4_647
    events = result["EVENT_HISTORY"]
    assert len(events) == 28
    assert len({event["EVENT_ID"] for event in events[:27]}) == 27
    assert events[-1]["EVENT_ID"] == integration.T227_DONOR_EVENT_ID
    assert all(event["EVENT_ID"] != "UNRESOLVED_CLASS_CERTIFICATE" for event in events)
    transitions = result["EVENT_FAMILY_TRANSITIONS"]
    assert transitions[-1]["EVENT_ID"] == integration.T227_DONOR_EVENT_ID
    assert transitions[-1]["FAMILY_BOUND_BEFORE"] == transitions[-1]["FAMILY_BOUND_AFTER"]


def test_t227_delta_and_full_family_recount(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen, base_rows, after_rows = replay
    assert result["T227"] == {
        "PROFILE_ID": integration.T227_PROFILE_ID,
        "OLD_CAP": 265,
        "NEW_CAP": 227,
        "OLD_BOUND": 313_392_128,
        "NEW_BOUND": 313_051_572,
        "OWNER_DELTA": 340_556,
        "EVENT_ID": integration.T227_DONOR_EVENT_ID,
    }
    assert {
        profile_id for profile_id in base_rows if base_rows[profile_id] != after_rows[profile_id]
    } == {integration.T227_PROFILE_ID}
    assert result["FAMILY_BOUND_BEFORE"] == 313_394_584
    assert result["FAMILY_BOUND_AFTER_T227_WITH_OLD_CURSOR"] == 313_394_584
    assert result["FAMILY_BOUND_AFTER"] == 313_391_844
    assert result["FAMILY_GAIN_VS_27_EVENT_BASE"] == 2_740
    assert result["FAMILY_GAIN_VS_FROZEN_SEVEN_ROW"] == 6_688
    assert result["MAX_RESOLVED_BOUND"] == 313_391_844
    assert result["MAX_RESOLVED_OWNERS"] == [
        "65555555555531100000",
        "66555555554441100000",
        "66555555555422100000",
    ]
    assert result["NEXT_DISTINCT_RESOLVED_BOUND"] == 313_391_740
    assert result["NEXT_DISTINCT_RESOLVED_OWNERS"] == [
        "66655555555331100000",
        "66655555555411110000",
    ]
    assert result["MAX_UNRESOLVED_CLASS_BOUND"] == 313_258_872
    assert result["NEXT_DISTINCT_BOUND"] == result["NEXT_DISTINCT_RESOLVED_BOUND"]
    assert result["GAP_TO_INCUMBENT"] == 127_956
    assert result["T227_FAMILY_GAIN_WITH_OLD_CURSOR"] == 0
    assert result["CLASS_INTEGRATION_TRANSITION"]["FAMILY_GAIN"] == 2_740


def test_class_bound_is_independent_of_resolved_row_events(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen, _base_rows, after_rows = replay
    class_summary = result["CLASS"]
    assert class_summary["COUNT"] == 197
    assert class_summary["ID_SET_SHA256"] == integration.CLASS_ID_SET_SHA256
    assert len(class_summary["PROFILE_IDS"]) == 197
    assert len(set(class_summary["PROFILE_IDS"])) == 197
    assert len(class_summary["PROFILE_BOUND_ROWS"]) == 197
    assert (
        max(row["CLASS_BOUND_AFTER"] for row in class_summary["PROFILE_BOUND_ROWS"]) == 313_258_872
    )
    assert class_summary["BOUND_BEFORE"] == 313_394_584
    assert class_summary["BOUND_AFTER"] == 313_258_872
    assert class_summary["BOUND_DELTA"] == 135_712
    assert class_summary["RESOLVED_ROW_EVENTS"] == 0
    assert class_summary["ORIGINAL_FOCUSED_TEST_EXIT_CODE"] is None
    assert class_summary["SUPPLEMENTAL_QA_RECEIPT"] == "11_PASSED_EXIT_0"
    assert len(after_rows) == 4_647


def test_full_and_bounds_digests_are_recomputed_from_final_rows(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen, _base_rows, after_rows = replay
    assert result["FULL_DIGEST"] == integration.twenty_seven.four.seven.two.full_digest(after_rows)
    assert result["BOUNDS_DIGEST"] == integration.twenty_seven.four.seven.two.bounds_digest(
        after_rows
    )
    assert result["FULL_DIGEST"] != result["BASE"]["FULL_DIGEST"]
    assert result["BOUNDS_DIGEST"] != result["BASE"]["BOUNDS_DIGEST"]


def test_historical_caveats_and_provenance_receipts_are_retained(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, *_ = replay
    caveats = result["INHERITED_CAVEATS"]
    assert caveats["HISTORICAL_22_EVENT_JUDGE"]["VERDICT"] == "REFUTED"
    assert caveats["HISTORICAL_22_EVENT_JUDGE"]["PRESERVED"] == "YES"
    historical_text = str(caveats["BASE_HISTORICAL_CAVEATS"])
    assert "NON_BLOCKING_FOR_T261_MATHEMATICS" in historical_text
    assert "TARGET_T_CAP=262" in historical_text
    assert (
        "NJ-01: Profile A source cap 266 from catalog, separate NB lemma gives 269"
        in historical_text
    )
    assert caveats["T227_PROCEDURAL_FINDING"]["ID"] == "RO-GIT-INDEX-001"
    class_qa = caveats["CLASS_ORIGINAL_QA_AND_SUPPLEMENTAL_RECEIPT"]
    assert class_qa["ORIGINAL_FOCUSED_TEST_EXIT_CODE"] is None
    assert class_qa["SUPPLEMENTAL_QA_RECEIPT"] == "11_PASSED_EXIT_0"
    assert class_qa["SUPPLEMENTAL_EXIT_CODE"] == 0
    assert class_qa["SUPPLEMENTAL_TESTS_PASSED"] == "11_PASSED"


def test_all_required_load_bearing_negative_controls_reject(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, *_ = replay
    cases = result["NEGATIVE_CASE_RESULTS"]
    expected = {
        "WRONG_27_EVENT_BASE",
        "WRONG_T227_DONOR_HEAD_TREE",
        "WRONG_T227_ORIGINAL_ROW_BOUND",
        "WRONG_T227_SCIENCE_PROOF",
        "WRONG_CLASS_DONOR",
        "WRONG_CLASS_ID_SET",
        "DUPLICATE_CLASS_ID",
        "DUPLICATE_T227_EVENT",
        "WRONG_EVENT_ANCESTRY",
        "UNRELATED_RESOLVED_ROW_MUTATION",
        "MISSING_UNRESOLVED_CLASS",
        "WRONG_OLD_CLASS_BOUND",
        "WRONG_NEW_CLASS_BOUND",
        "HISTORICAL_19_EVENT_FRONTIER",
        "WRONG_SOURCE_PROOF_LOCATOR",
    }
    assert set(cases) == expected
    for reason in cases.values():
        assert reason.startswith("REJECTED:")
        assert len(reason.split(":", maxsplit=2)[-1].strip()) > 0


def test_result_reports_self_check_only_and_no_publication(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, *_ = replay
    assert result["NEW_COMPOSITE_JUDGE"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["PUSH"] == "NOT_RUN"
    assert result["MERGE"] == "NOT_RUN"
    assert result["PR_CREATION"] == "NOT_RUN"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert result["VERIFICATION"]["POSTCOMMIT_REPLAY"] == "NOT_RUN_AT_COMMIT"
