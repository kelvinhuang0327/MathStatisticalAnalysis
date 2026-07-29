"""Unit contracts for the fifteenth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave15 import (
    ATTENTION_REPLAY_METHOD_ID,
    LegacySourceNativeWave15Error,
    LegacySourceNativeWave15Request,
    generate_legacy_source_native_wave15_portfolio,
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


def test_wave15_preserves_fixed_attention_output_semantics() -> None:
    result = generate_legacy_source_native_wave15_portfolio(
        LegacySourceNativeWave15Request(
            legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
            target_draw_number="101",
            history=_history(100),
        )
    )

    assert len(result.tickets) == 1
    assert result.metadata.native_ticket_count == 1
    assert result.metadata.history_cutoff_draw_number == "100"
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert len(result.metadata.frozen_support_artifacts) == 3
    assert result.metadata.source_runtime_parameters == (
        "context_draw_count=15",
        "raw_weight[index]=1.0+index*0.1",
        "normalized_weight_sum=25.5",
    )
    assert "LOGITS_ARE_NOT_USED" in (
        result.metadata.source_ignored_model_output_semantics
    )


def test_wave15_uses_only_last_15_history_draws() -> None:
    history = _history(100)
    full = generate_legacy_source_native_wave15_portfolio(
        LegacySourceNativeWave15Request(
            legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
            target_draw_number="101",
            history=history,
        )
    )
    last_15 = generate_legacy_source_native_wave15_portfolio(
        LegacySourceNativeWave15Request(
            legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
            target_draw_number="101",
            history=history[-15:],
        )
    )

    assert full.tickets == last_15.tickets


def test_wave15_requires_one_prior_draw() -> None:
    with pytest.raises(LegacySourceNativeWave15Error):
        generate_legacy_source_native_wave15_portfolio(
            LegacySourceNativeWave15Request(
                legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )


def test_wave15_is_independent_of_bookkeeping_seed() -> None:
    history = _history(15)
    first = generate_legacy_source_native_wave15_portfolio(
        LegacySourceNativeWave15Request(
            legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
            target_draw_number="16",
            history=history,
            user_seed="a",
        )
    )
    second = generate_legacy_source_native_wave15_portfolio(
        LegacySourceNativeWave15Request(
            legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
            target_draw_number="different",
            history=history,
            user_seed="b",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.randomness_used is False
