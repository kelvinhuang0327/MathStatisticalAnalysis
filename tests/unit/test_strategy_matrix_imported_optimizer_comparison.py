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
