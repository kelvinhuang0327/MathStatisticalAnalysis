"""Unit contracts for the eleventh frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave11 import (
    EXHAUSTIVE_NBET_METHOD_ID,
    MUST_HIT_METHOD_ID,
    LegacySourceNativeWave11Error,
    LegacySourceNativeWave11Request,
    generate_legacy_source_native_wave11_portfolio,
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
        (EXHAUSTIVE_NBET_METHOD_ID, 500, 65),
        (MUST_HIT_METHOD_ID, 50, 1),
    ),
)
def test_wave11_preserves_native_ticket_count_and_order(
    method_id: str,
    history_count: int,
    expected_count: int,
) -> None:
    result = generate_legacy_source_native_wave11_portfolio(
        LegacySourceNativeWave11Request(
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


def test_wave11_preserves_repeated_bets_and_excludes_only_baselines() -> None:
    result = generate_legacy_source_native_wave11_portfolio(
        LegacySourceNativeWave11Request(
            legacy_method_id=EXHAUSTIVE_NBET_METHOD_ID,
            target_draw_number="501",
            history=_history(500),
        )
    )

    assert len(result.metadata.source_combination_members) == 26
    assert result.metadata.source_candidate_ticket_counts == (
        *((2,) * 13),
        *((3,) * 13),
    )
    assert result.metadata.native_duplicate_ticket_count > 0
    assert result.tickets[0] == result.tickets[1]
    assert result.metadata.excluded_non_strategy_source_members == (
        "BIG_LOTTO_2BET:RANDOM_BASELINE",
        "BIG_LOTTO_3BET:RANDOM_BASELINE",
    )
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


def test_wave11_keeps_candidate_k_and_legal_ticket_count_distinct() -> None:
    result = generate_legacy_source_native_wave11_portfolio(
        LegacySourceNativeWave11Request(
            legacy_method_id=MUST_HIT_METHOD_ID,
            target_draw_number="51",
            history=_history(50),
        )
    )

    assert len(result.tickets) == 1
    assert result.metadata.source_candidate_ticket_counts == (1, 0, 0)
    assert result.metadata.source_candidate_k_values == (6, 10, 15)
    assert tuple(
        len(pool)
        for pool in result.metadata.source_candidate_number_pools
    ) == (6, 10, 15)
    assert result.tickets[0] == tuple(
        sorted(result.metadata.source_candidate_number_pools[0])
    )
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None


@pytest.mark.parametrize(
    ("method_id", "minimum"),
    (
        (EXHAUSTIVE_NBET_METHOD_ID, 500),
        (MUST_HIT_METHOD_ID, 50),
    ),
)
def test_wave11_enforces_effective_frozen_source_minimum(
    method_id: str,
    minimum: int,
) -> None:
    with pytest.raises(LegacySourceNativeWave11Error):
        generate_legacy_source_native_wave11_portfolio(
            LegacySourceNativeWave11Request(
                legacy_method_id=method_id,
                target_draw_number=str(minimum),
                history=_history(minimum - 1),
            )
        )


def test_wave11_sum_optimal_source_seed_is_request_independent() -> None:
    history = _history(500)
    first = generate_legacy_source_native_wave11_portfolio(
        LegacySourceNativeWave11Request(
            legacy_method_id=EXHAUSTIVE_NBET_METHOD_ID,
            target_draw_number="501",
            history=history,
            user_seed="evidence-a",
        )
    )
    second = generate_legacy_source_native_wave11_portfolio(
        LegacySourceNativeWave11Request(
            legacy_method_id=EXHAUSTIVE_NBET_METHOD_ID,
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
