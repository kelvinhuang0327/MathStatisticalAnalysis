"""Exact parity of delta-accelerated recombination against the reference engine."""

from __future__ import annotations

import itertools
import random
from collections.abc import Sequence

import numpy as np
import pytest

from lottolab.research.b649_fixed_k_exact_recombination import (
    RecombinationTrace,
    _marginal_outcome_gains,  # pyright: ignore[reportPrivateUsage]
    select_fixed_k_exact_recombination,
    trace_fixed_k_exact_recombination,
)
from lottolab.research.b649_official_any_prize_delta import (
    ExactPortfolioDeltaEvaluator,
    ticket_cache_bytes,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Domain = tuple[int, int, int]

# (pool_size, draw_size, outright_matches), including outright_matches == 1 where
# the special-ball rescue condition is "zero main matches".
DOMAINS: list[Domain] = [(6, 3, 3), (8, 3, 2), (7, 3, 1), (9, 4, 3)]
BIG_CHUNK = 1 << 21


def _all_tickets(domain: Domain) -> list[Ticket]:
    return list(itertools.combinations(range(1, domain[0] + 1), domain[1]))


def _ticket_wins(drawn: set[int], ticket: Sequence[int], special: int, outright: int) -> bool:
    hits = len(drawn.intersection(ticket))
    return hits >= outright or (hits == outright - 1 and special in ticket)


def _count(portfolio: Sequence[Sequence[int]], domain: Domain) -> int:
    """Independent brute-force OFFICIAL_ANY_PRIZE outcome count."""
    pool_size, draw_size, outright = domain
    winning = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        drawn = set(draw)
        for special in range(1, pool_size + 1):
            if special not in drawn and any(
                _ticket_wins(drawn, ticket, special, outright) for ticket in portfolio
            ):
                winning += 1
    return winning


def _brute_gains(
    selected: Sequence[Ticket], candidates: Sequence[Ticket], domain: Domain
) -> tuple[int, ...]:
    base = _count(selected, domain) if selected else 0
    return tuple(_count([*selected, ticket], domain) - base for ticket in candidates)


def _brute_greedy(
    pool: Sequence[Ticket], k: int, domain: Domain
) -> tuple[tuple[Ticket, ...], tuple[int, ...]]:
    remaining = sorted({tuple(sorted(ticket)) for ticket in pool})
    selected: list[Ticket] = []
    gains: list[int] = []
    current = 0
    for _ in range(k):
        options = [(_count([*selected, c], domain) - current, c) for c in remaining]
        gain, chosen = min(options, key=lambda option: (-option[0], option[1]))
        selected.append(chosen)
        gains.append(gain)
        current += gain
        remaining.remove(chosen)
    return tuple(selected), tuple(gains)


def _trace(
    pool: Sequence[Sequence[int]], k: int, domain: Domain, **options: object
) -> RecombinationTrace:
    pool_size, draw_size, outright = domain
    return trace_fixed_k_exact_recombination(
        pool,
        k,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright,
        **options,  # pyright: ignore[reportArgumentType]
    )


@pytest.mark.parametrize("domain", DOMAINS)
def test_delta_marginal_gains_equal_reference_and_brute_force(domain: Domain) -> None:
    pool_size, draw_size, outright = domain
    candidates = _all_tickets(domain)
    draws = all_main_draw_masks(pool_size, draw_size)
    rng = random.Random(649)
    prefixes = [[], *(rng.sample(candidates, size) for size in (1, 3, 6))]

    for selected in prefixes:
        expected = _brute_gains(selected, candidates, domain)
        for chunk_size in (1, 20, BIG_CHUNK):
            evaluator = ExactPortfolioDeltaEvaluator(
                pool_size=pool_size,
                draw_size=draw_size,
                outright_matches=outright,
                draws=draws,
                chunk_size=chunk_size,
            )
            reference = _marginal_outcome_gains(
                draws,
                [np.uint64(ticket_mask(ticket)) for ticket in candidates],
                [np.uint64(ticket_mask(ticket)) for ticket in selected],
                special_count=pool_size - draw_size,
                outright_matches=outright,
                chunk_size=chunk_size,
            )
            delta = evaluator.marginal_gains(selected, candidates)

            assert delta == tuple(reference) == expected
            if selected:
                base = evaluator.evaluate(selected).official_any_prize_outcome_count
                assert delta == tuple(
                    evaluator.add(selected, ticket).official_any_prize_outcome_count - base
                    for ticket in candidates
                )


@pytest.mark.parametrize("chunk_size", [3, BIG_CHUNK])
@pytest.mark.parametrize("domain", DOMAINS)
def test_engines_select_identical_tickets_and_marginal_trace(
    domain: Domain, chunk_size: int
) -> None:
    pool = _all_tickets(domain)
    k = 5
    expected_selected, expected_gains = _brute_greedy(pool, k, domain)

    delta = _trace(pool, k, domain, engine="delta", chunk_size=chunk_size)
    reference = _trace(pool, k, domain, engine="reference", chunk_size=chunk_size)

    assert (delta.engine, reference.engine) == ("delta", "reference")
    assert delta.selected == reference.selected == expected_selected
    assert delta.marginal_gains == reference.marginal_gains == expected_gains
    for size in range(1, k + 1):
        prefix = evaluate_portfolio(
            delta.selected[:size],
            pool_size=domain[0],
            draw_size=domain[1],
            outright_matches=domain[2],
        )
        assert prefix.official_any_prize_outcome_count == sum(delta.marginal_gains[:size])


def test_candidate_pool_order_invariance_holds_for_the_delta_engine() -> None:
    domain: Domain = (8, 3, 2)
    rng = random.Random(7)
    canonical = rng.sample(_all_tickets(domain), 20)
    baseline = _trace(canonical, 6, domain, engine="delta", chunk_size=9)
    reference = _trace(canonical, 6, domain, engine="reference", chunk_size=9)
    assert baseline.selected == reference.selected
    assert baseline.marginal_gains == reference.marginal_gains

    for _ in range(5):
        shuffled = [tuple(rng.sample(ticket, len(ticket))) for ticket in canonical]
        shuffled += shuffled[:3]  # duplicates collapse to the same canonical ticket
        rng.shuffle(shuffled)
        for engine in ("delta", "reference"):
            trace = _trace(shuffled, 6, domain, engine=engine, chunk_size=9)
            assert trace.selected == baseline.selected
            assert trace.marginal_gains == baseline.marginal_gains


def test_special_ball_rescue_ranking_matches_between_engines() -> None:
    domain: Domain = (6, 3, 3)
    first: Ticket = (1, 2, 3)
    lower: Ticket = (1, 2, 4)
    higher: Ticket = (1, 4, 5)
    base_main = evaluate_portfolio(
        [first], pool_size=6, draw_size=3, outright_matches=3
    ).m3_plus_draw_count
    main_only = [
        evaluate_portfolio(
            [first, ticket], pool_size=6, draw_size=3, outright_matches=3
        ).m3_plus_draw_count
        - base_main
        for ticket in (lower, higher)
    ]
    evaluator = ExactPortfolioDeltaEvaluator(pool_size=6, draw_size=3, outright_matches=3)

    assert main_only[0] == main_only[1]  # only the special-ball rescue separates them
    assert evaluator.marginal_gains([first], [lower, higher]) == (8, 12)
    for engine in ("delta", "reference"):
        trace = _trace([first, lower, higher], 2, domain, engine=engine, chunk_size=4)
        assert trace.selected == (first, higher)
        assert trace.marginal_gains[1] == 12


def test_zero_marginal_candidates_and_ties_match_between_engines() -> None:
    domain: Domain = (4, 3, 1)
    pool = _all_tickets(domain)
    delta = _trace(pool, 4, domain, engine="delta", chunk_size=2)
    reference = _trace(pool, 4, domain, engine="reference", chunk_size=2)

    assert delta.selected == reference.selected == tuple(pool)
    assert delta.marginal_gains == reference.marginal_gains == (4, 0, 0, 0)


def test_engine_auto_falls_back_when_the_cache_exceeds_the_budget() -> None:
    domain: Domain = (8, 3, 2)
    pool = _all_tickets(domain)[:10]
    needed = len(pool) * ticket_cache_bytes(len(all_main_draw_masks(8, 3)))

    assert _trace(pool, 3, domain).engine == "delta"
    assert _trace(pool, 3, domain, cache_budget_bytes=needed).engine == "delta"
    assert _trace(pool, 3, domain, cache_budget_bytes=needed - 1).engine == "reference"
    fallback = _trace(pool, 3, domain, cache_budget_bytes=0)
    assert fallback.engine == "reference"
    assert fallback.selected == _trace(pool, 3, domain, engine="delta").selected
    assert select_fixed_k_exact_recombination(
        pool, 3, pool_size=8, draw_size=3, outright_matches=2
    ) == fallback.selected


def test_cache_byte_accounting_matches_the_real_cache() -> None:
    evaluator = ExactPortfolioDeltaEvaluator(pool_size=9, draw_size=4, outright_matches=3)
    evaluator.marginal_gains([(1, 2, 3, 4)], [(1, 2, 3, 5), (5, 6, 7, 8)])
    cached = evaluator._ticket_outcomes  # pyright: ignore[reportPrivateUsage]

    assert evaluator.cached_ticket_count == len(cached) == 3
    for wins, rescues in cached.values():
        assert wins.nbytes + rescues.nbytes == evaluator.cache_bytes_per_ticket
    assert ticket_cache_bytes(13_983_816) == 3_495_954


def test_marginal_gains_edge_cases_and_cache_reuse() -> None:
    evaluator = ExactPortfolioDeltaEvaluator(pool_size=8, draw_size=3, outright_matches=2)
    ticket = (1, 2, 3)

    assert evaluator.marginal_gains([ticket], []) == ()
    assert evaluator.marginal_gains([], [ticket]) == (
        evaluator.evaluate([ticket]).official_any_prize_outcome_count,
    )
    assert evaluator.marginal_gains([ticket], [ticket, (3, 2, 1)]) == (0, 0)

    before = evaluator.cached_ticket_count
    evaluator.marginal_gains([ticket], [(1, 2, 4), (4, 5, 6)])
    after_first = evaluator.cached_ticket_count
    evaluator.marginal_gains([ticket], [(1, 2, 4), (4, 5, 6)])
    assert (before, after_first, evaluator.cached_ticket_count) == (1, 3, 3)

    for bad in ((1, 2), (1, 1, 2), (0, 2, 3), (1, 2, 9), (True, 2, 3)):
        with pytest.raises(ValueError, match="illegal ticket"):
            evaluator.marginal_gains([ticket], [bad])
        with pytest.raises(ValueError, match="illegal ticket"):
            evaluator.marginal_gains([bad], [ticket])


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"engine": "fast"}, "engine must be"),
        ({"cache_budget_bytes": -1}, "cache_budget_bytes"),
        ({"cache_budget_bytes": True}, "cache_budget_bytes"),
        ({"cache_budget_bytes": 1.5}, "cache_budget_bytes"),
    ],
)
def test_rejects_invalid_engine_options(options: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _trace([(1, 2, 3)], 1, (6, 3, 3), **options)
