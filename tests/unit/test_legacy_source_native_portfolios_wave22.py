"""Unit contracts for the twenty-second frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave22 import (
    SMART_2BET_METHOD_ID,
    LegacySourceNativeWave22Error,
    LegacySourceNativeWave22Request,
    LegacySourceNativeWave22SourceError,
    generate_legacy_source_native_wave22_portfolio,
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


def test_wave22_preserves_two_source_ticket_positions() -> None:
    result = generate_legacy_source_native_wave22_portfolio(
        LegacySourceNativeWave22Request(
            legacy_method_id=SMART_2BET_METHOD_ID,
            target_draw_number="601",
            history=_history(600),
        )
    )

    assert result.tickets == (
        (5, 29, 34, 39, 44, 49),
        (10, 11, 12, 14, 16, 17),
    )
    assert result.metadata.native_ticket_count == 2
    assert result.metadata.native_duplicate_ticket_count == 0
    assert result.metadata.source_candidate_ticket_counts == (42, 49)
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave22_true_frequency_uses_only_latest_fifty() -> None:
    history = _history(600)
    full = generate_legacy_source_native_wave22_portfolio(
        LegacySourceNativeWave22Request(
            legacy_method_id=SMART_2BET_METHOD_ID,
            target_draw_number="601",
            history=history,
        )
    )
    latest_fifty = generate_legacy_source_native_wave22_portfolio(
        LegacySourceNativeWave22Request(
            legacy_method_id=SMART_2BET_METHOD_ID,
            target_draw_number="601",
            history=history[-50:],
        )
    )

    assert full.tickets[0] == latest_fifty.tickets[0]
    assert full.tickets[1] != latest_fifty.tickets[1]


def test_wave22_is_independent_of_bookkeeping_seed() -> None:
    history = _history(100)
    first = generate_legacy_source_native_wave22_portfolio(
        LegacySourceNativeWave22Request(
            legacy_method_id=SMART_2BET_METHOD_ID,
            target_draw_number="101",
            history=history,
            user_seed="first",
        )
    )
    second = generate_legacy_source_native_wave22_portfolio(
        LegacySourceNativeWave22Request(
            legacy_method_id=SMART_2BET_METHOD_ID,
            target_draw_number="101",
            history=history,
            user_seed="second",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.seed_digest != second.metadata.seed_digest


def test_wave22_requires_one_prior_draw() -> None:
    with pytest.raises(
        LegacySourceNativeWave22SourceError,
        match="AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM",
    ):
        generate_legacy_source_native_wave22_portfolio(
            LegacySourceNativeWave22Request(
                legacy_method_id=SMART_2BET_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )


def test_wave22_rejects_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave22Error):
        generate_legacy_source_native_wave22_portfolio(
            LegacySourceNativeWave22Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
