"""Focused acceptance checks for the exact-tree R2 32-event candidate."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_w832_z6_t256_32_event_from31_r2 as candidate


@pytest.fixture(scope="module")
def replay() -> Iterator[
    tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ]
]:
    yield candidate.build_candidate()


def test_pinned_base_and_replayed_ledger(replay: tuple[Any, ...]) -> None:
    result, before_rows, after_rows = replay
    assert result["BASE"]["HEAD"] == candidate.BASE_HEAD
    assert result["BASE"]["TREE"] == candidate.BASE_TREE
    assert result["BASE"]["RESULT_SHA256"] == candidate.BASE_RESULT_SHA256
    assert result["BASE"]["FULL_DIGEST"] == candidate.BASE_FULL_DIGEST
    assert result["BASE"]["BOUNDS_DIGEST"] == candidate.BASE_BOUNDS_DIGEST
    assert len(before_rows) == len(after_rows) == 4_647
    assert result["ROWS_BEFORE"] == result["ROWS_AFTER"] == 4_647
    assert result["EVENTS_BEFORE"] == 31
    assert result["EVENTS_AFTER"] == 32
    assert result["EVENT_PREFIX_PARITY"] == "EXACT"
    assert len(result["EVENT_HISTORY"]) == 32
    assert result["EVENT_HISTORY"][-1]["EVENT_ID"] == candidate.EVENT_ID
    assert result["CHANGED_ROWS"] == 1
    assert result["UNCHANGED_ROWS"] == 4_646
    assert result["UNRELATED_ROW_MUTATION"] == 0


def test_only_target_profile_receives_judged_t256_update(
    replay: tuple[Any, ...],
) -> None:
    result, before_rows, after_rows = replay
    profile = result["TARGET_PROFILE"]
    assert profile["PROFILE_ID"] == candidate.PROFILE_ID
    assert profile["DEGREE_DISTRIBUTION"] == candidate.EXPECTED_DISTRIBUTION
    assert profile["OLD_CAP"] == 263
    assert profile["NEW_CAP"] == 256
    assert profile["OLD_BOUND"] == 313_388_988
    assert profile["NEW_BOUND"] == 313_326_448
    assert profile["OWNER_DELTA"] == 62_540
    assert profile["SUPPORT_VALIDATION"] == "R5_PASS"
    changed = {
        profile_id
        for profile_id in before_rows
        if before_rows[profile_id] != after_rows[profile_id]
    }
    assert changed == {candidate.PROFILE_ID}
    assert result["MATH_BINDING"]["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert result["MATH_BINDING"]["PROOF_SCOPE"] == "FULL_PROFILE"
    assert result["MATH_BINDING"]["EVIDENCE_KIND"] == "TRANSCRIPT_ONLY"
    assert result["MATH_BINDING"]["JUDGE_REPORT_SHA256"] == "NOT_APPLICABLE"
    assert result["MATH_BINDING"]["JUDGE_REPORT_SHA256_STATUS"] == "UNKNOWN"
    assert result["MATH_BINDING"]["GLOBAL_OPTIMALITY"] == "NOT_CLAIMED"


def test_route_b_terms_recount_and_rounding_control(
    replay: tuple[Any, ...],
) -> None:
    result, _before_rows, _after_rows = replay
    route = result["ROUTE_B"]
    old_route = route["OLD"]
    new_route = route["NEW"]
    assert old_route["DOMAIN"] == [22, 263]
    assert old_route["TERM_COUNT"] == 242
    assert old_route["BOUND"] == 313_388_988
    assert old_route["ARGMAX_TERM"] == candidate.EXPECTED_OLD_ARGMAX
    assert new_route["DOMAIN"] == [22, 256]
    assert new_route["TERM_COUNT"] == 235
    assert new_route["BOUND"] == 313_326_448
    assert new_route["ARGMAX_TERM"] == candidate.EXPECTED_NEW_ARGMAX
    assert new_route["TERMS"] == old_route["TERMS"][:235]
    assert route["TERM_MISMATCH_COUNT"] == 0
    assert route["INTEGER_RECOUNT"] == "PASS"
    assert route["FRACTION_RECOUNT"] == "PASS"
    assert route["R32_CROSSCHECK"] == "PASS"
    assert all(term[4] % 7 == 0 for term in new_route["TERMS"])
    rounding = route["S4_ROUNDING_NEGATIVE_CONTROL"]
    assert rounding["FOUR_S4_OVER_SEVEN"] == "4/7"
    assert rounding["FLOOR"] == 0
    assert rounding["CEILING"] == 1
    assert rounding["MUTATED_CEILING"].startswith("REJECTED:")


def test_class_and_family_authorities_remain_unchanged(
    replay: tuple[Any, ...],
) -> None:
    result, _before_rows, _after_rows = replay
    assert result["CLASS_COUNT"] == 197
    assert result["CLASS_BOUND"] == 313_258_872
    assert result["CLASS_ID_SET_SHA256"] == candidate.EXPECTED_CLASS_ID_SET_SHA256
    assert result["CLASS_MUTATIONS"] == 0
    assert result["FAMILY_BEFORE"] == result["FAMILY_AFTER"] == 313_391_740
    assert result["FAMILY_GAIN"] == 0
    assert result["MAX_RESOLVED_BOUND"] == 313_391_740
    assert result["MAX_RESOLVED_OWNERS"] == candidate.EXPECTED_MAX_OWNERS
    assert result["NEXT_DISTINCT_BOUND"] == 313_391_636
    assert result["NEXT_DISTINCT_OWNERS"] == candidate.EXPECTED_NEXT_OWNERS


def test_required_negative_controls_reject(replay: tuple[Any, ...]) -> None:
    result, _before_rows, _after_rows = replay
    negative = result["NEGATIVE_CASE_RESULTS"]
    required = {
        "WRONG_BASE_HEAD_TREE",
        "WRONG_BASE_RESULT_SHA",
        "WRONG_TARGET_PROFILE",
        "WRONG_ORIGINAL_CAP",
        "WRONG_DEGREE_DISTRIBUTION",
        "WRONG_W",
        "WRONG_U",
        "WRONG_A_MAX",
        "UNSUPPORTED_T_CAP_255",
        "WRONG_T256_BOUND",
        "MISSING_EVENT",
        "DUPLICATE_EVENT",
        "UNRELATED_ROW_MUTATION",
        "WRONG_CLASS_IDENTITY",
        "WRONG_FAMILY_GAIN",
        "CROSS_LINEAGE_34_38_SOURCE",
        "MISSING_SCIENCE_JUDGE_PROVENANCE",
        "S4_ROUNDING_CEILING_MUTATION",
        "WRONG_CANDIDATE_PARENT",
        "WRONG_COMMITTED_PATH_SET",
        "WRONG_SOURCE_CLOSURE",
    }
    assert set(negative) == required
    assert all(value.startswith("REJECTED:") for value in negative.values())
    assert all(len(value.split(":", maxsplit=2)) == 3 for value in negative.values())


def test_candidate_replay_hashes_and_local_only_status(
    replay: tuple[Any, ...],
) -> None:
    result, _before_rows, _after_rows = replay
    assert result["TASK_STATUS"] == "LOCAL_COMMIT_COMPATIBLE_32_EVENT_R2_CANDIDATE_REPLAYED"
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert result["NEW_ENGINEERING_JUDGE"] == "SELF_CHECK_ONLY"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["COMMIT_MODEL"] == {
        "PARENT": candidate.BASE_HEAD,
        "EXPECTED_PATHS": list(candidate.COMMITTED_PATHS),
        "MAX_LOCAL_COMMITS": 1,
        "FINAL_HEAD_EMBEDDED": False,
        "FINAL_TREE_EMBEDDED": False,
    }
    assert result["POSTCOMMIT_REPLAY_POLICY"].startswith("RUN_CANDIDATE_CHECK")
    assert result["FINAL_GIT_IDENTITY_POLICY"].endswith("EXTERNALLY")
    assert result["EXTERNAL_UNCOMMITTED_IMPORTS"] == 0
    assert result["FULL_DIGEST"] == (
        "5667e54776b5fade56831c76228bf65fd926aed9d66048b459450eb31ec4de7f"
    )
    assert result["BOUNDS_DIGEST"] == (
        "3b8ee21e9c6d96712bf7310434b0de3158f665ca54cee2d53f0841b62e3e6d67"
    )
    source_path = Path(candidate.ROOT) / candidate.SOURCE_PATH
    test_path = Path(candidate.ROOT) / candidate.TEST_PATH
    assert result["SOURCE_SHA256"] == candidate.sha256(source_path.read_bytes())
    assert result["TEST_SHA256"] == candidate.sha256(test_path.read_bytes())
    assert result["FULL_DIGEST"] != candidate.BASE_FULL_DIGEST
    assert result["BOUNDS_DIGEST"] != candidate.BASE_BOUNDS_DIGEST


def test_source_closure_rejects_uncommitted_lottolab_modules() -> None:
    assert candidate.verify_source_closure() > 0
    rejected = candidate.expect_rejected(
        lambda: candidate.verify_source_closure(
            {
                "lottolab.foreign_candidate": str(
                    Path(candidate.ROOT)
                    / "src/lottolab/research/foreign_untracked_candidate.py"
                )
            }
        )
    )
    assert rejected == (
        "REJECTED: ValueError: UNCOMMITTED_IMPORT_MODULE:"
        "src/lottolab/research/foreign_untracked_candidate.py"
    )


def test_candidate_head_guard_rejects_wrong_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    wrong_head = "f" * 40

    def fake_git_text(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return wrong_head
        if args == ("rev-list", "--parents", "-n", "1", wrong_head):
            return f"{wrong_head} {'0' * 40}"
        raise AssertionError(f"unexpected git query: {args}")

    monkeypatch.setattr(candidate, "git_text", fake_git_text)
    rejected = candidate.expect_rejected(candidate.verify_candidate_ancestry)
    assert rejected == (
        "REJECTED: ValueError: CANDIDATE_MUST_BE_DIRECT_CHILD_OF_PINNED_BASE"
    )


def test_candidate_head_guard_rejects_extra_committed_path(
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
