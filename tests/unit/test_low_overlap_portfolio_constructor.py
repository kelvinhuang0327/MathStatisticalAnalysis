"""Regression tests A-H (plus legality/dedup/delegation coverage and the
per-lottery fixed-K checks) for `build_low_overlap_portfolio` --
STRATEGY_MATRIX_PHASE5_GEOMETRY_ONLY_PORTFOLIO_APPLICATION_R1.
"""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import statistics

import pytest

from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    DAILY_539_RULE_CONTRACT,
    POWER_LOTTO_RULE_CONTRACT,
    LotteryRuleContract,
)
from lottolab.research import low_overlap_portfolio_constructor as constructor_module
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.low_overlap_portfolio_constructor import (
    build_low_overlap_portfolio,
    compute_portfolio_geometry_metrics,
)

# LotteryRuleContract.validate() only accepts a source_url on a fixed
# real-publisher allowlist (AUTHORITATIVE_SOURCE_HOSTS) -- it is not meant to
# be freely constructed with fabricated provenance for toy shapes. Deriving
# from a real, already-sealed contract keeps every provenance field genuine
# and only overrides the numeric shape, so this is still a real
# LotteryRuleContract (not a duck-typed stand-in), exercising the same
# type(...) is LotteryRuleContract check production callers go through.
TOY_RULES = dataclasses.replace(DAILY_539_RULE_CONTRACT, main_number_max=10, main_number_count=3)


def _toy_candidate_pool(size: int) -> list[tuple[int, ...]]:
    return list(itertools.islice(itertools.combinations(range(1, 11), 3), size))


# --- A. exactly K tickets returned ------------------------------------------


def test_a_returns_exactly_k_tickets() -> None:
    result = build_low_overlap_portfolio(_toy_candidate_pool(20), 5, TOY_RULES)
    assert len(result) == 5


def test_a_returns_exactly_k_tickets_with_scores() -> None:
    candidates = _toy_candidate_pool(20)
    scores = [float(len(candidates) - i) for i in range(len(candidates))]
    result = build_low_overlap_portfolio(candidates, 7, TOY_RULES, optional_scores=scores)
    assert len(result) == 7


# --- B. every ticket lottery-legal ------------------------------------------


def test_b_every_ticket_is_lottery_legal() -> None:
    result = build_low_overlap_portfolio(_toy_candidate_pool(20), 6, TOY_RULES)
    for ticket in result:
        assert len(ticket) == TOY_RULES.main_number_count
        assert len(set(ticket)) == len(ticket)
        assert all(TOY_RULES.main_number_min <= n <= TOY_RULES.main_number_max for n in ticket)
        assert list(ticket) == sorted(ticket)


# --- C. deterministic with fixed input/seed ---------------------------------


def test_c_deterministic_across_repeated_calls() -> None:
    candidates = _toy_candidate_pool(20)
    first = build_low_overlap_portfolio(candidates, 6, TOY_RULES)
    second = build_low_overlap_portfolio(candidates, 6, TOY_RULES)
    assert first == second


def test_c_deterministic_with_scores_too() -> None:
    candidates = _toy_candidate_pool(20)
    scores = [float(len(candidates) - i) for i in range(len(candidates))]
    first = build_low_overlap_portfolio(candidates, 6, TOY_RULES, optional_scores=scores)
    second = build_low_overlap_portfolio(candidates, 6, TOY_RULES, optional_scores=scores)
    assert first == second


# --- D. no duplicate tickets -------------------------------------------------


def test_d_no_duplicate_tickets_in_output() -> None:
    result = build_low_overlap_portfolio(_toy_candidate_pool(20), 10, TOY_RULES)
    assert len(set(result)) == len(result)


# --- E. geometry-only requires no outcome/future data -----------------------


def test_e_signature_has_no_outcome_or_draw_parameter() -> None:
    parameters = inspect.signature(build_low_overlap_portfolio).parameters
    assert set(parameters) == {"candidates", "k", "lottery_rules", "optional_scores"}


def test_e_module_imports_no_draw_outcome_or_database_dependency() -> None:
    forbidden_substrings = (
        "sqlite3",
        "replay_research_session",
        "prize_evaluation",
        "lottolab.interfaces",
        "lottolab.domain.draws",
    )
    source = inspect.getsource(constructor_module)
    for forbidden in forbidden_substrings:
        assert forbidden not in source


def test_e_geometry_only_works_on_synthetic_candidates_unrelated_to_any_draw() -> None:
    candidates = [(1, 2, 3), (4, 5, 6), (7, 8, 9)]
    result = build_low_overlap_portfolio(candidates, 3, TOY_RULES)
    assert len(result) == 3


# --- F. score-plus-geometry does not mutate upstream scores -----------------


def test_f_optional_scores_sequence_is_not_mutated() -> None:
    candidates = [(1, 2, 3), (1, 2, 4), (1, 2, 5), (4, 5, 6), (7, 8, 9)]
    scores = [10.0, 9.0, 8.0, 7.0, 1.0]
    scores_before = list(scores)
    build_low_overlap_portfolio(candidates, 3, TOY_RULES, optional_scores=scores)
    assert scores == scores_before


def test_f_candidates_sequence_is_not_mutated() -> None:
    candidates = [(1, 2, 3), (1, 2, 4), (1, 2, 5), (4, 5, 6), (7, 8, 9)]
    candidates_before = list(candidates)
    build_low_overlap_portfolio(candidates, 3, TOY_RULES)
    assert candidates == candidates_before


# --- G. low-overlap portfolio has lower/equal overlap than naive top-K ------

_G_CANDIDATES = [(1, 2, 3), (1, 2, 4), (1, 2, 5), (4, 5, 6), (7, 8, 9)]
_G_SCORES = [10.0, 9.0, 8.0, 7.0, 1.0]


def test_g_low_overlap_portfolio_beats_naive_top_k_by_score() -> None:
    naive_top_k = _G_CANDIDATES[:3]  # already given in descending-score order
    naive_metrics = compute_portfolio_geometry_metrics(naive_top_k, TOY_RULES)

    low_overlap = build_low_overlap_portfolio(
        _G_CANDIDATES, 3, TOY_RULES, optional_scores=_G_SCORES
    )
    low_overlap_metrics = compute_portfolio_geometry_metrics(low_overlap, TOY_RULES)

    assert low_overlap_metrics.max_pairwise_overlap <= naive_metrics.max_pairwise_overlap
    assert low_overlap_metrics.mean_pairwise_overlap <= naive_metrics.mean_pairwise_overlap
    # concrete, not just directional: naive top-K collapses onto {1,2}, the
    # geometry constraint finds the fully disjoint optimum instead.
    assert naive_metrics.max_pairwise_overlap == 2
    assert low_overlap_metrics.max_pairwise_overlap == 0


# --- H. exposure remains exactly matched -------------------------------------


def test_h_exposure_is_exactly_k_never_a_silent_shortfall() -> None:
    candidates = [(1, 2, 3), (1, 2, 4), (1, 2, 5)]
    result = build_low_overlap_portfolio(candidates, 3, TOY_RULES)
    assert len(result) == 3  # every unique legal candidate consumed, none dropped


def test_h_k_exceeding_unique_legal_candidates_raises_instead_of_shorting() -> None:
    candidates = [(1, 2, 3), (1, 2, 3), (1, 2, 4)]  # only 2 unique tickets
    with pytest.raises(ValueError, match="exceeds"):
        build_low_overlap_portfolio(candidates, 3, TOY_RULES)


def test_h_total_numbers_bet_matches_k_times_draw_size() -> None:
    k = 7
    result = build_low_overlap_portfolio(_toy_candidate_pool(20), k, TOY_RULES)
    total_numbers_bet = sum(len(ticket) for ticket in result)
    assert total_numbers_bet == k * TOY_RULES.main_number_count


# --- legality rejection -------------------------------------------------------


def test_rejects_candidate_with_wrong_length() -> None:
    with pytest.raises(ValueError, match="does not have"):
        build_low_overlap_portfolio([(1, 2)], 1, TOY_RULES)


def test_rejects_candidate_with_out_of_range_number() -> None:
    with pytest.raises(ValueError, match="outside"):
        build_low_overlap_portfolio([(1, 2, 99)], 1, TOY_RULES)


def test_rejects_candidate_with_duplicate_number_within_ticket() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_low_overlap_portfolio([(1, 1, 2)], 1, TOY_RULES)


def test_rejects_candidate_with_non_integer_number() -> None:
    with pytest.raises(ValueError, match="non-integer"):
        build_low_overlap_portfolio([(1, 2, 3.5)], 1, TOY_RULES)  # type: ignore[list-item]


def test_rejects_negative_k() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_low_overlap_portfolio([(1, 2, 3)], -1, TOY_RULES)


def test_rejects_non_contract_lottery_rules() -> None:
    with pytest.raises(TypeError, match="LotteryRuleContract"):
        build_low_overlap_portfolio([(1, 2, 3)], 1, {"main_number_count": 3})  # type: ignore[arg-type]


def test_rejects_optional_scores_length_mismatch() -> None:
    with pytest.raises(ValueError, match="same length"):
        build_low_overlap_portfolio([(1, 2, 3), (4, 5, 6)], 1, TOY_RULES, optional_scores=[1.0])


def test_zero_k_returns_empty_tuple() -> None:
    assert build_low_overlap_portfolio([(1, 2, 3)], 0, TOY_RULES) == ()


def test_duplicate_candidate_tickets_collapse_to_one() -> None:
    candidates = [(1, 2, 3), (3, 2, 1), (4, 5, 6)]  # first two are the same ticket
    result = build_low_overlap_portfolio(candidates, 2, TOY_RULES)
    assert len(result) == 2
    assert len(set(result)) == 2


# --- candidates=None: real reuse of the sealed shared constructor -----------


def test_module_imports_the_real_shared_function_object() -> None:
    # No local reimplementation, nothing shadowed -- an identity check, not
    # just an equality check.
    assert constructor_module.greedy_min_overlap_portfolio is greedy_min_overlap_portfolio


def test_candidates_none_delegates_to_the_sealed_shared_constructor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int, int]] = []
    sentinel: tuple[tuple[int, ...], ...] = ((1, 2, 3), (4, 5, 6))

    def stub(pool_size: int, draw_size: int, ticket_count: int) -> tuple[tuple[int, ...], ...]:
        calls.append((pool_size, draw_size, ticket_count))
        return sentinel

    monkeypatch.setattr(constructor_module, "greedy_min_overlap_portfolio", stub)

    result = build_low_overlap_portfolio(None, 2, TOY_RULES)

    assert calls == [(TOY_RULES.main_number_max, TOY_RULES.main_number_count, 2)]
    assert result == sentinel


def test_candidates_none_works_end_to_end_at_toy_scale() -> None:
    result = build_low_overlap_portfolio(None, 3, TOY_RULES)
    assert result == ((1, 2, 3), (4, 5, 6), (7, 8, 9))


def test_candidates_none_rejects_optional_scores() -> None:
    with pytest.raises(ValueError, match="requires an explicit candidates"):
        build_low_overlap_portfolio(None, 2, TOY_RULES, optional_scores=[1.0, 2.0])


# --- geometry metrics ----------------------------------------------------------


def test_geometry_metrics_on_a_known_disjoint_toy_portfolio() -> None:
    portfolio = [(1, 2, 3), (4, 5, 6), (7, 8, 9)]
    metrics = compute_portfolio_geometry_metrics(portfolio, TOY_RULES)
    assert metrics.max_pairwise_overlap == 0
    assert metrics.mean_pairwise_overlap == 0.0
    assert metrics.overlap_profile == {0: 3}
    assert metrics.union_size == 9
    assert metrics.duplicate_tickets == 0
    assert metrics.duplicate_pair_exposure == 0
    assert metrics.duplicate_triple_exposure == 0
    assert metrics.coverage_concentration == pytest.approx(statistics.pstdev([1] * 9 + [0]))


def test_geometry_metrics_detect_duplicate_pair_exposure() -> None:
    portfolio = [(1, 2, 3), (1, 2, 4)]  # share the sub-pair (1, 2)
    metrics = compute_portfolio_geometry_metrics(portfolio, TOY_RULES)
    assert metrics.max_pairwise_overlap == 2
    assert metrics.duplicate_pair_exposure == 1
    assert metrics.duplicate_triple_exposure == 0


# --- per-lottery fixed-K checks (isolated, not pooled) -----------------------


def _synthetic_pool(rule_contract: LotteryRuleContract, size: int) -> list[tuple[int, ...]]:
    combos = itertools.combinations(
        range(rule_contract.main_number_min, rule_contract.main_number_max + 1),
        rule_contract.main_number_count,
    )
    return list(itertools.islice(combos, size))


def test_b649_fixed_k_check_geometry_only() -> None:
    candidates = _synthetic_pool(BIG_LOTTO_RULE_CONTRACT, 60)
    result = build_low_overlap_portfolio(candidates, 5, BIG_LOTTO_RULE_CONTRACT)
    assert len(result) == 5
    assert len(set(result)) == 5
    for ticket in result:
        assert len(ticket) == 6
        assert all(1 <= n <= 49 for n in ticket)


def test_b649_fixed_k_check_score_plus_geometry() -> None:
    candidates = _synthetic_pool(BIG_LOTTO_RULE_CONTRACT, 60)
    scores = [float(len(candidates) - i) for i in range(len(candidates))]
    result = build_low_overlap_portfolio(
        candidates, 5, BIG_LOTTO_RULE_CONTRACT, optional_scores=scores
    )
    assert len(result) == 5
    assert len(set(result)) == 5


def test_t539_fixed_k_check_geometry_only() -> None:
    candidates = _synthetic_pool(DAILY_539_RULE_CONTRACT, 60)
    result = build_low_overlap_portfolio(candidates, 5, DAILY_539_RULE_CONTRACT)
    assert len(result) == 5
    assert len(set(result)) == 5
    for ticket in result:
        assert len(ticket) == 5
        assert all(1 <= n <= 39 for n in ticket)


def test_t539_fixed_k_check_score_plus_geometry() -> None:
    candidates = _synthetic_pool(DAILY_539_RULE_CONTRACT, 60)
    scores = [float(len(candidates) - i) for i in range(len(candidates))]
    result = build_low_overlap_portfolio(
        candidates, 5, DAILY_539_RULE_CONTRACT, optional_scores=scores
    )
    assert len(result) == 5
    assert len(set(result)) == 5


def test_p638_zone1_fixed_k_check_geometry_only() -> None:
    candidates = _synthetic_pool(POWER_LOTTO_RULE_CONTRACT, 60)
    result = build_low_overlap_portfolio(candidates, 5, POWER_LOTTO_RULE_CONTRACT)
    assert len(result) == 5
    assert len(set(result)) == 5
    for ticket in result:
        assert len(ticket) == 6
        assert all(1 <= n <= 38 for n in ticket)


def test_p638_zone1_fixed_k_check_score_plus_geometry() -> None:
    candidates = _synthetic_pool(POWER_LOTTO_RULE_CONTRACT, 60)
    scores = [float(len(candidates) - i) for i in range(len(candidates))]
    result = build_low_overlap_portfolio(
        candidates, 5, POWER_LOTTO_RULE_CONTRACT, optional_scores=scores
    )
    assert len(result) == 5
    assert len(set(result)) == 5


# --- k is caller-controlled, not fixed to a historically-best value ---------


@pytest.mark.parametrize("k", [1, 3, 5, 10, 15, 20])
def test_k_is_a_free_caller_controlled_exposure_parameter(k: int) -> None:
    candidates = _synthetic_pool(POWER_LOTTO_RULE_CONTRACT, 200)
    result = build_low_overlap_portfolio(candidates, k, POWER_LOTTO_RULE_CONTRACT)
    assert len(result) == k
