"""Bounded incremental cache for deterministic B649 walk-forward statistics.

The cache stores only the occurrence counts and trailing gaps used by the
existing multiscale omission-pressure candidate. It never caches candidate
tickets, evaluation records, or strategy callback results, and it has no RNG
dependency. Callers with mutable, stochastic, or otherwise incompatible
history semantics should keep using the original uncached evaluator.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations

from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _multiscale,
)

type HistoryDraw = tuple[int, int, int, int, int, int]

STATISTIC_SEMANTIC_ID = "B649_MAIN_OCCURRENCE_AND_CURRENT_GAP_V1"
_PREFIX_DIGEST_DOMAIN = b"lottolab:b649-walkforward-prefix:v1\0"
_NUMBER_COUNT = _multiscale.NUMBER_DOMAIN[1] - _multiscale.NUMBER_DOMAIN[0] + 1


class B649WalkForwardCacheError(ValueError):
    """Invalid immutable history or cache request."""


@dataclass(frozen=True, slots=True)
class B649WalkForwardHistory:
    """Immutable, content-identified history snapshot in oldest-first order.

    ``source_identity`` identifies the upstream dataset/source generation.
    Prefix digests additionally bind each cache entry to the exact rows used
    before its cutoff, so reusing a source label after a correction is safe.
    """

    source_identity: str
    draws: tuple[HistoryDraw, ...]
    _prefix_digests: tuple[bytes, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.source_identity) is not str or not self.source_identity.strip():
            raise B649WalkForwardCacheError(
                "source_identity must be a non-empty string"
            )
        if type(self.draws) is not tuple:
            raise B649WalkForwardCacheError("draws must be an immutable tuple")

        digest = hashlib.sha256(_PREFIX_DIGEST_DOMAIN).digest()
        prefix_digests = [digest]
        for draw_index, draw in enumerate(self.draws):
            if type(draw) is not tuple or len(draw) != _multiscale.PICK_COUNT:
                raise B649WalkForwardCacheError(
                    f"history[{draw_index}] must contain exactly six numbers"
                )
            if any(type(number) is not int for number in draw):
                raise B649WalkForwardCacheError(
                    f"history[{draw_index}] must contain exact integers"
                )
            if any(
                not _multiscale.NUMBER_DOMAIN[0]
                <= number
                <= _multiscale.NUMBER_DOMAIN[1]
                for number in draw
            ):
                raise B649WalkForwardCacheError(
                    f"history[{draw_index}] numbers must be in 1..49"
                )
            if len(set(draw)) != _multiscale.PICK_COUNT:
                raise B649WalkForwardCacheError(
                    f"history[{draw_index}] must contain six unique numbers"
                )
            digest = hashlib.sha256(digest + bytes(draw)).digest()
            prefix_digests.append(digest)

        object.__setattr__(self, "_prefix_digests", tuple(prefix_digests))

    @classmethod
    def from_draws(
        cls,
        source_identity: str,
        draws: Sequence[Sequence[int]],
    ) -> B649WalkForwardHistory:
        """Copy a concrete sequence into a validated immutable snapshot."""

        if not isinstance(draws, Sequence):
            raise B649WalkForwardCacheError(
                "draws must be a concrete sequence; lazy iterables use the safe path"
            )
        normalized: list[HistoryDraw] = []
        for draw_index, raw_draw in enumerate(draws):
            if type(raw_draw) not in (tuple, list):
                raise B649WalkForwardCacheError(
                    f"history[{draw_index}] must be a tuple or list"
                )
            normalized.append(tuple(raw_draw))  # type: ignore[arg-type]
        return cls(source_identity, tuple(normalized))

    def prefix_digest(self, cutoff_index: int) -> bytes:
        """Fingerprint rows ``[0, cutoff_index)``; later draws are excluded."""

        if type(cutoff_index) is not int or not 0 <= cutoff_index <= len(self.draws):
            raise B649WalkForwardCacheError(
                "cutoff_index must be an integer within the history length"
            )
        return self._prefix_digests[cutoff_index]


@dataclass(frozen=True, slots=True)
class B649WalkForwardWindowStatistics:
    """Exact integer occurrence and trailing-gap statistics for one window."""

    cutoff_index: int
    window: int
    history_draw_count: int
    occurrence_counts: tuple[int, ...]
    current_gaps: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class B649WalkForwardCacheInfo:
    hits: int
    misses: int
    entries: int
    incremental_draw_updates: int


@dataclass(slots=True)
class _WindowState:
    cutoff_index: int
    prefix_digest: bytes
    rows: deque[HistoryDraw]
    positions_by_number: list[deque[int]]


class B649WalkForwardIncrementalCache:
    """Reuse pure window statistics and increment them across adjacent cutoffs.

    The result LRU and the rolling states are each bounded by ``max_entries``.
    Keys include source identity, statistic semantics, window, exclusive
    cutoff, and a digest of exactly the strictly-prior prefix.
    """

    def __init__(self, *, max_entries: int = 4096) -> None:
        if type(max_entries) is not int or max_entries < 1:
            raise B649WalkForwardCacheError("max_entries must be a positive integer")
        self._max_entries = max_entries
        self._results: OrderedDict[
            tuple[str, str, int, int, bytes], B649WalkForwardWindowStatistics
        ] = OrderedDict()
        self._states: OrderedDict[tuple[str, str, int], _WindowState] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._incremental_draw_updates = 0

    @property
    def cache_info(self) -> B649WalkForwardCacheInfo:
        return B649WalkForwardCacheInfo(
            hits=self._hits,
            misses=self._misses,
            entries=len(self._results),
            incremental_draw_updates=self._incremental_draw_updates,
        )

    def get_window_statistics(
        self,
        history: B649WalkForwardHistory,
        cutoff_index: int,
        window: int,
        *,
        use_cache: bool = True,
    ) -> B649WalkForwardWindowStatistics:
        """Return statistics from draws strictly before ``cutoff_index``.

        ``use_cache=False`` is the explicit uncached route for consumers that
        cannot establish compatibility with this pure B649 statistic.
        """

        self._validate_request(history, cutoff_index, window, use_cache)
        if not use_cache:
            return _calculate_window_statistics(history, cutoff_index, window)

        prefix_digest = history.prefix_digest(cutoff_index)
        result_key = (
            history.source_identity,
            STATISTIC_SEMANTIC_ID,
            window,
            cutoff_index,
            prefix_digest,
        )
        cached = self._results.get(result_key)
        if cached is not None:
            self._results.move_to_end(result_key)
            self._hits += 1
            return cached

        self._misses += 1
        state_key = (history.source_identity, STATISTIC_SEMANTIC_ID, window)
        state = self._states.get(state_key)
        if (
            state is not None
            and state.cutoff_index <= cutoff_index
            and history.prefix_digest(state.cutoff_index) == state.prefix_digest
        ):
            for draw_index in range(state.cutoff_index, cutoff_index):
                self._append_draw(state, history.draws[draw_index], window)
                self._incremental_draw_updates += 1
            state.cutoff_index = cutoff_index
            state.prefix_digest = prefix_digest
        else:
            state = self._build_state(history, cutoff_index, window)
            self._states[state_key] = state

        self._states.move_to_end(state_key)
        while len(self._states) > self._max_entries:
            self._states.popitem(last=False)

        statistics = self._statistics_from_state(state, cutoff_index, window)
        self._results[result_key] = statistics
        self._results.move_to_end(result_key)
        while len(self._results) > self._max_entries:
            self._results.popitem(last=False)
        return statistics

    @staticmethod
    def _validate_request(
        history: B649WalkForwardHistory,
        cutoff_index: int,
        window: int,
        use_cache: bool,
    ) -> None:
        if type(history) is not B649WalkForwardHistory:
            raise B649WalkForwardCacheError(
                "history must be a validated B649WalkForwardHistory snapshot"
            )
        if type(cutoff_index) is not int or not 0 <= cutoff_index <= len(history.draws):
            raise ValueError("target_index must not exceed history length")
        if type(window) is not int or window < 1:
            raise ValueError("window must be a positive integer")
        if type(use_cache) is not bool:
            raise B649WalkForwardCacheError("use_cache must be a boolean")
        if cutoff_index < window:
            raise _multiscale.InsufficientHistoryError(
                f"window {window} requires at least {window} prior draws"
            )

    @staticmethod
    def _build_state(
        history: B649WalkForwardHistory,
        cutoff_index: int,
        window: int,
    ) -> _WindowState:
        first_index = cutoff_index - window
        state = _WindowState(
            cutoff_index=first_index,
            prefix_digest=history.prefix_digest(first_index),
            rows=deque(),
            positions_by_number=[deque() for _ in range(_NUMBER_COUNT)],
        )
        for draw_index in range(first_index, cutoff_index):
            B649WalkForwardIncrementalCache._append_draw(
                state, history.draws[draw_index], window
            )
        state.prefix_digest = history.prefix_digest(cutoff_index)
        return state

    @staticmethod
    def _append_draw(
        state: _WindowState,
        draw: HistoryDraw,
        window: int,
    ) -> None:
        if len(state.rows) == window:
            expired_draw = state.rows.popleft()
            for number in expired_draw:
                positions = state.positions_by_number[number - 1]
                if not positions:
                    raise AssertionError("rolling occurrence state is inconsistent")
                positions.popleft()

        draw_index = state.cutoff_index
        state.rows.append(draw)
        for number in draw:
            state.positions_by_number[number - 1].append(draw_index)
        state.cutoff_index += 1

    @staticmethod
    def _statistics_from_state(
        state: _WindowState,
        cutoff_index: int,
        window: int,
    ) -> B649WalkForwardWindowStatistics:
        occurrence_counts = tuple(
            len(positions) for positions in state.positions_by_number
        )
        current_gaps = tuple(
            cutoff_index - 1 - positions[-1] if positions else window
            for positions in state.positions_by_number
        )
        return B649WalkForwardWindowStatistics(
            cutoff_index=cutoff_index,
            window=window,
            history_draw_count=window,
            occurrence_counts=occurrence_counts,
            current_gaps=current_gaps,
        )


def _calculate_window_statistics(
    history: B649WalkForwardHistory,
    cutoff_index: int,
    window: int,
) -> B649WalkForwardWindowStatistics:
    """Uncached reference calculation over only the requested prior window."""

    start = cutoff_index - window
    window_draws = history.draws[start:cutoff_index]
    occurrences = _multiscale.calculate_occurrences(window_draws)
    gaps = _multiscale.calculate_current_gaps(window_draws)
    return B649WalkForwardWindowStatistics(
        cutoff_index=cutoff_index,
        window=window,
        history_draw_count=len(window_draws),
        occurrence_counts=occurrences,
        current_gaps=gaps,
    )


def _ranking_from_statistics(
    statistics: B649WalkForwardWindowStatistics,
) -> _multiscale.WindowRanking:
    window = statistics.window
    occurrences = statistics.occurrence_counts
    gaps = statistics.current_gaps
    recurrence_cycles = _multiscale.calculate_recurrence_cycles(occurrences, window)
    omission_pressures = _multiscale.calculate_omission_pressures(
        gaps, occurrences, window
    )
    ordered_numbers = tuple(
        sorted(
            range(
                _multiscale.NUMBER_DOMAIN[0],
                _multiscale.NUMBER_DOMAIN[1] + 1,
            ),
            key=lambda number: (
                -omission_pressures[number - 1],
                -gaps[number - 1],
                -occurrences[number - 1],
                number,
            ),
        )
    )
    positions = [0] * _NUMBER_COUNT
    normalized_ranks = [Fraction(0, 1)] * _NUMBER_COUNT
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)
    return _multiscale.WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=statistics.history_draw_count,
        OCCURRENCE_COUNTS=occurrences,
        CURRENT_GAPS=gaps,
        RECURRENCE_CYCLES=recurrence_cycles,
        OMISSION_PRESSURES=omission_pressures,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def calculate_window_rankings_cached(
    history: B649WalkForwardHistory | Sequence[object],
    target_index: int,
    cache: B649WalkForwardIncrementalCache | None,
    *,
    use_cache: bool = True,
) -> tuple[_multiscale.WindowRanking, ...]:
    """Build the existing three exact rankings, or use its raw safe path.

    Only a validated immutable snapshot plus an explicit cache opts into the
    accelerated path. Raw sequences, lazy histories, or ``use_cache=False``
    delegate directly to the unchanged original evaluator.
    """

    if (
        type(history) is not B649WalkForwardHistory
        or type(cache) is not B649WalkForwardIncrementalCache
        or not use_cache
    ):
        raw_history = history.draws if type(history) is B649WalkForwardHistory else history
        return _multiscale.calculate_window_rankings(raw_history, target_index)

    if type(target_index) is not int or target_index < 0:
        return _multiscale.calculate_window_rankings(history.draws, target_index)
    if target_index > len(history.draws):
        raise ValueError("target_index must not exceed history length")
    if target_index < _multiscale.MINIMUM_HISTORY:
        raise _multiscale.InsufficientHistoryError(
            f"insufficient history: target_index provides {target_index} prior draws; "
            f"at least {_multiscale.MINIMUM_HISTORY} are required"
        )

    rankings = tuple(
        _ranking_from_statistics(
            cache.get_window_statistics(history, target_index, window)
        )
        for window in _multiscale.OMISSION_WINDOWS
    )
    return rankings


def calculate_fused_number_ranking_cached(
    history: B649WalkForwardHistory | Sequence[object],
    target_index: int,
    cache: B649WalkForwardIncrementalCache | None,
    *,
    use_cache: bool = True,
) -> _multiscale.FusedNumberRanking:
    """Use the existing exact rank fusion over cached or raw window rankings."""

    rankings = calculate_window_rankings_cached(
        history, target_index, cache, use_cache=use_cache
    )
    return _multiscale.fuse_window_rankings(rankings)


def produce_source_ticket_universe_cached(
    history: B649WalkForwardHistory | Sequence[object],
    target_index: int,
    cache: B649WalkForwardIncrementalCache | None,
    *,
    use_cache: bool = True,
) -> _multiscale.TicketPortfolio:
    """Produce the same ordered 210-ticket source universe as the baseline."""

    if (
        type(history) is not B649WalkForwardHistory
        or type(cache) is not B649WalkForwardIncrementalCache
        or not use_cache
    ):
        raw_history = history.draws if type(history) is B649WalkForwardHistory else history
        return _multiscale.produce_source_ticket_universe(raw_history, target_index)

    top_numbers = calculate_fused_number_ranking_cached(
        history, target_index, cache
    ).TOP_NUMBERS
    if len(top_numbers) != _multiscale.TOP_NUMBER_COUNT:
        raise RuntimeError("fused ranking did not produce the configured top-number pool")
    tickets = tuple(
        tuple(
            sorted(top_numbers[position] for position in rank_positions)
        )
        for rank_positions in combinations(
            range(_multiscale.TOP_NUMBER_COUNT), _multiscale.PICK_COUNT
        )
    )
    if len(tickets) != _multiscale.SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError("source universe did not produce exactly 210 tickets")
    if len(set(tickets)) != len(tickets):
        raise RuntimeError("source universe produced duplicate tickets")
    return tickets


__all__ = [
    "STATISTIC_SEMANTIC_ID",
    "B649WalkForwardCacheError",
    "B649WalkForwardCacheInfo",
    "B649WalkForwardHistory",
    "B649WalkForwardIncrementalCache",
    "B649WalkForwardWindowStatistics",
    "calculate_fused_number_ranking_cached",
    "calculate_window_rankings_cached",
    "produce_source_ticket_universe_cached",
]
