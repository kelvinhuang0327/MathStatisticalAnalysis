"""Unit contracts for the seventeenth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave17 import (
    SCIENTIFIC_SMART_RANDOM_METHOD_ID,
    SMART_MULTI_BET_METHOD_ID,
    LegacySourceNativeWave17Error,
    LegacySourceNativeWave17Request,
    generate_legacy_source_native_wave17_portfolio,
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
    ("method_id", "ticket_count", "combination_count"),
    (
        (SCIENTIFIC_SMART_RANDOM_METHOD_ID, 7, 1),
        (SMART_MULTI_BET_METHOD_ID, 6, 6),
    ),
)
def test_wave17_preserves_native_ticket_and_configuration_semantics(
    method_id: str,
    ticket_count: int,
    combination_count: int,
) -> None:
    result = generate_legacy_source_native_wave17_portfolio(
        LegacySourceNativeWave17Request(
            legacy_method_id=method_id,
            target_draw_number="351",
            history=_history(350),
        )
    )

    assert len(result.tickets) == ticket_count
    assert result.metadata.native_ticket_count == ticket_count
    assert (
        len(result.metadata.source_combination_members)
        == combination_count
    )
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.randomness_used is True
    assert all(
        len(ticket) == len(set(ticket)) == 6
        for ticket in result.tickets
    )


def test_wave17_scientific_report_preserves_ev_sorted_fixture() -> None:
    result = generate_legacy_source_native_wave17_portfolio(
        LegacySourceNativeWave17Request(
            legacy_method_id=SCIENTIFIC_SMART_RANDOM_METHOD_ID,
            target_draw_number="351",
            history=_history(350),
        )
    )

    assert result.tickets == (
        (3, 26, 35, 37, 44, 48),
        (8, 27, 30, 39, 47, 49),
        (2, 11, 13, 17, 33, 34),
        (16, 18, 22, 28, 32, 39),
        (8, 12, 21, 23, 35, 39),
        (9, 13, 14, 15, 33, 41),
        (1, 2, 21, 27, 29, 38),
    )
    assert len(result.metadata.frozen_support_artifacts) == 2
    assert result.metadata.source_candidate_ticket_counts == ()


def test_wave17_smart_multi_bet_preserves_pool_and_strategy_order() -> None:
    result = generate_legacy_source_native_wave17_portfolio(
        LegacySourceNativeWave17Request(
            legacy_method_id=SMART_MULTI_BET_METHOD_ID,
            target_draw_number="351",
            history=_history(350),
        )
    )

    assert result.tickets == (
        (5, 9, 12, 24, 32, 34),
        (14, 18, 26, 44, 46, 47),
        (2, 4, 7, 19, 43, 48),
        (5, 7, 10, 29, 36, 41),
        (1, 17, 21, 40, 43, 45),
        (9, 12, 20, 27, 34, 41),
    )
    assert result.metadata.source_candidate_ticket_counts == (
        15,
        15,
        19,
        42,
        6,
        0,
    )
    assert result.metadata.native_ticket_order == (
        "SOURCE_STRATEGY_DECLARATION_ORDER"
    )


def test_wave17_smart_multi_uses_only_latest_300_draws() -> None:
    history = _history(350)
    full = generate_legacy_source_native_wave17_portfolio(
        LegacySourceNativeWave17Request(
            legacy_method_id=SMART_MULTI_BET_METHOD_ID,
            target_draw_number="351",
            history=history,
        )
    )
    last_300 = generate_legacy_source_native_wave17_portfolio(
        LegacySourceNativeWave17Request(
            legacy_method_id=SMART_MULTI_BET_METHOD_ID,
            target_draw_number="351",
            history=history[-300:],
        )
    )

    assert full.tickets == last_300.tickets
    assert (
        full.metadata.source_candidate_ticket_counts
        == last_300.metadata.source_candidate_ticket_counts
    )


def test_wave17_seed_is_reproducible_and_target_stable() -> None:
    request = LegacySourceNativeWave17Request(
        legacy_method_id=SCIENTIFIC_SMART_RANDOM_METHOD_ID,
        target_draw_number="351",
        history=_history(10),
        user_seed="fixture",
    )
    first = generate_legacy_source_native_wave17_portfolio(request)
    second = generate_legacy_source_native_wave17_portfolio(request)
    changed = generate_legacy_source_native_wave17_portfolio(
        LegacySourceNativeWave17Request(
            legacy_method_id=SCIENTIFIC_SMART_RANDOM_METHOD_ID,
            target_draw_number="352",
            history=_history(10),
            user_seed="fixture",
        )
    )

    assert first == second
    assert first.tickets != changed.tickets


def test_wave17_rejects_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave17Error):
        generate_legacy_source_native_wave17_portfolio(
            LegacySourceNativeWave17Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
