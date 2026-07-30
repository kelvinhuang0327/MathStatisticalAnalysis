"""Unit contracts for the forty-first frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave41 import (
    GRAPH_METHOD_ID,
    LegacySourceNativeWave41Error,
    LegacySourceNativeWave41Request,
    generate_legacy_source_native_wave41_portfolio,
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
    return generate_legacy_source_native_wave41_portfolio(
        LegacySourceNativeWave41Request(
            legacy_method_id=GRAPH_METHOD_ID,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave41_preserves_graph_then_deviation_source_order() -> None:
    result = _generate()

    assert result.tickets == (
        (5, 22, 27, 29, 32, 34),
        (10, 12, 14, 15, 17, 18),
    )
    assert result.metadata.graph_edge_count == 105
    assert result.metadata.graph_ranked_numbers[:10] == (
        5,
        22,
        27,
        29,
        32,
        34,
        37,
        39,
        42,
        44,
    )
    assert result.metadata.graph_history_draw_count == 250
    assert result.metadata.native_duplicate_ticket_count == 0
    assert result.metadata.source_method_combination_count == 2


def test_wave41_keeps_candidate_configuration_and_ticket_counts_distinct() -> (
    None
):
    result = _generate()

    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.native_ticket_count == 2
    assert result.metadata.randomness_used is False
    assert result.metadata.random_protocol == "NONE_DETERMINISTIC"


def test_wave41_caps_graph_history_at_five_hundred() -> None:
    result = _generate(history_count=600)

    assert result.metadata.graph_history_draw_count == 500


def test_wave41_rejects_short_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave41Error):
        _generate(history_count=49)
    with pytest.raises(LegacySourceNativeWave41Error):
        generate_legacy_source_native_wave41_portfolio(
            LegacySourceNativeWave41Request(
                legacy_method_id="missing",
                target_draw_number="51",
                history=_history(50),
            )
        )
