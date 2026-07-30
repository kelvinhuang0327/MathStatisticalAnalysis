"""Unit contracts for the wave-52 frozen source-grid ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_source_grid_native_portfolios_wave52 as module
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_grid_native_portfolios_wave52 import (
    FEATURE_METHOD_ID,
    HISTORICAL_AUDIT_METHOD_ID,
    PINNED_DATASET_SHA256,
    LegacySourceGridNativeWave52Request,
    LegacySourceGridNativeWave52SourceError,
    generate_legacy_source_grid_native_wave52_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave52_packaged_ledger_preserves_all_source_configurations() -> None:
    ledger = module.load_legacy_source_grid_native_wave52_ledger_for_verification()

    assert ledger.targets[0] == "96000002"
    assert ledger.targets[648] == "102000030"
    assert len(ledger.tickets_by_method) == 2
    assert ledger.tickets_by_method[FEATURE_METHOD_ID][2129] is None
    assert ledger.tickets_by_method[HISTORICAL_AUDIT_METHOD_ID][198] is None
    feature = ledger.tickets_by_method[FEATURE_METHOD_ID][2130]
    audit = ledger.tickets_by_method[HISTORICAL_AUDIT_METHOD_ID][199]

    assert feature is not None
    assert audit is not None
    assert len(feature) == 3
    assert len(audit) == 2


def test_wave52_generates_exact_random_source_portfolio(monkeypatch: Any) -> None:
    ledger = module.load_legacy_source_grid_native_wave52_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[2130]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave52_portfolio(
        LegacySourceGridNativeWave52Request(
            legacy_method_id=FEATURE_METHOD_ID,
            target_draw_number=ledger.targets[2130],
            history=_history(2131),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets_by_method[FEATURE_METHOD_ID][2130]
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_method_combination_count == 3
    assert result.metadata.source_candidate_k_values == (49, 100000)
    assert result.metadata.native_ticket_count == 3
    assert result.metadata.randomness_used is True
    assert result.metadata.randomness_reproduction == "EXACT_FROZEN_RUNTIME_LEDGER"


def test_wave52_keeps_candidate_configuration_and_ticket_counts_distinct(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_source_grid_native_wave52_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[199]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave52_portfolio(
        LegacySourceGridNativeWave52Request(
            legacy_method_id=HISTORICAL_AUDIT_METHOD_ID,
            target_draw_number=ledger.targets[199],
            history=_history(200),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 1
    assert result.metadata.native_ticket_count == 2
    assert result.metadata.native_ticket_count != 20
    assert result.metadata.randomness_used is True
    assert result.metadata.source_history_order == "OLDEST_FIRST"


def test_wave52_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacySourceGridNativeWave52SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_source_grid_native_wave52_portfolio(
            LegacySourceGridNativeWave52Request(
                legacy_method_id=HISTORICAL_AUDIT_METHOD_ID,
                target_draw_number="115000001",
                history=_history(199),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
