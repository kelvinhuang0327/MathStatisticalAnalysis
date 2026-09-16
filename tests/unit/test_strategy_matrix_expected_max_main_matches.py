# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from lottolab.research.expected_max_main_matches import expected_max_main_matches
from lottolab.research.strategy_matrix_comparison import (
    EXPECTED_MAX_CORE_HEAD,
    EXPECTED_MAX_CORE_PATH,
    EXPECTED_MAX_CORE_TREE,
    EXPECTED_MAX_EXACT_1EXCHANGE,
    EXPECTED_MAX_EXACTNESS,
    EXPECTED_MAX_MAIN_MATCHES_V1,
    EXPECTED_MAX_RESULT_PATH,
    RESULT_PATH,
    TABU7_CANDIDATE_CASE_ID,
    _expected_max_discrimination,
    canonical_json_bytes,
    evaluate_expected_max_main_matches,
    parse_rational,
    rational,
)

ROOT = Path(__file__).resolve().parents[2]


def _stored_row(
    *,
    row_id: str = "TEST|METHOD_A|default|k2|m3",
    portfolio: tuple[tuple[int, ...], ...] = ((1, 2, 3), (4, 5, 6)),
    pool_size: int = 10,
    draw_size: int = 3,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "case_id": "TEST",
        "lottery": "SYNTHETIC",
        "k": len(portfolio),
        "strategy_id": "METHOD_A",
        "status": "MEASURED",
        "minimum_matches": 3,
        "portfolio": [list(ticket) for ticket in portfolio],
        "portfolio_sha256": hashlib.sha256(canonical_json_bytes(portfolio)).hexdigest(),
        "pool_size": pool_size,
        "draw_size": draw_size,
        "objective": "NATIVE_OBJECTIVE",
        "evaluation_objective": "UNIFORM_MAIN_DRAW_COVERAGE",
        "exact_q": None,
    }


def test_integration_matches_direct_core_invocation() -> None:
    row = _stored_row()
    integrated = evaluate_expected_max_main_matches(row)
    direct = expected_max_main_matches(
        10,
        3,
        ((1, 2, 3), (4, 5, 6)),
    )
    assert integrated == direct


def test_invalid_portfolio_is_rejected_before_evaluator_call() -> None:
    row = _stored_row(portfolio=((1, 2, 999), (4, 5, 6)))
    calls = 0

    def evaluator(
        _pool_size: int,
        _draw_size: int,
        _minimum_matches: int,
        _portfolio: tuple[tuple[int, ...], ...],
    ) -> Fraction:
        nonlocal calls
        calls += 1
        return Fraction(0)

    with pytest.raises(ValueError, match="illegal ticket"):
        evaluate_expected_max_main_matches(row, evaluator=evaluator)
    assert calls == 0


def test_rational_round_trip_is_exact() -> None:
    from lottolab.research.strategy_matrix_comparison import parse_rational

    value = Fraction(123, 456)
    assert parse_rational(rational(value)) == value
    assert rational(value) == {
        "numerator": 41,
        "denominator": 152,
        "exact": "41/152",
    }


def test_discrimination_classification_records_a_coverage_tie_separated_by_expected_max() -> None:
    cells = [
        {
            **_stored_row(row_id="TEST|A|default|k2|m3"),
            "portfolio_sha256": "a" * 64,
            "strategy_id": "METHOD_A",
            "native_exact_q": rational(Fraction(1, 2)),
            "expected_max_main_matches_v1": rational(Fraction(2, 1)),
        },
        {
            **_stored_row(row_id="TEST|B|default|k2|m3"),
            "portfolio_sha256": "b" * 64,
            "strategy_id": "METHOD_B",
            "native_exact_q": rational(Fraction(1, 2)),
            "expected_max_main_matches_v1": rational(Fraction(1, 1)),
        },
    ]
    evidence = _expected_max_discrimination(cells)
    assert evidence["overall_classification"] == "DISTINCT_OBJECTIVE_SIGNAL"
    assert evidence["separated_coverage_tie_count"] == 1
    assert evidence["different_relation_pair_count"] == 1


def test_expected_max_surface_constants_declare_exact_evaluation_only() -> None:
    assert EXPECTED_MAX_MAIN_MATCHES_V1 == "EXPECTED_MAX_MAIN_MATCHES_V1"
    assert EXPECTED_MAX_EXACTNESS == "EXACT_COMBINATORIAL_EXPECTATION"


def test_checked_in_surface_is_canonical_and_binds_the_frozen_inputs() -> None:
    artifact_path = ROOT / EXPECTED_MAX_RESULT_PATH
    artifact_bytes = artifact_path.read_bytes()
    artifact = json.loads(artifact_bytes)
    assert canonical_json_bytes(artifact) == artifact_bytes
    assert artifact["core_head"] == EXPECTED_MAX_CORE_HEAD
    assert artifact["core_tree"] == EXPECTED_MAX_CORE_TREE
    assert artifact["core"]["path"] == EXPECTED_MAX_CORE_PATH.as_posix()
    assert (
        artifact["core"]["sha256"]
        == hashlib.sha256((ROOT / EXPECTED_MAX_CORE_PATH).read_bytes()).hexdigest()
    )
    assert (
        artifact["matrix_source"]["sha256"]
        == hashlib.sha256(
            (ROOT / "src/lottolab/research/strategy_matrix_comparison.py").read_bytes()
        ).hexdigest()
    )
    input_path = ROOT / RESULT_PATH
    assert (
        artifact["input_canonical_result"]["sha256"]
        == hashlib.sha256(input_path.read_bytes()).hexdigest()
    )


def test_surface_preserves_existing_matrix_identity_fields_and_marks_gaps_explicitly() -> None:
    input_rows = {
        row["row_id"]: row for row in json.loads((ROOT / RESULT_PATH).read_text())["rows"]
    }
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    evaluated = {cell["row_id"]: cell for cell in artifact["evaluated_cells"]}
    unavailable = {cell["row_id"]: cell for cell in artifact["unavailable_cells"]}
    assert len(evaluated) == artifact["evaluated_cell_count"] == 253
    assert len(unavailable) == artifact["unavailable_cell_count"] == 124
    assert set(evaluated) | set(unavailable) == set(input_rows)
    assert not set(evaluated) & set(unavailable)

    for row_id, cell in evaluated.items():
        source = input_rows[row_id]
        assert source["portfolio"] is not None
        assert cell["portfolio_sha256"] == source["portfolio_sha256"]
        assert cell["strategy_id"] == source["strategy_id"]
        assert cell["native_method_objective"] == source["objective"]
        assert cell["native_evaluation_objective"] == source["evaluation_objective"]
        assert cell["native_exact_q"] == source["exact_q"]
        assert cell["evaluation_metric_id"] == EXPECTED_MAX_MAIN_MATCHES_V1
        assert cell["exactness"] == EXPECTED_MAX_EXACTNESS
        assert parse_rational(cell["expected_max_main_matches_v1"]) >= 0

    for row_id, cell in unavailable.items():
        assert input_rows[row_id]["portfolio"] is None
        assert "expected_max_main_matches_v1" not in cell
        assert cell["reason"].startswith("NO_CANONICAL_PORTFOLIO_STORED")

    gap = artifact["gap_semantics"]
    assert gap["previous_gap_id"] == "EXPECTED_HIT_UTILITY_CONTRACT"
    assert gap["contract_evaluator"] == "RESOLVED"
    assert gap["optimizer_gap_id"] == "EXPECTED_MAX_MAIN_MATCHES_OPTIMIZER"
    assert gap["optimizer_status"] == "RESOLVED"
    assert gap["dedicated_optimizer_implemented"] is True
    assert gap["dedicated_optimizer_id"] == "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1"
    assert gap["remaining_prospective_gap"] == "CROSS_STRUCTURE_EXPECTED_MAX_OPTIMIZATION"
    assert "DAILY_539 k2" in gap["existing_capability"]
    assert gap["missing_capability"] == "DAILY_539 k3, k5, k10, k20; POWER_LOTTO_ZONE1 replication."


def test_daily539_k2_adds_one_cell_and_preserves_all_252_existing_evaluations() -> None:
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    row_id = f"NATIVE_DAILY_539|{EXPECTED_MAX_EXACT_1EXCHANGE}|default|k2|m3"
    cells = {cell["row_id"]: cell for cell in artifact["evaluated_cells"]}
    cell = cells[row_id]
    assert cell["lottery"] == "DAILY_539"
    assert cell["k"] == 2
    assert cell["status"] == "MEASURED"
    assert cell["expected_max_main_matches_v1"] == rational(Fraction(597050, 575757))
    assert cell["native_exact_q"] == rational(Fraction(3854, 191919))
    assert artifact["claim_boundary"]["cross_lottery_normalization"] == "NOT_PERFORMED"
    # Frozen from producer commit 88a6892: the added cell must be the only
    # evaluated-cell change, including every BIG_LOTTO value and portfolio hash.
    previous_cells = [cell for cell in artifact["evaluated_cells"] if cell["row_id"] != row_id]
    assert len(previous_cells) == 252
    assert hashlib.sha256(canonical_json_bytes(previous_cells)).hexdigest() == (
        "aa49ad78598e1b2f770ad6c747205e944fb27d7e7a5af901b355493e1c978fbd"
    )
    evaluation = next(e for e in artifact["portfolio_evaluations"] if row_id in e["row_ids"])
    method_e_id = "NATIVE_DAILY_539|GREEDY_MINMAX_THEN_SUM_OVERLAP_V1|default|k2|m3"
    assert method_e_id in evaluation["row_ids"]
    assert evaluation["lottery"] == "DAILY_539"
    assert evaluation["expected_max_main_matches_v1"] == cell["expected_max_main_matches_v1"]
    unavailable = {cell["row_id"]: cell for cell in artifact["unavailable_cells"]}
    for k in (3, 5, 10, 20):
        sibling = unavailable[f"NATIVE_DAILY_539|{EXPECTED_MAX_EXACT_1EXCHANGE}|default|k{k}|m3"]
        assert sibling["status"] == "NOT_RUN"
        assert sibling["reason"] == (
            "NO_CANONICAL_PORTFOLIO_STORED:"
            "CANONICAL_EXPECTED_MAX_EXACT_1EXCHANGE_DAILY539_ARTIFACT_NOT_AVAILABLE_FOR_K"
        )


def test_surface_reuses_each_exact_value_for_every_duplicate_portfolio_identity() -> None:
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    cells = {cell["row_id"]: cell for cell in artifact["evaluated_cells"]}
    assert len(artifact["portfolio_evaluations"]) == 142
    for evaluation in artifact["portfolio_evaluations"]:
        row_ids = evaluation["row_ids"]
        assert evaluation["computed_once"] is True
        assert evaluation["reused_row_count"] == len(row_ids)
        values = {cells[row_id]["expected_max_main_matches_v1"]["exact"] for row_id in row_ids}
        assert values == {evaluation["expected_max_main_matches_v1"]["exact"]}


def test_surface_covers_every_existing_portfolio_supported_k_and_lottery_group() -> None:
    input_rows = json.loads((ROOT / RESULT_PATH).read_text())["rows"]
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    expected_groups = {
        (row["lottery"], row["k"]) for row in input_rows if row["portfolio"] is not None
    }
    actual_groups = {(cell["lottery"], cell["k"]) for cell in artifact["evaluated_cells"]}
    assert actual_groups == expected_groups
    assert {k for _, k in actual_groups} == {2, 3, 5, 10, 20}


def test_surface_has_a_distinct_objective_signal_without_a_leaderboard() -> None:
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    discrimination = artifact["objective_discrimination"]
    assert discrimination["overall_classification"] == "DISTINCT_OBJECTIVE_SIGNAL"
    assert discrimination["different_relation_pair_count"] > 0
    assert discrimination["separated_coverage_tie_count"] > 0
    assert artifact["claim_boundary"]["global_leaderboard"] == "NOT_PRODUCED"
    assert (
        artifact["claim_boundary"]["strategy_id_added"]
        == "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1"
    )
    assert artifact["claim_boundary"]["dedicated_optimizer_implemented"] == "YES"


def test_tabu7_candidate_rows_are_all_evaluated_and_bound_to_the_primary_artifact() -> None:
    """The five new Tabu7 candidate-source rows are exact-evaluated cells whose
    identity is bound to the primary Matrix artifact, never a leaderboard entry."""

    input_rows = {
        row["row_id"]: row for row in json.loads((ROOT / RESULT_PATH).read_text())["rows"]
    }
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    evaluated = {cell["row_id"]: cell for cell in artifact["evaluated_cells"]}

    tabu7_row_ids = {
        row_id for row_id, row in input_rows.items() if row["case_id"] == TABU7_CANDIDATE_CASE_ID
    }
    assert len(tabu7_row_ids) == 5
    assert tabu7_row_ids <= set(evaluated)

    for row_id in tabu7_row_ids:
        source = input_rows[row_id]
        cell = evaluated[row_id]
        assert source["portfolio"] is not None
        assert cell["strategy_id"] == "CANDIDATE_LOW_OVERLAP_V1"
        assert cell["portfolio_sha256"] == source["portfolio_sha256"]
        assert cell["native_method_objective"] == source["objective"]
        assert cell["native_evaluation_objective"] == "GEOMETRY" == source["evaluation_objective"]
        assert source["exact_q"] is None
        assert cell["native_exact_q"] is None
        assert cell["evaluation_metric_id"] == EXPECTED_MAX_MAIN_MATCHES_V1
        assert cell["exactness"] == EXPECTED_MAX_EXACTNESS

        # The exact expected-max value matches direct invocation of the existing
        # exact evaluator on the row's own stored portfolio -- never reconstructed.
        direct_value = evaluate_expected_max_main_matches(source)
        assert parse_rational(cell["expected_max_main_matches_v1"]) == direct_value
        assert direct_value >= 0

    assert artifact["claim_boundary"]["global_leaderboard"] == "NOT_PRODUCED"
    assert artifact["claim_boundary"]["cross_lottery_normalization"] == "NOT_PERFORMED"
