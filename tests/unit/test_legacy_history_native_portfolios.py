"""Frozen-source parity tests for four history-native BIG_LOTTO methods."""

from __future__ import annotations

import random
from typing import cast

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    EXHAUSTIVE_AUDIT_METHOD_ID,
    OPTIMIZED_ENSEMBLE_METHOD_ID,
    QUICK_ML_METHOD_ID,
    QUICK_ML_PATTERN_SLICE_REASON,
    SOCIAL_WISDOM_METHOD_ID,
    LegacyHistoryDraw,
    LegacyHistoryNativeError,
    LegacyHistoryNativeRequest,
    LegacyHistoryNativeSourceError,
    generate_legacy_history_native_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket


def _history(count: int = 60) -> tuple[LegacyHistoryDraw, ...]:
    rng = random.Random(20260728)
    return tuple(
        LegacyHistoryDraw(
            draw_number=str(index + 1),
            numbers=cast(
                Ticket,
                tuple(sorted(rng.sample(range(1, 50), 6))),
            ),
        )
        for index in range(count)
    )


@pytest.mark.parametrize(
    ("method_id", "history_count", "expected"),
    (
        (
            OPTIMIZED_ENSEMBLE_METHOD_ID,
            60,
            ((10, 15, 29, 37, 38, 42),),
        ),
        (
            SOCIAL_WISDOM_METHOD_ID,
            60,
            (
                (12, 35, 36, 44, 47, 49),
                (2, 4, 8, 34, 40, 46),
                (3, 4, 38, 45, 46, 47),
                (1, 15, 17, 18, 40, 48),
                (24, 27, 33, 39, 40, 44),
                (30, 32, 37, 43, 46, 47),
                (14, 15, 21, 31, 33, 35),
                (1, 2, 12, 22, 25, 44),
            ),
        ),
        (
            QUICK_ML_METHOD_ID,
            4,
            (
                (7, 29, 31, 37, 41, 49),
                (2, 4, 8, 10, 38, 49),
            ),
        ),
        (
            EXHAUSTIVE_AUDIT_METHOD_ID,
            50,
            (
                (16, 22, 23, 28, 31, 32),
                (2, 5, 20, 36, 46, 47),
                (1, 4, 10, 15, 17, 30),
            ),
        ),
    ),
)
def test_port_matches_frozen_source_fixture(
    method_id: str,
    history_count: int,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    result = generate_legacy_history_native_portfolio(
        LegacyHistoryNativeRequest(
            legacy_method_id=method_id,
            target_draw_number="fixture-target",
            history=_history(history_count),
        )
    )

    assert result.tickets == expected
    assert result.metadata.history_draw_count == history_count
    assert result.metadata.history_cutoff_draw_number == str(history_count)
    assert result.metadata.native_ticket_count == len(expected)
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_generation_is_target_stable_and_outcome_blind() -> None:
    request = LegacyHistoryNativeRequest(
        legacy_method_id=SOCIAL_WISDOM_METHOD_ID,
        target_draw_number="target-1",
        history=_history(),
    )
    first = generate_legacy_history_native_portfolio(request)
    second = generate_legacy_history_native_portfolio(request)
    another_target = generate_legacy_history_native_portfolio(
        LegacyHistoryNativeRequest(
            legacy_method_id=SOCIAL_WISDOM_METHOD_ID,
            target_draw_number="target-2",
            history=request.history,
        )
    )

    assert first == second
    assert first.tickets != another_target.tickets
    assert "winning" not in first.metadata.seed_material.lower()


def test_quick_ml_preserves_frozen_pattern_slice_failure() -> None:
    with pytest.raises(
        LegacyHistoryNativeSourceError,
        match=QUICK_ML_PATTERN_SLICE_REASON,
    ) as captured:
        generate_legacy_history_native_portfolio(
            LegacyHistoryNativeRequest(
                legacy_method_id=QUICK_ML_METHOD_ID,
                target_draw_number="fixture-target",
                history=_history(5),
            )
        )

    assert captured.value.reason_code == QUICK_ML_PATTERN_SLICE_REASON


def test_exhaustive_audit_requires_its_frozen_window() -> None:
    with pytest.raises(LegacyHistoryNativeError, match="at least 50"):
        generate_legacy_history_native_portfolio(
            LegacyHistoryNativeRequest(
                legacy_method_id=EXHAUSTIVE_AUDIT_METHOD_ID,
                target_draw_number="fixture-target",
                history=_history(49),
            )
        )


def test_invalid_method_and_empty_history_fail_explicitly() -> None:
    with pytest.raises(LegacyHistoryNativeError, match="outside"):
        generate_legacy_history_native_portfolio(
            LegacyHistoryNativeRequest(
                legacy_method_id="missing",
                target_draw_number="fixture-target",
                history=_history(1),
            )
        )
    with pytest.raises(LegacyHistoryNativeError, match="must not be empty"):
        generate_legacy_history_native_portfolio(
            LegacyHistoryNativeRequest(
                legacy_method_id=OPTIMIZED_ENSEMBLE_METHOD_ID,
                target_draw_number="fixture-target",
                history=(),
            )
        )
