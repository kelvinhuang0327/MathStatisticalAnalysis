"""Focused unit tests for b649_arm_d_vs_sealed_exact_probability_r2 module."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from lottolab.research import b649_arm_d_vs_sealed_exact_probability as r1_module
from lottolab.research import b649_arm_d_vs_sealed_exact_probability_r2 as r2_module
from lottolab.research.b649_arm_d_vs_sealed_exact_probability_r2 import (
    EVALUATOR_CONTENT_SHA256,
    EXPECTED_SEALED_PROBABILITY_K10,
    EXPECTED_SEALED_PROBABILITY_K20,
    HISTORICAL_R1_EVALUATOR_SHA256,
    HISTORICAL_R1_METHOD_VERSION,
    HISTORICAL_R1_TASK_ID,
    LABEL_SUCCESS,
    METHOD_VERSION,
    PRIMARY_K,
    SEALED_INPUT_LOCATOR,
    SEALED_INPUT_SHA256,
    SECONDARY_K,
    TARGET_EVALUATOR_COMMIT,
    TARGET_EVALUATOR_GIT_BLOB,
    TARGET_EVALUATOR_TREE,
    TASK_ID,
    InconclusiveGateError,
    default_evaluator_path,
    generate_markdown_report,
    load_frozen_v1_portfolio,
    verify_evaluator_content_sha256,
    verify_production_sealed_portfolios,
    verify_r2_sources_and_authorities,
)
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    validate_main_draw_masks,
)


@pytest.fixture(scope="module")
def shared_draws() -> DrawMasks:
    return all_main_draw_masks(49, 6)


def test_r2_identity_and_version_distinct_from_r1() -> None:
    """Verify R2 identity, method version, and evaluator pin do not impersonate R1."""
    assert TASK_ID == "B649_ARM_D_VS_SEALED_OUTCOME_FREE_EXACT_PROBABILITY_R2"
    assert METHOD_VERSION == "2.0.0"
    assert TASK_ID != r1_module.TASK_ID
    assert METHOD_VERSION != r1_module.METHOD_VERSION

    assert HISTORICAL_R1_TASK_ID == "B649_ARM_D_VS_SEALED_OUTCOME_FREE_EXACT_PROBABILITY_R1"
    assert HISTORICAL_R1_METHOD_VERSION == "1.0.0"
    assert HISTORICAL_R1_TASK_ID == r1_module.TASK_ID
    assert HISTORICAL_R1_METHOD_VERSION == r1_module.METHOD_VERSION


def test_r2_does_not_mutate_r1_module_or_globals() -> None:
    """Verify importing and using R2 does not mutate R1 globals or constants."""
    assert r1_module.TASK_ID == "B649_ARM_D_VS_SEALED_OUTCOME_FREE_EXACT_PROBABILITY_R1"
    assert r1_module.METHOD_VERSION == "1.0.0"
    assert (
        r1_module.EVALUATOR_CONTENT_SHA256
        == "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
    )
    assert r2_module.TASK_ID != r1_module.TASK_ID
    assert r2_module.EVALUATOR_CONTENT_SHA256 != r1_module.EVALUATOR_CONTENT_SHA256


def test_r2_evaluator_content_sha_matches_b411_pin() -> None:
    """Verify R2 explicitly pins the b411 evaluator file SHA256 and succeeds on live source."""
    assert (
        EVALUATOR_CONTENT_SHA256
        == "ae260a9f77f341483c9f86ed5854d603138e5be070c3aaaa70bb67c3cf8b16e6"
    )
    assert TARGET_EVALUATOR_COMMIT == "b411536c811d18fad530019c775527a818555513"
    assert TARGET_EVALUATOR_TREE == "63ac31d403c77e5fd8fd183f98e6c85ce2481363"
    assert TARGET_EVALUATOR_GIT_BLOB == "c5b5346d1369a7ee8456610df96d2b85c19db016"

    # Evaluator SHA256 must differ from Git blob SHA
    assert EVALUATOR_CONTENT_SHA256 != TARGET_EVALUATOR_GIT_BLOB

    # Live evaluator file inspection
    path = default_evaluator_path()
    assert path.is_file(), f"Target evaluator file absent: {path}"
    raw_bytes = path.read_bytes()
    computed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    assert computed_sha256 == EVALUATOR_CONTENT_SHA256

    # Function verification succeeds
    verified_path = verify_evaluator_content_sha256()
    assert verified_path == path


def test_r2_rejects_modified_or_missing_evaluator(tmp_path: Path) -> None:
    """Verify R2 fails closed with InconclusiveGateError on tampered or absent evaluator."""
    # Absent file
    missing = tmp_path / "nonexistent.py"
    with pytest.raises(InconclusiveGateError, match="absent"):
        verify_evaluator_content_sha256(missing)

    # Tampered content
    tampered = tmp_path / "tampered.py"
    tampered.write_text("# tampered evaluator\n", encoding="utf-8")
    with pytest.raises(InconclusiveGateError, match="mismatch"):
        verify_evaluator_content_sha256(tampered)

    # Empty file
    empty = tmp_path / "empty.py"
    empty.touch()
    with pytest.raises(InconclusiveGateError, match="mismatch"):
        verify_evaluator_content_sha256(empty)


def test_r1_fixed_sha_and_protection_preserved() -> None:
    """Verify R1 source pin is intact and cleanly fails closed against b411 evaluator."""
    # R1 constants are unmodified
    assert (
        r1_module.EVALUATOR_CONTENT_SHA256
        == "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
    )
    assert HISTORICAL_R1_EVALUATOR_SHA256 == r1_module.EVALUATOR_CONTENT_SHA256
    assert r1_module.EVALUATOR_CONTENT_SHA256 != EVALUATOR_CONTENT_SHA256

    # In b411 worktree, R1 fails closed because evaluator was modified
    with pytest.raises(InconclusiveGateError, match="Exact evaluator content SHA256 mismatch"):
        r1_module.verify_evaluator_content_sha256()

    # When supplied with baseline blob bytes, R1 verification passes
    baseline_blob = "3d053b2d9bc2182fc00b22889e837be5d0ba10aa"
    try:
        content = subprocess.check_output(["git", "cat-file", "-p", baseline_blob])
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Git baseline blob unavailable in current environment")

    assert (
        hashlib.sha256(content).hexdigest()
        == "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
    )
    with tempfile.NamedTemporaryFile(suffix=".py", mode="wb", delete=True) as f:
        f.write(content)
        f.flush()
        # R1 succeeds on original baseline content
        r1_module.verify_evaluator_content_sha256(Path(f.name))


def test_r2_exact_reproduction_of_sealed_baselines(shared_draws: DrawMasks) -> None:
    """Verify R2 produces exact Fraction matches for K10 and K20 with 0 mismatch."""
    probs = verify_production_sealed_portfolios(draws=shared_draws)

    # Exact Fraction equality
    assert probs[PRIMARY_K] == EXPECTED_SEALED_PROBABILITY_K10
    assert probs[SECONDARY_K] == EXPECTED_SEALED_PROBABILITY_K20

    assert probs[PRIMARY_K] == Fraction(1095245, 3734808)
    assert probs[SECONDARY_K] == Fraction(44615213, 85900584)

    # Exact outcome counts check:
    p10 = load_frozen_v1_portfolio(PRIMARY_K)
    res10 = evaluate_portfolio(p10, draws=shared_draws)
    assert res10.official_any_prize_outcome_count == 176334445
    assert Fraction(res10.official_any_prize_outcome_count, 601304088) == Fraction(1095245, 3734808)

    p20 = load_frozen_v1_portfolio(SECONDARY_K)
    res20 = evaluate_portfolio(p20, draws=shared_draws)
    assert res20.official_any_prize_outcome_count == 312306491
    assert Fraction(res20.official_any_prize_outcome_count, 601304088) == Fraction(
        44615213, 85900584
    )


def test_patched_evaluator_legal_inputs_produce_consistent_results(
    shared_draws: DrawMasks,
) -> None:
    """Verify patched evaluator evaluates legal portfolios accurately."""
    single_ticket = [(1, 2, 3, 4, 5, 6)]
    res = evaluate_portfolio(single_ticket, draws=shared_draws)
    assert res.official_any_prize == Fraction(7729, 249711)
    assert res.m3_plus == Fraction(4654, 249711)

    toy_draws = all_main_draw_masks(5, 2)
    toy_res = evaluate_portfolio(
        [(1, 2)],
        pool_size=5,
        draw_size=2,
        outright_matches=2,
        draws=toy_draws,
    )
    assert toy_res.official_any_prize == Fraction(9, 30)


def test_patched_evaluator_rejects_illegal_draw_spaces() -> None:
    """Verify patched evaluator rejects incomplete, wrong-sized, or duplicate draw spaces."""
    portfolio = [(1, 2, 3, 4, 5, 6)]

    # Incomplete space (wrong size)
    incomplete = np.array([1, 2, 3], dtype=np.uint64)
    with pytest.raises(ValueError, match="complete main-draw space"):
        evaluate_portfolio(portfolio, draws=incomplete)

    # Wrong bit count (numbers per draw)
    wrong_bits = np.zeros(13983816, dtype=np.uint64)
    with pytest.raises(ValueError, match="exactly draw_size numbers"):
        evaluate_portfolio(portfolio, draws=wrong_bits)

    # Duplicate draws with valid draw_size bits
    duplicate = np.array([3, 3, 5, 6, 9, 10, 17, 18, 20, 24], dtype=np.uint64)
    with pytest.raises(ValueError, match="unique"):
        evaluate_portfolio(
            [(1, 2)],
            pool_size=5,
            draw_size=2,
            outright_matches=2,
            draws=duplicate,
        )

    # Wrong dtype
    wrong_dtype = np.ones(13983816, dtype=np.int32)
    with pytest.raises(ValueError, match="uint64"):
        evaluate_portfolio(portfolio, draws=cast(DrawMasks, wrong_dtype))


def test_r2_sources_and_authorities_pre_flight_check(tmp_path: Path) -> None:
    """Verify pre-flight gate validates authorities before scoring and fails closed."""
    # Normal pre-flight succeeds
    sealed_path = verify_r2_sources_and_authorities()
    assert sealed_path.is_file()

    # Tampered evaluator fails closed
    tampered_eval = tmp_path / "tampered_eval.py"
    tampered_eval.write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(InconclusiveGateError, match="mismatch"):
        verify_r2_sources_and_authorities(evaluator_path=tampered_eval)

    # Tampered sealed input fails closed
    tampered_input = tmp_path / "tampered_input.json"
    tampered_input.write_text('{"bad": 1}\n', encoding="utf-8")
    with pytest.raises(InconclusiveGateError, match="mismatch"):
        verify_r2_sources_and_authorities(input_path=tampered_input)


def test_draw_space_seal_reuse_avoids_repeated_validation(shared_draws: DrawMasks) -> None:
    """Verify that validated draw space is reused via immutable seal without full recheck."""
    validated = validate_main_draw_masks(shared_draws, 49, 6)
    # Re-validating the sealed draw space returns the same object instantly
    second_pass = validate_main_draw_masks(validated, 49, 6)
    assert second_pass is validated


def test_r2_report_formatting() -> None:
    """Verify R2 markdown report reflects R2 task ID and provenance accurately."""
    fake_result = {
        "task_id": TASK_ID,
        "method_version": METHOD_VERSION,
        "authorities": {
            "sealed_input_locator": SEALED_INPUT_LOCATOR,
            "sealed_input_sha256": SEALED_INPUT_SHA256,
            "branch2_upstream_commit": "abc",
            "branch2_upstream_tree": "def",
            "branch2_upstream_sha256": "123",
            "production_authority_commit": "prod123",
            "evaluator_content_sha256": EVALUATOR_CONTENT_SHA256,
            "target_evaluator_commit": TARGET_EVALUATOR_COMMIT,
            "target_evaluator_tree": TARGET_EVALUATOR_TREE,
            "historical_r1_task_id": HISTORICAL_R1_TASK_ID,
            "historical_r1_method_version": HISTORICAL_R1_METHOD_VERSION,
            "historical_r1_evaluator_sha256": HISTORICAL_R1_EVALUATOR_SHA256,
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
    assert TASK_ID in report
    assert METHOD_VERSION in report
    assert TARGET_EVALUATOR_COMMIT[:8] in report
    assert EVALUATOR_CONTENT_SHA256 in report
    assert HISTORICAL_R1_TASK_ID in report
    assert HISTORICAL_R1_EVALUATOR_SHA256 in report
    assert "CANDIDATE_INTEGRATION" in report
    assert "NOT authorized" in report
