"""Exhaustive cross-lottery P638 ports, Wave 4 (18 portable families).

These 18 strategy specs preserve the native portfolio order and donor-declared
random protocols of their BIG_LOTTO sources while binding all pool/pick math to
the P638 first-zone GameSpec.  No BIG_LOTTO module is imported.  Complete
tickets, including the canonical second-zone prediction, are composed only by
``P638StrategySpec``.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.powerlotto_biglotto_core import (
    HIGH_HALF_START,
    MAXIMUM,
    MINIMUM,
    PICK_COUNT,
    bayesian_ticket,
    continuous_temperature,
    deviation_ticket,
    echo_scores,
    frequency_ticket,
    high_prize_trend_ticket,
    hot_cold_mix_ticket,
    kill_numbers,
    markov_ticket,
    optimized_ensemble_ticket,
    statistical_ticket,
    ticket,
    trend_ticket,
    weighted_candidates,
    zone_balance_ticket,
)
from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638FirstZoneTicketSet,
    P638HistoryRow,
    P638StrategySpec,
)

_DONOR_SHA256: Final = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"


def _as_portfolio(row: tuple[int, ...]) -> P638FirstZoneTicketSet:
    return (row,)


# biglotto_zone_split_3bet_bet1/bet2/bet3 collapse to their one generator.
_ZONE_STRATEGY_ID = "power_biglotto_zone_split_3bet"


def _zone_split_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    full_range = MAXIMUM - MINIMUM + 1
    zone_size = full_range // 3
    pools: list[tuple[int, ...]] = []
    for index in range(3):
        start = MINIMUM + index * zone_size
        end = MINIMUM + (index + 1) * zone_size - 1
        if index == 2:
            end = MAXIMUM
        pool = tuple(range(max(MINIMUM, start - 2), min(MAXIMUM, end + 2) + 1))
        pools.append(pool if len(pool) >= PICK_COUNT else tuple(range(MINIMUM, MAXIMUM + 1)))
    payload = {
        "strategy_id": _ZONE_STRATEGY_ID,
        "lottery_type": LotteryType.POWER_LOTTO.value,
        "causal_history": [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)} for row in history
        ],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest, byteorder="big", signed=False))
    return tuple(ticket(rng.sample(list(pool), PICK_COUNT)) for pool in pools)


def _high_prize_trend_7bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return tuple(
        high_prize_trend_ticket(history, lambda_value)
        for lambda_value in (0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15)
    )


def _core_satellite_pool(history: tuple[P638HistoryRow, ...], method: str) -> list[int]:
    recent = history[-30:]
    frequency = Counter(number for draw in recent for number in draw.numbers)
    numbers = list(range(MINIMUM, MAXIMUM + 1))
    if method == "hot":
        return sorted(numbers, key=lambda number: frequency.get(number, 0), reverse=True)
    if method == "cold":
        return sorted(numbers, key=lambda number: frequency.get(number, 0))
    if method == "balanced":
        hot = sorted(numbers, key=lambda number: frequency.get(number, 0), reverse=True)
        cold = sorted(numbers, key=lambda number: frequency.get(number, 0))
        result: list[int] = []
        for hot_number, cold_number in zip(hot, cold, strict=True):
            if hot_number not in result:
                result.append(hot_number)
            if cold_number not in result:
                result.append(cold_number)
        return result
    expected = 30 * PICK_COUNT / MAXIMUM
    return sorted(numbers, key=lambda number: abs(frequency.get(number, 0) - expected))


def _core_satellite_12bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    rows: list[tuple[int, ...]] = []
    for method in ("mid_frequency", "hot", "cold", "balanced"):
        pool = _core_satellite_pool(history, method)
        anchors = pool[:3]
        satellites = [number for number in pool if number not in anchors]
        satellite_count = PICK_COUNT - len(anchors)
        used: set[int] = set()
        for _ in range(3):
            selected: list[int] = []
            for number in satellites:
                if number not in used and len(selected) < satellite_count:
                    selected.append(number)
                    used.add(number)
            rows.append(ticket(anchors + selected))
    return tuple(rows)


def _two_bet_final(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    candidates = weighted_candidates(
        (
            (deviation_ticket(history), 2.0),
            (markov_ticket(history), 2.0),
            (statistical_ticket(history), 2.0),
        ),
        limit=15,
    )
    second_candidates = candidates[3:12]
    second: list[int] = []
    for number in second_candidates:
        if number >= HIGH_HALF_START and sum(item >= HIGH_HALF_START for item in second) < 3:
            second.append(number)
    for number in second_candidates:
        if number not in second and len(second) < PICK_COUNT:
            second.append(number)
    return (ticket(candidates[:PICK_COUNT]), ticket(second))


def _two_bet_optimizer(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    candidates = weighted_candidates(
        (
            (deviation_ticket(history), 2.0),
            (markov_ticket(history), 1.5),
            (statistical_ticket(history), 1.0),
        ),
        limit=12,
    )
    return (ticket(candidates[:PICK_COUNT]), ticket(candidates[3 : 3 + PICK_COUNT]))


def _two_bet_optimizer_v2(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    candidates = weighted_candidates(
        (
            (deviation_ticket(history), 1.5),
            (markov_ticket(history), 1.5),
            (statistical_ticket(history), 1.2),
            (bayesian_ticket(history), 1.0),
            (frequency_ticket(history), 1.0),
        ),
        limit=18,
    )
    return (ticket(candidates[:PICK_COUNT]), ticket(candidates[4 : 4 + PICK_COUNT]))


def _tme_optimizer(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (
        statistical_ticket(history),
        deviation_ticket(history),
        markov_ticket(history),
        hot_cold_mix_ticket(history),
    )


def _two_bet_elite(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    candidates = weighted_candidates(
        (
            (deviation_ticket(history), 2.5),
            (markov_ticket(history), 2.0),
            (statistical_ticket(history), 1.5),
            (zone_balance_ticket(history), 1.5),
            (frequency_ticket(history), 1.0),
        ),
        limit=20,
        excluded=kill_numbers(history, 8),
    )
    second = (
        candidates[PICK_COUNT : 2 * PICK_COUNT]
        if len(candidates) >= 2 * PICK_COUNT
        else candidates[:PICK_COUNT]
    )
    return (ticket(candidates[:PICK_COUNT]), ticket(second))


def _optimized_ensemble(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return _as_portfolio(optimized_ensemble_ticket(history))


def _echo_2bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    temperatures = continuous_temperature(history, 50)
    echoes = echo_scores(history, 5)
    hot_scores = {
        number: temperatures.get(number, 0.5) * 0.75 + echoes.get(number, 0.0) * 0.25
        for number in range(MINIMUM, MAXIMUM + 1)
    }
    cold_scores = {
        number: (1 - temperatures.get(number, 0.5)) * 0.75 + echoes.get(number, 0.0) * 0.25
        for number in range(MINIMUM, MAXIMUM + 1)
    }
    hot = sorted(hot_scores, key=lambda number: hot_scores[number], reverse=True)[:PICK_COUNT]
    used = set(hot)
    cold = [
        number
        for number in sorted(cold_scores, key=lambda item: cold_scores[item], reverse=True)
        if number not in used
    ][:PICK_COUNT]
    return (ticket(hot), ticket(cold))


def _elite_7bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    source = tuple(reversed(history))
    rows: list[tuple[int, ...]] = []
    for method, window in (
        ("markov", 50),
        ("markov", 100),
        ("deviation", 100),
        ("deviation", 200),
        ("statistical", 100),
        ("statistical", 110),
    ):
        try:
            sample = source[-window:]
            if method == "markov":
                rows.append(markov_ticket(tuple(reversed(sample))))
            elif method == "deviation":
                rows.append(deviation_ticket(sample))
            else:
                rows.append(statistical_ticket(sample))
        except Exception:
            continue
    if rows:
        rows.append(
            ticket(
                [
                    number
                    for number, _value in Counter(n for r in rows for n in r).most_common(
                        PICK_COUNT
                    )
                ]
            )
        )
    return tuple(rows)


def _variant_history_11bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    rows: list[tuple[int, ...]] = []
    for method, window in (
        ("deviation", 50),
        ("deviation", 100),
        ("deviation", 200),
        ("statistical", 50),
        ("statistical", 100),
        ("statistical", 200),
        ("markov", 50),
        ("markov", 100),
        ("markov", 200),
        ("frequency", 50),
        ("zone_balance", 100),
    ):
        sample = history[-window:]
        if method == "deviation":
            rows.append(deviation_ticket(sample))
        elif method == "statistical":
            try:
                rows.append(statistical_ticket(sample))
            except ValueError as exc:
                if str(exc) != "FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED":
                    raise
                rows.append(frequency_ticket(sample))
        elif method == "markov":
            if len(sample) > 1 and sample[0].draw > sample[-1].draw:
                sample = tuple(reversed(sample))
            rows.append(markov_ticket(sample))
        elif method == "frequency":
            rows.append(frequency_ticket(sample))
        else:
            rows.append(zone_balance_ticket(sample))
    return tuple(rows)


def _auto_optimizer_25bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    methods = (
        zone_balance_ticket,
        bayesian_ticket,
        trend_ticket,
        frequency_ticket,
        deviation_ticket,
    )
    return tuple(
        method(history[-window:]) for method in methods for window in (50, 100, 200, 300, 500)
    )


def _ewma_ticket(history: tuple[P638HistoryRow, ...], value: float) -> tuple[int, ...]:
    weighted: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            weighted[number] += math.exp(-value * age)
    total = sum(weighted.values())
    probabilities = {
        number: weighted.get(number, 0.0) / total for number in range(MINIMUM, MAXIMUM + 1)
    }
    return ticket(
        sorted(probabilities, key=lambda number: probabilities[number], reverse=True)[:PICK_COUNT]
    )


def _backtest_10bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    markov_history = history
    if len(history) > 1 and history[0].draw > history[-1].draw:
        markov_history = tuple(reversed(history))
    return (
        markov_ticket(markov_history),
        deviation_ticket(history),
        statistical_ticket(history),
        trend_ticket(history),
        frequency_ticket(history),
        bayesian_ticket(history),
        hot_cold_mix_ticket(history),
        _ewma_ticket(history, 0.03),
        _ewma_ticket(history, 0.10),
        _ewma_ticket(history, 0.15),
    )


def _tme_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    markov_history = history
    if len(history) > 1 and history[0].draw > history[-1].draw:
        markov_history = tuple(reversed(history))
    return (statistical_ticket(history), deviation_ticket(history), markov_ticket(markov_history))


def _gemini_v1_2bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    markov_history = history
    if len(history) > 1 and history[0].draw > history[-1].draw:
        markov_history = tuple(reversed(history))
    candidates = weighted_candidates(
        (
            (deviation_ticket(history), 2.0),
            (markov_ticket(markov_history), 1.5),
            (statistical_ticket(history), 1.0),
        ),
        limit=12,
    )
    return (ticket(candidates[:PICK_COUNT]), ticket(candidates[3 : 3 + PICK_COUNT]))


def _five_me_5bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    markov_history = history
    if len(history) > 1 and history[0].draw > history[-1].draw:
        markov_history = tuple(reversed(history))
    return (
        statistical_ticket(history),
        deviation_ticket(history),
        markov_ticket(markov_history),
        hot_cold_mix_ticket(history),
        trend_ticket(history),
    )


def _smart_2bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    frequency = Counter(number for draw in history[-50:] for number in draw.numbers)
    conservative = ticket(
        [
            number
            for number, _value in sorted(frequency.items(), key=lambda item: (-item[1], item[0]))
        ][:PICK_COUNT]
    )
    return (conservative, deviation_ticket(tuple(reversed(history))))


def _spec(
    strategy_id: str,
    native_ticket_count: int,
    min_history: int,
    donor_id: str,
    source_path: str,
    predictor: Callable[[tuple[P638HistoryRow, ...]], P638FirstZoneTicketSet],
) -> P638StrategySpec:
    return P638StrategySpec(
        strategy_id=strategy_id,
        strategy_version="v0.1-p638-wave4",
        native_ticket_count=native_ticket_count,
        min_history=min_history,
        source_paths=(source_path,),
        provenance=(
            f"Exhaustive POWER_LOTTO GameSpec port of {donor_id}; donor archive "
            f"{_DONOR_SHA256}; native ticket order and declared seed protocol preserved."
        ),
        _predictor=predictor,
    )


WAVE4_STRATEGIES: tuple[P638StrategySpec, ...] = (
    _spec(
        _ZONE_STRATEGY_ID,
        3,
        1,
        "biglotto_zone_split_3bet_bet1/bet2/bet3",
        "src/lottolab/strategies/adapters/biglotto_selected.py",
        _zone_split_3bet,
    ),
    _spec(
        "power_biglotto_high_prize_trend_7bet",
        7,
        1,
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
        "src/lottolab/strategies/adapters/biglotto_wave2.py",
        _high_prize_trend_7bet,
    ),
    _spec(
        "power_biglotto_core_satellite_12bet",
        12,
        1,
        "legacy_biglotto__core_satellite__2e82891003b3",
        "src/lottolab/strategies/adapters/biglotto_wave2.py",
        _core_satellite_12bet,
    ),
    _spec(
        "power_biglotto_two_bet_final_2bet",
        2,
        1,
        "legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
        "src/lottolab/strategies/adapters/biglotto_wave3.py",
        _two_bet_final,
    ),
    _spec(
        "power_biglotto_two_bet_optimizer_2bet",
        2,
        1,
        "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
        "src/lottolab/strategies/adapters/biglotto_wave3.py",
        _two_bet_optimizer,
    ),
    _spec(
        "power_biglotto_two_bet_optimizer_v2_2bet",
        2,
        1,
        "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
        "src/lottolab/strategies/adapters/biglotto_wave3.py",
        _two_bet_optimizer_v2,
    ),
    _spec(
        "power_biglotto_tme_optimizer_4bet",
        4,
        1,
        "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
        "src/lottolab/strategies/adapters/biglotto_wave4.py",
        _tme_optimizer,
    ),
    _spec(
        "power_biglotto_optimized_ensemble_1bet",
        1,
        1,
        "legacy_biglotto__optimized_ensemble__e05e0fde22d7",
        "src/lottolab/strategies/adapters/biglotto_wave4.py",
        _optimized_ensemble,
    ),
    _spec(
        "power_biglotto_two_bet_elite_2bet",
        2,
        1,
        "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
        "src/lottolab/strategies/adapters/biglotto_wave4.py",
        _two_bet_elite,
    ),
    _spec(
        "power_biglotto_echo_2bet",
        2,
        1,
        "legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa",
        "src/lottolab/strategies/adapters/biglotto_wave5.py",
        _echo_2bet,
    ),
    _spec(
        "power_biglotto_elite_7bet",
        7,
        1,
        "legacy_biglotto__predict_biglotto_elite7__eb46a9856446",
        "src/lottolab/strategies/adapters/biglotto_wave5.py",
        _elite_7bet,
    ),
    _spec(
        "power_biglotto_variant_history_11bet",
        11,
        20,
        "legacy_biglotto__research_variant_history__149648f9fffc",
        "src/lottolab/strategies/adapters/biglotto_wave5.py",
        _variant_history_11bet,
    ),
    _spec(
        "power_biglotto_auto_optimizer_alpha_25bet",
        25,
        1,
        "legacy_biglotto__auto_optimizer_alpha__7eaa9572e384",
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
        _auto_optimizer_25bet,
    ),
    _spec(
        "power_biglotto_backtest_10bet",
        10,
        1,
        "legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
        _backtest_10bet,
    ),
    _spec(
        "power_biglotto_tme_3bet",
        3,
        1,
        "legacy_biglotto__test_tme__f3bb5106dfe3",
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
        _tme_3bet,
    ),
    _spec(
        "power_biglotto_gemini_v1_2bet",
        2,
        50,
        "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776",
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
        _gemini_v1_2bet,
    ),
    _spec(
        "power_biglotto_five_me_5bet",
        5,
        1,
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
        "src/lottolab/strategies/adapters/biglotto_wave7.py",
        _five_me_5bet,
    ),
    _spec(
        "power_biglotto_smart_2bet",
        2,
        1,
        "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a",
        "src/lottolab/strategies/adapters/biglotto_wave7.py",
        _smart_2bet,
    ),
)

WAVE4_STRATEGY_BY_ID = {spec.strategy_id: spec for spec in WAVE4_STRATEGIES}

__all__ = ["WAVE4_STRATEGIES", "WAVE4_STRATEGY_BY_ID"]
