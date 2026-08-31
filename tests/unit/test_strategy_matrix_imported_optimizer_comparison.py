"""Focused contract tests for the imported-optimizer Strategy Matrix."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from lottolab.research.biglotto_multi_ticket_constructors_r1 import CONSTRUCTORS
from lottolab.research.strategy_matrix_comparison import (
    BOUNDED,
    K_SCOPE,
    LEDGER_PATH,
    NATIVE_MEASUREMENT_PATH,
    RESULT_PATH,
    build_comparison,
    canonical_json_bytes,
)

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SURFACE = {
    "strategy_family",
    "strategy_id",
    "method_type",
    "portfolio_or_ticket_level",
    "supported_lottery",
    "supported_k",
    "objective",
    "search_type",
    "neighborhood_radius",
    "exact_or_heuristic",
    "diversification_constraint",
    "deterministic",
    "source_status",
    "evidence_source",
    "proof_status",
}


@pytest.fixture(scope="module")
def comparison() -> dict[str, Any]:
    return build_comparison(ROOT)


def test_intake_has_eleven_methods_six_deduplicated_families_and_full_surface(
    comparison: dict[str, Any],
) -> None:
    methods = comparison["methods"]
    assert comparison["imported_method_count"] == len(methods) == 11
    assert comparison["distinct_family_count"] == len(comparison["method_families"]) == 6
    assert len({method["strategy_id"] for method in methods}) == 11
    assert all(method.keys() >= REQUIRED_SURFACE for method in methods)

    bounded = next(method for method in methods if method["strategy_id"] == BOUNDED)
    assert {entry["path"] for entry in bounded["source_files"]} >= {
        "src/lottolab/research/bounded_coverage_optimizer.py",
        "src/lottolab/research/bounded_coverage_optimizer_fast.py",
    }
    assert not any("FAST" in method["strategy_id"] for method in methods)


def test_frozen_candidate_constructors_map_k_5_10_20_and_mark_low_k_not_applicable(
    comparison: dict[str, Any],
) -> None:
    methods = {method["strategy_id"]: method for method in comparison["methods"]}
    for strategy_id in CONSTRUCTORS:
        assert methods[strategy_id]["supported_k"] == [5, 10, 20]
        rows = [
            row
            for row in comparison["rows"]
            if row["strategy_id"] == strategy_id
            and row["case_id"].startswith("CANDIDATES_BIG_LOTTO_")
        ]
        by_k = {k: {row["status"] for row in rows if row["k"] == k} for k in K_SCOPE}
        assert by_k[2] == by_k[3] == {"NOT_APPLICABLE"}
        assert by_k[5] == by_k[10] == by_k[20] == {"MEASURED"}


def test_exact_evaluation_and_local_certificates_do_not_imply_global_optimum(
    comparison: dict[str, Any],
) -> None:
    exact_rows = [row for row in comparison["rows"] if row["exact_q"] is not None]
    assert exact_rows
    for row in exact_rows:
        q = Fraction(row["exact_q"]["exact"])
        if row["global_optimum_status"] == "CERTIFIED_BY_UNIT_UPPER_BOUND":
            assert q == 1
            assert row["proof_status"] == "GLOBAL_OPTIMUM_CERTIFIED_BY_UNIT_UPPER_BOUND"
        else:
            assert row["global_optimum_status"] == "UNKNOWN"

    local_rows = [
        row
        for row in exact_rows
        if row["local_optimum_status"] == "CERTIFIED_ONE_NUMBER_EXCHANGE"
        and Fraction(row["exact_q"]["exact"]) < 1
    ]
    assert local_rows
    assert all("NO_GLOBAL_PROOF" in row["proof_status"] for row in local_rows)


def test_missing_search_capabilities_are_explicit_gaps_not_false_results(
    comparison: dict[str, Any],
) -> None:
    gaps = {gap["gap_id"]: gap for gap in comparison["gaps"]}
    assert {
        "GLOBAL_EXACT_SOLVER",
        "TWO_EXCHANGE_AND_RADIUS_N",
        "COVERAGE_WITH_HARD_DIVERSIFICATION",
        "EXPECTED_HIT_UTILITY_CONTRACT",
    } <= gaps.keys()
    assert gaps["GLOBAL_EXACT_SOLVER"]["category"] == "METHOD_GAPS"
    assert gaps["TWO_EXCHANGE_AND_RADIUS_N"]["category"] == "SEARCH_GAPS"
    assert set(comparison["handoffs"]["branch_3"]) == {
        "GLOBAL_EXACT_SOLVER",
        "K_GAP_NATIVE_CANDIDATE_CONSTRUCTORS",
        "TWO_EXCHANGE_AND_RADIUS_N",
        "COVERAGE_WITH_HARD_DIVERSIFICATION",
    }
    assert gaps["EXPECTED_HIT_UTILITY_CONTRACT"]["handoff_branch"] is None
    assert not any(
        row["search_type"] in {"GLOBAL_EXACT_SOLVER", "TWO_EXCHANGE", "RADIUS_N"}
        for row in comparison["rows"]
    )


def test_new_comparisons_and_reused_native_evidence_remain_disjoint(
    comparison: dict[str, Any],
) -> None:
    measured = {row["row_id"] for row in comparison["rows"] if row["status"] == "MEASURED"}
    reused = {row["row_id"] for row in comparison["rows"] if row["status"] == "REUSED_VERIFIED"}
    assert measured == set(comparison["new_deterministic_comparison_row_ids"])
    assert reused == set(comparison["reused_native_evidence_row_ids"])
    assert measured and reused and measured.isdisjoint(reused)
    assert all(
        row["source_evidence"] is not None
        for row in comparison["rows"]
        if row["status"] == "REUSED_VERIFIED"
    )


def test_native_measurement_artifact_closes_open_cells_without_pooling_evidence(
    comparison: dict[str, Any],
) -> None:
    ledger = json.loads((ROOT / LEDGER_PATH).read_text())
    entry = ledger["imported_optimizer_matrix"]["native_evidence"]["native_coverage_r1"]
    artifact_path = ROOT / NATIVE_MEASUREMENT_PATH
    artifact = json.loads(artifact_path.read_text())

    assert entry["evidence_class"] == "NEW_NATIVE_MEASURED_EVIDENCE"
    assert entry["path"] == NATIVE_MEASUREMENT_PATH.as_posix()
    assert entry["sha256"] == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    assert artifact["starting_supported_native_not_run_count"] == 79
    assert artifact["new_native_measured_count"] == 73
    assert artifact["remaining_native_not_run_count"] == 6
    assert len(artifact["rows"]) == 79
    assert canonical_json_bytes(artifact) == artifact_path.read_bytes()

    measured = [row for row in artifact["rows"] if row["status"] == "MEASURED"]
    not_run = [row for row in artifact["rows"] if row["status"] == "NOT_RUN"]
    assert all(
        row["measurement_evidence"]["execution_classification"]
        == "EXECUTED_EXISTING_NATIVE_METHOD"
        for row in measured
    )
    assert all(
        row["measurement_evidence"]["execution_classification"]
        == "NOT_RUN_RESOURCE_BOUND"
        and row["measurement_evidence"]["dependency"]
        == "MEMORY_BOUNDED_EXACT_ONE_EXCHANGE_EVALUATOR"
        and row["exact_q"] is None
        and row["portfolio"] is None
        for row in not_run
    )

    native_rows = [row for row in comparison["rows"] if row["case_id"].startswith("NATIVE_")]
    new_native_rows = [
        row
        for row in native_rows
        if row["status"] == "MEASURED"
        and row["source_evidence"] is not None
        and row["source_evidence"]["path"] == NATIVE_MEASUREMENT_PATH.as_posix()
    ]
    assert len(new_native_rows) == 73
    assert all(row["evidence_scope"] == "NATIVE_UNIFORM_WINNING_SPACE" for row in new_native_rows)
    assert all(
        row["status"] in {"REUSED_VERIFIED", "NOT_APPLICABLE", "NOT_RUN"}
        or row["source_evidence"]["evidence_class"] == "NEW_NATIVE_MEASURED_EVIDENCE"
        for row in native_rows
    )

    geometry_rows = [
        row
        for row in comparison["rows"]
        if row["evidence_scope"] == "NATIVE_RULE_SYNTHETIC_CANDIDATE_GEOMETRY"
        and row.get("coverage_status") is not None
    ]
    assert geometry_rows
    assert all(row["coverage_status"] == "NOT_RUN" for row in geometry_rows)


def test_canonical_ledger_is_consumed_and_build_is_deterministic(
    comparison: dict[str, Any],
) -> None:
    ledger = json.loads((ROOT / LEDGER_PATH).read_text())
    intake = ledger["imported_optimizer_matrix"]
    assert intake["canonical_result_path"] == RESULT_PATH.as_posix()
    assert (
        comparison["matrix_intake_sha256"]
        == hashlib.sha256(canonical_json_bytes(intake)).hexdigest()
    )
    assert canonical_json_bytes(comparison) == canonical_json_bytes(build_comparison(ROOT))


def test_checked_in_result_is_the_canonical_build(comparison: dict[str, Any]) -> None:
    assert (ROOT / RESULT_PATH).read_bytes() == canonical_json_bytes(comparison)
