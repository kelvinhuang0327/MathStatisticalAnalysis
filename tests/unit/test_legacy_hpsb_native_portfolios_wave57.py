"""Unit contracts for the wave-57 frozen HPSB-V2 ticket ledger."""

from __future__ import annotations

from datetime import date

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_hpsb_native_portfolios_wave57 import (
    ENSEMBLE_ALIAS_METHOD_ID,
    HPSB_METHOD_ID,
    PINNED_DATASET_SHA256,
    LegacyHpsbNativeWave57Error,
    LegacyHpsbNativeWave57Request,
    LegacyHpsbNativeWave57SourceError,
    generate_legacy_hpsb_native_wave57_portfolio,
    load_legacy_hpsb_native_wave57_ledger_for_verification,
)

FIRST_DRAW = LegacyHistoryDraw(
    draw_number="96000001",
    numbers=(13, 21, 23, 27, 31, 49),
)


def _request(
    *,
    target_draw_number: str = "96000001",
    target_draw_date: date = date(2007, 1, 2),
    history: tuple[LegacyHistoryDraw, ...] = (),
    method_id: str = HPSB_METHOD_ID,
) -> LegacyHpsbNativeWave57Request:
    return LegacyHpsbNativeWave57Request(
        legacy_method_id=method_id,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        history=history,
        dataset_sha256=PINNED_DATASET_SHA256,
    )


def test_wave57_replays_first_empty_history_hpsb_v2_ticket() -> None:
    result = generate_legacy_hpsb_native_wave57_portfolio(_request())

    assert result.tickets == ((1, 2, 3, 21, 25, 27),)
    assert result.metadata.history_draw_count == 0
    assert result.metadata.history_first_draw_number is None
    assert result.metadata.history_cutoff_draw_number is None
    assert result.metadata.seed_integer == 0
    assert result.metadata.seed_material == "random.seed(0)"
    assert result.metadata.candidate_k is None
    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.native_ticket_count == 1
    assert result.metadata.combination_count is None
    assert result.metadata.randomness_used is True
    assert result.metadata.imported_comparators_excluded == ()


def test_wave57_replays_second_strict_prefix_ticket() -> None:
    result = generate_legacy_hpsb_native_wave57_portfolio(
        _request(
            target_draw_number="96000002",
            target_draw_date=date(2007, 1, 5),
            history=(FIRST_DRAW,),
        )
    )

    assert result.tickets == ((3, 13, 21, 23, 27, 49),)
    assert result.metadata.history_draw_count == 1
    assert result.metadata.history_first_draw_number == "96000001"
    assert result.metadata.history_cutoff_draw_number == "96000001"
    assert result.metadata.context_draw_count == 1
    assert result.metadata.seed_integer == 1


def test_wave57_rejects_wrong_prefix_and_noncanonical_alias_execution() -> None:
    with pytest.raises(
        LegacyHpsbNativeWave57SourceError,
        match="FULL_PREFIX_CONTEXT_MISMATCH",
    ):
        generate_legacy_hpsb_native_wave57_portfolio(
            _request(
                target_draw_number="96000002",
                target_draw_date=date(2007, 1, 5),
            )
        )

    with pytest.raises(
        LegacyHpsbNativeWave57Error,
        match="outside the executable",
    ):
        generate_legacy_hpsb_native_wave57_portfolio(
            _request(method_id=ENSEMBLE_ALIAS_METHOD_ID)
        )


def test_wave57_ledger_covers_every_target_once() -> None:
    ledger = load_legacy_hpsb_native_wave57_ledger_for_verification()

    assert len(ledger.targets) == 2149
    assert len(set(ledger.targets)) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert len(ledger.context_sha256) == 2149
    assert set(ledger.tickets_by_method) == {HPSB_METHOD_ID}
