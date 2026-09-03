# pyright: reportPrivateUsage=false

"""Focused contract tests for HARD_DIV exact radius-2 reconciliation."""

from __future__ import annotations

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path

from lottolab.research.exact_radius_two_local_escape import (
    PackedWinningSpace,
    evaluate_exact_radius_two_neighborhood,
    radius_two_endpoint_feasibility,
)
from lottolab.research.global_exact_coverage_solver import PAIRWISE_MAX_INTERSECTION
from lottolab.research.hard_div_exact_radius_two import (
    FROZEN_RADIUS1_PORTFOLIO_SHA256,
    FROZEN_RADIUS1_Q,
    GLOBAL_OPTIMUM_STATUS,
    AdapterStatus,
    FiveKClassification,
    HardDivRadiusTwoKResult,
    Radius2Classification,
    canonical_json_bytes,
    classify_five_k,
    compare_hard_div_radius_two,
    evaluate_hard_feasible_radius_two_neighborhood,
    k_result_payload,
    load_frozen_radius1_baseline,
    payload_sha256,
    reconciliation_payload,
)
from lottolab.research.hard_div_pairwise_bounded_candidate_adapter import (
    HardDivPairwiseAdapterDispatch,
    _portfolio_max_pairwise_intersection,
    big_lotto_dispatch,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import Portfolio


def _brute_force_q(pool_size: int, draw_size: int, portfolio: Portfolio) -> Fraction:
    covered = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_set = set(draw)
        if any(len(draw_set.intersection(ticket)) >= 3 for ticket in portfolio):
            covered += 1
    return Fraction(covered, math.comb(pool_size, draw_size))


def test_hard_feasible_neighborhood_counts_match_unfiltered_cardinality() -> None:
    portfolio: Portfolio = ((1, 2, 3, 4), (5, 6, 7, 8))
    space = PackedWinningSpace.build(8, 4)
    feasibility = radius_two_endpoint_feasibility(8, 4, portfolio)
    hard = evaluate_hard_feasible_radius_two_neighborhood(space, portfolio)

    assert PAIRWISE_MAX_INTERSECTION == 1
    assert hard.complete_endpoint_count == feasibility.unique_endpoint_count
    assert hard.exact_evaluated_endpoint_count == hard.hard_feasible_endpoint_count
    assert hard.hard_feasible_endpoint_count <= hard.complete_endpoint_count
    assert hard.input_q == _brute_force_q(8, 4, portfolio)
    assert hard.best_feasible_q == _brute_force_q(8, 4, hard.best_feasible_portfolio)
    assert _portfolio_max_pairwise_intersection(hard.best_feasible_portfolio) <= 1
    assert hard.delta == hard.best_feasible_q - hard.input_q
    if hard.accepted_move:
        assert hard.best_feasible_q > hard.input_q
    else:
        assert hard.best_feasible_portfolio == portfolio
        assert hard.delta == 0


def test_hard_filter_does_not_select_pairwise_violating_unfiltered_best() -> None:
    portfolio: Portfolio = ((1, 2, 3, 4), (1, 5, 6, 7))
    space = PackedWinningSpace.build(8, 4)
    unfiltered = evaluate_exact_radius_two_neighborhood(space, portfolio)
    hard = evaluate_hard_feasible_radius_two_neighborhood(space, portfolio)

    assert _portfolio_max_pairwise_intersection(unfiltered.best_endpoint_portfolio) >= 0
    assert _portfolio_max_pairwise_intersection(hard.best_feasible_portfolio) <= 1
    if _portfolio_max_pairwise_intersection(unfiltered.best_endpoint_portfolio) > 1:
        assert hard.best_feasible_portfolio != unfiltered.best_endpoint_portfolio


def test_frozen_radius1_identities_are_unchanged() -> None:
    for k, expected_q in FROZEN_RADIUS1_Q.items():
        baseline = load_frozen_radius1_baseline(k)
        assert baseline.exact_q == expected_q
        assert baseline.portfolio_sha256 == FROZEN_RADIUS1_PORTFOLIO_SHA256[k]
        assert baseline.global_optimum_status == GLOBAL_OPTIMUM_STATUS
        assert baseline.local_optimum_status == "CERTIFIED_ONE_NUMBER_EXCHANGE"
        assert _portfolio_max_pairwise_intersection(baseline.portfolio) <= 1


def test_unsupported_dispatch_is_not_applicable_not_fabricated() -> None:
    result = compare_hard_div_radius_two(
        HardDivPairwiseAdapterDispatch(
            lottery="DAILY_539",
            pool_size=39,
            draw_size=5,
            minimum_matches=3,
            k=2,
        )
    )
    assert result.status == AdapterStatus.NOT_APPLICABLE
    assert result.radius2_q is None
    assert result.classification is None
    assert result.global_optimum_status == GLOBAL_OPTIMUM_STATUS


def test_execution_failure_is_not_run_not_fabricated(tmp_path: Path) -> None:
    missing = tmp_path / "missing-frozen.json"
    result = compare_hard_div_radius_two(
        big_lotto_dispatch(2),
        frozen_result_path=missing,
    )
    assert result.status == AdapterStatus.NOT_RUN
    assert result.radius2_q is None
    assert result.status_reason is not None
    assert result.status_reason.startswith("EXISTING_NATIVE_EXECUTION_FAILED:")


def test_serialize_reuses_semantic_result_without_second_search() -> None:
    neighborhood = evaluate_hard_feasible_radius_two_neighborhood(
        PackedWinningSpace.build(8, 4),
        ((1, 2, 3, 4), (5, 6, 7, 8)),
    )
    measured = HardDivRadiusTwoKResult(
        status=AdapterStatus.MEASURED,
        status_reason=None,
        k=2,
        radius1_q=neighborhood.input_q,
        radius2_q=neighborhood.best_feasible_q,
        delta=neighborhood.delta,
        classification=(
            Radius2Classification.STRICT_IMPROVEMENT
            if neighborhood.accepted_move
            else Radius2Classification.NO_STRICT_IMPROVEMENT
        ),
        radius1_portfolio=neighborhood.input_portfolio,
        radius1_portfolio_sha256="seed",
        radius2_portfolio=neighborhood.best_feasible_portfolio,
        radius2_portfolio_sha256="term",
        max_pairwise_intersection=_portfolio_max_pairwise_intersection(
            neighborhood.best_feasible_portfolio
        ),
        radius2_terminal_certificate="CERTIFIED_RADIUS2_LOCAL_OPTIMUM",
        global_optimum_status=GLOBAL_OPTIMUM_STATUS,
        neighborhood=neighborhood,
    )
    payload = reconciliation_payload((measured,), five_k_classification=None)
    first = canonical_json_bytes(payload)
    second = canonical_json_bytes(payload)
    assert first == second
    assert payload_sha256(payload) == payload_sha256(json.loads(first))
    assert b"globally optimal" not in first
    assert GLOBAL_OPTIMUM_STATUS.encode() in first
    reconstructed_q = Fraction(
        k_result_payload(measured)["radius2_q"]["numerator"],
        k_result_payload(measured)["radius2_q"]["denominator"],
    )
    assert reconstructed_q == neighborhood.best_feasible_q


def test_five_k_classification_and_delta_arithmetic() -> None:
    def _row(k: int, improved: bool) -> HardDivRadiusTwoKResult:
        radius1 = Fraction(k, 100)
        radius2 = radius1 + (Fraction(1, 100) if improved else Fraction(0, 1))
        return HardDivRadiusTwoKResult(
            status=AdapterStatus.MEASURED,
            status_reason=None,
            k=k,
            radius1_q=radius1,
            radius2_q=radius2,
            delta=radius2 - radius1,
            classification=(
                Radius2Classification.STRICT_IMPROVEMENT
                if improved
                else Radius2Classification.NO_STRICT_IMPROVEMENT
            ),
            radius1_portfolio=None,
            radius1_portfolio_sha256=None,
            radius2_portfolio=None,
            radius2_portfolio_sha256=None,
            max_pairwise_intersection=1,
            radius2_terminal_certificate="CERTIFIED_RADIUS2_LOCAL_OPTIMUM",
            global_optimum_status=GLOBAL_OPTIMUM_STATUS,
            neighborhood=None,
        )

    none_rows = tuple(_row(k, False) for k in (2, 3, 5, 10, 20))
    strong_rows = tuple(_row(k, True) for k in (2, 3, 5, 10, 20))
    mixed_rows = tuple(_row(k, k in {2, 10}) for k in (2, 3, 5, 10, 20))
    assert classify_five_k(none_rows) == FiveKClassification.CROSS_K_NONE
    assert classify_five_k(strong_rows) == FiveKClassification.CROSS_K_STRONG
    assert classify_five_k(mixed_rows) == FiveKClassification.CROSS_K_MIXED
    for row in mixed_rows:
        assert row.delta is not None
        assert row.radius2_q is not None
        assert row.radius1_q is not None
        assert row.delta == row.radius2_q - row.radius1_q


def test_global_optimum_status_is_unknown_on_shipped_constants() -> None:
    assert GLOBAL_OPTIMUM_STATUS == "UNKNOWN"
    source = Path("src/lottolab/research/hard_div_exact_radius_two.py").read_text(
        encoding="utf-8"
    )
    assert "GLOBAL_OPTIMUM_STATUS" in source
    assert "globally optimal" not in source.lower()
    assert "exhaustive global" not in source.lower()
