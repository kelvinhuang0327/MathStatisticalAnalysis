"""Pure DAILY_539 ports of the complete P36 single-ticket producers.

These two identities are kept separate from the existing PR #85 Markov Cold
adapter because the donor registry treats them as distinct strategies.  The
implementations are intentionally DB-free and use only the immutable causal
history supplied by the caller.
"""

from __future__ import annotations

from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)

_POOL = 39
_PICK = 5
_MARKOV_WINDOW = 30
_ACB_WINDOW = 100


def _validated_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    rows: list[CausalDrawRow] = []
    for index, candidate in enumerate(cast(tuple[object, ...], history)):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        if type(row.draw) is not str or not row.draw:
            raise InvalidOutput(f"{strategy_id}: history row {index} draw is invalid")
        if type(row.date) is not str or not row.date:
            raise InvalidOutput(f"{strategy_id}: history row {index} date is invalid")
        if type(row.numbers) is not tuple:
            raise InvalidOutput(f"{strategy_id}: history row {index} numbers are invalid")
        numbers = cast(tuple[object, ...], row.numbers)
        if len(numbers) != _PICK or not all(type(number) is int for number in numbers):
            raise InvalidOutput(f"{strategy_id}: history row {index} needs five integers")
        typed = cast(tuple[int, ...], numbers)
        if len(set(typed)) != _PICK or not all(1 <= number <= _POOL for number in typed):
            raise InvalidOutput(f"{strategy_id}: history row {index} numbers are illegal")
        if typed != tuple(sorted(typed)):
            raise InvalidOutput(f"{strategy_id}: history row {index} numbers are not ascending")
        rows.append(CausalDrawRow(draw=row.draw, date=row.date, numbers=typed))
    return tuple(rows)


def _validated_ticket(numbers: object, strategy_id: str) -> tuple[int, ...]:
    if type(numbers) is not tuple:
        raise InvalidOutput(f"{strategy_id}: output must be a tuple")
    values = cast(tuple[object, ...], numbers)
    if len(values) != _PICK or not all(type(number) is int for number in values):
        raise InvalidOutput(f"{strategy_id}: output needs five built-in integers")
    typed = cast(tuple[int, ...], values)
    if len(set(typed)) != _PICK or not all(1 <= number <= _POOL for number in typed):
        raise InvalidOutput(f"{strategy_id}: output numbers are illegal")
    if typed != tuple(sorted(typed)):
        raise InvalidOutput(f"{strategy_id}: output numbers are not ascending")
    return typed


def _markov_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-_MARKOV_WINDOW:] if len(history) >= _MARKOV_WINDOW else history
    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for index in range(len(recent) - 1):
        for current in recent[index].numbers:
            for following in recent[index + 1].numbers:
                transition[current - 1][following - 1] += 1.0
    for row in transition:
        row_sum = sum(row)
        if row_sum != 0:
            for column in range(_POOL):
                row[column] /= row_sum
    scores = [0.0] * _POOL
    for current in recent[-1].numbers:
        for column, score in enumerate(transition[current - 1]):
            scores[column] += score
    ranked = sorted(range(_POOL), key=lambda index: (-scores[index], index))
    return tuple(sorted(index + 1 for index in ranked[:_PICK]))


def _zone(number: int) -> int:
    if number <= 13:
        return 1
    if number <= 26:
        return 2
    return 3


def _acb_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-_ACB_WINDOW:] if len(history) >= _ACB_WINDOW else history
    width = len(recent)
    expected = width * _PICK / _POOL
    frequency = {number: 0 for number in range(1, _POOL + 1)}
    last_seen: dict[int, int] = {}
    for index, row in enumerate(recent):
        for number in row.numbers:
            frequency[number] += 1
            last_seen[number] = index

    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        actual = frequency[number]
        deficit = (expected - actual) / max(expected, 1.0)
        gap_index = last_seen.get(number, -1)
        gap_score = (width - 1 - gap_index) / width
        boundary_bonus = 1.2 if number <= 5 or number >= 35 else 1.0
        mod3_bonus = 1.1 if number % 3 == 0 else 1.0
        scores[number] = (deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus

    ranked = sorted(range(1, _POOL + 1), key=lambda number: -scores[number])
    selected = list(ranked[:_PICK])
    zones_present = {_zone(number) for number in selected}
    if len(zones_present) < 2:
        zone_counts: dict[int, int] = {}
        for number in selected:
            zone_counts[_zone(number)] = zone_counts.get(_zone(number), 0) + 1
        dominant_zone = max(zone_counts, key=lambda zone_id: zone_counts[zone_id])
        for missing_zone in (1, 2, 3):
            if missing_zone in zones_present:
                continue
            candidates = [
                number
                for number in ranked
                if _zone(number) == missing_zone and number not in selected
            ]
            if not candidates:
                continue
            dominant_numbers = [number for number in selected if _zone(number) == dominant_zone]
            if dominant_numbers:
                remove = min(dominant_numbers, key=lambda number: scores[number])
                selected = [number for number in selected if number != remove]
                selected.append(candidates[0])
                break
    return tuple(sorted(selected[:_PICK]))


class Daily539Markov1BetAdapter:
    """P36 Markov transition 1-bet identity (window 30)."""

    strategy_id = "markov_1bet_539"
    strategy_name = "今彩539 Markov 1注"
    strategy_version = "v0.1-p36"
    min_history = _MARKOV_WINDOW
    native_ticket_count = 1
    supported_lottery_types = (LotteryType.DAILY_539,)

    def get_one_bet(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        canonical = _validated_history(history, self.strategy_id)
        if len(canonical) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical)}"
            )
        return _validated_ticket(_markov_predict(canonical), self.strategy_id), None


class Daily539AcbSingleAdapter:
    """P36 ACB single-ticket identity with its cross-zone rule."""

    strategy_id = "acb_single_539"
    strategy_name = "今彩539 ACB Single 1注"
    strategy_version = "v0.1-p36"
    min_history = _ACB_WINDOW
    native_ticket_count = 1
    supported_lottery_types = (LotteryType.DAILY_539,)

    def get_one_bet(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        canonical = _validated_history(history, self.strategy_id)
        if len(canonical) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical)}"
            )
        return _validated_ticket(_acb_predict(canonical), self.strategy_id), None


__all__ = ["Daily539AcbSingleAdapter", "Daily539Markov1BetAdapter"]
