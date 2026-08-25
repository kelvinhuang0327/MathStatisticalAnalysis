"""Target-native port of the legacy frontend Sum-range/AC strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/SumRangeStrategy.js``.
It consumes the complete caller-supplied history, uses a synchronous
``calculateFrequency`` call, and emits one Big Lotto ticket.  The source's
confidence, method, and report fields have no counterpart in the native
single-ticket response and are intentionally not invented here.

The production StatisticsService exposes ``calculateFrequency`` as an async
method even though this donor calls it synchronously.  The donor was genuinely
revived with a bounded synchronous statistics-compatible stub before this port;
the adapter reproduces that source-visible frequency map from causal history
and does not open a database.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_sum_range_strategy__4941213e6c46"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_MEANINGFUL_HISTORY_LENGTH: Final = 10
_MAX_STARTS: Final = 20


def _calculate_ac(numbers: tuple[int, ...]) -> int:
    """Return the donor's pairwise absolute-difference set cardinality."""

    differences: set[int] = set()
    for index, left in enumerate(numbers):
        for right in numbers[index + 1 :]:
            differences.add(abs(left - right))
    return len(differences)


def _sum_distribution(
    history: tuple[CausalDrawRow, ...],
) -> tuple[float, float, float, float]:
    """Return donor mean, population SD, and clamped target sum bounds."""

    sums = [sum(row.numbers) for row in history]
    average = sum(sums) / len(sums)
    variance = sum((value - average) ** 2 for value in sums) / len(sums)
    standard_deviation = math.sqrt(variance)

    theoretical_minimum = (
        _MIN_NUMBER * _PICK_COUNT + _PICK_COUNT * (_PICK_COUNT - 1) / 2
    )
    theoretical_maximum = (
        _MAX_NUMBER * _PICK_COUNT - _PICK_COUNT * (_PICK_COUNT - 1) / 2
    )
    target_minimum = max(average - standard_deviation, theoretical_minimum)
    target_maximum = min(average + standard_deviation, theoretical_maximum)
    return average, standard_deviation, target_minimum, target_maximum


def _ac_distribution(history: tuple[CausalDrawRow, ...]) -> tuple[float, int, int]:
    """Return donor AC average and the common AC range with source tie order."""

    ac_values = [_calculate_ac(row.numbers) for row in history]
    average = sum(ac_values) / len(ac_values)
    counts = Counter(ac_values)
    common_values = sorted(counts, key=lambda value: (-counts[value], value))[:3]
    return average, min(common_values), max(common_values)


class BigLottoFrontendSumRangeAdapter(BetAdapter):
    """Reproduce ``SumRangeStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Sum-range/AC Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's frequency fallback or sum/AC greedy search."""

        frequency = Counter(number for row in history for number in row.numbers)
        ranked_numbers = [
            (number, frequency.get(number, 0))
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        ]
        ranked_numbers.sort(key=lambda item: (-item[1], item[0]))

        if len(history) < _MEANINGFUL_HISTORY_LENGTH:
            selected = [number for number, _frequency in ranked_numbers[:_PICK_COUNT]]
            return tuple(sorted(selected))

        sum_average, _sum_standard_deviation, sum_minimum, sum_maximum = _sum_distribution(
            history
        )
        target_minimum = math.floor(sum_minimum)
        target_maximum = math.ceil(sum_maximum)
        ac_average, target_ac_minimum, target_ac_maximum = _ac_distribution(history)

        best_combination: list[int] | None = None
        best_score = -1.0
        for start_index in range(
            min(_MAX_STARTS, len(ranked_numbers) - _PICK_COUNT)
        ):
            start_number, start_frequency = ranked_numbers[start_index]
            combination = [start_number]
            used = {start_number}
            current_sum = start_number
            frequency_score = start_frequency

            for number, number_frequency in ranked_numbers:
                if len(combination) >= _PICK_COUNT:
                    break
                if number in used:
                    continue

                new_sum = current_sum + number
                remaining = _PICK_COUNT - len(combination) - 1
                minimum_possible = new_sum + _MIN_NUMBER * remaining
                maximum_possible = new_sum + _MAX_NUMBER * remaining
                if maximum_possible >= target_minimum and minimum_possible <= target_maximum:
                    combination.append(number)
                    used.add(number)
                    current_sum = new_sum
                    frequency_score += number_frequency

            if len(combination) != _PICK_COUNT:
                continue

            total = sum(combination)
            ac_value = _calculate_ac(tuple(combination))
            if not (
                target_minimum <= total <= target_maximum
                and target_ac_minimum <= ac_value <= target_ac_maximum
            ):
                continue

            score = (
                frequency_score
                - abs(total - sum_average) * 0.1
                - abs(ac_value - ac_average) * 0.5
            )
            if score > best_score:
                best_score = score
                best_combination = sorted(combination)

        if best_combination is None:
            selected = [number for number, _frequency in ranked_numbers[:_PICK_COUNT]]
            return tuple(sorted(selected))

        return tuple(best_combination)


__all__ = ["BigLottoFrontendSumRangeAdapter"]
