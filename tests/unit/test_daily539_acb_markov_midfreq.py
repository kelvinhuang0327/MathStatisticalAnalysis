"""Independent contract and donor-oracle tests for the P31A ACB+Markov fusion."""

from __future__ import annotations

import builtins
import pathlib
import socket
import sqlite3
import urllib.request
from collections import Counter
from math import sqrt

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_acb_markov_midfreq import (
    Daily539AcbMarkovMidfreqAdapter,
)

_POOL = 39
_PICK = 5
_ACB_WINDOW = 100
_MARKOV_WINDOW = 30


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
    recent = history[-_ACB_WINDOW:] if len(history) >= _ACB_WINDOW else history
    width = len(recent)
    expected = width * _PICK / _POOL

    frequency: Counter[int] = Counter()
    last_seen: dict[int, int] = {}
    for index, row in enumerate(recent):
        for number in row.numbers:
            frequency[number] += 1
            last_seen[number] = index

    acb: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        deficit = (expected - frequency.get(number, 0)) / max(expected, 1.0)
        gap = (width - 1 - last_seen.get(number, -1)) / width
        boundary = 1.2 if number <= 5 or number >= 35 else 1.0
        mod3 = 1.1 if number % 3 == 0 else 1.0
        acb[number] = (deficit * 0.4 + gap * 0.6) * boundary * mod3

    markov_recent = history[-_MARKOV_WINDOW:] if len(history) >= _MARKOV_WINDOW else history
    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for index in range(len(markov_recent) - 1):
        for source in markov_recent[index].numbers:
            for target in markov_recent[index + 1].numbers:
                transition[source - 1][target - 1] += 1.0
    for row_values in transition:
        row_sum = sum(row_values)
        if row_sum != 0.0:
            for column in range(_POOL):
                row_values[column] /= row_sum
    markov = [0.0] * _POOL
    for source in markov_recent[-1].numbers:
        for column, value in enumerate(transition[source - 1]):
            markov[column] += value

    acb_values = [acb[number] for number in range(1, _POOL + 1)]
    a_min, a_max = min(acb_values), max(acb_values)
    a_range = (a_max - a_min) if a_max > a_min else 1.0
    acb_norm = [(value - a_min) / a_range for value in acb_values]

    m_min, m_max = min(markov), max(markov)
    m_range = (m_max - m_min) if m_max > m_min else 1.0
    markov_norm = [(value - m_min) / m_range for value in markov]

    freq_values = [float(frequency.get(number, 0)) for number in range(1, _POOL + 1)]
    freq_mean = sum(freq_values) / len(freq_values)
    sigma = sqrt(sum((value - freq_mean) ** 2 for value in freq_values) / len(freq_values))

    combined: dict[int, float] = {}
    for index, number in enumerate(range(1, _POOL + 1)):
        boost = 1.1 if abs(freq_values[index] - expected) <= sigma else 0.8
        combined[number] = (acb_norm[index] * 0.5 + markov_norm[index] * 0.5) * boost

    ranked = sorted(range(1, _POOL + 1), key=lambda number: -combined[number])
    selected = list(ranked[:_PICK])
    zones_present = {_zone(number) for number in selected}
    if len(zones_present) < 2:
        zone_counts = Counter(_zone(number) for number in selected)
        dominant = max(zone_counts, key=lambda zone_id: zone_counts[zone_id])
        for missing in (1, 2, 3):
            if missing in zones_present:
                continue
            candidates = [
                number for number in ranked if _zone(number) == missing and number not in selected
            ]
            dominant_numbers = [number for number in selected if _zone(number) == dominant]
            if candidates and dominant_numbers:
                remove = min(dominant_numbers, key=lambda number: combined[number])
                selected = [number for number in selected if number != remove]
                selected.append(candidates[0])
                break
    return tuple(sorted(selected[:_PICK]))


def test_identity_and_donor_version() -> None:
    adapter = Daily539AcbMarkovMidfreqAdapter()
    assert adapter.strategy_id == "acb_markov_midfreq"
    assert adapter.strategy_name == "今彩539 ACB+Markov 中頻"
    assert adapter.strategy_version == "v0.1-p31a"
    assert adapter.min_history == 100
    assert adapter.native_ticket_count == 1
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)


@pytest.mark.parametrize("offset", [0, 3, 11, 23])
def test_matches_independent_donor_oracle(offset: int) -> None:
    history = _history(140, offset)
    expected = _oracle(history)
    actual, special = Daily539AcbMarkovMidfreqAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert actual == expected
    assert special is None


def test_minimum_history_boundary() -> None:
    adapter = Daily539AcbMarkovMidfreqAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet(_history(99), LotteryType.DAILY_539)
    numbers, special = adapter.get_one_bet(_history(100), LotteryType.DAILY_539)
    assert len(numbers) == _PICK
    assert special is None


def test_prefix_before_window_does_not_change_result() -> None:
    tail = _history(100, 4)
    first = _history(20, 0) + tail
    second = _history(140, 17) + tail
    adapter = Daily539AcbMarkovMidfreqAdapter()
    assert adapter.get_one_bet(first, LotteryType.DAILY_539) == adapter.get_one_bet(
        second, LotteryType.DAILY_539
    )


def test_wrong_lottery_type_rejected() -> None:
    with pytest.raises(UnsupportedLotteryType):
        Daily539AcbMarkovMidfreqAdapter().get_one_bet(_history(120), LotteryType.BIG_LOTTO)


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
        Daily539AcbMarkovMidfreqAdapter().get_one_bet(rows, LotteryType.DAILY_539)


def test_malformed_history_container_rejected() -> None:
    with pytest.raises(InvalidOutput):
        Daily539AcbMarkovMidfreqAdapter().get_one_bet(list(_history(120)), LotteryType.DAILY_539)


def test_repeated_prediction_is_deterministic() -> None:
    history = _history()
    adapter = Daily539AcbMarkovMidfreqAdapter()
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

    numbers, special = Daily539AcbMarkovMidfreqAdapter().get_one_bet(
        _history(), LotteryType.DAILY_539
    )
    assert len(numbers) == _PICK
    assert special is None
