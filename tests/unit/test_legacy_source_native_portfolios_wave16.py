"""Unit contracts for the sixteenth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave16 import (
    HOT_COOCCURRENCE_METHOD_ID,
    LegacySourceNativeWave16Error,
    LegacySourceNativeWave16Request,
    generate_legacy_source_native_wave16_portfolio,
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


def test_wave16_preserves_hot_pool_and_cooccurrence_semantics() -> None:
    result = generate_legacy_source_native_wave16_portfolio(
        LegacySourceNativeWave16Request(
            legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
            target_draw_number="101",
            history=_history(100),
        )
    )

    assert len(result.tickets) == 1
    assert result.metadata.native_ticket_count == 1
    assert result.metadata.history_cutoff_draw_number == "100"
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_candidate_k_values == (20,)
    assert len(result.metadata.frozen_support_artifacts) == 1
    assert result.metadata.source_runtime_parameters == (
        "hot_window=50",
        "hot_pool_limit=20",
        "cooccurrence_window=100",
        "cooccurrence_normalization=window_draw_count",
        "cooccurrence_weight=0.3",
    )


def test_wave16_uses_only_the_frozen_hot_and_cooccurrence_windows() -> None:
    history = _history(150)
    full = generate_legacy_source_native_wave16_portfolio(
        LegacySourceNativeWave16Request(
            legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
            target_draw_number="151",
            history=history,
        )
    )
    last_100 = generate_legacy_source_native_wave16_portfolio(
        LegacySourceNativeWave16Request(
            legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
            target_draw_number="151",
            history=history[-100:],
        )
    )

    assert full.tickets == last_100.tickets


def test_wave16_single_draw_is_one_valid_native_ticket() -> None:
    history = _history(1)
    result = generate_legacy_source_native_wave16_portfolio(
        LegacySourceNativeWave16Request(
            legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
            target_draw_number="2",
            history=history,
        )
    )

    assert result.tickets == (history[0].numbers,)
    assert result.metadata.source_candidate_k_values == (6,)


def test_wave16_requires_one_prior_draw() -> None:
    with pytest.raises(LegacySourceNativeWave16Error):
        generate_legacy_source_native_wave16_portfolio(
            LegacySourceNativeWave16Request(
                legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )


def test_wave16_is_independent_of_bookkeeping_seed() -> None:
    history = _history(100)
    first = generate_legacy_source_native_wave16_portfolio(
        LegacySourceNativeWave16Request(
            legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
            target_draw_number="101",
            history=history,
            user_seed="a",
        )
    )
    second = generate_legacy_source_native_wave16_portfolio(
        LegacySourceNativeWave16Request(
            legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
            target_draw_number="different",
            history=history,
            user_seed="b",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.randomness_used is False
