"""Unit contracts for the wave-45 frozen FFT ticket ledger."""

from __future__ import annotations

from typing import Any

import pytest

import lottolab.application.legacy_fft_native_portfolios_wave45 as module
from lottolab.application.legacy_fft_native_portfolios_wave45 import (
    FCF_VS_TS3_METHOD_ID,
    PINNED_DATASET_SHA256,
    PP3_METHOD_ID,
    LegacyFftNativeWave45Request,
    LegacyFftNativeWave45SourceError,
    generate_legacy_fft_native_wave45_portfolio,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=f"synthetic-{index:04d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(count)
    )


def test_wave45_packaged_ledger_preserves_source_positions() -> None:
    ledger = module.load_legacy_fft_native_wave45_ledger_for_verification()

    assert ledger.targets[0] == "97000049"
    assert ledger.targets[350] == "100000089"
    assert ledger.tickets_by_method[FCF_VS_TS3_METHOD_ID][0] == (
        (1, 15, 23, 29, 40, 44),
        (4, 6, 14, 30, 33, 45),
        (8, 9, 16, 20, 22, 31),
        (1, 15, 23, 29, 40, 44),
        (4, 6, 14, 30, 33, 45),
        (8, 9, 12, 22, 31, 42),
    )
    assert ledger.tickets_by_method[PP3_METHOD_ID][350] == (
        (5, 10, 19, 27, 35, 36),
        (23, 24, 33, 38, 41, 43),
        (4, 7, 13, 14, 21, 29),
    )


def test_wave45_generates_exact_ledger_portfolio(
    monkeypatch: Any,
) -> None:
    ledger = module.load_legacy_fft_native_wave45_ledger_for_verification()

    def fake_context(
        history: tuple[LegacyHistoryDraw, ...],
    ) -> str:
        del history
        return ledger.context_sha256[350]

    monkeypatch.setattr(
        module,
        "_context_sha256",
        fake_context,
    )
    result = generate_legacy_fft_native_wave45_portfolio(
        LegacyFftNativeWave45Request(
            legacy_method_id=PP3_METHOD_ID,
            target_draw_number=ledger.targets[350],
            history=_history(500),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == (
        (5, 10, 19, 27, 35, 36),
        (23, 24, 33, 38, 41, 43),
        (4, 7, 13, 14, 21, 29),
    )
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert result.metadata.native_ticket_count == 3
    assert result.metadata.randomness_used is False


def test_wave45_rejects_insufficient_history() -> None:
    with pytest.raises(
        LegacyFftNativeWave45SourceError,
        match="AVAILABLE_HISTORY_BELOW",
    ):
        generate_legacy_fft_native_wave45_portfolio(
            LegacyFftNativeWave45Request(
                legacy_method_id=PP3_METHOD_ID,
                target_draw_number="100000089",
                history=_history(499),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
