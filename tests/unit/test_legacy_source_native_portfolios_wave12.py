"""Unit contracts for the twelfth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave12 import (
    MODERATE_SELECTION_METHOD_ID,
    LegacySourceNativeWave12Error,
    LegacySourceNativeWave12Request,
    generate_legacy_source_native_wave12_portfolio,
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


def test_wave12_preserves_grid_ticket_count_order_and_duplicates() -> None:
    result = generate_legacy_source_native_wave12_portfolio(
        LegacySourceNativeWave12Request(
            legacy_method_id=MODERATE_SELECTION_METHOD_ID,
            target_draw_number="301",
            history=_history(300),
        )
    )

    assert len(result.tickets) == 360
    assert result.metadata.native_ticket_count == 360
    assert len(result.metadata.source_combination_members) == 180
    assert result.metadata.source_candidate_ticket_counts == (2,) * 180
    assert result.metadata.native_duplicate_ticket_count > 0
    assert result.metadata.history_cutoff_draw_number == "300"
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        for ticket in result.tickets
    )


def test_wave12_keeps_configuration_and_candidate_semantics_distinct() -> None:
    result = generate_legacy_source_native_wave12_portfolio(
        LegacySourceNativeWave12Request(
            legacy_method_id=MODERATE_SELECTION_METHOD_ID,
            target_draw_number="51",
            history=_history(50),
        )
    )

    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_combination_members[0] == (
        "penalty=0.00|hot_rank_min=3|cold_gap=6-10"
    )
    assert result.metadata.source_combination_members[-1] == (
        "penalty=0.40|hot_rank_min=6|cold_gap=10-14"
    )


def test_wave12_enforces_frozen_source_backtest_minimum() -> None:
    with pytest.raises(LegacySourceNativeWave12Error):
        generate_legacy_source_native_wave12_portfolio(
            LegacySourceNativeWave12Request(
                legacy_method_id=MODERATE_SELECTION_METHOD_ID,
                target_draw_number="50",
                history=_history(49),
            )
        )


def test_wave12_deterministic_source_ignores_bookkeeping_seed() -> None:
    history = _history(50)
    first = generate_legacy_source_native_wave12_portfolio(
        LegacySourceNativeWave12Request(
            legacy_method_id=MODERATE_SELECTION_METHOD_ID,
            target_draw_number="51",
            history=history,
            user_seed="evidence-a",
        )
    )
    second = generate_legacy_source_native_wave12_portfolio(
        LegacySourceNativeWave12Request(
            legacy_method_id=MODERATE_SELECTION_METHOD_ID,
            target_draw_number="different-target",
            history=history,
            user_seed="evidence-b",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.randomness_used is False
    assert first.metadata.randomness_reproduction == "SOURCE_DETERMINISTIC"
