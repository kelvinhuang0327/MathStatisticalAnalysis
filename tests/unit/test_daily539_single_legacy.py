from __future__ import annotations

import math
from collections import Counter
from typing import Protocol

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_single_legacy import (
<<<<<<< HEAD
    Daily539Acb1BetAdapter,
=======
>>>>>>> codex/t539-all-strategies-migration-backtest-wave1-r1
    Daily539AcbSingleAdapter,
    Daily539Markov1BetAdapter,
)

_POOL = 39
_PICK = 5


class SingleAdapter(Protocol):
    strategy_id: str
    strategy_version: str

    def get_one_bet(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]: ...


def _row(index: int, offset: int = 0) -> CausalDrawRow:
    numbers = tuple(sorted(((offset + index + step * 7) % _POOL) + 1 for step in range(_PICK)))
    return CausalDrawRow(
        draw=f"d-{index}-{offset}", date=f"2020-01-{(index % 28) + 1:02d}", numbers=numbers
    )


def _history(count: int = 140, offset: int = 0) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(index, offset) for index in range(count))


def _markov_oracle(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-30:]
    transition = [[0.0] * _POOL for _ in range(_POOL)]
    for index in range(len(recent) - 1):
        for current in recent[index].numbers:
            for following in recent[index + 1].numbers:
                transition[current - 1][following - 1] += 1.0
    for row in transition:
        row_sum = sum(row)
        if row_sum:
            for column in range(_POOL):
                row[column] /= row_sum
    scores = [0.0] * _POOL
    for current in recent[-1].numbers:
        for column, value in enumerate(transition[current - 1]):
            scores[column] += value
    ranked = sorted(range(_POOL), key=lambda index: (-scores[index], index))
    return tuple(sorted(index + 1 for index in ranked[:_PICK]))


def _acb_oracle(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    recent = history[-100:]
    width = len(recent)
    expected = width * _PICK / _POOL
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    last_seen: dict[int, int] = {}
    for index, row in enumerate(recent):
        for number in row.numbers:
            last_seen[number] = index
    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        deficit = (expected - frequency.get(number, 0)) / max(expected, 1.0)
        gap = (width - 1 - last_seen.get(number, -1)) / width
        boundary = 1.2 if number <= 5 or number >= 35 else 1.0
        mod3 = 1.1 if number % 3 == 0 else 1.0
        scores[number] = (deficit * 0.4 + gap * 0.6) * boundary * mod3
    ranked = sorted(range(1, _POOL + 1), key=lambda number: -scores[number])
    selected = list(ranked[:_PICK])

    def zone(number: int) -> int:
        return 1 if number <= 13 else 2 if number <= 26 else 3

    present = {zone(number) for number in selected}
    if len(present) < 2:
        counts = Counter(zone(number) for number in selected)
        dominant = max(counts, key=lambda zone_id: counts[zone_id])
        for missing in (1, 2, 3):
            if missing in present:
                continue
            candidates = [
                number for number in ranked if zone(number) == missing and number not in selected
            ]
            dominant_numbers = [number for number in selected if zone(number) == dominant]
            if candidates and dominant_numbers:
                remove = min(dominant_numbers, key=lambda number: scores[number])
                selected = [number for number in selected if number != remove]
                selected.append(candidates[0])
                break
    return tuple(sorted(selected[:_PICK]))


def test_markov_identity_and_donor_parity() -> None:
    history = _history()
    adapter = Daily539Markov1BetAdapter()
    assert adapter.strategy_id == "markov_1bet_539"
    assert adapter.strategy_version == "v0.1-p36"
    assert adapter.get_one_bet(history, LotteryType.DAILY_539) == (_markov_oracle(history), None)


def test_acb_identity_and_donor_parity() -> None:
    history = _history()
    adapter = Daily539AcbSingleAdapter()
    assert adapter.strategy_id == "acb_single_539"
    assert adapter.strategy_version == "v0.1-p36"
    assert adapter.get_one_bet(history, LotteryType.DAILY_539) == (_acb_oracle(history), None)


<<<<<<< HEAD
def test_acb_1bet_alias_identity_and_donor_version() -> None:
    adapter = Daily539Acb1BetAdapter()
    assert adapter.strategy_id == "acb_1bet"
    # Proven from the P31A donor's own executable adapter (Acb1BetAdapter in
    # p31a_wave1_retired_adapters.py), not assumed from acb_single_539's v0.1-p36
    # or the lifecycle-registry stub's placeholder v0.0.
    assert adapter.strategy_version == "v0.1-p31a"
    assert adapter.min_history == 100
    assert adapter.native_ticket_count == 1


def test_acb_1bet_alias_matches_acb_single_539_on_every_target() -> None:
    for offset in range(5):
        history = _history(140, offset)
        alias = Daily539Acb1BetAdapter().get_one_bet(history, LotteryType.DAILY_539)
        single = Daily539AcbSingleAdapter().get_one_bet(history, LotteryType.DAILY_539)
        assert alias == single == (_acb_oracle(history), None)


@pytest.mark.parametrize(
    "adapter", [Daily539Markov1BetAdapter(), Daily539AcbSingleAdapter(), Daily539Acb1BetAdapter()]
)
=======
@pytest.mark.parametrize("adapter", [Daily539Markov1BetAdapter(), Daily539AcbSingleAdapter()])
>>>>>>> codex/t539-all-strategies-migration-backtest-wave1-r1
def test_single_adapters_are_deterministic_and_causal(adapter: SingleAdapter) -> None:
    history = _history()
    get_one_bet = adapter.get_one_bet
    first = get_one_bet(history, LotteryType.DAILY_539)
    second = get_one_bet(history, LotteryType.DAILY_539)
    assert first == second


def test_prefix_before_window_does_not_change_markov() -> None:
    tail = _history(30, 4)
    first = _history(80, 0) + tail
    second = _history(140, 17) + tail
    assert Daily539Markov1BetAdapter().get_one_bet(
        first, LotteryType.DAILY_539
    ) == Daily539Markov1BetAdapter().get_one_bet(second, LotteryType.DAILY_539)


def test_prefix_before_window_does_not_change_acb() -> None:
    tail = _history(100, 4)
    first = _history(20, 0) + tail
    second = _history(140, 17) + tail
    assert Daily539AcbSingleAdapter().get_one_bet(
        first, LotteryType.DAILY_539
    ) == Daily539AcbSingleAdapter().get_one_bet(second, LotteryType.DAILY_539)


@pytest.mark.parametrize(
    ("adapter", "minimum"),
<<<<<<< HEAD
    [
        (Daily539Markov1BetAdapter(), 30),
        (Daily539AcbSingleAdapter(), 100),
        (Daily539Acb1BetAdapter(), 100),
    ],
=======
    [(Daily539Markov1BetAdapter(), 30), (Daily539AcbSingleAdapter(), 100)],
>>>>>>> codex/t539-all-strategies-migration-backtest-wave1-r1
)
def test_minimum_history_boundary(adapter: SingleAdapter, minimum: int) -> None:
    get_one_bet = adapter.get_one_bet
    with pytest.raises(InsufficientHistory):
        get_one_bet(_history(minimum - 1), LotteryType.DAILY_539)
    numbers, special = get_one_bet(_history(minimum), LotteryType.DAILY_539)
    assert len(numbers) == _PICK
    assert special is None


<<<<<<< HEAD
@pytest.mark.parametrize(
    "adapter", [Daily539Markov1BetAdapter(), Daily539AcbSingleAdapter(), Daily539Acb1BetAdapter()]
)
=======
@pytest.mark.parametrize("adapter", [Daily539Markov1BetAdapter(), Daily539AcbSingleAdapter()])
>>>>>>> codex/t539-all-strategies-migration-backtest-wave1-r1
def test_wrong_lottery_and_malformed_history_fail_closed(adapter: SingleAdapter) -> None:
    get_one_bet = adapter.get_one_bet
    with pytest.raises(UnsupportedLotteryType):
        get_one_bet(_history(120), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        get_one_bet(list(_history(120)), LotteryType.DAILY_539)
    malformed = (*_history(120)[:-1], CausalDrawRow("bad", "2020-01-01", (1, 1, 2, 3, 4)))
    with pytest.raises(InvalidOutput):
        get_one_bet(malformed, LotteryType.DAILY_539)


def test_no_external_state_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"external access: {args} {kwargs}")

    monkeypatch.setattr("sqlite3.connect", fail)
    monkeypatch.setattr("socket.socket", fail)
    history = _history()
    assert Daily539Markov1BetAdapter().get_one_bet(history, LotteryType.DAILY_539)[1] is None
    assert Daily539AcbSingleAdapter().get_one_bet(history, LotteryType.DAILY_539)[1] is None
<<<<<<< HEAD
    assert Daily539Acb1BetAdapter().get_one_bet(history, LotteryType.DAILY_539)[1] is None
=======
>>>>>>> codex/t539-all-strategies-migration-backtest-wave1-r1


def test_no_nan_is_emitted() -> None:
    numbers, _ = Daily539AcbSingleAdapter().get_one_bet(_history(), LotteryType.DAILY_539)
    assert not any(math.isnan(float(number)) for number in numbers)
<<<<<<< HEAD
    alias_numbers, _ = Daily539Acb1BetAdapter().get_one_bet(_history(), LotteryType.DAILY_539)
    assert not any(math.isnan(float(number)) for number in alias_numbers)
=======
>>>>>>> codex/t539-all-strategies-migration-backtest-wave1-r1
