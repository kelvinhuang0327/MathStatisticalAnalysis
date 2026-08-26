"""Target-native port of the legacy frontend Wheeling strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/WheelingStrategy.js``.
Despite its name and comments, the donor emits one six-number ticket: it
builds a 12-number hot/cold/random pool, samples 120 randomized candidate
orders, scores each candidate, and returns the best candidate. The donor's
confidence, method, and report fields have no counterpart in the native
single-ticket response.

The production frontend ``StatisticsService.calculateFrequency`` is async,
while this donor consumes it synchronously. The adapter therefore reproduces
the donor's source-visible frequency map from caller-supplied causal history
at the native boundary and never opens a database.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from itertools import pairwise
from typing import Final, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow, InvalidOutput

_STRATEGY_ID: Final = "legacy_biglotto__frontend_wheeling_strategy__ce978baff05b"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_POOL_SIZE: Final = 12
_MAX_ATTEMPTS: Final = 200


class _RandomSource(Protocol):
    """The one random operation used by the donor's ``Math.random`` calls."""

    def random(self) -> float:
        """Return one unseeded value in the half-open interval [0, 1)."""

        ...


def _frequency_map(history: tuple[CausalDrawRow, ...]) -> Counter[int]:
    """Build the donor's initialized 1-through-49 frequency object."""

    frequency: Counter[int] = Counter(
        {number: 0 for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)}
    )
    frequency.update(number for row in history for number in row.numbers)
    return frequency


def _random_combination_from_pool(
    pool: tuple[int, ...],
    count: int,
    rng: _RandomSource,
) -> tuple[int, ...]:
    """Reproduce Node/V8's stable sort for the donor's 12-item array.

    Node 20's ``Array.prototype.sort`` takes one natural run through this
    twelve-item ascending pool and then uses binary insertion for the forced
    run. Implementing those two source-visible phases preserves the donor's
    exact random-comparator call sequence without a runtime dependency.
    """

    shuffled = list(pool)

    def _compare(_left: int, _right: int) -> int:
        decision = 0.5 - rng.random()
        if decision < 0:
            return -1
        if decision > 0:
            return 1
        return 0

    if len(shuffled) < 2:
        return tuple(shuffled[:count])

    # This is V8's CountAndMakeAscending phase. The production call site is
    # fixed at length 12, for which V8's computed min-run is also 12.
    run_length = 2
    if _compare(shuffled[1], shuffled[0]) < 0:
        while run_length < len(shuffled):
            if _compare(shuffled[run_length], shuffled[run_length - 1]) < 0:
                run_length += 1
            else:
                break
        shuffled[:run_length] = reversed(shuffled[:run_length])
    else:
        while run_length < len(shuffled):
            if _compare(shuffled[run_length], shuffled[run_length - 1]) >= 0:
                run_length += 1
            else:
                break

    if run_length < len(shuffled):
        # This is V8's BinaryInsertionSort phase for the forced min-run.
        start = run_length
        while start < len(shuffled):
            pivot = shuffled[start]
            left = 0
            right = start
            while left < right:
                middle = (left + right) // 2
                if _compare(pivot, shuffled[middle]) < 0:
                    right = middle
                else:
                    left = middle + 1
            shuffled[left + 1 : start + 1] = shuffled[left:start]
            shuffled[left] = pivot
            start += 1

    return tuple(shuffled[:count])


def _evaluate_combination(
    numbers: tuple[int, ...], frequency: Counter[int]
) -> float:
    """Apply the donor's frequency, parity, sum, and adjacency score."""

    score = float(sum(frequency.get(number, 0) for number in numbers))

    odd_count = sum(number % 2 == 1 for number in numbers)
    ideal_odd = math.floor(_PICK_COUNT / 2 + 0.5)
    if odd_count == ideal_odd:
        score += 20
    elif abs(odd_count - ideal_odd) == 1:
        score += 10
    else:
        score -= 10

    total = sum(numbers)
    theoretical_minimum = (
        _MIN_NUMBER * _PICK_COUNT + _PICK_COUNT * (_PICK_COUNT - 1) / 2
    )
    theoretical_maximum = (
        _MAX_NUMBER * _PICK_COUNT - _PICK_COUNT * (_PICK_COUNT - 1) / 2
    )
    ideal_sum = (theoretical_minimum + theoretical_maximum) / 2
    acceptable_range = (theoretical_maximum - theoretical_minimum) * 0.4
    if abs(total - ideal_sum) <= acceptable_range:
        score += 20
    else:
        score -= abs(total - ideal_sum) * 0.1

    sorted_numbers = sorted(numbers)
    consecutive_count = sum(
        right - left == 1 for left, right in pairwise(sorted_numbers)
    )
    if consecutive_count > _PICK_COUNT / 2:
        score -= 20

    return score


class BigLottoFrontendWheelingAdapter(BetAdapter):
    """Reproduce ``WheelingStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Wheeling Strategy"
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
        """Build, score, and return the donor's best sampled combination."""

        del lottery_type
        frequency = _frequency_map(history)
        sorted_by_frequency = tuple(
            number
            for number, _count in sorted(
                frequency.items(), key=lambda item: -item[1]
            )
        )

        hot_count = math.ceil(_POOL_SIZE / 3)
        cold_count = math.ceil(_POOL_SIZE / 3)
        random_count = _POOL_SIZE - hot_count - cold_count
        hot_numbers = sorted_by_frequency[:hot_count]
        cold_numbers = sorted_by_frequency[-cold_count:]

        remaining_numbers = [
            number
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
            if number not in hot_numbers and number not in cold_numbers
        ]
        random_pool: list[int] = []
        while len(random_pool) < random_count and remaining_numbers:
            index = math.floor(self._rng.random() * len(remaining_numbers))
            random_pool.append(remaining_numbers.pop(index))

        candidate_pool = tuple(sorted((*hot_numbers, *cold_numbers, *random_pool)))
        attempts = min(_MAX_ATTEMPTS, len(candidate_pool) * 10)

        best_combination: tuple[int, ...] | None = None
        best_score = -math.inf
        for _ in range(attempts):
            combination = _random_combination_from_pool(
                candidate_pool, _PICK_COUNT, self._rng
            )
            score = _evaluate_combination(combination, frequency)
            if score > best_score:
                best_score = score
                best_combination = combination

        if best_combination is None:
            raise InvalidOutput(f"{self.strategy_id}: donor emitted no combination")
        return tuple(sorted(best_combination))


__all__ = ["BigLottoFrontendWheelingAdapter"]
