"""Exact BIG_LOTTO portfolio win probabilities under the uniform fair-draw model.

A portfolio wins OFFICIAL_ANY_PRIZE on an outcome (main draw ``D``, special
``s``) when some ticket ``t`` has ``|t & D| >= 3``, or ``|t & D| == 2`` and
``s in t`` -- the lowest official tier (柒獎), see
``lottolab.domain.lottery_rules.resolve_big_lotto_prize_tier``. The special is
drawn uniformly from the ``pool_size - draw_size`` numbers not in ``D``
(``main_special_overlap_allowed=False``), so on a main draw where no ticket
reaches 3 matches the portfolio wins on exactly
``|U_{t: |t & D| == 2} (t - D)|`` of those specials.

Every count is exact: all ``C(pool_size, draw_size)`` main draws are enumerated
as ``uint64`` bitmasks and the special is collapsed analytically
(MAIN_DRAW_COLLAPSED_EXACT_SPECIAL_UNION). No sampling and no historical draws.
The draw space is generic over ``(pool_size, draw_size, outright_matches)`` so
the same code path can be checked against brute force on a small lottery.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from typing import cast

import numpy as np
import numpy.typing as npt

type Ticket = tuple[int, ...]
type DrawMasks = npt.NDArray[np.uint64]

BIG_LOTTO_POOL_SIZE = 49
BIG_LOTTO_DRAW_SIZE = 6
BIG_LOTTO_OUTRIGHT_MATCHES = 3
_DEFAULT_CHUNK_SIZE = 1 << 21


@dataclass(frozen=True, slots=True)
class _DrawSpaceSeal:
    pool_size: int
    draw_size: int
    buffer: bytes


class _CompleteDrawMasks(np.ndarray[tuple[int], np.dtype[np.uint64]]):
    """An immutable complete space; views/copies do not inherit its seal."""

    __slots__ = ("_seal",)
    _seal: _DrawSpaceSeal

    def __setattr__(self, name: str, value: object) -> None:
        if name == "_seal" and hasattr(self, "_seal"):
            raise AttributeError("draw-space seal is immutable")
        super().__setattr__(name, value)

    @classmethod
    def from_complete_buffer(
        cls, buffer: bytes, pool_size: int, draw_size: int
    ) -> _CompleteDrawMasks:
        # Bytes, rather than a writeable array with its flag cleared, make the
        # data immutable even through aliases or setflags(write=True).
        result = np.ndarray.__new__(cls, shape=(len(buffer) // 8,), dtype=np.uint64, buffer=buffer)
        result._seal = _DrawSpaceSeal(pool_size, draw_size, buffer)
        return result


def _check_draw_parameters(pool_size: int, draw_size: int) -> None:
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("draw space must satisfy 1 <= draw_size <= pool_size <= 64")


def validate_main_draw_masks(draws: object, pool_size: int, draw_size: int) -> DrawMasks:
    """Validate a complete space and return an immutable snapshot for reuse.

    External arrays must be one-dimensional native uint64 masks. Validation
    copies the input before checking it, so later mutations of the source cannot
    invalidate the result. Keep the returned array to avoid repeating this cost.
    A space built by :func:`all_main_draw_masks` is already trusted. Only its
    exact immutable backing buffer, shape, dtype and parameters earn that trust;
    derived arrays and mutable copies must be validated again.
    """

    _check_draw_parameters(pool_size, draw_size)
    if not isinstance(draws, np.ndarray) or draws.ndim != 1:
        raise ValueError("draws must be a one-dimensional uint64 ndarray")
    draws = cast(DrawMasks, draws)
    if draws.dtype != np.dtype(np.uint64):
        raise ValueError("draws must have native uint64 dtype")
    expected = comb(pool_size, draw_size)
    if draws.size != expected:
        raise ValueError("draws must be the complete main-draw space")
    if type(draws) is _CompleteDrawMasks:
        seal = getattr(draws, "_seal", None)
        if seal is not None and draws.base is seal.buffer and draws.strides == (8,):
            if (seal.pool_size, seal.draw_size) != (pool_size, draw_size):
                raise ValueError("draws parameters do not match pool_size and draw_size")
            return draws

    # Check the snapshot we will actually score, not the mutable source.
    buffer = draws.tobytes(order="C")
    snapshot = np.frombuffer(buffer, dtype=np.uint64)
    if pool_size < 64 and np.any(snapshot >> np.uint64(pool_size)):
        raise ValueError("draws contain masks outside the number pool")
    if np.any(np.bitwise_count(snapshot) != draw_size):
        raise ValueError("each draw mask must contain exactly draw_size numbers")
    if np.unique(snapshot).size != expected:
        raise ValueError("draws must contain every main-draw combination exactly once (unique)")
    # All entries are legal subsets. Exactly C(n, k) distinct entries proves
    # completeness, regardless of their order.
    return _CompleteDrawMasks.from_complete_buffer(buffer, pool_size, draw_size)


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
    Python-level loop over all ``C(pool_size, draw_size)`` draws. The returned
    ndarray has immutable backing storage and can be reused without validation.
    """

    _check_draw_parameters(pool_size, draw_size)
    numbers = range(1, pool_size + 1)
    if draw_size < 3:
        draws = np.array(
            [ticket_mask(draw) for draw in itertools.combinations(numbers, draw_size)],
            dtype=np.uint64,
        )
        return _CompleteDrawMasks.from_complete_buffer(draws.tobytes(), pool_size, draw_size)

    rest = tuple(itertools.combinations(numbers, draw_size - 2))
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
            tail = rest_masks[int(first_index_with_minimum[high + 1]) :]
            draws[position : position + tail.size] = tail | np.uint64(ticket_mask((low, high)))
            position += tail.size
    if position != draws.size:
        raise AssertionError("draw-space construction did not fill C(pool_size, draw_size)")
    return _CompleteDrawMasks.from_complete_buffer(draws.tobytes(), pool_size, draw_size)


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
    from :func:`all_main_draw_masks` or :func:`validate_main_draw_masks` to reuse
    one immutable draw space across portfolios. Other arrays are fully validated
    and snapshotted on each call; the source array is never cached as trusted.
    """

    if not portfolio:
        raise ValueError("portfolio must contain at least one ticket")
    if not 1 <= outright_matches <= draw_size:
        raise ValueError("outright_matches must be within 1..draw_size")
    masks: list[np.uint64] = []
    for ticket in portfolio:
        if (
            len(ticket) != draw_size
            or len(set(ticket)) != draw_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError(f"illegal ticket: {tuple(ticket)}")
        masks.append(np.uint64(ticket_mask(ticket)))
    if draws is None:
        draws = all_main_draw_masks(pool_size, draw_size)
    draws = validate_main_draw_masks(draws, pool_size, draw_size)
    # Strip the ndarray subclass once, keeping the scoring loop unchanged.
    draws = np.asarray(draws)

    special_count = pool_size - draw_size
    rescue_matches = outright_matches - 1
    zero = np.uint64(0)
    m3_plus = 0
    rescued_specials = 0
    for start in range(0, draws.size, chunk_size):
        chunk = draws[start : start + chunk_size]
        won = np.zeros(chunk.size, dtype=np.bool_)
        rescue = np.zeros(chunk.size, dtype=np.uint64)
        for mask in masks:
            hits = np.bitwise_count(chunk & mask)
            won |= hits >= outright_matches
            # (a & ~D) | (b & ~D) == (a | b) & ~D: OR the tickets, strip D once below.
            rescue |= np.where(hits == rescue_matches, mask, zero)
        rescue &= ~chunk
        m3_plus += int(np.count_nonzero(won))
        rescued_specials += int(np.bitwise_count(rescue[~won]).sum(dtype=np.int64))
    return ExactPortfolioProbability(
        main_draw_count=int(draws.size),
        special_count=special_count,
        m3_plus_draw_count=m3_plus,
        official_any_prize_outcome_count=m3_plus * special_count + rescued_specials,
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
    "ExactPortfolioProbability",
    "all_main_draw_masks",
    "evaluate_portfolio",
    "evaluate_single_ticket_closed_form",
    "independent_random_official_any_prize",
    "ticket_mask",
    "validate_main_draw_masks",
]
