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

import lottolab.strategies.adapters.biglotto_selected as biglotto_selected_module
from lottolab.domain.draws import LotteryType
from lottolab.strategies import adapters as public_adapters
from lottolab.strategies.adapters import (
    BetAdapter,
    BigLottoDeviation2BetAdapter,
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
    _deviation_complement_2bet,
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
        "BigLottoDeviation2BetAdapter",
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


def test_social_secondary_number_tie_break_is_load_bearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The boundary fixture above ties on score, but `range(1, 50)` already
    enumerates candidates ascending and Python's sort is stable, so a mutant
    that drops the explicit ``number`` tie-break can still pass it by
    accident. Reverse the candidate enumeration for the ranking call only
    (not the score-table call inside ``_unpopular_scores``) so the correct
    code must lean on the explicit tie-break to still get the right answer.
    """

    call_count = {"n": 0}
    real_range = range

    def reordering_range(*args: int) -> object:
        call_count["n"] += 1
        sequence = real_range(*args)
        if call_count["n"] == 1:
            # First call: _unpopular_scores() building its score table. This
            # must stay ascending or the number<->score correspondence breaks.
            return sequence
        # Second call: the candidate enumeration inside _social_wisdom_prediction's
        # sorted(...). Reversing it defeats "stable sort of already-sorted input".
        return tuple(reversed(sequence))

    monkeypatch.setattr(biglotto_selected_module, "range", reordering_range, raising=False)

    boundary_candidates = (32, 33, 34, 35, 37, 39, 41)
    history = tuple(
        _row(
            draw=f"equal-{excluded}",
            date=f"equal-{excluded}",
            numbers=tuple(number for number in boundary_candidates if number != excluded),
        )
        for excluded in boundary_candidates
    )

    result = _social_wisdom_prediction(history)

    assert call_count["n"] == 2
    assert result == (32, 33, 34, 35, 37, 39)
    assert 41 not in result

    # Mutation-sensitivity proof: recompute the ranking with the same reversed
    # candidate order but the mutant key (-score,) with no secondary tie-break.
    # A stable sort over the reversed order now preserves that reversed order
    # among the tied candidates, selecting the *largest* six instead.
    unpopular = _unpopular_scores()
    historical = _historical_frequency(history)
    combined = tuple(
        _UNPOPULAR_BLEND * u + _HISTORICAL_BLEND * h
        for u, h in zip(unpopular, historical, strict=True)
    )
    mutant_candidates = tuple(reversed(real_range(1, 50)))
    mutant_ranked = sorted(mutant_candidates, key=lambda number: -combined[number - 1])
    mutant_result = tuple(sorted(mutant_ranked[:6]))
    assert mutant_result != result
    assert 41 in mutant_result
    assert 32 not in mutant_result


BLEND_BOUNDARY_HISTORY = (
    _row("blend-1", "blend-1", (2, 3, 4, 5, 32, 42)),
    _row("blend-2", "blend-2", (11, 12, 13, 14, 15, 43)),
    _row("blend-3", "blend-3", (17, 19, 21, 22, 23, 44)),
    _row("blend-4", "blend-4", (24, 25, 27, 29, 31, 45)),
    _row("blend-5", "blend-5", (6, 7, 8, 9, 16, 47)),
)


def test_social_blend_use_site_operand_swap_flips_sixth_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """42-45 and 47 are the only zero-history members of the top unpopularity
    tier once they're the only ones with any historical mention, so they're
    safely top-5 under either blend. 49 (also top-tier, zero history) and 32
    (a lower tier boosted by one historical mention) are engineered to swap
    which of them takes the sixth slot depending on which blend weight lands
    on which term."""

    assert _UNPOPULAR_BLEND == 0.7
    assert _HISTORICAL_BLEND == 0.3

    correct_result = _social_wisdom_prediction(BLEND_BOUNDARY_HISTORY)
    assert correct_result == (42, 43, 44, 45, 47, 49)
    assert 32 not in correct_result

    unpopular = _unpopular_scores()
    historical = _historical_frequency(BLEND_BOUNDARY_HISTORY)
    score_49_correct = 0.7 * unpopular[48] + 0.3 * historical[48]
    score_32_correct = 0.7 * unpopular[31] + 0.3 * historical[31]
    assert score_49_correct > score_32_correct

    # Simulate the use-site operand swap by monkeypatching the constants to
    # their swapped *values*: `_UNPOPULAR_BLEND * u + _HISTORICAL_BLEND * h`
    # with (0.3, 0.7) computes the identical formula as swapping which
    # constant multiplies which variable while leaving the values at
    # (0.7, 0.3) — without ever touching production source.
    monkeypatch.setattr(biglotto_selected_module, "_UNPOPULAR_BLEND", 0.3)
    monkeypatch.setattr(biglotto_selected_module, "_HISTORICAL_BLEND", 0.7)

    swapped_result = _social_wisdom_prediction(BLEND_BOUNDARY_HISTORY)
    assert swapped_result != correct_result
    assert swapped_result == (32, 42, 43, 44, 45, 47)
    assert 49 not in swapped_result

    score_49_swapped = 0.3 * unpopular[48] + 0.7 * historical[48]
    score_32_swapped = 0.3 * unpopular[31] + 0.7 * historical[31]
    assert score_32_swapped > score_49_swapped


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


def test_social_51_entries_excludes_oldest_boundary_row_via_get_one_bet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exactly 51 rows: the oldest one is deliberately malformed. Correct
    ``history[-50:]`` windowing drops it before row validation ever sees it;
    an off-by-one (or missing) window pulls it into validation and fails
    closed. Goes through ``get_one_bet`` itself, not just the frequency
    helper, since the window is applied by the adapter before validation."""

    malformed_oldest_entry = cast(CausalDrawRow, {"excluded": "oldest-boundary"})
    valid_50 = tuple(
        _row(
            draw=f"latest-{index}",
            date=f"latest-{index}",
            numbers=(32, 33, 34, 35, 41, 49),
        )
        for index in range(50)
    )
    history = (malformed_oldest_entry, *valid_50)
    assert len(history) == 51
    assert len(valid_50) == 50

    adapter = BigLottoSocialWisdomAntiPopularityAdapter()
    result = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
    assert result == ((32, 33, 34, 35, 41, 49), None)

    # Mutation-sensitivity proof: history[-50:] mutated to history[-51:], or
    # to no windowing at all, pulls the malformed oldest row into validation.
    def off_by_one_window(
        self: BigLottoSocialWisdomAntiPopularityAdapter,
        raw_history: tuple[object, ...],
    ) -> tuple[object, ...]:
        return raw_history[-51:]

    def no_window(
        self: BigLottoSocialWisdomAntiPopularityAdapter,
        raw_history: tuple[object, ...],
    ) -> tuple[object, ...]:
        return raw_history

    for mutant_window in (off_by_one_window, no_window):
        monkeypatch.setattr(
            BigLottoSocialWisdomAntiPopularityAdapter,
            "_history_window",
            mutant_window,
        )
        with pytest.raises(InvalidOutput):
            adapter.get_one_bet(history, LotteryType.BIG_LOTTO)


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


# ─── biglotto_deviation_2bet (P603A) ──────────────────────────────────────────
#
# Frozen donor semantics from tools/predict_biglotto_deviation_2bet.py and
# lottery_api/models/replay_strategy_registry.py::_BigLottoDeviation2BetAdapter
# at 520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f: window=50 recent-history slice,
# expected = total*6/49, hot dev>1 / cold dev<-1 (both strict), descending
# deviation with donor-stable (ascending number) ties, hot fallback pads by
# nearest-expected-frequency, cold fallback pads by ascending unused number,
# and the registry adapter exposes only the first (hot) of the two donor bets.

DEVIATION_OUTSIDE_WINDOW_NUMBERS = (1, 2, 3, 4, 5, 6)
DEVIATION_INSIDE_WINDOW_NUMBERS = (10, 20, 30, 40, 41, 42)


def _deviation_row(index: int, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(draw=f"dev-{index}", date=f"dev-{index}", numbers=numbers)


def _deviation_history(
    outside_window: tuple[int, ...] = DEVIATION_OUTSIDE_WINDOW_NUMBERS,
    inside_window: tuple[int, ...] = DEVIATION_INSIDE_WINDOW_NUMBERS,
) -> tuple[CausalDrawRow, ...]:
    return tuple(_deviation_row(index, outside_window) for index in range(50)) + tuple(
        _deviation_row(50 + index, inside_window) for index in range(50)
    )


def _counts_history(counts: dict[int, int], total_rows: int) -> tuple[CausalDrawRow, ...]:
    """Build a synthetic history realizing an exact per-number occurrence count.

    Greedily assigns, for each row, the six numbers with the largest
    remaining budget (ties broken ascending) until every budget is
    exhausted. A number absent from ``counts`` implicitly gets zero.
    """
    remaining = dict(counts)
    rows: list[CausalDrawRow] = []
    for index in range(total_rows):
        chosen = sorted(remaining, key=lambda n: (-remaining[n], n))[:6]
        for number in chosen:
            remaining[number] -= 1
        rows.append(_deviation_row(index, tuple(sorted(chosen))))
    assert all(count == 0 for count in remaining.values())
    return tuple(rows)


def test_deviation_golden_windowing_and_first_bet_extraction() -> None:
    """100 rows: the oldest 50 hold one number set, the newest 50 hold
    another. Only the newest 50 (the window) may influence the result, and
    ``get_one_bet`` must expose only the hot bet, matching the donor
    registry's first-bet extraction from ``[bet1_hot, bet2_cold]``."""
    history = _deviation_history()
    hot, cold = _deviation_complement_2bet(history)
    assert hot == DEVIATION_INSIDE_WINDOW_NUMBERS
    assert cold == DEVIATION_OUTSIDE_WINDOW_NUMBERS
    assert BigLottoDeviation2BetAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    ) == (DEVIATION_INSIDE_WINDOW_NUMBERS, None)


def test_deviation_50_vs_51_rows_boundary_is_mutation_sensitive() -> None:
    """``history[-window:] if len(history) > window else history``: exactly
    50 rows must use all of them; 51 rows must drop the oldest one. An extra
    oldest row with a distinct number set changes the result only if it is
    wrongly counted, proving the boundary is load-bearing."""
    window_rows = tuple(_deviation_row(index, (7, 8, 9, 10, 11, 12)) for index in range(50))
    extra_row = _deviation_row(-1, (1, 2, 3, 4, 5, 6))

    history_50 = window_rows
    history_51 = (extra_row, *window_rows)

    result_50 = _deviation_complement_2bet(history_50)
    result_51_correct = _deviation_complement_2bet(history_51)
    assert result_50 == result_51_correct == ((7, 8, 9, 10, 11, 12), (1, 2, 3, 4, 5, 6))

    # Mutation-sensitivity proof: an off-by-one window (51 instead of 50)
    # wrongly counts the extra row and changes the cold bet.
    result_51_wrong_window = _deviation_complement_2bet(history_51, window=51)
    assert result_51_wrong_window != result_51_correct
    assert result_51_wrong_window == ((7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18))


def test_deviation_strict_thresholds_exclude_exact_boundary() -> None:
    """window=49 makes expected exactly 6. Number 2 sits at dev=+1 (the hot
    boundary) and number 3 at dev=-1 (the cold boundary) — neither strict
    inequality is satisfied, so both must be excluded despite six genuine
    hot and six genuine cold candidates existing at more extreme deviations."""
    counts = {2: 7, 3: 5}
    for number in (10, 11, 12, 13, 14, 15):
        counts[number] = 8  # dev=+2, genuinely hot
    for number in (20, 21, 22, 23, 24, 25):
        counts[number] = 4  # dev=-2, genuinely cold
    for number in range(1, 50):
        counts.setdefault(number, 6)  # dev=0, neutral filler

    history = _counts_history(counts, total_rows=49)
    hot, cold = _deviation_complement_2bet(history, window=49)

    assert hot == (10, 11, 12, 13, 14, 15)
    assert 2 not in hot
    assert cold == (20, 21, 22, 23, 24, 25)
    assert 3 not in cold


def test_deviation_selects_top_six_by_descending_deviation() -> None:
    """Eight numbers all exceed the hot threshold at distinct deviations;
    only the top six by deviation may be selected, not merely any six."""
    counts = {1: 15, 2: 14, 3: 13, 4: 12, 5: 11, 6: 10, 7: 9, 8: 8}
    remaining_numbers = tuple(range(9, 50))
    budget = 294 - sum(counts.values())
    base, extra = divmod(budget, len(remaining_numbers))
    for index, number in enumerate(remaining_numbers):
        counts[number] = base + (1 if index < extra else 0)

    history = _counts_history(counts, total_rows=49)
    hot, _cold = _deviation_complement_2bet(history, window=49)

    assert hot == (1, 2, 3, 4, 5, 6)
    assert 7 not in hot
    assert 8 not in hot


def test_deviation_hot_fallback_uses_nearest_expected_not_ascending_order() -> None:
    """Only one number clears the hot threshold; the other five bet-one
    slots must be filled by nearest-to-expected frequency. Numbers 45-49 sit
    at the expected frequency while the smallest-numbered alternatives sit
    far from it — an ascending-order fallback would wrongly prefer those."""
    counts = {40: 8}
    for number in (45, 46, 47, 48, 49):
        counts[number] = 6  # dev≈-0.12, nearest to expected
    others = tuple(number for number in range(1, 50) if number not in counts)
    for index, number in enumerate(others):
        counts[number] = 7 if index < 30 else 4  # never exactly 6, never the nearest

    history = _counts_history(counts, total_rows=50)
    hot, _cold = _deviation_complement_2bet(history)

    assert hot == (40, 45, 46, 47, 48, 49)
    assert not any(number in hot for number in (1, 2, 3, 4, 5))


def test_deviation_cold_fallback_uses_ascending_unused_not_nearest_expected() -> None:
    """Mirrors the hot-fallback test above but for bet two: only one number
    clears the cold threshold, so the other five bet-two slots must be
    filled by ascending unused number, not nearest-to-expected frequency.
    Numbers 1-10 sit one count below expected (dev=-1, the cold boundary,
    correctly excluded from ``cold`` itself) — a nearest-frequency fallback
    would wrongly prefer them, and the dev=0 filler numbers 11-15 even more
    so, ahead of the correct ascending-unused numbers 1-5."""
    counts: dict[int, int] = {}
    for number in range(40, 46):
        counts[number] = 8  # dev=+2, hot
    counts[30] = 4  # dev=-2, the only genuine cold candidate
    for number in range(1, 11):
        counts[number] = 5  # dev=-1, the cold boundary (excluded, not cold)
    for number in range(1, 50):
        counts.setdefault(number, 6)  # dev=0, neutral filler

    assert sum(counts.values()) == 49 * 6

    history = _counts_history(counts, total_rows=49)
    hot, cold = _deviation_complement_2bet(history, window=49)

    assert hot == (40, 41, 42, 43, 44, 45)
    assert cold == (1, 2, 3, 4, 5, 30)
    assert not any(number in cold for number in (11, 12, 13, 14, 15))


def test_deviation_minimum_history_gate_is_explicit() -> None:
    history_99 = tuple(_deviation_row(index, (1, 2, 3, 4, 5, 6)) for index in range(99))
    history_100 = tuple(_deviation_row(index, (1, 2, 3, 4, 5, 6)) for index in range(100))

    with pytest.raises(InsufficientHistory):
        BigLottoDeviation2BetAdapter().get_one_bet(history_99, LotteryType.BIG_LOTTO)

    assert BigLottoDeviation2BetAdapter().get_one_bet(
        history_100, LotteryType.BIG_LOTTO
    ) == ((1, 2, 3, 4, 5, 6), None)


def test_deviation_wrong_lottery_type_is_rejected() -> None:
    with pytest.raises(UnsupportedLotteryType):
        BigLottoDeviation2BetAdapter().get_one_bet(None, LotteryType.POWER_LOTTO)


def test_deviation_validates_full_history_before_window_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """100 rows exactly meet min_history=100. The oldest row is malformed
    and sits outside the last-50-row window ``_deviation_complement_2bet``
    slices for its own calculation. This adapter does not override
    ``_history_window`` (unlike the Social adapter), so base-class
    validation covers the full supplied history before any windowing —
    the malformed row is caught even though it never reaches the internal
    50-row calculation.
    """
    malformed_oldest = cast(CausalDrawRow, {"excluded": "oldest-outside-window"})
    valid_99 = tuple(_deviation_row(index, (1, 2, 3, 4, 5, 6)) for index in range(99))
    history = (malformed_oldest, *valid_99)
    assert len(history) == 100

    with pytest.raises(InvalidOutput):
        BigLottoDeviation2BetAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)

    # Mutation-sensitivity proof: if the adapter validated only its
    # calculation window — mirroring the Social adapter's real
    # `_history_window` override — the malformed row (outside that window)
    # would be sliced away before validation ever saw it. Because the
    # calculation window (50) is smaller than min_history (100), this
    # specific mutant cannot silently succeed instead: it necessarily
    # surfaces as a *different* failure, InsufficientHistory, proving the
    # malformed row is no longer what the adapter rejects.
    def window_before_validation(
        self: BigLottoDeviation2BetAdapter,
        raw_history: tuple[object, ...],
    ) -> tuple[object, ...]:
        return raw_history[-50:]

    monkeypatch.setattr(
        BigLottoDeviation2BetAdapter,
        "_history_window",
        window_before_validation,
    )
    with pytest.raises(InsufficientHistory):
        BigLottoDeviation2BetAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)


def test_deviation_input_is_immutable_and_never_modified() -> None:
    history = _deviation_history()
    before = history
    BigLottoDeviation2BetAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert history == before
    with pytest.raises(FrozenInstanceError):
        history[0].draw = "changed"  # pyright: ignore[reportAttributeAccessIssue]


def test_deviation_preserves_global_random_state() -> None:
    before = random.getstate()
    _deviation_complement_2bet(_deviation_history())
    assert random.getstate() == before


def test_deviation_cross_instance_equality() -> None:
    history = _deviation_history()
    first = BigLottoDeviation2BetAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    second = BigLottoDeviation2BetAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_deviation_execution_needs_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _deviation_history()
    assert BigLottoDeviation2BetAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    ) == (DEVIATION_INSIDE_WINDOW_NUMBERS, None)
