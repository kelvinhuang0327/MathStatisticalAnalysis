"""BigLotto composite 5-bet native strategy adapter:
TS3 (Fourier Rhythm + Cold + Tail Balance) + Markov(w=30) + Frequency Orthogonal Leftover.

Canonical reproducible migration basis:
* historical window: 101000079-115000018 (1500 aligned targets)
* success event: any of 5 tickets matches >=3 main numbers
* reproducible result: 160 / 1500 (10.67%)
* native ticket count: 5
* prefix preservation: Tickets 1-4 match canonical 4-ticket TS3+Markov output
"""

from __future__ import annotations

import cmath
import math
from collections import Counter
from itertools import combinations
from typing import ClassVar

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    PortfolioBetAdapter,
)

_MAX_NUM = 49
_PICK = 6
_MIN_HISTORY = 500
_FOURIER_WINDOW = 500
_SUM_TARGET_WINDOW = 300
_COLD_WINDOW = 100
_COLD_POOL_SIZE = 12
_TAIL_WINDOW = 100
_MARKOV_WINDOW = 30
_FREQ_WINDOW = 100


def _fft_complex_pow2(values: tuple[complex, ...]) -> tuple[complex, ...]:
    """Radix-2 complex FFT; len(values) must be a power of two."""
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
    """Inverse of _fft_complex_pow2 via forward-FFT-of-conjugate."""
    length = len(values)
    conjugated = tuple(value.conjugate() for value in values)
    transformed = _fft_complex_pow2(conjugated)
    return tuple(value.conjugate() / length for value in transformed)


def _bluestein_dft(signal: tuple[float, ...]) -> tuple[complex, ...]:
    """Exact discrete Fourier transform matching numpy.fft.fft."""
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


_COS_TABLE_500: tuple[tuple[float, ...], ...] = tuple(
    tuple(math.cos(2.0 * math.pi * k * j / _FOURIER_WINDOW) for j in range(_FOURIER_WINDOW))
    for k in range((_FOURIER_WINDOW - 1) // 2 + 1)
)
_SIN_TABLE_500: tuple[tuple[float, ...], ...] = tuple(
    tuple(math.sin(2.0 * math.pi * k * j / _FOURIER_WINDOW) for j in range(_FOURIER_WINDOW))
    for k in range((_FOURIER_WINDOW - 1) // 2 + 1)
)


def _fourier_rhythm_bet(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Ticket 1: Fourier Rhythm — FFT period analysis (window=500)."""
    h_slice = history[-_FOURIER_WINDOW:] if len(history) >= _FOURIER_WINDOW else history
    w = len(h_slice)
    if w < 10:
        return tuple(range(1, _PICK + 1))

    scores = [0.0] * (_MAX_NUM + 1)
    max_k = (w - 1) // 2

    hit_positions: dict[int, list[int]] = {i: [] for i in range(1, _MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d.numbers:
            if n <= _MAX_NUM:
                hit_positions[n].append(idx)

    use_table = w == _FOURIER_WINDOW

    for n in range(1, _MAX_NUM + 1):
        hits = hit_positions[n]
        if len(hits) < 2:
            continue

        best_mag = -1.0
        best_k = 0

        if use_table:
            for k in range(1, max_k + 1):
                c_row = _COS_TABLE_500[k]
                s_row = _SIN_TABLE_500[k]
                re = sum(c_row[j] for j in hits)
                im = sum(-s_row[j] for j in hits)
                mag = re * re + im * im
                if mag > best_mag:
                    best_mag = mag
                    best_k = k
        else:
            bh = [0.0] * w
            for j in hits:
                bh[j] = 1.0
            mean_bh = len(hits) / w
            centered = tuple(v - mean_bh for v in bh)
            yf = _bluestein_dft(centered)
            for k in range(1, max_k + 1):
                val = yf[k]
                mag = val.real * val.real + val.imag * val.imag
                if mag > best_mag:
                    best_mag = mag
                    best_k = k

        if best_k == 0:
            continue

        period = w / best_k
        if 2 < period < w / 2:
            last_hit = hits[-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)

    sorted_candidates = sorted(
        range(1, _MAX_NUM + 1),
        key=lambda n: (scores[n], -n),
        reverse=True,
    )
    return tuple(sorted(sorted_candidates[:_PICK]))


def _sum_target(history: tuple[CausalDrawRow, ...]) -> tuple[float, float]:
    """Calculate target sum range using mean reversion over trailing 300 draws."""
    h = history[-_SUM_TARGET_WINDOW:] if len(history) >= _SUM_TARGET_WINDOW else history
    sums = [sum(d.numbers) for d in h]
    n = len(sums)
    mu = sum(sums) / n
    variance = sum((x - mu) ** 2 for x in sums) / n
    sg = math.sqrt(variance)
    last_s = sum(history[-1].numbers)
    if last_s < mu - 0.5 * sg:
        return mu, mu + sg
    if last_s > mu + 0.5 * sg:
        return mu - sg, mu
    return mu - 0.5 * sg, mu + 0.5 * sg


def _cold_numbers_bet(
    history: tuple[CausalDrawRow, ...],
    exclude: set[int] | None = None,
) -> tuple[int, ...]:
    """Ticket 2: Cold Numbers with Sum Constraint v2 (pool=12, window=100)."""
    exclude_set = exclude or set()
    recent = history[-_COLD_WINDOW:] if len(history) >= _COLD_WINDOW else history
    all_nums = [n for d in recent for n in d.numbers]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, _MAX_NUM + 1) if n not in exclude_set]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))

    if len(history) < 2 or _COLD_POOL_SIZE <= _PICK:
        return tuple(sorted(sorted_cold[:_PICK]))

    pool = sorted_cold[:_COLD_POOL_SIZE]
    tlo, thi = _sum_target(history)
    tmid = (tlo + thi) / 2.0

    best_combo: tuple[int, ...] | None = None
    best_dist = float("inf")
    best_in_range = False

    for combo in combinations(pool, _PICK):
        s = sum(combo)
        in_range = tlo <= s <= thi
        dist = abs(s - tmid)
        if in_range and (not best_in_range or dist < best_dist):
            best_combo = combo
            best_dist = dist
            best_in_range = True
        elif not in_range and not best_in_range and dist < best_dist:
            best_combo = combo
            best_dist = dist

    return tuple(sorted(best_combo if best_combo is not None else pool[:_PICK]))


def _tail_balance_bet(
    history: tuple[CausalDrawRow, ...],
    exclude: set[int] | None = None,
) -> tuple[int, ...]:
    """Ticket 3: Tail Balance — balanced tail distribution (window=100)."""
    exclude_set = exclude or set()
    recent = history[-_TAIL_WINDOW:] if len(history) >= _TAIL_WINDOW else history
    all_nums = [n for d in recent for n in d.numbers]
    freq = Counter(all_nums)

    tail_groups: dict[int, list[tuple[int, int]]] = {i: [] for i in range(10)}
    for n in range(1, _MAX_NUM + 1):
        if n not in exclude_set:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: x[1], reverse=True)

    selected: list[int] = []
    available_tails = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True,
    )
    idx_in_group = {t: 0 for t in range(10)}

    while len(selected) < _PICK:
        added = False
        for tail in available_tails:
            if len(selected) >= _PICK:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break

    if len(selected) < _PICK:
        remaining = [
            n for n in range(1, _MAX_NUM + 1) if n not in selected and n not in exclude_set
        ]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[: _PICK - len(selected)])

    return tuple(sorted(selected[:_PICK]))


def _markov_orthogonal_bet(
    history: tuple[CausalDrawRow, ...],
    exclude: set[int] | None = None,
    markov_window: int = _MARKOV_WINDOW,
) -> tuple[int, ...]:
    """Ticket 4: Markov Orthogonal — transition matrix conditional probabilities (window=30)."""
    exclude_set = exclude or set()
    window = min(markov_window, len(history))
    recent = history[-window:]

    transitions: Counter[tuple[int, int]] = Counter()
    for i in range(len(recent) - 1):
        prev_nums = recent[i].numbers
        next_nums = recent[i + 1].numbers
        for p in prev_nums:
            for n in next_nums:
                transitions[(p, n)] += 1

    if len(history) < 2:
        candidates = [n for n in range(1, _MAX_NUM + 1) if n not in exclude_set]
        return tuple(sorted(candidates[:_PICK]))

    last_draw_nums = history[-1].numbers
    scores: Counter[int] = Counter()
    for prev_num in last_draw_nums:
        for n in range(1, _MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)

    candidates = [(n, scores[n]) for n in range(1, _MAX_NUM + 1) if n not in exclude_set]
    candidates.sort(key=lambda x: -x[1])
    selected = [n for n, _ in candidates[:_PICK]]

    if len(selected) < _PICK:
        remaining = [
            n for n in range(1, _MAX_NUM + 1) if n not in exclude_set and n not in selected
        ]
        selected.extend(remaining[: _PICK - len(selected)])

    return tuple(sorted(selected[:_PICK]))


def _frequency_orthogonal_bet(
    history: tuple[CausalDrawRow, ...],
    exclude: set[int] | None = None,
    window: int = _FREQ_WINDOW,
) -> tuple[int, ...]:
    """Ticket 5: Frequency Orthogonal Leftover (window=100)."""
    exclude_set = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d.numbers]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, _MAX_NUM + 1) if n not in exclude_set]
    candidates.sort(key=lambda x: freq.get(x, 0), reverse=True)
    return tuple(sorted(candidates[:_PICK]))


class BigLottoCompositeQuickPredict5BetAdapter(PortfolioBetAdapter):
    """Production 5-ticket coordinated portfolio adapter:
    TS3 (Fourier + Cold + Tail) + Markov(w=30) + Frequency Orthogonal Leftover.
    """

    strategy_id: ClassVar[str] = "legacy_composite__quick_predict_5bet_ts3_markov_freqort"
    strategy_name: ClassVar[str] = "大樂透 Quick Predict 5注（TS3 + Markov + FreqOrt）"  # noqa: RUF001
    strategy_version: ClassVar[str] = "v0.1"
    min_history: ClassVar[int] = _MIN_HISTORY
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (LotteryType.BIG_LOTTO,)
    native_ticket_count: ClassVar[int] = 5

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        bet1 = _fourier_rhythm_bet(history)
        bet2 = _cold_numbers_bet(history, exclude=set(bet1))
        bet3 = _tail_balance_bet(history, exclude=set(bet1) | set(bet2))
        used_3 = set(bet1) | set(bet2) | set(bet3)
        bet4 = _markov_orthogonal_bet(history, exclude=used_3, markov_window=_MARKOV_WINDOW)
        used_4 = used_3 | set(bet4)
        bet5 = _frequency_orthogonal_bet(history, exclude=used_4, window=_FREQ_WINDOW)
        return (bet1, bet2, bet3, bet4, bet5)


__all__ = [
    "BigLottoCompositeQuickPredict5BetAdapter",
]
