"""Unit contracts for the wave-62 diversified frozen ledger."""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from lottolab.application.legacy_diversified_native_portfolios_wave62 import (
    BACKTEST_METHOD_ID,
    ENSEMBLE_METHOD_ID,
    PINNED_DATASET_SHA256,
    LegacyDiversifiedNativeWave62Request,
    LegacyDiversifiedNativeWave62SourceError,
    generate_legacy_diversified_native_wave62_portfolio,
    load_legacy_diversified_native_wave62_ledger_for_verification,
)


@pytest.mark.parametrize(
    ("method_id", "reason"),
    [
        (
            ENSEMBLE_METHOD_ID,
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM",
        ),
        (
            BACKTEST_METHOD_ID,
            "TARGET_OUTSIDE_FROZEN_SOURCE_MAIN_HORIZONS_150_AND_500",
        ),
    ],
)
def test_wave62_first_target_is_explicitly_closed(
    method_id: str,
    reason: str,
) -> None:
    with pytest.raises(
        LegacyDiversifiedNativeWave62SourceError,
        match=reason,
    ):
        generate_legacy_diversified_native_wave62_portfolio(
            LegacyDiversifiedNativeWave62Request(
                legacy_method_id=method_id,
                target_draw_number="96000001",
                target_draw_date=date(2007, 1, 2),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )


def test_wave62_ledger_preserves_horizons_counts_order_and_duplicates() -> None:
    ledger = (
        load_legacy_diversified_native_wave62_ledger_for_verification()
    )

    assert len(ledger.targets) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert set(ledger.tickets_by_method) == {
        ENSEMBLE_METHOD_ID,
        BACKTEST_METHOD_ID,
    }
    assert Counter(
        len(portfolio)
        for portfolio in ledger.tickets_by_method[ENSEMBLE_METHOD_ID]
        if portfolio is not None
    ) == {3: 2099}
    assert Counter(
        len(portfolio)
        for portfolio in ledger.tickets_by_method[BACKTEST_METHOD_ID]
        if portfolio is not None
    ) == {3: 350, 6: 150}
    assert Counter(
        len(portfolio) - len(set(portfolio))
        for portfolio in ledger.tickets_by_method[BACKTEST_METHOD_ID]
        if portfolio is not None
    ) == {0: 350, 1: 139, 2: 10, 3: 1}
    assert Counter(
        ledger.closed_reason_by_method[ENSEMBLE_METHOD_ID]
    ) == {
        "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM": 50,
        None: 2099,
    }
    assert Counter(
        ledger.closed_reason_by_method[BACKTEST_METHOD_ID]
    ) == {
        "TARGET_OUTSIDE_FROZEN_SOURCE_MAIN_HORIZONS_150_AND_500": 1649,
        None: 500,
    }
    assert Counter(
        value
        for value in ledger.configuration_count_by_method[
            BACKTEST_METHOD_ID
        ]
        if value is not None
    ) == {1: 350, 2: 150}


def test_wave62_rejects_non_full_prefix_context() -> None:
    ledger = (
        load_legacy_diversified_native_wave62_ledger_for_verification()
    )
    target_index = 50

    with pytest.raises(
        LegacyDiversifiedNativeWave62SourceError,
        match="FROZEN_WAVE62_FULL_PREFIX_CONTEXT_MISMATCH",
    ):
        generate_legacy_diversified_native_wave62_portfolio(
            LegacyDiversifiedNativeWave62Request(
                legacy_method_id=ENSEMBLE_METHOD_ID,
                target_draw_number=ledger.targets[target_index],
                target_draw_date=date(2007, 6, 22),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
