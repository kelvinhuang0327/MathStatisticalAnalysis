"""Frozen-source parity tests for history-native wave two."""

from __future__ import annotations

import random
from typing import cast

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
    LegacyNumpyRandomState,
)
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    ANTI_CONSENSUS_METHOD_ID,
    CONCENTRATED_POOL_METHOD_ID,
    CONSTRAINT_FILTER_METHOD_ID,
    COOCCURRENCE_GRAPH_METHOD_ID,
    LegacyHistoryNativeWave2Error,
    LegacyHistoryNativeWave2Request,
    generate_legacy_history_native_wave2_portfolio,
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
            ANTI_CONSENSUS_METHOD_ID,
            (
                (4, 19, 32, 40, 45, 47),
                (13, 31, 34, 36, 39, 48),
                (7, 13, 39, 42, 46, 48),
                (4, 14, 32, 35, 46, 48),
                (36, 43, 44, 45, 47, 49),
                (35, 37, 38, 43, 45, 49),
            ),
        ),
        (
            CONSTRAINT_FILTER_METHOD_ID,
            (
                (5, 11, 22, 35, 40, 42),
                (3, 7, 21, 36, 39, 48),
            ),
        ),
        (
            COOCCURRENCE_GRAPH_METHOD_ID,
            (
                (19, 33, 35, 40, 41, 48),
                (1, 2, 3, 4, 5, 6),
                (6, 9, 11, 35, 43, 48),
                (9, 14, 22, 40, 46, 49),
            ),
        ),
        (
            CONCENTRATED_POOL_METHOD_ID,
            (
                (9, 12, 13, 25, 33, 40),
                (14, 23, 29, 35, 39, 42),
            ),
        ),
    ),
)
def test_port_matches_frozen_source_fixture(
    method_id: str,
    expected: tuple[Ticket, ...],
) -> None:
    result = generate_legacy_history_native_wave2_portfolio(
        LegacyHistoryNativeWave2Request(
            legacy_method_id=method_id,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert result.tickets == expected
    assert result.metadata.history_draw_count == 120
    assert result.metadata.history_cutoff_draw_number == "120"
    assert result.metadata.native_ticket_count == len(expected)
    assert result.metadata.combination_count is None


def test_candidate_k_stays_distinct_from_native_ticket_count() -> None:
    graph = generate_legacy_history_native_wave2_portfolio(
        LegacyHistoryNativeWave2Request(
            legacy_method_id=COOCCURRENCE_GRAPH_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )
    concentrated = generate_legacy_history_native_wave2_portfolio(
        LegacyHistoryNativeWave2Request(
            legacy_method_id=CONCENTRATED_POOL_METHOD_ID,
            target_draw_number="fixture-target",
            history=_history(),
        )
    )

    assert graph.metadata.candidate_k is None
    assert graph.metadata.native_ticket_count == 4
    assert concentrated.metadata.candidate_k is None
    assert concentrated.metadata.native_ticket_count == 2


def test_graph_requires_frozen_benchmark_history_gate() -> None:
    with pytest.raises(LegacyHistoryNativeWave2Error, match="at least 100"):
        generate_legacy_history_native_wave2_portfolio(
            LegacyHistoryNativeWave2Request(
                legacy_method_id=COOCCURRENCE_GRAPH_METHOD_ID,
                target_draw_number="fixture-target",
                history=_history(99),
            )
        )


def test_generation_is_target_stable_and_outcome_blind() -> None:
    request = LegacyHistoryNativeWave2Request(
        legacy_method_id=CONSTRAINT_FILTER_METHOD_ID,
        target_draw_number="target-1",
        history=_history(),
    )
    first = generate_legacy_history_native_wave2_portfolio(request)
    second = generate_legacy_history_native_wave2_portfolio(request)
    another_target = generate_legacy_history_native_wave2_portfolio(
        LegacyHistoryNativeWave2Request(
            legacy_method_id=request.legacy_method_id,
            target_draw_number="target-2",
            history=request.history,
        )
    )

    assert first == second
    assert first.tickets != another_target.tickets
    assert "winning" not in first.metadata.seed_material.lower()


def test_legacy_numpy_choice_matches_pinned_fixtures() -> None:
    uniform = LegacyNumpyRandomState(42).choice_without_replacement(
        list(range(1, 50)),
        6,
    )
    probabilities = [float(index + 1) for index in range(49)]
    total = sum(probabilities)
    weighted = LegacyNumpyRandomState(42).choice_without_replacement(
        list(range(1, 50)),
        6,
        probabilities=[value / total for value in probabilities],
    )

    assert uniform == [14, 46, 48, 45, 18, 28]
    assert weighted == [30, 48, 42, 38, 20, 11]
