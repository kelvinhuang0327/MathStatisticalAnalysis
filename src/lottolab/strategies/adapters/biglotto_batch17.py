"""BigLotto native-strategy batch 17 (Base Method Universe Batch03 intake):
thin ports of four frozen legacy BACKTESTED methods (donor commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9``, the same frozen snapshot as
waves 1-14 and batches 15-16). No algorithm was changed, tuned, or "improved"
during the port. Selected by
``B_BASE_METHOD_UNIVERSE_COVERAGE_AND_BATCH03_SELECTION_R1`` as the four
distinct-mechanism, no-blocking-dependency candidates from that task's
23-member, previously-unverified ``READY_FOR_INTAKE`` pool.

NUMPY_SUBSTITUTION note (applies to the two Fourier-based ports below,
``predict_biglotto_triple_strike`` and ``backtest_biglotto_markov_4bet``):
this project has zero scientific-computing dependencies and every prior
wave/batch port hand-rewrites donor numpy/scipy usage into pure stdlib
Python -- the established precedent is ``daily539_fourier4.py``'s hand-rolled
DFT. Both donors' ``scipy.fft.fft``/``fftfreq`` usage is translated as an
exact mathematical equivalent: a direct summation DFT restricted to the
positive-frequency bins ``xf > 0`` actually inspects (indices
``k = 1..(window-1)//2``, matching ``numpy.fft.fftfreq``'s own bin layout for
both even and odd window lengths), with the cosine/sine table for those bins
precomputed once per call and shared across all 49 numbers' bitstreams -- an
implementation-only efficiency choice (avoids redundant transcendental
calls across 49 numbers), not a change to the DFT formula: every number's
score is still exactly ``|DFT_k|`` at its own peak bin, computed the same
way. Where the donor ranks via ``numpy.argsort(...)[::-1]`` (ascending-
stable, then reversed), this port uses ``sorted(..., key=...)[::-1]`` rather
than ``sorted(..., reverse=True)`` -- reversing an ascending-stable order
also reverses tied keys' relative order, which Python's native
``reverse=True`` (stable in *both* directions, ties keep original order)
does not do, matching this repository's established translation convention
(``biglotto_batch16.py``'s Gum port). Donor code that itself already uses
plain Python ``sort(key=..., reverse=True)`` or a negated-key sort (e.g. the
Markov and Hot-Stop-Rebound rankings below) is left exactly as such --
both forms preserve original relative order for tied keys, so no translation
is needed there.

RNG/seed contract (applies to all four ports): each of the four donor files'
only randomness (``np.random.seed(SEED)``) lives exclusively inside that
file's own backtest/evaluation harness (``run_backtest``), never inside the
production selection path ported here -- confirmed independently while
reading each donor file in full for this port, and consistent with the
Batch03 selection authority's own causal-input-cleanliness finding. No RNG
replacement was needed for any of the four -- unlike ``backtest_apriori`` in
batch 16, none of these four donors have a non-causal randomness fallback
reachable from their own selection logic.

* ``legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504`` -- donor
  ``tools/predict_biglotto_triple_strike.py``, ``generate_triple_strike``.
  Three-ticket, zero-overlap-by-construction ensemble: a Fourier-rhythm bet,
  then a sum-constrained cold-numbers bet (excluding bet 1's numbers), then a
  tail-balance bet (excluding bets 1-2's numbers). ``min_history=150``: this
  donor file declares no ``MIN_HISTORY`` constant of its own, but its sibling
  ``backtest_biglotto_markov_4bet.py`` embeds a byte-identical copy of these
  same three functions (see that port's note below) under an explicit
  ``MIN_HISTORY_BUFFER = 150``, independently confirmed by diffing the two
  donor files this task -- used here as the best-evidenced floor for the
  identical mechanism, disclosed as an inference from the sibling file
  rather than assumed.
* ``legacy_biglotto__backtest_sum_constraint__acb3b118300d`` -- donor
  ``tools/backtest_sum_constraint.py``, ``generate_ts_sum_constrained``.
  Combination-level sum mean-reversion: predicts next period's target sum
  range from the prior period's sum tier (vs a 300-draw mean/std), then --
  per bet -- enumerates ``C(pool_size, 6)`` combinations from a
  top-``pool_size`` signal pool and keeps the one closest to the target
  range. Ported at the function's own declared defaults
  (``pool_size=12, apply_to='all'``): the donor's ``main()`` only grid-
  searches a parameter sweep for diagnostic reporting and never fixes one
  configuration as a production recommendation independent of a given
  dataset's measured edge, so adopting a grid-search "winner" here would be
  retuning from an evaluation outcome (out of scope for this intake).
  ``min_history=150`` matches the donor's own explicit ``MIN_HISTORY``
  constant. The donor's ``len(history) < 2`` fallback branch (a plain,
  unconstrained top-6-per-pool triple-strike variant local to this same
  file) is unreachable at ``min_history=150`` and is omitted, matching
  wave 14's "same final state, not a behavior change" precedent for
  provably-inert donor branches (see ``biglotto_batch16.py``'s Gum note).
* ``legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b`` -- donor
  ``tools/backtest_biglotto_markov_4bet.py``, ``generate_ts3_markov4``.
  Four-ticket portfolio: the same Triple Strike three bets, plus a fourth,
  Markov-transition-ranked bet restricted to numbers none of the first three
  bets used ("orthogonal"). PHASE_0 SEQUENCING NOTE (the Batch03 selection
  authority's disclosed caveat): this donor file does not import
  ``predict_biglotto_triple_strike.py`` -- it embeds its own byte-identical
  copy of ``fourier_rhythm_bet``/``cold_numbers_bet``/``tail_balance_bet``/
  ``generate_triple_strike`` (independently diffed against the sibling donor
  file this task: identical). There is therefore no real cross-file
  dependency to sequence; this port preserves the donor's own duplication
  verbatim (separate ``_markov4_``-prefixed helpers below, not a shared call
  into this module's own triple-strike section) rather than introducing a
  coupling the donor itself does not have. ``min_history=150`` matches the
  donor's own explicit ``MIN_HISTORY_BUFFER`` constant.
* ``legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae`` --
  donor ``tools/backtest_biglotto_hot_stop_rebound.py``,
  ``generate_hot_stop_bet``. Single-ticket compound AND-gate signal: numbers
  with ``freq100 >= 15`` (near-100-draw frequency) AND ``gap >= 10`` (draws
  since last appearance) simultaneously, ranked by ``freq * gap``, padded
  with the highest-frequency remaining numbers if fewer than 6 qualify.
  Ported at the function's own declared defaults
  (``freq_threshold=15, gap_threshold=10``), which match both the module's
  own "信號定義" docstring header and the Batch03 selection authority's
  mechanism summary -- the donor's ``main()`` grid-search over a parameter
  sweep is a diagnostic sensitivity analysis, not an alternative production
  configuration. ``min_history=200`` matches the donor's own explicit
  ``MIN_HISTORY`` constant. This is the only one of the four ports using
  ``BetAdapter`` (single-ticket, ``ResponseShape.SINGLE_TICKET``); the other
  three are ``PortfolioBetAdapter`` (``ResponseShape.PORTFOLIO``).

Shared DFT substrate note: ``_dft_tables``/``_dft_positive_magnitudes`` below
are a generic numpy-to-stdlib translation of the DFT formula itself (pure
math substrate, like this module's shared ``_MAX_NUM``/``_PICK``), reused by
both Fourier-based ports. Everything downstream of that substrate -- which
window, which post-processing, how scores map to a bet -- is kept as
separate, per-donor-file helpers (``_ts_*`` vs ``_markov4_*``), never shared,
so each canonical ID's own mechanism stays independently traceable to its
own donor file.
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
# legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b
# ═════════════════════════════════════════════════════════════════════════

_MARKOV4_STRATEGY_ID = "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b"
_MARKOV4_MIN_HISTORY = 150
_MARKOV4_FOURIER_WINDOW = 500
_MARKOV4_COLD_WINDOW = 100
_MARKOV4_COLD_POOL_SIZE = 12
_MARKOV4_TAIL_WINDOW = 100
_MARKOV4_SUM_WINDOW = 300
_MARKOV4_TRANSITION_WINDOW = 100
_MARKOV4_NATIVE_TICKET_COUNT = 4


def _markov4_sum_target(
    history: tuple[CausalDrawRow, ...], window: int = _MARKOV4_SUM_WINDOW
) -> tuple[float, float]:
    """Byte-identical donor duplicate of ``_ts_sum_target`` -- see the
    PHASE_0 SEQUENCING NOTE in the module docstring for why this is kept as
    a separate copy rather than a shared call."""

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


def _markov4_fourier_rhythm_bet(
    history: tuple[CausalDrawRow, ...], window: int = _MARKOV4_FOURIER_WINDOW
) -> list[int]:
    """Byte-identical donor duplicate of ``_ts_fourier_rhythm_bet``."""

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


def _markov4_cold_numbers_bet(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _MARKOV4_COLD_WINDOW,
    exclude: frozenset[int] | None = None,
    pool_size: int = _MARKOV4_COLD_POOL_SIZE,
) -> list[int]:
    """Byte-identical donor duplicate of ``_ts_cold_numbers_bet``."""

    excluded = exclude or frozenset()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for draw in recent for n in draw.numbers)
    candidates = [n for n in range(1, _MAX_NUM + 1) if n not in excluded]
    sorted_cold = sorted(candidates, key=lambda n: freq.get(n, 0))

    if len(history) < 2 or pool_size <= _PICK:
        return sorted(sorted_cold[:_PICK])

    pool = sorted_cold[:pool_size]
    target_low, target_high = _markov4_sum_target(history)
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


def _markov4_tail_balance_bet(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _MARKOV4_TAIL_WINDOW,
    exclude: frozenset[int] | None = None,
) -> list[int]:
    """Byte-identical donor duplicate of ``_ts_tail_balance_bet``."""

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


def _markov4_generate_triple_strike(history: tuple[CausalDrawRow, ...]) -> list[list[int]]:
    """Byte-identical donor duplicate of ``_ts_generate_triple_strike``."""

    bet1 = _markov4_fourier_rhythm_bet(history)
    bet2 = _markov4_cold_numbers_bet(history, exclude=frozenset(bet1))
    bet3 = _markov4_tail_balance_bet(history, exclude=frozenset(bet1) | frozenset(bet2))
    return [bet1, bet2, bet3]


def _markov4_orthogonal_bet(
    history: tuple[CausalDrawRow, ...],
    *,
    exclude: frozenset[int] | None = None,
    markov_window: int = _MARKOV4_TRANSITION_WINDOW,
) -> list[int]:
    """Port of ``markov_orthogonal_bet``: deterministic first-order Markov
    transition rank, restricted to numbers outside ``exclude``, bet 4."""

    excluded = exclude or frozenset()
    window = min(markov_window, len(history))
    recent = history[-window:] if window > 0 else history

    transitions: Counter[tuple[int, int]] = Counter()
    for i in range(len(recent) - 1):
        prev_nums = recent[i].numbers
        next_nums = recent[i + 1].numbers
        for p in prev_nums:
            for n in next_nums:
                transitions[(p, n)] += 1

    if len(history) < 2:
        candidates_fallback = [n for n in range(1, _MAX_NUM + 1) if n not in excluded]
        return sorted(candidates_fallback[:_PICK])

    last_draw_nums = history[-1].numbers
    scores: Counter[int] = Counter()
    for prev_num in last_draw_nums:
        for n in range(1, _MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)

    candidates = [(n, scores[n]) for n in range(1, _MAX_NUM + 1) if n not in excluded]
    candidates.sort(key=lambda item: -item[1])
    selected = [n for n, _score in candidates[:_PICK]]

    if len(selected) < _PICK:
        remaining = [n for n in range(1, _MAX_NUM + 1) if n not in excluded and n not in selected]
        selected.extend(remaining[: _PICK - len(selected)])

    return sorted(selected[:_PICK])


def _markov4_generate_ts3_markov4(
    history: tuple[CausalDrawRow, ...], *, markov_window: int = _MARKOV4_TRANSITION_WINDOW
) -> list[list[int]]:
    """Port of ``generate_ts3_markov4``: Triple Strike 3 bets + orthogonal
    Markov 4th bet."""

    ts3_bets = _markov4_generate_triple_strike(history)
    ts3_used: set[int] = set()
    for bet in ts3_bets:
        ts3_used.update(bet)
    bet4 = _markov4_orthogonal_bet(
        history, exclude=frozenset(ts3_used), markov_window=markov_window
    )
    return [*ts3_bets, bet4]


class BigLottoBacktestBiglottoMarkov4BetAdapter(PortfolioBetAdapter):
    """Triple Strike 3 bets + orthogonal Markov-transition 4th bet. See the
    module docstring's PHASE_0 SEQUENCING NOTE for why this port embeds its
    own Triple-Strike helpers rather than depending on the sibling
    ``BigLottoPredictBiglottoTripleStrikeAdapter``."""

    strategy_id = _MARKOV4_STRATEGY_ID
    strategy_name = "大樂透 三重打擊 + Markov 正交注四"
    strategy_version = "v0.1"
    min_history = _MARKOV4_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _MARKOV4_NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        bets = _markov4_generate_ts3_markov4(history)
        return tuple(tuple(bet) for bet in bets)


# ═════════════════════════════════════════════════════════════════════════
# legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae
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
    "BigLottoBacktestBiglottoMarkov4BetAdapter",
    "BigLottoBacktestSumConstraintAdapter",
    "BigLottoPredictBiglottoTripleStrikeAdapter",
]
