"""Unit contracts for the seventh frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave7 import (
    APRIORI_BACKTEST_METHOD_ID,
    APRIORI_PREDICT_METHOD_ID,
    BEST_HYBRID_METHOD_ID,
    CLUSTER_6_METHOD_ID,
    CLUSTER_7_METHOD_ID,
    LegacySourceNativeWave7Request,
    LegacySourceNativeWave7SourceError,
    generate_legacy_source_native_wave7_portfolio,
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
    ("method_id", "expected_count"),
    (
        (CLUSTER_6_METHOD_ID, 6),
        (CLUSTER_7_METHOD_ID, 7),
        (APRIORI_PREDICT_METHOD_ID, 7),
        (APRIORI_BACKTEST_METHOD_ID, 13),
        (BEST_HYBRID_METHOD_ID, 7),
    ),
)
def test_wave7_preserves_source_native_ticket_counts_and_order(
    method_id: str,
    expected_count: int,
) -> None:
    result = generate_legacy_source_native_wave7_portfolio(
        LegacySourceNativeWave7Request(
            legacy_method_id=method_id,
            target_draw_number="31",
            history=_history(30),
        )
    )

    assert len(result.tickets) == expected_count
    assert result.metadata.native_ticket_count == expected_count
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.history_cutoff_draw_number == "30"
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        for ticket in result.tickets
    )


def test_wave7_cluster_and_best_share_frozen_first_six_positions() -> None:
    history = _history(30)
    cluster = generate_legacy_source_native_wave7_portfolio(
        LegacySourceNativeWave7Request(
            legacy_method_id=CLUSTER_6_METHOD_ID,
            target_draw_number="31",
            history=history,
        )
    )
    best = generate_legacy_source_native_wave7_portfolio(
        LegacySourceNativeWave7Request(
            legacy_method_id=BEST_HYBRID_METHOD_ID,
            target_draw_number="31",
            history=history,
        )
    )

    assert best.tickets[:6] == cluster.tickets
    assert best.tickets[6] == (6, 22, 28, 38, 44, 48)


def test_wave7_preserves_positional_duplicates() -> None:
    history = _history(30)
    apriori = generate_legacy_source_native_wave7_portfolio(
        LegacySourceNativeWave7Request(
            legacy_method_id=APRIORI_PREDICT_METHOD_ID,
            target_draw_number="31",
            history=history,
        )
    )
    backtest = generate_legacy_source_native_wave7_portfolio(
        LegacySourceNativeWave7Request(
            legacy_method_id=APRIORI_BACKTEST_METHOD_ID,
            target_draw_number="31",
            history=history,
        )
    )

    assert len(set(apriori.tickets)) == 1
    assert len(set(backtest.tickets)) == 1
    assert apriori.metadata.native_duplicate_ticket_count == 6
    assert backtest.metadata.native_duplicate_ticket_count == 12


def test_wave7_random_methods_are_target_stable_and_versioned() -> None:
    request = LegacySourceNativeWave7Request(
        legacy_method_id=BEST_HYBRID_METHOD_ID,
        target_draw_number="31",
        history=_history(30),
    )
    first = generate_legacy_source_native_wave7_portfolio(request)
    second = generate_legacy_source_native_wave7_portfolio(request)
    next_target = generate_legacy_source_native_wave7_portfolio(
        LegacySourceNativeWave7Request(
            legacy_method_id=BEST_HYBRID_METHOD_ID,
            target_draw_number="32",
            history=request.history,
        )
    )

    assert first == second
    assert first.tickets[:6] == next_target.tickets[:6]
    assert first.tickets[6] != next_target.tickets[6]
    assert first.metadata.randomness_reproduction == (
        "TARGET_STABLE_SOURCE_CALL_ORDER_PRESERVING_VERSIONED_SEED"
    )


def test_wave7_closes_frozen_empty_or_invalid_early_output() -> None:
    with pytest.raises(
        LegacySourceNativeWave7SourceError,
        match="FROZEN_SOURCE_INVALID_TICKET",
    ):
        generate_legacy_source_native_wave7_portfolio(
            LegacySourceNativeWave7Request(
                legacy_method_id=CLUSTER_6_METHOD_ID,
                target_draw_number="2",
                history=_history(1),
            )
        )
    with pytest.raises(
        LegacySourceNativeWave7SourceError,
        match="FROZEN_SOURCE_NO_NATIVE_TICKETS",
    ):
        generate_legacy_source_native_wave7_portfolio(
            LegacySourceNativeWave7Request(
                legacy_method_id=APRIORI_PREDICT_METHOD_ID,
                target_draw_number="2",
                history=_history(1),
            )
        )
