"""Focused lock/execute checks for the Phase-7 T539 constructor replication.

Toy, mapping, lock, and sealed-artifact checks only. Native `C(39,5)`
coverage is the separate lock-and-execute tool, not this module.
"""

from __future__ import annotations

import inspect
from fractions import Fraction
from pathlib import Path

from tools.hash_preregistration_constructor_frontier_next_generation_t539_v1 import (
    LOCKED_PARAMETERS,
)
from tools.run_constructor_frontier_next_generation_t539_v1 import (
    NATIVE_MAPPING_STOP,
    assert_t539_native_mapping,
    constructor_source_has_b649_hardcodes,
    evaluate_t539_replication_gate,
    load_locked_parameters,
    load_sealed_q,
    multiplicity_prefix_counts,
    parse_fraction,
    rational,
    ticket_bitmask,
    validate_portfolio,
    verify_b649_authority,
    verify_sealed_t539_comparators,
)

from lottolab.domain.lottery_rules import DAILY_539_RULE_CONTRACT
from lottolab.research.exact_coverage_baseline import exact_random_portfolio_coverage
from lottolab.research.exact_coverage_fast_evaluator import fast_exact_portfolio_coverage
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)
from lottolab.research.greedy_minmax_then_sum_overlap_constructor_t539 import (
    DRAW_SIZE,
    POOL_SIZE,
    greedy_minmax_then_sum_overlap_portfolio_t539,
)

CONSTRUCTOR_SOURCE = Path(
    "src/lottolab/research/greedy_minmax_then_sum_overlap_constructor.py"
).read_text(encoding="utf-8")


def test_lock_hash_roundtrip_matches_written_sidecar() -> None:
    locked = load_locked_parameters()
    assert locked["constructor_id"] == "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
    assert locked["lock_scope"] == "THIS_EXACT_T539_REPLICATION_ONLY"
    assert locked["lottery_type"] == "DAILY_539"
    assert locked["pool_size"] == 39
    assert locked["draw_size"] == 5
    assert locked["primary_event"] == "M3+"
    assert locked["exposure_ladder"] == [1, 3, 5, 10, 15, 20]
    assert locked["b649_rerun"] == "forbidden"
    assert locked["arm_c_rerun"] == "forbidden"
    assert locked["p638_execution"] == "not_run"
    assert locked["weights"] == "none"
    assert locked["randomness"] == "none"
    assert locked["t539_replication_gate"] == [
        "q_e_gt_q_d_for_every_k_gt_1",
        "q_e_ge_q_b_for_every_k_gt_1",
        "q_e_gt_q_b_at_k_10_15_20",
        "duplicate_count_eq_0",
        "geometry_lex_max_sum_not_increased_where_coverage_superiority_claimed",
    ]
    assert locked == LOCKED_PARAMETERS


def test_native_mapping_uses_daily_539_rules_and_generic_constructor() -> None:
    assert_t539_native_mapping(LOCKED_PARAMETERS)
    assert DAILY_539_RULE_CONTRACT.main_number_max == 39
    assert DAILY_539_RULE_CONTRACT.main_number_count == 5
    assert POOL_SIZE == 39
    assert DRAW_SIZE == 5
    signature = inspect.signature(greedy_minmax_then_sum_overlap_portfolio)
    assert list(signature.parameters) == ["pool_size", "draw_size", "ticket_count"]
    assert constructor_source_has_b649_hardcodes(CONSTRUCTOR_SOURCE) is False
    function_body = CONSTRUCTOR_SOURCE.split("def greedy_minmax_then_sum_overlap_portfolio", 1)[1]
    assert "49" not in function_body
    first = greedy_minmax_then_sum_overlap_portfolio_t539(1)
    assert first == ((1, 2, 3, 4, 5),)
    assert first == greedy_minmax_then_sum_overlap_portfolio(39, 5, 1)


def test_native_mapping_stop_token_is_stable() -> None:
    assert NATIVE_MAPPING_STOP == "STOP_PHASE7_T539_NATIVE_MAPPING_DRIFT"


def test_constructor_determinism_and_lex_key_on_toy_and_native_prefix() -> None:
    first = greedy_minmax_then_sum_overlap_portfolio(10, 3, 6)
    second = greedy_minmax_then_sum_overlap_portfolio(10, 3, 6)
    assert first == second
    native_a = greedy_minmax_then_sum_overlap_portfolio(39, 5, 3)
    native_b = greedy_minmax_then_sum_overlap_portfolio_t539(3)
    assert native_a == native_b
    assert native_a == greedy_minmax_then_sum_overlap_portfolio(39, 5, 3)
    assert native_a == (
        (1, 2, 3, 4, 5),
        (6, 7, 8, 9, 10),
        (11, 12, 13, 14, 15),
    )
    arm_b = greedy_min_overlap_portfolio(39, 5, 3)
    assert native_a == arm_b


def test_sealed_t539_comparators_match_lock_and_exact_random() -> None:
    verify_sealed_t539_comparators(LOCKED_PARAMETERS)
    verify_b649_authority(LOCKED_PARAMETERS)
    sealed_a = load_sealed_q(LOCKED_PARAMETERS, "sealed_q_a")
    sealed_b = load_sealed_q(LOCKED_PARAMETERS, "sealed_q_b")
    sealed_d = load_sealed_q(LOCKED_PARAMETERS, "sealed_q_d")
    assert sealed_a[1] == sealed_b[1] == sealed_d[1] == Fraction(1927, 191919)
    for k, expected in sealed_d.items():
        assert exact_random_portfolio_coverage(39, 5, 3, k) == expected


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


def test_k1_identity_on_toy_pool() -> None:
    pool_size, draw_size, minimum_matches = 8, 3, 2
    candidate = greedy_minmax_then_sum_overlap_portfolio(pool_size, draw_size, 1)
    arm_b = greedy_min_overlap_portfolio(pool_size, draw_size, 1)
    counts = multiplicity_prefix_counts(
        pool_size,
        draw_size,
        minimum_matches,
        (1,),
        {"a": candidate, "b": arm_b, "e": candidate},
    )
    total = 56
    q_e = Fraction(sum(counts["e"][1][1:]), total)
    q_b = Fraction(sum(counts["b"][1][1:]), total)
    q_a = Fraction(sum(counts["a"][1][1:]), total)
    q_d = exact_random_portfolio_coverage(pool_size, draw_size, minimum_matches, 1)
    assert q_e == q_b == q_a == q_d


def _synthetic_pass_payload() -> tuple[
    list[int],
    dict[int, Fraction],
    dict[int, Fraction],
    dict[int, Fraction],
    dict[int, int],
    dict[int, tuple[int, int]],
    dict[int, tuple[int, int]],
]:
    ladder = [1, 3, 5, 10, 15, 20]
    q_d = {k: Fraction(k, 1000) for k in ladder}
    q_b = {k: q_d[k] + Fraction(2, 1000) for k in ladder}
    q_e = {k: q_b[k] for k in ladder}
    for k in (10, 15, 20):
        q_e[k] = q_b[k] + Fraction(1, 1000)
    duplicates = dict.fromkeys(ladder, 0)
    lex_e: dict[int, tuple[int, int]] = {k: (1, 4) for k in ladder}
    lex_b: dict[int, tuple[int, int]] = {k: (1, 5) for k in ladder}
    return ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b


def test_replication_gate_passes_only_when_every_clause_holds() -> None:
    ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b = _synthetic_pass_payload()
    passed = evaluate_t539_replication_gate(ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b)
    assert passed["passed"] is True
    assert passed["classification"] == "T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED"
    assert passed["p638_replication_eligible"] is True


def test_replication_gate_fails_if_candidate_loses_to_random() -> None:
    ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b = _synthetic_pass_payload()
    q_e[5] = q_d[5]
    failed = evaluate_t539_replication_gate(ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b)
    assert failed["clauses"]["q_e_gt_q_d_for_every_k_gt_1"] is False
    assert failed["passed"] is False
    assert failed["classification"] == "DO_NOT_ADVANCE_THIS_EXACT_T539_REPLICATION"
    assert failed["p638_replication_eligible"] is False


def test_replication_gate_fails_if_candidate_loses_to_arm_b() -> None:
    ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b = _synthetic_pass_payload()
    q_e[3] = q_b[3] - Fraction(1, 1000)
    failed = evaluate_t539_replication_gate(ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b)
    assert failed["clauses"]["q_e_ge_q_b_for_every_k_gt_1"] is False
    assert failed["passed"] is False


def test_replication_gate_fails_if_not_strictly_better_at_large_k() -> None:
    ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b = _synthetic_pass_payload()
    q_e[10] = q_b[10]
    failed = evaluate_t539_replication_gate(ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b)
    assert failed["clauses"]["q_e_gt_q_b_at_k_10_15_20"] is False
    assert failed["passed"] is False


def test_replication_gate_fails_on_duplicates() -> None:
    ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b = _synthetic_pass_payload()
    duplicates[20] = 1
    failed = evaluate_t539_replication_gate(ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b)
    assert failed["clauses"]["duplicate_count_eq_0"] is False
    assert failed["passed"] is False


def test_replication_gate_fails_when_lex_objective_increases_where_superiority_claimed() -> None:
    ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b = _synthetic_pass_payload()
    lex_e[15] = (1, 6)
    lex_b[15] = (1, 5)
    failed = evaluate_t539_replication_gate(ladder, q_e, q_b, q_d, duplicates, lex_e, lex_b)
    clause = "geometry_lex_max_sum_not_increased_where_coverage_superiority_claimed"
    assert failed["clauses"][clause] is False
    assert failed["passed"] is False
    assert failed["classification"] == "DO_NOT_ADVANCE_THIS_EXACT_T539_REPLICATION"


def test_rational_encoding_and_bitmask() -> None:
    encoded = rational(Fraction(1927, 191919))
    assert encoded["exact"] == "1927/191919"
    assert parse_fraction(encoded["exact"]) == Fraction(1927, 191919)
    validate_portfolio(((1, 2, 3, 4, 5),), 39, 5, 1)
    assert ticket_bitmask((1, 2, 3)) == 0b111
