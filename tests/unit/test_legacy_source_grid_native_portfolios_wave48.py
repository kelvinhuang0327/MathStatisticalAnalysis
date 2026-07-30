"""Unit contracts for the wave-48 frozen source-grid ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_source_grid_native_portfolios_wave48 as module
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_grid_native_portfolios_wave48 import (
    DIRECTION_3_METHOD_ID,
    ENHANCEMENTS_METHOD_ID,
    OPTIMIZE_5BET_ALIAS_METHOD_ID,
    PINNED_DATASET_SHA256,
    LegacySourceGridNativeWave48Request,
    LegacySourceGridNativeWave48SourceError,
    generate_legacy_source_grid_native_wave48_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave48_packaged_ledger_preserves_positions_and_alias_source() -> None:
    ledger = module.load_legacy_source_grid_native_wave48_ledger_for_verification()

    assert ledger.targets[0] == "96000002"
    assert ledger.targets[648] == "102000030"
    assert len(ledger.tickets_by_method) == 3
    assert ledger.tickets_by_method[ENHANCEMENTS_METHOD_ID][647] is None
    enhancements = ledger.tickets_by_method[ENHANCEMENTS_METHOD_ID][648]
    direction = ledger.tickets_by_method[DIRECTION_3_METHOD_ID][499]

    assert enhancements is not None
    assert direction is not None
    assert len(enhancements) == 42
    assert len(direction) == 6

    from lottolab.application.legacy_source_grid_native_portfolios_wave47 import (
        STANDARD_TS3_METHOD_ID,
        load_legacy_source_grid_native_wave47_ledger_for_verification,
    )

    wave47 = load_legacy_source_grid_native_wave47_ledger_for_verification()
    assert (
        ledger.tickets_by_method[OPTIMIZE_5BET_ALIAS_METHOD_ID][648:]
        == wave47.tickets_by_method[STANDARD_TS3_METHOD_ID][648:]
    )


def test_wave48_generates_exact_ledger_portfolio(monkeypatch: Any) -> None:
    ledger = module.load_legacy_source_grid_native_wave48_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[648]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave48_portfolio(
        LegacySourceGridNativeWave48Request(
            legacy_method_id=ENHANCEMENTS_METHOD_ID,
            target_draw_number=ledger.targets[648],
            history=_history(649),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets_by_method[ENHANCEMENTS_METHOD_ID][648]
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 10
    assert result.metadata.native_ticket_count == 42
    assert result.metadata.randomness_used is False


def test_wave48_keeps_candidate_configuration_and_ticket_counts_distinct(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_source_grid_native_wave48_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[499]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave48_portfolio(
        LegacySourceGridNativeWave48Request(
            legacy_method_id=DIRECTION_3_METHOD_ID,
            target_draw_number=ledger.targets[499],
            history=_history(500),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.source_method_combination_count == 2
    assert result.metadata.native_ticket_count == 6
    assert result.metadata.native_ticket_count != 20


def test_wave48_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacySourceGridNativeWave48SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_source_grid_native_wave48_portfolio(
            LegacySourceGridNativeWave48Request(
                legacy_method_id=ENHANCEMENTS_METHOD_ID,
                target_draw_number="102000052",
                history=_history(648),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
