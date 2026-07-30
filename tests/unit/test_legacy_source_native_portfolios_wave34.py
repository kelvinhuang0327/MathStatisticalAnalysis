"""Unit contracts for the thirty-fourth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave34 import (
    AUTO_OPTIMIZER_METHOD_ID,
    VARIANT_CONFIGURATIONS,
    LegacySourceNativeWave34Error,
    LegacySourceNativeWave34Request,
    generate_legacy_source_native_wave34_portfolio,
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
    return generate_legacy_source_native_wave34_portfolio(
        LegacySourceNativeWave34Request(
            legacy_method_id=AUTO_OPTIMIZER_METHOD_ID,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave34_preserves_method_major_5_by_5_grid() -> None:
    result = _generate()

    assert len(result.tickets) == 25
    assert result.tickets[:6] == (
        (5, 29, 34, 39, 44, 49),
        (5, 22, 27, 29, 32, 34),
        (5, 22, 27, 32, 34, 37),
        (1, 5, 22, 27, 29, 42),
        (1, 5, 22, 27, 29, 42),
        (5, 29, 34, 39, 44, 49),
    )
    assert result.tickets[20:] == (
        (3, 10, 17, 24, 31, 38),
        (10, 13, 15, 16, 17, 18),
        (10, 11, 12, 14, 16, 17),
        (10, 12, 14, 15, 17, 18),
        (10, 12, 14, 15, 17, 18),
    )
    assert result.metadata.variant_history_draw_counts == (
        50,
        100,
        200,
        250,
        250,
    ) * 5
    assert result.metadata.native_duplicate_ticket_count == 15
    assert result.metadata.source_method_combination_count == 25
    assert len(result.metadata.combination_members) == len(
        VARIANT_CONFIGURATIONS
    )


def test_wave34_keeps_candidate_configuration_and_ticket_counts_distinct() -> None:
    result = _generate()

    assert result.metadata.candidate_k is None
    assert result.metadata.candidate_pools == ()
    assert result.metadata.combination_count is None
    assert result.metadata.native_ticket_count == 25
    assert result.metadata.randomness_used is False
    assert result.metadata.random_protocol == "NONE_DETERMINISTIC"


def test_wave34_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave34Error):
        _generate(history_count=0)
    with pytest.raises(LegacySourceNativeWave34Error):
        generate_legacy_source_native_wave34_portfolio(
            LegacySourceNativeWave34Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
