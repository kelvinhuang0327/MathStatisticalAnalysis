"""Independent contract and donor-oracle tests for the frequency portfolios."""

from __future__ import annotations

import builtins
import cmath
import inspect
import math
import os
import pathlib
import socket
import sqlite3
import time
import urllib.request
from collections import Counter
from collections.abc import Callable

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import daily539_portfolio_frequency as module
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_portfolio_frequency import (
    Daily539MidfreqAcb2BetAdapter,
    Daily539MidfreqFourier2BetAdapter,
)

_POOL = 39
_PICK = 5
_WINDOW = 100

AdapterFactory = Callable[[], Daily539MidfreqAcb2BetAdapter | Daily539MidfreqFourier2BetAdapter]


def _row(index: int, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(
        draw=f"d539-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _stride_row(index: int, stride: int = 8) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * stride) % _POOL) + 1 for step in range(_PICK)))
    assert len(set(numbers)) == _PICK
    return _row(index, numbers)


def _history(count: int = 160, stride: int = 8) -> tuple[CausalDrawRow, ...]:
    return tuple(_stride_row(index, stride) for index in range(count))


def _oracle_top_n(scores: dict[int, float]) -> tuple[int, ...]:
    ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    return tuple(sorted(ranked[:_PICK]))


def _oracle_midfreq(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-_WINDOW:]
    expected = len(recent) * _PICK / _POOL
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    scores = {number: -abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)}
    return _oracle_top_n(scores)


def _oracle_acb(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-_WINDOW:]
    probability = _PICK / _POOL
    expected = len(recent) * probability
    sigma = (len(recent) * probability * (1.0 - probability)) ** 0.5
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    scores = {
        number: (expected - frequency.get(number, 0)) / sigma for number in range(1, _POOL + 1)
    }
    return _oracle_top_n(scores)


def _oracle_fourier_power(series: tuple[float, ...]) -> tuple[float, ...]:
    """Independent direct DFT oracle for the donor's rfft power bins."""

    length = len(series)
    centered = tuple(value - sum(series) / length for value in series)
    return tuple(
        abs(
            sum(
                value * cmath.exp(-2j * math.pi * frequency * index / length)
                for index, value in enumerate(centered)
            )
        )
        ** 2
        for frequency in range(length // 2 + 1)
    )


def _oracle_fourier(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-_WINDOW:]
    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        series = tuple(1.0 if number in row.numbers else 0.0 for row in recent)
        if sum(series) < 2:
            scores[number] = 0.0
            continue
        power = _oracle_fourier_power(series)
        dominant_index = max(
            range(1, len(power)), key=lambda frequency_index: power[frequency_index]
        )
        period = len(recent) / dominant_index
        last_hit = max(index for index, value in enumerate(series) if value == 1.0)
        gap = len(recent) - 1 - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return _oracle_top_n(scores)


ADAPTERS: tuple[tuple[AdapterFactory, str, str], ...] = (
    (
        Daily539MidfreqAcb2BetAdapter,
        "midfreq_acb_2bet",
        "今彩539 中頻 ACB 2注",
    ),
    (
        Daily539MidfreqFourier2BetAdapter,
        "midfreq_fourier_2bet",
        "今彩539 中頻 Fourier 2注",
    ),
)


def _bad_list(history: tuple[CausalDrawRow, ...]) -> object:
    return list(history)


def _bad_object(history: tuple[CausalDrawRow, ...]) -> object:
    return (*history[:-1], object())


def _bad_short_row(history: tuple[CausalDrawRow, ...]) -> object:
    return (*history[:-1], _row(159, (1, 2, 3, 4)))


def _bad_duplicate_row(history: tuple[CausalDrawRow, ...]) -> object:
    return (*history[:-1], _row(159, (1, 2, 3, 4, 1)))


def _bad_bool_row(history: tuple[CausalDrawRow, ...]) -> object:
    return (*history[:-1], _row(159, (1, 2, 3, 4, True)))


def _bad_range_row(history: tuple[CausalDrawRow, ...]) -> object:
    return (*history[:-1], _row(159, (1, 2, 3, 4, 40)))


def _bad_empty_draw(history: tuple[CausalDrawRow, ...]) -> object:
    return (*history[:-1], CausalDrawRow("", "2020-01-01", (1, 2, 3, 4, 5)))


def _bad_empty_date(history: tuple[CausalDrawRow, ...]) -> object:
    return (*history[:-1], CausalDrawRow("d", "", (1, 2, 3, 4, 5)))


BAD_HISTORY_FACTORIES: tuple[Callable[[tuple[CausalDrawRow, ...]], object], ...] = (
    _bad_list,
    _bad_object,
    _bad_short_row,
    _bad_duplicate_row,
    _bad_bool_row,
    _bad_range_row,
    _bad_empty_draw,
    _bad_empty_date,
)


def _malformed_predict(
    _history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    return ((1, 2, 3, 4, 5),)


@pytest.mark.parametrize("factory,strategy_id,strategy_name", ADAPTERS)
def test_identity_native_count_order_and_shape(
    factory: AdapterFactory, strategy_id: str, strategy_name: str
) -> None:
    adapter = factory()
    assert adapter.strategy_id == strategy_id  # type: ignore[attr-defined]
    assert adapter.strategy_name == strategy_name  # type: ignore[attr-defined]
    assert adapter.strategy_version == "v0.1"  # type: ignore[attr-defined]
    assert adapter.min_history == 100  # type: ignore[attr-defined]
    assert adapter.native_ticket_count == 2  # type: ignore[attr-defined]
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)  # type: ignore[attr-defined]

    bets = adapter.get_bets(_history(), LotteryType.DAILY_539)  # type: ignore[attr-defined]
    assert type(bets) is tuple
    assert len(bets) == 2
    assert all(type(ticket) is tuple for ticket in bets)
    assert all(len(ticket) == _PICK for ticket in bets)
    assert all(ticket == tuple(sorted(ticket)) for ticket in bets)
    assert all(len(set(ticket)) == _PICK for ticket in bets)
    assert all(all(type(number) is int for number in ticket) for ticket in bets)
    assert all(all(1 <= number <= _POOL for number in ticket) for ticket in bets)


def test_midfreq_acb_matches_independent_donor_oracle() -> None:
    history = _history(173, stride=11)
    expected = (_oracle_midfreq(history), _oracle_acb(history))
    assert Daily539MidfreqAcb2BetAdapter().get_bets(history, LotteryType.DAILY_539) == expected


def test_midfreq_fourier_matches_independent_donor_oracle() -> None:
    history = _history(173, stride=11)
    expected = (_oracle_midfreq(history), _oracle_fourier(history))
    assert Daily539MidfreqFourier2BetAdapter().get_bets(history, LotteryType.DAILY_539) == expected


def test_native_ticket_order_and_positional_duplicate_are_preserved() -> None:
    history = tuple(_row(index, (1, 2, 3, 4, 5)) for index in range(_WINDOW))
    assert Daily539MidfreqAcb2BetAdapter().get_bets(history, LotteryType.DAILY_539) == (
        (6, 7, 8, 9, 10),
        (6, 7, 8, 9, 10),
    )
    assert Daily539MidfreqFourier2BetAdapter().get_bets(history, LotteryType.DAILY_539) == (
        (6, 7, 8, 9, 10),
        (1, 2, 3, 4, 5),
    )


@pytest.mark.parametrize("factory,_,__", ADAPTERS)
def test_insufficient_history_is_rejected(factory: AdapterFactory, _: str, __: str) -> None:
    with pytest.raises(InsufficientHistory):
        factory().get_bets(_history(99), LotteryType.DAILY_539)  # type: ignore[attr-defined]


@pytest.mark.parametrize("factory,_,__", ADAPTERS)
@pytest.mark.parametrize("lottery_type", [LotteryType.BIG_LOTTO, LotteryType.POWER_LOTTO])
def test_wrong_lottery_type_is_rejected(
    factory: AdapterFactory, _: str, __: str, lottery_type: LotteryType
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        factory().get_bets(_history(), lottery_type)  # type: ignore[attr-defined]


@pytest.mark.parametrize("factory,_,__", ADAPTERS)
@pytest.mark.parametrize(
    "bad_history",
    BAD_HISTORY_FACTORIES,
)
def test_malformed_history_or_numbers_are_rejected(
    factory: AdapterFactory,
    _: str,
    __: str,
    bad_history: Callable[[tuple[CausalDrawRow, ...]], object],
) -> None:
    with pytest.raises(InvalidOutput):
        factory().get_bets(  # type: ignore[attr-defined]
            bad_history(_history()), LotteryType.DAILY_539
        )


@pytest.mark.parametrize("factory,_,__", ADAPTERS)
def test_malformed_native_output_fails_closed(
    factory: AdapterFactory, _: str, __: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = factory()
    monkeypatch.setattr(adapter, "_predict_all", _malformed_predict)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(_history(), LotteryType.DAILY_539)  # type: ignore[attr-defined]


@pytest.mark.parametrize("factory,_,__", ADAPTERS)
def test_deterministic_repeat(factory: AdapterFactory, _: str, __: str) -> None:
    history = _history(201, stride=11)
    adapter = factory()
    first = adapter.get_bets(history, LotteryType.DAILY_539)  # type: ignore[attr-defined]
    second = adapter.get_bets(history, LotteryType.DAILY_539)  # type: ignore[attr-defined]
    third = factory().get_bets(history, LotteryType.DAILY_539)  # type: ignore[attr-defined]
    assert first == second == third


@pytest.mark.parametrize("factory,_,__", ADAPTERS)
def test_causal_prefix_invariance(factory: AdapterFactory, _: str, __: str) -> None:
    tail = _history(100, stride=17)
    short_history = tail
    long_history = _history(50, stride=3) + tuple(
        _row(index + 50, row.numbers) for index, row in enumerate(tail)
    )
    assert len(long_history) == 150
    assert tuple(row.numbers for row in short_history[-100:]) == tuple(
        row.numbers for row in long_history[-100:]
    )
    adapter = factory()
    assert adapter.get_bets(  # type: ignore[attr-defined]
        short_history, LotteryType.DAILY_539
    ) == adapter.get_bets(long_history, LotteryType.DAILY_539)  # type: ignore[attr-defined]


def test_prediction_source_has_no_external_state_imports() -> None:
    source = inspect.getsource(module)
    forbidden = (
        "import numpy",
        "from numpy",
        "import sqlite3",
        "from sqlite3",
        "import random",
        "from random",
        "import requests",
        "import httpx",
        "import urllib",
        "import pathlib",
        "os.environ",
        "time.time(",
        "time.monotonic(",
        "datetime.now(",
        "open(",
    )
    for token in forbidden:
        assert token not in source, f"forbidden reference found: {token!r}"


@pytest.mark.parametrize("factory,_,__", ADAPTERS)
def test_prediction_uses_no_database_network_filesystem_or_clock(
    factory: AdapterFactory, _: str, __: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden during prediction")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    bets = factory().get_bets(_history(), LotteryType.DAILY_539)  # type: ignore[attr-defined]
    assert len(bets) == 2
