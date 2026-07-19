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
    _HISTORICAL_BLEND,
    _UNPOPULAR_BLEND,
    _historical_frequency,
    _social_wisdom_prediction,
    _unpopular_scores,
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


SOCIAL_NEAR_TIE_HISTORY = (
    CausalDrawRow("near-tie-01", "near-tie-01", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-02", "near-tie-02", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-03", "near-tie-03", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-04", "near-tie-04", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-05", "near-tie-05", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-06", "near-tie-06", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-07", "near-tie-07", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-08", "near-tie-08", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-09", "near-tie-09", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-10", "near-tie-10", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-11", "near-tie-11", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-12", "near-tie-12", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-13", "near-tie-13", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-14", "near-tie-14", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-15", "near-tie-15", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-16", "near-tie-16", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-17", "near-tie-17", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-18", "near-tie-18", (32, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-19", "near-tie-19", (1, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-20", "near-tie-20", (2, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-21", "near-tie-21", (3, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-22", "near-tie-22", (4, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-23", "near-tie-23", (5, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-24", "near-tie-24", (6, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-25", "near-tie-25", (7, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-26", "near-tie-26", (8, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-27", "near-tie-27", (9, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-28", "near-tie-28", (10, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-29", "near-tie-29", (11, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-30", "near-tie-30", (12, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-31", "near-tie-31", (13, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-32", "near-tie-32", (14, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-33", "near-tie-33", (15, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-34", "near-tie-34", (16, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-35", "near-tie-35", (17, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-36", "near-tie-36", (18, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-37", "near-tie-37", (19, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-38", "near-tie-38", (20, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-39", "near-tie-39", (21, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-40", "near-tie-40", (22, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-41", "near-tie-41", (23, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-42", "near-tie-42", (24, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-43", "near-tie-43", (25, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-44", "near-tie-44", (26, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-45", "near-tie-45", (27, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-46", "near-tie-46", (28, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-47", "near-tie-47", (29, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-48", "near-tie-48", (30, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-49", "near-tie-49", (31, 42, 43, 44, 45, 47)),
    CausalDrawRow("near-tie-50", "near-tie-50", (33, 42, 43, 44, 45, 47)),
)


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


def test_social_equal_score_boundary_uses_ascending_number_tie_break() -> None:
    boundary_candidates = (32, 33, 34, 35, 37, 39, 41)
    history = tuple(
        _row(
            draw=f"equal-{excluded}",
            date=f"equal-{excluded}",
            numbers=tuple(
                number for number in boundary_candidates if number != excluded
            ),
        )
        for excluded in boundary_candidates
    )

    result = BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
        history,
        LotteryType.BIG_LOTTO,
    )

    assert result == ((32, 33, 34, 35, 37, 39), None)
    assert 41 not in result[0]


def test_social_near_tie_freezes_float_scores_and_target_output() -> None:
    common = frozenset({42, 43, 44, 45, 47})
    low_frequency_candidates = tuple(
        next(iter(set(row.numbers) - common)) for row in SOCIAL_NEAR_TIE_HISTORY[18:]
    )
    assert len(SOCIAL_NEAR_TIE_HISTORY) == 50
    assert all(common.issubset(row.numbers) for row in SOCIAL_NEAR_TIE_HISTORY)
    assert sum(32 in row.numbers for row in SOCIAL_NEAR_TIE_HISTORY) == 18
    assert low_frequency_candidates == (*range(1, 32), 33)
    assert _UNPOPULAR_BLEND == 0.7
    assert _HISTORICAL_BLEND == 0.3

    unpopular = _unpopular_scores()
    historical = _historical_frequency(tuple(reversed(SOCIAL_NEAR_TIE_HISTORY)))
    score_32 = _UNPOPULAR_BLEND * unpopular[31] + _HISTORICAL_BLEND * historical[31]
    score_49 = _UNPOPULAR_BLEND * unpopular[48] + _HISTORICAL_BLEND * historical[48]
    assert score_32 == pytest.approx(0.04032617478205401, rel=0.0, abs=1e-15)
    assert score_49 == pytest.approx(0.040187114607697215, rel=0.0, abs=1e-15)
    assert score_32 - score_49 == pytest.approx(
        0.00013906017435679624,
        rel=0.0,
        abs=1e-15,
    )

    result = BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
        SOCIAL_NEAR_TIE_HISTORY,
        LotteryType.BIG_LOTTO,
    )
    assert result == ((32, 42, 43, 44, 45, 47), None)
    assert 49 not in result[0]


def test_social_oldest_first_input_selects_only_the_latest_50_rows() -> None:
    oldest_high_impact = tuple(
        _row(
            draw=f"oldest-high-{index}",
            date=f"oldest-high-{index}",
            numbers=(42, 43, 44, 45, 47, 49),
        )
        for index in range(50)
    )
    latest_low = tuple(
        _row(
            draw=f"latest-low-{index}",
            date=f"latest-low-{index}",
            numbers=(32, 33, 34, 35, 37, 39),
        )
        for index in range(50)
    )
    adapter = BigLottoSocialWisdomAntiPopularityAdapter()

    first_50_result = adapter.get_one_bet(oldest_high_impact, LotteryType.BIG_LOTTO)
    latest_50_result = adapter.get_one_bet(latest_low, LotteryType.BIG_LOTTO)
    high_rows_outside_window = adapter.get_one_bet(
        oldest_high_impact + latest_low,
        LotteryType.BIG_LOTTO,
    )
    high_rows_moved_into_window = adapter.get_one_bet(
        latest_low + oldest_high_impact,
        LotteryType.BIG_LOTTO,
    )

    assert first_50_result == ((42, 43, 44, 45, 47, 49), None)
    assert latest_50_result == ((32, 33, 34, 35, 37, 39), None)
    assert first_50_result != latest_50_result
    assert high_rows_outside_window == latest_50_result
    assert high_rows_moved_into_window == first_50_result


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
