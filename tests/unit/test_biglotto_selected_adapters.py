# pyright: reportPrivateUsage=false

"""Frozen donor goldens and target-native fail-closed adapter tests."""

from __future__ import annotations

import builtins
import json
import os
import random
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies import adapters as public_adapters
from lottolab.strategies.adapters import (
    BetAdapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_selected import (
    _social_wisdom_prediction,
    _zone_seed_digest,
    _zone_seed_preimage,
    _zone_split_bets,
    _zone_split_pools,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Frozen verbatim from donor test_p541d_r2_biglotto_selected_adapters.py at
# 520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f.
ZONE_HISTORY = [
    {
        "draw": "1",
        "date": "2026-01-01",
        "numbers": [1, 2, 3, 4, 5, 6],
    }
]
ZONE_PREIMAGE = (
    b'{"causal_history":[{"date":"2026-01-01","draw":"1",'
    b'"numbers":[1,2,3,4,5,6]}],"lottery_type":"BIG_LOTTO",'
    b'"strategy_id":"biglotto_zone_split_3bet_bet1"}'
)
ZONE_DIGEST = "8d1984bfcf997abb35fd4eaf53115c0afcbcfd7bb763dc9a1fd66dbe869872f3"
ZONE_BETS = [
    [4, 6, 11, 14, 15, 18],
    [15, 16, 17, 21, 26, 31],
    [38, 41, 42, 44, 48, 49],
]


def _zone_history() -> tuple[CausalDrawRow, ...]:
    frozen = ZONE_HISTORY[0]
    return (
        CausalDrawRow(
            draw=cast(str, frozen["draw"]),
            date=cast(str, frozen["date"]),
            numbers=tuple(cast(list[int], frozen["numbers"])),
        ),
    )


def _row(
    draw: str = "1",
    date: str = "2026-01-01",
    numbers: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
) -> CausalDrawRow:
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)


class _TwoHistoryAdapter(BetAdapter):
    strategy_id = "fixture_two_history"
    strategy_name = "Fixture Two History"
    strategy_version = "v0.1"
    min_history = 2
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return (1, 2, 3, 4, 5, 6)


class _InvalidOutputAdapter(BetAdapter):
    strategy_id = "fixture_invalid_output"
    strategy_name = "Fixture Invalid Output"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return (1, 2, 3)


class _UnsortedOutputAdapter(BetAdapter):
    strategy_id = "fixture_unsorted_output"
    strategy_name = "Fixture Unsorted Output"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return (6, 5, 4, 3, 2, 1)


ADAPTER_CLASSES = (
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
)


def test_public_adapter_exports_are_explicit() -> None:
    assert set(public_adapters.__all__) == {
        "BetAdapter",
        "BetAdapterError",
        "BigLottoSocialWisdomAntiPopularityAdapter",
        "BigLottoZoneSplit3BetBet1Adapter",
        "CausalDrawRow",
        "InsufficientHistory",
        "InvalidOutput",
        "RejectPrediction",
        "UnsupportedLotteryType",
    }


def test_zone_exact_preimage_digest_and_sequential_bets() -> None:
    history = _zone_history()
    assert _zone_seed_preimage(history) == ZONE_PREIMAGE
    assert _zone_seed_digest(history) == ZONE_DIGEST
    assert _zone_split_pools() == (
        tuple(range(1, 19)),
        tuple(range(15, 35)),
        tuple(range(31, 50)),
    )
    assert _zone_split_bets(history) == tuple(tuple(bet) for bet in ZONE_BETS)


def test_zone_adapter_returns_frozen_donor_bet_one() -> None:
    assert BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
        _zone_history(), LotteryType.BIG_LOTTO
    ) == ((4, 6, 11, 14, 15, 18), None)


def test_social_repeated_high_golden() -> None:
    causal_history = tuple(
        _row(
            draw=str(index),
            date=str(index),
            numbers=(32, 33, 34, 35, 41, 49),
        )
        for index in range(50)
    )
    assert BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
        causal_history, LotteryType.BIG_LOTTO
    ) == ((32, 33, 34, 35, 41, 49), None)


def test_social_empty_history_scorer_golden() -> None:
    assert _social_wisdom_prediction(()) == (42, 43, 44, 45, 47, 49)


def test_social_uses_only_latest_50_of_54_causal_rows() -> None:
    latest_50 = tuple(
        _row(
            draw=f"latest-{index}",
            date=f"latest-{index}",
            numbers=(32, 33, 34, 35, 41, 49),
        )
        for index in range(50)
    )
    oldest_a = tuple(
        _row(draw=f"old-a-{index}", date=f"old-a-{index}") for index in range(4)
    )
    oldest_b = tuple(
        _row(
            draw=f"old-b-{index}",
            date=f"old-b-{index}",
            numbers=(42, 43, 44, 45, 47, 49),
        )
        for index in range(4)
    )
    malformed_oldest = tuple(
        cast(CausalDrawRow, {"excluded": index}) for index in range(4)
    )
    adapter = BigLottoSocialWisdomAntiPopularityAdapter()
    first = adapter.get_one_bet(oldest_a + latest_50, LotteryType.BIG_LOTTO)
    second = adapter.get_one_bet(oldest_b + latest_50, LotteryType.BIG_LOTTO)
    malformed_excluded = adapter.get_one_bet(
        malformed_oldest + latest_50,
        LotteryType.BIG_LOTTO,
    )
    latest_only = adapter.get_one_bet(latest_50, LotteryType.BIG_LOTTO)
    assert first == second == malformed_excluded == latest_only
    assert latest_only == ((32, 33, 34, 35, 41, 49), None)


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_wrong_lottery_type_precedes_malformed_history(
    adapter_class: type[BetAdapter],
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_one_bet(None, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_empty_history_is_insufficient(adapter_class: type[BetAdapter]) -> None:
    with pytest.raises(InsufficientHistory):
        adapter_class().get_one_bet((), LotteryType.BIG_LOTTO)


def test_minimum_history_gate_is_explicit() -> None:
    with pytest.raises(InsufficientHistory):
        _TwoHistoryAdapter().get_one_bet((_row(),), LotteryType.BIG_LOTTO)


def test_row_validation_precedes_minimum_history() -> None:
    malformed = cast(CausalDrawRow, {"draw": "1"})
    with pytest.raises(InvalidOutput):
        _TwoHistoryAdapter().get_one_bet((malformed,), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize(
    "history",
    [
        [_row()],
        (_row(),),
    ],
    ids=["list-container", "valid-tuple-control"],
)
def test_history_requires_exact_tuple_without_coercion(history: object) -> None:
    adapter = BigLottoZoneSplit3BetBet1Adapter()
    if type(history) is tuple:
        typed_history = cast(tuple[CausalDrawRow, ...], history)
        assert adapter.get_one_bet(typed_history, LotteryType.BIG_LOTTO)[0] == tuple(
            ZONE_BETS[0]
        )
    else:
        with pytest.raises(InvalidOutput):
            adapter.get_one_bet(history, LotteryType.BIG_LOTTO)


@pytest.mark.parametrize(
    "malformed",
    [
        {"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 6]},
        ["1", "2026-01-01", [1, 2, 3, 4, 5, 6]],
    ],
    ids=["mapping-row", "list-row"],
)
@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_malformed_row_is_not_coerced(
    malformed: object,
    adapter_class: type[BetAdapter],
) -> None:
    with pytest.raises(InvalidOutput):
        adapter_class().get_one_bet(
            (cast(CausalDrawRow, malformed),),
            LotteryType.BIG_LOTTO,
        )


def test_numbers_container_requires_exact_tuple() -> None:
    malformed_numbers = cast(tuple[int, ...], [1, 2, 3, 4, 5, 6])
    with pytest.raises(InvalidOutput):
        BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
            (_row(numbers=malformed_numbers),), LotteryType.BIG_LOTTO
        )


@pytest.mark.parametrize(
    "bad_number",
    [True, "1", 1.0],
    ids=["bool", "numeric-string", "float"],
)
def test_historical_numbers_reject_non_exact_integers(bad_number: object) -> None:
    malformed_numbers = cast(tuple[int, ...], (bad_number, 2, 3, 4, 5, 6))
    with pytest.raises(InvalidOutput):
        BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
            (_row(numbers=malformed_numbers),), LotteryType.BIG_LOTTO
        )


@pytest.mark.parametrize(
    "numbers",
    [
        (1, 1, 2, 3, 4, 5),
        (0, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 50),
    ],
    ids=["duplicate", "below-range", "above-range"],
)
def test_history_rejects_duplicates_and_range_errors(numbers: tuple[int, ...]) -> None:
    with pytest.raises(InvalidOutput):
        BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
            (_row(numbers=numbers),), LotteryType.BIG_LOTTO
        )


def test_invalid_adapter_output_is_rejected_and_valid_output_is_canonicalized() -> None:
    with pytest.raises(InvalidOutput):
        _InvalidOutputAdapter().get_one_bet((_row(),), LotteryType.BIG_LOTTO)
    assert _UnsortedOutputAdapter().get_one_bet(
        (_row(),), LotteryType.BIG_LOTTO
    ) == ((1, 2, 3, 4, 5, 6), None)


def test_input_is_immutable_and_never_modified() -> None:
    history = _zone_history()
    before = history
    BigLottoZoneSplit3BetBet1Adapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert history == before
    with pytest.raises(FrozenInstanceError):
        history[0].draw = "changed"  # pyright: ignore[reportAttributeAccessIssue]


def test_zone_preserves_global_random_state() -> None:
    before = random.getstate()
    _zone_split_bets(_zone_history())
    assert random.getstate() == before


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_cross_instance_equality(adapter_class: type[BetAdapter]) -> None:
    history = _zone_history()
    first = adapter_class().get_one_bet(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import json
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import (
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
    CausalDrawRow,
)
zone = (CausalDrawRow("1", "2026-01-01", (1, 2, 3, 4, 5, 6)),)
social = tuple(CausalDrawRow(str(i), str(i), (32, 33, 34, 35, 41, 49)) for i in range(50))
result = {
    "zone": BigLottoZoneSplit3BetBet1Adapter().get_one_bet(zone, LotteryType.BIG_LOTTO),
    "social": BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
        social, LotteryType.BIG_LOTTO
    ),
}
print(json.dumps(result, sort_keys=True))
"""
    outputs: list[str] = []
    for hash_seed in ("1", "9173"):
        environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0]) == {
        "social": [[32, 33, 34, 35, 41, 49], None],
        "zone": [[4, 6, 11, 14, 15, 18], None],
    }


def test_adapter_execution_needs_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    assert BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
        _zone_history(), LotteryType.BIG_LOTTO
    ) == ((4, 6, 11, 14, 15, 18), None)
