"""BigLotto native-strategy wave 4: thin ports of frozen legacy BACKTESTED methods.

Each adapter below is a direct, dependency-free port of one frozen legacy
source file (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``, the
same frozen snapshot as waves 1-3; see each class's ``provenance`` in
``strategies/catalog.py`` for the exact path/hash). No algorithm was
changed, tuned, or "improved" during the port.

Three of the four donor files below are further thin coverage-optimization
wrappers around the donor's own
``lottery_api/models/unified_predictor.py::UnifiedPredictionEngine``, exactly
like wave 3. Rather than re-derive and re-verify the five shared engine
ticket functions a second time, this module imports wave 3's already-tested
ports directly (``_unified_deviation_ticket`` / ``_unified_markov_ticket`` /
``_unified_statistical_ticket`` / ``_unified_frequency_ticket``) --
``lottolab.strategies.adapters.biglotto_wave3`` is a sibling module in the
same ``strategies.adapters`` package, so this is not a layer violation (see
``tests/architecture/test_dependency_rules.py``); byte-identical reuse is
strictly stronger evidence of parity than a second independent
transcription would be.

New engine methods ported here, not needed by waves 1-3:

* ``hot_cold_mix_predict`` -- only its ``numbers`` field is load-bearing for
  this port; the donor's own ``confidence``/``method``/``temp_levels``/
  ``hot_count`` fields are never read by ``bets``, so
  ``_calculate_multi_window_consistency``, ``_calculate_transition_stability``
  and ``_classify_temperature_levels`` (which feed only those discarded
  fields) are correctly not ported -- only
  ``_multi_window_temperature_analysis`` and
  ``_detect_hot_cold_transitions`` actually shape ``numbers``. The donor's
  ``np.clip(velocity / 10, -1, 1)`` is reproduced with plain ``min``/``max``
  (bit-identical for these small-integer-derived floats -- no unstable sort
  or platform-dependent reduction is involved).
* ``zone_balance_predict`` -- likewise only its ``numbers`` field is
  load-bearing; ``_calculate_zone_quality`` feeds only the discarded
  ``confidence``/``method`` fields and is not ported. ``_dynamic_zone_partition``
  uses plain ``sorted(..., reverse=True)`` (CPython's stable sort, not
  NumPy), so no argsort reproduction is needed here. The donor's zone
  ``start``/``end`` bounds are the min/max of each frequency-rank bucket,
  not a contiguous numeric range -- ported exactly as-is, including that a
  number technically outside its own bucket's numeric span but inside
  another bucket's ``[start, end]`` window is double-countable in the
  ``zone_counts``/``recent_zone_counts`` tally; this is the donor's own
  documented behavior (``fixed size-then-slice`` on a frequency-sorted
  list), not a bug this port should "fix."
* ``tools/negative_selector.py::NegativeSelector.predict_kill_numbers`` --
  used by two of the four donor files below to exclude numbers before the
  final candidate ranking. Every call site in both donor files passes its
  own ``history`` argument through explicitly (``predict_kill_numbers(count=N,
  history=history)``), so ``NegativeSelector``'s own DB-backed
  ``self.get_data()`` fallback path is provably unreachable here and is not
  ported -- only the pure ``history is not None`` branch is. The donor's
  ``strategy == "aggressive_mixed"`` branch inside the score loop is
  likewise provably unreachable: ``predict_kill_numbers`` only ever assigns
  ``strategy`` to ``"targeted_cold"``, ``"safe_conservative"``, or
  ``"balanced"`` -- omitted, not "improved away."
* ``OptimizedEnsemblePredictor`` (``tools/optimized_ensemble.py``) is a
  fully self-contained class (no shared engine dependency). Its own
  ``np.argsort(final_scores[1:])[::-1] + 1`` ranking reuses wave 3's
  already-verified ``_numpy_argsort`` (the literal NumPy introsort port),
  copied by reference via import, not retranscribed. ``np.exp`` is
  reproduced with ``math.exp`` (identical libm delegate for scalar
  float64 input).

Donor parity for the two new shared engine methods (hot_cold_mix,
zone_balance) was independently re-derived by reading
``lottery_api/models/unified_predictor.py`` at the frozen commit (no
pandas/scipy/sklearn is installed in this environment to execute the donor
class directly, though plain NumPy -- used here only to spot-check
``np.mean``/``np.std``/``np.clip``/``np.argsort`` scalar semantics during
development, never at adapter runtime -- is available). This module's own
test goldens were computed by executing this module's own adapters, the
same methodology wave 3 used for the same reason.
"""

# pyright: reportPrivateUsage=false
# (intentional reuse of wave 3's already-verified private ticket/argsort
# helpers -- see module docstring; wave 3 itself is not modified)

from __future__ import annotations

import math
from collections import Counter
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _numpy_argsort,
    _ticket,
    _unified_deviation_ticket,
    _unified_frequency_ticket,
    _unified_markov_ticket,
    _unified_statistical_ticket,
)

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6


# ─── tools/negative_selector.py::NegativeSelector.predict_kill_numbers ─────
# (see module docstring: DB fallback and the dead "aggressive_mixed" branch
# are not ported).


def _regional_entropy(history: tuple[CausalDrawRow, ...], num_zones: int = 5) -> float:
    """Port ``NegativeSelector._calculate_regional_entropy``."""

    if not history:
        return 0.0
    zone_size = _MAX_NUM / num_zones
    zone_counts = [0] * num_zones
    for draw in history:
        for number in draw.numbers:
            zone_index = min(int((number - 1) / zone_size), num_zones - 1)
            zone_counts[zone_index] += 1
    total_hits = sum(zone_counts)
    if total_hits == 0:
        return 0.0
    entropy = 0.0
    for count in zone_counts:
        probability = count / total_hits
        if probability > 0:
            entropy -= probability * math.log2(probability)
    return entropy


def _kill_numbers(history: tuple[CausalDrawRow, ...], count: int) -> list[int]:
    """Port ``NegativeSelector.predict_kill_numbers`` (``history`` always
    provided by the caller, so the DB-backed fallback is unreachable)."""

    if len(history) < 30:
        return []
    recent_30 = history[-30:]
    entropy = _regional_entropy(recent_30, num_zones=5)
    if entropy < 2.0:
        dynamic_count = min(15, count + 2)
    elif entropy > 2.2:
        dynamic_count = max(5, count - 5)
    else:
        dynamic_count = count
    frequency_100 = Counter(number for draw in history[-100:] for number in draw.numbers)
    gaps = dict.fromkeys(range(_MIN_NUM, _MAX_NUM + 1), 999)
    for index, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            if gaps[number] == 999:
                gaps[number] = index
    scores: list[tuple[int, float]] = []
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        frequency = frequency_100.get(number, 0)
        gap = gaps[number]
        score: float = frequency
        if gap > 22:
            score += 100
        scores.append((number, score))
    scores.sort(key=lambda item: item[1])
    return sorted(number for number, _score in scores[:dynamic_count])


# ─── UnifiedPredictionEngine.hot_cold_mix_predict (numbers-only; see module
#     docstring for the confidence/method fields deliberately not ported) ──


def _multi_window_temperature_analysis(
    history: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    if len(history) < 15:
        frequency = Counter(number for draw in history for number in draw.numbers)
        maximum = max(frequency.values()) if frequency else 1
        return {
            number: frequency.get(number, 0) / maximum
            for number in range(_MIN_NUM, _MAX_NUM + 1)
        }
    windows = {
        "short": min(15, len(history)),
        "mid": min(25, len(history)),
        "long": min(45, len(history)),
    }
    window_scores: dict[str, dict[int, float]] = {}
    for name, size in windows.items():
        recent = history[-size:]
        frequency = Counter(number for draw in recent for number in draw.numbers)
        maximum = max(frequency.values()) if frequency else 1
        window_scores[name] = {
            number: frequency.get(number, 0) / maximum
            for number in range(_MIN_NUM, _MAX_NUM + 1)
        }
    return {
        number: (
            window_scores["short"][number] * 0.5
            + window_scores["mid"][number] * 0.3
            + window_scores["long"][number] * 0.2
        )
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }


def _detect_hot_cold_transitions(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    if len(history) < 30:
        return dict.fromkeys(range(_MIN_NUM, _MAX_NUM + 1), 0.0)
    period1 = history[-30:-20]
    period2 = history[-20:-10]
    period3 = history[-10:]
    frequency1 = Counter(number for draw in period1 for number in draw.numbers)
    frequency2 = Counter(number for draw in period2 for number in draw.numbers)
    frequency3 = Counter(number for draw in period3 for number in draw.numbers)
    transition_scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        f1, f2, f3 = (
            frequency1.get(number, 0),
            frequency2.get(number, 0),
            frequency3.get(number, 0),
        )
        velocity = (f3 - f2) - (f2 - f1)
        transition_scores[number] = max(-1.0, min(1.0, velocity / 10))
    minimum_score = min(transition_scores.values())
    maximum_score = max(transition_scores.values())
    score_range = maximum_score - minimum_score if maximum_score > minimum_score else 1
    return {
        number: (score - minimum_score) / score_range
        for number, score in transition_scores.items()
    }


def _unified_hot_cold_mix_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.hot_cold_mix_predict``'s number
    selection (multi-window temperature fused with transition velocity)."""

    window_scores = _multi_window_temperature_analysis(history)
    transition_scores = _detect_hot_cold_transitions(history)
    final_scores = {
        number: window_scores[number] * 0.7 + transition_scores[number] * 0.3
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }
    ranked = sorted(final_scores, key=lambda number: final_scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


# ─── UnifiedPredictionEngine.zone_balance_predict (numbers-only; see module
#     docstring for the confidence/method fields deliberately not ported) ──


class _Zone:
    __slots__ = ("end", "numbers", "start")

    def __init__(self, numbers: list[int]) -> None:
        self.start = min(numbers)
        self.end = max(numbers)
        self.numbers = sorted(numbers)


def _dynamic_zone_partition(history: tuple[CausalDrawRow, ...]) -> list[_Zone]:
    """Port ``UnifiedPredictionEngine._dynamic_zone_partition`` (49-number
    domain always selects 4 zones; frequency-rank buckets, not contiguous
    numeric ranges -- see module docstring)."""

    frequency = Counter(number for draw in history for number in draw.numbers)
    pairs = [(number, frequency.get(number, 0)) for number in range(_MIN_NUM, _MAX_NUM + 1)]
    num_zones = 4
    sorted_pairs = sorted(pairs, key=lambda pair: pair[1], reverse=True)
    zone_size = len(sorted_pairs) // num_zones
    remainder = len(sorted_pairs) % num_zones
    zones: list[_Zone] = []
    start_index = 0
    for zone_index in range(num_zones):
        current_size = zone_size + (1 if zone_index < remainder else 0)
        zone_numbers = [
            pair[0] for pair in sorted_pairs[start_index : start_index + current_size]
        ]
        if zone_numbers:
            zones.append(_Zone(zone_numbers))
        start_index += current_size
    return zones


def _unified_zone_balance_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.zone_balance_predict``'s number
    selection. The donor's history-direction standardization check is not
    ported: ``CausalDrawRow`` history is always oldest-first under this
    framework's own contract (every wave 1-3 adapter already relies on this),
    so the donor's reversal branch is provably unreachable here."""

    zones = _dynamic_zone_partition(history)
    analysis_window = min(len(history), 80)
    zone_counts = [0] * len(zones)
    for draw in history[-analysis_window:]:
        for number in draw.numbers:
            for zone_index, zone in enumerate(zones):
                if zone.start <= number <= zone.end:
                    zone_counts[zone_index] += 1
                    break
    recent_zone_counts = [0] * len(zones)
    for draw in history[-20:]:
        for number in draw.numbers:
            for zone_index, zone in enumerate(zones):
                if zone.start <= number <= zone.end:
                    recent_zone_counts[zone_index] += 1
                    break
    total = sum(zone_counts) if sum(zone_counts) > 0 else 1
    recent_total = sum(recent_zone_counts) if sum(recent_zone_counts) > 0 else 1
    targets: list[int] = []
    for zone_index in range(len(zones)):
        historical_ratio = zone_counts[zone_index] / total
        recent_ratio = recent_zone_counts[zone_index] / recent_total
        combined_ratio = historical_ratio * 0.7 + recent_ratio * 0.3
        targets.append(round(combined_ratio * _PICK))
    while sum(targets) < _PICK:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > _PICK:
        targets[targets.index(max(targets))] -= 1

    frequency = Counter(number for draw in history for number in draw.numbers)
    recent_30 = history[-30:]
    predicted: list[int] = []
    for zone_index, zone in enumerate(zones):
        scored: list[tuple[int, float]] = []
        for number in zone.numbers:
            base_frequency = frequency.get(number, 0)
            recent_frequency = sum(
                1 for draw in recent_30 for candidate in draw.numbers if candidate == number
            )
            scored.append((number, base_frequency * 0.6 + recent_frequency * 0.4))
        scored.sort(key=lambda item: item[1], reverse=True)
        predicted.extend(number for number, _score in scored[: targets[zone_index]])
    return _ticket(sorted(predicted))


# ─── tools/optimized_ensemble.py::OptimizedEnsemblePredictor (self-
#     contained; BIG_LOTTO config only -- see class docstring) ─────────────


def _momentum_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    window = 5
    recent = history[-window:]
    scores = dict.fromkeys(range(_MIN_NUM, _MAX_NUM + 1), 0.0)
    for index, draw in enumerate(recent):
        weight = math.exp(index / window)
        for number in draw.numbers:
            if number <= _MAX_NUM:
                scores[number] += weight
    for number in history[-1].numbers:
        if number <= _MAX_NUM:
            scores[number] *= 1.2
    return scores


def _entropy_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    window = 150
    recent = history[-window:]
    all_numbers = [number for draw in recent for number in draw.numbers]
    frequency = Counter(all_numbers)
    target_frequency = (len(recent) * _PICK) / _MAX_NUM
    return {
        number: 1.0 / (abs(frequency.get(number, 0) - target_frequency) + 0.1)
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }


def _lag_reversion_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    last_seen = dict.fromkeys(range(_MIN_NUM, _MAX_NUM + 1), -1)
    for index, draw in enumerate(history):
        for number in draw.numbers:
            if number <= _MAX_NUM:
                last_seen[number] = index
    current_index = len(history)
    lag_min, lag_max = 6, 12
    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        lag = current_index - last_seen[number]
        if lag_min <= lag <= lag_max:
            scores[number] = 1.5
        elif lag > 25:
            scores[number] = 1.25
        else:
            scores[number] = 1.0
    return scores


def _unified_optimized_ensemble_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``OptimizedEnsemblePredictor.predict`` (``n_bets=1``, BIG_LOTTO
    config: ``w_m=0.4, w_e=0.3, w_l=0.2, entropy_multiplier=40.0``)."""

    if len(history) < 20:
        return _ticket(list(range(1, 7)))
    momentum = _momentum_scores(history)
    entropy = _entropy_scores(history)
    lag_reversion = _lag_reversion_scores(history)
    final_scores = [0.0] * (_MAX_NUM + 1)
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        final_scores[number] = (
            momentum[number] * 0.4 + entropy[number] * 40.0 * 0.3 + lag_reversion[number] * 0.2
        )
    ascending = _numpy_argsort(final_scores[1:])
    ranked_numbers = [index + 1 for index in reversed(ascending)]
    return _ticket(sorted(ranked_numbers[:_PICK]))


# ─── legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5 ────────────────
# Donor: lottery_api/models/biglotto_3bet_optimizer.py --
# BigLotto3BetOptimizer.predict_3bets_diversified(use_kill=True, the
# donor's own default). P1 dynamic kill-number exclusion (count=10) then
# three engine methods (deviation 2.0, markov 1.5, statistical 1.0) into a
# weighted Counter, top-18 candidate pool, sliced at (0,6)/(4,10)/(8,14) --
# an intentionally overlapping 3-ticket "diversified" portfolio.


class BigLottoThreeBetOptimizerAdapter(PortfolioBetAdapter):
    """P1 kill-filtered top-3 engine coverage optimizer: top-18 pool sliced
    into three overlapping 6-number tickets -- a 3-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5"
    strategy_name = "大樂透三注智能組合預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        kill_numbers = _kill_numbers(history, count=10)
        deviation = _unified_deviation_ticket(history)
        markov = _unified_markov_ticket(history)
        statistical = _unified_statistical_ticket(history)
        candidates: Counter[int] = Counter()
        for ticket, weight in ((deviation, 2.0), (markov, 1.5), (statistical, 1.0)):
            for number in ticket:
                candidates[number] += cast(int, weight)
        for number in kill_numbers:
            candidates[number] = -9999
        top_18 = [number for number, _score in candidates.most_common(18)]
        return tuple(_ticket(top_18[start:end]) for start, end in ((0, 6), (4, 10), (8, 14)))


# ─── legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad ─────────────────
# Donor: lottery_api/models/biglotto_tme_optimizer.py --
# BigLottoTMEOptimizer.predict_4bets(use_kill=False, the donor's own
# default -- P1 kill-filtering is only ever computed for its own log line
# when enabled and never applied to the four independent bets in either
# mode). Four fully independent engine methods, one bet each, in fixed
# order: statistical, deviation, markov, hot_cold_mix.


class BigLottoTMEOptimizerAdapter(PortfolioBetAdapter):
    """Triple/Quad-Method-Ensemble: one bet per independently-run engine
    method (statistical/deviation/markov/hot_cold_mix), no slicing or
    blending -- a 4-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad"
    strategy_name = "大樂透 TME 4注智能組合預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 4

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        statistical = _unified_statistical_ticket(history)
        deviation = _unified_deviation_ticket(history)
        markov = _unified_markov_ticket(history)
        hot_cold_mix = _unified_hot_cold_mix_ticket(history)
        return (
            _ticket(sorted(statistical)),
            _ticket(sorted(deviation)),
            _ticket(sorted(markov)),
            _ticket(sorted(hot_cold_mix)),
        )


# ─── legacy_biglotto__optimized_ensemble__e05e0fde22d7 ─────────────────────
# Donor: tools/optimized_ensemble.py -- OptimizedEnsemblePredictor.predict
# (n_bets=1, BIG_LOTTO config). Momentum + entropy + lag-reversion scoring
# fused and ranked by NumPy argsort -- a single-ticket strategy.


class BigLottoOptimizedEnsembleAdapter(BetAdapter):
    """ROI-stacked momentum/entropy/lag-reversion ensemble ranked by NumPy
    argsort -- a single-ticket strategy (donor's own ``n_bets=1`` default;
    only ``bets[0]`` is native, the ``all_bets``/orthogonal-complement branch
    for ``n_bets > 1`` is never exercised by any donor call site)."""

    strategy_id = "legacy_biglotto__optimized_ensemble__e05e0fde22d7"
    strategy_name = "ROI 優化集成預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _unified_optimized_ensemble_ticket(history)


# ─── legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511 ──────
# Donor: tools/predict_biglotto_115000007_2bets.py --
# BigLotto2BetOptimizer.predict_2bets(use_kill=True, the donor's own
# default). P1 dynamic kill-number exclusion (count=8) then five engine
# methods (deviation 2.5, markov 2.0, statistical 1.5, zone_balance 1.5,
# frequency 1.0) into a weighted Counter, top-20 candidate pool, bet 1 =
# pool[0:6], bet 2 = pool[6:12].


class BigLottoTwoBetElitePredictorAdapter(PortfolioBetAdapter):
    """P1 kill-filtered five-engine-method coverage optimizer: top-20 pool
    sliced at [0:6] and [6:12] -- a 2-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511"
    strategy_name = "大樂透兩注精選預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        kill_numbers = _kill_numbers(history, count=8)
        deviation = _unified_deviation_ticket(history)
        markov = _unified_markov_ticket(history)
        statistical = _unified_statistical_ticket(history)
        zone_balance = _unified_zone_balance_ticket(history)
        frequency = _unified_frequency_ticket(history)
        candidates: Counter[int] = Counter()
        for ticket, weight in (
            (deviation, 2.5),
            (markov, 2.0),
            (statistical, 1.5),
            (zone_balance, 1.5),
            (frequency, 1.0),
        ):
            for number in ticket:
                candidates[number] += cast(int, weight)
        for number in kill_numbers:
            candidates[number] = -9999
        top_20 = [number for number, _score in candidates.most_common(20)]
        bet1 = top_20[:6]
        bet2 = top_20[6:12] if len(top_20) >= 12 else top_20[:6]
        return (_ticket(sorted(bet1)), _ticket(sorted(bet2)))


__all__ = [
    "BigLottoOptimizedEnsembleAdapter",
    "BigLottoTMEOptimizerAdapter",
    "BigLottoThreeBetOptimizerAdapter",
    "BigLottoTwoBetElitePredictorAdapter",
]
