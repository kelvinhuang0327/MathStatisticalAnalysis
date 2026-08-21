"""BigLotto native-strategy Batch03 publication adapters.

These are the three MAIN_ABSENT adapters selected from the frozen Batch03
implementation commit ``aee5c23a54fa44af607d2365876c4567f4f3159d``:
Triple Strike, Sum Constraint, and Hot Stop Rebound. Their donor source
bindings and algorithm bodies are retained exactly from that commit.

The source commit also contains a local Markov implementation for the
canonical ID ``legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b``.
That implementation is intentionally excluded here because current main
already owns that canonical ID with the owner-authorized authoritative
implementation. No Markov evaluation lineage is transferred.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from itertools import combinations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    PortfolioBetAdapter,
)

_MAX_NUM = 49
_PICK = 6


# ═════════════════════════════════════════════════════════════════════════
# Shared DFT substrate (numpy.fft -> stdlib translation; see module docstring)
# ═════════════════════════════════════════════════════════════════════════


def _dft_tables(window: int) -> tuple[list[list[float]], list[list[float]]]:
    """Precompute ``cos(2*pi*k*t/window)``/``sin(...)`` for every positive-
    frequency bin ``k=1..(window-1)//2`` (matching ``numpy.fft.fftfreq``'s
    positive-frequency layout) and every ``t=0..window-1``, shared across all
    49 numbers' score computation in one call."""

    k_max = (window - 1) // 2
    cos_table = [
        [math.cos(2.0 * math.pi * k * t / window) for t in range(window)]
        for k in range(1, k_max + 1)
    ]
    sin_table = [
        [math.sin(2.0 * math.pi * k * t / window) for t in range(window)]
        for k in range(1, k_max + 1)
    ]
    return cos_table, sin_table


def _dft_positive_magnitudes(
    bits: list[float],
    cos_table: list[list[float]],
    sin_table: list[list[float]],
) -> list[float]:
    """Magnitude of ``bits``'s DFT at each precomputed positive-frequency
    bin. ``magnitudes[j]`` corresponds to bin ``k = j + 1``."""

    window = len(bits)
    mean_bit = sum(bits) / window
    centered = [b - mean_bit for b in bits]
    magnitudes: list[float] = []
    for cos_row, sin_row in zip(cos_table, sin_table, strict=True):
        real = sum(c * cos_t for c, cos_t in zip(centered, cos_row, strict=True))
        imag = -sum(c * sin_t for c, sin_t in zip(centered, sin_row, strict=True))
        magnitudes.append(math.hypot(real, imag))
    return magnitudes


# ═════════════════════════════════════════════════════════════════════════
# legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504
# ═════════════════════════════════════════════════════════════════════════

_TS_STRATEGY_ID = "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504"
_TS_MIN_HISTORY = 150
_TS_FOURIER_WINDOW = 500
_TS_COLD_WINDOW = 100
_TS_COLD_POOL_SIZE = 12
_TS_TAIL_WINDOW = 100
_TS_SUM_WINDOW = 300
_TS_NATIVE_TICKET_COUNT = 3


def _ts_sum_target(
    history: tuple[CausalDrawRow, ...], window: int = _TS_SUM_WINDOW
) -> tuple[float, float]:
    """Port of ``_sum_target``: mean-reversion target sum range derived from
    the prior period's sum tier vs a rolling mean/std."""

    recent = history[-window:] if len(history) >= window else history
    sums = [sum(draw.numbers) for draw in recent]
    mean_sum = statistics.fmean(sums)
    std_sum = statistics.pstdev(sums)
    last_sum = sum(history[-1].numbers)
    if last_sum < mean_sum - 0.5 * std_sum:
        return mean_sum, mean_sum + std_sum
    if last_sum > mean_sum + 0.5 * std_sum:
        return mean_sum - std_sum, mean_sum
    return mean_sum - 0.5 * std_sum, mean_sum + 0.5 * std_sum


def _ts_fourier_rhythm_bet(
    history: tuple[CausalDrawRow, ...], window: int = _TS_FOURIER_WINDOW
) -> list[int]:
    """Port of ``fourier_rhythm_bet``: FFT-periodicity rank, bet 1."""

    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams: dict[int, list[float]] = {n: [0.0] * w for n in range(1, _MAX_NUM + 1)}
    for idx, draw in enumerate(h_slice):
        for n in draw.numbers:
            if n <= _MAX_NUM:
                bitstreams[n][idx] = 1.0

    cos_table, sin_table = _dft_tables(w)
    scores = [0.0] * (_MAX_NUM + 1)
    if cos_table:
        for n in range(1, _MAX_NUM + 1):
            bh = bitstreams[n]
            if sum(bh) < 2:
                continue
            magnitudes = _dft_positive_magnitudes(bh, cos_table, sin_table)
            peak_index = max(range(len(magnitudes)), key=lambda i: magnitudes[i])
            freq_val = (peak_index + 1) / w
            period = 1.0 / freq_val
            if 2 < period < w / 2:
                last_hit = max(t for t in range(w) if bh[t] == 1.0)
                gap = (w - 1) - last_hit
                scores[n] = 1.0 / (abs(gap - period) + 1.0)

    ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: scores[n])[::-1]
    return sorted(ranked[:_PICK])


def _ts_cold_numbers_bet(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _TS_COLD_WINDOW,
    exclude: frozenset[int] | None = None,
    pool_size: int = _TS_COLD_POOL_SIZE,
) -> list[int]:
    """Port of ``cold_numbers_bet``: sum-constrained cold-numbers rank,
    bet 2."""

    excluded = exclude or frozenset()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for draw in recent for n in draw.numbers)
    candidates = [n for n in range(1, _MAX_NUM + 1) if n not in excluded]
    sorted_cold = sorted(candidates, key=lambda n: freq.get(n, 0))

    if len(history) < 2 or pool_size <= _PICK:
        return sorted(sorted_cold[:_PICK])

    pool = sorted_cold[:pool_size]
    target_low, target_high = _ts_sum_target(history)
    target_mid = (target_low + target_high) / 2.0

    best_combo: tuple[int, ...] | None = None
    best_distance = math.inf
    best_in_range = False
    for combo in combinations(pool, _PICK):
        combo_sum = sum(combo)
        in_range = target_low <= combo_sum <= target_high
        distance = abs(combo_sum - target_mid)
        if in_range and (not best_in_range or distance < best_distance):
            best_combo, best_distance, best_in_range = combo, distance, True
        elif not in_range and not best_in_range and distance < best_distance:
            best_combo, best_distance = combo, distance

    return sorted(best_combo) if best_combo is not None else sorted(pool[:_PICK])


def _ts_tail_balance_bet(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _TS_TAIL_WINDOW,
    exclude: frozenset[int] | None = None,
) -> list[int]:
    """Port of ``tail_balance_bet``: tail-digit-balanced coverage, bet 3."""

    excluded = exclude or frozenset()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for draw in recent for n in draw.numbers)

    tail_groups: dict[int, list[tuple[int, int]]] = {t: [] for t in range(10)}
    for n in range(1, _MAX_NUM + 1):
        if n not in excluded:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for group in tail_groups.values():
        group.sort(key=lambda item: item[1], reverse=True)

    available_tails = sorted(
        (t for t in range(10) if tail_groups[t]),
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True,
    )
    index_in_group: dict[int, int] = dict.fromkeys(range(10), 0)
    selected: list[int] = []

    while len(selected) < _PICK:
        added = False
        for tail in available_tails:
            if len(selected) >= _PICK:
                break
            if index_in_group[tail] < len(tail_groups[tail]):
                number, _count = tail_groups[tail][index_in_group[tail]]
                if number not in selected:
                    selected.append(number)
                    added = True
                index_in_group[tail] += 1
        if not added:
            break

    if len(selected) < _PICK:
        remaining = [n for n in range(1, _MAX_NUM + 1) if n not in selected and n not in excluded]
        remaining.sort(key=lambda n: freq.get(n, 0), reverse=True)
        selected.extend(remaining[: _PICK - len(selected)])

    return sorted(selected[:_PICK])


def _ts_generate_triple_strike(history: tuple[CausalDrawRow, ...]) -> list[list[int]]:
    """Port of ``generate_triple_strike``: the three-bet ensemble."""

    bet1 = _ts_fourier_rhythm_bet(history)
    bet2 = _ts_cold_numbers_bet(history, exclude=frozenset(bet1))
    bet3 = _ts_tail_balance_bet(history, exclude=frozenset(bet1) | frozenset(bet2))
    return [bet1, bet2, bet3]


class BigLottoPredictBiglottoTripleStrikeAdapter(PortfolioBetAdapter):
    """Fourier + Cold + Tail zero-overlap-by-construction 3-bet ensemble.
    See module docstring for the ``min_history`` derivation."""

    strategy_id = _TS_STRATEGY_ID
    strategy_name = "大樂透 三重打擊（Fourier+冷號+尾數平衡）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = _TS_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _TS_NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        bets = _ts_generate_triple_strike(history)
        return tuple(tuple(bet) for bet in bets)


# ═════════════════════════════════════════════════════════════════════════
# legacy_biglotto__backtest_sum_constraint__acb3b118300d
# ═════════════════════════════════════════════════════════════════════════

_SUMC_STRATEGY_ID = "legacy_biglotto__backtest_sum_constraint__acb3b118300d"
_SUMC_MIN_HISTORY = 150
_SUMC_SUM_WINDOW = 300
_SUMC_POOL_SIZE = 12
_SUMC_FOURIER_WINDOW = 500
_SUMC_COLD_WINDOW = 100
_SUMC_TAIL_WINDOW = 100
_SUMC_NATIVE_TICKET_COUNT = 3


def _sumc_sum_target(
    history: tuple[CausalDrawRow, ...], window: int = _SUMC_SUM_WINDOW
) -> tuple[float, float]:
    """Port of ``compute_sum_target`` (the ``tier`` label it also returns is
    only consumed by the donor's own diagnostic printing, never by
    selection, and is omitted here)."""

    recent = history[-window:] if len(history) >= window else history
    sums = [sum(draw.numbers) for draw in recent]
    mean_sum = statistics.fmean(sums)
    std_sum = statistics.pstdev(sums)
    last_sum = sum(history[-1].numbers)
    if last_sum < mean_sum - 0.5 * std_sum:
        return mean_sum, mean_sum + std_sum
    if last_sum > mean_sum + 0.5 * std_sum:
        return mean_sum - std_sum, mean_sum
    return mean_sum - 0.5 * std_sum, mean_sum + 0.5 * std_sum


def _sumc_sum_select_from_pool(
    pool: list[int], target_low: float, target_high: float, n: int = _PICK
) -> list[int]:
    """Port of ``sum_select_from_pool``: closest-to-target-range combo."""

    if len(pool) < n:
        return sorted(pool)

    target_mid = (target_low + target_high) / 2.0
    best_combo: tuple[int, ...] | None = None
    best_distance = math.inf
    best_in_range = False
    for combo in combinations(pool, n):
        combo_sum = sum(combo)
        in_range = target_low <= combo_sum <= target_high
        distance = abs(combo_sum - target_mid)
        if in_range and (not best_in_range or distance < best_distance):
            best_combo, best_distance, best_in_range = combo, distance, True
        elif not in_range and not best_in_range and distance < best_distance:
            best_combo, best_distance = combo, distance

    return sorted(best_combo) if best_combo is not None else sorted(pool[:n])


def _sumc_fourier_pool(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _SUMC_FOURIER_WINDOW,
    pool_size: int = _SUMC_POOL_SIZE,
) -> list[int]:
    """Port of ``fourier_pool``: top-``pool_size`` Fourier-rank candidates."""

    h = history[-window:] if len(history) >= window else history
    w = len(h)
    bitstreams: dict[int, list[float]] = {n: [0.0] * w for n in range(1, _MAX_NUM + 1)}
    for idx, draw in enumerate(h):
        for n in draw.numbers:
            if n <= _MAX_NUM:
                bitstreams[n][idx] = 1.0

    cos_table, sin_table = _dft_tables(w)
    scores = [0.0] * (_MAX_NUM + 1)
    if cos_table:
        for n in range(1, _MAX_NUM + 1):
            bh = bitstreams[n]
            if sum(bh) < 2:
                continue
            magnitudes = _dft_positive_magnitudes(bh, cos_table, sin_table)
            if not magnitudes:
                continue
            peak_index = max(range(len(magnitudes)), key=lambda i: magnitudes[i])
            freq_val = (peak_index + 1) / w
            period = 1.0 / freq_val
            if 2 < period < w / 2:
                last_hit = max(t for t in range(w) if bh[t] == 1.0)
                gap = (w - 1) - last_hit
                scores[n] = 1.0 / (abs(gap - period) + 1.0)

    ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: scores[n])[::-1]
    return ranked[:pool_size]


def _sumc_cold_pool(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _SUMC_COLD_WINDOW,
    exclude: frozenset[int] | None = None,
    pool_size: int = _SUMC_POOL_SIZE,
) -> list[int]:
    """Port of ``cold_pool``: top-``pool_size`` cold-number candidates."""

    excluded = exclude or frozenset()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for draw in recent for n in draw.numbers)
    candidates = [n for n in range(1, _MAX_NUM + 1) if n not in excluded]
    return sorted(candidates, key=lambda n: freq.get(n, 0))[:pool_size]


def _sumc_tail_pool(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _SUMC_TAIL_WINDOW,
    exclude: frozenset[int] | None = None,
    pool_size: int = _SUMC_POOL_SIZE,
) -> list[int]:
    """Port of ``tail_pool``: top-``pool_size`` tail-balanced candidates."""

    excluded = exclude or frozenset()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for draw in recent for n in draw.numbers)

    tail_groups: dict[int, list[tuple[int, int]]] = {t: [] for t in range(10)}
    for n in range(1, _MAX_NUM + 1):
        if n not in excluded:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for group in tail_groups.values():
        group.sort(key=lambda item: item[1], reverse=True)

    available_tails = sorted(
        (t for t in range(10) if tail_groups[t]),
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True,
    )
    index_in_group: dict[int, int] = dict.fromkeys(range(10), 0)
    selected: list[int] = []

    while len(selected) < pool_size:
        added = False
        for tail in available_tails:
            if len(selected) >= pool_size:
                break
            if index_in_group[tail] < len(tail_groups[tail]):
                number, _count = tail_groups[tail][index_in_group[tail]]
                if number not in selected:
                    selected.append(number)
                    added = True
                index_in_group[tail] += 1
        if not added:
            break

    if len(selected) < pool_size:
        remaining = [n for n in range(1, _MAX_NUM + 1) if n not in selected and n not in excluded]
        remaining.sort(key=lambda n: freq.get(n, 0), reverse=True)
        selected.extend(remaining[: pool_size - len(selected)])

    return selected[:pool_size]


def _sumc_generate_ts_sum_constrained(
    history: tuple[CausalDrawRow, ...],
    *,
    pool_size: int = _SUMC_POOL_SIZE,
    apply_to: str = "all",
) -> list[list[int]]:
    """Port of ``generate_ts_sum_constrained`` at its own declared defaults.
    The donor's ``len(history) < 2`` fallback is unreachable at
    ``min_history=150`` and is omitted (see module docstring)."""

    target_low, target_high = _sumc_sum_target(history)

    fourier_pool = _sumc_fourier_pool(history, pool_size=pool_size)
    bet1 = (
        _sumc_sum_select_from_pool(fourier_pool, target_low, target_high)
        if apply_to in ("all", "bet1_only")
        else sorted(fourier_pool[:_PICK])
    )

    cold_pool = _sumc_cold_pool(history, exclude=frozenset(bet1), pool_size=pool_size)
    bet2 = (
        _sumc_sum_select_from_pool(cold_pool, target_low, target_high)
        if apply_to in ("all", "bet2_only")
        else sorted(cold_pool[:_PICK])
    )

    tail_pool = _sumc_tail_pool(
        history, exclude=frozenset(bet1) | frozenset(bet2), pool_size=pool_size
    )
    bet3 = (
        _sumc_sum_select_from_pool(tail_pool, target_low, target_high)
        if apply_to == "all"
        else sorted(tail_pool[:_PICK])
    )

    return [bet1, bet2, bet3]


class BigLottoBacktestSumConstraintAdapter(PortfolioBetAdapter):
    """Combination-level sum mean-reversion 3-bet ensemble. See module
    docstring for the ``pool_size=12, apply_to='all'`` default-parameter
    rationale."""

    strategy_id = _SUMC_STRATEGY_ID
    strategy_name = "大樂透 總和回歸約束三注"
    strategy_version = "v0.1"
    min_history = _SUMC_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _SUMC_NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        bets = _sumc_generate_ts_sum_constrained(history)
        return tuple(tuple(bet) for bet in bets)


# ═════════════════════════════════════════════════════════════════════════

_HSR_STRATEGY_ID = "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae"
_HSR_MIN_HISTORY = 200
_HSR_FREQ_THRESHOLD = 15
_HSR_GAP_THRESHOLD = 10
_HSR_FREQ_WINDOW = 100
_HSR_GAP_WINDOW = 10


def _hsr_get_hot_stop_candidates(
    history: tuple[CausalDrawRow, ...],
    *,
    freq_threshold: int = _HSR_FREQ_THRESHOLD,
    gap_threshold: int = _HSR_GAP_THRESHOLD,
    freq_window: int = _HSR_FREQ_WINDOW,
    gap_window: int = _HSR_GAP_WINDOW,
) -> tuple[list[tuple[int, int]], dict[int, int], dict[int, int]]:
    """Port of ``get_hot_stop_candidates``: numbers with both ``freq100 >=
    freq_threshold`` and ``gap >= gap_threshold``, ranked by ``freq * gap``."""

    recent_freq = history[-freq_window:] if len(history) >= freq_window else history
    freq = Counter(n for draw in recent_freq for n in draw.numbers)

    recent_gap = history[-gap_window:] if len(history) >= gap_window else history
    appeared_in_recent = {n for draw in recent_gap for n in draw.numbers}

    all_gaps: dict[int, int] = {}
    for n in range(1, _MAX_NUM + 1):
        if n in appeared_in_recent:
            all_gaps[n] = 0
            continue
        gap = 0
        for draw in reversed(history):
            if n in draw.numbers:
                break
            gap += 1
        else:
            gap = len(history)
        all_gaps[n] = gap

    all_freqs = {n: freq.get(n, 0) for n in range(1, _MAX_NUM + 1)}

    candidates = [
        (n, all_freqs[n] * all_gaps[n])
        for n in range(1, _MAX_NUM + 1)
        if all_freqs[n] >= freq_threshold and all_gaps[n] >= gap_threshold
    ]
    candidates.sort(key=lambda item: -item[1])
    return candidates, all_gaps, all_freqs


def _hsr_generate_hot_stop_bet(
    history: tuple[CausalDrawRow, ...],
    *,
    freq_threshold: int = _HSR_FREQ_THRESHOLD,
    gap_threshold: int = _HSR_GAP_THRESHOLD,
) -> tuple[int, ...]:
    """Port of ``generate_hot_stop_bet``: the single 6-number ticket."""

    candidates, _all_gaps, all_freqs = _hsr_get_hot_stop_candidates(
        history, freq_threshold=freq_threshold, gap_threshold=gap_threshold
    )
    result = [n for n, _score in candidates[:_PICK]]

    if len(result) < _PICK:
        used = set(result)
        freq_ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: -all_freqs[n])
        for n in freq_ranked:
            if n not in used:
                result.append(n)
                if len(result) >= _PICK:
                    break

    return tuple(sorted(result[:_PICK]))


class BigLottoBacktestBiglottoHotStopReboundAdapter(BetAdapter):
    """Hot-then-abruptly-stopped conjunctive reversal signal (single
    ticket). See module docstring for the default-parameter rationale."""

    strategy_id = _HSR_STRATEGY_ID
    strategy_name = "大樂透 熱號休停回歸"
    strategy_version = "v0.1"
    min_history = _HSR_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _hsr_generate_hot_stop_bet(history)



__all__ = [
    "BigLottoBacktestBiglottoHotStopReboundAdapter",
    "BigLottoBacktestSumConstraintAdapter",
    "BigLottoPredictBiglottoTripleStrikeAdapter",
]
