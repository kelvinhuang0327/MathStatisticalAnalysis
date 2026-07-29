"""Unit contracts for the twenty-ninth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave29 import (
    ELITE_CLAIM_VERIFIER_METHOD_ID,
    OPTIMIZED_BACKTEST_METHOD_ID,
    LegacySourceNativeWave29Error,
    LegacySourceNativeWave29Request,
    generate_legacy_source_native_wave29_portfolio,
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
    return generate_legacy_source_native_wave29_portfolio(
        LegacySourceNativeWave29Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave29_preserves_rolling_elite7_portfolio_and_duplicates() -> None:
    expected = (
        (5, 29, 34, 39, 44, 49),
        (5, 29, 34, 39, 44, 49),
        (10, 11, 13, 15, 17, 18),
        (10, 12, 13, 14, 15, 17),
        (7, 22, 25, 27, 32, 46),
        (15, 23, 25, 35, 47, 48),
        (5, 15, 29, 34, 39, 44),
    )
    optimized = _generate(OPTIMIZED_BACKTEST_METHOD_ID)
    verifier = _generate(ELITE_CLAIM_VERIFIER_METHOD_ID)

    assert optimized.tickets == verifier.tickets == expected
    assert optimized.metadata.native_duplicate_ticket_count == 1
    assert optimized.metadata.source_recent_windows == (
        50,
        100,
        100,
        200,
        100,
        110,
    )
    assert optimized.metadata.candidate_pool_size is None
    assert optimized.metadata.source_method_combination_count == 6


def test_wave29_keeps_distinct_all_failure_and_source_contracts() -> None:
    optimized = _generate(OPTIMIZED_BACKTEST_METHOD_ID)
    verifier = _generate(ELITE_CLAIM_VERIFIER_METHOD_ID)

    assert (
        optimized.metadata.all_base_methods_failed_behavior
        == "UNSEEDED_RANDOM_FALLBACK"
    )
    assert (
        verifier.metadata.all_base_methods_failed_behavior
        == "NO_CONSENSUS_TICKET"
    )
    assert optimized.metadata.source_sha256 != verifier.metadata.source_sha256


def test_wave29_preserves_chronological_recent_window_semantics() -> None:
    result = _generate(OPTIMIZED_BACKTEST_METHOD_ID)

    assert result.metadata.history_first_draw_number == "1"
    assert result.metadata.history_cutoff_draw_number == "200"
    assert result.metadata.source_history_first_draw_number == "1"
    assert result.metadata.source_history_last_draw_number == "200"
    assert result.metadata.source_history_order == "OLDEST_FIRST"
    assert result.metadata.source_history_order_detail == (
        "DATABASE_GET_ALL_DRAWS_REVERSED_TO_ASCENDING_BEFORE_WINDOWS"
    )


def test_wave29_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave29Error):
        generate_legacy_source_native_wave29_portfolio(
            LegacySourceNativeWave29Request(
                legacy_method_id=OPTIMIZED_BACKTEST_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave29Error):
        generate_legacy_source_native_wave29_portfolio(
            LegacySourceNativeWave29Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
