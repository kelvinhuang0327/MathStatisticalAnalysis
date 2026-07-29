"""Unit contracts for the wave-53 frozen source-grid ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_source_grid_native_portfolios_wave53 as module
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_grid_native_portfolios_wave53 import (
    ANALYSIS_METHOD_ID,
    PINNED_DATASET_SHA256,
    RGF_METHOD_ID,
    LegacySourceGridNativeWave53Request,
    LegacySourceGridNativeWave53SourceError,
    generate_legacy_source_grid_native_wave53_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave53_packaged_ledger_preserves_all_source_configurations() -> None:
    ledger = module.load_legacy_source_grid_native_wave53_ledger_for_verification()

    assert ledger.targets[0] == "96000002"
    assert ledger.targets[648] == "102000030"
    assert len(ledger.tickets_by_method) == 2
    assert ledger.tickets_by_method[ANALYSIS_METHOD_ID][498] is None
    assert ledger.tickets_by_method[RGF_METHOD_ID][198] is None
    analysis = ledger.tickets_by_method[ANALYSIS_METHOD_ID][499]
    rgf = ledger.tickets_by_method[RGF_METHOD_ID][199]

    assert analysis is not None
    assert rgf is not None
    assert len(analysis) == 14
    assert len(rgf) == 6


def test_wave53_generates_exact_random_source_portfolio(monkeypatch: Any) -> None:
    ledger = module.load_legacy_source_grid_native_wave53_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[499]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave53_portfolio(
        LegacySourceGridNativeWave53Request(
            legacy_method_id=ANALYSIS_METHOD_ID,
            target_draw_number=ledger.targets[499],
            history=_history(500),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets_by_method[ANALYSIS_METHOD_ID][499]
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_method_combination_count == 4
    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.native_ticket_count == 14
    assert result.metadata.randomness_used is False
    assert result.metadata.randomness_reproduction == "NOT_APPLICABLE"


def test_wave53_keeps_candidate_configuration_and_ticket_counts_distinct(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_source_grid_native_wave53_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[199]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave53_portfolio(
        LegacySourceGridNativeWave53Request(
            legacy_method_id=RGF_METHOD_ID,
            target_draw_number=ledger.targets[199],
            history=_history(200),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 6
    assert result.metadata.native_ticket_count == 6
    assert result.metadata.native_ticket_count != 20
    assert result.metadata.randomness_used is False
    assert result.metadata.source_history_order == "OLDEST_FIRST"


def test_wave53_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacySourceGridNativeWave53SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_source_grid_native_wave53_portfolio(
            LegacySourceGridNativeWave53Request(
                legacy_method_id=RGF_METHOD_ID,
                target_draw_number="115000001",
                history=_history(199),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
