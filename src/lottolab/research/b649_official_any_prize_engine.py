"""Exact BIG_LOTTO portfolio win probabilities under the uniform fair-draw model.

A portfolio wins OFFICIAL_ANY_PRIZE on an outcome (main draw ``D``, special
``s``) when some ticket ``t`` has ``|t & D| >= 3``, or ``|t & D| == 2`` and
``s in t`` -- the lowest official tier (柒獎), see
``lottolab.domain.lottery_rules.resolve_big_lotto_prize_tier``. The special is
drawn uniformly from the ``pool_size - draw_size`` numbers not in ``D``
(``main_special_overlap_allowed=False``), so on a main draw where no ticket
reaches 3 matches the portfolio wins on exactly
``|U_{t: |t & D| == 2} (t - D)|`` of those specials.

Auto uses the complete integer loss polynomial for six-number/threshold-three
requests. The independent reference enumerates all main draws as uint64 masks
and collapses the special analytically. No sampling or historical draws.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from typing import Literal

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_official_any_prize_dp import (
    CountIncomplete,
    EvaluationBudget,
    EvaluationLimits,
    EvaluationRuntime,
    UnsupportedDP,
    count_loss_polynomial,
    supports_dp,
)

type Ticket = tuple[int, ...]
type DrawMasks = npt.NDArray[np.uint64]

BIG_LOTTO_POOL_SIZE = 49
BIG_LOTTO_DRAW_SIZE = 6
BIG_LOTTO_OUTRIGHT_MATCHES = 3
_DEFAULT_CHUNK_SIZE = 1 << 21


@dataclass(frozen=True, slots=True)
class ExactPortfolioProbability:
    """Exact outcome counts for one portfolio over the whole outcome space."""

    main_draw_count: int
    special_count: int
    m3_plus_draw_count: int
    official_any_prize_outcome_count: int

    @property
    def m3_plus(self) -> Fraction:
        """P(some ticket matches ``>= outright_matches`` main numbers)."""

        return Fraction(self.m3_plus_draw_count, self.main_draw_count)

    @property
    def official_any_prize(self) -> Fraction:
        """P(some ticket wins any official prize, special ball included)."""

        return Fraction(
            self.official_any_prize_outcome_count,
            self.main_draw_count * self.special_count,
        )


def ticket_mask(ticket: Sequence[int]) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def all_main_draw_masks(pool_size: int, draw_size: int) -> DrawMasks:
    """Every ``draw_size``-subset of ``1..pool_size`` exactly once, as bitmasks.

    Built as (two smallest numbers) + (remaining subset whose minimum exceeds
    both), which is exhaustive and duplicate-free by construction and avoids a
    Python-level loop over all ``C(pool_size, draw_size)`` draws.
    """

    return _construct_draws(pool_size, draw_size)


def _construct_draws(
    pool_size: int, draw_size: int, budget: EvaluationBudget | None = None
) -> DrawMasks:
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("draw space must satisfy 1 <= draw_size <= pool_size <= 64")
    numbers = range(1, pool_size + 1)
    if draw_size < 3:
        return np.array(
            [ticket_mask(draw) for draw in itertools.combinations(numbers, draw_size)],
            dtype=np.uint64,
        )

    rest: list[tuple[int, ...]] = []
    for index, subset in enumerate(itertools.combinations(numbers, draw_size - 2)):
        if budget is not None and index % 2048 == 0:
            budget.check()
        rest.append(subset)
    rest_masks = np.array([ticket_mask(subset) for subset in rest], dtype=np.uint64)
    rest_minimum = np.array([subset[0] for subset in rest], dtype=np.int64)
    order = np.argsort(rest_minimum, kind="stable")
    rest_masks = rest_masks[order]
    first_index_with_minimum = np.searchsorted(
        rest_minimum[order], np.arange(0, pool_size + 2), side="left"
    )

    draws = np.empty(comb(pool_size, draw_size), dtype=np.uint64)
    position = 0
    for low in numbers:
        for high in range(low + 1, pool_size + 1):
            if budget is not None:
                budget.check()
            tail = rest_masks[int(first_index_with_minimum[high + 1]) :]
            draws[position : position + tail.size] = tail | np.uint64(ticket_mask((low, high)))
            position += tail.size
    if position != draws.size:
        raise AssertionError("draw-space construction did not fill C(pool_size, draw_size)")
    return draws


def evaluate_portfolio(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
    draws: DrawMasks | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> ExactPortfolioProbability:
    """Exact M3+ and OFFICIAL_ANY_PRIZE counts for one portfolio.

    Tickets must be ``draw_size`` distinct numbers in ``1..pool_size``. A
    repeated ticket is inert (success is a union over tickets). Pass ``draws``
    from :func:`all_main_draw_masks` to reuse one draw space across portfolios.
    """

    return evaluate_portfolio_with_diagnostics(
        portfolio,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
        draws=draws,
        chunk_size=chunk_size,
    ).probability


def _validate(
    portfolio: Sequence[Sequence[int]],
    pool_size: int,
    draw_size: int,
    outright_matches: int,
    chunk_size: int,
) -> None:
    if not portfolio:
        raise ValueError("portfolio must contain at least one ticket")
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("draw space must satisfy 1 <= draw_size <= pool_size <= 64")
    if not 1 <= outright_matches <= draw_size:
        raise ValueError("outright_matches must be within 1..draw_size")
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    for ticket in portfolio:
        if (
            len(ticket) != draw_size
            or len(set(ticket)) != draw_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError(f"illegal ticket: {tuple(ticket)}")


def evaluate_portfolio_reference(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
    draws: DrawMasks | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    limits: EvaluationLimits | None = None,
    runtime: EvaluationRuntime | None = None,
    _budget: EvaluationBudget | None = None,
) -> ExactPortfolioProbability:
    """Independent complete main-draw/special-union enumeration; never calls DP.

    Supplied draws retain the existing complete-size contract. Their content is
    caller-owned, as before. Resource/deadline refusal raises CountIncomplete.
    """
    budget = _budget or EvaluationBudget(
        limits or EvaluationLimits(), runtime or EvaluationRuntime()
    )
    _validate(portfolio, pool_size, draw_size, outright_matches, chunk_size)
    if draws is not None and draws.size != comb(pool_size, draw_size):
        raise ValueError("draws must be the complete main-draw space")
    budget.admit_reference(pool_size, draw_size, len(portfolio), chunk_size, draws is not None)
    masks = [np.uint64(ticket_mask(ticket)) for ticket in portfolio]
    if draws is None:
        draws = _construct_draws(pool_size, draw_size, budget)

    special_count = pool_size - draw_size
    rescue_matches = outright_matches - 1
    zero = np.uint64(0)
    m3_plus = 0
    rescued_specials = 0
    for start in range(0, draws.size, chunk_size):
        budget.check()
        chunk = draws[start : start + chunk_size]
        won = np.zeros(chunk.size, dtype=np.bool_)
        rescue = np.zeros(chunk.size, dtype=np.uint64)
        for mask in masks:
            budget.check()
            hits = np.bitwise_count(chunk & mask)
            won |= hits >= outright_matches
            # (a & ~D) | (b & ~D) == (a | b) & ~D: OR the tickets, strip D once below.
            rescue |= np.where(hits == rescue_matches, mask, zero)
        rescue &= ~chunk
        m3_plus += int(np.count_nonzero(won))
        rescued_specials += int(np.bitwise_count(rescue[~won]).sum(dtype=np.int64))
    budget.check()
    return ExactPortfolioProbability(
        main_draw_count=int(draws.size),
        special_count=special_count,
        m3_plus_draw_count=m3_plus,
        official_any_prize_outcome_count=m3_plus * special_count + rescued_specials,
    )


type Engine = Literal["auto", "dp", "enumeration"]


@dataclass(frozen=True, slots=True)
class EvaluationDiagnostics:
    requested_engine: Engine
    actual_engine: Literal["dp", "enumeration"]
    fallback_reason: str | None
    dp_states: int
    peak_live_states: int
    loss_polynomial: tuple[int, ...] | None
    total_seconds: float
    observed_peak_rss_bytes: int


@dataclass(frozen=True, slots=True)
class PortfolioEvaluation:
    probability: ExactPortfolioProbability
    diagnostics: EvaluationDiagnostics


def evaluate_portfolio_with_diagnostics(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
    draws: DrawMasks | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    engine: Engine = "auto",
    limits: EvaluationLimits | None = None,
    runtime: EvaluationRuntime | None = None,
) -> PortfolioEvaluation:
    """Explicit engine selection and per-call diagnostics without changing the old API.

    Explicit DP never falls back. Auto attempts DP only in its supported domain,
    with no supplied draws and the default chunk size. Only named limits and
    MemoryError permit one full reference restart; defects/cancellation propagate.
    RSS is polled and reference admission is estimated, not an OS memory sandbox.
    """
    budget = EvaluationBudget(limits or EvaluationLimits(), runtime or EvaluationRuntime())
    _validate(portfolio, pool_size, draw_size, outright_matches, chunk_size)
    if engine not in ("auto", "dp", "enumeration"):
        raise ValueError("engine must be auto, dp, or enumeration")
    eligible = supports_dp(pool_size, draw_size, outright_matches)
    eligible = eligible and draws is None and chunk_size == _DEFAULT_CHUNK_SIZE
    if engine == "dp" and not eligible:
        raise UnsupportedDP("DP_UNSUPPORTED_REQUEST")
    fallback_reason: str | None = None
    polynomial: tuple[int, ...] | None = None
    result: ExactPortfolioProbability | None = None
    actual_engine: Literal["dp", "enumeration"] = "enumeration"
    if engine != "enumeration" and eligible:
        try:
            loss = count_loss_polynomial(portfolio, pool_size=pool_size, budget=budget)
            polynomial = loss.coefficients
            result = ExactPortfolioProbability(
                comb(pool_size, 6),
                pool_size - 6,
                comb(pool_size, 6) - polynomial[6],
                7 * (comb(pool_size, 7) - polynomial[7]),
            )
            actual_engine = "dp"
        except (CountIncomplete, MemoryError) as error:
            if engine == "dp":
                raise
            fallback_reason = error.reason if isinstance(error, CountIncomplete) else "MEMORY_LIMIT"
        if result is None:
            budget.release_partial()
    if result is None:
        result = evaluate_portfolio_reference(
            portfolio,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            draws=draws,
            chunk_size=chunk_size,
            _budget=budget,
        )
    budget.check()
    return PortfolioEvaluation(
        result,
        EvaluationDiagnostics(
            engine,
            actual_engine,
            fallback_reason,
            budget.states,
            budget.peak_live_states,
            polynomial,
            budget.runtime.clock() - budget.started,
            budget.observed_rss,
        ),
    )


def independent_random_official_any_prize(ticket_count: int) -> Fraction:
    """``1 - (1 - p)^k`` for ``k`` independent uniformly random tickets."""

    single = evaluate_single_ticket_closed_form()
    return 1 - (1 - single) ** ticket_count


def evaluate_single_ticket_closed_form(
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
) -> Fraction:
    """Single-ticket OFFICIAL_ANY_PRIZE from the hypergeometric law alone."""

    total = comb(pool_size, draw_size)
    others = pool_size - draw_size
    outright = sum(
        comb(draw_size, hits) * comb(others, draw_size - hits)
        for hits in range(outright_matches, draw_size + 1)
    )
    rescue_hits = outright_matches - 1
    rescue_draws = comb(draw_size, rescue_hits) * comb(others, draw_size - rescue_hits)
    return Fraction(outright, total) + Fraction(rescue_draws, total) * Fraction(
        draw_size - rescue_hits, others
    )


__all__ = [
    "BIG_LOTTO_DRAW_SIZE",
    "BIG_LOTTO_OUTRIGHT_MATCHES",
    "BIG_LOTTO_POOL_SIZE",
    "CountIncomplete",
    "EvaluationDiagnostics",
    "EvaluationLimits",
    "EvaluationRuntime",
    "ExactPortfolioProbability",
    "PortfolioEvaluation",
    "UnsupportedDP",
    "all_main_draw_masks",
    "evaluate_portfolio",
    "evaluate_portfolio_reference",
    "evaluate_portfolio_with_diagnostics",
    "evaluate_single_ticket_closed_form",
    "independent_random_official_any_prize",
    "ticket_mask",
]
