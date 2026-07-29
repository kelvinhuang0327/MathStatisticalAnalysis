"""Unit contracts for the wave-60 seeded benchmark ticket ledger."""

from __future__ import annotations

from datetime import date

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_seeded_benchmark_native_portfolios_wave60 import (
    HYBRID_METHOD_ID,
    ORTHOGONAL_METHOD_ID,
    PINNED_DATASET_SHA256,
    SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS,
    ZONE_METHOD_ID,
    LegacySeededBenchmarkNativeWave60Request,
    LegacySeededBenchmarkNativeWave60SourceError,
    generate_legacy_seeded_benchmark_native_wave60_portfolio,
    load_legacy_seeded_benchmark_native_wave60_ledger_for_verification,
)

FIRST_DRAW = LegacyHistoryDraw(
    draw_number="96000001",
    numbers=(13, 21, 23, 27, 31, 49),
)


def _request(
    *,
    method_id: str,
    target_draw_number: str = "96000001",
    target_draw_date: date = date(2007, 1, 2),
    history: tuple[LegacyHistoryDraw, ...] = (),
) -> LegacySeededBenchmarkNativeWave60Request:
    return LegacySeededBenchmarkNativeWave60Request(
        legacy_method_id=method_id,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        history=history,
        dataset_sha256=PINNED_DATASET_SHA256,
    )


@pytest.mark.parametrize(
    "method_id",
    SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS,
)
def test_wave60_first_target_is_explicitly_closed(
    method_id: str,
) -> None:
    with pytest.raises(
        LegacySeededBenchmarkNativeWave60SourceError,
        match="NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF",
    ):
        generate_legacy_seeded_benchmark_native_wave60_portfolio(
            _request(method_id=method_id)
        )


@pytest.mark.parametrize(
    ("method_id", "expected_count", "first_ticket"),
    [
        (
            HYBRID_METHOD_ID,
            12,
            (1, 2, 3, 4, 5, 13),
        ),
        (
            ORTHOGONAL_METHOD_ID,
            35,
            (2, 8, 15, 16, 18, 41),
        ),
        (
            ZONE_METHOD_ID,
            18,
            (1, 4, 5, 12, 14, 16),
        ),
    ],
)
def test_wave60_replays_second_target_source_order(
    method_id: str,
    expected_count: int,
    first_ticket: tuple[int, int, int, int, int, int],
) -> None:
    result = generate_legacy_seeded_benchmark_native_wave60_portfolio(
        _request(
            method_id=method_id,
            target_draw_number="96000002",
            target_draw_date=date(2007, 1, 5),
            history=(FIRST_DRAW,),
        )
    )

    assert len(result.tickets) == expected_count
    assert result.tickets[0] == first_ticket
    assert result.metadata.history_draw_count == 1
    assert result.metadata.history_cutoff_draw_number == "96000001"
    assert result.metadata.source_history_order == "RECENT_FIRST"
    assert result.metadata.seed_integer == 42
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert (
        result.metadata.local_configuration_count
        in {4, 6, 14}
    )


def test_wave60_ledger_covers_all_targets_and_methods() -> None:
    ledger = (
        load_legacy_seeded_benchmark_native_wave60_ledger_for_verification()
    )

    assert len(ledger.targets) == 2149
    assert len(set(ledger.targets)) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert set(ledger.tickets_by_method) == set(
        SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
    )
