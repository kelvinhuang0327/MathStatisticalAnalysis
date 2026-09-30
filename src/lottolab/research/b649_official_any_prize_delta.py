"""Exact cached add/remove/replace probes for OFFICIAL_ANY_PRIZE portfolios.

Each ticket's main-win and special-rescue classifications are cached as two
packed bits per main draw. The cache belongs to an immutable snapshot of the
draw space and this evaluator's objective parameters. Candidate results are
reduced with the canonical evaluator's exact main-win and rescue-union rules;
no sampling or approximate score is used.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    ticket_mask,
)

_BITS_PER_BYTE = 8
_CACHE_BUILD_CHUNK_SIZE = 1 << 20


class ExactPortfolioDeltaEvaluator:
    """Evaluate exact one-ticket portfolio edits while caching ticket outcomes.

    The draw array is copied once into an immutable byte-backed snapshot. This
    binds every cached ticket classification to the exact draw space and
    objective parameters used to build it, even if the caller later mutates the
    array originally passed as draws.
    """

    def __init__(
        self,
        *,
        pool_size: int = BIG_LOTTO_POOL_SIZE,
        draw_size: int = BIG_LOTTO_DRAW_SIZE,
        outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
        draws: DrawMasks | None = None,
        chunk_size: int = 1 << 21,
    ) -> None:
        if type(pool_size) is not int or not 1 <= pool_size <= 64:
            raise ValueError("pool_size must be an integer within 1..64")
        if type(draw_size) is not int or not 1 <= draw_size < pool_size:
            raise ValueError("draw_size must be an integer within 1..pool_size-1")
        if (
            type(outright_matches) is not int
            or not 1 <= outright_matches <= draw_size
        ):
            raise ValueError("outright_matches must be an integer within 1..draw_size")
        if type(chunk_size) is not int or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")

        source_draws = (
            all_main_draw_masks(pool_size, draw_size)
            if draws is None
            else np.asarray(draws)
        )
        if source_draws.dtype != np.dtype(np.uint64) or source_draws.ndim != 1:
            raise ValueError("draws must be a one-dimensional uint64 array")
        if source_draws.size != comb(pool_size, draw_size):
            raise ValueError("draws must be the complete main-draw space")

        immutable_draw_bytes = source_draws.tobytes()
        self._draws: DrawMasks = np.frombuffer(immutable_draw_bytes, dtype=np.uint64)
        self._pool_size = pool_size
        self._draw_size = draw_size
        self._outright_matches = outright_matches
        self._chunk_size = chunk_size
        self._ticket_outcomes: dict[
            int, tuple[npt.NDArray[np.uint8], npt.NDArray[np.uint8]]
        ] = {}

    @property
    def draws(self) -> DrawMasks:
        """The evaluator's immutable draw-space snapshot."""

        return self._draws

    @property
    def cached_ticket_count(self) -> int:
        """Number of ticket masks whose exact draw classifications are cached."""

        return len(self._ticket_outcomes)

    def evaluate(self, portfolio: Sequence[Sequence[int]]) -> ExactPortfolioProbability:
        """Return the exact canonical result for portfolio."""

        return self._evaluate_masks(self._portfolio_masks(portfolio))

    def add(
        self, portfolio: Sequence[Sequence[int]], ticket: Sequence[int]
    ) -> ExactPortfolioProbability:
        """Return the exact result after adding one ticket."""

        masks = self._portfolio_masks(portfolio)
        return self._evaluate_masks((*masks, self._ticket_mask(ticket)))

    def remove(
        self, portfolio: Sequence[Sequence[int]], ticket: Sequence[int]
    ) -> ExactPortfolioProbability:
        """Return the exact result after removing one matching ticket occurrence."""

        masks = list(self._portfolio_masks(portfolio))
        mask = self._ticket_mask(ticket)
        try:
            masks.remove(mask)
        except ValueError as error:
            raise ValueError("ticket to remove is not present in portfolio") from error
        if not masks:
            raise ValueError("portfolio must contain at least one ticket after removal")
        return self._evaluate_masks(tuple(masks))

    def replace(
        self,
        portfolio: Sequence[Sequence[int]],
        old_ticket: Sequence[int],
        new_ticket: Sequence[int],
    ) -> ExactPortfolioProbability:
        """Return the exact result after replacing one matching ticket occurrence."""

        masks = list(self._portfolio_masks(portfolio))
        old_mask = self._ticket_mask(old_ticket)
        new_mask = self._ticket_mask(new_ticket)
        try:
            old_index = masks.index(old_mask)
        except ValueError as error:
            raise ValueError("ticket to replace is not present in portfolio") from error
        masks[old_index] = new_mask
        return self._evaluate_masks(tuple(masks))

    def _ticket_mask(self, ticket: Sequence[int]) -> int:
        if (
            len(ticket) != self._draw_size
            or len(set(ticket)) != self._draw_size
            or any(
                type(number) is not int or not 1 <= number <= self._pool_size
                for number in ticket
            )
        ):
            raise ValueError(f"illegal ticket: {tuple(ticket)}")
        return ticket_mask(ticket)

    def _portfolio_masks(self, portfolio: Sequence[Sequence[int]]) -> tuple[int, ...]:
        if not portfolio:
            raise ValueError("portfolio must contain at least one ticket")
        return tuple(self._ticket_mask(ticket) for ticket in portfolio)

    def _outcomes_for_ticket(
        self, mask: int
    ) -> tuple[npt.NDArray[np.uint8], npt.NDArray[np.uint8]]:
        cached = self._ticket_outcomes.get(mask)
        if cached is not None:
            return cached

        packed_size = (self._draws.size + 7) // _BITS_PER_BYTE
        packed_wins = np.empty(packed_size, dtype=np.uint8)
        packed_rescues = np.empty(packed_size, dtype=np.uint8)
        rescue_matches = self._outright_matches - 1
        build_chunk_size = max(
            _BITS_PER_BYTE,
            (_CACHE_BUILD_CHUNK_SIZE // _BITS_PER_BYTE) * _BITS_PER_BYTE,
        )
        ticket_bits = np.uint64(mask)
        for start in range(0, self._draws.size, build_chunk_size):
            stop = min(start + build_chunk_size, self._draws.size)
            hits = np.bitwise_count(self._draws[start:stop] & ticket_bits)
            output_slice = slice(start // _BITS_PER_BYTE, (stop + 7) // _BITS_PER_BYTE)
            packed_wins[output_slice] = np.packbits(
                hits >= self._outright_matches, bitorder="little"
            )
            packed_rescues[output_slice] = np.packbits(
                hits == rescue_matches, bitorder="little"
            )

        outcomes = packed_wins, packed_rescues
        self._ticket_outcomes[mask] = outcomes
        return outcomes

    @staticmethod
    def _unpack_outcomes(
        packed: npt.NDArray[np.uint8], start: int, stop: int
    ) -> npt.NDArray[np.uint8]:
        byte_start = start // _BITS_PER_BYTE
        byte_stop = (stop + _BITS_PER_BYTE - 1) // _BITS_PER_BYTE
        offset = start % _BITS_PER_BYTE
        unpacked = np.unpackbits(packed[byte_start:byte_stop], bitorder="little")
        return unpacked[offset : offset + stop - start]

    def _evaluate_masks(self, masks: tuple[int, ...]) -> ExactPortfolioProbability:
        if not masks:
            raise ValueError("portfolio must contain at least one ticket")

        packed_outcomes = tuple(
            (mask, *self._outcomes_for_ticket(mask)) for mask in masks
        )
        packed_wins = np.zeros((self._draws.size + 7) // _BITS_PER_BYTE, dtype=np.uint8)
        for _, ticket_wins, _ in packed_outcomes:
            packed_wins |= ticket_wins

        main_win_draw_count = 0
        rescued_special_count = 0
        zero = np.uint64(0)
        for start in range(0, self._draws.size, self._chunk_size):
            stop = min(start + self._chunk_size, self._draws.size)
            chunk = self._draws[start:stop]
            won = self._unpack_outcomes(packed_wins, start, stop) != 0
            rescue_union = np.zeros(chunk.size, dtype=np.uint64)
            for mask, _, packed_rescues in packed_outcomes:
                rescue_union |= np.where(
                    self._unpack_outcomes(packed_rescues, start, stop) != 0,
                    np.uint64(mask),
                    zero,
                )
            rescue_union &= ~chunk
            main_win_draw_count += int(np.count_nonzero(won))
            rescued_special_count += int(
                np.bitwise_count(rescue_union[~won]).sum(dtype=np.int64)
            )

        special_count = self._pool_size - self._draw_size
        return ExactPortfolioProbability(
            main_draw_count=int(self._draws.size),
            special_count=special_count,
            m3_plus_draw_count=main_win_draw_count,
            official_any_prize_outcome_count=(
                main_win_draw_count * special_count + rescued_special_count
            ),
        )


__all__ = ["ExactPortfolioDeltaEvaluator"]
