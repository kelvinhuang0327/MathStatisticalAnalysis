"""Frozen-source parity tests for the sixth source-native wave."""

from __future__ import annotations

import random
from typing import cast

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave6 import (
    COMPARE_RANDOM_METHOD_ID,
    ECHO_PHASE2_METHOD_ID,
    HOT_STOP_REBOUND_METHOD_ID,
    SBP_RANDOM_METHOD_ID,
    LegacySourceNativeWave6Error,
    LegacySourceNativeWave6Request,
    generate_legacy_source_native_wave6_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket


def _history(count: int = 220) -> tuple[LegacyHistoryDraw, ...]:
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
            ECHO_PHASE2_METHOD_ID,
            (
                (5, 8, 24, 25, 37, 43),
                (13, 20, 22, 28, 35, 47),
                (5, 8, 24, 25, 37, 43),
                (13, 20, 22, 28, 35, 47),
                (6, 16, 19, 23, 44, 46),
            ),
        ),
        (
            HOT_STOP_REBOUND_METHOD_ID,
            (
                (20, 21, 28, 29, 33, 44),
                (20, 21, 28, 29, 33, 44),
                (8, 10, 33, 36, 43, 44),
                (8, 10, 33, 36, 43, 44),
                (8, 10, 33, 36, 43, 44),
                (8, 10, 33, 36, 43, 44),
                (8, 10, 33, 36, 43, 44),
                (8, 10, 33, 36, 43, 44),
            ),
        ),
        (
            COMPARE_RANDOM_METHOD_ID,
            (
                (7, 13, 14, 38, 40, 41),
                (3, 15, 31, 42, 43, 49),
                (4, 8, 9, 13, 14, 19),
                (1, 2, 15, 23, 37, 49),
                (11, 22, 26, 27, 31, 49),
            ),
        ),
        (
            SBP_RANDOM_METHOD_ID,
            (
                (12, 20, 26, 31, 33, 43),
                (14, 16, 28, 37, 44, 49),
                (3, 10, 16, 23, 29, 44),
            ),
        ),
    ),
)
def test_wave6_port_matches_frozen_source_call_order_fixture(
    method_id: str,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    result = generate_legacy_source_native_wave6_portfolio(
        LegacySourceNativeWave6Request(
            legacy_method_id=method_id,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert result.tickets == expected
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave6_preserves_configuration_duplicates_and_counts() -> None:
    echo = generate_legacy_source_native_wave6_portfolio(
        LegacySourceNativeWave6Request(
            legacy_method_id=ECHO_PHASE2_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )
    hot_stop = generate_legacy_source_native_wave6_portfolio(
        LegacySourceNativeWave6Request(
            legacy_method_id=HOT_STOP_REBOUND_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert echo.tickets[:2] == echo.tickets[2:4]
    assert echo.metadata.native_duplicate_ticket_count == 2
    assert len(echo.metadata.source_combination_members) == 2
    assert hot_stop.metadata.native_duplicate_ticket_count == 6
    assert len(hot_stop.metadata.source_combination_members) == 8


@pytest.mark.parametrize(
    ("method_id", "uses_randomness"),
    (
        (ECHO_PHASE2_METHOD_ID, False),
        (HOT_STOP_REBOUND_METHOD_ID, False),
        (COMPARE_RANDOM_METHOD_ID, True),
        (SBP_RANDOM_METHOD_ID, True),
    ),
)
def test_wave6_is_reproducible_and_outcome_blind(
    method_id: str,
    uses_randomness: bool,
) -> None:
    first = generate_legacy_source_native_wave6_portfolio(
        LegacySourceNativeWave6Request(
            legacy_method_id=method_id,
            target_draw_number="first-target",
            history=_history(),
        )
    )
    repeat = generate_legacy_source_native_wave6_portfolio(
        LegacySourceNativeWave6Request(
            legacy_method_id=method_id,
            target_draw_number="first-target",
            history=_history(),
        )
    )
    changed_target = generate_legacy_source_native_wave6_portfolio(
        LegacySourceNativeWave6Request(
            legacy_method_id=method_id,
            target_draw_number="second-target",
            history=_history(),
        )
    )

    assert first == repeat
    assert first.metadata.randomness_used is uses_randomness
    if uses_randomness:
        assert first.tickets != changed_target.tickets
    else:
        assert first.tickets == changed_target.tickets


@pytest.mark.parametrize(
    ("method_id", "history_count", "minimum"),
    (
        (ECHO_PHASE2_METHOD_ID, 0, 1),
        (HOT_STOP_REBOUND_METHOD_ID, 199, 200),
        (COMPARE_RANDOM_METHOD_ID, 0, 1),
        (SBP_RANDOM_METHOD_ID, 0, 1),
    ),
)
def test_wave6_requires_source_minimum_history(
    method_id: str,
    history_count: int,
    minimum: int,
) -> None:
    with pytest.raises(
        LegacySourceNativeWave6Error,
        match=f"at least {minimum}",
    ):
        generate_legacy_source_native_wave6_portfolio(
            LegacySourceNativeWave6Request(
                legacy_method_id=method_id,
                target_draw_number="fixture-target",
                history=_history(history_count),
            )
        )
