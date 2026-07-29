"""Frozen-source parity tests for the fifth history-native wave."""

from __future__ import annotations

import random
from typing import cast

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_history_native_portfolios_wave5 import (
    DIVERSIFIED_2BET_METHOD_ID,
    ECHO_2BET_METHOD_ID,
    MODERATE_SELECTION_METHOD_ID,
    LegacyHistoryNativeWave5Error,
    LegacyHistoryNativeWave5Request,
    generate_legacy_history_native_wave5_portfolio,
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
    ("method_id", "expected"),
    (
        (
            MODERATE_SELECTION_METHOD_ID,
            (
                (14, 22, 28, 29, 45, 48),
                (14, 28, 34, 43, 45, 48),
                (14, 22, 24, 28, 29, 45),
            ),
        ),
        (
            DIVERSIFIED_2BET_METHOD_ID,
            (
                (14, 28, 34, 43, 45, 48),
                (4, 22, 28, 29, 36, 45),
                (6, 9, 30, 32, 44, 45),
                (14, 28, 34, 43, 45, 48),
                (4, 22, 28, 29, 36, 45),
                (14, 28, 34, 43, 45, 48),
                (4, 22, 28, 29, 36, 45),
                (6, 9, 30, 32, 44, 45),
            ),
        ),
        (
            ECHO_2BET_METHOD_ID,
            (
                (19, 27, 33, 38, 48, 49),
                (5, 7, 8, 9, 12, 30),
            ),
        ),
    ),
)
def test_wave5_port_matches_frozen_source_fixture(
    method_id: str,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    result = generate_legacy_history_native_wave5_portfolio(
        LegacyHistoryNativeWave5Request(
            legacy_method_id=method_id,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert result.tickets == expected
    assert result.metadata.random_protocol == "NONE_DETERMINISTIC"
    assert result.metadata.randomness_used is False
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave5_preserves_configuration_order_and_duplicates() -> None:
    moderate = generate_legacy_history_native_wave5_portfolio(
        LegacyHistoryNativeWave5Request(
            legacy_method_id=MODERATE_SELECTION_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )
    diversified = generate_legacy_history_native_wave5_portfolio(
        LegacyHistoryNativeWave5Request(
            legacy_method_id=DIVERSIFIED_2BET_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert moderate.metadata.source_combination_members == (
        "moderate_selection_strategy:last_draw_penalty=0.15",
        "moderate_selection_2bet",
    )
    assert diversified.tickets[0:3] == diversified.tickets[5:8]
    assert diversified.tickets[3:5] == diversified.tickets[0:2]
    assert diversified.metadata.native_duplicate_ticket_count == 5


@pytest.mark.parametrize(
    "method_id",
    (
        MODERATE_SELECTION_METHOD_ID,
        DIVERSIFIED_2BET_METHOD_ID,
        ECHO_2BET_METHOD_ID,
    ),
)
def test_wave5_is_target_stable_and_outcome_blind(
    method_id: str,
) -> None:
    first = generate_legacy_history_native_wave5_portfolio(
        LegacyHistoryNativeWave5Request(
            legacy_method_id=method_id,
            target_draw_number="first-target",
            history=_history(),
        )
    )
    second = generate_legacy_history_native_wave5_portfolio(
        LegacyHistoryNativeWave5Request(
            legacy_method_id=method_id,
            target_draw_number="second-target",
            history=_history(),
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.seed_digest != second.metadata.seed_digest


@pytest.mark.parametrize(
    ("method_id", "history_count", "minimum"),
    (
        (MODERATE_SELECTION_METHOD_ID, 9, 10),
        (DIVERSIFIED_2BET_METHOD_ID, 29, 30),
        (ECHO_2BET_METHOD_ID, 0, 1),
    ),
)
def test_wave5_requires_frozen_source_minimum_history(
    method_id: str,
    history_count: int,
    minimum: int,
) -> None:
    with pytest.raises(
        LegacyHistoryNativeWave5Error,
        match=f"at least {minimum}",
    ):
        generate_legacy_history_native_wave5_portfolio(
            LegacyHistoryNativeWave5Request(
                legacy_method_id=method_id,
                target_draw_number="fixture-target",
                history=_history(history_count),
            )
        )
