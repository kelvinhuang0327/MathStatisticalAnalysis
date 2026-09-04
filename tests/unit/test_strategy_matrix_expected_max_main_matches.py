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
    EXPECTED_MAX_EXACTNESS,
    EXPECTED_MAX_MAIN_MATCHES_V1,
    EXPECTED_MAX_RESULT_PATH,
    RESULT_PATH,
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
    assert artifact["core"]["sha256"] == hashlib.sha256(
        (ROOT / EXPECTED_MAX_CORE_PATH).read_bytes()
    ).hexdigest()
    assert artifact["matrix_source"]["sha256"] == hashlib.sha256(
        (ROOT / "src/lottolab/research/strategy_matrix_comparison.py").read_bytes()
    ).hexdigest()
    input_path = ROOT / RESULT_PATH
    assert artifact["input_canonical_result"]["sha256"] == hashlib.sha256(
        input_path.read_bytes()
    ).hexdigest()


def test_surface_preserves_existing_matrix_identity_fields_and_marks_gaps_explicitly() -> None:
    input_rows = {
        row["row_id"]: row
        for row in json.loads((ROOT / RESULT_PATH).read_text())["rows"]
    }
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    evaluated = {cell["row_id"]: cell for cell in artifact["evaluated_cells"]}
    unavailable = {cell["row_id"]: cell for cell in artifact["unavailable_cells"]}
    assert len(evaluated) == 242
    assert len(unavailable) == 115
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
    assert gap["remaining_prospective_gap"] == "EXPECTED_MAX_MAIN_MATCHES_OPTIMIZER"
    assert gap["dedicated_optimizer_implemented"] is False


def test_surface_reuses_each_exact_value_for_every_duplicate_portfolio_identity() -> None:
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    cells = {cell["row_id"]: cell for cell in artifact["evaluated_cells"]}
    assert len(artifact["portfolio_evaluations"]) == 136
    for evaluation in artifact["portfolio_evaluations"]:
        row_ids = evaluation["row_ids"]
        assert evaluation["computed_once"] is True
        assert evaluation["reused_row_count"] == len(row_ids)
        values = {
            cells[row_id]["expected_max_main_matches_v1"]["exact"] for row_id in row_ids
        }
        assert values == {evaluation["expected_max_main_matches_v1"]["exact"]}


def test_surface_covers_every_existing_portfolio_supported_k_and_lottery_group() -> None:
    input_rows = json.loads((ROOT / RESULT_PATH).read_text())["rows"]
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    expected_groups = {
        (row["lottery"], row["k"])
        for row in input_rows
        if row["portfolio"] is not None
    }
    actual_groups = {
        (cell["lottery"], cell["k"]) for cell in artifact["evaluated_cells"]
    }
    assert actual_groups == expected_groups
    assert {k for _, k in actual_groups} == {2, 3, 5, 10, 20}


def test_surface_has_a_distinct_objective_signal_without_a_leaderboard() -> None:
    artifact = json.loads((ROOT / EXPECTED_MAX_RESULT_PATH).read_text())
    discrimination = artifact["objective_discrimination"]
    assert discrimination["overall_classification"] == "DISTINCT_OBJECTIVE_SIGNAL"
    assert discrimination["different_relation_pair_count"] > 0
    assert discrimination["separated_coverage_tie_count"] > 0
    assert artifact["claim_boundary"]["global_leaderboard"] == "NOT_PRODUCED"
    assert artifact["claim_boundary"]["strategy_id_added"] == "NO"
