"""Deterministic simultaneous 2/3-ticket exchanges for exact B649 any-prize search.

An exchange replaces one number in each of two or three *distinct* tickets.
The added numbers need not come from another ticket, so the search is free to
leave the minimum-overlap face. Proposal generation may be heuristic, but a
move is accepted only after a full canonical OFFICIAL_ANY_PRIZE evaluation.
No local-optimum or exhaustive-neighborhood claim follows from a bounded scan.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from lottolab.research.b649_official_any_prize_exact import (
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]

POOL_SIZE = 49
DRAW_SIZE = 6
TICKET_COUNT = 20
OBJECTIVE = "OFFICIAL_ANY_PRIZE"


@dataclass(frozen=True, slots=True)
class ExchangeMove:
    """One simultaneous one-number replacement in each selected ticket."""

    slots: tuple[int, ...]
    removed: tuple[int, ...]
    added: tuple[int, ...]
    mode: str = "CALLER_PROPOSED"


@dataclass(frozen=True, slots=True)
class ScoredExchange:
    move: ExchangeMove
    portfolio: Portfolio
    score: ExactPortfolioProbability


@dataclass(frozen=True, slots=True)
class ExchangeScan:
    input_portfolio: Portfolio
    input_score: ExactPortfolioProbability
    candidates: tuple[ScoredExchange, ...]
    selected_portfolio: Portfolio
    selected_score: ExactPortfolioProbability
    selected_move: ExchangeMove | None
    strict_improvement: bool

    @property
    def delta(self) -> Fraction:
        return self.selected_score.official_any_prize - self.input_score.official_any_prize


def canonical_portfolio(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    ticket_count: int = TICKET_COUNT,
) -> Portfolio:
    """Validate and sort a fixed-size set of lottery tickets."""

    if not 1 <= draw_size < pool_size <= 64 or ticket_count < 2:
        raise ValueError("invalid lottery shape")
    if len(portfolio) != ticket_count:
        raise ValueError(f"expected exactly {ticket_count} tickets")
    tickets: list[Ticket] = []
    for ticket in portfolio:
        if (
            len(ticket) != draw_size
            or len(set(ticket)) != draw_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError(f"illegal ticket: {tuple(ticket)}")
        tickets.append(tuple(sorted(ticket)))
    if len(set(tickets)) != ticket_count:
        raise ValueError("portfolio contains duplicate tickets")
    return tuple(sorted(tickets))


def apply_exchange(
    portfolio: Portfolio,
    move: ExchangeMove,
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    ticket_count: int = TICKET_COUNT,
) -> Portfolio:
    """Apply a legal simultaneous exchange against the unchanged input state."""

    original = canonical_portfolio(
        portfolio, pool_size=pool_size, draw_size=draw_size, ticket_count=ticket_count
    )
    arity = len(move.slots)
    if (
        arity not in (2, 3)
        or arity > ticket_count
        or len(move.removed) != arity
        or len(move.added) != arity
        or tuple(sorted(set(move.slots))) != move.slots
        or any(type(slot) is not int or not 0 <= slot < ticket_count for slot in move.slots)
    ):
        raise ValueError("exchange must name two or three distinct ascending ticket slots")
    updated = list(original)
    for slot, removed, added in zip(move.slots, move.removed, move.added, strict=True):
        ticket = original[slot]
        if (
            type(removed) is not int
            or removed not in ticket
            or type(added) is not int
            or not 1 <= added <= pool_size
            or added in ticket
        ):
            raise ValueError("exchange has an illegal number replacement")
        updated[slot] = tuple(sorted((set(ticket) - {removed}) | {added}))
    return canonical_portfolio(
        updated, pool_size=pool_size, draw_size=draw_size, ticket_count=ticket_count
    )


def scan_exchanges(
    portfolio: Sequence[Sequence[int]],
    moves: Sequence[ExchangeMove],
    *,
    max_proposals: int,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    ticket_count: int = TICKET_COUNT,
    outright_matches: int = 3,
) -> ExchangeScan:
    """Exact-score a bounded proposal list and accept only a strict objective gain.

    Equal-score candidates use the lexicographically smallest full portfolio
    for deterministic selection. An equal score never displaces the incumbent.
    Duplicate endpoints and invalid proposals fail loudly.
    """

    if max_proposals < 1 or len(moves) > max_proposals:
        raise ValueError("proposal list exceeds the explicit positive budget")
    original = canonical_portfolio(
        portfolio, pool_size=pool_size, draw_size=draw_size, ticket_count=ticket_count
    )
    draws = all_main_draw_masks(pool_size, draw_size)

    def score(candidate: Portfolio) -> ExactPortfolioProbability:
        return evaluate_portfolio(
            candidate,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            draws=draws,
        )

    input_score = score(original)
    best_portfolio = original
    best_score = input_score
    best_move: ExchangeMove | None = None
    seen = {original}
    scored: list[ScoredExchange] = []
    for move in moves:
        candidate = apply_exchange(
            original,
            move,
            pool_size=pool_size,
            draw_size=draw_size,
            ticket_count=ticket_count,
        )
        if candidate in seen:
            raise ValueError("exchange proposals contain a repeated endpoint")
        seen.add(candidate)
        result = score(candidate)
        scored.append(ScoredExchange(move, candidate, result))
        candidate_q = result.official_any_prize
        best_q = best_score.official_any_prize
        if candidate_q > best_q or (
            candidate_q == best_q
            and candidate_q > input_score.official_any_prize
            and candidate < best_portfolio
        ):
            best_portfolio, best_score, best_move = candidate, result, move
    return ExchangeScan(
        input_portfolio=original,
        input_score=input_score,
        candidates=tuple(scored),
        selected_portfolio=best_portfolio,
        selected_score=best_score,
        selected_move=best_move,
        strict_improvement=best_move is not None,
    )


def frequency_profile(portfolio: Portfolio) -> dict[int, int]:
    counts = Counter(number for ticket in portfolio for number in ticket)
    return dict(sorted(Counter(counts.values()).items()))


def bounded_pilot_moves(
    portfolio: Portfolio,
    *,
    arity: int,
    seed: int = 20260923,
) -> tuple[ExchangeMove, ExchangeMove]:
    """Propose one legal frequency-preserving cycle and one external exchange.

    The deterministic strided slot traversal is a proposal policy only. It
    makes no claim to screen the full neighborhood or predict the objective.
    The external proposal must change the frequency profile of its input.
    """

    original = canonical_portfolio(portfolio)
    if arity not in (2, 3):
        raise ValueError("pilot supports only arity two or three")
    slot_sets = tuple(itertools.combinations(range(TICKET_COUNT), arity))
    profile = frequency_profile(original)
    selected: list[ExchangeMove] = []
    for mode in ("NUMBER_CYCLE", "EXTERNAL_SUBSTITUTION"):
        for attempt in range(len(slot_sets)):
            slots = slot_sets[(seed + 37 * attempt) % len(slot_sets)]
            removed = tuple(
                original[slot][(seed + attempt + index) % DRAW_SIZE]
                for index, slot in enumerate(slots)
            )
            if mode == "NUMBER_CYCLE":
                added = removed[1:] + removed[:1]
            else:
                added = tuple(
                    next(
                        number
                        for offset in range(POOL_SIZE)
                        if (number := (seed + 13 * attempt + 17 * index + offset) % POOL_SIZE + 1)
                        not in original[slot]
                    )
                    for index, slot in enumerate(slots)
                )
            move = ExchangeMove(slots, removed, added, mode)
            try:
                candidate = apply_exchange(original, move)
            except ValueError:
                continue
            if mode == "EXTERNAL_SUBSTITUTION" and frequency_profile(candidate) == profile:
                continue
            if any(apply_exchange(original, previous) == candidate for previous in selected):
                continue
            selected.append(move)
            break
        else:
            raise RuntimeError(f"no legal {mode} proposal found for arity {arity}")
    return selected[0], selected[1]


__all__ = [
    "ExchangeMove",
    "ExchangeScan",
    "ScoredExchange",
    "apply_exchange",
    "bounded_pilot_moves",
    "canonical_portfolio",
    "frequency_profile",
    "scan_exchanges",
]
