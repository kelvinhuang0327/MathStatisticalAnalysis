"""Unit contracts for the eighth frozen source-native wave."""

from __future__ import annotations

import math

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave8 import (
    CLUSTER_ENHANCEMENTS_METHOD_ID,
    DYNAMIC_FREQUENCY_METHOD_ID,
    GEMINI_PHASE2_METHOD_ID,
    OPTIMIZE_THIRD_BET_METHOD_ID,
    LegacySourceNativeWave8Error,
    LegacySourceNativeWave8Request,
    generate_legacy_source_native_wave8_portfolio,
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
    ("method_id", "history_count", "expected_count"),
    (
        (GEMINI_PHASE2_METHOD_ID, 240, 7),
        (DYNAMIC_FREQUENCY_METHOD_ID, 240, 1),
        (CLUSTER_ENHANCEMENTS_METHOD_ID, 240, 14),
        (OPTIMIZE_THIRD_BET_METHOD_ID, 240, 1),
    ),
)
def test_wave8_preserves_native_ticket_count_and_order(
    method_id: str,
    history_count: int,
    expected_count: int,
) -> None:
    result = generate_legacy_source_native_wave8_portfolio(
        LegacySourceNativeWave8Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )

    assert len(result.tickets) == expected_count
    assert result.metadata.native_ticket_count == expected_count
    assert result.metadata.history_cutoff_draw_number == str(history_count)
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        for ticket in result.tickets
    )


def test_wave8_keeps_candidate_and_configuration_semantics_distinct() -> None:
    history = _history(240)
    gemini = generate_legacy_source_native_wave8_portfolio(
        LegacySourceNativeWave8Request(
            legacy_method_id=GEMINI_PHASE2_METHOD_ID,
            target_draw_number="241",
            history=history,
        )
    )
    dynamic = generate_legacy_source_native_wave8_portfolio(
        LegacySourceNativeWave8Request(
            legacy_method_id=DYNAMIC_FREQUENCY_METHOD_ID,
            target_draw_number="241",
            history=history,
        )
    )
    optimized = generate_legacy_source_native_wave8_portfolio(
        LegacySourceNativeWave8Request(
            legacy_method_id=OPTIMIZE_THIRD_BET_METHOD_ID,
            target_draw_number="241",
            history=history,
        )
    )

    assert gemini.metadata.combination_count is None
    assert len(gemini.metadata.source_combination_members) == 7
    assert gemini.metadata.candidate_k is None
    assert dynamic.metadata.combination_count is None
    assert len(dynamic.metadata.source_combination_members) == 5
    assert dynamic.metadata.native_ticket_count == 1
    assert optimized.metadata.combination_count is None
    assert len(optimized.metadata.source_combination_members) == 1
    assert optimized.metadata.native_ticket_count == 1
    assert optimized.metadata.candidate_k is None
    assert optimized.metadata.candidate_combination_count is None
    candidate_k = optimized.metadata.source_candidate_ticket_counts[0]
    assert math.comb(
        candidate_k,
        6,
    ) > 1


def test_wave8_cluster_configuration_counts_are_source_ordered() -> None:
    early = generate_legacy_source_native_wave8_portfolio(
        LegacySourceNativeWave8Request(
            legacy_method_id=CLUSTER_ENHANCEMENTS_METHOD_ID,
            target_draw_number="101",
            history=_history(100),
        )
    )
    mature = generate_legacy_source_native_wave8_portfolio(
        LegacySourceNativeWave8Request(
            legacy_method_id=CLUSTER_ENHANCEMENTS_METHOD_ID,
            target_draw_number="241",
            history=_history(240),
        )
    )

    assert early.metadata.source_candidate_ticket_counts == (
        1,
        1,
        1,
        1,
        1,
        1,
        3,
        3,
    )
    assert mature.metadata.source_candidate_ticket_counts == (
        1,
        1,
        1,
        1,
        1,
        1,
        4,
        4,
    )


@pytest.mark.parametrize(
    ("method_id", "minimum"),
    (
        (GEMINI_PHASE2_METHOD_ID, 100),
        (DYNAMIC_FREQUENCY_METHOD_ID, 200),
        (CLUSTER_ENHANCEMENTS_METHOD_ID, 100),
        (OPTIMIZE_THIRD_BET_METHOD_ID, 1),
    ),
)
def test_wave8_enforces_effective_frozen_source_minimum(
    method_id: str,
    minimum: int,
) -> None:
    with pytest.raises(LegacySourceNativeWave8Error):
        generate_legacy_source_native_wave8_portfolio(
            LegacySourceNativeWave8Request(
                legacy_method_id=method_id,
                target_draw_number=str(minimum),
                history=_history(minimum - 1),
            )
        )


def test_wave8_is_target_stable_and_deterministic() -> None:
    request = LegacySourceNativeWave8Request(
        legacy_method_id=GEMINI_PHASE2_METHOD_ID,
        target_draw_number="241",
        history=_history(240),
    )

    first = generate_legacy_source_native_wave8_portfolio(request)
    second = generate_legacy_source_native_wave8_portfolio(request)

    assert first == second
    assert first.metadata.random_protocol == "NONE_DETERMINISTIC"
    assert first.metadata.randomness_used is False
    assert first.metadata.randomness_reproduction == "SOURCE_DETERMINISTIC"
