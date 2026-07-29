"""Unit contracts for the wave-47 frozen source-grid ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_source_grid_native_portfolios_wave47 as module
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_grid_native_portfolios_wave47 import (
    EDGE_SPLICER_METHOD_ID,
    ORTHOGONAL_2_3_METHOD_ID,
    PINNED_DATASET_SHA256,
    STABILITY_ALIAS_METHOD_ID,
    LegacySourceGridNativeWave47Request,
    LegacySourceGridNativeWave47SourceError,
    generate_legacy_source_grid_native_wave47_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave47_packaged_ledger_preserves_positions_and_cross_wave_alias() -> None:
    ledger = module.load_legacy_source_grid_native_wave47_ledger_for_verification()

    assert ledger.targets[0] == "96000002"
    assert ledger.targets[648] == "102000030"
    assert len(ledger.tickets_by_method) == 8
    assert ledger.tickets_by_method[EDGE_SPLICER_METHOD_ID][647] is None
    edge = ledger.tickets_by_method[EDGE_SPLICER_METHOD_ID][648]
    orthogonal = ledger.tickets_by_method[ORTHOGONAL_2_3_METHOD_ID][648]

    assert edge is not None
    assert orthogonal is not None
    assert len(edge) == 5
    assert len(orthogonal) == 5

    from lottolab.application.legacy_source_grid_native_portfolios_wave46 import (
        ORTHOGONAL_5BET_METHOD_ID,
        load_legacy_source_grid_native_wave46_ledger_for_verification,
    )

    wave46 = load_legacy_source_grid_native_wave46_ledger_for_verification()
    assert (
        ledger.tickets_by_method[STABILITY_ALIAS_METHOD_ID][499:]
        == wave46.tickets_by_method[ORTHOGONAL_5BET_METHOD_ID][499:]
    )


def test_wave47_generates_exact_ledger_portfolio(monkeypatch: Any) -> None:
    ledger = module.load_legacy_source_grid_native_wave47_ledger_for_verification()

    def fake_context(
        history: tuple[LegacyHistoryDraw, ...],
    ) -> str:
        del history
        return ledger.context_sha256[648]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave47_portfolio(
        LegacySourceGridNativeWave47Request(
            legacy_method_id=EDGE_SPLICER_METHOD_ID,
            target_draw_number=ledger.targets[648],
            history=_history(649),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets_by_method[EDGE_SPLICER_METHOD_ID][648]
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 2
    assert result.metadata.native_ticket_count == 5
    assert result.metadata.randomness_used is False
    assert (
        result.metadata.source_minimum_history_rationale
        == "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY"
    )


def test_wave47_keeps_candidate_configuration_and_ticket_counts_distinct(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_source_grid_native_wave47_ledger_for_verification()

    def fake_context(
        history: tuple[LegacyHistoryDraw, ...],
    ) -> str:
        del history
        return ledger.context_sha256[0]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave47_portfolio(
        LegacySourceGridNativeWave47Request(
            legacy_method_id=ORTHOGONAL_2_3_METHOD_ID,
            target_draw_number=ledger.targets[0],
            history=_history(1),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 2
    assert result.metadata.native_ticket_count == 5
    assert result.metadata.native_ticket_count != 20


def test_wave47_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacySourceGridNativeWave47SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_source_grid_native_wave47_portfolio(
            LegacySourceGridNativeWave47Request(
                legacy_method_id=EDGE_SPLICER_METHOD_ID,
                target_draw_number="102000052",
                history=_history(648),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
