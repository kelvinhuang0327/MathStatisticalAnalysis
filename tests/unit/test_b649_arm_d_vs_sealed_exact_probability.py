"""Focused unit tests for b649_arm_d_vs_sealed_exact_probability module."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import pytest

from lottolab.research.b649_arm_d_vs_sealed_exact_probability import (
    EXPECTED_ARCHIVE_ROW_COUNT,
    EXPECTED_SEALED_PROBABILITY_K10,
    EXPECTED_SEALED_PROBABILITY_K20,
    LABEL_SUCCESS,
    PRIMARY_K,
    SECONDARY_K,
    TOTAL_OUTCOME_SPACE,
    UPSTREAM_AUTHORITY_LOCATOR,
    InconclusiveGateError,
    evaluate_arm_d_stream,
    generate_markdown_report,
    load_frozen_arm_d_archive,
    verify_evaluator_content_sha256,
    verify_production_sealed_portfolios,
    verify_upstream_authority_file,
)
from lottolab.research.b649_official_any_prize_exact import DrawMasks, all_main_draw_masks


@pytest.fixture(scope="module")
def shared_draws() -> DrawMasks:
    return all_main_draw_masks(49, 6)


def test_verify_upstream_authority_file_success() -> None:
    verify_upstream_authority_file(UPSTREAM_AUTHORITY_LOCATOR)


def test_verify_upstream_authority_file_fails_on_missing(tmp_path: Path) -> None:
    with pytest.raises(InconclusiveGateError, match="absent"):
        verify_upstream_authority_file(tmp_path / "nonexistent.json")


def test_verify_upstream_authority_file_fails_on_mismatch(tmp_path: Path) -> None:
    tampered = tmp_path / "tampered.json"
    tampered.write_text('{"bad": "data"}', encoding="utf-8")
    with pytest.raises(InconclusiveGateError, match="mismatch"):
        verify_upstream_authority_file(tampered)


def test_verify_evaluator_content_sha256_success() -> None:
    verify_evaluator_content_sha256()


def test_verify_evaluator_content_sha256_fails_on_mismatch(tmp_path: Path) -> None:
    tampered = tmp_path / "eval.py"
    tampered.write_text("# tampered code\n", encoding="utf-8")
    with pytest.raises(InconclusiveGateError, match="mismatch"):
        verify_evaluator_content_sha256(tampered)


def test_verify_production_sealed_portfolios_reproduce_exact_probabilities(
    shared_draws: DrawMasks,
) -> None:
    probs = verify_production_sealed_portfolios(draws=shared_draws)
    assert probs[PRIMARY_K] == EXPECTED_SEALED_PROBABILITY_K10
    assert probs[SECONDARY_K] == EXPECTED_SEALED_PROBABILITY_K20


def test_load_frozen_arm_d_archive_contract() -> None:
    target_draws, portfolios = load_frozen_arm_d_archive(UPSTREAM_AUTHORITY_LOCATOR)

    assert len(target_draws) == EXPECTED_ARCHIVE_ROW_COUNT
    assert len(portfolios[PRIMARY_K]) == EXPECTED_ARCHIVE_ROW_COUNT
    assert len(portfolios[SECONDARY_K]) == EXPECTED_ARCHIVE_ROW_COUNT

    # Validate structure of loaded portfolios
    for k in (PRIMARY_K, SECONDARY_K):
        for p in portfolios[k]:
            assert len(p) == k
            for ticket in p:
                assert len(ticket) == 6
                assert sorted(ticket) == list(ticket)
                assert all(1 <= n <= 49 for n in ticket)


def test_load_frozen_arm_d_archive_fails_on_target_draw_divergence(tmp_path: Path) -> None:
    raw = json.loads(Path(UPSTREAM_AUTHORITY_LOCATOR).read_text(encoding="utf-8"))
    # Corrupt target draw in K20 first row
    raw["by_k"]["20"]["paired_draws"][0]["target_draw"] = 99999999

    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(raw), encoding="utf-8")

    patch_target = (
        "lottolab.research.b649_arm_d_vs_sealed_exact_probability."
        "verify_upstream_authority_file"
    )
    with (
        patch(patch_target),
        pytest.raises(InconclusiveGateError, match="target draw ID sequences differ"),
    ):
        load_frozen_arm_d_archive(tampered)


def test_evaluate_arm_d_stream_memoization_and_exact_weighting() -> None:
    # 3 identical portfolios and 1 different portfolio
    p1 = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
        (31, 32, 33, 34, 35, 36),
        (37, 38, 39, 40, 41, 42),
        (43, 44, 45, 46, 47, 48),
        (1, 7, 13, 19, 25, 31),
        (2, 8, 14, 20, 26, 32),
    )
    p2 = (
        (2, 3, 4, 5, 6, 7),
        (8, 9, 10, 11, 12, 13),
        (14, 15, 16, 17, 18, 19),
        (20, 21, 22, 23, 24, 25),
        (26, 27, 28, 29, 30, 31),
        (32, 33, 34, 35, 36, 37),
        (38, 39, 40, 41, 42, 43),
        (44, 45, 46, 47, 48, 49),
        (3, 9, 15, 21, 27, 33),
        (4, 10, 16, 22, 28, 34),
    )

    portfolios = [p1] * 1760 + [p2]
    targets = list(range(1761))
    sealed_prob = Fraction(1095245, 3734808)

    result = evaluate_arm_d_stream(
        k=10,
        portfolios=portfolios,
        target_draws=targets,
        sealed_prob=sealed_prob,
        max_workers=1,
    )

    assert result.row_count == 1761
    assert result.unique_portfolio_count == 2
    assert result.cache_hit_count == 1759
    expected_sum = (
        1760 * result.row_evaluations[0].outcome_count
        + result.row_evaluations[-1].outcome_count
    )
    assert result.exact_sum_arm_d_outcomes == expected_sum
    assert result.exact_mean_arm_d_probability == Fraction(
        result.exact_sum_arm_d_outcomes, 1761 * TOTAL_OUTCOME_SPACE
    )
    assert result.exact_delta == result.exact_mean_arm_d_probability - sealed_prob


def test_generate_markdown_report_formatting() -> None:
    fake_result = {
        "task_id": "TEST_TASK",
        "method_version": "1.0.0",
        "authorities": {
            "branch2_upstream_commit": "abc1",
            "branch2_upstream_tree": "abc2",
            "branch2_upstream_sha256": "abc3",
            "production_authority_commit": "prod1",
            "evaluator_content_sha256": "eval1",
        },
        "model": {
            "model_identity": "BIG_LOTTO_UNIFORM_FAIR_DRAW",
            "outcome_space_exact_count": 601304088,
            "total_main_draws": 13983816,
            "special_count": 43,
            "event_definition": "OFFICIAL_ANY_PRIZE",
            "evaluation_method": "MAIN_DRAW_COLLAPSED_EXACT_SPECIAL_UNION",
        },
        "gates": {
            "primary_result_label": LABEL_SUCCESS,
            "secondary_k20_description": "EXACT_GEOMETRY_ADVANTAGE_AT_K20",
            "exact_tie": False,
            "k10_delta_positive": True,
            "k20_delta_positive": True,
            "all_identity_checks_passed": True,
            "reproduction_oracle_passed": True,
        },
        "k10": {
            "k": 10,
            "row_count": 1761,
            "unique_portfolio_count": 1761,
            "cache_hit_count": 0,
            "exact_production_probability": "1095245/3734808",
            "exact_sum_arm_d_outcomes": 123456789,
            "exact_mean_arm_d_probability": "123/456",
            "exact_delta": "1/1000",
            "decimal_production_probability": 0.2932,
            "decimal_mean_arm_d_probability": 0.2942,
            "decimal_delta": 0.001,
            "row_outcomes_sha256": "deadbeef",
        },
        "k20": {
            "k": 20,
            "row_count": 1761,
            "unique_portfolio_count": 1761,
            "cache_hit_count": 0,
            "exact_production_probability": "44615213/85900584",
            "exact_sum_arm_d_outcomes": 987654321,
            "exact_mean_arm_d_probability": "789/1011",
            "exact_delta": "2/1000",
            "decimal_production_probability": 0.5193,
            "decimal_mean_arm_d_probability": 0.5213,
            "decimal_delta": 0.002,
            "row_outcomes_sha256": "feedface",
        },
    }

    report = generate_markdown_report(fake_result)
    assert LABEL_SUCCESS in report
    assert "CONFIRMATORY_OOS_SUCCESS" in report
    assert "PREDICTIVE_EDGE" in report
    assert "1095245/3734808" in report
    assert "44615213/85900584" in report
