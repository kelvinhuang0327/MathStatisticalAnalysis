"""Unit contracts for the wave-63 advanced-method frozen ledger."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date

import pytest

from lottolab.application.legacy_advanced_methods_native_portfolios_wave63 import (
    FIRST_TARGET_REASON,
    METHOD_ORDER,
    PINNED_DATASET_SHA256,
    LegacyAdvancedMethodsNativeWave63Request,
    LegacyAdvancedMethodsNativeWave63SourceError,
    generate_legacy_advanced_methods_native_wave63_portfolio,
    load_legacy_advanced_methods_native_wave63_ledger_for_verification,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)

EXPECTED_TICKET_SEQUENCE_SHA256 = (
    "7a1927a300c96155ce9914344fa0247911ea2c3f0dda55ec84192766a2b6ed5f"
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_wave63_first_target_is_explicitly_closed() -> None:
    with pytest.raises(
        LegacyAdvancedMethodsNativeWave63SourceError,
        match=FIRST_TARGET_REASON,
    ):
        generate_legacy_advanced_methods_native_wave63_portfolio(
            LegacyAdvancedMethodsNativeWave63Request(
                target_draw_number="96000001",
                target_draw_date=date(2007, 1, 2),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )


def test_wave63_ledger_preserves_counts_order_duplicates_and_sequence() -> None:
    ledger = (
        load_legacy_advanced_methods_native_wave63_ledger_for_verification()
    )

    assert len(ledger.targets) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert Counter(
        len(portfolio)
        for portfolio in ledger.tickets
        if portfolio is not None
    ) == {25: 2148}
    assert Counter(
        len(portfolio) - len(set(portfolio))
        for portfolio in ledger.tickets
        if portfolio is not None
    ) == {20: 2133, 21: 8, 22: 6, 23: 1}
    assert Counter(ledger.closed_reason) == {
        FIRST_TARGET_REASON: 1,
        None: 2148,
    }
    assert Counter(
        value
        for value in ledger.local_configuration_count
        if value is not None
    ) == {10: 2148}
    assert (
        hashlib.sha256(_canonical_bytes(ledger.tickets)).hexdigest()
        == EXPECTED_TICKET_SEQUENCE_SHA256
    )


def test_wave63_replays_second_target_with_distinct_native_semantics() -> None:
    ledger = (
        load_legacy_advanced_methods_native_wave63_ledger_for_verification()
    )
    result = generate_legacy_advanced_methods_native_wave63_portfolio(
        LegacyAdvancedMethodsNativeWave63Request(
            target_draw_number="96000002",
            target_draw_date=date(2007, 1, 5),
            history=(
                LegacyHistoryDraw(
                    draw_number="96000001",
                    numbers=(13, 21, 23, 27, 31, 49),
                ),
            ),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets[1]
    assert len(result.tickets) == 25
    assert len(result.tickets) - len(set(result.tickets)) == 23
    assert result.metadata.candidate_k is None
    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.local_configuration_count == 10
    assert result.metadata.combination_count is None
    assert result.metadata.native_ticket_count == 25
    assert result.metadata.local_method_order == METHOD_ORDER
    assert result.metadata.source_history_input_draw_count == 1
    assert result.metadata.source_random_baseline_excluded is True
    assert result.metadata.target_stable_reinstantiation is True


def test_wave63_rejects_non_full_prefix_context() -> None:
    with pytest.raises(
        LegacyAdvancedMethodsNativeWave63SourceError,
        match="FROZEN_WAVE63_FULL_PREFIX_CONTEXT_MISMATCH",
    ):
        generate_legacy_advanced_methods_native_wave63_portfolio(
            LegacyAdvancedMethodsNativeWave63Request(
                target_draw_number="96000002",
                target_draw_date=date(2007, 1, 5),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
