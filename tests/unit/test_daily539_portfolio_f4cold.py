"""Independent contract and parity tests for the DAILY_539 F4Cold card."""

from __future__ import annotations

import builtins
import math
import pathlib
import socket
import sqlite3
import urllib.request

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import daily539_portfolio_f4cold as module
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_portfolio_f4cold import (
    Daily539F4Cold3BetAdapter,
    Daily539F4Cold5BetAdapter,
)

_POOL = 39
_PICK = 5
_MIN_HISTORY = 100
_FOURIER_WINDOW = 500


def _row(index: int, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(
        draw=f"d539-{index}",
        date=f"2024-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
        numbers=numbers,
    )


def _stride_numbers(index: int, phase: int = 0) -> tuple[int, ...]:
    """Five distinct residues from a deterministic coprime stride."""

    numbers = tuple(sorted(((index + phase + step * 8) % _POOL) + 1 for step in range(_PICK)))
    assert len(set(numbers)) == _PICK
    return numbers


def _history(length: int = 180, phase: int = 0, start: int = 0) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(start + index, _stride_numbers(index, phase)) for index in range(length))


def _direct_dft_oracle(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Independent test-local translation of the frozen donor algorithm.

    Unlike the production implementation, this deliberately computes every
    centered indicator sample in the DFT sum instead of using the
    mathematically equivalent hit-position shortcut.  Positive FFT bins,
    first-maximum selection, stable ascending number ties, four orthogonal
    tickets, and the final 100-draw cold ticket mirror the donor contract.
    """

    recent = history[-_FOURIER_WINDOW:] if len(history) >= _FOURIER_WINDOW else history
    width = len(recent)
    scores: dict[int, float] = {}
    positive_bins = range(1, (width - 1) // 2 + 1)

    for number in range(1, _POOL + 1):
        indicator = [1.0 if number in row.numbers else 0.0 for row in recent]
        if sum(indicator) < 2:
            scores[number] = 0.0
            continue
        mean = sum(indicator) / width
        best_magnitude = -1.0
        best_frequency = 0.0
        for frequency_bin in positive_bins:
            real = 0.0
            imaginary = 0.0
            for position, value in enumerate(indicator):
                angle = 2.0 * math.pi * frequency_bin * position / width
                centered = value - mean
                real += centered * math.cos(angle)
                imaginary += centered * math.sin(angle)
            magnitude = math.hypot(real, imaginary)
            if magnitude > best_magnitude:
                best_magnitude = magnitude
                best_frequency = frequency_bin / width
        if best_frequency == 0.0:
            scores[number] = 0.0
            continue
        last_hit = max(index for index, value in enumerate(indicator) if value == 1.0)
        gap = (width - 1) - last_hit
        period = 1.0 / best_frequency
        scores[number] = 1.0 / (abs(gap - period) + 1.0)

    ranked = [
        number
        for number in sorted(scores, key=lambda candidate: -scores[candidate])
        if scores[number] > 0.0
    ]
    assert len(ranked) >= 4 * _PICK
    bets = [sorted(ranked[index * _PICK : (index + 1) * _PICK]) for index in range(4)]
    excluded = {number for bet in bets for number in bet}

    frequencies = {number: 0 for number in range(1, _POOL + 1)}
    for row in history[-100:]:
        for number in row.numbers:
            frequencies[number] += 1
    cold_sorted = sorted(range(1, _POOL + 1), key=lambda number: frequencies[number])
    bets.append(sorted([number for number in cold_sorted if number not in excluded][:5]))
    assert all(len(ticket) == _PICK for ticket in bets)
    return tuple(tuple(ticket) for ticket in bets)


@pytest.fixture
def parity_history() -> tuple[CausalDrawRow, ...]:
    return _history()


def test_full_five_ticket_output_matches_independent_donor_oracle(
    parity_history: tuple[CausalDrawRow, ...],
) -> None:
    expected = _direct_dft_oracle(parity_history)
    actual = Daily539F4Cold5BetAdapter().get_bets(parity_history, LotteryType.DAILY_539)
    assert actual == expected
    assert actual == (
        (2, 3, 10, 25, 33),
        (4, 11, 18, 26, 34),
        (5, 12, 19, 27, 35),
        (6, 13, 20, 28, 36),
        (1, 7, 8, 9, 14),
    )


def test_three_ticket_output_is_exact_first_three_ticket_slice(
    parity_history: tuple[CausalDrawRow, ...],
) -> None:
    five = Daily539F4Cold5BetAdapter().get_bets(parity_history, LotteryType.DAILY_539)
    three = Daily539F4Cold3BetAdapter().get_bets(parity_history, LotteryType.DAILY_539)
    assert len(three) == 3
    assert three == five[:3]
    assert three == (
        (2, 3, 10, 25, 33),
        (4, 11, 18, 26, 34),
        (5, 12, 19, 27, 35),
    )


@pytest.mark.parametrize(
    ("adapter_class", "strategy_id", "strategy_name", "native_count"),
    [
        (
            Daily539F4Cold3BetAdapter,
            "daily539_f4cold_3bet",
            "今彩539 F4Cold 3注",
            3,
        ),
        (
            Daily539F4Cold5BetAdapter,
            "daily539_f4cold_5bet",
            "今彩539 F4Cold 5注",
            5,
        ),
    ],
)
def test_identity_native_count_and_ticket_shape(
    adapter_class: type[Daily539F4Cold3BetAdapter | Daily539F4Cold5BetAdapter],
    strategy_id: str,
    strategy_name: str,
    native_count: int,
    parity_history: tuple[CausalDrawRow, ...],
) -> None:
    adapter = adapter_class()
    assert adapter.strategy_id == strategy_id
    assert adapter.strategy_name == strategy_name
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == _MIN_HISTORY
    assert adapter.native_ticket_count == native_count
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)

    bets = adapter.get_bets(parity_history, LotteryType.DAILY_539)
    assert type(bets) is tuple
    assert len(bets) == native_count
    for ticket in bets:
        assert type(ticket) is tuple
        assert len(ticket) == _PICK
        assert all(type(number) is int for number in ticket)
        assert len(set(ticket)) == _PICK
        assert all(1 <= number <= _POOL for number in ticket)
        assert ticket == tuple(sorted(ticket))


@pytest.mark.parametrize("adapter_class", [Daily539F4Cold3BetAdapter, Daily539F4Cold5BetAdapter])
def test_insufficient_history_rejected(adapter_class: type[object]) -> None:
    adapter = adapter_class()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(_history(_MIN_HISTORY - 1), LotteryType.DAILY_539)  # type: ignore[attr-defined]


@pytest.mark.parametrize("adapter_class", [Daily539F4Cold3BetAdapter, Daily539F4Cold5BetAdapter])
@pytest.mark.parametrize("lottery_type", [LotteryType.BIG_LOTTO, LotteryType.POWER_LOTTO])
def test_wrong_lottery_type_rejected(
    adapter_class: type[object], lottery_type: LotteryType
) -> None:
    adapter = adapter_class()
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_history(), lottery_type)  # type: ignore[attr-defined]


@pytest.mark.parametrize("adapter_class", [Daily539F4Cold3BetAdapter, Daily539F4Cold5BetAdapter])
def test_malformed_history_container_rejected(adapter_class: type[object]) -> None:
    adapter = adapter_class()
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_history()), LotteryType.DAILY_539)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "bad_row",
    [
        object(),
        CausalDrawRow("", "2024-01-01", (1, 2, 3, 4, 5)),
        CausalDrawRow("d539-bad", "", (1, 2, 3, 4, 5)),
        CausalDrawRow("d539-bad", "2024-01-01", (1, 2, 3, 4)),
        CausalDrawRow("d539-bad", "2024-01-01", (1, 2, 3, 4, True)),  # type: ignore[arg-type]
        CausalDrawRow("d539-bad", "2024-01-01", (1, 2, 3, 4, 40)),
        CausalDrawRow("d539-bad", "2024-01-01", (1, 1, 2, 3, 4)),
        CausalDrawRow("d539-bad", "2024-01-01", [1, 2, 3, 4, 5]),  # type: ignore[arg-type]
    ],
)
@pytest.mark.parametrize("adapter_class", [Daily539F4Cold3BetAdapter, Daily539F4Cold5BetAdapter])
def test_malformed_history_or_numbers_rejected(
    adapter_class: type[object], bad_row: object
) -> None:
    adapter = adapter_class()
    rows = (*_history(_MIN_HISTORY - 1), bad_row)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(rows, LotteryType.DAILY_539)  # type: ignore[attr-defined]


def test_malformed_native_output_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    parity_history: tuple[CausalDrawRow, ...],
) -> None:
    def malformed_predict(
        _history: tuple[CausalDrawRow, ...],
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5),)

    monkeypatch.setattr(module, "_predict_f4cold_all", malformed_predict)
    with pytest.raises(InvalidOutput):
        Daily539F4Cold5BetAdapter().get_bets(parity_history, LotteryType.DAILY_539)


def test_repeated_prediction_is_deterministic(
    parity_history: tuple[CausalDrawRow, ...],
) -> None:
    adapter = Daily539F4Cold5BetAdapter()
    first = adapter.get_bets(parity_history, LotteryType.DAILY_539)
    second = adapter.get_bets(parity_history, LotteryType.DAILY_539)
    third = Daily539F4Cold5BetAdapter().get_bets(parity_history, LotteryType.DAILY_539)
    assert first == second == third


def test_older_prefix_is_causally_invisible_once_outside_500_draw_window() -> None:
    shared_tail = _history(500, phase=17, start=1000)
    history_one = _history(75, phase=0, start=0) + shared_tail
    history_two = _history(160, phase=11, start=2000) + shared_tail
    adapter = Daily539F4Cold5BetAdapter()
    assert adapter.get_bets(history_one, LotteryType.DAILY_539) == adapter.get_bets(
        history_two, LotteryType.DAILY_539
    )


def test_positive_frequency_ties_follow_ascending_number_order() -> None:
    groups = (
        (1, 2, 3, 4, 5),
        (6, 7, 8, 9, 10),
        (11, 12, 13, 14, 15),
        (16, 17, 18, 19, 20),
        (21, 22, 23, 24, 25),
        (26, 27, 28, 29, 30),
        (31, 32, 33, 34, 35),
        (35, 36, 37, 38, 39),
    )
    history = tuple(_row(index, groups[index % len(groups)]) for index in range(500))
    expected = _direct_dft_oracle(history)
    assert expected == (
        (35, 36, 37, 38, 39),
        (1, 2, 3, 4, 5),
        (6, 31, 32, 33, 34),
        (7, 8, 9, 10, 26),
        (21, 22, 23, 24, 25),
    )
    assert Daily539F4Cold5BetAdapter().get_bets(history, LotteryType.DAILY_539) == expected


def test_prediction_does_not_access_sqlite_network_or_filesystem(
    monkeypatch: pytest.MonkeyPatch,
    parity_history: tuple[CausalDrawRow, ...],
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("prediction attempted forbidden external access")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)

    bets = Daily539F4Cold5BetAdapter().get_bets(parity_history, LotteryType.DAILY_539)
    assert len(bets) == 5
