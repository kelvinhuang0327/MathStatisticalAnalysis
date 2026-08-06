"""Pure-Python DAILY_539 ports of the P36 "Fourier4正交" bet-1 identities.

Donors: ``P0b539FColdFmidAdapter`` / ``predict_fourier4_cold_fmid_bet1`` and
``P0c539FColdX2Adapter`` / ``predict_fourier4_cold_x2_bet1`` in
``LotteryNewMeraged/lottery_api/models/p36_wave2_daily539_adapters.py``
(strategy_ids ``p0b_539_3bet_f_cold_fmid`` and ``p0c_539_3bet_f_cold_x2``,
``strategy_version=v0.1-p36``). Both named "3bet" identities only ever had
bet-1 recorded or implemented by any donor script -- there is no bet-2/bet-3
algorithm to port -- so only that proven bet-1 is exposed here, via
``get_one_bet``, matching the rest of the P31A/P36 bet-1-only family.

Both bets rank numbers by a Fourier recurrence score (dominant-frequency
magnitude over the trailing 500 draws, converted to a period-vs-recency-gap
score) structurally similar to the one already ported in
``daily539_portfolio_f4cold.py`` -- but not identical: this donor's own
``_fourier_scores`` computes ``numpy.fft.rfft(series - series.mean())`` and
scans its full ``power[1:]`` range (Nyquist bin included), while the F4Cold
donor uses ``numpy.fft.fft``/``fftfreq``'s strictly-positive range and never
mean-subtracts. See ``_fourier_scores`` below for why that difference is
numerically load-bearing, not cosmetic. Kept self-contained (no cross-module
import) per this adapter family's convention. When fewer than five numbers
score positively the donor falls back to a secondary ranking appended after
the Fourier ranking: MidFreq mean-reversion for p0b, raw ACB
(freq-deficit/gap/boundary/mod3, no cross-zone constraint) for p0c.
"""

from __future__ import annotations

from collections import Counter
from math import cos, hypot, pi, sin
from typing import cast

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
_FOURIER_WINDOW = 500
_MIDFREQ_WINDOW = 100
_ACB_WINDOW = 100


def _validated_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    rows: list[CausalDrawRow] = []
    for index, candidate in enumerate(cast(tuple[object, ...], history)):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        if type(row.draw) is not str or not row.draw:
            raise InvalidOutput(f"{strategy_id}: history row {index} draw is invalid")
        if type(row.date) is not str or not row.date:
            raise InvalidOutput(f"{strategy_id}: history row {index} date is invalid")
        if type(row.numbers) is not tuple:
            raise InvalidOutput(f"{strategy_id}: history row {index} numbers are invalid")
        numbers = cast(tuple[object, ...], row.numbers)
        if len(numbers) != _PICK or not all(type(number) is int for number in numbers):
            raise InvalidOutput(f"{strategy_id}: history row {index} needs five integers")
        typed = cast(tuple[int, ...], numbers)
        if len(set(typed)) != _PICK or not all(1 <= number <= _POOL for number in typed):
            raise InvalidOutput(f"{strategy_id}: history row {index} numbers are illegal")
        if typed != tuple(sorted(typed)):
            raise InvalidOutput(f"{strategy_id}: history row {index} numbers are not ascending")
        rows.append(CausalDrawRow(draw=row.draw, date=row.date, numbers=typed))
    return tuple(rows)


def _validated_ticket(numbers: object, strategy_id: str) -> tuple[int, ...]:
    if type(numbers) is not tuple:
        raise InvalidOutput(f"{strategy_id}: output must be a tuple")
    values = cast(tuple[object, ...], numbers)
    if len(values) != _PICK or not all(type(number) is int for number in values):
        raise InvalidOutput(f"{strategy_id}: output needs five built-in integers")
    typed = cast(tuple[int, ...], values)
    if len(set(typed)) != _PICK or not all(1 <= number <= _POOL for number in typed):
        raise InvalidOutput(f"{strategy_id}: output numbers are illegal")
    if typed != tuple(sorted(typed)):
        raise InvalidOutput(f"{strategy_id}: output numbers are not ascending")
    return typed


def _fourier_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Donor-equivalent Fourier recurrence score.

    The P36 donor computes ``numpy.fft.rfft(series - series.mean())`` over the
    *full* window and scans ``power[1:]`` -- bins ``1..width // 2`` inclusive
    (the Nyquist bin included, unlike the ``daily539_portfolio_f4cold``
    donor's strictly-positive ``fftfreq`` range of ``1..(width - 1) // 2``).
    Mean-subtracting before the transform matters numerically, not just
    algebraically: for a number present in *every* draw of the window the
    mean equals exactly 1.0, so the donor's per-position weight
    ``(1.0 - 1.0) == 0.0`` exactly, making every frequency bin's magnitude
    exactly zero and the first bin win the argmax deterministically. Summing
    only the raw hit-position exponentials (as ``daily539_portfolio_f4cold``
    does) computes the mathematically-identical value in exact arithmetic,
    but leaves an unpredictable floating-point residual instead of an exact
    zero, and that residual can pick a different "winning" bin. This port
    reproduces the donor's cancellation instead: for each frequency bin it
    sums ``cos``/``sin`` once over every position in the window (shared
    across all numbers, since it does not depend on which number is being
    scored), then derives each number's mean-subtracted coefficient as
    ``hit_sum - mean * all_position_sum`` -- algebraically the direct
    per-position sum, but preserving the same exact-zero cancellation for a
    constant series (subtracting an identical float from itself is exact in
    IEEE754, regardless of its value).
    """

    recent = history[-_FOURIER_WINDOW:] if len(history) >= _FOURIER_WINDOW else history
    width = len(recent)
    scores: dict[int, float] = {}
    max_positive_bin = width // 2
    if max_positive_bin < 1:
        return {number: 0.0 for number in range(1, _POOL + 1)}

    hit_positions_by_number: dict[int, tuple[int, ...]] = {
        number: tuple(index for index, row in enumerate(recent) if number in row.numbers)
        for number in range(1, _POOL + 1)
    }

    all_cos_by_bin: list[float] = [0.0] * (max_positive_bin + 1)
    all_sin_by_bin: list[float] = [0.0] * (max_positive_bin + 1)
    for frequency_bin in range(1, max_positive_bin + 1):
        angle_scale = 2.0 * pi * frequency_bin / width
        total_cos = 0.0
        total_sin = 0.0
        for position in range(width):
            angle = angle_scale * position
            total_cos += cos(angle)
            total_sin += sin(angle)
        all_cos_by_bin[frequency_bin] = total_cos
        all_sin_by_bin[frequency_bin] = total_sin

    for number in range(1, _POOL + 1):
        hit_positions = hit_positions_by_number[number]
        if len(hit_positions) < 2:
            scores[number] = 0.0
            continue
        mean = len(hit_positions) / width

        best_magnitude = -1.0
        best_frequency = 0.0
        for frequency_bin in range(1, max_positive_bin + 1):
            angle_scale = 2.0 * pi * frequency_bin / width
            hit_cos = 0.0
            hit_sin = 0.0
            for position in hit_positions:
                angle = angle_scale * position
                hit_cos += cos(angle)
                hit_sin += sin(angle)
            real = hit_cos - mean * all_cos_by_bin[frequency_bin]
            imaginary = hit_sin - mean * all_sin_by_bin[frequency_bin]
            magnitude = hypot(real, imaginary)
            if magnitude > best_magnitude:
                best_magnitude = magnitude
                best_frequency = frequency_bin / width

        if best_frequency == 0.0:
            scores[number] = 0.0
            continue
        last_hit = hit_positions[-1]
        gap = (width - 1) - last_hit
        period = 1.0 / best_frequency
        scores[number] = 1.0 / (abs(gap - period) + 1.0)

    return scores


def _midfreq_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    recent = history[-_MIDFREQ_WINDOW:] if len(history) >= _MIDFREQ_WINDOW else history
    width = len(recent)
    if width == 0:
        return {number: 0.0 for number in range(1, _POOL + 1)}
    expected = width * _PICK / _POOL
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: -abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)}


def _acb_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    recent = history[-_ACB_WINDOW:] if len(history) >= _ACB_WINDOW else history
    width = len(recent)
    if width == 0:
        return {number: 0.0 for number in range(1, _POOL + 1)}
    expected = width * _PICK / _POOL
    frequency: Counter[int] = Counter()
    last_seen: dict[int, int] = {}
    for index, row in enumerate(recent):
        for number in row.numbers:
            frequency[number] += 1
            last_seen[number] = index
    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        deficit = (expected - frequency.get(number, 0)) / max(expected, 1.0)
        gap = (width - 1 - last_seen.get(number, -1)) / width
        boundary = 1.2 if number <= 5 or number >= 35 else 1.0
        mod3 = 1.1 if number % 3 == 0 else 1.0
        scores[number] = (deficit * 0.4 + gap * 0.6) * boundary * mod3
    return scores


def _ranked_positive(scores: dict[int, float]) -> list[int]:
    """Ascending-index-stable descending rank, positive scores only."""

    return sorted(
        (number for number in range(1, _POOL + 1) if scores[number] > 0.0),
        key=lambda number: -scores[number],
    )


def _ranked_all(scores: dict[int, float]) -> list[int]:
    """Ascending-index-stable descending rank over the full pool."""

    return sorted(range(1, _POOL + 1), key=lambda number: -scores[number])


def _predict_with_fallback(
    history: tuple[CausalDrawRow, ...], fallback_scores: dict[int, float]
) -> tuple[int, ...]:
    ranked = _ranked_positive(_fourier_scores(history))
    if len(ranked) < _PICK:
        seen = set(ranked)
        remaining = [number for number in _ranked_all(fallback_scores) if number not in seen]
        ranked = ranked + remaining
    return tuple(sorted(ranked[:_PICK]))


def _predict_p0b(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    return _predict_with_fallback(history, _midfreq_scores(history))


def _predict_p0c(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    return _predict_with_fallback(history, _acb_scores(history))


class Daily539P0bFourierColdFmidAdapter:
    """P36 Fourier4正交 cold+midfreq identity, bet-1 only."""

    strategy_id = "p0b_539_3bet_f_cold_fmid"
    strategy_name = "今彩539 Fourier4正交 cold+midfreq 3注"
    strategy_version = "v0.1-p36"
    min_history = _MIN_HISTORY
    native_ticket_count = 1
    supported_lottery_types = (LotteryType.DAILY_539,)

    def get_one_bet(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        canonical = _validated_history(history, self.strategy_id)
        if len(canonical) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical)}"
            )
        return _validated_ticket(_predict_p0b(canonical), self.strategy_id), None


class Daily539P0cFourierColdX2Adapter:
    """P36 Fourier4正交 x2 cold identity, bet-1 only."""

    strategy_id = "p0c_539_3bet_f_cold_x2"
    strategy_name = "今彩539 Fourier4正交 x2 cold 3注"
    strategy_version = "v0.1-p36"
    min_history = _MIN_HISTORY
    native_ticket_count = 1
    supported_lottery_types = (LotteryType.DAILY_539,)

    def get_one_bet(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        canonical = _validated_history(history, self.strategy_id)
        if len(canonical) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical)}"
            )
        return _validated_ticket(_predict_p0c(canonical), self.strategy_id), None


__all__ = ["Daily539P0bFourierColdFmidAdapter", "Daily539P0cFourierColdX2Adapter"]
