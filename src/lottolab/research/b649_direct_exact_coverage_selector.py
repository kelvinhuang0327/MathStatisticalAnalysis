"""Frozen B649 direct exact-success coverage selector, version 1.

The selector optimises the repository's canonical exact OFFICIAL_ANY_PRIZE
outcome count (``b649_official_any_prize_exact``) directly, instead of an
overlap or diversity proxy. It never sees a draw result: its only inputs are an
already ordered pool of legal tickets and the budget ``k``.

Stage A -- exact greedy marginal coverage. For step ``1..k`` every ticket not yet
chosen is scored by its exact marginal gain ``N(S + t) - N(S)`` over the whole
outcome space; the largest gain wins and ties go to the earliest pool position.
All tickets tie at step 1, so the first pick is always pool position 1.

Stage B -- bounded exact swap improvement. At most ``MAX_ACCEPTED_SWAPS`` times,
every one-ticket replacement of the current set by an unchosen pool ticket is
scored exactly. Only a strict improvement is accepted, and the best one wins;
ties go to the lexicographically smallest resulting ascending rank vector.
The result is therefore never worse than its own greedy initialisation. A
strict swap local optimum is certified only when a complete scan finds no
improvement inside the bound; otherwise ``local_optimum_certified`` is False.

Marginal gains come from per-draw incremental state that mirrors the loop body
of ``evaluate_portfolio`` (outright win flag plus the union of near-miss
tickets, special ball collapsed analytically). That engine is never authority:
every accepted state is re-counted by the canonical evaluator and any
disagreement raises. No global optimum and no predictive advantage is claimed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, cast

import numpy as np
import numpy.typing as npt

from lottolab.research import b649_official_any_prize_exact as exact

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type RankVector = tuple[int, ...]

METHOD_ID: Final = "B649_DIRECT_EXACT_SUCCESS_COVERAGE_SELECTOR"
METHOD_VERSION: Final = "1.0.0"
CANDIDATE_ID: Final = "B649_DIRECT_EXACT_SUCCESS_COVERAGE_SELECTOR_V1"
LOTTERY: Final = "BIG_LOTTO"
PRIMARY_OBJECTIVE: Final = "OFFICIAL_ANY_PRIZE_EXACT"
PRIMARY_K: Final = 10
SECONDARY_K: Final = 20
SUPPORTED_K: Final = (PRIMARY_K, SECONDARY_K)
MAX_ACCEPTED_SWAPS: Final = 2
GREEDY_TIE_BREAK: Final = "EARLIEST_POOL_POSITION"
SWAP_TIE_BREAK: Final = "LEXICOGRAPHICALLY_SMALLEST_RESULTING_ASCENDING_RANK_VECTOR"
_CHUNK_SIZE: Final = 1 << 20


@dataclass(frozen=True, slots=True)
class DrawSpace:
    """Generic draw space; the frozen candidate only ever uses BIG_LOTTO."""

    pool_size: int
    draw_size: int
    outright_matches: int

    @property
    def special_count(self) -> int:
        return self.pool_size - self.draw_size


BIG_LOTTO_SPACE: Final = DrawSpace(
    exact.BIG_LOTTO_POOL_SIZE, exact.BIG_LOTTO_DRAW_SIZE, exact.BIG_LOTTO_OUTRIGHT_MATCHES
)


@dataclass(frozen=True, slots=True)
class AcceptedSwap:
    outgoing_rank: int
    incoming_rank: int
    resulting_ranks: RankVector
    previous_outcome_count: int
    resulting_outcome_count: int


@dataclass(frozen=True, slots=True)
class DirectExactCoverageSelection:
    ordered_candidate_pool: Portfolio
    k: int
    space: DrawSpace
    greedy_pick_order: RankVector
    greedy_marginal_gains: tuple[int, ...]
    greedy_ranks: RankVector
    greedy_probability: exact.ExactPortfolioProbability
    swaps: tuple[AcceptedSwap, ...]
    final_ranks: RankVector
    final_probability: exact.ExactPortfolioProbability
    local_optimum_certified: bool
    candidate_gain_evaluations: int
    canonical_evaluations: int

    @property
    def tickets(self) -> Portfolio:
        return tuple(self.ordered_candidate_pool[rank - 1] for rank in self.final_ranks)

    @property
    def greedy_tickets(self) -> Portfolio:
        return tuple(self.ordered_candidate_pool[rank - 1] for rank in self.greedy_ranks)

    @property
    def absolute_probability_delta(self) -> Fraction:
        return (
            self.final_probability.official_any_prize - self.greedy_probability.official_any_prize
        )


class _CoverageState:
    """Per-draw state after some tickets: outright-win flag and near-miss union."""

    __slots__ = ("rescue", "won")

    def __init__(self, draw_count: int) -> None:
        self.won: npt.NDArray[np.bool_] = np.zeros(draw_count, dtype=np.bool_)
        self.rescue: npt.NDArray[np.uint64] = np.zeros(draw_count, dtype=np.uint64)


def _fold(state: _CoverageState, draws: exact.DrawMasks, mask: int, space: DrawSpace) -> None:
    """Add one ticket to ``state`` (the loop body of ``evaluate_portfolio``)."""

    ticket = np.uint64(mask)
    zero = np.uint64(0)
    rescue_hits = space.outright_matches - 1
    for start in range(0, draws.size, _CHUNK_SIZE):
        chunk = draws[start : start + _CHUNK_SIZE]
        hits = np.bitwise_count(chunk & ticket)
        state.won[start : start + chunk.size] |= hits >= space.outright_matches
        state.rescue[start : start + chunk.size] |= np.where(hits == rescue_hits, ticket, zero)


def _outcome_count(state: _CoverageState, draws: exact.DrawMasks, space: DrawSpace) -> int:
    wins = 0
    rescued = 0
    for start in range(0, draws.size, _CHUNK_SIZE):
        chunk = draws[start : start + _CHUNK_SIZE]
        won = state.won[start : start + chunk.size]
        rescue = state.rescue[start : start + chunk.size] & ~chunk
        wins += int(np.count_nonzero(won))
        rescued += int(np.bitwise_count(rescue[~won]).sum(dtype=np.int64))
    return wins * space.special_count + rescued


def _marginal_gains(
    state: _CoverageState,
    draws: exact.DrawMasks,
    masks: Sequence[int],
    space: DrawSpace,
) -> list[int]:
    """Exact ``N(S + t) - N(S)`` for every ticket mask, without mutating ``state``."""

    rescue_hits = space.outright_matches - 1
    gains = [0] * len(masks)
    for start in range(0, draws.size, _CHUNK_SIZE):
        chunk = draws[start : start + _CHUNK_SIZE]
        is_open = ~state.won[start : start + chunk.size]
        open_draws = chunk[is_open]
        open_rescue = state.rescue[start : start + chunk.size][is_open]
        # Specials still unwon on an open draw if a new ticket wins it outright.
        unwon_specials = space.special_count - np.bitwise_count(open_rescue & ~open_draws).astype(
            np.int64
        )
        for index, mask in enumerate(masks):
            ticket = np.uint64(mask)
            hits = np.bitwise_count(open_draws & ticket)
            gain = int(unwon_specials[hits >= space.outright_matches].sum(dtype=np.int64))
            near = hits == rescue_hits
            gain += int(
                np.bitwise_count(ticket & ~open_draws[near] & ~open_rescue[near]).sum(
                    dtype=np.int64
                )
            )
            gains[index] += gain
    return gains


def _validated_pool(
    ordered_candidate_pool: object, k: int, space: DrawSpace, supported_k: Sequence[int] | None
) -> Portfolio:
    if type(k) is not int or k < 1 or (supported_k is not None and k not in supported_k):
        raise ValueError(
            f"k must be one of {tuple(supported_k)}" if supported_k else "k must be >= 1"
        )
    if not isinstance(ordered_candidate_pool, Sequence) or isinstance(
        ordered_candidate_pool, (str, bytes)
    ):
        raise ValueError("candidate pool must be an ordered sequence of tickets")
    pool: list[Ticket] = []
    for raw in cast(Sequence[object], ordered_candidate_pool):
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ValueError("each candidate must be a sequence of integers")
        numbers = cast(Sequence[object], raw)
        if len(numbers) != space.draw_size or any(
            type(number) is not int or not 1 <= number <= space.pool_size for number in numbers
        ):
            raise ValueError(
                f"each candidate must contain {space.draw_size} integers in 1..{space.pool_size}"
            )
        ticket = tuple(sorted(cast(Sequence[int], numbers)))
        if len(set(ticket)) != space.draw_size:
            raise ValueError("candidate numbers must be distinct")
        pool.append(ticket)
    if len(set(pool)) != len(pool):
        raise ValueError("candidate tickets must be distinct; the pool is never deduplicated")
    if len(pool) < k:
        raise ValueError("candidate pool must contain at least k distinct tickets")
    return tuple(pool)


def run_direct_exact_coverage_search(
    ordered_candidate_pool: Sequence[Sequence[int]],
    k: int,
    *,
    space: DrawSpace = BIG_LOTTO_SPACE,
    max_accepted_swaps: int = MAX_ACCEPTED_SWAPS,
) -> DirectExactCoverageSelection:
    """Generic engine behind the frozen candidate; a test and diagnostic surface.

    The frozen candidate is :func:`select_direct_exact_coverage`, which fixes the
    draw space, the supported budgets and the swap bound.
    """

    pool = _validated_pool(ordered_candidate_pool, k, space, None)
    if type(max_accepted_swaps) is not int or max_accepted_swaps < 0:
        raise ValueError("max_accepted_swaps must be a non-negative integer")
    masks = [exact.ticket_mask(ticket) for ticket in pool]
    draws = exact.all_main_draw_masks(space.pool_size, space.draw_size)
    gain_evaluations = 0
    canonical_evaluations = 0

    def canonical(positions: Sequence[int]) -> exact.ExactPortfolioProbability:
        nonlocal canonical_evaluations
        canonical_evaluations += 1
        return exact.evaluate_portfolio(
            tuple(pool[position] for position in positions),
            pool_size=space.pool_size,
            draw_size=space.draw_size,
            outright_matches=space.outright_matches,
            draws=draws,
        )

    def require_canonical_count(
        positions: Sequence[int], count: int
    ) -> exact.ExactPortfolioProbability:
        probability = canonical(positions)
        if probability.official_any_prize_outcome_count != count:
            raise AssertionError(
                "incremental coverage engine disagrees with the canonical evaluator"
            )
        return probability

    # Stage A: exact greedy marginal coverage.
    state = _CoverageState(draws.size)
    chosen: list[int] = []
    gains_taken: list[int] = []
    count = 0
    for _ in range(k):
        remaining = [position for position in range(len(pool)) if position not in chosen]
        gains = _marginal_gains(state, draws, [masks[position] for position in remaining], space)
        gain_evaluations += len(remaining)
        best = max(gains)
        pick = remaining[gains.index(best)]
        _fold(state, draws, masks[pick], space)
        chosen.append(pick)
        gains_taken.append(best)
        count += best
        require_canonical_count(chosen, count)
    greedy_positions = tuple(sorted(chosen))
    greedy_probability = require_canonical_count(greedy_positions, count)

    # Stage B: bounded exact best-improvement swaps.
    current = list(greedy_positions)
    swaps: list[AcceptedSwap] = []
    certified = False
    while len(swaps) < max_accepted_swaps:
        best_move: tuple[int, RankVector, int, int] | None = None
        for slot, outgoing in enumerate(current):
            kept = current[:slot] + current[slot + 1 :]
            kept_state = _CoverageState(draws.size)
            for position in kept:
                _fold(kept_state, draws, masks[position], space)
            kept_count = _outcome_count(kept_state, draws, space)
            incoming_pool = [position for position in range(len(pool)) if position not in current]
            gains = _marginal_gains(
                kept_state, draws, [masks[position] for position in incoming_pool], space
            )
            gain_evaluations += len(incoming_pool)
            for incoming, gain in zip(incoming_pool, gains, strict=True):
                if kept_count + gain <= count:
                    continue
                ranks = tuple(sorted(position + 1 for position in (*kept, incoming)))
                key = (-(kept_count + gain), ranks, outgoing + 1, incoming + 1)
                if best_move is None or key < best_move:
                    best_move = key
        if best_move is None:
            certified = True
            break
        negative_count, ranks, outgoing_rank, incoming_rank = best_move
        current = [rank - 1 for rank in ranks]
        require_canonical_count(current, -negative_count)
        swaps.append(AcceptedSwap(outgoing_rank, incoming_rank, ranks, count, -negative_count))
        count = -negative_count

    final_probability = greedy_probability if not swaps else canonical(current)
    if final_probability.official_any_prize_outcome_count != count:
        raise AssertionError("final coverage count disagrees with the canonical evaluator")
    return DirectExactCoverageSelection(
        ordered_candidate_pool=pool,
        k=k,
        space=space,
        greedy_pick_order=tuple(position + 1 for position in chosen),
        greedy_marginal_gains=tuple(gains_taken),
        greedy_ranks=tuple(position + 1 for position in greedy_positions),
        greedy_probability=greedy_probability,
        swaps=tuple(swaps),
        final_ranks=tuple(position + 1 for position in current),
        final_probability=final_probability,
        local_optimum_certified=certified,
        candidate_gain_evaluations=gain_evaluations,
        canonical_evaluations=canonical_evaluations,
    )


def select_direct_exact_coverage(
    ordered_candidate_pool: Sequence[Sequence[int]], k: int
) -> DirectExactCoverageSelection:
    """The frozen BIG_LOTTO candidate for ``k`` in {10, 20}.

    Numbers within each ticket are normalised; pool order is never changed.
    Invalid or duplicate tickets fail rather than being silently repaired.

    Complexity, for pool size ``P`` and budget ``k``: Stage A performs
    ``sum_{j<k}(P - j)`` marginal-gain evaluations and Stage B at most
    ``MAX_ACCEPTED_SWAPS * k * (P - k)``; each evaluation is one pass over the
    ``C(49, 6) = 13,983,816`` main draws. The canonical evaluator is called
    once per accepted state (``k`` greedy steps plus one per swap, plus the
    final portfolio).
    """

    _validated_pool(ordered_candidate_pool, k, BIG_LOTTO_SPACE, SUPPORTED_K)
    return run_direct_exact_coverage_search(ordered_candidate_pool, k)


__all__ = [
    "BIG_LOTTO_SPACE",
    "CANDIDATE_ID",
    "GREEDY_TIE_BREAK",
    "LOTTERY",
    "MAX_ACCEPTED_SWAPS",
    "METHOD_ID",
    "METHOD_VERSION",
    "PRIMARY_K",
    "PRIMARY_OBJECTIVE",
    "SECONDARY_K",
    "SUPPORTED_K",
    "SWAP_TIE_BREAK",
    "AcceptedSwap",
    "DirectExactCoverageSelection",
    "DrawSpace",
    "run_direct_exact_coverage_search",
    "select_direct_exact_coverage",
]
