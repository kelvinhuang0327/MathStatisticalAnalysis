"""Focused acceptance tests for the combined 31-event family integration."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from lottolab.research import b649_triple_t262_31_event_family_integration_r1 as integration


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
    result, _frozen_rows, base_rows, after_rows = replay
    gates = result["AUTHORITY_GATES"]
    assert gates["FROZEN_HEAD_TREE"] == "MATCH"
    assert gates["BASE_HEAD_TREE"] == "MATCH"
    assert gates["BASE_RESULT_SHA256"] == "MATCH"
    assert gates["BASE_FULL_DIGEST_REPLAY"] == "MATCH"
    assert gates["BASE_BOUNDS_DIGEST_REPLAY"] == "MATCH"
    assert gates["DONOR_HEAD_TREE"] == "MATCH"
    assert gates["DONOR_RESULT_SHA256"] == "MATCH"
    assert gates["DONOR_SOURCE_SHA256"] == "MATCH"
    assert gates["DONOR_TEST_SHA256"] == "MATCH"
    assert gates["DONOR_PROOF_DOCUMENT_SHA256"] == "MATCH"
    assert gates["ALL_PROFILE_PROOF_LOCATORS"] == "RESOLVED"
    assert gates["SCIENCE_JUDGE_REPORT_SHA256"] == "MATCH"
    assert gates["SCIENCE_JUDGE_BINDING"] == "MATCH"
    assert gates["CLASS_COUNT"] == "MATCH"
    assert gates["CLASS_ID_SET"] == "EXACT_MATCH"
    assert gates["CLASS_BOUND"] == "MATCH"
    assert gates["CLASS_MUTATIONS"] == 0

    assert result["BASE"]["HEAD"] == integration.BASE_HEAD
    assert result["BASE"]["TREE"] == integration.BASE_TREE
    assert result["BASE"]["RESULT_SHA256"] == integration.BASE_RESULT_SHA256
    assert result["ROWS_BEFORE"] == result["ROWS_AFTER"] == integration.BASE_ROWS
    assert result["EVENTS_BEFORE"] == integration.BASE_EVENTS
    assert result["NEW_RESOLVED_EVENTS"] == 3
    assert result["EVENTS_AFTER"] == 31
    assert result["CHANGED_ROWS_FROM_BASE"] == 3
    assert result["UNCHANGED_ROWS_FROM_BASE"] == 4_644
    assert result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"] == 30
    assert result["UNCHANGED_ROWS_FROM_FROZEN"] == 4_617

    assert len(base_rows) == len(after_rows) == 4_647
    events = result["EVENT_HISTORY"]
    assert len(events) == 31
    assert [e["EVENT_ID"] for e in events[-3:]] == [
        integration.DONOR_A.event_id,
        integration.DONOR_B.event_id,
        integration.DONOR_C.event_id,
    ]
    assert all(e["EVENT_ID"] != "UNRESOLVED_CLASS_CERTIFICATE" for e in events)


def test_triple_t262_delta_and_full_family_recount(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen_rows, base_rows, after_rows = replay
    profiles = result["PROFILES"]
    assert profiles["PROFILE_A"]["NEW_CAP"] == 262
    assert profiles["PROFILE_A"]["NEW_BOUND"] == 313_355_996
    assert profiles["PROFILE_A"]["OWNER_DELTA"] == 35_848

    assert profiles["PROFILE_B"]["NEW_CAP"] == 262
    assert profiles["PROFILE_B"]["NEW_BOUND"] == 313_355_996
    assert profiles["PROFILE_B"]["OWNER_DELTA"] == 35_848

    assert profiles["PROFILE_C"]["NEW_CAP"] == 262
    assert profiles["PROFILE_C"]["NEW_BOUND"] == 313_355_996
    assert profiles["PROFILE_C"]["OWNER_DELTA"] == 35_848

    assert profiles["TOTAL_OWNER_DELTA"] == 107_544

    changed_pids = {pid for pid in base_rows if base_rows[pid] != after_rows[pid]}
    assert changed_pids == {
        integration.PROFILE_A_ID,
        integration.PROFILE_B_ID,
        integration.PROFILE_C_ID,
    }

    assert result["FAMILY_BOUND_BEFORE"] == 313_391_844
    assert result["FAMILY_BOUND_AFTER"] == 313_391_740
    assert result["FAMILY_GAIN"] == 104
    assert result["FAMILY_GAIN_VS_28_EVENT_BASE"] == 104
    assert result["FAMILY_GAIN_VS_FROZEN_SEVEN_ROW"] == 6_792
    assert result["GAP_TO_INCUMBENT"] == 127_852

    assert result["MAX_RESOLVED_BOUND"] == 313_391_740
    assert result["MAX_RESOLVED_OWNERS"] == [
        "66655555555331100000",
        "66655555555411110000",
    ]
    assert result["NEXT_DISTINCT_RESOLVED_BOUND"] == 313_391_636
    assert result["NEXT_DISTINCT_RESOLVED_OWNERS"] == ["66665555555321100000"]
    assert result["NEXT_DISTINCT_BOUND"] == 313_391_636
    assert result["NEXT_DISTINCT_OWNERS"] == ["66665555555321100000"]


def test_class_bound_is_independent_and_unchanged(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen_rows, _base_rows, _after_rows = replay
    class_info = result["CLASS"]
    assert class_info["COUNT"] == 197
    assert class_info["ID_SET_SHA256"] == integration.CLASS_ID_SET_SHA256
    assert class_info["BOUND_BEFORE"] == integration.CLASS_BOUND
    assert class_info["BOUND_AFTER"] == integration.CLASS_BOUND
    assert class_info["BOUND_DELTA"] == 0
    assert class_info["RESOLVED_ROW_EVENTS"] == 0

    cursor = result["CURSOR_AUTHORITY"]
    assert cursor["ID"] == integration.CLASS_CURSOR_ID
    assert cursor["BOUND"] == integration.CLASS_BOUND
    assert cursor["COUNT"] == 197
    assert cursor["IDS_SHA256"] == integration.CLASS_ID_SET_SHA256


def test_full_and_bounds_digests_are_recomputed_from_final_rows(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen_rows, base_rows, after_rows = replay
    full_before = integration.base.twenty_seven.four.seven.two.full_digest(base_rows)
    bounds_before = integration.base.twenty_seven.four.seven.two.bounds_digest(base_rows)
    full_after = integration.base.twenty_seven.four.seven.two.full_digest(after_rows)
    bounds_after = integration.base.twenty_seven.four.seven.two.bounds_digest(after_rows)

    assert full_before == integration.BASE_FULL_DIGEST
    assert bounds_before == integration.BASE_BOUNDS_DIGEST
    assert full_after == integration.EXPECTED_FULL_DIGEST
    assert bounds_after == integration.EXPECTED_BOUNDS_DIGEST
    assert result["FULL_DIGEST"] == full_after
    assert result["BOUNDS_DIGEST"] == bounds_after
    assert full_after != full_before
    assert bounds_after != bounds_before


def test_historical_caveats_and_provenance_receipts_are_retained(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen_rows, _base_rows, _after_rows = replay
    caveats = result["INHERITED_CAVEATS"]
    assert "BASE_28_EVENT_JUDGE" in caveats
    assert caveats["BASE_28_EVENT_JUDGE"]["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert caveats["BASE_28_EVENT_JUDGE"]["REPORT_SHA256"] == integration.BASE_JUDGE_REPORT_SHA256

    assert "TRIPLE_T262_SCIENCE_JUDGE" in caveats
    assert caveats["TRIPLE_T262_SCIENCE_JUDGE"]["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert (
        caveats["TRIPLE_T262_SCIENCE_JUDGE"]["REPORT_SHA256"]
        == integration.SCIENCE_JUDGE_REPORT_SHA256
    )


def test_all_sixteen_required_load_bearing_negative_controls_reject(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen_rows, _base_rows, _after_rows = replay
    negative = result["NEGATIVE_CASE_RESULTS"]
    assert len(negative) == 16
    expected_controls = {
        "WRONG_28_EVENT_BASE",
        "WRONG_DONOR_HEAD_TREE",
        "WRONG_DONOR_RESULT_SHA",
        "WRONG_PROFILE_ID",
        "WRONG_ORIGINAL_CAP",
        "WRONG_ORIGINAL_BOUND",
        "UNSUPPORTED_T262_PROOF",
        "WRONG_NEW_BOUND",
        "MISSING_PROOF_LOCATOR",
        "WRONG_JUDGE_SOURCE",
        "DUPLICATE_UPDATE_EVENT",
        "MISSING_ONE_OF_THREE_UPDATES",
        "UNRELATED_ROW_MUTATION",
        "WRONG_CLASS_ID_SET",
        "WRONG_CLASS_BOUND",
        "WRONG_EVENT_ANCESTRY",
    }
    assert set(negative.keys()) == expected_controls
    for key, val in negative.items():
        assert val.startswith("REJECTED:"), f"{key} did not report rejection: {val}"


def test_result_reports_self_check_only_and_no_publication(
    replay: tuple[
        dict[str, Any],
        dict[str, integration.Row],
        dict[str, integration.Row],
        dict[str, integration.Row],
    ],
) -> None:
    result, _frozen_rows, _base_rows, _after_rows = replay
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert result["NEW_INTEGRATION_JUDGE"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["FULL_SUITE"] == "NOT_RUN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["PUSH"] == "NOT_RUN"
    assert result["MERGE"] == "NOT_RUN"
    assert result["PR"] == "NOT_RUN"
    assert result["PRODUCTION_MUTATION"] == "NONE"
