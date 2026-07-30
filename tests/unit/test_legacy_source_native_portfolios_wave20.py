"""Unit contracts for the twentieth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave20 import (
    ZONE_BALANCE_500_METHOD_ID,
    LegacySourceNativeWave20Error,
    LegacySourceNativeWave20Request,
    LegacySourceNativeWave20SourceError,
    generate_legacy_source_native_wave20_portfolio,
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


def test_wave20_preserves_five_positional_outputs_and_duplicate() -> None:
    result = generate_legacy_source_native_wave20_portfolio(
        LegacySourceNativeWave20Request(
            legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
            target_draw_number="601",
            history=_history(600),
        )
    )

    assert result.tickets == (
        (5, 22, 27, 29, 42, 44),
        (5, 22, 27, 29, 32, 34),
        (5, 22, 27, 32, 34, 37),
        (1, 5, 22, 27, 34, 37),
        (5, 22, 27, 29, 42, 44),
    )
    assert result.tickets[0] == result.tickets[4]
    assert result.metadata.native_ticket_count == 5
    assert result.metadata.native_duplicate_ticket_count == 1
    assert len(result.metadata.source_combination_members) == 4
    assert result.metadata.source_candidate_ticket_counts == (1, 1, 1, 1)
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave20_uses_only_each_declared_window() -> None:
    history = _history(600)
    full = generate_legacy_source_native_wave20_portfolio(
        LegacySourceNativeWave20Request(
            legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
            target_draw_number="601",
            history=history,
        )
    )
    last_500 = generate_legacy_source_native_wave20_portfolio(
        LegacySourceNativeWave20Request(
            legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
            target_draw_number="601",
            history=history[-500:],
        )
    )

    assert full.tickets[0] == last_500.tickets[0]
    assert full.tickets[4] == last_500.tickets[4]


def test_wave20_preserves_all_same_output_positions() -> None:
    result = generate_legacy_source_native_wave20_portfolio(
        LegacySourceNativeWave20Request(
            legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
            target_draw_number="2",
            history=_history(1),
        )
    )

    assert len(set(result.tickets)) == 1
    assert result.metadata.native_duplicate_ticket_count == 4


def test_wave20_is_independent_of_bookkeeping_seed() -> None:
    history = _history(100)
    first = generate_legacy_source_native_wave20_portfolio(
        LegacySourceNativeWave20Request(
            legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
            target_draw_number="101",
            history=history,
            user_seed="first",
        )
    )
    second = generate_legacy_source_native_wave20_portfolio(
        LegacySourceNativeWave20Request(
            legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
            target_draw_number="101",
            history=history,
            user_seed="second",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.seed_digest != second.metadata.seed_digest


def test_wave20_requires_one_prior_draw() -> None:
    with pytest.raises(
        LegacySourceNativeWave20SourceError,
        match="AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM",
    ):
        generate_legacy_source_native_wave20_portfolio(
            LegacySourceNativeWave20Request(
                legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )


def test_wave20_rejects_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave20Error):
        generate_legacy_source_native_wave20_portfolio(
            LegacySourceNativeWave20Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
