"""Focused checks for the pinned 36-event B649 exact-tree continuation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_34_plus_t250_t237_36_exact_r1 as candidate


@pytest.fixture(scope="module")
def replay() -> Iterator[tuple[dict[str, Any], dict[str, candidate.Row], dict[str, candidate.Row]]]:
    yield candidate.build_candidate()


def test_pinned_parent_and_34_35_36_event_replay(replay: tuple[Any, ...]) -> None:
    result, before_rows, after_rows = replay
    parent_raw = candidate.run_git("show", f"{candidate.BASE_HEAD}:{candidate.BASE_RESULT_PATH}")
    parent_result = candidate.json_object(parent_raw, "PARENT_RESULT_INVALID_JSON")
    history = result["EVENT_HISTORY"]

    assert result["BASE"]["HEAD"] == candidate.BASE_HEAD
    assert result["BASE"]["TREE"] == candidate.BASE_TREE
    assert result["BASE"]["RESULT_SHA256"] == candidate.BASE_RESULT_SHA256
    assert result["BASE"]["FULL_DIGEST"] == candidate.BASE_FULL_DIGEST
    assert result["BASE"]["BOUNDS_DIGEST"] == candidate.BASE_BOUNDS_DIGEST
    assert result["ROWS_BEFORE"] == result["ROWS_AFTER"] == 4_647
    assert result["EVENTS_BEFORE"] == 34
    assert result["EVENTS_MIDDLE"] == 35
    assert result["EVENTS_AFTER"] == 36
    assert result["ADDED_EVENTS"] == 2
    assert result["EVENT_PREFIX_PARITY"] == "EXACT"
    assert history[:34] == parent_result["EVENT_HISTORY"]
    assert [event["EVENT_ID"] for event in history[34:]] == [
        candidate.PROFILE_T250.event_id,
        candidate.PROFILE_T237.event_id,
    ]
    assert len({event["EVENT_ID"] for event in history}) == 36
    assert len(before_rows) == len(after_rows) == 4_647
    assert result["CHANGED_ROWS"] == 2
    assert result["CHANGED_ROW_IDS"] == sorted(
        (candidate.PROFILE_T250.profile_id, candidate.PROFILE_T237.profile_id)
    )
    assert result["UNCHANGED_ROWS"] == 4_645
    assert result["BEFORE_STATE_MISMATCHES"] == 0
    assert result["UNRELATED_ROW_MUTATIONS"] == 0


def test_t250_increment_and_t237_bound_bindings(replay: tuple[Any, ...]) -> None:
    result, before_rows, after_rows = replay
    middle_rows = candidate.apply_event_history(before_rows, [result["EVENT_HISTORY"][34]])
    profiles = {item["PROFILE_ID"]: item for item in result["PROFILES"]}

    assert set(profiles) == {candidate.PROFILE_T250.profile_id, candidate.PROFILE_T237.profile_id}
    for spec in candidate.PROFILE_SPECS:
        old_rows = before_rows if spec is candidate.PROFILE_T250 else middle_rows
        old_row = old_rows[spec.profile_id]
        new_row = after_rows[spec.profile_id]
        item = profiles[spec.profile_id]
        assert (old_row.cap, old_row.bound, old_row.s4_base) == (
            spec.old_cap,
            spec.old_bound,
            spec.s4_base,
        )
        assert (new_row.cap, new_row.bound, new_row.s4_base, new_row.source) == (
            spec.new_cap,
            spec.new_bound,
            spec.s4_base,
            candidate.row_source_after(spec),
        )
        assert item["OLD_CAP"] == spec.old_cap
        assert item["NEW_CAP"] == spec.new_cap
        assert item["OLD_BOUND"] == spec.old_bound
        assert item["NEW_BOUND"] == spec.new_bound
        assert item["W"] == spec.w
        assert item["U"] == spec.u
        assert item["G_MAX"] == spec.g_max
        assert item["A_MAX"] == spec.a_max
        assert item["S4_BASE"] == 112
        assert item["CAP_ATTAINMENT"] == spec.cap_attainment
        old_route, new_route = item["ROUTE_B"]["OLD"], item["ROUTE_B"]["NEW"]
        assert old_route["CAP"] == spec.old_cap
        assert old_route["BOUND"] == spec.old_bound
        assert old_route["TERM_COUNT"] == spec.route_b_old_terms
        assert new_route["CAP"] == spec.new_cap
        assert new_route["BOUND"] == spec.new_bound
        assert new_route["TERM_COUNT"] == spec.route_b_new_terms
        assert new_route["ARGMAX_TERM"] == list(spec.argmax_term)
        assert new_route["TERMS"] == old_route["TERMS"][: len(new_route["TERMS"])]
        assert old_route["TERM_MISMATCH_COUNT"] == 0
        assert new_route["TERM_MISMATCH_COUNT"] == 0
        assert new_route["INTEGER_RECOUNT"] == "PASS"
        assert new_route["FRACTION_RECOUNT"] == "PASS"
        assert new_route["R32_CROSSCHECK"] == "PASS"

    t250_event = result["EVENT_HISTORY"][34]
    t250_donor = candidate.json_object(
        candidate.run_git("show", f"{candidate.T250_COMMIT}:{candidate.T250_RESULT_PATH}"),
        "T250_RESULT_INVALID_JSON",
    )
    assert t250_event == t250_donor["EVENT_HISTORY"][-1]
    t237_event = result["EVENT_HISTORY"][35]
    assert t237_event["DONOR"]["CAP_ATTAINMENT"] == "NOT_PROVEN"
    assert t237_event["ROUTE_B"]["OLD_TERM_COUNT"] == 246
    assert t237_event["ROUTE_B"]["NEW_TERM_COUNT"] == 216


def test_class_and_every_family_frontier(replay: tuple[Any, ...]) -> None:
    result, before_rows, after_rows = replay
    assert result["CLASS_COUNT"] == 197
    assert result["CLASS_BOUND"] == 313_258_872
    assert result["CLASS_ID_SET_SHA256"] == (
        "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
    )
    assert result["CLASS_MUTATIONS"] == 0
    assert result["FAMILY_34"] == 313_391_636
    assert result["FAMILY_35"] == 313_391_560
    assert result["FAMILY_36"] == 313_391_172
    assert result["FAMILY_GAIN_34_TO_35"] == 76
    assert result["FAMILY_GAIN_35_TO_36"] == 388
    assert result["FAMILY_GAIN_34_TO_36"] == 464
    assert result["FAMILY_GAIN_31_TO_36"] == 568
    assert result["MAXIMIZING_OWNERS"] == ["65555555555511111000"]
    assert result["MAX_RESOLVED_BOUND"] == 313_391_172
    assert result["NEXT_DISTINCT_BOUND"] == 313_390_396
    assert result["NEXT_DISTINCT_OWNERS"] == ["55555555555443000000"]
    changed = {pid for pid in before_rows if before_rows[pid] != after_rows[pid]}
    assert changed == {candidate.PROFILE_T250.profile_id, candidate.PROFILE_T237.profile_id}
    transitions = result["EVENT_TRANSITIONS"]
    assert len(transitions) == 2
    assert transitions[0]["FAMILY_BOUND_BEFORE"] == 313_391_636
    assert transitions[0]["FAMILY_BOUND_AFTER"] == 313_391_560
    assert transitions[1]["FAMILY_BOUND_BEFORE"] == 313_391_560
    assert transitions[1]["FAMILY_BOUND_AFTER"] == 313_391_172


def test_digests_source_closure_provenance_and_authority(replay: tuple[Any, ...]) -> None:
    result, _before_rows, _after_rows = replay
    assert result["BOUNDS_DIGEST"] == (
        "2f22be18f8555ad413d786adfe019aeeeb60084b392d584f12e1c50b8f598649"
    )
    assert len(result["FULL_DIGEST"]) == 64
    assert result["FULL_DIGEST"] != candidate.BASE_FULL_DIGEST
    assert result["SOURCE_CLOSURE"]["STATUS"] == "PASS"
    assert result["SOURCE_CLOSURE"]["EXTERNAL_UNCOMMITTED_IMPORTS"] == 0
    assert result["EVENT_SOURCE_EVIDENCE"]["T250_DONOR_USED_AS_RUNTIME_IMPORT"] is False
    assert result["EVENT_SOURCE_EVIDENCE"]["DONOR_FULL_HISTORY_CONCATENATED"] is False
    assert result["EVENT_SOURCE_EVIDENCE"]["COMMON_31_EVENT_PREFIX_PARITY"] == "EXACT"
    assert result["MATH_PROVENANCE"]["T250"]["EVIDENCE_KIND"] == "TRANSCRIPT_ONLY"
    assert result["MATH_PROVENANCE"]["T237"]["CAP_ATTAINMENT"] == "NOT_PROVEN"
    assert result["ENGINEERING_JUDGE_STATUS"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["FORMAL_FAMILY_AUTHORITY_ADOPTION"] == "NOT_ACCEPTED"
    assert result["PUSH"] == result["PR"] == result["MERGE"] == "NOT_RUN"
    assert candidate.verify_source_closure() > 0


def test_all_negative_controls_reject_with_observed_reasons(replay: tuple[Any, ...]) -> None:
    result, _before_rows, _after_rows = replay
    reasons = {
        "WRONG_PARENT_HEAD_TREE": "PARENT_HEAD_TREE_MISMATCH",
        "WRONG_PARENT_COMMIT_PARENT": "CANDIDATE_MUST_BE_DIRECT_CHILD_OF_PINNED_BASE",
        "WRONG_COMMITTED_PATH_SET": "COMMITTED_PATH_SET_MISMATCH",
        "WRONG_COMMITTED_TREE_ENTRIES": "COMMITTED_TREE_ENTRIES_MISMATCH",
        "WRONG_SOURCE_CLOSURE": "UNCOMMITTED_IMPORT_MODULE",
        "WRONG_T250_PROFILE": "TARGET_PROFILE_ID_MISMATCH",
        "WRONG_T237_PROFILE": "TARGET_PROFILE_ID_MISMATCH",
        "WRONG_T250_OLD_CAP": "TARGET_OLD_ROW_IDENTITY_MISMATCH",
        "WRONG_T237_OLD_BOUND": "TARGET_OLD_ROW_IDENTITY_MISMATCH",
        "WRONG_BEFORE_STATE": "EVENT_BEFORE_STATE_MISMATCH:T237_65555555555432100000",
        "UNSUPPORTED_CAP": "UNSUPPORTED_TARGET_CAP",
        "WRONG_R32_BOUND": "TARGET_CAP_BOUND_MISMATCH",
        "MISSING_EVENT": "EVENT_COUNT_MISMATCH:EXPECTED_36",
        "DUPLICATE_EVENT": "DUPLICATE_EVENT_ID",
        "EVENT_PREFIX_MUTATION": "EVENT_PREFIX_MUTATION",
        "UNRELATED_ROW_MUTATION": "ROW_MUTATION_SET_MISMATCH",
        "WRONG_CLASS_IDENTITY": "CLASS_IDENTITY_MISMATCH",
        "INCORRECT_FAMILY_GAIN": "FAMILY_GAIN_MISMATCH",
        "MISSING_SCIENCE_PROVENANCE": "SCIENCE_PROVENANCE_MISSING_OR_MISMATCHED",
        "CROSS_LINEAGE_UNCOMMITTED_IMPORT": "UNCOMMITTED_IMPORT_MODULE",
        "UNEXPECTED_DIRTY_PATH": "OUT_OF_SCOPE_WORKTREE_PATH:src/unapproved.py",
        "PRE_POSTCOMMIT_CANONICAL_BYTE_DRIFT": "CANDIDATE_RESULT_REPLAY_MISMATCH",
    }
    controls = result["NEGATIVE_CASE_RESULTS"]
    assert set(controls) == set(reasons)
    for name, reason in reasons.items():
        assert controls[name].startswith("REJECTED: ValueError:")
        assert reason in controls[name]


def test_canonical_result_binds_only_the_three_candidate_files(replay: tuple[Any, ...]) -> None:
    result, _before_rows, _after_rows = replay
    source = Path(candidate.ROOT) / candidate.SOURCE_PATH
    test = Path(candidate.ROOT) / candidate.TEST_PATH
    output = Path(candidate.ROOT) / candidate.RESULT_PATH
    encoded = candidate.serialize_result(result)
    assert source.is_file() and test.is_file() and output.is_file()
    assert output.read_bytes() == encoded
    assert result["SOURCE_SHA256"] == candidate.sha256(source.read_bytes())
    assert result["TEST_SHA256"] == candidate.sha256(test.read_bytes())
    candidate.validate_result_bytes(output.read_bytes(), encoded)
    assert "OBSERVED_ALLOWED_DIRTY_PATHS" not in result
    assert set(candidate.validate_worktree_scope()).issubset(candidate.COMMITTED_PATHS)
