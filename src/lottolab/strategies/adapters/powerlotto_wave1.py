"""Pure POWER_LOTTO adapters for migration Wave 1.

The donor modules are legacy application scripts and are intentionally not
imported here.  This module ports their deterministic first-zone signal
families into a dependency-free strategy boundary:

* every prediction is POWER_LOTTO-only and uses the 1..38 first zone;
* history is immutable, causal, and normalized through
  :func:`coerce_p638_history`;
* each strategy returns its native ordered portfolio of complete tickets,
  including positional duplicates when a donor family emits them;
* every complete ticket pairs the first-zone port with the shared second-zone
  SSOT; no caller may silently promote a first-zone-only prediction.

The long-window Fourier donor uses a NumPy FFT.  Most callers (see
:func:`_fourier_scores`) use a deterministic radix-2 real periodogram over a
zero-padded power-of-two window: it preserves the donor's period-alignment
signal and tie policy without adding NumPy, but does not reproduce the
donor's exact-length dominant-bin selection bit-for-bit.  ``power_fourier_rhythm_2bet``
and ``power_orthogonal_5bet`` instead need that exact reproduction, so they
use the arbitrary-length :func:`bluestein_dft` at the donor's own unpadded
length (see :func:`_fourier_rhythm_fixed_window_scores` and
:func:`_fourier_scores_exact`) -- still no NumPy or other external state.
"""

from __future__ import annotations

import cmath
import itertools
import math
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Final, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.powerlotto_second_zone import (
    second_zone_predict,
    validate_power_lotto_ticket,
)

_POOL: Final = 38
_PICK: Final = 6
_ZONE_WINDOW: Final = 30
_COLD_WINDOW: Final = 100
_MIDFREQ_WINDOW: Final = 100
_FOURIER_LONG_WINDOW: Final = 500
_FOURIER_SHORT_WINDOW: Final = 100
_MARKOV_WINDOW: Final = 30
_ACB_WINDOW: Final = 100
_ENTROPY_CHAOS_THRESHOLD: Final = 2.2

type P638FirstZoneTicket = tuple[int, ...]
type P638FirstZoneTicketSet = tuple[P638FirstZoneTicket, ...]
type P638Ticket = tuple[P638FirstZoneTicket, int]
type P638TicketSet = tuple[P638Ticket, ...]


def _validated_numbers(value: object, context: str) -> tuple[int, ...]:
    """Validate and canonicalize one six-number POWER_LOTTO first zone."""

    if type(value) is not tuple:
        raise InvalidOutput(f"{context}: numbers must be an exact tuple")
    raw = cast(tuple[object, ...], value)
    if len(raw) != _PICK:
        raise InvalidOutput(f"{context}: expected {_PICK} first-zone numbers")
    if not all(type(number) is int for number in raw):
        raise InvalidOutput(f"{context}: numbers must be exact built-in integers")
    numbers = tuple(sorted(cast(tuple[int, ...], raw)))
    if len(set(numbers)) != _PICK:
        raise InvalidOutput(f"{context}: first-zone numbers must be distinct")
    if any(number < 1 or number > _POOL for number in numbers):
        raise InvalidOutput(f"{context}: first-zone numbers must be in [1..{_POOL}]")
    return numbers


@dataclass(frozen=True, slots=True)
class P638HistoryRow:
    """One immutable, oldest-first causal POWER_LOTTO history row.

    The canonical mapping form accepted by :func:`coerce_p638_history` is::

        {"draw": "115000061", "date": "2026-07-30",
         "numbers": [8, 14, 17, 19, 21, 23], "special": 1}

    ``draw_id``/``draw_number``, ``draw_date``, ``main_numbers``, and
    ``second_number`` are accepted as explicit interoperability aliases.
    """

    draw: str
    date: str
    numbers: tuple[int, ...]
    second_number: int

    def __post_init__(self) -> None:
        if type(self.draw) is not str or not self.draw:
            raise InvalidOutput("P638 history draw must be a non-empty string")
        if type(self.date) is not str or not self.date:
            raise InvalidOutput("P638 history date must be a non-empty string")
        object.__setattr__(
            self,
            "numbers",
            _validated_numbers(self.numbers, f"P638 history draw {self.draw}"),
        )
        if type(self.second_number) is not int or not 1 <= self.second_number <= 8:
            raise InvalidOutput(f"P638 history draw {self.draw}: second_number must be in [1..8]")


def _mapping_value(
    row: Mapping[object, object],
    keys: tuple[str, ...],
    context: str,
) -> object:
    for key in keys:
        if key in row:
            return row[key]
    joined = ", ".join(keys)
    raise InvalidOutput(f"{context}: missing one of {joined}")


def _mapping_text(value: object, context: str, *, allow_int: bool = False) -> str:
    if type(value) is str and value:
        return value
    if allow_int and type(value) is int:
        return str(value)
    raise InvalidOutput(f"{context}: expected a non-empty string")


def _mapping_numbers(value: object, context: str) -> tuple[int, ...]:
    if type(value) not in (tuple, list):
        raise InvalidOutput(f"{context}: numbers must be a list or tuple")
    raw = cast(tuple[object, ...] | list[object], value)
    if not all(type(number) is int for number in raw):
        raise InvalidOutput(f"{context}: numbers must be exact built-in integers")
    return _validated_numbers(tuple(cast(tuple[int, ...], raw)), context)


def _mapping_lottery_type(value: object, context: str) -> None:
    if value is LotteryType.POWER_LOTTO:
        return
    if type(value) is str and value == LotteryType.POWER_LOTTO.value:
        return
    raise UnsupportedLotteryType(f"{context}: history row is not POWER_LOTTO")


def coerce_p638_history(history: object) -> tuple[P638HistoryRow, ...]:
    """Coerce typed rows or canonical mappings into immutable causal rows.

    The function deliberately preserves caller order.  Callers must provide
    oldest-first rows strictly before the target draw; this adapter layer does
    not sort or fetch additional history.
    """

    if type(history) not in (tuple, list):
        raise InvalidOutput("P638 history must be an exact tuple or list")

    rows: list[P638HistoryRow] = []
    raw_history = cast(tuple[object, ...] | list[object], history)
    for index, candidate in enumerate(raw_history):
        context = f"P638 history row {index}"
        if type(candidate) is P638HistoryRow:
            rows.append(candidate)
            continue
        if not isinstance(candidate, Mapping):
            raise InvalidOutput(f"{context}: expected P638HistoryRow or mapping")

        row = cast(Mapping[object, object], candidate)
        if "lottery_type" in row:
            _mapping_lottery_type(row["lottery_type"], context)
        draw = _mapping_text(
            _mapping_value(row, ("draw", "draw_id", "draw_number"), context),
            f"{context} draw",
            allow_int=True,
        )
        date = _mapping_text(
            _mapping_value(row, ("date", "draw_date"), context),
            f"{context} date",
        )
        numbers = _mapping_numbers(
            _mapping_value(row, ("numbers", "main_numbers"), context),
            f"{context} numbers",
        )
        second_number = _mapping_value(row, ("special", "second_number"), context)
        if type(second_number) is not int or not 1 <= second_number <= 8:
            raise InvalidOutput(f"{context}: second_number must be an exact integer in [1..8]")
        rows.append(
            P638HistoryRow(
                draw=draw,
                date=date,
                numbers=numbers,
                second_number=second_number,
            )
        )
    return tuple(rows)


def _require_power_lotto(lottery_type: object, strategy_id: str) -> None:
    if type(lottery_type) is not LotteryType or lottery_type is not LotteryType.POWER_LOTTO:
        raise UnsupportedLotteryType(f"{strategy_id} supports only {LotteryType.POWER_LOTTO.value}")


def _recent(
    history: tuple[P638HistoryRow, ...],
    window: int,
) -> tuple[P638HistoryRow, ...]:
    return history[-window:] if len(history) > window else history


@lru_cache(maxsize=4096)
def _frequency(
    history: tuple[P638HistoryRow, ...],
    window: int,
) -> Counter[int]:
    frequency: Counter[int] = Counter()
    for row in _recent(history, window):
        frequency.update(row.numbers)
    return frequency


def _ranked_ticket(scores: Mapping[int, float], *, reverse: bool = True) -> P638FirstZoneTicket:
    if reverse:
        ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    else:
        ranked = sorted(range(1, _POOL + 1), key=lambda number: (scores[number], number))
    return tuple(sorted(ranked[:_PICK]))


@lru_cache(maxsize=4096)
def _hot_ticket(
    history: tuple[P638HistoryRow, ...],
    window: int,
) -> P638FirstZoneTicket:
    frequency = _frequency(history, window)
    return _ranked_ticket(
        {number: float(frequency.get(number, 0)) for number in range(1, _POOL + 1)}
    )


@lru_cache(maxsize=4096)
def _cold_ticket(
    history: tuple[P638HistoryRow, ...],
    window: int,
) -> P638FirstZoneTicket:
    frequency = _frequency(history, window)
    return _ranked_ticket(
        {number: float(frequency.get(number, 0)) for number in range(1, _POOL + 1)},
        reverse=False,
    )


@lru_cache(maxsize=4096)
def _midfreq_scores(
    history: tuple[P638HistoryRow, ...],
    window: int = _MIDFREQ_WINDOW,
) -> dict[int, float]:
    recent = _recent(history, window)
    expected = len(recent) * _PICK / _POOL
    frequency = _frequency(history, window)
    return {number: -abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)}


def _zone(number: int) -> int:
    return 7 if number > 35 else (number - 1) // 5


@lru_cache(maxsize=4096)
def _zone_entropy(
    history: tuple[P638HistoryRow, ...],
    window: int = _ZONE_WINDOW,
) -> float:
    zone_counts: Counter[int] = Counter()
    for row in _recent(history, window):
        for number in row.numbers:
            zone_counts[_zone(number)] += 1
    total = sum(zone_counts.values())
    if total == 0:
        return 0.0
    return -sum(
        (count / total) * math.log2(count / total) for count in zone_counts.values() if count
    )


@lru_cache(maxsize=4096)
def _weighted_recency_ticket(
    history: tuple[P638HistoryRow, ...],
    window: int = _MARKOV_WINDOW,
) -> P638FirstZoneTicket:
    recent = _recent(history, window)
    if not recent:
        return tuple(range(1, _PICK + 1))
    weighted: dict[int, float] = {}
    size = len(recent)
    for index, row in enumerate(recent):
        weight = 1.0 + 2.0 * (index / size)
        for number in row.numbers:
            weighted[number] = weighted.get(number, 0.0) + weight
    return _ranked_ticket({number: weighted.get(number, 0.0) for number in range(1, _POOL + 1)})


@lru_cache(maxsize=4096)
def _markov_ticket(
    history: tuple[P638HistoryRow, ...],
    window: int = _MARKOV_WINDOW,
) -> P638FirstZoneTicket:
    recent = _recent(history, window)
    if len(recent) < 2:
        return tuple(range(1, _PICK + 1))

    transition: dict[int, Counter[int]] = {number: Counter() for number in range(1, _POOL + 1)}
    for previous, current in itertools.pairwise(recent):
        for left in previous.numbers:
            transition[left].update(current.numbers)

    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        score = 0.0
        for previous_number in recent[-1].numbers:
            row = transition[previous_number]
            total = sum(row.values())
            if total:
                score += row.get(number, 0) / total
        scores[number] = score
    return _ranked_ticket(scores)


def _fft_power_spectrum(series: tuple[float, ...]) -> tuple[float, ...]:
    """Return a deterministic one-sided spectrum without external libraries."""

    fft_length = 1
    while fft_length < len(series):
        fft_length <<= 1
    values = [complex(value, 0.0) for value in series]
    values.extend([0j] * (fft_length - len(values)))

    reverse_index = 0
    for index in range(1, fft_length):
        bit = fft_length >> 1
        while reverse_index & bit:
            reverse_index ^= bit
            bit >>= 1
        reverse_index ^= bit
        if index < reverse_index:
            values[index], values[reverse_index] = values[reverse_index], values[index]

    length = 2
    while length <= fft_length:
        angle = -2.0 * math.pi / length
        unit = complex(math.cos(angle), math.sin(angle))
        half = length // 2
        for start in range(0, fft_length, length):
            factor = 1.0 + 0.0j
            for offset in range(half):
                left = values[start + offset]
                right = factor * values[start + offset + half]
                values[start + offset] = left + right
                values[start + offset + half] = left - right
                factor *= unit
        length <<= 1

    return tuple(
        value.real * value.real + value.imag * value.imag for value in values[: fft_length // 2 + 1]
    )


def _fft_complex_pow2(values: tuple[complex, ...]) -> tuple[complex, ...]:
    """Radix-2 complex FFT; ``len(values)`` must already be a power of two."""

    length = len(values)
    result = list(values)

    reverse_index = 0
    for index in range(1, length):
        bit = length >> 1
        while reverse_index & bit:
            reverse_index ^= bit
            bit >>= 1
        reverse_index ^= bit
        if index < reverse_index:
            result[index], result[reverse_index] = result[reverse_index], result[index]

    size = 2
    while size <= length:
        angle = -2.0 * math.pi / size
        unit = complex(math.cos(angle), math.sin(angle))
        half = size // 2
        for start in range(0, length, size):
            factor = 1.0 + 0.0j
            for offset in range(half):
                left = result[start + offset]
                right = factor * result[start + offset + half]
                result[start + offset] = left + right
                result[start + offset + half] = left - right
                factor *= unit
        size <<= 1

    return tuple(result)


def _ifft_complex_pow2(values: tuple[complex, ...]) -> tuple[complex, ...]:
    """Inverse of :func:`_fft_complex_pow2` via forward-FFT-of-conjugate."""

    length = len(values)
    conjugated = tuple(value.conjugate() for value in values)
    transformed = _fft_complex_pow2(conjugated)
    return tuple(value.conjugate() / length for value in transformed)


def bluestein_dft(signal: tuple[float, ...]) -> tuple[complex, ...]:
    """Exact discrete Fourier transform of ``signal`` for an arbitrary length.

    The fixed-window Fourier-rhythm donor requires an exact 500-point FFT,
    which is not a power of two, so the existing radix-2 engine cannot be
    applied directly without changing the frequency bins.  Bluestein's
    algorithm rewrites an arbitrary-length DFT as a linear convolution
    computable with a power-of-two FFT, reproducing NumPy's ``fft`` exactly
    (up to floating-point rounding) with no new dependency.
    """

    n = len(signal)
    if n == 0:
        return ()
    if n == 1:
        return (complex(signal[0]),)

    padded_length = 1
    while padded_length < 2 * n - 1:
        padded_length <<= 1

    chirp = tuple(cmath.exp(-1j * math.pi * (index * index) / n) for index in range(n))

    forward = [0j] * padded_length
    for index in range(n):
        forward[index] = signal[index] * chirp[index]

    filter_sequence = [0j] * padded_length
    filter_sequence[0] = complex(1.0, 0.0)
    for index in range(1, n):
        value = chirp[index].conjugate()
        filter_sequence[index] = value
        filter_sequence[padded_length - index] = value

    transformed_signal = _fft_complex_pow2(tuple(forward))
    transformed_filter = _fft_complex_pow2(tuple(filter_sequence))
    convolved = _ifft_complex_pow2(
        tuple(
            left * right
            for left, right in zip(transformed_signal, transformed_filter, strict=True)
        )
    )
    return tuple(convolved[index] * chirp[index] for index in range(n))


@lru_cache(maxsize=4096)
def _fourier_scores(
    history: tuple[P638HistoryRow, ...],
    window: int,
) -> dict[int, float]:
    """Compute donor-style period-alignment scores for numbers 1..38."""

    recent = _recent(history, window)
    size = len(recent)
    if size < 10:
        return {number: 0.0 for number in range(1, _POOL + 1)}

    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        raw = tuple(1.0 if number in row.numbers else 0.0 for row in recent)
        if sum(raw) < 2:
            scores[number] = 0.0
            continue
        mean = sum(raw) / size
        spectrum = _fft_power_spectrum(tuple(value - mean for value in raw))
        dominant_index = max(
            range(1, len(spectrum)),
            key=lambda index: (spectrum[index], -index),
        )
        period = size / dominant_index
        last_hit = max(index for index, value in enumerate(raw) if value)
        gap = (size - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


@lru_cache(maxsize=4096)
def _acb_scores(
    history: tuple[P638HistoryRow, ...],
    window: int = _ACB_WINDOW,
) -> dict[int, float]:
    recent = _recent(history, window)
    count = len(recent)
    expected = count * _PICK / _POOL
    variance = count * (_PICK / _POOL) * (1.0 - (_PICK / _POOL))
    sigma = math.sqrt(variance) if variance > 0 else 1.0
    frequency = _frequency(history, window)
    return {number: (expected - frequency.get(number, 0)) / sigma for number in range(1, _POOL + 1)}


@lru_cache(maxsize=4096)
def _midfreq_fourier_fusion(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicket:
    midfreq = _midfreq_scores(history)
    fourier = _fourier_scores(history, _FOURIER_LONG_WINDOW)
    midfreq_ranked = sorted(
        range(1, _POOL + 1),
        key=lambda number: (-midfreq[number], number),
    )
    fourier_ranked = sorted(
        range(1, _POOL + 1),
        key=lambda number: (-fourier[number], number),
    )
    intersection = sorted(
        set(midfreq_ranked[:20]) & set(fourier_ranked[:20]),
        key=lambda number: (-(midfreq[number] + fourier[number]), number),
    )
    if len(intersection) < _PICK:
        remainder = [number for number in midfreq_ranked if number not in intersection]
        intersection.extend(remainder)
    return tuple(sorted(intersection[:_PICK]))


@lru_cache(maxsize=4096)
def _zonal_entropy_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    chaotic = _zone_entropy(history) > _ENTROPY_CHAOS_THRESHOLD
    if chaotic:
        return (_cold_ticket(history, _COLD_WINDOW), _hot_ticket(history, _ZONE_WINDOW))
    return (_hot_ticket(history, _ZONE_WINDOW), _cold_ticket(history, _COLD_WINDOW))


@lru_cache(maxsize=4096)
def _cold_complement_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    return (_cold_ticket(history, _COLD_WINDOW), _hot_ticket(history, _COLD_WINDOW))


@lru_cache(maxsize=4096)
def _midfreq_fourier_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    return (
        _midfreq_fourier_fusion(history),
        _ranked_ticket(_fourier_scores(history, _FOURIER_LONG_WINDOW)),
    )


@lru_cache(maxsize=4096)
def _fourier30_markov30_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    return (
        _weighted_recency_ticket(history, _MARKOV_WINDOW),
        _markov_ticket(history, _MARKOV_WINDOW),
    )


@lru_cache(maxsize=4096)
def _midfreq_fourier_mk_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    return (
        _ranked_ticket(_midfreq_scores(history)),
        _ranked_ticket(_fourier_scores(history, _FOURIER_LONG_WINDOW)),
        _markov_ticket(history, _MARKOV_WINDOW),
    )


@lru_cache(maxsize=4096)
def _fourier_rhythm_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    return (
        _ranked_ticket(_fourier_scores(history, _FOURIER_LONG_WINDOW)),
        _ranked_ticket(_fourier_scores(history, _FOURIER_SHORT_WINDOW)),
        _ranked_ticket(_acb_scores(history)),
    )


@lru_cache(maxsize=4096)
def _power_precision_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    return (
        _midfreq_fourier_fusion(history),
        _cold_ticket(history, _COLD_WINDOW),
        _markov_ticket(history, _MARKOV_WINDOW),
    )


@lru_cache(maxsize=4096)
def _pp3_freqort_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    return (
        _ranked_ticket(_midfreq_scores(history)),
        _ranked_ticket(_fourier_scores(history, _FOURIER_LONG_WINDOW)),
        _cold_ticket(history, _COLD_WINDOW),
        _markov_ticket(history, _MARKOV_WINDOW),
    )


_FOURIER_RHYTHM_WINDOW: Final = 500


@lru_cache(maxsize=4096)
def _fourier_rhythm_fixed_window_scores(
    history: tuple[P638HistoryRow, ...],
) -> dict[int, float]:
    """Donor-exact period-alignment scores using a fixed, zero-padded window.

    Ported from the donor's ``tools/power_fourier_rhythm.py`` researcher
    (``fourier_rhythm_predict``/``detect_dominant_period``): every number's
    appearance bitstream occupies a *fixed*-length
    ``_FOURIER_RHYTHM_WINDOW``-slot array -- trailing slots stay zero when
    causal history is shorter than the window, exactly as the donor's
    ``np.zeros(window)`` bitstream does -- then gets detrended and
    transformed with a full complex DFT.  Only strictly positive frequency
    bins count (this excludes both the DC term and, for an even window, the
    Nyquist bin, matching NumPy's ``fftfreq`` sign convention exactly), and a
    number only scores when its dominant period falls strictly inside
    ``(2, window / 2)``, exactly as the donor gates it.  This is a distinct
    algorithm family from :func:`_fourier_scores`: that helper windows at
    the donor's actual (unpadded) length, already used by six of the eight
    prior Wave 1 strategies, but its FFT is a next-power-of-two zero-padded
    radix-2 transform -- a pre-existing, accepted approximation of the
    donor's exact-length rfft (it does not reproduce numpy's dominant-bin
    selection bit-for-bit).  This function needs a different property from
    that helper -- an exact match to the donor's *fixed* 500-slot window --
    which is why it uses the exact arbitrary-length :func:`bluestein_dft`
    instead of reusing :func:`_fourier_scores`.
    """

    window = _FOURIER_RHYTHM_WINDOW
    recent = _recent(history, window)
    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        bitstream = [0.0] * window
        for index, row in enumerate(recent):
            if number in row.numbers:
                bitstream[index] = 1.0
        if sum(bitstream) < 2:
            scores[number] = 0.0
            continue
        mean = sum(bitstream) / window
        spectrum = bluestein_dft(tuple(value - mean for value in bitstream))
        half = window // 2
        # Strictly positive frequency bins only: NumPy's even-length
        # fftfreq marks the Nyquist bin (index `half`) as negative, so the
        # donor's `xf > 0` filter keeps exactly indices 1..half-1.
        dominant_index = max(range(1, half), key=lambda index: (abs(spectrum[index]), -index))
        period = window / dominant_index
        if not (2 < period < window / 2):
            scores[number] = 0.0
            continue
        last_hit = max(index for index, value in enumerate(bitstream) if value)
        gap = (window - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


@lru_cache(maxsize=4096)
def _power_fourier_rhythm_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    """Two consecutive rank-chunks of the donor's single descending score list.

    The donor ranks all 38 numbers by score, descending, then slices the
    ranking into consecutive 6-number chunks (bet 1 = ranks 1-6, bet 2 =
    ranks 7-12) via ``numpy.argsort``.  Where many numbers tie at score 0.0
    (which numpy's unstable default sort resolves in an
    implementation-defined, version-dependent order that is not part of the
    donor's substantive algorithm), this port applies the same
    ascending-number tie-break every other Wave 1 strategy already uses.
    """

    scores = _fourier_rhythm_fixed_window_scores(history)
    ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    return (
        tuple(sorted(ranked[0:_PICK])),
        tuple(sorted(ranked[_PICK : 2 * _PICK])),
    )


@lru_cache(maxsize=4096)
def _fourier_scores_exact(
    history: tuple[P638HistoryRow, ...],
    window: int,
) -> dict[int, float]:
    """Donor-exact period-alignment scores at the causal window's own length.

    Ported bit-for-bit (up to floating-point rounding) from the donor's
    ``p128_wave2_phase2_adapters.py::_pl_fourier_scores``: ``np.fft.rfft``
    runs at ``w = len(recent)`` -- the *actual*, unpadded causal length --
    never at a padded power-of-two length.  Unlike :func:`_fourier_scores`
    (whose own FFT pads to the next power of two, a pre-existing accepted
    approximation kept as-is for the five sibling strategies that already
    ship with it), this helper reuses the exact arbitrary-length
    :func:`bluestein_dft` at that unpadded length and keeps only the
    one-sided bins ``0 .. size // 2`` NumPy's ``rfft`` would return, so its
    dominant-bin selection matches the donor's real FFT exactly rather than
    approximating it.
    """

    recent = _recent(history, window)
    size = len(recent)
    if size < 10:
        return {number: 0.0 for number in range(1, _POOL + 1)}

    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        raw = tuple(1.0 if number in row.numbers else 0.0 for row in recent)
        if sum(raw) < 2:
            scores[number] = 0.0
            continue
        mean = sum(raw) / size
        transform = bluestein_dft(tuple(value - mean for value in raw))
        power = tuple(
            value.real * value.real + value.imag * value.imag
            for value in transform[: size // 2 + 1]
        )
        if len(power) <= 1:
            scores[number] = 0.0
            continue
        dominant_index = max(range(1, len(power)), key=lambda index: (power[index], -index))
        period = size / dominant_index
        last_hit = max(index for index, value in enumerate(raw) if value)
        gap = (size - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


@lru_cache(maxsize=4096)
def _power_orthogonal_tickets(
    history: tuple[P638HistoryRow, ...],
) -> P638FirstZoneTicketSet:
    """Five orthogonal signals: MidFreq, Fourier500 (donor-exact), Cold, Markov30, ACB.

    Ported from the donor's ``p128_wave2_phase2_adapters.py::
    get_all_bets_power_orthogonal``, which composes the same building blocks
    already ported for ``pp3_freqort_4bet`` (MidFreq, Fourier500, Cold,
    Markov30) plus one ACB hedge ticket.  The Fourier ticket uses
    :func:`_fourier_scores_exact`, not :func:`_fourier_scores`: an
    independent Judge pass showed the latter's power-of-two-padded FFT does
    not reproduce the donor's exact-length ``rfft`` dominant-bin selection,
    so this strategy -- the only Wave 1 caller not already shipped against
    that approximation -- gets the exact port instead.
    """

    return (
        _ranked_ticket(_midfreq_scores(history)),
        _ranked_ticket(_fourier_scores_exact(history, _FOURIER_LONG_WINDOW)),
        _cold_ticket(history, _COLD_WINDOW),
        _markov_ticket(history, _MARKOV_WINDOW),
        _ranked_ticket(_acb_scores(history)),
    )


@dataclass(frozen=True, slots=True)
class P638StrategySpec:
    """Immutable metadata and callable boundary for one Wave 1 portfolio."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    source_paths: tuple[str, ...]
    provenance: str
    _predictor: Callable[[tuple[P638HistoryRow, ...]], P638FirstZoneTicketSet]

    def __post_init__(self) -> None:
        if type(self.strategy_id) is not str or not self.strategy_id:
            raise InvalidOutput("P638 strategy_id must be a non-empty string")
        if type(self.strategy_version) is not str or not self.strategy_version:
            raise InvalidOutput("P638 strategy_version must be a non-empty string")
        if type(self.native_ticket_count) is not int or self.native_ticket_count <= 0:
            raise InvalidOutput("P638 native_ticket_count must be positive")
        if type(self.min_history) is not int or self.min_history < 0:
            raise InvalidOutput("P638 min_history must be non-negative")
        if (
            type(self.source_paths) is not tuple
            or not self.source_paths
            or not all(type(path) is str and path for path in self.source_paths)
        ):
            raise InvalidOutput("P638 source_paths must be a non-empty string tuple")
        if type(self.provenance) is not str or not self.provenance:
            raise InvalidOutput("P638 provenance must be a non-empty string")
        if not callable(self._predictor):
            raise InvalidOutput("P638 predictor must be callable")

    def predict_tickets(
        self,
        history: object,
        lottery_type: object,
    ) -> P638TicketSet:
        """Return the ordered native portfolio of complete P638 tickets."""

        _require_power_lotto(lottery_type, self.strategy_id)
        canonical_history = coerce_p638_history(history)
        if len(canonical_history) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical_history)}"
            )

        tickets = self._predictor(canonical_history)
        if type(tickets) is not tuple:
            raise InvalidOutput(f"{self.strategy_id}: predictor must return a tuple")
        if len(tickets) != self.native_ticket_count:
            raise InvalidOutput(
                f"{self.strategy_id}: expected {self.native_ticket_count} native tickets, "
                f"got {len(tickets)}"
            )
        validated_first_zone: list[P638FirstZoneTicket] = []
        for index, ticket in enumerate(tickets):
            validated_first_zone.append(
                _validated_numbers(ticket, f"{self.strategy_id} ticket {index}")
            )

        second_zone = second_zone_predict(
            [{"special": row.second_number} for row in canonical_history]
        )
        return tuple(
            validate_power_lotto_ticket(first_zone, second_zone)
            for first_zone in validated_first_zone
        )

    def get_bets(
        self,
        history: object,
        lottery_type: object,
    ) -> P638TicketSet:
        """Alias used by replay callers that expose adapter-style methods."""

        return self.predict_tickets(history, lottery_type)


@dataclass(frozen=True, slots=True)
class P638BlockedStrategy:
    """A donor strategy excluded from this card's selected Wave 1 set."""

    strategy_id: str
    reason: str
    source_paths: tuple[str, ...]


_DONOR_SHA256 = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"

WAVE1_STRATEGIES: tuple[P638StrategySpec, ...] = (
    P638StrategySpec(
        strategy_id="zonal_entropy_2bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=2,
        min_history=30,
        source_paths=(
            "lottery_api/models/p128_wave2_phase1_adapters.py",
            "lottery_api/models/p56_wave5_powerlotto_adapters.py",
        ),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 Phase 1 entropy-gated hot/cold portfolio, P56 min-history=30."
        ),
        _predictor=_zonal_entropy_tickets,
    ),
    P638StrategySpec(
        strategy_id="cold_complement_2bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=2,
        min_history=10,
        source_paths=(
            "lottery_api/models/p128_wave2_phase1_adapters.py",
            "lottery_api/models/p56_wave5_powerlotto_adapters.py",
        ),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128/P56 cold-then-hot 100-draw complement portfolio."
        ),
        _predictor=_cold_complement_tickets,
    ),
    P638StrategySpec(
        strategy_id="midfreq_fourier_2bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=2,
        min_history=10,
        source_paths=(
            "lottery_api/models/p128_wave2_phase1_adapters.py",
            "lottery_api/models/p47_wave4_powerlotto_adapters.py",
        ),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 orthogonal MidFreq/Fourier fusion plus pure long-window Fourier."
        ),
        _predictor=_midfreq_fourier_tickets,
    ),
    P638StrategySpec(
        strategy_id="fourier30_markov30_2bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=2,
        min_history=30,
        source_paths=(
            "lottery_api/models/p128_wave2_phase1_adapters.py",
            "lottery_api/models/p56_wave5_powerlotto_adapters.py",
        ),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 Fourier30 weighted-recency ticket plus Markov30 transition ticket."
        ),
        _predictor=_fourier30_markov30_tickets,
    ),
    P638StrategySpec(
        strategy_id="midfreq_fourier_mk_3bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=3,
        min_history=30,
        source_paths=(
            "lottery_api/models/p128_wave2_phase2_adapters.py",
            "lottery_api/models/p47_wave4_powerlotto_adapters.py",
        ),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 Phase 2 ordered MidFreq, Fourier, and Markov30 portfolio."
        ),
        _predictor=_midfreq_fourier_mk_tickets,
    ),
    P638StrategySpec(
        strategy_id="fourier_rhythm_3bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=3,
        min_history=10,
        source_paths=("lottery_api/models/p128_wave2_phase2_adapters.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 Phase 2 long Fourier, short Fourier, and ACB hedge; donor RSR-7 "
            "extra-row note is retained as a low-priority data risk."
        ),
        _predictor=_fourier_rhythm_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_precision_3bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=3,
        min_history=30,
        source_paths=("lottery_api/models/p128_wave2_phase2_adapters.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 Phase 2 MidFreq/Fourier fusion, cold, and Markov30. Donor RSR-6 "
            "20-orphan bet-index=2 warning remains visible; this adapter is "
            "forward-only until the main Worker resolves that external data issue."
        ),
        _predictor=_power_precision_tickets,
    ),
    P638StrategySpec(
        strategy_id="pp3_freqort_4bet",
        strategy_version="v0.1-p638-wave1",
        native_ticket_count=4,
        min_history=30,
        source_paths=(
            "lottery_api/models/p128_wave2_phase2_adapters.py",
            "lottery_api/models/p47_wave4_powerlotto_adapters.py",
        ),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 Phase 2 ordered MidFreq, Fourier, cold, and Markov30 portfolio."
        ),
        _predictor=_pp3_freqort_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_fourier_rhythm_2bet",
        strategy_version="v0.1-p638-all10",
        native_ticket_count=2,
        min_history=100,
        source_paths=(
            "lottery_api/models/p93_tierb_replay_adapters.py",
            "tools/power_fourier_rhythm.py",
        ),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P93 Tier B adapter wraps tools/power_fourier_rhythm.py::"
            "fourier_rhythm_predict(n_bets=2, window=500); fixed-window "
            "zero-padded bitstream FFT reproduced exactly via Bluestein's "
            "algorithm (no NumPy/SciPy). Supersedes the prior "
            "DEFERRED_WAVE_2 research-ledger disposition."
        ),
        _predictor=_power_fourier_rhythm_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_orthogonal_5bet",
        strategy_version="v0.1-p638-all10",
        native_ticket_count=5,
        min_history=30,
        source_paths=("lottery_api/models/p128_wave2_phase2_adapters.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P128 Phase 2 ordered MidFreq, Fourier500, Cold, Markov30, and "
            "ACB portfolio (get_all_bets_power_orthogonal). The RSR-6 "
            "20-orphan bet-index=2 rows were a defect in the prior donor "
            "replay ledger, not this algorithm; this adapter always emits "
            "all 5 native positions including position 2 (Fourier). "
            "Supersedes the prior BLOCKED_DEFERRED_WAVE disposition."
        ),
        _predictor=_power_orthogonal_tickets,
    ),
)

WAVE1_BLOCKED_STRATEGIES: tuple[P638BlockedStrategy, ...] = ()

WAVE1_STRATEGY_BY_ID = MappingProxyType({spec.strategy_id: spec for spec in WAVE1_STRATEGIES})

__all__ = [
    "WAVE1_BLOCKED_STRATEGIES",
    "WAVE1_STRATEGIES",
    "WAVE1_STRATEGY_BY_ID",
    "P638BlockedStrategy",
    "P638FirstZoneTicket",
    "P638FirstZoneTicketSet",
    "P638HistoryRow",
    "P638StrategySpec",
    "P638Ticket",
    "P638TicketSet",
    "bluestein_dft",
    "coerce_p638_history",
]
