"""Target-native port of the frozen BIG_LOTTO Power Fourier Rhythm donor.

The donor is ``tools/power_fourier_rhythm.py`` at legacy commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (recorded blob
``8ed6d90393fa175d4f661979d312b8739af21ac8``, SHA-256
``cb75e72e4c948466a23a432527ca9e5af40e8618c509154f54277ac860d62d59``).
Its frozen-runtime output is retained in source-grid Wave 49; its complete
source-equivalent Fourier formula is retained by the independently tested
``powerlotto_wave1`` fixed-window port.

For every number 1..49, the donor builds a fixed 500-slot appearance
bitstream, subtracts its mean, runs a full complex DFT, and selects the
largest-amplitude strictly-positive bin (indices 1..249). A selected period
must lie strictly inside ``(2, 250)``. The score is the reciprocal distance
between that period and the current last-hit gap, plus one. All numbers are
ranked once; ranks 1..6 and 7..12 form the two native positional tickets.
There is no RNG, phase extrapolation, harmonic combination, database access,
or alternate predictor.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import bluestein_dft

_STRATEGY_ID = "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_WINDOW = 500
_FIRST_POSITIVE_BIN = 1
_POSITIVE_BIN_STOP = _WINDOW // 2
_NATIVE_TICKET_COUNT = 2


@dataclass(frozen=True, slots=True)
class _FourierRhythmComponent:
    """Observable stages of one number's donor score."""

    appearance_series: tuple[float, ...]
    detrended_series: tuple[float, ...]
    spectrum: tuple[complex, ...]
    dominant_frequency_index: int | None
    dominant_amplitude: float
    rhythm_period: float | None
    last_hit_gap: int | None
    score: float


def _appearance_series(
    history: tuple[CausalDrawRow, ...],
    number: int,
) -> tuple[float, ...]:
    """Return the donor's fixed-length, trailing-zero-padded binary series."""

    values = [0.0] * _WINDOW
    for index, row in enumerate(history[-_WINDOW:]):
        if number in row.numbers:
            values[index] = 1.0
    return tuple(values)


def _fourier_rhythm_component(
    history: tuple[CausalDrawRow, ...],
    number: int,
) -> _FourierRhythmComponent:
    series = _appearance_series(history, number)
    appearance_count = sum(series)
    if appearance_count < 2:
        return _FourierRhythmComponent(
            appearance_series=series,
            detrended_series=(),
            spectrum=(),
            dominant_frequency_index=None,
            dominant_amplitude=0.0,
            rhythm_period=None,
            last_hit_gap=None,
            score=0.0,
        )

    mean = appearance_count / _WINDOW
    detrended = tuple(value - mean for value in series)
    spectrum = bluestein_dft(detrended)
    dominant_index = max(
        range(_FIRST_POSITIVE_BIN, _POSITIVE_BIN_STOP),
        key=lambda index: (abs(spectrum[index]), -index),
    )
    amplitude = abs(spectrum[dominant_index])
    period = _WINDOW / dominant_index
    if not 2 < period < _WINDOW / 2:
        return _FourierRhythmComponent(
            appearance_series=series,
            detrended_series=detrended,
            spectrum=spectrum,
            dominant_frequency_index=dominant_index,
            dominant_amplitude=amplitude,
            rhythm_period=period,
            last_hit_gap=None,
            score=0.0,
        )

    last_hit = max(index for index, value in enumerate(series) if value)
    gap = (_WINDOW - 1) - last_hit
    score = 1.0 / (abs(gap - period) + 1.0)
    return _FourierRhythmComponent(
        appearance_series=series,
        detrended_series=detrended,
        spectrum=spectrum,
        dominant_frequency_index=dominant_index,
        dominant_amplitude=amplitude,
        rhythm_period=period,
        last_hit_gap=gap,
        score=score,
    )


def _power_fourier_rhythm_scores(
    history: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    return {
        number: _fourier_rhythm_component(history, number).score
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }


def _tickets_from_scores(scores: Mapping[int, float]) -> tuple[tuple[int, ...], ...]:
    """Apply the retained deterministic tie rule and consecutive rank chunks."""

    if set(scores) != set(range(_MIN_NUMBER, _MAX_NUMBER + 1)):
        raise InvalidOutput(f"{_STRATEGY_ID}: Fourier score domain must be exactly 1..49")
    ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: (-scores[number], number),
    )
    return tuple(tuple(sorted(ranked[start : start + _PICK_COUNT])) for start in (0, _PICK_COUNT))


def _power_fourier_rhythm_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    return _tickets_from_scores(_power_fourier_rhythm_scores(history))


class BigLottoPowerFourierRhythmAdapter(PortfolioBetAdapter):
    """Deterministic fixed-window, two-position Fourier-rhythm portfolio."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Power Fourier Rhythm 2注"
    strategy_version = "v0.1"
    min_history = _WINDOW
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_WINDOW:]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(f"{self.strategy_id}: causal draw identities must be unique")
        return _power_fourier_rhythm_tickets(history)


__all__ = ["BigLottoPowerFourierRhythmAdapter"]
