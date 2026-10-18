"""Focused regression checks for the State135 H10 certificate adoption."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from lottolab.research import (
    b649_k20_r3_post_h17_state135_h10_12_r1 as cert,
)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


@pytest.fixture(scope="module")
def source_context() -> tuple[dict[str, Any], dict[str, Any], set[str]]:
    h17, h13, _ = cert.read_inputs()
    existing = cert._previous_correction_members(h13, h17)
    return h17, h13, existing


def test_fixed_identity_and_exact_twelve_member_vector_coverage(
    result: dict[str, Any],
) -> None:
    coverage = result["TARGET_COVERAGE"]
    assert result["BASE_HEAD"] == cert.BASE_HEAD
    assert result["BASE_TREE"] == cert.BASE_TREE
    assert result["TASK_BRANCH"] == cert.TASK_BRANCH
    assert coverage["P_members"] == coverage["P_vectors"] == 6
    assert coverage["Q_members"] == coverage["Q_vectors"] == 6
    assert coverage["distinct_members"] == coverage["represented_vectors"] == 12
    assert coverage["target_aliases"] == 0
    assert coverage["existing_correction_overlap"] == 0
    assert result["PREVIOUS_SCOPE"]["cumulative_members"] == 125
    assert result["PREVIOUS_SCOPE"]["cumulative_vectors"] == 136


def test_all_target_bounds_use_max_credit_once(result: dict[str, Any]) -> None:
    state = result["STATE135"]
    records = state["target_certificates"]
    assert len(records) == 12
    for record in records:
        assert record["existing_credit"] == 3_444_000
        assert record["h10_credit"] == 3_767_400
        assert record["effective_credit"] == max(
            record["existing_credit"], record["h10_credit"]
        )
        assert record["uncorrected_bound"] - record["effective_credit"] == record["new_bound"]
        assert record["represented_vector_count"] == 1
        assert record["target_aliases"] == 0

    assert {record["new_bound"] for record in records if record["cohort"] == "P"} == {
        354_657_975
    }
    assert {record["new_bound"] for record in records if record["cohort"] == "Q"} == {
        354_657_527
    }
    assert state["preserved_member_count"] == 1_415
    assert state["preserved_vector_count"] == 1_531
    assert state["preserved_remainder_max"] == 354_980_479
    assert state["new_state_bound"] == 354_980_479


def test_h10_universal_certificate_and_zero_credit_leaf_tree(
    result: dict[str, Any],
) -> None:
    proof = result["H10_CERTIFICATE"]
    assert proof["core_type"] == 0
    assert proof["core_event_count"] == 10
    assert proof["core_pair_floors"] == [107_800, 574_000, 1_691_620, 3_451_651]
    assert proof["threshold_minimum"]["collision_floor"] == 20
    assert proof["threshold_minimum"]["threshold_cases"] == 16_982
    assert proof["threshold_minimum"]["ranks"] == [6, 0, 0]
    assert proof["credit"] == 3_767_400
    assert proof["proof_scope"] == "ALL_LEGAL_SUPPORTS"
    assert proof["witness_used_as_proof"] is False

    tree = proof["tree_extension"]
    assert tree["vertices"] == 18
    assert tree["edges"] == tree["distinct_edges"] == 17
    assert tree["leaf_edge_credits"] == [0] * 8
    assert tree["leaf_credit_total"] == 0
    assert tree["is_tree"] is True
    for target in result["STATE135"]["target_certificates"]:
        assert target["tree_extension"]["leaf_event_count"] == 8
        assert target["tree_extension"]["leaf_edge_credits"] == [0] * 8


def test_complete_family_terms_are_recomputed_from_the_actual_sequence(
    result: dict[str, Any],
) -> None:
    h17, _, classified = cert.read_inputs()
    terms = list(cert._family_terms(h17, classified))
    target_index = next(
        i for i, (stable_id, _) in enumerate(terms) if stable_id == cert.STATE135
    )
    terms[target_index] = (cert.STATE135, 354_980_479)
    actual_digest = cert._terms_digest(tuple(terms))

    family = result["FAMILY_RECOMPUTATION"]
    assert len(terms) == 56_574
    assert family["classified_term_count"] == 56_550
    assert family["baseline_digest"] == cert.EXPECTED_BASELINE_FAMILY_DIGEST
    assert actual_digest == cert.EXPECTED_FINAL_FAMILY_DIGEST
    assert family["new_digest"] == actual_digest
    assert family["changed_terms"] == 1
    assert family["preserved_terms"] == 56_573
    assert family["incremental_gain"] == 546
    assert family["final_max"] == 354_980_829
    assert family["owner"] == {
        "stable_id": "state:s2-12692531-s3-681744",
        "bound": 354_980_829,
    }
    assert family["runner_up"] == {
        "stable_id": cert.STATE135,
        "bound": 354_980_479,
    }
    assert family["owner_runner_up_gap"] == 350


@pytest.mark.parametrize("cohort", ["P", "Q"])
def test_regression_rejects_a_missing_target_member(
    result: dict[str, Any],
    source_context: tuple[dict[str, Any], dict[str, Any], set[str]],
    cohort: str,
) -> None:
    h17, h13, existing = source_context
    source_region = next(
        region for region in h13["REGIONS"] if region["state_id"] == cert.STATE135
    )
    rows = copy.deepcopy(source_region["complete_region_members"])
    missing = next(spec for spec in cert.target_specs() if spec["cohort"] == cohort)
    rows = [row for row in rows if row["member_id"] != missing["member_id"]]

    with pytest.raises(AssertionError):
        cert.apply_state135(
            h13,
            h17,
            result["H10_CERTIFICATE"],
            existing,
            member_rows=rows,
        )


def test_regression_rejects_illegal_addition_of_credits(result: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(result["STATE135"])
    corrupted["target_certificates"][0]["effective_credit"] = (
        corrupted["target_certificates"][0]["existing_credit"]
        + corrupted["target_certificates"][0]["h10_credit"]
    )
    with pytest.raises(AssertionError, match="MAX and subtracted once"):
        cert.verify_state135_payload(corrupted)


def test_regression_rejects_a_paid_zero_credit_leaf(result: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(result["H10_CERTIFICATE"])
    corrupted["tree_extension"]["leaf_edge_credits"][0] = 107_800
    with pytest.raises(AssertionError, match="zero-credit tree"):
        cert.validate_h10_certificate(corrupted)


def test_regression_rejects_wrong_compressed_member_max(result: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(result["STATE135"])
    member = next(
        row
        for row in corrupted["complete_region_members"]
        if int(row["represented_vector_count"]) > 1
    )
    member.pop("new_bound", None)
    vector_rows = member["represented_vector_bounds"]
    for row in vector_rows:
        row.pop("new_bound", None)
    vector_rows[0]["final_bound"] = int(member["final_bound"]) + 1

    with pytest.raises(AssertionError, match="MAX"):
        cert._validate_member_max(member)


def test_regression_rejects_stale_state135_and_family_terms(
    result: dict[str, Any],
) -> None:
    stale_state = copy.deepcopy(result)
    state_index = next(
        i
        for i, term in enumerate(stale_state["FINAL_STATE_TERMS"])
        if term["stable_id"] == cert.STATE135
    )
    stale_state["FINAL_STATE_TERMS"][state_index]["bound"] = 354_981_375
    with pytest.raises(AssertionError, match="source-bound deterministic replay"):
        cert.verify_result(stale_state)

    stale_family = copy.deepcopy(result)
    stale_family["FAMILY_RECOMPUTATION"]["new_digest"] = (
        cert.EXPECTED_BASELINE_FAMILY_DIGEST
    )
    with pytest.raises(AssertionError, match="source-bound deterministic replay"):
        cert.verify_result(stale_family)


def test_stored_result_replays_byte_for_byte() -> None:
    summary = cert.verify_stored_result()
    assert summary["status"] == "PASS"
    assert summary["target_members"] == 12
    assert summary["target_vectors"] == 12
    assert summary["target_aliases"] == 0
    assert summary["h10_credit"] == 3_767_400
    assert summary["new_state135_ub"] == 354_980_479
    assert summary["family_ub"] == 354_980_829
    assert summary["family_gain"] == 546
    assert summary["family_digest"] == cert.EXPECTED_FINAL_FAMILY_DIGEST
