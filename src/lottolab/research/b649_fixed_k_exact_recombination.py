"""Greedy exact recombination of a caller-supplied BIG_LOTTO ticket pool.

Selection maximizes each next ticket's exact marginal OFFICIAL_ANY_PRIZE
outcome count within the supplied pool. The greedy result makes no claim about
tickets outside that pool or a full-domain optimum, and it uses no historical
outcomes or prediction model.

Two exact engines compute the same marginal gains. The delta engine reuses
ExactPortfolioDeltaEvaluator's cached per-ticket outcome bits across greedy
steps; the reference engine recomputes every candidate's draw hits at every
step and is kept as the parity oracle and as the bounded-memory fallback. Both
feed one shared greedy loop, so the selection and tie break cannot diverge.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import comb
from typing import Literal

import numpy as np

from lottolab.research.b649_official_any_prize_delta import (
    ExactPortfolioDeltaEvaluator,
    ticket_cache_bytes,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Engine = Literal["auto", "delta", "reference"]
type _GainsFor = Callable[[Sequence[Ticket], Sequence[Ticket]], Sequence[int]]

_DEFAULT_CHUNK_SIZE = 1 << 21
_DEFAULT_CACHE_BUDGET_BYTES = 1 << 30


@dataclass(frozen=True, slots=True)
class RecombinationTrace:
    """Selected tickets with each pick's exact marginal outcome-count gain."""

    selected: tuple[Ticket, ...]
    marginal_gains: tuple[int, ...]
    engine: Literal["delta", "reference"]


def _validate_space(
    *, pool_size: int, draw_size: int, outright_matches: int
) -> None:
    if type(pool_size) is not int or not 1 <= pool_size <= 64:
        raise ValueError("pool_size must be an integer in 1..64")
    if type(draw_size) is not int or not 1 <= draw_size < pool_size:
        raise ValueError("draw_size must be an integer in 1..pool_size-1")
    if type(outright_matches) is not int or not 1 <= outright_matches <= draw_size:
        raise ValueError("outright_matches must be an integer in 1..draw_size")


def _canonical_ticket(
    raw_ticket: Sequence[int], *, pool_size: int, draw_size: int
) -> Ticket:
    try:
        ticket = tuple(raw_ticket)
    except TypeError as exc:
        raise ValueError("each candidate ticket must be a sequence of integers") from exc
    if (
        len(ticket) != draw_size
        or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        or len(set(ticket)) != draw_size
    ):
        raise ValueError(f"illegal candidate ticket: {ticket}")
    return tuple(sorted(ticket))


def _marginal_outcome_gains(
    draws: DrawMasks,
    candidate_masks: Sequence[np.uint64],
    selected_masks: Sequence[np.uint64],
    *,
    special_count: int,
    outright_matches: int,
    chunk_size: int,
) -> list[int]:
    """Return exact added main-draw and special-ball outcome counts."""
    gains = [0] * len(candidate_masks)
    rescue_matches = outright_matches - 1

    for start in range(0, draws.size, chunk_size):
        chunk = draws[start : start + chunk_size]
        won = np.zeros(chunk.size, dtype=np.bool_)
        rescued = np.zeros(chunk.size, dtype=np.uint64)

        for selected_mask in selected_masks:
            hits = np.bitwise_count(chunk & selected_mask)
            won |= hits >= outright_matches
            rescued |= np.where(hits == rescue_matches, selected_mask, np.uint64(0))
        rescued &= ~chunk
        not_yet_won = ~won
        rescued_special_count = np.bitwise_count(rescued)

        for index, candidate_mask in enumerate(candidate_masks):
            hits = np.bitwise_count(chunk & candidate_mask)

            outright_rows = not_yet_won & (hits >= outright_matches)
            if np.any(outright_rows):
                gains[index] += int(
                    special_count * int(np.count_nonzero(outright_rows))
                    - np.sum(rescued_special_count[outright_rows], dtype=np.int64)
                )

            rescue_rows = not_yet_won & (hits == rescue_matches)
            if np.any(rescue_rows):
                new_specials = (candidate_mask & ~chunk) & ~rescued
                gains[index] += int(
                    np.sum(
                        np.bitwise_count(new_specials)[rescue_rows],
                        dtype=np.int64,
                    )
                )

    return gains


def _greedy_select(
    tickets: Sequence[Ticket], k: int, gains_for: _GainsFor
) -> tuple[tuple[Ticket, ...], tuple[int, ...]]:
    remaining = list(tickets)
    selected: list[Ticket] = []
    chosen_gains: list[int] = []

    for _ in range(k):
        gains = gains_for(selected, remaining)

        # remaining is sorted, so retaining the first equal-gain item is the
        # deterministic lexicographic tie break.
        best_index = 0
        for index in range(1, len(remaining)):
            if gains[index] > gains[best_index]:
                best_index = index
        chosen_gains.append(int(gains[best_index]))
        selected.append(remaining.pop(best_index))

    return tuple(selected), tuple(chosen_gains)


def trace_fixed_k_exact_recombination(
    candidate_pool: Sequence[Sequence[int]],
    k: int,
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
    draws: DrawMasks | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    engine: Engine = "auto",
    cache_budget_bytes: int = _DEFAULT_CACHE_BUDGET_BYTES,
) -> RecombinationTrace:
    """Greedily select exactly k distinct tickets and record each exact gain.

    Ticket number order is canonicalized and duplicate tickets are collapsed.
    Equal marginal gains use the lexicographically smaller ticket first. No
    overlap constraint is applied between selected tickets. A complete draw
    space may be supplied to reuse the result of all_main_draw_masks.

    engine "delta" caches every distinct candidate's packed outcome bits, about
    ticket_cache_bytes(C(pool_size, draw_size)) each, and reuses them across
    steps. engine "reference" caches nothing. engine "auto" uses "delta" only
    while that cache fits cache_budget_bytes. Every engine selects the same
    tickets with the same gains.
    """
    _validate_space(
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    if type(chunk_size) is not int or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    if engine not in ("auto", "delta", "reference"):
        raise ValueError('engine must be "auto", "delta" or "reference"')
    if type(cache_budget_bytes) is not int or cache_budget_bytes < 0:
        raise ValueError("cache_budget_bytes must be a non-negative integer")

    tickets = sorted(
        {
            _canonical_ticket(
                candidate,
                pool_size=pool_size,
                draw_size=draw_size,
            )
            for candidate in candidate_pool
        }
    )
    if k > len(tickets):
        raise ValueError(
            f"requested K{k} but only {len(tickets)} distinct legal candidates are available"
        )

    draw_masks = all_main_draw_masks(pool_size, draw_size) if draws is None else draws
    if draw_masks.size != comb(pool_size, draw_size):
        raise ValueError("draws must be the complete main-draw space")

    resolved: Literal["delta", "reference"]
    if engine == "auto":
        cache_bytes = len(tickets) * ticket_cache_bytes(int(draw_masks.size))
        resolved = "delta" if cache_bytes <= cache_budget_bytes else "reference"
    else:
        resolved = engine

    gains_for: _GainsFor
    if resolved == "delta":
        evaluator = ExactPortfolioDeltaEvaluator(
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            draws=draw_masks,
            chunk_size=chunk_size,
        )
        gains_for = evaluator.marginal_gains
    else:
        masks = {ticket: np.uint64(ticket_mask(ticket)) for ticket in tickets}
        special_count = pool_size - draw_size

        def recompute_gains(
            selected: Sequence[Ticket], remaining: Sequence[Ticket]
        ) -> Sequence[int]:
            return _marginal_outcome_gains(
                draw_masks,
                [masks[ticket] for ticket in remaining],
                [masks[ticket] for ticket in selected],
                special_count=special_count,
                outright_matches=outright_matches,
                chunk_size=chunk_size,
            )

        gains_for = recompute_gains

    selected, marginal_gains = _greedy_select(tickets, k, gains_for)
    return RecombinationTrace(
        selected=selected, marginal_gains=marginal_gains, engine=resolved
    )


def select_fixed_k_exact_recombination(
    candidate_pool: Sequence[Sequence[int]],
    k: int,
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
    draws: DrawMasks | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    engine: Engine = "auto",
    cache_budget_bytes: int = _DEFAULT_CACHE_BUDGET_BYTES,
) -> tuple[Ticket, ...]:
    """Greedily select exactly k distinct tickets from the supplied pool.

    See trace_fixed_k_exact_recombination for the selection rules and engines.
    """
    return trace_fixed_k_exact_recombination(
        candidate_pool,
        k,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=draws,
        chunk_size=chunk_size,
        engine=engine,
        cache_budget_bytes=cache_budget_bytes,
    ).selected
