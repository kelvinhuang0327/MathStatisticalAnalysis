"""Exact single-ticket number-exchange steepest ascent for the sealed B649 K20 portfolio.

One scan enumerates the complete single-ticket exchange neighborhood of a portfolio --
for each ticket remove exactly ``e`` of its numbers and insert exactly ``e`` of the
numbers it lacks, every other ticket unchanged, for every ``e`` in the scan's exchange
sizes (``20 * C(6, 2) * C(43, 2) = 270900`` candidates for the K20 two-number exchange,
``20 * C(6, 3) * C(43, 3) = 4936400`` for the three-number exchange, 5212460 for the
1-, 2- and 3-number union) -- and scores every candidate on exact OFFICIAL_ANY_PRIZE over
the complete fair-draw outcome space. The ascent accepts the single best strict
improvement (ties: lexicographically smallest canonical portfolio) and rescans until one
complete scan finds none.

Exact delta scoring
-------------------
A ticket ``t`` wins outcome ``(D, s)`` iff ``|t & (D | {s})| >= r`` (``r`` outright
matches): ``|t & D| >= r`` wins outright, and at ``|t & D| == r - 1`` the special
supplies the missing common number exactly when ``s in t`` (the 柒獎 rescue). An
outcome's status therefore depends only on the ``(d + 1)``-set ``E = D | {s}``, and
every such ``E`` is exactly ``d + 1`` outcomes (choose which member is the special).

Fix ticket ``i`` and let ``u(B)`` count the specials that the *other* tickets still
lose on main draw ``B`` -- the canonical evaluator's per-draw quantity, equal to the
number of uncovered ``E`` containing ``B``. Replacing ticket ``i`` by ``t'`` wins what
the others win plus every uncovered ``E`` with ``|E & t'| >= r``. Summing ``u(B)``
with weight ``w(|B & t'|)`` counts those ``E`` exactly when
``m * w(m - 1) + (d + 1 - m) * w(m) == [m >= r]`` for every ``m``, because ``E`` has
``m`` six-subsets ``B`` with ``|B & t'| = m - 1`` and ``d + 1 - m`` with ``m``. For
B649 that forces ``w(3) = 1/4, w(4) = 0, w(5) = 1/2, w(6) = -2``. Through the superset
marginals ``V_k(A) = sum_{B >= A} u(B)`` -- exact integer down-projections of ``u`` --
the newly won ``E`` count is ``(T3 - 4 T4 + 12 T5 - 40 T6) / 4`` with ``T_k`` the sum
of ``V_k`` over the ``k``-subsets of ``t'``: 42 table lookups per candidate instead of
a full 601,304,088-outcome evaluation. Nothing here depends on how ``t'`` relates to the
ticket it replaces, so one scorer serves every exchange size. Arithmetic is int64
throughout, every division is checked to be exact, and every accepted portfolio is
re-scored by ``lottolab.research.b649_official_any_prize_exact.evaluate_portfolio``.

No historical draw, prediction stream, or live result is read: the only inputs are
the sealed portfolio and the combinatorial outcome space.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from math import comb, lcm
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_METHOD_ID,
    SEALED_GEOMETRY_METHOD_VERSION,
    SEALED_GEOMETRY_PORTFOLIOS,
    SealedGeometryPortfolio,
    canonical_portfolio_sha256,
    verify_sealed_geometry_portfolio,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type TicketRows = npt.NDArray[np.int64]
type OutcomeCounts = npt.NDArray[np.int64]

TWO_EXCHANGE_TASK_ID: Final = "B649_V3_K20_EXACT_TWO_NUMBER_EXCHANGE_SEARCH_R1"
THREE_EXCHANGE_TASK_ID: Final = "B649_V3_K20_EXACT_THREE_NUMBER_EXCHANGE_SEARCH_R1"
TWO_NUMBER_EXCHANGE: Final = 2
THREE_NUMBER_EXCHANGE: Final = 3
UP_TO_THREE_NUMBER_EXCHANGES: Final = (1, 2, 3)
BASELINE_TICKET_COUNT: Final = 20
BASELINE_METHOD_VERSION: Final = "3.0.0"
BASELINE_PORTFOLIO_SHA256: Final = (
    "242a04c1236f53d74a939f24495868287a4ad63d63b20903fc91d5987b14a9bd"
)
BASELINE_WINNING_OUTCOMES: Final = 312850818
# The known v2 -> v3 one-number move recorded by the sealed-v2 direct OFFICIAL_ANY_PRIZE
# terminal authority (docs/research/matrix-native-results/
# b649-sealed-v2-direct-official-any-prize-k20-terminal-r1.json).
KNOWN_V2_TICKET: Final = (3, 13, 14, 20, 36, 44)
KNOWN_V3_TICKET: Final = (3, 13, 14, 28, 36, 44)
KNOWN_V2_WINNING_OUTCOMES: Final = 312838750
# Complete-neighborhood evidence for the unchanged v3 baseline that the three-number search
# reuses instead of re-running: the terminal authority above certifies the one-number local
# optimum, and this module's two-number search (commit 75fa570) scanned all 270900
# two-number candidates without a strict improvement.
PRIOR_ONE_EXCHANGE_EVIDENCE: Final = (
    "docs/research/matrix-native-results/"
    "b649-sealed-v2-direct-official-any-prize-k20-terminal-r1.json"
    "#TERMINAL_ONE_NUMBER_EXCHANGE_LOCAL_OPTIMUM"
)
PRIOR_TWO_EXCHANGE_EVIDENCE: Final = (
    "B649_V3_K20_EXACT_TWO_NUMBER_EXCHANGE_SEARCH_R1@75fa570bf4fc616a02722cbade6eb500f959a9c7"
)
_THREE_EXCHANGE_PARITY_SEED: Final = 20260926
_THREE_EXCHANGE_SPREAD_INDICES: Final = (0, 4, 9, 14, 19)
# BIG_LOTTO's recursion depth (draw 6, outright 3) on a 16-number pool: small enough to check
# all 9405 <=3-number exchange candidates of this portfolio against the canonical evaluator,
# yet far from covering every outcome (a 12-number pool saturates at three or four tickets,
# so nearly every candidate would score the same). Its first two tickets share three
# numbers, so the enumeration includes duplicate-ticket candidates.
_SMALL_PARITY_SHAPE: Final = (16, 6, 3)
_SMALL_PARITY_PORTFOLIO: Final = (
    (1, 2, 3, 4, 5, 6),
    (4, 5, 6, 7, 8, 9),
    (1, 7, 10, 12, 14, 16),
)
_DEFAULT_CHUNK_SIZE: Final = 1 << 21
_INT32_MAX: Final = int(np.iinfo(np.int32).max)


def draw_weight_coefficients(draw_size: int, outright_matches: int) -> tuple[dict[int, int], int]:
    """Integers ``C_k`` and ``L`` with ``newly won (d + 1)-sets = sum_k C_k T_k / L``.

    ``w`` solves ``m w(m - 1) + (d + 1 - m) w(m) = [m >= r]``; ``C_k / L`` re-expresses
    ``sum_m w(m) S_m`` (``S_m`` = draws meeting the ticket in exactly ``m`` numbers)
    through the superset sums ``T_k = sum_m C(m, k) S_m``.
    """

    if not 1 <= outright_matches <= draw_size:
        raise ValueError("outright_matches must be within 1..draw_size")
    weights = [Fraction(0)] * (draw_size + 1)
    weights[outright_matches] = Fraction(1, draw_size + 1 - outright_matches)
    for matches in range(outright_matches + 1, draw_size + 1):
        weights[matches] = (1 - matches * weights[matches - 1]) / (draw_size + 1 - matches)
    exact = {
        size: sum(
            (
                weights[matches] * (-1) ** (size - matches) * comb(size, matches)
                for matches in range(outright_matches, size + 1)
            ),
            Fraction(0),
        )
        for size in range(outright_matches, draw_size + 1)
    }
    denominator = lcm(*(coefficient.denominator for coefficient in exact.values()))
    return {size: int(value * denominator) for size, value in exact.items()}, denominator


def _colex_levels(pool_size: int, largest: int) -> list[npt.NDArray[np.uint8]]:
    """``levels[k]``: every ``k``-subset of ``0..pool_size-1`` as sorted rows, colex order.

    Row ``j`` of level ``k`` has colex rank ``j = sum_p C(row[p], p + 1)``: the
    ``k``-sets with largest element ``m`` are the ``(k - 1)``-subsets of ``0..m-1``
    (the first ``C(m, k - 1)`` rows of the previous level) with ``m`` appended.
    """

    levels = [np.zeros((1, 0), dtype=np.uint8)]
    for size in range(1, largest + 1):
        previous = levels[-1]
        blocks = [
            np.hstack(
                (
                    previous[: comb(top, size - 1)],
                    np.full((comb(top, size - 1), 1), top, dtype=np.uint8),
                )
            )
            for top in range(size - 1, pool_size)
        ]
        levels.append(np.concatenate(blocks))
    return levels


def _row_masks(rows: npt.NDArray[np.uint8]) -> DrawMasks:
    masks = np.zeros(rows.shape[0], dtype=np.uint64)
    for column in range(rows.shape[1]):
        masks |= np.left_shift(np.uint64(1), rows[:, column].astype(np.uint64))
    return masks


def _superset_ranks(
    rows: npt.NDArray[np.uint8], pool_size: int, binomial: npt.NDArray[np.int64]
) -> npt.NDArray[np.int32]:
    """``table[a, j]``: colex rank of ``A | {z}`` for the ``j``-th number ``z`` not in ``A``.

    With ``q`` members of ``A`` below ``z`` the sorted superset is
    ``a_0 .. a_{q-1}, z, a_q ..``, so its rank is ``sum_{p<q} C(a_p, p + 1) + C(z, q + 1)
    + sum_{p>=q} C(a_p, p + 2)``, and ``z`` is the ``(z - q)``-th non-member.
    """

    count, size = rows.shape
    elements = rows.astype(np.intp)
    prefix = np.zeros((count, size + 1), dtype=np.int64)
    for position in range(size):
        prefix[:, position + 1] = (
            prefix[:, position] + binomial[elements[:, position], position + 1]
        )
    suffix = np.zeros((count, size + 1), dtype=np.int64)
    for position in range(size - 1, -1, -1):
        suffix[:, position] = (
            suffix[:, position + 1] + binomial[elements[:, position], position + 2]
        )
    table = np.empty((count, pool_size - size), dtype=np.int32)
    below = np.zeros(count, dtype=np.intp)
    for number in range(pool_size):
        member = (elements == number).any(axis=1)
        outside = np.flatnonzero(~member)
        before = below[outside]
        table[outside, number - before] = (
            prefix[outside, before] + binomial[number, before + 1] + suffix[outside, before]
        )
        below += member
    return table


def _uncovered_specials(
    draws: DrawMasks,
    masks: Sequence[np.uint64],
    *,
    outright_matches: int,
    special_count: int,
    chunk_size: int,
) -> npt.NDArray[np.uint8]:
    """Per main draw, the specials on which no ticket in ``masks`` wins any prize.

    Same rule as ``evaluate_portfolio``: 0 once some ticket reaches ``outright_matches``,
    otherwise the specials outside every ``outright_matches - 1``-hit ticket.
    """

    uncovered = np.empty(draws.size, dtype=np.uint8)
    zero = np.uint64(0)
    specials = np.uint8(special_count)
    rescue_matches = outright_matches - 1
    for start in range(0, draws.size, chunk_size):
        chunk = draws[start : start + chunk_size]
        won = np.zeros(chunk.size, dtype=np.bool_)
        rescue = np.zeros(chunk.size, dtype=np.uint64)
        for mask in masks:
            hits = np.bitwise_count(chunk & mask)
            won |= hits >= outright_matches
            rescue |= np.where(hits == rescue_matches, mask, zero)
        rescue &= ~chunk
        block = specials - np.bitwise_count(rescue)
        block[won] = 0
        uncovered[start : start + chunk.size] = block
    return uncovered


def _legal_tickets(
    portfolio: Sequence[Sequence[int]], *, pool_size: int, draw_size: int
) -> tuple[Ticket, ...]:
    """Sorted tickets in input order; repeated tickets are legal (and inert)."""

    tickets: list[Ticket] = []
    for ticket in portfolio:
        if (
            len(ticket) != draw_size
            or len(set(ticket)) != draw_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError(f"illegal ticket: {tuple(ticket)}")
        tickets.append(tuple(sorted(ticket)))
    if not tickets:
        raise ValueError("portfolio must contain at least one ticket")
    return tuple(tickets)


def canonical_portfolio(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
) -> Portfolio:
    """Canonical lexical representation: sorted tickets, tickets in ascending order."""

    return tuple(sorted(_legal_tickets(portfolio, pool_size=pool_size, draw_size=draw_size)))


@dataclass(frozen=True, slots=True, eq=False)
class PortfolioCoverage:
    """One portfolio's per-draw losing-special counts, in the space's colex draw order."""

    tickets: tuple[Ticket, ...]
    masks: tuple[np.uint64, ...]
    uncovered: npt.NDArray[np.uint8]
    outcome_count: int


@dataclass(frozen=True, slots=True, eq=False)
class ReplacementScorer:
    """Exact marginals for replacing ticket ``index`` of a portfolio by any ticket."""

    index: int
    uncovered: npt.NDArray[np.uint8]
    marginals: Mapping[int, npt.NDArray[np.int64]]
    others_outcome_count: int


class ExactExchangeSpace:
    """Colex-ranked main-draw space plus exact superset tables for one lottery shape.

    Generic over ``(pool_size, draw_size, outright_matches)`` exactly like
    ``evaluate_portfolio``, so small lotteries can be checked against it exhaustively.
    """

    def __init__(
        self,
        *,
        pool_size: int = BIG_LOTTO_POOL_SIZE,
        draw_size: int = BIG_LOTTO_DRAW_SIZE,
        outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> None:
        if not 1 <= outright_matches <= draw_size < pool_size <= 64:
            raise ValueError(
                "space must satisfy 1 <= outright_matches <= draw_size < pool_size <= 64"
            )
        if max(comb(pool_size, size) for size in range(outright_matches, draw_size + 1)) > (
            _INT32_MAX
        ):
            raise ValueError("draw space is too large for int32 rank tables")
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        self.pool_size = pool_size
        self.draw_size = draw_size
        self.outright_matches = outright_matches
        self.special_count = pool_size - draw_size
        self.total_outcomes = comb(pool_size, draw_size) * self.special_count
        self.coefficients, self.denominator = draw_weight_coefficients(draw_size, outright_matches)
        self._chunk_size = chunk_size
        self._binomial = np.array(
            [
                [comb(number, size) for size in range(draw_size + 2)]
                for number in range(pool_size + 1)
            ],
            dtype=np.int64,
        )
        levels = _colex_levels(pool_size, draw_size)
        self.draw_masks: DrawMasks = _row_masks(levels[draw_size])
        self._supersets = {
            size: _superset_ranks(levels[size], pool_size, self._binomial)
            for size in range(outright_matches, draw_size)
        }
        self._positions = {
            size: tuple(itertools.combinations(range(draw_size), size))
            for size in self.coefficients
        }

    def ticket_rows(self, tickets: npt.ArrayLike) -> TicketRows:
        """0-based rows for candidate tickets given as strictly increasing numbers."""

        rows = np.asarray(tickets, dtype=np.int64)
        if rows.ndim != 2 or rows.shape[1] != self.draw_size:
            raise ValueError(f"candidates must be an (n, {self.draw_size}) array of tickets")
        if rows.size and (
            int(rows.min()) < 1
            or int(rows.max()) > self.pool_size
            or not bool((np.diff(rows, axis=1) > 0).all())
        ):
            raise ValueError("candidate tickets must be strictly increasing numbers in the pool")
        return rows - 1

    def _ranks(self, rows: TicketRows, positions: Sequence[int]) -> npt.NDArray[np.int64]:
        ranks = np.zeros(rows.shape[0], dtype=np.int64)
        for order, column in enumerate(positions):
            ranks += self._binomial[rows[:, column], order + 1]
        return ranks

    def ticket_ranks(self, tickets: npt.ArrayLike) -> npt.NDArray[np.int64]:
        """Colex rank of each ticket in the main-draw space (its identity key)."""

        return self._ranks(self.ticket_rows(tickets), range(self.draw_size))

    def coverage(self, portfolio: Sequence[Sequence[int]]) -> PortfolioCoverage:
        """Exact per-draw coverage of ``portfolio`` (tickets kept in input order)."""

        tickets = _legal_tickets(portfolio, pool_size=self.pool_size, draw_size=self.draw_size)
        masks = tuple(np.uint64(ticket_mask(ticket)) for ticket in tickets)
        uncovered = _uncovered_specials(
            self.draw_masks,
            masks,
            outright_matches=self.outright_matches,
            special_count=self.special_count,
            chunk_size=self._chunk_size,
        )
        return PortfolioCoverage(
            tickets=tickets,
            masks=masks,
            uncovered=uncovered,
            outcome_count=self.total_outcomes - int(uncovered.sum(dtype=np.int64)),
        )

    def replacement_scorer(self, coverage: PortfolioCoverage, index: int) -> ReplacementScorer:
        """Marginals of the portfolio without ticket ``index``, ready for any replacement."""

        if not 0 <= index < len(coverage.masks):
            raise IndexError(f"ticket index {index} is outside the portfolio")
        others = coverage.masks[:index] + coverage.masks[index + 1 :]
        uncovered = coverage.uncovered.copy()
        # A ticket with fewer than outright_matches - 1 hits on a draw neither wins it nor
        # rescues a special there, so removing it changes only the draws it touches.
        touched = np.flatnonzero(
            np.bitwise_count(self.draw_masks & coverage.masks[index]) >= self.outright_matches - 1
        )
        uncovered[touched] = _uncovered_specials(
            self.draw_masks[touched],
            others,
            outright_matches=self.outright_matches,
            special_count=self.special_count,
            chunk_size=self._chunk_size,
        )
        marginals: dict[int, npt.NDArray[np.int64]] = {}
        for size in range(self.draw_size - 1, self.outright_matches - 1, -1):
            superset = self._supersets[size]
            if size == self.draw_size - 1:
                sums = uncovered[superset].sum(axis=1, dtype=np.int64)
            else:
                sums = marginals[size + 1][superset].sum(axis=1, dtype=np.int64)
            # sum_z V_{k+1}(A | {z}) counts each draw B >= A exactly d - k times.
            quotient, remainder = np.divmod(sums, self.draw_size - size)
            if remainder.any():
                raise ArithmeticError(f"superset marginal V_{size} is not an exact integer")
            marginals[size] = quotient
        return ReplacementScorer(
            index=index,
            uncovered=uncovered,
            marginals=marginals,
            others_outcome_count=self.total_outcomes - int(uncovered.sum(dtype=np.int64)),
        )

    def replacement_outcome_counts(
        self, scorer: ReplacementScorer, candidates: npt.ArrayLike
    ) -> OutcomeCounts:
        """Exact OFFICIAL_ANY_PRIZE outcome count with ticket ``scorer.index`` replaced."""

        rows = self.ticket_rows(candidates)
        numerator = np.zeros(rows.shape[0], dtype=np.int64)
        for size, coefficient in self.coefficients.items():
            if coefficient == 0:
                continue
            total = np.zeros(rows.shape[0], dtype=np.int64)
            for positions in self._positions[size]:
                ranks = self._ranks(rows, positions)
                if size == self.draw_size:
                    total += scorer.uncovered[ranks]
                else:
                    total += scorer.marginals[size][ranks]
            numerator += coefficient * total
        newly_won, remainder = np.divmod(numerator, self.denominator)
        if remainder.any():
            raise ArithmeticError("replacement gain is not an exact integer")
        return scorer.others_outcome_count + (self.draw_size + 1) * newly_won


@dataclass(frozen=True, slots=True, eq=False)
class ExchangeNeighborhood:
    """Every ticket that keeps all but ``exchange_size`` numbers of ``ticket``.

    Row ``j`` removes ``removed[j // len(inserted)]`` and inserts
    ``inserted[j % len(inserted)]`` (both in lexicographic order).
    """

    ticket: Ticket
    removed: tuple[Ticket, ...]
    inserted: tuple[Ticket, ...]
    rows: TicketRows

    def move(self, row: int) -> tuple[Ticket, Ticket, Ticket]:
        """``(removed numbers, inserted numbers, new ticket)`` of candidate ``row``."""

        removed = self.removed[row // len(self.inserted)]
        inserted = self.inserted[row % len(self.inserted)]
        return removed, inserted, tuple(int(number) for number in self.rows[row])


def exchange_neighborhood(
    ticket: Sequence[int],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    exchange_size: int = TWO_NUMBER_EXCHANGE,
) -> ExchangeNeighborhood:
    """Complete ``exchange_size``-number exchange neighborhood of one ticket."""

    current = tuple(sorted(ticket))
    if len(set(current)) != len(current) or any(
        type(number) is not int or not 1 <= number <= pool_size for number in current
    ):
        raise ValueError(f"illegal ticket: {tuple(ticket)}")
    outside = tuple(number for number in range(1, pool_size + 1) if number not in current)
    if not 1 <= exchange_size <= min(len(current), len(outside)):
        raise ValueError("exchange_size must be within 1..min(ticket size, numbers outside)")
    removed = tuple(itertools.combinations(current, exchange_size))
    inserted = tuple(itertools.combinations(outside, exchange_size))
    kept = np.array(
        [[number for number in current if number not in pair] for pair in removed],
        dtype=np.int64,
    ).reshape(len(removed), len(current) - exchange_size)
    added = np.array(inserted, dtype=np.int64).reshape(len(inserted), exchange_size)
    rows = np.sort(
        np.concatenate(
            (np.repeat(kept, len(inserted), axis=0), np.tile(added, (len(removed), 1))), axis=1
        ),
        axis=1,
    )
    return ExchangeNeighborhood(ticket=current, removed=removed, inserted=inserted, rows=rows)


@dataclass(frozen=True, slots=True)
class ExchangeMove:
    """One accepted-or-candidate single-ticket exchange."""

    ticket_index: int
    old_ticket: Ticket
    new_ticket: Ticket
    removed_numbers: Ticket
    inserted_numbers: Ticket

    @property
    def exchange_size(self) -> int:
        """How many numbers of the old ticket the move replaces."""

        return len(self.removed_numbers)


def _exchange_move(index: int, ticket: Ticket, new_ticket: Ticket) -> ExchangeMove:
    return ExchangeMove(
        ticket_index=index,
        old_ticket=ticket,
        new_ticket=new_ticket,
        removed_numbers=tuple(number for number in ticket if number not in new_ticket),
        inserted_numbers=tuple(number for number in new_ticket if number not in ticket),
    )


@dataclass(frozen=True, slots=True)
class TicketNeighborhoodBest:
    """Exact best exchange of one ticket (ties: smallest canonical portfolio)."""

    ticket_index: int
    ticket: Ticket
    candidate_count: int
    duplicate_ticket_candidate_count: int
    improving_candidate_count: int
    best_outcome_count: int
    best_tie_count: int
    best_move: ExchangeMove
    best_portfolio: Portfolio


@dataclass(frozen=True, slots=True)
class NeighborhoodScan:
    """One complete exact scan of a portfolio's single-ticket exchange neighborhood.

    The ``*_by_size`` counts are aligned with ``exchange_sizes``.
    """

    portfolio: Portfolio
    outcome_count: int
    exchange_sizes: tuple[int, ...]
    candidate_count: int
    candidate_count_by_size: tuple[int, ...]
    distinct_portfolio_count: int
    duplicate_ticket_candidate_count: int
    improving_candidate_count: int
    improving_candidate_count_by_size: tuple[int, ...]
    best_outcome_count: int
    best_tie_count: int
    best_move: ExchangeMove
    best_portfolio: Portfolio
    per_ticket: tuple[TicketNeighborhoodBest, ...]


def _exchange_sizes(exchange_sizes: Sequence[int]) -> tuple[int, ...]:
    sizes = tuple(sorted(set(exchange_sizes)))
    if not sizes or len(sizes) != len(exchange_sizes):
        raise ValueError("exchange_sizes must be a non-empty collection of distinct sizes")
    return sizes


def scan_exchange_neighborhood(
    space: ExactExchangeSpace,
    portfolio: Sequence[Sequence[int]],
    *,
    exchange_sizes: Sequence[int] = (TWO_NUMBER_EXCHANGE,),
) -> NeighborhoodScan:
    """Exact-score every candidate of the complete single-ticket exchange neighborhood.

    The neighborhood is the union over ``exchange_sizes``; a size-``e`` candidate keeps
    exactly ``draw_size - e`` numbers of the ticket it replaces, so the sizes never overlap.
    A candidate that would repeat another ticket of the portfolio is scored but is not
    eligible (a sealed portfolio's tickets are distinct); it can never improve anyway,
    since everything it covers is already covered by the ticket it repeats.

    Replacing ticket ``t`` of portfolio ``P`` by ``t' != t`` gives the multiset
    ``P - {t} + {t'}``, whose differences from ``P`` are exactly ``{t}`` and ``{t'}``. The
    colex-rank pair of ``(t, t')`` is therefore a canonical key of the resulting portfolio,
    so candidates are deduplicated without materializing whole portfolios.
    """

    sizes = _exchange_sizes(exchange_sizes)
    tickets = canonical_portfolio(portfolio, pool_size=space.pool_size, draw_size=space.draw_size)
    if len(set(tickets)) != len(tickets):
        raise ValueError("portfolio tickets must be distinct")
    coverage = space.coverage(tickets)
    current = coverage.outcome_count
    ticket_ranks = space.ticket_ranks(tickets)
    ticket_space = comb(space.pool_size, space.draw_size)
    per_ticket: list[TicketNeighborhoodBest] = []
    portfolio_keys: list[npt.NDArray[np.int64]] = []
    candidates_by_size = [0] * len(sizes)
    improving_by_size = [0] * len(sizes)
    for index, ticket in enumerate(tickets):
        scorer = space.replacement_scorer(coverage, index)
        if int(space.replacement_outcome_counts(scorer, [ticket])[0]) != current:
            raise ArithmeticError(f"re-inserting ticket {index} does not reproduce the portfolio")
        blocks = [
            exchange_neighborhood(ticket, pool_size=space.pool_size, exchange_size=size).rows
            for size in sizes
        ]
        rows = np.concatenate(blocks)
        counts = space.replacement_outcome_counts(scorer, rows)
        ranks = space.ticket_ranks(rows)
        if np.unique(ranks).size != ranks.size or bool((ranks == ticket_ranks[index]).any()):
            raise AssertionError("exchange neighborhood produced a repeated or unchanged ticket")
        other_ranks = np.delete(ticket_ranks, index)
        duplicate = np.isin(ranks, other_ranks)
        eligible = np.where(duplicate, -1, counts)
        best_count = int(eligible.max())
        if best_count < 0:
            raise ValueError(f"ticket {index} has no eligible exchange candidate")
        improving = eligible > current
        start = 0
        for position, block in enumerate(blocks):
            stop = start + block.shape[0]
            candidates_by_size[position] += block.shape[0]
            improving_by_size[position] += int(np.count_nonzero(improving[start:stop]))
            start = stop
        others = tickets[:index] + tickets[index + 1 :]
        tied: list[tuple[Portfolio, Ticket]] = []
        for row in np.flatnonzero(eligible == best_count).tolist():
            new_ticket = tuple(int(number) for number in rows[row])
            tied.append((tuple(sorted((*others, new_ticket))), new_ticket))
        best_portfolio, new_ticket = min(tied)
        per_ticket.append(
            TicketNeighborhoodBest(
                ticket_index=index,
                ticket=ticket,
                candidate_count=int(ranks.size),
                duplicate_ticket_candidate_count=int(np.count_nonzero(duplicate)),
                improving_candidate_count=int(np.count_nonzero(improving)),
                best_outcome_count=best_count,
                best_tie_count=len(tied),
                best_move=_exchange_move(index, ticket, new_ticket),
                best_portfolio=best_portfolio,
            )
        )
        portfolio_keys.append(ranks + int(ticket_ranks[index]) * ticket_space)
    best_outcome_count = max(entry.best_outcome_count for entry in per_ticket)
    leaders = [entry for entry in per_ticket if entry.best_outcome_count == best_outcome_count]
    winner = min(leaders, key=lambda entry: entry.best_portfolio)
    return NeighborhoodScan(
        portfolio=tickets,
        outcome_count=current,
        exchange_sizes=sizes,
        candidate_count=sum(entry.candidate_count for entry in per_ticket),
        candidate_count_by_size=tuple(candidates_by_size),
        distinct_portfolio_count=int(np.unique(np.concatenate(portfolio_keys)).size),
        duplicate_ticket_candidate_count=sum(
            entry.duplicate_ticket_candidate_count for entry in per_ticket
        ),
        improving_candidate_count=sum(entry.improving_candidate_count for entry in per_ticket),
        improving_candidate_count_by_size=tuple(improving_by_size),
        best_outcome_count=best_outcome_count,
        best_tie_count=sum(entry.best_tie_count for entry in leaders),
        best_move=winner.best_move,
        best_portfolio=winner.best_portfolio,
        per_ticket=tuple(per_ticket),
    )


@dataclass(frozen=True, slots=True)
class AcceptedExchange:
    """A strict improvement accepted by the ascent, re-verified canonically."""

    iteration: int
    move: ExchangeMove
    old_outcome_count: int
    new_outcome_count: int
    portfolio: Portfolio


@dataclass(frozen=True, slots=True)
class ExchangeAscent:
    """Exact steepest ascent from ``initial_portfolio`` to an exchange local optimum."""

    initial_portfolio: Portfolio
    initial_outcome_count: int
    final_portfolio: Portfolio
    final_outcome_count: int
    scans: tuple[NeighborhoodScan, ...]
    accepted: tuple[AcceptedExchange, ...]

    @property
    def local_optimum(self) -> bool:
        """The last complete scan (over its ``exchange_sizes``) found no strict improvement."""

        return self.scans[-1].best_outcome_count <= self.final_outcome_count


def _canonical_outcome_count(
    space: ExactExchangeSpace, portfolio: Sequence[Sequence[int]], draws: DrawMasks
) -> int:
    return evaluate_portfolio(
        portfolio,
        pool_size=space.pool_size,
        draw_size=space.draw_size,
        outright_matches=space.outright_matches,
        draws=draws,
    ).official_any_prize_outcome_count


def exact_steepest_ascent(
    space: ExactExchangeSpace,
    portfolio: Sequence[Sequence[int]],
    *,
    exchange_sizes: Sequence[int] = (TWO_NUMBER_EXCHANGE,),
    first_scan_exchange_sizes: Sequence[int] | None = None,
    draws: DrawMasks | None = None,
    on_scan: Callable[[NeighborhoodScan], None] | None = None,
) -> ExchangeAscent:
    """Accept the best strict improvement per complete scan until a scan finds none.

    ``first_scan_exchange_sizes`` (default ``exchange_sizes``) narrows only the scan of the
    starting portfolio, for a start already proven optimal under the other sizes; every
    scan after an accepted move covers the complete ``exchange_sizes`` union. Each accepted
    portfolio is re-scored by the canonical evaluator and must agree exactly; any
    disagreement aborts the ascent.
    """

    if draws is None:
        draws = all_main_draw_masks(space.pool_size, space.draw_size)
    current = canonical_portfolio(portfolio, pool_size=space.pool_size, draw_size=space.draw_size)
    current_count = _canonical_outcome_count(space, current, draws)
    initial_portfolio, initial_count = current, current_count
    scans: list[NeighborhoodScan] = []
    accepted: list[AcceptedExchange] = []
    sizes = exchange_sizes if first_scan_exchange_sizes is None else first_scan_exchange_sizes
    while True:
        scan = scan_exchange_neighborhood(space, current, exchange_sizes=sizes)
        if scan.outcome_count != current_count:
            raise ArithmeticError("accelerated and canonical portfolio counts disagree")
        scans.append(scan)
        if on_scan is not None:
            on_scan(scan)
        if scan.best_outcome_count <= current_count:
            break
        verified = _canonical_outcome_count(space, scan.best_portfolio, draws)
        if verified != scan.best_outcome_count:
            raise ArithmeticError("canonical evaluator disagrees with the accepted move")
        accepted.append(
            AcceptedExchange(
                iteration=len(accepted) + 1,
                move=scan.best_move,
                old_outcome_count=current_count,
                new_outcome_count=verified,
                portfolio=scan.best_portfolio,
            )
        )
        current, current_count = scan.best_portfolio, verified
        sizes = exchange_sizes
    return ExchangeAscent(
        initial_portfolio=initial_portfolio,
        initial_outcome_count=initial_count,
        final_portfolio=current,
        final_outcome_count=current_count,
        scans=tuple(scans),
        accepted=tuple(accepted),
    )


def _replaced(tickets: Sequence[Ticket], index: int, ticket: Ticket) -> list[Ticket]:
    return [*tickets[:index], ticket, *tickets[index + 1 :]]


def _scorer_parity_checks(
    space: ExactExchangeSpace, draws: DrawMasks, baseline: Portfolio
) -> list[dict[str, object]]:
    """Accelerated vs canonical exact counts on deterministic baseline-adjacent portfolios."""

    checks: list[dict[str, object]] = []

    def record(label: str, portfolio: Sequence[Ticket], accelerated: int) -> None:
        canonical = _canonical_outcome_count(space, portfolio, draws)
        checks.append(
            {
                "CHECK": label,
                "PORTFOLIO_SHA256": canonical_portfolio_sha256(sorted(portfolio)),
                "ACCELERATED_WINNING_OUTCOMES": accelerated,
                "CANONICAL_WINNING_OUTCOMES": canonical,
                "EXACT_MATCH": accelerated == canonical,
            }
        )

    def replacement(portfolio: Sequence[Ticket], index: int, ticket: Ticket) -> int:
        scorer = space.replacement_scorer(space.coverage(portfolio), index)
        return int(space.replacement_outcome_counts(scorer, [ticket])[0])

    coverage = space.coverage(baseline)
    record("BASELINE_V3_FULL", baseline, coverage.outcome_count)
    for index, ticket in enumerate(baseline):
        scorer = space.replacement_scorer(coverage, index)
        identity = int(space.replacement_outcome_counts(scorer, [ticket])[0])
        record(f"BASELINE_V3_IDENTITY_REPLACEMENT[{index}]", baseline, identity)

    v3_index = baseline.index(KNOWN_V3_TICKET)
    v2 = _replaced(baseline, v3_index, KNOWN_V2_TICKET)
    record("ONE_NUMBER_KNOWN_V3_TO_V2", v2, replacement(baseline, v3_index, KNOWN_V2_TICKET))
    record(
        "ONE_NUMBER_KNOWN_V2_TO_V3",
        baseline,
        replacement(v2, v3_index, KNOWN_V3_TICKET),
    )
    for index in (0, 6, 13, 19):
        neighborhood = exchange_neighborhood(baseline[index], exchange_size=1)
        for row in (0, neighborhood.rows.shape[0] - 1):
            ticket = neighborhood.move(row)[2]
            record(
                f"ONE_NUMBER[{index}][{row}]",
                _replaced(baseline, index, ticket),
                replacement(baseline, index, ticket),
            )
    for index in (0, 5, 10, 15, 19):
        neighborhood = exchange_neighborhood(baseline[index], exchange_size=2)
        last = neighborhood.rows.shape[0] - 1
        for row in (0, last // 2, last):
            ticket = neighborhood.move(row)[2]
            record(
                f"TWO_NUMBER[{index}][{row}]",
                _replaced(baseline, index, ticket),
                replacement(baseline, index, ticket),
            )
    record(
        "DUPLICATE_TICKET[0<-1]",
        _replaced(baseline, 0, baseline[1]),
        replacement(baseline, 0, baseline[1]),
    )
    overlap = next(
        candidate
        for row in range(exchange_neighborhood(baseline[1], exchange_size=1).rows.shape[0])
        if (candidate := exchange_neighborhood(baseline[1], exchange_size=1).move(row)[2])
        not in baseline
    )
    record(
        "FIVE_NUMBER_OVERLAP[0<-near(1)]",
        _replaced(baseline, 0, overlap),
        replacement(baseline, 0, overlap),
    )
    return checks


def _three_exchange_parity_checks(
    space: ExactExchangeSpace, draws: DrawMasks, baseline: Portfolio
) -> list[dict[str, object]]:
    """Accelerated vs canonical exact counts for three-number replacements of ``baseline``.

    Every ticket gets one seeded-random candidate plus the two candidates that meet the rest
    of the portfolio hardest -- the largest overlap with any single other ticket, and the
    largest overlap summed over all of them; five tickets also get rows spread across their
    whole neighborhood.
    """

    coverage = space.coverage(baseline)
    rng = random.Random(_THREE_EXCHANGE_PARITY_SEED)
    checks: list[dict[str, object]] = []
    for index, ticket in enumerate(baseline):
        neighborhood = exchange_neighborhood(
            ticket, pool_size=space.pool_size, exchange_size=THREE_NUMBER_EXCHANGE
        )
        other_masks = np.array(
            coverage.masks[:index] + coverage.masks[index + 1 :], dtype=np.uint64
        )
        overlaps = np.bitwise_count(
            _row_masks((neighborhood.rows - 1).astype(np.uint8))[:, np.newaxis] & other_masks
        ).astype(np.int64)
        single, total = overlaps.max(axis=1), overlaps.sum(axis=1)
        last = neighborhood.rows.shape[0] - 1
        # argmax takes the first row among ties, so every pick is deterministic.
        samples = {
            "RANDOM": rng.randint(0, last),
            "MAX_ONE_TICKET_OVERLAP": int(np.argmax(single * (int(total.max()) + 1) + total)),
            "MAX_TOTAL_OVERLAP": int(np.argmax(total * (int(single.max()) + 1) + single)),
        }
        if index in _THREE_EXCHANGE_SPREAD_INDICES:
            samples |= {"FIRST": 0, "THIRD": last // 3, "TWO_THIRDS": 2 * last // 3, "LAST": last}
        scorer = space.replacement_scorer(coverage, index)
        accelerated = space.replacement_outcome_counts(
            scorer, neighborhood.rows[list(samples.values())]
        ).tolist()
        for (label, row), count in zip(samples.items(), accelerated, strict=True):
            portfolio = _replaced(baseline, index, neighborhood.move(row)[2])
            canonical = _canonical_outcome_count(space, portfolio, draws)
            checks.append(
                {
                    "CHECK": f"THREE_NUMBER_{label}[{index}][{row}]",
                    "PORTFOLIO_SHA256": canonical_portfolio_sha256(sorted(portfolio)),
                    "MAX_OVERLAP_WITH_ONE_OTHER_TICKET": int(single[row]),
                    "TOTAL_OVERLAP_WITH_OTHER_TICKETS": int(total[row]),
                    "ACCELERATED_WINNING_OUTCOMES": count,
                    "CANONICAL_WINNING_OUTCOMES": canonical,
                    "EXACT_MATCH": count == canonical,
                }
            )
    return checks


def _small_lottery_exchange_parity() -> dict[str, object]:
    """Every <=3-number exchange candidate of a small-lottery portfolio vs the canonical count."""

    pool_size, draw_size, outright_matches = _SMALL_PARITY_SHAPE
    space = ExactExchangeSpace(
        pool_size=pool_size, draw_size=draw_size, outright_matches=outright_matches
    )
    draws = all_main_draw_masks(pool_size, draw_size)
    portfolio = canonical_portfolio(
        _SMALL_PARITY_PORTFOLIO, pool_size=pool_size, draw_size=draw_size
    )
    coverage = space.coverage(portfolio)
    candidates = dict.fromkeys(UP_TO_THREE_NUMBER_EXCHANGES, 0)
    values: set[int] = set()
    duplicates = exact = 0
    for index, ticket in enumerate(portfolio):
        scorer = space.replacement_scorer(coverage, index)
        for size in UP_TO_THREE_NUMBER_EXCHANGES:
            neighborhood = exchange_neighborhood(ticket, pool_size=pool_size, exchange_size=size)
            counts = space.replacement_outcome_counts(scorer, neighborhood.rows).tolist()
            for row, count in enumerate(counts):
                replaced = _replaced(portfolio, index, neighborhood.move(row)[2])
                canonical = _canonical_outcome_count(space, replaced, draws)
                exact += int(count == canonical)
                values.add(canonical)
                duplicates += int(len(set(replaced)) != len(replaced))
                candidates[size] += 1
    total = sum(candidates.values())
    return {
        "POOL_SIZE": pool_size,
        "DRAW_SIZE": draw_size,
        "OUTRIGHT_MATCHES": outright_matches,
        "PORTFOLIO": [list(ticket) for ticket in portfolio],
        "PORTFOLIO_WINNING_OUTCOMES": coverage.outcome_count,
        "TOTAL_OUTCOMES": space.total_outcomes,
        "CANDIDATES_BY_EXCHANGE_SIZE": {str(size): count for size, count in candidates.items()},
        "CANDIDATES": total,
        "DISTINCT_CANONICAL_WINNING_OUTCOME_VALUES": len(values),
        "DUPLICATE_TICKET_CANDIDATES": duplicates,
        "EXACT_MATCHES": exact,
        "EXACT_MATCH": exact == total,
    }


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _decimal_text(value: Fraction, places: int = 12) -> str:
    with localcontext() as context:
        context.prec = 40
        return str(
            (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
                Decimal(1).scaleb(-places)
            )
        )


def _move_record(move: ExchangeMove) -> dict[str, object]:
    return {
        "TICKET_INDEX": move.ticket_index,
        "EXCHANGE_SIZE": move.exchange_size,
        "OLD_TICKET": list(move.old_ticket),
        "NEW_TICKET": list(move.new_ticket),
        "REMOVED_NUMBERS": list(move.removed_numbers),
        "INSERTED_NUMBERS": list(move.inserted_numbers),
    }


def _by_size(scan: NeighborhoodScan, counts: tuple[int, ...]) -> dict[str, int]:
    return {str(size): count for size, count in zip(scan.exchange_sizes, counts, strict=True)}


def _scan_record(iteration: int, scan: NeighborhoodScan) -> dict[str, object]:
    return {
        "ITERATION": iteration,
        "PORTFOLIO_SHA256": canonical_portfolio_sha256(scan.portfolio),
        "CURRENT_WINNING_OUTCOMES": scan.outcome_count,
        "EXCHANGE_SIZES": list(scan.exchange_sizes),
        "CANDIDATE_COUNT": scan.candidate_count,
        "CANDIDATE_COUNT_BY_EXCHANGE_SIZE": _by_size(scan, scan.candidate_count_by_size),
        "DISTINCT_CANDIDATE_PORTFOLIOS": scan.distinct_portfolio_count,
        "DUPLICATE_TICKET_CANDIDATES": scan.duplicate_ticket_candidate_count,
        "STRICTLY_IMPROVING_CANDIDATES": scan.improving_candidate_count,
        "STRICTLY_IMPROVING_CANDIDATES_BY_EXCHANGE_SIZE": _by_size(
            scan, scan.improving_candidate_count_by_size
        ),
        "BEST_NEIGHBOR_WINNING_OUTCOMES": scan.best_outcome_count,
        "BEST_NEIGHBOR_TIE_COUNT": scan.best_tie_count,
        "BEST_NEIGHBOR_MOVE": _move_record(scan.best_move),
        "BEST_NEIGHBOR_PORTFOLIO_SHA256": canonical_portfolio_sha256(scan.best_portfolio),
        "STRICT_IMPROVEMENT_FOUND": scan.best_outcome_count > scan.outcome_count,
        "PER_TICKET_BEST_WINNING_OUTCOMES": [entry.best_outcome_count for entry in scan.per_ticket],
    }


def _frozen_v3_k20_baseline(
    started: float, log: Callable[[str], None]
) -> tuple[SealedGeometryPortfolio, ExactExchangeSpace, DrawMasks, Portfolio]:
    """The sealed v3 K20 portfolio, re-verified against its seal and the canonical evaluator."""

    entry = SEALED_GEOMETRY_PORTFOLIOS[BASELINE_TICKET_COUNT]
    verify_sealed_geometry_portfolio(entry)
    if (
        SEALED_GEOMETRY_METHOD_VERSION != BASELINE_METHOD_VERSION
        or entry.portfolio_sha256 != BASELINE_PORTFOLIO_SHA256
    ):
        raise ValueError("sealed K20 portfolio is not the frozen v3 baseline")
    space = ExactExchangeSpace()
    draws = all_main_draw_masks(space.pool_size, space.draw_size)
    log(f"space ready in {time.perf_counter() - started:.1f}s")
    baseline = canonical_portfolio(entry.tickets)
    if baseline != entry.tickets:
        raise ValueError("sealed K20 tickets are not in canonical order")
    baseline_result = evaluate_portfolio(baseline, draws=draws)
    if (
        baseline_result.official_any_prize_outcome_count != BASELINE_WINNING_OUTCOMES
        or baseline_result.official_any_prize != entry.official_any_prize_probability
    ):
        raise ArithmeticError("canonical evaluator does not reproduce the v3 baseline")
    return entry, space, draws, baseline


def _run_v3_k20_ascent(
    *,
    task_id: str,
    search_algorithm: str,
    exchange_sizes: Sequence[int],
    first_scan_exchange_sizes: Sequence[int] | None = None,
    extra_parity_checks: (
        Callable[[ExactExchangeSpace, DrawMasks, Portfolio], list[dict[str, object]]] | None
    ) = None,
    log: Callable[[str], None],
) -> tuple[ExchangeAscent, dict[str, object]]:
    """Parity-gate the accelerated scorer, then run the exact ascent from sealed v3 K20.

    Every count in the returned record has been checked against the canonical evaluator:
    the parity samples, each accepted portfolio, each terminal per-ticket best, and the
    original and final portfolios.
    """

    started = time.perf_counter()
    entry, space, draws, baseline = _frozen_v3_k20_baseline(started, log)
    parity = _scorer_parity_checks(space, draws, baseline)
    if extra_parity_checks is not None:
        parity += extra_parity_checks(space, draws, baseline)
    known = {str(check["CHECK"]): check for check in parity}
    if (
        not all(check["EXACT_MATCH"] for check in parity)
        or known["ONE_NUMBER_KNOWN_V3_TO_V2"]["CANONICAL_WINNING_OUTCOMES"]
        != KNOWN_V2_WINNING_OUTCOMES
    ):
        raise ArithmeticError("accelerated scorer failed exact canonical parity")
    log(f"{len(parity)} parity checks exact in {time.perf_counter() - started:.1f}s")

    def on_scan(scan: NeighborhoodScan) -> None:
        log(
            f"scan {list(scan.exchange_sizes)}: current={scan.outcome_count} "
            f"best={scan.best_outcome_count} improving={scan.improving_candidate_count} "
            f"candidates={scan.candidate_count} t={time.perf_counter() - started:.1f}s"
        )

    ascent = exact_steepest_ascent(
        space,
        baseline,
        exchange_sizes=exchange_sizes,
        first_scan_exchange_sizes=first_scan_exchange_sizes,
        draws=draws,
        on_scan=on_scan,
    )
    outside = space.pool_size - space.draw_size
    for scan in ascent.scans:
        complete = tuple(
            len(scan.portfolio) * comb(space.draw_size, size) * comb(outside, size)
            for size in scan.exchange_sizes
        )
        if (
            scan.candidate_count_by_size != complete
            or scan.distinct_portfolio_count != scan.candidate_count
        ):
            raise AssertionError("an exchange scan did not cover its complete neighborhood")
    final_result = evaluate_portfolio(ascent.final_portfolio, draws=draws)
    original_recheck = evaluate_portfolio(entry.tickets, draws=draws)
    terminal = ascent.scans[-1]
    terminal_checks = [
        {
            "TICKET_INDEX": best.ticket_index,
            "ACCELERATED_WINNING_OUTCOMES": best.best_outcome_count,
            "CANONICAL_WINNING_OUTCOMES": _canonical_outcome_count(
                space, best.best_portfolio, draws
            ),
        }
        for best in terminal.per_ticket
    ]
    if any(
        check["ACCELERATED_WINNING_OUTCOMES"] != check["CANONICAL_WINNING_OUTCOMES"]
        for check in terminal_checks
    ):
        raise ArithmeticError("terminal per-ticket best disagrees with the canonical evaluator")
    if (
        final_result.official_any_prize_outcome_count != ascent.final_outcome_count
        or original_recheck.official_any_prize_outcome_count != ascent.initial_outcome_count
    ):
        raise ArithmeticError("final canonical validation disagrees with the search")
    log(f"done in {time.perf_counter() - started:.1f}s")

    total = space.total_outcomes
    gain = ascent.final_outcome_count - ascent.initial_outcome_count
    final_probability = final_result.official_any_prize
    return ascent, {
        "TASK_ID": task_id,
        "OBJECTIVE": "OFFICIAL_ANY_PRIZE",
        "PROBABILITY_MODEL": "BIG_LOTTO_UNIFORM_FAIR_DRAW",
        "SEARCH_ALGORITHM": search_algorithm,
        "SCORER": (
            "EXACT_SUPERSET_MARGINAL_DELTA: 4*newly_won_7sets = T3 - 4*T4 + 12*T5 - 40*T6 "
            "over per-draw losing-special counts of the other tickets; int64, exact division"
        ),
        "BASELINE": {
            "STRATEGY": f"{SEALED_GEOMETRY_METHOD_ID}@{SEALED_GEOMETRY_METHOD_VERSION}",
            "K": BASELINE_TICKET_COUNT,
            "PORTFOLIO": [list(ticket) for ticket in baseline],
            "PORTFOLIO_SHA256": entry.portfolio_sha256,
            "WINNING_OUTCOMES": ascent.initial_outcome_count,
            "TOTAL_OUTCOMES": total,
            "EXACT_ANY_PRIZE": _fraction_text(Fraction(ascent.initial_outcome_count, total)),
        },
        "SCORER_PARITY_CHECKS": parity,
        "SCORER_PARITY_CHECK_COUNT": len(parity),
        "SCORER_PARITY": "PASS",
        "ITERATIONS": [
            _scan_record(iteration, scan) for iteration, scan in enumerate(ascent.scans)
        ],
        "ITERATION_COUNT": len(ascent.scans),
        "ACCEPTED_MOVES": [
            {
                "ITERATION": move.iteration,
                **_move_record(move.move),
                "OLD_WINNING_OUTCOMES": move.old_outcome_count,
                "NEW_WINNING_OUTCOMES": move.new_outcome_count,
                "GAIN_OUTCOMES": move.new_outcome_count - move.old_outcome_count,
                "PORTFOLIO_SHA256": canonical_portfolio_sha256(move.portfolio),
                "CANONICAL_RECHECK": "PASS",
            }
            for move in ascent.accepted
        ],
        "TOTAL_CANDIDATES_EVALUATED": sum(scan.candidate_count for scan in ascent.scans),
        "TOTAL_DISTINCT_CANDIDATES_EVALUATED": sum(
            scan.distinct_portfolio_count for scan in ascent.scans
        ),
        "TERMINAL_SCAN_PER_TICKET_BEST_CANONICAL_CHECKS": terminal_checks,
        "FINAL_PORTFOLIO": [list(ticket) for ticket in ascent.final_portfolio],
        "FINAL_PORTFOLIO_SHA256": canonical_portfolio_sha256(ascent.final_portfolio),
        "FINAL_PORTFOLIO_UNCHANGED_V3": ascent.final_portfolio == baseline,
        "FINAL_WINNING_OUTCOMES": ascent.final_outcome_count,
        "FINAL_EXACT_ANY_PRIZE": _fraction_text(final_probability),
        "FINAL_EXACT_ANY_PRIZE_DECIMAL": _decimal_text(final_probability),
        "FINAL_M3_PLUS_PROBABILITY": _fraction_text(final_result.m3_plus),
        "CANONICAL_FINAL_VALIDATION": {
            "ORIGINAL_V3_CANONICAL_WINNING_OUTCOMES": (
                original_recheck.official_any_prize_outcome_count
            ),
            "FINAL_CANONICAL_WINNING_OUTCOMES": final_result.official_any_prize_outcome_count,
            "EXACT_AGREEMENT_WITH_SEARCH": "PASS",
        },
        "ABSOLUTE_GAIN_WINNING_OUTCOMES": gain,
        "ABSOLUTE_GAIN_PERCENTAGE_POINTS": _fraction_text(Fraction(100 * gain, total)),
        "ABSOLUTE_GAIN_PERCENTAGE_POINTS_DECIMAL": _decimal_text(Fraction(100 * gain, total)),
        "RELATIVE_GAIN": _fraction_text(Fraction(gain, ascent.initial_outcome_count)),
        "SEARCH_SPACE_COMPLETE": "YES",
        "RESULT_LEAKAGE": "NONE",
        "OUTCOME_FIELDS_USED": "NO",
    }


def run_v3_k20_two_exchange_search(
    *, log: Callable[[str], None] = lambda _message: None
) -> dict[str, object]:
    """Parity-gate the accelerated scorer, then run the exact ascent from sealed v3 K20."""

    ascent, result = _run_v3_k20_ascent(
        task_id=TWO_EXCHANGE_TASK_ID,
        search_algorithm=(
            "EXACT_STEEPEST_ASCENT_SINGLE_TICKET_TWO_NUMBER_EXCHANGE: complete neighborhood "
            "K*C(6,2)*C(43,2) per scan; accept the best strict improvement (ties: smallest "
            "canonical lexical portfolio); stop when a complete scan has none"
        ),
        exchange_sizes=(TWO_NUMBER_EXCHANGE,),
        log=log,
    )
    return result | {"TWO_EXCHANGE_LOCAL_OPTIMUM": "YES" if ascent.local_optimum else "NO"}


def run_v3_k20_three_exchange_search(
    *, log: Callable[[str], None] = lambda _message: None
) -> dict[str, object]:
    """Exact three-number ascent from sealed v3 K20, widening to the <=3 union after a move.

    The unchanged baseline is already one- and two-number optimal (``PRIOR_*_EVIDENCE``), so
    the first scan covers its three-number neighborhood only. An accepted move voids that
    evidence for the new portfolio, so every later scan covers the complete 1-, 2- and
    3-number union, until one finds no strict improvement.
    """

    small = _small_lottery_exchange_parity()
    if small["EXACT_MATCH"] is not True:
        raise ArithmeticError("small-lottery exhaustive exchange parity failed")
    log(f"small-lottery exhaustive parity: {small['EXACT_MATCHES']}/{small['CANDIDATES']} exact")
    ascent, result = _run_v3_k20_ascent(
        task_id=THREE_EXCHANGE_TASK_ID,
        search_algorithm=(
            "EXACT_STEEPEST_ASCENT_SINGLE_TICKET_LEQ3_NUMBER_EXCHANGE: iteration 0 scans the "
            "complete three-number neighborhood K*C(6,3)*C(43,3) of the sealed v3 baseline "
            "(already one- and two-number optimal); every scan after an accepted move covers "
            "the complete union K*(C(6,1)*C(43,1)+C(6,2)*C(43,2)+C(6,3)*C(43,3)); accept the "
            "best strict improvement (ties: smallest canonical lexical portfolio); stop when a "
            "complete scan has none"
        ),
        exchange_sizes=UP_TO_THREE_NUMBER_EXCHANGES,
        first_scan_exchange_sizes=(THREE_NUMBER_EXCHANGE,),
        extra_parity_checks=_three_exchange_parity_checks,
        log=log,
    )
    first, *later = ascent.scans
    terminal = ascent.scans[-1]
    three_optimum = ascent.local_optimum and THREE_NUMBER_EXCHANGE in terminal.exchange_sizes
    union_optimum = three_optimum and terminal.exchange_sizes == UP_TO_THREE_NUMBER_EXCHANGES
    # Without an accepted move the final portfolio is the baseline itself, whose one- and
    # two-number optimality is the reused prior evidence.
    prior_optimum = three_optimum and not ascent.accepted
    return result | {
        "PRIOR_EXCHANGE_EVIDENCE_REUSED": {
            "ONE_NUMBER_EXCHANGE_LOCAL_OPTIMUM": PRIOR_ONE_EXCHANGE_EVIDENCE,
            "TWO_NUMBER_EXCHANGE_LOCAL_OPTIMUM": PRIOR_TWO_EXCHANGE_EVIDENCE,
        },
        "SMALL_LOTTERY_EXHAUSTIVE_EXCHANGE_PARITY": small,
        "FIRST_THREE_EXCHANGE_SCAN_CANDIDATES": first.candidate_count,
        "POST_MOVE_UNION_SCAN_CANDIDATES": [scan.candidate_count for scan in later],
        "POST_MOVE_UNION_SCAN_CANDIDATES_TOTAL": sum(scan.candidate_count for scan in later),
        "THREE_EXCHANGE_LOCAL_OPTIMUM": "YES" if three_optimum else "NO",
        "LEQ3_EXCHANGE_LOCAL_OPTIMUM": "YES" if union_optimum or prior_optimum else "NO",
        "LEQ3_EXCHANGE_LOCAL_OPTIMUM_BASIS": (
            "THIS_RUN_COMPLETE_1_2_3_UNION_SCAN_OF_FINAL_PORTFOLIO"
            if union_optimum
            else "THIS_RUN_COMPLETE_3_SCAN_PLUS_PRIOR_EXCHANGE_EVIDENCE_REUSED"
            if prior_optimum
            else "NONE"
        ),
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run an exact sealed-v3 K20 exchange search")
    parser.add_argument(
        "--search",
        choices=("two-number", "three-number"),
        required=True,
        help=f"two-number: {TWO_EXCHANGE_TASK_ID}; three-number: {THREE_EXCHANGE_TASK_ID}",
    )
    parser.add_argument("--output", type=Path, required=True, help="result JSON path")
    arguments = parser.parse_args(argv)
    output: Path = arguments.output
    search: str = arguments.search

    def log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    log(f"{search} search: {__file__}")
    if search == "three-number":
        result = run_v3_k20_three_exchange_search(log=log)
    else:
        result = run_v3_k20_two_exchange_search(log=log)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {output}")


if __name__ == "__main__":
    main()
