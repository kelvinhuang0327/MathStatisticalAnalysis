"""Frozen-source parity tests for history-native wave three."""

from __future__ import annotations

import random
from typing import cast

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_history_native_portfolios_wave3 import (
    CORE_SATELLITE_METHOD_ID,
    NEGATIVE_SELECTION_METHOD_ID,
    QUANTUM_RANDOM_METHOD_ID,
    LegacyHistoryNativeWave3Error,
    LegacyHistoryNativeWave3Request,
    generate_legacy_history_native_wave3_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket


def _history(count: int = 120) -> tuple[LegacyHistoryDraw, ...]:
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
            CORE_SATELLITE_METHOD_ID,
            (
                (3, 7, 10, 14, 18, 21),
                (3, 7, 10, 36, 38, 39),
                (1, 3, 5, 7, 8, 10),
                (6, 9, 12, 34, 40, 48),
                (9, 13, 33, 34, 40, 46),
                (2, 9, 11, 25, 34, 40),
                (4, 19, 24, 28, 31, 45),
                (15, 16, 19, 20, 24, 28),
                (19, 22, 24, 27, 28, 30),
                (9, 19, 24, 28, 34, 40),
                (6, 9, 19, 31, 40, 48),
                (4, 9, 12, 19, 40, 45),
            ),
        ),
        (
            NEGATIVE_SELECTION_METHOD_ID,
            (
                (16, 18, 24, 31, 42, 45),
                (7, 17, 20, 32, 46, 49),
                (8, 15, 19, 26, 30, 35),
                (4, 5, 9, 23, 43, 44),
                (6, 17, 19, 35, 36, 48),
                (5, 7, 26, 32, 41, 42),
                (11, 12, 15, 34, 38, 40),
                (19, 21, 26, 39, 43, 48),
            ),
        ),
        (
            QUANTUM_RANDOM_METHOD_ID,
            (
                (7, 8, 16, 24, 27, 49),
                (2, 17, 25, 34, 42, 47),
                (21, 23, 26, 35, 38, 45),
                (4, 13, 19, 20, 30, 37),
                (5, 10, 31, 33, 36, 44),
                (6, 28, 29, 39, 40, 48),
                (9, 11, 22, 24, 28, 46),
                (20, 28, 32, 41, 43, 49),
            ),
        ),
    ),
)
def test_wave3_port_matches_frozen_source_fixture(
    method_id: str,
    expected: tuple[Ticket, ...],
) -> None:
    result = generate_legacy_history_native_wave3_portfolio(
        LegacyHistoryNativeWave3Request(
            legacy_method_id=method_id,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert result.tickets == expected
    assert result.metadata.history_draw_count == 120
    assert result.metadata.history_cutoff_draw_number == "120"
    assert result.metadata.native_ticket_count == len(expected)
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave3_combination_semantics_remain_separate() -> None:
    core = generate_legacy_history_native_wave3_portfolio(
        LegacyHistoryNativeWave3Request(
            legacy_method_id=CORE_SATELLITE_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )
    negative = generate_legacy_history_native_wave3_portfolio(
        LegacyHistoryNativeWave3Request(
            legacy_method_id=NEGATIVE_SELECTION_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert len(core.tickets) == 12
    assert len(core.metadata.source_combination_members) == 4
    assert core.metadata.source_candidate_ticket_counts == ()
    assert len(negative.tickets) == 8
    assert len(negative.metadata.source_combination_members) == 2
    assert negative.metadata.source_candidate_ticket_counts == (400, 200)


@pytest.mark.parametrize(
    "method_id",
    (
        CORE_SATELLITE_METHOD_ID,
        NEGATIVE_SELECTION_METHOD_ID,
        QUANTUM_RANDOM_METHOD_ID,
    ),
)
def test_wave3_target_stable_and_outcome_blind(method_id: str) -> None:
    request = LegacyHistoryNativeWave3Request(
        legacy_method_id=method_id,
        target_draw_number="fixture-target",
        history=_history(),
    )

    first = generate_legacy_history_native_wave3_portfolio(request)
    second = generate_legacy_history_native_wave3_portfolio(request)
    changed_target = generate_legacy_history_native_wave3_portfolio(
        LegacyHistoryNativeWave3Request(
            legacy_method_id=method_id,
            target_draw_number="different-target",
            history=_history(),
        )
    )

    assert first == second
    if first.metadata.randomness_used:
        assert first.tickets != changed_target.tickets
    else:
        assert first.tickets == changed_target.tickets


def test_wave3_requires_strictly_prior_history() -> None:
    with pytest.raises(LegacyHistoryNativeWave3Error, match="at least 1"):
        generate_legacy_history_native_wave3_portfolio(
            LegacyHistoryNativeWave3Request(
                legacy_method_id=CORE_SATELLITE_METHOD_ID,
                target_draw_number="fixture-target",
                history=(),
            )
        )
