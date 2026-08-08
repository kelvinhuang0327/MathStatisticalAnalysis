"""Focused contract and oracle tests for the pure POWER_LOTTO Wave 2 adapters."""

from __future__ import annotations

import builtins
import inspect
import math
import os
import pathlib
import socket
import sqlite3
import statistics
import time
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from itertools import combinations, pairwise
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import powerlotto_wave2 as module
from lottolab.strategies.adapters.base import (
    InsufficientHistory,
    InvalidOutput,
    SourceNativePortfolioClosure,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.powerlotto_wave1 import P638HistoryRow, P638StrategySpec
from lottolab.strategies.adapters.powerlotto_wave2 import (
    WAVE2_BLOCKED_STRATEGIES,
    WAVE2_STRATEGIES,
)
from lottolab.strategies.powerlotto_second_zone import second_zone_predict

_EXPECTED_IDS = (
    "power_apriori_2bet",
    "power_apriori_ext_4bet",
    "lag_reversion_2bet",
    "power_lead_lag_2bet",
    "power_momentum_2bet",
    "power_fourier_gap_rebound_2bet",
    "power_c01_recency_decay_1bet",
    "power_c02_gap_overdue_1bet",
    "power_c04_zone_balanced_1bet",
    "power_c03_pair_centrality_1bet",
    "power_c05_dispersion_match_1bet",
    "power_c06_regime_cusum_1bet",
    "power_c07_borda_ensemble_1bet",
)
_EXPECTED_COUNTS = (2, 4, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1)
_EXPECTED_MIN_HISTORY = (10, 50, 10, 10, 10, 100, 10, 10, 500, 10, 10, 10, 500)


def _row(index: int) -> P638HistoryRow:
    numbers = tuple(sorted(((index * 7 + offset * 5) % 38) + 1 for offset in range(6)))
    assert len(set(numbers)) == 6
    return P638HistoryRow(
        draw=f"{index + 1:09d}",
        date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
        second_number=(index % 8) + 1,
    )


def _history(count: int) -> tuple[P638HistoryRow, ...]:
    return tuple(_row(index) for index in range(count))


def _source_native_closure_history() -> tuple[P638HistoryRow, ...]:
    return tuple(
        P638HistoryRow(
            draw=f"{index + 1:09d}",
            date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(((index + offset * 3) % 38) + 1 for offset in range(6))),
            second_number=(index % 8) + 1,
        )
        for index in range(50)
    )


def _first_zones(tickets: object) -> tuple[tuple[int, ...], ...]:
    assert type(tickets) is tuple
    return tuple(ticket[0] for ticket in tickets)  # type: ignore[index]


# ─── Module-level safety scans ──────────────────────────────────────────────


def test_module_source_has_no_forbidden_dependency_tokens() -> None:
    source = inspect.getsource(module)
    forbidden = (
        "import numpy",
        "from numpy",
        "import scipy",
        "from scipy",
        "import sqlite3",
        "from sqlite3",
        "import random",
        "from random",
        "import requests",
        "import httpx",
        "import urllib",
        "os.environ",
        "time.time(",
        "time.monotonic(",
        "datetime.now(",
        "open(",
    )
    for token in forbidden:
        assert token not in source, f"forbidden reference found: {token!r}"


@pytest.mark.parametrize("spec", WAVE2_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_prediction_uses_no_database_network_filesystem_or_clock(
    spec: P638StrategySpec, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden during prediction")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    tickets = spec.predict_tickets(_history(max(spec.min_history, 500)), LotteryType.POWER_LOTTO)
    assert len(tickets) == spec.native_ticket_count


# ─── Generic contract tests over WAVE2_STRATEGIES ──────────────────────────


def test_wave2_selection_metadata_is_ordered_and_provenanced() -> None:
    assert tuple(spec.strategy_id for spec in WAVE2_STRATEGIES) == _EXPECTED_IDS
    assert tuple(spec.native_ticket_count for spec in WAVE2_STRATEGIES) == _EXPECTED_COUNTS
    assert tuple(spec.min_history for spec in WAVE2_STRATEGIES) == _EXPECTED_MIN_HISTORY
    assert all(spec.source_paths and spec.provenance for spec in WAVE2_STRATEGIES)
    assert {
        spec.strategy_id: spec.source_native_closure_ticket_counts
        for spec in WAVE2_STRATEGIES
        if spec.source_native_closure_ticket_counts
    } == {"power_apriori_ext_4bet": (3,)}
    assert len(WAVE2_BLOCKED_STRATEGIES) == 2
    assert all(entry.reason and entry.source_paths for entry in WAVE2_BLOCKED_STRATEGIES)


@pytest.mark.parametrize("spec", WAVE2_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave2_outputs_have_native_shape_and_are_repeatable(spec: P638StrategySpec) -> None:
    history = _history(max(spec.min_history, 500))

    first = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    second = spec.get_bets(history, LotteryType.POWER_LOTTO)

    assert first == second
    assert len(first) == spec.native_ticket_count
    for ticket in first:
        assert type(ticket) is tuple
        assert len(ticket) == 2
        first_zone, second_zone = ticket
        assert first_zone == tuple(sorted(first_zone))
        assert len(set(first_zone)) == 6
        assert all(type(number) is int and 1 <= number <= 38 for number in first_zone)
        assert type(second_zone) is int and 1 <= second_zone <= 8
    assert {ticket[1] for ticket in first} == {
        second_zone_predict([{"special": row.second_number} for row in history])
    }


@pytest.mark.parametrize("spec", WAVE2_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave2_accepts_documented_mapping_coercion(spec: P638StrategySpec) -> None:
    history = _history(max(spec.min_history, 120))
    mapped: list[Mapping[str, object]] = [
        {
            "draw": row.draw,
            "date": row.date,
            "numbers": list(reversed(row.numbers)),
            "special": row.second_number,
            "lottery_type": "POWER_LOTTO",
        }
        for row in history
    ]

    typed = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    coerced = spec.predict_tickets(mapped, LotteryType.POWER_LOTTO)
    assert coerced == typed


@pytest.mark.parametrize("spec", WAVE2_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave2_rejects_non_power_lotto_context(spec: P638StrategySpec) -> None:
    with pytest.raises(UnsupportedLotteryType):
        spec.predict_tickets(_history(max(spec.min_history, 500)), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("spec", WAVE2_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave2_enforces_strategy_minimum_history(spec: P638StrategySpec) -> None:
    minimum = spec.min_history
    with pytest.raises(InsufficientHistory):
        spec.predict_tickets(_history(max(0, minimum - 1)), LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("spec", WAVE2_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave2_rejects_malformed_history(spec: P638StrategySpec) -> None:
    with pytest.raises(InvalidOutput):
        spec.predict_tickets(
            [{"draw": "1", "date": "2026-01-01", "numbers": [1, 1, 2, 3, 4, 5], "special": 1}],
            LotteryType.POWER_LOTTO,
        )


# ─── Independent oracles (fresh reimplementations, not the adapter's own) ──

_SPEC_BY_ID = {spec.strategy_id: spec for spec in WAVE2_STRATEGIES}


def _oracle_ranked_chunks(scores: Mapping[int, float], n_bets: int) -> tuple[tuple[int, ...], ...]:
    ranked = sorted(range(1, 39), key=lambda n: (-scores[n], n))
    return tuple(tuple(sorted(ranked[i * 6 : (i + 1) * 6])) for i in range(n_bets))


def _oracle_ranked_single(scores: Mapping[int, float]) -> tuple[int, ...]:
    ranked = sorted(range(1, 39), key=lambda n: (-scores[n], n))
    return tuple(sorted(ranked[:6]))


def test_power_apriori_2bet_matches_oracle() -> None:
    history = _history(250)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[tuple[int, ...], ...]:
        recent = history[-200:] if len(history) > 200 else history
        pair_counts: Counter[tuple[int, int]] = Counter()
        for row in recent:
            for pair in combinations(row.numbers, 2):
                pair_counts[pair] += 1
        top_pairs = sorted(pair_counts.items(), key=lambda item: item[1], reverse=True)[:50]
        scores = {n: 0.0 for n in range(1, 39)}
        for (a, b), count in top_pairs:
            scores[a] += count
            scores[b] += count
        return _oracle_ranked_chunks(scores, 2)

    spec = _SPEC_BY_ID["power_apriori_2bet"]
    assert _first_zones(spec.predict_tickets(history, LotteryType.POWER_LOTTO)) == oracle(history)


def test_power_apriori_ext_4bet_matches_oracle() -> None:
    history = _history(150)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[tuple[int, ...], ...]:
        recent = history[-100:] if len(history) > 100 else history
        pair_freq: Counter[tuple[int, int]] = Counter()
        for row in recent:
            for pair in combinations(row.numbers, 2):
                pair_freq[pair] += 1
        top_pairs = [
            p for p, _ in sorted(pair_freq.items(), key=lambda item: item[1], reverse=True)[:12]
        ]
        bets: list[tuple[int, ...]] = []
        used: set[int] = set()
        for pair in top_pairs:
            if len(bets) >= 4:
                break
            base = set(pair)
            extensions: Counter[int] = Counter()
            for row in recent:
                row_numbers = set(row.numbers)
                if base.issubset(row_numbers):
                    for n in row_numbers - base:
                        extensions[n] += 1
            bet = list(pair)
            for n, _ in sorted(extensions.items(), key=lambda item: item[1], reverse=True)[:4]:
                if n not in bet:
                    bet.append(n)
                if len(bet) >= 6:
                    break
            while len(bet) < 6:
                for n in range(1, 39):
                    if n not in bet:
                        bet.append(n)
                        break
            head = bet[:6]
            if len(set(head) & used) <= 2:
                bets.append(tuple(sorted(head)))
                used.update(head[:3])
        return tuple(bets)

    spec = _SPEC_BY_ID["power_apriori_ext_4bet"]
    assert _first_zones(spec.predict_tickets(history, LotteryType.POWER_LOTTO)) == oracle(history)


def test_power_apriori_ext_preserves_three_ticket_source_native_closure() -> None:
    history = _source_native_closure_history()
    raw_predictor = cast(
        Callable[
            [tuple[P638HistoryRow, ...], int],
            tuple[tuple[int, ...], ...],
        ],
        module.__dict__["_apriori_ext_tickets"],
    )
    assert raw_predictor(history, 4) == (
        (4, 7, 10, 13, 16, 19),
        (5, 8, 11, 14, 17, 20),
        (6, 9, 12, 15, 18, 21),
    )

    spec = _SPEC_BY_ID["power_apriori_ext_4bet"]
    with pytest.raises(SourceNativePortfolioClosure) as caught:
        spec.predict_tickets(history, LotteryType.POWER_LOTTO)

    assert caught.value.strategy_id == spec.strategy_id
    assert caught.value.expected_ticket_count == 4
    assert caught.value.actual_ticket_count == 3


def test_lag_reversion_2bet_matches_oracle() -> None:
    history = _history(220)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[tuple[int, ...], ...]:
        recent = history[-500:] if len(history) > 500 else history
        last_seen: dict[int, int] = {}
        intervals: dict[int, list[int]] = {n: [] for n in range(1, 39)}
        for idx, row in enumerate(recent):
            for n in row.numbers:
                if n in last_seen:
                    intervals[n].append(idx - last_seen[n])
                last_seen[n] = idx
        current = len(recent)
        fallback = 38 / 6.0
        scores: dict[int, float] = {}
        for n in range(1, 39):
            median = statistics.median(intervals[n]) if intervals[n] else fallback
            lag = current - last_seen.get(n, -1)
            scores[n] = lag / (median + 0.1)
        return _oracle_ranked_chunks(scores, 2)

    spec = _SPEC_BY_ID["lag_reversion_2bet"]
    assert _first_zones(spec.predict_tickets(history, LotteryType.POWER_LOTTO)) == oracle(history)


def test_power_lead_lag_2bet_matches_oracle() -> None:
    history = _history(180)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[tuple[int, ...], ...]:
        recent = history[-500:] if len(history) > 500 else history
        matrix: dict[int, Counter[int]] = {n: Counter() for n in range(1, 39)}
        for previous, current in pairwise(recent):
            for left in previous.numbers:
                matrix[left].update(current.numbers)
        scores = {n: 0.0 for n in range(1, 39)}
        for left in history[-1].numbers:
            row = matrix[left]
            for n in range(1, 39):
                scores[n] += row.get(n, 0)
        return _oracle_ranked_chunks(scores, 2)

    spec = _SPEC_BY_ID["power_lead_lag_2bet"]
    assert _first_zones(spec.predict_tickets(history, LotteryType.POWER_LOTTO)) == oracle(history)


def test_power_momentum_2bet_matches_oracle() -> None:
    history = _history(90)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[tuple[int, ...], ...]:
        short_window = 15
        recent = history[-short_window:] if len(history) > short_window else history
        short_freq: Counter[int] = Counter()
        for row in recent:
            short_freq.update(row.numbers)
        avg_expected = (short_window * 6.0) / 38.0
        scores = {n: short_freq.get(n, 0) / (avg_expected + 0.1) for n in range(1, 39)}
        return _oracle_ranked_chunks(scores, 2)

    spec = _SPEC_BY_ID["power_momentum_2bet"]
    assert _first_zones(spec.predict_tickets(history, LotteryType.POWER_LOTTO)) == oracle(history)


def _oracle_naive_dft(values: tuple[float, ...]) -> tuple[complex, ...]:
    import cmath

    n = len(values)
    return tuple(
        sum(values[t] * cmath.exp(-2j * math.pi * k * t / n) for t in range(n)) for k in range(n)
    )


def test_power_fourier_gap_rebound_2bet_matches_oracle() -> None:
    history = _history(160)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[tuple[int, ...], ...]:
        recent = history[-500:] if len(history) > 500 else history
        size = len(recent)
        scores = {n: 0.0 for n in range(1, 39)}
        for n in range(1, 39):
            raw = tuple(1.0 if n in row.numbers else 0.0 for row in recent)
            if sum(raw) < 2:
                continue
            mean = sum(raw) / size
            spectrum = _oracle_naive_dft(tuple(v - mean for v in raw))
            positive_bound = math.ceil(size / 2)
            if positive_bound <= 1:
                continue
            dominant = max(range(1, positive_bound), key=lambda i: (abs(spectrum[i]), -i))
            freq = dominant / size
            if freq == 0:
                continue
            period = 1.0 / freq
            if not (2 < period < size / 2):
                continue
            last_hit = max(i for i, v in enumerate(raw) if v)
            gap = (size - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)

        recent30 = history[-30:] if len(history) >= 30 else history
        freq30: Counter[int] = Counter()
        for row in recent30:
            freq30.update(row.numbers)
        last_seen_gap: dict[int, int] = {}
        n30 = len(recent30)
        for idx, row in enumerate(recent30):
            for n in row.numbers:
                last_seen_gap[n] = n30 - 1 - idx
        avg_gap = 38 / 6.0
        for n in range(1, 39):
            if freq30.get(n, 0) < 3 or n not in last_seen_gap:
                continue
            gap = last_seen_gap[n]
            if gap > avg_gap * 1.2:
                scores[n] += 1.5 * (gap / avg_gap - 1.2 + 1)
        return _oracle_ranked_chunks(scores, 2)

    spec = _SPEC_BY_ID["power_fourier_gap_rebound_2bet"]
    assert _first_zones(spec.predict_tickets(history, LotteryType.POWER_LOTTO)) == oracle(history)


def test_power_c01_recency_decay_1bet_matches_oracle() -> None:
    history = _history(260)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        lookback = history[-200:] if len(history) > 200 else history
        scores = {n: 0.0 for n in range(1, 39)}
        ln2 = math.log(2)
        for age, row in enumerate(reversed(lookback)):
            weight = math.exp(-ln2 * age / 50)
            for n in row.numbers:
                scores[n] += weight
        return _oracle_ranked_single(scores)

    spec = _SPEC_BY_ID["power_c01_recency_decay_1bet"]
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert _first_zones(tickets) == (oracle(history),)


def test_power_c02_gap_overdue_1bet_matches_oracle() -> None:
    history = _history(140)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        last_seen: dict[int, int] = {}
        for idx, row in enumerate(history):
            for n in row.numbers:
                last_seen[n] = idx
        n_prior = len(history)
        scores = {
            n: (n_prior - 1 - last_seen[n] if n in last_seen else n_prior) / 6.333
            for n in range(1, 39)
        }
        return _oracle_ranked_single(scores)

    spec = _SPEC_BY_ID["power_c02_gap_overdue_1bet"]
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert _first_zones(tickets) == (oracle(history),)


_ORACLE_ZONE_LOW = tuple(range(1, 14))
_ORACLE_ZONE_MID = tuple(range(14, 26))
_ORACLE_ZONE_HIGH_ITER = (32, 33, 34, 35, 36, 37, 38, 26, 27, 28, 29, 30, 31)


def _oracle_zone_targets(calibration: tuple[P638HistoryRow, ...]) -> tuple[int, int, int]:
    low, mid, high = set(_ORACLE_ZONE_LOW), set(_ORACLE_ZONE_MID), set(_ORACLE_ZONE_HIGH_ITER)
    low_counts: list[int] = []
    mid_counts: list[int] = []
    high_counts: list[int] = []
    for row in calibration:
        low_counts.append(sum(1 for n in row.numbers if n in low))
        mid_counts.append(sum(1 for n in row.numbers if n in mid))
        high_counts.append(sum(1 for n in row.numbers if n in high))
    t_low, t_mid, t_high = (
        statistics.mode(low_counts),
        statistics.mode(mid_counts),
        statistics.mode(high_counts),
    )
    total = t_low + t_mid + t_high
    if total != 6:
        t_mid = max(0, t_mid + (6 - total))
        total = t_low + t_mid + t_high
        if total != 6:
            t_high = max(0, t_high + (6 - total))
    return (t_low, t_mid, t_high)


def test_power_c04_zone_balanced_1bet_matches_oracle() -> None:
    history = _history(560)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        t_low, t_mid, t_high = _oracle_zone_targets(history[:500])
        freq: Counter[int] = Counter()
        for row in history:
            freq.update(row.numbers)
        low_r = sorted(_ORACLE_ZONE_LOW, key=lambda n: -freq.get(n, 0))
        mid_r = sorted(_ORACLE_ZONE_MID, key=lambda n: -freq.get(n, 0))
        high_r = sorted(_ORACLE_ZONE_HIGH_ITER, key=lambda n: -freq.get(n, 0))
        selected = low_r[:t_low] + mid_r[:t_mid] + high_r[:t_high]
        if len(selected) < 6:
            remaining = sorted(
                (n for n in range(1, 39) if n not in set(selected)), key=lambda n: -freq.get(n, 0)
            )
            selected = selected + remaining[: 6 - len(selected)]
        return tuple(sorted(selected[:6]))

    spec = _SPEC_BY_ID["power_c04_zone_balanced_1bet"]
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert _first_zones(tickets) == (oracle(history),)


def test_power_c03_pair_centrality_1bet_matches_oracle() -> None:
    history = _history(130)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        counts: Counter[tuple[int, int]] = Counter()
        for row in history:
            for pair in combinations(row.numbers, 2):
                counts[pair] += 1
        degree: dict[int, float] = defaultdict(float)
        for (a, b), count in counts.items():
            if count >= 2:
                degree[a] += count
                degree[b] += count
        return _oracle_ranked_single(degree)

    spec = _SPEC_BY_ID["power_c03_pair_centrality_1bet"]
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert _first_zones(tickets) == (oracle(history),)


def test_power_c05_dispersion_match_1bet_matches_oracle() -> None:
    history = _history(110)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        sums = [sum(row.numbers) for row in history]
        spans = [max(row.numbers) - min(row.numbers) for row in history]
        target_sum = sum(sums) / len(sums)
        target_span = sum(spans) / len(spans)
        norm_sum = target_sum if target_sum > 0 else 117.0
        norm_span = target_span if target_span > 0 else 25.0
        selected: list[int] = []
        remaining = list(range(1, 39))
        for _ in range(6):
            best_n, best_score = None, math.inf
            for n in remaining:
                trial = [*selected, n]
                t_sum = sum(trial)
                t_span = max(trial) - min(trial) if len(trial) > 1 else 0
                proj_sum = t_sum + (6 - len(trial)) * (norm_sum / 6)
                proj_span = max(t_span, norm_span * len(trial) / 6)
                score = (proj_sum - norm_sum) ** 2 / (norm_sum**2 + 1) + (
                    proj_span - norm_span
                ) ** 2 / (norm_span**2 + 1)
                if score < best_score:
                    best_score, best_n = score, n
            assert best_n is not None
            selected.append(best_n)
            remaining.remove(best_n)
        return tuple(sorted(selected))

    spec = _SPEC_BY_ID["power_c05_dispersion_match_1bet"]
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert _first_zones(tickets) == (oracle(history),)


def _oracle_cusum_regime(history: tuple[P638HistoryRow, ...]) -> str:
    cusum = 0.0
    sums: list[int] = []
    mean, std = 117.0, 14.0
    for row in history:
        value = sum(row.numbers)
        sums.append(value)
        if len(sums) >= 10:
            mean = sum(sums) / len(sums)
            variance = sum((item - mean) ** 2 for item in sums) / len(sums)
            std = max(1.0, math.sqrt(variance))
        z = (value - mean) / std
        cusum = max(0.0, cusum + z - 0.5)
    if cusum > 2.0:
        return "high"
    if sums and len(sums) >= 5 and sum(sums[-5:]) / 5 < mean - std:
        return "low"
    return "neutral"


def test_power_c06_regime_cusum_1bet_matches_oracle() -> None:
    history = _history(170)

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        windows = {"high": 50, "neutral": 100, "low": 200}
        window = windows[_oracle_cusum_regime(history)]
        recent = history[-window:] if len(history) > window else history
        freq: Counter[int] = Counter()
        for row in recent:
            freq.update(row.numbers)
        return _oracle_ranked_single({n: float(freq.get(n, 0)) for n in range(1, 39)})

    spec = _SPEC_BY_ID["power_c06_regime_cusum_1bet"]
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert _first_zones(tickets) == (oracle(history),)


def test_power_c07_borda_ensemble_1bet_matches_oracle() -> None:
    history = _history(540)

    def raw_c01(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        lookback = history[-200:] if len(history) > 200 else history
        scores = {n: 0.0 for n in range(1, 39)}
        ln2 = math.log(2)
        for age, row in enumerate(reversed(lookback)):
            weight = math.exp(-ln2 * age / 50)
            for n in row.numbers:
                scores[n] += weight
        return tuple(sorted(range(1, 39), key=lambda n: (-scores[n], n)))

    def raw_c02(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        last_seen: dict[int, int] = {}
        for idx, row in enumerate(history):
            for n in row.numbers:
                last_seen[n] = idx
        n_prior = len(history)
        scores = {
            n: (n_prior - 1 - last_seen[n] if n in last_seen else n_prior) / 6.333
            for n in range(1, 39)
        }
        return tuple(sorted(range(1, 39), key=lambda n: (-scores[n], n)))

    def raw_c04(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        t_low, t_mid, t_high = _oracle_zone_targets(history[:500])
        freq: Counter[int] = Counter()
        for row in history:
            freq.update(row.numbers)
        low_r = sorted(_ORACLE_ZONE_LOW, key=lambda n: -freq.get(n, 0))
        mid_r = sorted(_ORACLE_ZONE_MID, key=lambda n: -freq.get(n, 0))
        high_r = sorted(_ORACLE_ZONE_HIGH_ITER, key=lambda n: -freq.get(n, 0))
        selected = low_r[:t_low] + mid_r[:t_mid] + high_r[:t_high]
        if len(selected) < 6:
            remaining = sorted(
                (n for n in range(1, 39) if n not in set(selected)), key=lambda n: -freq.get(n, 0)
            )
            selected = selected + remaining[: 6 - len(selected)]
        selected_set = set(selected)
        tail = [n for n in range(1, 39) if n not in selected_set]
        return tuple(selected) + tuple(tail)

    def raw_c03(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        counts: Counter[tuple[int, int]] = Counter()
        for row in history:
            for pair in combinations(row.numbers, 2):
                counts[pair] += 1
        degree: dict[int, float] = defaultdict(float)
        for (a, b), count in counts.items():
            if count >= 2:
                degree[a] += count
                degree[b] += count
        return tuple(sorted(range(1, 39), key=lambda n: (-degree.get(n, 0.0), n)))

    def oracle(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
        rankings = (raw_c01(history), raw_c02(history), raw_c04(history), raw_c03(history))
        borda: dict[int, float] = defaultdict(float)
        for ranking in rankings:
            for rank, number in enumerate(ranking):
                borda[number] += 38 - rank
        return _oracle_ranked_single(borda)

    spec = _SPEC_BY_ID["power_c07_borda_ensemble_1bet"]
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert _first_zones(tickets) == (oracle(history),)
