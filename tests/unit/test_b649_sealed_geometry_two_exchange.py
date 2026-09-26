"""Exactness and search-mechanics checks for the K20 number-exchange engine."""

from __future__ import annotations

import dataclasses
import itertools
import random
from collections.abc import Sequence
from math import comb
from typing import Any, cast

import numpy as np
import pytest

import lottolab.research.b649_sealed_geometry_two_exchange as exchange_module
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.research.b649_sealed_geometry_two_exchange import (
    BASELINE_WINNING_OUTCOMES,
    UP_TO_THREE_NUMBER_EXCHANGES,
    ExactExchangeSpace,
    canonical_portfolio,
    draw_weight_coefficients,
    exact_steepest_ascent,
    exchange_neighborhood,
    run_v3_k20_three_exchange_search,
    run_v3_k20_two_exchange_search,
    scan_exchange_neighborhood,
)

# Same (draw_size=6, outright_matches=3) recursion depth as real BIG_LOTTO, but a pool small
# enough that every replacement candidate -- all C(12, 6) = 924 of them, not a sample -- can be
# checked against the canonical evaluator directly.
_SMALL_POOL, _SMALL_DRAW, _SMALL_OUTRIGHT = 12, 6, 3
# Larger pools at the same depth. Three tickets of the 12-number pool already win nearly every
# outcome, so almost every candidate ties there; these leave room for rankings to differ.
_MEDIUM_POOL = 16
_ASCENT_POOL = 19
# Its first two tickets share three numbers (duplicate-ticket candidates), and its best
# neighbors are reached from two different tickets, so the cross-ticket tie-break decides.
_MEDIUM_PORTFOLIO = ((1, 2, 3, 4, 5, 6), (4, 5, 6, 7, 8, 9), (1, 7, 10, 12, 14, 16))
# From here the three-then-union ascent takes a three-number move and then a one-number move
# that beats every three-number move, and it stops short of winning every outcome.
_ASCENT_START = ((6, 10, 11, 12, 13, 14), (1, 4, 5, 9, 13, 16), (1, 2, 3, 9, 14, 19))

type _Portfolio = tuple[tuple[int, ...], ...]


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


@pytest.fixture(scope="module")
def medium_space() -> ExactExchangeSpace:
    return ExactExchangeSpace(pool_size=_MEDIUM_POOL, draw_size=6, outright_matches=3)


@pytest.fixture(scope="module")
def medium_draws() -> DrawMasks:
    return all_main_draw_masks(_MEDIUM_POOL, 6)


@pytest.fixture(scope="module")
def ascent_space() -> ExactExchangeSpace:
    return ExactExchangeSpace(pool_size=_ASCENT_POOL, draw_size=6, outright_matches=3)


@pytest.fixture(scope="module")
def ascent_draws() -> DrawMasks:
    return all_main_draw_masks(_ASCENT_POOL, 6)


def _canonical_count(portfolio: Sequence[Sequence[int]], draws: DrawMasks) -> int:
    return evaluate_portfolio(
        portfolio,
        pool_size=_SMALL_POOL,
        draw_size=_SMALL_DRAW,
        outright_matches=_SMALL_OUTRIGHT,
        draws=draws,
    ).official_any_prize_outcome_count


def _pool_count(portfolio: Sequence[Sequence[int]], pool_size: int, draws: DrawMasks) -> int:
    return evaluate_portfolio(
        portfolio, pool_size=pool_size, draw_size=6, outright_matches=3, draws=draws
    ).official_any_prize_outcome_count


@dataclasses.dataclass(frozen=True)
class _BruteForceScan:
    candidate_count_by_size: tuple[int, ...]
    distinct_portfolio_count: int
    duplicate_ticket_candidate_count: int
    improving_candidate_count_by_size: tuple[int, ...]
    best_outcome_count: int
    best_tie_count: int
    best_portfolio: _Portfolio


def _brute_force_scan(
    portfolio: Sequence[Sequence[int]], sizes: Sequence[int], pool_size: int, draws: DrawMasks
) -> _BruteForceScan:
    """Canonical-evaluator truth for a complete exchange neighborhood.

    Candidates are drawn from all ``C(pool_size, 6)`` tickets by overlap with the ticket
    they replace, not from ``exchange_neighborhood``.
    """

    tickets = canonical_portfolio(portfolio, pool_size=pool_size, draw_size=6)
    current = _pool_count(tickets, pool_size, draws)
    position = {size: order for order, size in enumerate(sizes)}
    candidates = [0] * len(sizes)
    improving = [0] * len(sizes)
    portfolios: set[_Portfolio] = set()
    duplicates = 0
    scored: list[tuple[int, _Portfolio]] = []
    for index, ticket in enumerate(tickets):
        others = tickets[:index] + tickets[index + 1 :]
        for candidate in itertools.combinations(range(1, pool_size + 1), 6):
            size = 6 - len(set(candidate) & set(ticket))
            if size not in position:
                continue
            replaced = tuple(sorted((*others, candidate)))
            candidates[position[size]] += 1
            portfolios.add(replaced)
            if candidate in others:
                duplicates += 1
                continue
            count = _pool_count(replaced, pool_size, draws)
            improving[position[size]] += int(count > current)
            scored.append((count, replaced))
    best = max(count for count, _ in scored)
    tied = sorted(replaced for count, replaced in scored if count == best)
    return _BruteForceScan(
        candidate_count_by_size=tuple(candidates),
        distinct_portfolio_count=len(portfolios),
        duplicate_ticket_candidate_count=duplicates,
        improving_candidate_count_by_size=tuple(improving),
        best_outcome_count=best,
        best_tie_count=len(tied),
        best_portfolio=tied[0],
    )


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


def test_three_number_exchange_neighborhood_is_complete_and_legal() -> None:
    ticket = (3, 13, 14, 28, 36, 44)
    rows = exchange_neighborhood(ticket, pool_size=49, exchange_size=3).rows

    assert rows.shape == (comb(6, 3) * comb(43, 3), 6) == (246820, 6)
    assert bool((np.diff(rows, axis=1) > 0).all())  # sorted, hence six distinct numbers
    assert int(rows.min()) >= 1 and int(rows.max()) <= 49
    assert bool((np.isin(rows, ticket).sum(axis=1) == 3).all())  # 3 removed, 3 inserted
    # C(6, 3) * C(43, 3) distinct legal tickets that each keep exactly three numbers of
    # ``ticket`` are every such ticket: the neighborhood is complete.
    assert np.unique(rows, axis=0).shape[0] == rows.shape[0]


@pytest.mark.parametrize("size", UP_TO_THREE_NUMBER_EXCHANGES)
def test_exchange_neighborhood_equals_brute_force_enumeration(size: int) -> None:
    ticket = (2, 5, 6, 9, 11, 15)
    rows = exchange_neighborhood(ticket, pool_size=_MEDIUM_POOL, exchange_size=size).rows
    expected = {
        candidate
        for candidate in itertools.combinations(range(1, _MEDIUM_POOL + 1), 6)
        if len(set(candidate) & set(ticket)) == 6 - size
    }
    assert rows.shape[0] == len(expected)
    assert {tuple(int(n) for n in row) for row in rows.tolist()} == expected


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
    scan = scan_exchange_neighborhood(small_space, portfolio, exchange_sizes=(2,))
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


@pytest.mark.parametrize("sizes", [(3,), UP_TO_THREE_NUMBER_EXCHANGES])
def test_scan_matches_an_independent_brute_force_including_the_tie_break(
    medium_space: ExactExchangeSpace, medium_draws: DrawMasks, sizes: tuple[int, ...]
) -> None:
    scan = scan_exchange_neighborhood(medium_space, _MEDIUM_PORTFOLIO, exchange_sizes=sizes)
    truth = _brute_force_scan(_MEDIUM_PORTFOLIO, sizes, _MEDIUM_POOL, medium_draws)

    assert scan.exchange_sizes == sizes
    assert scan.candidate_count_by_size == truth.candidate_count_by_size
    assert truth.candidate_count_by_size == tuple(
        3 * comb(6, size) * comb(_MEDIUM_POOL - 6, size) for size in sizes
    )
    assert scan.candidate_count == sum(truth.candidate_count_by_size)
    assert scan.distinct_portfolio_count == truth.distinct_portfolio_count == scan.candidate_count
    assert scan.duplicate_ticket_candidate_count == truth.duplicate_ticket_candidate_count > 0
    assert scan.improving_candidate_count_by_size == truth.improving_candidate_count_by_size
    assert scan.best_outcome_count == truth.best_outcome_count
    leaders = {
        entry.ticket_index
        for entry in scan.per_ticket
        if entry.best_outcome_count == scan.best_outcome_count
    }
    assert len(leaders) > 1  # the tie spans tickets, so the cross-ticket reduction decides
    assert scan.best_tie_count == truth.best_tie_count > 1
    assert scan.best_portfolio == truth.best_portfolio  # smallest canonical portfolio

    move = scan.best_move
    kept = [ticket for index, ticket in enumerate(scan.portfolio) if index != move.ticket_index]
    assert (
        canonical_portfolio([*kept, move.new_ticket], pool_size=_MEDIUM_POOL, draw_size=6)
        == scan.best_portfolio
    )
    assert move.old_ticket == scan.portfolio[move.ticket_index]
    assert move.exchange_size == len(move.inserted_numbers) in sizes
    assert set(move.new_ticket) == (set(move.old_ticket) - set(move.removed_numbers)) | set(
        move.inserted_numbers
    )


def test_scan_is_deterministic_and_independent_of_input_order(
    medium_space: ExactExchangeSpace,
) -> None:
    rng = random.Random(20260929)
    shuffled = [tuple(rng.sample(ticket, len(ticket))) for ticket in _MEDIUM_PORTFOLIO]
    rng.shuffle(shuffled)

    first = scan_exchange_neighborhood(
        medium_space, _MEDIUM_PORTFOLIO, exchange_sizes=UP_TO_THREE_NUMBER_EXCHANGES
    )
    again = scan_exchange_neighborhood(
        medium_space, _MEDIUM_PORTFOLIO, exchange_sizes=UP_TO_THREE_NUMBER_EXCHANGES
    )
    reordered = scan_exchange_neighborhood(medium_space, shuffled, exchange_sizes=(3, 1, 2))
    assert first == again == reordered


@pytest.mark.parametrize("sizes", [(), (2, 2)])
def test_scan_rejects_empty_or_repeated_exchange_sizes(
    small_space: ExactExchangeSpace, sizes: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError, match="exchange_sizes"):
        scan_exchange_neighborhood(small_space, [(1, 2, 3, 4, 5, 6)], exchange_sizes=sizes)


def test_scan_flags_a_constructed_duplicate_ticket_candidate(
    small_space: ExactExchangeSpace,
) -> None:
    ticket_a = (1, 2, 3, 4, 5, 6)
    ticket_b = (1, 2, 3, 4, 7, 8)  # exactly A with {5, 6} exchanged for {7, 8}
    portfolio = canonical_portfolio(
        [ticket_a, ticket_b], pool_size=_SMALL_POOL, draw_size=_SMALL_DRAW
    )
    scan = scan_exchange_neighborhood(small_space, portfolio, exchange_sizes=(2,))

    per_ticket_a = next(entry for entry in scan.per_ticket if entry.ticket == ticket_a)
    assert per_ticket_a.duplicate_ticket_candidate_count == 1


def test_scan_exchange_neighborhood_rejects_duplicate_portfolio_tickets(
    small_space: ExactExchangeSpace,
) -> None:
    with pytest.raises(ValueError):
        scan_exchange_neighborhood(
            small_space, [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6)], exchange_sizes=(2,)
        )


def test_exact_steepest_ascent_matches_independent_canonical_replay_on_small_lottery(
    small_space: ExactExchangeSpace, small_draws: DrawMasks
) -> None:
    start = canonical_portfolio(
        [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7)], pool_size=_SMALL_POOL, draw_size=_SMALL_DRAW
    )
    ascent = exact_steepest_ascent(small_space, start, exchange_sizes=(2,), draws=small_draws)

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


def test_three_then_union_ascent_takes_the_best_union_move_and_stops_at_a_union_optimum(
    ascent_space: ExactExchangeSpace, ascent_draws: DrawMasks
) -> None:
    ascent = exact_steepest_ascent(
        ascent_space,
        _ASCENT_START,
        exchange_sizes=UP_TO_THREE_NUMBER_EXCHANGES,
        first_scan_exchange_sizes=(3,),
        draws=ascent_draws,
    )

    # Only the scan of the start is narrowed; every scan after an accepted move is the union.
    assert [scan.exchange_sizes for scan in ascent.scans] == [(3,)] + [
        UP_TO_THREE_NUMBER_EXCHANGES
    ] * len(ascent.accepted)
    # The second move is a one-number exchange that beats every three-number move, so the
    # union rule changes where the ascent ends rather than merely re-confirming it.
    assert [step.move.exchange_size for step in ascent.accepted] == [3, 1]
    three_only = exact_steepest_ascent(
        ascent_space, _ASCENT_START, exchange_sizes=(3,), draws=ascent_draws
    )
    assert three_only.final_outcome_count < ascent.final_outcome_count

    previous = canonical_portfolio(_ASCENT_START, pool_size=_ASCENT_POOL, draw_size=6)
    assert ascent.initial_outcome_count == _pool_count(previous, _ASCENT_POOL, ascent_draws)
    for step, scan in zip(ascent.accepted, ascent.scans, strict=False):
        truth = _brute_force_scan(previous, scan.exchange_sizes, _ASCENT_POOL, ascent_draws)
        # The accepted move is the globally best strict improvement of its complete scan
        # (ties: smallest canonical portfolio), and it re-scores canonically.
        assert (step.new_outcome_count, step.portfolio) == (
            truth.best_outcome_count,
            truth.best_portfolio,
        )
        assert step.old_outcome_count == _pool_count(previous, _ASCENT_POOL, ascent_draws)
        assert step.new_outcome_count > step.old_outcome_count
        assert _pool_count(step.portfolio, _ASCENT_POOL, ascent_draws) == step.new_outcome_count
        kept = [ticket for index, ticket in enumerate(previous) if index != step.move.ticket_index]
        assert (
            canonical_portfolio([*kept, step.move.new_ticket], pool_size=_ASCENT_POOL, draw_size=6)
            == step.portfolio
        )
        previous = step.portfolio
    assert previous == ascent.final_portfolio

    # Stopping rule: the final portfolio's complete union neighborhood has no strict
    # improvement, and the optimum is a real one -- short of winning every outcome.
    final = _brute_force_scan(
        ascent.final_portfolio, UP_TO_THREE_NUMBER_EXCHANGES, _ASCENT_POOL, ascent_draws
    )
    assert ascent.local_optimum
    assert final.best_outcome_count <= ascent.final_outcome_count < ascent_space.total_outcomes


def test_ascent_stops_after_one_three_number_scan_without_a_strict_improvement(
    medium_space: ExactExchangeSpace, medium_draws: DrawMasks
) -> None:
    start = canonical_portfolio(
        [(1, 2, 5, 6, 9, 10), (3, 4, 7, 11, 12, 14)], pool_size=_MEDIUM_POOL, draw_size=6
    )
    ascent = exact_steepest_ascent(
        medium_space,
        start,
        exchange_sizes=UP_TO_THREE_NUMBER_EXCHANGES,
        first_scan_exchange_sizes=(3,),
        draws=medium_draws,
    )

    assert [scan.exchange_sizes for scan in ascent.scans] == [(3,)]
    assert ascent.accepted == ()
    assert ascent.local_optimum
    assert ascent.final_portfolio == start
    assert (
        ascent.final_outcome_count
        == ascent.initial_outcome_count
        == _pool_count(start, _MEDIUM_POOL, medium_draws)
    )


def test_ascent_aborts_when_the_canonical_recheck_of_an_accepted_move_disagrees(
    monkeypatch: pytest.MonkeyPatch, medium_space: ExactExchangeSpace, medium_draws: DrawMasks
) -> None:
    calls = 0

    def skewed(portfolio: Sequence[Sequence[int]], **kwargs: Any) -> ExactPortfolioProbability:
        nonlocal calls
        calls += 1
        exact = evaluate_portfolio(portfolio, **kwargs)
        if calls == 1:  # the starting portfolio's count stays honest
            return exact
        return dataclasses.replace(
            exact, official_any_prize_outcome_count=exact.official_any_prize_outcome_count + 1
        )

    monkeypatch.setattr(exchange_module, "evaluate_portfolio", skewed)
    with pytest.raises(ArithmeticError, match="canonical evaluator disagrees"):
        exact_steepest_ascent(
            medium_space,
            _MEDIUM_PORTFOLIO,
            exchange_sizes=UP_TO_THREE_NUMBER_EXCHANGES,
            first_scan_exchange_sizes=(3,),
            draws=medium_draws,
        )
    assert calls == 2


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


def test_run_v3_k20_three_exchange_search_reproduces_the_frozen_v3_local_optimum() -> None:
    result = cast("dict[str, Any]", run_v3_k20_three_exchange_search())

    checks = result["SCORER_PARITY_CHECKS"]
    assert result["SCORER_PARITY"] == "PASS"
    assert all(check["EXACT_MATCH"] for check in checks)
    assert len(checks) == result["SCORER_PARITY_CHECK_COUNT"] == 128
    assert sum(check["CHECK"].startswith("THREE_NUMBER_") for check in checks) == 80
    small = result["SMALL_LOTTERY_EXHAUSTIVE_EXCHANGE_PARITY"]
    assert small["CANDIDATES"] == small["EXACT_MATCHES"] == 9405
    assert small["DUPLICATE_TICKET_CANDIDATES"] == 2
    assert result["BASELINE"]["WINNING_OUTCOMES"] == BASELINE_WINNING_OUTCOMES == 312850818

    # One complete three-number scan of the unchanged baseline; no strict improvement, so
    # the ascent stops without a union scan.
    (scan,) = result["ITERATIONS"]
    assert scan["EXCHANGE_SIZES"] == [3]
    assert result["FIRST_THREE_EXCHANGE_SCAN_CANDIDATES"] == 20 * comb(6, 3) * comb(43, 3)
    assert scan["DISTINCT_CANDIDATE_PORTFOLIOS"] == scan["CANDIDATE_COUNT"] == 4936400
    assert result["TOTAL_DISTINCT_CANDIDATES_EVALUATED"] == 4936400
    assert scan["STRICTLY_IMPROVING_CANDIDATES"] == 0
    assert scan["BEST_NEIGHBOR_WINNING_OUTCOMES"] == 312835761 < BASELINE_WINNING_OUTCOMES
    assert scan["BEST_NEIGHBOR_TIE_COUNT"] == 1
    assert scan["BEST_NEIGHBOR_MOVE"] == {
        "TICKET_INDEX": 5,
        "EXCHANGE_SIZE": 3,
        "OLD_TICKET": [3, 13, 14, 28, 36, 44],
        "NEW_TICKET": [6, 14, 20, 36, 39, 44],
        "REMOVED_NUMBERS": [3, 13, 28],
        "INSERTED_NUMBERS": [6, 20, 39],
    }
    assert result["ACCEPTED_MOVES"] == []
    assert result["POST_MOVE_UNION_SCAN_CANDIDATES"] == []
    assert result["SEARCH_SPACE_COMPLETE"] == "YES"
    assert result["THREE_EXCHANGE_LOCAL_OPTIMUM"] == "YES"
    assert result["LEQ3_EXCHANGE_LOCAL_OPTIMUM"] == "YES"
    assert (
        result["LEQ3_EXCHANGE_LOCAL_OPTIMUM_BASIS"]
        == "THIS_RUN_COMPLETE_3_SCAN_PLUS_PRIOR_EXCHANGE_EVIDENCE_REUSED"
    )
    assert result["FINAL_PORTFOLIO_UNCHANGED_V3"] is True
    assert result["FINAL_WINNING_OUTCOMES"] == BASELINE_WINNING_OUTCOMES
    assert result["FINAL_EXACT_ANY_PRIZE"] == "7448829/14316764"
    assert result["CANONICAL_FINAL_VALIDATION"]["EXACT_AGREEMENT_WITH_SEARCH"] == "PASS"
    assert result["RESULT_LEAKAGE"] == "NONE"
