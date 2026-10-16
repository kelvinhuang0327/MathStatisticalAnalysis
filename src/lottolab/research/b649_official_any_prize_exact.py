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
A caller-supplied draw space is used only after it is proven to be exactly that
set of draws (:class:`CompleteDrawSpace`); its length alone proves nothing.
"""

from __future__ import annotations

import itertools
import weakref
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


def _require_draw_shape(pool_size: int, draw_size: int) -> None:
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("draw space must satisfy 1 <= draw_size <= pool_size <= 64")


def all_main_draw_masks(pool_size: int, draw_size: int) -> DrawMasks:
    """Every ``draw_size``-subset of ``1..pool_size`` exactly once, as bitmasks.

    Built as (two smallest numbers) + (remaining subset whose minimum exceeds
    both), which is exhaustive and duplicate-free by construction and avoids a
    Python-level loop over all ``C(pool_size, draw_size)`` draws.
    """

    _require_draw_shape(pool_size, draw_size)
    numbers = range(1, pool_size + 1)
    if draw_size < 3:
        return np.array(
            [ticket_mask(draw) for draw in itertools.combinations(numbers, draw_size)],
            dtype=np.uint64,
        )

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
    return draws


def _verified_snapshot(draws: object, pool_size: int, draw_size: int) -> DrawMasks:
    """An immutable copy of ``draws`` once it is proven to be the complete main-draw space.

    ``C(pool_size, draw_size)`` distinct masks, each exactly ``draw_size`` bits of
    ``1..pool_size``, are every ``draw_size``-subset exactly once (pigeonhole), in any order.
    Nothing is repaired: any other input raises.
    """

    _require_draw_shape(pool_size, draw_size)
    array = cast("npt.NDArray[np.generic]", draws) if isinstance(draws, np.ndarray) else None
    if array is None or array.dtype != np.dtype(np.uint64):
        raise TypeError("draws must be a numpy.uint64 array of main-draw bitmasks")
    if array.ndim != 1:
        raise ValueError(f"draws must be one-dimensional, got shape {array.shape}")
    expected = comb(pool_size, draw_size)
    if array.size != expected:
        raise ValueError(
            f"draws must hold C({pool_size}, {draw_size}) = {expected} main draws, got {array.size}"
        )
    # Checks and evaluation read this bytes-backed copy, which numpy refuses to make writable,
    # so editing the caller's array afterwards cannot change what was proven.
    snapshot: DrawMasks = np.frombuffer(array.tobytes(), dtype=np.uint64)
    if np.any(snapshot & ~np.uint64((1 << pool_size) - 1)):
        raise ValueError(f"draws contain a number outside 1..{pool_size}")
    if np.any(np.bitwise_count(snapshot) != draw_size):
        raise ValueError(f"every draw must contain exactly {draw_size} numbers")
    ordered = np.sort(snapshot)
    if np.any(ordered[1:] == ordered[:-1]):
        raise ValueError("draws repeat a main draw, so they are not the complete main-draw space")
    return snapshot


@dataclass(frozen=True, slots=True, eq=False)
class CompleteDrawSpace:
    """A main-draw space proven complete once, for reuse across many portfolios.

    Construction validates ``masks`` and keeps its own immutable copy;
    :func:`evaluate_portfolio` then uses it without re-checking.
    """

    masks: DrawMasks
    pool_size: int = BIG_LOTTO_POOL_SIZE
    draw_size: int = BIG_LOTTO_DRAW_SIZE

    def __post_init__(self) -> None:
        snapshot = _verified_snapshot(self.masks, self.pool_size, self.draw_size)
        object.__setattr__(self, "masks", snapshot)

    def __reduce__(self) -> tuple[type[CompleteDrawSpace], tuple[DrawMasks, int, int]]:
        # Unpickling re-validates and re-freezes instead of restoring a writable array.
        return (CompleteDrawSpace, (self.masks, self.pool_size, self.draw_size))

    @classmethod
    def build(
        cls, pool_size: int = BIG_LOTTO_POOL_SIZE, draw_size: int = BIG_LOTTO_DRAW_SIZE
    ) -> CompleteDrawSpace:
        return cls(all_main_draw_masks(pool_size, draw_size), pool_size, draw_size)


# The last caller-owned ndarray that passed validation, with its snapshot. Reused only for that
# same live array while it still equals the snapshot exactly (one O(n) comparison, no sort), so
# an in-place edit forces full re-validation instead of inheriting the earlier verdict.
_last_verified_external: tuple[weakref.ReferenceType[DrawMasks], CompleteDrawSpace] | None = None


def _forget_verified_external(reference: weakref.ReferenceType[DrawMasks]) -> None:
    global _last_verified_external
    if _last_verified_external is not None and _last_verified_external[0] is reference:
        _last_verified_external = None


def _complete_draw_space(
    draws: CompleteDrawSpace | DrawMasks, pool_size: int, draw_size: int
) -> CompleteDrawSpace:
    global _last_verified_external
    if isinstance(draws, CompleteDrawSpace):
        if (draws.pool_size, draws.draw_size) != (pool_size, draw_size):
            raise ValueError(
                f"draw space is C({draws.pool_size}, {draws.draw_size}), "
                f"not C({pool_size}, {draw_size})"
            )
        return draws
    memo = _last_verified_external
    if memo is not None:
        reference, space = memo
        if (
            reference() is draws
            and (space.pool_size, space.draw_size) == (pool_size, draw_size)
            and draws.dtype == space.masks.dtype
            and np.array_equal(draws, space.masks)
        ):
            return space
    space = CompleteDrawSpace(draws, pool_size, draw_size)
    _last_verified_external = (weakref.ref(draws, _forget_verified_external), space)
    return space


def evaluate_portfolio(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
    draws: CompleteDrawSpace | DrawMasks | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> ExactPortfolioProbability:
    """Exact M3+ and OFFICIAL_ANY_PRIZE counts for one portfolio.

    Tickets must be ``draw_size`` distinct numbers in ``1..pool_size``. A
    repeated ticket is inert (success is a union over tickets). To reuse one
    draw space across portfolios pass a :class:`CompleteDrawSpace` (validated
    once), or a ``uint64`` mask array such as :func:`all_main_draw_masks`
    returns, which is validated on first use and then re-compared exactly on
    every call. Draws that are not every ``draw_size``-subset exactly once raise.
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
        space = all_main_draw_masks(pool_size, draw_size)
    else:
        space = _complete_draw_space(draws, pool_size, draw_size).masks

    special_count = pool_size - draw_size
    rescue_matches = outright_matches - 1
    zero = np.uint64(0)
    m3_plus = 0
    rescued_specials = 0
    for start in range(0, space.size, chunk_size):
        chunk = space[start : start + chunk_size]
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
        main_draw_count=int(space.size),
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
    "CompleteDrawSpace",
    "ExactPortfolioProbability",
    "all_main_draw_masks",
    "evaluate_portfolio",
    "evaluate_single_ticket_closed_form",
    "independent_random_official_any_prize",
    "ticket_mask",
]
