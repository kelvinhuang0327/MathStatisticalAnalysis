"""Unregistered, distinct research derivative of the frozen Wave12 QuickML.

Only the historical-pattern loop upper bound changes: each three-row slice
must also leave a valid next row at ``index + 3``. The advanced calculation
is copied from the frozen implementation with that one bound corrected;
its helpers and the complete hybrid calculation are reused unchanged.

The successor does not use the frozen parent's history >= 5 closure, alter
the parent, register itself, or inherit the parent's historical evidence.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections import Counter, defaultdict
from typing import ClassVar

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_wave12 import (
    _MAX_NUMBER,
    _PICK_COUNT,
    _mean,
    _population_standard_deviation,
    _quick_ml_hybrid,
    _ticket,
)


def _quick_ml_advanced(recent_first: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    scores: defaultdict[int, float] = defaultdict(float)
    for weight, period in zip((0.4, 0.3, 0.2, 0.1), (10, 20, 30, 50), strict=True):
        frequency = Counter(
            number
            for draw in recent_first[: min(period, len(recent_first))]
            for number in draw.numbers
        )
        maximum = max(frequency.values()) if frequency else 1
        for number, count in frequency.items():
            scores[number] += count / maximum * weight * 15

    for number in range(1, _MAX_NUMBER + 1):
        missing = 0
        for draw in recent_first:
            if number in draw.numbers:
                break
            missing += 1
        if missing > 0:
            scores[number] += min(missing / 10, 2.5) * 12

    for number in range(1, _MAX_NUMBER + 1):
        appearances = [index for index, draw in enumerate(recent_first) if number in draw.numbers]
        if len(appearances) >= 3:
            intervals = [
                appearances[index] - appearances[index + 1] for index in range(len(appearances) - 1)
            ]
            average_interval = _mean(intervals)
            standard_deviation = _population_standard_deviation(intervals)
            current_missing = appearances[0] if appearances else len(recent_first)
            if abs(current_missing - average_interval) < standard_deviation:
                scores[number] += 10

    recent_numbers = [number for draw in recent_first[:5] for number in draw.numbers]
    for number in range(1, _MAX_NUMBER + 1):
        if number - 1 in recent_numbers or number + 1 in recent_numbers:
            scores[number] += 8

    recent_odd_counts = [
        sum(1 for number in draw.numbers if number % 2 == 1) for draw in recent_first[:20]
    ]
    average_odd = _mean(recent_odd_counts)
    for number in range(1, _MAX_NUMBER + 1):
        if (number % 2 == 1 and average_odd > _PICK_COUNT / 2) or (
            number % 2 == 0 and average_odd < _PICK_COUNT / 2
        ):
            scores[number] += 8

    zone_size = _MAX_NUMBER // 3
    zone_counts = [0, 0, 0]
    for draw in recent_first[:10]:
        for number in draw.numbers:
            zone = min((number - 1) // zone_size, 2)
            zone_counts[zone] += 1
    average_zone = _mean(zone_counts)
    for number in range(1, _MAX_NUMBER + 1):
        zone = min((number - 1) // zone_size, 2)
        if zone_counts[zone] < average_zone:
            scores[number] += 8

    temporary_top = sorted(scores.items(), key=lambda item: item[1], reverse=True)[
        : _PICK_COUNT * 2
    ]
    for number, _score in temporary_top:
        scores[number] += 7

    recent_acs: list[int] = []
    for draw in recent_first[:20]:
        numbers = sorted(draw.numbers)
        differences = [numbers[index + 1] - numbers[index] for index in range(len(numbers) - 1)]
        recent_acs.append(len(set(differences)))
    average_ac = _mean(recent_acs)
    if average_ac > _PICK_COUNT - 2:
        for number in range(1, _MAX_NUMBER + 1):
            if number % 7 == 0:
                scores[number] += 7

    recent_pattern = recent_first[:3]
    for index in range(3, len(recent_first) - 3):
        pattern = recent_first[index : index + 3]
        similarity = 0.0
        for position in range(3):
            intersection = len(
                set(pattern[position].numbers) & set(recent_pattern[position].numbers)
            )
            similarity += intersection / _PICK_COUNT
        similarity /= 3
        if similarity > 0.25:
            next_numbers = recent_first[index + 3].numbers
            for number in next_numbers:
                scores[number] += similarity * 15

    for number in range(1, _MAX_NUMBER + 1):
        probability = 0.0
        for index, draw in enumerate(recent_first[:30]):
            if number in draw.numbers:
                probability += 0.9**index * 10
        scores[number] += probability

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return _ticket([number for number, _score in ranked[:_PICK_COUNT]])


class BigLottoQuickMlCorrectedSuccessorAdapter(PortfolioBetAdapter):
    """Deterministic two-ticket successor, available only by direct import."""

    strategy_id = "research_biglotto__quick_ml_corrected_successor_v1"
    strategy_name = "BigLotto QuickML corrected successor (2 tickets)"
    strategy_version = "v1"
    status: ClassVar[str] = "UNREGISTERED_RESEARCH_DERIVATIVE"
    provenance: ClassVar[tuple[str, ...]] = (
        "frozen_parent_strategy_id:legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
        "frozen_donor_source:tools/quick_ml_predict.py",
        "frozen_donor_source_sha256:"
        "8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80",
        "frozen_implementation_module:src/lottolab/strategies/adapters/biglotto_wave12.py",
        "correction:historical-pattern range(3, len(recent_first) - 1)"
        " -> range(3, len(recent_first) - 3)",
        "lineage_status:DISTINCT_DERIVATIVE",
    )
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        recent_first = tuple(reversed(history))
        return (_quick_ml_advanced(recent_first), _quick_ml_hybrid(recent_first))


__all__ = ["BigLottoQuickMlCorrectedSuccessorAdapter"]
