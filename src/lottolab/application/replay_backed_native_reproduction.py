"""Native-ticket completion for exact-mapped replay-backed BIG_LOTTO methods.

The replay table already preserves Triple Strike's Fourier first ticket and
all four TS3+Markov tickets.  Triple Strike's remaining cold and tail tickets
are reconstructed from the frozen source logic using only causal history.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from lottolab.application.strategy_preserving_20_ticket import Ticket

TRIPLE_STRIKE_REGISTRY_ID = "biglotto_triple_strike"
TS3_MARKOV_4BET_REGISTRY_ID = "biglotto_ts3_markov_4bet_w30"
SUPPORTED_REPLAY_REGISTRY_IDS = (
    TRIPLE_STRIKE_REGISTRY_ID,
    TS3_MARKOV_4BET_REGISTRY_ID,
)
_MAX_NUMBER = 49
_SUM_WINDOW = 300


class ReplayBackedNativeReproductionError(ValueError):
    """Replay rows or causal history cannot reproduce native ticket semantics."""


@dataclass(frozen=True, slots=True)
class CausalMainDraw:
    draw_number: str
    numbers: Ticket


def _sum_target(history: Sequence[CausalMainDraw]) -> tuple[float, float]:
    selected = history[-_SUM_WINDOW:]
    sums = [sum(draw.numbers) for draw in selected]
    if not sums:
        raise ReplayBackedNativeReproductionError(
            "sum target requires causal history"
        )
    mean = sum(sums) / len(sums)
    variance = sum((value - mean) ** 2 for value in sums) / len(sums)
    deviation = math.sqrt(variance)
    last_sum = sums[-1]
    if last_sum < mean - 0.5 * deviation:
        return mean, mean + deviation
    if last_sum > mean + 0.5 * deviation:
        return mean - deviation, mean
    return mean - 0.5 * deviation, mean + 0.5 * deviation


def _cold_numbers_bet(
    history: Sequence[CausalMainDraw],
    *,
    exclude: set[int],
    window: int = 100,
    pool_size: int = 12,
) -> Ticket:
    recent = history[-window:]
    frequency = Counter(
        number for draw in recent for number in draw.numbers
    )
    candidates = [
        number
        for number in range(1, _MAX_NUMBER + 1)
        if number not in exclude
    ]
    sorted_cold = sorted(candidates, key=lambda number: frequency.get(number, 0))
    if len(history) < 2 or pool_size <= 6:
        return _as_ticket(sorted(sorted_cold[:6]))

    pool = sorted_cold[:pool_size]
    target_low, target_high = _sum_target(history)
    target_middle = (target_low + target_high) / 2.0
    best_combo: tuple[int, ...] | None = None
    best_distance = float("inf")
    best_in_range = False
    for combo in combinations(pool, 6):
        total = sum(combo)
        in_range = target_low <= total <= target_high
        distance = abs(total - target_middle)
        if in_range and (not best_in_range or distance < best_distance):
            best_combo = combo
            best_distance = distance
            best_in_range = True
        elif not in_range and not best_in_range and distance < best_distance:
            best_combo = combo
            best_distance = distance
    if best_combo is None:
        best_combo = tuple(pool[:6])
    return _as_ticket(sorted(best_combo))


def _tail_balance_bet(
    history: Sequence[CausalMainDraw],
    *,
    exclude: set[int],
    window: int = 100,
) -> Ticket:
    recent = history[-window:]
    frequency = Counter(
        number for draw in recent for number in draw.numbers
    )
    tail_groups: dict[int, list[tuple[int, int]]] = {
        tail: [] for tail in range(10)
    }
    for number in range(1, _MAX_NUMBER + 1):
        if number not in exclude:
            tail_groups[number % 10].append(
                (number, frequency.get(number, 0))
            )
    for group in tail_groups.values():
        group.sort(key=lambda item: item[1], reverse=True)
    available_tails = sorted(
        (tail for tail in range(10) if tail_groups[tail]),
        key=lambda tail: tail_groups[tail][0][1],
        reverse=True,
    )
    indexes = {tail: 0 for tail in range(10)}
    selected: list[int] = []
    while len(selected) < 6:
        added = False
        for tail in available_tails:
            if len(selected) >= 6:
                break
            index = indexes[tail]
            if index < len(tail_groups[tail]):
                number, _frequency = tail_groups[tail][index]
                if number not in selected:
                    selected.append(number)
                    added = True
                indexes[tail] += 1
        if not added:
            break
    if len(selected) < 6:
        remaining = [
            number
            for number in range(1, _MAX_NUMBER + 1)
            if number not in selected and number not in exclude
        ]
        remaining.sort(
            key=lambda number: frequency.get(number, 0),
            reverse=True,
        )
        selected.extend(remaining[: 6 - len(selected)])
    return _as_ticket(sorted(selected[:6]))


def _as_ticket(numbers: Sequence[int]) -> Ticket:
    values = tuple(numbers)
    if (
        len(values) != 6
        or values != tuple(sorted(values))
        or len(set(values)) != 6
        or any(type(number) is not int or not 1 <= number <= 49 for number in values)
    ):
        raise ReplayBackedNativeReproductionError(
            "native strategy emitted an invalid BIG_LOTTO ticket"
        )
    return (
        values[0],
        values[1],
        values[2],
        values[3],
        values[4],
        values[5],
    )


def reproduce_native_tickets(
    *,
    registry_strategy_id: str,
    replay_tickets: Sequence[Sequence[int]],
    causal_history: Sequence[CausalMainDraw],
) -> tuple[Ticket, ...]:
    """Return source-ordered native tickets for one exact-mapped strategy."""

    validated_replay = tuple(_as_ticket(ticket) for ticket in replay_tickets)
    if registry_strategy_id == TS3_MARKOV_4BET_REGISTRY_ID:
        if len(validated_replay) != 4:
            raise ReplayBackedNativeReproductionError(
                "TS3+Markov replay requires exactly four ordered tickets"
            )
        return validated_replay
    if registry_strategy_id != TRIPLE_STRIKE_REGISTRY_ID:
        raise ReplayBackedNativeReproductionError(
            "registry strategy is outside the exact-mapped replay batch"
        )
    if len(validated_replay) != 1:
        raise ReplayBackedNativeReproductionError(
            "Triple Strike replay requires exactly one distinct Fourier ticket"
        )
    if not causal_history:
        raise ReplayBackedNativeReproductionError(
            "Triple Strike requires causal history"
        )
    first = validated_replay[0]
    second = _cold_numbers_bet(causal_history, exclude=set(first))
    third = _tail_balance_bet(
        causal_history,
        exclude=set(first) | set(second),
    )
    return first, second, third


__all__ = [
    "SUPPORTED_REPLAY_REGISTRY_IDS",
    "TRIPLE_STRIKE_REGISTRY_ID",
    "TS3_MARKOV_4BET_REGISTRY_ID",
    "CausalMainDraw",
    "ReplayBackedNativeReproductionError",
    "reproduce_native_tickets",
]
