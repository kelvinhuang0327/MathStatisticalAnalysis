"""Unit contracts for the wave-51 frozen source-grid ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_source_grid_native_portfolios_wave51 as module
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_grid_native_portfolios_wave51 import (
    CLUSTER_METHOD_ID,
    DEVIATION_METHOD_ID,
    PINNED_DATASET_SHA256,
    LegacySourceGridNativeWave51Request,
    LegacySourceGridNativeWave51SourceError,
    generate_legacy_source_grid_native_wave51_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave51_packaged_ledger_preserves_all_source_configurations() -> None:
    ledger = module.load_legacy_source_grid_native_wave51_ledger_for_verification()

    assert ledger.targets[0] == "96000002"
    assert ledger.targets[648] == "102000030"
    assert len(ledger.tickets_by_method) == 2
    assert ledger.tickets_by_method[CLUSTER_METHOD_ID][1997] is None
    assert ledger.tickets_by_method[DEVIATION_METHOD_ID][1997] is None
    cluster = ledger.tickets_by_method[CLUSTER_METHOD_ID][1998]
    deviation = ledger.tickets_by_method[DEVIATION_METHOD_ID][1998]

    assert cluster is not None
    assert deviation is not None
    assert len(cluster) == 4
    assert len(deviation) == 1


def test_wave51_generates_exact_random_source_portfolio(monkeypatch: Any) -> None:
    ledger = module.load_legacy_source_grid_native_wave51_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[1998]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave51_portfolio(
        LegacySourceGridNativeWave51Request(
            legacy_method_id=CLUSTER_METHOD_ID,
            target_draw_number=ledger.targets[1998],
            history=_history(1999),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets_by_method[CLUSTER_METHOD_ID][1998]
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_method_combination_count == 1
    assert result.metadata.native_ticket_count == 4
    assert result.metadata.randomness_used is True
    assert result.metadata.randomness_reproduction == "EXACT_FROZEN_RUNTIME_LEDGER"


def test_wave51_keeps_candidate_configuration_and_ticket_counts_distinct(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_source_grid_native_wave51_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[1998]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave51_portfolio(
        LegacySourceGridNativeWave51Request(
            legacy_method_id=DEVIATION_METHOD_ID,
            target_draw_number=ledger.targets[1998],
            history=_history(1999),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 1
    assert result.metadata.native_ticket_count == 1
    assert result.metadata.native_ticket_count != 20
    assert result.metadata.randomness_used is True
    assert result.metadata.source_history_order == "RECENT_FIRST"


def test_wave51_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacySourceGridNativeWave51SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_source_grid_native_wave51_portfolio(
            LegacySourceGridNativeWave51Request(
                legacy_method_id=DEVIATION_METHOD_ID,
                target_draw_number="115000001",
                history=_history(1998),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
