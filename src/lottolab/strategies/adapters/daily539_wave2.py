"""Daily539 native-strategy wave 2: shared-contract ports of two frozen
frequency portfolios.

Pinned source authority (SELECT_REPLACEMENTS_FOR_BLOCKED_TWO_R2):

``tools/run_daily539_t539_wave1.py`` at
``69b6790204e5df821b11e8ef316ea001606568ff``, SHA-256
``55feb185278bc7355f49c1695afe49b872f1dd4161528dd158bc8fe5efcb9d8b``.
That runner constructs these two identities from the MidFreq / ACB / Fourier
producers already named there:

* ``midfreq_fourier_2bet`` emits MidFreq, then Fourier.
* ``midfreq_acb_2bet`` emits MidFreq, then ACB.

Each identity is a ``PortfolioBetAdapter`` so ticket count, lottery type, and
per-ticket legal-number canonicalization stay in the shared template. Native
ticket order and positional cross-ticket duplicates are preserved. No
algorithm was changed, tuned, or combined. Not registered in the production
strategy catalog.
"""

from __future__ import annotations

import math
from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_POOL = 39
_PICK = 5
_MIN_HISTORY = 100
_MIDFREQ_WINDOW = 100
_ACB_WINDOW = 100
_FOURIER_WINDOW = 100


def _recent(history: tuple[CausalDrawRow, ...], window: int) -> tuple[CausalDrawRow, ...]:
    return history[-window:] if len(history) >= window else history


def _top_n(scores: dict[int, float], count: int) -> tuple[int, ...]:
    """Rank by descending score, then pinned-source ascending number."""

    ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    return tuple(sorted(ranked[:count]))


def _midfreq_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Pinned MidFreq scores: closeness to expected hit count over 100 draws."""

    recent = _recent(history, _MIDFREQ_WINDOW)
    draw_count = len(recent)
    expected = draw_count * _PICK / _POOL
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: -abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)}


def _acb_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Pinned ACB scores: standardized coldness over 100 draws."""

    recent = _recent(history, _ACB_WINDOW)
    draw_count = len(recent)
    probability = _PICK / _POOL
    expected = draw_count * probability
    variance = draw_count * probability * (1.0 - probability)
    sigma = variance**0.5 if variance > 0 else 1.0
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: (expected - frequency.get(number, 0)) / sigma for number in range(1, _POOL + 1)}


def _rfft_power(series: tuple[float, ...]) -> tuple[float, ...]:
    """Real-input FFT power bins using only the Python standard library.

    The pinned producer matches ``numpy.fft.rfft(series - series.mean())`` bin
    definition and first-maximum tie behavior without a numpy runtime
    dependency.
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
    """Pinned Fourier scores: period-gap closeness over 100 draws."""

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


class Daily539MidfreqFourier2BetAdapter(PortfolioBetAdapter):
    """Native [MidFreq, Fourier] DAILY_539 portfolio."""

    strategy_id = "midfreq_fourier_2bet"
    strategy_name = "今彩539 中頻 Fourier 2注"
    strategy_version = "v0.1"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.DAILY_539,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return (
            _top_n(_midfreq_scores(history), _PICK),
            _top_n(_fourier_scores(history), _PICK),
        )


class Daily539MidfreqAcb2BetAdapter(PortfolioBetAdapter):
    """Native [MidFreq, ACB] DAILY_539 portfolio."""

    strategy_id = "midfreq_acb_2bet"
    strategy_name = "今彩539 中頻 ACB 2注"
    strategy_version = "v0.1"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.DAILY_539,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return (
            _top_n(_midfreq_scores(history), _PICK),
            _top_n(_acb_scores(history), _PICK),
        )


__all__ = [
    "Daily539MidfreqAcb2BetAdapter",
    "Daily539MidfreqFourier2BetAdapter",
]
