"""Unit contracts for the twenty-fifth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave25 import (
    CAG_METHOD_ID,
    CLUSTER_COVER_METHOD_ID,
    TME_OPTIMIZER_METHOD_ID,
    ZDP_METHOD_ID,
    LegacySourceNativeWave25Error,
    LegacySourceNativeWave25Request,
    LegacySourceNativeWave25SourceError,
    generate_legacy_source_native_wave25_portfolio,
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
    return generate_legacy_source_native_wave25_portfolio(
        LegacySourceNativeWave25Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave25_preserves_all_four_native_ticket_mappings() -> None:
    expected = {
        TME_OPTIMIZER_METHOD_ID: (
            (5, 11, 16, 21, 43, 49),
            (3, 10, 17, 31, 38, 45),
            (8, 13, 18, 23, 28, 33),
            (1, 6, 11, 16, 21, 26),
        ),
        CAG_METHOD_ID: (
            (3, 10, 17, 31, 38, 45),
            (3, 10, 17, 31, 38, 45),
            (3, 10, 17, 31, 38, 45),
        ),
        CLUSTER_COVER_METHOD_ID: (
            (3, 8, 13, 18, 23, 33),
            (5, 10, 28, 43, 45, 49),
            (11, 16, 17, 21, 31, 38),
        ),
        ZDP_METHOD_ID: (
            (3, 10, 11, 16, 17, 21),
            (11, 16, 17, 18, 21, 31),
            (11, 16, 38, 43, 45, 49),
        ),
    }

    results = {
        method_id: _generate(method_id) for method_id in expected
    }

    assert {
        method_id: result.tickets
        for method_id, result in results.items()
    } == expected
    assert (
        results[TME_OPTIMIZER_METHOD_ID].metadata.candidate_pool_size
        is None
    )
    assert results[CAG_METHOD_ID].metadata.candidate_pool_size == 18
    assert results[ZDP_METHOD_ID].metadata.candidate_pool_size == 21
    assert (
        results[CAG_METHOD_ID].metadata.native_duplicate_ticket_count
        == 2
    )
    assert (
        results[
            CLUSTER_COVER_METHOD_ID
        ].metadata.native_duplicate_ticket_count
        == 0
    )
    assert results[ZDP_METHOD_ID].metadata.statistical_call_count == 2


def test_wave25_preserves_explicit_short_cluster_closure() -> None:
    with pytest.raises(
        LegacySourceNativeWave25SourceError,
        match="FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET",
    ):
        _generate(CLUSTER_COVER_METHOD_ID, history_count=3)


def test_wave25_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave25Error):
        generate_legacy_source_native_wave25_portfolio(
            LegacySourceNativeWave25Request(
                legacy_method_id=TME_OPTIMIZER_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave25Error):
        generate_legacy_source_native_wave25_portfolio(
            LegacySourceNativeWave25Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
