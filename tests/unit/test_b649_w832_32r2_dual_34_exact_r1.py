"""Focused checks for the fixed 34-event B649 R2 continuation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_w832_32r2_dual_34_exact_r1 as candidate


@pytest.fixture(scope="module")
def replay() -> Iterator[
    tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ]
]:
    yield candidate.build_candidate()


def test_fixed_r2_base_and_exact_32_event_prefix(replay: tuple[Any, ...]) -> None:
    result, before_rows, after_rows = replay
    base_raw = candidate.run_git(
        "show", f"{candidate.BASE_HEAD}:{candidate.BASE_RESULT_PATH}"
    )
    base_result = candidate.json_object(base_raw, "R2_RESULT_INVALID_JSON")
    base_history = base_result["EVENT_HISTORY"]

    assert result["BASE"]["HEAD"] == candidate.BASE_HEAD
    assert result["BASE"]["TREE"] == candidate.BASE_TREE
    assert result["BASE"]["RESULT_SHA256"] == candidate.BASE_RESULT_SHA256
    assert result["BASE"]["FULL_DIGEST"] == candidate.BASE_FULL_DIGEST
    assert result["BASE"]["BOUNDS_DIGEST"] == candidate.BASE_BOUNDS_DIGEST
    assert result["ROWS_BEFORE"] == result["ROWS_AFTER"] == 4_647
    assert result["EVENTS_BEFORE"] == 32
    assert result["EVENTS_AFTER"] == 34
    assert result["ADDED_EVENTS"] == 2
    assert result["EVENT_PREFIX_PARITY"] == "EXACT"
    assert result["EVENT_HISTORY"][:32] == base_history
    assert result["EVENT_HISTORY"][32:] == [
        event for event in result["EVENT_HISTORY"] if event["EVENT_ID"] in {
            candidate.PROFILE_A.event_id,
            candidate.PROFILE_B.event_id,
        }
    ]
    assert result["EVENT_PREFIX_SHA256"] == result["BASE"]["EVENT_HISTORY_SHA256"]
    assert len(before_rows) == len(after_rows) == 4_647
    assert result["CHANGED_ROWS"] == 2
    assert result["UNCHANGED_ROWS"] == 4_645
    assert result["BEFORE_STATE_MISMATCH"] == 0
    assert result["UNRELATED_ROW_MUTATION"] == 0


def test_both_complete_before_states_and_route_b_results(
    replay: tuple[Any, ...],
) -> None:
    result, before_rows, after_rows = replay
    profiles = {item["PROFILE_ID"]: item for item in result["PROFILES"]}
    assert set(profiles) == {
        candidate.PROFILE_A.profile_id,
        candidate.PROFILE_B.profile_id,
    }

    for spec in candidate.PROFILE_SPECS:
        old_row = before_rows[spec.profile_id]
        new_row = after_rows[spec.profile_id]
        profile_result = profiles[spec.profile_id]
        assert (old_row.bound, old_row.cap, old_row.s4_base, old_row.source) == (
            spec.old_bound,
            spec.old_cap,
            spec.s4_base,
            spec.catalog_source,
        )
        assert (new_row.bound, new_row.cap, new_row.s4_base, new_row.source) == (
            spec.new_bound,
            spec.new_cap,
            spec.s4_base,
            candidate.row_source_after(spec),
        )
        assert profile_result["OLD_CAP"] == 265
        assert profile_result["NEW_CAP"] == spec.new_cap
        assert profile_result["OLD_BOUND"] == 313_391_740
        assert profile_result["NEW_BOUND"] == spec.new_bound
        assert profile_result["OWNER_BOUND_DELTA"] == (
            spec.old_bound - spec.new_bound
        )
        assert profile_result["W"] == 827
        assert profile_result["U"] == spec.u
        assert profile_result["G_MAX"] == 12
        assert profile_result["A_MAX"] == 197
        assert profile_result["S4_BASE"] == 112
        assert profile_result["SUPPORT_VALIDATION"] == "NOT_RUN_NO_ROW_REALIZATION"
        assert profile_result["SUPPORT_SIGNATURE"] is None
        assert profile_result["CATALOG_SOURCE_KIND"] == (
            "VIRTUAL_LOCATOR_PRESERVED_AS_PROVENANCE"
        )

        route = profile_result["ROUTE_B"]
        old_route = route["OLD"]
        new_route = route["NEW"]
        assert old_route["CAP"] == 265
        assert old_route["BOUND"] == 313_391_740
        assert old_route["TERM_COUNT"] == 244
        assert new_route["CAP"] == spec.new_cap
        assert new_route["BOUND"] == spec.new_bound
        assert new_route["TERM_COUNT"] == spec.new_cap - 21
        assert new_route["ARGMAX_TERM"] == list(spec.argmax_term)
        assert new_route["TERMS"] == old_route["TERMS"][: len(new_route["TERMS"])]
        assert old_route["TERM_MISMATCH_COUNT"] == 0
        assert new_route["TERM_MISMATCH_COUNT"] == 0
        assert old_route["INTEGER_RECOUNT"] == "PASS"
        assert new_route["FRACTION_RECOUNT"] == "PASS"
        assert new_route["R32_CROSSCHECK"] == "PASS"


def test_class_and_full_family_recomputation(replay: tuple[Any, ...]) -> None:
    result, before_rows, after_rows = replay
    assert result["CLASS_COUNT"] == 197
    assert result["CLASS_BOUND"] == 313_258_872
    assert result["CLASS_ID_SET_SHA256"] == (
        "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
    )
    assert result["CLASS_MUTATIONS"] == 0
    assert result["FAMILY_BEFORE"] == 313_391_740
    assert result["FAMILY_AFTER"] == 313_391_636
    assert result["FAMILY_GAIN"] == 104
    assert result["MAX_OWNER"] == "66665555555321100000"
    assert result["NEXT_DISTINCT_BOUND"] == 313_391_560
    assert result["NEXT_DISTINCT_OWNER"] == "65555555555432100000"

    changed = {
        profile_id
        for profile_id in before_rows
        if before_rows[profile_id] != after_rows[profile_id]
    }
    assert changed == {
        candidate.PROFILE_A.profile_id,
        candidate.PROFILE_B.profile_id,
    }
    transitions = result["EVENT_TRANSITIONS"]
    assert len(transitions) == 2
    assert transitions[0]["FAMILY_BOUND_BEFORE"] == 313_391_740
    assert transitions[0]["FAMILY_BOUND_AFTER"] == 313_391_740
    assert transitions[1]["FAMILY_BOUND_BEFORE"] == 313_391_740
    assert transitions[1]["FAMILY_BOUND_AFTER"] == 313_391_636


def test_canonical_digests_math_provenance_and_authority_boundary(
    replay: tuple[Any, ...],
) -> None:
    result, _before_rows, _after_rows = replay
    assert result["BOUNDS_DIGEST"] == (
        "850eda553999f1dd0a92ff14df01c4ba3ee33e0d37a823c11dff1092918bd872"
    )
    assert len(result["FULL_DIGEST"]) == 64
    assert result["FULL_DIGEST"] != candidate.BASE_FULL_DIGEST
    assert result["MATH_PROVENANCE_STATUS"] == "INHERITED_REPORT_ONLY"
    assert result["MATH_PROVENANCE"]["EVIDENCE_KIND"] == "TRANSCRIPT_ONLY"
    assert result["MATH_PROVENANCE"]["ACTUAL_TRANSCRIPT_LOCATOR"] == "UNKNOWN"
    assert result["MATH_PROVENANCE"]["FRESH_CERTIFICATION"] == "NOT_PERFORMED"
    assert result["ENGINEERING_JUDGE_STATUS"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["FORMAL_FAMILY_AUTHORITY_ADOPTION"] == "NOT_ACCEPTED"
    assert result["PUSH"] == result["PR"] == result["MERGE"] == "NOT_RUN"


def test_all_required_negative_controls_reject(replay: tuple[Any, ...]) -> None:
    result, _before_rows, _after_rows = replay
    negative = result["NEGATIVE_CASE_RESULTS"]
    expected_reasons = {
        "WRONG_BASE_HEAD_TREE": "BASE_HEAD_TREE_MISMATCH",
        "WRONG_BASE_RESULT_SHA": "BASE_RESULT_SHA256_MISMATCH",
        "WRONG_TARGET_PROFILE": "TARGET_PROFILE_ID_MISMATCH",
        "WRONG_ORIGINAL_CAP": "TARGET_OLD_ROW_IDENTITY_MISMATCH",
        "WRONG_ORIGINAL_BOUND": "TARGET_OLD_ROW_IDENTITY_MISMATCH",
        "WRONG_NEW_CAP": "UNSUPPORTED_TARGET_CAP",
        "WRONG_NEW_BOUND": "TARGET_CAP_BOUND_MISMATCH",
        "WRONG_W": "TARGET_W_MISMATCH",
        "WRONG_U": "TARGET_U_MISMATCH",
        "WRONG_A_MAX": "TARGET_A_MAX_MISMATCH",
        "MISSING_EVENT": "EVENT_COUNT_MISMATCH:EXPECTED_34",
        "DUPLICATE_EVENT": "DUPLICATE_EVENT_ID",
        "WRONG_BEFORE_STATE": "EVENT_BEFORE_STATE_MISMATCH:T258_66655555555411110000",
        "UNRELATED_ROW_MUTATION": "ROW_MUTATION_SET_MISMATCH",
        "WRONG_FAMILY_GAIN": "FAMILY_GAIN_MISMATCH",
        "WRONG_CLASS": "CLASS_IDENTITY_MISMATCH",
        "CROSS_LINEAGE_IMPORT": (
            "UNCOMMITTED_IMPORT_MODULE:"
            "src/lottolab/research/foreign_untracked_candidate.py"
        ),
        "WRONG_PARENT": "CANDIDATE_MUST_BE_DIRECT_CHILD_OF_PINNED_BASE",
        "WRONG_PATH_SET": "COMMITTED_PATH_SET_MISMATCH",
        "WRONG_POSTCOMMIT_GUARD": "CANDIDATE_RESULT_REPLAY_MISMATCH",
        "FALSE_FRESH_MATH_CERTIFICATION": (
            "MATH_PROVENANCE_NOT_INHERITED_REPORT_ONLY"
        ),
        "WRONG_R2_PREFIX": "R2_EVENT_PREFIX_PARITY_MISMATCH",
        "WRONG_BASE_ROWS": "R2_REPLAY_ROW_COUNT_MISMATCH",
    }
    assert set(negative) == set(expected_reasons)
    for name, reason in expected_reasons.items():
        assert negative[name].startswith("REJECTED: ValueError:")
        assert reason in negative[name]


def test_source_closure_and_fixed_donor_identity(replay: tuple[Any, ...]) -> None:
    result, _before_rows, _after_rows = replay
    assert candidate.verify_source_closure() > 0
    closure = result["SOURCE_CLOSURE"]
    assert closure["STATUS"] == "PASS"
    assert closure["EXTERNAL_UNCOMMITTED_IMPORTS"] == 0
    event_sources = result["EVENT_SOURCE_EVIDENCE"]
    assert event_sources["DONOR_BASE_HEAD"] == (
        "88a37370e6db035d6155190723de8cea646e76b7"
    )
    assert event_sources["DONOR_SOURCE_SHA256"] == (
        "4ca05fd20ba3a336a0652cc5a37ae33b4ab126e78b2e15da10b6a58856eff326"
    )
    assert event_sources["DONOR_RESULT_SHA256"] == (
        "2a581072b4ee4e0c1fa3d1878362d6c270527ed4b027c827022f14e90b54b39e"
    )
    assert event_sources["DONOR_USED_AS_RUNTIME_IMPORT"] is False
    assert event_sources["VIRTUAL_CATALOG_LOCATORS_TREATED_AS_ARRAYS"] is False


def test_result_bytes_bind_source_and_test(
    replay: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _before_rows, _after_rows = replay
    source_path = Path(candidate.ROOT) / candidate.SOURCE_PATH
    test_path = Path(candidate.ROOT) / candidate.TEST_PATH
    result_path = Path(candidate.ROOT) / candidate.RESULT_PATH
    encoded = candidate.serialize_result(result)
    assert source_path.is_file()
    assert test_path.is_file()
    assert result_path.read_bytes() == encoded
    assert result["SOURCE_SHA256"] == candidate.sha256(source_path.read_bytes())
    assert result["TEST_SHA256"] == candidate.sha256(test_path.read_bytes())
    candidate.validate_result_bytes(result_path.read_bytes(), encoded)
    assert "OBSERVED_ALLOWED_DIRTY_PATHS" not in result

    precommit_paths = {
        str(path)
        for path in (*candidate.COMMITTED_PATHS, *candidate.PRESERVED_R1_PATHS)
    }
    postcommit_paths = {str(path) for path in candidate.PRESERVED_R1_PATHS}
    current_paths = set(candidate.validate_worktree_scope())
    assert current_paths in (precommit_paths, postcommit_paths)

    def status_for(paths: set[str]) -> str:
        return "\n".join(
            f"{' M ' if path in candidate.COMMITTED_PATHS else '?? '}{path}"
            for path in sorted(paths)
        )

    original_run_git = candidate.run_git
    for expected_paths in (precommit_paths, postcommit_paths):
        simulated_status = status_for(expected_paths).encode("utf-8")

        def run_git_with_simulated_status(
            *args: str, status: bytes = simulated_status
        ) -> bytes:
            if args == ("status", "--short", "--untracked-files=all"):
                return status
            return original_run_git(*args)

        with monkeypatch.context() as patch:
            patch.setattr(candidate, "run_git", run_git_with_simulated_status)
            assert set(candidate.validate_worktree_scope()) == expected_paths
            state_result = candidate.serialize_result(result)
            assert state_result == encoded
            candidate.validate_result_bytes(result_path.read_bytes(), state_result)

    def run_git_with_unexpected_path(*args: str) -> bytes:
        if args == ("status", "--short", "--untracked-files=all"):
            return b"?? src/foreign.py\n"
        return original_run_git(*args)

    with monkeypatch.context() as patch:
        patch.setattr(candidate, "run_git", run_git_with_unexpected_path)
        rejected = candidate.expect_rejected(candidate.validate_worktree_scope)
    assert rejected == (
        "REJECTED: ValueError: OUT_OF_SCOPE_WORKTREE_PATH:src/foreign.py"
    )


def test_postcommit_parent_guard_rejects_wrong_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_head = "f" * 40

    def fake_git_text(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return candidate_head
        if args == ("rev-list", "--parents", "-n", "1", candidate_head):
            return f"{candidate_head} {'0' * 40}"
        raise AssertionError(f"unexpected git query: {args}")

    monkeypatch.setattr(candidate, "git_text", fake_git_text)
    rejected = candidate.expect_rejected(candidate.verify_candidate_ancestry)
    assert rejected == (
        "REJECTED: ValueError: CANDIDATE_MUST_BE_DIRECT_CHILD_OF_PINNED_BASE"
    )


def test_postcommit_path_guard_rejects_wrong_path_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_head = "f" * 40

    def fake_git_text(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return candidate_head
        if args == ("rev-list", "--parents", "-n", "1", candidate_head):
            return f"{candidate_head} {candidate.BASE_HEAD}"
        raise AssertionError(f"unexpected git query: {args}")

    def fake_run_git(*args: str) -> bytes:
        if args == (
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            candidate_head,
        ):
            return b"src/foreign.py\n"
        raise AssertionError(f"unexpected git command: {args}")

    monkeypatch.setattr(candidate, "git_text", fake_git_text)
    monkeypatch.setattr(candidate, "run_git", fake_run_git)
    rejected = candidate.expect_rejected(candidate.verify_candidate_ancestry)
    assert rejected == "REJECTED: ValueError: COMMITTED_PATH_SET_MISMATCH"
