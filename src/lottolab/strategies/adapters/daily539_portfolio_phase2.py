"""Pure-Python port of the donor DAILY_539 phase-2 three-bet strategy.

The frozen donor is ``p128_wave2_phase2_adapters.py`` from the
``LotteryNewMeraged`` archive.  This module ports only its deterministic P7
formulae and does not import or execute donor code.  The adapter deliberately
keeps its own DAILY_539 validation because the shared portfolio base validates
the different BigLotto number contract.
"""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from math import sqrt
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
_ACB_WINDOW = 100
_MIDFREQ_WINDOW = 100
_MARKOV_WINDOW = 30


def _validated_daily539_numbers(
    numbers: object,
    strategy_id: str,
    context: str,
    *,
    require_sorted: bool,
) -> tuple[int, ...]:
    """Validate one exact DAILY_539 five-number tuple without coercion."""

    if type(numbers) is not tuple:
        raise InvalidOutput(f"{strategy_id}: {context} expected a number tuple")
    raw_numbers = cast(tuple[object, ...], numbers)
    if len(raw_numbers) != _PICK:
        raise InvalidOutput(
            f"{strategy_id}: {context} expected {_PICK} numbers, got {len(raw_numbers)}"
        )
    if not all(type(number) is int for number in raw_numbers):
        raise InvalidOutput(f"{strategy_id}: {context} numbers must be exact built-in integers")
    validated = cast(tuple[int, ...], raw_numbers)
    if not all(1 <= number <= _POOL for number in validated):
        raise InvalidOutput(f"{strategy_id}: {context} numbers out of range [1..{_POOL}]")
    if len(set(validated)) != _PICK:
        raise InvalidOutput(f"{strategy_id}: {context} duplicate numbers")
    sorted_numbers = tuple(sorted(validated))
    if require_sorted and validated != sorted_numbers:
        raise InvalidOutput(f"{strategy_id}: {context} numbers must be sorted ASC")
    return sorted_numbers


def _validated_daily539_history(
    history: object,
    strategy_id: str,
) -> tuple[CausalDrawRow, ...]:
    """Validate immutable causal rows and normalize only their number order."""

    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    raw_rows = cast(tuple[object, ...], history)
    validated: list[CausalDrawRow] = []
    for index, candidate in enumerate(raw_rows):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        if type(row.draw) is not str or not row.draw:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} draw must be a non-empty string"
            )
        if type(row.date) is not str or not row.date:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} date must be a non-empty string"
            )
        validated.append(
            CausalDrawRow(
                draw=row.draw,
                date=row.date,
                numbers=_validated_daily539_numbers(
                    row.numbers,
                    strategy_id,
                    f"history row {index}",
                    require_sorted=False,
                ),
            )
        )
    return tuple(validated)


def _recent(history: tuple[CausalDrawRow, ...], window: int) -> tuple[CausalDrawRow, ...]:
    return history[-window:] if len(history) >= window else history


def _acb_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Donor ACB score: ``(expected - actual) / sigma`` over 100 draws."""

    recent = _recent(history, _ACB_WINDOW)
    width = len(recent)
    if width == 0:
        return {number: 0.0 for number in range(1, _POOL + 1)}
    probability = _PICK / _POOL
    expected = width * probability
    variance = width * probability * (1.0 - probability)
    sigma = sqrt(variance) if variance > 0 else 1.0
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: (expected - frequency.get(number, 0)) / sigma for number in range(1, _POOL + 1)}


def _midfreq_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Donor MidFreq score: ``-|actual - expected|`` over 100 draws."""

    recent = _recent(history, _MIDFREQ_WINDOW)
    width = len(recent)
    if width == 0:
        return {number: 0.0 for number in range(1, _POOL + 1)}
    expected = width * _PICK / _POOL
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: -abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)}


def _markov_scores(history: tuple[CausalDrawRow, ...]) -> list[float]:
    """Donor 30-draw Markov transition scores using Python float matrices."""

    recent = _recent(history, _MARKOV_WINDOW)
    if len(recent) < 2:
        return [1.0] * _POOL

    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for current, following in pairwise(recent):
        for source in current.numbers:
            for target in following.numbers:
                transition[source - 1][target - 1] += 1.0

    for row in transition:
        row_sum = sum(row)
        if row_sum != 0.0:
            for index, value in enumerate(row):
                row[index] = value / row_sum

    scores = [0.0] * _POOL
    for source in recent[-1].numbers:
        source_scores = transition[source - 1]
        for index, value in enumerate(source_scores):
            scores[index] += value
    return scores


def _top_n_dict(scores: dict[int, float]) -> tuple[int, ...]:
    ranked = sorted(
        range(1, _POOL + 1),
        key=lambda number: (-scores.get(number, 0.0), number),
    )
    return tuple(sorted(ranked[:_PICK]))


def _top_n_array(scores: list[float]) -> tuple[int, ...]:
    ranked = sorted(
        range(1, _POOL + 1),
        key=lambda number: (-scores[number - 1], number),
    )
    return tuple(sorted(ranked[:_PICK]))


def _predict_all(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Return donor-native order: ACB, Markov, then MidFreq."""

    return (
        _top_n_dict(_acb_scores(history)),
        _top_n_array(_markov_scores(history)),
        _top_n_dict(_midfreq_scores(history)),
    )


def _validated_portfolio(
    predicted: object,
    strategy_id: str,
) -> tuple[tuple[int, ...], ...]:
    """Fail closed on native count, ticket shape, order, or number values."""

    if type(predicted) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a tuple of tickets")
    raw_tickets = cast(tuple[object, ...], predicted)
    if len(raw_tickets) != 3:
        raise InvalidOutput(f"{strategy_id}: expected 3 native tickets, got {len(raw_tickets)}")
    return tuple(
        _validated_daily539_numbers(
            ticket,
            strategy_id,
            f"ticket {index}",
            require_sorted=True,
        )
        for index, ticket in enumerate(raw_tickets, start=1)
    )


class Daily539AcbMarkovMidfreq3BetAdapter:
    """Deterministic native ACB/Markov/MidFreq DAILY_539 portfolio adapter."""

    strategy_id = "acb_markov_midfreq_3bet"
    strategy_name = "今彩539 ACB+Markov 中頻 3注"
    strategy_version = "v0.1"
    min_history = 100
    native_ticket_count = 3
    supported_lottery_types = (LotteryType.DAILY_539,)

    def get_bets(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        executions = self.get_bets_with_emission(history, lottery_type)
        return tuple(execution.legal_main_numbers for execution in executions)

    def get_bets_with_emission(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[BetAdapterExecution, ...]:
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

        predicted = _validated_portfolio(
            _predict_all(canonical_history),
            self.strategy_id,
        )
        return tuple(
            BetAdapterExecution(
                emitted_main_numbers=ticket,
                legal_main_numbers=ticket,
                special_number=None,
            )
            for ticket in predicted
        )


__all__ = ["Daily539AcbMarkovMidfreq3BetAdapter"]
