"""Unit tests for exact one-number-exchange neighborhood refinement.

Verifies:
1. Complete neighborhood count on toy portfolios.
2. Duplicate ticket rejection.
3. Lexicographic tie-breaking among maximal-coverage neighbors.
4. Exact fast coverage parity against combinatorial brute-force evaluation.
5. Known local-improvement fixture (suboptimal starting portfolio).
6. Known no-improvement fixture (local/global optimum starting portfolio).
7. Validation and error handling for malformed inputs.
8. Preregistration, result JSON, and report document integrity and consistency.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path

import pytest

from lottolab.research.exact_coverage_fast_evaluator import fast_exact_portfolio_coverage
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    canonicalize_portfolio,
    canonicalize_ticket,
    enumerate_legal_one_exchange_neighbors,
    evaluate_one_exchange_neighborhood,
    legal_one_exchange_tickets,
)

PREREGISTRATION_PATH = Path(
    "docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-preregistration.md"
)
RESULT_PATH = Path(
    "docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-result.json"
)
REPORT_PATH = Path(
    "docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-report.md"
)

LOCKED_PREREGISTRATION_SHA256 = (
    "68b25e8e2c7ee82d2f6c035003a3d21f67c649b00c465345e5d85423b377eb8d"
)


def brute_force_exact_portfolio_coverage(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: tuple[tuple[int, ...], ...],
) -> Fraction:
    """Exact combinatorial coverage via brute-force winning space scan (test authority)."""
    all_draws = list(itertools.combinations(range(1, pool_size + 1), draw_size))
    total = len(all_draws)
    covered = 0
    for draw in all_draws:
        draw_set = set(draw)
        if any(len(draw_set & set(ticket)) >= minimum_matches for ticket in portfolio):
            covered += 1
    return Fraction(covered, total)


def test_legal_one_exchange_tickets_count_and_uniqueness() -> None:
    pool_size = 6
    ticket = (1, 2, 3)
    mutations = legal_one_exchange_tickets(pool_size, ticket)
    # d * (pool_size - d) = 3 * 3 = 9
    assert len(mutations) == 9
    assert len(set(mutations)) == 9
    for mutated in mutations:
        assert len(mutated) == 3
        assert mutated == tuple(sorted(mutated))
        assert len(set(ticket) & set(mutated)) == 2  # exactly 1 number changed


def test_complete_neighborhood_count_disjoint_portfolio() -> None:
    pool_size = 6
    portfolio = ((1, 2, 3), (4, 5, 6))
    neighbors = enumerate_legal_one_exchange_neighbors(portfolio, pool_size)
    # 2 slots * 3 * 3 = 18 legal mutations, all disjoint and distinct
    assert len(neighbors) == 18
    assert len(set(neighbors)) == 18
    for neighbor in neighbors:
        assert len(neighbor) == 2
        assert len(set(neighbor)) == 2


def test_duplicate_rejection() -> None:
    pool_size = 6
    # Tickets share 2 numbers: (1, 2, 3) and (1, 2, 4)
    # Slot 0 mutating 3 -> 4 yields (1, 2, 4), which is already in portfolio
    # Slot 1 mutating 4 -> 3 yields (1, 2, 3), which is already in portfolio
    portfolio = ((1, 2, 3), (1, 2, 4))
    neighbors = enumerate_legal_one_exchange_neighbors(portfolio, pool_size)
    # 18 total single-ticket mutations minus 2 duplicates = 16 unique valid neighbors
    assert len(neighbors) == 16
    for neighbor in neighbors:
        assert len(neighbor) == 2
        assert neighbor[0] != neighbor[1]  # no duplicates within neighbor portfolio


def test_lexicographic_tie_breaking() -> None:
    pool_size = 6
    draw_size = 3
    minimum_matches = 2
    portfolio = ((1, 2, 3), (4, 5, 6))

    result = evaluate_one_exchange_neighborhood(pool_size, draw_size, minimum_matches, portfolio)
    # All 18 neighbors achieve coverage 17/20.
    # The lexicographically smallest complete portfolio is ((1, 2, 3), (1, 4, 5)).
    best = result["best_neighbor"]
    assert best == ((1, 2, 3), (1, 4, 5))
    assert result["unique_neighbor_count"] == 18

    # Verify that best <= all other neighbors that share the maximum coverage
    all_neighbors = enumerate_legal_one_exchange_neighbors(portfolio, pool_size)
    for n in all_neighbors:
        cov = fast_exact_portfolio_coverage(pool_size, draw_size, minimum_matches, n)
        if cov == result["q_best_neighbor"]:
            assert best <= n


def test_exact_fast_coverage_parity_against_brute_force() -> None:
    pool_size = 7
    draw_size = 3
    minimum_matches = 2
    portfolio = ((1, 2, 3), (4, 5, 6), (1, 4, 7))

    neighbors = enumerate_legal_one_exchange_neighbors(portfolio, pool_size)
    assert len(neighbors) > 0

    for neighbor in neighbors[:10]:  # check sample of neighbors against brute force
        fast_cov = fast_exact_portfolio_coverage(pool_size, draw_size, minimum_matches, neighbor)
        brute_cov = brute_force_exact_portfolio_coverage(
            pool_size, draw_size, minimum_matches, neighbor
        )
        assert fast_cov == brute_cov


def test_known_local_improvement_fixture() -> None:
    # Suboptimal starting portfolio with heavy overlap
    pool_size = 7
    draw_size = 3
    minimum_matches = 2
    portfolio = ((1, 2, 3), (1, 2, 4))

    result = evaluate_one_exchange_neighborhood(pool_size, draw_size, minimum_matches, portfolio)
    assert result["delta_vs_reference"] > 0
    assert result["classification"] == "ONE_EXCHANGE_IMPROVEMENT_FOUND"
    assert result["q_best_neighbor"] > result["q_reference"]


def test_known_no_improvement_fixture() -> None:
    # Starting portfolio with optimal complete coverage
    pool_size = 6
    draw_size = 3
    minimum_matches = 2
    portfolio = ((1, 2, 3), (4, 5, 6))

    result = evaluate_one_exchange_neighborhood(pool_size, draw_size, minimum_matches, portfolio)
    # Reference covers 100% of winning space (Fraction(1, 1))
    assert result["q_reference"] == Fraction(1, 1)
    assert result["delta_vs_reference"] <= 0
    assert result["classification"] == "REFERENCE_E_ONE_EXCHANGE_LOCAL_OPTIMUM"


def test_canonicalize_portfolio_validation() -> None:
    assert canonicalize_ticket([3, 1, 2]) == (1, 2, 3)
    assert canonicalize_portfolio([[4, 5, 6], [3, 2, 1]]) == ((1, 2, 3), (4, 5, 6))

    with pytest.raises(ValueError, match="duplicate numbers"):
        canonicalize_ticket([1, 2, 2])

    with pytest.raises(ValueError, match="duplicate tickets"):
        canonicalize_portfolio([(1, 2, 3), (1, 2, 3)])


def test_phase9_preregistration_and_result_artifacts_integrity() -> None:
    assert PREREGISTRATION_PATH.exists()
    prereg_content = PREREGISTRATION_PATH.read_bytes()
    computed_hash = hashlib.sha256(prereg_content).hexdigest()
    assert computed_hash == LOCKED_PREREGISTRATION_SHA256

    assert RESULT_PATH.exists()
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    assert result["study_id"] == "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_V1"
    assert result["task_id"] == "STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1"
    assert result["gate"]["phase9_advance_gate"] == "PASS"
    assert result["gate"]["global_optimum_status"] == "UNKNOWN"

    for k_str in ("10", "15", "20"):
        k_res = result["per_k"][k_str]
        assert k_res["classification"] == "ONE_EXCHANGE_IMPROVEMENT_FOUND"
        delta_num = k_res["delta_vs_reference_e"]["numerator"]
        assert delta_num > 0


def test_phase9_report_consistency() -> None:
    assert REPORT_PATH.exists()
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "PHASE9_ADVANCE_GATE: PASS" in report
    assert "GLOBAL_OPTIMUM_STATUS:        UNKNOWN" in report
    assert "HISTORICAL_DRAWS:       NOT_USED" in report
    assert "RNG:                    NONE" in report
    assert "MONTE_CARLO:            NONE" in report
    assert "DB_ACCESS:              NO" in report
    assert "RUNTIME_PROMOTION:      NOT_AUTHORIZED" in report
    assert "PUSH:                   NOT_RUN" in report
    assert "PR:                     NOT_CREATED" in report
    assert LOCKED_PREREGISTRATION_SHA256 in report
