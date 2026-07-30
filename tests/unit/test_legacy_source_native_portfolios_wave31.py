"""Unit contracts for the thirty-first frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave31 import (
    RADICAL_BACKTEST_METHOD_ID,
    RADICAL_PREDICT_METHOD_ID,
    LegacySourceNativeWave31Error,
    LegacySourceNativeWave31Request,
    generate_legacy_source_native_wave31_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    rows: list[LegacyHistoryDraw] = []
    for index in range(count):
        values = sorted(
            ((index * 7 + offset * 5) % 49) + 1
            for offset in range(6)
        )
        rows.append(
            LegacyHistoryDraw(
                draw_number=str(index + 1),
                numbers=(
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                ),
            )
        )
    return tuple(rows)


def _generate(method_id: str, history_count: int = 200):
    return generate_legacy_source_native_wave31_portfolio(
        LegacySourceNativeWave31Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave31_preserves_live_radical_gap_and_low_sum_shift() -> None:
    result = _generate(RADICAL_PREDICT_METHOD_ID)

    assert result.tickets == ((24, 29, 31, 34, 38, 39),)
    assert result.metadata.candidate_pools == (
        (24, 31, 38, 29, 34, 39, 44, 49, 45),
    )
    assert result.metadata.gap_exclusion_ranges == ((1, 19),)
    assert result.metadata.hardcoded_excluded_draw_numbers == (
        "115000007",
    )
    assert result.metadata.candidate_k is None
    assert result.metadata.source_method_combination_count == 3


def test_wave31_preserves_backtest_gap_ticket_order_and_window() -> None:
    result = _generate(RADICAL_BACKTEST_METHOD_ID)

    assert result.tickets == (
        (24, 29, 34, 39, 44, 49),
        (10, 11, 12, 14, 16, 17),
    )
    assert result.metadata.gap_exclusion_ranges == (
        (1, 19),
        (20, 29),
    )
    assert result.metadata.native_ticket_order == (
        "GAP_01_19_THEN_GAP_20_29"
    )
    assert result.metadata.source_history_limit == 300
    assert result.metadata.source_history_first_draw_number == "200"
    assert result.metadata.source_history_last_draw_number == "1"
    assert result.metadata.source_method_combination_count == 2


def test_wave31_rejects_insufficient_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave31Error):
        _generate(RADICAL_BACKTEST_METHOD_ID, history_count=49)
    with pytest.raises(LegacySourceNativeWave31Error):
        generate_legacy_source_native_wave31_portfolio(
            LegacySourceNativeWave31Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
