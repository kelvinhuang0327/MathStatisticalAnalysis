"""Independent contract and donor-oracle tests for the P36 zone-gap composite."""

from __future__ import annotations

import builtins
import pathlib
import socket
import sqlite3
import urllib.request
from collections import Counter

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_zone_gap import Daily539ZoneGap3BetAdapter

_POOL = 39
_PICK = 5
_ZONE_WINDOW = 100

# CPython's frozenset(range(27, 40)) iteration order -- verified against the
# donor's own `list(_Z3)` -- differs from ascending and is the tie-break
# order for zone 3 candidates sharing an identical combined score.
_ZONE_NUMBERS = {
    1: tuple(range(1, 14)),
    2: tuple(range(14, 27)),
    3: (32, 33, 34, 35, 36, 37, 38, 39, 27, 28, 29, 30, 31),
}


def _row(index: int, offset: int = 0) -> CausalDrawRow:
    numbers = tuple(sorted(((offset + index + step * 7) % _POOL) + 1 for step in range(_PICK)))
    assert len(set(numbers)) == _PICK
    return CausalDrawRow(
        draw=f"d-{index}-{offset}", date=f"2020-01-{(index % 28) + 1:02d}", numbers=numbers
    )


def _history(count: int = 140, offset: int = 0) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(index, offset) for index in range(count))


def _zone(number: int) -> int:
    return 1 if number <= 13 else 2 if number <= 26 else 3


def _oracle(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-_ZONE_WINDOW:] if len(history) >= _ZONE_WINDOW else history
    width = len(recent)

    zone_counter: Counter[int] = Counter()
    for row in recent:
        for number in row.numbers:
            zone_counter[_zone(number)] += 1

    total = sum(zone_counter.values())
    expected_zone = total / 3.0
    zone_deficit = {
        zone_id: max(0.0, expected_zone - zone_counter.get(zone_id, 0)) for zone_id in (1, 2, 3)
    }
    total_deficit = sum(zone_deficit.values())

    if total_deficit == 0:
        allocations = {1: 2, 2: 2, 3: 1}
    else:
        raw = {zone_id: zone_deficit[zone_id] / total_deficit * _PICK for zone_id in (1, 2, 3)}
        allocations = {zone_id: max(1, round(raw[zone_id])) for zone_id in (1, 2, 3)}
        while sum(allocations.values()) > _PICK:
            allocations[max(allocations, key=lambda zone_id: allocations[zone_id])] -= 1
        while sum(allocations.values()) < _PICK:
            allocations[min(allocations, key=lambda zone_id: allocations[zone_id])] += 1

    last_seen: dict[int, int] = {}
    for index, row in enumerate(recent):
        for number in row.numbers:
            last_seen[number] = index
    gap_scores = {
        number: (width - 1 - last_seen.get(number, -1)) / width for number in range(1, _POOL + 1)
    }

    combined: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        share = zone_deficit.get(_zone(number), 0.0) / max(total_deficit, 1.0)
        combined[number] = share * 0.5 + gap_scores[number] * 0.5

    result: list[int] = []
    for zone_id in (1, 2, 3):
        ranked_in_zone = sorted(_ZONE_NUMBERS[zone_id], key=lambda number: -combined[number])
        result.extend(ranked_in_zone[: allocations[zone_id]])
    return tuple(sorted(result[:_PICK]))


def test_identity_and_donor_version() -> None:
    adapter = Daily539ZoneGap3BetAdapter()
    assert adapter.strategy_id == "zone_gap_3bet_539"
    assert adapter.strategy_name == "今彩539 Zone+Gap 3注"
    assert adapter.strategy_version == "v0.1-p36"
    assert adapter.min_history == 100
    assert adapter.native_ticket_count == 1
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)


@pytest.mark.parametrize("offset", [0, 3, 11, 23])
def test_matches_independent_donor_oracle(offset: int) -> None:
    history = _history(140, offset)
    expected = _oracle(history)
    actual, special = Daily539ZoneGap3BetAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert actual == expected
    assert special is None


def test_zone_three_tie_break_follows_donor_frozenset_iteration_order() -> None:
    """Every draw is identical, so every number's gap score and zone share tie.

    Within zone 3 the donor's stable sort over ``list(frozenset(range(27, 40)))``
    keeps CPython's non-ascending iteration order for the tie; an
    ascending-number tie-break would silently pick a different candidate.
    """

    constant_row = CausalDrawRow(draw="const", date="2020-01-01", numbers=(1, 14, 27, 28, 29))
    history = tuple(
        CausalDrawRow(draw=f"c-{i}", date="2020-01-01", numbers=constant_row.numbers)
        for i in range(100)
    )
    expected = _oracle(history)
    actual, _ = Daily539ZoneGap3BetAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert actual == expected


def test_minimum_history_boundary() -> None:
    adapter = Daily539ZoneGap3BetAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet(_history(99), LotteryType.DAILY_539)
    numbers, special = adapter.get_one_bet(_history(100), LotteryType.DAILY_539)
    assert len(numbers) == _PICK
    assert special is None


def test_prefix_before_window_does_not_change_result() -> None:
    tail = _history(100, 4)
    first = _history(20, 0) + tail
    second = _history(140, 17) + tail
    adapter = Daily539ZoneGap3BetAdapter()
    assert adapter.get_one_bet(first, LotteryType.DAILY_539) == adapter.get_one_bet(
        second, LotteryType.DAILY_539
    )


def test_wrong_lottery_type_rejected() -> None:
    with pytest.raises(UnsupportedLotteryType):
        Daily539ZoneGap3BetAdapter().get_one_bet(_history(120), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize(
    "bad_row",
    [
        object(),
        CausalDrawRow("", "2020-01-01", (1, 2, 3, 4, 5)),
        CausalDrawRow("d-bad", "", (1, 2, 3, 4, 5)),
        CausalDrawRow("d-bad", "2020-01-01", (1, 2, 3, 4)),
        CausalDrawRow("d-bad", "2020-01-01", (1, 2, 3, 4, 40)),
        CausalDrawRow("d-bad", "2020-01-01", (1, 1, 2, 3, 4)),
    ],
)
def test_malformed_history_rejected(bad_row: object) -> None:
    rows = (*_history(120)[:-1], bad_row)
    with pytest.raises(InvalidOutput):
        Daily539ZoneGap3BetAdapter().get_one_bet(rows, LotteryType.DAILY_539)


def test_malformed_history_container_rejected() -> None:
    with pytest.raises(InvalidOutput):
        Daily539ZoneGap3BetAdapter().get_one_bet(list(_history(120)), LotteryType.DAILY_539)


def test_repeated_prediction_is_deterministic() -> None:
    history = _history()
    adapter = Daily539ZoneGap3BetAdapter()
    first = adapter.get_one_bet(history, LotteryType.DAILY_539)
    second = adapter.get_one_bet(history, LotteryType.DAILY_539)
    assert first == second


def test_prediction_does_not_access_sqlite_network_or_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("prediction attempted forbidden external access")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)

    numbers, special = Daily539ZoneGap3BetAdapter().get_one_bet(_history(), LotteryType.DAILY_539)
    assert len(numbers) == _PICK
    assert special is None
