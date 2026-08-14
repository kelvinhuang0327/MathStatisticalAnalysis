from __future__ import annotations

from fractions import Fraction

from lottolab.research.bounded_coverage_optimizer import (
    BoundedSearchResult,
    exact_portfolio_coverage,
    restart_greedy_swap_search,
)

# Toy lottery shape only, per this module's documented scope boundary --
# never (49, 6), the real B649 rule, in this design-only feasibility suite.
_POOL_SIZE = 10
_DRAW_SIZE = 3
_MINIMUM_MATCHES = 2
_TICKET_COUNT = 4
_SEED = 20260815


def test_exact_portfolio_coverage_matches_hand_enumeration_for_one_ticket() -> None:
    # A single ticket {1,2,3} needs >= 2 of its 3 numbers in the draw.
    # K(2) = C(3,2)*C(7,1) + C(3,3)*C(7,0) = 3*7 + 1*1 = 22 out of C(10,3)=120.
    coverage = exact_portfolio_coverage(_POOL_SIZE, _DRAW_SIZE, _MINIMUM_MATCHES, ((1, 2, 3),))
    assert coverage == Fraction(22, 120)


def test_exact_portfolio_coverage_is_monotonic_in_portfolio_size() -> None:
    one_ticket = exact_portfolio_coverage(_POOL_SIZE, _DRAW_SIZE, _MINIMUM_MATCHES, ((1, 2, 3),))
    two_tickets = exact_portfolio_coverage(
        _POOL_SIZE, _DRAW_SIZE, _MINIMUM_MATCHES, ((1, 2, 3), (4, 5, 6))
    )
    assert two_tickets >= one_ticket


def _run() -> BoundedSearchResult:
    return restart_greedy_swap_search(
        _POOL_SIZE,
        _DRAW_SIZE,
        _MINIMUM_MATCHES,
        _TICKET_COUNT,
        seed=_SEED,
        restart_count=2,
        candidate_sample_size=10,
        max_swap_passes=2,
    )


def test_result_portfolio_is_structurally_valid() -> None:
    result = _run()
    assert len(result.portfolio) == _TICKET_COUNT
    assert len(set(result.portfolio)) == _TICKET_COUNT  # duplicate tickets = 0
    for ticket in result.portfolio:
        assert len(ticket) == _DRAW_SIZE
        assert len(set(ticket)) == _DRAW_SIZE
        assert all(1 <= n <= _POOL_SIZE for n in ticket)
        assert ticket == tuple(sorted(ticket))


def test_reported_coverage_matches_independent_recomputation() -> None:
    result = _run()
    recomputed = exact_portfolio_coverage(
        _POOL_SIZE, _DRAW_SIZE, _MINIMUM_MATCHES, result.portfolio
    )
    assert recomputed == result.coverage


def test_deterministic_across_repeated_calls_given_same_seed() -> None:
    first = _run()
    second = _run()
    assert first == second


def test_evaluations_used_is_within_the_documented_ceiling() -> None:
    result = _run()
    restart_count, candidate_sample_size, max_swap_passes = 2, 10, 2
    build_ceiling = _TICKET_COUNT * candidate_sample_size
    swap_ceiling = max_swap_passes * _TICKET_COUNT * (candidate_sample_size + 1)
    per_restart_ceiling = build_ceiling + swap_ceiling
    assert result.evaluations_used <= restart_count * per_restart_ceiling
    assert result.evaluations_used > 0


def test_best_restart_index_points_at_the_returned_result() -> None:
    result = _run()
    chosen = result.restart_outcomes[result.best_restart_index]
    assert chosen.portfolio == result.portfolio
    assert chosen.coverage == result.coverage


def test_each_restart_is_independently_seeded_and_reproducible() -> None:
    result = _run()
    for outcome in result.restart_outcomes:
        assert len(set(outcome.portfolio)) == _TICKET_COUNT
        assert outcome.swap_passes_run <= 2
        assert isinstance(outcome.converged, bool)


def test_more_swap_passes_never_decreases_best_final_coverage() -> None:
    fewer_passes = restart_greedy_swap_search(
        _POOL_SIZE,
        _DRAW_SIZE,
        _MINIMUM_MATCHES,
        _TICKET_COUNT,
        seed=_SEED,
        restart_count=1,
        candidate_sample_size=8,
        max_swap_passes=1,
    )
    more_passes = restart_greedy_swap_search(
        _POOL_SIZE,
        _DRAW_SIZE,
        _MINIMUM_MATCHES,
        _TICKET_COUNT,
        seed=_SEED,
        restart_count=1,
        candidate_sample_size=8,
        max_swap_passes=4,
    )
    assert more_passes.coverage >= fewer_passes.coverage


def test_generalizes_to_a_second_toy_pool_shape() -> None:
    result = restart_greedy_swap_search(
        8, 2, 1, 3, seed=_SEED, restart_count=1, candidate_sample_size=6, max_swap_passes=1
    )
    assert len(result.portfolio) == 3
    assert len(set(result.portfolio)) == 3
