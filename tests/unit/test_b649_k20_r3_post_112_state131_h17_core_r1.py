"""Focused checks for the incremental State131 H17 core certificate."""

from __future__ import annotations

import copy
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_post_112_state131_h17_core_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("the accepted 112/123 novel-target builder must not be rerun")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for name in ("build_result", "update_target_regions", "witness_analysis", "recompute_family"):
            patch.setattr(cert.legacy, name, forbidden)
        return cert.build_result()


def test_base_authority_and_112_123_coverage(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert authority == result["SOURCE_AUTHORITY"]
    assert (authority["base_head"], authority["base_tree"]) == (
        cert.BASE_HEAD,
        cert.BASE_TREE,
    )
    baseline = result["BASELINE_112_123"]
    assert baseline["members"] == 112
    assert baseline["vectors"] == 123
    assert baseline["new_distinct_members"] == 1
    assert baseline["new_distinct_vectors"] == 1
    assert baseline["combined_members"] == 113
    assert baseline["combined_vectors"] == 124
    assert baseline["effective_final_bound_read"].startswith("final_bound")
    assert result["COMPRESSED_ALIASES"] == cert.load_baseline_result()["COMPRESSED_ALIASES"]
    assert result["COMPRESSED_ALIASES_SHA256"] == baseline["ledger_projection"][
        "compressed_aliases_sha256"
    ]


def test_full_state131_ledger_has_only_the_fixed_blocker(result: dict[str, Any]) -> None:
    state = result["STATE131"]
    rows = state["complete_region_members"]
    assert state["canonical_members"] == len(rows) == 989
    assert state["represented_vectors"] == 1072
    assert state["prior_blocker_count"] == 1
    assert state["prior_blocker_ids"] == ["[0,17][25,1]"]
    assert state["target_vector"] == [[0, 17], [25, 1]]
    assert state["preserved_members"] == 988
    assert state["preserved_vectors"] == 1071
    assert state["preserved_remainder_max"] == 354977147
    assert state["new_state_bound"] == 354977147
    assert state["preserved_member_vector_bounds_sha256"] == state[
        "preservation_check_sha256"
    ]
    for member in rows:
        cert.validate_member_max(member)
    assert max(member["final_bound"] for member in rows) == 354977147


def test_h17_is_a_universal_threshold_proof_and_tree_is_legal(result: dict[str, Any]) -> None:
    proof = result["H17_PROOF"]
    cert.verify_h17_proof(proof)
    assert proof["proof_scope"] == "ALL_LEGAL_SUPPORTS"
    assert proof["witness_used_as_proof"] is False
    assert proof["outside_incidences"] == 102
    assert proof["outside_labels"] == 40
    assert proof["balanced_collision"]["floor_q"] == 84
    assert proof["core_pair_floors"] == [107800, 574000, 1691620, 3451651]
    assert proof["threshold_minimum"] == {
        "edge_counts": [84, 0, 0],
        "rank_floors": [13, 0, 0],
        "credit": 7785400,
        "cases_examined": 420020,
    }
    assert proof["core_tree_edges"] == 16
    assert proof["type25_leaf"]["credit"] == 0
    assert proof["type25_leaf"]["positive_floor_applied"] is False
    assert proof["complete_tree"] == {"vertices": 18, "edges": 17, "is_tree": True}
    assert "for every outcome" in proof["pointwise_hunter_inequality"].lower()


def test_existing_and_new_credits_combine_by_max_and_subtract_once(
    result: dict[str, Any],
) -> None:
    state = result["STATE131"]
    assert state["target_uncorrected_bound"] == 362443480
    assert state["target_prior_effective_bound"] == 354981480
    assert state["target_existing_credit"] == 7462000
    assert state["target_h17_credit"] == 7785400
    assert state["target_effective_credit"] == 7785400
    assert cert.corrected_bound(362443480, 7462000, 7785400) == 354658080
    assert 362443480 - 7462000 - 7785400 != state["target_new_bound"]
    assert state["target_new_bound"] == 354658080
    assert result["NO_DOUBLE_COUNT_STATUS"] == "PASS_MAX_CREDITS_SUBTRACT_ONCE"


def test_complete_family_terms_owner_runner_up_and_digest(result: dict[str, Any]) -> None:
    family = result["FAMILY_RECOMPUTATION"]
    assert family["term_count"] == 56574
    assert family["changed_terms"] == 1
    assert family["preserved_terms"] == 56573
    assert family["baseline_digest"] == "ed40b014be4d95a310cf4816b1be3f8ca58fa6bb879f5f41af9aeaa194931c95"
    assert family["new_digest"] == "bf3f3df1496ab353813e4d8f400fae6eb7c837509a6b9c7375cd7f48f8aea074"
    assert family["owner"] == {
        "stable_id": "state:s2-13548976-s3-951748",
        "bound": 354981375,
    }
    assert family["runner_up"] == {
        "stable_id": "state:s2-12692531-s3-681744",
        "bound": 354980829,
    }
    assert family["incremental_gain"] == 105


def test_regressions_reject_missing_target_sum_credit_unsafe_leaf_and_stale_family(
    result: dict[str, Any],
) -> None:
    missing = copy.deepcopy(result)
    missing["STATE131"]["complete_region_members"] = [
        member
        for member in missing["STATE131"]["complete_region_members"]
        if member["member_id"] != "[0,17][25,1]"
    ]
    with pytest.raises(AssertionError):
        cert.verify_result(missing)

    unsafe_leaf = copy.deepcopy(result["H17_PROOF"])
    unsafe_leaf["type25_leaf"]["credit"] = 103880
    with pytest.raises(AssertionError):
        cert.verify_h17_proof(unsafe_leaf)

    stale_family = copy.deepcopy(result)
    state_term = next(
        term for term in stale_family["FINAL_STATE_TERMS"] if term["stable_id"] == cert.STATE131
    )
    state_term["bound"] = 354981480
    with pytest.raises(AssertionError):
        cert.verify_result(stale_family)


def test_regression_rejects_wrong_compressed_alias_max(result: dict[str, Any]) -> None:
    baseline = cert.load_baseline_result()
    alias = baseline["COMPRESSED_ALIASES"]["A2"][0]
    region = next(
        region for region in baseline["REGIONS"] if region["state_id"] == cert.legacy.STATE_A
    )
    member = copy.deepcopy(
        next(
            member
            for member in region["complete_region_members"]
            if member["member_id"] == alias["canonical_member_id"]
        )
    )
    vector_bounds = [row["final_bound"] for row in member["represented_vector_bounds"]]
    assert len(vector_bounds) == 2
    member["final_bound"] = min(vector_bounds) - 1
    with pytest.raises(AssertionError, match="MAX"):
        cert.validate_member_max(member)


def test_stored_result_replays_byte_for_byte() -> None:
    summary = cert.verify_stored_result()
    assert summary["status"] == "PASS"


def test_curated_merge_authority_passes_on_distinct_branch() -> None:
    branch = cert._git_bytes("branch", "--show-current").decode().strip()
    assert branch != cert.TASK_BRANCH

    h17_authority = cert.verify_source_authority()
    legacy_authority = cert.legacy.verify_source_authority()

    assert h17_authority["base_head"] == cert.BASE_HEAD
    assert legacy_authority["HEAD"] == cert.legacy.BASE_HEAD


@pytest.mark.parametrize("authority", ["h17", "legacy"])
def test_wrong_base_ancestry_is_rejected(
    monkeypatch: pytest.MonkeyPatch, authority: str
) -> None:
    base_head = cert.BASE_HEAD if authority == "h17" else cert.legacy.BASE_HEAD
    verify = (
        cert.verify_source_authority
        if authority == "h17"
        else cert.legacy.verify_source_authority
    )
    original_run = cert.subprocess.run

    def reject_pinned_ancestry(command: Any, *args: Any, **kwargs: Any) -> Any:
        argv = list(command)
        if (
            argv[:3] == ["git", "-C", str(cert.REPO_ROOT)]
            and argv[3:5] == ["merge-base", "--is-ancestor"]
            and argv[-2:] == [base_head, "HEAD"]
        ):
            return cert.subprocess.CompletedProcess(argv, 1)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(cert.subprocess, "run", reject_pinned_ancestry)
    with pytest.raises(AssertionError):
        verify()


@pytest.mark.parametrize("authority", ["h17", "legacy"])
def test_wrong_pinned_source_identity_is_rejected(
    monkeypatch: pytest.MonkeyPatch, authority: str
) -> None:
    module = cert if authority == "h17" else cert.legacy
    original_git_bytes = module._git_bytes if authority == "h17" else module.git_bytes

    def wrong_commit_tree(*args: str) -> bytes:
        if args[:3] == ("show", "-s", "--format=%H %T"):
            return b"0" * 40 + b" " + b"0" * 40
        return original_git_bytes(*args)

    monkeypatch.setattr(module, "_git_bytes" if authority == "h17" else "git_bytes", wrong_commit_tree)
    verify = (
        cert.verify_source_authority
        if authority == "h17"
        else cert.legacy.verify_source_authority
    )
    with pytest.raises(AssertionError):
        verify()
