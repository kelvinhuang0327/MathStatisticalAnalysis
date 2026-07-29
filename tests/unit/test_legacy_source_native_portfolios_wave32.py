"""Unit contracts for the thirty-second frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave32 import (
    VARIANT_CONFIGURATIONS,
    VARIANT_HISTORY_METHOD_ID,
    LegacySourceNativeWave32Error,
    LegacySourceNativeWave32Request,
    generate_legacy_source_native_wave32_portfolio,
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
    return generate_legacy_source_native_wave32_portfolio(
        LegacySourceNativeWave32Request(
            legacy_method_id=VARIANT_HISTORY_METHOD_ID,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave32_preserves_eleven_variant_positions_and_windows() -> None:
    result = _generate()

    assert result.tickets == (
        (3, 10, 17, 24, 31, 38),
        (10, 13, 15, 16, 17, 18),
        (10, 11, 12, 14, 16, 17),
        (2, 5, 6, 32, 39, 49),
        (7, 22, 27, 32, 34, 46),
        (2, 23, 25, 28, 32, 33),
        (2, 7, 12, 36, 41, 46),
        (2, 7, 12, 36, 41, 46),
        (1, 6, 11, 16, 21, 26),
        (3, 10, 17, 24, 31, 38),
        (5, 22, 27, 29, 32, 34),
    )
    assert result.metadata.variant_history_draw_counts == (
        50,
        100,
        200,
        50,
        100,
        200,
        50,
        100,
        200,
        50,
        100,
    )
    assert result.metadata.native_duplicate_ticket_count == 2
    assert result.metadata.source_method_combination_count == 11
    assert len(result.metadata.combination_members) == len(
        VARIANT_CONFIGURATIONS
    )
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave32_preserves_len_seeded_statistical_metadata() -> None:
    result = _generate()

    assert result.metadata.statistical_candidate_counts == (
        None,
        None,
        None,
        20,
        20,
        20,
        None,
        None,
        None,
        None,
        None,
    )
    assert result.metadata.statistical_fallback_positions == ()
    assert result.metadata.randomness_used is True
    assert "HISTORY_LENGTH" in result.metadata.random_protocol


def test_wave32_rejects_insufficient_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave32Error):
        _generate(history_count=19)
    with pytest.raises(LegacySourceNativeWave32Error):
        generate_legacy_source_native_wave32_portfolio(
            LegacySourceNativeWave32Request(
                legacy_method_id="missing",
                target_draw_number="21",
                history=_history(20),
            )
        )
