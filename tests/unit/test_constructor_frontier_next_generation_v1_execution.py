"""Focused lock/execute checks for the Phase-7 B649 next-gen constructor.

Toy and sealed-artifact checks only. Native `C(49,6)` coverage is the
separate lock-and-execute tool, not this module.
"""

from __future__ import annotations

from fractions import Fraction

from tools.hash_preregistration_constructor_frontier_next_generation_v1 import (
    LOCKED_PARAMETERS,
)
from tools.run_constructor_frontier_next_generation_v1 import (
    evaluate_b649_advance_gate,
    load_locked_parameters,
    load_sealed_q,
    multiplicity_prefix_counts,
    optional_ratio,
    parse_fraction,
    rational,
    ticket_bitmask,
    validate_portfolio,
    verify_sealed_frontier_file,
)

from lottolab.research.exact_coverage_fast_evaluator import fast_exact_portfolio_coverage
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)


def test_lock_hash_roundtrip_matches_written_sidecar() -> None:
    locked = load_locked_parameters()
    assert locked["constructor_id"] == "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
    assert locked["lock_scope"] == "THIS_EXACT_CONSTRUCTOR_VARIANT_ONLY"
    assert locked["arm_c_rerun"] == "forbidden"
    assert locked["t539_execution"] == "not_run"
    assert locked["p638_execution"] == "not_run"
    assert locked["exposure_ladder"] == [1, 3, 5, 10, 15, 20]
    assert locked["material_gap_capture_threshold"] == "1/4"


def test_sealed_q_c_matches_frontier_artifact() -> None:
    verify_sealed_frontier_file(LOCKED_PARAMETERS)
    q_c = load_sealed_q(LOCKED_PARAMETERS, "sealed_q_c")
    assert q_c[1] == Fraction(4654, 249711)
    assert q_c[20] == Fraction(4788733, 13983816)


def test_optional_ratio_and_rational_encoding() -> None:
    assert optional_ratio(Fraction(1, 8), Fraction(1, 2)) == Fraction(1, 4)
    assert optional_ratio(Fraction(1, 8), Fraction(0)) is None
    encoded = rational(Fraction(19, 37191))
    assert encoded["exact"] == "19/37191"
    assert encoded["numerator"] == 19
    assert encoded["denominator"] == 37191
    assert parse_fraction(encoded["exact"]) == Fraction(19, 37191)


def test_advance_gate_passes_only_when_every_clause_holds() -> None:
    ladder = [1, 3, 5, 10, 15, 20]
    q_d = {k: Fraction(k, 1000) for k in ladder}
    q_b = {k: q_d[k] + Fraction(2, 1000) for k in ladder}
    q_c = {k: q_b[k] + Fraction(4, 1000) for k in ladder}
    q_e = {k: q_b[k] + Fraction(1, 1000) for k in ladder}
    q_e[20] = q_b[20] + Fraction(1, 1000)  # 1/4 of the k=20 gap exactly
    duplicates = dict.fromkeys(ladder, 0)
    passed = evaluate_b649_advance_gate(ladder, q_e, q_b, q_d, q_c, duplicates)
    assert passed["passed"] is True
    assert passed["classification"] == "B649_NEXT_GEN_CONSTRUCTOR_ADVANCE"

    failing = dict(q_e)
    failing[20] = q_b[20] + Fraction(1, 1001)
    failed = evaluate_b649_advance_gate(ladder, failing, q_b, q_d, q_c, duplicates)
    assert failed["passed"] is False
    assert failed["classification"] == "DO_NOT_ADVANCE_THIS_EXACT_VARIANT"
    assert failed["cross_lottery_replication_eligible"] is False


def test_advance_gate_fails_if_candidate_loses_to_arm_b() -> None:
    ladder = [1, 3, 5, 10, 15, 20]
    q_d = dict.fromkeys(ladder, Fraction(1, 100))
    q_b = dict.fromkeys(ladder, Fraction(2, 100))
    q_c = dict.fromkeys(ladder, Fraction(4, 100))
    q_e = dict.fromkeys(ladder, Fraction(3, 100))
    q_e[10] = Fraction(2, 100)
    result = evaluate_b649_advance_gate(ladder, q_e, q_b, q_d, q_c, dict.fromkeys(ladder, 0))
    assert result["clauses"]["q_e_gt_q_b_at_k_10_15_20"] is False
    assert result["passed"] is False


def test_one_pass_prefix_counts_match_fast_evaluator_on_toy_pool() -> None:
    pool_size, draw_size, minimum_matches = 8, 3, 2
    portfolio = greedy_minmax_then_sum_overlap_portfolio(pool_size, draw_size, 4)
    counts = multiplicity_prefix_counts(
        pool_size,
        draw_size,
        minimum_matches,
        (1, 2, 4),
        {"e": portfolio},
    )
    total = sum(counts["e"][4])
    assert total == 56
    for k in (1, 2, 4):
        covered = sum(counts["e"][k][1:])
        fast = fast_exact_portfolio_coverage(pool_size, draw_size, minimum_matches, portfolio[:k])
        assert Fraction(covered, total) == fast


def test_candidate_and_arm_b_share_disjoint_prefix_and_then_diverge() -> None:
    candidate = greedy_minmax_then_sum_overlap_portfolio(10, 3, 4)
    arm_b = greedy_min_overlap_portfolio(10, 3, 4)
    assert candidate[:3] == arm_b[:3]
    assert candidate[3] != arm_b[3]
    validate_portfolio(candidate, 10, 3, 4)
    assert ticket_bitmask((1, 2, 3)) == 0b111
