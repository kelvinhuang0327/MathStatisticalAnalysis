"""Pure-Python DAILY_539 port of the P36 zone-gap composite strategy.

Donor: ``ZoneGap3Bet539Adapter`` / ``predict_zone_gap_1bet`` in
``LotteryNewMeraged/lottery_api/models/p36_wave2_daily539_adapters.py``
(``strategy_id=zone_gap_3bet_539``, ``strategy_version=v0.1-p36``). The donor
only records and implements bet-1 of the named 3-bet identity -- no bet-2 or
bet-3 algorithm exists in any donor script -- so only that proven bet-1 is
ported here, matching how the P31A/P36 family's other bet-1-only identities
were already migrated.

Algorithm: allocate the five picks across the three zones (1-13, 14-26,
27-39) in proportion to each zone's frequency deficit over the trailing 100
draws (falling back to a fixed 2/2/1 split when no zone is deficient), then
within each zone rank candidates by a 50/50 blend of zone deficit share and
per-number recency gap, taking each zone's top allocation. The donor used a
``round()``-then-rebalance integer allocation and plain Python floats
throughout (no numpy); this port is a direct, unchanged transcription,
including the donor's own dead ``zone_num_deficit`` local (computed but never
read) which is dropped here since it cannot affect the result.
"""

from __future__ import annotations

from collections import Counter
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
_ZONE_WINDOW = 100


# The donor's ``zone_nums = {1: list(_Z1), ...}`` iterates each zone's frozenset
# directly; CPython's small-int hash placement makes zones 1-2 iterate
# ascending but zone 3 does not (verified empirically against
# ``frozenset(range(27, 40))``: ``[32, 33, ..., 39, 27, 28, ..., 31]``). The
# donor's ranking sort is stable, so this iteration order is the tie-break
# for numbers with an identical combined score -- it must be reproduced
# exactly, not assumed ascending.
_ZONE_NUMBERS: dict[int, tuple[int, ...]] = {
    1: tuple(range(1, 14)),
    2: tuple(range(14, 27)),
    3: (32, 33, 34, 35, 36, 37, 38, 39, 27, 28, 29, 30, 31),
}


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
    if number <= 13:
        return 1
    if number <= 26:
        return 2
    return 3


def _zone_allocations(zone_counter: Counter[int]) -> dict[int, int]:
    total = sum(zone_counter.values())
    expected_zone = total / 3.0
    zone_deficit = {
        zone_id: max(0.0, expected_zone - zone_counter.get(zone_id, 0)) for zone_id in (1, 2, 3)
    }
    total_deficit = sum(zone_deficit.values())

    if total_deficit == 0:
        return {1: 2, 2: 2, 3: 1}

    raw = {zone_id: zone_deficit[zone_id] / total_deficit * _PICK for zone_id in (1, 2, 3)}
    allocations = {zone_id: max(1, round(raw[zone_id])) for zone_id in (1, 2, 3)}
    while sum(allocations.values()) > _PICK:
        max_zone = max(allocations, key=lambda zone_id: allocations[zone_id])
        allocations[max_zone] -= 1
    while sum(allocations.values()) < _PICK:
        min_zone = min(allocations, key=lambda zone_id: allocations[zone_id])
        allocations[min_zone] += 1
    return allocations


def _predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-_ZONE_WINDOW:] if len(history) >= _ZONE_WINDOW else history
    width = len(recent)

    zone_counter: Counter[int] = Counter()
    for row in recent:
        for number in row.numbers:
            zone_counter[_zone(number)] += 1

    allocations = _zone_allocations(zone_counter)

    expected_zone = sum(zone_counter.values()) / 3.0
    zone_deficit = {
        zone_id: max(0.0, expected_zone - zone_counter.get(zone_id, 0)) for zone_id in (1, 2, 3)
    }
    total_deficit = sum(zone_deficit.values())

    last_seen: dict[int, int] = {}
    for index, row in enumerate(recent):
        for number in row.numbers:
            last_seen[number] = index

    gap_scores = {
        number: (width - 1 - last_seen.get(number, -1)) / width for number in range(1, _POOL + 1)
    }

    combined: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        zone_share = zone_deficit.get(_zone(number), 0.0) / max(total_deficit, 1.0)
        combined[number] = zone_share * 0.5 + gap_scores[number] * 0.5

    result: list[int] = []
    for zone_id in (1, 2, 3):
        # Stable sort: ties keep _ZONE_NUMBERS[zone_id]'s donor-matching order.
        ranked_in_zone = sorted(_ZONE_NUMBERS[zone_id], key=lambda number: -combined[number])
        result.extend(ranked_in_zone[: allocations[zone_id]])

    return tuple(sorted(result[:_PICK]))


class Daily539ZoneGap3BetAdapter:
    """P36 zone-gap composite identity, bet-1 only (donor never records more)."""

    strategy_id = "zone_gap_3bet_539"
    strategy_name = "今彩539 Zone+Gap 3注"
    strategy_version = "v0.1-p36"
    min_history = _ZONE_WINDOW
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


__all__ = ["Daily539ZoneGap3BetAdapter"]
