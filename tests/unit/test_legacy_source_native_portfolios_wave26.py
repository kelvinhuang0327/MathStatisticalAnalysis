"""Unit contracts for the twenty-sixth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave26 import (
    CES_METHOD_ID,
    DMS_METHOD_ID,
    GREEDY_METHOD_ID,
    MWSC_METHOD_ID,
    PCE_METHOD_ID,
    SMH_CLOSED_REASON_CODE,
    LegacySourceNativeWave26Error,
    LegacySourceNativeWave26Request,
    LegacySourceNativeWave26SourceError,
    generate_legacy_source_native_wave26_portfolio,
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
    return generate_legacy_source_native_wave26_portfolio(
        LegacySourceNativeWave26Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave26_preserves_all_five_native_ticket_mappings() -> None:
    expected = {
        CES_METHOD_ID: (
            (10, 11, 16, 21, 43, 49),
            (3, 11, 16, 17, 31, 38),
            (11, 13, 16, 18, 23, 45),
        ),
        DMS_METHOD_ID: (
            (8, 13, 18, 23, 28, 33),
            (5, 11, 16, 21, 43, 49),
            (1, 6, 11, 30, 43, 48),
        ),
        GREEDY_METHOD_ID: (
            (11, 13, 18, 21, 28, 33),
            (13, 16, 18, 23, 33, 49),
            (11, 16, 21, 23, 28, 49),
        ),
        MWSC_METHOD_ID: (
            (3, 10, 13, 17, 31, 38),
            (13, 18, 23, 28, 33, 38),
            (9, 21, 28, 33, 43, 45),
        ),
        PCE_METHOD_ID: (
            (1, 3, 6, 11, 16, 21),
            (1, 3, 6, 10, 11, 16),
            (1, 3, 6, 11, 16, 17),
        ),
    }
    results = {
        method_id: _generate(method_id) for method_id in expected
    }

    assert {
        method_id: result.tickets
        for method_id, result in results.items()
    } == expected
    assert results[CES_METHOD_ID].metadata.candidate_pool_size == 20
    assert results[GREEDY_METHOD_ID].metadata.candidate_pool_size == 18
    assert results[MWSC_METHOD_ID].metadata.candidate_pool_size == 18
    assert results[PCE_METHOD_ID].metadata.candidate_pool_size is None
    assert results[DMS_METHOD_ID].metadata.selected_methods == (
        "markov",
        "statistical",
        "zone_balance",
    )
    assert results[DMS_METHOD_ID].metadata.statistical_call_count == 21


def test_wave26_preserves_dms_minimum_and_smh_closed_semantics() -> None:
    with pytest.raises(
        LegacySourceNativeWave26SourceError,
        match="AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM",
    ):
        _generate(DMS_METHOD_ID, history_count=19)
    assert SMH_CLOSED_REASON_CODE == (
        "CLOSED_UNEXECUTABLE:UNSEEDED_MODULE_GLOBAL_RANDOM_STATE_NOT_SERIALIZED"
    )


def test_wave26_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave26Error):
        generate_legacy_source_native_wave26_portfolio(
            LegacySourceNativeWave26Request(
                legacy_method_id=CES_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave26Error):
        generate_legacy_source_native_wave26_portfolio(
            LegacySourceNativeWave26Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
