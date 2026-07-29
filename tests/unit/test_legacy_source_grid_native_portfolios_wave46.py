"""Unit contracts for the wave-46 frozen source-grid ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_source_grid_native_portfolios_wave46 as module
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_grid_native_portfolios_wave46 import (
    MARKOV_4BET_METHOD_ID,
    OPTIMAL_MATRIX_METHOD_ID,
    PINNED_DATASET_SHA256,
    PREDICTABILITY_ALIAS_METHOD_ID,
    SIX_BET_METHOD_ID,
    SUM_CONSTRAINT_METHOD_ID,
    LegacySourceGridNativeWave46Request,
    LegacySourceGridNativeWave46SourceError,
    generate_legacy_source_grid_native_wave46_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave46_packaged_ledger_preserves_positions_duplicates_and_alias() -> None:
    ledger = module.load_legacy_source_grid_native_wave46_ledger_for_verification()

    assert ledger.targets[0] == "96000002"
    assert ledger.targets[199] == "97000100"
    six_bet = ledger.tickets_by_method[SIX_BET_METHOD_ID][199]
    markov = ledger.tickets_by_method[MARKOV_4BET_METHOD_ID][149]
    constrained = ledger.tickets_by_method[SUM_CONSTRAINT_METHOD_ID][149]

    assert six_bet is not None
    assert len(six_bet) == 11
    assert len(six_bet) - len(set(six_bet)) == 5
    assert markov is not None
    assert len(markov) == 27
    assert len(markov) - len(set(markov)) == 20
    assert constrained is not None
    assert len(constrained) == 39
    assert len(constrained) - len(set(constrained)) == 26
    assert (
        ledger.tickets_by_method[OPTIMAL_MATRIX_METHOD_ID][199]
        == ledger.tickets_by_method[PREDICTABILITY_ALIAS_METHOD_ID][199]
    )


def test_wave46_generates_exact_ledger_portfolio(monkeypatch: Any) -> None:
    ledger = module.load_legacy_source_grid_native_wave46_ledger_for_verification()

    def fake_context(
        history: tuple[LegacyHistoryDraw, ...],
    ) -> str:
        del history
        return ledger.context_sha256[199]

    monkeypatch.setattr(module, "_context_sha256", fake_context)
    result = generate_legacy_source_grid_native_wave46_portfolio(
        LegacySourceGridNativeWave46Request(
            legacy_method_id=SIX_BET_METHOD_ID,
            target_draw_number=ledger.targets[199],
            history=_history(200),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets_by_method[SIX_BET_METHOD_ID][199]
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.source_method_combination_count == 2
    assert result.metadata.native_ticket_count == 11
    assert result.metadata.native_duplicate_ticket_count == 5
    assert result.metadata.randomness_used is False


def test_wave46_keeps_candidate_pool_configuration_and_ticket_counts_distinct(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_source_grid_native_wave46_ledger_for_verification()

    def fake_context(
        history: tuple[LegacyHistoryDraw, ...],
    ) -> str:
        del history
        return ledger.context_sha256[149]

    monkeypatch.setattr(
        module,
        "_context_sha256",
        fake_context,
    )
    result = generate_legacy_source_grid_native_wave46_portfolio(
        LegacySourceGridNativeWave46Request(
            legacy_method_id=SUM_CONSTRAINT_METHOD_ID,
            target_draw_number=ledger.targets[149],
            history=_history(150),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.metadata.source_candidate_k_values == (8, 10, 12, 15)
    assert result.metadata.source_method_combination_count == 13
    assert result.metadata.native_ticket_count == 39
    assert "CANONICALIZED_TO_SORTED" in result.metadata.intra_ticket_order_semantics


def test_wave46_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacySourceGridNativeWave46SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_source_grid_native_wave46_portfolio(
            LegacySourceGridNativeWave46Request(
                legacy_method_id=SIX_BET_METHOD_ID,
                target_draw_number="97000100",
                history=_history(199),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
