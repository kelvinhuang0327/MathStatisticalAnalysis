"""Independent contract and donor-parity tests for the T539 phase-2 card."""

from __future__ import annotations

import builtins
import pathlib
import socket
import sqlite3
import time
import urllib.request
from collections import Counter
from itertools import pairwise
from math import sqrt

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_portfolio_phase2 import (
    Daily539AcbMarkovMidfreq3BetAdapter,
)

_POOL = 39
_PICK = 5
_ACB_WINDOW = 100
_MIDFREQ_WINDOW = 100
_MARKOV_WINDOW = 30


def _row(index: int, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(
        draw=f"d539-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _stride_row(index: int, mod: int = _POOL, stride: int = 8) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * stride) % mod) + 1 for step in range(_PICK)))
    assert len(set(numbers)) == _PICK
    return _row(index, numbers)


def _history(rows: list[CausalDrawRow]) -> tuple[CausalDrawRow, ...]:
    return tuple(rows)


def _oracle_top_dict(scores: dict[int, float]) -> tuple[int, ...]:
    ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    return tuple(sorted(ranked[:_PICK]))


def _oracle_top_array(scores: list[float]) -> tuple[int, ...]:
    ranked = sorted(
        range(1, _POOL + 1),
        key=lambda number: (-scores[number - 1], number),
    )
    return tuple(sorted(ranked[:_PICK]))


def _oracle_predict(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Test-local pure-Python transcription of the pinned donor formulas."""

    acb_recent = history[-_ACB_WINDOW:]
    width = len(acb_recent)
    probability = _PICK / _POOL
    expected = width * probability
    sigma = sqrt(width * probability * (1.0 - probability))
    acb_frequency: Counter[int] = Counter(number for row in acb_recent for number in row.numbers)
    acb = {
        number: (expected - acb_frequency.get(number, 0)) / sigma for number in range(1, _POOL + 1)
    }

    midfreq_frequency: Counter[int] = Counter(
        number for row in acb_recent for number in row.numbers
    )
    midfreq = {
        number: -abs(midfreq_frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)
    }

    markov_recent = history[-_MARKOV_WINDOW:]
    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for current, following in pairwise(markov_recent):
        for source in current.numbers:
            for target in following.numbers:
                transition[source - 1][target - 1] += 1.0
    for row in transition:
        row_sum = sum(row)
        if row_sum != 0.0:
            for index, value in enumerate(row):
                row[index] = value / row_sum
    markov = [0.0] * _POOL
    for source in markov_recent[-1].numbers:
        for index, value in enumerate(transition[source - 1]):
            markov[index] += value

    return (_oracle_top_dict(acb), _oracle_top_array(markov), _oracle_top_dict(midfreq))


def test_identity_and_native_shape_are_exact() -> None:
    adapter = Daily539AcbMarkovMidfreq3BetAdapter()
    assert adapter.strategy_id == "acb_markov_midfreq_3bet"
    assert adapter.strategy_name == "今彩539 ACB+Markov 中頻 3注"
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == 100
    assert adapter.native_ticket_count == 3
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)

    bets = adapter.get_bets(_history([_stride_row(i) for i in range(100)]), LotteryType.DAILY_539)
    assert type(bets) is tuple
    assert len(bets) == 3
    for ticket in bets:
        assert type(ticket) is tuple
        assert len(ticket) == _PICK
        assert all(type(number) is int for number in ticket)
        assert len(set(ticket)) == _PICK
        assert all(1 <= number <= _POOL for number in ticket)
        assert ticket == tuple(sorted(ticket))


def test_donor_oracle_parity_preserves_acb_markov_midfreq_order() -> None:
    tail = [_row(1000 + index, (20, 21, 22, 23, 24)) for index in range(_MARKOV_WINDOW)]
    history = _history([_stride_row(i) for i in range(100)] + tail)
    assert Daily539AcbMarkovMidfreq3BetAdapter().get_bets(
        history, LotteryType.DAILY_539
    ) == _oracle_predict(history)


def test_donor_oracle_parity_on_multiple_synthetic_histories() -> None:
    adapter = Daily539AcbMarkovMidfreq3BetAdapter()
    for length, stride in ((100, 5), (101, 11), (150, 17), (300, 8)):
        history = _history([_stride_row(index, stride=stride) for index in range(length)])
        assert adapter.get_bets(history, LotteryType.DAILY_539) == _oracle_predict(history)


def test_positional_duplicate_tickets_are_preserved() -> None:
    history = _history([_row(index, (1, 2, 3, 4, 5)) for index in range(100)])
    bets = Daily539AcbMarkovMidfreq3BetAdapter().get_bets(history, LotteryType.DAILY_539)
    assert bets[0] == bets[2]
    assert len(bets) == 3


def test_insufficient_history_is_rejected_at_exact_boundary() -> None:
    adapter = Daily539AcbMarkovMidfreq3BetAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(_history([_stride_row(i) for i in range(99)]), LotteryType.DAILY_539)
    adapter.get_bets(_history([_stride_row(i) for i in range(100)]), LotteryType.DAILY_539)


@pytest.mark.parametrize("lottery_type", [LotteryType.BIG_LOTTO, LotteryType.POWER_LOTTO])
def test_wrong_lottery_type_is_rejected(lottery_type: LotteryType) -> None:
    history = _history([_stride_row(i) for i in range(100)])
    with pytest.raises(UnsupportedLotteryType):
        Daily539AcbMarkovMidfreq3BetAdapter().get_bets(history, lottery_type)


def test_malformed_history_container_and_row_are_rejected() -> None:
    adapter = Daily539AcbMarkovMidfreq3BetAdapter()
    rows = [_stride_row(i) for i in range(100)]
    with pytest.raises(InvalidOutput):
        adapter.get_bets(rows, LotteryType.DAILY_539)  # type: ignore[arg-type]
    with pytest.raises(InvalidOutput):
        adapter.get_bets(
            tuple([*rows[:-1], (1, 2, 3, 4, 5)]),  # type: ignore[list-item]
            LotteryType.DAILY_539,
        )


@pytest.mark.parametrize(
    "bad_numbers",
    [
        (1, 2, 3, 4),
        (1, 1, 2, 3, 4),
        (1, 2, 3, 4, 40),
        (1, 2, 3, 4, True),
        [1, 2, 3, 4, 5],
    ],
)
def test_malformed_history_numbers_are_rejected(bad_numbers: object) -> None:
    rows: list[CausalDrawRow] = [_stride_row(i) for i in range(99)]
    rows.append(_row(99, bad_numbers))  # type: ignore[arg-type]
    with pytest.raises(InvalidOutput):
        Daily539AcbMarkovMidfreq3BetAdapter().get_bets(tuple(rows), LotteryType.DAILY_539)


def test_deterministic_repeat() -> None:
    history = _history([_stride_row(i, stride=11) for i in range(250)])
    adapter = Daily539AcbMarkovMidfreq3BetAdapter()
    assert adapter.get_bets(history, LotteryType.DAILY_539) == adapter.get_bets(
        history, LotteryType.DAILY_539
    )
    assert adapter.get_bets(history, LotteryType.DAILY_539) == (
        Daily539AcbMarkovMidfreq3BetAdapter().get_bets(history, LotteryType.DAILY_539)
    )


def test_causal_prefix_invariance() -> None:
    tail = [_row(1000 + index, (20, 21, 22, 23, 24)) for index in range(_ACB_WINDOW)]
    first = _history([_stride_row(i, stride=5) for i in range(70)] + tail)
    second = _history([_stride_row(i, stride=11) for i in range(150)] + tail)
    adapter = Daily539AcbMarkovMidfreq3BetAdapter()
    assert adapter.get_bets(first, LotteryType.DAILY_539) == adapter.get_bets(
        second, LotteryType.DAILY_539
    )


def test_no_external_state_access_during_prediction(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _history([_stride_row(i) for i in range(120)])
    bets = Daily539AcbMarkovMidfreq3BetAdapter().get_bets(history, LotteryType.DAILY_539)
    assert bets == _oracle_predict(history)


def test_emission_preserves_ticket_order_and_no_special() -> None:
    history = _history([_stride_row(i) for i in range(120)])
    adapter = Daily539AcbMarkovMidfreq3BetAdapter()
    executions = adapter.get_bets_with_emission(history, LotteryType.DAILY_539)
    assert tuple(execution.legal_main_numbers for execution in executions) == adapter.get_bets(
        history, LotteryType.DAILY_539
    )
    assert tuple(execution.emitted_main_numbers for execution in executions) == adapter.get_bets(
        history, LotteryType.DAILY_539
    )
    assert all(execution.special_number is None for execution in executions)
