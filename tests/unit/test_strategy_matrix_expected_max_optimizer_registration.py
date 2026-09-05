# pyright: reportPrivateUsage=false

"""Dedicated unit tests for ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1 registration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research.strategy_matrix_comparison import (
    EXPECTED_MAX_EXACT_1EXCHANGE,
    EXPECTED_MAX_EXACT_1EXCHANGE_ASCENT_PATH,
    EXPECTED_MAX_EXACT_1EXCHANGE_ASCENT_SHA256,
    EXPECTED_MAX_MAIN_MATCHES_V1,
    EXPECTED_MAX_RESULT_PATH,
    LEDGER_PATH,
    NATIVE_PORTFOLIO_HASH_CANONICALIZATION,
    RESULT_PATH,
    canonical_json_bytes,
)

ROOT = Path(__file__).resolve().parents[2]

FROZEN_ASCENT_EXPECTATIONS: dict[int, dict[str, str]] = {
    2: {
        "terminal_expected_max": "677444/582659",
        "exact_q": "21702/582659",
        "move_count": "0",
        "iteration_count": "1",
        "delta_seed": "0/1",
        "delta_ref": "0/1",
        "local_optimum_status": "COMPLETE_RADIUS_1_LOCAL_OPTIMUM",
        "terminal_sha256": "e0e10f5293e03f95e34a89ac7c39ad4fa4cd1d7140b283294c022d1669e9ef83",
    },
    3: {
        "terminal_expected_max": "1657533/1165318",
        "exact_q": "32528/582659",
        "move_count": "0",
        "iteration_count": "1",
        "delta_seed": "0/1",
        "delta_ref": "0/1",
        "local_optimum_status": "COMPLETE_RADIUS_1_LOCAL_OPTIMUM",
        "terminal_sha256": "a454b5611aa0dbc16b95b148d4b1b0256ea2d96329e88a7b22b81384df4fcb22",
    },
    5: {
        "terminal_expected_max": "43822/25333",
        "exact_q": "54130/582659",
        "move_count": "0",
        "iteration_count": "1",
        "delta_seed": "0/1",
        "delta_ref": "0/1",
        "local_optimum_status": "COMPLETE_RADIUS_1_LOCAL_OPTIMUM",
        "terminal_sha256": "ec858fe04075ee40931366c05617ad7d04d934c5f72ac35c9b74c26ba91f8d87",
    },
    10: {
        "terminal_expected_max": "7381249/3495954",
        "exact_q": "90995/499422",
        "move_count": "1",
        "iteration_count": "2",
        "delta_seed": "3560/1747977",
        "delta_ref": "40/1747977",
        "local_optimum_status": "COMPLETE_RADIUS_1_LOCAL_OPTIMUM",
        "terminal_sha256": "4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5",
    },
}


@pytest.fixture(scope="module")
def comparison() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((ROOT / RESULT_PATH).read_text()))


@pytest.fixture(scope="module")
def expected_max_surface() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text()))


@pytest.fixture(scope="module")
def ledger() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((ROOT / LEDGER_PATH).read_text()))


def test_registered_method_metadata_and_ledger_intake(
    comparison: dict[str, Any],
    ledger: dict[str, Any],
) -> None:
    intake_methods = {m["strategy_id"]: m for m in ledger["imported_optimizer_matrix"]["methods"]}
    assert EXPECTED_MAX_EXACT_1EXCHANGE in intake_methods
    intake = intake_methods[EXPECTED_MAX_EXACT_1EXCHANGE]
    assert intake["strategy_family"] == "EXACT_ONE_NUMBER_EXCHANGE"
    assert intake["objective"] == EXPECTED_MAX_MAIN_MATCHES_V1
    assert intake["neighborhood_radius"] == 1
    assert intake["supported_lottery"] == ["BIG_LOTTO"]
    assert intake["supported_k"] == [2, 3, 5, 10]
    assert intake["source_status"] == "IMPLEMENTED"
    assert intake["search_type"] == "EXACT_ONE_NUMBER_EXCHANGE_LOCAL_ASCENT"
    assert intake["exact_or_heuristic"] == "EXACT_RADIUS_1_LOCAL_ASCENT"
    assert intake["proof_status"] == "COMPLETE_RADIUS_1_LOCAL_OPTIMUM"
    assert any(
        sf["path"] == "src/lottolab/research/expected_max_main_matches_exact_1exchange_ascent.py"
        for sf in intake["source_files"]
    )

    matrix_methods = {m["strategy_id"]: m for m in comparison["methods"]}
    assert EXPECTED_MAX_EXACT_1EXCHANGE in matrix_methods
    method = matrix_methods[EXPECTED_MAX_EXACT_1EXCHANGE]
    assert method == intake

    evidence_entry = ledger["imported_optimizer_matrix"]["native_evidence"][
        "expected_max_exact_1exchange_ascent"
    ]
    assert evidence_entry["evidence_class"] == "EXISTING_NATIVE_EXACT_EVIDENCE"
    assert evidence_entry["path"] == EXPECTED_MAX_EXACT_1EXCHANGE_ASCENT_PATH.as_posix()
    assert (
        evidence_entry["sha256"]
        == hashlib.sha256(
            (ROOT / EXPECTED_MAX_EXACT_1EXCHANGE_ASCENT_PATH).read_bytes()
        ).hexdigest()
    )


def test_registered_method_row_structure_and_counts(comparison: dict[str, Any]) -> None:
    rows = [row for row in comparison["rows"] if row["strategy_id"] == EXPECTED_MAX_EXACT_1EXCHANGE]
    assert len(rows) == 15

    measured = [row for row in rows if row["status"] == "MEASURED"]
    not_applicable = [row for row in rows if row["status"] == "NOT_APPLICABLE"]
    assert len(measured) == 4
    assert len(not_applicable) == 11
    assert not any(row["status"] == "NOT_RUN" for row in rows)

    assert {row["lottery"] for row in measured} == {"BIG_LOTTO"}
    assert {row["k"] for row in measured} == {2, 3, 5, 10}
    assert all(row["case_id"] == "NATIVE_BIG_LOTTO" for row in measured)
    assert all(row["evidence_scope"] == "NATIVE_UNIFORM_WINNING_SPACE" for row in measured)
    assert all(row["minimum_matches"] == 3 for row in measured)

    unsupported_lotteries = [
        row for row in not_applicable if row["lottery"] in {"DAILY_539", "POWER_LOTTO_ZONE1"}
    ]
    assert len(unsupported_lotteries) == 10
    k20_row = [row for row in not_applicable if row["lottery"] == "BIG_LOTTO"]
    assert len(k20_row) == 1
    assert k20_row[0]["k"] == 20
    assert all(row["status_reason"] == "UNSUPPORTED_LOTTERY_OR_K" for row in not_applicable)
    assert all(row["exact_q"] is None for row in not_applicable)
    assert all(row["portfolio"] is None for row in not_applicable)


def test_measured_rows_reproduce_exact_metrics_and_local_certificates(
    comparison: dict[str, Any],
) -> None:
    measured = {
        row["k"]: row
        for row in comparison["rows"]
        if row["strategy_id"] == EXPECTED_MAX_EXACT_1EXCHANGE and row["status"] == "MEASURED"
    }

    for k, expected in FROZEN_ASCENT_EXPECTATIONS.items():
        row = measured[k]
        assert row["exact_q"]["exact"] == expected["exact_q"]
        assert row["local_optimum_status"] == expected["local_optimum_status"]
        assert row["global_optimum_status"] == "UNKNOWN"
        assert row["proof_status"] == "COMPLETE_RADIUS_1_LOCAL_OPTIMUM"
        assert row["native_portfolio_sha256"] == expected["terminal_sha256"]
        assert (
            row["native_portfolio_sha256_canonicalization"]
            == NATIVE_PORTFOLIO_HASH_CANONICALIZATION
        )

        search_ev = row["search_evidence"]
        assert search_ev["neighborhood_unit"] == "REMOVE_ONE_ADD_ONE_NUMBER_IN_ONE_TICKET"
        assert search_ev["neighborhood_radius"] == 1
        assert str(search_ev["move_count"]) == expected["move_count"]
        assert str(search_ev["iteration_count"]) == expected["iteration_count"]
        assert search_ev["terminal_expected_max"]["exact"] == expected["terminal_expected_max"]
        assert search_ev["local_optimum_status"] == expected["local_optimum_status"]

        delta_obj = search_ev["delta_seed_to_terminal"]
        assert delta_obj["exact"] == expected["delta_seed"]

        delta_vs_ref = row["delta_vs_reference"]
        assert delta_vs_ref["exact"] == expected["delta_ref"]
        assert row["reference"]["strategy_id"] == "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"


def test_expected_max_surface_evaluations_and_gap_closure(
    expected_max_surface: dict[str, Any],
) -> None:
    evaluated = {
        cell["k"]: cell
        for cell in expected_max_surface["evaluated_cells"]
        if cell["strategy_id"] == EXPECTED_MAX_EXACT_1EXCHANGE
    }
    assert set(evaluated.keys()) == {2, 3, 5, 10}

    for k, expected in FROZEN_ASCENT_EXPECTATIONS.items():
        cell = evaluated[k]
        assert cell["evaluation_metric_id"] == EXPECTED_MAX_MAIN_MATCHES_V1
        assert cell["expected_max_main_matches_v1"]["exact"] == expected["terminal_expected_max"]
        assert cell["native_exact_q"]["exact"] == expected["exact_q"]
        assert cell["portfolio_sha256"] is not None

    gap = expected_max_surface["gap_semantics"]
    assert gap["previous_gap_id"] == "EXPECTED_HIT_UTILITY_CONTRACT"
    assert gap["contract_evaluator"] == "RESOLVED"
    assert gap["optimizer_gap_id"] == "EXPECTED_MAX_MAIN_MATCHES_OPTIMIZER"
    assert gap["optimizer_status"] == "RESOLVED"
    assert gap["dedicated_optimizer_implemented"] is True
    assert gap["dedicated_optimizer_id"] == EXPECTED_MAX_EXACT_1EXCHANGE
    assert gap["remaining_prospective_gap"] == "CROSS_STRUCTURE_AND_K20_EXPECTED_MAX_OPTIMIZATION"

    claim_boundary = expected_max_surface["claim_boundary"]
    assert claim_boundary["historical_outcomes_used"] == "NO"
    assert claim_boundary["historical_replay"] == "NOT_RUN"
    assert claim_boundary["strategy_id_added"] == EXPECTED_MAX_EXACT_1EXCHANGE
    assert claim_boundary["dedicated_optimizer_implemented"] == "YES"
    assert claim_boundary["global_leaderboard"] == "NOT_PRODUCED"
    assert claim_boundary["production_mutation"] == "NONE"


def test_matrix_comparison_gap_resolution(comparison: dict[str, Any]) -> None:
    gaps = {g["gap_id"]: g for g in comparison["gaps"]}
    assert "EXPECTED_HIT_UTILITY_CONTRACT" in gaps
    gap = gaps["EXPECTED_HIT_UTILITY_CONTRACT"]
    assert gap["category"] == "OBJECTIVE_GAPS"
    assert EXPECTED_MAX_EXACT_1EXCHANGE in gap["existing_capability"]
    assert "k=20" in gap["missing_capability"]
    assert "Daily 539" in gap["missing_capability"]


def test_registration_result_artifact_is_canonical_and_complete() -> None:
    path = ROOT / (
        "docs/research/matrix-native-results/"
        "expected-max-optimizer-matrix-registration-r1-result.json"
    )
    assert path.exists()
    content = path.read_bytes()
    artifact = json.loads(content.decode("utf-8"))
    assert canonical_json_bytes(artifact) == content

    assert artifact["task_id"] == "EXPECTED_MAX_MAIN_MATCHES_OPTIMIZER_MATRIX_REGISTRATION_R1"
    assert artifact["registration_status"] == "REGISTERED"
    assert artifact["strategy_id"] == EXPECTED_MAX_EXACT_1EXCHANGE
    assert artifact["supported_k"] == [2, 3, 5, 10]
    assert artifact["deferred_k"] == [20]
    assert artifact["upstream_authority"]["sha256"] == EXPECTED_MAX_EXACT_1EXCHANGE_ASCENT_SHA256

    for k_str, rel in artifact["portfolio_relation_to_method_e"].items():
        if k_str in {"2", "3", "5"}:
            assert rel == "IDENTICAL_TO_METHOD_E_SEED"
        else:
            assert rel == "DISTINCT_TERMINAL_PORTFOLIO_AFTER_1_ACCEPTED_MOVE"

    assert artifact["claim_boundary"]["optimizer_rerun"] == "NO"
    assert artifact["claim_boundary"]["historical_replay"] == "NOT_RUN"
    assert artifact["claim_boundary"]["ranking"] == "NOT_RUN"
    assert artifact["claim_boundary"]["production_mutation"] == "NONE"
