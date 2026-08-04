"""BigLotto native-strategy wave 1: thin ports of frozen legacy BACKTESTED methods.

Each adapter below is a direct, dependency-free port of one frozen legacy
source file (see each class's ``provenance`` in ``strategies/catalog.py`` for
the exact commit/path/hash). Where the donor used numpy/pandas only for
operations with an exact, order-independent pure-Python equivalent (scalar
``math.exp``, integer counting, ``Counter``), this port uses the stdlib
equivalent instead so this module has zero new dependencies. No algorithm
was changed, tuned, or "improved" during the port.
"""

from __future__ import annotations

import math
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


# ─── legacy_biglotto__graph_predictor__cd70713a5709 ─────────────────────────
# Donor: ai_lab/scripts/graph_predictor.py — CooccurrenceGraphPredictor.predict


def _graph_build_graph(
    history: tuple[CausalDrawRow, ...], max_num: int = _MAX_NUM
) -> dict[int, dict[int, float]]:
    adj: dict[int, dict[int, float]] = {}
    for i, draw in enumerate(reversed(history)):
        weight = math.exp(-0.02 * i)
        nums = draw.numbers
        for a, b in combinations(nums, 2):
            adj.setdefault(a, {})
            adj.setdefault(b, {})
            adj[a][b] = adj[a].get(b, 0.0) + weight
            adj[b][a] = adj[b].get(a, 0.0) + weight
    return adj


def _graph_pagerank(
    adj: dict[int, dict[int, float]],
    max_num: int = _MAX_NUM,
    damping: float = 0.85,
    iterations: int = 20,
) -> dict[int, float]:
    nodes = list(range(1, max_num + 1))
    rank = dict.fromkeys(nodes, 1.0 / max_num)
    for _ in range(iterations):
        new_rank: dict[int, float] = {}
        for n in nodes:
            incoming = sum(
                adj[m].get(n, 0.0) * rank[m] / max(sum(adj[m].values()), 1)
                for m in nodes
                if m in adj and adj[m].get(n, 0.0) > 0
            )
            new_rank[n] = (1 - damping) / max_num + damping * incoming
        rank = new_rank
    return rank


def _graph_select_clique(
    adj: dict[int, dict[int, float]],
    candidates: list[int],
    pick_count: int = _PICK,
) -> tuple[int, ...]:
    selected: list[int] = []
    remaining = list(candidates)
    while len(selected) < pick_count and remaining:
        best: int | None = None
        best_score = -1.0
        for c in remaining:
            score = sum(adj.get(c, {}).get(s, 0.0) for s in selected) + 0.1
            if score > best_score:
                best_score = score
                best = c
        if best is not None:
            selected.append(best)
            remaining.remove(best)
    return tuple(sorted(selected))


class BigLottoGraphPredictorAdapter(BetAdapter):
    """PageRank-centrality + greedy-clique co-occurrence graph predictor."""

    strategy_id = "legacy_biglotto__graph_predictor__cd70713a5709"
    strategy_name = "大樂透 Co-occurrence Graph (PageRank + Clique)"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        adj = _graph_build_graph(history, _MAX_NUM)
        rank = _graph_pagerank(adj, _MAX_NUM)
        sorted_by_rank = sorted(rank.items(), key=lambda item: item[1], reverse=True)
        top_candidates = [n for n, _ in sorted_by_rank[:15]]
        return _graph_select_clique(adj, top_candidates, _PICK)


# ─── legacy_biglotto__backtest_must_hit__909c91fd2fd0 ───────────────────────
# Donor: tools/backtest_must_hit.py — MustHitBacktester.predict_must_hit(top_n=6)


class BigLottoMustHitTop6Adapter(BetAdapter):
    """Top-6-most-frequent-in-last-50-draws "must hit" predictor."""

    strategy_id = "legacy_biglotto__backtest_must_hit__909c91fd2fd0"
    strategy_name = "大樂透 Must-Hit Top6（近50期最頻繁）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 50
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        freq = Counter(n for draw in history[-50:] for n in draw.numbers)
        return tuple(n for n, _ in freq.most_common(6))


# ─── legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac ─────────────
# Donor: tools/dynamic_frequency_predictor.py — DynamicFrequencyPredictor.predict


_DYNAMIC_FREQUENCY_WINDOWS = (30, 50, 100, 200, 300)
_DYNAMIC_FREQUENCY_LOOKBACK = 50
_DYNAMIC_FREQUENCY_MIN_HISTORY = 200


def _dynamic_frequency_predict(
    history: tuple[CausalDrawRow, ...], window: int
) -> tuple[int, ...]:
    recent = history[-window:] if len(history) > window else history
    all_nums = [n for draw in recent for n in draw.numbers]
    freq = Counter(all_nums)
    return tuple(n for n, _ in freq.most_common(6))


def _dynamic_frequency_optimal_window(history: tuple[CausalDrawRow, ...]) -> int:
    lookback = _DYNAMIC_FREQUENCY_LOOKBACK
    window_scores: dict[int, float] = {}
    for window in _DYNAMIC_FREQUENCY_WINDOWS:
        total_hits = 0
        for i in range(lookback):
            test_idx = len(history) - lookback + i
            prefix = history[:test_idx]
            actual = set(history[test_idx].numbers)
            predicted = set(_dynamic_frequency_predict(prefix, window))
            total_hits += len(predicted & actual)
        window_scores[window] = total_hits / lookback
    return max(window_scores, key=lambda window: window_scores[window])


class BigLottoDynamicFrequencyAdapter(BetAdapter):
    """Self-tuning frequency-window predictor (best of 5 frozen windows)."""

    strategy_id = "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac"
    strategy_name = "大樂透 Dynamic Frequency（自動選窗）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = _DYNAMIC_FREQUENCY_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        best_window = _dynamic_frequency_optimal_window(history)
        return _dynamic_frequency_predict(history, best_window)


# ─── legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee ───────────────
# Donor: tools/hot_cooccurrence_analyzer.py — HotCooccurrenceAnalyzer.analyze_and_recommend


def _cooccurrence_hot_numbers(
    history: tuple[CausalDrawRow, ...], window_size: int
) -> list[tuple[int, int]]:
    recent = history[-window_size:] if len(history) > window_size else history
    all_numbers = [n for draw in recent for n in draw.numbers]
    return Counter(all_numbers).most_common(None)


def _cooccurrence_matrix(
    history: tuple[CausalDrawRow, ...], window_size: int
) -> dict[int, dict[int, float]]:
    recent = history[-window_size:] if len(history) > window_size else history
    co: dict[int, dict[int, float]] = {
        i: dict.fromkeys(range(1, _MAX_NUM + 1), 0.0) for i in range(1, _MAX_NUM + 1)
    }
    for draw in recent:
        numbers = draw.numbers
        for i, num1 in enumerate(numbers):
            for num2 in numbers[i + 1 :]:
                co[num1][num2] += 1
                co[num2][num1] += 1
    if len(recent) > 0:
        max_co = len(recent)
        for i in co:
            for j in co[i]:
                co[i][j] = co[i][j] / max_co
    return co


def _cooccurrence_apply_rules(
    hot_numbers: list[int],
    co_matrix: dict[int, dict[int, float]],
    pick_count: int,
    cooccurrence_weight: float = 0.3,
) -> tuple[int, ...]:
    if len(hot_numbers) <= pick_count:
        return tuple(sorted(hot_numbers))

    scores: dict[int, float] = {}
    for i, num in enumerate(hot_numbers):
        rank_score = (len(hot_numbers) - i) / len(hot_numbers)
        co_scores = [
            co_matrix[num].get(other, 0.0) for other in hot_numbers if other != num
        ]
        co_score = (sum(co_scores) / len(co_scores)) if co_scores else 0.0
        scores[num] = (1 - cooccurrence_weight) * rank_score + cooccurrence_weight * co_score

    sorted_nums = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
    return tuple(sorted(sorted_nums[:pick_count]))


class BigLottoHotCooccurrenceAdapter(BetAdapter):
    """Hot-number + co-occurrence-weighted predictor."""

    strategy_id = "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee"
    strategy_name = "大樂透 Hot Co-occurrence Analyzer"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        hot_freq = _cooccurrence_hot_numbers(history, 50)
        hot_nums = [n for n, _ in hot_freq[:20]]
        co_matrix = _cooccurrence_matrix(history, 100)
        return _cooccurrence_apply_rules(hot_nums, co_matrix, _PICK)


# ─── legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4 ────────────
# Donor: tools/predict_biglotto_echo_phase2.py, plus two pure helper functions
# reused (by the donor itself) from tools/predict_biglotto_echo_2bet.py
# (echo_detector, continuous_temperature) and tools/predict_biglotto_echo_3bet.py
# (structural_score). Only these three pure, side-effect-free functions are
# reused; none of the DB-loading/CLI code from those two files is used.
# Native output: phase2_echo_2bet's 2 tickets, then phase2_echo_3bet's 3
# tickets, in that fixed source order — 5 tickets total, one strategy identity.

_ECHO_MAX_LAG = 5


def _echo_detector(
    history: tuple[CausalDrawRow, ...], max_lag: int = _ECHO_MAX_LAG
) -> dict[int, float]:
    if len(history) < max_lag + 1:
        return {}
    latest = set(history[-1].numbers)
    echo_scores: dict[int, float] = {}
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)].numbers)
        overlap = latest & past
        overlap_count = len(overlap)
        if overlap_count >= 2:
            weight = overlap_count / _PICK * (1.0 / lag)
            for n in overlap:
                echo_scores[n] = echo_scores.get(n, 0.0) + weight * 0.5
            echo_candidates = past - latest
            for n in echo_candidates:
                echo_scores[n] = echo_scores.get(n, 0.0) + weight * 1.0
    if echo_scores:
        max_score = max(echo_scores.values())
        if max_score > 0:
            for n in echo_scores:
                echo_scores[n] /= max_score
    return echo_scores


def _continuous_temperature(
    history: tuple[CausalDrawRow, ...], window: int = 50
) -> dict[int, float]:
    recent = history[-window:] if len(history) > window else history
    short_window = min(20, len(recent))
    short_recent = history[-short_window:] if len(history) > short_window else history

    freq_long: Counter[int] = Counter()
    for d in recent:
        for n in d.numbers:
            freq_long[n] += 1

    freq_short: Counter[int] = Counter()
    for d in short_recent:
        for n in d.numbers:
            freq_short[n] += 1

    gaps: dict[int, int] = {}
    for n in range(1, _MAX_NUM + 1):
        gap = 0
        for d in reversed(history):
            if n in d.numbers:
                break
            gap += 1
        gaps[n] = gap

    temperatures: dict[int, float] = {}
    freq_values = [freq_long.get(n, 0) for n in range(1, _MAX_NUM + 1)]
    freq_sorted = sorted(freq_values)

    for n in range(1, _MAX_NUM + 1):
        f = freq_long.get(n, 0)
        rank = sum(1 for v in freq_sorted if v <= f) / _MAX_NUM
        freq_component = rank

        median_gap = _MAX_NUM / _PICK
        gap_component = math.exp(-gaps[n] / median_gap)

        expected_short = short_window * _PICK / _MAX_NUM
        expected_long = len(recent) * _PICK / _MAX_NUM
        short_ratio = freq_short.get(n, 0) / max(expected_short, 0.1)
        long_ratio = f / max(expected_long, 0.1)
        trend_component = min(1.0, max(0.0, 0.5 + (short_ratio - long_ratio) * 0.5))

        temperatures[n] = 0.40 * freq_component + 0.30 * gap_component + 0.30 * trend_component

    return temperatures


def _structural_score(bet: list[int]) -> int:
    s = sum(bet)
    odd = sum(1 for n in bet if n % 2 == 1)
    zones = [0, 0, 0]
    for n in bet:
        if n <= 16:
            zones[0] += 1
        elif n <= 33:
            zones[1] += 1
        else:
            zones[2] += 1
    consec = sum(1 for i in range(len(bet) - 1) if bet[i + 1] - bet[i] == 1)
    spread = bet[-1] - bet[0]

    score = 0
    if 100 <= s <= 200:
        score += 2
    if 120 <= s <= 180:
        score += 2
    if 2 <= odd <= 4:
        score += 2
    if all(z >= 1 for z in zones):
        score += 2
    if consec <= 1:
        score += 1
    if spread >= 25:
        score += 1
    return score


def _echo_signal_strength(
    history: tuple[CausalDrawRow, ...], max_lag: int = _ECHO_MAX_LAG
) -> float:
    if len(history) < max_lag + 1:
        return 0.0
    latest = set(history[-1].numbers)
    total_score = 0.0
    max_possible = 0.0
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)].numbers)
        overlap = len(latest & past)
        weight = 1.0 / lag
        max_possible += _PICK * weight
        total_score += overlap * weight
    if max_possible == 0:
        return 0.0
    return min(1.0, total_score / max_possible)


def _rolling_echo_accuracy(
    history: tuple[CausalDrawRow, ...], lookback: int = 50, echo_threshold: float = 0.3
) -> float:
    if len(history) < lookback + 10:
        return 0.5
    hits = 0
    events = 0
    start = max(10, len(history) - lookback)
    for idx in range(start, len(history)):
        train = history[:idx]
        actual = set(history[idx].numbers)
        echoes = _echo_detector(train, max_lag=5)
        echo_nums = {n for n, sc in echoes.items() if sc > echo_threshold}
        if echo_nums:
            events += 1
            if len(echo_nums & actual) > 0:
                hits += 1
    if events == 0:
        return 0.5
    return hits / events


def _adaptive_echo_weight(
    history: tuple[CausalDrawRow, ...], base_weight: float = 0.25, lookback: int = 50
) -> tuple[float, float, float]:
    strength = _echo_signal_strength(history)
    accuracy = _rolling_echo_accuracy(history, lookback)

    strength_factor = 0.3 + strength * 2.4
    strength_factor = min(1.5, max(0.3, strength_factor))

    accuracy_factor = 0.3 + accuracy * 1.7
    accuracy_factor = min(1.5, max(0.3, accuracy_factor))

    weight = base_weight * strength_factor * accuracy_factor
    weight = min(0.50, max(0.05, weight))

    return weight, strength, accuracy


def _phase2_echo_2bet(
    history: tuple[CausalDrawRow, ...], window: int = 50, lookback: int = 50
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    temps = _continuous_temperature(history, window)
    echoes = _echo_detector(history, max_lag=5)
    ew, _strength, _accuracy = _adaptive_echo_weight(history, lookback=lookback)

    hot_scores: dict[int, float] = {}
    cold_scores: dict[int, float] = {}
    for n in range(1, _MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        hot_scores[n] = t * (1 - ew) + e * ew
        cold_scores[n] = (1 - t) * (1 - ew) + e * ew

    hot_ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)
    cold_ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True)

    bet1 = sorted(hot_ranked[:_PICK])
    used = set(bet1)

    bet2: list[int] = []
    for n in cold_ranked:
        if n not in used and len(bet2) < _PICK:
            bet2.append(n)
    bet2 = sorted(bet2[:_PICK])

    return tuple(bet1), tuple(bet2)


def _phase2_echo_3bet(
    history: tuple[CausalDrawRow, ...], window: int = 50, lookback: int = 50
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    temps = _continuous_temperature(history, window)
    echoes = _echo_detector(history, max_lag=5)
    ew, _strength, _accuracy = _adaptive_echo_weight(history, lookback=lookback)

    hot_scores: dict[int, float] = {}
    cold_scores: dict[int, float] = {}
    for n in range(1, _MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        hot_scores[n] = t * (1 - ew) + e * ew
        cold_scores[n] = (1 - t) * (1 - ew) + e * ew

    hot_ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)
    bet1 = sorted(hot_ranked[:_PICK])
    used = set(bet1)

    cold_ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True)
    bet2: list[int] = []
    for n in cold_ranked:
        if n not in used and len(bet2) < _PICK:
            bet2.append(n)
    bet2 = sorted(bet2[:_PICK])
    used.update(bet2)

    bet3_scores: dict[int, float] = {}
    for n in range(1, _MAX_NUM + 1):
        if n in used:
            continue
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        warm_proximity = 1.0 - abs(t - 0.5) * 2.0
        echo_share = min(0.7, ew * 2)
        bet3_scores[n] = e * echo_share + warm_proximity * (1 - echo_share)

    bet3_ranked = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)
    candidates = sorted(bet3_ranked[:12])

    if len(candidates) < _PICK:
        candidates = sorted(n for n in range(1, _MAX_NUM + 1) if n not in used)

    best_bet3: list[int] | None = None
    best_score = -1.0

    if len(candidates) >= _PICK:
        for combo in combinations(candidates, _PICK):
            bet = sorted(combo)
            sc = _structural_score(bet)
            avg_s = sum(bet3_scores.get(n, 0.0) for n in bet) / _PICK
            composite = sc + avg_s * 0.1
            if composite > best_score:
                best_score = composite
                best_bet3 = bet

    if best_bet3 is None:
        best_bet3 = sorted(candidates[:_PICK])

    return tuple(bet1), tuple(bet2), tuple(best_bet3)


class BigLottoEchoPhase2Adapter(PortfolioBetAdapter):
    """Adaptive echo-weighted portfolio: Phase-2 2-bet, then Phase-2 3-bet (5 tickets)."""

    strategy_id = "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4"
    strategy_name = "大樂透 Echo-Aware Phase 2（自適應權重，2注+3注）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 5

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        bet1, bet2 = _phase2_echo_2bet(history)
        bet3, bet4, bet5 = _phase2_echo_3bet(history)
        return (bet1, bet2, bet3, bet4, bet5)


__all__ = [
    "BigLottoDynamicFrequencyAdapter",
    "BigLottoEchoPhase2Adapter",
    "BigLottoGraphPredictorAdapter",
    "BigLottoHotCooccurrenceAdapter",
    "BigLottoMustHitTop6Adapter",
]
