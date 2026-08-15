"""`RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1` (arm C), fast-evaluator-backed.

This is the *same* frozen search family `bounded_coverage_optimizer.py`
defines and `docs/research/strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md`
§6 specifies -- not a new constructor, not a redefinition. It exists as a
separate module, rather than an edit to `bounded_coverage_optimizer.py`, so
that module stays exactly as committed and toy-verified (10 passing tests,
`exact_portfolio_coverage` as its correctness authority) with zero risk of
regression, while this module substitutes `exact_coverage_fast_evaluator`'s
already parity-verified `coverage_with_base` / `fast_exact_portfolio_coverage`
for `exact_portfolio_coverage` wherever the frozen algorithm calls it --
exactly the "drop-in, exact-parity replacement" that module's own docstring
describes. Every candidate-sampling call goes through the same
`bounded_coverage_optimizer._sample_distinct_candidates` helper (imported,
not copied), so the sequence of `rng.sample()` calls -- and therefore every
tie-break and convergence decision -- is identical between this module and
the slow one for the same seed: coverage values are proven exact-equal
(`test_exact_coverage_fast_evaluator.py`), so the two searches can only
diverge if the control flow itself diverges, which
`test_bounded_coverage_optimizer_fast.py`'s direct parity tests check at
toy scale.

`_sample_distinct_candidates` below is an exact copy of
`bounded_coverage_optimizer._sample_distinct_candidates`, not a fork: it is
reproduced here (rather than imported) only because it is a private,
underscore-prefixed helper and pyright's strict mode correctly rejects
cross-module private access. Copying it, instead of exporting it from the
frozen module, keeps that module's public surface exactly as committed.
Because `bounded_coverage_optimizer.py` is frozen (971b97b, §2), this is a
one-time duplication, not an ongoing two-copies-to-maintain risk.

Cache policy (locked by `STRATEGY_MATRIX_PHASE5_B649_CONSTRUCTOR_FRONTIER_LOCK_EXECUTE_R1`):
clear between swap slots, clear between restarts, no result-dependent
policy. This module additionally clears once per construction step (i.e.
once per ticket built, not just once per swap slot). That third point is a
disclosed, results-neutral superset of the two locked clearing points, not
a change to them: `exact_coverage_fast_evaluator.clear_cache()` never
changes any returned value (`test_clear_cache_does_not_change_results`),
only which per-ticket results are already memoized, and the construction
phase samples `candidate_sample_size` fresh candidates per ticket exactly
like a swap slot does -- at real B649 scale (~26 MB per distinct cached
ticket at `minimum_matches=3`, per `exact_coverage_fast_evaluator`'s own
measurement), leaving an entire `ticket_count`-step construction phase
uncleared before the first "between restarts" boundary risks tens of GB of
resident memory for the richer ladder rungs. Clearing every step keeps peak
memory near one step's own candidate batch regardless of `ticket_count`.
"""

from __future__ import annotations

import random
from fractions import Fraction

from lottolab.research.bounded_coverage_optimizer import BoundedSearchResult, RestartOutcome
from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    coverage_with_base,
    fast_exact_portfolio_coverage,
    portfolio_qualifying_draws,
    ticket_qualifying_draws,
)

Ticket = tuple[int, ...]


def _sample_distinct_candidates(
    rng: random.Random,
    pool_size: int,
    draw_size: int,
    sample_size: int,
    exclude: set[Ticket],
    max_attempts: int,
) -> list[Ticket]:
    """Exact copy of `bounded_coverage_optimizer._sample_distinct_candidates`.

    Reproduced, not imported, so this module's RNG call sequence is
    guaranteed identical to the frozen slow search's for the same seed
    (module docstring) without depending on that module's private surface.
    """

    found: list[Ticket] = []
    seen = set(exclude)
    attempts = 0
    while len(found) < sample_size and attempts < max_attempts:
        attempts += 1
        candidate = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
        if candidate in seen:
            continue
        seen.add(candidate)
        found.append(candidate)
    return found


def _build_by_randomized_greedy_fast(
    rng: random.Random,
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    ticket_count: int,
    candidate_sample_size: int,
    max_sample_attempts: int,
) -> tuple[tuple[Ticket, ...], int]:
    portfolio: list[Ticket] = []
    base_draws: frozenset[Ticket] = frozenset()
    evaluations = 0
    for _ in range(ticket_count):
        candidates = _sample_distinct_candidates(
            rng, pool_size, draw_size, candidate_sample_size, set(portfolio), max_sample_attempts
        )
        best_candidate: Ticket | None = None
        best_coverage: Fraction | None = None
        for candidate in candidates:
            coverage = coverage_with_base(
                pool_size, draw_size, minimum_matches, base_draws, candidate
            )
            evaluations += 1
            is_new_best = best_coverage is None or coverage > best_coverage
            is_lexicographic_tie_winner = (
                best_candidate is not None
                and coverage == best_coverage
                and candidate < best_candidate
            )
            if is_new_best or is_lexicographic_tie_winner:
                best_coverage = coverage
                best_candidate = candidate
        assert best_candidate is not None  # candidate_sample_size >= 1 and space not exhausted
        portfolio.append(best_candidate)
        base_draws = base_draws | ticket_qualifying_draws(
            pool_size, draw_size, minimum_matches, best_candidate
        )
        clear_cache()
    return tuple(portfolio), evaluations


def _local_swap_search_fast(
    rng: random.Random,
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: tuple[Ticket, ...],
    candidate_sample_size: int,
    max_swap_passes: int,
    max_sample_attempts: int,
    evaluations_so_far: int,
) -> tuple[tuple[Ticket, ...], Fraction, int, bool, int]:
    current = list(portfolio)
    evaluations = evaluations_so_far
    current_coverage = fast_exact_portfolio_coverage(
        pool_size, draw_size, minimum_matches, tuple(current)
    )
    evaluations += 1
    clear_cache()
    passes_run = 0
    converged = False
    for pass_index in range(max_swap_passes):
        passes_run = pass_index + 1
        improved_this_pass = False
        for slot in range(len(current)):
            remaining = [ticket for index, ticket in enumerate(current) if index != slot]
            base_draws = portfolio_qualifying_draws(
                pool_size, draw_size, minimum_matches, tuple(remaining)
            )
            exclude = set(remaining)
            candidates = _sample_distinct_candidates(
                rng, pool_size, draw_size, candidate_sample_size, exclude, max_sample_attempts
            )
            best_candidate = current[slot]
            best_coverage = current_coverage
            for candidate in candidates:
                if candidate == current[slot]:
                    continue
                coverage = coverage_with_base(
                    pool_size, draw_size, minimum_matches, base_draws, candidate
                )
                evaluations += 1
                if coverage > best_coverage or (
                    coverage == best_coverage and candidate < best_candidate
                ):
                    best_coverage = coverage
                    best_candidate = candidate
            if best_coverage > current_coverage:
                current[slot] = best_candidate
                current_coverage = best_coverage
                improved_this_pass = True
            clear_cache()
        if not improved_this_pass:
            converged = True
            break
    return tuple(current), current_coverage, evaluations, converged, passes_run


def restart_greedy_swap_search_fast(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    ticket_count: int,
    *,
    seed: int,
    restart_count: int,
    candidate_sample_size: int,
    max_swap_passes: int,
    max_sample_attempts: int = 200,
) -> BoundedSearchResult:
    """Fast-evaluator-backed `restart_greedy_swap_search`, identical contract.

    Same signature, same return type, same frozen algorithm (§6 of the
    Phase-5 design doc) as `bounded_coverage_optimizer.restart_greedy_swap_search`
    -- only the coverage-evaluation calls are swapped for the parity-verified
    fast evaluator, with the locked cache policy applied (module docstring).
    """

    if restart_count < 1:
        raise ValueError("restart_count must be >= 1")

    restart_outcomes: list[RestartOutcome] = []
    for restart_index in range(restart_count):
        clear_cache()
        rng = random.Random(seed + restart_index)
        built_portfolio, build_evaluations = _build_by_randomized_greedy_fast(
            rng,
            pool_size,
            draw_size,
            minimum_matches,
            ticket_count,
            candidate_sample_size,
            max_sample_attempts,
        )
        final_portfolio, final_coverage, total_evaluations, converged, passes_run = (
            _local_swap_search_fast(
                rng,
                pool_size,
                draw_size,
                minimum_matches,
                built_portfolio,
                candidate_sample_size,
                max_swap_passes,
                max_sample_attempts,
                build_evaluations,
            )
        )
        restart_outcomes.append(
            RestartOutcome(
                portfolio=final_portfolio,
                coverage=final_coverage,
                evaluations_used=total_evaluations,
                converged=converged,
                swap_passes_run=passes_run,
            )
        )
    clear_cache()

    best_index = 0
    for index, outcome in enumerate(restart_outcomes[1:], start=1):
        current_best = restart_outcomes[best_index]
        if outcome.coverage > current_best.coverage or (
            outcome.coverage == current_best.coverage
            and outcome.portfolio < current_best.portfolio
        ):
            best_index = index

    best = restart_outcomes[best_index]
    total_evaluations = sum(outcome.evaluations_used for outcome in restart_outcomes)
    return BoundedSearchResult(
        portfolio=best.portfolio,
        coverage=best.coverage,
        evaluations_used=total_evaluations,
        restart_outcomes=tuple(restart_outcomes),
        best_restart_index=best_index,
    )
