"""Exactness and search-mechanics checks for the K20 two-number-exchange engine."""

from __future__ import annotations

import itertools
import random
from collections.abc import Sequence
from math import comb
from typing import Any, cast

import numpy as np
import pytest

from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.research.b649_sealed_geometry_two_exchange import (
    BASELINE_WINNING_OUTCOMES,
    ExactExchangeSpace,
    canonical_portfolio,
    draw_weight_coefficients,
    exact_steepest_ascent,
    exchange_neighborhood,
    run_v3_k20_two_exchange_search,
    scan_exchange_neighborhood,
)

# Same (draw_size=6, outright_matches=3) recursion depth as real BIG_LOTTO, but a pool small
# enough that every replacement candidate -- all C(12, 6) = 924 of them, not a sample -- can be
# checked against the canonical evaluator directly.
_SMALL_POOL, _SMALL_DRAW, _SMALL_OUTRIGHT = 12, 6, 3


@pytest.fixture(scope="module")
def small_space() -> ExactExchangeSpace:
    return ExactExchangeSpace(
        pool_size=_SMALL_POOL, draw_size=_SMALL_DRAW, outright_matches=_SMALL_OUTRIGHT
    )


@pytest.fixture(scope="module")
def small_draws() -> DrawMasks:
    return all_main_draw_masks(_SMALL_POOL, _SMALL_DRAW)


@pytest.fixture(scope="module")
def small_tickets() -> list[tuple[int, ...]]:
    return list(itertools.combinations(range(1, _SMALL_POOL + 1), _SMALL_DRAW))


def _canonical_count(portfolio: Sequence[Sequence[int]], draws: DrawMasks) -> int:
    return evaluate_portfolio(
        portfolio,
        pool_size=_SMALL_POOL,
        draw_size=_SMALL_DRAW,
        outright_matches=_SMALL_OUTRIGHT,
        draws=draws,
    ).official_any_prize_outcome_count


def test_draw_weight_coefficients_match_the_module_docstrings_formula() -> None:
    coefficients, denominator = draw_weight_coefficients(6, 3)
    assert denominator == 4
    assert coefficients == {3: 1, 4: -4, 5: 12, 6: -40}


def test_two_number_exchange_neighborhood_is_exhaustive_and_legal() -> None:
    ticket = (3, 13, 14, 28, 36, 44)
    neighborhood = exchange_neighborhood(ticket, pool_size=49, exchange_size=2)
    assert neighborhood.rows.shape == (comb(6, 2) * comb(43, 2), 6)

    seen: set[tuple[int, ...]] = set()
    for row in neighborhood.rows.tolist():
        candidate = tuple(int(n) for n in row)
        assert len(set(candidate)) == 6
        assert list(candidate) == sorted(candidate)
        assert all(1 <= n <= 49 for n in candidate)
        assert len(set(candidate) ^ set(ticket)) == 4  # exactly 2 removed, 2 inserted
        seen.add(candidate)
    assert len(seen) == neighborhood.rows.shape[0]


@pytest.mark.parametrize(
    "ticket",
    [(1, 2, 3, 4, 5, 5), (0, 1, 2, 3, 4, 5), (1, 2, 3, 4, 5, 50)],
)
def test_exchange_neighborhood_rejects_illegal_tickets(ticket: tuple[int, ...]) -> None:
    # exchange_neighborhood only checks distinctness and pool range: it is a generic
    # k-of-n combinatorial primitive, agnostic to draw_size (callers such as
    # scan_exchange_neighborhood enforce draw_size via canonical_portfolio/_legal_tickets
    # before any ticket reaches here), so a wrong-length-but-otherwise-legal ticket is
    # deliberately not covered by this parametrization.
    with pytest.raises(ValueError):
        exchange_neighborhood(ticket, pool_size=49, exchange_size=2)


def test_exchange_neighborhood_is_agnostic_to_ticket_length() -> None:
    neighborhood = exchange_neighborhood((1, 2, 3, 4, 5), pool_size=49, exchange_size=2)
    assert neighborhood.rows.shape == (comb(5, 2) * comb(44, 2), 5)


def test_canonical_portfolio_sorts_tickets_and_their_numbers() -> None:
    scrambled = [(6, 2, 4), (1, 9, 3)]
    assert canonical_portfolio(scrambled, pool_size=9, draw_size=3) == ((1, 3, 9), (2, 4, 6))


def test_replacement_scorer_matches_canonical_exhaustively_on_small_lottery(
    small_space: ExactExchangeSpace, small_draws: DrawMasks, small_tickets: list[tuple[int, ...]]
) -> None:
    rng = random.Random(20260926)
    checked = 0
    for _ in range(6):
        portfolio = canonical_portfolio(
            rng.sample(small_tickets, rng.randint(3, 5)),
            pool_size=_SMALL_POOL,
            draw_size=_SMALL_DRAW,
        )
        coverage = small_space.coverage(portfolio)
        assert coverage.outcome_count == _canonical_count(portfolio, small_draws)

        for index in range(len(portfolio)):
            scorer = small_space.replacement_scorer(coverage, index)
            candidates = np.array(small_tickets, dtype=np.int64)
            fast_counts = small_space.replacement_outcome_counts(scorer, candidates)
            for row, candidate in enumerate(small_tickets):
                replaced = [*portfolio[:index], candidate, *portfolio[index + 1 :]]
                expected = _canonical_count(replaced, small_draws)
                assert int(fast_counts[row]) == expected, (portfolio, index, candidate)
                checked += 1
    assert checked > 0


def test_scan_exchange_neighborhood_best_matches_brute_force_on_small_lottery(
    small_space: ExactExchangeSpace, small_draws: DrawMasks, small_tickets: list[tuple[int, ...]]
) -> None:
    rng = random.Random(20260927)
    portfolio = canonical_portfolio(
        rng.sample(small_tickets, 4), pool_size=_SMALL_POOL, draw_size=_SMALL_DRAW
    )
    scan = scan_exchange_neighborhood(small_space, portfolio, exchange_size=2)
    assert scan.outcome_count == _canonical_count(portfolio, small_draws)

    brute_best = scan.outcome_count
    for index in range(len(portfolio)):
        neighborhood = exchange_neighborhood(
            portfolio[index], pool_size=_SMALL_POOL, exchange_size=2
        )
        for row in range(neighborhood.rows.shape[0]):
            candidate = neighborhood.move(row)[2]
            replaced = [*portfolio[:index], candidate, *portfolio[index + 1 :]]
            if len(set(replaced)) != len(replaced):
                continue  # duplicate-ticket candidate: ineligible, matches scan's own exclusion
            brute_best = max(brute_best, _canonical_count(replaced, small_draws))

    assert scan.best_outcome_count == brute_best


def test_scan_flags_a_constructed_duplicate_ticket_candidate(
    small_space: ExactExchangeSpace,
) -> None:
    ticket_a = (1, 2, 3, 4, 5, 6)
    ticket_b = (1, 2, 3, 4, 7, 8)  # exactly A with {5, 6} exchanged for {7, 8}
    portfolio = canonical_portfolio(
        [ticket_a, ticket_b], pool_size=_SMALL_POOL, draw_size=_SMALL_DRAW
    )
    scan = scan_exchange_neighborhood(small_space, portfolio, exchange_size=2)

    per_ticket_a = next(entry for entry in scan.per_ticket if entry.ticket == ticket_a)
    assert per_ticket_a.duplicate_ticket_candidate_count == 1


def test_scan_exchange_neighborhood_rejects_duplicate_portfolio_tickets(
    small_space: ExactExchangeSpace,
) -> None:
    with pytest.raises(ValueError):
        scan_exchange_neighborhood(
            small_space, [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6)], exchange_size=2
        )


def test_exact_steepest_ascent_matches_independent_canonical_replay_on_small_lottery(
    small_space: ExactExchangeSpace, small_draws: DrawMasks
) -> None:
    start = canonical_portfolio(
        [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7)], pool_size=_SMALL_POOL, draw_size=_SMALL_DRAW
    )
    ascent = exact_steepest_ascent(small_space, start, exchange_size=2, draws=small_draws)

    assert ascent.initial_outcome_count == _canonical_count(start, small_draws)
    assert len(ascent.accepted) >= 1  # a genuinely weak start must find at least one improvement
    assert ascent.local_optimum

    replay = start
    for step in ascent.accepted:
        replay = canonical_portfolio(
            [t for i, t in enumerate(replay) if i != step.move.ticket_index]
            + [step.move.new_ticket],
            pool_size=_SMALL_POOL,
            draw_size=_SMALL_DRAW,
        )
        assert replay == step.portfolio
        assert _canonical_count(replay, small_draws) == step.new_outcome_count
    assert replay == ascent.final_portfolio
    assert _canonical_count(replay, small_draws) == ascent.final_outcome_count


def test_run_v3_k20_two_exchange_search_reproduces_the_frozen_v3_local_optimum() -> None:
    # The function's own return type is the deliberately loose dict[str, object] of a
    # heterogeneous JSON-shaped result; cast once at the boundary rather than fighting
    # strict-mode subscripting on `object` for every nested field this test inspects.
    result = cast("dict[str, Any]", run_v3_k20_two_exchange_search())

    assert result["SCORER_PARITY"] == "PASS"
    assert result["SCORER_PARITY_CHECKS"]
    assert all(check["EXACT_MATCH"] for check in result["SCORER_PARITY_CHECKS"])
    assert result["BASELINE"]["WINNING_OUTCOMES"] == BASELINE_WINNING_OUTCOMES == 312850818
    assert result["TOTAL_CANDIDATES_EVALUATED"] == 20 * comb(6, 2) * comb(43, 2) == 270900
    assert result["SEARCH_SPACE_COMPLETE"] == "YES"
    assert result["TWO_EXCHANGE_LOCAL_OPTIMUM"] == "YES"
    assert result["ACCEPTED_MOVES"] == []
    assert result["ITERATION_COUNT"] == 1
    assert result["FINAL_PORTFOLIO_UNCHANGED_V3"] is True
    assert result["FINAL_WINNING_OUTCOMES"] == BASELINE_WINNING_OUTCOMES
    assert result["CANONICAL_FINAL_VALIDATION"]["EXACT_AGREEMENT_WITH_SEARCH"] == "PASS"
    assert result["RESULT_LEAKAGE"] == "NONE"
