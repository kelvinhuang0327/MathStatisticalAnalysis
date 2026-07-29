"""Unit contracts for the ninth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave9 import (
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
    P0P1_UPGRADE_METHOD_ID,
    TRUE_ORTHOGONAL_METHOD_ID,
    LegacySourceNativeWave9Error,
    LegacySourceNativeWave9Request,
    generate_legacy_source_native_wave9_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    rows: list[LegacyHistoryDraw] = []
    for index in range(count):
        values = sorted(
            ((index * 7 + offset * 5) % 49) + 1
            for offset in range(6)
        )
        rows.append(
            LegacyHistoryDraw(
                draw_number=str(index + 1),
                numbers=(
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                ),
            )
        )
    return tuple(rows)


@pytest.mark.parametrize(
    ("method_id", "history_count", "expected_count"),
    (
        (CLUSTER_PIVOT_BENCHMARK_METHOD_ID, 240, 19),
        (TRUE_ORTHOGONAL_METHOD_ID, 240, 19),
        (P0P1_UPGRADE_METHOD_ID, 240, 10),
    ),
)
def test_wave9_preserves_native_ticket_count_and_order(
    method_id: str,
    history_count: int,
    expected_count: int,
) -> None:
    result = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )

    assert len(result.tickets) == expected_count
    assert result.metadata.native_ticket_count == expected_count
    assert result.metadata.history_cutoff_draw_number == str(history_count)
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        for ticket in result.tickets
    )


def test_wave9_preserves_source_configuration_counts() -> None:
    cluster_50 = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
            target_draw_number="51",
            history=_history(50),
        )
    )
    cluster_100 = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
            target_draw_number="101",
            history=_history(100),
        )
    )
    orthogonal = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=TRUE_ORTHOGONAL_METHOD_ID,
            target_draw_number="241",
            history=_history(240),
        )
    )

    assert cluster_50.metadata.source_candidate_ticket_counts == (
        1,
        2,
        3,
        4,
        2,
        2,
        3,
    )
    assert cluster_100.metadata.source_candidate_ticket_counts == (
        1,
        2,
        3,
        4,
        2,
        3,
        4,
    )
    assert orthogonal.metadata.source_candidate_ticket_counts == (
        1,
        1,
        1,
        1,
        2,
        3,
        4,
        3,
        3,
    )


def test_wave9_keeps_candidate_and_configuration_semantics_distinct() -> None:
    result = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=P0P1_UPGRADE_METHOD_ID,
            target_draw_number="241",
            history=_history(240),
        )
    )

    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert len(result.metadata.source_combination_members) == 4
    assert result.metadata.source_candidate_ticket_counts == (2, 2, 3, 3)
    assert result.metadata.source_candidate_k_values == (24, 15)
    assert result.metadata.source_sample_attempt_counts == (200, 200)


@pytest.mark.parametrize(
    ("method_id", "minimum"),
    (
        (CLUSTER_PIVOT_BENCHMARK_METHOD_ID, 50),
        (TRUE_ORTHOGONAL_METHOD_ID, 100),
        (P0P1_UPGRADE_METHOD_ID, 1),
    ),
)
def test_wave9_enforces_effective_frozen_source_minimum(
    method_id: str,
    minimum: int,
) -> None:
    with pytest.raises(LegacySourceNativeWave9Error):
        generate_legacy_source_native_wave9_portfolio(
            LegacySourceNativeWave9Request(
                legacy_method_id=method_id,
                target_draw_number=str(minimum),
                history=_history(minimum - 1),
            )
        )


def test_wave9_frozen_seed_is_target_stable_and_exact() -> None:
    history = _history(240)
    first = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=P0P1_UPGRADE_METHOD_ID,
            target_draw_number="241",
            history=history,
            user_seed="evidence-a",
        )
    )
    second = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=P0P1_UPGRADE_METHOD_ID,
            target_draw_number="different-target",
            history=history,
            user_seed="evidence-b",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.randomness_used is True
    assert (
        first.metadata.randomness_reproduction
        == "FROZEN_SOURCE_LOCAL_SEED_EXACT"
    )
    assert "effective_rng_seed=282" in (
        first.metadata.source_runtime_parameters
    )
