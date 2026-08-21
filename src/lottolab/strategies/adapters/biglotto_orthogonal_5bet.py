"""Target-native port of the frozen BIG_LOTTO Orthogonal 5-Bet donor.

The donor is ``tools/backtest_big_lotto_orthogonal_5bet.py`` at legacy commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (blob
``5721de1742a46add8c3103ea297510dac3ace451``, SHA-256
``c4dff46c5a5eff0621cdfba64a623c0a36ad365a4912355b90d3a9ad1c8a0df0``).
Its frozen SciPy/NumPy outputs and five positional tickets are retained in
source-grid Wave 46.

"Orthogonal" is the donor's concrete no-reuse construction, not a new
mathematical interpretation. Bets 1 and 2 are consecutive six-number chunks
of one descending Fourier period-alignment ranking. Bet 3 takes eligible
lag-2 echo numbers, then fills with the coldest trailing-100 numbers while
excluding bets 1 and 2. Bets 4 and 5 are consecutive hot-frequency chunks
from the numbers left after bets 1 through 3. The result is exactly five
ordered, pairwise-disjoint tickets (30 distinct numbers). There is no RNG,
database access, retry, or alternate predictor.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import bluestein_dft

_STRATEGY_ID = "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_FOURIER_WINDOW = 500
_FREQUENCY_WINDOW = 100
_POSITIVE_BIN_STOP = _FOURIER_WINDOW // 2
_NATIVE_TICKET_COUNT = 5
_NUMPY_126_SMALL_QUICKSORT = 15


@dataclass(frozen=True, slots=True)
class _FourierRankComponent:
    """Observable stages of one donor Fourier score."""

    appearance_series: tuple[float, ...]
    dominant_frequency_index: int | None
    dominant_amplitude: float
    rhythm_period: float | None
    last_hit_gap: int | None
    score: float


def _appearance_series(
    history: tuple[CausalDrawRow, ...],
    number: int,
) -> tuple[float, ...]:
    return tuple(1.0 if number in row.numbers else 0.0 for row in history[-_FOURIER_WINDOW:])


def _fourier_rank_component(
    history: tuple[CausalDrawRow, ...],
    number: int,
) -> _FourierRankComponent:
    """Port ``get_fourier_rank`` for one number without its database shell."""

    series = _appearance_series(history, number)
    appearance_count = sum(series)
    if appearance_count < 2:
        return _FourierRankComponent(
            appearance_series=series,
            dominant_frequency_index=None,
            dominant_amplitude=0.0,
            rhythm_period=None,
            last_hit_gap=None,
            score=0.0,
        )

    size = len(series)
    mean = appearance_count / size
    spectrum = bluestein_dft(tuple(value - mean for value in series))
    dominant_index = max(
        range(1, _POSITIVE_BIN_STOP),
        key=lambda index: (abs(spectrum[index]), -index),
    )
    amplitude = abs(spectrum[dominant_index])
    period = size / dominant_index
    last_hit = max(index for index, value in enumerate(series) if value)
    gap = (size - 1) - last_hit
    return _FourierRankComponent(
        appearance_series=series,
        dominant_frequency_index=dominant_index,
        dominant_amplitude=amplitude,
        rhythm_period=period,
        last_hit_gap=gap,
        score=1.0 / (abs(gap - period) + 1.0),
    )


def _fourier_scores(history: tuple[CausalDrawRow, ...]) -> tuple[float, ...]:
    """Return the donor's NumPy-shaped score vector, including index zero."""

    return (
        0.0,
        *(
            _fourier_rank_component(history, number).score
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        ),
    )


def _numpy_126_quicksort_argsort(values: tuple[float, ...]) -> tuple[int, ...]:
    """Reproduce NumPy 1.26's indirect quicksort for the donor's score vector.

    ``np.argsort`` defaults to an unstable indirect quicksort. Its ordering of
    equal scores is therefore part of the frozen donor's positional output and
    cannot be replaced by Python's stable sort. This is the corresponding
    median-of-three partition and small-range insertion sort over indices.
    """

    if not values or any(not math.isfinite(value) for value in values):
        raise InvalidOutput(f"{_STRATEGY_ID}: Fourier scores must be finite")

    indices = list(range(len(values)))
    if len(indices) < 2:
        return tuple(indices)

    stack: list[tuple[int, int]] = []
    left = 0
    right = len(indices) - 1
    while True:
        while right - left > _NUMPY_126_SMALL_QUICKSORT:
            middle = left + ((right - left) >> 1)
            if values[indices[middle]] < values[indices[left]]:
                indices[middle], indices[left] = indices[left], indices[middle]
            if values[indices[right]] < values[indices[middle]]:
                indices[right], indices[middle] = indices[middle], indices[right]
            if values[indices[middle]] < values[indices[left]]:
                indices[middle], indices[left] = indices[left], indices[middle]

            pivot = indices[middle]
            indices[middle] = indices[right - 1]
            indices[right - 1] = pivot
            low = left
            high = right - 1
            while True:
                low += 1
                while values[indices[low]] < values[pivot]:
                    low += 1
                high -= 1
                while values[pivot] < values[indices[high]]:
                    high -= 1
                if low >= high:
                    break
                indices[low], indices[high] = indices[high], indices[low]
            if low != right - 1:
                indices[low], indices[right - 1] = indices[right - 1], indices[low]

            if low - left < right - low:
                stack.append((low + 1, right))
                right = low - 1
            else:
                stack.append((left, low - 1))
                left = low + 1

        for current in range(left + 1, right + 1):
            pivot = indices[current]
            insertion = current
            while insertion > left and values[pivot] < values[indices[insertion - 1]]:
                indices[insertion] = indices[insertion - 1]
                insertion -= 1
            indices[insertion] = pivot

        if not stack:
            return tuple(indices)
        left, right = stack.pop()


def _fourier_rank(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    return tuple(reversed(_numpy_126_quicksort_argsort(_fourier_scores(history))))


def _tickets_from_rank(
    history: tuple[CausalDrawRow, ...],
    fourier_rank: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    """Apply the donor's five positional constructions to one frozen rank."""

    if len(fourier_rank) != _MAX_NUMBER + 1 or set(fourier_rank) != set(
        range(_MAX_NUMBER + 1)
    ):
        raise InvalidOutput(f"{_STRATEGY_ID}: Fourier rank must permute indices 0..49")

    first_start = 0
    while first_start < len(fourier_rank) and fourier_rank[first_start] == 0:
        first_start += 1
    bet1 = tuple(sorted(fourier_rank[first_start : first_start + _PICK_COUNT]))

    second_start = first_start + _PICK_COUNT
    while second_start < len(fourier_rank) and fourier_rank[second_start] == 0:
        second_start += 1
    bet2 = tuple(sorted(fourier_rank[second_start : second_start + _PICK_COUNT]))

    first_two_numbers = set(bet1) | set(bet2)
    echo_numbers = [
        number
        for number in history[-2].numbers
        if number <= _MAX_NUMBER and number not in first_two_numbers
    ]
    frequencies = Counter(
        number for row in history[-_FREQUENCY_WINDOW:] for number in row.numbers
    )
    cold_remainder = [
        number
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        if number not in first_two_numbers and number not in echo_numbers
    ]
    cold_remainder.sort(key=lambda number: frequencies.get(number, 0))
    bet3 = tuple(sorted((echo_numbers + cold_remainder)[:_PICK_COUNT]))

    used = first_two_numbers | set(bet3)
    hot_leftover = [
        number
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        if number not in used
    ]
    hot_leftover.sort(key=lambda number: frequencies.get(number, 0), reverse=True)
    bet4 = tuple(sorted(hot_leftover[:_PICK_COUNT]))
    bet5 = tuple(sorted(hot_leftover[_PICK_COUNT : 2 * _PICK_COUNT]))
    return bet1, bet2, bet3, bet4, bet5


def _orthogonal_5bet_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    return _tickets_from_rank(history, _fourier_rank(history))


def _validated_orthogonal_portfolio(
    tickets: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    """Fail closed if the donor's exact five-position no-reuse rule breaks."""

    if len(tickets) != _NATIVE_TICKET_COUNT:
        raise InvalidOutput(
            f"{_STRATEGY_ID}: expected {_NATIVE_TICKET_COUNT} positional tickets"
        )
    seen: set[int] = set()
    for position, ticket in enumerate(tickets, start=1):
        if (
            len(ticket) != _PICK_COUNT
            or len(set(ticket)) != _PICK_COUNT
            or any(number < _MIN_NUMBER or number > _MAX_NUMBER for number in ticket)
        ):
            raise InvalidOutput(f"{_STRATEGY_ID}: donor ticket {position} is invalid")
        if not seen.isdisjoint(ticket):
            raise InvalidOutput(
                f"{_STRATEGY_ID}: donor orthogonality failed at ticket {position}"
            )
        seen.update(ticket)
    if len(seen) != _NATIVE_TICKET_COUNT * _PICK_COUNT:
        raise InvalidOutput(f"{_STRATEGY_ID}: donor portfolio must use 30 distinct numbers")
    return tickets


class BigLottoOrthogonal5BetAdapter(PortfolioBetAdapter):
    """Deterministic five-position, pairwise-disjoint donor portfolio."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Orthogonal 5-Bet 正交 5注"
    strategy_version = "v0.1"
    min_history = _FOURIER_WINDOW
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_FOURIER_WINDOW:]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(f"{self.strategy_id}: causal draw identities must be unique")
        return _validated_orthogonal_portfolio(_orthogonal_5bet_tickets(history))


__all__ = ["BigLottoOrthogonal5BetAdapter"]
