"""Unit contracts for the fourteenth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave14 import (
    GRAPH_PREDICTOR_METHOD_ID,
    HIGH_PRIZE_TREND_METHOD_ID,
    LegacySourceNativeWave14Error,
    LegacySourceNativeWave14Request,
    generate_legacy_source_native_wave14_portfolio,
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


@pytest.mark.parametrize(
    ("method_id", "expected_ticket_count"),
    (
        (GRAPH_PREDICTOR_METHOD_ID, 1),
        (HIGH_PRIZE_TREND_METHOD_ID, 7),
    ),
)
def test_wave14_preserves_native_ticket_count_and_order(
    method_id: str,
    expected_ticket_count: int,
) -> None:
    result = generate_legacy_source_native_wave14_portfolio(
        LegacySourceNativeWave14Request(
            legacy_method_id=method_id,
            target_draw_number="301",
            history=_history(300),
        )
    )

    assert len(result.tickets) == expected_ticket_count
    assert result.metadata.native_ticket_count == expected_ticket_count
    assert result.metadata.history_cutoff_draw_number == "300"
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        for ticket in result.tickets
    )


def test_wave14_keeps_candidate_and_configuration_semantics_distinct() -> None:
    history = _history(300)
    graph = generate_legacy_source_native_wave14_portfolio(
        LegacySourceNativeWave14Request(
            legacy_method_id=GRAPH_PREDICTOR_METHOD_ID,
            target_draw_number="301",
            history=history,
        )
    )
    trend = generate_legacy_source_native_wave14_portfolio(
        LegacySourceNativeWave14Request(
            legacy_method_id=HIGH_PRIZE_TREND_METHOD_ID,
            target_draw_number="301",
            history=history,
        )
    )

    assert graph.metadata.candidate_k is None
    assert graph.metadata.combination_count is None
    assert graph.metadata.source_candidate_k_values == (15,)
    assert trend.metadata.candidate_k is None
    assert trend.metadata.combination_count is None
    assert trend.metadata.source_combination_members == (
        "BIG_LOTTO:lambda=0.01",
        "BIG_LOTTO:lambda=0.02",
        "BIG_LOTTO:lambda=0.03",
        "BIG_LOTTO:lambda=0.05",
        "BIG_LOTTO:lambda=0.07",
        "BIG_LOTTO:lambda=0.10",
        "BIG_LOTTO:lambda=0.15",
    )


@pytest.mark.parametrize(
    ("method_id", "history_count"),
    (
        (GRAPH_PREDICTOR_METHOD_ID, 0),
        (HIGH_PRIZE_TREND_METHOD_ID, 99),
    ),
)
def test_wave14_enforces_frozen_source_minimums(
    method_id: str,
    history_count: int,
) -> None:
    with pytest.raises(LegacySourceNativeWave14Error):
        generate_legacy_source_native_wave14_portfolio(
            LegacySourceNativeWave14Request(
                legacy_method_id=method_id,
                target_draw_number="target",
                history=_history(history_count),
            )
        )


def test_wave14_deterministic_sources_ignore_bookkeeping_seed() -> None:
    history = _history(300)
    first = generate_legacy_source_native_wave14_portfolio(
        LegacySourceNativeWave14Request(
            legacy_method_id=HIGH_PRIZE_TREND_METHOD_ID,
            target_draw_number="301",
            history=history,
            user_seed="evidence-a",
        )
    )
    second = generate_legacy_source_native_wave14_portfolio(
        LegacySourceNativeWave14Request(
            legacy_method_id=HIGH_PRIZE_TREND_METHOD_ID,
            target_draw_number="different-target",
            history=history,
            user_seed="evidence-b",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.randomness_used is False
    assert first.metadata.randomness_reproduction == "NONE_DETERMINISTIC"
