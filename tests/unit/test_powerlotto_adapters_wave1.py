"""Focused contract tests for the pure POWER_LOTTO Wave 1 adapters."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.powerlotto_wave1 import (
    WAVE1_BLOCKED_STRATEGIES,
    WAVE1_STRATEGIES,
    P638HistoryRow,
    P638StrategySpec,
    coerce_p638_history,
)
from lottolab.strategies.powerlotto_second_zone import second_zone_predict

_EXPECTED_IDS = (
    "zonal_entropy_2bet",
    "cold_complement_2bet",
    "midfreq_fourier_2bet",
    "fourier30_markov30_2bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "power_precision_3bet",
    "pp3_freqort_4bet",
)
_EXPECTED_COUNTS = (2, 2, 2, 2, 3, 3, 3, 4)
_EXPECTED_MIN_HISTORY = (30, 10, 10, 30, 30, 10, 30, 30)


def _row(index: int) -> P638HistoryRow:
    numbers = tuple(sorted(((index * 7 + offset * 5) % 38) + 1 for offset in range(6)))
    assert len(set(numbers)) == 6
    return P638HistoryRow(
        draw=f"{index + 1:09d}",
        date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
        second_number=(index % 8) + 1,
    )


def _history(count: int) -> tuple[P638HistoryRow, ...]:
    return tuple(_row(index) for index in range(count))


def test_wave1_selection_metadata_is_ordered_and_provenanced() -> None:
    assert tuple(spec.strategy_id for spec in WAVE1_STRATEGIES) == _EXPECTED_IDS
    assert tuple(spec.native_ticket_count for spec in WAVE1_STRATEGIES) == _EXPECTED_COUNTS
    assert tuple(spec.min_history for spec in WAVE1_STRATEGIES) == _EXPECTED_MIN_HISTORY
    assert all(spec.source_paths and spec.provenance for spec in WAVE1_STRATEGIES)
    assert tuple(item.strategy_id for item in WAVE1_BLOCKED_STRATEGIES) == (
        "power_orthogonal_5bet",
    )


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_outputs_have_native_shape_and_are_repeatable(spec: P638StrategySpec) -> None:
    strategy = spec
    history = _history(500)

    first = strategy.predict_tickets(history, LotteryType.POWER_LOTTO)
    second = strategy.get_bets(history, LotteryType.POWER_LOTTO)

    assert first == second
    assert len(first) == strategy.native_ticket_count
    for ticket in first:
        assert type(ticket) is tuple
        assert len(ticket) == 2
        first_zone, second_zone = ticket
        assert first_zone == tuple(sorted(first_zone))
        assert len(set(first_zone)) == 6
        assert all(type(number) is int and 1 <= number <= 38 for number in first_zone)
        assert type(second_zone) is int and 1 <= second_zone <= 8
    assert {ticket[1] for ticket in first} == {
        second_zone_predict([{"special": row.second_number} for row in history])
    }


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_accepts_documented_mapping_coercion(spec: P638StrategySpec) -> None:
    history = _history(120)
    mapped: list[Mapping[str, object]] = [
        {
            "draw": row.draw,
            "date": row.date,
            "numbers": list(reversed(row.numbers)),
            "special": row.second_number,
            "lottery_type": "POWER_LOTTO",
        }
        for row in history
    ]

    typed = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    coerced = spec.predict_tickets(mapped, LotteryType.POWER_LOTTO)
    assert coerced == typed


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_rejects_non_power_lotto_context(spec: P638StrategySpec) -> None:
    with pytest.raises(UnsupportedLotteryType):
        spec.predict_tickets(_history(500), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_enforces_strategy_minimum_history(spec: P638StrategySpec) -> None:
    minimum = spec.min_history
    with pytest.raises(InsufficientHistory):
        spec.predict_tickets(_history(max(0, minimum - 1)), LotteryType.POWER_LOTTO)


def test_coerce_history_is_immutable_and_fail_closed() -> None:
    row = _row(0)
    coerced = coerce_p638_history(
        [
            {
                "draw_number": 1,
                "draw_date": row.date,
                "main_numbers": list(row.numbers),
                "special": row.second_number,
            }
        ]
    )
    assert coerced == (
        P638HistoryRow(
            draw="1",
            date=row.date,
            numbers=row.numbers,
            second_number=row.second_number,
        ),
    )

    with pytest.raises(InvalidOutput):
        coerce_p638_history(
            [
                {
                    "draw": "1",
                    "date": row.date,
                    "numbers": [1, 1, 2, 3, 4, 5],
                    "special": row.second_number,
                }
            ]
        )

    with pytest.raises(UnsupportedLotteryType):
        coerce_p638_history(
            [
                {
                    "draw": "1",
                    "date": row.date,
                    "numbers": list(row.numbers),
                    "special": row.second_number,
                    "lottery_type": "BIG_LOTTO",
                }
            ]
        )
