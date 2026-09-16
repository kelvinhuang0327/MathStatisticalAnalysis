# pyright: reportPrivateUsage=false

"""Focused contract tests for the bounded hard-diversification B649 adapter."""

from __future__ import annotations

import hashlib
import inspect
import itertools
import json
import math
from dataclasses import fields
from fractions import Fraction

import pytest

from lottolab.research import hard_div_pairwise_bounded_candidate_adapter as adapter
from lottolab.research.cyclic_sidon_shift import (
    sidon_shift_portfolio as canonical_sidon_shift_portfolio,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    canonicalize_portfolio,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    ExactOneExchangeNeighbor,
    _ExchangeCandidate,
    enumerate_unique_legal_one_exchange_neighbors,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    _exact_neighbor_coverages as canonical_exact_neighbor_coverages,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    _exchange_candidates as canonical_exchange_candidates,
)


def _brute_force_exact_coverage(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: Portfolio,
) -> Fraction:
    covered = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_set = set(draw)
        if any(len(draw_set.intersection(ticket)) >= minimum_matches for ticket in portfolio):
            covered += 1
    return Fraction(covered, math.comb(pool_size, draw_size))


def _terminal_ascent(portfolio: Portfolio) -> adapter._HardDivAscentResult:
    exact_q = Fraction(len(portfolio), adapter.WINNING_DRAW_COUNT)
    terminal_iteration = adapter.HardDivPairwiseIteration(
        iteration_index=0,
        input_portfolio=portfolio,
        input_q=exact_q,
        complete_neighbor_count=1,
        hard_feasible_neighbor_count=1,
        exact_evaluated_neighbor_count=1,
        best_neighbor_portfolio=portfolio,
        best_neighbor_q=exact_q,
        delta=Fraction(0, 1),
        accepted_move=False,
    )
    return adapter._HardDivAscentResult(
        seed_portfolio=portfolio,
        seed_q=exact_q,
        iterations=(terminal_iteration,),
        move_count=0,
        terminal_portfolio=portfolio,
        terminal_q=exact_q,
    )


def _exact_neighbors(
    candidates: tuple[_ExchangeCandidate, ...],
    scores: dict[Portfolio, Fraction],
) -> tuple[ExactOneExchangeNeighbor, ...]:
    return tuple(
        ExactOneExchangeNeighbor(
            portfolio=candidate.portfolio,
            slot_index=candidate.slot_index,
            removed_number=candidate.removed_number,
            added_number=candidate.added_number,
            exact_q=scores[candidate.portfolio],
        )
        for candidate in candidates
    )


def test_frozen_identity_supported_k_and_public_api_surface() -> None:
    assert adapter.METHOD_ID == "HARD_DIV_PAIRWISE_OVERLAP_R1"
    assert adapter.REFERENCE_STRATEGY_ID == "CYCLIC_SIDON_SHIFT_V1"
    assert adapter.SUPPORTED_K == (2, 3, 5, 10, 20)
    assert adapter.PAIRWISE_MAX_INTERSECTION == 1
    assert adapter.EXACT_ONE_EXCHANGE_REUSE == "BOUNDED_ADAPTER"
    assert adapter.GLOBAL_EXACT_REUSE_ROLE == "ORACLE_ONLY"
    assert adapter.FULL_DOMAIN_B649_GLOBAL_OPTIMALITY == "UNPROVEN"
    assert tuple(
        inspect.signature(adapter.run_hard_div_pairwise_bounded_candidate_adapter).parameters
    ) == ("dispatch",)
    assert [field.name for field in fields(adapter.HardDivPairwiseAdapterDispatch)] == [
        "lottery",
        "pool_size",
        "draw_size",
        "minimum_matches",
        "k",
    ]
    assert not {
        "history",
        "database",
        "db",
        "future_outcomes",
        "pairwise_max_intersection",
        "seed_family",
    }.intersection(
        inspect.signature(adapter.run_hard_div_pairwise_bounded_candidate_adapter).parameters
    )


@pytest.mark.parametrize(
    "dispatch",
    [
        adapter.HardDivPairwiseAdapterDispatch("POWER_LOTTO", 49, 6, 3, 2),
        adapter.HardDivPairwiseAdapterDispatch("BIG_LOTTO", 48, 6, 3, 2),
        adapter.HardDivPairwiseAdapterDispatch("BIG_LOTTO", 49, 5, 3, 2),
        adapter.HardDivPairwiseAdapterDispatch("BIG_LOTTO", 49, 6, 2, 2),
        adapter.HardDivPairwiseAdapterDispatch("BIG_LOTTO", 49, 6, 3, 4),
        adapter.HardDivPairwiseAdapterDispatch("BIG_LOTTO", 49, 6, 3, True),
    ],
)
def test_unsupported_dispatch_rejects_before_seed_or_expensive_evaluation(
    monkeypatch: pytest.MonkeyPatch,
    dispatch: adapter.HardDivPairwiseAdapterDispatch,
) -> None:
    def unexpected_call(*_args: object, **_kwargs: object) -> None:
        pytest.fail("unsupported dispatch reached seed or exact evaluation")

    monkeypatch.setattr(adapter, "sidon_shift_portfolio", unexpected_call)
    monkeypatch.setattr(adapter, "_iterative_hard_feasible_ascent", unexpected_call)

    result = adapter.run_hard_div_pairwise_bounded_candidate_adapter(dispatch)

    assert result.status is adapter.AdapterStatus.NOT_APPLICABLE
    assert result.status_reason == adapter.UNSUPPORTED_REASON
    assert result.seed_portfolio is None
    assert result.portfolio is None
    assert result.search_evidence is None


def test_all_supported_sidon_seeds_are_canonical_distinct_and_hard_feasible() -> None:
    for k in adapter.SUPPORTED_K:
        seed = canonicalize_portfolio(canonical_sidon_shift_portfolio(k))
        assert len(seed) == k
        assert len(set(seed)) == k
        assert adapter._terminal_hard_postcheck(seed, expected_k=k)
        assert adapter._portfolio_max_pairwise_intersection(seed) <= 1


def test_complete_neighborhood_and_exact_objective_match_existing_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio: Portfolio = ((1, 2, 3, 4), (1, 5, 6, 7))
    observed_candidates: list[tuple[_ExchangeCandidate, ...]] = []
    observed_neighbors: list[tuple[ExactOneExchangeNeighbor, ...]] = []

    def observing_exact_evaluator(
        pool_size: int,
        draw_size: int,
        minimum_matches: int,
        current: Portfolio,
        candidates: tuple[_ExchangeCandidate, ...],
    ) -> tuple[int, tuple[ExactOneExchangeNeighbor, ...]]:
        observed_candidates.append(candidates)
        covered_count, neighbors = canonical_exact_neighbor_coverages(
            pool_size,
            draw_size,
            minimum_matches,
            current,
            candidates,
        )
        observed_neighbors.append(neighbors)
        return covered_count, neighbors

    monkeypatch.setattr(adapter, "_exact_neighbor_coverages", observing_exact_evaluator)
    result = adapter._evaluate_hard_feasible_neighborhood(8, 4, 3, portfolio)

    complete_candidates = canonical_exchange_candidates(portfolio, 8)
    complete_neighbors = enumerate_unique_legal_one_exchange_neighbors(portfolio, 8)
    expected_feasible = tuple(
        candidate
        for candidate in complete_candidates
        if adapter._canonical_hard_feasible_candidate(
            candidate.portfolio,
            expected_k=2,
            pool_size=8,
            draw_size=4,
        )
        is not None
    )
    assert result.complete_neighbor_count == len(complete_candidates) == len(complete_neighbors)
    assert observed_candidates == [expected_feasible]
    assert result.hard_feasible_neighbor_count == len(expected_feasible)
    assert result.exact_evaluated_neighbor_count == len(expected_feasible)
    assert all(
        adapter._portfolio_max_pairwise_intersection(candidate.portfolio) <= 1
        for candidate in observed_candidates[0]
    )
    assert result.input_q == _brute_force_exact_coverage(8, 4, 3, portfolio)
    for neighbor in observed_neighbors[0]:
        assert neighbor.exact_q == _brute_force_exact_coverage(8, 4, 3, neighbor.portfolio)


def test_infeasible_high_q_candidate_is_filtered_before_exact_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current: Portfolio = ((1, 2, 3, 4), (1, 5, 6, 7))
    infeasible: Portfolio = ((1, 3, 4, 5), (1, 5, 6, 7))
    feasible: Portfolio = ((1, 3, 4, 8), (1, 5, 6, 7))
    candidates = tuple(
        sorted(
            (
                _ExchangeCandidate(infeasible, 0, 2, 5),
                _ExchangeCandidate(feasible, 0, 2, 8),
            ),
            key=lambda candidate: candidate.portfolio,
        )
    )
    scores: dict[Portfolio, Fraction] = {
        infeasible: Fraction(1, 1),
        feasible: Fraction(2, 70),
    }
    evaluated: list[tuple[_ExchangeCandidate, ...]] = []

    def fake_candidates(_portfolio: Portfolio, _pool_size: int) -> tuple[_ExchangeCandidate, ...]:
        return candidates

    def fake_exact_evaluator(
        _pool_size: int,
        _draw_size: int,
        _minimum_matches: int,
        _portfolio: Portfolio,
        eligible: tuple[_ExchangeCandidate, ...],
    ) -> tuple[int, tuple[ExactOneExchangeNeighbor, ...]]:
        evaluated.append(eligible)
        return 1, _exact_neighbors(eligible, scores)

    monkeypatch.setattr(adapter, "_exchange_candidates", fake_candidates)
    monkeypatch.setattr(adapter, "_exact_neighbor_coverages", fake_exact_evaluator)
    result = adapter._evaluate_hard_feasible_neighborhood(8, 4, 3, current)

    assert scores[infeasible] > scores[feasible]
    assert adapter._portfolio_max_pairwise_intersection(infeasible) == 2
    assert evaluated == [
        (next(candidate for candidate in candidates if candidate.portfolio == feasible),)
    ]
    assert result.complete_neighbor_count == 2
    assert result.hard_feasible_neighbor_count == 1
    assert result.exact_evaluated_neighbor_count == 1
    assert result.best_neighbor_portfolio == feasible
    assert result.best_neighbor_q == scores[feasible]


def test_equal_q_best_candidate_uses_complete_portfolio_lexicographic_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current: Portfolio = ((1, 2, 3, 4), (1, 5, 6, 7))
    first: Portfolio = ((1, 2, 3, 8), (1, 5, 6, 7))
    second: Portfolio = ((1, 2, 4, 8), (1, 5, 6, 7))
    candidates = tuple(
        sorted(
            (
                _ExchangeCandidate(first, 0, 4, 8),
                _ExchangeCandidate(second, 0, 3, 8),
            ),
            key=lambda candidate: candidate.portfolio,
        )
    )
    scores: dict[Portfolio, Fraction] = {
        first: Fraction(2, 70),
        second: Fraction(2, 70),
    }

    def fake_candidates(_portfolio: Portfolio, _pool_size: int) -> tuple[_ExchangeCandidate, ...]:
        return candidates

    def fake_exact_evaluator(
        _pool_size: int,
        _draw_size: int,
        _minimum_matches: int,
        _portfolio: Portfolio,
        _candidates: tuple[_ExchangeCandidate, ...],
    ) -> tuple[int, tuple[ExactOneExchangeNeighbor, ...]]:
        return 1, _exact_neighbors(tuple(reversed(candidates)), scores)

    monkeypatch.setattr(adapter, "_exchange_candidates", fake_candidates)
    monkeypatch.setattr(adapter, "_exact_neighbor_coverages", fake_exact_evaluator)

    result = adapter._evaluate_hard_feasible_neighborhood(8, 4, 3, current)

    assert result.best_neighbor_q == Fraction(2, 70)
    assert result.best_neighbor_portfolio == min(first, second)


def test_equal_q_neighbor_is_not_accepted_as_a_move(monkeypatch: pytest.MonkeyPatch) -> None:
    seed: Portfolio = ((1, 2, 3, 4), (1, 5, 6, 7))
    equal_neighbor: Portfolio = ((1, 2, 3, 8), (1, 5, 6, 7))
    exact_q = Fraction(1, 2)

    def equal_neighborhood(*_args: object) -> adapter._HardFeasibleNeighborhoodResult:
        return adapter._HardFeasibleNeighborhoodResult(
            input_portfolio=seed,
            input_q=exact_q,
            complete_neighbor_count=2,
            hard_feasible_neighbor_count=2,
            exact_evaluated_neighbor_count=2,
            best_neighbor_portfolio=equal_neighbor,
            best_neighbor_q=exact_q,
            delta=Fraction(0, 1),
        )

    monkeypatch.setattr(adapter, "_evaluate_hard_feasible_neighborhood", equal_neighborhood)
    result = adapter._iterative_hard_feasible_ascent(8, 4, 3, seed)

    assert result.move_count == 0
    assert result.terminal_portfolio == seed
    assert len(result.iterations) == 1
    assert not result.iterations[0].accepted_move


def test_strict_improvements_continue_until_terminal_no_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed: Portfolio = ((1, 2, 3, 4), (1, 5, 6, 7))
    first: Portfolio = ((1, 2, 3, 8), (1, 5, 6, 7))
    second: Portfolio = ((1, 2, 4, 8), (1, 5, 6, 7))
    q0, q1, q2 = Fraction(1, 4), Fraction(1, 3), Fraction(2, 5)
    states: dict[Portfolio, tuple[Fraction, Portfolio, Fraction]] = {
        seed: (q0, first, q1),
        first: (q1, second, q2),
        second: (q2, first, q2),
    }

    def scripted_neighborhood(
        _pool_size: int,
        _draw_size: int,
        _minimum_matches: int,
        portfolio: Portfolio,
    ) -> adapter._HardFeasibleNeighborhoodResult:
        input_q, best_portfolio, best_q = states[portfolio]
        return adapter._HardFeasibleNeighborhoodResult(
            input_portfolio=portfolio,
            input_q=input_q,
            complete_neighbor_count=3,
            hard_feasible_neighbor_count=2,
            exact_evaluated_neighbor_count=2,
            best_neighbor_portfolio=best_portfolio,
            best_neighbor_q=best_q,
            delta=best_q - input_q,
        )

    monkeypatch.setattr(adapter, "_evaluate_hard_feasible_neighborhood", scripted_neighborhood)
    result = adapter._iterative_hard_feasible_ascent(8, 4, 3, seed)

    assert result.move_count == 2
    assert result.terminal_portfolio == second
    assert result.terminal_q == q2
    assert [iteration.input_portfolio for iteration in result.iterations] == [seed, first, second]
    assert [iteration.accepted_move for iteration in result.iterations] == [True, True, False]
    assert all(
        iteration.delta is not None and iteration.delta > 0 for iteration in result.iterations[:-1]
    )
    assert result.iterations[-1].delta == 0


def test_measured_calls_reuse_independent_sidon_seeds_and_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_calls: list[int] = []
    ascent_inputs: list[Portfolio] = []

    def observed_sidon(k: int) -> Portfolio:
        seed_calls.append(k)
        return canonical_sidon_shift_portfolio(k)

    def fake_ascent(
        _pool_size: int,
        _draw_size: int,
        _minimum_matches: int,
        seed: Portfolio,
    ) -> adapter._HardDivAscentResult:
        ascent_inputs.append(seed)
        return _terminal_ascent(seed)

    monkeypatch.setattr(adapter, "sidon_shift_portfolio", observed_sidon)
    monkeypatch.setattr(adapter, "_iterative_hard_feasible_ascent", fake_ascent)

    results = {
        k: adapter.run_hard_div_pairwise_bounded_candidate_adapter(adapter.big_lotto_dispatch(k))
        for k in adapter.SUPPORTED_K
    }
    repeated = adapter.run_hard_div_pairwise_bounded_candidate_adapter(
        adapter.big_lotto_dispatch(10)
    )

    assert seed_calls == [2, 3, 5, 10, 20, 10]
    for index, k in enumerate(adapter.SUPPORTED_K):
        expected_seed = canonicalize_portfolio(canonical_sidon_shift_portfolio(k))
        result = results[k]
        expected_hash = hashlib.sha256(
            json.dumps(expected_seed, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert ascent_inputs[index] == expected_seed
        assert result.status is adapter.AdapterStatus.MEASURED
        assert result.status_reason is None
        assert result.seed_portfolio == expected_seed
        assert result.portfolio == expected_seed
        assert result.seed_portfolio_sha256 == expected_hash
        assert result.portfolio_sha256 == expected_hash
        assert result.seed_exact_q == Fraction(k, adapter.WINNING_DRAW_COUNT)
        assert result.exact_q == result.seed_exact_q
        assert result.covered_draw_count == k
        assert result.delta_vs_reference == 0
        assert result.geometry_max_pairwise_overlap is not None
        assert result.geometry_max_pairwise_overlap <= 1
        assert result.local_optimum_status == adapter.LOCAL_OPTIMUM_STATUS
        assert result.proof_status == adapter.PROOF_STATUS
        assert result.global_optimum_status == "UNKNOWN"
        assert result.search_evidence is not None
        assert result.search_evidence.terminal_no_strict_improvement
        assert result.search_evidence.complete_neighborhood_certified
        assert result.search_evidence.hard_feasible_filter_before_exact_evaluation
    assert repeated == results[10]
    assert ascent_inputs[-1] == canonicalize_portfolio(canonical_sidon_shift_portfolio(10))


@pytest.mark.parametrize(
    "bad_seed",
    [
        (
            (1, 2, 3, 4, 5, 6),
            (1, 2, 3, 4, 5, 6),
        ),
        (
            (1, 2, 3, 4, 5, 6),
            (1, 2, 7, 8, 9, 10),
        ),
    ],
)
def test_malformed_or_infeasible_seed_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    bad_seed: Portfolio,
) -> None:
    def bad_sidon(_k: int) -> Portfolio:
        return bad_seed

    def unexpected_ascent(
        _pool_size: int,
        _draw_size: int,
        _minimum_matches: int,
        _seed: Portfolio,
    ) -> adapter._HardDivAscentResult:
        pytest.fail("invalid seed reached exact ascent")

    monkeypatch.setattr(adapter, "sidon_shift_portfolio", bad_sidon)
    monkeypatch.setattr(adapter, "_iterative_hard_feasible_ascent", unexpected_ascent)

    result = adapter.run_hard_div_pairwise_bounded_candidate_adapter(adapter.big_lotto_dispatch(2))

    assert result.status is adapter.AdapterStatus.NOT_RUN
    assert result.status_reason is not None
    assert result.status_reason.startswith("EXISTING_NATIVE_EXECUTION_FAILED:")
    assert result.seed_portfolio is None
    assert result.portfolio is None
    assert result.exact_q is None


def test_independent_terminal_hard_postcheck_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    postcheck_calls: list[Portfolio] = []

    def staged_postcheck(portfolio: Portfolio, *, expected_k: int) -> bool:
        assert len(portfolio) == expected_k
        postcheck_calls.append(portfolio)
        return len(postcheck_calls) == 1

    def fake_ascent(
        _pool_size: int,
        _draw_size: int,
        _minimum_matches: int,
        seed: Portfolio,
    ) -> adapter._HardDivAscentResult:
        return _terminal_ascent(seed)

    monkeypatch.setattr(adapter, "_terminal_hard_postcheck", staged_postcheck)
    monkeypatch.setattr(adapter, "_iterative_hard_feasible_ascent", fake_ascent)

    result = adapter.run_hard_div_pairwise_bounded_candidate_adapter(adapter.big_lotto_dispatch(2))

    assert len(postcheck_calls) == 2
    assert result.status is adapter.AdapterStatus.NOT_RUN
    assert result.status_reason is not None
    assert result.status_reason.endswith("terminal hard postcheck mismatch")
    assert result.portfolio is None
    assert result.local_optimum_status is None
    assert result.proof_status is None
    assert result.global_optimum_status == "UNKNOWN"
