"""Unit contracts for the twenty-eighth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave28 import (
    ELITE_SEVEN_METHOD_ID,
    SEVEN_BET_METHOD_ID,
    TWO_BET_METHOD_ID,
    LegacySourceNativeWave28Error,
    LegacySourceNativeWave28Request,
    generate_legacy_source_native_wave28_portfolio,
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


def _generate(method_id: str, history_count: int = 50):
    return generate_legacy_source_native_wave28_portfolio(
        LegacySourceNativeWave28Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave28_preserves_all_three_native_ticket_mappings() -> None:
    expected = {
        TWO_BET_METHOD_ID: (
            (3, 10, 17, 31, 33, 38),
            (11, 13, 18, 23, 28, 45),
        ),
        SEVEN_BET_METHOD_ID: (
            (3, 10, 17, 31, 33, 38),
            (11, 13, 31, 33, 38, 45),
            (11, 13, 18, 23, 28, 45),
            (16, 18, 21, 23, 28, 43),
            (1, 6, 16, 21, 43, 49),
            (1, 6, 24, 30, 44, 49),
            (2, 4, 5, 7, 8, 24),
        ),
        ELITE_SEVEN_METHOD_ID: (
            (8, 13, 18, 23, 28, 33),
            (8, 13, 18, 23, 28, 33),
            (3, 10, 17, 31, 38, 45),
            (3, 10, 17, 31, 38, 45),
            (5, 11, 16, 21, 43, 49),
            (5, 11, 16, 21, 43, 49),
            (8, 13, 18, 23, 28, 33),
        ),
    }
    results = {
        method_id: _generate(method_id) for method_id in expected
    }

    assert {
        method_id: result.tickets
        for method_id, result in results.items()
    } == expected
    assert results[TWO_BET_METHOD_ID].metadata.candidate_pool_size == 20
    assert results[SEVEN_BET_METHOD_ID].metadata.candidate_pool_size == 26
    assert results[ELITE_SEVEN_METHOD_ID].metadata.candidate_pool_size is None
    assert (
        results[ELITE_SEVEN_METHOD_ID].metadata.native_duplicate_ticket_count
        == 4
    )
    assert results[SEVEN_BET_METHOD_ID].metadata.native_ticket_count == 7


def test_wave28_preserves_database_newest_first_source_order() -> None:
    result = _generate(TWO_BET_METHOD_ID)

    assert result.metadata.history_first_draw_number == "1"
    assert result.metadata.history_cutoff_draw_number == "50"
    assert result.metadata.source_history_first_draw_number == "50"
    assert result.metadata.source_history_last_draw_number == "1"
    assert result.metadata.source_history_order == "RECENT_FIRST"
    assert result.metadata.source_history_order_detail == (
        "DATABASE_GET_ALL_DRAWS_ORDER_BY_INTEGER_DRAW_DESC_NEWEST_FIRST"
    )


def test_wave28_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave28Error):
        generate_legacy_source_native_wave28_portfolio(
            LegacySourceNativeWave28Request(
                legacy_method_id=TWO_BET_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave28Error):
        generate_legacy_source_native_wave28_portfolio(
            LegacySourceNativeWave28Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
