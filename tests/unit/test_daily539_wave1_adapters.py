"""Contract and parity tests for the isolated Daily539 Markov Cold adapter.

The oracle below is an independent, test-local pure-Python translation of the
pinned donor algorithm (LotteryNewMeraged/tools/backtest_39lotto_comprehensive.py
::MarkovStrategy, window=30) — written from the frozen algorithm description,
not imported from the production module — used to prove the adapter's output
matches the donor's numpy-based transition-matrix scoring, including its
descending-score / ascending-number tie order.
"""

from __future__ import annotations

import builtins
import socket
import time

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import daily539_wave1 as module
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_wave1 import Daily539MarkovColdAdapter

_POOL = 39
_PICK = 5
_WINDOW = 30


def _row(index: int, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(
        draw=f"d539-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _stride_row(index: int, mod: int = 39, stride: int = 8) -> CausalDrawRow:
    """Deterministic 5-of-mod draw. Stride 8 is coprime with 39, so five
    consecutive steps always land on five distinct residues — no collisions."""

    numbers = tuple(sorted(((index + step * stride) % mod) + 1 for step in range(_PICK)))
    assert len(set(numbers)) == _PICK
    return _row(index, numbers)


def _history(rows: list[CausalDrawRow]) -> tuple[CausalDrawRow, ...]:
    return tuple(rows)


def _oracle_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Independent pure-Python port of the frozen donor Markov(window=30)
    algorithm: build a POOLxPOOL transition-count matrix over the causal
    window, normalize each source row by its own sum, sum the normalized rows
    for the latest draw's numbers, then rank descending by score with ties
    broken by ascending lottery number (mirrors ``np.argsort(-scores)``'s
    donor-index-order tie semantics)."""

    recent = history[-_WINDOW:] if len(history) >= _WINDOW else history
    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for i in range(len(recent) - 1):
        current_numbers = recent[i].numbers
        next_numbers = recent[i + 1].numbers
        for a in current_numbers:
            for b in next_numbers:
                transition[a - 1][b - 1] += 1.0
    for row in transition:
        row_sum = sum(row)
        if row_sum != 0:
            for j in range(_POOL):
                row[j] /= row_sum
    last_numbers = recent[-1].numbers
    scores = [0.0] * _POOL
    for a in last_numbers:
        row = transition[a - 1]
        for j in range(_POOL):
            scores[j] += row[j]
    ranked = sorted(range(_POOL), key=lambda idx: (-scores[idx], idx))
    return tuple(sorted(idx + 1 for idx in ranked[:_PICK]))


# ─── identity and boundary ───────────────────────────────────────────────────


def test_identity_fields_are_exact() -> None:
    adapter = Daily539MarkovColdAdapter()
    assert adapter.strategy_id == "daily539_markov_cold"
    assert adapter.strategy_name == "今彩539 Markov Cold"
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == 100
    assert adapter.supported_lottery_types == (LotteryType.DAILY_539,)


def test_daily_539_accepted() -> None:
    history = _history([_stride_row(i) for i in range(100)])
    numbers, special = Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert len(numbers) == _PICK
    assert special is None


def test_big_lotto_rejected() -> None:
    history = _history([_stride_row(i) for i in range(100)])
    with pytest.raises(UnsupportedLotteryType):
        Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)


def test_power_lotto_rejected() -> None:
    history = _history([_stride_row(i) for i in range(100)])
    with pytest.raises(UnsupportedLotteryType):
        Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.POWER_LOTTO)


def test_list_history_rejected() -> None:
    history = [_stride_row(i) for i in range(100)]
    with pytest.raises(InvalidOutput):
        Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.DAILY_539)  # type: ignore[arg-type]


def test_non_causal_draw_row_rejected() -> None:
    rows = [_stride_row(i) for i in range(99)] + [(1, 2, 3, 4, 5)]  # type: ignore[list-item]
    with pytest.raises(InvalidOutput):
        Daily539MarkovColdAdapter().get_one_bet(tuple(rows), LotteryType.DAILY_539)  # type: ignore[arg-type]


def test_99_rows_raises_insufficient_history() -> None:
    history = _history([_stride_row(i) for i in range(99)])
    with pytest.raises(InsufficientHistory):
        Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.DAILY_539)


def test_100_rows_is_the_exact_boundary() -> None:
    history = _history([_stride_row(i) for i in range(100)])
    numbers, _ = Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert len(numbers) == _PICK


def test_malformed_row_number_count_rejected() -> None:
    rows = [_stride_row(i) for i in range(99)] + [_row(99, (1, 2, 3, 4))]
    with pytest.raises(InvalidOutput):
        Daily539MarkovColdAdapter().get_one_bet(tuple(rows), LotteryType.DAILY_539)


def test_duplicate_row_number_rejected() -> None:
    rows = [_stride_row(i) for i in range(99)] + [_row(99, (1, 1, 2, 3, 4))]
    with pytest.raises(InvalidOutput):
        Daily539MarkovColdAdapter().get_one_bet(tuple(rows), LotteryType.DAILY_539)


def test_bool_as_int_rejected() -> None:
    rows = [_stride_row(i) for i in range(99)] + [_row(99, (1, 2, 3, 4, True))]  # type: ignore[list-item]
    with pytest.raises(InvalidOutput):
        Daily539MarkovColdAdapter().get_one_bet(tuple(rows), LotteryType.DAILY_539)


def test_out_of_range_values_rejected() -> None:
    rows = [_stride_row(i) for i in range(99)] + [_row(99, (1, 2, 3, 4, 40))]
    with pytest.raises(InvalidOutput):
        Daily539MarkovColdAdapter().get_one_bet(tuple(rows), LotteryType.DAILY_539)


# ─── output contract ─────────────────────────────────────────────────────────


def test_output_is_exactly_five_unique_sorted_builtin_ints_in_range() -> None:
    history = _history([_stride_row(i) for i in range(300)])
    numbers, special = Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert len(numbers) == _PICK
    assert len(set(numbers)) == _PICK
    assert all(type(n) is int for n in numbers)
    assert all(1 <= n <= _POOL for n in numbers)
    assert numbers == tuple(sorted(numbers))
    assert special is None


def test_get_one_bet_with_emission_matches_get_one_bet() -> None:
    history = _history([_stride_row(i) for i in range(150)])
    adapter = Daily539MarkovColdAdapter()
    execution = adapter.get_one_bet_with_emission(history, LotteryType.DAILY_539)
    numbers, special = adapter.get_one_bet(history, LotteryType.DAILY_539)
    assert execution.legal_main_numbers == numbers
    assert execution.special_number == special
    assert execution.special_number is None


# ─── parity fixtures ──────────────────────────────────────────────────────────

# Fixture A — transition-dominant: the last-30 window is 30 identical draws of
# {20..24}, so every source row in {20..24} funnels 100% of its normalized
# transition mass into exactly those five columns — an unambiguous nonzero
# dominant signal, distinct from the tie fixture's all-zero result below.
_DOMINANT_TAIL = [_row(1000 + i, (20, 21, 22, 23, 24)) for i in range(_WINDOW)]
FIXTURE_A_HISTORY = _history([_stride_row(i) for i in range(70)] + _DOMINANT_TAIL)
FIXTURE_A_EXPECTED = (20, 21, 22, 23, 24)


def test_transition_dominant_fixture_matches_oracle_and_expected() -> None:
    assert _oracle_predict(FIXTURE_A_HISTORY) == FIXTURE_A_EXPECTED
    numbers, _ = Daily539MarkovColdAdapter().get_one_bet(FIXTURE_A_HISTORY, LotteryType.DAILY_539)
    assert numbers == FIXTURE_A_EXPECTED


# Fixture B — older-prefix invariance: two histories share the identical
# last-30-row dominant tail but differ in every earlier row (different
# stride and different total length), proving only ``history[-30:]`` is
# causally visible to the prediction.
FIXTURE_B_HISTORY_1 = _history([_stride_row(i, stride=8) for i in range(70)] + _DOMINANT_TAIL)
FIXTURE_B_HISTORY_2 = _history([_stride_row(i, stride=11) for i in range(120)] + _DOMINANT_TAIL)


def test_older_prefix_invariance_fixture_matches_oracle_and_expected() -> None:
    assert _oracle_predict(FIXTURE_B_HISTORY_1) == FIXTURE_A_EXPECTED
    assert _oracle_predict(FIXTURE_B_HISTORY_2) == FIXTURE_A_EXPECTED
    adapter = Daily539MarkovColdAdapter()
    numbers_1, _ = adapter.get_one_bet(FIXTURE_B_HISTORY_1, LotteryType.DAILY_539)
    numbers_2, _ = adapter.get_one_bet(FIXTURE_B_HISTORY_2, LotteryType.DAILY_539)
    assert numbers_1 == numbers_2 == FIXTURE_A_EXPECTED


# Fixture C — score tie proving ascending-number order: the window's first 29
# rows are drawn only from 1..34, and the final window row is (35..39), a set
# that never appeared earlier in the window. Those five numbers' transition
# rows are therefore never incremented (all-zero), so every one of the 39
# scores is exactly 0.0 — a full 39-way tie resolved purely by the
# (-score, ascending index) sort key, yielding the five smallest numbers.
def _bounded_stride_row(index: int, mod: int = 34, stride: int = 8) -> CausalDrawRow:
    return _row(index, tuple(sorted(((index + step * stride) % mod) + 1 for step in range(_PICK))))


_TIE_WINDOW = [_bounded_stride_row(i) for i in range(_WINDOW - 1)] + [
    _row(2000, (35, 36, 37, 38, 39))
]
FIXTURE_C_HISTORY = _history([_bounded_stride_row(i) for i in range(70)] + _TIE_WINDOW)
FIXTURE_C_EXPECTED = (1, 2, 3, 4, 5)


def test_score_tie_fixture_proves_ascending_number_order() -> None:
    assert len(FIXTURE_C_HISTORY[-_WINDOW:]) == _WINDOW
    seen_before_last_row = {n for row in FIXTURE_C_HISTORY[-_WINDOW:-1] for n in row.numbers}
    assert seen_before_last_row.isdisjoint({35, 36, 37, 38, 39})

    assert _oracle_predict(FIXTURE_C_HISTORY) == FIXTURE_C_EXPECTED
    numbers, _ = Daily539MarkovColdAdapter().get_one_bet(FIXTURE_C_HISTORY, LotteryType.DAILY_539)
    assert numbers == FIXTURE_C_EXPECTED
    assert numbers != FIXTURE_A_EXPECTED  # distinct mechanism from the dominant fixture


# Fixture D — repeated-call determinism.
FIXTURE_D_HISTORY = _history([_stride_row(i) for i in range(250)])


def test_repeated_call_fixture_is_deterministic() -> None:
    adapter = Daily539MarkovColdAdapter()
    first = adapter.get_one_bet(FIXTURE_D_HISTORY, LotteryType.DAILY_539)
    second = adapter.get_one_bet(FIXTURE_D_HISTORY, LotteryType.DAILY_539)
    third = Daily539MarkovColdAdapter().get_one_bet(FIXTURE_D_HISTORY, LotteryType.DAILY_539)
    assert first == second == third
    assert first == (_oracle_predict(FIXTURE_D_HISTORY), None)


@pytest.mark.parametrize("n", [100, 101, 150, 300])
def test_production_adapter_matches_oracle_across_generic_histories(n: int) -> None:
    history = _history([_stride_row(i) for i in range(n)])
    expected = _oracle_predict(history)
    numbers, special = Daily539MarkovColdAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert numbers == expected
    assert special is None


def test_recent_target_draw_rolls_forward() -> None:
    """100 -> 101 adds one causal draw and changes the window's tail,
    proving the adapter is sensitive to the most recent target draw."""
    history_100 = _history([_stride_row(i) for i in range(100)])
    history_101 = _history([_stride_row(i) for i in range(101)])
    numbers_100, _ = Daily539MarkovColdAdapter().get_one_bet(history_100, LotteryType.DAILY_539)
    numbers_101, _ = Daily539MarkovColdAdapter().get_one_bet(history_101, LotteryType.DAILY_539)
    assert numbers_100 != numbers_101


# ─── negative dependency proof ───────────────────────────────────────────────


def test_source_has_no_forbidden_imports_or_external_state_access() -> None:
    import inspect

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


def test_adapter_needs_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    numbers, _ = Daily539MarkovColdAdapter().get_one_bet(FIXTURE_A_HISTORY, LotteryType.DAILY_539)
    assert numbers == FIXTURE_A_EXPECTED


def test_history_rows_are_immutable() -> None:
    row = _stride_row(0)
    with pytest.raises(Exception):  # noqa: B017 — dataclass(frozen=True) raises FrozenInstanceError
        row.numbers = (1, 2, 3, 4, 5)  # type: ignore[misc]
