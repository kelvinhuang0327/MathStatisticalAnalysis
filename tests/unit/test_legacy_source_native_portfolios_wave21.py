"""Unit contracts for the twenty-first frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave21 import (
    POST_SELECTION_FILTER_METHOD_ID,
    LegacySourceNativeWave21Error,
    LegacySourceNativeWave21Request,
    LegacySourceNativeWave21SourceError,
    generate_legacy_source_native_wave21_portfolio,
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


def test_wave21_preserves_two_source_ticket_positions() -> None:
    result = generate_legacy_source_native_wave21_portfolio(
        LegacySourceNativeWave21Request(
            legacy_method_id=POST_SELECTION_FILTER_METHOD_ID,
            target_draw_number="601",
            history=_history(600),
        )
    )

    assert result.tickets == (
        (5, 29, 34, 39, 44, 49),
        (5, 22, 27, 29, 42, 44),
    )
    assert result.metadata.native_ticket_count == 2
    assert result.metadata.native_duplicate_ticket_count == 0
    assert result.metadata.source_candidate_ticket_counts == (42, 49)
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave21_preserves_danger_filter_and_zone_retry() -> None:
    history = (
        LegacyHistoryDraw(
            draw_number="1",
            numbers=(1, 2, 3, 4, 5, 6),
        ),
        LegacyHistoryDraw(
            draw_number="2",
            numbers=(1, 7, 8, 9, 10, 11),
        ),
        LegacyHistoryDraw(
            draw_number="3",
            numbers=(1, 12, 13, 14, 15, 16),
        ),
    )

    result = generate_legacy_source_native_wave21_portfolio(
        LegacySourceNativeWave21Request(
            legacy_method_id=POST_SELECTION_FILTER_METHOD_ID,
            target_draw_number="4",
            history=history,
        )
    )

    assert result.tickets == (
        (2, 3, 4, 5, 6, 7),
        (1, 2, 3, 4, 5, 14),
    )
    assert result.metadata.danger_numbers == (1,)
    assert result.metadata.zone_retry_used is True
    assert result.metadata.zone_fallback_used is False


def test_wave21_preserves_source_invalid_frequency_ticket() -> None:
    history = tuple(
        LegacyHistoryDraw(
            draw_number=str(index + 1),
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(3)
    )

    with pytest.raises(
        LegacySourceNativeWave21SourceError,
        match="FROZEN_SOURCE_INVALID_TICKET",
    ):
        generate_legacy_source_native_wave21_portfolio(
            LegacySourceNativeWave21Request(
                legacy_method_id=POST_SELECTION_FILTER_METHOD_ID,
                target_draw_number="4",
                history=history,
            )
        )


def test_wave21_is_independent_of_bookkeeping_seed() -> None:
    history = _history(100)
    first = generate_legacy_source_native_wave21_portfolio(
        LegacySourceNativeWave21Request(
            legacy_method_id=POST_SELECTION_FILTER_METHOD_ID,
            target_draw_number="101",
            history=history,
            user_seed="first",
        )
    )
    second = generate_legacy_source_native_wave21_portfolio(
        LegacySourceNativeWave21Request(
            legacy_method_id=POST_SELECTION_FILTER_METHOD_ID,
            target_draw_number="101",
            history=history,
            user_seed="second",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.seed_digest != second.metadata.seed_digest


def test_wave21_requires_one_prior_draw() -> None:
    with pytest.raises(
        LegacySourceNativeWave21SourceError,
        match="AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM",
    ):
        generate_legacy_source_native_wave21_portfolio(
            LegacySourceNativeWave21Request(
                legacy_method_id=POST_SELECTION_FILTER_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )


def test_wave21_rejects_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave21Error):
        generate_legacy_source_native_wave21_portfolio(
            LegacySourceNativeWave21Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
