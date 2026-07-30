"""Unit contracts for the wave-58 dual/seeded frozen ticket ledger."""

from __future__ import annotations

from datetime import date

import pytest

from lottolab.application.legacy_dual_seeded_native_portfolios_wave58 import (
    ENHANCED_DUAL_METHOD_ID,
    PINNED_DATASET_SHA256,
    SEEDED_V6_METHOD_ID,
    LegacyDualSeededNativeWave58Request,
    LegacyDualSeededNativeWave58SourceError,
    generate_legacy_dual_seeded_native_wave58_portfolio,
    load_legacy_dual_seeded_native_wave58_ledger_for_verification,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)

FIRST_DRAW = LegacyHistoryDraw(
    draw_number="96000001",
    numbers=(13, 21, 23, 27, 31, 49),
)


def _request(
    *,
    method_id: str,
    target_draw_number: str = "96000001",
    target_draw_date: date = date(2007, 1, 2),
    history: tuple[LegacyHistoryDraw, ...] = (),
) -> LegacyDualSeededNativeWave58Request:
    return LegacyDualSeededNativeWave58Request(
        legacy_method_id=method_id,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        history=history,
        dataset_sha256=PINNED_DATASET_SHA256,
    )


@pytest.mark.parametrize(
    "method_id",
    [ENHANCED_DUAL_METHOD_ID, SEEDED_V6_METHOD_ID],
)
def test_wave58_first_target_is_explicitly_closed(
    method_id: str,
) -> None:
    with pytest.raises(
        LegacyDualSeededNativeWave58SourceError,
        match="AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM",
    ):
        generate_legacy_dual_seeded_native_wave58_portfolio(
            _request(method_id=method_id)
        )


def test_wave58_replays_seeded_v6_second_strict_prefix() -> None:
    result = generate_legacy_dual_seeded_native_wave58_portfolio(
        _request(
            method_id=SEEDED_V6_METHOD_ID,
            target_draw_number="96000002",
            target_draw_date=date(2007, 1, 5),
            history=(FIRST_DRAW,),
        )
    )

    assert result.tickets == (
        (13, 21, 23, 27, 31, 49),
        (1, 2, 3, 4, 5, 6),
        (1, 9, 11, 13, 19, 39),
    )
    assert result.metadata.history_draw_count == 1
    assert result.metadata.history_first_draw_number == "96000001"
    assert result.metadata.history_cutoff_draw_number == "96000001"
    assert result.metadata.source_history_order == "RECENT_FIRST"
    assert result.metadata.seed_integer == 42
    assert result.metadata.seed_material == (
        "random.seed(42);numpy.random.seed(42)"
    )
    assert result.metadata.candidate_k is None
    assert result.metadata.source_candidate_k_values == (12, 20, 49)
    assert result.metadata.native_ticket_count == 3
    assert result.metadata.combination_count is None
    assert result.metadata.randomness_used is True


def test_wave58_rejects_non_full_prefix_context() -> None:
    with pytest.raises(
        LegacyDualSeededNativeWave58SourceError,
        match="FROZEN_WAVE58_FULL_PREFIX_CONTEXT_MISMATCH",
    ):
        generate_legacy_dual_seeded_native_wave58_portfolio(
            _request(
                method_id=SEEDED_V6_METHOD_ID,
                target_draw_number="96000002",
                target_draw_date=date(2007, 1, 5),
            )
        )


def test_wave58_ledger_covers_every_target_and_method() -> None:
    ledger = (
        load_legacy_dual_seeded_native_wave58_ledger_for_verification()
    )

    assert len(ledger.targets) == 2149
    assert len(set(ledger.targets)) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert len(ledger.context_sha256) == 2149
    assert set(ledger.tickets_by_method) == {
        ENHANCED_DUAL_METHOD_ID,
        SEEDED_V6_METHOD_ID,
    }
