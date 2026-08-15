from __future__ import annotations

import pytest

from lottolab.research.bounded_coverage_optimizer import (
    BoundedSearchResult,
    restart_greedy_swap_search,
)
from lottolab.research.bounded_coverage_optimizer_fast import restart_greedy_swap_search_fast

# Toy lottery shapes only, per the Phase-5 design doc's scope boundary --
# (49, 6) parity is exercised separately by the B649-native tests below,
# each bounded to a tiny budget so the suite stays fast (the canonical
# `exact_portfolio_coverage` re-enumerates the full C(49,6) winning space
# per call).
_POOL_SIZE = 10
_DRAW_SIZE = 3
_MINIMUM_MATCHES = 2
_TICKET_COUNT = 4
_SEED = 20260815


def _run_fast(**overrides: object) -> BoundedSearchResult:
    kwargs: dict[str, object] = dict(
        pool_size=_POOL_SIZE,
        draw_size=_DRAW_SIZE,
        minimum_matches=_MINIMUM_MATCHES,
        ticket_count=_TICKET_COUNT,
        seed=_SEED,
        restart_count=2,
        candidate_sample_size=10,
        max_swap_passes=2,
    )
    kwargs.update(overrides)
    return restart_greedy_swap_search_fast(**kwargs)  # type: ignore[arg-type]


# Parity against the frozen slow search (the correctness authority): same
# seed must produce byte-identical portfolio, coverage, evaluations_used,
# and best_restart_index, because candidate sampling never depends on which
# evaluator computed a coverage value, only exact-parity coverage values do
# (test_exact_coverage_fast_evaluator.py) -- so the two searches can only
# diverge if control flow itself diverges.


def test_parity_with_slow_search_default_toy_shape() -> None:
    fast = _run_fast()
    slow = restart_greedy_swap_search(
        _POOL_SIZE,
        _DRAW_SIZE,
        _MINIMUM_MATCHES,
        _TICKET_COUNT,
        seed=_SEED,
        restart_count=2,
        candidate_sample_size=10,
        max_swap_passes=2,
    )
    assert fast.portfolio == slow.portfolio
    assert fast.coverage == slow.coverage
    assert fast.evaluations_used == slow.evaluations_used
    assert fast.best_restart_index == slow.best_restart_index
    outcome_pairs = zip(fast.restart_outcomes, slow.restart_outcomes, strict=True)
    for fast_outcome, slow_outcome in outcome_pairs:
        assert fast_outcome.portfolio == slow_outcome.portfolio
        assert fast_outcome.coverage == slow_outcome.coverage
        assert fast_outcome.evaluations_used == slow_outcome.evaluations_used
        assert fast_outcome.converged == slow_outcome.converged
        assert fast_outcome.swap_passes_run == slow_outcome.swap_passes_run


def test_parity_with_slow_search_across_several_configs() -> None:
    configs: list[dict[str, object]] = [
        dict(
            pool_size=8, draw_size=2, minimum_matches=1, ticket_count=3,
            seed=20260815, restart_count=1, candidate_sample_size=6, max_swap_passes=1,
        ),
        dict(
            pool_size=14, draw_size=4, minimum_matches=2, ticket_count=5,
            seed=999, restart_count=3, candidate_sample_size=12, max_swap_passes=3,
        ),
        dict(
            pool_size=12, draw_size=5, minimum_matches=3, ticket_count=6,
            seed=1234, restart_count=2, candidate_sample_size=8, max_swap_passes=2,
        ),
        dict(
            pool_size=9, draw_size=3, minimum_matches=1, ticket_count=1,
            seed=7, restart_count=1, candidate_sample_size=5, max_swap_passes=1,
        ),
    ]
    for kwargs in configs:
        fast = restart_greedy_swap_search_fast(**kwargs)  # type: ignore[arg-type]
        slow = restart_greedy_swap_search(**kwargs)  # type: ignore[arg-type]
        assert fast.portfolio == slow.portfolio, kwargs
        assert fast.coverage == slow.coverage, kwargs
        assert fast.evaluations_used == slow.evaluations_used, kwargs


def test_b649_native_parity_at_tiny_budget() -> None:
    # Real B649 shape, budget kept tiny so the slow correctness authority
    # (full C(49,6) re-enumeration per call) stays fast in CI.
    kwargs: dict[str, object] = dict(
        pool_size=49, draw_size=6, minimum_matches=3, ticket_count=3,
        seed=20260815, restart_count=1, candidate_sample_size=6, max_swap_passes=1,
    )
    fast = restart_greedy_swap_search_fast(**kwargs)  # type: ignore[arg-type]
    slow = restart_greedy_swap_search(**kwargs)  # type: ignore[arg-type]
    assert fast.portfolio == slow.portfolio
    assert fast.coverage == slow.coverage
    assert fast.evaluations_used == slow.evaluations_used


# Structural validity, determinism, and budget enforcement, mirroring
# test_bounded_coverage_optimizer.py's own suite for the slow search.


def test_result_portfolio_is_structurally_valid() -> None:
    result = _run_fast()
    assert len(result.portfolio) == _TICKET_COUNT
    assert len(set(result.portfolio)) == _TICKET_COUNT  # duplicate tickets = 0
    for ticket in result.portfolio:
        assert len(ticket) == _DRAW_SIZE
        assert len(set(ticket)) == _DRAW_SIZE
        assert all(1 <= n <= _POOL_SIZE for n in ticket)
        assert ticket == tuple(sorted(ticket))


def test_deterministic_across_repeated_calls_given_same_seed() -> None:
    first = _run_fast()
    second = _run_fast()
    assert first == second


def test_evaluations_used_is_within_the_documented_ceiling() -> None:
    result = _run_fast()
    restart_count, candidate_sample_size, max_swap_passes = 2, 10, 2
    build_ceiling = _TICKET_COUNT * candidate_sample_size
    swap_ceiling = max_swap_passes * _TICKET_COUNT * (candidate_sample_size + 1)
    per_restart_ceiling = build_ceiling + swap_ceiling
    assert result.evaluations_used <= restart_count * per_restart_ceiling
    assert result.evaluations_used > 0


def test_best_restart_index_points_at_the_returned_result() -> None:
    result = _run_fast()
    chosen = result.restart_outcomes[result.best_restart_index]
    assert chosen.portfolio == result.portfolio
    assert chosen.coverage == result.coverage


def test_generalizes_to_a_second_toy_pool_shape() -> None:
    result = restart_greedy_swap_search_fast(
        8, 2, 1, 3, seed=_SEED, restart_count=1, candidate_sample_size=6, max_swap_passes=1
    )
    assert len(result.portfolio) == 3
    assert len(set(result.portfolio)) == 3


def test_restart_count_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="restart_count"):
        restart_greedy_swap_search_fast(
            _POOL_SIZE, _DRAW_SIZE, _MINIMUM_MATCHES, _TICKET_COUNT,
            seed=_SEED, restart_count=0, candidate_sample_size=10, max_swap_passes=1,
        )
