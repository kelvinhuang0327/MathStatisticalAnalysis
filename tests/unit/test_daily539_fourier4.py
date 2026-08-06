"""Independent contract and donor-oracle tests for the P36 Fourier4正交 bets."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import math
import pathlib
import socket
import sqlite3
import urllib.request
from collections import Counter
from unittest import mock

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import daily539_fourier4 as module
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_fourier4 import (
    Daily539P0bFourierColdFmidAdapter,
    Daily539P0cFourierColdX2Adapter,
)

_POOL = 39
_PICK = 5
_MIN_HISTORY = 100
_FOURIER_WINDOW = 500
_MIDFREQ_WINDOW = 100
_ACB_WINDOW = 100


def _row(index: int, offset: int = 0) -> CausalDrawRow:
    numbers = tuple(sorted(((offset + index + step * 7) % _POOL) + 1 for step in range(_PICK)))
    assert len(set(numbers)) == _PICK
    return CausalDrawRow(
        draw=f"d-{index}-{offset}", date=f"2020-01-{(index % 28) + 1:02d}", numbers=numbers
    )


def _history(count: int = 150, offset: int = 0) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(index, offset) for index in range(count))


def _fourier_oracle(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Independent translation mirroring numpy.fft.rfft(series - mean) exactly:

    every centered sample is summed (not just hit positions), and the
    positive-bin range includes the Nyquist bin (``width // 2``), matching
    ``rfft``'s ``power[1:]`` rather than the F4Cold donor's strictly-positive
    ``fftfreq`` range.
    """

    recent = history[-_FOURIER_WINDOW:] if len(history) >= _FOURIER_WINDOW else history
    width = len(recent)
    scores: dict[int, float] = {}
    max_bin = width // 2

    for number in range(1, _POOL + 1):
        indicator = [1.0 if number in row.numbers else 0.0 for row in recent]
        if sum(indicator) < 2 or max_bin < 1:
            scores[number] = 0.0
            continue
        mean = sum(indicator) / width
        best_magnitude = -1.0
        best_frequency = 0.0
        for frequency_bin in range(1, max_bin + 1):
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
    return scores


def _midfreq_oracle(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    recent = history[-_MIDFREQ_WINDOW:] if len(history) >= _MIDFREQ_WINDOW else history
    width = len(recent)
    expected = width * _PICK / _POOL
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    return {number: -abs(frequency.get(number, 0) - expected) for number in range(1, _POOL + 1)}


def _acb_oracle(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    recent = history[-_ACB_WINDOW:] if len(history) >= _ACB_WINDOW else history
    width = len(recent)
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


def _oracle_with_fallback(
    history: tuple[CausalDrawRow, ...], fallback: dict[int, float]
) -> tuple[int, ...]:
    scores = _fourier_oracle(history)
    ranked = [
        number
        for number in sorted(scores, key=lambda candidate: -scores[candidate])
        if scores[number] > 0.0
    ]
    if len(ranked) < _PICK:
        seen = set(ranked)
        remaining = [
            number
            for number in sorted(fallback, key=lambda candidate: -fallback[candidate])
            if number not in seen
        ]
        ranked = ranked + remaining
    return tuple(sorted(ranked[:_PICK]))


@pytest.mark.parametrize(
    ("adapter_class", "strategy_id", "strategy_name", "fallback_builder"),
    [
        (
            Daily539P0bFourierColdFmidAdapter,
            "p0b_539_3bet_f_cold_fmid",
            "今彩539 Fourier4正交 cold+midfreq 3注",
            _midfreq_oracle,
        ),
        (
            Daily539P0cFourierColdX2Adapter,
            "p0c_539_3bet_f_cold_x2",
            "今彩539 Fourier4正交 x2 cold 3注",
            _acb_oracle,
        ),
    ],
)
def test_identity_and_donor_version(
    adapter_class: type[Daily539P0bFourierColdFmidAdapter | Daily539P0cFourierColdX2Adapter],
    strategy_id: str,
    strategy_name: str,
    fallback_builder: object,
) -> None:
    adapter = adapter_class()
    assert adapter.strategy_id == strategy_id
    assert adapter.strategy_name == strategy_name
    assert adapter.strategy_version == "v0.1-p36"
    assert adapter.min_history == _MIN_HISTORY
    assert adapter.native_ticket_count == 1
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)


@pytest.mark.parametrize("offset", [0, 3, 11])
def test_p0b_matches_independent_donor_oracle(offset: int) -> None:
    history = _history(150, offset)
    expected = _oracle_with_fallback(history, _midfreq_oracle(history))
    actual, special = Daily539P0bFourierColdFmidAdapter().get_one_bet(
        history, LotteryType.DAILY_539
    )
    assert actual == expected
    assert special is None


@pytest.mark.parametrize("offset", [0, 3, 11])
def test_p0c_matches_independent_donor_oracle(offset: int) -> None:
    history = _history(150, offset)
    expected = _oracle_with_fallback(history, _acb_oracle(history))
    actual, special = Daily539P0cFourierColdX2Adapter().get_one_bet(
        history, LotteryType.DAILY_539
    )
    assert actual == expected
    assert special is None


def test_p0b_and_p0c_share_the_same_fourier_ranking_when_no_fallback_needed() -> None:
    history = _history(500, 5)
    p0b, _ = Daily539P0bFourierColdFmidAdapter().get_one_bet(history, LotteryType.DAILY_539)
    p0c, _ = Daily539P0cFourierColdX2Adapter().get_one_bet(history, LotteryType.DAILY_539)
    assert p0b == p0c


def test_fallback_branch_is_exercised_directly() -> None:
    """pool=39/pick=5/min_history=100 make <5 positive-Fourier numbers
    unreachable via any real history (every draw forces 5 distinct hits, so
    by pigeonhole at least 5 numbers accrue >=2 hits by min_history). The
    fallback path is still real donor logic (donor explicitly guards for it),
    so it is exercised here as a white-box unit against the internal helper
    rather than left unverified.
    """

    history = _history(100, 0)
    sparse_fourier = {1: 0.9, 2: 0.5, 3: 0.0, **{n: 0.0 for n in range(4, _POOL + 1)}}
    fallback = {number: float(_POOL - number) for number in range(1, _POOL + 1)}

    with mock.patch.object(module, "_fourier_scores", return_value=sparse_fourier):
        predicted = module._predict_with_fallback(history, fallback)

    assert len(predicted) == _PICK
    assert predicted == tuple(sorted(predicted))
    # Fourier-positive numbers 1 and 2 must lead; the remaining three come
    # from the fallback ranking (highest fallback score first: 39, 38, 37,
    # ..., skipping any already selected).
    assert set(predicted) & {1, 2} == {1, 2}
    remaining_expected = [
        n for n in sorted(fallback, key=lambda x: -fallback[x]) if n not in (1, 2)
    ]
    assert set(predicted) - {1, 2} == set(remaining_expected[:3])


def test_minimum_history_boundary() -> None:
    for adapter in (Daily539P0bFourierColdFmidAdapter(), Daily539P0cFourierColdX2Adapter()):
        with pytest.raises(InsufficientHistory):
            adapter.get_one_bet(_history(_MIN_HISTORY - 1), LotteryType.DAILY_539)
        numbers, special = adapter.get_one_bet(_history(_MIN_HISTORY), LotteryType.DAILY_539)
        assert len(numbers) == _PICK
        assert special is None


def test_older_prefix_is_causally_invisible_once_outside_500_draw_window() -> None:
    shared_tail = _history(500, 17)
    history_one = _history(75, 0) + shared_tail
    history_two = _history(160, 11) + shared_tail
    for adapter in (Daily539P0bFourierColdFmidAdapter(), Daily539P0cFourierColdX2Adapter()):
        assert adapter.get_one_bet(history_one, LotteryType.DAILY_539) == adapter.get_one_bet(
            history_two, LotteryType.DAILY_539
        )


def test_wrong_lottery_type_rejected() -> None:
    for adapter in (Daily539P0bFourierColdFmidAdapter(), Daily539P0cFourierColdX2Adapter()):
        with pytest.raises(UnsupportedLotteryType):
            adapter.get_one_bet(_history(120), LotteryType.BIG_LOTTO)


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
    for adapter in (Daily539P0bFourierColdFmidAdapter(), Daily539P0cFourierColdX2Adapter()):
        with pytest.raises(InvalidOutput):
            adapter.get_one_bet(rows, LotteryType.DAILY_539)


def test_malformed_history_container_rejected() -> None:
    for adapter in (Daily539P0bFourierColdFmidAdapter(), Daily539P0cFourierColdX2Adapter()):
        with pytest.raises(InvalidOutput):
            adapter.get_one_bet(list(_history(120)), LotteryType.DAILY_539)


def test_repeated_prediction_is_deterministic() -> None:
    history = _history()
    for adapter in (Daily539P0bFourierColdFmidAdapter(), Daily539P0cFourierColdX2Adapter()):
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

    history = _history()
    for adapter in (Daily539P0bFourierColdFmidAdapter(), Daily539P0cFourierColdX2Adapter()):
        numbers, special = adapter.get_one_bet(history, LotteryType.DAILY_539)
        assert len(numbers) == _PICK
        assert special is None
