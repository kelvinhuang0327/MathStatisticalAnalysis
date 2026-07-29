"""Unit contracts for the thirty-third frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave33 import (
    FEASIBILITY_METHOD_ID,
    LegacySourceNativeWave33Error,
    LegacySourceNativeWave33Request,
    generate_legacy_source_native_wave33_portfolio,
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


def _generate(history_count: int = 250):
    return generate_legacy_source_native_wave33_portfolio(
        LegacySourceNativeWave33Request(
            legacy_method_id=FEASIBILITY_METHOD_ID,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave33_preserves_six_configs_and_eight_ticket_positions() -> None:
    result = _generate()

    assert result.tickets == (
        (2, 7, 12, 36, 41, 46),
        (10, 12, 14, 15, 17, 18),
        (5, 8, 18, 20, 26, 28),
        (1, 5, 6, 8, 11, 13),
        (2, 7, 12, 36, 41, 46),
        (10, 12, 14, 15, 17, 18),
        (2, 7, 12, 18, 36, 41),
        (5, 10, 14, 15, 17, 46),
    )
    assert result.metadata.candidate_pools == (
        (12, 18, 2, 7, 36, 41, 46, 10, 14, 15, 17, 5),
    )
    assert result.metadata.native_duplicate_ticket_count == 2
    assert result.metadata.source_method_combination_count == 6
    assert result.metadata.native_ticket_count == 8
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave33_preserves_statistical_seed_and_counter_ties() -> None:
    result = _generate()

    assert result.metadata.statistical_candidate_count == 20
    assert result.metadata.statistical_fallback_used is False
    assert result.metadata.randomness_used is True
    assert "HISTORY_LENGTH" in result.metadata.random_protocol
    assert result.metadata.tie_order_semantics == (
        "COUNTER_FIRST_INSERTION_MARKOV_THEN_DEVIATION_THEN_STATISTICAL"
    )


def test_wave33_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave33Error):
        _generate(history_count=0)
    with pytest.raises(LegacySourceNativeWave33Error):
        generate_legacy_source_native_wave33_portfolio(
            LegacySourceNativeWave33Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
