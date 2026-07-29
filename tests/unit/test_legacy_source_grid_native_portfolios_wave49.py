"""Unit contracts for the wave-49 frozen source-grid ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_source_grid_native_portfolios_wave49 as module
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_grid_native_portfolios_wave49 import (
    AUTO_DISCOVERY_METHOD_ID,
    EVALUATE_COMBINATIONS_METHOD_ID,
    FOURIER_RHYTHM_METHOD_ID,
    PINNED_DATASET_SHA256,
    LegacySourceGridNativeWave49Request,
    LegacySourceGridNativeWave49SourceError,
    generate_legacy_source_grid_native_wave49_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave49_packaged_ledger_preserves_all_source_configurations() -> None:
    ledger = module.load_legacy_source_grid_native_wave49_ledger_for_verification()

    assert ledger.targets[0] == "96000002"
    assert ledger.targets[648] == "102000030"
    assert len(ledger.tickets_by_method) == 3
    assert ledger.tickets_by_method[AUTO_DISCOVERY_METHOD_ID][647] is None
    auto = ledger.tickets_by_method[AUTO_DISCOVERY_METHOD_ID][648]
    combinations = ledger.tickets_by_method[EVALUATE_COMBINATIONS_METHOD_ID][648]
    fourier = ledger.tickets_by_method[FOURIER_RHYTHM_METHOD_ID][499]

    assert auto is not None
    assert combinations is not None
    assert fourier is not None
    assert len(auto) == 54
    assert len(combinations) == 14
    assert len(fourier) == 2


def test_wave49_generates_exact_ledger_portfolio(monkeypatch: Any) -> None:
    ledger = module.load_legacy_source_grid_native_wave49_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[648]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave49_portfolio(
        LegacySourceGridNativeWave49Request(
            legacy_method_id=AUTO_DISCOVERY_METHOD_ID,
            target_draw_number=ledger.targets[648],
            history=_history(649),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets_by_method[AUTO_DISCOVERY_METHOD_ID][648]
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_method_combination_count == 54
    assert result.metadata.native_ticket_count == 54
    assert result.metadata.randomness_used is False


def test_wave49_keeps_candidate_configuration_and_ticket_counts_distinct(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_source_grid_native_wave49_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[648]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave49_portfolio(
        LegacySourceGridNativeWave49Request(
            legacy_method_id=EVALUATE_COMBINATIONS_METHOD_ID,
            target_draw_number=ledger.targets[648],
            history=_history(649),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 4
    assert result.metadata.native_ticket_count == 14
    assert result.metadata.native_ticket_count != 20


def test_wave49_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacySourceGridNativeWave49SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_source_grid_native_wave49_portfolio(
            LegacySourceGridNativeWave49Request(
                legacy_method_id=AUTO_DISCOVERY_METHOD_ID,
                target_draw_number="102000052",
                history=_history(648),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
