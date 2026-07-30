"""Unit contracts for the wave-61 closed-result five-bet ledger."""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from lottolab.application.legacy_five_bet_native_portfolios_wave61 import (
    OUTSIDE_HORIZON_REASON,
    PINNED_DATASET_SHA256,
    LegacyFiveBetNativeWave61Request,
    LegacyFiveBetNativeWave61SourceError,
    generate_legacy_five_bet_native_wave61_portfolio,
    load_legacy_five_bet_native_wave61_ledger_for_verification,
)


def test_wave61_first_target_is_outside_source_horizons() -> None:
    with pytest.raises(
        LegacyFiveBetNativeWave61SourceError,
        match=OUTSIDE_HORIZON_REASON,
    ):
        generate_legacy_five_bet_native_wave61_portfolio(
            LegacyFiveBetNativeWave61Request(
                target_draw_number="96000001",
                target_draw_date=date(2007, 1, 2),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )


def test_wave61_ledger_preserves_partial_coverage_and_variable_counts() -> None:
    ledger = load_legacy_five_bet_native_wave61_ledger_for_verification()
    native_counts = Counter(
        len(portfolio)
        for portfolio in ledger.tickets
        if portfolio is not None
    )
    configuration_counts = Counter(
        count
        for count in ledger.local_configuration_count
        if count is not None
    )
    reason_counts = Counter(ledger.closed_reason)

    assert len(ledger.targets) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert native_counts == {15: 49, 25: 137}
    assert configuration_counts == {3: 49, 5: 137}
    assert reason_counts[OUTSIDE_HORIZON_REASON] == 1949
    assert reason_counts[None] == 186
    assert sum(
        count
        for reason, count in reason_counts.items()
        if isinstance(reason, str)
        and reason.startswith("FROZEN_SOURCE_EXECUTION_ERROR:")
    ) == 14
