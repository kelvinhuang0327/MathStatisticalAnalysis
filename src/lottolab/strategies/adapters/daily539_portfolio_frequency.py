"""Pure-Python DAILY_539 ports of the donor frequency portfolios.

The algorithms are ported from
``LotteryNewMeraged/lottery_api/models/p128_wave2_phase1_adapters.py`` without
importing or executing the donor package.  The native ticket order is frozen:

* ``midfreq_acb_2bet`` emits MidFreq, then ACB.
* ``midfreq_fourier_2bet`` emits MidFreq, then Fourier.

This module deliberately does not use :class:`PortfolioBetAdapter`: that shared
base currently validates the BigLotto 6-of-49 contract.  DAILY_539 validation
is kept local so this card does not change shared strategy infrastructure.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import ClassVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)

_POOL = 39
_PICK = 5
_MIN_HISTORY = 100
_MIDFREQ_WINDOW = 100
_ACB_WINDOW = 100
_FOURIER_WINDOW = 100


def _validated_daily539_numbers(numbers: object, strategy_id: str, context: str) -> tuple[int, ...]:
    """Validate one exact DAILY_539 number tuple without coercing values."""

    if type(numbers) is not tuple:
        raise InvalidOutput(f"{strategy_id}: {context} expected a number tuple")
    raw_numbers = cast(tuple[object, ...], numbers)
    if len(raw_numbers) != _PICK:
        raise InvalidOutput(
            f"{strategy_id}: {context} expected {_PICK} numbers, got {len(raw_numbers)}"
        )
    if not all(type(number) is int for number in raw_numbers):
        raise InvalidOutput(f"{strategy_id}: {context} numbers must be exact built-in integers")
    validated = cast(tuple[int, ...], raw_numbers)
    if not all(1 <= number <= _POOL for number in validated):
        raise InvalidOutput(f"{strategy_id}: {context} numbers out of range [1..{_POOL}]")
    if len(set(validated)) != _PICK:
        raise InvalidOutput(f"{strategy_id}: {context} duplicate numbers")
    return tuple(sorted(validated))


def _validated_daily539_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    """Validate and canonicalize immutable causal rows."""

    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    raw_rows = cast(tuple[object, ...], history)
    validated: list[CausalDrawRow] = []
    for index, candidate in enumerate(raw_rows):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        if type(row.draw) is not str or not row.draw:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} draw must be a non-empty string"
            )
        if type(row.date) is not str or not row.date:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} date must be a non-empty string"
            )
        validated.append(
            CausalDrawRow(
                draw=row.draw,
                date=row.date,
                numbers=_validated_daily539_numbers(
                    row.numbers, strategy_id, f"history row {index}"
                ),
            )
        )
    return tuple(validated)


def _recent(history: tuple[CausalDrawRow, ...], window: int) -> tuple[CausalDrawRow, ...]:
    return history[-window:] if len(history) >= window else history


def _top_n(scores: dict[int, float], count: int) -> tuple[int, ...]:
    """Rank by descending score, then donor-prescribed ascending number."""

    ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    return tuple(sorted(ranked[:count]))


def _midfreq_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port donor ``_d539_midfreq_scores`` with its 100-draw window."""

    recent = _recent(history, _MIDFREQ_WINDOW)
    draw_count = len(recent)
    expected = draw_count * _PICK / _POOL
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: -abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)}


def _acb_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port donor ``_d539_acb_scores`` with its 100-draw window."""

    recent = _recent(history, _ACB_WINDOW)
    draw_count = len(recent)
    probability = _PICK / _POOL
    expected = draw_count * probability
    variance = draw_count * probability * (1.0 - probability)
    sigma = variance**0.5 if variance > 0 else 1.0
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: (expected - frequency.get(number, 0)) / sigma for number in range(1, _POOL + 1)}


def _rfft_power(series: tuple[float, ...]) -> tuple[float, ...]:
    """Return real-input FFT power bins using only the Python standard library.

    The donor calls ``numpy.fft.rfft(series - series.mean())``.  The direct
    DFT below has the same rfft bin definition and stable first-maximum tie
    behavior, while keeping prediction free of third-party and external state.
    """

    length = len(series)
    mean = sum(series) / length
    centered = tuple(value - mean for value in series)
    powers: list[float] = []
    for frequency_index in range(length // 2 + 1):
        real = 0.0
        imaginary = 0.0
        for sample_index, value in enumerate(centered):
            angle = 2.0 * math.pi * frequency_index * sample_index / length
            real += value * math.cos(angle)
            imaginary -= value * math.sin(angle)
        powers.append(real * real + imaginary * imaginary)
    return tuple(powers)


def _fourier_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port donor ``_d539_fourier_scores`` with a stdlib-only rfft."""

    recent = _recent(history, _FOURIER_WINDOW)
    draw_count = len(recent)
    if draw_count < 10:
        return {number: 0.0 for number in range(1, _POOL + 1)}

    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        series = tuple(1.0 if number in row.numbers else 0.0 for row in recent)
        if sum(series) < 2:
            scores[number] = 0.0
            continue

        power = _rfft_power(series)
        if len(power) <= 1:
            scores[number] = 0.0
            continue

        dominant_index = max(
            range(1, len(power)), key=lambda frequency_index: power[frequency_index]
        )
        period = draw_count / dominant_index
        last_hit = max(index for index, value in enumerate(series) if value == 1.0)
        gap = (draw_count - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def _validated_portfolio_output(
    predicted: object, strategy_id: str, native_ticket_count: int
) -> tuple[tuple[int, ...], ...]:
    """Fail closed while preserving native ticket order and duplicates."""

    if type(predicted) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a tuple of tickets")
    raw_tickets = cast(tuple[object, ...], predicted)
    if len(raw_tickets) != native_ticket_count:
        raise InvalidOutput(
            f"{strategy_id}: expected {native_ticket_count} native tickets, got {len(raw_tickets)}"
        )

    validated: list[tuple[int, ...]] = []
    for index, ticket in enumerate(raw_tickets):
        validated_ticket = _validated_daily539_numbers(
            ticket, strategy_id, f"output ticket {index + 1}"
        )
        if validated_ticket != ticket:
            raise InvalidOutput(
                f"{strategy_id}: output ticket {index + 1} numbers must be ascending"
            )
        validated.append(validated_ticket)
    return tuple(validated)


class _Daily539PortfolioAdapter:
    """Small local portfolio contract for the 5-of-39 adapter family."""

    strategy_id: ClassVar[str]
    strategy_name: ClassVar[str]
    strategy_version: ClassVar[str]
    min_history: ClassVar[int] = _MIN_HISTORY
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (LotteryType.DAILY_539,)
    native_ticket_count: ClassVar[int] = 2

    def get_bets(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )

        canonical_history = _validated_daily539_history(history, self.strategy_id)
        if len(canonical_history) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical_history)}"
            )

        predicted = self._predict_all(canonical_history)
        return _validated_portfolio_output(predicted, self.strategy_id, self.native_ticket_count)

    def _predict_all(self, history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
        raise NotImplementedError


class Daily539MidfreqAcb2BetAdapter(_Daily539PortfolioAdapter):
    """Native [MidFreq, ACB] DAILY_539 portfolio."""

    strategy_id = "midfreq_acb_2bet"
    strategy_name = "今彩539 中頻 ACB 2注"
    strategy_version = "v0.1"

    def _predict_all(self, history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
        return (
            _top_n(_midfreq_scores(history), _PICK),
            _top_n(_acb_scores(history), _PICK),
        )


class Daily539MidfreqFourier2BetAdapter(_Daily539PortfolioAdapter):
    """Native [MidFreq, Fourier] DAILY_539 portfolio."""

    strategy_id = "midfreq_fourier_2bet"
    strategy_name = "今彩539 中頻 Fourier 2注"
    strategy_version = "v0.1"

    def _predict_all(self, history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
        return (
            _top_n(_midfreq_scores(history), _PICK),
            _top_n(_fourier_scores(history), _PICK),
        )


__all__ = [
    "Daily539MidfreqAcb2BetAdapter",
    "Daily539MidfreqFourier2BetAdapter",
]
