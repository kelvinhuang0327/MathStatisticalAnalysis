"""Unit contracts for the wave-55 frozen-checkpoint ticket ledger."""

from __future__ import annotations

from datetime import date

import pytest

import lottolab.application.legacy_checkpoint_native_portfolios_wave55 as module
from lottolab.application.legacy_checkpoint_native_portfolios_wave55 import (
    ORTHOGONAL_METHOD_ID,
    PINNED_DATASET_SHA256,
    SIX_EXPERT_METHOD_ID,
    LegacyCheckpointNativeWave55Request,
    LegacyCheckpointNativeWave55SourceError,
    generate_legacy_checkpoint_native_wave55_portfolio,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)

CONTEXT = (
    ("115000011", (4, 12, 24, 25, 39, 48)),
    ("115000012", (6, 16, 20, 21, 24, 35)),
    ("115000013", (1, 3, 8, 15, 20, 48)),
    ("115000014", (9, 20, 25, 35, 39, 48)),
    ("115000015", (1, 11, 22, 35, 36, 40)),
    ("115000016", (3, 6, 11, 18, 25, 28)),
    ("115000017", (11, 16, 18, 27, 38, 46)),
    ("115000018", (6, 12, 24, 26, 37, 46)),
    ("115000019", (16, 35, 36, 37, 39, 49)),
    ("115000020", (20, 28, 29, 31, 35, 41)),
    ("115000021", (13, 15, 18, 24, 33, 49)),
    ("115000022", (12, 13, 17, 27, 41, 48)),
    ("115000023", (5, 7, 17, 22, 24, 47)),
    ("115000024", (6, 10, 23, 27, 47, 48)),
    ("115000025", (12, 19, 22, 27, 28, 31)),
)


def _history() -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(draw_number=draw_number, numbers=numbers)
        for draw_number, numbers in CONTEXT
    )


def _request(
    method_id: str,
    *,
    target_date: date = date(2026, 2, 25),
    history: tuple[LegacyHistoryDraw, ...] | None = None,
) -> LegacyCheckpointNativeWave55Request:
    return LegacyCheckpointNativeWave55Request(
        legacy_method_id=method_id,
        target_draw_number="115000026",
        target_draw_date=target_date,
        history=_history() if history is None else history,
        dataset_sha256=PINNED_DATASET_SHA256,
    )


def test_wave55_replays_both_exact_source_runtime_portfolios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = module.load_legacy_checkpoint_native_wave55_ledger_for_verification()

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[0]

    monkeypatch.setattr(
        module,
        "_full_context_sha256",
        fake_context,
    )
    expected = {
        ORTHOGONAL_METHOD_ID: (
            (18, 29, 35, 40, 42, 46),
            (6, 12, 18, 24, 27, 35),
            (4, 5, 14, 25, 31, 43),
        ),
        SIX_EXPERT_METHOD_ID: (
            (18, 29, 35, 40, 42, 46),
            (6, 12, 18, 24, 27, 35),
            (16, 20, 25, 35, 39, 48),
            (4, 5, 14, 25, 31, 43),
            (2, 30, 34, 42, 44, 45),
            (10, 19, 39, 42, 46, 49),
        ),
    }

    for method_id, portfolio in expected.items():
        result = generate_legacy_checkpoint_native_wave55_portfolio(
            _request(method_id)
        )
        assert result.tickets == portfolio
        assert result.metadata.candidate_k is None
        assert 49 in result.metadata.source_candidate_k_values
        assert result.metadata.native_ticket_count == len(portfolio)
        assert result.metadata.combination_count is None
        assert result.metadata.model_context_draw_count == 15
        assert result.metadata.imported_comparators_excluded == ()
    assert (
        generate_legacy_checkpoint_native_wave55_portfolio(
            _request(ORTHOGONAL_METHOD_ID)
        ).metadata.randomness_used
        is False
    )
    assert (
        generate_legacy_checkpoint_native_wave55_portfolio(
            _request(SIX_EXPERT_METHOD_ID)
        ).metadata.randomness_used
        is True
    )


def test_wave55_rejects_pre_checkpoint_and_wrong_model_context() -> None:
    with pytest.raises(
        LegacyCheckpointNativeWave55SourceError,
        match="TARGET_NOT_STRICTLY_AFTER",
    ):
        generate_legacy_checkpoint_native_wave55_portfolio(
            _request(
                ORTHOGONAL_METHOD_ID,
                target_date=date(2026, 2, 24),
            )
        )

    changed = list(_history())
    changed[-1] = LegacyHistoryDraw(
        draw_number="115000025",
        numbers=(1, 2, 3, 4, 5, 6),
    )
    with pytest.raises(
        LegacyCheckpointNativeWave55SourceError,
        match="FROZEN_MODEL_CONTEXT_IDENTITY_MISMATCH",
    ):
        generate_legacy_checkpoint_native_wave55_portfolio(
            _request(
                ORTHOGONAL_METHOD_ID,
                history=tuple(changed),
            )
        )
