"""Pure-Python DAILY_539 port of the retired P31A ACB+Markov midfreq fusion.

Donor: ``AcbMarkovMidfreqAdapter`` / ``predict_acb_markov_midfreq`` in
``LotteryNewMeraged/lottery_api/models/p31a_wave1_retired_adapters.py``
(``strategy_id=acb_markov_midfreq``, ``strategy_version=v0.1-p31a``). This is a
standalone single-bet fusion, distinct from ``acb_markov_midfreq_3bet`` (a
different, already-migrated donor family in ``daily539_portfolio_phase2.py``
whose bet-1 is pure ACB): here the donor blends normalized ACB and Markov
scores, boosts numbers within one population standard deviation of the
expected 100-draw frequency, then applies the same cross-zone constraint used
throughout the P31A/P36 family.

The donor used ``numpy`` only for min/max normalization and population
standard deviation (``ddof=0``); both are ported here as plain Python
arithmetic over the exact same score dictionaries, with no functional change.
Kept self-contained (no cross-module imports of ACB/Markov helpers) to match
the rest of the DAILY_539 adapter family.
"""

from __future__ import annotations

from collections import Counter
from math import sqrt
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
_ACB_WINDOW = 100
_MARKOV_WINDOW = 30

_Z1 = frozenset(range(1, 14))
_Z2 = frozenset(range(14, 27))
_Z3 = frozenset(range(27, 40))


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


def _zone(number: int) -> int:
    if number in _Z1:
        return 1
    if number in _Z2:
        return 2
    return 3


def _acb_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Donor ACB score: freq-deficit/gap composite with boundary and mod3 bonuses."""

    recent = history[-_ACB_WINDOW:] if len(history) >= _ACB_WINDOW else history
    width = len(recent)
    if width == 0:
        return {number: 0.0 for number in range(1, _POOL + 1)}
    expected = width * _PICK / _POOL
    frequency: Counter[int] = Counter()
    last_seen: dict[int, int] = {}
    for index, row in enumerate(recent):
        for number in row.numbers:
            frequency[number] += 1
            last_seen[number] = index
    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        deficit = (expected - frequency.get(number, 0)) / max(expected, 1.0)
        gap = (width - 1 - last_seen.get(number, -1)) / width
        boundary = 1.2 if number <= 5 or number >= 35 else 1.0
        mod3 = 1.1 if number % 3 == 0 else 1.0
        scores[number] = (deficit * 0.4 + gap * 0.6) * boundary * mod3
    return scores


def _markov_scores(history: tuple[CausalDrawRow, ...]) -> list[float]:
    """Donor 30-draw Markov transition scores."""

    recent = history[-_MARKOV_WINDOW:] if len(history) >= _MARKOV_WINDOW else history
    if len(recent) < 2:
        return [1.0] * _POOL
    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for index in range(len(recent) - 1):
        for source in recent[index].numbers:
            for target in recent[index + 1].numbers:
                transition[source - 1][target - 1] += 1.0
    for row in transition:
        row_sum = sum(row)
        if row_sum != 0.0:
            for column in range(_POOL):
                row[column] /= row_sum
    scores = [0.0] * _POOL
    for source in recent[-1].numbers:
        source_row = transition[source - 1]
        for column, value in enumerate(source_row):
            scores[column] += value
    return scores


def _apply_cross_zone(
    ranked: list[int], scores: dict[int, float], count: int = _PICK
) -> list[int]:
    """Swap into the top-N until at least two zones are represented."""

    selected = list(ranked[:count])
    zones_present = {_zone(number) for number in selected}
    if len(zones_present) >= 2:
        return selected

    zone_count = Counter(_zone(number) for number in selected)
    dominant_zone = max(zone_count, key=lambda zone_id: zone_count[zone_id])
    missing_zones = [zone_id for zone_id in (1, 2, 3) if zone_id not in zones_present]

    for missing in missing_zones:
        candidates = [
            number for number in ranked if _zone(number) == missing and number not in selected
        ]
        if not candidates:
            continue
        dominant_numbers = [number for number in selected if _zone(number) == dominant_zone]
        if dominant_numbers:
            remove = min(dominant_numbers, key=lambda number: scores[number])
            selected = [number for number in selected if number != remove]
            selected.append(candidates[0])
            break
    return selected[:count]


def _predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """ACB+Markov fusion: 0.5/0.5 min-max-normalized blend, midfreq-boosted."""

    recent = history[-_ACB_WINDOW:] if len(history) >= _ACB_WINDOW else history
    width = len(recent)

    acb = _acb_scores(history)
    markov = _markov_scores(history)

    acb_values = [acb[number] for number in range(1, _POOL + 1)]
    a_min, a_max = min(acb_values), max(acb_values)
    a_range = (a_max - a_min) if a_max > a_min else 1.0
    acb_norm = [(value - a_min) / a_range for value in acb_values]

    m_min, m_max = min(markov), max(markov)
    m_range = (m_max - m_min) if m_max > m_min else 1.0
    markov_norm = [(value - m_min) / m_range for value in markov]

    expected = width * _PICK / _POOL
    frequency: Counter[int] = Counter()
    for row in recent:
        for number in row.numbers:
            frequency[number] += 1
    freq_values = [float(frequency.get(number, 0)) for number in range(1, _POOL + 1)]
    freq_mean = sum(freq_values) / len(freq_values)
    sigma = sqrt(sum((value - freq_mean) ** 2 for value in freq_values) / len(freq_values))

    combined: dict[int, float] = {}
    for index, number in enumerate(range(1, _POOL + 1)):
        is_midfreq = abs(freq_values[index] - expected) <= sigma
        boost = 1.1 if is_midfreq else 0.8
        combined[number] = (acb_norm[index] * 0.5 + markov_norm[index] * 0.5) * boost

    ranked = sorted(range(1, _POOL + 1), key=lambda number: -combined[number])
    selected = _apply_cross_zone(ranked, combined, _PICK)
    return tuple(sorted(selected))


class Daily539AcbMarkovMidfreqAdapter:
    """P31A-retired ACB+Markov midfreq-boosted fusion, single ticket."""

    strategy_id = "acb_markov_midfreq"
    strategy_name = "今彩539 ACB+Markov 中頻"
    strategy_version = "v0.1-p31a"
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
        return _validated_ticket(_predict(canonical), self.strategy_id), None


__all__ = ["Daily539AcbMarkovMidfreqAdapter"]
