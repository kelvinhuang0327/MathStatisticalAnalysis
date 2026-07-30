"""Unit contracts for the wave-64 frozen XGBoost ledger."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    CLOSED_REASON,
    PINNED_DATASET_SHA256,
    PROBABILITY_SEQUENCE_SHA256,
    TICKET_SEQUENCE_SHA256,
    LegacyXGBoostNativeWave64Request,
    LegacyXGBoostNativeWave64SourceError,
    generate_legacy_xgboost_native_wave64_portfolio,
    load_legacy_xgboost_native_wave64_ledger_for_verification,
)

_FIRST_15 = (
    ("96000001", (13, 21, 23, 27, 31, 49)),
    ("96000002", (12, 19, 23, 42, 44, 48)),
    ("96000003", (26, 28, 35, 39, 44, 45)),
    ("96000004", (10, 16, 26, 28, 31, 33)),
    ("96000005", (13, 28, 33, 38, 43, 48)),
    ("96000006", (6, 26, 27, 44, 45, 46)),
    ("96000007", (6, 7, 15, 31, 36, 44)),
    ("96000008", (8, 13, 18, 26, 34, 36)),
    ("96000009", (6, 18, 26, 39, 42, 45)),
    ("96000010", (7, 8, 10, 12, 47, 48)),
    ("96000011", (12, 16, 26, 32, 41, 48)),
    ("96000012", (7, 28, 30, 41, 45, 48)),
    ("96000013", (2, 8, 25, 39, 43, 46)),
    ("96000014", (18, 19, 27, 34, 44, 48)),
    ("96000015", (1, 13, 19, 33, 38, 45)),
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _history() -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=draw_number,
            numbers=numbers,
        )
        for draw_number, numbers in _FIRST_15
    )


def test_wave64_first_target_is_explicitly_closed() -> None:
    with pytest.raises(
        LegacyXGBoostNativeWave64SourceError,
        match=CLOSED_REASON,
    ):
        generate_legacy_xgboost_native_wave64_portfolio(
            LegacyXGBoostNativeWave64Request(
                target_draw_number="96000001",
                target_draw_date=date(2007, 1, 2),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )


def test_wave64_ledger_preserves_boundary_ticket_and_probability_sequences() -> None:
    ledger = load_legacy_xgboost_native_wave64_ledger_for_verification()

    assert len(ledger.targets) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert Counter(
        len(portfolio)
        for portfolio in ledger.tickets
        if portfolio is not None
    ) == {1: 2134}
    assert Counter(ledger.closed_reason) == {
        CLOSED_REASON: 15,
        None: 2134,
    }
    assert (
        hashlib.sha256(_canonical_bytes(ledger.tickets)).hexdigest()
        == TICKET_SEQUENCE_SHA256
    )
    assert (
        hashlib.sha256(_canonical_bytes(ledger.probabilities)).hexdigest()
        == PROBABILITY_SEQUENCE_SHA256
    )


def test_wave64_replays_first_executable_target_with_distinct_semantics() -> None:
    ledger = load_legacy_xgboost_native_wave64_ledger_for_verification()
    result = generate_legacy_xgboost_native_wave64_portfolio(
        LegacyXGBoostNativeWave64Request(
            target_draw_number="96000016",
            target_draw_date=date(2007, 2, 23),
            history=_history(),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == ledger.tickets[15]
    assert result.tickets == ((6, 18, 26, 44, 45, 48),)
    assert result.metadata.candidate_k is None
    assert result.metadata.source_candidate_k_values == (49,)
    assert result.metadata.local_configuration_count == 1
    assert result.metadata.combination_count is None
    assert result.metadata.native_ticket_count == 1
    assert result.metadata.native_duplicate_ticket_count == 0
    assert result.metadata.model_label_count == 49
    assert result.metadata.estimators_per_label == 50
    assert result.metadata.source_random_state_explicit is False
    assert result.metadata.repeatability_parity_passed is True
    assert result.metadata.thread_count_parity_passed is True
    assert len(result.metadata.selected_probabilities) == 6


def test_wave64_rejects_non_full_prefix_context() -> None:
    altered = list(_history())
    altered[-1] = LegacyHistoryDraw(
        draw_number="96000015",
        numbers=(1, 2, 3, 4, 5, 6),
    )
    with pytest.raises(
        LegacyXGBoostNativeWave64SourceError,
        match="FROZEN_WAVE64_FULL_PREFIX_CONTEXT_MISMATCH",
    ):
        generate_legacy_xgboost_native_wave64_portfolio(
            LegacyXGBoostNativeWave64Request(
                target_draw_number="96000016",
                target_draw_date=date(2007, 2, 23),
                history=tuple(altered),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
