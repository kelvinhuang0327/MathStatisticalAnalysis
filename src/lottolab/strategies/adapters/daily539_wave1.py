"""Daily539 native-strategy wave 1: an isolated, dependency-free port of one
frozen legacy Markov transition-matrix predictor.

Donor: LotteryNewMeraged/tools/backtest_39lotto_comprehensive.py::MarkovStrategy
(window=30), bound to legacy identity ``daily539_markov_cold`` in
LotteryNewMeraged/lottery_api/models/replay_strategy_registry.py. The donor
used numpy for the transition matrix and ``np.argsort(-scores)``; this port
uses plain Python floats and an explicit (descending score, ascending number)
sort key, which is an exact order-preserving equivalent.

Kept entirely separate from ``strategies/adapters/base.py``: DAILY_539 has a
different pick count and number range than the BigLotto adapters that module
validates against, so this module implements its own local history/output
validation instead of reusing ``BetAdapter`` or the BigLotto-only
``_validated_biglotto_numbers``. Not registered in the shared strategy
catalog — that is a separate, later scope.
"""

from __future__ import annotations

from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)

_POOL = 39
_PICK = 5
_WINDOW = 30


def _validated_daily539_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    """Return canonical immutable rows without coercing legacy values."""

    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    raw_rows = cast(tuple[object, ...], history)
    validated: list[CausalDrawRow] = []
    for index, candidate in enumerate(raw_rows):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        validated.append(
            CausalDrawRow(
                draw=row.draw,
                date=row.date,
                numbers=_validated_daily539_numbers(row.numbers, strategy_id, index),
            )
        )
    return tuple(validated)


def _validated_daily539_numbers(
    numbers: object, strategy_id: str, row_index: int | None = None
) -> tuple[int, ...]:
    """Validate exact integers against the DAILY_539 5-of-39 contract."""

    context = f"history row {row_index}" if row_index is not None else "output"
    if type(numbers) is not tuple:
        raise InvalidOutput(f"{strategy_id}: {context} expected a number tuple")
    raw_numbers = cast(tuple[object, ...], numbers)
    if len(raw_numbers) != _PICK:
        raise InvalidOutput(
            f"{strategy_id}: {context} expected {_PICK} numbers, got {len(raw_numbers)}"
        )
    if not all(type(number) is int for number in raw_numbers):
        raise InvalidOutput(f"{strategy_id}: {context} numbers must be exact built-in integers")
    validated_numbers = cast(tuple[int, ...], raw_numbers)
    if not all(1 <= number <= _POOL for number in validated_numbers):
        raise InvalidOutput(f"{strategy_id}: {context} numbers out of range [1..{_POOL}]")
    if len(set(validated_numbers)) != _PICK:
        raise InvalidOutput(f"{strategy_id}: {context} duplicate numbers")
    return tuple(sorted(validated_numbers))


def _markov_cold_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Frozen 30-draw Markov transition-matrix predictor (donor: MarkovStrategy)."""

    recent = history[-_WINDOW:] if len(history) >= _WINDOW else history

    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for i in range(len(recent) - 1):
        current_numbers = recent[i].numbers
        next_numbers = recent[i + 1].numbers
        for a in current_numbers:
            for b in next_numbers:
                transition[a - 1][b - 1] += 1.0

    for row in transition:
        row_sum = sum(row)
        if row_sum != 0:
            for j in range(_POOL):
                row[j] /= row_sum

    last_numbers = recent[-1].numbers
    scores = [0.0] * _POOL
    for number in last_numbers:
        row = transition[number - 1]
        for j in range(_POOL):
            scores[j] += row[j]

    ranked = sorted(range(_POOL), key=lambda idx: (-scores[idx], idx))
    top_numbers = [idx + 1 for idx in ranked[:_PICK]]
    return tuple(sorted(top_numbers))


class Daily539MarkovColdAdapter:
    """Frozen 30-draw Markov transition-matrix predictor for DAILY_539."""

    strategy_id = "daily539_markov_cold"
    strategy_name = "今彩539 Markov Cold"
    strategy_version = "v0.1"
    min_history = 100
    supported_lottery_types = (LotteryType.DAILY_539,)

    def get_one_bet(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], int | None]:
        execution = self.get_one_bet_with_emission(history, lottery_type)
        return execution.legal_main_numbers, execution.special_number

    def get_one_bet_with_emission(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> BetAdapterExecution:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )

        canonical_history = _validated_daily539_history(history, self.strategy_id)
        if len(canonical_history) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical_history)}"
            )

        predicted = _markov_cold_predict(canonical_history)
        validated = _validated_daily539_numbers(predicted, self.strategy_id)
        return BetAdapterExecution(
            emitted_main_numbers=predicted,
            legal_main_numbers=validated,
            special_number=None,
        )


__all__ = ["Daily539MarkovColdAdapter"]
