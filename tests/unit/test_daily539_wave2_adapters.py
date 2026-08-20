"""Contract and source-parity tests for Daily539 wave 2 portfolio adapters.

Independent test-local oracles re-derive MidFreq, ACB, and Fourier scoring
from the pinned runner authority (window 100, descending-score / ascending-
number ties, stdlib rfft). They are not imported from the production module.
Tests drive the shipped ``PortfolioBetAdapter`` subclasses.
"""

from __future__ import annotations

import builtins
import inspect
import math
import socket
import time
from collections import Counter

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import daily539_wave2 as module
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_wave2 import (
    Daily539MidfreqAcb2BetAdapter,
    Daily539MidfreqFourier2BetAdapter,
)

_POOL = 39
_PICK = 5
_MIN_HISTORY = 100
_WINDOW = 100

_FOURIER_ADAPTER = Daily539MidfreqFourier2BetAdapter
_ACB_ADAPTER = Daily539MidfreqAcb2BetAdapter
_ADAPTERS = (_FOURIER_ADAPTER, _ACB_ADAPTER)


def _row(index: int, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(
        draw=f"d539-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _stride_row(index: int, mod: int = 39, stride: int = 8) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * stride) % mod) + 1 for step in range(_PICK)))
    assert len(set(numbers)) == _PICK
    return _row(index, numbers)


def _history(rows: list[CausalDrawRow]) -> tuple[CausalDrawRow, ...]:
    return tuple(rows)


def _oracle_recent(
    history: tuple[CausalDrawRow, ...], window: int
) -> tuple[CausalDrawRow, ...]:
    return history[-window:] if len(history) >= window else history


def _oracle_top_n(scores: list[float], count: int) -> tuple[int, ...]:
    ranked = sorted(range(_POOL), key=lambda idx: (-scores[idx], idx))
    return tuple(sorted(idx + 1 for idx in ranked[:count]))


def _oracle_midfreq_scores(history: tuple[CausalDrawRow, ...]) -> list[float]:
    recent = _oracle_recent(history, _WINDOW)
    draw_count = len(recent)
    expected = draw_count * _PICK / _POOL
    frequency = Counter(number for row in recent for number in row.numbers)
    return [-abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)]


def _oracle_acb_scores(history: tuple[CausalDrawRow, ...]) -> list[float]:
    recent = _oracle_recent(history, _WINDOW)
    draw_count = len(recent)
    probability = _PICK / _POOL
    expected = draw_count * probability
    variance = draw_count * probability * (1.0 - probability)
    sigma = math.sqrt(variance) if variance > 0 else 1.0
    frequency = Counter(number for row in recent for number in row.numbers)
    return [(expected - frequency.get(number, 0)) / sigma for number in range(1, _POOL + 1)]


def _oracle_rfft_power(series: list[float]) -> list[float]:
    length = len(series)
    mean = sum(series) / length
    centered = [value - mean for value in series]
    powers: list[float] = []
    for frequency_index in range(length // 2 + 1):
        real = 0.0
        imaginary = 0.0
        for sample_index, value in enumerate(centered):
            angle = 2.0 * math.pi * frequency_index * sample_index / length
            real += value * math.cos(angle)
            imaginary -= value * math.sin(angle)
        powers.append(real * real + imaginary * imaginary)
    return powers


def _oracle_fourier_scores(history: tuple[CausalDrawRow, ...]) -> list[float]:
    recent = _oracle_recent(history, _WINDOW)
    draw_count = len(recent)
    if draw_count < 10:
        return [0.0] * _POOL
    scores: list[float] = []
    for number in range(1, _POOL + 1):
        series = [1.0 if number in row.numbers else 0.0 for row in recent]
        if sum(series) < 2:
            scores.append(0.0)
            continue
        power = _oracle_rfft_power(series)
        if len(power) <= 1:
            scores.append(0.0)
            continue
        dominant_index = max(range(1, len(power)), key=lambda idx: power[idx])
        period = draw_count / dominant_index
        last_hit = max(index for index, value in enumerate(series) if value == 1.0)
        gap = (draw_count - 1) - last_hit
        scores.append(1.0 / (abs(gap - period) + 1.0))
    return scores


def _oracle_fourier_tickets(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    return (
        _oracle_top_n(_oracle_midfreq_scores(history), _PICK),
        _oracle_top_n(_oracle_fourier_scores(history), _PICK),
    )


def _oracle_acb_tickets(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    return (
        _oracle_top_n(_oracle_midfreq_scores(history), _PICK),
        _oracle_top_n(_oracle_acb_scores(history), _PICK),
    )


def _legal_shape(ticket: tuple[int, ...]) -> None:
    assert len(ticket) == _PICK
    assert len(set(ticket)) == _PICK
    assert all(type(number) is int for number in ticket)
    assert all(1 <= number <= _POOL for number in ticket)
    assert ticket == tuple(sorted(ticket))


# ─── identity and contract ───────────────────────────────────────────────────


def test_fourier_identity_fields_are_exact() -> None:
    adapter = _FOURIER_ADAPTER()
    assert adapter.strategy_id == "midfreq_fourier_2bet"
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == _MIN_HISTORY
    assert adapter.native_ticket_count == 2
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)
    assert isinstance(adapter, PortfolioBetAdapter)


def test_acb_identity_fields_are_exact() -> None:
    adapter = _ACB_ADAPTER()
    assert adapter.strategy_id == "midfreq_acb_2bet"
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == _MIN_HISTORY
    assert adapter.native_ticket_count == 2
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)
    assert isinstance(adapter, PortfolioBetAdapter)


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_native_ticket_count_is_two(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history([_stride_row(i) for i in range(_MIN_HISTORY)])
    tickets = adapter_class().get_bets(history, LotteryType.DAILY_539)
    assert len(tickets) == 2
    for ticket in tickets:
        _legal_shape(ticket)


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_wrong_lottery_types_rejected(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history([_stride_row(i) for i in range(_MIN_HISTORY)])
    adapter = adapter_class()
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_minimum_history_boundary(adapter_class: type[PortfolioBetAdapter]) -> None:
    short = _history([_stride_row(i) for i in range(_MIN_HISTORY - 1)])
    exact = _history([_stride_row(i) for i in range(_MIN_HISTORY)])
    with pytest.raises(InsufficientHistory):
        adapter_class().get_bets(short, LotteryType.DAILY_539)
    tickets = adapter_class().get_bets(exact, LotteryType.DAILY_539)
    assert len(tickets) == 2


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_list_history_rejected(adapter_class: type[PortfolioBetAdapter]) -> None:
    history = [_stride_row(i) for i in range(_MIN_HISTORY)]
    with pytest.raises(InvalidOutput):
        adapter_class().get_bets(history, LotteryType.DAILY_539)  # type: ignore[arg-type]


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_biglotto_shaped_history_rejected(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    rows = [_stride_row(i) for i in range(_MIN_HISTORY - 1)] + [
        CausalDrawRow("bad", "2020-01-01", (1, 2, 3, 4, 5, 6))
    ]
    with pytest.raises(InvalidOutput):
        adapter_class().get_bets(tuple(rows), LotteryType.DAILY_539)


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_no_special_second_zone_number(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history([_stride_row(i) for i in range(_MIN_HISTORY)])
    executions = adapter_class().get_bets_with_emission(history, LotteryType.DAILY_539)
    assert len(executions) == 2
    assert all(execution.special_number is None for execution in executions)


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_ticket_local_canonicalization_only(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history([_stride_row(i) for i in range(150)])
    executions = adapter_class().get_bets_with_emission(history, LotteryType.DAILY_539)
    tickets = adapter_class().get_bets(history, LotteryType.DAILY_539)
    assert tickets == tuple(execution.legal_main_numbers for execution in executions)
    for execution in executions:
        assert execution.legal_main_numbers == tuple(sorted(execution.emitted_main_numbers))
        _legal_shape(execution.legal_main_numbers)


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_repeated_execution_is_deterministic(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history([_stride_row(i) for i in range(180)])
    first = adapter_class().get_bets(history, LotteryType.DAILY_539)
    second = adapter_class().get_bets(history, LotteryType.DAILY_539)
    third = adapter_class().get_bets(history, LotteryType.DAILY_539)
    assert first == second == third


# ─── fixtures ────────────────────────────────────────────────────────────────

ORDINARY_HISTORY = _history([_stride_row(i) for i in range(_MIN_HISTORY)])
LONG_HISTORY = _history([_stride_row(i) for i in range(250)])

# Frequency-biased: last 100 draws are identical {1..5}. MidFreq prefers
# unused numbers nearest expected count; ACB prefers the same unused cold
# numbers, so both tickets collide — proving portfolio-level dedup is absent.
_BIASED_TAIL = [_row(10_000 + i, (1, 2, 3, 4, 5)) for i in range(_WINDOW)]
FREQUENCY_BIASED_HISTORY = _history(
    [_stride_row(i, stride=11) for i in range(40)] + _BIASED_TAIL
)

# Mixed frequencies so MidFreq (near-expected) and ACB (cold) diverge.
# Numbers 10-14 appear 13 times (~expected 12.82); 1-5 appear every draw;
# remaining numbers never appear (cold).
def _mixed_frequency_history() -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for index in range(_WINDOW):
        if index < 13:
            rows.append(_row(index, (1, 2, 3, 4, 5)))
        else:
            rows.append(_row(index, (1, 2, 3, 4, 10)))
    # Force 10-14 toward expected by splicing 11-14 into later draws.
    for index in range(13, 25):
        extra = 11 + ((index - 13) % 4)
        rows[index] = _row(index, tuple(sorted((1, 2, 3, extra, 10))))
    return _history(rows)


MIXED_FREQUENCY_HISTORY = _mixed_frequency_history()

# Tie-heavy MidFreq/ACB: all 39 numbers appear equally often in 39 draws of
# a sliding 5-window repeated to length 100, then padded. Use 39 identical
# cycles of every residue appearing equally: 39 draws covering each number
# exactly 5 times, repeated. For 100 draws this is imperfect; construct
# 100 copies of disjoint rotation so frequencies stay as equal as possible.
TIE_HEAVY_HISTORY = _history([_stride_row(i, stride=5) for i in range(_MIN_HISTORY)])


@pytest.mark.parametrize(
    ("adapter_class", "oracle"),
    [
        (_FOURIER_ADAPTER, _oracle_fourier_tickets),
        (_ACB_ADAPTER, _oracle_acb_tickets),
    ],
)
@pytest.mark.parametrize(
    "history",
    [
        ORDINARY_HISTORY,
        LONG_HISTORY,
        FREQUENCY_BIASED_HISTORY,
        TIE_HEAVY_HISTORY,
        MIXED_FREQUENCY_HISTORY,
    ],
    ids=["ordinary", "longer-than-window", "frequency-biased", "tie-heavy", "mixed-frequency"],
)
def test_adapter_matches_independent_oracle(
    adapter_class: type[PortfolioBetAdapter],
    oracle: object,
    history: tuple[CausalDrawRow, ...],
) -> None:
    expected = oracle(history)  # type: ignore[operator]
    tickets = adapter_class().get_bets(history, LotteryType.DAILY_539)
    assert tickets == expected
    assert len(tickets) == 2


def test_midfreq_then_fourier_native_order() -> None:
    tickets = _FOURIER_ADAPTER().get_bets(MIXED_FREQUENCY_HISTORY, LotteryType.DAILY_539)
    midfreq_ticket = _oracle_top_n(_oracle_midfreq_scores(MIXED_FREQUENCY_HISTORY), _PICK)
    fourier_ticket = _oracle_top_n(_oracle_fourier_scores(MIXED_FREQUENCY_HISTORY), _PICK)
    assert tickets[0] == midfreq_ticket
    assert tickets[1] == fourier_ticket


def test_midfreq_then_acb_native_order() -> None:
    tickets = _ACB_ADAPTER().get_bets(MIXED_FREQUENCY_HISTORY, LotteryType.DAILY_539)
    midfreq_ticket = _oracle_top_n(_oracle_midfreq_scores(MIXED_FREQUENCY_HISTORY), _PICK)
    acb_ticket = _oracle_top_n(_oracle_acb_scores(MIXED_FREQUENCY_HISTORY), _PICK)
    assert tickets[0] == midfreq_ticket
    assert tickets[1] == acb_ticket
    assert tickets[0] != tickets[1]


def test_frequency_biased_intermediate_midfreq_and_acb_scores() -> None:
    midfreq = _oracle_midfreq_scores(FREQUENCY_BIASED_HISTORY)
    acb = _oracle_acb_scores(FREQUENCY_BIASED_HISTORY)
    hot = {1, 2, 3, 4, 5}
    unused = set(range(6, _POOL + 1))
    assert all(midfreq[number - 1] < midfreq[6] for number in hot)
    assert all(acb[number - 1] < acb[6] for number in hot)
    assert min(acb[number - 1] for number in unused) > max(acb[number - 1] for number in hot)
    tickets = _ACB_ADAPTER().get_bets(FREQUENCY_BIASED_HISTORY, LotteryType.DAILY_539)
    assert tickets[0] == (6, 7, 8, 9, 10)
    assert tickets[1] == (6, 7, 8, 9, 10)


def test_identical_tickets_are_not_deduplicated() -> None:
    tickets = _ACB_ADAPTER().get_bets(FREQUENCY_BIASED_HISTORY, LotteryType.DAILY_539)
    assert tickets[0] == tickets[1]
    assert len(tickets) == 2


def test_portfolio_is_not_sorted_across_tickets() -> None:
    tickets = _FOURIER_ADAPTER().get_bets(FREQUENCY_BIASED_HISTORY, LotteryType.DAILY_539)
    assert tickets[0] == (6, 7, 8, 9, 10)
    assert tickets[1] == (1, 2, 3, 4, 5)
    assert tickets != tuple(sorted(tickets))


def test_older_prefix_beyond_window_is_ignored() -> None:
    tail = [_stride_row(i) for i in range(200, 300)]
    history_a = _history([_stride_row(i, stride=8) for i in range(80)] + tail)
    history_b = _history([_stride_row(i, stride=11) for i in range(40)] + tail)
    assert _FOURIER_ADAPTER().get_bets(history_a, LotteryType.DAILY_539) == (
        _FOURIER_ADAPTER().get_bets(history_b, LotteryType.DAILY_539)
    )
    assert _ACB_ADAPTER().get_bets(history_a, LotteryType.DAILY_539) == (
        _ACB_ADAPTER().get_bets(history_b, LotteryType.DAILY_539)
    )


def test_fourier_zero_when_number_hits_fewer_than_twice() -> None:
    history = FREQUENCY_BIASED_HISTORY
    scores = _oracle_fourier_scores(history)
    for number in range(6, _POOL + 1):
        assert scores[number - 1] == 0.0
    tickets = _FOURIER_ADAPTER().get_bets(history, LotteryType.DAILY_539)
    assert tickets[0] == _oracle_top_n(_oracle_midfreq_scores(history), _PICK)
    assert tickets[1] == _oracle_top_n(scores, _PICK)


# ─── isolation ───────────────────────────────────────────────────────────────


def test_source_has_no_forbidden_imports_or_external_state_access() -> None:
    source = inspect.getsource(module)
    forbidden_substrings = (
        "import numpy",
        "from numpy",
        "import sqlite3",
        "from sqlite3",
        "import random",
        "from random",
        "random.",
        "import requests",
        "import httpx",
        "import urllib",
        "os.environ",
        "time.time(",
        "time.monotonic(",
        "datetime.now(",
        "open(",
    )
    for forbidden in forbidden_substrings:
        assert forbidden not in source, f"forbidden reference found: {forbidden!r}"


@pytest.mark.parametrize("adapter_class", _ADAPTERS)
def test_adapter_needs_no_filesystem_clock_database_or_network(
    adapter_class: type[PortfolioBetAdapter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    tickets = adapter_class().get_bets(ORDINARY_HISTORY, LotteryType.DAILY_539)
    assert len(tickets) == 2
    for ticket in tickets:
        _legal_shape(ticket)
