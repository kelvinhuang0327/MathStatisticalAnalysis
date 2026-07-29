"""Unit contracts for the fortieth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave40 import (
    PORTFOLIO_METHOD_ID,
    LegacySourceNativeWave40Error,
    LegacySourceNativeWave40Request,
    generate_legacy_source_native_wave40_portfolio,
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
    return generate_legacy_source_native_wave40_portfolio(
        LegacySourceNativeWave40Request(
            legacy_method_id=PORTFOLIO_METHOD_ID,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave40_preserves_source_portfolio_order_and_duplicate_suppression() -> (
    None
):
    result = _generate()

    assert result.tickets == (
        (1, 6, 11, 16, 21, 26),
        (2, 6, 11, 16, 21, 26),
        (3, 6, 11, 16, 21, 26),
        (5, 29, 34, 39, 44, 49),
    )
    assert result.metadata.source_candidate_ticket_counts == (3, 1, 1)
    assert result.metadata.source_duplicate_suppression_results == (
        "AUXILIARY_DUPLICATE_SUPPRESSED",
        "WINDOW50_FILL_APPENDED",
    )
    assert result.metadata.native_duplicate_ticket_count == 0
    assert result.metadata.source_method_combination_count == 3


def test_wave40_keeps_candidate_component_and_ticket_counts_distinct() -> None:
    result = _generate()

    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.native_ticket_count == 4
    assert result.metadata.randomness_used is False
    assert (
        result.metadata.random_protocol
        == "NONE_DETERMINISTIC_NATIVE_SELECTION"
    )


def test_wave40_rejects_short_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave40Error):
        _generate(history_count=99)
    with pytest.raises(LegacySourceNativeWave40Error):
        generate_legacy_source_native_wave40_portfolio(
            LegacySourceNativeWave40Request(
                legacy_method_id="missing",
                target_draw_number="101",
                history=_history(100),
            )
        )
