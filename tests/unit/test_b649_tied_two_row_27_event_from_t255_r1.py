"""Focused tests for the 27-event local B649 family integration."""

from __future__ import annotations

from typing import Any

import pytest

from lottolab.research import b649_tied_two_row_27_event_from_t255_r1 as integration


@pytest.fixture(scope="module")
def replay() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return integration.build_candidate()


def test_pinned_base_donor_and_judge_identities_match(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    base = result["BASE_25_EVENT_AUTHORITY"]
    assert (base["HEAD"], base["TREE"], base["PARENT"]) == (
        integration.BASE_HEAD,
        integration.BASE_TREE,
        integration.BASE_PARENT,
    )
    assert base["RESULT_SHA256"] == integration.BASE_RESULT_SHA256
    assert base["EVENTS"] == 25
    assert base["REPLAY_MATCH"] == "YES"
    assert base["FULL_DIGEST"] == integration.BASE_FULL_DIGEST
    assert base["BOUNDS_DIGEST"] == integration.BASE_BOUNDS_DIGEST

    donor_a = result["DONOR_A_IDENTITY"]
    donor_b = result["DONOR_B_IDENTITY"]
    for donor in (donor_a, donor_b):
        assert (donor["HEAD"], donor["TREE"], donor["PARENT"]) == (
            integration.DONOR_HEAD,
            integration.DONOR_TREE,
            integration.DONOR_PARENT,
        )
        assert donor["RESULT_SHA256"] == integration.DONOR_RESULT_SHA256
        assert donor["RESULT_FILE_SHA256"] == integration.DONOR_RESULT_FILE_SHA256
        assert donor["SOURCE_SHA256"] == integration.DONOR_SOURCE_SHA256
        assert donor["TEST_SHA256"] == integration.DONOR_TEST_SHA256
        assert donor["PROOF_SHA256"] == integration.DONOR_PROOF_SHA256
        assert donor["PROOF_REPORT_PATH"] == integration.DONOR_PROOF_REPORT
        assert (
            donor["FRESH_CONTEXT_JUDGE"]["REPORT_SHA256"]
            == integration.JUDGE_REPORT_SHA256
        )
        assert donor["FRESH_CONTEXT_JUDGE"]["VERDICT"] == "VERIFIED_WITH_CAVEATS"

    assert result["AUTHORITY_GATES"]["DONOR_JUDGE_BINDING"] == "MATCH"
    assert result["AUTHORITY_GATES"]["DONOR_PROOF_LOCATORS"] == "RESOLVED"
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["FORMAL_FAMILY_ADOPTION"] == "NOT_ACCEPTED"


def test_two_row_events_change_only_their_profiles_and_provenance(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, frozen, base_rows, after_rows = replay
    assert (result["ROWS_BEFORE"], result["ROWS_AFTER"]) == (4_647, 4_647)
    assert (result["OLD_EVENTS"], result["PREVIOUS_EVENTS"], result["NEW_EVENTS"]) == (25, 25, 2)
    assert result["TOTAL_EVENTS"] == 27
    assert (
        result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"],
        result["UNCHANGED_ROWS_FROM_FROZEN"],
        result["CHANGED_ROWS_FROM_BASE"],
        result["UNCHANGED_ROWS_FROM_BASE"],
    ) == (26, 4_621, 2, 4_645)

    changed_from_frozen = {
        profile_id for profile_id in frozen if frozen[profile_id] != after_rows[profile_id]
    }
    assert set(result["CHANGED_PROFILE_IDS_FROM_FROZEN"]) == changed_from_frozen
    assert integration.PROFILE_A_ID in changed_from_frozen
    assert integration.PROFILE_B_ID in changed_from_frozen
    assert set(base_rows) == set(after_rows) == set(frozen)

    # Profile A checks
    before_a = base_rows[integration.PROFILE_A_ID]
    after_a = after_rows[integration.PROFILE_A_ID]
    donor_a = result["DONOR_A_IDENTITY"]
    event_a = result["EVENT_HISTORY"][-2]
    assert (event_a["EVENT_ID"], event_a["PROFILE_ID"]) == (
        integration.DONOR_A.event_id,
        integration.PROFILE_A_ID,
    )
    assert (before_a.cap, after_a.cap, before_a.bound, after_a.bound) == (
        266,
        224,
        313_392_232,
        313_015_432,
    )
    assert (after_a.cap, after_a.bound, after_a.s4_base) == (224, 313_015_432, 112)
    assert event_a["SOURCE_AFTER"] == donor_a["ROW_SOURCE"] == after_a.source
    assert f"RESULT_SHA256={integration.DONOR_RESULT_SHA256}" in after_a.source
    assert f"JUDGE_REPORT_SHA256={integration.JUDGE_REPORT_SHA256}" in after_a.source
    assert after_a.source.endswith(f"#CERTIFICATES[0]:sha256={integration.DONOR_PROOF_SHA256}")
    assert result["PROFILE_A"]["OWNER_DELTA"] == 376_800
    assert result["PROFILE_A"]["OLD_CAP"] == 266
    assert result["PROFILE_A"]["SEPARATE_NB_CAP"] == 269
    assert result["PROFILE_A"]["NEW_CAP"] == 224
    assert (
        result["PROFILE_A"]["CAVEAT"]
        == "NJ-01_PROFILE_A_SOURCE_CAP_CATALOG_266_NOT_RAW_NB_LEMMA_269"
    )

    # Profile B checks
    before_b = base_rows[integration.PROFILE_B_ID]
    after_b = after_rows[integration.PROFILE_B_ID]
    donor_b = result["DONOR_B_IDENTITY"]
    event_b = result["EVENT_HISTORY"][-1]
    assert (event_b["EVENT_ID"], event_b["PROFILE_ID"]) == (
        integration.DONOR_B.event_id,
        integration.PROFILE_B_ID,
    )
    assert (before_b.cap, after_b.cap, before_b.bound, after_b.bound) == (
        266,
        222,
        313_392_232,
        312_995_528,
    )
    assert (after_b.cap, after_b.bound, after_b.s4_base) == (222, 312_995_528, 112)
    assert event_b["SOURCE_AFTER"] == donor_b["ROW_SOURCE"] == after_b.source
    assert f"RESULT_SHA256={integration.DONOR_RESULT_SHA256}" in after_b.source
    assert f"JUDGE_REPORT_SHA256={integration.JUDGE_REPORT_SHA256}" in after_b.source
    assert after_b.source.endswith(f"#CERTIFICATES[1]:sha256={integration.DONOR_PROOF_SHA256}")
    assert result["PROFILE_B"]["OWNER_DELTA"] == 396_704
    assert result["PROFILE_B"]["OLD_CAP"] == 266
    assert result["PROFILE_B"]["NEW_CAP"] == 222

    # Owner delta sum vs Family gain
    assert result["OWNER_DELTA_SUM"] == 773_504
    assert result["FAMILY_GAIN"] == 0


def test_recomputed_digests_and_family_frontier_preserve_cursor(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, base_rows, after_rows = replay
    assert result["FULL_DIGEST"] == integration.four.seven.two.full_digest(after_rows)
    assert result["BOUNDS_DIGEST"] == integration.four.seven.two.bounds_digest(after_rows)
    assert result["FULL_DIGEST"] == (
        "869a3ccfb20535694b6e6c842337bd69290a6a45f77e326f9264ab9b273ef767"
    )
    assert result["BOUNDS_DIGEST"] == (
        "e897ee98b83d166a40471a6449cd9f6b38652f376e669bc221b8f0010b05d472"
    )
    assert result["FAMILY_BOUND_BEFORE"] == result["FAMILY_BOUND_AFTER"] == 313_394_584
    assert result["FAMILY_GAIN"] == 0
    assert result["MAXIMIZING_OWNERS"] == ["66544333333333332222"]
    assert result["MAX_OWNER_TYPE"] == "UNRESOLVED_CURSOR"
    assert result["CURSOR_AUTHORITY"]["BOUND"] == 313_394_584
    assert result["CURSOR_AUTHORITY"]["COUNT"] == 197
    assert result["CURSOR_INCLUDED"] == "YES"

    assert result["MAX_RESOLVED_BOUND"] == 313_392_128
    assert result["MAX_RESOLVED_OWNERS"] == ["66655555554432000000"]
    assert result["NEXT_DISTINCT_RESOLVED_BOUND"] == 313_391_844
    assert result["NEXT_DISTINCT_RESOLVED_OWNERS"] == [
        "65555555555531100000",
        "66555555554441100000",
        "66555555555422100000",
    ]

    assert result["PROSPECTIVE_FAMILY_WITH_NEW_CLASS"] == 313_392_128
    assert result["PROSPECTIVE_FAMILY_WITH_NEW_CLASS_STATUS"] == "PROSPECTIVE_ONLY_NOT_ADOPTED"
    assert result["UNADOPTED_197_PROFILE_CLASS_BOUND"] == 313_258_872
    assert result["RESOLVED_PROFILES_ABOVE_INCUMBENT"] == 1_362
    assert integration.four.seven.two.full_digest(base_rows) == integration.BASE_FULL_DIGEST
    assert integration.four.seven.two.bounds_digest(base_rows) == integration.BASE_BOUNDS_DIGEST


def test_all_thirteen_negative_controls_reject(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    expected = {
        "WRONG_BASE_REJECTED",
        "WRONG_DONOR_HEAD_TREE_REJECTED",
        "WRONG_DONOR_RESULT_SHA_REJECTED",
        "WRONG_PROFILE_REJECTED",
        "WRONG_ORIGINAL_ROW_BOUND_REJECTED",
        "PROFILE_A_WRONG_CATALOG_CAP_269_REJECTED",
        "WRONG_NEW_CAP_REJECTED",
        "WRONG_NEW_BOUND_REJECTED",
        "WRONG_PROOF_LOCATOR_REJECTED",
        "DUPLICATE_EVENT_REJECTED",
        "UNRELATED_ROW_MUTATION_REJECTED",
        "CURSOR_OMISSION_REJECTED",
        "WRONG_EVENT_ANCESTRY_REJECTED",
    }
    assert set(result["NEGATIVE_VALIDATIONS"]) == expected
    assert set(result["NEGATIVE_VALIDATIONS"].values()) == {"PASS"}


def test_result_artifact_and_forbidden_actions_are_recorded_truthfully(
    replay: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    result, _frozen, _base_rows, _after_rows = replay
    path = integration.ROOT / integration.RESULT_PATH
    assert path.read_bytes() == integration.serialize_result(result)
    assert result["TASK_STATUS"] == "LOCAL_27_EVENT_CANDIDATE_REPLAYED"
    assert result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["FULL_SUITE"] == "NOT_RUN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PUSH"] == result["PR"] == result["MERGE"] == "NOT_RUN"
    assert result["PRODUCTION_MUTATION"] == "NONE"
