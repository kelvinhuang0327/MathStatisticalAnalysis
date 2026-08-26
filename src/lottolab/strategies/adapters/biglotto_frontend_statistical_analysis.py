"""Target-native port of the legacy frontend Statistical Analysis strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/StatisticalAnalysisStrategy.js``.
It consumes the complete caller-supplied history through a synchronous
``calculateFrequency`` call, generates weighted random combinations, filters
them through five statistical conditions, and emits one Big Lotto ticket.
The source confidence, method, and report fields have no counterpart in the
native single-ticket response and are intentionally not invented here.

The production frontend StatisticsService exposes ``calculateFrequency`` as
an async method even though this donor consumes it synchronously. The donor
was genuinely revived with a bounded synchronous statistics-compatible seam;
this adapter reproduces that source-visible frequency map from causal history
and never opens a database.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Final, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_statistical_analysis_strategy__a9364825de2a"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_MAX_ATTEMPTS: Final = 2_000
_VALID_COMBINATION_TARGET: Final = 20


class _RandomSource(Protocol):
    """The one random operation used by the donor's ``Math.random`` calls."""

    def random(self) -> float:
        """Return one unseeded value in the half-open interval [0, 1)."""

        ...


def _frequency_map(history: tuple[CausalDrawRow, ...]) -> Counter[int]:
    """Build the donor's all-history frequency map for numbers 1 through 49."""

    frequency: Counter[int] = Counter()
    frequency.update(number for row in history for number in row.numbers)
    return frequency


def _weighted_random(
    minimum: int,
    maximum: int,
    count: int,
    frequency: Counter[int],
    rng: _RandomSource,
) -> tuple[int, ...]:
    """Reproduce the donor's repeated weighted pool and insertion order."""

    pool: list[int] = []
    for number in range(minimum, maximum + 1):
        weight = math.floor(math.sqrt(frequency.get(number, 0) or 1) * 10)
        pool.extend([number] * weight)

    selected: list[int] = []
    selected_set: set[int] = set()
    while len(selected) < count:
        number = pool[math.floor(rng.random() * len(pool))]
        if number not in selected_set:
            selected_set.add(number)
            selected.append(number)
    return tuple(selected)


def _stats(numbers: tuple[int, ...]) -> tuple[int, int, int, int, int]:
    """Return the donor's sum, odd/even counts, spread, and AC value."""

    sorted_numbers = sorted(numbers)
    total = sum(sorted_numbers)
    odd = sum(number % 2 == 1 for number in sorted_numbers)
    even = len(sorted_numbers) - odd
    spread = sorted_numbers[-1] - sorted_numbers[0]

    differences: set[int] = set()
    for index, left in enumerate(sorted_numbers):
        for right in sorted_numbers[index + 1 :]:
            differences.add(right - left)
    ac = len(differences) - (len(sorted_numbers) - 1)
    return total, odd, even, spread, ac


def _meets_conditions(
    numbers: tuple[int, ...],
    lottery_type: LotteryType,
) -> bool:
    """Apply the donor's dynamic sum, AC, parity, spread, and tail rules."""

    del lottery_type
    total, odd, _even, spread, ac = _stats(numbers)
    pick_count = _PICK_COUNT
    minimum = _MIN_NUMBER
    maximum = _MAX_NUMBER
    total_numbers = maximum - minimum + 1

    theoretical_minimum = (
        minimum * pick_count + pick_count * (pick_count - 1) / 2
    )
    theoretical_maximum = (
        maximum * pick_count - pick_count * (pick_count - 1) / 2
    )
    ideal_sum = (theoretical_minimum + theoretical_maximum) / 2
    sum_range = (theoretical_maximum - theoretical_minimum) * 0.6
    if total < ideal_sum - sum_range / 2 or total > ideal_sum + sum_range / 2:
        return False

    minimum_ac = max(pick_count - 1, math.floor(total_numbers * 0.15))
    maximum_ac = min(
        pick_count * (pick_count - 1) / 2,
        math.ceil(total_numbers * 0.35),
    )
    if ac < minimum_ac or ac > maximum_ac:
        return False

    ideal_odd = math.floor(pick_count / 2 + 0.5)
    if abs(odd - ideal_odd) > math.ceil(pick_count / 3):
        return False

    if spread < math.floor(total_numbers * 0.4):
        return False

    unique_last_digits = {number % 10 for number in numbers}
    minimum_unique_digits = max(3, math.floor(pick_count * 0.6))
    return len(unique_last_digits) >= minimum_unique_digits


class BigLottoFrontendStatisticalAnalysisAdapter(BetAdapter):
    """Reproduce ``StatisticalAnalysisStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Statistical Analysis Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, rng: _RandomSource | None = None) -> None:
        # The source uses process-global, unseeded Math.random. The module
        # default preserves that behavior; the narrow seam makes exact donor
        # parity testable without adding a production seed or dependency.
        self._rng: _RandomSource = random if rng is None else rng

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Generate, filter, and frequency-score the donor's combinations."""

        frequency = _frequency_map(history)
        valid_combinations: list[tuple[int, ...]] = []
        for _ in range(_MAX_ATTEMPTS):
            combination = _weighted_random(
                _MIN_NUMBER,
                _MAX_NUMBER,
                _PICK_COUNT,
                frequency,
                self._rng,
            )
            if _meets_conditions(combination, lottery_type):
                valid_combinations.append(combination)
            if len(valid_combinations) >= _VALID_COMBINATION_TARGET:
                break

        if not valid_combinations:
            fallback = _weighted_random(
                _MIN_NUMBER,
                _MAX_NUMBER,
                _PICK_COUNT,
                frequency,
                self._rng,
            )
            return tuple(sorted(fallback))

        best_combination = valid_combinations[0]
        best_score = -1
        for combination in valid_combinations:
            score = sum(frequency.get(number, 0) for number in combination)
            if score > best_score:
                best_score = score
                best_combination = combination
        return tuple(sorted(best_combination))


__all__ = ["BigLottoFrontendStatisticalAnalysisAdapter"]
